import streamlit as st
import os
import tempfile
import json
import time
from pathlib import Path
import sys
import random

# Rimuovi il file di log se esiste (per evitare loop infinito)
try:
    if os.path.exists("logs/app_debug.log"):
        os.remove("logs/app_debug.log")
    if os.path.exists("logs"):
        import shutil
        shutil.rmtree("logs")
except:
    pass

# Aggiungi il percorso del modulo Elaborazione
sys.path.append('Elaborazione')

# Importa le funzioni da prova.py
try:
    from prova import (
        process_video, 
        generate_subtitles_only,
        finalize_video_processing,
        get_openai_client, 
        create_srt_file, 
        add_subtitles_to_video,
        format_timestamp,
        split_text
    )
except ImportError as e:
    st.error(f"❌ Errore importazione modulo prova: {e}")
    st.stop()

# Importa le funzioni per YouTube e Drive
from youtube_manager import upload_to_youtube, check_youtube_setup, get_youtube_status
from drive_manager import upload_video_to_drive, add_tracking_entry

# Importa le funzioni per YouTube
from youtube_manager import upload_to_youtube, check_youtube_setup, get_youtube_status

# Importa le funzioni per la gestione dei dati
from data_manager import (
    load_apartments,
    get_video_types,
    get_prompt_for_video_type,
    get_translation_prompt_for_video_type
)

# Importa le funzioni per Google Drive
from drive_manager import upload_video_to_drive, add_tracking_entry



def create_session_temp_file(prefix, suffix):
    """Crea un file temporaneo unico per questa sessione"""
    session_id = st.session_state.session_id
    timestamp = int(time.time())
    random_id = random.randint(1000, 9999)
    filename = f"{prefix}_{session_id}_{timestamp}_{random_id}{suffix}"
    return os.path.join(tempfile.gettempdir(), filename)

def create_session_temp_dir():
    """Crea una directory temporanea unica per questa sessione"""
    session_id = st.session_state.session_id
    timestamp = int(time.time())
    random_id = random.randint(1000, 9999)
    dirname = f"session_{session_id}_{timestamp}_{random_id}"
    temp_dir = os.path.join(tempfile.gettempdir(), dirname)
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def cleanup_session_files():
    """Pulisce i file temporanei di questa sessione"""
    session_id = st.session_state.session_id
    temp_dir = tempfile.gettempdir()
    
    # Trova e rimuovi tutti i file di questa sessione
    for filename in os.listdir(temp_dir):
        if filename.startswith(f"session_{session_id}_"):
            filepath = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                elif os.path.isdir(filepath):
                    import shutil
                    shutil.rmtree(filepath)
            except Exception as e:
                print(f"Errore nella pulizia file {filepath}: {e}")

# Configurazione della pagina
st.set_page_config(
    page_title="🎬 Elaborazione Tutorial",
    page_icon="🎬",
    layout="wide"
)

# Inizializza session state per multi-tab
if 'session_id' not in st.session_state:
    st.session_state.session_id = f"session_{int(time.time())}_{random.randint(1000, 9999)}"

if 'current_video_path' not in st.session_state:
    st.session_state.current_video_path = None

if 'processed_video' not in st.session_state:
    st.session_state.processed_video = None

if 'has_voice' not in st.session_state:
    st.session_state.has_voice = True

if 'youtube_link' not in st.session_state:
    st.session_state.youtube_link = ''

# Pulisci file temporanei di sessioni precedenti (più vecchie di 1 ora)
def cleanup_old_session_files():
    """Pulisce i file temporanei di sessioni vecchie"""
    temp_dir = tempfile.gettempdir()
    current_time = time.time()
    
    for filename in os.listdir(temp_dir):
        if filename.startswith("session_"):
            try:
                # Estrai timestamp dal nome file
                parts = filename.split('_')
                if len(parts) >= 3:
                    timestamp_str = parts[2]
                    if timestamp_str.isdigit():
                        file_timestamp = int(timestamp_str)
                        # Se il file è più vecchio di 1 ora, rimuovilo
                        if current_time - file_timestamp > 3600:  # 1 ora
                            filepath = os.path.join(temp_dir, filename)
                            if os.path.isfile(filepath):
                                os.remove(filepath)
                            elif os.path.isdir(filepath):
                                import shutil
                                shutil.rmtree(filepath)
            except Exception as e:
                pass  # Ignora errori di pulizia

