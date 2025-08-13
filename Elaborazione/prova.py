from openai import OpenAI
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

# Configurazione ffmpeg robusta
try:
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ["FFMPEG_BINARY"] = ffmpeg_path
    print(f"🔧 DEBUG: FFMPEG_BINARY set to: {ffmpeg_path}")
except Exception as e:
    print(f"⚠️ DEBUG: Could not set FFMPEG_BINARY: {e}")
    # Fallback: usa ffmpeg dal PATH se disponibile
    pass

def get_video_info(input_video):
    """Ottiene informazioni sul video per gestire meglio i codec usando subprocess diretto"""
    try:
        # Usa subprocess diretto con imageio-ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

        # Prova prima ffprobe, se non funziona usa ffmpeg
        ffprobe_path = ffmpeg_path.replace('ffmpeg', 'ffprobe')
        
        # Verifica se ffprobe esiste
        if not os.path.exists(ffprobe_path):
            print(f"⚠️ DEBUG: ffprobe not found at {ffprobe_path}, using ffmpeg fallback")
            # Fallback: usa ffmpeg per ottenere info reali del video
            try:
                cmd = [
                    ffmpeg_path,
                    '-i', input_video,
                    '-f', 'null',
                    '-'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                # Estrai info dal stderr di ffmpeg
                stderr_output = result.stderr
                
                # Cerca dimensioni video
                import re
                size_match = re.search(r'(\d{2,4})x(\d{2,4})', stderr_output)
                width = int(size_match.group(1)) if size_match else 1920
                height = int(size_match.group(2)) if size_match else 1080
                
                # Cerca durata
                duration_match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})', stderr_output)
                if duration_match:
                    hours, minutes, seconds = map(int, duration_match.groups())
                    duration = hours * 3600 + minutes * 60 + seconds
                else:
                    duration = 60.0
                
                print(f"✅ DEBUG: ffmpeg fallback successful - size: {width}x{height}, duration: {duration}s")
                return {
                    'video_codec': 'unknown',
                    'audio_codec': 'unknown', 
                    'width': width,
                    'height': height,
                    'duration': duration,
                }
            except Exception as e:
                print(f"⚠️ DEBUG: ffmpeg fallback failed: {e}, using default values")
                return {
                    'video_codec': 'unknown',
                    'audio_codec': 'unknown', 
                    'width': 1920,
                    'height': 1080,
                    'duration': 60.0,
                }

        # Comando ffprobe per ottenere informazioni sul video
        cmd = [
            ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            input_video,
        ]

        # Esegui il comando
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        if result.returncode == 0:
            # Parsa il JSON di output
            probe_data = json.loads(result.stdout)

            # Trova gli stream
            video_stream = next((s for s in probe_data['streams'] if s.get('codec_type') == 'video'), None)
            audio_stream = next((s for s in probe_data['streams'] if s.get('codec_type') == 'audio'), None)

            if video_stream:
                return {
                    'video_codec': video_stream.get('codec_name', 'unknown'),
                    'audio_codec': audio_stream.get('codec_name', 'unknown') if audio_stream else None,
                    'width': int(video_stream.get('width', 0)),
                    'height': int(video_stream.get('height', 0)),
                    'duration': float(probe_data.get('format', {}).get('duration', 0)),
                }
            else:
                print(f"❌ DEBUG: No video stream found in {input_video}")
                return None
        else:
            print(f"❌ DEBUG: ffprobe error: {result.stderr}")
            return None

    except subprocess.CalledProcessError as e:
        print(f"❌ DEBUG: Error in get_video_info subprocess: {e}")
        return None
    except Exception as e:
        print(f"❌ DEBUG: Error in get_video_info: {e}")
        return None

# === CONFIG ===
def get_openai_client(api_key):
    """Inizializza il client OpenAI"""
    return OpenAI(api_key=api_key)

