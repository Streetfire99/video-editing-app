import openai
import subprocess
import os
import json
import re
from datetime import timedelta
import pickle
import tempfile
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import google_auth_oauthlib.flow
import threading
import glob
import random
from google.auth.transport.requests import Request

def get_video_info(input_video):
    """Ottiene informazioni sul video per gestire meglio i codec"""
    try:
        import ffmpeg
        probe = ffmpeg.probe(input_video)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        audio_info = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
        
        return {
            'video_codec': video_info.get('codec_name', 'unknown'),
            'audio_codec': audio_info.get('codec_name', 'unknown') if audio_info else None,
            'width': int(video_info.get('width', 0)),
            'height': int(video_info.get('height', 0)),
            'duration': float(probe.get('format', {}).get('duration', 0))
        }
    except Exception as e:
        return None

# === CONFIG ===
def get_openai_client(api_key):
    """Inizializza il client OpenAI"""
    return openai.OpenAI(api_key=api_key)

def extract_audio_from_video(input_video, audio_file):
    """Estrae l'audio dal video"""
    print(f"🔧 DEBUG: extract_audio_from_video - input: {input_video}, output: {audio_file}")
    # Usa solo ffmpeg-python
    try:
        print("🔧 DEBUG: Importing ffmpeg...")
        import ffmpeg
        print("🔧 DEBUG: ffmpeg imported successfully")
        stream = ffmpeg.input(input_video)
        stream = ffmpeg.output(stream, audio_file, vn=None, ac=1, ar=16000, acodec='pcm_s16le')
        print("🔧 DEBUG: Running ffmpeg.run...")
        ffmpeg.run(stream, overwrite_output=True)
        print("🔧 DEBUG: ffmpeg.run completed successfully")
    except ImportError as e:
        print(f"❌ DEBUG: ImportError - {e}")
        raise Exception("ffmpeg-python non è disponibile. Installa ffmpeg-python.")
    except Exception as e:
        print(f"❌ DEBUG: Unexpected error in extract_audio_from_video - {e}")
        raise e
    return audio_file

def transcribe_audio(audio_file, client):
    """Trascrive l'audio usando Whisper API"""
    with open(audio_file, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json"
        )
    return transcript

def optimize_transcription(raw_transcription, client, custom_prompt=None, video_type=None):
    """Ottimizza la trascrizione con descrizione visiva"""
    
    # Prompt base per la tipologia di video
    base_prompt = "You are a video subtitle editor specializing in instructional videos."
    
    base_prompt += """
Your task is to optimize the following raw transcription of an instructional video. The video shows a person performing the actions described in the audio. Follow these steps:

1. Keep the text in Italian, as it is the original language.
2. Write short, complete sentences that describe exactly what is shown in the video.
3. Each sentence should be self-contained and not reference previous or next actions.
4. Avoid long explanations or multiple actions in one sentence.
5. Keep each line under 20 characters to prevent overlap.
6. Each subtitle should be exactly 2 lines maximum.
7. DO NOT add any prefix to the text - just write the Italian text as is.
8. DO NOT add periods, exclamation marks, or question marks at the end of sentences.
9. Provide the output as a JSON array of segments, where each segment has:
   - text: subtitle text in Italian (complete sentence, ready for subtitles)

Raw transcription:
{raw_transcription}

Example output:
[
  {{"text": "Apri lo sportello"}},
  {{"text": "Inserisci il bucato"}},
  {{"text": "Aggiungi il detersivo"}}
]
"""

    # Se c'è un prompt personalizzato, combinalo con quello base
    if custom_prompt:
        final_prompt = base_prompt + f"\n\nAdditional instructions:\n{custom_prompt}"
    else:
        final_prompt = base_prompt

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": final_prompt.format(raw_transcription=raw_transcription)}
        ],
        temperature=0.1
    )

    # Clean the response content before parsing JSON
    content = response.choices[0].message.content.strip()
    if content.startswith('```json'):
        content = content[7:]
    if content.endswith('```'):
        content = content[:-3]
    content = content.strip()

    # Parse JSON response
    try:
        optimized_texts = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Errore nel parsing della risposta JSON: {e}")
        print("Risposta ricevuta:", content)
        raise

    # Validate segments
    if not isinstance(optimized_texts, list):
        raise ValueError("La risposta di OpenAI non è una lista di segmenti")

            # Post-processing: assicurati che ogni testo sia adatto per i sottotitoli
        for segment in optimized_texts:
            if 'text' in segment:
                # Usa process_subtitle_text per coerenza
                lines = process_subtitle_text(segment['text'])
                # Ricombina in un singolo testo (le righe saranno separate da \n nel file SRT)
                segment['text'] = lines[0] + (f"\n{lines[1]}" if lines[1] else "")

    return optimized_texts

def format_timestamp(seconds):
    """Formatta i timestamp per SRT"""
    td = timedelta(seconds=seconds)
    millis = int((td.total_seconds() % 1) * 1000)
    return str(td).split('.')[0].replace('.', ',') + f',{millis:03d}'

def process_subtitle_text(text):
    """Processa il testo per i sottotitoli - funzione unificata"""
    if not text:
        return ["", ""]
    
    # Pulisci il testo aggressivamente da caratteri problematici
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').strip()
    
    # Rimuovi spazi multipli
    import re
    text = re.sub(r'\s+', ' ', text)
    
    # Rimuovi punti, esclamazioni e domande finali
    text = text.rstrip('.!?')
    
    # Se il testo è troppo lungo, troncalo
    if len(text) > 40:  # 2 righe x 20 caratteri
        text = text[:37] + "..."
    
    # Usa split_text per garantire sempre 2 righe
    return split_text(text, max_length=25, max_lines=2)

def split_text(text, max_length=25, max_lines=2):
    """Divide il testo per i sottotitoli - versione che funzionava bene"""
    # First, try to split on natural sentence boundaries
    import re
    sentences = re.split(r'([.!?])\s+', text)
    # Recombine the punctuation with the sentences
    sentences = [''.join(i) for i in zip(sentences[::2], sentences[1::2] + [''])]
    
    lines = []
    current_line = []
    current_length = 0
    
    for sentence in sentences:
        words = sentence.split()
        for word in words:
            if current_length + len(word) + 1 <= max_length:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word) + 1
    
    if current_line:
        lines.append(' '.join(current_line))
    
    # If we have more than 2 lines, try to combine them intelligently
    if len(lines) > max_lines:
        # Try to combine lines while respecting sentence boundaries
        combined = []
        current = []
        current_length = 0
        
        for line in lines:
            if current_length + len(line) + 1 <= max_length:
                current.append(line)
                current_length += len(line) + 1
            else:
                if current:
                    combined.append(' '.join(current))
                current = [line]
                current_length = len(line) + 1
        
        if current:
            combined.append(' '.join(current))
        
        lines = combined[:max_lines]
    
    return lines[:max_lines]