# Esegui pulizia all'avvio
cleanup_old_session_files()

# Pulisci session state per evitare memory leaks
def cleanup_session_state():
    """Pulisce i dati temporanei dalla session state"""
    keys_to_clean = [key for key in st.session_state.keys() if key.startswith('auth_cache_') or key.startswith('pending_auth_')]
    for key in keys_to_clean:
        if key in st.session_state:
            del st.session_state[key]

def create_instructions_from_transcription(transcription, video_name, language="italiano", openai_api_key=None):
    """Crea istruzioni in formato elenco puntato dalla trascrizione"""
    try:
        if not openai_api_key:
            return None
            
        client = get_openai_client(openai_api_key)
        
        # Se la trascrizione è troppo breve o generica, usa il nome del video
        if len(transcription) < 50 or "amara" in transcription.lower():
            return f"Manuale {language} per {video_name}"
        
        if language == "italiano":
            prompt = f"""
Analizza attentamente questa trascrizione audio e crea istruzioni SPECIFICHE per il contenuto del video.

Video: {video_name}
Trascrizione: "{transcription}"

IMPORTANTE: 
- Le istruzioni devono essere SPECIFICHE per il contenuto del video
- NON creare istruzioni generiche come "accedi al sito" o "seguire le istruzioni"
- Analizza il contenuto della trascrizione e crea istruzioni concrete
- Se la trascrizione è troppo breve, deduci il contenuto dal nome del video
- Massimo 3-4 punti in formato elenco numerato (1., 2., 3., 4.)
- Ogni frase deve essere di circa 9-10 parole
- Frasi brevi, concrete e dirette
- NON mettere punti alla fine delle istruzioni

Esempio di istruzioni specifiche (non generiche):
1. Individua il boiler sotto la lavatrice nella stanza principale
2. Assicurati che il boiler sia sempre acceso e collegato alla presa
3. Controlla che il boiler mostri una luce blu durante il funzionamento
4. Se l'acqua finisce attendi che il boiler ricarichi per 20-30 minuti

Istruzioni specifiche per questo video:
"""
        else:  # inglese - traduci da italiano
            prompt = f"""
Traduci queste istruzioni italiane in inglese, mantenendo lo stesso formato e struttura:

Istruzioni italiane:
{transcription}

IMPORTANTE:
- Mantieni il formato elenco numerato 1., 2., 3., 4.
- NON mettere punti alla fine delle istruzioni
- Traduci fedelmente mantenendo la stessa struttura
- NON aggiungere "English Translation:" o altri prefissi
- Restituisci SOLO la traduzione numerata
- Crea frasi COMPLETE e COERENTI, non spezzate
- Ogni frase deve essere di circa 9-10 parole
- Massimo 3-4 punti

Esempio di traduzione corretta:
1. Locate the boiler under the washing machine in the main room
2. Ensure the boiler is always turned on and connected to the socket
3. Check that the boiler displays a blue light during operation
4. If the water runs out wait for the boiler to recharge for 20-30 minutes

Traduzione in inglese:"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Sei un esperto nell'analisi di contenuti video. Crea SEMPRE istruzioni specifiche e concrete basate sul contenuto reale del video. MAI istruzioni generiche o vaghe. Analizza attentamente la trascrizione e deduci il contenuto specifico."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.1
        )
        
        instructions = response.choices[0].message.content.strip()
        
        # Pulisci il testo rimuovendo il prompt se presente
        if language == "inglese":
            # Rimuovi il prompt se presente nel risultato
            if "IMPORTANT:" in instructions:
                instructions = instructions.split("IMPORTANT:")[0].strip()
            if "Traduzione in inglese:" in instructions:
                instructions = instructions.split("Traduzione in inglese:")[1].strip()
            if "English Translation:" in instructions:
                instructions = instructions.split("English Translation:")[1].strip()
            # Rimuovi eventuali prefissi rimasti
            instructions = instructions.replace("English Translation:", "").strip()
        
        return instructions
    except Exception as e:
        print(f"❌ Errore creazione istruzioni: {e}")
        return None

# Esegui pulizia ogni 10 minuti
if 'last_cleanup' not in st.session_state:
    st.session_state.last_cleanup = time.time()

if time.time() - st.session_state.last_cleanup > 600:  # 10 minuti
    cleanup_session_state()
    cleanup_session_files()  # Pulisci anche i file di questa sessione
    st.session_state.last_cleanup = time.time()

# Titolo dell'app
st.title("🎬 Elaborazione Video")
st.markdown("Sistema di elaborazione video con sottotitoli automatici per database tutorial")

# Mostra session ID per debug multi-tab
with st.expander("🔧 Debug Info"):
    st.write(f"**Session ID:** {st.session_state.session_id}")
    st.write(f"**Current Video:** {st.session_state.current_video_path}")
    st.write(f"**Processed Video:** {st.session_state.processed_video is not None}")
    st.write(f"**Has Voice:** {st.session_state.has_voice}")

# Carica gli appartamenti e le tipologie
apartments = load_apartments()

# Inizializza video_types nel session state se non esiste
if 'video_types' not in st.session_state:
    st.session_state.video_types = get_video_types()

video_types = st.session_state.video_types

# Carica configurazioni
def load_config():
    """Carica la configurazione dalle variabili d'ambiente"""
    config = {}
    
    # Carica OpenAI API Key da Streamlit secrets
    openai_api_key = st.secrets.get('OPENAI_API_KEY')
    if openai_api_key:
        config['openai_api_key'] = openai_api_key
    else:
        # Fallback alle variabili d'ambiente
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            config['openai_api_key'] = openai_api_key
        else:
            st.error("❌ OPENAI_API_KEY non trovata nei secrets o nelle variabili d'ambiente")
    
    return config

