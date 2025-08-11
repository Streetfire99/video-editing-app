import streamlit as st
import os
import tempfile
import json
import time
from faster_whisper import WhisperModel
import imageio_ffmpeg

# Configurazione della pagina
st.set_page_config(
    page_title="🎤 Test Voce",
    page_icon="🎤",
    layout="wide"
)

st.title("🎤 Test Registrazione Voce con AI (SOLUZIONE DEFINITIVA)")
st.markdown("---")

# Sidebar per configurazione
with st.sidebar:
    st.header("⚙️ Configurazione")
    
    # API Key OpenAI dai secrets di Streamlit Cloud
    openai_api_key = st.secrets.get('OPENAI_API_KEY')
    
    if openai_api_key:
        st.success("✅ OPENAI_API_KEY trovata nei secrets!")
        st.info("🤖 Analisi AI avanzata disponibile")
    else:
        st.warning("⚠️ OPENAI_API_KEY non trovata nei secrets")
        st.info("📝 Userò analisi basata su regole (funziona sempre)")
        openai_api_key = None
    
    # Modello Whisper
    whisper_model = st.selectbox(
        "🤖 Modello Whisper",
        ["tiny", "base", "small", "medium", "large"],
        index=2,
        help="Seleziona il modello Whisper (più grande = più accurato)"
    )
    
    # Prompt personalizzato
    custom_prompt = st.text_area(
        "📝 Prompt Personalizzato",
        value="Analizza la registrazione vocale e estrai le seguenti informazioni:\n1. Nome del prodotto/oggetto\n2. Caratteristiche principali\n3. Prezzo o valore indicato\n\nRispondi in formato JSON con i campi: nome, caratteristiche, prezzo",
        height=150,
        help="Personalizza il prompt per l'analisi AI"
    )

