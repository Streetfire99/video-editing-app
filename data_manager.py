import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configurazione Google Sheets
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_google_sheets_client():
    """Ottiene il client per Google Sheets"""
    try:
        print("🔧 DEBUG: Starting get_google_sheets_client")
        
        # Prova prima da Streamlit secrets
        google_credentials = st.secrets.get('GOOGLE_SHEETS_CREDENTIALS')
        print(f"🔧 DEBUG: Got credentials from secrets: {type(google_credentials)}")
        
        if google_credentials:
            # Se è una stringa JSON, convertila in dizionario
            if isinstance(google_credentials, str):
                print("🔧 DEBUG: Converting string to dict")
                import json
                try:
                    google_credentials = json.loads(google_credentials)
                    print("🔧 DEBUG: JSON parsing successful")
                    print(f"🔧 DEBUG: Parsed credentials keys: {list(google_credentials.keys())}")
                except json.JSONDecodeError as e:
                    print(f"❌ DEBUG: JSON parsing failed: {e}")
                    st.error(f"❌ Errore nel parsing JSON delle credenziali: {e}")
                    return None
            
            print("🔧 DEBUG: Creating credentials from service account info")
            # Crea le credenziali dal dizionario
            from google.oauth2.service_account import Credentials
            try:
                print(f"🔧 DEBUG: Credentials dict keys: {list(google_credentials.keys())}")
                print(f"🔧 DEBUG: private_key present: {'private_key' in google_credentials}")
                if 'private_key' in google_credentials:
                    print(f"🔧 DEBUG: private_key length: {len(google_credentials['private_key'])}")
                    print(f"🔧 DEBUG: private_key starts with: {google_credentials['private_key'][:50]}...")
                    # Sostituisci \\n con \n se necessario
                    if '\\\\n' in google_credentials['private_key']:
                        print("🔧 DEBUG: Replacing \\\\n with \\n")
                        google_credentials['private_key'] = google_credentials['private_key'].replace('\\\\n', '\\n')
                    elif '\\n' not in google_credentials['private_key']:
                        print("🔧 DEBUG: No \\n found in private_key, this might be the issue")
                
                credentials = Credentials.from_service_account_info(google_credentials)
                print("🔧 DEBUG: Credentials created successfully")
            except Exception as e:
                print(f"❌ DEBUG: Error creating credentials: {e}")
                print(f"❌ DEBUG: Error type: {type(e)}")
                st.error(f"❌ Errore nella creazione delle credenziali: {e}")
                return None
            
            # Crea il client
            print("🔧 DEBUG: Building service")
            service = build('sheets', 'v4', credentials=credentials)
            print("🔧 DEBUG: Service built successfully")
            return service
        else:
            print("🔧 DEBUG: No credentials in secrets, trying environment")
            # Fallback alle variabili d'ambiente
            google_credentials = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
            if google_credentials:
                # Se è una stringa JSON, convertila in dizionario
                if isinstance(google_credentials, str):
                    import json
                    google_credentials = json.loads(google_credentials)
                
                # Crea le credenziali dal dizionario
                from google.oauth2.service_account import Credentials
                credentials = Credentials.from_service_account_info(google_credentials)
                
                # Crea il client
                service = build('sheets', 'v4', credentials=credentials)
                return service
            else:
                st.error("❌ Credenziali Google Sheets non configurate")
                return None
    except Exception as e:
        st.error(f"❌ Errore nel caricamento delle credenziali Google: {e}")
        st.error(f"❌ Tipo di errore: {type(e)}")
        st.error(f"❌ Dettagli: {str(e)}")
        return None

def load_apartments():
    """Carica gli appartamenti dal Google Sheets"""
    try:
        client = get_google_sheets_client()
        if not client:
            return []
        
        # Apri il foglio "contratti"
        sheet = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1XlbRK6suO1x3CV8sgQMzcKtiIcSoUdO6OJh_mykjS9M/edit?gid=217032800#gid=217032800"
        ).worksheet("contratti")
        
        # Leggi la colonna A a partire da A2
        apartments = sheet.col_values(1)[1:]  # Salta l'intestazione
        
        # Filtra valori vuoti
        apartments = [apt for apt in apartments if apt.strip()]
        
        return sorted(apartments)
        
    except Exception as e:
        st.error(f"Errore nel caricamento degli appartamenti: {e}")
        return []

