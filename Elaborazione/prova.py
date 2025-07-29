import openai
import os
import json
import re
from datetime import timedelta
import tempfile
import ffmpeg
import time
import threading
import uuid
from pathlib import Path

# Lock per gestire la concurrency
processing_lock = threading.Lock()

def get_openai_client(api_key):
    """Inizializza il client OpenAI"""
    return openai.OpenAI(api_key=api_key)

def create_unique_temp_dir():
    """Crea una directory temporanea unica per evitare conflitti"""
    unique_id = str(uuid.uuid4())
    temp_dir = os.path.join(tempfile.gettempdir(), f"video_processing_{unique_id}")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def extract_audio_from_video(input_video, audio_file):
    """Estrae l'audio dal video"""
    try:
        stream = ffmpeg.input(input_video)
        stream = ffmpeg.output(stream, audio_file, acodec='pcm_s16le', ac=1, ar=16000)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
    except Exception as e:
        raise Exception(f"Errore nell'estrazione audio: {e}")

def transcribe_audio(audio_file, client):
    """Trascrive l'audio usando OpenAI Whisper"""
    try:
        with open(audio_file, "rb") as audio:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        return transcript
    except Exception as e:
        raise Exception(f"Errore nella trascrizione: {e}")

def optimize_transcription(raw_transcription, client, custom_prompt=None, video_type=None):
    """Ottimizza la trascrizione per i sottotitoli"""
    try:
        import sys
        sys.path.append('..')
        from data_manager import get_prompt_for_video_type
        
        if video_type and not custom_prompt:
            prompt = get_prompt_for_video_type(video_type)
        elif custom_prompt:
            prompt = custom_prompt
        else:
            prompt = """
You are an expert in creating clear, concise subtitles for instructional videos. 
Optimize the following transcription for subtitles, ensuring:
- Each subtitle is clear and easy to read
- Use imperative tone for instructions
- Keep each line under 25 characters
- Break long sentences appropriately
- Remove filler words and repetitions
- Make it suitable for dual-language subtitles (Italian/English)
            """
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw_transcription}
            ]
        )
        
        optimized_text = response.choices[0].message.content.strip()
        return [{"text": line.strip()} for line in optimized_text.split('\n') if line.strip()]
        
    except Exception as e:
        raise Exception(f"Errore nell'ottimizzazione: {e}")

def format_timestamp(seconds):
    """Formatta i secondi in formato SRT"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

def split_text(text, max_length=25, max_lines=2):
    """Divide il testo in linee per i sottotitoli"""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        if len(current_line + " " + word) <= max_length:
            current_line += (" " + word) if current_line else word
        else:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Parola troppo lunga, spezzala
                lines.append(word[:max_length])
                current_line = word[max_length:]
    
    if current_line:
        lines.append(current_line)
    
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
    """Crea un file SRT"""
    with open(output_file, "w", encoding="utf-8") as srt:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text']
            lines = split_text(text)
            srt.write(f"{i}\n{start} --> {end}\n[{language}] {lines[0]}\n{lines[1] if len(lines) > 1 else ''}\n\n")

def translate_subtitles(segments, client, output_file, video_type=None):
    """Traduce i sottotitoli in inglese"""
    import sys
    sys.path.append('..')
    from data_manager import get_translation_prompt_for_video_type
    
    if video_type:
        translation_prompt = get_translation_prompt_for_video_type(video_type)
    else:
        translation_prompt = """