config = load_config()

# Campo per inserire la chiave API OpenAI
openai_api_key = st.text_input(
    "🔑 OpenAI API Key",
    value=config.get('openai_api_key', ''),
    type="password",
    help="Inserisci la tua chiave API OpenAI"
)

# Sidebar vuota - rimossa per interfaccia più pulita

# ============================================================================
# NUOVO SISTEMA BULK PROCESSING
# ============================================================================

# Inizializza session state per bulk processing
if 'bulk_processing' not in st.session_state:
    st.session_state.bulk_processing = {
        'videos': [],
        'global_config': {
            'apartment': None
        },
        'current_phase': 'upload'  # upload, generate_edit, process, results
    }

# Sezione principale - Upload multiplo
st.header("📤 Carica Video Multipli")

# Upload multiplo di video
uploaded_videos = st.file_uploader(
    "Scegli i file video da elaborare",
    type=['mp4', 'avi', 'mov', 'mkv'],
    help="Formati supportati: MP4, AVI, MOV, MKV",
    accept_multiple_files=True
)

# Salva i video caricati nel session state
if uploaded_videos:
    for uploaded_video in uploaded_videos:
        # Salva il video temporaneamente
        video_path = create_session_temp_file(f"video_{uploaded_video.name}", ".mp4")
        with open(video_path, "wb") as f:
            f.write(uploaded_video.getvalue())
        
        # Aggiungi alla lista se non esiste già
        video_exists = any(v['name'] == uploaded_video.name for v in st.session_state.bulk_processing['videos'])
        if not video_exists:
            st.session_state.bulk_processing['videos'].append({
                'file': uploaded_video,
                'name': uploaded_video.name,
                'path': video_path,
                'apartment': None,
                'video_type': None,
                'subtitles': {'it': [], 'en': []},
                'manuals': {'it': '', 'en': ''},
                'processed_video': None,
                'drive_links': {'video': None, 'manual_it': None, 'manual_en': None},
                'youtube_link': None
            })
    
    st.success(f"✅ Caricati {len(uploaded_videos)} video!")

