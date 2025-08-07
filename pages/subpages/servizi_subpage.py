"""
Subpage Servizi
Gestisce la logica e il rendering della sezione servizi per add_property.
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
    """Crea un registratore audio usando st.camera_input come alternativa a st_audiorec."""
    st.markdown("#### 🎤 Registrazione Audio")
    st.info("⚠️ Registrazione audio non disponibile su Streamlit Cloud. Usa l'upload di file audio.")
    
    # Opzioni per audio: upload file o registrazione (se disponibile)
    audio_option = st.radio(
        "Scegli opzione audio:",
        ["📁 Carica file audio", "🎤 Registra audio (non disponibile)"],
        key=f"audio_option_{component_name}"
    )
    
    if audio_option == "📁 Carica file audio":
        audio_file = st.file_uploader(
            "Carica file audio (MP3, WAV, M4A)",
            type=["mp3", "wav", "m4a"],
            key=f"audio_upload_{component_name}"
        )
        if audio_file:
            st.audio(audio_file, format=f"audio/{audio_file.type}")
            return audio_file
    else:
        st.warning("Registrazione audio non disponibile su Streamlit Cloud. Usa l'upload di file audio.")
    
    return None

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
        boolean_fields = [f for f in fields if f['type'] == 'boolean']
        
        field_info = []
        for field in fields:
            field_type = field['type']
            if field_type == 'boolean':
                field_info.append(f"'{field['label']}' (vero/falso, nome tecnico: {field['name']})")
            else:
                field_info.append(f"'{field['label']}' (testo, nome tecnico: {field['name']})")
        
        prompt = f"""
        Analizza il seguente testo che descrive i servizi disponibili in un appartamento.
        Estrai le informazioni per ogni campo nell'elenco, rispettando il tipo di dato richiesto.
        
        Elenco dei campi da verificare:
        {', '.join(field_info)}
        
        Testo: "{transcription_text}"
        
        Rispondi solo con un JSON valido. Le chiavi del JSON devono essere i nomi tecnici dei campi.
        - Per i campi booleani: usa true/false (es. "wifi": true, "pulizie": false)
        - Per i campi testuali: usa stringhe (es. "note": "servizio disponibile")
        
        Esempio di risposta:
        {{
            "wifi": true,
            "pulizie": false,
            "biancheria": true,
            "note": "wifi incluso nel prezzo"
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
    """Rende un registratore audio per le informazioni dei servizi."""
    st.subheader("🎤 Registrazione Audio Servizi")
    st.write("Descrivi a voce i servizi disponibili (es. 'c'è il wifi incluso, le pulizie sono a carico del proprietario, la biancheria è disponibile').")

    if 'servizi_audio_data' not in st.session_state:
        st.session_state.servizi_audio_data = None

    # Use a unique component name for this recorder
    audio_data = create_audio_recorder("servizi_audio_recorder")

    if audio_data is not None and audio_data != st.session_state.get('servizi_processed_audio_data'):
        st.session_state.servizi_audio_data = audio_data
        st.success("✅ Audio registrato!")
        st.audio(audio_data, format='audio/wav')

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Elabora Audio Servizi", key="elabora_servizi"):
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
                                key = f"serv_{field_name}"
                                st.session_state[key] = value
                            
                            st.session_state.servizi_processed_audio_data = audio_data
                            st.rerun() # Ricarica per mostrare i campi aggiornati
                        else:
                            st.warning("⚠️ Non è stato possibile estrarre dati.")
                        
                        os.unlink(audio_path)
                    except Exception as e:
                        st.error(f"❌ Errore durante l'elaborazione: {e}")
                        logger.error(f"Errore durante l'elaborazione dell'audio registrato: {e}")

        with col2:
            if st.button("🔄 Registra di Nuovo", key="registra_nuovo_servizi"):
                st.session_state.servizi_audio_data = None
                st.session_state.servizi_processed_audio_data = None
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

def render_field(field, existing_data, key_prefix="serv"):
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
                # Converti stringhe comuni a boolean
                string_value = str(existing_value).lower().strip()
                st.session_state[key] = string_value in ['true', 'vero', 'si', 'yes', '1', 't', 'v']
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

def render_servizi_subpage(selected_apartment, existing_data=None):
    # Carica i dati dell'appartamento solo una volta
    if f"servizi_data_{selected_apartment}" not in st.session_state:
        st.session_state[f"servizi_data_{selected_apartment}"] = get_apartment_data("servizi", selected_apartment)
    
    existing_data = st.session_state[f"servizi_data_{selected_apartment}"]
    
    # Debug: mostra i dati caricati
    st.write(f"DEBUG - Dati servizi per {selected_apartment}: {existing_data}")
    
    # Carica la configurazione dei campi
    config_path = "field_configs/servizi.csv"
    fields = load_field_config(config_path)
    
    st.markdown("#### Gestione Servizi")
    
    if not fields:
        st.error("Configurazione campi non trovata. Controlla il file field_configs/servizi.csv")
        return
    
    # Filtra solo i campi visibili
    visible_fields = [f for f in fields if f['visible']]
    
    if not visible_fields:
        st.warning("Nessun campo visibile configurato.")
        return
        
    # --- REGISTRAZIONE AUDIO ---
    render_audio_recorder(visible_fields)
    st.markdown("---")
    
    # Organizza i servizi in categorie per una migliore visualizzazione
    categories = {
        "🏠 Accessibilità": [f for f in visible_fields if any(word in f['name'].lower() for word in ['disabili', 'ascensore', 'livello', 'sedia', 'accessibile'])],
        "🛁 Bagno": [f for f in visible_fields if any(word in f['name'].lower() for word in ['asciugamani', 'bidet', 'phon', 'shampoo', 'vasca', 'bagno', 'doccia'])],
        "🛏️ Camera": [f for f in visible_fields if any(word in f['name'].lower() for word in ['cuscini', 'appendini', 'biancheria', 'scuranti', 'letto'])],
        "🌡️ Clima": [f for f in visible_fields if any(word in f['name'].lower() for word in ['aria', 'riscaldamento'])],
        "🍳 Cucina": [f for f in visible_fields if any(word in f['name'].lower() for word in ['cucina', 'forno', 'pentole', 'piatti', 'fornelli', 'frigorifero', 'lavastoviglie', 'caffe', 'cucinino'])],
        "👕 Lavanderia": [f for f in visible_fields if any(word in f['name'].lower() for word in ['ferro', 'lavatrice', 'asciugatrice'])],
        "🛋️ Soggiorno": [f for f in visible_fields if any(word in f['name'].lower() for word in ['sala', 'soggiorno', 'tv', 'laptop', 'web_tv', 'widescreen'])],
        "🔒 Sicurezza": [f for f in visible_fields if any(word in f['name'].lower() for word in ['contactless', 'estintore', 'rilevatore', 'monossido', 'fumo'])],
        "🌳 Esterno": [f for f in visible_fields if any(word in f['name'].lower() for word in ['balcone', 'giardino', 'parcheggio', 'spiaggia', 'terrazza'])],
        "📶 Connessione": [f for f in visible_fields if any(word in f['name'].lower() for word in ['wifi', 'connessione'])],
        "📝 Altri Servizi": [f for f in visible_fields if not any(word in f['name'].lower() for word in ['disabili', 'ascensore', 'livello', 'sedia', 'accessibile', 'asciugamani', 'bidet', 'phon', 'shampoo', 'vasca', 'bagno', 'doccia', 'cuscini', 'appendini', 'biancheria', 'scuranti', 'letto', 'aria', 'riscaldamento', 'cucina', 'forno', 'pentole', 'piatti', 'fornelli', 'frigorifero', 'lavastoviglie', 'caffe', 'cucinino', 'ferro', 'lavatrice', 'asciugatrice', 'sala', 'soggiorno', 'tv', 'laptop', 'web_tv', 'widescreen', 'contactless', 'estintore', 'rilevatore', 'monossido', 'fumo', 'balcone', 'giardino', 'parcheggio', 'spiaggia', 'terrazza', 'wifi', 'connessione'])]
    }
    
    # Rimuovi categorie vuote
    categories = {k: v for k, v in categories.items() if v}
    
    # Set per tracciare i campi già renderizzati
    rendered_fields = set()
    
    # Renderizza i servizi per categoria
    for category, category_fields in categories.items():
        st.markdown(f"### {category}")
        cols = st.columns(3)  # 3 colonne per una migliore visualizzazione
        col_index = 0
        for field in category_fields:
            # Controlla se il campo è già stato renderizzato
            if field['name'] not in rendered_fields:
                with cols[col_index % 3]:
                    render_field(field, existing_data)
                    rendered_fields.add(field['name'])
                col_index += 1
        st.markdown("---")
    
    # Salvataggio
    if st.button("Salva servizi"):
        # Raccogli tutti i valori dal session state
        data = {"appartamento": selected_apartment}
        
        for field in visible_fields:
            field_name = field['name']
            key = f"serv_{field_name}"
            
            # Ottieni il valore dal session state
            if key in st.session_state:
                data[field_name] = st.session_state[key]
            else:
                data[field_name] = existing_data.get(field_name, "")
        
        # Salva i dati
        save_to_sheets("servizi", data)
        st.success("Servizi salvati con successo!")
        
        # Aggiorna i dati nel session state
        st.session_state[f"servizi_data_{selected_apartment}"] = data 