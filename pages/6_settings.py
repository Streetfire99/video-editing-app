"""
Settings Page

This page allows users to configure form fields for all sections.
"""

import streamlit as st
import sys
import os

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import get_data, get_form_config, save_to_sheets, save_field_config

import json
import logging
import traceback

logger = logging.getLogger(__name__)

def render_field_config(fields, section_name):
    """Render field configuration UI for a section"""
    st.subheader(f"Configurazione Campi {section_name}")
    
    # Skip the first field (appartamento) as it's always the default
    fields = [f for f in fields if f["name"] != "appartamento"]
    
    # Create header row
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    with col1:
        st.markdown("**Nome Campo**")
    with col2:
        st.markdown("**Tipo**")
    with col3:
        st.markdown("**Configurazione**")
    with col4:
        st.markdown("**Tendina**")
    with col5:
        st.markdown("**Visibile**")
    
    st.markdown("---")
    
    # Create a table-like layout
    for field in fields:
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
        
        with col1:
            name = st.text_input(
                "",
                value=field["name"],
                key=f"{section_name}_{field['name']}_name",
                label_visibility="collapsed"
            )
            field["name"] = name
        
        with col2:
            field_type_options = ["testo", "numero", "foto", "video", "boolean"]
            current_type = field.get("type", "testo")
            if current_type not in field_type_options:
                current_type = "testo" # Default to "testo" if current type is invalid

            field_type = st.selectbox(
                "",
                options=field_type_options,
                index=field_type_options.index(current_type),
                key=f"{section_name}_{field['name']}_type",
                label_visibility="collapsed"
            )
            field["type"] = field_type
        
        with col3:
            if field_type in ["foto", "video"]:
                special_config = st.selectbox(
                    "",
                    options=["Nessuna", "Caricamento Drive", "Editing Video", "Editing e YouTube"],
                    index=0,
                    key=f"{section_name}_{field['name']}_special",
                    label_visibility="collapsed"
                )
                field["special_config"] = special_config
            else:
                st.empty()  # Empty space for non-media fields
        
        with col4:
            dropdown = False
            if field_type == "testo":
                dropdown = st.checkbox(
                    "",
                    value=field.get("dropdown", False),
                    key=f"{section_name}_{field['name']}_dropdown",
                    label_visibility="collapsed"
                )
            field["dropdown"] = dropdown if field_type == "testo" else False
        
        with col5:
            visible = st.checkbox(
                "",
                value=field.get("visible", True),
                key=f"{section_name}_{field['name']}_visible",
                label_visibility="collapsed"
            )
            field["visible"] = visible  # Salva lo stato del checkbox
        
        st.markdown("---")
    
    # Save changes automatically
    if save_field_config(section_name, fields):  # Pass fields list directly
        st.success("Modifiche salvate automaticamente")

