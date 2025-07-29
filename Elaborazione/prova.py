import openai
import subprocess
import os
import json
import re
from datetime import timedelta
import pickle
import tempfile
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import google_auth_oauthlib.flow
import threading
import glob
import random
from google.auth.transport.requests import Request

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === CONFIG ===
def get_openai_client(api_key):
    """Inizializza il client OpenAI"""
    return openai.OpenAI(api_key=api_key)

def extract_audio_from_video(input_video, audio_file):
    """Estrae l'audio dal video"""
    subprocess.run(["ffmpeg", "-y", "-i", input_video, "-vn", "-ac", "1", "-ar", "16000", audio_file])
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

    # Se c'è un prompt personalizzato, combinalo con quello base
    if custom_prompt:
        final_prompt = base_prompt + f"\n\nAdditional instructions:\n{custom_prompt}"
    else:
        final_prompt = base_prompt

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": final_prompt.format(raw_transcription=raw_transcription)},
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
    """Formatta i timestamp per SRT"""
    td = timedelta(seconds=seconds)
    millis = int((td.total_seconds() % 1) * 1000)
    return str(td).split('.')[0].replace('.', ',') + f',{millis:03d}'

def split_text(text, max_length=25, max_lines=2):
    """Divide il testo per i sottotitoli"""
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
    """Crea file SRT"""
    with open(output_file, "w", encoding="utf-8") as srt:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text']
            lines = split_text(text)
            # Aggiungi il prefisso solo alla prima riga
            if language == "IT":
                prefix = "[IT] "
            else:
                prefix = "[EN] "
            srt.write(f"{i}\n{start} --> {end}\n{prefix}{lines[0]}\n{lines[1] if len(lines) > 1 else ''}\n\n")

def translate_subtitles(segments, client, output_file, video_type=None):
    """Traduce i sottotitoli in inglese"""
    
    # Importa le funzioni per i prompt personalizzati
    import sys
    sys.path.append('..')
    from data_manager import get_translation_prompt_for_video_type
    
    # Ottieni il prompt di traduzione per la tipologia di video
    if video_type:
        translation_prompt = get_translation_prompt_for_video_type(video_type)
    else:
        translation_prompt = "You are a translator specializing in instructional videos."
    
    translation_prompt += """
Translate the following Italian text to English, ensuring:
- The translation is clear, concise, and suitable for subtitles.
- Use an imperative tone, avoiding questions or incomplete sentences.
- Keep each line under 25 characters to prevent overlap.
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
            lines = split_text(text)
            srt.write(f"{i}\n{start} --> {end}\n[EN] {lines[0]}\n{lines[1] if len(lines) > 1 else ''}\n\n")

def add_background_music(input_video, music_file, output_video):
    """Aggiunge musica di sottofondo"""
    subprocess.run([
        "ffmpeg", "-y",
        "-i", input_video,
        "-stream_loop", "-1",  # Loop infinito dell'audio
        "-i", music_file,
        "-filter_complex", "[1:a]volume=0.7[a1]",
        "-map", "0:v", "-map", "[a1]",
        "-c:v", "copy", "-shortest",
        output_video
    ])

def add_subtitles_to_video(input_video, subtitle_file_it, subtitle_file_en, output_video):
    """Aggiunge sottotitoli duali al video"""
    # Sottotitoli italiani - posizionati più in alto
    subprocess.run([
        "ffmpeg", "-y",
        "-i", input_video,
        "-vf", f"subtitles={subtitle_file_it}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV=75'",
        "-c:a", "copy",
        "temp_with_it_subs.mp4"
    ])

    # Sottotitoli inglesi - posizionati sotto quelli italiani
    subprocess.run([
        "ffmpeg", "-y",
        "-i", "temp_with_it_subs.mp4",
        "-vf", f"subtitles={subtitle_file_en}:force_style='FontSize=12,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BackColour=&H00FFFFFF&,BorderStyle=1,Alignment=2,MarginV=50'",
        "-c:a", "copy",
        output_video
    ])

    # Rimuovi il file temporaneo
    if os.path.exists("temp_with_it_subs.mp4"):
        os.remove("temp_with_it_subs.mp4")

def process_video(input_video, music_file, openai_api_key, output_dir=".", custom_prompt=None, video_type=None):
    """Funzione principale per elaborare il video"""
    # Configura file di output
    audio_file = os.path.join(output_dir, "audio.wav")
    subtitle_file_it = os.path.join(output_dir, "subtitles_it.srt")
    subtitle_file_en = os.path.join(output_dir, "subtitles_en.srt")
    video_with_music = os.path.join(output_dir, "video_with_music.mp4")
    final_output = os.path.join(output_dir, "final_output.mp4")
    
    # Inizializza client OpenAI
    client = get_openai_client(openai_api_key)
    
    try:
        # 1. Estrai l'audio dal video
        extract_audio_from_video(input_video, audio_file)
        
        # 2. Trascrivi l'audio
        transcript = transcribe_audio(audio_file, client)
        
        # 3. Ottimizza la trascrizione
        raw_transcription = "\n".join([seg.text for seg in transcript.segments])
        optimized_texts = optimize_transcription(raw_transcription, client, custom_prompt, video_type)
        
        # 4. Distribuisci i sottotitoli
        distributed_segments = distribute_subtitles(transcript.segments, optimized_texts)
        
        # 5. Crea file SRT italiani
        create_srt_file(distributed_segments, subtitle_file_it, "IT")
        
        # 6. Traduci e crea file SRT inglesi
        translate_subtitles(distributed_segments, client, subtitle_file_en, video_type)
        
        # 7. Aggiungi musica di sottofondo
        if music_file:
            add_background_music(input_video, music_file, video_with_music)
        else:
            # Se non c'è musica, copia il video originale
            subprocess.run(["ffmpeg", "-y", "-i", input_video, "-c", "copy", video_with_music])
        
        # 8. Aggiungi sottotitoli duali
        add_subtitles_to_video(video_with_music, subtitle_file_it, subtitle_file_en, final_output)
        
        return {
            "success": True,
            "final_video": final_output,
            "subtitles_it": subtitle_file_it,
            "subtitles_en": subtitle_file_en,
            "transcript": raw_transcription,
            "segments": distributed_segments
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
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
        logger.error(f"Errore nell'estrazione dell'ID del file: {e}")
        return None

def combine_instructions(existing_instructions, new_instructions):
    """Combina le istruzioni esistenti con le nuove usando OpenAI"""
    try:
        # Carica la configurazione dalle variabili d'ambiente
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            print("❌ OPENAI_API_KEY non trovata nelle variabili d'ambiente")
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