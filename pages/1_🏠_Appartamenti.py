import streamlit as st
import sys
import os

# Aggiungi il percorso per importare i moduli
sys.path.append('..')
from data_manager import load_apartments
from drive_manager import get_processed_apartments

# Configurazione della pagina
st.set_page_config(
    page_title="🏠 Appartamenti",
    page_icon="🏠",
    layout="wide"
)

# Titolo della pagina
st.title("🏠 Appartamenti")

# Pulsanti di navigazione
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🏠 Home"):
        st.switch_page("Home.py")

# Carica appartamenti elaborati
processed_apartments = get_processed_apartments()

if not processed_apartments:
    st.info("📝 Nessun appartamento elaborato ancora. Vai alla pagina di editing per iniziare!")
else:
    st.subheader("📋 Appartamenti con video elaborati")
    
    # Dizionario delle emoji per le tipologie
    video_type_icons = {
        'spazzatura': '🗑️',
        'caldaia': '🔥',
        'forno': '🍕',
        'frigorifero': '❄️',
        'lavatrice': '👕',
        'piano_cottura': '🍳',
        'scaldabagno': '🚿',
        'lavastoviglie': '🍽️',
        'microonde': '⚡',
        'asciugatrice': '🌬️',
        'riscaldamento': '🌡️',
        'condizionamento': '❄️',
        'check-in': '🔑'
    }
    
    # Mostra appartamenti elaborati con solo emoji
    for apartment, video_types in processed_apartments.items():
        with st.container():
            col1, col2, col3 = st.columns([2, 3, 1])
            
            with col1:
                st.write(f"**{apartment}**")
            
            with col2:
                # Mostra solo emoji per le tipologie di video
                icons_text = " ".join([video_type_icons.get(vt, '📹') for vt in video_types])
                st.write(icons_text)
            
            with col3:
                # Pulsante per andare alla pagina dei dettagli dell'appartamento
                if st.button(f"📋 Gestisci", key=f"btn_{apartment}"):
                    st.session_state.selected_apartment = apartment
                    st.switch_page("pages/📋_Dettagli_Appartamento.py") 