def distribute_subtitles(segments, texts):
    """Distribuisce i sottotitoli in modo uniforme"""
    total_duration = segments[-1].end
    num_subtitles = len(texts)
    duration_per_subtitle = total_duration / num_subtitles
    
    distributed_segments = []
    for i in range(num_subtitles):
        start_time = i * duration_per_subtitle
        end_time = (i + 1) * duration_per_subtitle
        
        distributed_segments.append({
            'start': start_time,
            'end': end_time,
            'text': texts[i]['text']
        })
    
    return distributed_segments

def create_srt_file(segments, output_file, language="IT"):
    """Crea file SRT con controllo diretto del testo"""
    with open(output_file, "w", encoding="utf-8") as srt:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            # Usa il testo appropriato in base alla lingua
            if language == "IT":
                text = segment['text']
                prefix = "[IT] "
            else:
                text = segment.get('text_en', segment['text'])  # Fallback al testo italiano se non c'è inglese
                prefix = "[EN] "
            
            # CONTROLLO DIRETTO DEL TESTO - Forza massimo 2 righe
            max_chars_per_line = 20  # Ridotto per sicurezza
            
            if len(text) > max_chars_per_line:
                # Dividi in modo intelligente
                words = text.split()
                lines = []
                current_line = ""
                
                for word in words:
                    test_line = current_line + (" " + word) if current_line else word
                    if len(test_line) <= max_chars_per_line:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                
                if current_line:
                    lines.append(current_line)
                
                # Assicurati di avere massimo 2 righe
                if len(lines) > 2:
                    # Combina le righe in eccesso
                    lines = [lines[0], " ".join(lines[1:])]
                    # Tronca se ancora troppo lungo
                    if len(lines[1]) > max_chars_per_line:
                        lines[1] = lines[1][:max_chars_per_line-3] + "..."
                
                # Unisci le righe con \n
                text = "\\N".join(lines)
            
            srt.write(f"{i}\n{start} --> {end}\n{prefix}{text}\n\n")

def read_srt_file(srt_file):
    """Legge un file SRT e restituisce una lista di (start_time, end_time, text)"""
    subtitles = []
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parsing del file SRT
    blocks = content.strip().split('\n\n')
    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            # Ignora il numero del sottotitolo (prima riga)
            time_line = lines[1]
            text = '\n'.join(lines[2:])
            
            # Parsing del timestamp
            if ' --> ' in time_line:
                start_str, end_str = time_line.split(' --> ')
                start_time = parse_timestamp(start_str)
                end_time = parse_timestamp(end_str)
                
                subtitles.append((start_time, end_time, text))
    
    return subtitles

def parse_timestamp(timestamp_str):
    """Converte un timestamp SRT in secondi"""
    # Formato: HH:MM:SS,mmm
    time_parts = timestamp_str.replace(',', '.').split(':')
    hours = int(time_parts[0])
    minutes = int(time_parts[1])
    seconds = float(time_parts[2])
    
    return hours * 3600 + minutes * 60 + seconds

def create_ass_file(segments, output_file, language="IT", margin_v=85, video_width=478, video_height=850):
    """Crea file ASS con posizione specifica"""
    with open(output_file, "w", encoding="utf-8") as ass:
        # Header ASS
        ass.write("[Script Info]\n")
        ass.write("Title: Subtitles\n")
        ass.write("ScriptType: v4.00+\n")
        ass.write("WrapStyle: 1\n")
        ass.write("ScaledBorderAndShadow: yes\n")
        ass.write(f"PlayResX: {video_width}\n")
        ass.write(f"PlayResY: {video_height}\n\n")
        
        # Stili
        ass.write("[V4+ Styles]\n")
        ass.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        ass.write(f"Style: Default,Arial,18,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,100,100,{margin_v},1\n\n")
        
        # Eventi
        ass.write("[Events]\n")
        ass.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            # Usa il testo appropriato in base alla lingua
            if language == "IT":
                text = segment['text']
            else:
                text = segment.get('text_en', segment['text'])
            
            # Usa split_text direttamente
            lines = split_text(text)
            full_text = lines[0]
            if lines[1]:
                full_text += "\\N" + lines[1]
            
            ass.write(f"Dialogue: 0,{start},{end},Default,,100,100,0,,{full_text}\n")

def create_ass_file_from_srt(srt_file, ass_file, margin_v=85, video_width=478, video_height=850):
    """Converte un file SRT in ASS con posizione specifica e risolve sovrapposizioni temporali"""
    with open(srt_file, 'r', encoding='utf-8') as srt, open(ass_file, 'w', encoding='utf-8') as ass:
        # Header ASS
        ass.write("[Script Info]\n")
        ass.write("Title: Subtitles\n")
        ass.write("ScriptType: v4.00+\n")
        ass.write("WrapStyle: 1\n")
        ass.write("ScaledBorderAndShadow: yes\n")
        ass.write(f"PlayResX: {video_width}\n")
        ass.write(f"PlayResY: {video_height}\n\n")
        
        # Stili
        ass.write("[V4+ Styles]\n")
        ass.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        ass.write(f"Style: Default,Arial,18,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,100,100,{margin_v},1\n\n")
        
        # Eventi
        ass.write("[Events]\n")
        ass.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        lines = srt.readlines()
        i = 0
        segments = []
        
        # Prima leggi tutti i segmenti
        while i < len(lines):
            line = lines[i].strip()
            if line.isdigit():  # Numero del sottotitolo
                i += 1
                if i < len(lines):
                    timestamp_line = lines[i].strip()
                    if ' --> ' in timestamp_line:
                        start, end = timestamp_line.split(' --> ')
                        # Converti formato timestamp
                        start = start.replace(',', '.')
                        end = end.replace(',', '.')
                        
                        i += 1
                        text_lines = []
                        while i < len(lines) and lines[i].strip():
                            text_lines.append(lines[i].strip())
                            i += 1
                        
                        if text_lines:
                            full_text = text_lines[0]
                            if len(text_lines) > 1:
                                full_text += "\\N" + text_lines[1]
                            
                            segments.append({
                                'start': start,
                                'end': end,
                                'text': full_text
                            })
            i += 1
        
        # Risolvi sovrapposizioni temporali
        for j in range(len(segments) - 1):
            current_end = float(segments[j]['end'])
            next_start = float(segments[j + 1]['start'])
            
            # Se c'è sovrapposizione, riduci la durata del primo
            if next_start < current_end:
                new_end = next_start - 0.5  # Lascia 0.5 secondi di gap
                segments[j]['end'] = f"{new_end:.3f}"
        
        # Scrivi i segmenti risolti
        for segment in segments:
            ass.write(f"Dialogue: 0,{segment['start']},{segment['end']},Default,,100,100,0,,{segment['text']}\n")

