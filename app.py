import streamlit as st
import os
import tempfile
from datetime import datetime
import pandas as pd
from googleapiclient.errors import HttpError
import json

# Import dei moduli personalizzati
from data_manager import (
    load_apartments, get_video_types, save_progress, load_all_progress,
    save_custom_apartment, load_custom_apartments,
    save_custom_video_type, load_custom_video_types
)
from youtube_upload import upload_to_youtube, check_youtube_setup
from youtube_account_manager import YouTubeAccountManager
from Elaborazione.prova import process_video

# Configurazione della pagina
st.set_page_config(
    page_title="Video Editing App",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inizializzazione del gestore account YouTube
@st.cache_resource
def get_account_manager():
    return YouTubeAccountManager()

account_manager = get_account_manager()

# Titolo principale
st.title("🎬 Video Editing App")
st.markdown("---")

# Sidebar per la navigazione
st.sidebar.title("📋 Menu")

# Sezione principale
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎬 Elaborazione Video", 
    "📊 Gestione Account YouTube", 
    "🔑 Gestione Token",
    "🏠 Gestione Appartamenti",
    "📝 Gestione Tipologie Video",
    "📈 Progresso Video"
])

# Tab 1: Elaborazione Video
with tab1:
    st.header("🎬 Elaborazione Video")
    
    # Upload del video
    uploaded_file = st.file_uploader(
        "Carica il video da elaborare",
        type=['mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm', 'm4v', '3gp', 'ogv', 'ts', 'mts', 'm2ts', 'vob', 'asf', 'rm', 'rmvb', 'divx', 'xvid', 'h264', 'h265', 'hevc', 'vp8', 'vp9', 'av1'],
        help="Formati supportati: MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V, 3GP, OGV, TS, MTS, M2TS, VOB, ASF, RM, RMVB, DivX, XviD, H.264, H.265, HEVC, VP8, VP9, AV1"
    )
    
    if uploaded_file is not None:
        # Mostra informazioni del video
        file_details = {
            "Nome file": uploaded_file.name,
            "Tipo file": uploaded_file.type,
            "Dimensione": f"{uploaded_file.size / (1024*1024):.2f} MB"
        }
        st.write("**Informazioni file:**")
        for key, value in file_details.items():
            st.write(f"- {key}: {value}")
        
        # Selezione appartamento
        st.subheader("🏠 Seleziona Appartamento")
        apartments = load_apartments()
        
        # Mostra appartamenti esistenti
        if apartments:
            selected_apartment = st.selectbox(
                "Scegli un appartamento esistente:",
                [apt['name'] for apt in apartments],
                index=None,
                placeholder="Seleziona un appartamento..."
            )
        else:
            selected_apartment = None
        
        # Opzione per aggiungere nuovo appartamento
        with st.expander("➕ Aggiungi nuovo appartamento"):
            new_apartment_name = st.text_input("Nome nuovo appartamento:")
            new_apartment_address = st.text_input("Indirizzo:")
            new_apartment_price = st.number_input("Prezzo (€):", min_value=0, value=0)
            new_apartment_rooms = st.number_input("Numero stanze:", min_value=1, value=1)
            new_apartment_bathrooms = st.number_input("Numero bagni:", min_value=1, value=1)
            new_apartment_sqm = st.number_input("Metri quadrati:", min_value=1, value=50)
            
            if st.button("Salva nuovo appartamento"):
                if new_apartment_name:
                    new_apartment = {
                        'name': new_apartment_name,
                        'address': new_apartment_address,
                        'price': new_apartment_price,
                        'rooms': new_apartment_rooms,
                        'bathrooms': new_apartment_bathrooms,
                        'sqm': new_apartment_sqm
                    }
                    save_custom_apartment(new_apartment)
                    st.success(f"Appartamento '{new_apartment_name}' salvato!")
                    st.rerun()
        
        # Selezione tipologia video
        st.subheader("📝 Seleziona Tipologia Video")
        video_types = get_video_types()
        
        # Mostra tipologie esistenti
        if video_types:
            selected_video_type = st.selectbox(
                "Scegli una tipologia esistente:",
                [vt['name'] for vt in video_types],
                index=None,
                placeholder="Seleziona una tipologia..."
            )
        else:
            selected_video_type = None
        
        # Opzione per aggiungere nuova tipologia
        with st.expander("➕ Aggiungi nuova tipologia video"):
            new_video_type_name = st.text_input("Nome nuova tipologia:")
            new_video_type_description = st.text_area("Descrizione:")
            
            if st.button("Salva nuova tipologia"):
                if new_video_type_name:
                    new_video_type = {
                        'name': new_video_type_name,
                        'description': new_video_type_description
                    }
                    save_custom_video_type(new_video_type)
                    st.success(f"Tipologia '{new_video_type_name}' salvata!")
                    st.rerun()
        
        # Controlli per procedere
        if selected_apartment and selected_video_type:
            st.success("✅ Tutti i campi sono compilati correttamente!")
            
            # Pulsante per elaborare il video
            if st.button("🎬 Elabora Video", type="primary"):
                with st.spinner("Elaborazione in corso..."):
                    try:
                        # Salva il file temporaneamente
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            temp_video_path = tmp_file.name
                        
                        # Trova l'appartamento e la tipologia selezionati
                        apartment = next((apt for apt in apartments if apt['name'] == selected_apartment), None)
                        video_type = next((vt for vt in video_types if vt['name'] == selected_video_type), None)
                        
                        if apartment and video_type:
                            # Elabora il video
                            output_path = process_video(
                                temp_video_path, 
                                apartment, 
                                video_type
                            )
                            
                            if output_path and os.path.exists(output_path):
                                st.success("✅ Video elaborato con successo!")
                                
                                # Mostra il video elaborato
                                with open(output_path, "rb") as video_file:
                                    st.video(video_file.read())
                                
                                # Pulsante per caricare su YouTube
                                if st.button("📤 Carica su YouTube", type="secondary"):
                                    # Controlla setup YouTube
                                    youtube_status = check_youtube_setup()
                                    if youtube_status['status'] == 'ready':
                                        try:
                                            # Carica su YouTube
                                            video_url = upload_to_youtube(output_path, apartment, video_type)
                                            if video_url:
                                                st.success(f"✅ Video caricato su YouTube!")
                                                st.markdown(f"**Link:** {video_url}")
                                                
                                                # Salva il progresso
                                                progress_data = {
                                                    'timestamp': datetime.now().isoformat(),
                                                    'apartment': apartment['name'],
                                                    'video_type': video_type['name'],
                                                    'youtube_url': video_url,
                                                    'file_name': uploaded_file.name
                                                }
                                                save_progress(progress_data)
                                                
                                        except Exception as e:
                                            st.error(f"❌ Errore durante il caricamento su YouTube: {str(e)}")
                                    else:
                                        st.error(f"❌ Setup YouTube non configurato: {youtube_status['message']}")
                                
                                # Pulsante per scaricare il video
                                with open(output_path, "rb") as video_file:
                                    st.download_button(
                                        label="💾 Scarica Video Elaborato",
                                        data=video_file.read(),
                                        file_name=f"elaborato_{uploaded_file.name}",
                                        mime="video/mp4"
                                    )
                                
                                # Pulisci i file temporanei
                                try:
                                    os.unlink(temp_video_path)
                                    os.unlink(output_path)
                                except:
                                    pass
                            else:
                                st.error("❌ Errore durante l'elaborazione del video")
                        else:
                            st.error("❌ Errore: appartamento o tipologia video non trovati")
                            
                    except Exception as e:
                        st.error(f"❌ Errore durante l'elaborazione: {str(e)}")
                        # Pulisci i file temporanei
                        try:
                            os.unlink(temp_video_path)
                        except:
                            pass
        else:
            if not selected_apartment:
                st.warning("⚠️ Seleziona un appartamento")
            if not selected_video_type:
                st.warning("⚠️ Seleziona una tipologia video")

