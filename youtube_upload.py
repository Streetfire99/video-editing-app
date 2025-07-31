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
    is_account_authenticated,
    get_next_account_to_authenticate,
    show_modern_authentication_banner,
    authenticate_with_code_modern
)

# Configurazione OAuth2 per YouTube
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.upload'
]

def check_youtube_setup():
    """Controlla se YouTube è configurato correttamente"""
    try:
        # Controlla se ci sono account autenticati
        authenticated_accounts = [acc for acc in ["xeniamilano.info@gmail.com", "videoxenia1@gmail.com", "videoxenia2@gmail.com", "videoxenia3@gmail.com", "videoxenia4@gmail.com"] if is_account_authenticated(acc)]
        
        if authenticated_accounts:
            return True, f"✅ YouTube configurato con {len(authenticated_accounts)} account autenticati"
        else:
            return False, "❌ Nessun account YouTube autenticato"
    except Exception as e:
        return False, f"❌ Errore nella configurazione YouTube: {e}"

def upload_to_youtube(video_path, title, privacy_status="unlisted", description="", tags=""):
    """Carica il video su YouTube usando la rotazione automatica degli account"""
    print("🔧 DEBUG: Starting upload_to_youtube")
    print(f"🔧 DEBUG: Video path: {video_path}")
    print(f"🔧 DEBUG: Title: {title}")
    print(f"🔧 DEBUG: Privacy status: {privacy_status}")
    
    try:
        print("🔧 DEBUG: Checking if any accounts are authenticated")
        # Controlla se ci sono account autenticati
        if not any(is_account_authenticated(acc) for acc in ["xeniamilano.info@gmail.com", "videoxenia1@gmail.com", "videoxenia2@gmail.com", "videoxenia3@gmail.com", "videoxenia4@gmail.com"]):
            print("❌ DEBUG: No authenticated accounts found")
            # Nessun account autenticato, mostra banner per il primo
            next_account = get_next_account_to_authenticate()
            if next_account:
                print(f"🔧 DEBUG: Showing authentication banner for {next_account}")
                show_modern_authentication_banner(next_account)
                return None
            else:
                print("❌ DEBUG: No accounts available for authentication")
                st.error("❌ Nessun account YouTube disponibile")
                return None
        
        print("🔧 DEBUG: Found authenticated accounts, starting upload")
        # Prova l'upload
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
        from youtube_account_manager import test_account
        success, message = test_account(account)
        if success:
            st.success(message)
        else:
            st.error(message)
        return success
    except Exception as e:
        st.error(f"❌ Errore nel test dell'account: {e}")
        return False 