def create_unified_srt_file(segments, output_file):
    """Crea file SRT unificato con italiano e inglese insieme"""
    with open(output_file, "w", encoding="utf-8") as srt:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            # Testo italiano
            italian_text = segment['text']
            italian_lines = split_text(italian_text)
            
            # Testo inglese
            english_text = segment.get('text_en', '')
            english_lines = split_text(english_text) if english_text else ['', '']
            
            # Scrivi il formato unificato
            srt.write(f"{i}\n{start} --> {end}\n")
            srt.write(f"[IT] {italian_lines[0]}\n")
            if italian_lines[1]:
                srt.write(f"{italian_lines[1]}\n")
            srt.write(f"[EN] {english_lines[0]}\n")
            if english_lines[1]:
                srt.write(f"{english_lines[1]}\n")
            srt.write("\n")

def translate_subtitles(segments, client, output_file, video_type=None):
    """Traduce i sottotitoli in inglese - identica al test che funzionava"""
    
    # Prompt di traduzione per la tipologia di video
    translation_prompt = "You are a translator specializing in instructional videos."
    
    translation_prompt += """
Translate the following Italian text to English, ensuring:
- The translation is clear, concise, and suitable for subtitles.
- Use an imperative tone, avoiding questions or incomplete sentences.
- Keep each line under 20 characters to prevent overlap.
- IMPORTANT: Always translate to English, never leave any Italian text.
- DO NOT add any prefix to the translation.
"""
    
    with open(output_file, "w", encoding="utf-8") as srt:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            # Usa il testo originale senza prefissi
            text_to_translate = segment['text']
            
            translation = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": translation_prompt},
                    {"role": "user", "content": text_to_translate}
                ]
            )
            text = translation.choices[0].message.content.strip()
            
            # Rimuovi punti, esclamazioni e domande finali
            text = text.rstrip('.!?')
            
            # Aggiungi il testo inglese al segmento
            segment['text_en'] = text
            
            # Usa il testo direttamente senza process_subtitle_text (come nel test)
            srt.write(f"{i}\n{start} --> {end}\n[EN] {text}\n\n")

def add_background_music(input_video, music_file, output_video):
    """Aggiunge musica di sottofondo"""
    print(f"🔧 DEBUG: add_background_music - input: {input_video}, music: {music_file}, output: {output_video}")
    # Usa solo ffmpeg-python
    try:
        print("🔧 DEBUG: Importing ffmpeg for background music...")
        import ffmpeg
        print("🔧 DEBUG: ffmpeg imported successfully for background music")
        input_stream = ffmpeg.input(input_video)
        music_stream = ffmpeg.input(music_file, stream_loop=-1)
        stream = ffmpeg.output(
            input_stream['v'],
            ffmpeg.filter(music_stream['a'], 'volume', 0.7),
            output_video,
            shortest=None,
            vcodec='libx264',
            acodec='aac',
            preset='medium',
            crf=18,
            pix_fmt='yuv420p'
        )
        print("🔧 DEBUG: Running ffmpeg.run for background music...")
        ffmpeg.run(stream, overwrite_output=True)
        print("🔧 DEBUG: Background music added successfully")
    except ImportError as e:
        print(f"❌ DEBUG: ImportError in add_background_music - {e}")
        raise Exception("ffmpeg-python non è disponibile. Installa ffmpeg-python.")
    except Exception as e:
        print(f"❌ DEBUG: Unexpected error in add_background_music - {e}")
        raise e



def add_subtitles_to_video(input_video, subtitle_file_it, subtitle_file_en, output_video, italian_height=120, english_height=60):
    """Aggiunge sottotitoli duali al video"""
    print(f"🔧 DEBUG: add_subtitles_to_video - input: {input_video}, it_subs: {subtitle_file_it}, en_subs: {subtitle_file_en}, output: {output_video}, it_height: {italian_height}, en_height: {english_height}")
    
    # Verifica che i file SRT esistano
    if not os.path.exists(subtitle_file_it):
        print(f"❌ DEBUG: Italian SRT file NOT found: {subtitle_file_it}")
        raise FileNotFoundError(f"File SRT italiano non trovato: {subtitle_file_it}")
    else:
        print(f"✅ DEBUG: Italian SRT file exists: {os.path.getsize(subtitle_file_it)} bytes")
    
    if not os.path.exists(subtitle_file_en):
        print(f"❌ DEBUG: English SRT file NOT found: {subtitle_file_en}")
        raise FileNotFoundError(f"File SRT inglese non trovato: {subtitle_file_en}")
    else:
        print(f"✅ DEBUG: English SRT file exists: {os.path.getsize(subtitle_file_en)} bytes")
    
    try:
        print("🔧 DEBUG: Importing ffmpeg for subtitles...")
        import ffmpeg
        print("🔧 DEBUG: ffmpeg imported successfully for subtitles")
        
        # Ottieni informazioni sul video per gestire meglio i codec
        video_info = get_video_info(input_video)
        print(f"🔧 DEBUG: Video codec detected: {video_info['video_codec'] if video_info else 'unknown'}")
        
        # Aggiungi entrambi i sottotitoli in un unico passaggio
        print("🔧 DEBUG: Adding both subtitles in single pass...")
        
        # Rimuovi il file di output se esiste già
        if os.path.exists(output_video):
            os.remove(output_video)
            print("🔧 DEBUG: Removed existing output file")
        
        stream = ffmpeg.input(input_video)
        
        # Ottieni le dimensioni del video per debug
        video_width = 478
        video_height = 850
        if video_info and 'width' in video_info and 'height' in video_info:
            video_width = video_info['width']
            video_height = video_info['height']
            print(f"🔧 DEBUG: Video dimensions: {video_width}x{video_height}")
        else:
            print(f"🔧 DEBUG: Using default dimensions: {video_width}x{video_height}")
        
        # NUOVO APPROCCIO: Usa drawtext per controllo diretto del posizionamento
        # Leggi i file SRT e crea i testi per drawtext
        italian_texts = read_srt_file(subtitle_file_it)
        english_texts = read_srt_file(subtitle_file_en)
        
        # Crea il filtro drawtext per ogni sottotitolo
        drawtext_filters = []
        
        # Aggiungi sottotitoli italiani
        for i, (start_time, end_time, text) in enumerate(italian_texts):
            # Calcola la posizione Y per l'italiano
            y_pos = video_height - italian_height
            # Escape dei caratteri speciali per drawtext
            text_escaped = text.replace("'", "\\'").replace('"', '\\"')
            drawtext_filters.append(f"drawtext=text='{text_escaped}':fontsize=14:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=2:x=(w-text_w)/2:y={y_pos}:enable='between(t,{start_time},{end_time})'")
        
        # Aggiungi sottotitoli inglesi
        for i, (start_time, end_time, text) in enumerate(english_texts):
            # Calcola la posizione Y per l'inglese (sopra l'italiano)
            y_pos = video_height - english_height
            # Escape dei caratteri speciali per drawtext
            text_escaped = text.replace("'", "\\'").replace('"', '\\"')
            drawtext_filters.append(f"drawtext=text='{text_escaped}':fontsize=14:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=2:x=(w-text_w)/2:y={y_pos}:enable='between(t,{start_time},{end_time})'")
        
        # Combina tutti i filtri drawtext
        vf_filter = ",".join(drawtext_filters)
        
        stream = ffmpeg.output(
            stream,
            output_video,
            vf=vf_filter,
            vcodec='libx264',
            acodec='aac',
            preset='medium',
            crf=18,
            pix_fmt='yuv420p'
        )
        ffmpeg.run(stream, overwrite_output=True)
        print("🔧 DEBUG: Drawtext subtitles added successfully")


            
    except ImportError as e:
        print(f"❌ DEBUG: ImportError in add_subtitles_to_video - {e}")
        raise Exception("ffmpeg-python non è disponibile. Installa ffmpeg-python.")
    except Exception as e:
        print(f"❌ DEBUG: Unexpected error in add_subtitles_to_video - {e}")
        # Fallback per video problematici
        print("🔧 DEBUG: Trying fallback method for problematic video...")
        try:
            import ffmpeg
            # Metodo alternativo: prima converti il video, poi aggiungi i sottotitoli
            stream = ffmpeg.input(input_video)
            stream = ffmpeg.output(stream, "temp_converted.mp4", vcodec='libx264', acodec='aac', preset='fast', crf=25)
            ffmpeg.run(stream, overwrite_output=True)
    
            # Ora aggiungi i sottotitoli al video convertito
            stream = ffmpeg.input("temp_converted.mp4")
            stream = ffmpeg.output(
                stream,
                output_video,
                vf=f"subtitles={subtitle_file_it}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={italian_height},MarginL=50,MarginR=50',subtitles={subtitle_file_en}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={english_height},MarginL=50,MarginR=50'",
                vcodec='libx264',
                acodec='aac',
                preset='medium',
                crf=18,
                pix_fmt='yuv420p'
            )
            ffmpeg.run(stream, overwrite_output=True)
            
            # Rimuovi i file temporanei
            if os.path.exists("temp_converted.mp4"):
                os.remove("temp_converted.mp4")
            print("🔧 DEBUG: Fallback method completed successfully")
        except Exception as fallback_error:
            print(f"❌ DEBUG: Fallback method also failed - {fallback_error}")
            raise e  # Rilancia l'errore originale

