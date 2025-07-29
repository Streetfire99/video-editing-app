import streamlit as st
import sys
import os
import pandas as pd

# Aggiungi il percorso per importare i moduli
sys.path.append('..')
from drive_manager import load_tracking_csv

# Configurazione della pagina
st.set_page_config(
    page_title="📋 Dettagli Appartamento",
    page_icon="📋",
    layout="wide"
)

# Controlla se è stato selezionato un appartamento
if 'selected_apartment' not in st.session_state:
    st.error("❌ Nessun appartamento selezionato!")
    if st.button("🏠 Torna agli Appartamenti"):
        st.switch_page("pages/1_🏠_Appartamenti.py")
    st.stop()

selected_apartment = st.session_state.selected_apartment

# Titolo della pagina
st.title(f"📋 Dettagli: {selected_apartment}")

# Pulsanti di navigazione
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🏠 Home"):
        st.switch_page("Home.py")
with col2:
    if st.button("📋 Torna agli Appartamenti"):
        st.switch_page("pages/1_🏠_Appartamenti.py")

# Carica i dati di tracking
tracking_data = load_tracking_csv()

# Filtra i dati per l'appartamento selezionato
apartment_data = [entry for entry in tracking_data if entry['apartment'] == selected_apartment]

if not apartment_data:
    st.info(f"📝 Nessun video elaborato per {selected_apartment}.")
else:
    st.subheader(f"🎬 Video elaborati per {selected_apartment}")
    
    # Crea una tabella con i dati
    table_data = []
    for entry in apartment_data:
        table_data.append({
            'Tipologia': entry['video_type'],
            'Drive': entry['drive_link'] if entry['drive_link'] else 'N/A',
            'YouTube': entry['youtube_link'] if entry['youtube_link'] else 'N/A'
        })
    
    # Mostra la tabella
    df = pd.DataFrame(table_data)
    
    # Funzione per creare link cliccabili
    def make_clickable(url):
        if url and url != 'N/A':
            return f'<a href="{url}" target="_blank">🔗 Link</a>'
        return 'N/A'
    
    # Applica la funzione ai link
    df['Drive'] = df['Drive'].apply(make_clickable)
    df['YouTube'] = df['YouTube'].apply(make_clickable)
    
    # Mostra la tabella con HTML
    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True) 