# Sezione configurazione globale
if st.session_state.bulk_processing['videos']:
    st.markdown("---")
    st.header("📋 Configurazione Globale")
    
    # Selezione appartamento globale
    selected_apartment = st.selectbox(
        "🏠 Seleziona Appartamento (valido per tutti i video)",
        options=[""] + apartments,
        help="Scegli l'appartamento per cui stai creando i video",
        key="global_apartment"
    )
    
    # Aggiorna configurazione globale
    if selected_apartment:
        st.session_state.bulk_processing['global_config']['apartment'] = selected_apartment
        
        # Aggiorna tutti i video con l'appartamento globale
        for video in st.session_state.bulk_processing['videos']:
            video['apartment'] = selected_apartment
        
        st.success(f"✅ Appartamento applicato: **{selected_apartment}**")
        
        # Mostra configurazione individuale per ogni video
        st.subheader("🎥 Configurazione Individuale Video")
        st.info("Seleziona la tipologia per ogni video individualmente")
        
        # Mostra lista video con selezione tipologia
        for i, video in enumerate(st.session_state.bulk_processing['videos']):
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**{video['name']}** ({video['file'].size / (1024*1024):.1f} MB)")
                
                with col2:
                    # Selezione tipologia per questo video specifico
                    video_type = st.selectbox(
                        f"Tipologia per {video['name']}",
                        options=[""] + video_types,
                        key=f"video_type_{i}",
                        help=f"Scegli la tipologia per {video['name']}"
                    )
                    
                    if video_type:
                        video['video_type'] = video_type
                        st.success(f"✅ {video_type}")
                
                with col3:
                    if st.button("🗑️", key=f"remove_{i}"):
                        st.session_state.bulk_processing['videos'].pop(i)
                        st.rerun()
        
        # Verifica che tutti i video abbiano una tipologia
        all_videos_configured = all(video.get('video_type') for video in st.session_state.bulk_processing['videos'])
        
        if all_videos_configured:
            st.success("✅ Tutti i video sono configurati!")
            
            # Pulsante per generare sottotitoli e manuali
            if st.button("🎬 Genera Sottotitoli e Manuali per Tutti i Video", type="primary"):
                st.session_state.bulk_processing['current_phase'] = 'generate_edit'
                st.rerun()
        else:
            st.warning("⚠️ Seleziona una tipologia per tutti i video prima di procedere")

# ============================================================================
# GESTIONE FASI BULK PROCESSING
# ============================================================================

# Campo per aggiungere nuove tipologie
with st.expander("➕ Aggiungi Nuova Tipologia"):
    new_video_type = st.text_input(
        "Nuova tipologia",
        placeholder="es: aspirapolvere",
        help="Inserisci una nuova tipologia di video"
    )
    if st.button("Aggiungi"):
        if new_video_type and new_video_type not in video_types:
            st.session_state.video_types.append(new_video_type)
            st.session_state.video_types.sort()
            st.success(f"✅ Tipologia '{new_video_type}' aggiunta!")
            st.rerun()

# Gestione fasi del bulk processing
current_phase = st.session_state.bulk_processing['current_phase']