def create_fixed_position_ass_file(segments, output_file, language="IT", margin_v=85, video_width=478, video_height=850):
    """Crea file ASS con posizione fissa - SOLUZIONE MIGLIORATA"""
    with open(output_file, "w", encoding="utf-8") as ass:
        # Header ASS
        ass.write("[Script Info]\n")
        ass.write("Title: Fixed Position Subtitles\n")
        ass.write("ScriptType: v4.00+\n")
        ass.write("WrapStyle: 0\n")  # NO WRAPPING - Forza testo su una riga
        ass.write("ScaledBorderAndShadow: yes\n")
        ass.write(f"PlayResX: {video_width}\n")
        ass.write(f"PlayResY: {video_height}\n\n")
        
        # Stili - Margini più ampi e font più grande
        ass.write("[V4+ Styles]\n")
        ass.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        
        # Stile con margini più ampi (200 invece di 50) e font più grande (18 invece di 16)
        ass.write(f"Style: Default,Arial,18,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,200,200,{margin_v},1\n\n")
        
        # Eventi
        ass.write("[Events]\n")
        ass.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            # Usa il testo appropriato in base alla lingua
            if language == "IT":
                text = segment['text']
                prefix = "[IT] "
            else:
                text = segment.get('text_en', segment['text'])
                prefix = "[EN] "
            
            # Pulisci il testo da caratteri problematici
            text = text.replace("\n", "").replace("\r", "").strip()
            
            # Gestione intelligente del testo lungo
            max_chars_per_line = 25  # Ridotto per sicurezza
            if len(text) > max_chars_per_line:
                # Dividi in modo intelligente mantenendo le parole intere
                words = text.split()
                lines = []
                current_line = ""
                
                for word in words:
                    test_line = current_line + (" " + word) if current_line else word
                    if len(test_line) <= max_chars_per_line:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                
                if current_line:
                    lines.append(current_line)
                
                # Assicurati di avere massimo 2 righe
                if len(lines) > 2:
                    # Combina le righe in eccesso
                    lines = [lines[0], " ".join(lines[1:])]
                    # Tronca se ancora troppo lungo
                    if len(lines[1]) > max_chars_per_line:
                        lines[1] = lines[1][:max_chars_per_line-3] + "..."
                
                full_text = "\\N".join(lines)
            else:
                full_text = text
            
            ass.write(f"Dialogue: 0,{start},{end},Default,,200,200,0,,{prefix}{full_text}\n")

def add_subtitles_with_fixed_position(input_video, subtitle_file_it, subtitle_file_en, output_video):
    """Aggiunge sottotitoli con posizione fissa usando il filtro ass"""
    print(f"🔧 DEBUG: add_subtitles_with_fixed_position - input: {input_video}, it_subs: {subtitle_file_it}, en_subs: {subtitle_file_en}, output: {output_video}")
    
    # Verifica che i file ASS esistano
    if not os.path.exists(subtitle_file_it):
        print(f"❌ DEBUG: Italian ASS file NOT found: {subtitle_file_it}")
        raise FileNotFoundError(f"File ASS italiano non trovato: {subtitle_file_it}")
    
    if not os.path.exists(subtitle_file_en):
        print(f"❌ DEBUG: English ASS file NOT found: {subtitle_file_en}")
        raise FileNotFoundError(f"File ASS inglese non trovato: {subtitle_file_en}")
    
    try:
        import ffmpeg
        
        # Ottieni informazioni sul video
        video_info = get_video_info(input_video)
        video_width = video_info['width'] if video_info else 478
        video_height = video_info['height'] if video_info else 850
        
        print(f"🔧 DEBUG: Video dimensions: {video_width}x{video_height}")
        
        # Rimuovi il file di output se esiste già
        if os.path.exists(output_video):
            os.remove(output_video)
        
        stream = ffmpeg.input(input_video)
        
        # Usa il filtro ass per controllo completo della posizione
        stream = ffmpeg.output(
            stream,
            output_video,
            vf=f"ass={subtitle_file_it},ass={subtitle_file_en}",
            vcodec='libx264',
            acodec='aac',
            preset='medium',
            crf=18,
            pix_fmt='yuv420p'
        )
        
        ffmpeg.run(stream, overwrite_output=True)
        print("🔧 DEBUG: Fixed position subtitles added successfully")
        
    except Exception as e:
        print(f"❌ DEBUG: Error in add_subtitles_with_fixed_position - {e}")
        raise e

