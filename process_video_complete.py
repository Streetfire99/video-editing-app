#!/usr/bin/env python3
"""
Script completo per elaborare video con musica e sottotitoli
- Aggiunge musica di sottofondo
- Rimuove audio originale
- Aggiunge sottotitoli IT/EN
- Crea istruzioni da audio
- Mostra il risultato
"""

import os
import sys
import subprocess
import tempfile
import json
from datetime import datetime
import csv
import multiprocessing as mp
import shutil
from pathlib import Path
import ffmpeg
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle
from datetime import timedelta

# ============================================================================
# FUNZIONI COPIATE DA prova.py (CORRETTE)
# ============================================================================

def get_video_info(input_video):
    """Ottiene informazioni sul video usando ffprobe"""
    try:
        import ffmpeg
        probe = ffmpeg.probe(input_video)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
        
        if video_stream:
            return {
                'video_codec': video_stream.get('codec_name', 'unknown'),
                'audio_codec': audio_stream.get('codec_name', 'unknown') if audio_stream else 'none',
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'duration': float(probe.get('format', {}).get('duration', 0))
            }
    except Exception as e:
        print(f"❌ Errore ottenimento info video: {e}")
    return None

def get_openai_client(api_key):
    """Inizializza il client OpenAI"""
    return OpenAI(api_key=api_key)

def extract_audio_from_video(input_video, audio_file):
    """Estrae l'audio dal video"""
    print(f"🔧 DEBUG: extract_audio_from_video - input: {input_video}, output: {audio_file}")
    try:
        print("🔧 DEBUG: Importing ffmpeg...")
        import ffmpeg
        print("🔧 DEBUG: ffmpeg imported successfully")
        stream = ffmpeg.input(input_video)
        stream = ffmpeg.output(stream, audio_file, acodec='pcm_s16le', ar=16000, ac=1)
        print("🔧 DEBUG: Running ffmpeg.run...")
        ffmpeg.run(stream, overwrite_output=True)
        print("🔧 DEBUG: ffmpeg.run completed successfully")
    except ImportError as e:
        print(f"❌ DEBUG: ImportError in extract_audio_from_video - {e}")
        raise Exception("ffmpeg-python non è disponibile. Installa ffmpeg-python.")
    except Exception as e:
        print(f"❌ DEBUG: Unexpected error in extract_audio_from_video - {e}")
        raise e