if current_phase == 'generate_edit':
    st.markdown("---")
    st.header("🎬 Generazione e Modifica Sottotitoli")
    
    if not openai_api_key:
        st.error("❌ Inserisci la tua OpenAI API Key")
        st.stop()
    
    # Controlla se i sottotitoli sono già stati generati
    videos_with_subtitles = []
    videos_needing_generation = []
    
    for video in st.session_state.bulk_processing['videos']:
        has_subtitles = video.get('subtitles', {}).get('it') and video.get('subtitles', {}).get('en')
        if has_subtitles:
            videos_with_subtitles.append(video)
        else:
            videos_needing_generation.append(video)
    
    # Genera sottotitoli per i video che ne hanno bisogno
    if videos_needing_generation:
        st.subheader("🔄 Generazione Sottotitoli")
        
        # Progress bar per la generazione
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, video in enumerate(videos_needing_generation):
            status_text.text(f"🔄 Generando sottotitoli per {video['name']}... ({i+1}/{len(videos_needing_generation)})")
            
            try:
                # Crea directory temporanea per questo video
                output_dir = create_session_temp_dir()
                
                # Genera sottotitoli
                result = generate_subtitles_only(
                    input_video=video['path'],
                    openai_api_key=openai_api_key,
                    output_dir=output_dir,
                    video_type=video['video_type']
                )
                
                if result['success']:
                    segments_it = result.get('segments', [])
                    segments_en = result.get('segments_en', [])
                    
                    video['subtitles'] = {
                        'it': segments_it,
                        'en': segments_en
                    }
                    video['subtitles_data'] = result
                    video['output_dir'] = output_dir
                    
                    # Genera manuali
                    try:
                        transcription_text = ""
                        for segment in result.get('segments', []):
                            transcription_text += segment.get('text', '') + " "
                        
                        manual_it = create_instructions_from_transcription(
                            transcription_text, 
                            video['name'], 
                            "italiano",
                            openai_api_key
                        )
                        
                        manual_en = create_instructions_from_transcription(
                            transcription_text, 
                            video['name'], 
                            "inglese",
                            openai_api_key
                        )
                        
                        video['manuals'] = {
                            'it': manual_it or f"Manuale italiano per {video['name']}",
                            'en': manual_en or f"English manual for {video['name']}"
                        }
                    except Exception as e:
                        st.error(f"❌ Errore generazione manuali per {video['name']}: {str(e)}")
                        video['manuals'] = {
                            'it': f"Manuale italiano per {video['name']}",
                            'en': f"English manual for {video['name']}"
                        }
                    
                    st.success(f"✅ {video['name']} - Sottotitoli e manuali generati!")
                else:
                    st.error(f"❌ {video['name']} - Errore: {result.get('error', 'Errore sconosciuto')}")
                    
            except Exception as e:
                st.error(f"❌ {video['name']} - Errore: {str(e)}")
            
            # Aggiorna progress bar
            progress_bar.progress((i + 1) / len(videos_needing_generation))
        
        status_text.text("✅ Generazione completata!")
    
    # Sezione modifica sottotitoli
    st.subheader("✏️ Modifica Sottotitoli e Manuali")
    st.info("📝 Modifica i sottotitoli e manuali prima di procedere con l'elaborazione video")
    
    for i, video in enumerate(st.session_state.bulk_processing['videos']):
        with st.expander(f"🎬 {video['name']} - {video.get('video_type', 'N/A')}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Sottotitoli Italiani:**")
                if video['subtitles']['it']:
                    for j, segment in enumerate(video['subtitles']['it']):
                        edited_text = st.text_area(
                            f"IT {j+1}",
                            value=segment.get('text', ''),
                            key=f"it_{i}_{j}",
                            height=60,
                            label_visibility="collapsed"
                        )
                        video['subtitles']['it'][j]['text'] = edited_text
                else:
                    st.write("❌ Nessun sottotitolo generato")
            
            with col2:
                st.write("**Sottotitoli Inglesi:**")
                if video['subtitles']['en']:
                    for j, segment in enumerate(video['subtitles']['en']):
                        if isinstance(segment, dict):
                            current_text = segment.get('text', '')
                        else:
                            current_text = segment[2] if len(segment) > 2 else ''
                        
                        edited_text = st.text_area(
                            f"EN {j+1}",
                            value=current_text,
                            key=f"en_{i}_{j}",
                            height=60,
                            label_visibility="collapsed"
                        )
                        
                        if isinstance(segment, dict):
                            video['subtitles']['en'][j]['text'] = edited_text
                        else:
                            video['subtitles']['en'][j] = {
                                'start': segment[0],
                                'end': segment[1],
                                'text': edited_text
                            }
                else:
                    st.write("❌ Nessun sottotitolo generato")
            
            # Manuali
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Manuale Italiano:**")
                video['manuals']['it'] = st.text_area(
                    "Manuale IT",
                    value=video['manuals']['it'],
                    key=f"manual_it_{i}",
                    height=150,
                    label_visibility="collapsed"
                )
            
            with col2:
                st.write("**Manuale Inglese:**")
                video['manuals']['en'] = st.text_area(
                    "Manuale EN",
                    value=video['manuals']['en'],
                    key=f"manual_en_{i}",
                    height=150,
                    label_visibility="collapsed"
                )
    
    # Pulsante per elaborare i video
    st.markdown("---")
    st.subheader("🚀 Elaborazione Video")
    st.info("📝 Dopo aver modificato i sottotitoli e manuali, clicca qui per elaborare tutti i video:")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Elabora Video", type="primary", use_container_width=True):
            st.session_state.bulk_processing['current_phase'] = 'process'
            st.rerun()