def add_subtitles_with_subtitles_filter(input_video, subtitle_file_it, subtitle_file_en, output_video, italian_height=120, english_height=60):
    """Aggiunge sottotitoli usando il filtro subtitles (più stabile)"""
    print(f"🔧 DEBUG: add_subtitles_with_subtitles_filter - input: {input_video}, it_subs: {subtitle_file_it}, en_subs: {subtitle_file_en}, output: {output_video}")
    
    try:
        import ffmpeg
        
        # Rimuovi il file di output se esiste già
        if os.path.exists(output_video):
            os.remove(output_video)
        
        stream = ffmpeg.input(input_video)
        
        # Usa il filtro subtitles con WrapStyle=0 per evitare wrapping
        vf = f"subtitles={subtitle_file_it}:force_style='FontSize=18,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={italian_height},MarginL=200,MarginR=200,WrapStyle=0',subtitles={subtitle_file_en}:force_style='FontSize=18,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={english_height},MarginL=200,MarginR=200,WrapStyle=0'"
        
        stream = ffmpeg.output(
            stream,
            output_video,
            vf=vf,
            vcodec='libx264',
            acodec='aac',
            preset='medium',
            crf=18,
            pix_fmt='yuv420p'
        )
        
        ffmpeg.run(stream, overwrite_output=True)
        print("🔧 DEBUG: Subtitles filter subtitles added successfully")
        
    except Exception as e:
        print(f"❌ DEBUG: Error in add_subtitles_with_subtitles_filter - {e}")
        raise e

def create_dual_ass_files(segments, output_file_it, output_file_en, video_width=478, video_height=850):
    """Crea file ASS separati per italiano e inglese con posizione fissa"""
    print(f"🔧 DEBUG: create_dual_ass_files - it: {output_file_it}, en: {output_file_en}")
    
    # Crea file ASS italiano
    create_fixed_position_ass_file(segments, output_file_it, "IT", margin_v=120, video_width=video_width, video_height=video_height)
    
    # Crea file ASS inglese
    create_fixed_position_ass_file(segments, output_file_en, "EN", margin_v=60, video_width=video_width, video_height=video_height)
    
    print("🔧 DEBUG: Dual ASS files created successfully")

def create_customizable_ass_file(segments, output_file, language="IT", margin_v=85, video_width=478, video_height=850, font_size=16):
    """Crea file ASS con parametri personalizzabili"""
    with open(output_file, "w", encoding="utf-8") as ass:
        # Header ASS
        ass.write("[Script Info]\n")
        ass.write("Title: Customizable Subtitles\n")
        ass.write("ScriptType: v4.00+\n")
        ass.write("WrapStyle: 0\n")  # No wrapping
        ass.write("ScaledBorderAndShadow: yes\n")
        ass.write(f"PlayResX: {video_width}\n")
        ass.write(f"PlayResY: {video_height}\n\n")
        
        # Stili con parametri personalizzabili
        ass.write("[V4+ Styles]\n")
        ass.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        
        # Stile personalizzabile
        ass.write(f"Style: Custom,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,50,50,{margin_v},1\n\n")
        
        # Eventi
        ass.write("[Events]\n")
        ass.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            # Usa il testo appropriato in base alla lingua
            if language == "IT":
                text = segment['text']
            else:
                text = segment.get('text_en', segment['text'])
            
            # Assicurati che il testo sia su massimo 2 righe
            lines = split_text(text, max_length=20, max_lines=2)
            full_text = lines[0]
            if lines[1]:
                full_text += "\\N" + lines[1]
            
            ass.write(f"Dialogue: 0,{start},{end},Custom,,0,0,0,,{full_text}\n")