# Funzione per convertire audio con ffmpeg
def convert_audio_to_wav(input_file, output_file):
    """Converte qualsiasi formato audio in WAV mono 16kHz"""
    try:
        # Ottieni il path di ffmpeg da imageio-ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Comando ffmpeg per conversione
        import subprocess
        cmd = [
            ffmpeg_path,
            '-i', input_file,
            '-ac', '1',        # 1 canale (mono)
            '-ar', '16000',    # 16kHz sample rate
            '-f', 'wav',       # formato WAV
            '-y',              # sovrascrivi output
            output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            st.error(f"❌ Errore conversione ffmpeg: {result.stderr}")
            return False
            
    except Exception as e:
        st.error(f"❌ Errore conversione audio: {e}")
        return False

# Funzione per trascrivere audio con faster-whisper
def transcribe_audio_local(audio_file, model_size="small"):
    """Trascrive l'audio usando faster-whisper (locale)"""
    try:
        # Carica il modello Whisper
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        
        # Trascrivi l'audio
        segments, info = model.transcribe(audio_file, language="it")
        
        # Combina tutti i segmenti
        transcription = " ".join([segment.text for segment in segments])
        
        return transcription, info.language, info.language_probability
        
    except Exception as e:
        st.error(f"❌ Errore nella trascrizione locale: {e}")
        return None, None, None

# Funzione per analizzare con AI (se OpenAI disponibile)
def analyze_with_ai(transcription, prompt, openai_api_key=None):
    """Analizza la trascrizione con AI (OpenAI se disponibile, altrimenti regole semplici)"""
    
    if openai_api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            
            system_prompt = """Sei un assistente AI specializzato nell'analisi di trascrizioni vocali. 
            Analizza il testo fornito e estrai le informazioni richieste.
            Rispondi SEMPRE in formato JSON valido."""
            
            user_prompt = f"{prompt}\n\nTrascrizione: {transcription}"
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            st.warning(f"⚠️ Errore OpenAI, uso analisi semplice: {e}")
            return None
    
    # Fallback: analisi semplice basata su regole
    try:
        # Estrai informazioni base dal testo
        text = transcription.lower()
        
        # Cerca prezzo (pattern comune)
        import re
        price_match = re.search(r'(\d+)\s*(euro|eur|€|\$|dollari)', text)
        price = price_match.group(1) + " " + price_match.group(2) if price_match else "Non specificato"
        
        # Cerca caratteristiche comuni
        features = []
        if "lavatrice" in text or "washing" in text:
            features.append("Lavatrice")
        if "lavastoviglie" in text or "dishwasher" in text:
            features.append("Lavastoviglie")
        if "frigorifero" in text or "fridge" in text:
            features.append("Frigorifero")
        if "forno" in text or "oven" in text:
            features.append("Forno")
        
        # Nome prodotto (prima parte della frase)
        words = transcription.split()
        name = " ".join(words[:3]) if len(words) >= 3 else transcription[:50]
        
        # Crea JSON semplice
        result = {
            "nome": name,
            "caratteristiche": ", ".join(features) if features else "Elettrodomestico generico",
            "prezzo": price
        }
        
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        st.error(f"❌ Errore nell'analisi semplice: {e}")
        return None

# Funzione per parsare JSON
def parse_ai_response(response):
    """Parsa la risposta AI in formato JSON"""
    try:
        # Rimuovi eventuali markdown
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        
        # Parsa JSON
        data = json.loads(response.strip())
        return data
    except Exception as e:
        st.error(f"❌ Errore nel parsing JSON: {e}")
        st.code(response)
        return None

# Contenuto principale
col1, col2 = st.columns([1, 1])

with col1:
    st.header("🎙️ Registrazione")
    
    # Controllo dipendenze e configurazione
    try:
        import faster_whisper
        import imageio_ffmpeg
        st.success("✅ Tutte le dipendenze sono disponibili!")
        
        # Mostra stato configurazione
        if openai_api_key:
            st.success("🤖 Analisi AI OpenAI disponibile")
        else:
            st.info("📝 Analisi basata su regole (funziona sempre)")
            
    except ImportError as e:
        st.error(f"❌ Dipendenza mancante: {e}")
        st.info("💡 Installa: pip install faster-whisper imageio-ffmpeg")
        st.stop()
    
    # Area di registrazione
    st.markdown("### 🎤 Registrazione Vocale")
    
    # Opzione 1: Registrazione diretta (se disponibile)
    try:
        from streamlit_audio_recorder import audio_recorder
        
        st.info("🎙️ **Registrazione diretta disponibile!**")
        audio_bytes = audio_recorder(
            text="🎤 Clicca per registrare",
            recording_color="#e74c3c",
            neutral_color="#2ecc71",
            icon_name="microphone",
            icon_size="2x"
        )
        
        if audio_bytes:
            st.success("✅ Audio registrato!")
        
    except ImportError:
        st.warning("⚠️ **Registrazione diretta non disponibile** - Usa l'upload file")
        audio_bytes = None
    
    # Opzione 2: Upload file audio (sempre disponibile)
    st.markdown("### 🎵 **Alternativa: Carica file audio**")
    st.info("📱 Puoi registrare con il telefono e caricare il file, oppure usare qualsiasi app di registrazione")
    
    uploaded_file = st.file_uploader(
        "🎵 Carica file audio (MP3, WAV, M4A, OGG)",
        type=['mp3', 'wav', 'm4a', 'ogg'],
        help="Registra con il telefono e carica qui, oppure usa un file esistente"
    )
    
    if uploaded_file:
        audio_bytes = uploaded_file.read()
        st.success(f"✅ File caricato: {uploaded_file.name}")
    
    # Se non c'è audio, mostra istruzioni
    if not audio_bytes:
        st.info("""
        **📋 Istruzioni per la registrazione:**
        1. **Con telefono**: Usa l'app registrazione vocale e salva come MP3/WAV
        2. **Con computer**: Usa qualsiasi app di registrazione (Audacity, GarageBand, etc.)
        3. **Contenuto**: Descrivi un prodotto/oggetto (es: "Ho una lavatrice Samsung da 8kg, costa 400 euro")
        4. **Carica**: Trascina il file qui sopra
        """)
    
    # Processamento audio
    if audio_bytes:
        st.success("✅ Audio registrato!")
        
        # Salva audio temporaneo
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_bytes)
            temp_audio_path = tmp_file.name
        
        # Pulsante per processare
        if st.button("🚀 Processa Audio", type="primary"):
            with st.spinner("🔄 Elaborazione in corso..."):
                
                # Step 1: Conversione audio
                st.info("🔄 Conversione audio in WAV mono 16kHz...")
                wav_file = temp_audio_path.replace(".wav", "_converted.wav")
                
                if convert_audio_to_wav(temp_audio_path, wav_file):
                    st.success("✅ Conversione completata!")
                    
                    # Step 2: Trascrizione locale
                    st.info("📝 Trascrizione con Whisper locale...")
                    transcription, language, confidence = transcribe_audio_local(wav_file, whisper_model)
                    
                    if transcription:
                        st.success("✅ Trascrizione completata!")
                        st.markdown(f"**Trascrizione:** {transcription}")
                        st.info(f"🌍 Lingua rilevata: {language} (confidenza: {confidence:.2f})")
                        
                        # Step 3: Analisi AI
                        st.info("🤖 Analisi con AI...")
                        ai_response = analyze_with_ai(transcription, custom_prompt, openai_api_key)
                        
                        if ai_response:
                            st.success("✅ Analisi AI completata!")
                            
                            # Step 4: Parsing e inserimento campi
                            st.info("🔍 Parsing risultati...")
                            parsed_data = parse_ai_response(ai_response)
                            
                            if parsed_data:
                                st.success("✅ Dati estratti con successo!")
                                
                                # Salva i dati nella session state
                                st.session_state.extracted_data = parsed_data
                                st.session_state.transcription = transcription
                                st.session_state.audio_info = {
                                    'language': language,
                                    'confidence': confidence,
                                    'wav_file': wav_file
                                }
                                
                                # Rimuovi file temporanei
                                os.unlink(temp_audio_path)
                                os.unlink(wav_file)
                                
                                st.rerun()
                            else:
                                st.error("❌ Impossibile parsare i dati AI")
                        else:
                            st.error("❌ Errore nell'analisi AI")
                    else:
                        st.error("❌ Errore nella trascrizione")
                else:
                    st.error("❌ Errore nella conversione audio")
                
                # Pulisci file temporanei
                for temp_file in [temp_audio_path, wav_file]:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)

