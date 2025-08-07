"""
Add Contract Page

This page allows users to add new contracts with related information.
"""

import streamlit as st
import sys
import os
import tempfile
import base64
import streamlit.components.v1 as components
import whisper
import logging
import shutil

# Add parent directory to path to import utils
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from utils import get_data, get_form_config, save_to_sheets, save_field_config, load_field_config

import json
import traceback
from collections import defaultdict

logger = logging.getLogger(__name__)

@st.cache_resource
def load_whisper_model():
    logger.info("Caricamento del modello Whisper...")
    model = whisper.load_model("base")
    logger.info("Modello Whisper caricato.")
    return model

def extract_fields_with_openai(transcript, field_names, openai_api_key):
    prompt = f"Estrarre i seguenti campi da questo testo e restituire un dizionario JSON con i valori. Campi: {', '.join(field_names)}. Testo: {transcript}"
    
    # Usa la nuova sintassi OpenAI
    from openai import OpenAI
    client = OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    try:
        data = json.loads(response.choices[0].message.content)
    except Exception:
        data = {}
    return data

# Custom audio recorder component
def st_audiorec():
    """Custom audio recorder component using HTML5 audio API"""
    audio_html = """
        <div>
            <audio id="audio" controls></audio>
            <button id="recordButton">Start Recording</button>
            <button id="stopButton" disabled>Stop Recording</button>
        </div>
        <script>
            let mediaRecorder;
            let audioChunks = [];
            const recordButton = document.getElementById('recordButton');
            const stopButton = document.getElementById('stopButton');
            const audio = document.getElementById('audio');

            recordButton.onclick = async () => {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    audio.src = audioUrl;
                    
                    // Convert blob to base64 and send to Streamlit
                    const reader = new FileReader();
                    reader.readAsDataURL(audioBlob);
                    reader.onloadend = () => {
                        const base64data = reader.result;
                        window.parent.postMessage({
                            type: 'audio_data',
                            data: base64data
                        }, '*');
                    };
                };
                
                mediaRecorder.start();
                recordButton.disabled = true;
                stopButton.disabled = false;
            };
            
            stopButton.onclick = () => {
                mediaRecorder.stop();
                recordButton.disabled = false;
                stopButton.disabled = true;
            };
        </script>
    """
    components.html(audio_html, height=100)
    
    # Listen for messages from the component
    audio_data = None
    if 'audio_data' in st.session_state:
        audio_data = st.session_state.audio_data
        del st.session_state.audio_data
    
    return audio_data

def format_number_for_italian(val):
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        else:
            return str(val).replace('.', ',')
    elif isinstance(val, int):
        return str(val)
    return val

def format_boolean_for_italian(val):
    """Convert boolean values to Italian format for Google Sheets"""
    if isinstance(val, bool):
        return "SI" if val else "NO"
    elif isinstance(val, str):
        val_lower = val.lower().strip()
        if val_lower in ['true', 'vero', 'si', 'yes', '1']:
            return "SI"
        elif val_lower in ['false', 'falso', 'no', '0']:
            return "NO"
    return val

