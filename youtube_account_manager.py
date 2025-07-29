import os
import pickle
import tempfile
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import streamlit as st
import json

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

def get_token_from_session_state(account):
    """Ottiene il token da session state"""
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    return st.session_state.get(key)

def save_token_to_session_state(account, credentials):
    """Salva il token in session state"""
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    st.session_state[key] = {
        'credentials': credentials,
        'created_at': datetime.now().timestamp()
    }

def is_token_expired_session_state(account):
    """Controlla se il token è scaduto"""
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    token_data = st.session_state.get(key)
    
    if not token_data:
        return True
    
    created_at = token_data.get('created_at', 0)
    now = datetime.now().timestamp()
    return (now - created_at) > 24 * 3600

def is_account_authenticated(account):
    """Controlla se un account è autenticato e valido"""
    token_data = get_token_from_session_state(account)
    if not token_data:
        return False
    
    if is_token_expired_session_state(account):
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
        
        # Salva il token
        save_token_to_session_state(account, credentials)
        
        # Pulisci il file temporaneo
        os.unlink(client_secrets_file)
        
        return True
        
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
    
    token_data = get_token_from_session_state(account)
    
    if not token_data:
        raise Exception(f"❌ Account {account} non autenticato")
    
    if is_token_expired_session_state(account):
        raise Exception(f"❌ Token scaduto per {account}")
    
    try:
        credentials = token_data['credentials']
        
        # Rinnova il token se necessario
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            save_token_to_session_state(account, credentials)
        
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
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    if key in st.session_state:
        del st.session_state[key]
        return True
    return False 