def modify_subtitle_height(ass_file, new_margin_v, new_font_size=None):
    """Modifica l'altezza e dimensione font di un file ASS esistente"""
    print(f"🔧 DEBUG: modify_subtitle_height - file: {ass_file}, new_margin: {new_margin_v}, new_font: {new_font_size}")
    
    try:
        # Leggi il file ASS
        with open(ass_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Modifica il MarginV
        import re
        content = re.sub(r'MarginV,\d+', f'MarginV,{new_margin_v}', content)
        
        # Modifica il FontSize se specificato
        if new_font_size:
            content = re.sub(r'Fontsize,\d+', f'Fontsize,{new_font_size}', content)
        
        # Scrivi il file modificato
        with open(ass_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ File ASS modificato: margin_v={new_margin_v}, font_size={new_font_size}")
        
    except Exception as e:
        print(f"❌ Errore modifica file ASS: {e}")
        raise e

def create_dual_ass_with_custom_height(segments, output_file_it, output_file_en, video_width=478, video_height=850, italian_height=120, english_height=60, font_size=16):
    """Crea file ASS duali con altezza personalizzabile"""
    print(f"🔧 DEBUG: create_dual_ass_with_custom_height - it_height: {italian_height}, en_height: {english_height}, font_size: {font_size}")
    
    # Crea file ASS italiano
    create_customizable_ass_file(segments, output_file_it, "IT", italian_height, video_width, video_height, font_size)
    
    # Crea file ASS inglese
    create_customizable_ass_file(segments, output_file_en, "EN", english_height, video_width, video_height, font_size)
    
    print("✅ File ASS duali creati con altezza personalizzabile")

def process_video(input_video, music_file, openai_api_key, output_dir=".", custom_prompt=None, video_type=None, italian_height=120, english_height=60):
    """Funzione principale per elaborare il video"""
    print(f"🔧 DEBUG: process_video started - input: {input_video}, music: {music_file}, output_dir: {output_dir}, it_height: {italian_height}, en_height: {english_height}")
    
    # Configura file di output
    audio_file = os.path.join(output_dir, "audio.wav")
    subtitle_file_it = os.path.join(output_dir, "subtitles_it.srt")
    subtitle_file_en = os.path.join(output_dir, "subtitles_en.srt")
    video_with_music = os.path.join(output_dir, "video_with_music.mp4")
    final_output = os.path.join(output_dir, "final_output.mp4")
    
    print(f"🔧 DEBUG: Output files - audio: {audio_file}, it_subs: {subtitle_file_it}, en_subs: {subtitle_file_en}, video_music: {video_with_music}, final: {final_output}")
    
    # Ottieni informazioni sul video
    video_info = get_video_info(input_video)
    if video_info:
        print(f"🔧 DEBUG: Video info - codec: {video_info['video_codec']}, audio: {video_info['audio_codec']}, size: {video_info['width']}x{video_info['height']}")
    
    # Inizializza client OpenAI
    client = get_openai_client(openai_api_key)
    
    try:
        print("🔧 DEBUG: Starting video processing steps...")
        
        # 1. Estrai l'audio dal video
        print("🔧 DEBUG: Step 1 - Extracting audio...")
        extract_audio_from_video(input_video, audio_file)
        print("🔧 DEBUG: Step 1 completed - Audio extracted")
        
        # 2. Trascrivi l'audio
        print("🔧 DEBUG: Step 2 - Transcribing audio...")
        transcript = transcribe_audio(audio_file, client)
        print("🔧 DEBUG: Step 2 completed - Audio transcribed")
        
        # Controlla se il video ha voce
        raw_transcription = "\n".join([seg.text for seg in transcript.segments])
        if not raw_transcription.strip():
            print("🔧 DEBUG: No voice detected in video, skipping subtitles")
            # Video senza voce - salta i sottotitoli
            distributed_segments = []
            has_voice = False
        else:
            # 3. Ottimizza la trascrizione
            print("🔧 DEBUG: Step 3 - Optimizing transcription...")
            optimized_texts = optimize_transcription(raw_transcription, client, custom_prompt, video_type)
            print("🔧 DEBUG: Step 3 completed - Transcription optimized")
            
            # 4. Distribuisci i sottotitoli
            print("🔧 DEBUG: Step 4 - Distributing subtitles...")
            distributed_segments = distribute_subtitles(transcript.segments, optimized_texts)
            print("🔧 DEBUG: Step 4 completed - Subtitles distributed")
            
            # 5. Crea file SRT italiani
            print("🔧 DEBUG: Step 5 - Creating Italian SRT file...")
            create_srt_file(distributed_segments, subtitle_file_it, "IT")
            print(f"🔧 DEBUG: Step 5 completed - Italian SRT created at {subtitle_file_it}")
            # Verifica che il file sia stato creato
            if os.path.exists(subtitle_file_it):
                print(f"✅ DEBUG: Italian SRT file exists: {os.path.getsize(subtitle_file_it)} bytes")
            else:
                print(f"❌ DEBUG: Italian SRT file NOT found: {subtitle_file_it}")
            
            # 6. Traduci e crea file SRT inglesi
            print("🔧 DEBUG: Step 6 - Creating English SRT file...")
            translate_subtitles(distributed_segments, client, subtitle_file_en, video_type)
            print(f"🔧 DEBUG: Step 6 completed - English SRT created at {subtitle_file_en}")
            # Verifica che il file sia stato creato
            if os.path.exists(subtitle_file_en):
                print(f"✅ DEBUG: English SRT file exists: {os.path.getsize(subtitle_file_en)} bytes")
            else:
                print(f"❌ DEBUG: English SRT file NOT found: {subtitle_file_en}")
            has_voice = True
        
        # 7. Aggiungi musica di sottofondo
        print("🔧 DEBUG: Step 7 - Adding background music...")
        if music_file:
            add_background_music(input_video, music_file, video_with_music)
        else:
            # Se non c'è musica, copia il video originale
            print(f"🔧 DEBUG: No music file, copying video - input: {input_video}, output: {video_with_music}")
            try:
                print("🔧 DEBUG: Importing ffmpeg for video copy...")
                import ffmpeg
                print("🔧 DEBUG: ffmpeg imported successfully for video copy")
                stream = ffmpeg.input(input_video)
                stream = ffmpeg.output(stream, video_with_music, vcodec='libx264', acodec='aac', preset='medium', crf=23)
                print("🔧 DEBUG: Running ffmpeg.run for video copy...")
                ffmpeg.run(stream, overwrite_output=True)
                print("🔧 DEBUG: Video copy completed successfully")
            except ImportError as e:
                print(f"❌ DEBUG: ImportError in video copy - {e}")
                raise Exception("ffmpeg-python non è disponibile. Installa ffmpeg-python.")
            except Exception as e:
                print(f"❌ DEBUG: Unexpected error in video copy - {e}")
                raise e
        print("🔧 DEBUG: Step 7 completed - Background music/video copy done")
        
        # 8. Aggiungi sottotitoli duali (solo se c'è voce)
        if has_voice:
            print("🔧 DEBUG: Step 8 - Adding subtitles...")
            add_subtitles_to_video(video_with_music, subtitle_file_it, subtitle_file_en, final_output, italian_height=italian_height, english_height=english_height)
            print("🔧 DEBUG: Step 8 completed - Subtitles added")
        else:
            print("🔧 DEBUG: Step 8 - No voice detected, copying video without subtitles...")
            # Copia il video senza sottotitoli
            try:
                import ffmpeg
                stream = ffmpeg.input(video_with_music)
                stream = ffmpeg.output(stream, final_output, vcodec='libx264', acodec='aac', preset='medium', crf=23)
                ffmpeg.run(stream, overwrite_output=True)
                print("🔧 DEBUG: Video copied without subtitles")
            except Exception as e:
                print(f"❌ DEBUG: Error copying video without subtitles - {e}")
                raise e
        
        print("🔧 DEBUG: All steps completed successfully!")
        return {
            "success": True,
            "final_video": final_output,
            "video_with_music": video_with_music,
            "subtitles_it": subtitle_file_it if has_voice else None,
            "subtitles_en": subtitle_file_en if has_voice else None,
            "transcript": raw_transcription,
            "segments": distributed_segments,
            "has_voice": has_voice
        }
        
    except Exception as e:
        print(f"❌ DEBUG: Error in process_video - {e}")
        print(f"❌ DEBUG: Error type - {type(e)}")
        import traceback
        print(f"❌ DEBUG: Traceback - {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e)
        }

def generate_subtitles_only(input_video, openai_api_key, output_dir=".", custom_prompt=None, video_type=None):
    """Genera solo i sottotitoli senza elaborare il video finale"""
    print(f"🔧 DEBUG: generate_subtitles_only - input: {input_video}, output_dir: {output_dir}")
    
    try:
        # Inizializza il client OpenAI
        client = get_openai_client(openai_api_key)
        
        # Crea directory di output se non esiste
        os.makedirs(output_dir, exist_ok=True)
        
        # Estrai l'audio dal video
        print("🔧 DEBUG: Extracting audio...")
        audio_file = os.path.join(output_dir, "temp_audio.wav")
        extract_audio_from_video(input_video, audio_file)
        
        # Trascrivi l'audio
        print("🔧 DEBUG: Transcribing audio...")
        transcript = transcribe_audio(audio_file, client)
        
        # Verifica se c'è audio nel video
        if not transcript.segments:
            print("🔧 DEBUG: No audio segments found")
            return {
                'success': False,
                'error': 'Nessun audio rilevato nel video',
                'has_voice': False
            }
        
        # Ottimizza la trascrizione
        print("🔧 DEBUG: Optimizing transcription...")
        optimized_segments = optimize_transcription(transcript.segments, client, custom_prompt, video_type)
        
        # Traduci i sottotitoli in inglese
        print("🔧 DEBUG: Translating subtitles...")
        srt_en_file = os.path.join(output_dir, "subtitles_en.srt")
        translate_subtitles(optimized_segments, client, srt_en_file, video_type)
        
        # Crea file SRT italiano
        print("🔧 DEBUG: Creating Italian SRT file...")
        srt_it_file = os.path.join(output_dir, "subtitles_it.srt")
        create_srt_file(optimized_segments, srt_it_file, "IT")
        
        # Pulisci il file audio temporaneo
        if os.path.exists(audio_file):
            os.remove(audio_file)
        
        return {
            'success': True,
            'segments': optimized_segments,
            'srt_it_file': srt_it_file,
            'srt_en_file': srt_en_file,
            'has_voice': True,
            'input_video': input_video
        }
        
    except Exception as e:
        print(f"❌ DEBUG: Error in generate_subtitles_only - {e}")
        return {
            'success': False,
            'error': str(e),
            'has_voice': False
        }

def finalize_video_processing(input_video, srt_it_file, srt_en_file, output_dir, italian_height=120, english_height=60):
    """Completa l'elaborazione del video usando i sottotitoli già generati"""
    print(f"🔧 DEBUG: finalize_video_processing - input: {input_video}, it_srt: {srt_it_file}, en_srt: {srt_en_file}")
    
    try:
        # Percorso del file musica
        music_file = os.path.join("Elaborazione", "audio.mp3")
        
        # Aggiungi musica di sottofondo
        print("🔧 DEBUG: Adding background music...")
        video_with_music = os.path.join(output_dir, "video_with_music.mp4")
        add_background_music(input_video, music_file, video_with_music)
        
        # Aggiungi sottotitoli
        print("🔧 DEBUG: Adding subtitles...")
        final_video = os.path.join(output_dir, "final_video.mp4")
        add_subtitles_to_video(
            input_video=video_with_music,
            subtitle_file_it=srt_it_file,
            subtitle_file_en=srt_en_file,
            output_video=final_video,
            italian_height=italian_height,
            english_height=english_height
        )
        
        return {
            'success': True,
            'video_with_music': video_with_music,
            'final_video': final_video,
            'has_voice': True
        }
        
    except Exception as e:
        print(f"❌ DEBUG: Error in finalize_video_processing - {e}")
        return {
            'success': False,
            'error': str(e),
            'has_voice': False
        }

def upload_to_youtube(video_path, title, description, tags, credentials_path="service_account_key.json"):
    """Carica il video su YouTube e restituisce il link"""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth import default
        
        # Carica le credenziali
        if os.path.exists(credentials_path):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            credentials, project = default()
        else:
            raise Exception("File credentials non trovato")
        
        # Crea il servizio YouTube
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Prepara i metadati del video
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': [tag.strip() for tag in tags.split(',')],
                'categoryId': '27'  # Education
            },
            'status': {
                'privacyStatus': 'private'  # Inizia come privato
            }
        }
        
        # Carica il video
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        
        # Esegui l'upload
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        
        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        return {
            "success": True,
            "video_url": video_url,
            "video_id": video_id
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets'
]

