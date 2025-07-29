import streamlit as st
import os
import tempfile
import json
import time
from pathlib import Path
import subprocess
import sys

# Aggiungi il percorso del modulo Elaborazione
sys.path.append('Elaborazione')

# Importa le funzioni da prova.py
from prova import (
    process_video, 
    get_openai_client, 
    create_srt_file, 
    add_subtitles_to_video,
    format_timestamp,
    split_text
)

# Importa le funzioni per YouTube
from youtube_upload import upload_to_youtube, check_youtube_setup

# Importa le funzioni per la gestione dei dati
from data_manager import (
    load_apartments,
    get_video_types,
    get_prompt_for_video_type,
    get_translation_prompt_for_video_type
)

# Importa le funzioni per Google Drive
from drive_manager import upload_video_to_drive, add_tracking_entry

# Configurazione della pagina
st.set_page_config(
    page_title="Video Editor con Sottotitoli",
    page_icon="🎬",
    layout="wide"
)

# Titolo dell'app
st.title("🎬 Editing Video")
st.markdown("Sistema di elaborazione video con sottotitoli automatici per appartamenti")

# Carica gli appartamenti e le tipologie
apartments = load_apartments()
video_types = get_video_types()

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

# Carica configurazioni
def load_config():
    """Carica la configurazione dalle variabili d'ambiente"""
    config = {}
    
    # Carica OpenAI API Key dalle variabili d'ambiente
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if openai_api_key:
        config['openai_api_key'] = openai_api_key
    else:
        st.error("❌ OPENAI_API_KEY non trovata nelle variabili d'ambiente")
    
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

# Sezione principale
st.header("📤 Carica Video")

# Upload del video
uploaded_video = st.file_uploader(
    "Scegli un file video",
    type=['mp4', 'avi', 'mov', 'mkv'],
    help="Formati supportati: MP4, AVI, MOV, MKV"
)

if uploaded_video is not None:
    # Salva il video temporaneamente
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        tmp_file.write(uploaded_video.getvalue())
        video_path = tmp_file.name
        st.session_state.current_video_path = video_path
    
    # Mostra informazioni del video
    st.success(f"✅ Video caricato: {uploaded_video.name}")
    
    # Pulsante per elaborare
    if uploaded_video:
        if st.button("🚀 Elabora Video", type="primary"):
            if not openai_api_key:
                st.error("❌ Inserisci la tua OpenAI API Key per elaborare il video")
                st.stop()
            
            with st.spinner("Elaborazione in corso..."):
                # Crea directory temporanea per i file
                temp_dir = tempfile.mkdtemp()
                
                # Usa musica di default
                default_music = "Elaborazione/audio.mp3"
                if os.path.exists(default_music):
                    music_path = default_music
                else:
                    st.error("❌ File musica di default non trovato: Elaborazione/audio.mp3")
                    st.stop()
                
                # Elabora il video
                result = process_video(
                    input_video=video_path,
                    music_file=music_path,
                    openai_api_key=openai_api_key,
                    output_dir=temp_dir,
                    custom_prompt=None,
                    video_type=selected_video_type
                )
                
                if result["success"]:
                    st.session_state.processed_video = result
                    st.session_state.segments = result["segments"]
                    
                    # Controlla se il video ha voce
                    has_voice = result.get("has_voice", True)
                    if has_voice:
                        st.success("✅ Video elaborato con successo!")
                    else:
                        st.success("✅ Video elaborato con successo! (Nessuna voce rilevata)")
                    
                    # Mostra il video elaborato
                    with open(result["final_video"], "rb") as video_file:
                        st.video(video_file.read())
                else:
                    st.error(f"❌ Errore durante l'elaborazione: {result['error']}")
    elif not uploaded_video:
        st.warning("⚠️ Carica un video per iniziare l'elaborazione")

