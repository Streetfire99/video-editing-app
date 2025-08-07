"""
Subpage Inventario
Gestisce la logica e il rendering della sezione inventario per add_property.
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
from datetime import datetime

logger = logging.getLogger(__name__)

# Predefined items for each room
ROOM_ITEMS = {
    "Soggiorno": [
        "Divano", "Poltrona", "Tavolino", "TV", "Mobile TV", "Lampada da tavolo", 
        "Lampada da terra", "Tappeto", "Quadri", "Piante", "Scaffale", "Libreria",
        "Sedia", "Specchio", "Cuscini", "Coperta", "Ventilatore", "Condizionatore"
    ],
    "Camera da Letto": [
        "Letto", "Materasso", "Cuscini", "Comodino", "Lampada da comodino", 
        "Armadio", "Cassettiera", "Specchio", "Sedia", "Tappeto", "Quadri",
        "Lampada da terra", "Ventilatore", "Condizionatore", "Tenda", "Coperta",
        "Cuscini decorativi", "Scaffale"
        ],
        "Cucina": [
        "Frigorifero", "Forno", "Microonde", "Lavastoviglie", "Lavello", 
        "Piano cottura", "Cappa", "Mobili cucina", "Sedia da cucina", 
        "Tavolo da cucina", "Pentole", "Padelle", "Piatti", "Bicchieri",
        "Posate", "Tovaglioli", "Tovaglie", "Macchina del caffè", "Tostapane",
        "Frullatore", "Mixer", "Bilancia", "Tagliere", "Coltelli"
    ],
    "Bagno": [
        "Washbasin", "WC", "Doccia", "Vasca", "Specchio", "Mobile bagno",
        "Asciugamani", "Tappetino", "Porta asciugamani", "Porta carta igienica",
        "Porta sapone", "Tendina doccia", "Tappeto bagno", "Lampada bagno",
        "Ventilatore bagno", "Scalda asciugamani", "Bidet", "Porta spazzolino"
        ],
        "Altro": [
        "Lavatrice", "Asciugatrice", "Ferro da stiro", "Tavolo da stiro",
        "Aspirapolvere", "Scopa", "Paletta", "Secchio", "Spazzolino",
        "Prodotti pulizia", "Carta igienica", "Sapone", "Shampoo", "Balsamo",
        "Dentifricio", "Spazzolino", "Rasoio", "Deodorante", "Crema viso",
        "Medicinali", "Primo soccorso", "Estintore", "Rivelatore fumo"
    ]
}

@st.cache_resource
def load_whisper_model():
    """Carica il modello Whisper per la trascrizione."""
    try:
        return whisper.load_model("base")
    except Exception as e:
        st.error(f"Errore nel caricamento del modello Whisper: {e}")
        return None

def create_audio_recorder(component_name):
    """Crea un componente audio recorder con nome univoco."""
    import streamlit.components.v1 as components
    
    # Percorso corretto per il componente
    build_dir = os.path.join(os.path.dirname(__file__), "..", "..", ".venv311", "lib", "python3.11", "site-packages", "st_audiorec", "frontend", "build")
    
    if not os.path.exists(build_dir):
        st.error(f"Component directory not found: {build_dir}")
        return None
    
    try:
        st_audiorec = components.declare_component(component_name, path=build_dir)
        return st_audiorec
    except Exception as e:
        st.error(f"Error creating audio recorder: {e}")
        return None

def process_audio_with_openai(transcription_text):
    """Processa l'audio con OpenAI per estrarre informazioni sugli oggetti per tutte le stanze."""
    try:
        # Crea il prompt dinamico per tutte le stanze
        all_items_text = ""
        for room_name, items in ROOM_ITEMS.items():
            all_items_text += f"\n{room_name}: {', '.join(items)}"
        
        prompt = f"""
        Analizza la seguente trascrizione audio e estrai informazioni sugli oggetti dell'inventario per tutte le stanze.
        
        Trascrizione: "{transcription_text}"
        
        Item predefiniti disponibili per stanza:
        {all_items_text}
        
        Estrai le informazioni nel seguente formato JSON:
        [
            {{
                "stanza": "nome della stanza (Soggiorno, Camera da Letto, Cucina, Bagno, Altro)",
                "articolo": "nome dell'oggetto (usa uno degli item predefiniti se possibile)",
                "quantita": numero,
                "posizione": "posizione specifica nella stanza"
            }}
        ]
        
        Regole:
        1. Usa preferibilmente gli item predefiniti se corrispondono
        2. Se l'oggetto non è nella lista predefinita, aggiungilo comunque
        3. Se non viene specificata la quantità, usa 1
        4. Se non viene specificata la posizione, lascia vuoto
        5. Associa ogni oggetto alla stanza appropriata
        6. Se non è chiaro a quale stanza appartiene, usa "Altro"
        7. Restituisci solo il JSON, senza testo aggiuntivo
        """
        
        # Configura OpenAI
        openai.api_key = st.secrets.get("OPENAI_API_KEY")
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Sei un assistente esperto nell'analisi di inventari immobiliari."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        # Estrai la risposta
        response_text = response.choices[0].message.content.strip()
        
        # Prova a parsare il JSON
        import json
        try:
            # Rimuovi eventuali backticks e "json" dal testo
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            items = json.loads(response_text)
            
            if isinstance(items, list):
                return items
            else:
                st.error("Formato di risposta non valido")
                return None
                
        except json.JSONDecodeError as e:
            st.error(f"Errore nel parsing JSON: {e}")
            st.text("Risposta ricevuta:")
            st.text(response_text)
            return None
            
    except Exception as e:
        st.error(f"Errore durante l'elaborazione con OpenAI: {e}")
        logger.error(f"Error processing with OpenAI: {e}")
        return None