def render_section(section_name, fields):
    """Render a section of the form e salva i dati in session_state"""
    st.subheader(section_name.title())
    
    # Inizializza la sezione in session_state se non esiste
    if "contract_data" not in st.session_state:
        st.session_state.contract_data = {}
    if section_name not in st.session_state.contract_data:
        st.session_state.contract_data[section_name] = {}

    # Get unique values for each field
    unique_values = {}
    try:
        df = get_data(section_name)
        if not df.empty:
            for field in fields:
                if field.get("visible", True) and field["name"] in df.columns:
                    vals = df[field["name"]].dropna().unique()
                    vals = [v for v in vals if str(v).strip() != ""]
                    unique_values[field["name"]] = vals
    except Exception as e:
        logger.error(f"Error getting unique values: {str(e)}")
        st.warning("Impossibile caricare i valori esistenti. I campi saranno vuoti.")

    # Gestione speciale per proprietari
    if section_name == "proprietari":
        if "proprietari" not in st.session_state:
            st.session_state.proprietari = [{}]
        
        for i, proprietario in enumerate(st.session_state.proprietari):
            st.markdown(f"### Proprietario {i+1}")
    for field in fields:
                if not field.get("visible", True):
                    continue
        field_name = field["name"]
        field_type = field.get("type", "testo")
        field_label = field.get("label", field_name)
        vals = unique_values.get(field_name, [])
                try:
                    if field_type == "testo":
        if field.get("dropdown", False):
            options = [v for v in vals if str(v).strip() != ""] + ["Altro..."]
            selected = st.selectbox(
                field_label,
                options=options,
                                key=f"{section_name}_{field_name}_{i}"
            )
            if selected == "Altro...":
                value = st.text_input(
                    f"Specifica {field_label}",
                                    key=f"{section_name}_{field_name}_{i}_other"
                )
            else:
                value = selected
                        else:
                            value = st.text_input(
                                field_label,
                                key=f"{section_name}_{field_name}_{i}"
                            )
                        st.session_state.proprietari[i][field_name] = value
                    elif field_type == "numero":
                        try:
                            default = float(vals[0].replace(',', '.')) if vals else 0.0
                        except (ValueError, TypeError):
                            default = 0.0
                        value = st.number_input(
                            field_label,
                            value=default,
                            key=f"{section_name}_{field_name}_{i}"
                        )
                        st.session_state.proprietari[i][field_name] = value
                    elif field_type == "boolean":
                        default_value = False
                        if vals:
                            try:
                                if str(vals[0]).lower() in ['true', 'vero', 'si', 'yes', '1']:
                                    default_value = True
                                elif str(vals[0]).lower() in ['false', 'falso', 'no', '0']:
                                    default_value = False
                            except:
                                default_value = False
                        value = st.checkbox(
                            field_label,
                            value=default_value,
                            key=f"{section_name}_{field_name}_{i}"
                        )
                        st.session_state.proprietari[i][field_name] = value
                except Exception as e:
                    logger.error(f"Error rendering field {field_name}: {str(e)}")
                    st.error(f"Errore nel rendering del campo {field_label}")
            if i > 0:
                if st.button(f"❌ Rimuovi Proprietario {i+1}", key=f"remove_owner_{i}"):
                    st.session_state.proprietari.pop(i)
                    st.experimental_rerun()
        if st.button("➕ Aggiungi Proprietario"):
            st.session_state.proprietari.append({})
            st.experimental_rerun()
        return

    # Gestione speciale per vicini nella sezione contatti
    if section_name == "contatti":
        if "vicini" not in st.session_state:
            st.session_state.vicini = [{"nome": "", "numero": ""}]
        
        # Prima renderizza i campi normali dei contatti
        for field in fields:
            if not field.get("visible", True):
                continue
            field_name = field["name"]
            field_type = field.get("type", "testo")
            field_label = field.get("label", field_name)
            vals = unique_values.get(field_name, [])
            
            try:
                # Forza tutti i campi della sezione contatti a essere text_input, tranne upload/file
                if field_type in ["foto", "video"]:
                    if field_type == "foto":
                        value = st.file_uploader(
                            field_label,
                            type=["jpg", "jpeg", "png"],
                            key=f"{section_name}_{field_name}"
                        )
                    elif field_type == "video":
                        value = st.file_uploader(
                            field_label,
                            type=["mp4", "mov"],
                            key=f"{section_name}_{field_name}"
                        )
                    st.session_state.contract_data[section_name][field_name] = value
        else:
            value = st.text_input(
                field_label,
                key=f"{section_name}_{field_name}"
            )
        st.session_state.contract_data[section_name][field_name] = value
            except Exception as e:
                logger.error(f"Error rendering field {field_name}: {str(e)}")
                st.error(f"Errore nel rendering del campo {field_label}")
        
        # Poi renderizza la sezione dei vicini
        st.markdown("### Vicini")
        for i, vicino in enumerate(st.session_state.vicini):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input(
                    f"Nome Vicino {i+1}",
                    value=vicino.get("nome", ""),
                    key=f"vicino_nome_{i}"
                )
            with col2:
                numero = st.text_input(
                    f"Numero Vicino {i+1}",
                    value=vicino.get("numero", ""),
                    key=f"vicino_numero_{i}"
                )
            st.session_state.vicini[i] = {"nome": nome, "numero": numero}
            
            if i > 0:  # Non mostrare il pulsante di rimozione per il primo vicino
                if st.button(f"❌ Rimuovi Vicino {i+1}", key=f"remove_neighbor_{i}"):
                    st.session_state.vicini.pop(i)
                    st.experimental_rerun()
        
        if st.button("➕ Aggiungi Vicino"):
            st.session_state.vicini.append({"nome": "", "numero": ""})
            st.experimental_rerun()
        return

    # Gestione standard per altre sezioni
    for field in fields:
        if not field.get("visible", True):
            continue
        field_name = field["name"]
        field_type = field.get("type", "testo")
        field_label = field.get("label", field_name)
        vals = unique_values.get(field_name, [])
        try:
            if field_type == "testo":
                if field.get("dropdown", False):
                    options = [v for v in vals if str(v).strip() != ""] + ["Altro..."]
                    selected = st.selectbox(
                        field_label,
                        options=options,
                        key=f"{section_name}_{field_name}"
                    )
                    if selected == "Altro...":
                        value = st.text_input(
                            f"Specifica {field_label}",
                            key=f"{section_name}_{field_name}_other"
                        )
                    else:
                        value = selected
                else:
                    value = st.text_input(
                        field_label,
                        key=f"{section_name}_{field_name}"
                    )
                st.session_state.contract_data[section_name][field_name] = value
            elif field_type == "numero":
                try:
                    default = float(vals[0].replace(',', '.')) if vals else 0.0
                except (ValueError, TypeError):
                    default = 0.0
                value = st.number_input(
                    field_label,
                    value=default,
                    key=f"{section_name}_{field_name}"
                )
                st.session_state.contract_data[section_name][field_name] = value
            elif field_type == "foto":
                value = st.file_uploader(
                    field_label,
                    type=["jpg", "jpeg", "png"],
                    key=f"{section_name}_{field_name}"
                )
                st.session_state.contract_data[section_name][field_name] = value
            elif field_type == "video":
                value = st.file_uploader(
                    field_label,
                    type=["mp4", "mov"],
                    key=f"{section_name}_{field_name}"
                )
                st.session_state.contract_data[section_name][field_name] = value
            elif field_type == "boolean":
                # Get default value from existing data or default to False
                default_value = False
                if vals:
                    try:
                        # Try to convert existing values to boolean
                        if str(vals[0]).lower() in ['true', 'vero', 'si', 'yes', '1']:
                            default_value = True
                        elif str(vals[0]).lower() in ['false', 'falso', 'no', '0']:
                            default_value = False
                    except:
                        default_value = False
                
                value = st.checkbox(
                    field_label,
                    value=default_value,
                    key=f"{section_name}_{field_name}"
                )
                st.session_state.contract_data[section_name][field_name] = value
        except Exception as e:
            logger.error(f"Error rendering field {field_name}: {str(e)}")
            st.error(f"Errore nel rendering del campo {field_label}")