# Sezione per modificare i sottotitoli (solo dopo elaborazione e solo se c'è voce)
if st.session_state.processed_video and st.session_state.segments and st.session_state.processed_video.get("has_voice", True):
    st.markdown("---")
    st.header("✏️ Modifica Sottotitoli")
    
    # Editor per i sottotitoli
    edited_segments = []
    
    for i, segment in enumerate(st.session_state.segments):
        st.markdown(f"**Sottotitolo {i+1}**")
        
        col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
        
        with col1:
            st.text("**Inizio**")
            start_time = st.text_input(
                "Inizio",
                value=format_timestamp(segment['start']),
                key=f"start_{i}",
                label_visibility="collapsed"
            )
        
        with col2:
            st.text("**Italiano**")
            edited_text_it = st.text_input(
                "Testo italiano",
                value=segment['text'],
                key=f"text_it_{i}",
                label_visibility="collapsed"
            )
        
        with col3:
            st.text("**Inglese**")
            # Usa il testo inglese se disponibile, altrimenti traduci
            english_text = segment.get('text_en', '')
            if not english_text and segment['text']:
                # Traduci automaticamente se non c'è già
                try:
                    client = get_openai_client(openai_api_key)
                    translation = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "Traduci in inglese questo testo per sottotitoli:"},
                            {"role": "user", "content": segment['text']}
                        ]
                    )
                    english_text = translation.choices[0].message.content.strip()
                except:
                    english_text = ""
            
            edited_text_en = st.text_input(
                "Testo inglese",
                value=english_text,
                key=f"text_en_{i}",
                label_visibility="collapsed"
            )
        
        with col4:
            st.text("**Fine**")
            end_time = st.text_input(
                "Fine",
                value=format_timestamp(segment['end']),
                key=f"end_{i}",
                label_visibility="collapsed"
            )
        
        edited_segments.append({
            'start': segment['start'],
            'end': segment['end'],
            'text': edited_text_it,
            'text_en': edited_text_en
        })
        
        st.markdown("---")
    
    # Pulsante per applicare le modifiche
    if st.button("💾 Applica Modifiche"):
        # Ricrea i file SRT con le modifiche
        temp_dir = tempfile.mkdtemp()
        
        # File SRT italiani
        subtitle_file_it = os.path.join(temp_dir, "subtitles_it_edited.srt")
        create_srt_file(edited_segments, subtitle_file_it, "IT")
        
        # File SRT inglesi (usa i testi modificati)
        subtitle_file_en = os.path.join(temp_dir, "subtitles_en_edited.srt")
        
        # Crea file SRT inglese con i testi modificati
        with open(subtitle_file_en, "w", encoding="utf-8") as srt:
            for i, segment in enumerate(edited_segments, start=1):
                start = format_timestamp(segment['start'])
                end = format_timestamp(segment['end'])
                text = segment['text_en']
                lines = split_text(text)
                srt.write(f"{i}\n{start} --> {end}\n{lines[0]}\n{lines[1] if len(lines) > 1 else ''}\n\n")
        
        # Ricrea il video con i sottotitoli modificati
        final_output = os.path.join(temp_dir, "final_output_edited.mp4")
        
        # Aggiungi sottotitoli al video originale
        add_subtitles_to_video(
            st.session_state.current_video_path,
            subtitle_file_it,
            subtitle_file_en,
            final_output
        )
        
        st.session_state.processed_video["final_video"] = final_output
        st.session_state.edited_segments = edited_segments  # Salva per i transcript
        st.success("✅ Video aggiornato con le modifiche!")

# Sezione per personalizzare altezza sottotitoli
if st.session_state.processed_video and st.session_state.processed_video.get("has_voice", True):
    st.markdown("---")
    st.header("📏 Personalizza Altezza Sottotitoli")
    st.info("Modifica l'altezza dei sottotitoli italiani e inglesi. Valori più alti = sottotitoli più in basso.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        italian_height = st.slider(
            "🇮🇹 Altezza sottotitoli italiani",
            min_value=20,
            max_value=150,
            value=75,
            step=5,
            help="Altezza dei sottotitoli italiani (default: 75)"
        )
    
    with col2:
        english_height = st.slider(
            "🇬🇧 Altezza sottotitoli inglesi",
            min_value=20,
            max_value=150,
            value=50,
            step=5,
            help="Altezza dei sottotitoli inglesi (default: 50)"
        )
    
    if st.button("🔄 Rielabora con nuove altezze"):
        with st.spinner("Rielaborazione con nuove altezze in corso..."):
            # Crea directory temporanea per i file
            temp_dir = tempfile.mkdtemp()
            
            # Usa musica di default
            default_music = "Elaborazione/audio.mp3"
            if os.path.exists(default_music):
                music_path = default_music
            else:
                st.error("❌ File musica di default non trovato: Elaborazione/audio.mp3")
                st.stop()
            
            # Elabora il video con le nuove altezze
            result = process_video(
                input_video=st.session_state.current_video_path,
                music_file=music_path,
                openai_api_key=openai_api_key,
                output_dir=temp_dir,
                video_type=selected_video_type,
                italian_height=italian_height,
                english_height=english_height
            )
            
            if result["success"]:
                st.session_state.processed_video = result
                st.session_state.segments = result["segments"]
                st.success(f"✅ Video rielaborato con nuove altezze! (IT: {italian_height}, EN: {english_height})")
                
                # Mostra il video elaborato
                with open(result["final_video"], "rb") as video_file:
                    st.video(video_file.read())
            else:
                st.error(f"❌ Errore durante la rielaborazione: {result['error']}")

