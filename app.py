import streamlit as st
import os
import tempfile
import json
import time
from pathlib import Path
import sys
import random

# Rimuovi il file di log se esiste (per evitare loop infinito)
try:
    if os.path.exists("logs/app_debug.log"):
        os.remove("logs/app_debug.log")
    if os.path.exists("logs"):
        import shutil
        shutil.rmtree("logs")
except:
    pass

# Aggiungi il percorso del modulo Elaborazione
sys.path.append('Elaborazione')

# Importa le funzioni da prova.py
from Elaborazione.prova import (
    process_video, 
    generate_subtitles_only,
    finalize_video_processing,
    get_openai_client, 
    create_srt_file, 
    add_subtitles_to_video,
    format_timestamp,
    split_text
)

# Importa le funzioni per YouTube e Drive
from youtube_manager import upload_to_youtube, check_youtube_setup, get_youtube_status
from drive_manager import upload_video_to_drive, add_tracking_entry

# Importa le funzioni per YouTube
from youtube_manager import upload_to_youtube, check_youtube_setup, get_youtube_status

# Importa le funzioni per la gestione dei dati
from data_manager import (
    load_apartments,
    get_video_types,
    get_prompt_for_video_type,
    get_translation_prompt_for_video_type
)

# Importa le funzioni per Google Drive
from drive_manager import upload_video_to_drive, add_tracking_entry

def create_session_temp_file(prefix, suffix):
    """Crea un file temporaneo unico per questa sessione"""
    session_id = st.session_state.session_id
    timestamp = int(time.time())
    random_id = random.randint(1000, 9999)
    filename = f"{prefix}_{session_id}_{timestamp}_{random_id}{suffix}"
    return os.path.join(tempfile.gettempdir(), filename)

def create_session_temp_dir():
    """Crea una directory temporanea unica per questa sessione"""
    session_id = st.session_state.session_id
    timestamp = int(time.time())
    random_id = random.randint(1000, 9999)
    dirname = f"session_{session_id}_{timestamp}_{random_id}"
    temp_dir = os.path.join(tempfile.gettempdir(), dirname)
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def cleanup_session_files():
    """Pulisce i file temporanei di questa sessione"""
    session_id = st.session_state.session_id
    temp_dir = tempfile.gettempdir()
    
    # Trova e rimuovi tutti i file di questa sessione
    for filename in os.listdir(temp_dir):
        if filename.startswith(f"session_{session_id}_"):
            filepath = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                elif os.path.isdir(filepath):
                    import shutil
                    shutil.rmtree(filepath)
            except Exception as e:
                print(f"Errore nella pulizia file {filepath}: {e}")

# Configurazione della pagina
st.set_page_config(
    page_title="Video Editor con Sottotitoli",
    page_icon="🎬",
    layout="wide"
)

# Inizializza session state per multi-tab
if 'session_id' not in st.session_state:
    st.session_state.session_id = f"session_{int(time.time())}_{random.randint(1000, 9999)}"

if 'current_video_path' not in st.session_state:
    st.session_state.current_video_path = None

if 'processed_video' not in st.session_state:
    st.session_state.processed_video = None

if 'has_voice' not in st.session_state:
    st.session_state.has_voice = True

if 'youtube_link' not in st.session_state:
    st.session_state.youtube_link = ''

# Pulisci file temporanei di sessioni precedenti (più vecchie di 1 ora)
def cleanup_old_session_files():
    """Pulisce i file temporanei di sessioni vecchie"""
    temp_dir = tempfile.gettempdir()
    current_time = time.time()
    
    for filename in os.listdir(temp_dir):
        if filename.startswith("session_"):
            try:
                # Estrai timestamp dal nome file
                parts = filename.split('_')
                if len(parts) >= 3:
                    timestamp_str = parts[2]
                    if timestamp_str.isdigit():
                        file_timestamp = int(timestamp_str)
                        # Se il file è più vecchio di 1 ora, rimuovilo
                        if current_time - file_timestamp > 3600:  # 1 ora
                            filepath = os.path.join(temp_dir, filename)
                            if os.path.isfile(filepath):
                                os.remove(filepath)
                            elif os.path.isdir(filepath):
                                import shutil
                                shutil.rmtree(filepath)
            except Exception as e:
                pass  # Ignora errori di pulizia

