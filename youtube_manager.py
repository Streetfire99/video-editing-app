import os
import pickle
import tempfile
import time
import json
import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Configurazione centralizzata
YOUTUBE_ACCOUNTS = [
    "xeniamilano.info@gmail.com",
    "videoxenia1@gmail.com", 
    "videoxenia2@gmail.com",
    "videoxenia3@gmail.com",
    "videoxenia4@gmail.com"
]

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
TOKEN_DIR = "youtube_tokens"

# Assicurati che la directory dei token esista
os.makedirs(TOKEN_DIR, exist_ok=True)

def get_client_secrets():
    """Ottiene le credenziali OAuth2 da Streamlit secrets o file locale"""
    try:
        print("🔧 DEBUG: get_client_secrets - Starting")
        
        # Prova prima da Streamlit secrets
        if st.secrets.get("YOUTUBE_CLIENT_SECRETS"):
            print("✅ DEBUG: Found YOUTUBE_CLIENT_SECRETS in st.secrets")
            client_secrets = st.secrets.get("YOUTUBE_CLIENT_SECRETS")
            if isinstance(client_secrets, str):
                print("🔧 DEBUG: Client secrets is string, parsing JSON")
                return json.loads(client_secrets)
            print("🔧 DEBUG: Client secrets is already dict")
            return client_secrets
        else:
            print("❌ DEBUG: YOUTUBE_CLIENT_SECRETS not found in st.secrets")
            # Fallback su file locale
            if os.path.exists("client_secrets.json"):
                print("✅ DEBUG: Found client_secrets.json locally")
                with open("client_secrets.json", "r") as f:
                    return json.load(f)
            else:
                print("❌ DEBUG: No client_secrets.json found locally")
                return None
    except Exception as e:
        print(f"❌ DEBUG: Error in get_client_secrets: {e}")
        return None

def get_token_path(account):
    """Ottiene il percorso del file token per un account"""
    safe_account = account.replace('@', '_at_').replace('.', '_')
    return os.path.join(TOKEN_DIR, f"{safe_account}.pickle")

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
    try:
        print(f"🔧 DEBUG: is_account_authenticated - Checking {account}")
        token_path = get_token_path(account)
        print(f"🔧 DEBUG: Token path: {token_path}")
        
        if not os.path.exists(token_path):
            print(f"❌ DEBUG: Token file not found for {account}")
            return False
        
        print(f"✅ DEBUG: Token file found for {account}")
        with open(token_path, 'rb') as token:
            credentials = pickle.load(token)
        
        is_expired = is_token_expired(credentials)
        print(f"🔧 DEBUG: Token expired: {is_expired}")
        
        return not is_expired
    except Exception as e:
        print(f"❌ DEBUG: Error in is_account_authenticated for {account}: {e}")
        return False

def authenticate_account(account):
    """Autentica un account YouTube"""
    try:
        print(f"🔧 DEBUG: authenticate_account - Starting authentication for {account}")
        client_secrets = get_client_secrets()
        if not client_secrets:
            raise Exception("Client secrets non trovati")
        
        # Crea file temporaneo per le credenziali
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(client_secrets, f)
            client_secrets_file = f.name
        
        try:
            # Crea il flusso OAuth2
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, 
                SCOPES
            )
            
            # In Streamlit, creiamo un URL di autenticazione
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            print(f"🔧 DEBUG: Generated auth URL for {account}")
            print(f"🔧 DEBUG: Auth URL: {auth_url}")
            
            # Per ora, restituiamo False perché l'utente deve completare l'autenticazione manualmente
            # In futuro, possiamo implementare un sistema per gestire il callback
            print(f"⚠️ DEBUG: Manual authentication required - user must visit URL and provide code")
            
            return False
            
        finally:
            # Pulisci il file temporaneo
            if os.path.exists(client_secrets_file):
                os.unlink(client_secrets_file)
                
    except Exception as e:
        print(f"❌ DEBUG: Error in authenticate_account for {account}: {e}")
        return False