# Sezione per modifiche personalizzate
if st.session_state.processed_video:
    st.markdown("---")
    st.header("✏️ Modifiche personalizzate al prompt")
    
    custom_prompt = st.text_area(
        "Modifiche personalizzate al prompt",
        placeholder="Es: Usa un tono più formale, Evita termini tecnici, etc.",
        help="Inserisci modifiche specifiche al prompt di elaborazione. Queste verranno applicate solo per questa elaborazione."
    )
    
    if custom_prompt and custom_prompt.strip():
        with st.expander("📝 Anteprima modifiche al prompt"):
            st.info("**Modifiche personalizzate:**")
            st.text(custom_prompt)
            st.info("Queste modifiche verranno aggiunte al prompt base di elaborazione.")
    
    if st.button("🔄 Rielabora con modifiche personalizzate"):
        with st.spinner("Rielaborazione in corso..."):
            # Crea directory temporanea per i file
            temp_dir = tempfile.mkdtemp()
            
            # Usa musica di default
            default_music = "Elaborazione/audio.mp3"
            if os.path.exists(default_music):
                music_path = default_music
            else:
                st.error("❌ File musica di default non trovato: Elaborazione/audio.mp3")
                st.stop()
            
            # Elabora il video con le modifiche personalizzate
            result = process_video(
                input_video=st.session_state.current_video_path,
                music_file=music_path,
                openai_api_key=openai_api_key,
                output_dir=temp_dir,
                custom_prompt=custom_prompt.strip(),
                video_type=selected_video_type
            )
            
            if result["success"]:
                st.session_state.processed_video = result
                st.session_state.segments = result["segments"]
                st.success("✅ Video rielaborato con successo!")
                
                # Mostra il video elaborato
                with open(result["final_video"], "rb") as video_file:
                    st.video(video_file.read())
            else:
                st.error(f"❌ Errore durante la rielaborazione: {result['error']}")