def main():
    """Add Contract page"""
    try:
        logger.info("Starting Add Contract page")
        st.title("📄 Nuovo Contratto")

        # --- BLOCCO REGISTRAZIONE E AI ---
        st.subheader("Compilazione vocale automatica")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            st.warning("Chiave OpenAI API non trovata nel file .env. La funzionalità di elaborazione vocale non sarà disponibile.")
        else:
            st.markdown("Clicca l'icona del microfono per registrare le informazioni del contratto, poi clicca di nuovo per fermare.")
            wav_audio_data = st_audiorec()

            if wav_audio_data is not None:
                st.audio(wav_audio_data, format='audio/wav')
                st.success("Audio registrato!")
                logger.info("Audio registrato con st-audiorec.")

                # Usa un file temporaneo in una directory temporanea
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_filename = temp_file.name
                    temp_file.write(wav_audio_data)
                
                try:
                    # Trascrizione con Whisper
                    whisper_model = load_whisper_model()
                    st.info("Trascrizione dell'audio in corso...")
                    logger.info(f"Inizio trascrizione di {temp_filename}...")
                    result = whisper_model.transcribe(temp_filename, fp16=False)
                    transcription_text = result["text"]
                    st.session_state.audio_transcript = transcription_text
                    st.session_state.audio_transcribed = True
                    st.subheader("Testo Trascritto:")
                    st.write(transcription_text)
                    logger.info(f"Trascrizione completata: {transcription_text}")

                    # Estrazione campi con OpenAI
                    if st.session_state.get("audio_transcribed") and st.session_state.audio_transcript:
                        st.info("Estrazione dei campi dalla trascrizione...")
                        # Ottieni i nomi dei campi dalle configurazioni
                        field_names_for_extraction = []
                        for section in ["contratti", "proprietari", "contatti"]:
                            config = get_form_config(section)
                            if config and "fields" in config:
                                field_names_for_extraction.extend([f["name"] for f in config["fields"] if f.get("visible", True)])
                        
                        extracted_data = extract_fields_with_openai(st.session_state.audio_transcript, field_names_for_extraction, openai_api_key)
                        logger.info(f"Dati estratti: {extracted_data}")
                        st.session_state.audio_extracted = extracted_data
                        st.subheader("Dati Estratti:")
                        st.json(extracted_data)
                        
                        # Popola i campi del form
                        for section in ["contratti", "proprietari", "contatti"]:
                            if section not in st.session_state.contract_data:
                                st.session_state.contract_data[section] = {}
                            config = get_form_config(section)
                            if config and "fields" in config:
                                for field in config["fields"]:
                                    if field["name"] in extracted_data:
                                        if section == "proprietari":
                                            # Per i proprietari, crea un nuovo proprietario con i dati estratti
                                            if "proprietari" not in st.session_state:
                                                st.session_state.proprietari = []
                                            st.session_state.proprietari.append({field["name"]: extracted_data[field["name"]]})
                                        else:
                                            st.session_state.contract_data[section][field["name"]] = extracted_data[field["name"]]
                                        logger.info(f"Impostato st.session_state.contract_data[{section}][{field['name']}] = {extracted_data[field['name']]}")
                        
                        st.success("Campi del modulo pre-compilati con i dati estratti!")
                        st.experimental_rerun()

                except Exception as e:
                    logger.error(f"Errore durante la trascrizione con Whisper: {e}")
                    st.error(f"Errore durante la trascrizione: {e}")
                    st.session_state.audio_transcribed = False
                finally:
                    # Pulisci il file temporaneo
                    try:
                        os.unlink(temp_filename)
                    except Exception as e:
                        logger.error(f"Errore durante la pulizia del file temporaneo: {e}")

        # --- RESTO DEL MAIN ORIGINALE ---
        # Initialize session state
        if "contract_data" not in st.session_state:
            st.session_state.contract_data = {}
        # Contract name input at the top
        contract_name = st.text_input("Nome del Contratto/Appartamento", key="contract_name")
        if not contract_name:
            st.warning("⚠️ Inserisci il nome del contratto/appartamento per continuare")
            return
        # Store contract name in session state
        st.session_state.contract_data["contract_name"] = contract_name
        st.session_state.contract_data["apartment_name"] = contract_name
        # Create tabs for different sections
        tab1, tab2, tab3 = st.tabs([
            "📄 Contratto",
            "👤 Proprietari",
            "👥 Contatti"
        ])
        # Contratto Tab
        with tab1:
            contract_config = get_form_config("contratti")
            if contract_config:
                render_section("contratti", contract_config["fields"])
            else:
                st.error("Errore nel caricamento della configurazione del contratto")
        # Proprietari Tab
        with tab2:
            owner_config = get_form_config("proprietari")
            if owner_config:
                render_section("proprietari", owner_config["fields"])
            else:
                st.error("Errore nel caricamento della configurazione del proprietario")
        # Contatti Tab
        with tab3:
            contacts_config = get_form_config("contatti")
            if contacts_config:
                # Filtra i campi che iniziano per 'Vicino' o 'Numero Vicino' (case insensitive, spazi inclusi)
                filtered_fields = [f for f in contacts_config["fields"] if not (f["name"].strip().lower().startswith("vicino") or f["name"].strip().lower().startswith("numero vicino"))]
                render_section("contatti", filtered_fields)
            else:
                st.error("Errore nel caricamento della configurazione dei contatti")
        # Save button at the bottom
        st.markdown("---")
        if st.button("💾 Salva Contratto", use_container_width=True):
            try:
                # Save contract data
                contract_data = st.session_state.contract_data["contratti"].copy()
                contract_data["appartamento"] = contract_name
                # Format numerics
                contratti_config = get_form_config("contratti")
                if contratti_config:
                    for f in contratti_config["fields"]:
                        if f.get("type") == "numero":
                            k = f["name"]
                            if k in contract_data:
                                contract_data[k] = format_number_for_italian(contract_data[k])
                        elif f.get("type") == "boolean":
                            k = f["name"]
                            if k in contract_data:
                                contract_data[k] = format_boolean_for_italian(contract_data[k])
                if save_to_sheets("contratti", contract_data):
                    st.success("Contratto salvato con successo!")
                else:
                    st.error("Errore nel salvataggio del contratto")
                # Save owners data
                for owner in st.session_state.get("proprietari", []):
                    owner_data = owner.copy()
                    owner_data["appartamento"] = contract_name
                    # Format boolean fields for owners
                    proprietari_config = get_form_config("proprietari")
                    if proprietari_config:
                        for f in proprietari_config["fields"]:
                            if f.get("type") == "boolean":
                                k = f["name"]
                                if k in owner_data:
                                    owner_data[k] = format_boolean_for_italian(owner_data[k])
                    if save_to_sheets("proprietari", owner_data):
                        st.success(f"Proprietario salvato con successo!")
                    else:
                        st.error(f"Errore nel salvataggio del proprietario")
                # Save contacts data
                contacts_data = st.session_state.contract_data["contatti"].copy()
                contacts_data["appartamento"] = contract_name
                # Format numerics for contacts
                contatti_config = get_form_config("contatti")
                if contatti_config:
                    for f in contatti_config["fields"]:
                        if f.get("type") == "numero" and "telefono" not in f["name"].lower():
                            k = f["name"]
                            if k in contacts_data:
                                contacts_data[k] = format_number_for_italian(contacts_data[k])
                # Add neighbors data
                for i, vicino in enumerate(st.session_state.get("vicini", []), 1):
                    contacts_data[f"Vicino {i}"] = vicino.get("nome", "")
                    contacts_data[f"Numero vicino {i}"] = vicino.get("numero", "")
                if save_to_sheets("contatti", contacts_data):
                    st.success("Dati contatti salvati con successo!")
                else:
                    st.error("Errore nel salvataggio dei dati dei contatti")
            except Exception as e:
                logger.error(f"Error saving data: {str(e)}")
                st.error(f"Errore nel salvataggio: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in main function: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        st.error("Si è verificato un errore imprevisto. Controlla i log per maggiori dettagli.")

if __name__ == "__main__":
    main() 