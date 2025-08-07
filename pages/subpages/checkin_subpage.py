"""
Subpage Check-in
Gestisce la logica e il rendering della sezione check-in per add_property.
"""
import streamlit as st
import pandas as pd
from utils import get_data, save_to_sheets, upload_file_to_drive, get_apartment_data
import os
from datetime import datetime

try:
    from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
    webrtc_available = True
except ImportError:
    webrtc_available = False

def get_address_from_contratti(selected_apartment):
    """Recupera l'indirizzo dal foglio contratti."""
    df = get_data("contratti")
    if df is None or df.empty:
        return None, None, None, None
    
    match = df[df["appartamento"] == selected_apartment]
    if match.empty:
        return None, None, None, None
        
    row = match.iloc[0]
    return row.get("via", ""), row.get("citta", ""), row.get("provincia", ""), row.get("regione", "")

def get_cap_from_contratti(selected_apartment):
    """Recupera il CAP dal foglio contratti."""
    df = get_data("contratti")
    if df is None or df.empty:
        return None
    
    match = df[df["appartamento"] == selected_apartment]
    if match.empty:
        return None
        
    return match.iloc[0].get("cap", "")

def get_coordinates(address):
    """Genera le coordinate da un indirizzo."""
    try:
        import geocoder
        g = geocoder.osm(address)
        if g.ok:
            return g.lat, g.lng
    except Exception as e:
        st.warning(f"Coordinate non generate per: {address}")
    return None, None

def handle_file_upload(uploaded_file, file_type, apartment_name):
    """Gestisce l'upload di file (video o immagini)."""
    if uploaded_file is None:
        return None
        
    # Crea il nome del file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = os.path.splitext(uploaded_file.name)[1]
    filename = f"{apartment_name}_{file_type}_{timestamp}{file_ext}"
    
    # Upload del file
    try:
        url = upload_file(uploaded_file, filename)
        return url
    except Exception as e:
        st.error(f"Errore durante l'upload del file: {e}")
        return None