def extract_audio_from_video(input_video, audio_file):
    """Estrae l'audio dal video"""
    try:
        # Usa subprocess diretto con imageio-ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"🔧 DEBUG: Using ffmpeg from: {ffmpeg_path}")
        
        # Comando ffmpeg per estrarre audio
        cmd = [
            ffmpeg_path,
            '-i', input_video,
            '-vn',  # No video
            '-ac', '1',  # Mono
            '-ar', '16000',  # 16kHz
            '-acodec', 'pcm_s16le',  # WAV PCM
            '-y',  # Overwrite
            audio_file
        ]
        
        print(f"🔧 DEBUG: Running command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ DEBUG: ffmpeg stderr: {result.stderr}")
            raise Exception(f"ffmpeg error: {result.stderr}")
            
        print(f"✅ DEBUG: Audio extracted successfully to {audio_file}")
        return audio_file

    except Exception as e:
        print(f"❌ DEBUG: Error in extract_audio: {e}")
        raise Exception(f"Errore estrazione audio: {e}")

def transcribe_audio(audio_file, client):
    """Trascrive l'audio usando Whisper API"""
    try:
        with open(audio_file, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json"
            )
        
        # Verifica che transcript sia valido
        if not transcript:
            print("❌ DEBUG: transcribe_audio returned None")
            raise Exception("Trascrizione restituita vuota")
        
        # Verifica che transcript abbia l'attributo segments
        if not hasattr(transcript, 'segments'):
            print("❌ DEBUG: transcript has no 'segments' attribute")
            raise Exception("Trascrizione senza attributo 'segments'")
        
        # Verifica che segments non sia vuoto
        if not transcript.segments:
            print("❌ DEBUG: transcript.segments is empty")
            raise Exception("Trascrizione senza segmenti audio")
        
        print(f"✅ DEBUG: transcribe_audio successful - {len(transcript.segments)} segments")
        return transcript
        
    except Exception as e:
        print(f"❌ DEBUG: Error in transcribe_audio: {e}")
        raise Exception(f"Errore trascrizione audio: {e}")