def main():
    """Settings page"""
    try:
        logger.info("Starting Settings page")
        
        # Configurazione della pagina
        st.set_page_config(
            page_title="⚙️ Settings",
            page_icon="⚙️",
            layout="wide"
        )
        
        st.title("⚙️ Impostazioni")
        
        # Pulsante per ricaricare configurazioni dal Google Sheet
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 Ricarica da Google Sheet"):
                # Pulisci la cache per forzare il reload
                from utils import clear_api_cache
                clear_api_cache()
                st.success("✅ Configurazioni ricaricate dal Google Sheet!")
                st.rerun()
        
        with col2:
            st.info("💡 Clicca 'Ricarica' per sincronizzare con le colonne del Google Sheet")
        
        # Create tabs for different sections
        tabs = st.tabs([
            "📄 Contratti",
            "👥 Contatti",
            "👤 Proprietari",
            "🏢 Appartamenti",
            "🔌 Elettrodomestici",
            "📋 Inventario",
            "💡 Utenze",
            "🔑 Check-in",
            "📶 Wi-Fi",
            "❄️ Climatizzazione",
            "🔧 Servizi"
        ])
        
        # Dictionary to store all configurations
        config = {}
        
        # Contratti Tab
        with tabs[0]:
            contratti_config = get_form_config("contratti")
            if contratti_config:
                render_field_config(contratti_config["fields"], "contratti")
                config["contratti"] = contratti_config
            else:
                st.error("Errore nel caricamento della configurazione dei contratti")
        
        # Contatti Tab
        with tabs[1]:
            contatti_config = get_form_config("contatti")
            if contatti_config:
                render_field_config(contatti_config["fields"], "contatti")
                config["contatti"] = contatti_config
            else:
                st.error("Errore nel caricamento della configurazione dei contatti")
        
        # Proprietari Tab
        with tabs[2]:
            proprietari_config = get_form_config("proprietari")
            if proprietari_config:
                render_field_config(proprietari_config["fields"], "proprietari")
                config["proprietari"] = proprietari_config
            else:
                st.error("Errore nel caricamento della configurazione dei proprietari")
        
        # Appartamenti Tab
        with tabs[3]:
            appartamenti_config = get_form_config("appartamenti")
            if appartamenti_config:
                render_field_config(appartamenti_config["fields"], "appartamenti")
                config["appartamenti"] = appartamenti_config
            else:
                st.error("Errore nel caricamento della configurazione degli appartamenti")
        
        # Elettrodomestici Tab
        with tabs[4]:
            elettrodomestici_config = get_form_config("elettrodomestici")
            if elettrodomestici_config:
                render_field_config(elettrodomestici_config["fields"], "elettrodomestici")
                config["elettrodomestici"] = elettrodomestici_config
            else:
                st.error("Errore nel caricamento della configurazione degli elettrodomestici")
        
        # Inventario Tab
        with tabs[5]:
            inventario_config = get_form_config("inventario")
            if inventario_config:
                render_field_config(inventario_config["fields"], "inventario")
                config["inventario"] = inventario_config
            else:
                st.error("Errore nel caricamento della configurazione dell'inventario")
        
        # Utenze Tab
        with tabs[6]:
            utenze_config = get_form_config("utenze")
            if utenze_config:
                render_field_config(utenze_config["fields"], "utenze")
                config["utenze"] = utenze_config
            else:
                st.error("Errore nel caricamento della configurazione delle utenze")
        
        # Check-in Tab
        with tabs[7]:
            checkin_config = get_form_config("check-in")
            if checkin_config:
                render_field_config(checkin_config["fields"], "check-in")
                config["check-in"] = checkin_config
            else:
                st.error("Errore nel caricamento della configurazione del check-in")
        
        # Wi-Fi Tab
        with tabs[8]:
            wifi_config = get_form_config("wi-fi")
            if wifi_config:
                render_field_config(wifi_config["fields"], "wi-fi")
                config["wi-fi"] = wifi_config
            else:
                st.error("Errore nel caricamento della configurazione del Wi-Fi")
        
        # Climatizzazione Tab
        with tabs[9]:
            climatizzazione_config = get_form_config("climatizzazione")
            if climatizzazione_config:
                render_field_config(climatizzazione_config["fields"], "climatizzazione")
                config["climatizzazione"] = climatizzazione_config
            else:
                st.error("Errore nel caricamento della configurazione della climatizzazione")
        
        # Servizi Tab
        with tabs[10]:
            servizi_config = get_form_config("servizi")
            if servizi_config:
                render_field_config(servizi_config["fields"], "servizi")
                config["servizi"] = servizi_config
            else:
                st.error("Errore nel caricamento della configurazione dei servizi")
        
        # Save button at the bottom
        st.markdown("---")
        if st.button("💾 Salva Configurazione", use_container_width=True):
            try:
                with open("form_config.json", "w") as f:
                    json.dump(config, f, indent=4)
                st.success("Configurazione salvata con successo!")
            except Exception as e:
                st.error(f"Errore nel salvataggio della configurazione: {str(e)}")
                
    except Exception as e:
        logger.error(f"Unexpected error in main function: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        st.error("Si è verificato un errore imprevisto. Controlla i log per maggiori dettagli.")

if __name__ == "__main__":
    main() 