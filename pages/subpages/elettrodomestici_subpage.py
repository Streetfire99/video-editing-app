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
        df = pd.DataFrame(columns=["appartamento", "nome_elettrodomestico", "modello", "marca_serial", "anno", "posizione", "descrizione", "url_video"])
    
    # Filtra per appartamento selezionato
    existing_appliances = df[df["appartamento"] == selected_apartment]
    
    # Filtra le righe che hanno un nome_elettrodomestico valido (non vuoto)
    existing_appliances = existing_appliances[
        existing_appliances["nome_elettrodomestico"].notna() & 
        (existing_appliances["nome_elettrodomestico"].str.strip() != "")
    ]
    
    # Mostra info sui dati esistenti
    if not existing_appliances.empty:
        st.info(f"📋 Trovati {len(existing_appliances)} elettrodomestici per {selected_apartment}")
        existing_list = existing_appliances["nome_elettrodomestico"].dropna().tolist()
        if existing_list:
            st.write(f"**Elettrodomestici esistenti:** {', '.join(existing_list)}")
    
    # Crea un dizionario per mappare nome -> dati esistenti
    existing_data_dict = {}
    for _, row in existing_appliances.iterrows():
        appliance_name = row.get("nome_elettrodomestico", "")
        if appliance_name and appliance_name.strip():
            existing_data_dict[appliance_name] = row
    
    # Mostra tutti gli elettrodomestici (esistenti + standard mancanti)
    st.markdown("### Elettrodomestici:")
    
    # Prima mostra gli elettrodomestici esistenti
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
                marca_serial = st.text_input(
                    "Marca/Serial", 
                    value=existing_data.get("marca_serial", ""), 
                    key=f"marca_serial_{appliance_name}_{selected_apartment}"
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
            
            # Gestione video
            st.markdown("#### Video Tutorial")
            existing_video_url = existing_data.get("url_video", "")
            if existing_video_url:
                st.markdown(f"**Video già presente:** [Guarda video]({existing_video_url})")
                if existing_video_url.endswith(('.mp4', '.mov')):
                    st.video(existing_video_url)
            nuovo_video = st.file_uploader(
                "Carica nuovo video (opzionale)", 
                type=["mp4", "mov"], 
                key=f"video_upload_{appliance_name}_{selected_apartment}"
            )
            if nuovo_video:
                video_url = upload_file_to_drive(nuovo_video, selected_apartment, f"Tutorial {appliance_name}")
                st.success(f"Video caricato per {appliance_name}!")
                st.video(nuovo_video)
            
            # Pulsante per salvare questo elettrodomestico
            if st.button(f"💾 Salva {appliance_name}", key=f"save_{appliance_name}_{selected_apartment}"):
                data_to_save = {
                    "appartamento": selected_apartment,
                    "nome_elettrodomestico": appliance_name,
                    "modello": modello,
                    "marca_serial": marca_serial,
                    "anno": anno,
                    "posizione": posizione,
                    "descrizione": descrizione,
                    "url_video": existing_video_url
                }
                save_to_sheets("elettrodomestici", data_to_save)
                st.success(f"✅ {appliance_name} salvato con successo!")
    
    # Poi mostra gli elettrodomestici standard che NON esistono ancora
    # Normalizza i nomi per il confronto (case insensitive)
    existing_names_normalized = [name.lower().strip() for name in existing_data_dict.keys()]
    
    missing_standard_appliances = []
    for appliance_name in standard_appliances:
        if appliance_name.lower().strip() not in existing_names_normalized:
            missing_standard_appliances.append(appliance_name)
    
    if missing_standard_appliances:
        st.markdown("### Elettrodomestici standard disponibili:")
        
        for appliance_name in missing_standard_appliances:
            with st.expander(f"🔧 {appliance_name}", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    modello = st.text_input(
                        "Modello", 
                        value="", 
                        key=f"modello_{appliance_name}_{selected_apartment}"
                    )
                    marca_serial = st.text_input(
                        "Marca/Serial", 
                        value="", 
                        key=f"marca_serial_{appliance_name}_{selected_apartment}"
                    )
                    anno = st.text_input(
                        "Anno", 
                        value="", 
                        key=f"anno_{appliance_name}_{selected_apartment}"
                    )
                
                with col2:
                    posizione = st.text_input(
                        "Posizione", 
                        value="", 
                        key=f"posizione_{appliance_name}_{selected_apartment}"
                    )
                
                descrizione = st.text_area(
                    "Descrizione", 
                    value="", 
                    key=f"descrizione_{appliance_name}_{selected_apartment}"
                )
                
                # Gestione video
                st.markdown("#### Video Tutorial")
                
                nuovo_video = st.file_uploader(
                    "Carica nuovo video (opzionale)", 
                    type=["mp4", "mov"], 
                    key=f"video_upload_{appliance_name}_{selected_apartment}"
                )
                
                if nuovo_video:
                    video_url = upload_file_to_drive(nuovo_video, selected_apartment, f"Tutorial {appliance_name}")
                    st.success(f"Video caricato per {appliance_name}!")
                    st.video(nuovo_video)
                
                # Pulsante per salvare questo elettrodomestico
                if st.button(f"💾 Salva {appliance_name}", key=f"save_{appliance_name}_{selected_apartment}"):
                    data_to_save = {
            "appartamento": selected_apartment,
                        "nome_elettrodomestico": appliance_name,
            "modello": modello,
            "marca_serial": marca_serial,
            "anno": anno,
            "posizione": posizione,
            "descrizione": descrizione,
                        "url_video": ""
                    }
                    save_to_sheets("elettrodomestici", data_to_save)
                    st.success(f"✅ {appliance_name} salvato con successo!")
    
    # Sezione per aggiungere nuovi elettrodomestici
    st.markdown("---")
    st.markdown("### Aggiungi nuovo elettrodomestico")
    
    nuovo_nome = st.text_input("Nome elettrodomestico", key="nuovo_elettro_nome")
    
    if st.button("Aggiungi elettrodomestico", key="aggiungi_elettro"):
        if nuovo_nome and nuovo_nome.strip():
            # Verifica se esiste già
            existing_names = existing_appliances["nome_elettrodomestico"].tolist()
            if nuovo_nome.strip() in existing_names:
                st.error(f"L'elettrodomestico '{nuovo_nome}' esiste già!")
            else:
                # Salva il nuovo elettrodomestico vuoto
                data_to_save = {
                    "appartamento": selected_apartment,
                    "nome_elettrodomestico": nuovo_nome.strip(),
                    "modello": "",
                    "marca_serial": "",
                    "anno": "",
                    "posizione": "",
                    "descrizione": "",
                    "url_video": ""
                }
                save_to_sheets("elettrodomestici", data_to_save)
                st.success(f"✅ Elettrodomestico '{nuovo_nome}' aggiunto! Ricarica la pagina per vederlo.")
                st.rerun() 