def optimize_transcription(raw_transcription, client, custom_prompt=None, video_type=None, original_segments=None):
    """Ottimizza la trascrizione con descrizione visiva"""
    
    # Importa la funzione per ottenere il prompt specifico
    try:
        from data_manager import get_prompt_for_video_type
    except ImportError:
        # Fallback se non riesce a importare
        def get_prompt_for_video_type(video_type):
            return "You are a video subtitle editor specializing in instructional videos."
    
    # Ottieni il prompt specifico per la tipologia di video
    if video_type:
        base_prompt = get_prompt_for_video_type(video_type)
    else:
        base_prompt = "You are a video subtitle editor specializing in instructional videos."
    
    base_prompt += """
Your task is to optimize the following raw transcription of an instructional video. The video shows a person performing the actions described in the audio. Follow these steps:

1. Keep the text in Italian, as it is the original language.
2. Write SHORT, CONCISE sentences that describe exactly what is shown in the video.
3. Each sentence should be self-contained and describe a single action clearly.
4. Write sentences that are 5-12 words long - SHORT and to the point.
5. NEVER truncate sentences with ellipsis (...) or cut them mid-sentence.
6. Write natural, flowing sentences that make sense on their own.
7. DO NOT add any prefix to the text - just write the Italian text as is.
8. DO NOT add periods, exclamation marks, or question marks at the end of sentences.
9. The text will be automatically formatted for subtitles later - focus on brevity and clarity.
10. Provide the output as a JSON array of segments, where each segment has:
    - text: subtitle text in Italian (SHORT, complete sentence)

Raw transcription:
{raw_transcription}

CRITICAL QUALITY CHECKS - Before providing output, verify each sentence:
1. Each sentence MUST be grammatically complete
2. NO sentences ending with "..." or ".." or "."
3. NO sentences ending with "e" or "o" or "a" (incomplete words)
4. NO sentences ending with "che" or "per" or "con" (incomplete phrases)
5. Each sentence MUST make sense on its own
6. Each sentence MUST describe a complete action
7. If any sentence seems incomplete, rewrite it completely
8. Each sentence MUST be a complete instruction that can stand alone
9. NEVER cut words in the middle - each sentence must end with a complete word
10. KEEP SENTENCES SHORT - prefer 5-12 words over longer sentences
11. Use simple, direct language - avoid unnecessary words
12. Focus on the action being performed, not descriptions

Example output (SHORT sentences):
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
        temperature=0.1,
        max_tokens=4000  # Aumenta il limite di token per evitare tagli
    )

    # Clean the response content before parsing JSON
    content = response.choices[0].message.content.strip()
    if content.startswith('```json'):
        content = content[7:]
    # Rimuovi solo se effettivamente finisce con ```
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

    # Distribuisci i testi ottimizzati sui segmenti originali mantenendo i timestamp
    if original_segments:
        # Usa i segmenti originali per distribuire i testi ottimizzati
        optimized_segments = distribute_subtitles(original_segments, optimized_texts)
    else:
        # Fallback: usa direttamente i testi ottimizzati
        optimized_segments = optimized_texts
    
    # Post-processing: assicurati che ogni testo sia adatto per i sottotitoli
    for i, segment in enumerate(optimized_segments):
        try:
            if 'text' in segment:
                text = segment['text']
                
                # Controlli di qualità per frasi tagliate - RIMOSSO per evitare tagli
                # incomplete_endings = ['...', '..', '.', 'e', 'o', 'a', 'che', 'per', 'con', 'di', 'da', 'in', 'su']
                # for ending in incomplete_endings:
                #     if text.rstrip().endswith(ending):
                #         print(f"⚠️ WARNING: Sentence {i} ends with incomplete word '{ending}': {text}")
                #         # Rimuovi l'ending incompleto
                #         text = text.rstrip().rstrip(ending).strip()
                #         segment['text'] = text
                
                # Controllo per parole tagliate a metà
                if text and not text.endswith(' ') and len(text.split()) > 0:
                    last_word = text.split()[-1]
                    if len(last_word) < 3:  # Se l'ultima parola è troppo corta, potrebbe essere tagliata
                        print(f"⚠️ WARNING: Sentence {i} might have incomplete last word: '{text}'")
                
                # Usa il testo direttamente senza processarlo
                segment['text'] = text
            else:
                print(f"❌ DEBUG: Segment {i} has no 'text' key: {segment}")
        except Exception as e:
            raise

    return optimized_segments

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
    
    # Usa il testo completo senza rimuovere caratteri finali
    
    # Usa il testo completo senza processarlo
    return [text, ""]

def split_text(text, max_length=80, max_lines=3):
    """Funzione semplificata che restituisce il testo completo senza tagli"""
    # Restituisce il testo completo senza processarlo
    return [text, ""]

def distribute_subtitles(segments, texts):
    """Distribuisce i sottotitoli in modo uniforme"""
    
    # Controlla se la lista è vuota
    if not segments:
        print("🔧 DEBUG: No segments found, creating default segments")
        # Crea segmenti di default se non ce ne sono
        distributed_segments = []
        for i, text in enumerate(texts):
            start_time = i * 5.0  # 5 secondi per segmento
            end_time = (i + 1) * 5.0
            
            # Gestisce sia stringhe che dizionari
            if isinstance(text, dict):
                text_content = text.get('text', str(text))
            else:
                text_content = str(text)
            
            distributed_segments.append({
                'start': start_time,
                'end': end_time,
                'text': text_content
            })
        return distributed_segments
    
    # Controlla se texts è vuoto
    if not texts:
        print("🔧 DEBUG: No texts found, returning empty segments")
        return []
    
    # Gestisce sia oggetti Whisper che dizionari
    try:
        if hasattr(segments[-1], 'end'):
            total_duration = segments[-1].end
        else:
            total_duration = segments[-1]['end']
    except (IndexError, KeyError) as e:
        print(f"🔧 DEBUG: Error accessing segment end: {e}")
        # Fallback: usa una durata di default
        total_duration = 60.0  # 60 secondi di default
    
    num_subtitles = len(texts)
    duration_per_subtitle = total_duration / num_subtitles
    
    distributed_segments = []
    for i in range(num_subtitles):
        start_time = i * duration_per_subtitle
        end_time = (i + 1) * duration_per_subtitle
        
        # Controlla che l'indice sia valido
        if i >= len(texts):
            print(f"🔧 DEBUG: Index {i} out of range for texts (length: {len(texts)})")
            break
        
        # Gestisce sia stringhe che dizionari
        if isinstance(texts[i], dict):
            text_content = texts[i].get('text', str(texts[i]))
        else:
            text_content = str(texts[i])
        
        distributed_segments.append({
            'start': start_time,
            'end': end_time,
            'text': text_content
        })
    
    print(f"🔧 DEBUG: Created {len(distributed_segments)} distributed segments")
    print(f"🔧 DEBUG: First segment: {distributed_segments[0] if distributed_segments else 'None'}")
    print(f"🔧 DEBUG: Last segment: {distributed_segments[-1] if distributed_segments else 'None'}")
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
                # Controlla se il prefisso è già presente
                if text.startswith('[IT] '):
                    prefix = ""
                else:
                    prefix = "[IT] "
            else:
                text = segment.get('text_en', segment['text'])  # Fallback al testo italiano se non c'è inglese
                # Controlla se il prefisso è già presente
                if text.startswith('[EN] '):
                    prefix = ""
                else:
                    prefix = "[EN] "
            
            # Usa il testo completo senza processarlo
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
            
            # Usa il testo completo senza processarlo
            full_text = text
            
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
            
            # Testo inglese
            english_text = segment.get('text_en', '')
            
            # Scrivi il formato unificato
            srt.write(f"{i}\n{start} --> {end}\n")
            
            # Aggiungi prefisso IT solo se non presente
            if italian_text.startswith('[IT] '):
                srt.write(f"{italian_text}\n")
            else:
                srt.write(f"[IT] {italian_text}\n")
            
            # Aggiungi prefisso EN solo se non presente
            if english_text.startswith('[EN] '):
                srt.write(f"{english_text}\n")
            else:
                srt.write(f"[EN] {english_text}\n")
            
            srt.write("\n")

def translate_subtitles(segments, client, output_file, video_type=None):
    """Traduce i sottotitoli in inglese - identica al test che funzionava"""
    
    # Importa la funzione per ottenere il prompt di traduzione specifico
    try:
        from data_manager import get_translation_prompt_for_video_type
    except ImportError:
        # Fallback se non riesce a importare
        def get_translation_prompt_for_video_type(video_type):
            return "You are a translator specializing in instructional videos."
    
    # Ottieni il prompt di traduzione specifico per la tipologia di video
    if video_type:
        translation_prompt = get_translation_prompt_for_video_type(video_type)
    else:
        translation_prompt = "You are a translator specializing in instructional videos."
    
    translation_prompt += """
