"""
Subpage Wi-Fi
Gestisce la logica e il rendering della sezione Wi-Fi per add_property.
"""
import streamlit as st
import pandas as pd
import csv
import os
import logging
from utils import get_apartment_data, save_to_sheets

# Setup logging
logger = logging.getLogger(__name__)

def render_wifi_subpage(selected_apartment):
    """Rende la subpage Wi-Fi con caching dei dati per evitare chiamate API ripetute."""
    logger.info(f"Rendering Wi-Fi subpage for apartment: {selected_apartment}")
    
    st.header("🌐 Configurazione Wi-Fi")
    
    config_file = "field_configs/wi-fi.csv"
    if not os.path.exists(config_file):
        st.error(f"File di configurazione {config_file} non trovato")
        return
    
    fields = []
    with open(config_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('visible', 'True').lower() == 'true':
                fields.append(row)
    
    if 'wifi_existing_data' not in st.session_state or st.session_state.get('wifi_apartment_name') != selected_apartment:
        with st.spinner(f"Caricamento dati per {selected_apartment}..."):
            st.session_state.wifi_existing_data = get_apartment_data("wi-fi", selected_apartment)
            st.session_state.wifi_apartment_name = selected_apartment
            st.session_state.wifi_fields = st.session_state.wifi_existing_data.copy()

    existing_data = st.session_state.get('wifi_existing_data', {})
    
    if 'wifi_fields' not in st.session_state:
        st.session_state.wifi_fields = existing_data.copy()
    
    st.subheader("📝 Campi Wi-Fi")
    
    for field in fields:
        field_name = field['name']
        field_label = field['label']
        field_type = field['type']
        
        current_value = st.session_state.wifi_fields.get(field_name, existing_data.get(field_name, ''))
        
        widget_key = f"wifi_{field_name}"
        
        if field_type == 'text':
            value = st.text_input(label=field_label, value=current_value, key=widget_key, help=f"Campo: {field_name}")
        elif field_type == 'number':
            try:
                num_value = float(current_value) if current_value else 0.0
            except (ValueError, TypeError):
                num_value = 0.0
            value = st.number_input(label=field_label, value=num_value, key=widget_key, help=f"Campo: {field_name}")
        elif field_type == 'boolean':
            bool_value = bool(current_value) if current_value else False
            value = st.checkbox(label=field_label, value=bool_value, key=widget_key, help=f"Campo: {field_name}")
        else:
            value = st.text_input(label=field_label, value=current_value, key=widget_key, help=f"Campo: {field_name}")
        
        st.session_state.wifi_fields[field_name] = value
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Salva Dati Wi-Fi", type="primary"):
            try:
                data_to_save = {}
                for field in fields:
                    field_name = field['name']
                    data_to_save[field_name] = st.session_state.wifi_fields.get(field_name, '')
                
                data_to_save['appartamento'] = selected_apartment
                
                success = save_to_sheets("wi-fi", [data_to_save])
                
                if success:
                    st.success("✅ Dati Wi-Fi salvati con successo!")
                    logger.info(f"Wi-Fi data saved for apartment: {selected_apartment}")
                else:
                    st.error("❌ Errore durante il salvataggio")
                    
            except Exception as e:
                st.error(f"❌ Errore: {e}")
                logger.error(f"Error saving Wi-Fi data: {e}")
    
    with col2:
        if st.button("🔄 Reset Campi"):
            st.session_state.wifi_fields = {}
            st.rerun() 