elif current_phase == 'process':
    st.markdown("---")
    st.header("🚀 Elaborazione Video")
    
    # Progress bar per l'elaborazione
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_videos = len(st.session_state.bulk_processing['videos'])
    
    for i, video in enumerate(st.session_state.bulk_processing['videos']):
        status_text.text(f"🔄 Elaborando {video['name']}... ({i+1}/{total_videos})")
        
        # Controlla se il video è già stato elaborato
        if video.get('processed_video') and video['processed_video'].get('success'):
            final_video_path = video['processed_video'].get('final_video')
            if final_video_path and os.path.exists(final_video_path):
                st.success(f"✅ {video['name']} - Video già elaborato!")
                st.write(f"🔧 DEBUG: Video già esistente: {final_video_path}")
                progress_bar.progress((i + 1) / total_videos)
                continue
        
        try:
            # Crea file SRT temporanei con i sottotitoli modificati
            temp_srt_it = tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8')
            temp_srt_en = tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8')
            
            # Scrivi i sottotitoli italiani modificati
            # Assicurati che i segmenti abbiano il formato corretto
            segments_it_formatted = []
            for segment in video['subtitles']['it']:
                if isinstance(segment, dict) and 'start' in segment and 'end' in segment and 'text' in segment:
                    segments_it_formatted.append(segment)
                else:
                    st.error(f"❌ Formato segmento IT non valido: {segment}")
                    continue
            
            create_srt_file(segments_it_formatted, temp_srt_it.name, "IT")
            
            # Scrivi i sottotitoli inglesi modificati
            # Assicurati che i segmenti abbiano il formato corretto
            segments_en_formatted = []
            for segment in video['subtitles']['en']:
                if isinstance(segment, dict) and 'start' in segment and 'end' in segment and 'text' in segment:
                    segments_en_formatted.append(segment)
                elif isinstance(segment, tuple) and len(segment) >= 3:
                    # Converti tuple in dizionario
                    segments_en_formatted.append({
                        'start': segment[0],
                        'end': segment[1],
                        'text': segment[2]
                    })
                else:
                    st.error(f"❌ Formato segmento EN non valido: {segment}")
                    continue
            
            create_srt_file(segments_en_formatted, temp_srt_en.name, "EN")
            
            # Elabora video con sottotitoli modificati
            result = finalize_video_processing(
                input_video=video['path'],
                srt_it_file=temp_srt_it.name,
                srt_en_file=temp_srt_en.name,
                output_dir=video['output_dir'],
                italian_height=120,
                english_height=60
            )
            
            # Pulisci i file temporanei
            temp_srt_it.close()
            temp_srt_en.close()
            os.unlink(temp_srt_it.name)
            os.unlink(temp_srt_en.name)
            
            if result['success']:
                video['processed_video'] = result
                st.success(f"✅ {video['name']} - Video elaborato!")
                st.write(f"🔧 DEBUG: Video salvato con success: {result.get('final_video', 'N/A')}")
            else:
                st.error(f"❌ {video['name']} - Errore: {result.get('error', 'Errore sconosciuto')}")
                st.write(f"🔧 DEBUG: Risultato fallito: {result}")
                
        except Exception as e:
            st.error(f"❌ {video['name']} - Errore: {str(e)}")
        
        # Aggiorna progress bar
        progress_bar.progress((i + 1) / total_videos)
    
    status_text.text("✅ Elaborazione completata!")
    
    # Pulsante per passare ai risultati
    if st.button("📊 Visualizza Risultati", type="primary"):
        st.session_state.bulk_processing['current_phase'] = 'results'
        st.rerun()

