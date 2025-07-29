import streamlit as st
import sys
import os

# Aggiungi il percorso per importare i moduli
sys.path.append('..')
from data_manager import load_apartments, get_video_types

# Configurazione della pagina
st.set_page_config(
    page_title="📹 Editing Video",
    page_icon="📹",
    layout="wide"
)

# Barra di navigazione
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("🏠 Home"):
        st.switch_page("Home.py")
with col2:
    st.markdown("### 📹 Editing Video")
with col3:
    if st.button("🏢 Appartamenti"):
        st.switch_page("pages/1_🏠_Appartamenti.py")

st.markdown("---")

# Controlla se è stato selezionato un appartamento
selected_apartment = st.session_state.get('selected_apartment', None)

if not selected_apartment:
    st.warning("⚠️ Nessun appartamento selezionato")
    st.info("Vai alla pagina Appartamenti per selezionare un appartamento")
    if st.button("🏢 Vai agli Appartamenti"):
        st.switch_page("pages/1_🏠_Appartamenti.py")
    st.stop()

# Mostra l'appartamento selezionato
st.success(f"🏢 Appartamento selezionato: **{selected_apartment}**")

# Carica gli appartamenti e le tipologie
apartments = load_apartments()
video_types = get_video_types()

# Sezione di selezione
st.header("📋 Configurazione Video")

col1, col2 = st.columns(2)

with col1:
    # Selezione appartamento (pre-selezionato)
    selected_apartment = st.selectbox(
        "🏠 Appartamento",
        options=apartments,
        index=apartments.index(selected_apartment) if selected_apartment in apartments else 0,
        help="Scegli l'appartamento per cui stai creando il video"
    )

with col2:
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

# Importa e usa il resto del codice dell'app originale
# (Qui andrebbe il resto del codice di app.py, ma semplificato per questa pagina)

st.markdown("---")
st.header("📤 Carica Video")

# Upload del video
uploaded_video = st.file_uploader(
    "Scegli un file video",
    type=['mp4', 'avi', 'mov', 'mkv'],
    help="Formati supportati: MP4, AVI, MOV, MKV"
)

if uploaded_video is not None:
    st.success("✅ Video caricato!")
    st.info("🚧 Funzionalità di elaborazione in sviluppo...")
    
    # Pulsante per elaborare (placeholder)
    if st.button("🎬 Elabora Video"):
        st.info("🚧 Funzionalità di elaborazione in sviluppo...")

# Pulsanti di navigazione in fondo
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🏠 Torna alla Home"):
        st.switch_page("Home.py")
with col2:
    if st.button("🏢 Torna agli Appartamenti"):
        st.switch_page("pages/1_🏠_Appartamenti.py")
with col3:
    st.info("📹 Editing Video") 