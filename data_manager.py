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
        credentials_str = st.secrets.get('GOOGLE_SHEETS_CREDENTIALS')
        if credentials_str:
            print("🔧 DEBUG: Got credentials from secrets:", type(credentials_str))
            
            # Se è una stringa JSON, convertila in dizionario
            if isinstance(credentials_str, str):
                print("🔧 DEBUG: Converting string to dict")
                import json
                credentials_dict = json.loads(credentials_str)
                print("🔧 DEBUG: JSON parsing successful")
            else:
                credentials_dict = credentials_str
                print("🔧 DEBUG: Using secrets directly")
        else:
            # Fallback alle variabili d'ambiente
            credentials_str = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
            if not credentials_str:
                st.error("❌ GOOGLE_SHEETS_CREDENTIALS non trovata nei secrets o nelle variabili d'ambiente")
                return None
            
            import json
            credentials_dict = json.loads(credentials_str)
        
        print("🔧 DEBUG: Parsed credentials keys:", list(credentials_dict.keys()))
        
        print("🔧 DEBUG: Creating credentials from service account info")
        print("🔧 DEBUG: Credentials dict keys:", list(credentials_dict.keys()))
        
        # Crea le credenziali
        from google.oauth2.service_account import Credentials
        credentials = Credentials.from_service_account_info(credentials_dict)
        
        print("🔧 DEBUG: Credentials created successfully")
        
        # Crea il client
        import gspread
        client = gspread.authorize(credentials)
        
        print("🔧 DEBUG: Service built successfully")
        return client
        
    except Exception as e:
        print("❌ DEBUG: Error creating credentials:", str(e))
        print("❌ DEBUG: Error type:", type(e))
        st.error(f"❌ Errore nel caricamento delle credenziali Google: {e}")
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