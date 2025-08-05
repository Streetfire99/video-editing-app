import streamlit as st
import os
import tempfile
from youtube_manager import check_youtube_setup, get_youtube_status, authenticate_youtube_account, upload_to_youtube

st.set_page_config(
    page_title="Test YouTube Upload",
    page_icon="📺",
    layout="wide"
)

st.title("📺 Test YouTube Upload")
st.info("Questa è una pagina di test per verificare l'upload YouTube. Verrà eliminata dopo i test.")

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

# Sezione 2: Autenticazione
st.header("🔐 Autenticazione")

from youtube_manager import get_next_available_account
next_account = get_next_available_account()

if next_account:
    st.warning(f"🔐 **Account da autenticare:** {next_account}")
    
    # Inizializza session state per l'autenticazione
    if 'youtube_auth_account' not in st.session_state:
        st.session_state.youtube_auth_account = None
    if 'youtube_auth_url' not in st.session_state:
        st.session_state.youtube_auth_url = None
    
    if st.button(f"🔐 Genera URL Autenticazione {next_account}"):
        success, message = authenticate_youtube_account(next_account)
        if not success:
            # Mostra l'URL di autenticazione
            st.session_state.youtube_auth_account = next_account
            st.session_state.youtube_auth_url = message
            st.info("🔐 **URL di autenticazione generato**")
            st.code(message, language=None)
            
            # Campo per inserire il codice di autorizzazione
            auth_code = st.text_input("Inserisci il codice di autorizzazione:", key="youtube_auth_code")
            
            if st.button("✅ Completa Autenticazione"):
                if auth_code:
                    success, message = authenticate_youtube_account(next_account, auth_code)
                    if success:
                        st.success(message)
                        # Pulisci session state
                        del st.session_state.youtube_auth_account
                        del st.session_state.youtube_auth_url
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("❌ Inserisci il codice di autorizzazione")
        else:
            st.success(message)
            st.rerun()
    
    # Se abbiamo già un URL di autenticazione, mostralo
    elif st.session_state.youtube_auth_url:
        st.info("🔐 **URL di autenticazione generato**")
        st.code(st.session_state.youtube_auth_url, language=None)
        
        # Campo per inserire il codice di autorizzazione
        auth_code = st.text_input("Inserisci il codice di autorizzazione:", key="youtube_auth_code")
        
        if st.button("✅ Completa Autenticazione"):
            if auth_code:
                success, message = authenticate_youtube_account(st.session_state.youtube_auth_account, auth_code)
                if success:
                    st.success(message)
                    # Pulisci session state
                    del st.session_state.youtube_auth_account
                    del st.session_state.youtube_auth_url
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("❌ Inserisci il codice di autorizzazione")
else:
    st.success("✅ Tutti gli account sono autenticati!")

# Sezione 3: Upload Test
st.header("🚀 Test Upload")

if youtube_status[0]:
    st.success("✅ YouTube configurato correttamente")
    
    # Upload di un video di test
    uploaded_file = st.file_uploader(
        "Carica un video per testare l'upload YouTube",
        type=['mp4', 'avi', 'mov', 'mkv'],
        help="Seleziona un video per testare l'upload"
    )
    
    if uploaded_file:
        st.info(f"📁 File caricato: {uploaded_file.name}")
        st.info(f"📏 Dimensione: {uploaded_file.size / (1024*1024):.2f} MB")
        
        # Salva il file temporaneamente
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_video_path = tmp_file.name
        
        st.success(f"✅ File salvato temporaneamente: {temp_video_path}")
        
        # Form per l'upload
        with st.form("youtube_test_upload"):
            st.subheader("📤 Carica su YouTube")
            
            youtube_title = st.text_input(
                "Titolo del video",
                value=f"Test Upload - {uploaded_file.name}",
                help="Titolo del video su YouTube"
            )
            
            youtube_description = st.text_area(
                "Descrizione",
                value="Video di test per verificare l'upload YouTube",
                help="Descrizione del video"
            )
            
            privacy_status = st.selectbox(
                "Privacy",
                options=["unlisted", "private", "public"],
                index=0,
                help="Impostazioni di privacy del video"
            )
            
            if st.form_submit_button("🚀 Carica su YouTube"):
                with st.spinner("Caricamento su YouTube..."):
                    try:
                        print(f"🔧 DEBUG: Starting YouTube upload test")
                        print(f"🔧 DEBUG: Video path: {temp_video_path}")
                        print(f"🔧 DEBUG: Title: {youtube_title}")
                        print(f"🔧 DEBUG: Privacy: {privacy_status}")
                        
                        youtube_link = upload_to_youtube(
                            video_path=temp_video_path,
                            title=youtube_title,
                            description=youtube_description,
                            privacy_status=privacy_status
                        )
                        
                        if youtube_link:
                            st.success("✅ Video caricato su YouTube con successo!")
                            st.markdown(f"**Link YouTube:** {youtube_link}")
                            st.session_state.youtube_test_link = youtube_link
                        else:
                            st.error("❌ Errore durante l'upload su YouTube")
                            
                    except Exception as e:
                        st.error(f"❌ Errore durante l'upload su YouTube: {str(e)}")
                        print(f"❌ DEBUG: Exception in YouTube upload test: {e}")
                    
                    finally:
                        # Pulisci il file temporaneo
                        if os.path.exists(temp_video_path):
                            os.unlink(temp_video_path)
                            print(f"🗑️ DEBUG: Cleaned up temp file: {temp_video_path}")
        
        # Mostra il link se disponibile
        if st.session_state.get('youtube_test_link'):
            st.success("✅ **Ultimo upload riuscito:**")
            st.markdown(f"**Link:** {st.session_state.youtube_test_link}")
    
else:
    st.error("❌ YouTube non configurato correttamente")
    st.info("🔐 Completa l'autenticazione prima di testare l'upload")

# Sezione 4: Debug Info
st.header("🔧 Debug Info")

if st.button("📊 Mostra Info Debug"):
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
st.info("ℹ️ **Nota:** Questa pagina è temporanea e verrà eliminata dopo i test.") 