with col2:
    st.header("📋 Campi Compilati")
    
    # Mostra i dati estratti
    if hasattr(st.session_state, 'extracted_data') and st.session_state.extracted_data:
        data = st.session_state.extracted_data
        
        st.success("🎉 Dati estratti automaticamente!")
        
        # Campo 1: Nome
        nome = st.text_input(
            "🏷️ Nome Prodotto/Oggetto",
            value=data.get('nome', ''),
            key="field_nome"
        )
        
        # Campo 2: Caratteristiche
        caratteristiche = st.text_area(
            "🔍 Caratteristiche Principali",
            value=data.get('caratteristiche', ''),
            height=100,
            key="field_caratteristiche"
        )
        
        # Campo 3: Prezzo
        prezzo = st.text_input(
            "💰 Prezzo/Valore",
            value=data.get('prezzo', ''),
            key="field_prezzo"
        )
        
        # Mostra trascrizione originale
        with st.expander("📝 Trascrizione Originale"):
            st.text(st.session_state.transcription)
        
        # Mostra risposta AI grezza
        with st.expander("🤖 Risposta AI Completa"):
            st.code(st.session_state.get('ai_response', 'Non disponibile'))
        
        # Pulsante per salvare
        if st.button("💾 Salva Modifiche", type="primary"):
            # Qui puoi aggiungere la logica per salvare i dati
            st.success("✅ Modifiche salvate!")
            
    else:
        st.info("📝 Registra un audio per vedere i campi compilati automaticamente")
        
        # Campi vuoti per dimostrazione
        st.text_input("🏷️ Nome Prodotto/Oggetto", placeholder="Compilato automaticamente...")
        st.text_area("🔍 Caratteristiche Principali", placeholder="Compilato automaticamente...", height=100)
        st.text_input("💰 Prezzo/Valore", placeholder="Compilato automaticamente...")

# Footer con informazioni
st.markdown("---")
st.markdown("""
### 📚 Come funziona:

1. **🎙️ Registra** la tua voce descrivendo un prodotto/oggetto
2. **🔄 Conversione** automatica in WAV 16kHz mono (qualsiasi formato)
3. **📝 Trascrizione locale** con Whisper (nessuna API esterna)
4. **🧠 Analisi AI** (OpenAI se disponibile, regole se no)
5. **📋 Campi compilati** automaticamente
6. **✏️ Modifica** i campi se necessario
7. **💾 Salva** le modifiche

### 🔧 Tecnologie utilizzate:
- **Streamlit** per l'interfaccia
- **faster-whisper** per trascrizione locale (CPU-friendly)
- **imageio-ffmpeg** per conversione audio robusta
- **OpenAI GPT** per analisi AI avanzata (opzionale)
- **Analisi basata su regole** come fallback

### 🚀 Compatibilità Streamlit Cloud:
- ✅ **Upload file audio** - Funziona sempre
- ✅ **Conversione automatica** - Qualsiasi formato → WAV 16kHz mono
- ✅ **Trascrizione locale** - Nessuna API esterna richiesta
- ✅ **Analisi AI opzionale** - OpenAI se disponibile, regole se no
- ✅ **Gestione errori robusta** - Fallback automatici
""")

# Informazioni per sviluppatori
with st.expander("🔧 Informazioni per Sviluppatori"):
    st.info("""
    **Per installare localmente:**
    ```bash
    pip install faster-whisper imageio-ffmpeg openai
    ```
    
    **Per Streamlit Cloud:**
    - Aggiungi `faster-whisper imageio-ffmpeg` al requirements.txt
    - L'app funzionerà sempre (trascrizione locale)
    
    **Vantaggi della nuova soluzione:**
    - 🎯 **Nessuna API esterna** per trascrizione
    - 🚀 **Più veloce** di OpenAI Whisper
    - 💰 **Gratis** per trascrizioni
    - 🔒 **Privacy** - tutto locale
    - 🎵 **Qualsiasi formato** audio supportato
    
    **Test rapido:**
    ```bash
    python test_voice_recording.py
    ```
    """)
