from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

# Configurazione
TEMPLATE_DOC_ID = '1OIzZ_E83EH1e3xB5W6ztztm6n05VFYE7HXBiao1q2PU'

# Scopes necessari
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets'
]

def get_credentials():
    return service_account.Credentials.from_service_account_file(
        'service_account_key.json', scopes=SCOPES)

def test_doc_write():
    print("\n=== Test scrittura documento ===")
    try:
        # Inizializza i servizi
        print("\nInizializzazione servizi...")
        credentials = get_credentials()
        docs_service = build('docs', 'v1', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)
        print("Servizi inizializzati con successo")

        # Verifica accesso al template
        print("\nVerifica accesso al template...")
        template = drive_service.files().get(
            fileId=TEMPLATE_DOC_ID, 
            fields='id, name, owners, permissions'
        ).execute()
        print(f"Template trovato: {template['name']}")
        print(f"Proprietari: {[owner['emailAddress'] for owner in template.get('owners', [])]}")
        print(f"Permessi:")
        for perm in template.get('permissions', []):
            print(f"- {perm.get('role')} su {perm.get('emailAddress', perm.get('type'))}")

        # Crea una copia di test
        print("\nCreazione copia di test...")
        copy_title = "Test Scrittura"
        copied_file = drive_service.files().copy(
            fileId=TEMPLATE_DOC_ID,
            body={'name': copy_title}
        ).execute()
        doc_id = copied_file['id']
        print(f"Template copiato con ID: {doc_id}")

        # Prova a scrivere nel documento
        print("\nTest scrittura nel documento...")
        requests = [
            {
                'insertText': {
                    'location': {
                        'index': 1
                    },
                    'text': 'Test di scrittura - Se vedi questo testo, i permessi sono corretti!'
                }
            }
        ]
        
        result = docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        print("Scrittura completata con successo!")

        # Elimina il documento di test
        print("\nPulizia...")
        drive_service.files().delete(fileId=doc_id).execute()
        print("Documento di test eliminato")

        print("\n=== Test completato con successo! ===")
        return True

    except Exception as e:
        print(f"\n=== ERRORE DURANTE IL TEST ===")
        print(f"Errore: {e}")
        return False

if __name__ == '__main__':
    test_doc_write() 