Translate the following Italian text to English, ensuring:
- The translation is clear, concise, and suitable for subtitles.
- Use an imperative tone, avoiding questions or incomplete sentences.
- Write SHORT sentences that are 5-12 words long - keep them brief.
- NEVER truncate sentences with ellipsis (...) or cut them mid-sentence.
- Write natural, flowing sentences that make sense on their own.
- IMPORTANT: Always translate to English, never leave any Italian text.
- DO NOT add any prefix to the translation.
- The text will be automatically formatted for subtitles later - focus on brevity.

CRITICAL QUALITY CHECKS - Before providing translation, verify each sentence:
1. Each sentence MUST be grammatically complete in English
2. NO sentences ending with "..." or ".." or "."
3. NO sentences ending with "and" or "or" or "the" (incomplete words)
4. NO sentences ending with "that" or "for" or "with" (incomplete phrases)
5. Each sentence MUST make sense on its own
6. Each sentence MUST describe a complete action
7. If any sentence seems incomplete, rewrite it completely
8. KEEP SENTENCES SHORT - prefer 5-12 words over longer sentences
9. Use simple, direct language - avoid unnecessary words
10. Focus on the action being performed, not descriptions
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
            
            # Usa il testo completo senza rimuovere caratteri finali
            
            # Aggiungi il testo inglese al segmento
            segment['text_en'] = text
            
            # Usa il testo direttamente senza process_subtitle_text (come nel test)
            srt.write(f"{i}\n{start} --> {end}\n{text}\n\n")

