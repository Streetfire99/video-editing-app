"""
Subpage Check-in
Gestisce la logica e il rendering della sezione check-in per add_property.
"""
import streamlit as st
import pandas as pd
from utils import get_data, save_to_sheets, upload_file_to_drive, get_apartment_data

def render_checkin_subpage(selected_apartment, existing_data=None):
    # Carica i dati del check-in per l'appartamento
    existing_data = get_apartment_data("check-in", selected_apartment)
    
    st.markdown("#### Gestione Check-in")
    
    # Informazioni base
    st.markdown("### Informazioni Base")
    col1, col2 = st.columns(2)
    with col1:
        lat = st.text_input("Latitudine", value=existing_data.get("lat", ""), key=f"lat_{selected_apartment}")
        long = st.text_input("Longitudine", value=existing_data.get("long", ""), key=f"long_{selected_apartment}")
        cap = st.text_input("CAP", value=existing_data.get("cap", ""), key=f"cap_{selected_apartment}")
        citofono = st.text_input("Citofono", value=existing_data.get("citofono", ""), key=f"citofono_{selected_apartment}")
    
    with col2:
        codice = st.text_input("Codice", value=existing_data.get("codice", ""), key=f"codice_{selected_apartment}")
        video = st.text_input("Video", value=existing_data.get("video", ""), key=f"video_{selected_apartment}")
        dispositivo_installato = st.text_input("Dispositivo Installato", value=existing_data.get("dispositivo_installato", ""), key=f"dispositivo_{selected_apartment}")
        shelly_id = st.text_input("Shelly ID", value=existing_data.get("shelly_id", ""), key=f"shelly_{selected_apartment}")
    
    # Gestione chiavi
    st.markdown("### Gestione Chiavi")
    col1, col2 = st.columns(2)
    with col1:
        chiavi_consegna_metodo = st.text_input("Chiavi - Metodo Consegna", value=existing_data.get("chiavi_consegna_metodo", ""), key=f"chiavi_consegna_{selected_apartment}")
        chiavi_deposito = st.text_input("Chiavi - Deposito", value=existing_data.get("chiavi_deposito", ""), key=f"chiavi_deposito_{selected_apartment}")
    
    with col2:
        chiavi_istruzioni = st.text_area("Chiavi - Istruzioni", value=existing_data.get("chiavi_istruzioni", ""), key=f"chiavi_istruzioni_{selected_apartment}")
    
    # Ingresso
    st.markdown("### Ingresso")
    col1, col2 = st.columns(2)
    with col1:
        ingresso_portone = st.text_input("Ingresso Portone", value=existing_data.get("ingresso_portone", ""), key=f"ingresso_portone_{selected_apartment}")
    
    with col2:
        # Gestione foto portone
        st.markdown("#### Foto Portone")
        portone_img_url = existing_data.get("ingresso_portone_immagine", "")
        if portone_img_url:
            st.markdown(f"[Vedi foto portone]({portone_img_url})")
        portone_img = st.file_uploader("Carica foto portone", type=["jpg", "jpeg", "png"], key=f"portone_img_{selected_apartment}")
        if portone_img:
            portone_img_url = upload_file_to_drive(portone_img, selected_apartment, "Foto portone")
    
    # Porta blindata
    st.markdown("### Porta Blindata")
    col1, col2 = st.columns(2)
    with col1:
        # Gestione foto porta blindata
        st.markdown("#### Foto Porta Blindata")
        blindata_img_url = existing_data.get("porta_blindata_immagine", "")
        if blindata_img_url:
            st.markdown(f"[Vedi foto porta blindata]({blindata_img_url})")
        blindata_img = st.file_uploader("Carica foto porta blindata", type=["jpg", "jpeg", "png"], key=f"blindata_img_{selected_apartment}")
        if blindata_img:
            blindata_img_url = upload_file_to_drive(blindata_img, selected_apartment, "Foto porta blindata")
    
    # Note speciali
    st.markdown("### Note Speciali")
    col1, col2 = st.columns(2)
    with col1:
        istruzioni_speciali = st.text_area("Istruzioni Speciali", value=existing_data.get("istruzioni_speciali", ""), key=f"istruzioni_speciali_{selected_apartment}")
        note_cassonetti = st.text_area("Note Cassonetti", value=existing_data.get("note_cassonetti", ""), key=f"note_cassonetti_{selected_apartment}")
    
    with col2:
        note_parcheggio = st.text_area("Note Parcheggio", value=existing_data.get("note_parcheggio", ""), key=f"note_parcheggio_{selected_apartment}")
    
    # Salvataggio
    if st.button("Salva configurazione Check-in", key=f"save_checkin_{selected_apartment}"):
        data = {
            "appartamento": selected_apartment,
            "lat": lat,
            "long": long,
            "cap": cap,
            "citofono": citofono,
            "codice": codice,
            "video": video,
            "dispositivo_installato": dispositivo_installato,
            "shelly_id": shelly_id,
            "chiavi_consegna_metodo": chiavi_consegna_metodo,
            "chiavi_deposito": chiavi_deposito,
            "chiavi_istruzioni": chiavi_istruzioni,
            "ingresso_portone": ingresso_portone,
            "ingresso_portone_immagine": portone_img_url if 'portone_img_url' in locals() else existing_data.get("ingresso_portone_immagine", ""),
            "porta_blindata_immagine": blindata_img_url if 'blindata_img_url' in locals() else existing_data.get("porta_blindata_immagine", ""),
            "istruzioni_speciali": istruzioni_speciali,
            "note_cassonetti": note_cassonetti,
            "note_parcheggio": note_parcheggio
        }
        save_to_sheets("check-in", data)
        st.success("Configurazione Check-in salvata con successo!") 