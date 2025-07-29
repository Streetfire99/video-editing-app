import os
import pickle
import tempfile
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from googleapiclient.errors import HttpError
import streamlit as st
import json
import io

# Configurazione degli account
YOUTUBE_ACCOUNTS = [
    "xeniamilano.info@gmail.com",
    "videoxenia1@gmail.com", 
    "videoxenia2@gmail.com",
    "videoxenia3@gmail.com",
    "videoxenia4@gmail.com"
]

# Scopes necessari per YouTube
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# ID della cartella Google Drive per i token
TOKENS_FOLDER_ID = "1w9P2oiRfFgsOOj82V7xOruhjnl-APCCi"  # Stessa cartella del CSV

def get_drive_service():
    """Ottiene il servizio Google Drive"""
    try:
        from drive_manager import get_drive_service
        return get_drive_service()
    except Exception as e:
        print(f"❌ Errore nel caricamento del servizio Drive: {e}")
        return None

def get_client_secrets():
    """Ottiene le credenziali OAuth2 da Streamlit secrets"""
    try:
        client_secrets = st.secrets.get("YOUTUBE_CLIENT_SECRETS")
        if client_secrets:
            if isinstance(client_secrets, str):
                import json
                client_secrets = json.loads(client_secrets)
            return client_secrets
        else:
            return None
    except Exception as e:
        print(f"❌ Errore nel caricamento delle credenziali: {e}")
        return None

def get_token_from_drive(account):
    """Ottiene il token da Google Drive"""
    try:
        service = get_drive_service()
        if not service:
            return None
        
        filename = f"{account.replace('@', '_at_').replace('.', '_')}.pickle"
        
        # Cerca il file su Google Drive
        query = f"'{TOKENS_FOLDER_ID}' in parents and name='{filename}' and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        if files:
            file_id = files[0]['id']
            
            # Scarica il file
            request = service.files().get_media(fileId=file_id)
            file_content = io.BytesIO(request.execute())
            file_content.seek(0)
            
            # Carica il token
            credentials = pickle.load(file_content)
            print(f"✅ Token caricato per {account}")
            return credentials
        else:
            print(f"❌ Nessun token trovato per {account}")
            return None
            
    except Exception as e:
        print(f"❌ Errore nel caricamento del token per {account}: {e}")
        return None

def save_token_to_drive(account, credentials):
    """Salva il token su Google Drive"""
    try:
        service = get_drive_service()
        if not service:
            return False
        
        filename = f"{account.replace('@', '_at_').replace('.', '_')}.pickle"
        
        # Serializza le credenziali
        token_data = io.BytesIO()
        pickle.dump(credentials, token_data)
        token_data.seek(0)
        
        # Cerca se il file esiste già
        query = f"'{TOKENS_FOLDER_ID}' in parents and name='{filename}' and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        if files:
            # Aggiorna il file esistente
            file_id = files[0]['id']
            media = MediaIoBaseUpload(
                token_data,
                mimetype='application/octet-stream',
                resumable=True
            )
            service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
        else:
            # Crea un nuovo file
            file_metadata = {
                'name': filename,
                'parents': [TOKENS_FOLDER_ID]
            }
            media = MediaIoBaseUpload(
                token_data,
                mimetype='application/octet-stream',
                resumable=True
            )
            service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
        
        print(f"✅ Token salvato per {account}")
        return True
        
    except Exception as e:
        print(f"❌ Errore nel salvataggio del token per {account}: {e}")
        return False

def is_token_expired(credentials):
    """Controlla se il token è scaduto"""
    if not credentials:
        return True
    
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            return False
        except:
            return True
    
    return credentials.expired

def is_account_authenticated(account):
    """Controlla se un account è autenticato e valido"""
    credentials = get_token_from_drive(account)
    if not credentials:
        return False
    
    if is_token_expired(credentials):
        return False
    
    return True

def get_next_account_to_authenticate():
    """Trova il prossimo account da autenticare"""
    for account in YOUTUBE_ACCOUNTS:
        if not is_account_authenticated(account):
            return account
    return None

def create_auth_url(account):
    """Crea l'URL di autenticazione per un account"""
    try:
        client_secrets = get_client_secrets()
        if not client_secrets:
            return None
        
        # Crea un file temporaneo con le credenziali
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(client_secrets, f)
            client_secrets_file = f.name
        
        # Crea il flusso OAuth2
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, 
            SCOPES,
            redirect_uri="https://video-editing-app-streetfire99.streamlit.app"
        )
        
        # Genera l'URL di autorizzazione
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        # Pulisci il file temporaneo
        os.unlink(client_secrets_file)
        
        return auth_url
        
    except Exception as e:
        print(f"❌ Errore nella creazione dell'URL di autenticazione: {e}")
        return None

def authenticate_with_code(account, auth_code):
    """Autentica un account con il codice di autorizzazione"""
    try:
        client_secrets = get_client_secrets()
        if not client_secrets:
            return False
        
        # Crea un file temporaneo con le credenziali
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(client_secrets, f)
            client_secrets_file = f.name
        
        # Crea il flusso OAuth2
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, 
            SCOPES,
            redirect_uri="https://video-editing-app-streetfire99.streamlit.app"
        )
        
        # Scambia il codice per i token
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials
        
        # Salva il token su Google Drive
        if save_token_to_drive(account, credentials):
            return True
        else:
            return False
        
    except Exception as e:
        print(f"❌ Errore nell'autenticazione: {e}")
        return False