# Esegui pulizia all'avvio
cleanup_old_session_files()

# Pulisci session state per evitare memory leaks
def cleanup_session_state():
    """Pulisce i dati temporanei dalla session state"""
    keys_to_clean = [key for key in st.session_state.keys() if key.startswith('auth_cache_') or key.startswith('pending_auth_')]
    for key in keys_to_clean:
        if key in st.session_state:
            del st.session_state[key]

# Esegui pulizia ogni 10 minuti
if 'last_cleanup' not in st.session_state:
    st.session_state.last_cleanup = time.time()

if time.time() - st.session_state.last_cleanup > 600:  # 10 minuti
    cleanup_session_state()
    cleanup_session_files()  # Pulisci anche i file di questa sessione
    st.session_state.last_cleanup = time.time()

# Titolo dell'app
st.title("🎬 Editing Video")
st.markdown("Sistema di elaborazione video con sottotitoli automatici per appartamenti")

# Mostra session ID per debug multi-tab
with st.expander("🔧 Debug Info"):
    st.write(f"**Session ID:** {st.session_state.session_id}")
    st.write(f"**Current Video:** {st.session_state.current_video_path}")
    st.write(f"**Processed Video:** {st.session_state.processed_video is not None}")
    st.write(f"**Has Voice:** {st.session_state.has_voice}")

# Carica gli appartamenti e le tipologie
apartments = load_apartments()
video_types = get_video_types()

# Carica configurazioni
def load_config():
    """Carica la configurazione dalle variabili d'ambiente"""
    config = {}
    
    # Carica OpenAI API Key da Streamlit secrets
    openai_api_key = st.secrets.get('OPENAI_API_KEY')
    if openai_api_key:
        config['openai_api_key'] = openai_api_key
    else:
        # Fallback alle variabili d'ambiente
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            config['openai_api_key'] = openai_api_key
        else:
            st.error("❌ OPENAI_API_KEY non trovata nei secrets o nelle variabili d'ambiente")
    
    return config

config = load_config()

# Campo per inserire la chiave API OpenAI
openai_api_key = st.text_input(
    "🔑 OpenAI API Key",
    value=config.get('openai_api_key', ''),
    type="password",
    help="Inserisci la tua chiave API OpenAI"
)

# Sidebar per configurazioni
with st.sidebar:
    st.header("⚙️ Configurazioni")
    
    # Debug section
    with st.expander("🔍 Debug Secrets"):
        st.write("**Testing secrets loading...**")
        
        # Test OpenAI API Key
        openai_secret = st.secrets.get('OPENAI_API_KEY')
        st.write(f"OpenAI API Key loaded: {'✅' if openai_secret else '❌'}")
        
        # Test Google Sheets Credentials
        google_secret = st.secrets.get('GOOGLE_SHEETS_CREDENTIALS')
        st.write(f"Google Sheets Credentials loaded: {'✅' if google_secret else '❌'}")
        
        if google_secret:
            st.write(f"Type: {type(google_secret)}")
            if isinstance(google_secret, str):
                st.write("Is string, attempting JSON parse...")
                try:
                    import json
                    parsed = json.loads(google_secret)
                    st.write("✅ JSON parsing successful")
                    
                    # Test private key
                    private_key = parsed.get('private_key', '')
                    if private_key:
                        st.write(f"Private key length: {len(private_key)}")
                        st.write(f"Private key starts with: {private_key[:50]}...")
                        st.write(f"Contains \\n: {'✅' if '\\n' in private_key else '❌'}")
                        st.write(f"Contains \\\\n: {'✅' if '\\\\n' in private_key else '❌'}")
                    else:
                        st.write("❌ No private_key found")
                        
                except Exception as e:
                    st.write(f"❌ JSON parsing failed: {e}")
        
        # Test YouTube Credentials
        youtube_secret = st.secrets.get('YOUTUBE_CLIENT_SECRETS')
        st.write(f"YouTube Credentials loaded: {'✅' if youtube_secret else '❌'}")
    
    # Mostra stato API Key
    if openai_api_key:
        # Test della chiave API
        try:
            client = get_openai_client(openai_api_key)
            client.models.list()
            st.success("✅ OpenAI API Key valida!")
        except Exception as e:
            st.error(f"❌ Errore con OpenAI API Key: {str(e)}")
            st.info("💡 Verifica che la chiave API sia corretta e abbia crediti sufficienti")
    else:
        st.warning("⚠️ Inserisci la tua OpenAI API Key per iniziare")
    
    # Pulsante per ricaricare configurazione
    if st.button("🔄 Ricarica Configurazione"):
        config = load_config()
        openai_api_key = os.getenv('OPENAI_API_KEY') or config.get('openai_api_key', '')
        st.success("✅ Configurazione ricaricata!")
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📋 Istruzioni")
    st.markdown("""
    1. **Inserisci la tua OpenAI API Key**
    2. **Carica il video** nel box principale
    3. **Clicca 'Elabora Video'**
    4. **Modifica i sottotitoli** se necessario
    5. **Scarica o carica su YouTube**
    """)