elif current_phase == 'results':
    st.markdown("---")
    st.header("📊 Risultati Elaborazione")
    
    # Debug: mostra informazioni sui video
    st.info(f"🔧 DEBUG: Numero video in sessione: {len(st.session_state.bulk_processing['videos'])}")
    
    # Crea tab per ogni video elaborato
    if st.session_state.bulk_processing['videos']:
        tab_names = [f"🎬 {video['name']}" for video in st.session_state.bulk_processing['videos']]
        tabs = st.tabs(tab_names)
        
        for i, (video, tab) in enumerate(zip(st.session_state.bulk_processing['videos'], tabs)):
            with tab:
                st.subheader(f"Risultati: {video['name']}")
                
                # Debug: mostra informazioni sul video
                st.write(f"🔧 DEBUG: Video ha processed_video: {video.get('processed_video') is not None}")
                if video.get('processed_video'):
                    st.write(f"🔧 DEBUG: processed_video keys: {list(video['processed_video'].keys())}")
                    if 'final_video' in video['processed_video']:
                        st.write(f"🔧 DEBUG: final_video path: {video['processed_video']['final_video']}")
                        st.write(f"🔧 DEBUG: final_video exists: {os.path.exists(video['processed_video']['final_video'])}")
                
                if video.get('processed_video') and video['processed_video'].get('success'):
                    # Mostra video elaborato
                    final_video_path = video['processed_video'].get('final_video')
                    if final_video_path and os.path.exists(final_video_path):
                        st.video(final_video_path)
                        
                        # Pulsanti individuali
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            with open(final_video_path, "rb") as video_file:
                                st.download_button(
                                    label="📥 Scarica Video",
                                    data=video_file.read(),
                                    file_name=f"{video['name']}_elaborato.mp4",
                                    mime="video/mp4"
                                )
                        
                        with col2:
                            if st.button("☁️ Upload Drive", key=f"drive_{i}"):
                                try:
                                    # Upload video su Drive
                                    drive_link = upload_video_to_drive(
                                        video_path=final_video_path,
                                        apartment_name=video['apartment'],
                                        video_type=video['video_type']
                                    )
                                    
                                    if drive_link:
                                        video['drive_links']['video'] = drive_link
                                        st.success(f"✅ Video caricato su Drive: {drive_link}")
                                        
                                        # Salva nel tracking
                                        add_tracking_entry(
                                            apartment=video['apartment'],
                                            video_type=video['video_type'],
                                            youtube_link=None,
                                            drive_link=drive_link
                                        )
                                    else:
                                        st.error("❌ Errore nel caricamento su Drive")
                                except Exception as e:
                                    st.error(f"❌ Errore upload Drive: {str(e)}")
                        
                        with col3:
                            if st.button("📺 Upload YouTube", key=f"youtube_{i}"):
                                try:
                                    # Upload video su YouTube
                                    youtube_link = upload_to_youtube(
                                        video_path=final_video_path,
                                        title=f"{video['apartment']} - {video['video_type']}",
                                        description=video['manuals']['it']
                                    )
                                    
                                    if youtube_link:
                                        video['youtube_link'] = youtube_link
                                        st.success(f"✅ Video caricato su YouTube: {youtube_link}")
                                        
                                        # Salva nel tracking
                                        add_tracking_entry(
                                            apartment=video['apartment'],
                                            video_type=video['video_type'],
                                            youtube_link=youtube_link,
                                            drive_link=video['drive_links']['video']
                                        )
                                    else:
                                        st.error("❌ Errore nel caricamento su YouTube")
                                except Exception as e:
                                    st.error(f"❌ Errore upload YouTube: {str(e)}")
                    else:
                        st.error(f"❌ Video elaborato non trovato: {final_video_path}")
                else:
                    st.error(f"❌ Video non elaborato correttamente per {video['name']}")
                    if video.get('processed_video'):
                        st.write(f"Errore: {video['processed_video'].get('error', 'Errore sconosciuto')}")
                
                # Manuali
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Manuale Italiano:**")
                    st.text_area("", value=video['manuals']['it'], height=150, disabled=True)
                    
                    st.download_button(
                        label="📥 Scarica Manuale IT",
                        data=video['manuals']['it'],
                        file_name=f"{video['name']}_manuale_IT.txt",
                        mime="text/plain",
                        key=f"download_it_{i}"
                    )
                
                with col2:
                    st.write("**Manuale Inglese:**")
                    st.text_area("", value=video['manuals']['en'], height=150, disabled=True)
                    
                    st.download_button(
                        label="📥 Scarica Manuale EN",
                        data=video['manuals']['en'],
                        file_name=f"{video['name']}_manuale_EN.txt",
                        mime="text/plain",
                        key=f"download_en_{i}"
                    )
        
        # Pulsanti bulk
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📥 Scarica Tutto", type="primary"):
                # Crea un file ZIP con tutti i video e manuali
                import zipfile
                import io
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for video in st.session_state.bulk_processing['videos']:
                        if video.get('processed_video') and video['processed_video'].get('success'):
                            final_video_path = video['processed_video'].get('final_video')
                            if final_video_path and os.path.exists(final_video_path):
                                # Aggiungi video
                                zip_file.write(final_video_path, f"{video['name']}_elaborato.mp4")
                                
                                # Aggiungi manuali
                                zip_file.writestr(f"{video['name']}_manuale_IT.txt", video['manuals']['it'])
                                zip_file.writestr(f"{video['name']}_manuale_EN.txt", video['manuals']['en'])
                
                st.download_button(
                    label="📥 Scarica Tutto (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="video_elaborati.zip",
                    mime="application/zip"
                )
        
        with col2:
            if st.button("☁️ Salva Tutto su Drive", type="primary"):
                uploaded_count = 0
                for video in st.session_state.bulk_processing['videos']:
                    if video.get('processed_video') and video['processed_video'].get('success'):
                        final_video_path = video['processed_video'].get('final_video')
                        if final_video_path and os.path.exists(final_video_path):
                            try:
                                # Upload video
                                drive_link = upload_video_to_drive(
                                    video_path=final_video_path,
                                    apartment_name=video['apartment'],
                                    video_type=video['video_type']
                                )
                                
                                if drive_link:
                                    video['drive_links']['video'] = drive_link
                                    uploaded_count += 1
                                    
                                    # Upload manuali
                                    manual_it_link = upload_manual_to_drive(
                                        manual_content=video['manuals']['it'],
                                        filename=f"{video['name']}_manuale_IT.txt",
                                        apartment_name=video['apartment'],
                                        video_type=video['video_type']
                                    )
                                    
                                    manual_en_link = upload_manual_to_drive(
                                        manual_content=video['manuals']['en'],
                                        filename=f"{video['name']}_manuale_EN.txt",
                                        apartment_name=video['apartment'],
                                        video_type=video['video_type']
                                    )
                                    
                                    if manual_it_link:
                                        st.success(f"✅ Manuale IT caricato: {manual_it_link}")
                                    if manual_en_link:
                                        st.success(f"✅ Manuale EN caricato: {manual_en_link}")
                                    
                                    # Salva nel tracking
                                    add_tracking_entry(
                                        apartment=video['apartment'],
                                        video_type=video['video_type'],
                                        youtube_link=None,
                                        drive_link=drive_link,
                                        italian_manual_link=manual_it_link,
                                        english_manual_link=manual_en_link
                                    )
                            except Exception as e:
                                st.error(f"❌ Errore upload {video['name']}: {str(e)}")
                
                if uploaded_count > 0:
                    st.success(f"✅ Caricati {uploaded_count} video su Drive!")
                else:
                    st.error("❌ Nessun video caricato su Drive")
        
        with col3:
            if st.button("📺 Upload Tutti su YouTube", type="primary"):
                uploaded_count = 0
                for video in st.session_state.bulk_processing['videos']:
                    if video.get('processed_video') and video['processed_video'].get('success'):
                        final_video_path = video['processed_video'].get('final_video')
                        if final_video_path and os.path.exists(final_video_path):
                            try:
                                # Upload video su YouTube
                                youtube_link = upload_to_youtube(
                                    video_path=final_video_path,
                                    title=f"{video['apartment']} - {video['video_type']}",
                                    description=video['manuals']['it']
                                )
                                
                                if youtube_link:
                                    video['youtube_link'] = youtube_link
                                    uploaded_count += 1
                                    
                                    # Salva nel tracking
                                    add_tracking_entry(
                                        apartment=video['apartment'],
                                        video_type=video['video_type'],
                                        youtube_link=youtube_link,
                                        drive_link=video['drive_links']['video']
                                    )
                            except Exception as e:
                                st.error(f"❌ Errore upload YouTube {video['name']}: {str(e)}")
                
                if uploaded_count > 0:
                    st.success(f"✅ Caricati {uploaded_count} video su YouTube!")
                else:
                    st.error("❌ Nessun video caricato su YouTube")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎬 Video Editor con Sottotitoli Automatici | Powered by OpenAI Whisper & GPT-4</p>
</div>
""", unsafe_allow_html=True) 