def render_global_audio_recorder():
    """Rende il registratore audio globale per tutte le stanze."""
    st.markdown("#### 🎤 Registrazione Audio Globale")
    st.write("Registra una descrizione audio di tutti gli oggetti dell'inventario. L'AI li distribuirà automaticamente nelle stanze appropriate.")
    
    # Mostra tutti gli item predefiniti per riferimento
    with st.expander("📋 Item predefiniti disponibili per riferimento"):
        for room_name, items in ROOM_ITEMS.items():
            st.markdown(f"**{room_name}:**")
            st.text(", ".join(items))
            st.markdown("---")
    
    # Crea un componente audio recorder univoco
    component_name = "st_audiorec_global_inventario"
    st_audiorec = create_audio_recorder(component_name)
    
    if st_audiorec is None:
        st.warning("⚠️ Registratore audio non disponibile")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Registrazione audio
        audio_data = st_audiorec()
        
        if audio_data is not None:
            st.session_state['inventario_global_audio_data'] = audio_data
            
            # Pulsante per processare l'audio
            if st.button("🔍 Processa Audio Globale", key="process_global_audio_inventario"):
                try:
                    # Salva l'audio temporaneamente
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                        tmp_file.write(audio_data)
                        audio_path = tmp_file.name
                    
                    # Trascrivi con Whisper
                    model = load_whisper_model()
                    if model:
                        result = model.transcribe(audio_path)
                        transcription = result["text"]
                        
                        st.markdown("**Trascrizione:**")
                        st.write(transcription)
                        
                        # Processa con OpenAI
                        extracted_items = process_audio_with_openai(transcription)
                        if extracted_items:
                            st.success("✅ **Oggetti estratti con successo!**")
                            st.json(extracted_items)
                            
                            # Distribuisci gli oggetti estratti nelle tabelle appropriate
                            for item in extracted_items:
                                room_name = item.get('stanza', 'Altro')
                                add_item_to_room_table(room_name, item)
                            
                            st.session_state['inventario_processed_global_audio_data'] = audio_data
                            st.success("✅ Oggetti distribuiti nelle tabelle appropriate!")
                            st.rerun() # Ricarica per mostrare i campi aggiornati
                        else:
                            st.warning("⚠️ Non è stato possibile estrarre oggetti.")
                        
                        os.unlink(audio_path)
                    else:
                        st.error("❌ Modello Whisper non disponibile")
                except Exception as e:
                    st.error(f"❌ Errore durante l'elaborazione: {e}")
                    logger.error(f"Errore durante l'elaborazione dell'audio registrato: {e}")

        with col2:
            if st.button("🔄 Registra di Nuovo", key="registra_nuovo_global_inventario"):
                st.session_state['inventario_global_audio_data'] = None
                st.session_state['inventario_processed_global_audio_data'] = None
                st.rerun()

def get_room_data(selected_apartment, room_name):
    """Ottiene i dati per una specifica stanza."""
    cache_key = f"inventario_data_{selected_apartment}_{room_name}"
    
    if cache_key not in st.session_state:
        # Carica i dati dal foglio inventario
        all_data = get_data("inventario")
        room_data = []
        
        if all_data is not None and not all_data.empty:
            try:
                # Filtra i dati per appartamento e stanza
                filtered_data = all_data[
                    (all_data['appartamento'] == selected_apartment) & 
                    (all_data['stanza'] == room_name)
                ]
                
                if not filtered_data.empty:
                    room_data = filtered_data.to_dict('records')
                    logger.info(f"Loaded {len(room_data)} items for {room_name} in {selected_apartment}")
                else:
                    logger.info(f"No existing data found for {room_name} in {selected_apartment}")
                    
            except Exception as e:
                logger.error(f"Error filtering data for {room_name}: {e}")
                room_data = []
        else:
            logger.info(f"No inventario data available for {selected_apartment}")
            
        st.session_state[cache_key] = room_data
    
    return st.session_state[cache_key]