# Inizializza session state
if 'processed_video' not in st.session_state:
    st.session_state.processed_video = None
if 'segments' not in st.session_state:
    st.session_state.segments = []
if 'current_video_path' not in st.session_state:
    st.session_state.current_video_path = None
if 'subtitles_generated' not in st.session_state:
    st.session_state.subtitles_generated = False
if 'subtitles_data' not in st.session_state:
    st.session_state.subtitles_data = None

# Sezione principale
st.header("📤 Carica Video")

# Upload del video
uploaded_video = st.file_uploader(
    "Scegli un file video",
    type=['mp4', 'avi', 'mov', 'mkv'],
    help="Formati supportati: MP4, AVI, MOV, MKV"
)

if uploaded_video is not None:
    # Salva il video temporaneamente con nome unico per la sessione
    video_path = create_session_temp_file("video", ".mp4")
    with open(video_path, "wb") as f:
        f.write(uploaded_video.getvalue())
    st.session_state.current_video_path = video_path
    
    # Mostra informazioni del video
    st.success(f"✅ Video caricato: {uploaded_video.name}")

# Sezione di selezione
st.header("📋 Configurazione Video")

# Selezione appartamento
selected_apartment = st.selectbox(
    "🏠 Seleziona Appartamento",
    options=[""] + apartments,
    help="Scegli l'appartamento per cui stai creando il video"
)

# Selezione tipologia video
selected_video_type = st.selectbox(
    "🎥 Tipologia Video",
    options=[""] + video_types,
    help="Scegli la tipologia di video che stai creando"
)

# Campo per aggiungere nuove tipologie
with st.expander("➕ Aggiungi Nuova Tipologia"):
    new_video_type = st.text_input(
        "Nuova tipologia",
        placeholder="es: aspirapolvere",
        help="Inserisci una nuova tipologia di video"
    )
    if st.button("Aggiungi"):
        if new_video_type and new_video_type not in video_types:
            video_types.append(new_video_type)
            video_types.sort()
            st.success(f"✅ Tipologia '{new_video_type}' aggiunta!")
            st.rerun()

# Verifica che siano state selezionate entrambe le opzioni
if not selected_apartment or not selected_video_type:
    st.warning("⚠️ Seleziona sia l'appartamento che la tipologia di video per procedere")
    st.stop()

# Mostra il titolo del video
video_title = f"{selected_apartment} {selected_video_type}"
st.success(f"📹 Titolo video: **{video_title}**")