def transcribe_audio(audio_file, client):
    """Trascrive l'audio usando Whisper"""
    with open(audio_file, "rb") as audio:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
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
5. Keep each line under 30 characters to prevent overlap.
6. Each subtitle should be exactly 2 lines maximum.
7. NEVER truncate sentences with ellipsis (...).
8. Write complete, self-contained sentences.
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
    print(f"🔧 DEBUG: Post-processing {len(optimized_texts)} texts")
    for i, text_item in enumerate(optimized_texts):
        print(f"🔧 DEBUG: Processing text {i}: {text_item}")
        try:
            if isinstance(text_item, dict) and 'text' in text_item:
                # Usa process_subtitle_text per coerenza
                lines = process_subtitle_text(text_item['text'])
                # Ricombina in un singolo testo (le righe saranno separate da \n nel file SRT)
                text_item['text'] = lines[0] + (f"\n{lines[1]}" if lines[1] else "")
                print(f"🔧 DEBUG: Processed text {i} text: {text_item['text']}")
            elif isinstance(text_item, str):
                # Se è una stringa, convertila in dizionario
                lines = process_subtitle_text(text_item)
                optimized_texts[i] = {
                    'text': lines[0] + (f"\n{lines[1]}" if lines[1] else "")
                }
                print(f"🔧 DEBUG: Converted string to dict for text {i}: {optimized_texts[i]['text']}")
            else:
                print(f"🔧 DEBUG: Text {i} has unexpected format: {text_item}")
        except Exception as e:
            print(f"❌ DEBUG: Error processing text {i}: {e}")
            import traceback
            print(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
            raise

    print(f"🔧 DEBUG: optimize_transcription returning {len(optimized_texts)} optimized texts")
    return optimized_texts

def format_timestamp(seconds):
    """Formatta i timestamp per SRT"""
    td = timedelta(seconds=seconds)
    millis = int((td.total_seconds() % 1) * 1000)
    return str(td).split('.')[0].replace('.', ',') + f',{millis:03d}'

def process_subtitle_text(text):
    """Processa il testo per i sottotitoli - funzione unificata"""
    print(f"🔧 DEBUG: process_subtitle_text called with text: '{text}'")
    
    if not text:
        print("🔧 DEBUG: Empty text, returning empty lines")
        return ["", ""]
    
    # Pulisci il testo aggressivamente da caratteri problematici
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').strip()
    print(f"🔧 DEBUG: Cleaned text: '{text}'")
    
    # Rimuovi spazi multipli
    import re
    text = re.sub(r'\s+', ' ', text)
    
    # Rimuovi punti, esclamazioni e domande finali
    text = text.rstrip('.!?')
    
    # Se il testo è troppo lungo, non troncarlo ma gestirlo in split_text
    if len(text) > 60:  # Aumentato il limite per evitare troncamenti
        print(f"🔧 DEBUG: Long text detected: '{text}' (length: {len(text)})")
        # Non troncare, lascia che split_text gestisca la divisione
    
    # Usa split_text per garantire sempre 2 righe
    result = split_text(text, max_length=25, max_lines=2)
    print(f"🔧 DEBUG: split_text result: {result}")
    return result

def split_text(text, max_length=30, max_lines=2):
    """Divide il testo per i sottotitoli - versione migliorata senza troncamenti"""
    print(f"🔧 DEBUG: split_text input: '{text}' (length: {len(text)})")
    
    # Se il testo è già abbastanza corto, restituiscilo direttamente
    if len(text) <= max_length:
        return [text, ""]
    
    # Dividi il testo in parole
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        # Prova ad aggiungere la parola alla riga corrente
        test_line = current_line + (" " + word) if current_line else word
        
        if len(test_line) <= max_length:
            current_line = test_line
        else:
            # Se la riga corrente non è vuota, salvala e inizia una nuova
            if current_line:
                lines.append(current_line)
            current_line = word
    
    # Aggiungi l'ultima riga se non è vuota
    if current_line:
        lines.append(current_line)
    
    # Assicurati di avere massimo 2 righe
    if len(lines) > max_lines:
        # Combina le righe in eccesso con la seconda riga
        first_line = lines[0]
        remaining_text = " ".join(lines[1:])
        
        # Se la seconda riga è troppo lunga, prova a dividerla
        if len(remaining_text) <= max_length:
            second_line = remaining_text
        else:
            # Dividi la seconda riga in modo intelligente
            words_remaining = remaining_text.split()
            second_line = ""
            for word in words_remaining:
                test_line = second_line + (" " + word) if second_line else word
                if len(test_line) <= max_length:
                    second_line = test_line
                else:
                    break
            
        lines = [first_line, second_line]
    
    # Assicurati di avere sempre 2 righe
    while len(lines) < max_lines:
        lines.append("")
    
    print(f"🔧 DEBUG: split_text result: {lines}")
    return lines[:max_lines]

def distribute_subtitles(segments, texts):
    """Distribuisce i sottotitoli in modo uniforme"""
    print(f"🔧 DEBUG: distribute_subtitles - segments: {len(segments)}, texts: {len(texts)}")
    print(f"🔧 DEBUG: texts type: {type(texts)}")
    if texts:
        print(f"🔧 DEBUG: first text type: {type(texts[0])}")
        print(f"🔧 DEBUG: first text: {texts[0]}")
        print(f"🔧 DEBUG: texts content: {texts}")
    else:
        print("🔧 DEBUG: texts is empty")
    
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
    
    # Gestisce sia oggetti Whisper che dizionari per calcolare la durata totale
    try:
        if hasattr(segments[-1], 'end'):
            total_duration = segments[-1].end
        elif isinstance(segments[-1], dict) and 'end' in segments[-1]:
            total_duration = segments[-1]['end']
        else:
            # Fallback: usa una durata di default
            total_duration = 60.0  # 60 secondi di default
            print(f"🔧 DEBUG: Could not determine total duration, using default: {total_duration}")
    except (IndexError, KeyError) as e:
        print(f"🔧 DEBUG: Error accessing segment end: {e}")
        # Fallback: usa una durata di default
        total_duration = 60.0  # 60 secondi di default
    
    print(f"🔧 DEBUG: Total duration: {total_duration}")
    
    num_subtitles = len(texts)
    duration_per_subtitle = total_duration / num_subtitles
    
    print(f"🔧 DEBUG: num_subtitles: {num_subtitles}, duration_per_subtitle: {duration_per_subtitle}")
    
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
    if distributed_segments:
        print(f"🔧 DEBUG: First segment: {distributed_segments[0]}")
        print(f"🔧 DEBUG: Last segment: {distributed_segments[-1]}")
    else:
        print("🔧 DEBUG: No segments created")
    
    return distributed_segments

def create_srt_file(segments, output_file, language="IT"):
    """Crea file SRT con controllo diretto del testo"""
    with open(output_file, "w", encoding="utf-8") as srt:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            # Usa il testo appropriato in base alla lingua
            if language == "IT":
                text = f"[IT] {segment['text']}"
            else:
                text = f"[EN] {segment.get('text_en', segment['text'])}"
            
            srt.write(f"{i}\n{start} --> {end}\n{text}\n\n")

def translate_subtitles(segments, client, output_file, video_type=None):
    """Traduce i sottotitoli in inglese"""
    print(f"🔧 DEBUG: translate_subtitles - segments: {len(segments)}, output: {output_file}")
    
    translation_prompt = "You are a translator specializing in instructional videos."
    
    translation_prompt += """
Translate the following Italian subtitle text to English. Keep the same meaning and style:

{text}

Translate to English:
"""

    with open(output_file, "w", encoding="utf-8") as srt:
        for i, segment in enumerate(segments, start=1):
            print(f"🔧 DEBUG: Translating segment {i}/{len(segments)}")
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            # Traduci il testo italiano
            text_to_translate = segment['text']
            print(f"🔧 DEBUG: Text to translate: '{text_to_translate}'")
            
            try:
                translation = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": translation_prompt},
                        {"role": "user", "content": text_to_translate}
                    ]
                )
                text = translation.choices[0].message.content.strip()
                print(f"🔧 DEBUG: Translation result: '{text}'")
                
                # Rimuovi punti, esclamazioni e domande finali
                text = text.rstrip('.!?')
                print(f"🔧 DEBUG: Cleaned translation: '{text}'")
                
                # Aggiungi il testo inglese al segmento
                segment['text_en'] = text
                
                # Usa il testo direttamente senza process_subtitle_text (come nel test)
                srt.write(f"{i}\n{start} --> {end}\n[EN] {text}\n\n")
                print(f"🔧 DEBUG: Written to SRT: segment {i}")
                
            except Exception as e:
                print(f"❌ DEBUG: Error translating segment {i}: {e}")
                # Fallback: usa il testo italiano
                segment['text_en'] = text_to_translate
                srt.write(f"{i}\n{start} --> {end}\n[EN] {text_to_translate}\n\n")
                print(f"🔧 DEBUG: Using fallback for segment {i}")
    
    print(f"🔧 DEBUG: Translation completed. File size: {os.path.getsize(output_file)} bytes")

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
        
        # METODO SEMPLICE: Usa il filtro subtitles che è più stabile
        # Aggiungi prima i sottotitoli italiani
        stream_it = ffmpeg.output(
            stream,
            'temp_it.mp4',
            vf=f"subtitles={subtitle_file_it}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={italian_height},MarginL=50,MarginR=50'",
            vcodec='libx264',
            acodec='aac',
            preset='medium',
            crf=18,
            pix_fmt='yuv420p'
        )
        ffmpeg.run(stream_it, overwrite_output=True)
        print("🔧 DEBUG: Italian subtitles added successfully")
        
        # Poi aggiungi i sottotitoli inglesi al video con sottotitoli italiani
        stream_final = ffmpeg.input('temp_it.mp4')
        stream_final = ffmpeg.output(
            stream_final,
            output_video,
            vf=f"subtitles={subtitle_file_en}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={english_height},MarginL=50,MarginR=50'",
            vcodec='libx264',
            acodec='aac',
            preset='medium',
            crf=18,
            pix_fmt='yuv420p'
        )
        ffmpeg.run(stream_final, overwrite_output=True)
        
        # Pulisci il file temporaneo
        if os.path.exists('temp_it.mp4'):
            os.remove('temp_it.mp4')
        
        print("🔧 DEBUG: Both subtitles added successfully")
        
    except ImportError as e:
        print(f"❌ DEBUG: ImportError in add_subtitles_to_video - {e}")
        raise Exception("ffmpeg-python non è disponibile. Installa ffmpeg-python.")
    except Exception as e:
        print(f"❌ DEBUG: Unexpected error in add_subtitles_to_video - {e}")
        raise e

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
        
        print(f"🔧 DEBUG: Found {len(transcript.segments)} audio segments")
        
        # Ottimizza la trascrizione
        print("🔧 DEBUG: Optimizing transcription...")
        try:
            raw_transcription = "\n".join([seg.text for seg in transcript.segments])
            optimized_texts = optimize_transcription(raw_transcription, client, custom_prompt, video_type)
            print(f"🔧 DEBUG: optimize_transcription completed successfully with {len(optimized_texts)} texts")
        except IndexError as e:
            print(f"❌ DEBUG: IndexError in optimize_transcription: {e}")
            import traceback
            print(f"❌ DEBUG: IndexError traceback: {traceback.format_exc()}")
            raise
        except Exception as e:
            print(f"❌ DEBUG: Error in optimize_transcription: {e}")
            import traceback
            print(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
            raise
        
        # Distribuisci i testi ottimizzati sui segmenti originali
        print("🔧 DEBUG: Distributing subtitles...")
        optimized_segments = distribute_subtitles(transcript.segments, optimized_texts)
        print(f"🔧 DEBUG: distribute_subtitles completed with {len(optimized_segments)} segments")
        
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
            'final_video': final_video
        }
        
    except Exception as e:
        print(f"❌ DEBUG: Error in finalize_video_processing - {e}")
        return {
            'success': False,
            'error': str(e)
        }

# ============================================================================
# FUNZIONI ORIGINALI DI process_video_complete.py
# ============================================================================

# Le funzioni sono ora integrate nel file

# Importa le funzioni di upload
from youtube_upload import upload_to_youtube
from drive_manager import upload_video_to_drive