def add_item_to_room_table(room_name, item):
    """Aggiunge un oggetto alla tabella della stanza."""
    if f"inventario_table_{room_name}" not in st.session_state:
        st.session_state[f"inventario_table_{room_name}"] = []
    
    new_item = {
        'articolo': item.get('articolo', ''),
        'quantita': item.get('quantita', 1),
        'posizione': item.get('posizione', ''),
        'data_aggiornamento': datetime.now().strftime("%Y-%m-%d")
    }
    
    st.session_state[f"inventario_table_{room_name}"].append(new_item)

def create_room_table_data(room_name, existing_data):
    """Crea i dati della tabella con item predefiniti."""
    predefined_items = ROOM_ITEMS.get(room_name, [])
    table_data = []
    
    # Prima, aggiungi tutti gli item predefiniti
    for item in predefined_items:
        # Cerca se esiste già un record per questo item
        existing_item = None
        if existing_data:
            for record in existing_data:
                if record.get('articolo') == item:
                    existing_item = record
                    break
        
        if existing_item:
            # Usa i dati esistenti
            table_data.append({
                'articolo': item,
                'quantita': existing_item.get('quantita', 0),
                'posizione': existing_item.get('posizione', ''),
                'data_aggiornamento': existing_item.get('data_aggiornamento', '')
            })
        else:
            # Crea una nuova riga vuota
            table_data.append({
                'articolo': item,
                'quantita': 0,
                'posizione': '',
                'data_aggiornamento': ''
            })
    
    # Poi, aggiungi gli item personalizzati che non sono nella lista predefinita
    if existing_data:
        for record in existing_data:
            articolo = record.get('articolo', '')
            if articolo and articolo not in predefined_items:
                # Questo è un item personalizzato
                table_data.append({
                    'articolo': articolo,
                    'quantita': record.get('quantita', 0),
                    'posizione': record.get('posizione', ''),
                    'data_aggiornamento': record.get('data_aggiornamento', '')
                })
    
    return table_data

def render_room_table(room_name, existing_data, selected_apartment):
    """Rende una tabella per una stanza specifica con item predefiniti."""
    st.markdown(f"### 🏠 {room_name}")
    
    # Crea i dati della tabella con item predefiniti
    table_data = create_room_table_data(room_name, existing_data)
    
    # Inizializza la tabella se non esiste
    if f"inventario_table_{room_name}" not in st.session_state:
        st.session_state[f"inventario_table_{room_name}"] = table_data
    
    # Ottieni i dati della tabella
    current_table_data = st.session_state[f"inventario_table_{room_name}"]
    
    # Converti in DataFrame per la visualizzazione
    if current_table_data:
        df = pd.DataFrame(current_table_data)
        # Assicurati che tutte le colonne necessarie siano presenti
        required_columns = ['articolo', 'quantita', 'posizione', 'data_aggiornamento']
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''
        
        # Riordina le colonne
        df = df[required_columns]
    else:
        df = pd.DataFrame(columns=['articolo', 'quantita', 'posizione', 'data_aggiornamento'])
    
    # Mostra la tabella esistente
    st.dataframe(df, use_container_width=True)
    
    # Form per aggiungere nuovi oggetti (non predefiniti)
    with st.expander(f"➕ Aggiungi oggetto personalizzato a {room_name}"):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_articolo = st.text_input("Articolo", key=f"new_articolo_{room_name}")
        with col2:
            new_quantita = st.number_input("Quantità", min_value=1, value=1, key=f"new_quantita_{room_name}")
        with col3:
            new_posizione = st.text_input("Posizione", key=f"new_posizione_{room_name}")
        
        if st.button("Aggiungi", key=f"add_item_{room_name}"):
            if new_articolo:
                new_item = {
                    'articolo': new_articolo,
                    'quantita': new_quantita,
                    'posizione': new_posizione,
                    'data_aggiornamento': datetime.now().strftime("%Y-%m-%d")
                }
                current_table_data.append(new_item)
                st.success(f"Oggetto aggiunto a {room_name}")
                st.rerun()
    
    st.markdown("---")