# Sezione per download e upload
if st.session_state.processed_video:
    st.markdown("---")
    st.header("📤 Esporta Video")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💾 Download")
        
        # Pulsante per scaricare il video
        with open(st.session_state.processed_video["final_video"], "rb") as video_file:
            st.download_button(
                label="📥 Scarica Video",
                data=video_file.read(),
                file_name="video_elaborato.mp4",
                mime="video/mp4"
            )
    
    with col2:
        st.subheader("📺 Upload YouTube")
        
        # Verifica configurazione YouTube
        youtube_status = check_youtube_setup()
        
        if not youtube_status["ready"]:
            st.warning("⚠️ YouTube non configurato")
            st.info("📋 Per caricare su YouTube, devi configurare le credenziali OAuth2")
            with st.expander("🔧 Come configurare YouTube"):
                st.markdown("""
                ### Configurazione YouTube OAuth2 per Streamlit Cloud:
                
                **⚠️ IMPORTANTE:** Questa app funziona su Streamlit Cloud. Per l'autenticazione YouTube:
                
                1. **Vai su Google Cloud Console:**
                   - Apri [Google Cloud Console](https://console.cloud.google.com/)
                   - Crea un nuovo progetto o seleziona uno esistente
                
                2. **Abilita l'API YouTube:**
                   - Vai su "APIs & Services" > "Library"
                   - Cerca "YouTube Data API v3"
                   - Clicca su "Enable"
                
                3. **Crea credenziali OAuth2:**
                   - Vai su "APIs & Services" > "Credentials"
                   - Clicca "Create Credentials" > "OAuth 2.0 Client IDs"
                   - Tipo: "Web application" (⚠️ IMPORTANTE per Streamlit Cloud)
                   - Nome: "YouTube Upload App"
                   - **URI autorizzati:** Aggiungi l'URL della tua app Streamlit
                   - Clicca "Create"
                
                4. **Scarica le credenziali:**
                   - Clicca sul client OAuth2 appena creato
                   - Clicca "Download JSON"
                   - Rinomina il file in `client_secrets.json`
                   - Carica il file nella sezione "Secrets" di Streamlit Cloud
                
                5. **Configura Streamlit Cloud:**
                   - Vai su [Streamlit Cloud](https://share.streamlit.io/)
                   - Seleziona il tuo repository
                   - Vai su "Settings" > "Secrets"
                   - Incolla il contenuto di `client_secrets.json`
                
                6. **Prima autenticazione:**
                   - Alla prima richiesta di upload, si aprirà una finestra per l'autenticazione
                   - Accedi con il tuo account YouTube
                   - Autorizza l'applicazione
                
                **💡 Suggerimento:** Ogni account YouTube ha un limite di 5 video al giorno. Se raggiungi il limite, configura un altro account.
                """)
        else:
            # Form per l'upload su YouTube
            with st.form("youtube_upload"):
                video_title = st.text_input("Titolo del video", value=video_title)
                privacy_status = st.selectbox(
                    "Privacy",
                    options=["unlisted", "private", "public"],
                    help="unlisted = solo con link, private = solo tu, public = tutti"
                )
                
                if st.form_submit_button("🚀 Carica su YouTube"):
                    with st.spinner("Caricamento su YouTube..."):
                        result = upload_to_youtube(
                            video_path=st.session_state.processed_video["final_video"],
                            title=video_title,
                            privacy_status=privacy_status
                        )
                        
                        if result["success"]:
                            st.success("✅ Video caricato con successo!")
                            st.markdown(f"**Link:** {result['video_url']}")
                            
                            # Salva il link YouTube nel session state
                            st.session_state.youtube_link = result['video_url']
                            
                            # Mostra informazioni aggiuntive
                            with st.expander("📊 Dettagli upload"):
                                st.json({
                                    "video_id": result['video_id'],
                                    "title": video_title,
                                    "privacy": privacy_status,
                                    "url": result['video_url']
                                })
                        else:
                            st.error(f"❌ Errore durante il caricamento: {result['error']}")
                            
                            # Gestione errori specifici per Streamlit Cloud
                            error_msg = result['error'].lower()
                            
                            if "quota" in error_msg or "daily" in error_msg or "limit" in error_msg:
                                st.warning("🚨 **Limite giornaliero raggiunto!**")
                                st.info("""
                                **Hai raggiunto il limite di 5 video al giorno per questo account YouTube.**
                                
                                **Soluzioni:**
                                1. **Cambia account YouTube:** Elimina il file `token.pickle` e riavvia l'app
                                2. **Aspetta domani:** Il limite si resetta ogni giorno
                                3. **Usa un altro account:** Configura un nuovo `client_secrets.json`
                                """)
                                
                                with st.expander("🔧 Come cambiare account YouTube"):
                                    st.markdown("""
                                    ### Per cambiare account YouTube:
                                    
                                    1. **Elimina il token esistente:**
                                       - Trova il file `token.pickle` nella cartella del progetto
                                       - Eliminalo (verrà ricreato automaticamente)
                                    
                                    2. **Configura nuovo account:**
                                       - Scarica un nuovo `client_secrets.json` da Google Cloud Console
                                       - Sostituisci quello esistente
                                    
                                    3. **Riautenticati:**
                                       - Riavvia l'app
                                       - Prova di nuovo l'upload
                                       - Si aprirà il browser per l'autenticazione del nuovo account
                                    """)
                                    
                            elif "authentication" in error_msg or "token" in error_msg:
                                st.warning("🔐 **Problema di autenticazione!**")
                                st.info("""
                                **Il token di accesso è scaduto o non valido.**
                                
                                **Soluzione:**
                                1. Elimina il file `token.pickle`
                                2. Riavvia l'app
                                3. Riprova l'upload (si aprirà il browser per riautenticarti)
                                """)
                                
                            elif "forbidden" in error_msg or "access" in error_msg:
                                st.warning("🚫 **Accesso negato!**")
                                st.info("""
                                **L'account YouTube non ha i permessi necessari.**
                                
                                **Possibili cause:**
                                - L'account non ha abilitato l'upload di video
                                - Le credenziali OAuth2 non sono configurate correttamente
                                - L'API YouTube non è abilitata nel progetto Google Cloud
                                
                                **Soluzione:**
                                1. Verifica la configurazione in Google Cloud Console
                                2. Assicurati che l'API YouTube Data API v3 sia abilitata
                                3. Ricrea le credenziali OAuth2 se necessario
                                """)
                                
                            else:
                                st.info("""
                                **Errore generico durante l'upload.**
                                
                                **Possibili soluzioni:**
                                1. Verifica la connessione internet
                                2. Controlla che il video non sia troppo grande
                                3. Prova a riavviare l'app
                                4. Contatta il supporto se il problema persiste
                                """)

    # Sezione per l'upload su Google Drive
    st.subheader("☁️ Carica su Google Drive")
    
    if st.button("🚀 Carica su Drive"):
        with st.spinner("Caricamento su Google Drive..."):
            drive_link = upload_video_to_drive(
                video_path=st.session_state.processed_video["final_video"],
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
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Salva Transcript Italiano"):
            try:
                # Crea il nome del file
                filename = f"Istruzioni_{selected_video_type}_{selected_apartment}_ita.txt"
                
                # Salva su Google Drive
                from drive_manager import get_drive_service, create_folder_if_not_exists
                
                service = get_drive_service()
                
                # Crea la cartella dell'appartamento se non esiste
                apartment_folder_id = create_folder_if_not_exists(service, selected_apartment)
                
                # Crea la cartella del tipo video se non esiste
                video_type_folder_id = create_folder_if_not_exists(service, selected_video_type, apartment_folder_id)
                
                # Carica il file su Drive
                from googleapiclient.http import MediaIoBaseUpload
                import io
                
                file_metadata = {
                    'name': filename,
                    'parents': [video_type_folder_id]
                }
                
                file_content = io.BytesIO(edited_italian_text.encode('utf-8'))
                media = MediaIoBaseUpload(file_content, mimetype='text/plain', resumable=True)
                
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,webViewLink'
                ).execute()
                
                # Rendi il file pubblico e ottieni il link
                service.permissions().create(
                    fileId=file['id'],
                    body={'type': 'anyone', 'role': 'reader'},
                    fields='id'
                ).execute()
                
                file_link = file['webViewLink']
                
                st.success(f"✅ Transcript italiano salvato su Drive: {filename}")
                st.session_state.italian_transcript_path = file_link
                
            except Exception as e:
                st.error(f"❌ Errore nel salvataggio del transcript italiano: {str(e)}")
    
    with col2:
        if st.button("💾 Salva Transcript Inglese"):
            try:
                # Crea il nome del file
                filename = f"Istruzioni_{selected_video_type}_{selected_apartment}_en.txt"
                
                # Salva su Google Drive
                from drive_manager import get_drive_service, create_folder_if_not_exists
                
                service = get_drive_service()
                
                # Crea la cartella dell'appartamento se non esiste
                apartment_folder_id = create_folder_if_not_exists(service, selected_apartment)
                
                # Crea la cartella del tipo video se non esiste
                video_type_folder_id = create_folder_if_not_exists(service, selected_video_type, apartment_folder_id)
                
                # Carica il file su Drive
                from googleapiclient.http import MediaIoBaseUpload
                import io
                
                file_metadata = {
                    'name': filename,
                    'parents': [video_type_folder_id]
                }
                
                file_content = io.BytesIO(edited_english_text.encode('utf-8'))
                media = MediaIoBaseUpload(file_content, mimetype='text/plain', resumable=True)
                
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,webViewLink'
                ).execute()
                
                # Rendi il file pubblico e ottieni il link
                service.permissions().create(
                    fileId=file['id'],
                    body={'type': 'anyone', 'role': 'reader'},
                    fields='id'
                ).execute()
                
                file_link = file['webViewLink']
                
                st.success(f"✅ Transcript inglese salvato su Drive: {filename}")
                st.session_state.english_transcript_path = file_link
                
            except Exception as e:
                st.error(f"❌ Errore nel salvataggio del transcript inglese: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎬 Video Editor con Sottotitoli Automatici | Powered by OpenAI Whisper & GPT-4</p>
</div>
""", unsafe_allow_html=True) 