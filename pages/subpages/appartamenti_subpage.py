"""
Subpage Appartamenti
Gestisce la logica e il rendering della sezione appartamenti per add_property.
"""
import streamlit as st
import pandas as pd
import csv
import os
import logging
import json
import tempfile
import re
from openai import OpenAI
import whisper
import streamlit.components.v1 as components
from utils import get_data, save_to_sheets, get_apartment_data

logger = logging.getLogger(__name__)

@st.cache_resource
def load_whisper_model():
    """Carica il modello Whisper per la trascrizione"""
    logger.info("Caricamento del modello Whisper...")
    model = whisper.load_model("base")
    logger.info("Modello Whisper caricato.")
    return model

def create_audio_recorder(component_name):
    """Crea un registratore audio con un nome di componente unico."""
    import os
    import numpy as np
    from io import BytesIO
    
    # Try to use the installed st_audiorec component
    try:
        import st_audiorec
        # Use the component directly if available
        raw_audio_data = st_audiorec.st_audiorec()
    except ImportError:
        # Fallback to manual component declaration
        try:
            # Try to find the component in the site-packages
            import site
            import glob
            
            # Search for st_audiorec in site-packages
            site_packages = site.getsitepackages()
            build_dir = None
            
            for site_pkg in site_packages:
                potential_path = os.path.join(site_pkg, "st_audiorec", "frontend", "build")
                if os.path.exists(potential_path):
                    build_dir = potential_path
                    break
            
            if build_dir is None:
                # Try alternative path
                build_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                        ".venv311/lib/python3.11/site-packages/st_audiorec/frontend/build")
            
            # specify directory and initialize st_audiorec object functionality with unique name
            st_audiorec = components.declare_component(component_name, path=build_dir)
            raw_audio_data = st_audiorec()
        except Exception as e:
            st.error(f"❌ Errore nel caricamento del componente audio: {e}")
            st.info("🎤 Registrazione audio temporaneamente non disponibile")
            return None

    # Handle the audio data
    wav_bytes = None                # wav_bytes: contains the recorded audio in .WAV format after conversion

    if raw_audio_data is not None:
        # the frontend returns raw audio data in the form of arraybuffer
        # (this arraybuffer is derived from web-media API WAV-blob data)

        if isinstance(raw_audio_data, dict):  # retrieve audio data
            with st.spinner('retrieving audio-recording...'):
                ind, raw_audio_data = zip(*raw_audio_data['arr'].items())
                ind = np.array(ind, dtype=int)  # convert to np array
                raw_audio_data = np.array(raw_audio_data)  # convert to np array
                sorted_ints = raw_audio_data[ind]
                stream = BytesIO(b"".join([int(v).to_bytes(1, "big") for v in sorted_ints]))
                # wav_bytes contains audio data in byte format, ready to be processed further
                wav_bytes = stream.read()

    return wav_bytes