def add_background_music(input_video, music_file, output_video):
    """Aggiunge musica di sottofondo usando subprocess diretto"""
    try:
        # Verifica che i file esistano
        if not os.path.exists(input_video):
            raise FileNotFoundError(f"Video input non trovato: {input_video}")
        if not os.path.exists(music_file):
            raise FileNotFoundError(f"File musica non trovato: {music_file}")
        
        # Usa subprocess diretto con imageio-ffmpeg
        # Ottieni il percorso di ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Comando per aggiungere musica di sottofondo
        cmd = [
            ffmpeg_path,
            '-i', input_video,
            '-i', music_file,
            '-filter_complex', '[1:a]volume=0.3[a1];[0:a][a1]amix=inputs=2:duration=first',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-crf', '20',
            '-pix_fmt', 'yuv420p',
            '-shortest',
            '-y',  # Sovrascrivi output
            output_video
        ]
        
        # Esegui il comando
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.returncode == 0:
            print(f"✅ Musica aggiunta con successo: {output_video}")
        else:
            print(f"⚠️ Warning: {result.stderr}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore subprocess: {e}")
        print(f"stderr: {e.stderr}")
        # Fallback: copia solo il video senza musica
        try:
            cmd_fallback = [
                ffmpeg_path,
                '-i', input_video,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast',
                '-crf', '20',
                '-pix_fmt', 'yuv420p',
                '-y',
                output_video
            ]
            subprocess.run(cmd_fallback, capture_output=True, text=True, check=True)
            print(f"✅ Fallback: video copiato senza musica: {output_video}")
        except Exception as e2:
            raise Exception(f"Fallback fallito: {e2}")
    except Exception as e:
        raise Exception(f"Errore aggiunta musica: {e}")



