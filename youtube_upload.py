import os
import tempfile
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import streamlit as st
from youtube_account_manager import YouTubeAccountManager
from data_manager import update_progress_with_links

def get_youtube_credentials():
    """Ottiene le credenziali YouTube usando il sistema di gestione account"""
    try:
        account_manager = YouTubeAccountManager()
        
        # Trova un account disponibile
        available_account = account_manager.get_available_account()
        if not available_account:
            return None, None, "Nessun account YouTube disponibile. Tutti gli account hanno raggiunto il limite giornaliero."
        
        # Ottieni le credenziali per l'account
        credentials = account_manager.get_credentials_for_account(available_account)
        if not credentials:
            return None, None, f"Errore nell'autenticazione per l'account '{available_account['name']}'. Verifica le credenziali."
        
        return credentials, available_account, None
        
    except Exception as e:
        return None, None, f"Errore nel caricamento delle credenziali Google: {str(e)}"

def upload_to_youtube(video_path, apartment, video_type):
    """Carica un video su YouTube"""
    try:
        # Ottieni credenziali e account
        credentials, account, error = get_youtube_credentials()
        if error:
            st.error(error)
            return None
        
        if not credentials or not account:
            st.error("Impossibile ottenere credenziali YouTube valide")
            return None
        
        # Crea il client YouTube
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Prepara i metadati del video
        title = f"{apartment['name']} - {video_type['name']}"
        description = f"""
🏠 {apartment['name']}
📍 {apartment.get('address', 'Indirizzo non disponibile')}
💰 Prezzo: €{apartment.get('price', 0):,}
🏠 {apartment.get('rooms', 0)} stanze, {apartment.get('bathrooms', 0)} bagni
📏 {apartment.get('sqm', 0)} m²

📝 {video_type.get('description', 'Video promozionale')}

#immobili #affitti #case #appartamenti
        """.strip()
        
        # Tag per il video
        tags = [
            'immobili', 'affitti', 'case', 'appartamenti', 
            'real estate', 'property', 'rental', 'housing'
        ]
        
        # Carica il video
        with open(video_path, 'rb') as video_file:
            media = MediaFileUpload(video_path, resumable=True)
            
            request = youtube.videos().insert(
                part='snippet,status',
                body={
                    'snippet': {
                        'title': title,
                        'description': description,
                        'tags': tags,
                        'categoryId': '22'  # People & Blogs
                    },
                    'status': {
                        'privacyStatus': 'public',
                        'selfDeclaredMadeForKids': False
                    }
                },
                media_body=media
            )
            
            # Esegui l'upload
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    st.write(f"Upload progresso: {int(status.progress() * 100)}%")
            
            # Aggiorna l'uso dell'account
            account_manager = YouTubeAccountManager()
            account_manager.update_account_usage(account['name'])
            
            video_url = f"https://www.youtube.com/watch?v={response['id']}"
            st.success(f"✅ Video caricato con successo su YouTube!")
            st.info(f"Account utilizzato: {account['name']} ({account.get('daily_uploads', 0)}/{account.get('max_daily_uploads', 5)} upload oggi)")
            
            # Salva il link YouTube nel progresso
            update_progress_with_links(
                apartment_name=apartment['name'],
                video_type=video_type['name'],
                youtube_url=video_url
            )
            
            return video_url
            
    except HttpError as e:
        error_message = f"Errore YouTube API: {e.resp.status} {e.content.decode()}"
        st.error(error_message)
        return None
    except Exception as e:
        error_message = f"Errore durante l'upload: {str(e)}"
        st.error(error_message)
        return None

def check_youtube_setup():
    """Controlla se il setup YouTube è configurato correttamente"""
    try:
        account_manager = YouTubeAccountManager()
        accounts_status = account_manager.get_accounts_status()
        
        if not accounts_status:
            return {
                'status': 'no_accounts',
                'message': 'Nessun account YouTube configurato. Aggiungi account nella sezione "Gestione Account YouTube".'
            }
        
        # Controlla se ci sono account disponibili
        available_accounts = [acc for acc in accounts_status if acc['available']]
        if not available_accounts:
            return {
                'status': 'no_available',
                'message': 'Tutti gli account YouTube hanno raggiunto il limite giornaliero. Riprova domani o resetta i contatori.'
            }
        
        # Controlla se ci sono token validi
        token_info = account_manager.get_token_info()
        valid_tokens = [token for token in token_info if token['token_valid']]
        
        if not valid_tokens:
            return {
                'status': 'no_tokens',
                'message': 'Nessun token YouTube valido. Autentica gli account nella sezione "Gestione Token".'
            }
        
        return {
            'status': 'ready',
            'message': f'Setup YouTube pronto. {len(available_accounts)} account disponibili, {len(valid_tokens)} token validi.'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Errore nel controllo setup YouTube: {str(e)}'
        }

def get_streamlit():
    """Helper per ottenere streamlit in modo sicuro"""
    try:
        import streamlit as st
        return st
    except ImportError:
        return None 