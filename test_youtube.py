#!/usr/bin/env python3
"""
Test YouTube Upload - Versione Standalone con Log Dettagliati
"""

import os
import sys
import pickle
import logging
from datetime import datetime

# Configura logging dettagliato
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('youtube_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_youtube_setup():
    """Test della configurazione YouTube"""
    logger.info("🔧 Iniziando test configurazione YouTube...")
    
    # Controlla file client_secrets.json
    if os.path.exists('client_secrets.json'):
        logger.info("✅ File client_secrets.json trovato")
        with open('client_secrets.json', 'r') as f:
            content = f.read()
            logger.info(f"📄 Contenuto file: {len(content)} caratteri")
    else:
        logger.error("❌ File client_secrets.json NON TROVATO")
        return False
    
    # Controlla file token.pickle
    if os.path.exists('token.pickle'):
        logger.info("✅ File token.pickle trovato (autenticazione salvata)")
    else:
        logger.info("⚠️ File token.pickle non trovato (prima autenticazione necessaria)")
    
    return True

def test_credentials():
    """Test delle credenziali OAuth2"""
    logger.info("🔐 Testando credenziali OAuth2...")
    
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        logger.info("✅ Moduli Google importati con successo")
        
        # Configurazione OAuth2
        SCOPES = [
            'https://www.googleapis.com/auth/youtube',
            'https://www.googleapis.com/auth/youtube.upload'
        ]
        
        logger.info(f"📋 Scopes configurati: {SCOPES}")
        
        creds = None
        
        # Carica token salvato
        if os.path.exists('token.pickle'):
            logger.info("🔄 Caricando token salvato...")
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
            logger.info("✅ Token caricato")
        
        # Verifica validità credenziali
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("🔄 Token scaduto, aggiornando...")
                creds.refresh(Request())
                logger.info("✅ Token aggiornato")
            else:
                logger.info("🔐 Autenticazione necessaria...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    'client_secrets.json', SCOPES)
                logger.info("🌐 Aprendo browser per autenticazione...")
                creds = flow.run_local_server(port=0)
                logger.info("✅ Autenticazione completata")
            
            # Salva credenziali
            logger.info("💾 Salvando credenziali...")
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
            logger.info("✅ Credenziali salvate")
        
        # Test connessione YouTube API
        logger.info("📺 Testando connessione YouTube API...")
        youtube = build('youtube', 'v3', credentials=creds)
        
        # Test chiamata API semplice
        logger.info("🔍 Testando chiamata API...")
        request = youtube.channels().list(
            part="snippet",
            mine=True
        )
        response = request.execute()
        
        logger.info(f"✅ Connessione YouTube OK - Canali trovati: {len(response.get('items', []))}")
        
        for channel in response.get('items', []):
            logger.info(f"📺 Canale: {channel['snippet']['title']} (ID: {channel['id']})")
        
        return True, youtube
        
    except Exception as e:
        logger.error(f"❌ Errore durante test credenziali: {str(e)}")
        return False, None

def test_upload_small_video(youtube):
    """Test upload video piccolo"""
    logger.info("🎬 Testando upload video...")
    
    # Crea un video di test piccolo
    test_video_path = "test_video.mp4"
    
    if not os.path.exists(test_video_path):
        logger.info("📹 Creando video di test...")
        try:
            # Usa ffmpeg per creare un video di test
            import subprocess
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", "testsrc=duration=5:size=320x240:rate=1",
                "-f", "lavfi", 
                "-i", "sine=frequency=1000:duration=5",
                "-c:v", "libx264",
                "-c:a", "aac",
                test_video_path
            ]
            logger.info(f"🔧 Comando ffmpeg: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ Video di test creato")
            else:
                logger.error(f"❌ Errore creazione video: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Errore creazione video: {str(e)}")
            return False
    
    # Test upload
    try:
        from googleapiclient.http import MediaFileUpload
        
        logger.info("📤 Iniziando upload test...")
        
        # Metadati video
        body = {
            'snippet': {
                'title': f'Test Upload {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                'description': 'Video di test per verifica upload YouTube API',
                'tags': ['test', 'api', 'upload'],
                'categoryId': '27'  # Education
            },
            'status': {
                'privacyStatus': 'unlisted'  # Non in elenco - visibile solo con link
            }
        }
        
        logger.info(f"📝 Metadati video: {body}")
        
        # Carica video
        media = MediaFileUpload(test_video_path, chunksize=-1, resumable=True)
        logger.info(f"📁 File caricato: {test_video_path} ({os.path.getsize(test_video_path)} bytes)")
        
        # Esegui upload
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        logger.info("🚀 Upload in corso...")
        
        response = None
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"📊 Progresso: {progress}%")
            except HttpError as e:
                logger.error(f"❌ Errore HTTP durante upload: {e}")
                if e.resp.status == 401:
                    logger.error("🔐 Errore autenticazione - token scaduto")
                    os.remove('token.pickle')
                return False
        
        logger.info("✅ Upload completato!")
        
        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        logger.info(f"🎬 Video ID: {video_id}")
        logger.info(f"🔗 URL: {video_url}")
        
        return True, video_url
        
    except Exception as e:
        logger.error(f"❌ Errore durante upload: {str(e)}")
        return False, None

def main():
    """Funzione principale"""
    logger.info("🚀 Iniziando test YouTube Upload...")
    logger.info(f"📅 Data/Ora: {datetime.now()}")
    logger.info(f"📁 Directory: {os.getcwd()}")
    
    # Test configurazione
    if not test_youtube_setup():
        logger.error("❌ Configurazione YouTube fallita")
        return
    
    # Test credenziali
    success, youtube = test_credentials()
    if not success:
        logger.error("❌ Test credenziali fallito")
        return
    
    # Test upload
    success, video_url = test_upload_small_video(youtube)
    if success:
        logger.info("🎉 TUTTI I TEST SUPERATI!")
        logger.info(f"🎬 Video caricato: {video_url}")
    else:
        logger.error("❌ Test upload fallito")

if __name__ == "__main__":
    main() 