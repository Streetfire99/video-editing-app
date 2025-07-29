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
import io

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Ottiene il servizio Google Drive"""
    try:
        print("🔧 DEBUG: Starting get_drive_service")
        
        # Prova prima da Streamlit secrets
        credentials_str = st.secrets.get('GOOGLE_SHEETS_CREDENTIALS')
        if credentials_str:
            print("🔧 DEBUG: Got credentials from secrets:", type(credentials_str))
            
            # Se è una stringa JSON, convertila in dizionario
            if isinstance(credentials_str, str):
                print("🔧 DEBUG: Converting string to dict")
                import json
                credentials_dict = json.loads(credentials_str)
                print("🔧 DEBUG: JSON parsing successful")
            else:
                credentials_dict = credentials_str
                print("🔧 DEBUG: Using secrets directly")
        else:
            # Fallback alle variabili d'ambiente
            credentials_str = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
            if not credentials_str:
                st.error("❌ GOOGLE_SHEETS_CREDENTIALS non trovata nei secrets o nelle variabili d'ambiente")
                return None
            
            import json
            credentials_dict = json.loads(credentials_str)
        
        print("🔧 DEBUG: Parsed credentials keys:", list(credentials_dict.keys()))
        
        # Correggi automaticamente la private_key se necessario
        if 'private_key' in credentials_dict:
            private_key = credentials_dict['private_key']
            print("🔧 DEBUG: private_key present:", bool(private_key))
            print("🔧 DEBUG: private_key length:", len(private_key))
            print("🔧 DEBUG: private_key starts with:", private_key[:50])
            print("🔧 DEBUG: private_key ends with:", private_key[-50:])
            
            # Conta i \\n e \n
            double_backslash_count = private_key.count('\\n')
            single_backslash_count = private_key.count('\n')
            print("🔧 DEBUG: \\n count:", double_backslash_count)
            print("🔧 DEBUG: \n count:", single_backslash_count)
            
            # Sostituisci \\n con \n se necessario
            if '\\n' in private_key:
                print("🔧 DEBUG: Fixing \\n in private_key")
                private_key = private_key.replace('\\n', '\n')
                credentials_dict['private_key'] = private_key
                print("🔧 DEBUG: After fix - \\n count:", private_key.count('\\n'))
                print("🔧 DEBUG: After fix - \n count:", private_key.count('\n'))
            
            # Verifica che la chiave inizi e finisca correttamente
            if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                print("❌ DEBUG: private_key doesn't start with BEGIN")
            if not private_key.endswith('-----END PRIVATE KEY-----'):
                print("❌ DEBUG: private_key doesn't end with END")
            
            # Verifica che non ci siano caratteri strani
            print("🔧 DEBUG: private_key contains \\r:", '\\r' in private_key)
            print("🔧 DEBUG: private_key contains \\t:", '\\t' in private_key)
        
        print("🔧 DEBUG: Creating credentials from service account info")
        print("🔧 DEBUG: Credentials dict keys:", list(credentials_dict.keys()))
        
        # Crea le credenziali
        from google.oauth2.service_account import Credentials
        credentials = Credentials.from_service_account_info(credentials_dict)
        
        print("🔧 DEBUG: Credentials created successfully")
        
        # Crea il servizio Drive
        from googleapiclient.discovery import build
        service = build('drive', 'v3', credentials=credentials)
        
        print("🔧 DEBUG: Service built successfully")
        return service
        
    except Exception as e:
        print("❌ DEBUG: Error creating credentials:", str(e))
        print("❌ DEBUG: Error type:", type(e))
        st.error(f"❌ Errore nel caricamento delle credenziali Google Drive: {e}")
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
    """Carica il CSV di tracking degli appartamenti elaborati da Google Drive"""
    try:
        service = get_drive_service()
        if not service:
            return []
        
        # ID della cartella principale
        main_folder_id = "1w9P2oiRfFgsOOj82V7xOruhjnl-APCCi"
        
        # Cerca il file CSV nella cartella principale
        query = f"'{main_folder_id}' in parents and name='apartments_tracking.csv' and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        if files:
            # Scarica il file CSV
            file_id = files[0]['id']
            request = service.files().get_media(fileId=file_id)
            file_content = request.execute()
            
            # Decodifica il contenuto
            csv_content = file_content.decode('utf-8')
            
            # Parsa il CSV
            import csv
            from io import StringIO
            
            tracking_data = []
            csv_reader = csv.DictReader(StringIO(csv_content))
            tracking_data = list(csv_reader)
            
            return tracking_data
        else:
            # File non esiste, restituisci lista vuota
            return []
            
    except Exception as e:
        st.error(f"❌ Errore nel caricamento del CSV di tracking: {e}")
        return []

def save_tracking_csv(tracking_data):
    """Salva il CSV di tracking su Google Drive"""
    try:
        service = get_drive_service()
        if not service:
            st.error("❌ Impossibile accedere a Google Drive")
            return False
        
        # ID della cartella principale
        main_folder_id = "1w9P2oiRfFgsOOj82V7xOruhjnl-APCCi"
        
        # Prepara il contenuto CSV
        import csv
        from io import StringIO
        
        fieldnames = ['apartment', 'video_type', 'youtube_link', 'drive_link', 'italian_transcript', 'english_transcript', 'date_created']
        
        csv_buffer = StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tracking_data)
        
        csv_content = csv_buffer.getvalue()
        
        # Cerca se il file esiste già
        query = f"'{main_folder_id}' in parents and name='apartments_tracking.csv' and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        if files:
            # Aggiorna il file esistente
            file_id = files[0]['id']
            media = MediaFileUpload(
                io.BytesIO(csv_content.encode('utf-8')),
                mimetype='text/csv',
                resumable=True
            )
            service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
        else:
            # Crea un nuovo file
            file_metadata = {
                'name': 'apartments_tracking.csv',
                'parents': [main_folder_id]
            }
            
            media = MediaFileUpload(
                io.BytesIO(csv_content.encode('utf-8')),
                mimetype='text/csv',
                resumable=True
            )
            
            service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
        
        return True
        
    except Exception as e:
        st.error(f"❌ Errore nel salvataggio del CSV di tracking: {e}")
        return False

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
    
    # Salva su Google Drive
    if save_tracking_csv(tracking_data):
        st.success(f"✅ Tracking aggiornato per {apartment} - {video_type}")
    else:
        st.error("❌ Errore nel salvataggio del tracking")

def verify_tracking_csv():
    """Verifica e ripara il CSV di tracking se necessario"""
    try:
        tracking_data = load_tracking_csv()
        
        # Verifica che tutti i record abbiano i campi necessari
        required_fields = ['apartment', 'video_type', 'youtube_link', 'drive_link', 'italian_transcript', 'english_transcript', 'date_created']
        
        for entry in tracking_data:
            for field in required_fields:
                if field not in entry:
                    entry[field] = ''
        
        # Salva il CSV riparato se necessario
        save_tracking_csv(tracking_data)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Errore nella verifica del CSV di tracking: {e}")
        return False

def get_processed_apartments():
    """Restituisce la lista degli appartamenti che hanno almeno un video elaborato"""
    # Prima verifica il CSV
    verify_tracking_csv()
    
    tracking_data = load_tracking_csv()
    processed_apartments = {}
    
    for entry in tracking_data:
        apartment = entry['apartment']
        if apartment not in processed_apartments:
            processed_apartments[apartment] = []
        processed_apartments[apartment].append(entry['video_type'])
    
    return processed_apartments 