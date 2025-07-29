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
        google_credentials = st.secrets.get('GOOGLE_SHEETS_CREDENTIALS')
        print(f"🔧 DEBUG: Got credentials from secrets: {type(google_credentials)}")
        
        if google_credentials:
            # Se è una stringa JSON, convertila in dizionario
            if isinstance(google_credentials, str):
                print("🔧 DEBUG: Converting string to dict")
                import json
                try:
                    google_credentials = json.loads(google_credentials)
                    print("🔧 DEBUG: JSON parsing successful")
                    print(f"🔧 DEBUG: Parsed credentials keys: {list(google_credentials.keys())}")
                except json.JSONDecodeError as e:
                    print(f"❌ DEBUG: JSON parsing failed: {e}")
                    st.error(f"❌ Errore nel parsing JSON delle credenziali: {e}")
                    return None
            
            print("🔧 DEBUG: Creating credentials from service account info")
            # Crea le credenziali dal dizionario
            from google.oauth2.service_account import Credentials
            try:
                print(f"🔧 DEBUG: Credentials dict keys: {list(google_credentials.keys())}")
                print(f"🔧 DEBUG: private_key present: {'private_key' in google_credentials}")
                if 'private_key' in google_credentials:
                    print(f"🔧 DEBUG: private_key length: {len(google_credentials['private_key'])}")
                    print(f"🔧 DEBUG: private_key starts with: {google_credentials['private_key'][:50]}...")
                    # Sostituisci \\n con \n se necessario
                    if '\\\\n' in google_credentials['private_key']:
                        print("🔧 DEBUG: Replacing \\\\n with \\n")
                        google_credentials['private_key'] = google_credentials['private_key'].replace('\\\\n', '\\n')
                    elif '\\n' not in google_credentials['private_key']:
                        print("🔧 DEBUG: No \\n found in private_key, this might be the issue")
                
                credentials = Credentials.from_service_account_info(google_credentials)
                print("🔧 DEBUG: Credentials created successfully")
            except Exception as e:
                print(f"❌ DEBUG: Error creating credentials: {e}")
                print(f"❌ DEBUG: Error type: {type(e)}")
                st.error(f"❌ Errore nella creazione delle credenziali: {e}")
                return None
            
            # Crea il client
            print("🔧 DEBUG: Building drive service")
            service = build('drive', 'v3', credentials=credentials)
            print("🔧 DEBUG: Drive service built successfully")
            return service
        else:
            print("🔧 DEBUG: No credentials in secrets, trying environment")
            # Fallback alle variabili d'ambiente
            google_credentials = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
            if google_credentials:
                # Se è una stringa JSON, convertila in dizionario
                if isinstance(google_credentials, str):
                    import json
                    google_credentials = json.loads(google_credentials)
                
                # Crea le credenziali dal dizionario
                from google.oauth2.service_account import Credentials
                credentials = Credentials.from_service_account_info(google_credentials)
                
                # Crea il client
                service = build('drive', 'v3', credentials=credentials)
                return service
            else:
                st.error("❌ Credenziali Google Drive non configurate")
                return None
    except Exception as e:
        st.error(f"❌ Errore nel caricamento delle credenziali Google Drive: {e}")
        st.error(f"❌ Tipo di errore: {type(e)}")
        st.error(f"❌ Dettagli: {str(e)}")
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