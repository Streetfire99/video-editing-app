import streamlit as st
import os
import json
import pickle
import time
from datetime import datetime, timedelta
import tempfile
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configurazione della pagina
st.set_page_config(
    page_title="YouTube Accounts Manager",
    page_icon="📺",
    layout="wide"
)

# Titolo della pagina
st.title("📺 Gestione Account YouTube")
st.markdown("Gestisci i token di autenticazione per gli account YouTube")

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
    print("🔧 DEBUG: Starting get_client_secrets")
    try:
        client_secrets = st.secrets.get("YOUTUBE_CLIENT_SECRETS")
        print(f"🔧 DEBUG: Client secrets loaded: {client_secrets is not None}")
        
        if client_secrets:
            # Se è una stringa JSON, convertila in dizionario
            if isinstance(client_secrets, str):
                print("🔧 DEBUG: Converting string to JSON")
                import json
                client_secrets = json.loads(client_secrets)
                print("✅ DEBUG: JSON conversion successful")
            else:
                print("🔧 DEBUG: Using secrets directly")
            
            print(f"🔧 DEBUG: Client secrets type: {type(client_secrets)}")
            return client_secrets
        else:
            print("❌ DEBUG: No client secrets found")
            st.error("❌ Credenziali YouTube non configurate nei secrets")
            return None
    except Exception as e:
        print(f"❌ DEBUG: Error loading client secrets: {e}")
        st.error(f"❌ Errore nel caricamento delle credenziali: {e}")
        return None

def get_token_from_session_state(account):
    """Ottiene il token da session state (per Streamlit Cloud)"""
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    return st.session_state.get(key)

def save_token_to_session_state(account, credentials):
    """Salva il token in session state (per Streamlit Cloud)"""
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    st.session_state[key] = {
        'credentials': credentials,
        'created_at': datetime.now().timestamp()
    }

def is_token_expired_session_state(account):
    """Controlla se il token in session state è scaduto"""
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    token_data = st.session_state.get(key)
    
    if not token_data:
        return True
    
    created_at = token_data.get('created_at', 0)
    now = datetime.now().timestamp()
    
    # Token scade dopo 24 ore
    return (now - created_at) > 24 * 3600

def is_account_authenticated(account):
    """Controlla se un account è autenticato e valido"""
    token_data = get_token_from_session_state(account)
    if not token_data:
        return False
    
    if is_token_expired_session_state(account):
        return False
    
    return True

def authenticate_account_simple(account):
    """Autenticazione semplificata per un account"""
    print(f"🔧 DEBUG: Starting simple authentication for: {account}")
    
    client_secrets = get_client_secrets()
    if not client_secrets:
        return False
    
    try:
        # Crea un file temporaneo con le credenziali
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(client_secrets, f)
            client_secrets_file = f.name
        
        # Crea il flusso OAuth2 per web application
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, 
            SCOPES
        )
        
        # Genera l'URL di autorizzazione
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        # Mostra l'URL e chiedi il codice
        st.info(f"🔐 Autenticazione per: {account}")
        st.markdown(f"**🔗 URL di Autorizzazione:**")
        st.code(auth_url)
        
        auth_code = st.text_input(
            f"Inserisci il codice per {account}:",
            key=f"auth_code_{account}",
            help="1. Clicca sul link sopra\n2. Autorizza l'applicazione\n3. Copia il codice e incollalo qui"
        )
        
        if auth_code and st.button(f"✅ Autentica {account}", key=f"auth_btn_{account}"):
            try:
                # Scambia il codice per i token
                flow.fetch_token(code=auth_code)
                credentials = flow.credentials
                
                # Salva il token
                save_token_to_session_state(account, credentials)
                
                st.success(f"✅ {account} autenticato con successo!")
                st.rerun()
                return True
                
            except Exception as e:
                st.error(f"❌ Errore nell'autenticazione: {e}")
                return False
        
        # Pulisci il file temporaneo
        os.unlink(client_secrets_file)
        return False
        
    except Exception as e:
        st.error(f"❌ Errore nella configurazione: {e}")
        return False

def delete_account_token(account):
    """Elimina il token di un account"""
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    if key in st.session_state:
        del st.session_state[key]
        st.success(f"✅ Token eliminato per {account}")

# Interfaccia principale
st.header("📋 Stato Account YouTube")

# Mostra lo stato di tutti gli account
for account in YOUTUBE_ACCOUNTS:
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.write(f"**{account}**")
    
    with col2:
        if is_account_authenticated(account):
            st.success("✅ Autenticato")
        else:
            st.error("❌ Non autenticato")
    
    with col3:
        if is_account_authenticated(account):
            if st.button(f"🗑️ Elimina", key=f"delete_{account}"):
                delete_account_token(account)
                st.rerun()
        else:
            if st.button(f"🔐 Autentica", key=f"auth_{account}"):
                authenticate_account_simple(account)

# Statistiche
st.header("📊 Statistiche")
authenticated_count = sum(1 for account in YOUTUBE_ACCOUNTS if is_account_authenticated(account))
total_count = len(YOUTUBE_ACCOUNTS)

st.metric("Account Autenticati", f"{authenticated_count}/{total_count}")

if authenticated_count == 0:
    st.warning("⚠️ Nessun account autenticato. Autentica almeno un account per caricare video su YouTube.")
elif authenticated_count < total_count:
    st.info(f"ℹ️ {total_count - authenticated_count} account non ancora autenticati.")
else:
    st.success("🎉 Tutti gli account sono autenticati!")

# Debug info
with st.expander("🔧 Debug Info"):
    st.write("**Token salvati in session state:**")
    for account in YOUTUBE_ACCOUNTS:
        key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
        token_data = st.session_state.get(key)
        if token_data:
            created_at = datetime.fromtimestamp(token_data.get('created_at', 0))
            st.write(f"- {account}: ✅ (creato: {created_at.strftime('%H:%M:%S')})")
        else:
            st.write(f"- {account}: ❌") 