# Tipologie di video predefinite
DEFAULT_VIDEO_TYPES = [
    "asciugatrice",
    "caldaia", 
    "check-in",
    "condizionamento",
    "forno",
    "frigorifero",
    "lavastoviglie",
    "lavatrice",
    "microonde",
    "piano_cottura",
    "riscaldamento",
    "scaldabagno",
    "spazzatura"
]

def get_video_types():
    """Restituisce le tipologie di video ordinate alfabeticamente"""
    return sorted(DEFAULT_VIDEO_TYPES)

def get_prompt_for_video_type(video_type):
    """Restituisce il prompt personalizzato per la tipologia di video"""
    prompts = {
        "spazzatura": "You are a video subtitle editor specializing in waste management and recycling instructions. Your task is to optimize the following raw transcription of an instructional video about waste disposal and recycling procedures.",
        "caldaia": "You are a video subtitle editor specializing in heating system instructions. Your task is to optimize the following raw transcription of an instructional video about boiler operation and maintenance.",
        "forno": "You are a video subtitle editor specializing in kitchen appliance instructions. Your task is to optimize the following raw transcription of an instructional video about oven operation and safety.",
        "frigorifero": "You are a video subtitle editor specializing in kitchen appliance instructions. Your task is to optimize the following raw transcription of an instructional video about refrigerator operation and maintenance.",
        "lavatrice": "You are a video subtitle editor specializing in household appliance instructions. Your task is to optimize the following raw transcription of an instructional video about washing machine operation and maintenance.",
        "piano_cottura": "You are a video subtitle editor specializing in kitchen appliance instructions. Your task is to optimize the following raw transcription of an instructional video about stovetop operation and safety.",
        "scaldabagno": "You are a video subtitle editor specializing in water heating system instructions. Your task is to optimize the following raw transcription of an instructional video about water heater operation and maintenance.",
        "lavastoviglie": "You are a video subtitle editor specializing in kitchen appliance instructions. Your task is to optimize the following raw transcription of an instructional video about dishwasher operation and maintenance.",
        "microonde": "You are a video subtitle editor specializing in kitchen appliance instructions. Your task is to optimize the following raw transcription of an instructional video about microwave operation and safety.",
        "asciugatrice": "You are a video subtitle editor specializing in household appliance instructions. Your task is to optimize the following raw transcription of an instructional video about dryer operation and maintenance.",
        "riscaldamento": "You are a video subtitle editor specializing in heating system instructions. Your task is to optimize the following raw transcription of an instructional video about heating system operation and maintenance.",
        "condizionamento": "You are a video subtitle editor specializing in climate control system instructions. Your task is to optimize the following raw transcription of an instructional video about air conditioning operation and maintenance.",
        "check-in": "You are a video subtitle editor specializing in apartment check-in procedures. Your task is to optimize the following raw transcription of an instructional video about apartment check-in process and procedures."
    }
    
    return prompts.get(video_type, "You are a video subtitle editor specializing in instructional videos. Your task is to optimize the following raw transcription of an instructional video.")

def get_translation_prompt_for_video_type(video_type):
    """Restituisce il prompt di traduzione personalizzato per la tipologia di video"""
    prompts = {
        "spazzatura": "You are a translator specializing in waste management and recycling instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "caldaia": "You are a translator specializing in heating system instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "forno": "You are a translator specializing in kitchen appliance instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "frigorifero": "You are a translator specializing in kitchen appliance instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "lavatrice": "You are a translator specializing in household appliance instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "piano_cottura": "You are a translator specializing in kitchen appliance instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "scaldabagno": "You are a translator specializing in water heating system instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "lavastoviglie": "You are a translator specializing in kitchen appliance instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "microonde": "You are a translator specializing in kitchen appliance instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "asciugatrice": "You are a translator specializing in household appliance instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "riscaldamento": "You are a translator specializing in heating system instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "condizionamento": "You are a translator specializing in climate control system instructions. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.",
        "check-in": "You are a translator specializing in apartment check-in procedures. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles."
    }
    
    return prompts.get(video_type, "You are a translator specializing in instructional videos. Translate the following Italian text to English, ensuring the translation is clear, concise, and suitable for subtitles.") 