# Pulsante per elaborare (solo se video caricato e selezioni fatte)
if uploaded_video is not None and selected_apartment and selected_video_type:
    # Crea directory temporanea per questa sessione
    output_dir = create_session_temp_dir()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🎬 Genera Sottotitoli", type="primary"):
            if not openai_api_key:
                st.error("❌ Inserisci la tua OpenAI API Key")
                st.stop()
            
            with st.spinner("🔄 Generazione sottotitoli in corso..."):
                try:
                    # Genera solo i sottotitoli
                    result = generate_subtitles_only(
                        input_video=video_path,
                        openai_api_key=openai_api_key,
                        output_dir=output_dir,
                        video_type=selected_video_type
                    )
                    
                    if result['success']:
                        st.session_state.subtitles_data = result
                        st.session_state.segments = result.get('segments', [])
                        st.session_state.subtitles_generated = True
                        st.success("✅ Sottotitoli generati con successo!")
                        st.rerun()
                    else:
                        st.error(f"❌ Errore durante la generazione: {result.get('error', 'Errore sconosciuto')}")
                        
                except Exception as e:
                    st.error(f"❌ Errore durante la generazione: {str(e)}")
                    cleanup_session_files()
    
    with col2:
        if st.session_state.subtitles_generated and st.button("🚀 Completa Elaborazione", type="secondary"):
            with st.spinner("🔄 Completamento elaborazione in corso..."):
                try:
                    # Valori di default per l'altezza dei sottotitoli (stessi del file locale)
                    italian_height = 120
                    english_height = 60
                    
                    # Completa l'elaborazione
                    result = finalize_video_processing(
                        input_video=video_path,
                        srt_it_file=st.session_state.subtitles_data['srt_it_file'],
                        srt_en_file=st.session_state.subtitles_data['srt_en_file'],
                        output_dir=output_dir,
                        italian_height=italian_height,
                        english_height=english_height
                    )
                    
                    if result['success']:
                        st.session_state.processed_video = result
                        st.success("✅ Video elaborato con successo!")
                        
                        # Mostra il video elaborato
                        if os.path.exists(result['final_video']):
                            st.video(result['final_video'])
                            
                            # Aggiungi pulsante di download
                            with open(result['final_video'], "rb") as video_file:
                                st.download_button(
                                    label="📥 Scarica Video Elaborato",
                                    data=video_file.read(),
                                    file_name=f"video_elaborato_{int(time.time())}.mp4",
                                    mime="video/mp4"
                                )
                    else:
                        st.error(f"❌ Errore durante l'elaborazione: {result.get('error', 'Errore sconosciuto')}")
                        
                except Exception as e:
                    st.error(f"❌ Errore durante l'elaborazione: {str(e)}")
                    cleanup_session_files()

