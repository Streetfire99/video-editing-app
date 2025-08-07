import streamlit as st
import sys
import os

# Configurazione della pagina
st.set_page_config(
    page_title="🎬 Elaborazione Video",
    page_icon="🎬",
    layout="wide"
)

# Titolo principale
st.title("🎬 Elaborazione Video")
st.markdown("Sistema di elaborazione video con sottotitoli automatici per database tutorial")

# Statistiche principali
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("🏢 Appartamenti", "12", "2 nuovi")
    
with col2:
    st.metric("📹 Video Editati", "45", "5 questa settimana")
    
with col3:
    st.metric("🎥 Tipologie", "13", "2 aggiunte")
    
with col4:
    st.metric("📺 YouTube", "38", "3 caricati")

st.markdown("---")

# Sezioni principali
col1, col2 = st.columns(2)

with col1:
    st.header("🏢 Gestione Appartamenti")
    st.markdown("""
    - **Visualizza** tutti gli appartamenti
    - **Seleziona** un appartamento per editing
    - **Gestisci** video per appartamento specifico
    """)
    
    if st.button("🏢 Vai agli Appartamenti", type="primary"):
        st.switch_page("pages/1_📚_Database_Tutorial.py")

with col2:
    st.header("📹 Editing Video")
    st.markdown("""
    - **Carica** video da elaborare
    - **Seleziona** appartamento e tipologia
    - **Elabora** con sottotitoli automatici
    - **Carica** su YouTube
    """)
    
    if st.button("📹 Inizia Editing", type="primary"):
        st.switch_page("app.py")

st.markdown("---")

# Funzionalità recenti
st.header("🆕 Funzionalità Recenti")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 🎯 Prompt Personalizzati
    - Prompt specifici per ogni tipologia
    - Traduzioni ottimizzate
    - Modifiche personalizzate
    """)

with col2:
    st.markdown("""
    ### 📺 Upload YouTube
    - Caricamento diretto su YouTube
    - Gestione privacy (private/unlisted/public)
    - Titoli automatici
    """)

with col3:
    st.markdown("""
    ### 🏢 Gestione Appartamenti
    - Caricamento da Google Sheets
    - Navigazione tra appartamenti
    - Statistiche per appartamento
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎬 Editing Video System v2.0</p>
    <p>Powered by Streamlit, OpenAI, and YouTube API</p>
</div>
""", unsafe_allow_html=True) 