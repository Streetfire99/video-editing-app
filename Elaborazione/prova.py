import openai
import os
import json
import re
from datetime import timedelta
import tempfile
import ffmpeg

def get_openai_client(api_key):
    """Inizializza il client OpenAI"""
    return openai.OpenAI(api_key=api_key)

def extract_audio_from_video(input_video, audio_file):
    """Estrae l'audio dal video"""
    try:
        stream = ffmpeg.input(input_video)
        stream = ffmpeg.output(stream, audio_file, vn=None, ac=1, ar=16000, acodec='pcm_s16le')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
    except Exception as e:
        raise Exception(f"Errore nell'estrazione audio: {e}")
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
    
    # Importa le funzioni per i prompt personalizzati
    import sys
    sys.path.append('..')
    from data_manager import get_prompt_for_video_type
    
    # Ottieni il prompt base per la tipologia di video
    if video_type:
        base_prompt = get_prompt_for_video_type(video_type)
    else:
        base_prompt = "You are a video subtitle editor specializing in instructional videos."
    
    base_prompt += """
Your task is to optimize the following raw transcription of an instructional video. The video shows a person performing the actions described in the audio. Follow these steps:

1. Keep the text in Italian, as it is the original language.
2. Write short, complete sentences that describe exactly what is shown in the video.
3. Each sentence should be self-contained and not reference previous or next actions.
4. Avoid long explanations or multiple actions in one sentence.
5. Keep each line under 25 characters to prevent overlap.
6. Each subtitle should be exactly 2 lines maximum.
7. DO NOT add any prefix to the text - just write the Italian text as is.
8. Provide the output as a JSON array of segments, where each segment has:
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

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": base_prompt.format(raw_transcription=raw_transcription)},
            {"role": "user", "content": raw_transcription}
        ]
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

    return optimized_texts

def format_timestamp(seconds):
    """Formatta i secondi in formato SRT"""
    td = timedelta(seconds=seconds)
    millis = int((td.total_seconds() % 1) * 1000)
    return str(td).split('.')[0].replace('.', ',') + f',{millis:03d}'

def split_text(text, max_length=25, max_lines=2):
    """Divide il testo in righe per i sottotitoli"""
    # First, try to split on natural sentence boundaries
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
        # Sottotitoli italiani
        stream = ffmpeg.input(input_video)
        stream = ffmpeg.output(stream, 'temp_with_it_subs.mp4',
                             vf=f"subtitles={subtitle_file_it}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={italian_height}'",
                             acodec='copy', vcodec='libx264', preset='medium', crf=23)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        # Sottotitoli inglesi
        stream = ffmpeg.input('temp_with_it_subs.mp4')
        stream = ffmpeg.output(stream, output_video,
                             vf=f"subtitles={subtitle_file_en}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV={english_height}'",
                             acodec='copy', vcodec='libx264', preset='medium', crf=23)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        # Pulisci il file temporaneo
        if os.path.exists('temp_with_it_subs.mp4'):
            os.remove('temp_with_it_subs.mp4')
            
    except Exception as e:
        raise Exception(f"Errore nell'aggiunta dei sottotitoli: {e}")

def process_video(input_video, music_file, openai_api_key, output_dir=".", custom_prompt=None, video_type=None, italian_height=75, english_height=50):
    """Processa il video completo"""
    try:
        # Inizializza OpenAI
        client = get_openai_client(openai_api_key)
        
        # Crea file temporanei
        audio_file = os.path.join(output_dir, "audio.wav")
        subtitle_file_it = os.path.join(output_dir, "subtitles_it.srt")
        subtitle_file_en = os.path.join(output_dir, "subtitles_en.srt")
        final_output = os.path.join(output_dir, "final_output.mp4")
        
        # 1. Estrai audio
        extract_audio_from_video(input_video, audio_file)
        
        # 2. Trascrivi audio
        transcript = transcribe_audio(audio_file, client)
        
        # 3. Ottimizza trascrizione
        raw_transcription = "\n".join([seg.text for seg in transcript.segments])
        optimized_texts = optimize_transcription(raw_transcription, client, custom_prompt, video_type)
        
        # 4. Distribuisci sottotitoli
        distributed_segments = distribute_subtitles(transcript.segments, optimized_texts)
        
        # 5. Crea file SRT
        create_srt_file(distributed_segments, subtitle_file_it, "IT")
        translate_subtitles(distributed_segments, client, subtitle_file_en, video_type)
        
        # 6. Aggiungi sottotitoli al video
        add_subtitles_to_video(input_video, subtitle_file_it, subtitle_file_en, final_output, italian_height, english_height)
        
        # Pulisci file temporanei
        for temp_file in [audio_file, subtitle_file_it, subtitle_file_en]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
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