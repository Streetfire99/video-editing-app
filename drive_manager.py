import os
import csv
import tempfile
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
import streamlit as st

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Inizializza il servizio Google Drive usando il service account"""
    try:
        # Carica le credenziali del service account
        google_credentials = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        
        if google_credentials:
            import json
            try:
                credentials_dict = json.loads(google_credentials)
                credentials = ServiceAccountCredentials.from_service_account_info(
                    credentials_dict,
                    scopes=SCOPES
                )
            except json.JSONDecodeError as e:
                st.error(f"❌ Errore nel parsing JSON delle credenziali: {e}")
                return None
        else:
            # Fallback al file locale
            if os.path.exists('service_account_key.json'):
                credentials = ServiceAccountCredentials.from_service_account_file(
                    'service_account_key.json',
                    scopes=SCOPES
                )
            else:
                st.error("Nessuna credenziale Google trovata. Configura GOOGLE_SHEETS_CREDENTIALS nei secrets.")
                return None

        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        st.error(f"Errore nel caricamento delle credenziali Google Drive: {e}")
        return None

def create_folder_if_not_exists(service, parent_folder_id, folder_name):
    """Crea una cartella se non esiste già"""
    try:
        # Cerca se la cartella esiste già
        query = f"name='{folder_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
        else:
            # Crea la nuova cartella
            folder_metadata = {
                'name': folder_name,
                'parents': [parent_folder_id],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            return folder.get('id')
    except HttpError as error:
        st.error(f'Errore nella creazione della cartella: {error}')
        return None

def upload_video_to_drive(video_path, apartment_name, video_type):
    """Carica il video su Google Drive nella struttura specificata"""
    try:
        service = get_drive_service()
        
        # ID della cartella principale (da sostituire con quello corretto)
        main_folder_id = "1w9P2oiRfFgsOOj82V7xOruhjnl-APCCi"
        
        # Crea cartella appartamento se non esiste
        apartment_folder_id = create_folder_if_not_exists(service, main_folder_id, apartment_name)
        if not apartment_folder_id:
            return None
        
        # Crea cartella tipologia video se non esiste
        type_folder_id = create_folder_if_not_exists(service, apartment_folder_id, video_type)
        if not type_folder_id:
            return None
        
        # Elimina video esistenti nella cartella
        query = f"'{type_folder_id}' in parents and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        for file in files:
            service.files().delete(fileId=file['id']).execute()
        
        # Carica il nuovo video
        file_metadata = {
            'name': f'{apartment_name}_{video_type}.mp4',
            'parents': [type_folder_id]
        }
        
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id,webViewLink').execute()
        
        return file.get('webViewLink')
        
    except HttpError as error:
        st.error(f'Errore nel caricamento su Drive: {error}')
        return None

def load_tracking_csv():
    """Carica il CSV di tracking degli appartamenti elaborati"""
    csv_file = 'apartments_tracking.csv'
    tracking_data = []
    
    if os.path.exists(csv_file):
        with open(csv_file, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            tracking_data = list(reader)
    
    return tracking_data

def save_tracking_csv(tracking_data):
    """Salva il CSV di tracking"""
    csv_file = 'apartments_tracking.csv'
    fieldnames = ['apartment', 'video_type', 'youtube_link', 'drive_link', 'italian_transcript', 'english_transcript', 'date_created']
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tracking_data)

def add_tracking_entry(apartment, video_type, youtube_link, drive_link, italian_transcript_path=None, english_transcript_path=None):
    """Aggiunge una nuova entry al tracking"""
    import datetime
    
    tracking_data = load_tracking_csv()
    
    # Rimuovi entry esistenti per lo stesso appartamento e tipo
    tracking_data = [entry for entry in tracking_data 
                    if not (entry['apartment'] == apartment and entry['video_type'] == video_type)]
    
    # Aggiungi nuova entry
    new_entry = {
        'apartment': apartment,
        'video_type': video_type,
        'youtube_link': youtube_link or '',
        'drive_link': drive_link or '',
        'italian_transcript': italian_transcript_path or '',
        'english_transcript': english_transcript_path or '',
        'date_created': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    tracking_data.append(new_entry)
    save_tracking_csv(tracking_data)

def get_processed_apartments():
    """Restituisce la lista degli appartamenti che hanno almeno un video elaborato"""
    tracking_data = load_tracking_csv()
    processed_apartments = {}
    
    for entry in tracking_data:
        apartment = entry['apartment']
        if apartment not in processed_apartments:
            processed_apartments[apartment] = []
        processed_apartments[apartment].append(entry['video_type'])
    
    return processed_apartments 