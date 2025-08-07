"""
Utility functions for the property management system.
"""

import os
import streamlit as st
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
import gspread
import json
import requests
import logging
import traceback
import sys
from pathlib import Path
import pandas as pd
import time
from googleapiclient.http import MediaIoBaseUpload
import io

# Setup logging
logger = logging.getLogger(__name__)

# Cache per le API calls
API_CACHE = {}
CACHE_DURATION = 300  # 5 minuti invece di 60 secondi per ridurre le chiamate API

def get_cached_data(key, fetch_func, *args, **kwargs):
    """Funzione helper per il caching dei dati API"""
    current_time = time.time()
    
    # Controlla se i dati sono in cache e ancora validi
    if key in API_CACHE:
        cached_data, timestamp = API_CACHE[key]
        if current_time - timestamp < CACHE_DURATION:
            logger.info(f"Using cached data for {key}")
            return cached_data
    
    # Se non in cache o scaduta, recupera i dati
    try:
        logger.info(f"Fetching fresh data for {key}")
        data = fetch_func(*args, **kwargs)
        API_CACHE[key] = (data, current_time)
        return data
    except Exception as e:
        logger.error(f"Error fetching data for {key}: {e}")
        # Se c'è un errore ma abbiamo dati in cache scaduti, usali comunque
        if key in API_CACHE:
            logger.warning(f"Using expired cached data for {key} due to API error")
            return API_CACHE[key][0]
        raise e

def clear_api_cache():
    """Pulisce la cache API"""
    global API_CACHE
    API_CACHE.clear()
    logger.info("API cache cleared")