# Sezione per modificare i sottotitoli (solo se i sottotitoli sono stati generati)
if st.session_state.segments and (st.session_state.subtitles_generated or (st.session_state.processed_video and st.session_state.processed_video.get("has_voice", True))):
    st.markdown("---")
    st.header("✏️ Modifica Sottotitoli")
    st.info("Modifica i sottotitoli italiani e inglesi. I sottotitoli inglesi manterranno la stessa durata di quelli italiani.")
    
    # Crea le colonne per la tabella
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.write("**Inizio**")
    with col2:
        st.write("**Italiano**")
    with col3:
        st.write("**Inglese**")
    with col4:
        st.write("**Fine**")
    
    # Inizializza edited_segments se non esiste
    if 'edited_segments' not in st.session_state:
        st.session_state.edited_segments = st.session_state.segments.copy()
    
    # Mostra i sottotitoli modificabili
    for i, segment in enumerate(st.session_state.edited_segments):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.write(format_timestamp(segment['start']))
        
        with col2:
            # Campo per il testo italiano
            edited_text = st.text_area(
                f"IT {i+1}",
                value=segment['text'],
                key=f"it_{i}",
                height=60
            )
            st.session_state.edited_segments[i]['text'] = edited_text
        
        with col3:
            # Campo per il testo inglese
            edited_text_en = st.text_area(
                f"EN {i+1}",
                value=segment.get('text_en', ''),
                key=f"en_{i}",
                height=60
            )
            st.session_state.edited_segments[i]['text_en'] = edited_text_en
        
        with col4:
            st.write(format_timestamp(segment['end']))
    
    # Pulsanti per rielaborare con i sottotitoli modificati
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Rielabora con Sottotitoli Modificati"):
            with st.spinner("Rielaborazione in corso..."):
                try:
                    # Crea i file SRT temporanei
                    temp_srt_it = tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False)
                    temp_srt_en = tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False)
                    
                    # Scrivi i sottotitoli modificati
                    create_srt_file(st.session_state.edited_segments, temp_srt_it.name, "IT")
                    create_srt_file(st.session_state.edited_segments, temp_srt_en.name, "EN")
                    
                    # Se il video è già stato elaborato, rielabora con i nuovi sottotitoli
                    if st.session_state.processed_video:
                        result = add_subtitles_to_video(
                            input_video=st.session_state.processed_video['video_with_music'],
                            subtitle_file_it=temp_srt_it.name,
                            subtitle_file_en=temp_srt_en.name,
                            output_video=st.session_state.processed_video['final_video']
                        )
                        
                        st.success("✅ Video rielaborato con successo!")
                        
                        # Mostra il video rielaborato
                        if os.path.exists(st.session_state.processed_video['final_video']):
                            st.video(st.session_state.processed_video['final_video'])
                            
                            # Aggiungi pulsante di download
                            with open(st.session_state.processed_video['final_video'], "rb") as video_file:
                                st.download_button(
                                    label="📥 Scarica Video Elaborato",
                                    data=video_file.read(),
                                    file_name=f"video_elaborato_{int(time.time())}.mp4",
                                    mime="video/mp4"
                                )
                    else:
                        # Aggiorna i file SRT per la prossima elaborazione
                        st.session_state.subtitles_data['srt_it_file'] = temp_srt_it.name
                        st.session_state.subtitles_data['srt_en_file'] = temp_srt_en.name
                        st.success("✅ Sottotitoli aggiornati! Ora puoi completare l'elaborazione.")
                    
                    # Pulisci i file temporanei
                    os.unlink(temp_srt_it.name)
                    os.unlink(temp_srt_en.name)
                    
                except Exception as e:
                    st.error(f"❌ Errore durante la rielaborazione: {str(e)}")
    
    with col2:
        if st.button("🔄 Rigenera Sottotitoli"):
            with st.spinner("Rigenerazione sottotitoli in corso..."):
                try:
                    # Rigenera i sottotitoli
                    result = generate_subtitles_only(
                        input_video=video_path,
                        openai_api_key=openai_api_key,
                        output_dir=output_dir,
                        video_type=selected_video_type
                    )
                    
                    if result['success']:
                        st.session_state.subtitles_data = result
                        st.session_state.segments = result.get('segments', [])
                        st.session_state.edited_segments = st.session_state.segments.copy()
                        st.success("✅ Sottotitoli rigenerati con successo!")
                        st.rerun()
                    else:
                        st.error(f"❌ Errore durante la rigenerazione: {result.get('error', 'Errore sconosciuto')}")
                        
                except Exception as e:
                    st.error(f"❌ Errore durante la rigenerazione: {str(e)}")

# Sezione per personalizzare l'altezza dei sottotitoli - RIMOSSA PER PROBLEMI FFMPEG



# Sezione per modifiche personalizzate al prompt
st.markdown("---")
st.header("✏️ Modifiche personalizzate al prompt")

custom_prompt = st.text_area(
    "Prompt personalizzato per l'ottimizzazione dei sottotitoli",
    placeholder="Inserisci un prompt personalizzato per l'ottimizzazione dei sottotitoli...",
    help="Questo prompt verrà utilizzato per ottimizzare i sottotitoli del video"
)

# Sezione per l'upload su YouTube
st.markdown("---")
st.header("📺 Upload YouTube")

# Controlla lo stato di YouTube
youtube_status = check_youtube_setup()
st.info(youtube_status[1])