def process_audio_with_openai(transcription_text, fields):
    """Elabora la trascrizione con OpenAI per estrarre i dati strutturati."""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        api_key = config.get('openai_api_key')
        if not api_key:
            st.error("Chiave API OpenAI non trovata nel file config.json")
            return {}
            
        client = OpenAI(api_key=api_key)
        
        # Organizza i campi per tipo
        numeric_fields = [f for f in fields if f['type'] == 'numero']
        text_fields = [f for f in fields if f['type'] == 'testo']
        boolean_fields = [f for f in fields if f['type'] == 'boolean']
        
        field_info = []
        for field in fields:
            field_type = field['type']
            if field_type == 'numero':
                field_info.append(f"'{field['label']}' (numero, nome tecnico: {field['name']})")
            elif field_type == 'boolean':
                field_info.append(f"'{field['label']}' (vero/falso, nome tecnico: {field['name']})")
            else:
                field_info.append(f"'{field['label']}' (testo, nome tecnico: {field['name']})")
        
        prompt = f"""
        Analizza il seguente testo che descrive le caratteristiche di un appartamento.
        Estrai le informazioni per ogni campo nell'elenco, rispettando il tipo di dato richiesto.
        
        Elenco dei campi da verificare:
        {', '.join(field_info)}
        
        Testo: "{transcription_text}"
        
        Rispondi solo con un JSON valido. Le chiavi del JSON devono essere i nomi tecnici dei campi.
        - Per i campi numerici: usa numeri interi (es. "camere": 3)
        - Per i campi booleani: usa true/false (es. "divano_letto": true)
        - Per i campi testuali: usa stringhe (es. "stato": "disponibile")
        
        Esempio di risposta:
        {{
            "camere": 3,
            "numero_ospiti": 6,
            "metratura": 85,
            "stato": "disponibile",
            "divano_letto": true,
            "balcone": false,
            "ascensore": "presente"
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        logger.info(f"OpenAI response: {result_text}")
        
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)
            return data
        else:
            logger.error("Nessun JSON trovato nella risposta di OpenAI")
            return {}
            
    except Exception as e:
        logger.error(f"Errore durante l'elaborazione con OpenAI: {e}")
        st.error(f"Errore nell'elaborazione con OpenAI: {e}")
        return {}

def render_audio_recorder(fields):
    """Rende un registratore audio per le informazioni dell'appartamento."""
    st.subheader("🎤 Registrazione Audio Appartamento")
    st.write("Descrivi a voce le caratteristiche dell'appartamento (es. 'è un appartamento di 85 metri quadri con 3 camere, 6 posti letto, ha il balcone ma non la cantina').")

    if 'appartamenti_audio_data' not in st.session_state:
        st.session_state.appartamenti_audio_data = None

    # Use a unique component name for this recorder
    audio_data = create_audio_recorder("appartamenti_audio_recorder")

    if audio_data is not None and audio_data != st.session_state.get('appartamenti_processed_audio_data'):
        st.session_state.appartamenti_audio_data = audio_data
        st.success("✅ Audio registrato!")
        st.audio(audio_data, format='audio/wav')

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Elabora Audio Appartamento", key="elabora_appartamenti"):
                with st.spinner("Elaborazione in corso..."):
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                            tmp_file.write(audio_data)
                            audio_path = tmp_file.name

                        model = load_whisper_model()
                        result = model.transcribe(audio_path, language="it")
                        transcription = result["text"]
                        st.success(f"📝 **Trascrizione:** *{transcription}*")

                        extracted_data = process_audio_with_openai(transcription, fields)
                        if extracted_data:
                            st.success("✅ **Dati estratti con successo!**")
                            st.json(extracted_data)
                            
                            for field_name, value in extracted_data.items():
                                key = f"app_{field_name}"
                                st.session_state[key] = value
                            
                            st.session_state.appartamenti_processed_audio_data = audio_data
                            st.rerun() # Ricarica per mostrare i campi aggiornati
                        else:
                            st.warning("⚠️ Non è stato possibile estrarre dati.")
                        
                        os.unlink(audio_path)
                    except Exception as e:
                        st.error(f"❌ Errore durante l'elaborazione: {e}")
                        logger.error(f"Errore durante l'elaborazione dell'audio registrato: {e}")

        with col2:
            if st.button("🔄 Registra di Nuovo", key="registra_nuovo_appartamenti"):
                st.session_state.appartamenti_audio_data = None
                st.session_state.appartamenti_processed_audio_data = None
                st.rerun()

