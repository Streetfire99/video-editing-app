"""
Subpage Climatizzazione
Gestisce la logica e il rendering della sezione climatizzazione per add_property.
"""
import streamlit as st
import pandas as pd
from utils import get_data, save_to_sheets, upload_file_to_drive, get_apartment_data

try:
    from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
    webrtc_available = True
except ImportError:
    webrtc_available = False

def render_climatizzazione_subpage(selected_apartment, existing_data=None):
    # Carica i dati della climatizzazione per l'appartamento
    existing_data = get_apartment_data("climatizzazione", selected_apartment)
    
    st.markdown("#### Gestione Climatizzazione")
    
    # Informazioni base
    st.markdown("### Informazioni Base")
    col1, col2 = st.columns(2)
    with col1:
        tipo_riscaldamento = st.selectbox(
            "Tipo Riscaldamento",
            ["Autonomo", "Centralizzato", "Pompa di Calore", "Altro"],
            index=["Autonomo", "Centralizzato", "Pompa di Calore", "Altro"].index(existing_data.get("tipo_riscaldamento", "Autonomo")),
            key="clima_tipo_riscaldamento"
        )
        tipo_raffreddamento = st.selectbox(
            "Tipo Raffreddamento",
            ["Condizionatore", "Ventilatore", "Nessuno", "Altro"],
            index=["Condizionatore", "Ventilatore", "Nessuno", "Altro"].index(existing_data.get("tipo_raffreddamento", "Condizionatore")),
            key="clima_tipo_raffreddamento"
        )
    
    with col2:
        temperatura_min = st.number_input("Temperatura Minima", min_value=0, max_value=30, value=int(existing_data.get("temperatura_min", 18)), key="clima_temp_min")
        temperatura_max = st.number_input("Temperatura Massima", min_value=0, max_value=30, value=int(existing_data.get("temperatura_max", 26)), key="clima_temp_max")
    
    # Dettagli impianto
    st.markdown("### Dettagli Impianto")
    col1, col2 = st.columns(2)
    with col1:
        marca_condizionatore = st.text_input("Marca Condizionatore", value=existing_data.get("marca_condizionatore", ""), key="clima_marca")
        modello_condizionatore = st.text_input("Modello Condizionatore", value=existing_data.get("modello_condizionatore", ""), key="clima_modello")
        numero_split = st.number_input("Numero Split", min_value=0, value=int(existing_data.get("numero_split", 0)), key="clima_split")
    
    with col2:
        posizione_termostato = st.text_input("Posizione Termostato", value=existing_data.get("posizione_termostato", ""), key="clima_termostato")
        posizione_condizionatore = st.text_input("Posizione Condizionatore", value=existing_data.get("posizione_condizionatore", ""), key="clima_posizione")
    
    # Istruzioni
    st.markdown("### Istruzioni")
    istruzioni = st.text_area("Istruzioni Uso", value=existing_data.get("istruzioni", ""), key="clima_istruzioni")
    
    # Note
    note = st.text_area("Note", value=existing_data.get("note", ""), key="clima_note")
    
    # Salvataggio
    if st.button("Salva configurazione Climatizzazione"):
        data = {
            "appartamento": selected_apartment,
            "tipo_riscaldamento": tipo_riscaldamento,
            "tipo_raffreddamento": tipo_raffreddamento,
            "temperatura_min": temperatura_min,
            "temperatura_max": temperatura_max,
            "marca_condizionatore": marca_condizionatore,
            "modello_condizionatore": modello_condizionatore,
            "numero_split": numero_split,
            "posizione_termostato": posizione_termostato,
            "posizione_condizionatore": posizione_condizionatore,
            "istruzioni": istruzioni,
            "note": note
        }
        save_to_sheets("climatizzazione", data)
        st.success("Configurazione Climatizzazione salvata con successo!")

    # Carica tutti i sistemi di climatizzazione dal foglio
    df = get_data("climatizzazione")
    if df is None or df.empty:
        df = pd.DataFrame(columns=["appartamento", "tipologia_sistema", "autonomo", "sorgente", 
                                 "marca_sorgente", "modello_sorgente", "diffusore", "marca_diffusore", 
                                 "modello_diffusore", "video YT"])
    
    # Filtra per appartamento selezionato
    existing = df[df["appartamento"] == selected_apartment]
    
    st.markdown("#### Gestione Sistemi di Climatizzazione")
    
    # Selezione tipologia (riscaldamento, condizionamento)
    tipologia = st.selectbox("Tipologia", ["Riscaldamento", "Condizionamento"], key="clima_tipologia")
    
    # Trova i dati esistenti per questa tipologia
    existing_data = {}
    if not existing.empty:
        match = existing[existing["tipologia_sistema"].str.lower() == tipologia.lower()]
        if not match.empty:
            existing_data = match.iloc[0].to_dict()
    
    # Campi comuni per tutti i sistemi
    nome_sistema = st.text_input("Nome Sistema", value=existing_data.get("sorgente", ""), key="clima_nome")
    modello = st.text_input("Modello", value=existing_data.get("modello_sorgente", ""), key="clima_modello")
    marca = st.text_input("Marca", value=existing_data.get("marca_sorgente", ""), key="clima_marca")
    autonomo = st.checkbox("Sistema Autonomo", value=existing_data.get("autonomo", False), key="clima_autonomo")
    
    # Campi per il diffusore
    st.markdown("#### Diffusore")
    diffusore = st.text_input("Tipo Diffusore", value=existing_data.get("diffusore", ""), key="clima_diffusore")
    marca_diffusore = st.text_input("Marca Diffusore", value=existing_data.get("marca_diffusore", ""), key="clima_marca_diffusore")
    modello_diffusore = st.text_input("Modello Diffusore", value=existing_data.get("modello_diffusore", ""), key="clima_modello_diffusore")
    
    # Video tutorial
    tutorial_url = existing_data.get("video YT", "")
    if tutorial_url:
        st.markdown(f"**Video tutorial esistente:** [Guarda video]({tutorial_url})")
    nuovo_video = st.file_uploader(
        "Carica nuovo video tutorial (opzionale)", 
        type=["mp4", "mov"], 
        key=f"clima_video_upload_{tipologia.lower()}"
    )
    if nuovo_video:
        tutorial_url = upload_file_to_drive(nuovo_video, selected_apartment, f"Video tutorial {tipologia}")
    
    # Permetti anche di registrare un video se streamlit-webrtc è disponibile
    if webrtc_available:
        st.markdown("---")
        st.markdown("##### Oppure registra un video dal browser:")
        webrtc_ctx = webrtc_streamer(
            key=f"clima_video_record_{tipologia.lower()}", 
            video_receiver_size=(640, 480),
            sendback_audio=False
        )
        if webrtc_ctx.video_receiver:
            st.info("Premi REC per registrare e STOP per terminare. Scarica il file e ricaricalo sopra.")
    else:
        st.info("Per registrare un video dal browser, installa streamlit-webrtc oppure usa l'upload.")

    # Salvataggio multiplo: lista in session_state
    if "climatizzazione_nuova" not in st.session_state:
        st.session_state.climatizzazione_nuova = []
        
    if st.button("Aggiungi sistema a lista da salvare"):
        st.session_state.climatizzazione_nuova.append({
            "appartamento": selected_apartment,
            "tipologia_sistema": tipologia,
            "autonomo": autonomo,
            "sorgente": nome_sistema,
            "marca_sorgente": marca,
            "modello_sorgente": modello,
            "diffusore": diffusore,
            "marca_diffusore": marca_diffusore,
            "modello_diffusore": modello_diffusore,
            "video YT": tutorial_url,
            "nuovo_video": None  # Placeholder per il file video, non va su Google Sheet
        })
        st.success("Sistema aggiunto alla lista!")
        
    # Mostra lista da salvare
    if st.session_state.climatizzazione_nuova:
        st.markdown("#### Sistemi da salvare:")
        for i, sistema in enumerate(st.session_state.climatizzazione_nuova):
            st.write(f"{i+1}. {sistema['tipologia_sistema']} - {sistema['sorgente']}")
            
        if st.button("Salva tutti i sistemi aggiunti", key="salva_climatizzazione"):
            for sistema in st.session_state.climatizzazione_nuova:
                data = sistema.copy()
                data.pop("nuovo_video", None)
                data["video YT"] = sistema.get("video YT", "")
                save_to_sheets("climatizzazione", data)
            st.session_state.climatizzazione_nuova = []
            st.success("Tutti i sistemi sono stati salvati!") 