You are a translator specializing in instructional videos for household appliances. Translate the following Italian text to English, ensuring:
- The translation is clear, concise, and suitable for subtitles.
- Use an imperative tone, avoiding questions or incomplete sentences.
- Keep each line under 25 characters to prevent overlap.
- IMPORTANT: Always translate to English, never leave any Italian text.
        """
    
    with open(output_file, "w", encoding="utf-8") as srt:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            translation = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": translation_prompt},
                    {"role": "user", "content": segment['text']}
                ]
            )
            text = translation.choices[0].message.content.strip()
            lines = split_text(text)
            srt.write(f"{i}\n{start} --> {end}\n[EN] {lines[0]}\n{lines[1] if len(lines) > 1 else ''}\n\n")

def add_background_music(input_video, music_file, output_video):
    """Aggiunge musica di sottofondo al video"""
    try:
        stream = ffmpeg.input(input_video)
        music = ffmpeg.input(music_file, stream_loop=-1)
        stream = ffmpeg.output(stream, music, output_video, 
                             filter_complex='[1:a]volume=0.2[a1];[0:v][a1]concat=n=1:v=1:a=1',
                             shortest=None, vcodec='copy', acodec='aac')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
    except Exception as e:
        raise Exception(f"Errore nell'aggiunta della musica: {e}")

def add_subtitles_to_video(input_video, subtitle_file_it, subtitle_file_en, output_video, italian_height=75, english_height=50):
    """Aggiunge sottotitoli duali al video"""
    try:
        # Crea file temporanei unici per evitare conflitti
        temp_it_subs = os.path.join(os.path.dirname(output_video), f"temp_it_subs_{uuid.uuid4().hex}.mp4")
        
        # Sottotitoli italiani
        stream = ffmpeg.input(input_video)
        stream = ffmpeg.output(stream, temp_it_subs,
                             vf=f"subtitles={subtitle_file_it}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={italian_height}'",
                             acodec='copy', vcodec='libx264', preset='medium', crf=23)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        # Sottotitoli inglesi
        stream = ffmpeg.input(temp_it_subs)
        stream = ffmpeg.output(stream, output_video,
                             vf=f"subtitles={subtitle_file_en}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={english_height}'",
                             acodec='copy', vcodec='libx264', preset='medium', crf=23)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        # Pulisci il file temporaneo
        if os.path.exists(temp_it_subs):
            os.remove(temp_it_subs)
            
    except Exception as e:
        raise Exception(f"Errore nell'aggiunta dei sottotitoli: {e}")

def process_video(input_video, music_file, openai_api_key, output_dir=".", custom_prompt=None, video_type=None, italian_height=75, english_height=50):
    """Processa il video completo con gestione concurrency"""
    # Usa lock per evitare conflitti
    with processing_lock:
        try:
            # Crea directory temporanea unica
            unique_output_dir = create_unique_temp_dir()
            
            # Inizializza OpenAI
            client = get_openai_client(openai_api_key)
            
            # Crea file temporanei con nomi unici
            audio_file = os.path.join(unique_output_dir, "audio.wav")
            subtitle_file_it = os.path.join(unique_output_dir, "subtitles_it.srt")
            subtitle_file_en = os.path.join(unique_output_dir, "subtitles_en.srt")
            final_output = os.path.join(output_dir, f"final_output_{uuid.uuid4().hex}.mp4")
            
            # 1. Estrai audio
            extract_audio_from_video(input_video, audio_file)
            
            # 2. Trascrivi audio
            transcript = transcribe_audio(audio_file, client)
            
            # 3. Ottimizza trascrizione
            raw_transcription = "\n".join([seg.text for seg in transcript.segments])
            optimized_texts = optimize_transcription(raw_transcription, client, custom_prompt, video_type)
            
            # 4. Distribuisci sottotitoli
            distributed_segments = distribute_subtitles(transcript.segments, optimized_texts)
            
            # 5. Traduci i sottotitoli e aggiungi ai segmenti
            import sys
            sys.path.append('..')
            from data_manager import get_translation_prompt_for_video_type
            
            if video_type:
                translation_prompt = get_translation_prompt_for_video_type(video_type)
            else:
                translation_prompt = """
You are a translator specializing in instructional videos for household appliances. Translate the following Italian text to English, ensuring:
- The translation is clear, concise, and suitable for subtitles.
- Use an imperative tone, avoiding questions or incomplete sentences.
- Keep each line under 25 characters to prevent overlap.
- IMPORTANT: Always translate to English, never leave any Italian text.
                """
            
            # Traduci ogni segmento e aggiungi il testo inglese
            for segment in distributed_segments:
                translation = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": translation_prompt},
                        {"role": "user", "content": segment['text']}
                    ]
                )
                segment['text_en'] = translation.choices[0].message.content.strip()
            
            # 6. Crea file SRT
            create_srt_file(distributed_segments, subtitle_file_it, "IT")
            translate_subtitles(distributed_segments, client, subtitle_file_en, video_type)
            
            # 7. Aggiungi sottotitoli al video
            add_subtitles_to_video(input_video, subtitle_file_it, subtitle_file_en, final_output, italian_height, english_height)
            
            # Pulisci file temporanei
            for temp_file in [audio_file, subtitle_file_it, subtitle_file_en]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            
            # Pulisci directory temporanea
            try:
                import shutil
                shutil.rmtree(unique_output_dir)
            except:
                pass
            
            return {
                'success': True,
                'final_video': final_output,
                'segments': distributed_segments,
                'has_voice': True,
                'transcript': raw_transcription,  # Mantieni per le box dei manuali
                'optimized_texts': optimized_texts  # Mantieni per le box dei manuali
            }
            
        except Exception as e:
            print(f"❌ Errore durante l'elaborazione: {e}")
            return {
                'success': False,
                'error': str(e),
                'has_voice': True
            }