def upload_to_youtube_with_retry_standalone(video_path, video_name, max_retries=3):
    """Carica video su YouTube con retry automatico e riautenticazione (standalone)"""
    for attempt in range(max_retries):
        try:
            print(f"📺 Tentativo {attempt + 1}/{max_retries} - Caricamento su YouTube: {video_name}")
            
            from youtube_upload import upload_to_youtube
            youtube_url = upload_to_youtube(
                video_path=video_path,
                title=f"{video_name} Umbria - Video Tutorial",
                privacy_status="unlisted",
                description=f"Video tutorial su {video_name} Umbria",
                tags="Umbria, tutorial, video, guida"
            )
            
            if youtube_url:
                print(f"✅ YouTube: {youtube_url}")
                return youtube_url
            else:
                print("❌ Errore caricamento YouTube")
                
        except Exception as e:
            error_msg = str(e).lower()
            print(f"❌ Errore YouTube (tentativo {attempt + 1}): {e}")
            
            # Se è un errore di autenticazione o permessi, forza riautenticazione
            if any(keyword in error_msg for keyword in ['insufficient', 'permission', 'scope', 'token', 'authentication']):
                print("🔄 Errore di autenticazione rilevato, forzando nuova autenticazione...")
                
                # Rimuovi il token YouTube esistente
                import os
                youtube_token_file = "youtube_token.pickle"
                if os.path.exists(youtube_token_file):
                    try:
                        os.remove(youtube_token_file)
                        print("🗑️ Token YouTube rimosso")
                    except:
                        pass
                
                # Aspetta un momento prima del prossimo tentativo
                import time
                time.sleep(2)
                
                if attempt < max_retries - 1:
                    print("🔄 Riprovo con nuova autenticazione...")
                    continue
                else:
                    print("❌ Impossibile caricare su YouTube dopo tutti i tentativi")
                    return None
            
            # Per altri errori, aspetta prima di riprovare
            if attempt < max_retries - 1:
                print(f"⏳ Attendo 5 secondi prima del prossimo tentativo...")
                import time
                time.sleep(5)
            else:
                print("❌ Impossibile caricare su YouTube dopo tutti i tentativi")
                return None
    
    return None

def process_single_video_standalone(video_file, input_folder, config_file, links_file):
    """Funzione standalone per multiprocessing"""
    try:
        # Importa qui per evitare problemi di pickle
        import os
        import tempfile
        import shutil
        from youtube_upload import upload_to_youtube
        from drive_manager import upload_video_to_drive
        
        video_path = os.path.join(input_folder, video_file)
        video_name = os.path.splitext(video_file)[0]
        
        print(f"🎬 Inizio elaborazione: {video_name}")
        
        # Crea directory temporanea
        temp_dir = tempfile.mkdtemp(prefix=f"parallel_processing_{video_name}_")
        
        # Elabora il video usando la funzione standalone
        result = process_video_standalone(video_file, input_folder, temp_dir)
        
        if result and isinstance(result, dict) and result.get("status") == "success":
            # Copia il risultato finale
            final_path = f"output_{video_name}.mp4"
            final_video_path = result.get("final_video")
            if final_video_path and os.path.exists(final_video_path):
                shutil.copy2(final_video_path, final_path)
                print(f"✅ Completato: {video_name} -> {final_path}")
                
                # Crea istruzioni per il video
                print("📝 Creazione istruzioni...")
                italian_instructions_url = None
                english_instructions_url = None
                
                try:
                    # Crea un'istanza temporanea per le istruzioni
                    processor = CompleteVideoProcessor()
                    italian_instructions_url, english_instructions_url = processor.create_instructions_for_video(video_name)
                    if italian_instructions_url and english_instructions_url:
                        print(f"✅ Istruzioni create: IT={italian_instructions_url}, EN={english_instructions_url}")
                    else:
                        print("❌ Errore creazione istruzioni")
                except Exception as e:
                    print(f"❌ Errore creazione istruzioni: {e}")
                
                # Upload su Drive e YouTube
                youtube_url = None
                drive_url = None
                
                # Upload su Drive
                try:
                    print(f"☁️  Caricamento su Google Drive: {video_name}")
                    drive_url = upload_video_to_drive(final_path, video_name, "video_elaborato")
                    if drive_url:
                        print(f"✅ Drive: {drive_url}")
                    else:
                        print("❌ Errore caricamento Drive")
                except Exception as e:
                    print(f"❌ Errore Drive: {e}")
                
                # Upload su YouTube (opzionale - continua anche se fallisce)
                try:
                    print(f"📺 Caricamento su YouTube: {video_name}")
                    youtube_url = upload_to_youtube_with_retry_standalone(
                        video_path=final_path,
                        video_name=video_name
                    )
                    if youtube_url:
                        print(f"✅ YouTube: {youtube_url}")
                    else:
                        print("⚠️  YouTube fallito, ma continuo con Drive e istruzioni")
                except Exception as e:
                    print(f"❌ Errore YouTube: {e}")
                    print("⚠️  YouTube fallito, ma continuo con Drive e istruzioni")
                
                # Salva i link nel CSV
                save_link_to_csv_standalone(video_name, video_path, final_path, youtube_url, drive_url, links_file, italian_instructions_url, english_instructions_url)
                
                return {
                    'video_name': video_name,
                    'original_path': video_path,
                    'processed_path': final_path,
                    'youtube_url': youtube_url,
                    'drive_url': drive_url,
                    'status': 'success'
                }
        
        print(f"❌ Errore elaborazione: {video_name}")
        return {
            'video_name': video_name,
            'original_path': video_path,
            'status': 'error'
        }
            
    except Exception as e:
        print(f"❌ Errore elaborazione {video_name}: {str(e)}")
        return {
            'video_name': video_name,
            'original_path': video_path,
            'status': 'error',
            'error': str(e)
        }

def process_video_standalone(video_file, input_folder, temp_dir):
    """Funzione standalone per elaborazione video"""
    try:
        # Importa qui per evitare problemi di pickle
        import os
        import ffmpeg
        import json
        
        # Carica la configurazione
        with open("config.json", "r") as f:
            config = json.load(f)
        openai_api_key = config.get("openai_api_key")
        
        video_path = os.path.join(input_folder, video_file)
        video_name = os.path.splitext(video_file)[0]
        
        print(f"🎬 Elaborazione: {video_name}")
        print(f"📁 Directory temporanea: {temp_dir}")
        
        # Fase 1: Genera sottotitoli
        print("🔧 DEBUG: Step 1 - Generating subtitles...")
        subtitles_result = generate_subtitles_only(
            input_video=video_path,
            openai_api_key=openai_api_key,
            output_dir=temp_dir
        )
        
        if not subtitles_result['success']:
            print(f"❌ Errore generazione sottotitoli: {subtitles_result.get('error', 'Errore sconosciuto')}")
            return {
                'video_name': video_name,
                'original_path': video_path,
                'status': 'error',
                'error': subtitles_result.get('error', 'Errore generazione sottotitoli')
            }
        
        print("🔧 DEBUG: Step 1 completed - Subtitles generated")
        
        # Fase 2: Completa elaborazione
        print("🔧 DEBUG: Step 2 - Finalizing video processing...")
        result = finalize_video_processing(
            input_video=video_path,
            srt_it_file=subtitles_result['srt_it_file'],
            srt_en_file=subtitles_result['srt_en_file'],
            output_dir=temp_dir,
            italian_height=120,
            english_height=60
        )
        
        if not result['success']:
            print(f"❌ Errore elaborazione finale: {result.get('error', 'Errore sconosciuto')}")
            return {
                'video_name': video_name,
                'original_path': video_path,
                'status': 'error',
                'error': result.get('error', 'Errore elaborazione finale')
            }
        
        print("🔧 DEBUG: Step 2 completed - Video processing finalized")
        
        # Combina i risultati
        final_result = {
            'video_name': video_name,
            'original_path': video_path,
            'status': 'success',
            'video_with_music': result['video_with_music'],
            'final_video': result['final_video'],
            'segments': subtitles_result['segments'],
            'has_voice': True
        }
        
        return final_result
        
    except Exception as e:
        print(f"❌ Errore elaborazione video: {e}")
        return {
            'video_name': video_name if 'video_name' in locals() else 'unknown',
            'original_path': video_path if 'video_path' in locals() else 'unknown',
            'status': 'error',
            'error': str(e)
        }