def get_youtube_service(account):
    """Ottiene il servizio YouTube per un account"""
    try:
        token_path = get_token_path(account)
        if not os.path.exists(token_path):
            raise Exception(f"Token non trovato per {account}")
        
        with open(token_path, 'rb') as token:
            credentials = pickle.load(token)
        
        # Rinnova il token se necessario
        if is_token_expired(credentials):
            credentials.refresh(Request())
            with open(token_path, 'wb') as token:
                pickle.dump(credentials, token)
        
        youtube_service = build('youtube', 'v3', credentials=credentials)
        return youtube_service
        
    except Exception as e:
        print(f"❌ Errore nell'accesso all'account {account}: {e}")
        return None

def get_next_available_account():
    """Trova il prossimo account disponibile"""
    for account in YOUTUBE_ACCOUNTS:
        if is_account_authenticated(account):
            return account
    return None

def handle_upload_error(error, account):
    """Gestisce gli errori di upload"""
    error_msg = str(error).lower()
    
    if isinstance(error, HttpError):
        error_details = error.error_details[0] if error.error_details else {}
        reason = error_details.get('reason', 'unknown')
        
        if reason in ['quotaExceeded', 'dailyLimitExceeded']:
            print(f"❌ Quota esaurita per {account}")
            return 'quota_exceeded'
        elif reason in ['authentication', 'unauthorized']:
            print(f"❌ Errore di autenticazione per {account}")
            # Rimuovi il token problematico
            token_path = get_token_path(account)
            if os.path.exists(token_path):
                os.remove(token_path)
            return 'authentication_error'
    
    print(f"❌ Errore generico per {account}: {error}")
    return 'general_error'

