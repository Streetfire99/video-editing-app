import streamlit as st
import os
import tempfile
import json
from openai import OpenAI
import time

# Configurazione della pagina
st.set_page_config(
    page_title="🎤 Test Voce",
    page_icon="🎤",
    layout="wide"
)

st.title("🎤 Test Registrazione Voce con AI")
st.markdown("---")

# Sidebar per configurazione
with st.sidebar:
    st.header("⚙️ Configurazione")
    
    # API Key OpenAI
    openai_api_key = st.text_input(
        "🔑 OpenAI API Key",
        type="password",
        help="Inserisci la tua OpenAI API Key"
    )
    
    # Modello da utilizzare
    model = st.selectbox(
        "🤖 Modello AI",
        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        index=0,
        help="Seleziona il modello OpenAI da utilizzare"
    )
    
    # Prompt personalizzato
    custom_prompt = st.text_area(
        "📝 Prompt Personalizzato",
        value="Analizza la registrazione vocale e estrai le seguenti informazioni:\n1. Nome del prodotto/oggetto\n2. Caratteristiche principali\n3. Prezzo o valore indicato\n\nRispondi in formato JSON con i campi: nome, caratteristiche, prezzo",
        height=150,
        help="Personalizza il prompt per l'analisi AI"
    )

# Funzione per ottenere il client OpenAI
def get_openai_client(api_key):
    """Ottiene il client OpenAI"""
    if not api_key:
        st.error("❌ API Key OpenAI richiesta")
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        return client
    except Exception as e:
        st.error(f"❌ Errore nella creazione del client OpenAI: {e}")
        return None

# Funzione per trascrivere audio
def transcribe_audio(client, audio_file):
    """Trascrive l'audio usando OpenAI Whisper"""
    try:
        with open(audio_file, "rb") as audio:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                response_format="text"
            )
        return transcript
    except Exception as e:
        st.error(f"❌ Errore nella trascrizione: {e}")
        return None

# Funzione per analizzare con AI
def analyze_with_ai(client, transcription, prompt):
    """Analizza la trascrizione con AI"""
    try:
        system_prompt = """Sei un assistente AI specializzato nell'analisi di trascrizioni vocali. 
        Analizza il testo fornito e estrai le informazioni richieste.
        Rispondi SEMPRE in formato JSON valido."""
        
        user_prompt = f"{prompt}\n\nTrascrizione: {transcription}"
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"❌ Errore nell'analisi AI: {e}")
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
    
    # Controllo API Key
    if not openai_api_key:
        st.warning("⚠️ Inserisci l'API Key OpenAI nella sidebar per iniziare")
        st.stop()
    
    client = get_openai_client(openai_api_key)
    if not client:
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
                
                # Step 1: Trascrizione
                st.info("📝 Trascrizione audio...")
                transcription = transcribe_audio(client, temp_audio_path)
                
                if transcription:
                    st.success("✅ Trascrizione completata!")
                    st.markdown(f"**Trascrizione:** {transcription}")
                    
                    # Step 2: Analisi AI
                    st.info("🤖 Analisi con AI...")
                    ai_response = analyze_with_ai(client, transcription, custom_prompt)
                    
                    if ai_response:
                        st.success("✅ Analisi AI completata!")
                        
                        # Step 3: Parsing e inserimento campi
                        st.info("🔍 Parsing risultati...")
                        parsed_data = parse_ai_response(ai_response)
                        
                        if parsed_data:
                            st.success("✅ Dati estratti con successo!")
                            
                            # Salva i dati nella session state
                            st.session_state.extracted_data = parsed_data
                            st.session_state.transcription = transcription
                            
                            # Rimuovi file temporaneo
                            os.unlink(temp_audio_path)
                            
                            st.rerun()
                        else:
                            st.error("❌ Impossibile parsare i dati AI")
                    else:
                        st.error("❌ Errore nell'analisi AI")
                else:
                    st.error("❌ Errore nella trascrizione")
                
                # Pulisci file temporaneo
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)

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
2. **🤖 AI trascrive** l'audio in testo
3. **🧠 AI analizza** e estrae le informazioni richieste
4. **📋 Campi compilati** automaticamente
5. **✏️ Modifica** i campi se necessario
6. **💾 Salva** le modifiche

### 🔧 Tecnologie utilizzate:
- **Streamlit** per l'interfaccia
- **OpenAI Whisper** per la trascrizione
- **OpenAI GPT** per l'analisi AI
- **streamlit-audio-recorder** per la registrazione (opzionale)

### 🚀 Compatibilità Streamlit Cloud:
- ✅ **Upload file audio** - Funziona sempre
- ✅ **Registrazione diretta** - Se disponibile
- ✅ **Fallback automatico** - Se mancano dipendenze
- ✅ **Gestione errori** - Robustezza garantita
""")

# Informazioni per sviluppatori
with st.expander("🔧 Informazioni per Sviluppatori"):
    st.info("""
    **Per installare localmente:**
    ```bash
    pip install streamlit-audio-recorder openai
    ```
    
    **Per Streamlit Cloud:**
    - Aggiungi `streamlit-audio-recorder` al requirements.txt
    - L'app funzionerà anche senza (con upload file)
    
    **Test rapido:**
    ```bash
    python test_voice_recording.py
    ```
    """)