def save_link_to_csv_standalone(video_name, original_path, processed_path, youtube_url, drive_url, links_file, italian_instructions_url=None, english_instructions_url=None):
    """Funzione standalone per salvare link nel CSV"""
    print(f"🔧 DEBUG: save_link_to_csv_standalone - video: {video_name}, file: {links_file}")
    print(f"🔧 DEBUG: URLs - YouTube: {youtube_url}, Drive: {drive_url}")
    print(f"🔧 DEBUG: Instructions - IT: {italian_instructions_url}, EN: {english_instructions_url}")
    
    try:
        import csv
        import os
        from datetime import datetime
        
        # Crea il file se non esiste
        file_exists = os.path.exists(links_file)
        print(f"🔧 DEBUG: CSV file exists: {file_exists}")
        
        with open(links_file, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['timestamp', 'video_name', 'original_path', 'processed_path', 'youtube_url', 'drive_url', 'italian_instructions_url', 'english_instructions_url']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
                print(f"🔧 DEBUG: Created CSV header")
            
            row_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'video_name': video_name,
                'original_path': original_path,
                'processed_path': processed_path,
                'youtube_url': youtube_url or '',
                'drive_url': drive_url or '',
                'italian_instructions_url': italian_instructions_url or '',
                'english_instructions_url': english_instructions_url or ''
            }
            
            writer.writerow(row_data)
            print(f"🔧 DEBUG: Written row: {row_data}")
        
        print(f"✅ Link salvato in: {links_file}")
        print(f"🔧 DEBUG: File size: {os.path.getsize(links_file)} bytes")
        
    except Exception as e:
        print(f"❌ Errore salvataggio CSV: {e}")
        import traceback
        print(f"❌ DEBUG: Traceback: {traceback.format_exc()}")