def upload_single_video(account, video_path, title, description="", tags="", privacy_status="unlisted"):
    """Carica un video su YouTube usando un account specifico"""
    try:
        print(f"🔧 Tentativo upload con account: {account}")
        
        youtube_service = get_youtube_service(account)
        if not youtube_service:
            return {'success': False, 'error': f'Impossibile ottenere servizio per {account}'}
        
        # Prepara il video per l'upload
        media = MediaFileUpload(video_path, resumable=True)
        
        # Crea la richiesta di upload
        request = youtube_service.videos().insert(
            part='snippet,status',
            body={
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': [tag.strip() for tag in tags.split(',')] if tags else []
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
        
        print(f"✅ Upload riuscito: {video_url}")
        return {
            'success': True,
            'video_url': video_url,
            'account_used': account,
            'video_id': video_id
        }
        
    except Exception as e:
        error_type = handle_upload_error(e, account)
        return {
            'success': False,
            'error': str(e),
            'error_type': error_type,
            'account': account
        }

def upload_video_to_youtube(video_path, title, description="", tags="", privacy_status="unlisted", max_retries=3):
    """Carica un video su YouTube con rotazione automatica degli account"""
    print(f"🚀 Inizio upload YouTube: {title}")
    
    # Trova account disponibili
    available_accounts = [acc for acc in YOUTUBE_ACCOUNTS if is_account_authenticated(acc)]
    
    if not available_accounts:
        print("❌ Nessun account YouTube autenticato")
        print("🔧 DEBUG: No OAuth2 accounts available for upload")
        return None
    
    print(f"🔧 Account disponibili: {len(available_accounts)}")
    
    # Prova ogni account
    for account in available_accounts:
        print(f"🔧 Tentativo con account: {account}")
        
        for attempt in range(max_retries):
            print(f"🔧 Tentativo {attempt + 1}/{max_retries}")
            
            result = upload_single_video(
                account=account,
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                privacy_status=privacy_status
            )
            
            if result['success']:
                print(f"✅ Upload completato con {account}")
                return result['video_url']
            
            # Gestisci errori specifici
            error_type = result.get('error_type', 'general_error')
            
            if error_type == 'quota_exceeded':
                print(f"❌ Quota esaurita per {account}, passo al prossimo")
                break  # Passa al prossimo account
            
            elif error_type == 'authentication_error':
                print(f"❌ Errore autenticazione per {account}, passo al prossimo")
                break  # Passa al prossimo account
            
            else:
                # Errore generico, riprova
                if attempt < max_retries - 1:
                    print(f"⏳ Attendo 5 secondi prima del prossimo tentativo...")
                    time.sleep(5)
                else:
                    print(f"❌ Tutti i tentativi falliti per {account}")
        
        print(f"❌ Account {account} esaurito, passo al prossimo")
    
    print("❌ Tutti gli account hanno fallito")
    return None

def check_youtube_setup():
    """Controlla se YouTube è configurato correttamente"""
    try:
        print("🔧 DEBUG: check_youtube_setup - Starting check")
        
        # Controlla se i client secrets sono disponibili
        client_secrets = get_client_secrets()
        if not client_secrets:
            print("❌ DEBUG: No client secrets found")
            return False, "❌ Client secrets non trovati"
        
        print("✅ DEBUG: Client secrets found")
        
        # Controlla se ci sono account autenticati
        authenticated_accounts = []
        for acc in YOUTUBE_ACCOUNTS:
            is_auth = is_account_authenticated(acc)
            print(f"🔧 DEBUG: Account {acc}: {'✅ Autenticato' if is_auth else '❌ Non autenticato'}")
            if is_auth:
                authenticated_accounts.append(acc)
        
        if authenticated_accounts:
            print(f"✅ DEBUG: Found {len(authenticated_accounts)} authenticated accounts")
            return True, f"✅ YouTube configurato con {len(authenticated_accounts)} account autenticati"
        else:
            print("❌ DEBUG: No authenticated accounts found")
            return False, "❌ Nessun account YouTube autenticato"
                
    except Exception as e:
        print(f"❌ DEBUG: Exception in check_youtube_setup: {e}")
        return False, f"❌ Errore nella configurazione YouTube: {e}"

def get_youtube_status():
    """Ottiene lo stato di tutti gli account YouTube"""
    try:
        summary = []
        for account in YOUTUBE_ACCOUNTS:
            status = "✅ Autenticato" if is_account_authenticated(account) else "❌ Non autenticato"
            summary.append({
                'account': account,
                'status': status
            })
        return summary
    except Exception as e:
        print(f"❌ Errore nel recupero dello stato YouTube: {e}")
        return None

def authenticate_youtube_account(account, auth_code=None):
    """Autentica un account YouTube specifico"""
    try:
        print(f"🔧 DEBUG: authenticate_youtube_account - Starting for {account}")
        
        client_secrets = get_client_secrets()
        if not client_secrets:
            return False, "❌ Client secrets non trovati"
        
        # Crea file temporaneo per le credenziali
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(client_secrets, f)
            client_secrets_file = f.name
        
        try:
            # Crea il flusso OAuth2
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, 
                SCOPES
            )
            
            if auth_code:
                # Se abbiamo il codice di autorizzazione, completiamo l'autenticazione
                print(f"🔧 DEBUG: Completing authentication with auth code")
                flow.fetch_token(code=auth_code)
                credentials = flow.credentials
                
                # Salva il token
                token_path = get_token_path(account)
                with open(token_path, 'wb') as token:
                    pickle.dump(credentials, token)
                
                print(f"✅ DEBUG: Account {account} authenticated successfully")
                return True, f"✅ Account {account} autenticato con successo"
            else:
                # Genera l'URL di autenticazione
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                print(f"🔧 DEBUG: Generated auth URL: {auth_url}")
                
                return False, f"🔐 Per autenticare {account}, visita questo URL:\n\n{auth_url}\n\nDopo l'autenticazione, copia il codice e inseriscilo qui."
            
        finally:
            # Pulisci il file temporaneo
            if os.path.exists(client_secrets_file):
                os.unlink(client_secrets_file)
                
    except Exception as e:
        print(f"❌ DEBUG: Error in authenticate_youtube_account: {e}")
        return False, f"❌ Errore nell'autenticazione: {e}"

def test_account(account):
    """Testa un account YouTube specifico"""
    try:
        if not is_account_authenticated(account):
            return False, f"Account {account} non autenticato"
        
        youtube_service = get_youtube_service(account)
        if not youtube_service:
            return False, f"Impossibile ottenere servizio per {account}"
        
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
        token_path = get_token_path(account)
        if os.path.exists(token_path):
            os.remove(token_path)
            print(f"🗑️ Token eliminato per {account}")
            return True
        return False
    except Exception as e:
        print(f"❌ Errore nell'eliminazione del token per {account}: {e}")
        return False

# Funzioni di utilità per compatibilità
def upload_to_youtube(video_path, title, privacy_status="unlisted", description="", tags=""):
    """Wrapper per compatibilità con app.py"""
    return upload_video_to_youtube(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status
    ) 