TOKENS_DIR = "tokens"
ROUND_ROBIN_FILE = "round_robin_state.txt"

# Mappature per i diversi tipi di video
VIDEO_TYPES = {
    "elettrodomestici": {
        "input_sheet": "Appliances",
        "output_sheet": "elettrodomestici",
        "input_columns": {
            "property": "Property Name",
            "type": "Tipologia",
            "video": "Video URL",
            "edited": "Url video editato"
        },
        "output_columns": {
            "property": "appartamento",
            "type": "tipologia",
            "video": "url_video_editato"
        }
    },
    "climatizzazione": {
        "input_sheet": "HeatingCooling",
        "output_sheet": "climatizzazione",
        "input_columns": {
            "property": "Property Name",
            "type": "Tipologia",
            "video": "Riscaldamento Video URL",  # o Climatizzazione Video URL
            "edited": "Url video editato riscaldamento"  # o climatizzazione
        },
        "output_columns": {
            "property": "appartamento",
            "type": "tipologia_sistema",
            "video": "video YT"
        }
    },
    "utenze": {
        "input_sheet": "Utilities",
        "output_sheet": "utenze",
        "input_columns": {
            "property": "Property Name",
            "type": "Tipo Utenza",
            "video": "Video URL",
            "edited": "Video URL editato"
        },
        "output_columns": {
            "property": "appartamento",
            "type": "tipologia",
            "video": "tutorial"
        }
    },
    "check-in": {
        "input_sheet": "CheckIn",
        "output_sheet": "check-in",
        "input_columns": {
            "property": "Property Name",
            "type": "Tipo",
            "video": "Video URL",
            "edited": "Video URL"  # da verificare
        },
        "output_columns": {
            "property": "appartamento",
            "type": "tipo",
            "video": "Tutorial spazzatura"  # colonna AD
        }
    }
}

# Funzioni per la gestione degli account (opzionali per future implementazioni)
def list_accounts():
    return sorted([d for d in os.listdir(TOKENS_DIR) if os.path.isdir(os.path.join(TOKENS_DIR, d))])

def get_next_account():
    with lock:
        accounts = list_accounts()
        if not accounts:
            raise Exception("Nessun account trovato in tokens/")
        idx = 0
        if os.path.exists(ROUND_ROBIN_FILE):
            with open(ROUND_ROBIN_FILE, 'r') as f:
                try:
                    idx = int(f.read().strip())
                except:
                    idx = 0
        next_idx = (idx + 1) % len(accounts)
        with open(ROUND_ROBIN_FILE, 'w') as f:
            f.write(str(next_idx))
        return accounts[idx]

def get_authenticated_service(account):
    account_dir = os.path.join(TOKENS_DIR, account)
    credentials = None
    cred_path = os.path.join(account_dir, "credentials.json")
    token_path = os.path.join(account_dir, "token.pickle")
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            credentials = pickle.load(token)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                cred_path, SCOPES)
            credentials = flow.run_local_server(port=0)
        with open(token_path, "wb") as token:
            pickle.dump(credentials, token)
    youtube = build('youtube', 'v3', credentials=credentials)
    drive = build('drive', 'v3', credentials=credentials)
    sheets = build('sheets', 'v4', credentials=credentials)
    return youtube, drive, sheets

def get_file_id_from_url(url):
    try:
        return url.split('/d/')[1].split('/')[0]
    except Exception as e:
        return None

