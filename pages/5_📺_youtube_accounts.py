# Cache busting - v2
import streamlit as st
import os
import tempfile
from youtube_manager import check_youtube_setup, get_youtube_status, authenticate_youtube_account, upload_to_youtube

st.set_page_config(
    page_title="Test YouTube Upload",
    page_icon="📺",
    layout="wide"
)

st.title("🔐 YouTube Accounts Manager")
st.info("Gestisci l'autenticazione e lo stato di tutti gli account YouTube. Autentica gli account all'inizio della giornata per upload automatici.")

# Sezione 1: Stato YouTube
st.header("🔍 Stato YouTube")

youtube_status = check_youtube_setup()
st.info(youtube_status[1])

# Mostra lo stato dettagliato degli account
st.subheader("📊 Stato Account")
accounts_status = get_youtube_status()
if accounts_status:
    for account in accounts_status:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{account['account']}**")
        with col2:
            if "✅" in account['status']:
                st.success(account['status'])
            else:
                st.error(account['status'])

# Sezione 2: Gestione Account
st.header("🔐 Gestione Account")

from youtube_manager import YOUTUBE_ACCOUNTS

# Controlla stato di tutti gli account
account_status = []
for account in YOUTUBE_ACCOUNTS:
    from youtube_manager import is_account_authenticated
    is_authenticated = is_account_authenticated(account)
    account_status.append({
        'account': account,
        'authenticated': is_authenticated,
        'status': '✅ Autenticato' if is_authenticated else '❌ Non autenticato'
    })

# Mostra riepilogo
authenticated_count = sum(1 for acc in account_status if acc['authenticated'])
st.info(f"📊 **Stato Account:** {authenticated_count}/{len(YOUTUBE_ACCOUNTS)} autenticati")

# Tabella degli account
st.subheader("📋 Lista Account")
for i, acc in enumerate(account_status):
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        st.write(f"**{acc['account']}**")
    
    with col2:
        if acc['authenticated']:
            st.success(acc['status'])
        else:
            st.error(acc['status'])
    
    with col3:
        if not acc['authenticated']:
            if st.button(f"🔐 Autentica {i+1}", key=f"auth_{i}"):
                st.session_state.auth_account = acc['account']
                success, message = authenticate_youtube_account(acc['account'])
                if not success:
                    st.session_state.auth_url = message
                    st.rerun()

# Sezione autenticazione per account selezionato
if st.session_state.get('auth_account'):
    st.subheader(f"🔐 Autenticazione: {st.session_state.auth_account}")
    
    if st.session_state.get('auth_url'):
        st.info("🔐 **URL di autenticazione generato**")
        st.code(st.session_state.auth_url, language=None)
        
        auth_code = st.text_input("Codice di autorizzazione:", key="youtube_auth_code")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Completa Autenticazione", type="primary"):
                if auth_code:
                    success, message = authenticate_youtube_account(st.session_state.auth_account, auth_code)
                    if success:
                        st.success(message)
                        del st.session_state.auth_url
                        del st.session_state.auth_account
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("❌ Inserisci il codice di autorizzazione")
        
        with col2:
            if st.button("❌ Annulla"):
                del st.session_state.auth_url
                del st.session_state.auth_account
                st.rerun()

# Sezione 3: Gestione Token
st.header("🗑️ Gestione Token")

st.info("Elimina i token per reautenticare gli account")

for acc in account_status:
    if acc['authenticated']:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**{acc['account']}** - Token presente")
        with col2:
            if st.button(f"🗑️ Elimina {acc['account']}", key=f"delete_{acc['account']}"):
                from youtube_manager import delete_account_token
                if delete_account_token(acc['account']):
                    st.success("✅ Token eliminato")
                    st.rerun()
                else:
                    st.error("❌ Errore eliminazione")

# Sezione 4: Debug Info
st.header("🔧 Debug Info")

if st.button("📊 Mostra Info Debug", key="debug_button_unique"):
    st.subheader("📋 Configurazione YouTube")
    
    # Client secrets
    try:
        from youtube_manager import get_client_secrets
        client_secrets = get_client_secrets()
        if client_secrets:
            st.success("✅ Client secrets trovati")
            st.json(client_secrets)
        else:
            st.error("❌ Client secrets non trovati")
    except Exception as e:
        st.error(f"❌ Errore nel recupero client secrets: {e}")
    
    # Token files
    st.subheader("📁 File Token")
    token_dir = "youtube_tokens"
    if os.path.exists(token_dir):
        token_files = os.listdir(token_dir)
        if token_files:
            st.success(f"✅ Trovati {len(token_files)} file token:")
            for token_file in token_files:
                st.write(f"- {token_file}")
        else:
            st.warning("⚠️ Directory token vuota")
    else:
        st.warning("⚠️ Directory token non trovata")
    
    # Session state
    st.subheader("💾 Session State")
    youtube_session_keys = [k for k in st.session_state.keys() if 'youtube' in k.lower()]
    if youtube_session_keys:
        for key in youtube_session_keys:
            st.write(f"- {key}: {st.session_state[key]}")
    else:
        st.info("ℹ️ Nessuna chiave YouTube in session state")

st.markdown("---")
st.info("ℹ️ **Nota:** Usa questa pagina per gestire tutti gli account YouTube. Autentica gli account all'inizio della giornata per upload automatici nell'app principale.") 