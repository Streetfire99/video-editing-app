import os
import csv
import tempfile
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials
import streamlit as st
import io
import json

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Ottiene il servizio Google Drive"""
    try:
        # Prova prima da Streamlit secrets
        credentials_str = st.secrets.get('GOOGLE_SHEETS_CREDENTIALS')
        if credentials_str:
            # Se è una stringa JSON, convertila in dizionario
            if isinstance(credentials_str, str):
                credentials_dict = json.loads(credentials_str)
            else:
                credentials_dict = credentials_str
        else:
            # Fallback alle variabili d'ambiente
            credentials_str = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
            if not credentials_str:
                st.error("❌ GOOGLE_SHEETS_CREDENTIALS non trovata nei secrets o nelle variabili d'ambiente")
                return None
            
            credentials_dict = json.loads(credentials_str)
        
        # Crea le credenziali con gli scope
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
        
        # Crea il servizio Drive
        service = build('drive', 'v3', credentials=credentials)
        
        return service
        
    except Exception as e:
        st.error(f"❌ Errore nel caricamento delle credenziali Google Drive: {e}")
        return None

def make_file_public_with_editor_permissions(service, file_id):
    """Rende il file pubblico con ruolo Editor per chiunque"""
    try:
        # Crea un permesso pubblico con ruolo Editor
        permission = {
            'type': 'anyone',
            'role': 'writer',  # 'writer' = Editor in Google Drive
            'allowFileDiscovery': True
        }
        
        service.permissions().create(
            fileId=file_id,
            body=permission,
            fields='id'
        ).execute()
        
        return True
    except Exception as e:
        st.error(f"❌ Errore nel rendere pubblico il file: {e}")
        return False

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
        
        file_id = file.get('id')
        
        # Rendi il file pubblico con ruolo Editor
        if make_file_public_with_editor_permissions(service, file_id):
            print(f"✅ File {file_id} reso pubblico con ruolo Editor")
        else:
            print(f"⚠️ Impossibile rendere pubblico il file {file_id}")
        
        return file.get('webViewLink')
        
    except HttpError as error:
        st.error(f'Errore nel caricamento su Drive: {error}')
        return None

def upload_manual_to_drive(manual_content, filename, apartment_name, video_type):
    """Carica un manuale su Google Drive con permessi pubblici"""
    try:
        service = get_drive_service()
        
        # ID della cartella principale
        main_folder_id = "1w9P2oiRfFgsOOj82V7xOruhjnl-APCCi"
        
        # Crea cartella appartamento se non esiste
        apartment_folder_id = create_folder_if_not_exists(service, main_folder_id, apartment_name)
        if not apartment_folder_id:
            return None
        
        # Crea cartella tipologia video se non esiste
        type_folder_id = create_folder_if_not_exists(service, apartment_folder_id, video_type)
        if not type_folder_id:
            return None
        
        # Carica il manuale
        file_metadata = {
            'name': filename,
            'parents': [type_folder_id]
        }
        
        # Crea il file temporaneo
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(manual_content)
            temp_file_path = temp_file.name
        
        try:
            media = MediaFileUpload(temp_file_path, mimetype='text/plain', resumable=True)
            file = service.files().create(body=file_metadata, media_body=media, fields='id,webViewLink').execute()
            
            file_id = file.get('id')
            
            # Rendi il file pubblico con ruolo Editor
            if make_file_public_with_editor_permissions(service, file_id):
                print(f"✅ Manuale {file_id} reso pubblico con ruolo Editor")
            else:
                print(f"⚠️ Impossibile rendere pubblico il manuale {file_id}")
            
            return file.get('webViewLink')
            
        finally:
            # Pulisci il file temporaneo
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        
    except HttpError as error:
        st.error(f'Errore nel caricamento del manuale su Drive: {error}')
        return None

def load_tracking_csv():
    """Carica il CSV di tracking degli appartamenti elaborati da Google Drive"""
    try:
        service = get_drive_service()
        if not service:
            st.warning("⚠️ Impossibile accedere a Google Drive. Usando dati locali.")
            return []
        
        # ID della cartella principale
        main_folder_id = "1w9P2oiRfFgsOOj82V7xOruhjnl-APCCi"
        
        try:
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
                
                # Migrazione automatica: converte i vecchi nomi campi ai nuovi manual_link
                for entry in tracking_data:
                    # Migra i vecchi campi transcript ai nuovi manual_link
                    if 'italian_transcript' in entry and 'italian_manual_link' not in entry:
                        entry['italian_manual_link'] = entry.pop('italian_transcript', '')
                    if 'english_transcript' in entry and 'english_manual_link' not in entry:
                        entry['english_manual_link'] = entry.pop('english_transcript', '')
                    
                    # Migra i vecchi campi manual ai nuovi manual_link
                    if 'italian_manual' in entry and 'italian_manual_link' not in entry:
                        entry['italian_manual_link'] = entry.pop('italian_manual', '')
                    if 'english_manual' in entry and 'english_manual_link' not in entry:
                        entry['english_manual_link'] = entry.pop('english_manual', '')
                    
                    # Assicurati che tutti i campi necessari esistano
                    required_fields = ['apartment', 'video_type', 'youtube_link', 'drive_link', 'italian_manual_link', 'english_manual_link', 'date_created']
                    for field in required_fields:
                        if field not in entry:
                            entry[field] = ''
                
                return tracking_data
            else:
                # File non esiste, restituisci lista vuota
                st.info("📝 File di tracking non trovato. Verrà creato al primo upload.")
                return []
                
        except HttpError as e:
            if 'invalid_grant' in str(e):
                st.error("❌ Errore di accesso: Il service account non ha i permessi per accedere alla cartella Drive.")
                st.info("💡 Verifica che il service account abbia accesso alla cartella: 1w9P2oiRfFgsOOj82V7xOruhjnl-APCCi")
                return []
            else:
                st.error(f"❌ Errore HTTP nel caricamento del CSV: {e}")
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
        
        fieldnames = ['apartment', 'video_type', 'youtube_link', 'drive_link', 'italian_manual_link', 'english_manual_link', 'date_created']
        
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
            media = MediaIoBaseUpload(
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
            
            media = MediaIoBaseUpload(
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

def add_tracking_entry(apartment, video_type, youtube_link, drive_link, italian_manual_link=None, english_manual_link=None):
    """Aggiunge una nuova entry al tracking"""
    import datetime
    
    # Prima verifica e ripara il CSV se necessario
    verify_tracking_csv()
    
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
        'italian_manual_link': italian_manual_link or '',
        'english_manual_link': english_manual_link or '',
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
        
        # La migrazione viene fatta automaticamente in load_tracking_csv
        # Qui verifichiamo solo che tutti i campi necessari esistano
        for entry in tracking_data:
            required_fields = ['apartment', 'video_type', 'youtube_link', 'drive_link', 'italian_manual_link', 'english_manual_link', 'date_created']
            
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