# Tab 2: Gestione Account YouTube
with tab2:
    st.header("📊 Gestione Account YouTube")
    
    # Dashboard account
    st.subheader("📈 Dashboard Account")
    accounts_status = account_manager.get_accounts_status()
    
    if accounts_status:
        # Crea una tabella con lo stato degli account
        status_data = []
        for account in accounts_status:
            status_data.append({
                "Account": account['name'],
                "Stato": "🟢 Attivo" if account['active'] else "🔴 Inattivo",
                "Upload Oggi": f"{account['daily_uploads']}/{account['max_daily_uploads']}",
                "Disponibile": "✅ Sì" if account['available'] else "❌ No",
                "Token": "✅ Salvato" if account['token_exists'] else "❌ Mancante",
                "Ultimo Uso": account['last_used'] or "Mai"
            })
        
        df = pd.DataFrame(status_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("📝 Nessun account configurato. Aggiungi il primo account qui sotto.")
    
    # Aggiunta nuovo account
    st.subheader("➕ Aggiungi Nuovo Account")
    with st.form("add_account"):
        account_name = st.text_input("Nome Account:")
        client_id = st.text_input("Client ID:")
        client_secret = st.text_input("Client Secret:", type="password")
        project_id = st.text_input("Project ID:", value="knowledge-base-457009")
        max_uploads = st.number_input("Limite upload giornalieri:", min_value=1, max_value=10, value=5)
        
        if st.form_submit_button("Aggiungi Account"):
            if account_name and client_id and client_secret:
                account_manager.add_account(account_name, client_id, client_secret, project_id, max_uploads)
                st.success(f"Account '{account_name}' aggiunto con successo!")
                st.rerun()
            else:
                st.error("Compila tutti i campi obbligatori")
    
    # Gestione account esistenti
    if accounts_status:
        st.subheader("⚙️ Gestione Account")
        
        for account in accounts_status:
            with st.expander(f"Account: {account['name']}"):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if st.button(f"{'🔴 Disattiva' if account['active'] else '🟢 Attiva'}", key=f"toggle_{account['name']}"):
                        account_manager.toggle_account_status(account['name'])
                        st.rerun()
                
                with col2:
                    if st.button("🔄 Reset Contatore", key=f"reset_{account['name']}"):
                        account_manager.reset_account_usage(account['name'])
                        st.rerun()
                
                with col3:
                    if st.button("🗑️ Rimuovi", key=f"remove_{account['name']}"):
                        account_manager.remove_account(account['name'])
                        st.rerun()
                
                with col4:
                    if st.button("🔑 Gestisci Token", key=f"token_{account['name']}"):
                        st.session_state['manage_token_account'] = account['name']
                        st.rerun()
                
                # Modifica limite upload
                new_limit = st.number_input(
                    "Nuovo limite upload:", 
                    min_value=1, 
                    max_value=10, 
                    value=account['max_daily_uploads'],
                    key=f"limit_{account['name']}"
                )
                if st.button("💾 Aggiorna Limite", key=f"update_limit_{account['name']}"):
                    account_manager.update_account_limit(account['name'], new_limit)
                    st.rerun()
    
    # Debug section
    with st.expander("🔧 Debug"):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Ricarica Account Manager"):
                account_manager = YouTubeAccountManager()
                st.success("Account manager ricaricato!")
            
            if st.button("🔄 Reset Tutti i Contatori"):
                account_manager.reset_all_accounts_usage()
                st.success("Tutti i contatori resettati!")
        
        with col2:
            if st.button("📊 Mostra Configurazione Completa"):
                config = account_manager.export_accounts_config()
                st.json(config)

# Tab 3: Gestione Token
with tab3:
    st.header("🔑 Gestione Token YouTube")
    
    # Informazioni sui token
    token_info = account_manager.get_token_info()
    
    if token_info:
        st.subheader("📋 Stato Token")
        
        # Crea una tabella con lo stato dei token
        token_data = []
        for token in token_info:
            token_data.append({
                "Account": token['account_name'],
                "Token Esiste": "✅ Sì" if token['token_exists'] else "❌ No",
                "Token Valido": "✅ Sì" if token['token_valid'] else "❌ No",
                "File Token": token['token_file']
            })
        
        df = pd.DataFrame(token_data)
        st.dataframe(df, use_container_width=True)
        
        # Gestione token per account specifico
        st.subheader("⚙️ Gestione Token per Account")
        
        account_names = [token['account_name'] for token in token_info]
        selected_account = st.selectbox(
            "Seleziona account per gestire il token:",
            account_names
        )
        
        if selected_account:
            selected_token = next(t for t in token_info if t['account_name'] == selected_account)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔑 Autentica Account", key=f"auth_{selected_account}"):
                    try:
                        account = next(acc for acc in account_manager.accounts if acc['name'] == selected_account)
                        credentials = account_manager.get_credentials_for_account(account)
                        if credentials:
                            st.success(f"✅ Token salvato per '{selected_account}'!")
                        else:
                            st.error(f"❌ Errore nell'autenticazione per '{selected_account}'")
                    except Exception as e:
                        st.error(f"❌ Errore: {str(e)}")
            
            with col2:
                if st.button("🗑️ Rimuovi Token", key=f"remove_token_{selected_account}"):
                    token_file = f"token_{selected_account.lower().replace(' ', '_')}.pickle"
                    if os.path.exists(token_file):
                        try:
                            os.remove(token_file)
                            st.success(f"✅ Token rimosso per '{selected_account}'!")
                        except Exception as e:
                            st.error(f"❌ Errore nel rimuovere il token: {str(e)}")
                    else:
                        st.warning(f"⚠️ Nessun token trovato per '{selected_account}'")
            
            with col3:
                if st.button("🔄 Verifica Token", key=f"verify_{selected_account}"):
                    if selected_token['token_valid']:
                        st.success(f"✅ Token valido per '{selected_account}'!")
                    else:
                        st.error(f"❌ Token non valido per '{selected_account}'")
        
        # Test upload
        st.subheader("🧪 Test Upload")
        test_account = st.selectbox(
            "Seleziona account per test upload:",
            [acc['name'] for acc in account_manager.accounts if acc.get('active', True)]
        )
        
        if test_account and st.button("🎬 Test Upload"):
            try:
                account = next(acc for acc in account_manager.accounts if acc['name'] == test_account)
                credentials = account_manager.get_credentials_for_account(account)
                if credentials:
                    st.success(f"✅ Credenziali valide per '{test_account}'!")
                    st.info(f"Account disponibile per upload: {account.get('daily_uploads', 0)}/{account.get('max_daily_uploads', 5)}")
                else:
                    st.error(f"❌ Credenziali non valide per '{test_account}'")
            except Exception as e:
                st.error(f"❌ Errore nel test: {str(e)}")
    
    else:
        st.info("📝 Nessun account configurato. Aggiungi account nella sezione 'Gestione Account YouTube'.")
    
    # Informazioni generali
    st.subheader("ℹ️ Informazioni sui Token")
    st.markdown("""
    **Come funzionano i token:**
    - I token vengono salvati automaticamente quando autentichi un account
    - I token scadono dopo un certo periodo e devono essere rinnovati
    - Ogni account ha il proprio file token separato
    - I token sono necessari per caricare video su YouTube
    
    **Gestione automatica:**
    - I contatori si resettano automaticamente ogni giorno
    - Gli account vengono usati in rotazione quando raggiungono il limite
    - I token vengono verificati automaticamente prima di ogni upload
    """)

# Tab 4: Gestione Appartamenti
with tab4:
    st.header("🏠 Gestione Appartamenti")
    
    # Mostra appartamenti esistenti
    apartments = load_apartments()
    all_progress = load_all_progress()
    
    if apartments:
        st.subheader("📋 Appartamenti con Video Processati")
        
        # Raggruppa i progressi per appartamento
        apartment_progress = {}
        for progress in all_progress:
            apartment_name = progress['apartment']
            video_type = progress['video_type']
            
            if apartment_name not in apartment_progress:
                apartment_progress[apartment_name] = {
                    'video_types': set(),
                    'youtube_urls': [],
                    'drive_urls': [],
                    'manuals_it': [],
                    'manuals_en': []
                }
            
            apartment_progress[apartment_name]['video_types'].add(video_type)
            
            # Aggiungi URL se disponibili
            if progress.get('youtube_url'):
                apartment_progress[apartment_name]['youtube_urls'].append(progress['youtube_url'])
            
            if progress.get('drive_url'):
                apartment_progress[apartment_name]['drive_urls'].append(progress['drive_url'])
            
            if progress.get('manual_it'):
                apartment_progress[apartment_name]['manuals_it'].append(progress['manual_it'])
            
            if progress.get('manual_en'):
                apartment_progress[apartment_name]['manuals_en'].append(progress['manual_en'])
        
        # Mostra gli appartamenti con video processati
        if apartment_progress:
            for apartment_name, progress_data in apartment_progress.items():
                # Trova i dettagli dell'appartamento
                apartment_details = next((apt for apt in apartments if apt['name'] == apartment_name), None)
                
                # Crea una card per ogni appartamento
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    
                    with col1:
                        st.markdown(f"**🏠 {apartment_name}**")
                        if apartment_details:
                            st.markdown(f"📍 {apartment_details.get('address', 'Indirizzo non disponibile')}")
                            st.markdown(f"💰 €{apartment_details.get('price', 0):,} | 🏠 {apartment_details.get('rooms', 0)} stanze | 📏 {apartment_details.get('sqm', 0)} m²")
                    
                    with col2:
                        # Mostra le emoji delle tipologie processate
                        video_type_emojis = {
                            'asciugatrice': '👕',
                            'caldaia': '🔥',
                            'check-in': '🔑',
                            'condizionamento': '❄️',
                            'forno': '🍳',
                            'frigorifero': '🧊',
                            'lavastoviglie': '🍽️',
                            'lavatrice': '👚',
                            'microonde': '⚡',
                            'piano_cottura': '🔥',
                            'riscaldamento': '🌡️',
                            'scaldabagno': '🚿',
                            'spazzatura': '🗑️'
                        }
                        
                        emoji_list = []
                        for video_type in progress_data['video_types']:
                            emoji = video_type_emojis.get(video_type.lower(), '📹')
                            emoji_list.append(emoji)
                        
                        st.markdown(f"**Tipologie processate:** {' '.join(emoji_list)}")
                        st.markdown(f"**Video totali:** {len(progress_data['video_types'])}")
                    
                    with col3:
                        if st.button("⚙️ Gestisci", key=f"manage_{apartment_name}"):
                            st.session_state['selected_apartment'] = apartment_name
                            st.session_state['apartment_progress'] = progress_data
                            st.rerun()
                    
                    st.divider()
        
        # Sezione dettagli appartamento
        if 'selected_apartment' in st.session_state:
            selected_apartment = st.session_state['selected_apartment']
            apartment_progress = st.session_state['apartment_progress']
            
            st.subheader(f"📋 Dettagli: {selected_apartment}")
            
            # Tabs per i diversi tipi di contenuto
            tab_details, tab_youtube, tab_drive, tab_manuals = st.tabs([
                "📊 Statistiche", "📺 YouTube", "☁️ Drive", "📚 Manuali"
            ])
            
            with tab_details:
                st.markdown(f"**Appartamento:** {selected_apartment}")
                st.markdown(f"**Tipologie processate:** {len(apartment_progress['video_types'])}")
                st.markdown(f"**Video YouTube:** {len(apartment_progress['youtube_urls'])}")
                st.markdown(f"**File Drive:** {len(apartment_progress['drive_urls'])}")
                st.markdown(f"**Manualetti IT:** {len(apartment_progress['manuals_it'])}")
                st.markdown(f"**Manualetti EN:** {len(apartment_progress['manuals_en'])}")
                
                # Lista delle tipologie
                st.markdown("**Tipologie video:**")
                for video_type in sorted(apartment_progress['video_types']):
                    st.markdown(f"- {video_type}")
            
            with tab_youtube:
                if apartment_progress['youtube_urls']:
                    st.markdown("**Video caricati su YouTube:**")
                    for i, url in enumerate(apartment_progress['youtube_urls'], 1):
                        st.markdown(f"{i}. [{url}]({url})")
                else:
                    st.info("📝 Nessun video caricato su YouTube")
            
            with tab_drive:
                if apartment_progress['drive_urls']:
                    st.markdown("**File su Google Drive:**")
                    for i, url in enumerate(apartment_progress['drive_urls'], 1):
                        st.markdown(f"{i}. [{url}]({url})")
                else:
                    st.info("📝 Nessun file su Google Drive")
            
            with tab_manuals:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**📖 Manualetti IT:**")
                    if apartment_progress['manuals_it']:
                        for i, url in enumerate(apartment_progress['manuals_it'], 1):
                            st.markdown(f"{i}. [{url}]({url})")
                    else:
                        st.info("📝 Nessun manualetto IT")
                
                with col2:
                    st.markdown("**📖 Manualetti EN:**")
                    if apartment_progress['manuals_en']:
                        for i, url in enumerate(apartment_progress['manuals_en'], 1):
                            st.markdown(f"{i}. [{url}]({url})")
                    else:
                        st.info("📝 Nessun manualetto EN")
            
            # Pulsante per tornare indietro
            if st.button("← Torna alla lista"):
                del st.session_state['selected_apartment']
                del st.session_state['apartment_progress']
                st.rerun()
        
        # Statistiche generali
        st.subheader("📊 Statistiche Generali")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Appartamenti con video", len(apartment_progress))
        
        with col2:
            total_videos = sum(len(data['video_types']) for data in apartment_progress.values())
            st.metric("Video totali", total_videos)
        
        with col3:
            total_youtube = sum(len(data['youtube_urls']) for data in apartment_progress.values())
            st.metric("Upload YouTube", total_youtube)
        
        with col4:
            total_manuals = sum(len(data['manuals_it']) + len(data['manuals_en']) for data in apartment_progress.values())
            st.metric("Manualetti", total_manuals)
    
    else:
        st.info("📝 Nessun appartamento configurato")
    
    # Sezione per aggiungere nuovi appartamenti
    st.subheader("➕ Aggiungi Nuovo Appartamento")
    with st.form("add_apartment_form"):
        new_apartment_name = st.text_input("Nome appartamento:")
        new_apartment_address = st.text_input("Indirizzo:")
        new_apartment_price = st.number_input("Prezzo (€):", min_value=0, value=0)
        new_apartment_rooms = st.number_input("Numero stanze:", min_value=1, value=1)
        new_apartment_bathrooms = st.number_input("Numero bagni:", min_value=1, value=1)
        new_apartment_sqm = st.number_input("Metri quadrati:", min_value=1, value=50)
        
        if st.form_submit_button("Salva appartamento"):
            if new_apartment_name:
                new_apartment = {
                    'name': new_apartment_name,
                    'address': new_apartment_address,
                    'price': new_apartment_price,
                    'rooms': new_apartment_rooms,
                    'bathrooms': new_apartment_bathrooms,
                    'sqm': new_apartment_sqm
                }
                save_custom_apartment(new_apartment)
                st.success(f"Appartamento '{new_apartment_name}' salvato!")
                st.rerun()
            else:
                st.error("Inserisci il nome dell'appartamento")

# Tab 5: Gestione Tipologie Video
with tab5:
    st.header("📝 Gestione Tipologie Video")
    
    # Mostra tipologie esistenti
    video_types = get_video_types()
    if video_types:
        st.subheader("📋 Tipologie Configurate")
        
        # Crea una tabella con le tipologie
        vt_data = []
        for vt in video_types:
            vt_data.append({
                "Nome": vt['name'],
                "Descrizione": vt.get('description', 'N/A')
            })
        
        df = pd.DataFrame(vt_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("📝 Nessuna tipologia configurata")
    
    # Statistiche
    st.subheader("📊 Statistiche")
    if video_types:
        total_types = len(video_types)
        st.metric("Totale Tipologie", total_types)

# Tab 6: Progresso Video
with tab6:
    st.header("📈 Progresso Video")
    
    # Carica tutti i progressi
    all_progress = load_all_progress()
    
    if all_progress:
        st.subheader("📋 Video Completati")
        
        # Filtri
        col1, col2 = st.columns(2)
        with col1:
            apartments_filter = st.multiselect(
                "Filtra per appartamento:",
                options=list(set(p['apartment'] for p in all_progress)),
                default=[]
            )
        
        with col2:
            video_types_filter = st.multiselect(
                "Filtra per tipologia:",
                options=list(set(p['video_type'] for p in all_progress)),
                default=[]
            )
        
        # Filtra i progressi
        filtered_progress = all_progress
        if apartments_filter:
            filtered_progress = [p for p in filtered_progress if p['apartment'] in apartments_filter]
        if video_types_filter:
            filtered_progress = [p for p in filtered_progress if p['video_type'] in video_types_filter]
        
        # Mostra i progressi filtrati
        if filtered_progress:
            # Crea una tabella con i progressi
            progress_data = []
            for p in filtered_progress:
                progress_data.append({
                    "Data": p['timestamp'][:10],
                    "Ora": p['timestamp'][11:19],
                    "Appartamento": p['apartment'],
                    "Tipologia": p['video_type'],
                    "File": p['file_name'],
                    "YouTube": p.get('youtube_url', 'N/A')
                })
            
            df = pd.DataFrame(progress_data)
            st.dataframe(df, use_container_width=True)
            
            # Statistiche
            st.subheader("📊 Statistiche")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Totale Video", len(filtered_progress))
            with col2:
                youtube_uploads = len([p for p in filtered_progress if p.get('youtube_url') != 'N/A'])
                st.metric("Upload YouTube", youtube_uploads)
            with col3:
                unique_apartments = len(set(p['apartment'] for p in filtered_progress))
                st.metric("Appartamenti Usati", unique_apartments)
        else:
            st.info("📝 Nessun video trovato con i filtri selezionati")
    else:
        st.info("📝 Nessun video completato ancora") 