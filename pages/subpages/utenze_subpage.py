"""
Subpage Utenze
Gestisce la logica e il rendering della sezione utenze per add_property.
"""
import streamlit as st
import pandas as pd
from utils import get_data, save_to_sheets, upload_file_to_drive, get_apartment_data

try:
    from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
    webrtc_available = True
except ImportError:
    webrtc_available = False

def render_utenze_subpage(selected_apartment, existing_data=None):
    # Carica i dati delle utenze per l'appartamento
    existing_data = get_apartment_data("utenze", selected_apartment)
    
    st.markdown("#### Gestione Utenze")
    
    # Informazioni base
    st.markdown("### Informazioni Base")
    col1, col2 = st.columns(2)
    with col1:
        fornitore_luce = st.text_input("Fornitore Luce", value=existing_data.get("fornitore_luce", ""), key="utenza_luce")
        numero_contratto_luce = st.text_input("Numero Contratto Luce", value=existing_data.get("numero_contratto_luce", ""), key="utenza_contratto_luce")
        pod_luce = st.text_input("POD Luce", value=existing_data.get("pod_luce", ""), key="utenza_pod_luce")
    
    with col2:
        fornitore_gas = st.text_input("Fornitore Gas", value=existing_data.get("fornitore_gas", ""), key="utenza_gas")
        numero_contratto_gas = st.text_input("Numero Contratto Gas", value=existing_data.get("numero_contratto_gas", ""), key="utenza_contratto_gas")
        pdr_gas = st.text_input("PDR Gas", value=existing_data.get("pdr_gas", ""), key="utenza_pdr_gas")
    
    # Informazioni acqua
    st.markdown("### Informazioni Acqua")
    col1, col2 = st.columns(2)
    with col1:
        fornitore_acqua = st.text_input("Fornitore Acqua", value=existing_data.get("fornitore_acqua", ""), key="utenza_acqua")
        numero_contratto_acqua = st.text_input("Numero Contratto Acqua", value=existing_data.get("numero_contratto_acqua", ""), key="utenza_contratto_acqua")
    
    with col2:
        numero_contatore_acqua = st.text_input("Numero Contatore Acqua", value=existing_data.get("numero_contatore_acqua", ""), key="utenza_contatore_acqua")
        posizione_contatore_acqua = st.text_input("Posizione Contatore Acqua", value=existing_data.get("posizione_contatore_acqua", ""), key="utenza_posizione_acqua")
    
    # Informazioni rifiuti
    st.markdown("### Informazioni Rifiuti")
    col1, col2 = st.columns(2)
    with col1:
        fornitore_rifiuti = st.text_input("Fornitore Rifiuti", value=existing_data.get("fornitore_rifiuti", ""), key="utenza_rifiuti")
        numero_contratto_rifiuti = st.text_input("Numero Contratto Rifiuti", value=existing_data.get("numero_contratto_rifiuti", ""), key="utenza_contratto_rifiuti")
    
    with col2:
        giorno_raccolta = st.text_input("Giorno Raccolta", value=existing_data.get("giorno_raccolta", ""), key="utenza_giorno_raccolta")
        tipo_raccolta = st.text_input("Tipo Raccolta", value=existing_data.get("tipo_raccolta", ""), key="utenza_tipo_raccolta")
    
    # Note
    note = st.text_area("Note", value=existing_data.get("note", ""), key="utenza_note")
    
    # Salvataggio
    if st.button("Salva configurazione Utenze"):
        data = {
            "appartamento": selected_apartment,
            "fornitore_luce": fornitore_luce,
            "numero_contratto_luce": numero_contratto_luce,
            "pod_luce": pod_luce,
            "fornitore_gas": fornitore_gas,
            "numero_contratto_gas": numero_contratto_gas,
            "pdr_gas": pdr_gas,
            "fornitore_acqua": fornitore_acqua,
            "numero_contratto_acqua": numero_contratto_acqua,
            "numero_contatore_acqua": numero_contatore_acqua,
            "posizione_contatore_acqua": posizione_contatore_acqua,
            "fornitore_rifiuti": fornitore_rifiuti,
            "numero_contratto_rifiuti": numero_contratto_rifiuti,
            "giorno_raccolta": giorno_raccolta,
            "tipo_raccolta": tipo_raccolta,
            "note": note
        }
        save_to_sheets("utenze", data)
        st.success("Configurazione Utenze salvata con successo!")

    # Video tutorial solo per luce e gas
    tutorial_url = existing_data.get("tutorial", "")
    if "luce" in existing_data or "gas" in existing_data:
        if tutorial_url:
            st.markdown(f"**Video tutorial esistente:** [Guarda video]({tutorial_url})")
        nuovo_video = st.file_uploader(
            "Carica nuovo video tutorial (opzionale)", 
            type=["mp4", "mov"], 
            key=f"utenza_video_upload_{'luce' if 'luce' in existing_data else 'gas'}"
        )
        if nuovo_video:
            tutorial_url = upload_file_to_drive(nuovo_video, selected_apartment, f"Video tutorial utenza {'luce' if 'luce' in existing_data else 'gas'}")
        
        # Permetti anche di registrare un video se streamlit-webrtc è disponibile
        if webrtc_available:
            st.markdown("---")
            st.markdown("##### Oppure registra un video dal browser:")
            webrtc_ctx = webrtc_streamer(
                key=f"utenza_video_record_{'luce' if 'luce' in existing_data else 'gas'}", 
                video_receiver_size=(640, 480),
                sendback_audio=False
            )
            if webrtc_ctx.video_receiver:
                st.info("Premi REC per registrare e STOP per terminare. Scarica il file e ricaricalo sopra.")
        else:
            st.info("Per registrare un video dal browser, installa streamlit-webrtc oppure usa l'upload.")

    # Salvataggio multiplo: lista in session_state
    if "utenze_nuove" not in st.session_state:
        st.session_state.utenze_nuove = []
        
    if st.button("Aggiungi utenza a lista da salvare"):
        st.session_state.utenze_nuove.append({
            "appartamento": selected_apartment,
            "tipologia": 'luce' if 'luce' in existing_data else 'gas',
            "nome_utenza": existing_data.get("nome_utenza", ""),
            "intestatario": existing_data.get("intestatario", ""),
            "codice_pod_pdr": existing_data.get("codice_pod_pdr", ""),
            "numero_cliente": existing_data.get("numero_cliente", ""),
            "url_contratto": existing_data.get("url_contratto", ""),
            "fornitore": existing_data.get("fornitore", ""),
            "posizione_interruttore": existing_data.get("posizione_interruttore", ""),
            "posizione_contatore": existing_data.get("posizione_contatore", ""),
            "note": existing_data.get("note", ""),
            "tutorial": tutorial_url,
            "nuovo_video": None  # Placeholder per il file video, non va su Google Sheet
        })
        st.success("Utenza aggiunta alla lista!")
        
    # Mostra lista da salvare
    if st.session_state.utenze_nuove:
        st.markdown("#### Utenze da salvare:")
        for i, utenza in enumerate(st.session_state.utenze_nuove):
            st.write(f"{i+1}. {utenza['tipologia']} - {utenza['nome_utenza']}")
            
        if st.button("Salva tutte le utenze aggiunte", key="salva_utenze"):
            for utenza in st.session_state.utenze_nuove:
                data = utenza.copy()
                data.pop("nuovo_video", None)
                data["tutorial"] = utenza.get("tutorial", "")
                save_to_sheets("utenze", data)
            st.session_state.utenze_nuove = []
            st.success("Tutte le utenze sono state salvate!") 