def render_checkin_subpage(selected_apartment, existing_data=None):
    # Carica i dati del check-in per l'appartamento
    existing_data = get_apartment_data("check-in", selected_apartment)
    
    st.markdown("#### Gestione Check-in")
    
    # Informazioni base
    st.markdown("### Informazioni Base")
    col1, col2 = st.columns(2)
    with col1:
        check_in_time = st.time_input("Orario Check-in", value=pd.to_datetime(existing_data.get("check_in_time", "15:00")).time(), key="checkin_time")
        check_out_time = st.time_input("Orario Check-out", value=pd.to_datetime(existing_data.get("check_out_time", "10:00")).time(), key="checkout_time")
        self_check_in = st.checkbox("Self Check-in", value=bool(existing_data.get("self_check_in", False)), key="self_checkin")
    
    with col2:
        check_in_instructions = st.text_area("Istruzioni Check-in", value=existing_data.get("check_in_instructions", ""), key="checkin_instructions")
        check_out_instructions = st.text_area("Istruzioni Check-out", value=existing_data.get("check_out_instructions", ""), key="checkout_instructions")
    
    # Codici e accessi
    st.markdown("### Codici e Accessi")
    col1, col2 = st.columns(2)
    with col1:
        codice_porta = st.text_input("Codice Porta", value=existing_data.get("codice_porta", ""), key="codice_porta")
        codice_ascensore = st.text_input("Codice Ascensore", value=existing_data.get("codice_ascensore", ""), key="codice_ascensore")
        codice_cancello = st.text_input("Codice Cancello", value=existing_data.get("codice_cancello", ""), key="codice_cancello")
    
    with col2:
        codice_armadietto = st.text_input("Codice Armadietto", value=existing_data.get("codice_armadietto", ""), key="codice_armadietto")
        codice_parcheggio = st.text_input("Codice Parcheggio", value=existing_data.get("codice_parcheggio", ""), key="codice_parcheggio")
        codice_garage = st.text_input("Codice Garage", value=existing_data.get("codice_garage", ""), key="codice_garage")
    
    # Note aggiuntive
    st.markdown("### Note Aggiuntive")
    note = st.text_area("Note", value=existing_data.get("note", ""), key="checkin_note")
    
    # Upload file
    st.markdown("### Upload File")
    uploaded_file = st.file_uploader("Carica file", type=["pdf", "doc", "docx", "txt"], key="checkin_file")
    if uploaded_file:
        try:
            url = upload_file_to_drive(uploaded_file, selected_apartment, "check-in")
            if url:
                st.success(f"File caricato con successo: {url}")
        except Exception as e:
            st.error(f"Errore durante l'upload del file: {e}")
    
    # Salvataggio
    if st.button("Salva configurazione Check-in"):
        data = {
            "appartamento": selected_apartment,
            "check_in_time": check_in_time.strftime("%H:%M"),
            "check_out_time": check_out_time.strftime("%H:%M"),
            "self_check_in": self_check_in,
            "check_in_instructions": check_in_instructions,
            "check_out_instructions": check_out_instructions,
            "codice_porta": codice_porta,
            "codice_ascensore": codice_ascensore,
            "codice_cancello": codice_cancello,
            "codice_armadietto": codice_armadietto,
            "codice_parcheggio": codice_parcheggio,
            "codice_garage": codice_garage,
            "note": note
        }
        save_to_sheets("check-in", data)
        st.success("Configurazione Check-in salvata con successo!")

    # Carica i dati esistenti
    df = get_data("check-in")
    if df is None or df.empty:
        df = pd.DataFrame(columns=["appartamento", "lat", "long", "cap", "citofono", "codice", 
                                 "video", "dispositivo_installato", "shelly_id", "chiavi_consegna_metodo",
                                 "chiavi_deposito", "chiavi_istruzioni", "ingresso_portone",
                                 "ingresso_portone_immagine", "porta_blindata_immagine",
                                 "istruzioni_speciali", "note_cassonetti", "note_parcheggio",
                                 "Descrizione Accesso", "Manuali ITA", "Manuali EN",
                                 "Messaggio Open ITA", "Messaggio Open EN",
                                 "Messaggio Come arrivare da MPX/BGY ITA",
                                 "Messaggio Come arrivare da MPX/BGY EN",
                                 "Messaggio Duomo ITA", "Messaggio Duomo EN",
                                 "Messaggio Parcheggio ITA", "Messaggio Parcheggio EN",
                                 "Video spazzatura"])
    
    # Filtra per appartamento selezionato
    existing = df[df["appartamento"] == selected_apartment]
    existing_data = existing.iloc[0].to_dict() if not existing.empty else {}
    
    # --- Campi principali in verticale ---
    via, citta, provincia, regione = get_address_from_contratti(selected_apartment)
    cap_from_contratti = get_cap_from_contratti(selected_apartment)
    address = f"{via}, {citta}, {provincia}, {regione}" if via and citta and provincia and regione else ""
    st.text_input("Indirizzo", value=address, disabled=True)

    lat = st.text_input("Latitudine", value=st.session_state.get("lat", existing_data.get("lat", "")), key="lat_input")
    lng = st.text_input("Longitudine", value=st.session_state.get("lng", existing_data.get("long", "")), key="lng_input")
    if address:
        if st.button("Genera coordinate da indirizzo"):
            lat_new, lng_new = get_coordinates(address)
            if lat_new and lng_new:
                st.session_state.lat = str(lat_new)
                st.session_state.lng = str(lng_new)
                st.success("Coordinate generate e sovrascritte!")
            else:
                st.error("Impossibile generare le coordinate")

    cap = st.text_input("CAP", value=cap_from_contratti or existing_data.get("cap", ""))
    citofono = st.text_input("Citofono", value=existing_data.get("citofono", ""))
    codice = st.text_input("Codice", value=existing_data.get("codice", ""))
    dispositivo = st.checkbox("Dispositivo Installato", value=bool(existing_data.get("dispositivo_installato", False)))
    shelly_id = st.text_input("Shelly ID", value=existing_data.get("shelly_id", ""))
    chiavi_consegna = st.text_input("Metodo Consegna Chiavi", value=existing_data.get("chiavi_consegna_metodo", ""))
    chiavi_deposito = st.text_input("Deposito Chiavi", value=existing_data.get("chiavi_deposito", ""))
    chiavi_istruzioni = st.text_area("Istruzioni Chiavi", value=existing_data.get("chiavi_istruzioni", ""))
    ingresso_portone = st.text_input("Ingresso Portone", value=existing_data.get("ingresso_portone", ""))
    istruzioni_speciali = st.text_area("Istruzioni Speciali", value=existing_data.get("istruzioni_speciali", ""))
    note_cassonetti = st.text_area("Note Cassonetti", value=existing_data.get("note_cassonetti", ""))
    note_parcheggio = st.text_area("Note Parcheggio", value=existing_data.get("note_parcheggio", ""))
    descrizione_accesso = st.text_area("Descrizione Accesso", value=existing_data.get("Descrizione Accesso", ""))

    # --- Manuali e Messaggi ---
    manuali_ita = existing_data.get("Manuali ITA", "")
    manuali_en = existing_data.get("Manuali EN", "")
    # Messaggi
    messages = [
        ("Open", "Messaggio Open"),
        ("Come arrivare da MPX/BGY", "Messaggio Come arrivare da MPX/BGY"),
        ("Duomo", "Messaggio Duomo"),
        ("Parcheggio", "Messaggio Parcheggio")
    ]
    messages_present = any(existing_data.get(f"{prefix} ITA", "") or existing_data.get(f"{prefix} EN", "") for _, prefix in messages)
    if manuali_ita or manuali_en:
        st.markdown("##### Manuali")
        if manuali_ita:
            st.markdown(f"[Manuali ITA]({manuali_ita})", unsafe_allow_html=True)
        if manuali_en:
            st.markdown(f"[Manuali EN]({manuali_en})", unsafe_allow_html=True)
    if messages_present:
        st.markdown("##### Messaggi")
        for title, prefix in messages:
            ita_msg = existing_data.get(f"{prefix} ITA", "")
            en_msg = existing_data.get(f"{prefix} EN", "")
            if ita_msg or en_msg:
                st.markdown(f"**{title}:**")
                if ita_msg:
                    st.markdown(f"- ITA: {ita_msg}")
                if en_msg:
                    st.markdown(f"- EN: {en_msg}")

    # --- Tutti i campi multimediali ALLA FINE, in verticale ---
    st.markdown("---")
    st.markdown("### Multimedia")

    # Video Accesso
    st.markdown("#### Video Accesso")
    access_video_url = existing_data.get("video", "")
    if access_video_url:
        st.markdown(f"[Guarda video accesso]({access_video_url})", unsafe_allow_html=True)
    access_video = st.file_uploader("Carica nuovo video accesso", type=["mp4", "mov"], key="checkin_video_access")
    if access_video:
        access_video_url = upload_file_to_drive(access_video, selected_apartment, "Tutorial check-in")
    if webrtc_available:
        if st.button("Registra video accesso dal browser"):
            webrtc_ctx = webrtc_streamer(
                key="checkin_video_access_record",
                video_receiver_size=(640, 480),
                sendback_audio=False
            )
            if webrtc_ctx.video_receiver:
                st.info("Premi REC per registrare e STOP per terminare. Scarica il file e ricaricalo sopra.")

    # Video Spazzatura
    st.markdown("#### Video Spazzatura")
    garbage_video_url = existing_data.get("Video spazzatura", "")
    if garbage_video_url:
        st.markdown(f"[Guarda video spazzatura]({garbage_video_url})", unsafe_allow_html=True)
    garbage_video = st.file_uploader("Carica nuovo video spazzatura", type=["mp4", "mov"], key="checkin_video_garbage")
    if garbage_video:
        garbage_video_url = upload_file_to_drive(garbage_video, selected_apartment, "Video spazzatura")
    if webrtc_available:
        if st.button("Registra video spazzatura dal browser"):
            webrtc_ctx = webrtc_streamer(
                key="checkin_video_garbage_record",
                video_receiver_size=(640, 480),
                sendback_audio=False
            )
            if webrtc_ctx.video_receiver:
                st.info("Premi REC per registrare e STOP per terminare. Scarica il file e ricaricalo sopra.")

    # Immagine Portone
    st.markdown("#### Immagine Portone")
    portone_img_url = existing_data.get("ingresso_portone_immagine", "")
    if portone_img_url:
        st.markdown(f"[Vedi immagine portone]({portone_img_url})", unsafe_allow_html=True)
    portone_img = st.file_uploader("Carica nuova immagine portone", type=["jpg", "jpeg", "png"], key="checkin_img_portone")
    if portone_img:
        portone_img_url = upload_file_to_drive(portone_img, selected_apartment, "Immagine portone")
        
    # Immagine Porta Blindata
    st.markdown("#### Immagine Porta Blindata")
    blindata_img_url = existing_data.get("porta_blindata_immagine", "")
    if blindata_img_url:
        st.markdown(f"[Vedi immagine porta blindata]({blindata_img_url})", unsafe_allow_html=True)
    blindata_img = st.file_uploader("Carica nuova immagine porta blindata", type=["jpg", "jpeg", "png"], key="checkin_img_blindata")
    if blindata_img:
        blindata_img_url = upload_file_to_drive(blindata_img, selected_apartment, "Immagine porta blindata")
        
    # Salvataggio
    if st.button("Salva dati check-in"):
        data = {
            "appartamento": selected_apartment,
            "lat": lat,
            "long": lng,
            "cap": cap,
            "citofono": citofono,
            "codice": codice,
            "video": access_video_url,
            "dispositivo_installato": dispositivo,
            "shelly_id": shelly_id,
            "chiavi_consegna_metodo": chiavi_consegna,
            "chiavi_deposito": chiavi_deposito,
            "chiavi_istruzioni": chiavi_istruzioni,
            "ingresso_portone": ingresso_portone,
            "ingresso_portone_immagine": portone_img_url,
            "porta_blindata_immagine": blindata_img_url,
            "istruzioni_speciali": istruzioni_speciali,
            "note_cassonetti": note_cassonetti,
            "note_parcheggio": note_parcheggio,
            "Descrizione Accesso": descrizione_accesso,
            "Video spazzatura": garbage_video_url
        }
        save_to_sheets("check-in", data)
        st.success("Dati check-in salvati con successo!") 