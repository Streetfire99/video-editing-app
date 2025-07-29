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
    try:
        client_secrets = st.secrets.get("YOUTUBE_CLIENT_SECRETS")
        if client_secrets:
            # Se è una stringa JSON, convertila in dizionario
            if isinstance(client_secrets, str):
                import json
                client_secrets = json.loads(client_secrets)
            return client_secrets
        else:
            st.error("❌ Credenziali YouTube non configurate nei secrets")
            return None
    except Exception as e:
        st.error(f"❌ Errore nel caricamento delle credenziali: {e}")
        st.error(f"❌ Tipo di errore: {type(e)}")
        st.error(f"❌ Dettagli: {str(e)}")
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

def authenticate_account(account):
    """Autentica un account YouTube specifico"""
    st.info(f"🔐 Autenticazione per: {account}")
    
    client_secrets = get_client_secrets()
    if not client_secrets:
        return None
    
    try:
        # Assicurati che client_secrets sia un dizionario
        if isinstance(client_secrets, str):
            import json
            client_secrets = json.loads(client_secrets)
        
        # Crea un file temporaneo con le credenziali
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(client_secrets, f)
            client_secrets_file = f.name
        
        # Configura il flow OAuth2 per web application
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, 
            SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )
        
        # Genera l'URL di autorizzazione
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        st.markdown(f"""
        ### 🔐 Autenticazione per {account}
        
        1. **Clicca sul link qui sotto** per autorizzare l'accesso
        2. **Accedi con l'account**: {account}
        3. **Copia il codice di autorizzazione** che appare
        4. **Incolla il codice** nel campo qui sotto
        
        [🔗 Autorizza Accesso]({auth_url})
        """)
        
        # Campo per inserire il codice di autorizzazione
        auth_code = st.text_input(
            "📋 Codice di Autorizzazione",
            key=f"auth_code_{account}",
            help="Incolla qui il codice di autorizzazione che hai ricevuto"
        )
        
        if auth_code and st.button("✅ Conferma Autenticazione", key=f"confirm_{account}"):
            try:
                # Scambia il codice per i token
                flow.fetch_token(code=auth_code)
                credentials = flow.credentials
                
                # Salva il token in session state
                save_token_to_session_state(account, credentials)
                
                st.success(f"✅ Autenticazione completata per {account}!")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Errore nell'autenticazione: {e}")
                st.error("💡 Assicurati che il codice sia corretto e non sia scaduto")
        
        # Pulisci il file temporaneo
        try:
            os.unlink(client_secrets_file)
        except:
            pass
            
    except Exception as e:
        st.error(f"❌ Errore nella configurazione OAuth2: {e}")
        st.error("💡 Verifica che le credenziali nei secrets siano corrette")
        return None

def get_account_status(account):
    """Ottiene lo stato di un account"""
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

def test_account_upload(account):
    """Testa l'upload di un account"""
    token_data = get_token_from_session_state(account)
    
    if not token_data or is_token_expired_session_state(account):
        st.warning("⚠️ Account non autenticato o token scaduto")
        return False
    
    try:
        credentials = token_data['credentials']
        
        # Rinnova il token se necessario
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            save_token_to_session_state(account, credentials)
        
        # Testa la connessione
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Ottieni informazioni sul canale
        channels_response = youtube.channels().list(
            part='snippet',
            mine=True
        ).execute()
        
        if channels_response['items']:
            channel_name = channels_response['items'][0]['snippet']['title']
            st.success(f"✅ Connessione riuscita: {channel_name}")
            return True
        else:
            st.error("❌ Errore nel recupero delle informazioni del canale")
            return False
            
    except Exception as e:
        st.error(f"❌ Errore nel test: {e}")
        return False

def delete_account_token(account):
    """Elimina il token di un account"""
    key = f"youtube_token_{account.replace('@', '_at_').replace('.', '_')}"
    if key in st.session_state:
        del st.session_state[key]
        st.success(f"🗑️ Token eliminato per {account}")
        st.rerun()

# Interfaccia principale
st.header("📊 Stato Account")

# Tabella degli account
col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

with col1:
    st.markdown("**Account**")
with col2:
    st.markdown("**Stato**")
with col3:
    st.markdown("**Azioni**")
with col4:
    st.markdown("**Test**")

for account in YOUTUBE_ACCOUNTS:
    with col1:
        st.write(account)
    
    with col2:
        status = get_account_status(account)
        st.write(status)
    
    with col3:
        if "Non autenticato" in status or "scaduto" in status:
            if st.button("🔐 Autentica", key=f"auth_{account}"):
                st.session_state[f"show_auth_{account}"] = True
        else:
            if st.button("🗑️ Elimina", key=f"delete_{account}"):
                delete_account_token(account)
    
    with col4:
        if st.button("🧪 Test", key=f"test_{account}"):
            test_account_upload(account)

# Sezione di autenticazione
st.header("🔐 Autenticazione Account")

selected_account = st.selectbox(
    "Seleziona account da autenticare:",
    YOUTUBE_ACCOUNTS,
    help="Scegli l'account per cui vuoi configurare l'autenticazione"
)

# Mostra l'interfaccia di autenticazione per l'account selezionato
if st.session_state.get(f"show_auth_{selected_account}", False):
    authenticate_account(selected_account)
    
    if st.button("❌ Annulla", key=f"cancel_{selected_account}"):
        st.session_state[f"show_auth_{selected_account}"] = False
        st.rerun()

# Informazioni aggiuntive
st.header("ℹ️ Informazioni")

st.markdown("""
### 📋 Come funziona:

1. **Autenticazione Manuale**: Ogni account richiede un'autenticazione manuale
2. **Token Giornalieri**: I token si resettano automaticamente ogni 24 ore
3. **Rotazione Automatica**: Gli account vengono usati in ordine fino al limite
4. **Test Connessione**: Puoi testare ogni account per verificare la funzionalità

### 🔄 Reset Automatico:
- I token scadono dopo 24 ore
- Devi re-autenticare manualmente ogni account
- Il sistema usa automaticamente l'account successivo disponibile

### 📊 Monitoraggio:
- Controlla lo stato di ogni account
- Testa la connessione prima dell'uso
- Elimina token non più necessari

### ☁️ Compatibilità Streamlit Cloud:
- I token vengono salvati in memoria (session state)
- Non persistono tra i riavvii dell'app
- Devi re-autenticare dopo ogni riavvio
""")

# Statistiche
st.header("📈 Statistiche")

active_accounts = 0
expired_accounts = 0
unauthenticated_accounts = 0

for account in YOUTUBE_ACCOUNTS:
    status = get_account_status(account)
    if "Attivo" in status:
        active_accounts += 1
    elif "scaduto" in status:
        expired_accounts += 1
    else:
        unauthenticated_accounts += 1

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("✅ Attivi", active_accounts)
with col2:
    st.metric("⏰ Scaduti", expired_accounts)
with col3:
    st.metric("❌ Non autenticati", unauthenticated_accounts) 