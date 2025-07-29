import gspread
import json
import os
from datetime import datetime

# File per la persistenza dei dati
PROGRESS_FILE = 'user_progress.json'
CUSTOM_APARTMENTS_FILE = 'custom_apartments.json'
CUSTOM_VIDEO_TYPES_FILE = 'custom_video_types.json'

def load_apartments():
    """Carica gli appartamenti da Google Sheets e combina con dati personalizzati"""
    try:
        # Carica dati da Google Sheets
        gc = gspread.service_account_from_dict(json.loads(os.environ.get('GOOGLE_SHEETS_CREDENTIALS', '{}')))
        sheet = gc.open('Appartamenti').sheet1
        data = sheet.get_all_records()
        
        # Converti in formato standard
        apartments = []
        for row in data:
            apartment = {
                'name': row.get('Nome', ''),
                'address': row.get('Indirizzo', ''),
                'price': int(row.get('Prezzo', 0)),
                'rooms': int(row.get('Stanze', 1)),
                'bathrooms': int(row.get('Bagni', 1)),
                'sqm': int(row.get('Metri Quadrati', 50))
            }
            apartments.append(apartment)
        
        # Carica dati personalizzati
        custom_apartments = load_custom_apartments()
        
        # Combina i dati
        all_apartments = apartments + custom_apartments
        
        return all_apartments
        
    except Exception as e:
        print(f"Errore nel caricamento appartamenti: {e}")
        # Fallback ai dati personalizzati
        return load_custom_apartments()

def get_video_types():
    """Carica le tipologie video da Google Sheets e combina con dati personalizzati"""
    try:
        # Carica dati da Google Sheets
        gc = gspread.service_account_from_dict(json.loads(os.environ.get('GOOGLE_SHEETS_CREDENTIALS', '{}')))
        sheet = gc.open('Tipologie Video').sheet1
        data = sheet.get_all_records()
        
        # Converti in formato standard
        video_types = []
        for row in data:
            video_type = {
                'name': row.get('Nome', ''),
                'description': row.get('Descrizione', '')
            }
            video_types.append(video_type)
        
        # Carica dati personalizzati
        custom_video_types = load_custom_video_types()
        
        # Combina i dati
        all_video_types = video_types + custom_video_types
        
        return all_video_types
        
    except Exception as e:
        print(f"Errore nel caricamento tipologie video: {e}")
        # Fallback ai dati personalizzati
        return load_custom_video_types()

def save_progress(progress_data):
    """Salva il progresso di un video elaborato"""
    try:
        # Carica progressi esistenti
        all_progress = load_all_progress()
        
        # Assicurati che tutti i campi necessari siano presenti
        required_fields = ['timestamp', 'apartment', 'video_type', 'file_name']
        optional_fields = ['youtube_url', 'drive_url', 'manual_it', 'manual_en']
        
        # Verifica che tutti i campi richiesti siano presenti
        for field in required_fields:
            if field not in progress_data:
                progress_data[field] = ''
        
        # Aggiungi campi opzionali se non presenti
        for field in optional_fields:
            if field not in progress_data:
                progress_data[field] = None
        
        # Aggiungi nuovo progresso
        all_progress.append(progress_data)
        
        # Salva nel file
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_progress, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Errore nel salvataggio progresso: {e}")

def update_progress_with_links(apartment_name, video_type, youtube_url=None, drive_url=None, manual_it=None, manual_en=None):
    """Aggiorna un progresso esistente con i link"""
    try:
        all_progress = load_all_progress()
        
        # Trova il progresso da aggiornare
        for progress in all_progress:
            if progress['apartment'] == apartment_name and progress['video_type'] == video_type:
                if youtube_url:
                    progress['youtube_url'] = youtube_url
                if drive_url:
                    progress['drive_url'] = drive_url
                if manual_it:
                    progress['manual_it'] = manual_it
                if manual_en:
                    progress['manual_en'] = manual_en
                break
        
        # Salva le modifiche
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_progress, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Errore nell'aggiornamento progresso: {e}")

def get_apartment_progress(apartment_name):
    """Ottiene tutti i progressi per un appartamento specifico"""
    try:
        all_progress = load_all_progress()
        return [p for p in all_progress if p['apartment'] == apartment_name]
    except Exception as e:
        print(f"Errore nel caricamento progressi appartamento: {e}")
        return []

def get_video_type_progress(apartment_name, video_type):
    """Ottiene il progresso per una specifica combinazione appartamento-tipologia"""
    try:
        all_progress = load_all_progress()
        for progress in all_progress:
            if progress['apartment'] == apartment_name and progress['video_type'] == video_type:
                return progress
        return None
    except Exception as e:
        print(f"Errore nel caricamento progresso specifico: {e}")
        return None

def load_all_progress():
    """Carica tutti i progressi salvati"""
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Errore nel caricamento progressi: {e}")
        return []

def get_user_progress(user_id=None):
    """Carica i progressi per un utente specifico (per ora tutti)"""
    return load_all_progress()

def save_custom_apartment(apartment_data):
    """Salva un appartamento personalizzato"""
    try:
        # Carica appartamenti personalizzati esistenti
        custom_apartments = load_custom_apartments()
        
        # Rimuovi se esiste già con lo stesso nome
        custom_apartments = [apt for apt in custom_apartments if apt['name'] != apartment_data['name']]
        
        # Aggiungi il nuovo
        custom_apartments.append(apartment_data)
        
        # Salva nel file
        with open(CUSTOM_APARTMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(custom_apartments, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Errore nel salvataggio appartamento personalizzato: {e}")

def load_custom_apartments():
    """Carica gli appartamenti personalizzati"""
    try:
        if os.path.exists(CUSTOM_APARTMENTS_FILE):
            with open(CUSTOM_APARTMENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Errore nel caricamento appartamenti personalizzati: {e}")
        return []

def save_custom_video_type(video_type_data):
    """Salva una tipologia video personalizzata"""
    try:
        # Carica tipologie personalizzate esistenti
        custom_video_types = load_custom_video_types()
        
        # Rimuovi se esiste già con lo stesso nome
        custom_video_types = [vt for vt in custom_video_types if vt['name'] != video_type_data['name']]
        
        # Aggiungi la nuova
        custom_video_types.append(video_type_data)
        
        # Salva nel file
        with open(CUSTOM_VIDEO_TYPES_FILE, 'w', encoding='utf-8') as f:
            json.dump(custom_video_types, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Errore nel salvataggio tipologia personalizzata: {e}")

def load_custom_video_types():
    """Carica le tipologie video personalizzate"""
    try:
        if os.path.exists(CUSTOM_VIDEO_TYPES_FILE):
            with open(CUSTOM_VIDEO_TYPES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Errore nel caricamento tipologie personalizzate: {e}")
        return []

def get_statistics():
    """Restituisce statistiche sui dati"""
    try:
        apartments = load_apartments()
        video_types = get_video_types()
        progress = load_all_progress()
        
        stats = {
            'total_apartments': len(apartments),
            'total_video_types': len(video_types),
            'total_videos_processed': len(progress),
            'youtube_uploads': len([p for p in progress if p.get('youtube_url')]),
            'custom_apartments': len(load_custom_apartments()),
            'custom_video_types': len(load_custom_video_types())
        }
        
        return stats
        
    except Exception as e:
        print(f"Errore nel calcolo statistiche: {e}")
        return {} 