def get_youtube_service(account=None):
    """Ottiene il servizio YouTube per un account specifico o il primo disponibile"""
    if account is None:
        # Trova il primo account autenticato
        for acc in YOUTUBE_ACCOUNTS:
            if is_account_authenticated(acc):
                account = acc
                break
    
    if account is None:
        raise Exception("❌ Nessun account YouTube disponibile")
    
    credentials = get_token_from_drive(account)
    
    if not credentials:
        raise Exception(f"❌ Account {account} non autenticato")
    
    if is_token_expired(credentials):
        raise Exception(f"❌ Token scaduto per {account}")
    
    try:
        # Rinnova il token se necessario
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            save_token_to_drive(account, credentials)
        
        youtube_service = build('youtube', 'v3', credentials=credentials)
        return youtube_service, account
        
    except Exception as e:
        raise Exception(f"❌ Errore nell'accesso all'account {account}: {e}")

def upload_video_with_rotation(video_path, title, privacy_status="unlisted", description="", tags=""):
    """Carica un video su YouTube usando la rotazione automatica degli account"""
    max_attempts = 5  # Numero massimo di tentativi per account
    
    for account in YOUTUBE_ACCOUNTS:
        if not is_account_authenticated(account):
            continue
            
        print(f"🔧 Tentativo con account: {account}")
        
        for attempt in range(max_attempts):
            try:
                youtube_service, used_account = get_youtube_service(account)
                
                # Prepara il video per l'upload
                media = MediaFileUpload(video_path, resumable=True)
                
                # Crea la richiesta di upload
                request = youtube_service.videos().insert(
                    part='snippet,status',
                    body={
                        'snippet': {
                            'title': title,
                            'description': description,
                            'tags': tags.split(',') if tags else []
                        },
                        'status': {
                            'privacyStatus': privacy_status
                        }
                    },
                    media_body=media
                )
                
                # Esegui l'upload
                response = request.execute()
                video_id = response['id']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                return {
                    "success": True,
                    "video_url": video_url,
                    "account_used": used_account,
                    "video_id": video_id
                }
                
            except HttpError as e:
                error_details = e.error_details[0] if e.error_details else {}
                reason = error_details.get('reason', 'unknown')
                
                if reason in ['quotaExceeded', 'dailyLimitExceeded']:
                    print(f"❌ Quota esaurita per {account}, prova prossimo account")
                    break  # Passa al prossimo account
                else:
                    print(f"❌ Tentativo {attempt + 1} fallito per {account}: {e}")
                    if attempt == max_attempts - 1:
                        continue  # Passa al prossimo account
                    else:
                        continue  # Riprova con lo stesso account
        
        print(f"❌ Account {account} esaurito, prova prossimo")
    
    # Se arriviamo qui, tutti gli account hanno fallito
    raise Exception("❌ Tutti gli account YouTube hanno fallito. Controlla le credenziali e le quote.")

def show_authentication_banner(account):
    """Mostra un banner per autenticare un account"""
    auth_url = create_auth_url(account)
    
    if auth_url:
        st.error(f"❌ **Account YouTube richiesto**")
        st.markdown(f"""
        Per caricare video su YouTube, devi autenticare l'account: **{account}**
        
        [🔗 **Clicca qui per autenticare**]({auth_url})
        
        Dopo l'autenticazione, torna qui e inserisci il codice di autorizzazione.
        """)
        
        # Campo per inserire il codice
        auth_code = st.text_input(
            f"Inserisci il codice di autorizzazione per {account}:",
            key=f"auth_code_{account}",
            help="Copia il codice che ricevi dopo l'autenticazione"
        )
        
        if auth_code and st.button(f"✅ Conferma Autenticazione", key=f"confirm_{account}"):
            if authenticate_with_code(account, auth_code):
                st.success(f"✅ {account} autenticato con successo!")
                st.rerun()
            else:
                st.error("❌ Errore nell'autenticazione. Riprova.")
    else:
        st.error("❌ Errore nella configurazione OAuth2")

def get_accounts_summary():
    """Ottiene un riassunto di tutti gli account"""
    summary = []
    for account in YOUTUBE_ACCOUNTS:
        status = "✅ Autenticato" if is_account_authenticated(account) else "❌ Non autenticato"
        summary.append({
            'account': account,
            'status': status
        })
    return summary

def test_account(account):
    """Testa un account YouTube specifico"""
    try:
        if not is_account_authenticated(account):
            return False, f"Account {account} non autenticato"
        
        youtube_service, _ = get_youtube_service(account)
        
        # Ottieni informazioni sul canale
        channels_response = youtube_service.channels().list(
            part='snippet',
            mine=True
        ).execute()
        
        if channels_response['items']:
            channel_name = channels_response['items'][0]['snippet']['title']
            return True, f"✅ Connessione riuscita: {channel_name}"
        else:
            return False, "❌ Errore nel recupero delle informazioni del canale"
            
    except Exception as e:
        return False, f"❌ Errore nel test: {e}"

def delete_account_token(account):
    """Elimina il token di un account"""
    try:
        service = get_drive_service()
        if not service:
            return False
        
        filename = f"{account.replace('@', '_at_').replace('.', '_')}.pickle"
        
        # Cerca il file su Google Drive
        query = f"'{TOKENS_FOLDER_ID}' in parents and name='{filename}' and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        if files:
            file_id = files[0]['id']
            service.files().delete(fileId=file_id).execute()
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Errore nell'eliminazione del token per {account}: {e}")
        return False 