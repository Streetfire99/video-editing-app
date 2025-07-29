import os
import pickle
import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Configurazione OAuth2 per YouTube
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.upload'
]

def get_youtube_credentials():
    """Ottiene le credenziali OAuth2 per YouTube"""
    creds = None
    
    # Il file token.pickle contiene i token di accesso e refresh
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # Se non ci sono credenziali valide, lascia che l'utente si autentichi
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Prova prima dalle variabili d'ambiente (per Streamlit Cloud)
            client_secrets_json = os.getenv('YOUTUBE_CLIENT_SECRETS')
            
            if client_secrets_json:
                # Usa le credenziali dalle variabili d'ambiente
                import json
                import tempfile
                
                client_secrets_dict = json.loads(client_secrets_json)
                
                # Crea un file temporaneo con le credenziali
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                    json.dump(client_secrets_dict, temp_file)
                    temp_file_path = temp_file.name
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        temp_file_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                finally:
                    # Pulisci il file temporaneo
                    os.unlink(temp_file_path)
            else:
                # Fallback al file locale (per sviluppo)
                client_secrets_file = None
                for file in os.listdir('.'):
                    if 'client_secret' in file and file.endswith('.json'):
                        client_secrets_file = file
                        break
                
                if not client_secrets_file:
                    st.error("❌ File client_secrets.json non trovato!")
                    st.info("📋 Per caricare su YouTube, devi configurare le credenziali OAuth2:")
                    st.markdown("""
                    **Per ambiente locale:**
                    1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
                    2. Crea un progetto o seleziona uno esistente
                    3. Abilita l'API YouTube Data v3
                    4. Crea credenziali OAuth2 (tipo: Applicazione desktop)
                    5. Scarica il file JSON delle credenziali
                    6. Rinominalo in `client_secrets.json` e mettilo nella cartella del progetto
                    
                    **Per Streamlit Cloud:**
                    1. Segui i passaggi sopra ma scegli "Web application" invece di "Desktop"
                    2. Aggiungi l'URL della tua app Streamlit agli URI autorizzati
                    3. Carica il contenuto del file JSON nelle "Secrets" di Streamlit Cloud
                    """)
                    return None
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets_file, SCOPES)
                creds = flow.run_local_server(port=0)
        
        # Salva le credenziali per la prossima esecuzione
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def upload_to_youtube(video_path, title, description, tags, privacy_status="unlisted"):
    """Carica il video su YouTube e restituisce il link"""
    try:
        # Ottieni le credenziali
        creds = get_youtube_credentials()
        if not creds:
            return {
                "success": False,
                "error": "Impossibile ottenere le credenziali YouTube"
            }
        
        # Crea il servizio YouTube
        youtube = build('youtube', 'v3', credentials=creds)
        
        # Prepara i metadati del video
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': [tag.strip() for tag in tags.split(',') if tag.strip()],
                'categoryId': '27'  # Education
            },
            'status': {
                'privacyStatus': privacy_status  # private, unlisted, public
            }
        }
        
        # Carica il video
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        
        # Esegui l'upload con progress bar
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    progress_bar.progress(progress)
                    status_text.text(f"Caricamento in corso... {progress}%")
            except HttpError as e:
                if e.resp.status == 401:
                    # Token scaduto, ricarica le credenziali
                    os.remove('token.pickle')
                    return upload_to_youtube(video_path, title, description, tags, privacy_status)
                else:
                    raise e
        
        progress_bar.progress(100)
        status_text.text("✅ Caricamento completato!")
        
        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        return {
            "success": True,
            "video_url": video_url,
            "video_id": video_id
        }
        
    except HttpError as e:
        error_details = e.error_details[0] if e.error_details else {}
        error_reason = error_details.get('reason', 'unknown')
        error_message = error_details.get('message', str(e))
        
        # Gestione errori specifici
        if e.resp.status == 403:
            if 'quota' in error_message.lower() or 'daily' in error_message.lower():
                return {
                    "success": False,
                    "error": f"Limite giornaliero raggiunto: {error_message}"
                }
            elif 'forbidden' in error_reason.lower():
                return {
                    "success": False,
                    "error": f"Accesso negato: {error_message}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Errore di autorizzazione: {error_message}"
                }
        elif e.resp.status == 401:
            return {
                "success": False,
                "error": f"Token di accesso scaduto: {error_message}"
            }
        elif e.resp.status == 400:
            return {
                "success": False,
                "error": f"Richiesta non valida: {error_message}"
            }
        else:
            return {
                "success": False,
                "error": f"Errore HTTP {e.resp.status}: {error_message}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Errore generico: {str(e)}"
        }

def check_youtube_setup():
    """Verifica se YouTube è configurato correttamente"""
    # Controlla se esiste il file client_secrets.json
    client_secrets_exists = any(
        'client_secret' in file and file.endswith('.json') 
        for file in os.listdir('.')
    )
    
    # Controlla se esiste il file token.pickle (credenziali salvate)
    token_exists = os.path.exists('token.pickle')
    
    return {
        "client_secrets_configured": client_secrets_exists,
        "authenticated": token_exists,
        "ready": client_secrets_exists
    } 