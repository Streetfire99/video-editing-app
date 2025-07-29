import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os

# Configurazione Google Sheets
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_google_sheets_client():
    """Inizializza il client Google Sheets"""
    try:
        # Prova prima dalle variabili d'ambiente (per Streamlit Cloud)
        google_credentials = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        
        st.write(f"🔍 Debug - GOOGLE_SHEETS_CREDENTIALS presente: {google_credentials is not None}")
        if google_credentials:
            st.write(f"🔍 Debug - Lunghezza credenziali: {len(google_credentials)} caratteri")
            st.write(f"🔍 Debug - Primi 50 caratteri: {google_credentials[:50]}...")
        
        if google_credentials:
            st.write("🔍 Debug - Usando credenziali da variabile d'ambiente")
            # Usa le credenziali dalle variabili d'ambiente
            import json
            try:
                credentials_dict = json.loads(google_credentials)
                st.write(f"🔍 Debug - JSON parsato correttamente, chiavi: {list(credentials_dict.keys())}")
                credentials = Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=SCOPES
                )
                st.write("🔍 Debug - Credenziali create con successo")
            except json.JSONDecodeError as e:
                st.error(f"❌ Errore nel parsing JSON delle credenziali: {e}")
                st.write(f"🔍 Debug - JSON problematico: {google_credentials[:200]}...")
                return None
        else:
            st.write("🔍 Debug - Usando credenziali da file locale")
            # Fallback al file locale (per sviluppo)
            if os.path.exists('service_account_key.json'):
                st.write("🔍 Debug - File service_account_key.json trovato")
                credentials = Credentials.from_service_account_file(
                    'service_account_key.json',
                    scopes=SCOPES
                )
            else:
                st.write("🔍 Debug - File service_account_key.json NON trovato")
                st.error("Nessuna credenziale Google trovata. Configura GOOGLE_SHEETS_CREDENTIALS nei secrets di Streamlit Cloud.")
                return None
        
        client = gspread.authorize(credentials)
        st.write("🔍 Debug - Client Google Sheets autorizzato con successo")
        return client
    except Exception as e:
        st.error(f"Errore nel caricamento delle credenziali Google: {e}")
        st.write(f"🔍 Debug - Errore completo: {str(e)}")
        st.write(f"🔍 Debug - Tipo di errore: {type(e).__name__}")
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