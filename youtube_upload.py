import os
import pickle
import streamlit as st
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Importa il nuovo sistema di gestione account
from youtube_account_manager import (
    upload_video_with_rotation,
    get_accounts_summary,
    get_available_account,
    get_account_status,
    test_account
)

# Configurazione OAuth2 per YouTube
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.upload'
]

def check_youtube_setup():
    """Controlla se YouTube è configurato correttamente"""
    print("🔧 DEBUG: Starting check_youtube_setup")
    try:
        # Controlla se ci sono account disponibili
        available_account = get_available_account()
        print(f"🔧 DEBUG: Available account: {available_account}")
        
        if available_account:
            print("✅ DEBUG: YouTube setup OK")
            return True, f"✅ YouTube configurato con account: {available_account}"
        else:
            print("❌ DEBUG: No available accounts")
            return False, "❌ Nessun account YouTube disponibile"
    except Exception as e:
        print(f"❌ DEBUG: Error in check_youtube_setup: {e}")
        return False, f"❌ Errore nella configurazione YouTube: {e}"

def upload_to_youtube(video_path, title, privacy_status="unlisted", description="", tags=""):
    """Carica il video su YouTube usando la rotazione automatica degli account"""
    print("🔧 DEBUG: Starting upload_to_youtube")
    print(f"🔧 DEBUG: Video path: {video_path}")
    print(f"🔧 DEBUG: Title: {title}")
    
    try:
        result = upload_video_with_rotation(
            video_path=video_path,
            title=title,
            privacy_status=privacy_status,
            description=description,
            tags=tags
        )
        
        print(f"🔧 DEBUG: Upload result: {result}")
        
        if result["success"]:
            print("✅ DEBUG: Upload successful")
            st.success(f"✅ Video caricato con successo su YouTube!")
            st.info(f"📺 Account utilizzato: {result['account_used']}")
            st.info(f"🔗 Link: {result['video_url']}")
            return result['video_url']
        else:
            print("❌ DEBUG: Upload failed")
            st.error("❌ Errore nel caricamento su YouTube")
            return None
            
    except Exception as e:
        print(f"❌ DEBUG: Exception in upload_to_youtube: {e}")
        st.error(f"❌ Errore nell'upload YouTube: {e}")
        return None

def get_youtube_status():
    """Ottiene lo stato di tutti gli account YouTube"""
    try:
        summary = get_accounts_summary()
        return summary
    except Exception as e:
        st.error(f"❌ Errore nel recupero dello stato YouTube: {e}")
        return None

def test_youtube_account(account):
    """Testa un account YouTube specifico"""
    try:
        success, message = test_account(account)
        if success:
            st.success(message)
        else:
            st.error(message)
        return success
    except Exception as e:
        st.error(f"❌ Errore nel test dell'account: {e}")
        return False 