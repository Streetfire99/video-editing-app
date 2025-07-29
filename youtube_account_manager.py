import json
import os
import pickle
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class YouTubeAccountManager:
    def __init__(self, accounts_file='youtube_accounts.json'):
        self.accounts_file = accounts_file
        self.accounts = []
        self.current_account_index = 0
        self.last_rotation = None
        self.load_accounts()
    
    def load_accounts(self):
        """Carica gli account dal file JSON"""
        try:
            if os.path.exists(self.accounts_file):
                with open(self.accounts_file, 'r') as f:
                    data = json.load(f)
                    self.accounts = data.get('accounts', [])
                    self.current_account_index = data.get('current_account_index', 0)
                    self.last_rotation = data.get('last_rotation')
            else:
                # Inizializza con un account vuoto che verrà configurato tramite l'interfaccia
                self.accounts = []
                self.current_account_index = 0
                self.last_rotation = None
        except Exception as e:
            self.print_error(f"Errore nel caricamento degli account: {e}")
            self.accounts = []
            self.current_account_index = 0
            self.last_rotation = None
    
    def save_accounts(self):
        """Salva gli account nel file JSON"""
        try:
            data = {
                'accounts': self.accounts,
                'current_account_index': self.current_account_index,
                'last_rotation': self.last_rotation
            }
            with open(self.accounts_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            self.print_error(f"Errore nel salvataggio degli account: {e}")
    
    def get_current_account(self):
        """Restituisce l'account corrente"""
        if self.accounts and 0 <= self.current_account_index < len(self.accounts):
            return self.accounts[self.current_account_index]
        return None
    
    def get_available_account(self):
        """Trova un account disponibile che non ha raggiunto il limite giornaliero"""
        # Prima controlla e resetta i contatori se necessario
        self._reset_daily_counters()
        
        for i, account in enumerate(self.accounts):
            if account.get('active', True):
                # Controlla se ha ancora upload disponibili
                if account.get('daily_uploads', 0) < account.get('max_daily_uploads', 5):
                    return account
        
        return None
    
    def _reset_daily_counters(self):
        """Resetta i contatori giornalieri se è un nuovo giorno"""
        today = datetime.now().date()
        for account in self.accounts:
            last_used = account.get('last_used')
            if last_used:
                try:
                    last_used_date = datetime.fromisoformat(last_used.replace('Z', '+00:00')).date()
                    if last_used_date != today:
                        # Reset del contatore se è un nuovo giorno
                        account['daily_uploads'] = 0
                        account['last_used'] = None
                except:
                    pass
    
    def get_credentials_for_account(self, account):
        """Ottiene le credenziali per un account specifico"""
        try:
            # Prova a caricare le credenziali dalle Secrets di Streamlit
            if self.is_streamlit_cloud():
                return self._get_credentials_from_secrets(account)
            else:
                return self._get_credentials_from_file(account)
        except Exception as e:
            self.print_error(f"Errore nell'ottenimento delle credenziali: {e}")
            return None
    
    def _get_credentials_from_secrets(self, account):
        """Ottiene le credenziali dalle Secrets di Streamlit"""
        try:
            import streamlit as st
            
            # Leggi le credenziali dalle Secrets
            client_secrets = st.secrets.get('YOUTUBE_CLIENT_SECRETS')
            if not client_secrets:
                self.print_error("YOUTUBE_CLIENT_SECRETS non trovato nelle Secrets")
                return None
            
            # Parsing delle credenziali
            if isinstance(client_secrets, str):
                import json
                client_secrets = json.loads(client_secrets)
            
            # Configura il flow OAuth2
            flow = InstalledAppFlow.from_client_config(
                client_secrets,
                scopes=['https://www.googleapis.com/auth/youtube.upload']
            )
            
            # Prova l'autenticazione locale
            try:
                credentials = flow.run_local_server(port=0)
            except Exception as e:
                if "could not locate runnable browser" in str(e):
                    self.print_info("Browser non disponibile, usando autenticazione console...")
                    # Fallback per ambiente headless
                    credentials = self._authenticate_console(flow)
                else:
                    raise e
            
            return credentials
            
        except Exception as e:
            self.print_error(f"Errore nell'autenticazione dalle Secrets: {e}")
            return None
    
    def _get_credentials_from_file(self, account):
        """Ottiene le credenziali da file locale (per sviluppo)"""
        try:
            # Cerca il file token per questo account
            token_file = f"token_{account['name'].lower().replace(' ', '_')}.pickle"
            
            credentials = None
            if os.path.exists(token_file):
                with open(token_file, 'rb') as token:
                    credentials = pickle.load(token)
            
            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                else:
                    # Crea un nuovo flow OAuth2
                    client_secrets_file = "client_secrets.json"
                    if not os.path.exists(client_secrets_file):
                        self.print_error(f"File {client_secrets_file} non trovato")
                        return None
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        client_secrets_file,
                        scopes=['https://www.googleapis.com/auth/youtube.upload']
                    )
                    
                    try:
                        credentials = flow.run_local_server(port=0)
                    except Exception as e:
                        if "could not locate runnable browser" in str(e):
                            self.print_info("Browser non disponibile, usando autenticazione console...")
                            credentials = self._authenticate_console(flow)
                        else:
                            raise e
                
                # Salva le credenziali
                with open(token_file, 'wb') as token:
                    pickle.dump(credentials, token)
            
            return credentials
            
        except Exception as e:
            self.print_error(f"Errore nell'autenticazione da file: {e}")
            return None
    
    def _authenticate_console(self, flow):
        """Autenticazione console per ambienti headless"""
        try:
            # Genera l'URL di autorizzazione
            auth_url, _ = flow.authorization_url(prompt='consent')
            self.print_info(f"Vai a questo URL per autorizzare l'applicazione: {auth_url}")
            
            # Chiedi il codice di autorizzazione
            auth_code = input("Incolla il codice di autorizzazione qui: ").strip()
            
            # Scambia il codice con le credenziali
            flow.fetch_token(code=auth_code)
            return flow.credentials
            
        except Exception as e:
            self.print_error(f"Errore nell'autenticazione console: {e}")
            return None
    
    def update_account_usage(self, account_name):
        """Aggiorna l'uso di un account"""
        for account in self.accounts:
            if account['name'] == account_name:
                # Incrementa il contatore
                account['daily_uploads'] = account.get('daily_uploads', 0) + 1
                account['last_used'] = datetime.now().isoformat()
                self.save_accounts()
                break
    
    def add_account(self, name, client_id, client_secret, project_id, max_daily_uploads=5):
        """Aggiunge un nuovo account YouTube"""
        # Rimuovi account esistenti con lo stesso nome
        self.accounts = [acc for acc in self.accounts if acc['name'] != name]
        
        new_account = {
            'name': name,
            'client_id': client_id,
            'client_secret': client_secret,
            'project_id': project_id,
            'daily_uploads': 0,
            'max_daily_uploads': max_daily_uploads,
            'last_used': None,
            'active': True
        }
        
        self.accounts.append(new_account)
        self.save_accounts()
        self.print_success(f"Account '{name}' aggiunto con successo!")
    
    def remove_account(self, account_name):
        """Rimuove un account"""
        # Rimuovi il file token associato
        token_file = f"token_{account_name.lower().replace(' ', '_')}.pickle"
        if os.path.exists(token_file):
            try:
                os.remove(token_file)
                self.print_info(f"File token {token_file} rimosso")
            except Exception as e:
                self.print_warning(f"Impossibile rimuovere {token_file}: {e}")
        
        # Rimuovi l'account dalla lista
        self.accounts = [acc for acc in self.accounts if acc['name'] != account_name]
        self.save_accounts()
        self.print_success(f"Account '{account_name}' rimosso!")
    
    def reset_account_usage(self, account_name):
        """Resetta l'uso giornaliero di un account"""
        for account in self.accounts:
            if account['name'] == account_name:
                account['daily_uploads'] = 0
                account['last_used'] = None
                self.save_accounts()
                self.print_success(f"Uso dell'account '{account_name}' resettato!")
                break
    
    def reset_all_accounts_usage(self):
        """Resetta l'uso di tutti gli account"""
        for account in self.accounts:
            account['daily_uploads'] = 0
            account['last_used'] = None
        self.save_accounts()
        self.print_success("Uso di tutti gli account resettato!")
    
    def toggle_account_status(self, account_name):
        """Attiva/disattiva un account"""
        for account in self.accounts:
            if account['name'] == account_name:
                account['active'] = not account.get('active', True)
                status = "attivato" if account['active'] else "disattivato"
                self.save_accounts()
                self.print_success(f"Account '{account_name}' {status}!")
                break
    
    def update_account_limit(self, account_name, new_limit):
        """Aggiorna il limite giornaliero di un account"""
        for account in self.accounts:
            if account['name'] == account_name:
                account['max_daily_uploads'] = new_limit
                self.save_accounts()
                self.print_success(f"Limite dell'account '{account_name}' aggiornato a {new_limit}!")
                break
    
    def export_accounts_config(self):
        """Esporta la configurazione degli account"""
        return {
            'accounts': self.accounts,
            'current_account_index': self.current_account_index,
            'last_rotation': self.last_rotation
        }
    
    def import_accounts_config(self, config_data):
        """Importa la configurazione degli account"""
        try:
            self.accounts = config_data.get('accounts', [])
            self.current_account_index = config_data.get('current_account_index', 0)
            self.last_rotation = config_data.get('last_rotation')
            self.save_accounts()
            self.print_success("Configurazione account importata con successo!")
        except Exception as e:
            self.print_error(f"Errore nell'importazione: {e}")
    
    def get_accounts_status(self):
        """Restituisce lo stato di tutti gli account"""
        # Prima resetta i contatori se necessario
        self._reset_daily_counters()
        
        status = []
        for account in self.accounts:
            status.append({
                'name': account['name'],
                'active': account.get('active', True),
                'daily_uploads': account.get('daily_uploads', 0),
                'max_daily_uploads': account.get('max_daily_uploads', 5),
                'last_used': account.get('last_used'),
                'available': account.get('active', True) and account.get('daily_uploads', 0) < account.get('max_daily_uploads', 5),
                'token_exists': self._check_token_exists(account['name'])
            })
        
        return status
    
    def _check_token_exists(self, account_name):
        """Controlla se esiste un token per l'account"""
        token_file = f"token_{account_name.lower().replace(' ', '_')}.pickle"
        return os.path.exists(token_file)
    
    def get_token_info(self):
        """Restituisce informazioni sui token salvati"""
        token_info = []
        for account in self.accounts:
            token_file = f"token_{account['name'].lower().replace(' ', '_')}.pickle"
            token_exists = os.path.exists(token_file)
            
            if token_exists:
                try:
                    # Prova a caricare il token per verificare se è valido
                    with open(token_file, 'rb') as f:
                        credentials = pickle.load(f)
                    
                    token_valid = credentials and credentials.valid
                    if credentials and credentials.expired and credentials.refresh_token:
                        try:
                            credentials.refresh(Request())
                            token_valid = True
                        except:
                            token_valid = False
                except:
                    token_valid = False
            else:
                token_valid = False
            
            token_info.append({
                'account_name': account['name'],
                'token_exists': token_exists,
                'token_valid': token_valid,
                'token_file': token_file
            })
        
        return token_info
    
    def print_info(self, message):
        """Stampa un messaggio informativo"""
        if self.is_streamlit_cloud():
            import streamlit as st
            st.info(message)
        else:
            print(f"ℹ️ {message}")
    
    def print_success(self, message):
        """Stampa un messaggio di successo"""
        if self.is_streamlit_cloud():
            import streamlit as st
            st.success(message)
        else:
            print(f"✅ {message}")
    
    def print_error(self, message):
        """Stampa un messaggio di errore"""
        if self.is_streamlit_cloud():
            import streamlit as st
            st.error(message)
        else:
            print(f"❌ {message}")
    
    def print_warning(self, message):
        """Stampa un messaggio di avvertimento"""
        if self.is_streamlit_cloud():
            import streamlit as st
            st.warning(message)
        else:
            print(f"⚠️ {message}")
    
    def is_streamlit_cloud(self):
        """Controlla se siamo su Streamlit Cloud"""
        return os.environ.get('STREAMLIT_SERVER_PORT') is not None 