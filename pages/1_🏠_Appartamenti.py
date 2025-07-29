import streamlit as st
import sys
import os

# Aggiungi il percorso per importare i moduli
sys.path.append('..')
from data_manager import load_apartments

# Configurazione della pagina
st.set_page_config(
    page_title="🏠 Appartamenti - Editing Video",
    page_icon="🏠",
    layout="wide"
)

# Titolo della pagina
st.title("🏠 Appartamenti")
st.markdown("Seleziona un appartamento per vedere i video editati o crearne di nuovi")

# Carica gli appartamenti
apartments = load_apartments()

if not apartments:
    st.warning("⚠️ Nessun appartamento trovato")
    st.info("📋 Gli appartamenti vengono caricati dal Google Sheets. Verifica la connessione.")
else:
    # Mostra gli appartamenti in una griglia
    cols = st.columns(3)
    
    for i, apartment in enumerate(apartments):
        col = cols[i % 3]
        
        with col:
            st.markdown(f"""
            ### 🏢 {apartment}
            
            **Video editati:** 0
            
            **Tipologie disponibili:**
            - 🗑️ Spazzatura
            - 🔥 Caldaia
            - 🧺 Lavatrice
            - 🍳 Piano cottura
            
            ---
            """)
            
            # Pulsante per andare alla pagina dell'appartamento
            if st.button(f"📋 Gestisci {apartment}", key=f"btn_{apartment}"):
                st.session_state.selected_apartment = apartment
                st.switch_page("pages/2_📹_Editing_Video.py")

# Pulsante per tornare alla pagina principale
st.markdown("---")
if st.button("🏠 Torna alla Home"):
    st.switch_page("Home.py") 