# Form per l'upload su YouTube
with st.form("youtube_upload_form"):
    st.subheader("📤 Carica su YouTube")
    
    # Campo per il titolo del video
    youtube_title = st.text_input(
        "Titolo del video",
        value=video_title,
        help="Titolo del video su YouTube"
    )
    
    # Campo per la privacy
    privacy_status = st.selectbox(
        "Privacy",
        options=["unlisted", "private", "public"],
        index=0,
        help="Impostazioni di privacy del video"
    )
    
    # Pulsante per caricare
    if st.form_submit_button("🚀 Carica su YouTube"):
        print("🔧 DEBUG: YouTube upload button clicked")
        print(f"🔧 DEBUG: Video title: {youtube_title}")
        print(f"🔧 DEBUG: Privacy status: {privacy_status}")
        
        # Controlla se c'è un codice di autenticazione in attesa (logica rimossa - ora usa youtube_manager)
        
        if youtube_status[0]:
            print("🔧 DEBUG: YouTube status is OK, starting upload")
            with st.spinner("Caricamento su YouTube..."):
                try:
                    print("🔧 DEBUG: Getting processed video path")
                    if st.session_state.processed_video and 'final_video' in st.session_state.processed_video:
                        video_path = st.session_state.processed_video['final_video']
                        print(f"🔧 DEBUG: Video path: {video_path}")
                        print(f"🔧 DEBUG: File exists: {os.path.exists(video_path)}")
                        
                        if os.path.exists(video_path):
                            print("🔧 DEBUG: Calling upload_to_youtube")
                            youtube_link = upload_to_youtube(
                                video_path=video_path,
                                title=youtube_title,
                                privacy_status=privacy_status
                            )
                            print(f"🔧 DEBUG: Upload result: {youtube_link}")
                            
                            if youtube_link:
                                st.success("✅ Video caricato su YouTube con successo!")
                                st.markdown(f"**Link YouTube:** {youtube_link}")
                                st.session_state.youtube_link = youtube_link
                            else:
                                st.error("❌ Errore durante l'upload su YouTube")
                        else:
                            st.error("❌ File video non trovato")
                            print(f"❌ DEBUG: Video file not found at {video_path}")
                    else:
                        st.error("❌ Nessun video elaborato disponibile")
                        print("❌ DEBUG: No processed video in session state")
                        
                except Exception as e:
                    st.error(f"❌ Errore durante l'upload su YouTube: {str(e)}")
                    print(f"❌ DEBUG: Exception in YouTube upload: {e}")
        else:
            print("❌ DEBUG: YouTube status is not OK")
            st.error("❌ YouTube non configurato correttamente")
            
            # Mostra banner di autenticazione se necessario
            from youtube_manager import get_next_available_account, authenticate_youtube_account
            next_account = get_next_available_account()
            if next_account:
                st.warning("🔐 **Autenticazione YouTube richiesta**")
                st.info(f"Per caricare video su YouTube, devi autenticare l'account: **{next_account}**")
                
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

# Sezione per l'upload su Google Drive
st.subheader("☁️ Carica su Google Drive")

if st.session_state.processed_video and os.path.exists(st.session_state.processed_video['final_video']):
    if st.button("🚀 Carica su Drive"):
        with st.spinner("Caricamento su Google Drive..."):
            drive_link = upload_video_to_drive(
                video_path=st.session_state.processed_video['final_video'],
                apartment_name=selected_apartment,
                video_type=selected_video_type
            )
            
            if drive_link:
                st.success("✅ Video caricato su Drive con successo!")
                st.markdown(f"**Link Drive:** {drive_link}")
                
                # Salva nel tracking
                youtube_link = st.session_state.get('youtube_link', '')
                italian_transcript_path = st.session_state.get('italian_transcript_path', '')
                english_transcript_path = st.session_state.get('english_transcript_path', '')
                add_tracking_entry(
                    apartment=selected_apartment,
                    video_type=selected_video_type,
                    youtube_link=youtube_link,
                    drive_link=drive_link,
                    italian_transcript_path=italian_transcript_path,
                    english_transcript_path=english_transcript_path
                )
                
                st.session_state.drive_link = drive_link
                st.success("✅ Entry aggiunta al tracking!")
            else:
                st.error("❌ Errore durante il caricamento su Drive")
                st.info("""
                **Possibili cause:**
                1. Problemi di autenticazione Google Drive
                2. Permessi insufficienti sulla cartella
                3. Connessione internet instabile
                
                **Soluzione:**
                1. Verifica le credenziali Google Drive
                2. Controlla i permessi sulla cartella condivisa
                3. Riprova più tardi
                """)

