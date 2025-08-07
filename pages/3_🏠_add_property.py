"""
Pagina Add Property
Gestisce l'aggiunta e la modifica delle proprietà.
"""
import streamlit as st
import pandas as pd
import logging
from utils import get_data, save_to_sheets, get_apartment_data, clear_api_cache
from pages.subpages.servizi_subpage import render_servizi_subpage
from pages.subpages.appartamenti_subpage import render_appartamenti_subpage
from pages.subpages.wifi_subpage import render_wifi_subpage
from pages.subpages.inventario_subpage import render_inventario_subpage
from pages.subpages.elettrodomestici_subpage import render_elettrodomestici_subpage
from pages.subpages.checkin_subpage import render_checkin_subpage
from pages.subpages.climatizzazione_subpage import render_climatizzazione_subpage
from pages.subpages.utenze_subpage import render_utenze_subpage

# Setup logging
logger = logging.getLogger(__name__)

def main():
    # Configurazione della pagina
    st.set_page_config(
        page_title="🏠 Add Property",
        page_icon="🏠",
        layout="wide"
    )
    
    st.title("Aggiungi Proprietà")
    
    # Pulsante per pulire la cache API
    if st.button("🔄 Pulisci Cache API"):
        clear_api_cache()
        st.success("Cache API pulita! Riprova ora.")
        st.rerun()
    
    # Messaggio di avviso per rate limit
    if st.session_state.get('api_error', False):
        st.warning("⚠️ Rilevato limite API Google Sheets. I dati potrebbero essere dalla cache. Clicca 'Pulisci Cache API' per aggiornare.")
    
    # Get apartment list
    contract_data = get_data("contratti")
    if contract_data is not None and not contract_data.empty:
        apartments = contract_data['appartamento'].dropna().unique().tolist()
        apartments.sort()
    else:
        st.error("❌ Impossibile caricare la lista degli appartamenti. Controlla la connessione a Google Sheets.")
        return
    
    # Apartment selection
    selected_apartment = st.selectbox(
        "Seleziona Appartamento:",
        apartments,
        index=0 if apartments else None
    )
    
    if selected_apartment:
        st.subheader(f"Configurazione per: {selected_apartment}")
            
        # Create tabs for different sections - ORDINE: Appartamento, Inventario, Elettrodomestici, Wi-Fi, Servizi, Check-in, Climatizzazione, Utenze
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(["🏠 Appartamenti", "📦 Inventario", "🔌 Elettrodomestici", "📶 Wi-Fi", "🔧 Servizi", "🏠 Check-in", "❄️ Climatizzazione", "💧 Utenze"])
        
        with tab1:
            render_appartamenti_subpage(selected_apartment)
        
        with tab2:
            render_inventario_subpage(selected_apartment)
        
        with tab3:
            render_elettrodomestici_subpage(selected_apartment)
        
        with tab4:
            render_wifi_subpage(selected_apartment)
        
        with tab5:
            render_servizi_subpage(selected_apartment)
            
        with tab6:
            render_checkin_subpage(selected_apartment)
            
        with tab7:
            render_climatizzazione_subpage(selected_apartment)
            
        with tab8:
            render_utenze_subpage(selected_apartment)

if __name__ == "__main__":
    main() 