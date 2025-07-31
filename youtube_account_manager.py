import os
import pickle
import tempfile
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from googleapiclient.errors import HttpError
import streamlit as st
import json
import io
import urllib.parse

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

# Streamlit app URL per OAuth2
REDIRECT_URI = "https://video-editing-app-streetfire99.streamlit.app"

def get_drive_service():
    """Ottiene il servizio Google Drive"""
    try:
        from drive_manager import get_drive_service
        return get_drive_service()
    except Exception as e:
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
        return None

def generate_pkce():
    """Genera PKCE code verifier e challenge"""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

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
            return credentials
        else:
            return None
            
    except Exception as e:
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
        
        return True
        
    except Exception as e:
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
    """Controlla se un account è autenticato"""
    # Cache per evitare controlli ripetuti
    cache_key = f"auth_cache_{account}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    try:
        credentials = get_token_from_drive(account)
        if credentials:
            if is_token_expired(credentials):
                result = False
            else:
                result = True
        else:
            result = False
        
        # Cache il risultato
        st.session_state[cache_key] = result
        return result
    except Exception as e:
        st.session_state[cache_key] = False
        return False

def get_next_account_to_authenticate():
    """Trova il prossimo account da autenticare"""
    for account in YOUTUBE_ACCOUNTS:
        if not is_account_authenticated(account):
            return account
    return None

def create_modern_auth_url(account):
    """Crea l'URL di autenticazione moderno con PKCE"""
    try:
        client_secrets = get_client_secrets()
        if not client_secrets:
            return None
        
        # Genera PKCE
        code_verifier, code_challenge = generate_pkce()
        
        # Salva code_verifier per dopo
        st.session_state[f"code_verifier_{account}"] = code_verifier
        
        # Crea un file temporaneo con le credenziali
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(client_secrets, f)
            client_secrets_file = f.name
        
        # Crea il flusso OAuth2 moderno
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, 
            SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        # Genera l'URL di autorizzazione con PKCE
        auth_url, _ = flow.authorization_url(
            prompt='consent',
            access_type='offline',
            include_granted_scopes='true',
            code_challenge=code_challenge,
            code_challenge_method='S256'
        )
        
        # Pulisci il file temporaneo
        os.unlink(client_secrets_file)
        
        return auth_url
        
    except Exception as e:
        return None

def authenticate_with_code_modern(account, auth_code):
    """Autentica un account con il codice di autorizzazione moderno"""
    try:
        client_secrets = get_client_secrets()
        if not client_secrets:
            return False
        
        # Recupera code_verifier
        code_verifier = st.session_state.get(f"code_verifier_{account}")
        if not code_verifier:
            return False
        
        # Crea un file temporaneo con le credenziali
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(client_secrets, f)
            client_secrets_file = f.name
        
        # Crea il flusso OAuth2 moderno
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, 
            SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        # Scambia il codice per i token con PKCE
        flow.fetch_token(
            code=auth_code,
            code_verifier=code_verifier
        )
        credentials = flow.credentials
        
        # Salva il token su Google Drive
        if save_token_to_drive(account, credentials):
            # Pulisci code_verifier
            if f"code_verifier_{account}" in st.session_state:
                del st.session_state[f"code_verifier_{account}"]
            return True
        else:
            return False
        
    except Exception as e:
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
    print("🔧 DEBUG: Starting upload_video_with_rotation")
    print(f"🔧 DEBUG: Video path: {video_path}")
    print(f"🔧 DEBUG: Title: {title}")
    print(f"🔧 DEBUG: Privacy status: {privacy_status}")
    
    max_attempts = 5  # Numero massimo di tentativi per account
    
    for account in YOUTUBE_ACCOUNTS:
        if not is_account_authenticated(account):
            print(f"❌ DEBUG: Account {account} not authenticated, skipping")
            continue
            
        print(f"🔧 DEBUG: Trying account: {account}")
        
        for attempt in range(max_attempts):
            try:
                print(f"🔧 DEBUG: Attempt {attempt + 1} for account {account}")
                youtube_service, used_account = get_youtube_service(account)
                print(f"🔧 DEBUG: Got YouTube service for {used_account}")
                
                # Prepara il video per l'upload
                print("🔧 DEBUG: Preparing video for upload")
                media = MediaFileUpload(video_path, resumable=True)
                print("🔧 DEBUG: MediaFileUpload created")
                
                # Crea la richiesta di upload
                print("🔧 DEBUG: Creating upload request")
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
                print("🔧 DEBUG: Upload request created")
                
                # Esegui l'upload
                print("🔧 DEBUG: Starting upload execution")
                response = request.execute()
                print("🔧 DEBUG: Upload executed successfully")
                video_id = response['id']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                print(f"🔧 DEBUG: Video ID: {video_id}")
                print(f"🔧 DEBUG: Video URL: {video_url}")
                
                return {
                    "success": True,
                    "video_url": video_url,
                    "account_used": used_account,
                    "video_id": video_id
                }
                
            except HttpError as e:
                error_details = e.error_details[0] if e.error_details else {}
                reason = error_details.get('reason', 'unknown')
                print(f"❌ DEBUG: HttpError for {account}, attempt {attempt + 1}: {e}")
                print(f"❌ DEBUG: Error reason: {reason}")
                
                if reason in ['quotaExceeded', 'dailyLimitExceeded']:
                    print(f"❌ DEBUG: Quota exceeded for {account}, trying next account")
                    break  # Passa al prossimo account
                else:
                    print(f"❌ DEBUG: Other error for {account}, attempt {attempt + 1}")
                    if attempt == max_attempts - 1:
                        print(f"❌ DEBUG: All attempts failed for {account}, trying next account")
                        continue  # Passa al prossimo account
                    else:
                        print(f"🔧 DEBUG: Retrying {account}")
                        continue  # Riprova con lo stesso account
            except Exception as e:
                print(f"❌ DEBUG: General exception for {account}, attempt {attempt + 1}: {e}")
                if attempt == max_attempts - 1:
                    continue  # Passa al prossimo account
                else:
                    continue  # Riprova con lo stesso account
        
        print(f"❌ DEBUG: Account {account} exhausted, trying next")
    
    # Se arriviamo qui, tutti gli account hanno fallito
    print("❌ DEBUG: All accounts failed")
    raise Exception("❌ Tutti gli account YouTube hanno fallito. Controlla le credenziali e le quote.")

def show_modern_authentication_banner(account):
    """Mostra un banner moderno per autenticare un account"""
    auth_url = create_modern_auth_url(account)
    
    if auth_url:
        st.error(f"❌ **Autenticazione YouTube richiesta**")
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
        
        if auth_code:
            st.info("💡 Dopo aver inserito il codice, clicca '🚀 Carica su YouTube' per confermare l'autenticazione")
            
            # Salva il codice nella session state per usarlo dopo
            st.session_state[f"pending_auth_code_{account}"] = auth_code
            st.session_state[f"pending_auth_account_{account}"] = account
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