# Sezione per i transcript modificabili (solo se c'è voce)
if st.session_state.processed_video and (st.session_state.segments or st.session_state.get('edited_segments')) and st.session_state.processed_video.get("has_voice", True):
    st.markdown("---")
    st.header("📝 Transcript per Manuali")
    st.info("Modifica i testi per creare i manuali di istruzioni. I file verranno salvati nella cartella del video.")
    
    # Usa i segmenti modificati se disponibili, altrimenti quelli originali
    segments_for_transcript = st.session_state.get('edited_segments', st.session_state.segments)
    
    # Prepara i testi per le box
    italian_text = ""
    english_text = ""
    
    for i, segment in enumerate(segments_for_transcript, 1):
        italian_text += f"{i}. {segment['text']}\n"
        
        # Usa il testo inglese se disponibile, altrimenti traduci
        english_segment = segment.get('text_en', '')
        if not english_segment and segment['text']:
            # Traduci automaticamente se non c'è già
            try:
                client = get_openai_client(openai_api_key)
                translation = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Traduci in inglese questo testo per manuali:"},
                        {"role": "user", "content": segment['text']}
                    ]
                )
                english_segment = translation.choices[0].message.content.strip()
            except:
                english_segment = ""
        
        english_text += f"{i}. {english_segment}\n"
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🇮🇹 Italiano")
        edited_italian_text = st.text_area(
            "Testo italiano",
            value=italian_text,
            key="transcript_italian_box",
            height=400
        )
    
    with col2:
        st.subheader("🇬🇧 Inglese")
        edited_english_text = st.text_area(
            "Testo inglese",
            value=english_text,
            key="transcript_english_box",
            height=400
        )
    
    # Pulsanti per salvare i transcript
    if st.button("💾 Salva Entrambi i Transcript"):
        try:
            # Salva su Google Drive
            from drive_manager import get_drive_service, create_folder_if_not_exists
            
            service = get_drive_service()
            
            # ID della cartella principale
            main_folder_id = "1w9P2oiRfFgsOOj82V7xOruhjnl-APCCi"
            
            # Crea la cartella dell'appartamento se non esiste
            apartment_folder_id = create_folder_if_not_exists(service, main_folder_id, selected_apartment)
            if not apartment_folder_id:
                st.error("❌ Errore nella creazione della cartella appartamento")
                st.stop()
            
            # Crea la cartella del tipo video se non esiste
            video_type_folder_id = create_folder_if_not_exists(service, apartment_folder_id, selected_video_type)
            if not video_type_folder_id:
                st.error("❌ Errore nella creazione della cartella tipo video")
                st.stop()
            
            # Carica il file su Drive
            from googleapiclient.http import MediaIoBaseUpload
            import io
            
            # Salva transcript italiano
            filename_it = f"Istruzioni_{selected_video_type}_{selected_apartment}_ita.txt"
            file_metadata_it = {
                'name': filename_it,
                'parents': [video_type_folder_id]
            }
            
            file_content_it = io.BytesIO(edited_italian_text.encode('utf-8'))
            media_it = MediaIoBaseUpload(file_content_it, mimetype='text/plain', resumable=True)
            
            file_it = service.files().create(
                body=file_metadata_it,
                media_body=media_it,
                fields='id,webViewLink'
            ).execute()
            
            # Rendi il file pubblico
            service.permissions().create(
                fileId=file_it['id'],
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
            
            file_link_it = file_it['webViewLink']
            
            # Salva transcript inglese
            filename_en = f"Istruzioni_{selected_video_type}_{selected_apartment}_en.txt"
            file_metadata_en = {
                'name': filename_en,
                'parents': [video_type_folder_id]
            }
            
            file_content_en = io.BytesIO(edited_english_text.encode('utf-8'))
            media_en = MediaIoBaseUpload(file_content_en, mimetype='text/plain', resumable=True)
            
            file_en = service.files().create(
                body=file_metadata_en,
                media_body=media_en,
                fields='id,webViewLink'
            ).execute()
            
            # Rendi il file pubblico
            service.permissions().create(
                fileId=file_en['id'],
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
            
            file_link_en = file_en['webViewLink']
            
            st.success(f"✅ Entrambi i transcript salvati su Drive!")
            st.info(f"🇮🇹 Italiano: {filename_it}")
            st.info(f"🇬🇧 Inglese: {filename_en}")
            
            st.session_state.italian_transcript_path = file_link_it
            st.session_state.english_transcript_path = file_link_en
            
        except Exception as e:
            st.error(f"❌ Errore nel salvataggio dei transcript: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎬 Video Editor con Sottotitoli Automatici | Powered by OpenAI Whisper & GPT-4</p>
</div>
""", unsafe_allow_html=True) 