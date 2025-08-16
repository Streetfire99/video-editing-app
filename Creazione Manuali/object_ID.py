from googleapiclient.discovery import build
from google.oauth2 import service_account
import json

SCOPES = ['https://www.googleapis.com/auth/documents']
DOCUMENT_ID = '1b7FpUOsnoNeGDEgIyB5-ADwSDHw8oDRfAYOnlvWUhuE'

creds = service_account.Credentials.from_service_account_file('service_account_key.json', scopes=SCOPES)
service = build('docs', 'v1', credentials=creds)

doc = service.documents().get(documentId=DOCUMENT_ID).execute()
print('--- INIZIO STRUTTURA DOCUMENTO (primi 2 livelli) ---')
for idx, element in enumerate(doc.get('body', {}).get('content', [])):
    print(f'Elemento {idx}: {list(element.keys())}')
    if 'paragraph' in element:
        for eidx, el in enumerate(element['paragraph'].get('elements', [])):
            print(f'  - paragraph element {eidx}: {list(el.keys())}')
    if 'table' in element:
        print('  - TABELLA trovata')
    if 'tableOfContents' in element:
        print('  - INDICE trovato')
print('--- FINE STRUTTURA DOCUMENTO ---')
# Se vuoi vedere tutto il JSON, decommenta la riga sotto
# print(json.dumps(doc, indent=2))

print('--- CERCO DRAWING (positionedObject/positionedObjectElement) ---')
for idx, element in enumerate(doc.get('body', {}).get('content', [])):
    if 'paragraph' in element:
        for eidx, el in enumerate(element['paragraph'].get('elements', [])):
            if 'positionedObjectElement' in el:
                object_id = el['positionedObjectElement']['positionedObjectId']
                print(f'Trovato drawing (positionedObjectElement) objectId: {object_id} (elemento {idx})')
if 'positionedObjects' in doc:
    for obj in doc['positionedObjects']:
        print('positionedObject:', obj)
print('--- FINE ---')
