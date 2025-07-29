import os
import pickle
import tempfile
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

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
        import streamlit as st
        client_secrets = st.secrets.get("YOUTUBE_CLIENT_SECRETS")
        if client_secrets:
            # Se è una stringa JSON, convertila in dizionario
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
    """Ottiene il token da session state (per Streamlit Cloud)"""
    import streamlit as st
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    token_data = st.session_state.get(key)
    print(f"🔧 DEBUG: Getting token for {account}, key: {key}, found: {token_data is not None}")
    return token_data

def save_token_to_session_state(account, credentials):
    """Salva il token in session state (per Streamlit Cloud)"""
    import streamlit as st
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    token_data = {
        'credentials': credentials,
        'created_at': datetime.now().timestamp()
    }
    st.session_state[key] = token_data
    print(f"🔧 DEBUG: Saved token for {account}, key: {key}")
    print(f"🔧 DEBUG: Session state keys: {list(st.session_state.keys())}")

def is_token_expired_session_state(account):
    """Controlla se il token in session state è scaduto"""
    import streamlit as st
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    token_data = st.session_state.get(key)
    
    print(f"🔧 DEBUG: Checking token expiry for {account}")
    print(f"🔧 DEBUG: Token data exists: {token_data is not None}")
    
    if not token_data:
        print(f"❌ DEBUG: No token data for {account}")
        return True
    
    created_at = token_data.get('created_at', 0)
    now = datetime.now().timestamp()
    time_diff = now - created_at
    is_expired = time_diff > 24 * 3600
    
    print(f"🔧 DEBUG: Token age: {time_diff/3600:.1f}h, expired: {is_expired}")
    
    # Token scade dopo 24 ore
    return is_expired

def get_available_account():
    """Ottiene il primo account disponibile con token valido"""
    print("🔧 DEBUG: Starting get_available_account")
    
    for account in YOUTUBE_ACCOUNTS:
        print(f"🔧 DEBUG: Checking account: {account}")
        is_expired = is_token_expired_session_state(account)
        print(f"🔧 DEBUG: Token expired: {is_expired}")
        
        if not is_expired:
            print(f"✅ DEBUG: Found available account: {account}")
            return account
    
    print("❌ DEBUG: No available accounts found")
    return None

def get_youtube_service(account=None):
    """Ottiene il servizio YouTube per un account specifico o il primo disponibile"""
    print("🔧 DEBUG: Starting get_youtube_service")
    print(f"🔧 DEBUG: Account parameter: {account}")
    
    if account is None:
        account = get_available_account()
        print(f"🔧 DEBUG: Selected account: {account}")
    
    if account is None:
        print("❌ DEBUG: No available account found")
        raise Exception("❌ Nessun account YouTube disponibile. Configura l'autenticazione nella pagina 'YouTube Accounts'.")
    
    print(f"🔧 DEBUG: Getting token for account: {account}")
    token_data = get_token_from_session_state(account)
    print(f"🔧 DEBUG: Token data: {token_data is not None}")
    
    if not token_data:
        print("❌ DEBUG: No token data found")
        raise Exception(f"❌ Account {account} non autenticato")
    
    if is_token_expired_session_state(account):
        print("❌ DEBUG: Token is expired")
        raise Exception(f"❌ Token scaduto per {account}. Re-autentica nella pagina 'YouTube Accounts'.")
    
    try:
        print("🔧 DEBUG: Creating credentials from token")
        credentials = token_data['credentials']
        print(f"🔧 DEBUG: Credentials type: {type(credentials)}")
        
        # Rinnova il token se necessario
        if credentials.expired and credentials.refresh_token:
            print("🔧 DEBUG: Refreshing expired credentials")
            credentials.refresh(Request())
            save_token_to_session_state(account, credentials)
        
        print("🔧 DEBUG: Building YouTube service")
        youtube_service = build('youtube', 'v3', credentials=credentials)
        print("✅ DEBUG: YouTube service created successfully")
        
        return youtube_service, account
        
    except Exception as e:
        print(f"❌ DEBUG: Error creating YouTube service: {e}")
        raise e

def upload_video_with_rotation(video_path, title, privacy_status="unlisted", description="", tags=""):
    """Carica un video su YouTube usando la rotazione automatica degli account"""
    
    # Prova tutti gli account disponibili
    for account in YOUTUBE_ACCOUNTS:
        try:
            print(f"🔧 DEBUG: Tentativo upload con account {account}")
            
            youtube_service, used_account = get_youtube_service(account)
            
            # Prepara i metadati del video
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': [tag.strip() for tag in tags.split(',')] if tags else [],
                    'categoryId': '27'  # Education
                },
                'status': {
                    'privacyStatus': privacy_status
                }
            }
            
            # Carica il video
            media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
            
            # Esegui l'upload
            request = youtube_service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"🔧 DEBUG: Upload progress: {int(status.progress() * 100)}%")
            
            video_id = response['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            print(f"✅ Video caricato con successo usando account {used_account}")
            return {
                "success": True,
                "video_id": video_id,
                "video_url": video_url,
                "account_used": used_account
            }
            
        except HttpError as e:
            error_details = e.error_details[0] if e.error_details else {}
            reason = error_details.get('reason', 'unknown')
            
            if 'quotaExceeded' in reason or 'quota' in str(e).lower():
                print(f"⚠️ Quota esaurita per account {account}, prova il prossimo...")
                continue
            elif 'forbidden' in reason or 'unauthorized' in reason:
                print(f"⚠️ Problemi di autorizzazione per account {account}, prova il prossimo...")
                continue
            else:
                print(f"❌ Errore specifico per account {account}: {e}")
                continue
                
        except Exception as e:
            print(f"❌ Errore generico per account {account}: {e}")
            continue
    
    # Se arriviamo qui, nessun account ha funzionato
    raise Exception("❌ Tutti gli account YouTube hanno fallito. Controlla le credenziali e le quote.")

def get_account_status(account):
    """Ottiene lo stato di un account"""
    import streamlit as st
    
    token_data = get_token_from_session_state(account)
    
    if not token_data:
        return "❌ Non autenticato"
    
    if is_token_expired_session_state(account):
        return "⏰ Token scaduto"
    
    # Controlla la data di creazione
    created_at = token_data.get('created_at', 0)
    creation_date = datetime.fromtimestamp(created_at)
    hours_remaining = 24 - (datetime.now() - creation_date).total_seconds() / 3600
    
    return f"✅ Attivo ({hours_remaining:.1f}h rimanenti)"

def test_account(account):
    """Testa un account specifico"""
    try:
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

def get_accounts_summary():
    """Ottiene un riepilogo di tutti gli account"""
    summary = {
        "active": 0,
        "expired": 0,
        "unauthenticated": 0,
        "accounts": {}
    }
    
    for account in YOUTUBE_ACCOUNTS:
        status = get_account_status(account)
        summary["accounts"][account] = status
        
        if "Attivo" in status:
            summary["active"] += 1
        elif "scaduto" in status:
            summary["expired"] += 1
        else:
            summary["unauthenticated"] += 1
    
    return summary

def delete_account_token(account):
    """Elimina il token di un account"""
    import streamlit as st
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    if key in st.session_state:
        del st.session_state[key]
        return True
    return False 