def combine_instructions(existing_instructions, new_instructions):
    """Combina le istruzioni esistenti con le nuove usando OpenAI"""
    try:
        # Carica la configurazione da Streamlit secrets
        import streamlit as st
        openai_api_key = st.secrets.get('OPENAI_API_KEY')
        if not openai_api_key:
            # Fallback alle variabili d'ambiente
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                print("❌ OPENAI_API_KEY non trovata nei secrets o nelle variabili d'ambiente")
                return "Istruzioni non disponibili"
        
        client = openai.OpenAI(api_key=openai_api_key)
        
        prompt = f"""Sei un assistente che combina e formatta istruzioni per elettrodomestici.
Combina le istruzioni esistenti con le nuove istruzioni, creando una lista di step numerati.

Istruzioni esistenti:
{existing_instructions}

Nuove istruzioni:
{new_instructions}

Regole:
1. Mantieni tutte le informazioni importanti da entrambe le fonti
2. Formatta il risultato in ESATTAMENTE 4 step numerati
3. Ogni step deve iniziare con un verbo all'imperativo
4. Ogni step deve essere una singola frase di circa 15 parole
5. Non usare punteggiatura alla fine di ogni step
6. Non aggiungere testo extra o spiegazioni
7. Le istruzioni devono essere esaustive e coprire l'intero processo di utilizzo dell'elettrodomestico
8. Se le istruzioni sono vuote o non disponibili, restituisci 'Istruzioni non disponibili'

Esempio di formato:
1. Apri lo sportello della lavatrice e inserisci il bucato fino a riempire il cestello per 3/4
2. Aggiungi il detersivo nel cassetto superiore e l'ammorbidente in quello con il fiore
3. Seleziona il programma di lavaggio desiderato usando la manopola e regola la temperatura
4. Premi il pulsante start per avviare il ciclo di lavaggio e attendi il segnale acustico di fine"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Combina le istruzioni seguendo il formato specificato"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Errore nella combinazione delle istruzioni: {e}")
        return "Istruzioni non disponibili"

def update_appliance_instructions(service, apartment_name, appliance_type, new_instructions):
    """Aggiorna le istruzioni dell'elettrodomestico nel foglio Appliances"""
    try:
        # Recupera le istruzioni esistenti
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='appliances!A:Z'
        ).execute()
        values = result.get('values', [])
        headers = values[0]
        
        # Trova la riga dell'appartamento e dell'elettrodomestico
        row_index = None
        for i, row in enumerate(values[1:], start=2):
            if (row[headers.index('Property Name')].lower() == apartment_name.lower() and 
                row[headers.index('Tipo')].lower() == appliance_type.lower()):
                row_index = i
                break
        
        if row_index:
            # Recupera le istruzioni esistenti
            existing_instructions = values[row_index-1][headers.index('istruzioni')] if 'istruzioni' in headers and len(values[row_index-1]) > headers.index('istruzioni') else ''
            
            # Combina le istruzioni
            combined_instructions = combine_instructions(existing_instructions, new_instructions)
            
            # Aggiorna la cella con le istruzioni combinate
            range_name = f'appliances!{chr(ord("A") + headers.index("istruzioni"))}{row_index}'
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=range_name,
                valueInputOption='RAW',
                body={'values': [[combined_instructions]]}
            ).execute()
            print(f"Istruzioni aggiornate per {appliance_type} in {apartment_name}")
            return True
        else:
            print(f"Nessuna riga trovata per {appliance_type} in {apartment_name}")
            return False
            
    except Exception as e:
        print(f"Errore nell'aggiornamento delle istruzioni: {e}")
        return False

def test_subtitle_positioning_methods(input_video, segments, output_dir="."):
    """Testa diversi metodi di posizionamento sottotitoli"""
    print("🧪 TEST: Confronto metodi posizionamento sottotitoli")
    
    # Ottieni informazioni video
    video_info = get_video_info(input_video)
    video_width = video_info['width'] if video_info else 478
    video_height = video_info['height'] if video_info else 850
    
    print(f"📐 Video dimensions: {video_width}x{video_height}")
    
    # Test 1: Metodo attuale (subtitles filter)
    print("\n🔧 TEST 1: Metodo attuale (subtitles filter)")
    try:
        srt_file_it = os.path.join(output_dir, "test1_italian.srt")
        srt_file_en = os.path.join(output_dir, "test1_english.srt")
        output_video = os.path.join(output_dir, "test1_subtitles.mp4")
        
        create_srt_file(segments, srt_file_it, "IT")
        create_srt_file(segments, srt_file_en, "EN")
        
        add_subtitles_to_video(input_video, srt_file_it, srt_file_en, output_video, 120, 60)
        print("✅ Test 1 completato")
    except Exception as e:
        print(f"❌ Test 1 fallito: {e}")
    
    # Test 2: Nuovo metodo (ass filter)
    print("\n🔧 TEST 2: Nuovo metodo (ass filter)")
    try:
        ass_file_it = os.path.join(output_dir, "test2_italian.ass")
        ass_file_en = os.path.join(output_dir, "test2_english.ass")
        output_video = os.path.join(output_dir, "test2_ass.mp4")
        
        create_fixed_position_ass_file(segments, ass_file_it, "IT", 120, video_width, video_height)
        create_fixed_position_ass_file(segments, ass_file_en, "EN", 60, video_width, video_height)
        
        add_subtitles_with_fixed_position(input_video, ass_file_it, ass_file_en, output_video)
        print("✅ Test 2 completato")
    except Exception as e:
        print(f"❌ Test 2 fallito: {e}")
    
    # Test 3: Metodo unificato (dual ass)
    print("\n🔧 TEST 3: Metodo unificato (dual ass)")
    try:
        ass_file_it = os.path.join(output_dir, "test3_italian.ass")
        ass_file_en = os.path.join(output_dir, "test3_english.ass")
        output_video = os.path.join(output_dir, "test3_dual.mp4")
        
        create_dual_ass_files(segments, ass_file_it, ass_file_en, video_width, video_height)
        
        add_subtitles_with_fixed_position(input_video, ass_file_it, ass_file_en, output_video)
        print("✅ Test 3 completato")
    except Exception as e:
        print(f"❌ Test 3 fallito: {e}")
    
    print("\n📊 RISULTATI TEST:")
    print("Test 1: Metodo attuale (subtitles) - Può avere sovrapposizioni")
    print("Test 2: Nuovo metodo (ass) - Posizione fissa, controllo completo")
    print("Test 3: Metodo unificato (dual ass) - Ottimizzato per dual-language")
    
    return {
        "test1": os.path.join(output_dir, "test1_subtitles.mp4"),
        "test2": os.path.join(output_dir, "test2_ass.mp4"),
        "test3": os.path.join(output_dir, "test3_dual.mp4")
    }