class CompleteVideoProcessor:
    def __init__(self):
        self.music_file = "Elaborazione/audio.mp3"
        self.input_folder = "Video_Umbria"  # Cartella di input predefinita
        self.links_file = f"processed_videos_{self.input_folder}.csv"  # CSV specifico per cartella
        
        # Carica configurazioni
        self.config = self.load_config()
        self.client = OpenAI(api_key=self.config.get('openai_api_key')) if self.config else None
        
        # Inizializza servizi Drive
        self.drive_service = None
        
        print("🎬 Processore Video Completo")
        print("=" * 50)
    
    def load_config(self):
        """Carica configurazione da config.json"""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
            print("✅ Configurazione caricata da config.json")
            return config
        except Exception as e:
            print(f"❌ Errore nel caricamento config.json: {e}")
            return None
    
    def authenticate_drive(self):
        """Autentica per Google Drive"""
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        
        creds = None
        drive_token_file = "drive_token.pickle"
        
        if os.path.exists(drive_token_file):
            with open(drive_token_file, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('client_secrets.json'):
                    print(f"❌ File client_secrets.json non trovato")
                    return None
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    'client_secrets.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(drive_token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        self.drive_service = build('drive', 'v3', credentials=creds)
        return self.drive_service
    
    def change_input_folder(self):
        """Permette di cambiare la cartella di input"""
        print(f"\n📁 Cartella di input attuale: {self.input_folder}")
        print("Cartelle disponibili:")
        
        # Lista tutte le cartelle che potrebbero contenere video
        available_folders = []
        for item in os.listdir('.'):
            if os.path.isdir(item) and any(name in item.lower() for name in ['video', 'Umbria']):
                available_folders.append(item)
        
        for i, folder in enumerate(available_folders, 1):
            print(f"{i}. {folder}")
        
        try:
            choice = int(input("\nSeleziona numero della cartella (0 per mantenere attuale): "))
            if 1 <= choice <= len(available_folders):
                new_folder = available_folders[choice - 1]
                self.input_folder = new_folder
                self.links_file = f"processed_videos_{self.input_folder}.csv"
                print(f"✅ Cartella di input cambiata in: {self.input_folder}")
                print(f"✅ File CSV: {self.links_file}")
            elif choice == 0:
                print("✅ Cartella mantenuta")
            else:
                print("❌ Selezione non valida")
        except ValueError:
            print("❌ Inserisci un numero valido")
    
    def save_link_to_csv(self, video_name, original_path, processed_path, youtube_url=None, drive_url=None, italian_instructions_url=None, english_instructions_url=None):
        """Salva i link del video in CSV"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Crea il file CSV se non esiste
        file_exists = os.path.exists(self.links_file)
        
        with open(self.links_file, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['timestamp', 'video_name', 'original_path', 'processed_path', 'youtube_url', 'drive_url', 'italian_instructions_url', 'english_instructions_url']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'timestamp': timestamp,
                'video_name': video_name,
                'original_path': original_path,
                'processed_path': processed_path,
                'youtube_url': youtube_url or '',
                'drive_url': drive_url or '',
                'italian_instructions_url': italian_instructions_url or '',
                'english_instructions_url': english_instructions_url or ''
            })
        
        print(f"✅ Link salvato in {self.links_file}")
    
    def get_video_files(self):
        """Ottiene la lista dei file video"""
        if not os.path.exists(self.input_folder):
            print(f"❌ Cartella {self.input_folder} non trovata!")
            return []
        
        video_files = []
        for file in os.listdir(self.input_folder):
            if file.lower().endswith(('.mov', '.mp4', '.avi', '.mkv')):
                video_files.append(file)
        
        return sorted(video_files)
    
    def extract_audio_from_video(self, video_path, audio_path):
        """Estrae audio da un video"""
        try:
            print(f"🔊 Estrazione audio da {os.path.basename(video_path)}")
            
            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(stream, audio_path, acodec='pcm_s16le', ac=1, ar='16000')
            ffmpeg.run(stream, overwrite_output=True)
            
            print(f"✅ Audio estratto: {audio_path}")
            return True
        except Exception as e:
            print(f"❌ Errore estrazione audio: {e}")
            return False
    
    def transcribe_audio(self, audio_path):
        """Trascrive l'audio usando OpenAI Whisper"""
        try:
            print("📝 Trascrizione audio...")
            
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="it"  # Specifica italiano
                )
            
            transcription = response.text.strip()
            print(f"✅ Trascrizione completata: {len(transcription)} caratteri")
            print(f"📄 Contenuto trascrizione: '{transcription}'")
            
            return transcription
        except Exception as e:
            print(f"❌ Errore trascrizione: {e}")
            return None
    
    def optimize_transcription(self, transcription):
        """Ottimizza la trascrizione per i sottotitoli"""
        try:
            if not self.client:
                return transcription
            
            prompt = f"""
Ottimizza questa trascrizione per i sottotitoli:

Trascrizione originale: "{transcription}"

IMPORTANTE:
- Mantieni il significato originale
- Correggi errori di trascrizione
- Rendi il testo più fluido e naturale
- Mantieni la lunghezza appropriata per i sottotitoli
- NON aggiungere punti alla fine delle frasi

Trascrizione ottimizzata:"""
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Sei un esperto nell'ottimizzazione di trascrizioni per sottotitoli. Mantieni sempre il significato originale ma rendi il testo più fluido e naturale."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Errore ottimizzazione: {e}")
            return transcription
    
    def distribute_subtitles(self, transcription):
        """Distribuisce la trascrizione in segmenti per sottotitoli"""
        try:
            if not self.client:
                return []
            
            prompt = f"""
Distribuisci questa trascrizione in segmenti per sottotitoli:

Trascrizione: "{transcription}"

IMPORTANTE:
- Crea segmenti di massimo 25 caratteri per riga
- Massimo 2 righe per segmento
- Ogni segmento deve essere comprensibile
- Mantieni la cronologia temporale
- Traduci ogni segmento in inglese

Formato richiesto:
Segmento 1: [testo italiano] -> [testo inglese]
Segmento 2: [testo italiano] -> [testo inglese]
..."""
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Sei un esperto nella distribuzione di testi per sottotitoli. Crea sempre segmenti bilanciati e comprensibili."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.1
            )
            
            # Parsing della risposta
            segments = []
            lines = response.choices[0].message.content.strip().split('\n')
            
            for line in lines:
                if ':' in line and '->' in line:
                    parts = line.split('->')
                    if len(parts) == 2:
                        italian = parts[0].split(':')[1].strip()
                        english = parts[1].strip()
                        segments.append({
                            'text': italian,
                            'text_en': english,
                            'start': '00:00:00',
                            'end': '00:00:05'
                        })
            
            return segments
        except Exception as e:
            print(f"❌ Errore distribuzione sottotitoli: {e}")
            return []
    
    def create_srt_file(self, subtitles, language):
        """Crea file SRT per i sottotitoli"""
        try:
            srt_content = ""
            for i, segment in enumerate(subtitles, 1):
                text = segment.get('text' if language == 'italiano' else 'text_en', '')
                start_time = segment.get('start', '00:00:00')
                end_time = segment.get('end', '00:00:05')
                
                srt_content += f"{i}\n"
                srt_content += f"{start_time},000 --> {end_time},000\n"
                srt_content += f"{text}\n\n"
            
            return srt_content
        except Exception as e:
            print(f"❌ Errore creazione SRT: {e}")
            return ""
    

    
    def create_instructions(self, transcription, video_name, language="italiano"):
        """Crea istruzioni in formato elenco puntato"""
        try:
            # Se la trascrizione è troppo breve o generica, usa il nome del video
            if len(transcription) < 50 or "amara" in transcription.lower():
                instructions = self.create_instructions_from_video_name(video_name, language)
                return instructions
            
            if language == "italiano":
                prompt = f"""
Analizza attentamente questa trascrizione audio e crea istruzioni SPECIFICHE per il contenuto del video.

Video: {video_name}
Trascrizione: "{transcription}"

IMPORTANTE: 
- Le istruzioni devono essere SPECIFICHE per il contenuto del video
- NON creare istruzioni generiche come "accedi al sito" o "seguire le istruzioni"
- Analizza il contenuto della trascrizione e crea istruzioni concrete
- Se la trascrizione è troppo breve, deduci il contenuto dal nome del video
- Massimo 5 punti in formato elenco numerato (1., 2., 3., ecc.)
- Frasi brevi e concrete
- NON mettere punti alla fine delle istruzioni

Esempio di istruzioni specifiche (non generiche):
1. Verifica che la caldaia sia spenta prima di iniziare
2. Controlla il livello dell'acqua nel serbatoio
3. Regola la temperatura al valore desiderato
4. Monitora la pressione durante il funzionamento
5. Chiudi la valvola principale quando hai finito

Istruzioni specifiche per questo video:
"""
            else:  # inglese - traduci da italiano
                prompt = f"""
Traduci queste istruzioni italiane in inglese, mantenendo lo stesso formato e struttura:

Istruzioni italiane:
{transcription}

IMPORTANTE:
- Mantieni il formato elenco numerato 1., 2., 3., ecc.
- NON mettere punti alla fine delle istruzioni
- Traduci fedelmente mantenendo la stessa struttura

Traduzione in inglese:"""
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Sei un esperto nell'analisi di contenuti video. Crea SEMPRE istruzioni specifiche e concrete basate sul contenuto reale del video. MAI istruzioni generiche o vaghe. Analizza attentamente la trascrizione e deduci il contenuto specifico."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            instructions = response.choices[0].message.content.strip()
            
            # Pulisci il testo rimuovendo il prompt se presente
            if language == "inglese":
                # Rimuovi il prompt se presente nel risultato
                if "IMPORTANT:" in instructions:
                    instructions = instructions.split("IMPORTANT:")[0].strip()
                if "Traduzione in inglese:" in instructions:
                    instructions = instructions.split("Traduzione in inglese:")[1].strip()
            
            return instructions
        except Exception as e:
            print(f"❌ Errore creazione istruzioni: {e}")
            return None
    
    def save_text_file(self, content, filename):
        """Salva contenuto in file TXT temporaneo"""
        try:
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
            temp_file.write(content)
            temp_file.close()
            return temp_file.name
        except Exception as e:
            print(f"❌ Errore salvataggio file TXT: {e}")
            return None
    
    def upload_text_to_drive(self, file_path, filename, video_name):
        """Carica file TXT su Google Drive"""
        try:
            if not self.drive_service:
                self.authenticate_drive()
                if not self.drive_service:
                    return None
            
            print(f"☁️  Caricamento {filename} su Google Drive")
            
            file_metadata = {
                'name': filename,
                'parents': ['root']
            }
            
            media = MediaFileUpload(file_path, mimetype='text/plain')
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            drive_url = file.get('webViewLink')
            print(f"✅ Drive: {drive_url}")
            return drive_url
            
        except Exception as e:
            print(f"❌ Errore caricamento Drive: {e}")
            return None
    
    def upload_to_youtube_with_retry(self, video_path, video_name, max_retries=3):
        """Carica video su YouTube con retry automatico e riautenticazione"""
        for attempt in range(max_retries):
            try:
                print(f"📺 Tentativo {attempt + 1}/{max_retries} - Caricamento su YouTube: {video_name}")
                
                youtube_url = upload_to_youtube(
                    video_path=video_path,
                    title=f"{video_name} Umbria - Video Tutorial",
                    privacy_status="unlisted",
                    description=f"Video tutorial su {video_name} Umbria",
                    tags="Umbria, tutorial, video, guida"
                )
                
                if youtube_url:
                    print(f"✅ YouTube: {youtube_url}")
                    return youtube_url
                else:
                    print("❌ Errore caricamento YouTube")
                    
            except Exception as e:
                error_msg = str(e).lower()
                print(f"❌ Errore YouTube (tentativo {attempt + 1}): {e}")
                
                # Se è un errore di autenticazione o permessi, forza riautenticazione
                if any(keyword in error_msg for keyword in ['insufficient', 'permission', 'scope', 'token', 'authentication']):
                    print("🔄 Errore di autenticazione rilevato, forzando nuova autenticazione...")
                    
                    # Rimuovi il token YouTube esistente
                    youtube_token_file = "youtube_token.pickle"
                    if os.path.exists(youtube_token_file):
                        try:
                            os.remove(youtube_token_file)
                            print("🗑️ Token YouTube rimosso")
                        except:
                            pass
                    
                    # Aspetta un momento prima del prossimo tentativo
                    import time
                    time.sleep(2)
                    
                    if attempt < max_retries - 1:
                        print("🔄 Riprovo con nuova autenticazione...")
                        continue
                    else:
                        print("❌ Impossibile caricare su YouTube dopo tutti i tentativi")
                        return None
                
                # Per altri errori, aspetta prima di riprovare
                if attempt < max_retries - 1:
                    print(f"⏳ Attendo 5 secondi prima del prossimo tentativo...")
                    import time
                    time.sleep(5)
                else:
                    print("❌ Impossibile caricare su YouTube dopo tutti i tentativi")
                    return None
        
        return None
    
    def create_instructions_for_video(self, video_name):
        """Crea istruzioni per un video specifico"""
        try:
            
            # 1. Estrai audio dal video originale
            # Prova prima .mp4, poi .MOV
            original_video_path = os.path.join(self.input_folder, f"{video_name}.mp4")
            if not os.path.exists(original_video_path):
                original_video_path = os.path.join(self.input_folder, f"{video_name}.MOV")
                if not os.path.exists(original_video_path):
                    print(f"❌ Video originale non trovato: {video_name}.mp4 o {video_name}.MOV")
                    return None, None
            
            temp_dir = tempfile.mkdtemp()
            audio_path = os.path.join(temp_dir, f"{video_name}_audio.wav")
            
            self.extract_audio_from_video(original_video_path, audio_path)
            if not os.path.exists(audio_path):
                return None, None
            
            # 2. Trascrivi audio
            transcription = self.transcribe_audio(audio_path)
            if not transcription:
                return None, None
            
            # 3. Crea istruzioni in italiano
            italian_instructions = self.create_instructions(transcription, video_name, "italiano")
            if not italian_instructions:
                return None, None
            
            # 4. Traduci istruzioni in inglese
            english_instructions = self.create_instructions(italian_instructions, video_name, "inglese")
            if not english_instructions:
                return None, None
            
            # 5. Salva file TXT
            italian_file = self.save_text_file(italian_instructions, f"{video_name}_Istruzioni_IT.txt")
            english_file = self.save_text_file(english_instructions, f"{video_name}_Istruzioni_EN.txt")
            
            if not italian_file or not english_file:
                return None, None
            
            # 6. Carica su Drive
            italian_url = self.upload_text_to_drive(italian_file, f"{video_name}_Istruzioni_IT.txt", video_name)
            english_url = self.upload_text_to_drive(english_file, f"{video_name}_Istruzioni_EN.txt", video_name)
            
            if not italian_url or not english_url:
                return None, None
            
            # 7. Pulisci file temporanei
            try:
                os.remove(audio_path)
                os.remove(italian_file)
                os.remove(english_file)
                os.rmdir(temp_dir)
            except:
                pass
            
            return italian_url, english_url
            
        except Exception as e:
            print(f"❌ Errore creazione istruzioni per {video_name}: {e}")
            return None, None
    
    def process_video_with_music_and_subtitles(self, video_file):
        """Elabora video con musica e sottotitoli"""
        video_path = os.path.join(self.input_folder, video_file)
        video_name = os.path.splitext(video_file)[0]
        
        print(f"\n🎬 Elaborazione: {video_name}")
        print("=" * 50)
        
        # Crea directory temporanea
        temp_dir = tempfile.mkdtemp(prefix=f"complete_processing_{video_name}_")
        print(f"📁 Directory temporanea: {temp_dir}")
        
        try:
            # 1. Elabora video con sottotitoli (senza musica)
            print("📝 Step 1: Elaborazione video con sottotitoli...")
            result = process_video(
                input_video=video_path,
                music_file=None,  # Nessuna musica per ora
                openai_api_key=self.config['openai_api_key'],
                output_dir=temp_dir,
                custom_prompt=None,
                video_type=None,
                italian_height=120,
                english_height=60
            )
            
            if not result['success']:
                print(f"❌ Errore nell'elaborazione di {video_name}")
                return False
            
            video_with_subtitles = result['final_video']
            print(f"✅ Video con sottotitoli: {os.path.basename(video_with_subtitles)}")
            
            # 2. Aggiungi musica e rimuovi audio originale
            print("🎵 Step 2: Aggiunta musica di sottofondo...")
            if os.path.exists(self.music_file):
                video_with_music = os.path.join(temp_dir, "video_with_music.mp4")
                
                # Estrai solo il video (senza audio)
                video_only = os.path.join(temp_dir, "video_only.mp4")
                try:
                    import ffmpeg
                    stream = ffmpeg.input(video_with_subtitles)
                    stream = ffmpeg.output(stream, video_only, vcodec='copy', an=None)
                    ffmpeg.run(stream, overwrite_output=True)
                    print("✅ Audio originale rimosso")
                except Exception as e:
                    print(f"❌ Errore rimozione audio: {e}")
                    return False
                
                # Aggiungi musica di sottofondo
                try:
                    add_background_music(video_only, self.music_file, video_with_music)
                    print(f"✅ Musica aggiunta: {os.path.basename(self.music_file)}")
                except Exception as e:
                    print(f"❌ Errore aggiunta musica: {e}")
                    return False
                
                final_video = video_with_music
            else:
                print(f"⚠️  File musica non trovato: {self.music_file}")
                final_video = video_with_subtitles
            
            # 3. Crea istruzioni per il video
            print("📝 Step 3: Creazione istruzioni...")
            italian_instructions_url, english_instructions_url = self.create_instructions_for_video(video_name)
            if not italian_instructions_url or not english_instructions_url:
                print(f"❌ Errore nella creazione delle istruzioni per {video_name}")
                return False
            
            # 4. Upload su Drive e YouTube
            youtube_url = None
            drive_url = None
            
            # Upload su Drive
            print("☁️  Step 4: Upload su Google Drive...")
            try:
                drive_url = upload_video_to_drive(final_video, video_name, "video_elaborato")
                if drive_url:
                    print(f"✅ Drive: {drive_url}")
                else:
                    print("❌ Errore caricamento Drive")
            except Exception as e:
                print(f"❌ Errore Drive: {e}")
            
            # Upload su YouTube (opzionale - continua anche se fallisce)
            print("📺 Step 5: Upload su YouTube...")
            try:
                youtube_url = self.upload_to_youtube_with_retry(final_video, video_name)
                if youtube_url:
                    print(f"✅ YouTube: {youtube_url}")
                else:
                    print("⚠️  YouTube fallito, ma continuo con Drive e istruzioni")
            except Exception as e:
                print(f"❌ Errore YouTube: {e}")
                print("⚠️  YouTube fallito, ma continuo con Drive e istruzioni")
            
            # 5. Mostra informazioni finali
            if os.path.exists(final_video):
                size_mb = os.path.getsize(final_video) / (1024 * 1024)
                print(f"✅ Video finale: {size_mb:.1f} MB")
                
                # Salva link
                self.save_link_to_csv(
                    video_name=video_name,
                    original_path=video_path,
                    processed_path=final_video,
                    youtube_url=youtube_url,
                    drive_url=drive_url,
                    italian_instructions_url=italian_instructions_url,
                    english_instructions_url=english_instructions_url
                )
                
                return final_video
            else:
                print("❌ Video finale non trovato")
                return False
                
        except Exception as e:
            print(f"❌ Errore generale per {video_name}: {e}")
            return False
    
    def show_video_info(self, video_path):
        """Mostra informazioni sul video"""
        if not os.path.exists(video_path):
            print(f"❌ File non trovato: {video_path}")
            return
        
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"\n📹 Informazioni video:")
        print(f"   📁 Percorso: {video_path}")
        print(f"   📏 Dimensione: {size_mb:.1f} MB")
        
        # Usa ffprobe per ottenere informazioni dettagliate
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_format', '-show_streams', video_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                
                if 'streams' in info:
                    for stream in info['streams']:
                        if stream['codec_type'] == 'video':
                            width = stream.get('width', 'N/A')
                            height = stream.get('height', 'N/A')
                            duration = stream.get('duration', 'N/A')
                            print(f"   📐 Risoluzione: {width}x{height}")
                            print(f"   ⏱️  Durata: {duration} secondi")
                            break
        except Exception as e:
            print(f"   ⚠️  Impossibile ottenere info dettagliate: {e}")
    
    def play_video(self, video_path):
        """Riproduce il video"""
        if not os.path.exists(video_path):
            print(f"❌ File non trovato: {video_path}")
            return
        
        print(f"\n🎬 Riproduzione video: {os.path.basename(video_path)}")
        print("   Premi 'q' per uscire dalla riproduzione")
        
        try:
            # Usa ffplay per riprodurre il video
            subprocess.run(['ffplay', video_path])
        except FileNotFoundError:
            print("❌ ffplay non trovato. Installa ffmpeg per la riproduzione.")
        except KeyboardInterrupt:
            print("\n⏹️  Riproduzione interrotta")
    
    def show_menu(self):
        """Mostra il menu principale"""
        print("\n" + "=" * 50)
        print("🎬 PROCESSORE VIDEO COMPLETO")
        print("=" * 50)
        print("1. 📋 Lista video disponibili")
        print("2. 🎬 Elabora un video specifico")
        print("3. 🔄 Elabora tutti i video (sequenziale)")
        print("4. 📝 Genera sottotitoli (controllo)")
        print("5. 🎬 Applica sottotitoli e upload")
        print("6. 📊 Visualizza link salvati")
        print("7. 🔄 Cambia cartella di input")
        print("0. ❌ Esci")
        print("=" * 50)
    
    def list_videos(self):
        """Mostra la lista dei video disponibili"""
        video_files = self.get_video_files()
        
        if not video_files:
            print("❌ Nessun video trovato nella cartella Video/")
            return
        
        print(f"\n📋 Video disponibili ({len(video_files)}):")
        for i, video in enumerate(video_files, 1):
            video_path = os.path.join(self.input_folder, video)
            size_mb = os.path.getsize(video_path) / (1024 * 1024)
            print(f"{i}. {video} ({size_mb:.1f} MB)")
    
    def process_specific_video(self):
        """Elabora un video specifico"""
        video_files = self.get_video_files()
        
        if not video_files:
            print("❌ Nessun video trovato!")
            return
        
        print(f"\n🎬 ELABORA VIDEO SPECIFICO")
        for i, video_file in enumerate(video_files, 1):
            size_mb = os.path.getsize(os.path.join(self.input_folder, video_file)) / (1024 * 1024)
            print(f"{i}. {video_file} ({size_mb:.1f} MB)")
        
        try:
            choice = int(input("\nSeleziona numero del video: "))
            if 1 <= choice <= len(video_files):
                selected_video = video_files[choice - 1]
                print(f"\n🎬 Elaborazione: {selected_video}")
                
                # Usa la funzione standalone
                result = process_single_video_standalone(
                    video_file=selected_video,
                    input_folder=self.input_folder,
                    config_file="config.json",
                    links_file=self.links_file
                )
                
                if result and result['status'] == 'success':
                    print(f"\n✅ Elaborazione completata!")
                    print(f"📁 Video elaborato: {result['processed_path']}")
                    if result.get('youtube_url'):
                        print(f"📺 YouTube: {result['youtube_url']}")
                    if result.get('drive_url'):
                        print(f"☁️  Drive: {result['drive_url']}")
                    
                    # Chiedi se vuole vedere il video
                    show_video = input("\n🎬 Vuoi vedere il video? (y/N): ").strip().lower()
                    if show_video == 'y':
                        self.play_video(result['processed_path'])
                else:
                    print(f"❌ Errore nell'elaborazione di {selected_video}")
            else:
                print("❌ Selezione non valida!")
        except ValueError:
            print("❌ Inserisci un numero valido!")
    
    def generate_subtitles_only(self):
        """Genera solo i sottotitoli per tutti i video (senza incollarli)"""
        video_files = self.get_video_files()
        
        if not video_files:
            print("❌ Nessun video trovato!")
            return
        
        print(f"\n📝 GENERAZIONE SOTTOTITOLI ({len(video_files)} video)")
        print("Questo processo genererà i sottotitoli e le istruzioni...")
        print("📁 I sottotitoli saranno salvati in CSV per controllo")
        print("⏸️  Il processo si fermerà per il tuo controllo")
        
        confirm = input("Procedere? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Operazione annullata")
            return
        
        # Crea cartella per i sottotitoli
        subtitles_dir = f"subtitles_{self.input_folder}"
        os.makedirs(subtitles_dir, exist_ok=True)
        
        successful = 0
        failed = 0
        
        for i, video_file in enumerate(video_files, 1):
            video_name = os.path.splitext(video_file)[0]
            print(f"\n📝 Progresso: {i}/{len(video_files)} - {video_name}")
            
            try:
                # Genera sottotitoli
                result = self.generate_subtitles_for_video(video_file, subtitles_dir)
                
                if result:
                    successful += 1
                    print(f"✅ Sottotitoli generati per: {video_name}")
                else:
                    failed += 1
                    print(f"❌ Fallito: {video_name}")
                    
            except Exception as e:
                failed += 1
                print(f"❌ Errore per {video_name}: {e}")
        
        print(f"\n✅ Generazione sottotitoli completata!")
        print(f"   ✅ Successi: {successful}")
        print(f"   ❌ Fallimenti: {failed}")
        print(f"📁 Sottotitoli salvati in: {subtitles_dir}")
        
        # Mostra i file generati
        self.show_subtitles_files(subtitles_dir)
        
        return subtitles_dir
    
    def generate_subtitles_for_video(self, video_file, subtitles_dir):
        """Genera sottotitoli per un singolo video"""
        try:
            video_path = os.path.join(self.input_folder, video_file)
            video_name = os.path.splitext(video_file)[0]
            
            # Crea directory temporanea
            temp_dir = tempfile.mkdtemp(prefix=f"subtitles_{video_name}_")
            
            # Estrai audio e trascrivi
            audio_path = os.path.join(temp_dir, f"{video_name}_audio.wav")
            self.extract_audio_from_video(video_path, audio_path)
            
            if not os.path.exists(audio_path):
                return False
            
            # Trascrivi audio
            transcription = self.transcribe_audio(audio_path)
            if not transcription:
                return False
            
            # Ottimizza trascrizione
            optimized_transcription = self.optimize_transcription(transcription)
            
            # Distribuisci sottotitoli
            distributed_subtitles = self.distribute_subtitles(optimized_transcription)
            
            # Crea file SRT
            italian_srt = self.create_srt_file(distributed_subtitles, "IT")
            english_srt = self.create_srt_file(distributed_subtitles, "EN")
            
            # Salva file CSV per controllo
            csv_file = os.path.join(subtitles_dir, f"{video_name}_subtitles.csv")
            self.save_subtitles_to_csv(video_name, distributed_subtitles, csv_file)
            
            # Pulisci file temporanei
            try:
                os.remove(audio_path)
                os.rmdir(temp_dir)
            except:
                pass
            
            return True
            
        except Exception as e:
            print(f"❌ Errore generazione sottotitoli: {e}")
            return False
    
    def save_subtitles_to_csv(self, video_name, subtitles, csv_file):
        """Salva sottotitoli in formato CSV per controllo"""
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Segmento', 'Inizio', 'Fine', 'Testo Italiano', 'Testo Inglese'])
                
                for i, segment in enumerate(subtitles, 1):
                    writer.writerow([
                        i,
                        segment.get('start', ''),
                        segment.get('end', ''),
                        segment.get('text', ''),
                        segment.get('text_en', '')
                    ])
            
            print(f"📄 CSV salvato: {csv_file}")
            
        except Exception as e:
            print(f"❌ Errore salvataggio CSV: {e}")
    
    def show_subtitles_files(self, subtitles_dir):
        """Mostra i file di sottotitoli generati"""
        print(f"\n📁 FILE SOTTOTITOLI GENERATI ({subtitles_dir}):")
        print("-" * 60)
        
        if os.path.exists(subtitles_dir):
            files = [f for f in os.listdir(subtitles_dir) if f.endswith('.csv')]
            for file in sorted(files):
                print(f"📄 {file}")
        else:
            print("❌ Nessun file trovato")
    
    def apply_subtitles_and_upload(self, subtitles_dir):
        """Applica i sottotitoli e carica i video"""
        print(f"\n🎬 APPLICAZIONE SOTTOTITOLI E UPLOAD")
        print("=" * 50)
        print("Questo processo incollerà i sottotitoli e caricherà i video...")
        
        confirm = input("Procedere con l'incollo dei sottotitoli? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Operazione annullata")
            return
        
        video_files = self.get_video_files()
        successful = 0
        failed = 0
        
        for i, video_file in enumerate(video_files, 1):
            video_name = os.path.splitext(video_file)[0]
            print(f"\n📝 Progresso: {i}/{len(video_files)} - {video_name}")
            
            try:
                # Usa la funzione standalone per consistenza
                result = process_single_video_standalone(
                    video_file=video_file,
                    input_folder=self.input_folder,
                    config_file="config.json",
                    links_file=self.links_file
                )
                
                if result and result['status'] == 'success':
                    successful += 1
                    print(f"✅ Completato: {video_name}")
                    if result.get('youtube_url'):
                        print(f"   📺 YouTube: {result['youtube_url']}")
                    if result.get('drive_url'):
                        print(f"   ☁️  Drive: {result['drive_url']}")
                else:
                    failed += 1
                    print(f"❌ Fallito: {video_name}")
                    
            except Exception as e:
                failed += 1
                print(f"❌ Errore per {video_name}: {e}")
        
        print(f"\n✅ Elaborazione completata!")
        print(f"   ✅ Successi: {successful}")
        print(f"   ❌ Fallimenti: {failed}")
        print(f"📊 Link salvati in: {self.links_file}")
    
    def process_all_videos(self):
        """Elabora tutti i video (sequenziale)"""
        video_files = self.get_video_files()
        
        if not video_files:
            print("❌ Nessun video trovato!")
            return
        
        print(f"\n🔄 ELABORAZIONE SEQUENZIALE TUTTI I VIDEO ({len(video_files)})")
        print("Questo processo elaborerà i video uno alla volta...")
        print("📺 Caricherà automaticamente su YouTube e Google Drive")
        print("📊 Salverà tutti i link nel file CSV")
        
        confirm = input("Procedere? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Operazione annullata")
            return
        
        successful = 0
        failed = 0
        
        for i, video_file in enumerate(video_files, 1):
            print(f"\n📝 Progresso: {i}/{len(video_files)}")
            
            # Usa la funzione standalone per consistenza
            result = process_single_video_standalone(
                video_file=video_file,
                input_folder=self.input_folder,
                config_file="config.json",
                links_file=self.links_file
            )
            
            if result and result['status'] == 'success':
                successful += 1
                print(f"✅ Completato: {result['video_name']}")
                if result.get('youtube_url'):
                    print(f"   📺 YouTube: {result['youtube_url']}")
                if result.get('drive_url'):
                    print(f"   ☁️  Drive: {result['drive_url']}")
            else:
                failed += 1
                print(f"❌ Fallito: {video_file}")
        
        print(f"\n✅ Elaborazione completata!")
        print(f"   ✅ Successi: {successful}")
        print(f"   ❌ Fallimenti: {failed}")
        print(f"📊 Link salvati in: {self.links_file}")
    
    def show_saved_links(self):
        """Visualizza link salvati"""
        if not os.path.exists(self.links_file):
            print("❌ Nessun link salvato")
            return
        
        print(f"\n📊 LINK SALVATI ({self.links_file})")
        print("-" * 80)
        
        with open(self.links_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                print(f"📅 {row['timestamp']}")
                print(f"🎬 {row['video_name']}")
                print(f"📁 {row['original_path']}")
                if row['youtube_url']:
                    print(f"📺 YouTube: {row['youtube_url']}")
                if row['drive_url']:
                    print(f"☁️  Drive: {row['drive_url']}")
                if row['italian_instructions_url']:
                    print(f"🇮🇹 Istruzioni: {row['italian_instructions_url']}")
                if row['english_instructions_url']:
                    print(f"🇬🇧 Istruzioni: {row['english_instructions_url']}")
                print("-" * 40)
    
    def run(self):
        """Esegue l'app"""
        if not self.config:
            print("❌ Configurazione non valida!")
            return
        
        while True:
            self.show_menu()
            
            try:
                choice = input("\nSeleziona opzione: ").strip()
                
                if choice == "1":
                    self.list_videos()
                elif choice == "2":
                    self.process_specific_video()
                elif choice == "3":
                    self.process_all_videos()
                elif choice == "4":
                    subtitles_dir = self.generate_subtitles_only()
                    if subtitles_dir:
                        print(f"\n⏸️  PAUSA PER CONTROLLO")
                        print("=" * 50)
                        print("📁 I sottotitoli sono stati generati in CSV")
                        print("📄 Controlla i file nella cartella:", subtitles_dir)
                        print("✅ Quando sei pronto, usa l'opzione 5 per continuare")
                        input("Premi ENTER per tornare al menu...")
                elif choice == "5":
                    subtitles_dir = f"subtitles_{self.input_folder}"
                    if os.path.exists(subtitles_dir):
                        self.apply_subtitles_and_upload(subtitles_dir)
                    else:
                        print("❌ Nessuna cartella sottotitoli trovata!")
                        print("📝 Usa prima l'opzione 4 per generare i sottotitoli")
                elif choice == "6":
                    self.show_saved_links()
                elif choice == "7":
                    self.change_input_folder()
                elif choice == "0":
                    print("👋 Arrivederci!")
                    break
                else:
                    print("❌ Opzione non valida!")
                    
            except KeyboardInterrupt:
                print("\n👋 Interruzione richiesta dall'utente")
                break
            except Exception as e:
                print(f"❌ Errore: {e}")

if __name__ == "__main__":
    processor = CompleteVideoProcessor()
    processor.run() 