# Configure logging
def setup_logger():
    """Setup and configure the logger."""
    # Create logs directory if it doesn't exist
    log_dir = Path('../logs')
    log_dir.mkdir(exist_ok=True)
    
    # Create a logger
    logger = logging.getLogger('property_management')
    logger.setLevel(logging.DEBUG)
    
    # Create handlers
    # File handler for all logs
    all_handler = logging.FileHandler(log_dir / 'all.log')
    all_handler.setLevel(logging.DEBUG)
    
    # File handler for errors only
    error_handler = logging.FileHandler(log_dir / 'error.log')
    error_handler.setLevel(logging.ERROR)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Create formatters and add it to handlers
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n%(funcName)s\n%(message)s')
    all_handler.setFormatter(log_format)
    error_handler.setFormatter(log_format)
    console_handler.setFormatter(log_format)
    
    # Add handlers to the logger
    logger.addHandler(all_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logger()

# Load environment variables
load_dotenv()

# Constants
def get_spreadsheet_id():
    """Get spreadsheet ID from secrets or environment variable"""
    try:
        # Try to get from Streamlit secrets first
        if 'st' in globals():
            spreadsheet_id = st.secrets.get('SPREADSHEET_ID')
            if spreadsheet_id:
                return spreadsheet_id
    except:
        pass
    
    # Fallback to environment variable
    env_spreadsheet_id = os.getenv('SPREADSHEET_ID')
    if env_spreadsheet_id:
        return env_spreadsheet_id
    
    # Default spreadsheet ID
    return "1Jd0FpZKboNYsr2lX502yVFq2BBHqy8lZmiO1GOhNaY0"

SPREADSHEET_ID = get_spreadsheet_id()
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def init_google_services():
    """Initialize Google services with detailed logging and caching."""
    try:
        # Check if services are already initialized in session state
        if 'sheets_service' in st.session_state and 'gspread_client' in st.session_state:
            logger.info("Returning cached Google services from session state.")
            return st.session_state.sheets_service, st.session_state.gspread_client

        logger.info("Initializing Google services...")
        
        # Try to get credentials from Streamlit secrets first
        try:
            google_credentials = st.secrets.get('GOOGLE_SHEETS_CREDENTIALS')
            if google_credentials:
                logger.info("Using Google credentials from Streamlit secrets")
                credentials_dict = json.loads(google_credentials)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict, scopes=SCOPES)
            else:
                # Fallback to service account key file
                logger.info("No Google credentials in secrets, trying service account key file")
                base_path = Path(__file__).resolve().parent.parent
                service_account_path = base_path / 'service_account_key.json'
                
                if not service_account_path.exists():
                    logger.warning(f"Service account key not found at {service_account_path}, trying utils.py directory.")
                    service_account_path = Path(__file__).resolve().parent / 'service_account_key.json'

                logger.debug(f"Attempting to load service account key from: {service_account_path}")
                
                if not os.path.exists(service_account_path):
                    logger.error(f"Service account key file not found at {service_account_path}")
                    st.error(f"Critical Error: service_account_key.json not found and no secrets configured")
                    return None, None

                credentials = service_account.Credentials.from_service_account_file(
                    str(service_account_path), scopes=SCOPES)
        except Exception as e:
            logger.error(f"Error loading Google credentials: {str(e)}")
            return None, None
        
        sheets_service = build('sheets', 'v4', credentials=credentials)
        gspread_client = gspread.authorize(credentials)
        
        # Cache the initialized services in session state
        st.session_state.sheets_service = sheets_service
        st.session_state.gspread_client = gspread_client
        
        logger.info("Google services initialized successfully and cached.")
        return sheets_service, gspread_client
    except Exception as e:
        logger.error(f"Error initializing Google services: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def get_sheet(sheet_name):
    """
    Get a specific sheet from the Google Spreadsheet with retry logic for rate limits.
    """
    max_retries = 3
    base_delay = 2  # secondi
    
    for attempt in range(max_retries):
        try:
            services = init_google_services()
            if services is None:
                logger.error("Failed to initialize Google services")
                return None
            
            sheets_service, gspread_client = services
            if gspread_client is None:
                logger.error("gspread_client is None")
                return None
                
            sheet = gspread_client.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
            return sheet
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error getting sheet {sheet_name} (attempt {attempt + 1}/{max_retries}): {error_msg}")
            
            # Gestione specifica per rate limit
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Backoff esponenziale
                    logger.warning(f"Rate limit exceeded for sheet {sheet_name}, retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Rate limit exceeded for sheet {sheet_name} after {max_retries} attempts")
                    # Imposta flag di errore API nella session state
                    if 'st' in globals():
                        st.session_state['api_error'] = True
                    return None
            else:
                logger.error(f"Traceback: {e}")
                return None
    
    return None

def get_data(sheet_name):
    """
    Recupera i dati da Google Sheets con caching e gestione errori migliorata.
    """
    cache_key = f"sheet_data_{sheet_name}"
    
    def fetch_sheet_data():
        try:
            logger.info(f"Fetching data for sheet: {sheet_name}")
            sheet = get_sheet(sheet_name)
            if sheet is None:
                logger.error(f"Sheet {sheet_name} not found")
                return None
            
            # Get all values from the sheet
            logger.info(f"Getting all values from sheet: {sheet_name}")
            all_values = sheet.get_all_values()
            
            if not all_values:
                logger.warning(f"No data found in sheet {sheet_name}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(all_values[1:], columns=all_values[0])
            logger.info(f"Headers found in {sheet_name}: {list(df.columns)}")
            logger.info(f"Data shape: {df.shape}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting sheet {sheet_name}: {e}")
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                logger.warning("Rate limit exceeded, will retry with cached data if available")
                # Aspetta un po' prima di riprovare
                time.sleep(2)
            return None
    
    # Usa il sistema di caching
    return get_cached_data(cache_key, fetch_sheet_data)

def save_to_sheets(sheet_name, data):
    """Save data to Google Sheets"""
    try:
        # Get the sheet
        sheets_service, gspread_client = init_google_services()
        sheet = gspread_client.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
        if not sheet:
            logger.error(f"Sheet {sheet_name} not found")
            return False
            
        # Convert data to list of lists format
        if isinstance(data, dict):
            # Get headers from the first row
            headers = sheet.row_values(1)
            if not headers:
                logger.error(f"No headers found in sheet {sheet_name}")
                return False
            # Aggiungi dinamicamente le colonne mancanti per i vicini
            for k in data.keys():
                if k not in headers:
                    headers.append(k)
                    sheet.add_cols(1)
                    col_index = len(headers)
                    sheet.update_cell(1, col_index, k)
            # Ricostruisci la lista headers aggiornata
            headers = sheet.row_values(1)
            # Prepara la riga da scrivere
            row = [data.get(h, "") for h in headers]
            sheet.append_row(row)
            return True
        else:
            logger.error(f"Invalid data format for sheet {sheet_name}")
            return False
            
    except Exception as e:
        logger.error(f"Error saving to sheet {sheet_name}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def save_field_config(section_name, fields):
    """Save field configuration to CSV file"""
    try:
        logger.info(f"Attempting to save configuration for {section_name}")
        logger.info(f"Received fields: {fields}")

        # Validazione input
        if not isinstance(fields, list):
            logger.error(f"Fields must be a list, got {type(fields)}")
            return False
            
        if not fields:
            logger.error(f"Empty fields list for {section_name}")
            return False

        # Crea la cartella field_configs se non esiste
        config_dir = "field_configs"
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            logger.info(f"Created directory: {config_dir}")

        # Mantieni tutti i campi, anche quelli non visibili
        if isinstance(fields[0], dict):
            # Assicurati che tutti i campi abbiano la proprietà visible
            for field in fields:
                if "visible" not in field:
                    field["visible"] = True
                if "label" not in field:
                    field["label"] = field["name"]
                if field.get("type", "testo") == "testo" and "dropdown" not in field:
                    field["dropdown"] = False
        else:
            logger.error(f"Fields must be a list of dictionaries")
            return False

        # Prepara il percorso del file
        config_file = f"field_configs/{section_name}.csv"
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        logger.info(f"Will save to: {config_file}")

        # Crea DataFrame e valida
        df = pd.DataFrame(fields)  # Usa tutti i campi, non solo quelli visibili
        logger.info(f"Created DataFrame with columns: {df.columns.tolist()}")
        
        if df.empty:
            logger.error(f"Empty DataFrame for {section_name}")
            return False
            
        if len(df.columns) == 0:
            logger.error(f"No columns in DataFrame for {section_name}")
            return False

        # Assicurati che tutti i campi necessari siano presenti
        required_columns = ['name', 'label', 'type', 'visible', 'dropdown']
        for col in required_columns:
            if col not in df.columns:
                logger.warning(f"Adding missing required column: {col}")
                if col == 'visible':
                    df[col] = True
                elif col == 'dropdown':
                    df[col] = False
                else:
                    df[col] = ''

        # Salva il file
        df.to_csv(config_file, index=False)
        logger.info(f"Successfully saved configuration to {config_file}")
        return True

    except Exception as e:
        logger.error(f"Error saving field config: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def load_field_config(section_name):
    """Load field configuration from CSV file"""
    try:
        config_file = f"field_configs/{section_name}.csv"
        
        # Check if file exists
        if not os.path.exists(config_file):
            # Return default configuration
            return {
                "fields": [
                    {"name": "nome", "label": "Nome", "type": "testo", "visible": True},
                    {"name": "descrizione", "label": "Descrizione", "type": "testo", "visible": True}
                ]
            }
            
        # Read configuration
        df = pd.read_csv(config_file)
        if df.empty:
            return None
            
        # Convert to dictionary
        fields = df.to_dict('records')
        return {"fields": fields}
        
    except Exception as e:
        logger.error(f"Error loading field config: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def get_form_config(section_name):
    """Generate form configuration by comparing Google Sheet columns with local CSV."""
    try:
        logger.info(f"Generating form config for {section_name}")
        
        # 1. Leggi le colonne dal Google Sheet
        sheet_data = get_data(section_name)
        if sheet_data is None or sheet_data.empty:
            logger.error(f"No data found in sheet {section_name}")
            return None
            
        sheet_columns = list(sheet_data.columns)
        logger.info(f"Sheet columns for {section_name}: {sheet_columns}")
        
        # 2. Leggi configurazione esistente dal CSV locale (se esiste)
        config_file = f"field_configs/{section_name}.csv"
        existing_config = {}
        
        if os.path.exists(config_file):
            try:
                df = pd.read_csv(config_file)
                if not df.empty:
                    for _, row in df.iterrows():
                        field_name = row.get("name", "")
                        existing_config[field_name] = {
                            "name": field_name,
                            "label": row.get("label", field_name),
                            "type": row.get("type", "testo"),
                            "required": row.get("required", True),
                            "visible": row.get("visible", True),
                            "dropdown": row.get("dropdown", False)
                        }
                        # Aggiungi configurazioni speciali se presenti
                        if "special_config" in row:
                            existing_config[field_name]["special_config"] = row["special_config"]
                    logger.info(f"Loaded existing config for {section_name}: {list(existing_config.keys())}")
            except Exception as e:
                logger.error(f"Error reading existing config: {str(e)}")
        else:
            logger.info(f"No existing config file found for {section_name}, will create new one")
        
        # 3. Crea la nuova configurazione
        config = {"fields": []}
        
        for column in sheet_columns:
            if column in existing_config:
                # Campo esistente: mantieni configurazione
                config["fields"].append(existing_config[column])
                logger.info(f"Keeping existing config for field: {column}")
            else:
                # Nuovo campo: crea configurazione di default
                new_field = {
                    "name": column,
                    "label": column,
                    "type": "testo",  # Default type
                    "required": True,
                    "visible": True,
                    "dropdown": False
                }
                config["fields"].append(new_field)
                logger.info(f"Added new field with default config: {column}")
        
        # 4. Salva automaticamente la nuova configurazione
        if config["fields"]:
            save_field_config(section_name, config["fields"])
            logger.info(f"Saved updated config for {section_name}")
        
        return config
        
    except Exception as e:
        logger.error(f"Error generating form config: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def initialize_session_state():
    """Initialize session state variables with logging."""
    try:
        logger.info("Initializing session state")
        
        if 'contract_data' not in st.session_state:
            st.session_state.contract_data = {}
            logger.debug("Initialized contract_data")
            
        if 'contact_data' not in st.session_state:
            st.session_state.contact_data = {}
            logger.debug("Initialized contact_data")
            
        if 'owner_data' not in st.session_state:
            st.session_state.owner_data = {}
            logger.debug("Initialized owner_data")
            
        if 'saved_rows' not in st.session_state:
            st.session_state.saved_rows = {
                'Contract': None,
                'Contacts': None,
                'Owners': None
            }
            logger.debug("Initialized saved_rows")
            
        logger.info("Session state initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing session state: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise 

def upload_file_to_drive(uploaded_file, apartment_name, file_type_label):
    """
    Carica un file su Google Drive nella cartella 'Tutorial e Materiali' dell'appartamento.
    Ritorna il link pubblico.
    """
    # ID della root Drive fornita
    ROOT_FOLDER_ID = '1sZUHgHo1pv_0II8b7uRyzxfn87512q2V'
    SCOPES = ['https://www.googleapis.com/auth/drive']
    SERVICE_ACCOUNT_FILE = 'service_account_key.json'

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)

    def find_or_create_folder(name, parent_id):
        # Cerca la cartella
        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        # Se non esiste, crea la cartella
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

    # 1. Trova/crea cartella appartamento
    apt_folder_id = find_or_create_folder(apartment_name, ROOT_FOLDER_ID)
    # 2. Trova/crea sottocartella "Tutorial e Materiali"
    materiali_folder_id = find_or_create_folder("Tutorial e Materiali", apt_folder_id)

    # 3. Carica il file
    file_ext = os.path.splitext(uploaded_file.name)[1]
    filename = f"{file_type_label} {apartment_name}{file_ext}"
    file_metadata = {
        'name': filename,
        'parents': [materiali_folder_id]
    }
    media = MediaIoBaseUpload(io.BytesIO(uploaded_file.getvalue()), mimetype=uploaded_file.type)
    uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = uploaded.get('id')

    # 4. Rendi il file pubblico
    drive_service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'},
    ).execute()
    file_url = f'https://drive.google.com/file/d/{file_id}/view?usp=sharing'
    return file_url 

def get_apartment_data(sheet_name, apartment):
    """
    Get data for a specific apartment from a sheet.
    
    Args:
        sheet_name (str): Name of the sheet to get data from
        apartment (str): Name of the apartment to filter for
        
    Returns:
        dict: Dictionary containing the apartment data, or empty dict if not found
    """
    try:
        # Get the sheet
        sheet = get_sheet(sheet_name)
        if not sheet:
            logger.error(f"Sheet {sheet_name} not found")
            return {}
            
        # Get all values from the sheet
        data = sheet.get_all_values()
        if not data:
            logger.warning(f"No data found in sheet {sheet_name}")
            return {}
            
        # Convert to DataFrame
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # Filter for the specific apartment
        apartment_data = df[df["appartamento"] == apartment]
        
        if apartment_data.empty:
            logger.info(f"No data found for apartment {apartment} in sheet {sheet_name}")
            return {}
            
        # Convert to dictionary
        return apartment_data.iloc[0].to_dict()
        
    except Exception as e:
        logger.error(f"Error getting apartment data from sheet {sheet_name}: {str(e)}")
        return {} 

def get_apartment_rows(sheet_name, apartment_value):
    df = get_data(sheet_name)
    if df is None or df.empty:
        return pd.DataFrame()
    first_col = df.columns[0]
    return df[df[first_col] == apartment_value] 

def save_apartment_data(apartment, sheet_name, data):
    """
    Salva i dati per un appartamento specifico in un foglio.
    Se esiste già una riga per quell'appartamento, la aggiorna.
    Altrimenti ne crea una nuova.
    """
    try:
        sheet = get_sheet(sheet_name)
        if sheet is None:
            logger.error(f"Impossibile ottenere il foglio {sheet_name}")
            return False
            
        # Ottieni tutti i dati
        all_data = sheet.get_all_records()
        
        # Cerca se esiste già una riga per questo appartamento e tipo (per elettrodomestici)
        existing_row = None
        if sheet_name == "elettrodomestici" and "tipo" in data:
            # Per elettrodomestici, cerca per appartamento + tipo
            for i, row in enumerate(all_data):
                if (row.get("appartamento") == apartment and 
                    row.get("tipo") == data.get("tipo")):
                    existing_row = i + 2  # +2 perché get_all_records() non include header e l'indice parte da 0
                    break
        else:
            # Per altri fogli, cerca solo per appartamento
            for i, row in enumerate(all_data):
                if row.get("appartamento") == apartment:
                    existing_row = i + 2
                    break
        
        if existing_row:
            # Aggiorna la riga esistente
            logger.info(f"Aggiornando riga esistente per {apartment} in {sheet_name}")
            
            # Ottieni gli header per mappare i campi
            headers = sheet.row_values(1)
            
            # Prepara i valori da aggiornare
            values = []
            for header in headers:
                if header in data:
                    values.append(data[header])
                else:
                    # Mantieni il valore esistente
                    values.append("")
            
            # Aggiorna la riga
            sheet.update(f"A{existing_row}:{chr(ord('A') + len(headers) - 1)}{existing_row}", [values])
            
        else:
            # Crea una nuova riga
            logger.info(f"Creando nuova riga per {apartment} in {sheet_name}")
            
            # Ottieni gli header
            headers = sheet.row_values(1)
            
            # Prepara i valori per la nuova riga
            values = []
            for header in headers:
                if header in data:
                    values.append(data[header])
                else:
                    values.append("")
            
            # Aggiungi la nuova riga
            sheet.append_row(values)
            
        return True
        
    except Exception as e:
        logger.error(f"Errore nel salvare dati per {apartment} in {sheet_name}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False 