def add_subtitles_to_video(input_video, subtitle_file_it, subtitle_file_en, output_video, italian_height=120, english_height=60):
    """Aggiunge sottotitoli duali al video usando subprocess diretto"""
    
    # Verifica che i file SRT esistano
    if not os.path.exists(subtitle_file_it):
        raise FileNotFoundError(f"File SRT italiano non trovato: {subtitle_file_it}")
    
    if not os.path.exists(subtitle_file_en):
        raise FileNotFoundError(f"File SRT inglese non trovato: {subtitle_file_en}")
    
    try:
        # Usa subprocess diretto con imageio-ffmpeg
        # Ottieni il percorso di ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Ottieni informazioni sul video per gestire meglio i codec
        video_info = get_video_info(input_video)
        
        # Rimuovi il file di output se esiste già
        if os.path.exists(output_video):
            os.remove(output_video)
        
        # METODO SEMPLIFICATO: Aggiungi entrambi i sottotitoli in un unico passaggio
        cmd = [
            ffmpeg_path,
            '-i', input_video,
            '-vf', f"subtitles={subtitle_file_it}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={italian_height},MarginL=50,MarginR=50,WrapStyle=0',subtitles={subtitle_file_en}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={english_height},MarginL=50,MarginR=50,WrapStyle=0'",
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',  # Usa preset veloce per maggiore stabilità
            '-crf', '20',  # Qualità leggermente più bassa per stabilità
            '-pix_fmt', 'yuv420p',
            '-y',  # Sovrascrivi output
            output_video
        ]
        
        # Esegui il comando
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.returncode == 0:
            print(f"✅ Sottotitoli aggiunti con successo: {output_video}")
        else:
            print(f"⚠️ Warning: {result.stderr}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore subprocess: {e}")
        print(f"stderr: {e.stderr}")
        # Se il metodo principale fallisce, prova senza sottotitoli
        try:
            cmd_fallback = [
                ffmpeg_path,
                '-i', input_video,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast',
                '-crf', '20',
                '-pix_fmt', 'yuv420p',
                '-y',
                output_video
            ]
            subprocess.run(cmd_fallback, capture_output=True, text=True, check=True)
            print(f"✅ Fallback: video copiato senza sottotitoli: {output_video}")
        except Exception as fallback_error:
            raise Exception(f"Fallback fallito: {fallback_error}")
    except Exception as e:
        raise Exception(f"Errore aggiunta sottotitoli: {e}")

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
            
            # Usa il testo completo senza limiti
            full_text = text
            
            ass.write(f"Dialogue: 0,{start},{end},Default,,200,200,0,,{prefix}{full_text}\n")

def add_subtitles_with_fixed_position(input_video, subtitle_file_it, subtitle_file_en, output_video):
    """Aggiunge sottotitoli con posizione fissa usando il filtro ass con subprocess diretto"""
    print(f"🔧 DEBUG: add_subtitles_with_fixed_position - input: {input_video}, it_subs: {subtitle_file_it}, en_subs: {subtitle_file_en}, output: {output_video}")
    
    # Verifica che i file ASS esistano
    if not os.path.exists(subtitle_file_it):
        print(f"❌ DEBUG: Italian ASS file NOT found: {subtitle_file_it}")
        raise FileNotFoundError(f"File ASS italiano non trovato: {subtitle_file_it}")
    
    if not os.path.exists(subtitle_file_en):
        print(f"❌ DEBUG: English ASS file NOT found: {subtitle_file_en}")
        raise FileNotFoundError(f"File ASS inglese non trovato: {subtitle_file_en}")
    
    try:
        # Usa subprocess diretto con imageio-ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Ottieni informazioni sul video
        video_info = get_video_info(input_video)
        video_width = video_info['width'] if video_info else 478
        video_height = video_info['height'] if video_info else 850
        
        print(f"🔧 DEBUG: Video dimensions: {video_width}x{video_height}")
        
        # Rimuovi il file di output se esiste già
        if os.path.exists(output_video):
            os.remove(output_video)
        
        # Usa il filtro ass per controllo completo della posizione
        cmd = [
            ffmpeg_path,
            '-i', input_video,
            '-vf', f"ass={subtitle_file_it},ass={subtitle_file_en}",
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'medium',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-y',  # Sovrascrivi output
            output_video
        ]
        
        # Esegui il comando
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.returncode == 0:
            print("🔧 DEBUG: Fixed position subtitles added successfully")
        else:
            print(f"⚠️ Warning: {result.stderr}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore subprocess: {e}")
        print(f"stderr: {e.stderr}")
        raise Exception(f"Errore aggiunta sottotitoli con posizione fissa: {e}")
    except Exception as e:
        print(f"❌ DEBUG: Error in add_subtitles_with_fixed_position - {e}")
        raise e

