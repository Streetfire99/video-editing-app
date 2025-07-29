import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

def get_drive_service():
    """Ottiene il servizio Google Drive usando Service Account"""
    try:
        # Usa il file JSON esistente
        credentials_file = "service_account_key.json"
        
        if not os.path.exists(credentials_file):
            print(f"❌ File {credentials_file} non trovato")
            return None
        
        # Crea le credenziali dal file JSON
        credentials = Credentials.from_service_account_file(
            credentials_file, 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        
        # Crea il servizio Drive
        service = build('drive', 'v3', credentials=credentials)
        
        return service
        
    except Exception as e:
        print(f"❌ Errore nel caricamento delle credenziali Google Drive: {e}")
        return None

def read_logs_from_drive():
    """Legge i log da Google Drive"""
    try:
        service = get_drive_service()
        if not service:
            return "❌ Servizio Drive non disponibile"
        
        # ID cartella Drive per i log
        LOGS_FOLDER_ID = "1w9P2oiRfFgsOOj82V7xOruhjnl-APCCi"
        
        # Cerca file log
        query = f"'{LOGS_FOLDER_ID}' in parents and name='app_debug.log' and trashed=false"
        results = service.files().list(q=query).execute()
        files = results.get('files', [])
        
        if not files:
            return "📝 Nessun file log trovato su Drive"
        
        # Leggi il primo file log
        file_id = files[0]['id']
        request = service.files().get_media(fileId=file_id)
        log_content = request.execute().decode('utf-8')
        
        return log_content
        
    except Exception as e:
        return f"❌ Errore nella lettura log: {e}"

if __name__ == "__main__":
    logs = read_logs_from_drive()
    print("=== LOGS DA GOOGLE DRIVE ===")
    print(logs) 