def load_field_config(config_path):
    """Carica la configurazione dei campi da CSV"""
    fields = []
    if os.path.exists(config_path):
        with open(config_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Converti i booleani
                row['required'] = row['required'] == 'True'
                row['visible'] = row['visible'] == 'True'
                row['dropdown'] = row['dropdown'] == 'True'
                fields.append(row)
    return fields

def render_field(field, existing_data, key_prefix="app"):
    """Rende un singolo campo in base alla sua configurazione"""
    field_name = field['name']
    field_label = field['label']
    field_type = field['type']
    field_dropdown = field['dropdown']
    
    # Chiave unica per il session state
    key = f"{key_prefix}_{field_name}"
    
    # Inizializza il valore nel session state se non esiste
    if key not in st.session_state:
        existing_value = existing_data.get(field_name, "")
        if field_type == "boolean":
            # Gestione sicura dei valori boolean
            if isinstance(existing_value, bool):
                st.session_state[key] = existing_value
            elif existing_value == "" or existing_value is None:
                st.session_state[key] = False
            else:
                st.session_state[key] = str(existing_value).lower() in ['true', 'vero', 'si', 'yes', '1']
        elif field_type == "numero":
            # Gestione sicura dei valori numerici
            if existing_value == "" or existing_value is None:
                st.session_state[key] = 0
            else:
                try:
                    st.session_state[key] = int(existing_value)
                except (ValueError, TypeError):
                    st.session_state[key] = 0
        else:
            st.session_state[key] = existing_value
    
    # Gestione sicura dei valori numerici
    def safe_int(value, default=0):
        if value == "" or value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    # Gestione sicura dei valori boolean
    def safe_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value == "" or value is None:
            return default
        try:
            return str(value).lower() in ['true', 'vero', 'si', 'yes', '1']
        except:
            return default
    
    if field_type == "testo":
        if field_dropdown:
            # Per ora usiamo text_input, ma potremmo implementare dropdown dinamici
            return st.text_input(field_label, value=st.session_state[key], key=key)
        else:
            return st.text_input(field_label, value=st.session_state[key], key=key)
    
    elif field_type == "numero":
        return st.number_input(field_label, min_value=0, value=st.session_state[key], key=key)
    
    elif field_type == "boolean":
        return st.checkbox(field_label, value=st.session_state[key], key=key)
    
    else:
        # Default a testo
        return st.text_input(field_label, value=st.session_state[key], key=key)

def render_appartamenti_subpage(selected_apartment, existing_data=None):
    # Carica i dati dell'appartamento solo una volta
    if f"appartamenti_data_{selected_apartment}" not in st.session_state:
        st.session_state[f"appartamenti_data_{selected_apartment}"] = get_apartment_data("appartamenti", selected_apartment)
    
    existing_data = st.session_state[f"appartamenti_data_{selected_apartment}"]
    
    # Carica la configurazione dei campi
    config_path = "field_configs/appartamenti.csv"
    fields = load_field_config(config_path)
    
    st.markdown("#### Gestione Appartamento")
    
    if not fields:
        st.error("Configurazione campi non trovata. Controlla il file field_configs/appartamenti.csv")
        return
    
    # Filtra solo i campi visibili
    visible_fields = [f for f in fields if f['visible']]
    
    if not visible_fields:
        st.warning("Nessun campo visibile configurato.")
        return
        
    # --- REGISTRAZIONE AUDIO ---
    render_audio_recorder(visible_fields)
    st.markdown("---")
    
    # Raggruppa i campi per sezioni (per ora tutti insieme)
    st.markdown("### Informazioni Appartamento")
    
    # Mostra i campi uno sotto l'altro
    for field in visible_fields:
        render_field(field, existing_data)
    
    # Salvataggio
    if st.button("Salva appartamento"):
        # Raccogli tutti i valori dal session state
        data = {"appartamento": selected_apartment}
        
        for field in visible_fields:
            field_name = field['name']
            key = f"app_{field_name}"
            
            # Ottieni il valore dal session state
            if key in st.session_state:
                data[field_name] = st.session_state[key]
            else:
                data[field_name] = existing_data.get(field_name, "")
        
        # Salva i dati
        save_to_sheets("appartamenti", data)
        st.success("Appartamento salvato con successo!")
        
        # Aggiorna i dati nel session state
        st.session_state[f"appartamenti_data_{selected_apartment}"] = data 