def add_subtitles_with_subtitles_filter(input_video, subtitle_file_it, subtitle_file_en, output_video, italian_height=120, english_height=60):
    """Aggiunge sottotitoli usando il filtro subtitles (più stabile) con subprocess diretto"""
    print(f"🔧 DEBUG: add_subtitles_with_subtitles_filter - input: {input_video}, it_subs: {subtitle_file_it}, en_subs: {subtitle_file_en}, output: {output_video}")
    
    try:
        # Usa subprocess diretto con imageio-ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Rimuovi il file di output se esiste già
        if os.path.exists(output_video):
            os.remove(output_video)
        
        # Usa il filtro subtitles con WrapStyle=0 per evitare wrapping
        vf = f"subtitles={subtitle_file_it}:force_style='FontSize=18,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={italian_height},MarginL=200,MarginR=200,WrapStyle=0',subtitles={subtitle_file_en}:force_style='FontSize=18,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={english_height},MarginL=200,MarginR=200,WrapStyle=0'"
        
        cmd = [
            ffmpeg_path,
            '-i', input_video,
            '-vf', vf,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'medium',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-y',  # Sovrascrivi output
            output_video
        ]
        
        # Esegui il comando
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.returncode == 0:
            print("🔧 DEBUG: Subtitles filter subtitles added successfully")
        else:
            print(f"⚠️ Warning: {result.stderr}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore subprocess: {e}")
        print(f"stderr: {e.stderr}")
        raise Exception(f"Errore aggiunta sottotitoli con filtro: {e}")
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
    """Processa un video completo: estrazione audio, trascrizione, sottotitoli, musica, output finale"""
    
    print(f"🔧 DEBUG: process_video started - input: {input_video}, music: {music_file}, output_dir: {output_dir}, it_height: {italian_height}, en_height: {english_height}")
    
    # Crea la directory di output se non esiste
    os.makedirs(output_dir, exist_ok=True)
    
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
        
        # Controlla se transcript è valido
        if not transcript:
            print("🔧 DEBUG: Transcript is None or empty")
            return {
                "success": False,
                "error": "Trascrizione non valida"
            }
        
        # Controlla se transcript ha l'attributo segments
        if not hasattr(transcript, 'segments'):
            print("🔧 DEBUG: Transcript has no 'segments' attribute")
            return {
                "success": False,
                "error": "Trascrizione senza segmenti"
            }
        
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
            distributed_segments = optimize_transcription(raw_transcription, client, custom_prompt, video_type, transcript.segments)
            print("🔧 DEBUG: Step 3 completed - Transcription optimized and distributed")
            
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
    """Genera solo i sottotitoli senza processare il video completo"""
    
    print(f"🔧 DEBUG: generate_subtitles_only - input: {input_video}, output_dir: {output_dir}")
    
    # Crea la directory di output se non esiste
    os.makedirs(output_dir, exist_ok=True)
    
    # Configura file di output
    audio_file = os.path.join(output_dir, "audio.wav")
    subtitle_file_it = os.path.join(output_dir, "subtitles_it.srt")
    subtitle_file_en = os.path.join(output_dir, "subtitles_en.srt")
    
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
        
        # Controlla se transcript è valido
        if not transcript:
            print("🔧 DEBUG: Transcript is None or empty")
            return {
                "success": False,
                "error": "Trascrizione non valida"
            }
        
        # Controlla se transcript ha l'attributo segments
        if not hasattr(transcript, 'segments'):
            print("🔧 DEBUG: Transcript has no 'segments' attribute")
            return {
                "success": False,
                "error": "Trascrizione senza segmenti"
            }
        
        # Controlla se c'è audio nel video
        if not transcript.segments:
            print("🔧 DEBUG: No audio segments found")
            return {
                "success": False,
                "error": "Nessun audio rilevato nel video"
            }
        
        print(f"🔧 DEBUG: Found {len(transcript.segments)} audio segments")
        
        # 3. Prepara la trascrizione grezza e ottimizza
        print("🔧 DEBUG: Optimizing transcription...")
        # Costruisci la trascrizione grezza dai segmenti Whisper
        raw_transcription = "\n".join([seg.text for seg in transcript.segments])
        if not raw_transcription.strip():
            print("🔧 DEBUG: Raw transcription empty after transcription - returning early")
            return {
                "success": False,
                "error": "Trascrizione vuota",
            }
        optimized_texts = optimize_transcription(raw_transcription, client, custom_prompt, video_type, transcript.segments)
        print(f"🔧 DEBUG: optimize_transcription completed successfully with {len(optimized_texts)} texts")
        
        # 4. Distribuisci i sottotitoli
        print("🔧 DEBUG: Distributing subtitles...")
        optimized_segments = distribute_subtitles(transcript.segments, optimized_texts)
        print(f"🔧 DEBUG: distribute_subtitles completed with {len(optimized_segments)} segments")
        
        # 5. Crea file SRT italiani
        print("🔧 DEBUG: Creating Italian SRT file...")
        try:
            create_srt_file(optimized_segments, subtitle_file_it, "IT")
            print("✅ DEBUG: Italian SRT file created successfully")
        except Exception as e:
            print(f"⚠️ DEBUG: Error creating Italian SRT file: {e}")
            # Crea file di fallback
            with open(subtitle_file_it, 'w', encoding='utf-8') as f:
                f.write("1\n00:00:00,000 --> 00:00:05,000\nSottotitoli non disponibili\n\n")
        
        # 6. Traduci e crea file SRT inglesi
        print("🔧 DEBUG: Translating subtitles...")
        try:
            translate_subtitles(optimized_segments, client, subtitle_file_en, video_type)
            print("✅ DEBUG: English subtitles created successfully")
        except Exception as e:
            print(f"⚠️ DEBUG: Error creating English subtitles: {e}")
            # Crea file vuoto per evitare crash
            with open(subtitle_file_en, 'w', encoding='utf-8') as f:
                f.write("")
        
        # Prepara anche i segmenti inglesi separati per l'UI (comodità)
        segments_en = [
            {
                'start': seg['start'],
                'end': seg['end'],
                'text': seg.get('text_en', '')
            }
            for seg in optimized_segments
        ]
        
        print("✅ DEBUG: generate_subtitles_only completed successfully")
        return {
            "success": True,
            "subtitles_it": subtitle_file_it,
            "subtitles_en": subtitle_file_en,
            "transcript": raw_transcription,
            "segments": optimized_segments,
            "segments_en": segments_en,
            "has_voice": True
        }
        
    except Exception as e:
        print(f"❌ DEBUG: Error in generate_subtitles_only: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def finalize_video_processing(input_video, srt_it_file, srt_en_file, output_dir, italian_height=120, english_height=60):
    """Finalizza il video aggiungendo sottotitoli e musica di sottofondo"""
    
    try:
        print(f"🔧 DEBUG: finalize_video_processing - input: {input_video}, it_srt: {srt_it_file}, en_srt: {srt_en_file}")
        
        # Crea la directory di output se non esiste
        os.makedirs(output_dir, exist_ok=True)
        
        # Configura file di output
        video_with_music = os.path.join(output_dir, "video_with_music.mp4")
        final_output = os.path.join(output_dir, "final_video.mp4")

        # Aggiungi musica di sottofondo
        music_file = os.path.join("Elaborazione", "audio.mp3")
        add_background_music(input_video, music_file, video_with_music)

        # Aggiungi sottotitoli
        add_subtitles_to_video(
            input_video=video_with_music,
            subtitle_file_it=srt_it_file,
            subtitle_file_en=srt_en_file,
            output_video=final_output,
            italian_height=italian_height,
            english_height=english_height
        )
        
        return {
            'success': True,
            'video_with_music': video_with_music,
            'final_video': final_output,
            'has_voice': True
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

# Funzione upload_to_youtube rimossa - ora usa youtube_manager.py
# Per compatibilità, importa da youtube_manager

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
        
        client = OpenAI(api_key=openai_api_key)
        
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