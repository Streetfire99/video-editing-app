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
    """Estrae i campi dalla trascrizione usando AI intelligente e contestuale"""
    
    # Crea un prompt più intelligente e strutturato
    system_prompt = """Sei un assistente AI specializzato nell'estrazione di informazioni da trascrizioni vocali di contratti immobiliari.

Il tuo compito è analizzare il testo e estrarre i valori per i campi specificati, considerando il contesto immobiliare.

ISTRUZIONI:
1. Analizza attentamente il testo per identificare informazioni sui contratti, proprietari e contatti
2. Per ogni campo, cerca la risposta più appropriata nel testo
3. Se un'informazione non è presente, usa "Non specificato"
4. Per i numeri, mantieni il formato originale (es. "1500 euro", "€1500")
5. Per i booleani, interpreta "si/no", "vero/falso", "presente/assente"
6. Per le date, usa il formato DD/MM/YYYY se possibile
7. Restituisci SEMPRE un JSON valido con tutti i campi richiesti

FORMATO OUTPUT:
{
    "campo1": "valore1",
    "campo2": "valore2",
    ...
}

CONTESTO IMMOBILIARE:
- I contratti riguardano affitti, vendite, gestione di appartamenti
- I proprietari sono persone fisiche o giuridiche che possiedono l'immobile
- I contatti includono informazioni di comunicazione e vicini"""

    user_prompt = f"""
Campi da estrarre: {', '.join(field_names)}

Trascrizione audio:
{transcript}

Analizza il testo e estrai i valori per ogni campo. Se un'informazione non è chiara o mancante, usa "Non specificato".

Rispondi SOLO con il JSON, senza testo aggiuntivo."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        # Parsa la risposta JSON
        try:
            data = json.loads(response.choices[0].message.content.strip())
            return data
        except json.JSONDecodeError:
            # Se il parsing JSON fallisce, prova a estrarre il JSON dal testo
            import re
            json_match = re.search(r'\{.*\}', response.choices[0].message.content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            
            # Fallback: crea un dizionario vuoto
            logger.warning("Impossibile parsare la risposta AI, creo dizionario vuoto")
            return {field: "Non specificato" for field in field_names}
            
    except Exception as e:
        logger.error(f"Errore nell'estrazione AI: {e}")
        # Fallback: crea un dizionario vuoto
        return {field: "Non specificato" for field in field_names}

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

    # Controlla se ci sono campi compilati automaticamente
    auto_populated_fields = set()
    if st.session_state.get("audio_extracted"):
        for field_name in st.session_state.audio_extracted.keys():
            if field_name in [f["name"] for f in fields]:
                auto_populated_fields.add(field_name)
    
    if auto_populated_fields:
        st.success(f"🎤 **{len(auto_populated_fields)} campi compilati automaticamente** in questa sezione")

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
                            # Mostra indicatore se il campo è stato compilato automaticamente
                            is_auto_populated = field_name in auto_populated_fields
                            if is_auto_populated:
                                st.info(f"🎤 Campo compilato automaticamente dalla registrazione vocale")
                            
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
        
        # Mostra indicatore se il campo è stato compilato automaticamente
        is_auto_populated = field_name in auto_populated_fields
        if is_auto_populated:
            st.info(f"🎤 Campo '{field_label}' compilato automaticamente dalla registrazione vocale")
        
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
        
        # Configurazione della pagina
        st.set_page_config(
            page_title="📄 Add Contract",
            page_icon="📄",
            layout="wide"
        )
        
        st.title("📄 Nuovo Contratto")

        # --- BLOCCO REGISTRAZIONE E AI ---
        st.subheader("🎤 Compilazione vocale automatica")
        
        # Controlla se l'API key è disponibile
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            st.warning("⚠️ Chiave OpenAI API non trovata nel file .env. La funzionalità di elaborazione vocale non sarà disponibile.")
        else:
            st.success("✅ OpenAI API disponibile - Registrazione vocale attiva!")
            
            # Mostra istruzioni chiare
            st.info("""
            **📋 Come registrare:**
            1. 🎤 **Clicca l'icona del microfono** per iniziare la registrazione
            2. 🗣️ **Parla chiaramente** descrivendo il contratto, proprietari e contatti
            3. 🛑 **Clicca di nuovo** per fermare la registrazione
            4. 🤖 **L'AI analizzerà** automaticamente e compilerà i campi
            """)
            
            # Area di registrazione
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("### 🎤 Registrazione")
                wav_audio_data = st_audiorec()
                
                if wav_audio_data is not None:
                    st.audio(wav_audio_data, format='audio/wav')
                    st.success("✅ Audio registrato con successo!")
                    logger.info("Audio registrato con st-audiorec.")
                    
                    # Pulsante per processare l'audio
                    if st.button("🚀 Processa Audio con AI", type="primary"):
                        with st.spinner("🔄 Elaborazione in corso..."):
                            try:
                                # Usa un file temporaneo in una directory temporanea
                                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                                    temp_filename = temp_file.name
                                    temp_file.write(wav_audio_data)
                                
                                # Step 1: Trascrizione con Whisper
                                st.info("📝 Trascrizione dell'audio in corso...")
                                logger.info(f"Inizio trascrizione di {temp_filename}...")
                                
                                whisper_model = load_whisper_model()
                                result = whisper_model.transcribe(temp_filename, fp16=False)
                                transcription_text = result["text"]
                                
                                if transcription_text.strip():
                                    st.session_state.audio_transcript = transcription_text
                                    st.session_state.audio_transcribed = True
                                    
                                    st.success("✅ Trascrizione completata!")
                                    st.markdown("**📝 Testo trascritto:**")
                                    st.text_area("Trascrizione", value=transcription_text, height=150, disabled=True)
                                    
                                    # Step 2: Estrazione campi con OpenAI
                                    st.info("🤖 Analisi AI e estrazione campi...")
                                    
                                    # Ottieni i nomi dei campi dalle configurazioni
                                    field_names_for_extraction = []
                                    for section in ["contratti", "proprietari", "contatti"]:
                                        config = get_form_config(section)
                                        if config and "fields" in config:
                                            field_names_for_extraction.extend([f["name"] for f in config["fields"] if f.get("visible", True)])
                                    
                                    if field_names_for_extraction:
                                        extracted_data = extract_fields_with_openai(transcription_text, field_names_for_extraction, openai_api_key)
                                        
                                        if extracted_data:
                                            logger.info(f"Dati estratti: {extracted_data}")
                                            st.session_state.audio_extracted = extracted_data
                                            
                                            st.success("✅ Analisi AI completata!")
                                            st.markdown("**🔍 Dati estratti:**")
                                            st.json(extracted_data)
                                            
                                            # Step 3: Popola i campi del form
                                            st.info("📋 Compilazione automatica dei campi...")
                                            
                                            fields_populated = 0
                                            for section in ["contratti", "proprietari", "contatti"]:
                                                if section not in st.session_state.contract_data:
                                                    st.session_state.contract_data[section] = {}
                                                
                                                config = get_form_config(section)
                                                if config and "fields" in config:
                                                    for field in config["fields"]:
                                                        if field["name"] in extracted_data:
                                                            value = extracted_data[field["name"]]
                                                            if value != "Non specificato":
                                                                if section == "proprietari":
                                                                    # Per i proprietari, crea un nuovo proprietario con i dati estratti
                                                                    if "proprietari" not in st.session_state:
                                                                        st.session_state.proprietari = []
                                                                    st.session_state.proprietari.append({field["name"]: value})
                                                                else:
                                                                    st.session_state.contract_data[section][field["name"]] = value
                                                                fields_populated += 1
                                                                logger.info(f"Campo popolato: {section}.{field['name']} = {value}")
                                            
                                            if fields_populated > 0:
                                                st.success(f"🎉 {fields_populated} campi compilati automaticamente!")
                                                st.info("💡 I campi sono ora pre-compilati nei tab sottostanti. Puoi modificarli se necessario.")
                                                st.rerun()
                                            else:
                                                st.warning("⚠️ Nessun campo è stato compilato automaticamente. Controlla la trascrizione.")
                                        else:
                                            st.error("❌ Errore nell'estrazione dei dati con AI")
                                    else:
                                        st.error("❌ Nessun campo trovato nelle configurazioni")
                                else:
                                    st.error("❌ La trascrizione è vuota. Riprova a registrare l'audio.")
                                    
                            except Exception as e:
                                logger.error(f"Errore durante l'elaborazione audio: {e}")
                                st.error(f"❌ Errore durante l'elaborazione: {e}")
                                st.session_state.audio_transcribed = False
                            finally:
                                # Pulisci il file temporaneo
                                try:
                                    if 'temp_filename' in locals():
                                        os.unlink(temp_filename)
                                except Exception as e:
                                    logger.error(f"Errore durante la pulizia del file temporaneo: {e}")
                else:
                    st.info("🎤 Clicca l'icona del microfono per iniziare la registrazione")
            
            with col2:
                st.markdown("### 📊 Stato Elaborazione")
                
                # Mostra lo stato dell'elaborazione
                if st.session_state.get("audio_transcribed", False):
                    st.success("✅ Audio trascritto")
                    
                    if st.session_state.get("audio_extracted"):
                        st.success("✅ Dati estratti")
                        st.success("✅ Campi compilati")
                    else:
                        st.info("⏳ In attesa di estrazione AI")
                else:
                    st.info("⏳ In attesa di registrazione")
                
                # Mostra statistiche
                if st.session_state.get("audio_transcript"):
                    st.markdown("**📊 Statistiche:**")
                    transcript_length = len(st.session_state.audio_transcript)
                    st.metric("Caratteri trascritti", transcript_length)
                    
                    if transcript_length > 100:
                        st.success("✅ Trascrizione sufficiente per analisi AI")
                    elif transcript_length > 50:
                        st.warning("⚠️ Trascrizione breve, potrebbe non essere sufficiente")
                    else:
                        st.error("❌ Trascrizione troppo breve")
                
                # Pulsante per pulire la sessione audio
                if st.session_state.get("audio_transcript") or st.session_state.get("audio_extracted"):
                    if st.button("🗑️ Pulisci Sessione Audio"):
                        st.session_state.audio_transcript = None
                        st.session_state.audio_transcribed = False
                        st.session_state.audio_extracted = None
                        st.rerun()

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
        
        # Mostra indicatori per campi compilati automaticamente
        if st.session_state.get("audio_extracted"):
            st.info(f"🎤 **{len(st.session_state.audio_extracted)} campi estratti dalla registrazione vocale** - I campi sono pre-compilati nei tab sottostanti")
        
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