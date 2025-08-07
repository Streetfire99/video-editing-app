"""
Subpage Elettrodomestici
Gestisce la logica e il rendering della sezione elettrodomestici per add_property.
"""
import streamlit as st
import pandas as pd
from utils import get_data, save_to_sheets, upload_file_to_drive, get_apartment_data

try:
    from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
    webrtc_available = True
except ImportError:
    webrtc_available = False

def render_elettrodomestici_subpage(selected_apartment):
    # Lista degli elettrodomestici standard
    standard_appliances = [
        "Caldaia", "Microonde", "Piano cottura", "Asciugatrice", "Forno", 
        "Lavastoviglie", "Scaldabagno", "Frigorifero", "Lavatrice"
    ]
    
    st.markdown("#### Gestione Elettrodomestici")
    
    # Carica tutti gli elettrodomestici dal foglio
    df = get_data("elettrodomestici")
    if df is None or df.empty:
        df = pd.DataFrame(columns=["appartamento", "tipologia", "modello", "marca", "anno", "posizione", "descrizione", "descrizione_problemi", "foto"])
    
    # Verifica se la colonna appartamento esiste
    if "appartamento" not in df.columns:
        st.warning("⚠️ Colonna 'appartamento' non trovata. Verificare la struttura del foglio Google Sheets.")
        existing_appliances = pd.DataFrame(columns=["appartamento", "tipologia", "modello", "marca", "anno", "posizione", "descrizione", "descrizione_problemi", "foto"])
    else:
        # Filtra per appartamento selezionato
        existing_appliances = df[df["appartamento"] == selected_apartment]
    
    # Verifica se la colonna tipologia esiste (nome_elettrodomestico nel foglio)
    if "tipologia" not in existing_appliances.columns:
        st.warning("⚠️ Colonna 'tipologia' non trovata. Verificare la struttura del foglio Google Sheets.")
        existing_appliances = pd.DataFrame(columns=["appartamento", "tipologia", "modello", "marca", "anno", "posizione", "descrizione", "descrizione_problemi", "foto"])
    else:
        # Filtra le righe che hanno una tipologia valida (non vuota)
        existing_appliances = existing_appliances[
            existing_appliances["tipologia"].notna() & 
            (existing_appliances["tipologia"].str.strip() != "")
        ]
    
    # Mostra info sui dati esistenti
    if not existing_appliances.empty:
        st.info(f"📋 Trovati {len(existing_appliances)} elettrodomestici per {selected_apartment}")
        existing_list = existing_appliances["tipologia"].dropna().tolist()
        if existing_list:
            st.write(f"**Elettrodomestici esistenti:** {', '.join(existing_list)}")
    
    # Crea un dizionario per mappare nome -> dati esistenti
    existing_data_dict = {}
    for _, row in existing_appliances.iterrows():
        appliance_name = row.get("tipologia", "")
        if appliance_name and appliance_name.strip():
            existing_data_dict[appliance_name] = row
    
    # Ottieni tutte le tipologie esistenti (dal foglio + standard)
    all_tipologie = list(existing_data_dict.keys()) + standard_appliances
    all_tipologie = list(set(all_tipologie))  # Rimuovi duplicati
    all_tipologie.sort()
    
    # Sezione per aggiungere nuovo elettrodomestico
    st.markdown("### ➕ Aggiungi Nuovo Elettrodomestico")
    
    col1, col2 = st.columns(2)
    with col1:
        # Menu a discesa per tipologie esistenti
        selected_tipologia = st.selectbox(
            "Seleziona Tipologia",
            options=all_tipologie + ["➕ Aggiungi nuova tipologia"],
            key="new_appliance_type"
        )
    
    with col2:
        # Campo per nuova tipologia se selezionato
        if selected_tipologia == "➕ Aggiungi nuova tipologia":
            new_tipologia = st.text_input("Nuova Tipologia", key="new_tipologia_input")
            if new_tipologia:
                selected_tipologia = new_tipologia
    
    # Form per nuovo elettrodomestico
    if selected_tipologia and selected_tipologia != "➕ Aggiungi nuova tipologia":
        st.markdown(f"#### 🔧 {selected_tipologia}")
        
        col1, col2 = st.columns(2)
        with col1:
            nuovo_modello = st.text_input("Modello", key=f"nuovo_modello_{selected_tipologia}")
            nuova_marca = st.text_input("Marca", key=f"nuova_marca_{selected_tipologia}")
            nuovo_anno = st.text_input("Anno", key=f"nuovo_anno_{selected_tipologia}")
        
        with col2:
            nuova_posizione = st.text_input("Posizione", key=f"nuova_posizione_{selected_tipologia}")
        
        nuova_descrizione = st.text_area("Descrizione", key=f"nuova_descrizione_{selected_tipologia}")
        nuova_descrizione_problemi = st.text_area("Descrizione Problemi", key=f"nuova_descrizione_problemi_{selected_tipologia}")
        
        # Gestione foto per nuovo elettrodomestico
        st.markdown("#### 📸 Foto")
        
        # Inizializza nuovo_foto
        nuovo_foto = None
        
        # Opzioni per foto: upload o scatta
        foto_option = st.radio(
            "Scegli opzione foto:",
            ["📁 Carica foto", "📷 Scatta foto"],
            key=f"nuovo_foto_option_{selected_tipologia}"
        )
        
        if foto_option == "📁 Carica foto":
            nuovo_foto = st.file_uploader(
                "Carica foto (opzionale)", 
                type=["jpg", "jpeg", "png"], 
                key=f"nuovo_foto_upload_{selected_tipologia}"
            )
            if nuovo_foto:
                st.image(nuovo_foto, caption=f"Foto {selected_tipologia}")
        else:
            # Scatta foto con webcam
            nuovo_foto = st.camera_input(
                f"Scatta foto per {selected_tipologia}",
                key=f"nuovo_camera_{selected_tipologia}"
            )
            if nuovo_foto:
                st.image(nuovo_foto, caption=f"Foto {selected_tipologia}")
        
        # Pulsante per salvare nuovo elettrodomestico
        if st.button(f"💾 Salva Nuovo {selected_tipologia}", key=f"save_new_{selected_tipologia}"):
            # Gestisce la foto
            foto_url = ""
            if nuovo_foto:
                foto_url = upload_file_to_drive(nuovo_foto, selected_apartment, f"Foto {selected_tipologia}")
            
            data_to_save = {
                "appartamento": selected_apartment,
                "tipologia": selected_tipologia,
                "modello": nuovo_modello,
                "marca": nuova_marca,
                "anno": nuovo_anno,
                "posizione": nuova_posizione,
                "descrizione": nuova_descrizione,
                "descrizione_problemi": nuova_descrizione_problemi,
                "foto": foto_url
            }
            save_to_sheets("elettrodomestici", data_to_save)
            st.success(f"✅ Nuovo {selected_tipologia} salvato con successo!")
            st.rerun()
    
    # Sezione per elettrodomestici esistenti
    if existing_data_dict:
        st.markdown("### 🔧 Elettrodomestici Esistenti")
        
        for appliance_name in existing_data_dict.keys():
            existing_data = existing_data_dict[appliance_name]
            
            with st.expander(f"🔧 {appliance_name}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    modello = st.text_input(
                        "Modello", 
                        value=existing_data.get("modello", ""), 
                        key=f"modello_{appliance_name}_{selected_apartment}"
                    )
                    marca = st.text_input(
                        "Marca", 
                        value=existing_data.get("marca", ""), 
                        key=f"marca_{appliance_name}_{selected_apartment}"
                    )
                    anno = st.text_input(
                        "Anno", 
                        value=existing_data.get("anno", ""), 
                        key=f"anno_{appliance_name}_{selected_apartment}"
                    )
                
                with col2:
                    posizione = st.text_input(
                        "Posizione", 
                        value=existing_data.get("posizione", ""), 
                        key=f"posizione_{appliance_name}_{selected_apartment}"
                    )
                
                descrizione = st.text_area(
                    "Descrizione", 
                    value=existing_data.get("descrizione", ""), 
                    key=f"descrizione_{appliance_name}_{selected_apartment}"
                )
                
                descrizione_problemi = st.text_area(
                    "Descrizione Problemi", 
                    value=existing_data.get("descrizione_problemi", ""), 
                    key=f"descrizione_problemi_{appliance_name}_{selected_apartment}"
                )
                
                # Gestione foto
                st.markdown("#### 📸 Foto")
                existing_foto = existing_data.get("foto", "")
                if existing_foto:
                    st.markdown(f"**Foto già presente:** [Vedi foto]({existing_foto})")
                
                # Inizializza nuovo_foto
                nuovo_foto = None
                
                # Opzioni per foto: upload o scatta
                foto_option = st.radio(
                    "Scegli opzione foto:",
                    ["📁 Carica foto", "📷 Scatta foto"],
                    key=f"foto_option_{appliance_name}_{selected_apartment}"
                )
                
                if foto_option == "📁 Carica foto":
                    nuovo_foto = st.file_uploader(
                        "Carica nuova foto (opzionale)", 
                        type=["jpg", "jpeg", "png"], 
                        key=f"foto_upload_{appliance_name}_{selected_apartment}"
                    )
                    if nuovo_foto:
                        st.success(f"Foto selezionata per {appliance_name}!")
                        st.image(nuovo_foto, caption=f"Foto {appliance_name}")
                else:
                    # Scatta foto con webcam
                    nuovo_foto = st.camera_input(
                        f"Scatta foto per {appliance_name}",
                        key=f"camera_{appliance_name}_{selected_apartment}"
                    )
                    if nuovo_foto:
                        st.success(f"Foto scattata per {appliance_name}!")
                        st.image(nuovo_foto, caption=f"Foto {appliance_name}")
                
                # Pulsante per salvare questo elettrodomestico
                if st.button(f"💾 Salva {appliance_name}", key=f"save_{appliance_name}_{selected_apartment}"):
                    # Gestisce la foto (nuova o esistente)
                    foto_url = existing_data.get("foto", "")
                    if nuovo_foto:
                        foto_url = upload_file_to_drive(nuovo_foto, selected_apartment, f"Foto {appliance_name}")
                    
                    data_to_save = {
                        "appartamento": selected_apartment,
                        "tipologia": appliance_name,
                        "modello": modello,
                        "marca": marca,
                        "anno": anno,
                        "posizione": posizione,
                        "descrizione": descrizione,
                        "descrizione_problemi": descrizione_problemi,
                        "foto": foto_url
                    }
                    save_to_sheets("elettrodomestici", data_to_save)
                    st.success(f"✅ {appliance_name} salvato con successo!")
    
    # Fine della funzione 