def render_inventario_subpage(selected_apartment, existing_data=None):
    """Rende la subpage Inventario con 5 tabelle predefinite + 1 personalizzata."""
    
    st.markdown("#### Gestione Inventario")
    st.write("Gestisci l'inventario dell'appartamento organizzato per stanze.")
    
    # Registrazione audio globale
    render_global_audio_recorder()
    st.markdown("---")
    
    # Definizione delle 5 stanze predefinite
    predefined_rooms = ["Soggiorno", "Camera da Letto", "Cucina", "Bagno", "Altro"]
    
    # Renderizza ogni stanza in sezioni separate
    for room_name in predefined_rooms:
        room_data = get_room_data(selected_apartment, room_name)
        render_room_table(room_name, room_data, selected_apartment)
    
    # Tabella personalizzata per oggetti aggiuntivi
    st.markdown("### 📝 Oggetti Aggiuntivi")
    st.write("Aggiungi oggetti che non rientrano nelle categorie precedenti.")
    
    # Inizializza la tabella personalizzata
    if "inventario_table_personalizzati" not in st.session_state:
        st.session_state["inventario_table_personalizzati"] = []
    
    # Mostra la tabella personalizzata
    custom_data = st.session_state["inventario_table_personalizzati"]
    if custom_data:
        custom_df = pd.DataFrame(custom_data)
        display_custom_df = custom_df[['articolo', 'quantita', 'posizione', 'data_aggiornamento']].copy()
    else:
        display_custom_df = pd.DataFrame(columns=['articolo', 'quantita', 'posizione', 'data_aggiornamento'])
    
    st.dataframe(display_custom_df, use_container_width=True)
    
    # Form per aggiungere oggetti personalizzati
    with st.expander("➕ Aggiungi oggetto personalizzato"):
        col1, col2, col3 = st.columns(3)
        with col1:
            custom_articolo = st.text_input("Articolo", key="new_articolo_custom")
        with col2:
            custom_quantita = st.number_input("Quantità", min_value=1, value=1, key="new_quantita_custom")
        with col3:
            custom_posizione = st.text_input("Posizione", key="new_posizione_custom")
        if st.button("Aggiungi", key="add_item_custom"):
            if custom_articolo:
                new_item = {
                    'articolo': custom_articolo,
                    'quantita': custom_quantita,
                    'posizione': custom_posizione,
                    'stanza': 'Altro',
                    'appartamento': selected_apartment
                }
                st.session_state[f"inventario_data_{selected_apartment}_Altro"].append(new_item)
                st.success("Oggetto aggiunto!")
                st.experimental_rerun()
    
    # Salvataggio
    if st.button("💾 Salva Inventario"):
        try:
            all_items = []
            
            # Raccogli tutti gli oggetti da tutte le tabelle
            for room_name in predefined_rooms:
                table_data = st.session_state.get(f"inventario_table_{room_name}", [])
                for item in table_data:
                    if item.get('quantita', 0) > 0:  # Salva solo gli item con quantità > 0
                        item_data = {
                            'appartamento': selected_apartment,
                            'stanza': room_name,
                            'articolo': item.get('articolo', ''),
                            'quantita': item.get('quantita', 0),
                            'posizione': item.get('posizione', ''),
                            'data_aggiornamento': item.get('data_aggiornamento', datetime.now().strftime("%Y-%m-%d"))
                        }
                        all_items.append(item_data)
            
            # Aggiungi gli oggetti personalizzati
            custom_items = st.session_state.get("inventario_table_personalizzati", [])
            for item in custom_items:
                if item.get('quantita', 0) > 0:
                    item_data = {
                        'appartamento': selected_apartment,
                        'stanza': 'Personalizzati',
                        'articolo': item.get('articolo', ''),
                        'quantita': item.get('quantita', 0),
                        'posizione': item.get('posizione', ''),
                        'data_aggiornamento': item.get('data_aggiornamento', datetime.now().strftime("%Y-%m-%d"))
                    }
                    all_items.append(item_data)
            
            # Salva tutti i dati
            if all_items:
                success = save_to_sheets("inventario", all_items)
                if success:
                    st.success("✅ Inventario salvato con successo!")
                    logger.info(f"Inventario saved for apartment: {selected_apartment}")
                else:
                    st.error("❌ Errore durante il salvataggio")
            else:
                st.warning("⚠️ Nessun oggetto da salvare")
                
        except Exception as e:
            st.error(f"❌ Errore: {e}")
            logger.error(f"Error saving inventario: {e}")
    
    # Pulsante per resettare tutte le tabelle
    if st.button("🔄 Reset Inventario"):
        for room_name in predefined_rooms:
            st.session_state[f"inventario_table_{room_name}"] = []
        st.session_state["inventario_table_personalizzati"] = []
        st.rerun() 