from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import openai
import json
import os
from PyPDF2 import PdfMerger
import sys
from flask import Flask, request, jsonify
import traceback

# Configurazione
SPREADSHEET_ID = '1Jd0FpZKboNYsr2lX502yVFq2BBHqy8lZmiO1GOhNaY0'
TEMPLATE_INIZIO_ID = '1NJgT2_lfd4t5fGNQMrvBdPvgoceuxnAY4EPh86vS5Vg'
TEMPLATE_FINE_ID = '1uWtYGUNEYPvpPZPBJrCTdIyVoLv-vhVBRpSXoW8KbU0'
TEMPLATE_LAVATRICE_ID = '1b7FpUOsnoNeGDEgIyB5-ADwSDHw8oDRfAYOnlvWUhuE'
FOLDER_ID = '1cqkfF3uKI_xmQYv7EaWW6Yf7tVBhD8UG'

# Scopes necessari
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets'
]

# Mappatura nome elettrodomestico (minuscolo) -> ID Google Docs
APPLIANCE_DOC_IDS = {
    'lavatrice': '1b7FpUOsnoNeGDEgIyB5-ADwSDHw8oDRfAYOnlvWUhuE',
    'lavastoviglie': '1X-_TzDIcyINKJ2g90rNLEq3XdHMg2uJYhjOZtvC5okc',
    'piano cottura': '1hrG141E1sm3sBPglvHaQxSj873S6djuLtY5Mt3GB1iY',
    'forno': '1WKq6Y2YFN2MzdpmHKMWBBwXVNYBIrrY3WWk1yUqJ_-Y',
    'asciugatrice': '1Xwm-INyTrKiRHYmLGyW8ji_3LKS5pICJ2zE53wmk4ro',
    'microonde': '1IhpQIVN-MUfhWLDEixlfAsmhTUHkgp6gGBlVukpPS2g',
}

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint per il health check"""
    return jsonify({"status": "healthy"}), 200

@app.route('/debug', methods=['GET'])
def debug():
    """Endpoint per il debug delle variabili d'ambiente e file system"""
    try:
        debug_info = {
            "cwd": os.getcwd(),
            "files": os.listdir('.'),
            "env": {k: v for k, v in os.environ.items() if not k.startswith('_')},
            "service_account_exists": os.path.exists('service_account_key.json'),
            "openai_config_exists": os.path.exists('openai_config.json')
        }
        return jsonify(debug_info), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/generate', methods=['GET'])
def handle_generate_manual():
    apartment_name = request.args.get('apartment_name')
    if not apartment_name:
        return jsonify({"error": "Il parametro 'apartment_name' è obbligatorio"}), 400

    print(f"Richiesta ricevuta per generare il manuale per: {apartment_name}")
    try:
        # Modifica generate_manual per restituire anche il link e l'errore
        success, pdf_link, error = generate_manual(apartment_name, return_link=True)
        if success:
            return jsonify({
                "message": f"Manuale generato con successo per {apartment_name}",
                "pdf_link": pdf_link
            }), 200
        else:
            return jsonify({
                "error": f"Errore nella generazione del manuale per {apartment_name}",
                "details": error
            }), 500
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return jsonify({
            "error": "Eccezione non gestita",
            "details": str(e),
            "traceback": tb
        }), 500

def get_credentials():
    """Ottiene le credenziali per le API Google"""
    try:
        print("Cerco service_account_key.json in:", os.getcwd())
        print("Contenuto della cartella:", os.listdir('.'))
        
        # Su Cloud Run, leggi da variabili d'ambiente
        if os.environ.get('K_SERVICE'):  # Siamo su Cloud Run
            print("Ambiente Cloud Run rilevato")
            service_account_key = os.environ.get('SERVICE_ACCOUNT_KEY')
            if not service_account_key:
                raise ValueError("SERVICE_ACCOUNT_KEY non trovato nelle variabili d'ambiente")
            service_account_info = json.loads(service_account_key)
            return service_account.Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES)
        else:  # Ambiente locale
            print("Ambiente locale rilevato")
            if not os.path.exists('service_account_key.json'):
                raise FileNotFoundError("service_account_key.json non trovato")
            return service_account.Credentials.from_service_account_file(
                'service_account_key.json', scopes=SCOPES)
    except Exception as e:
        print(f"Errore nel caricamento delle credenziali: {str(e)}")
        print(f"Traceback completo: {traceback.format_exc()}")
        raise

def get_apartment_data(service, apartment_name):
    """Recupera i dati dell'appartamento da tutti i fogli necessari"""
    print(f"\n=== Recupero dati per l'appartamento: {apartment_name} ===")
    data = {}
    
    # Dati base dall'appartamento
    print("\n1. Recupero dati base dall'appartamento...")
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='contratti!A:Z'
    ).execute()
    values = result.get('values', [])
    headers = values[0]
    print(f"Colonne trovate: {headers}")
    
    for row in values[1:]:
        if row[headers.index('appartamento')].lower() == apartment_name.lower():
            data['nome_appartamento'] = row[headers.index('appartamento')]
            # Mostra indirizzo completo se disponibile
            if 'Via' in headers and len(row) > headers.index('Via'):
                data['indirizzo'] = row[headers.index('Via')]
            else:
                data['indirizzo'] = data['nome_appartamento']
            
            # Aggiungi città, provincia e regione per le indicazioni
            if 'Citta' in headers and len(row) > headers.index('Citta'):
                data['citta'] = row[headers.index('Citta')]
            else:
                data['citta'] = 'Milano'
                
            if 'Provincia' in headers and len(row) > headers.index('Provincia'):
                data['provincia'] = row[headers.index('Provincia')]
            else:
                data['provincia'] = 'MI'
                
            if 'Regione' in headers and len(row) > headers.index('Regione'):
                data['regione'] = row[headers.index('Regione')]
            else:
                data['regione'] = 'Lombardia'
                
            print(f"Dati base trovati - Indirizzo: {data['indirizzo']}, Città: {data['citta']}, Provincia: {data['provincia']}, Regione: {data['regione']}")
            break
    
    # Dati WiFi
    print("\n2. Recupero dati WiFi...")
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='wi-fi!A:Z'
    ).execute()
    values = result.get('values', [])
    headers = values[0]
    print(f"Colonne WiFi trovate: {headers}")
    
    for row in values[1:]:
        if row[headers.index('appartamento')].lower() == apartment_name.lower():
            data['wifi'] = {
                'nome_rete': row[headers.index('nome_rete')] if 'nome_rete' in headers and len(row) > headers.index('nome_rete') else '',
                'password': row[headers.index('password')] if 'password' in headers and len(row) > headers.index('password') else ''
            }
            print(f"Dati WiFi trovati - Rete: {data['wifi']['nome_rete']}")
            break
    
    # Genera istruzioni per arrivare da Malpensa e Orio al Serio
    print("\n3. Generazione istruzioni per Malpensa e Orio al Serio...")
    indirizzo_completo = f"{data['indirizzo']}, {data['citta']} ({data['provincia']}), {data['regione']}"
    data['istruzioni_malpensa'] = generate_directions(indirizzo_completo, "Malpensa")
    data['istruzioni_orio'] = generate_directions(indirizzo_completo, "Orio al Serio")
    
    # Genera istruzioni per arrivare da Linate e per il Duomo
    print("\n4. Generazione istruzioni per Linate e Duomo...")
    data['istruzioni_linate'] = generate_directions(indirizzo_completo, "Linate")
    data['istruzioni_duomo'] = generate_directions(indirizzo_completo, "Duomo")
    
    # Elettrodomestici e loro istruzioni
    print("\n5. Recupero dati elettrodomestici...")
    data['elettrodomestici'] = []
    
    # Prima recupero gli elettrodomestici presenti
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='elettrodomestici!A:Z'
    ).execute()
    values = result.get('values', [])
    headers = values[0]
    print(f"Colonne elettrodomestici trovate: {headers}")
    
    elettrodomestici = []
    for row in values[1:]:
        app_value = row[headers.index('appartamento')] if len(row) > headers.index('appartamento') else ''
        if app_value.lower() == apartment_name.lower():
            nome = row[headers.index('nome_elettrodomestico')] if 'nome_elettrodomestico' in headers and len(row) > headers.index('nome_elettrodomestico') else ''
            url_video = row[headers.index('url_video')] if 'url_video' in headers and len(row) > headers.index('url_video') else ''
            if nome:  # Solo se c'è un nome valido
                elettrodomestico = {
                    'nome': nome,
                    'url_video': url_video
                }
                elettrodomestici.append(elettrodomestico)
    
    # Poi recupero le istruzioni
    print("\n6. Recupero istruzioni elettrodomestici...")
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='appliances!A:Z'
    ).execute()
    values = result.get('values', [])
    headers = values[0]
    print(f"Colonne istruzioni trovate: {headers}")
    
    for row in values[1:]:
        app_value = row[headers.index('Property Name')] if 'Property Name' in headers and len(row) > headers.index('Property Name') else ''
        if app_value.lower() == apartment_name.lower():
            nome_elettrodomestico = row[headers.index('Tipo')] if 'Tipo' in headers and len(row) > headers.index('Tipo') else ''
            istruzioni = row[headers.index('istruzioni')] if 'istruzioni' in headers and len(row) > headers.index('istruzioni') else ''
            
            for elettrodomestico in elettrodomestici:
                if elettrodomestico['nome'].lower() == nome_elettrodomestico.lower():
                    elettrodomestico['istruzioni'] = istruzioni if istruzioni else 'Istruzioni non disponibili'
                    data['elettrodomestici'].append(elettrodomestico)
                    print(f"Istruzioni trovate per: {nome_elettrodomestico}")
                    break
    
    print("\n=== Dati recuperati completi ===")
    print(f"Indirizzo: {data.get('indirizzo', 'Non trovato')}")
    print(f"Città: {data.get('citta', 'Non trovato')}")
    print(f"Provincia: {data.get('provincia', 'Non trovato')}")
    print(f"Regione: {data.get('regione', 'Non trovato')}")
    print(f"WiFi: {data.get('wifi', 'Non trovato')}")
    print(f"Numero elettrodomestici: {len(data.get('elettrodomestici', []))}")
    return data

def generate_directions(indirizzo_completo, source):
    """Genera istruzioni per arrivare all'appartamento da una fonte specifica"""
    try:
        with open('openai_config.json') as f:
            config = json.load(f)
            client = openai.OpenAI(api_key=config['openai_api_key'])
        
        if source == "Duomo":
            prompt = f"""Genera istruzioni chiare e concise per andare dall'appartamento in {indirizzo_completo} al centro città (Duomo).

Le istruzioni devono essere:
1. In italiano (NON usare parole in inglese)
2. Formattate in 3 step numerati
3. Ogni step deve iniziare con un verbo all'imperativo
4. Ogni step deve essere una singola frase breve e chiara
5. Non usare punteggiatura alla fine di ogni step
6. Non aggiungere testo extra o spiegazioni
7. Tutte le istruzioni devono stare in una sola pagina

Esempio di formato:
OPZIONE 1: PER RAGGIUNGERE IL CENTRO CITTÀ

1. Prendi la metropolitana M1 dalla fermata Gambara in direzione Sesto
2. Fai 9 fermate e scendi alla fermata Duomo
3. Esci dalla stazione e sei arrivato in Piazza Duomo"""
        else:
            prompt = f"""Genera istruzioni chiare e concise per arrivare all'appartamento in {indirizzo_completo} da {source}.

Le istruzioni devono essere:
1. In italiano (NON usare parole in inglese)
2. Formattate in 3 step numerati
3. Ogni step deve iniziare con un verbo all'imperativo
4. Ogni step deve essere una singola frase breve e chiara
5. Non usare punteggiatura alla fine di ogni step
6. Non aggiungere testo extra o spiegazioni
7. Tutte le istruzioni devono stare in una sola pagina

Esempio di formato per le istruzioni da Linate:
OPZIONE 1: AEROPORTO DI MILANO LINATE

1. Prendi la metropolitana M4 dalla fermata Linate Aeroporto in direzione San Babila
2. Fai 7 fermate e scendi alla fermata San Babila
3. Fai il cambio con la metropolitana M1 direzione Bisceglie e scendi alla fermata Gambara

L'appartamento sarà a pochi passi dalla fermata."""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Genera le istruzioni per {'andare al centro città' if source == 'Duomo' else f'arrivare da {source}'} all'indirizzo {indirizzo_completo}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Errore nella generazione delle istruzioni per {source}: {e}")
        return f"Istruzioni non disponibili per {source}"

def generate_appliance_instructions(instructions):
    """Genera istruzioni in 4-5 step usando OpenAI"""
    print(f"\n=== Generazione istruzioni per elettrodomestico ===")
    print(f"Istruzioni originali: {instructions[:100]}...")
    try:
        # Su Cloud Run, leggi da variabili d'ambiente
        if os.environ.get('K_SERVICE'):
            openai_api_key = os.environ.get('OPENAI_API_KEY')
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY non trovato nelle variabili d'ambiente")
            client = openai.OpenAI(api_key=openai_api_key)
        else:
            if not os.path.exists('openai_config.json'):
                raise FileNotFoundError("openai_config.json non trovato")
            with open('openai_config.json') as f:
                config = json.load(f)
                client = openai.OpenAI(api_key=config['openai_api_key'])
        
        print("Client OpenAI inizializzato correttamente")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """Sei un assistente che crea istruzioni chiare e concise per elettrodomestici.
Le istruzioni devono essere:
1. In italiano (NON usare parole in inglese)
2. Formattate in ESATTAMENTE 4 step numerati (non di più, non di meno)
3. Ogni step deve iniziare con un verbo all'imperativo
4. Ogni step deve essere una singola frase di circa 15 parole
5. Non usare punteggiatura alla fine di ogni step
6. Non aggiungere testo extra o spiegazioni
7. Tutte le istruzioni devono stare in una sola pagina
8. Se le istruzioni originali sono vuote o non disponibili, restituisci 'Istruzioni non disponibili'
9. Le istruzioni devono essere esaustive e coprire l'intero processo di utilizzo dell'elettrodomestico

Esempio di formato per una lavatrice:
1. Apri lo sportello della lavatrice e inserisci il bucato fino a riempire il cestello per 3/4
2. Aggiungi il detersivo nel cassetto superiore e l'ammorbidente in quello con il fiore
3. Seleziona il programma di lavaggio desiderato usando la manopola e regola la temperatura
4. Premi il pulsante start per avviare il ciclo di lavaggio e attendi il segnale acustico di fine"""},
                {"role": "user", "content": f"Trasforma queste istruzioni in ESATTAMENTE 4 step seguendo il formato specificato: {instructions}"}
            ]
        )
        generated_instructions = response.choices[0].message.content
        print(f"Istruzioni generate: {generated_instructions[:100]}...")
        return generated_instructions
    except Exception as e:
        print(f"Errore nella generazione delle istruzioni: {e}")
        print(f"Traceback completo: {traceback.format_exc()}")
        return "Istruzioni non disponibili"

def read_template_content(docs_service):
    """Legge il contenuto del template per debug"""
    try:
        doc = docs_service.documents().get(documentId=TEMPLATE_DOC_ID).execute()
        print("\n=== Contenuto del Template ===")
        for element in doc.get('body', {}).get('content', []):
            if 'paragraph' in element:
                for para_element in element['paragraph']['elements']:
                    if 'textRun' in para_element:
                        text = para_element['textRun'].get('content', '')
                        if text.strip():  # Solo testo non vuoto
                            print(f"Testo trovato: '{text.strip()}'")
    except Exception as e:
        print(f"Errore nella lettura del template: {e}")

def create_manual_copy(drive_service, docs_service, apartment_name, data):
    """Crea una copia del template e la personalizza"""
    print(f"\n=== Creazione manuale per {apartment_name} ===")
    try:
        # Crea copie dei template
        print("\nCreazione copie dei template...")
        doc_ids = {}
        
        # Copia INIZIO
        copy_inizio = drive_service.files().copy(
            fileId=TEMPLATE_INIZIO_ID,
            body={'name': f"INIZIO MANUALE ITA {apartment_name}"}
        ).execute()
        doc_ids['inizio'] = copy_inizio['id']
        print(f"Template INIZIO copiato con ID: {doc_ids['inizio']}")
        
        # Copia FINE
        copy_fine = drive_service.files().copy(
            fileId=TEMPLATE_FINE_ID,
            body={'name': f"FINE MANUALE ITA {apartment_name}"}
        ).execute()
        doc_ids['fine'] = copy_fine['id']
        print(f"Template FINE copiato con ID: {doc_ids['fine']}")
        
        # Personalizza INIZIO
        print("\nPersonalizzazione INIZIO...")
        requests_inizio = [
            # Aggiorna intestazione
            {
                'replaceAllText': {
                    'containsText': {'text': 'Indirizzo, Città'},
                    'replaceText': f"{data['indirizzo']}, {data['citta']}"
                }
            },
            # Aggiorna WiFi
            {
                'replaceAllText': {
                    'containsText': {'text': 'NOME RETE'},
                    'replaceText': data['wifi']['nome_rete']
                }
            },
            {
                'replaceAllText': {
                    'containsText': {'text': 'PASSWORD'},
                    'replaceText': data['wifi']['password']
                }
            },
            # Aggiorna istruzioni Malpensa
            {
                'replaceAllText': {
                    'containsText': {'text': 'La migliore opzione per raggiungere la casa da Milano-Malpensa è'},
                    'replaceText': data['istruzioni_malpensa']
                }
            },
            # Aggiorna istruzioni Orio al Serio
            {
                'replaceAllText': {
                    'containsText': {'text': 'La migliore opzione per raggiungere la casa da Orio al Serio è'},
                    'replaceText': data['istruzioni_orio']
                }
            },
            # Aggiorna istruzioni Linate
            {
                'replaceAllText': {
                    'containsText': {'text': 'La migliore opzione per raggiungere la casa da Milano-Linate è'},
                    'replaceText': data['istruzioni_linate']
                }
            },
            # Aggiorna istruzioni Duomo
            {
                'replaceAllText': {
                    'containsText': {'text': 'La migliore opzione per raggiungere il centro città è'},
                    'replaceText': data['istruzioni_duomo']
                }
            }
        ]
        
        # Applica modifiche a INIZIO
        docs_service.documents().batchUpdate(
            documentId=doc_ids['inizio'],
            body={'requests': requests_inizio}
        ).execute()
        print("INIZIO personalizzato con successo")
        
        # Per ogni elettrodomestico
        print("\nAggiornamento istruzioni elettrodomestici...")
        for elettrodomestico in data['elettrodomestici']:
            nome_elettro = elettrodomestico['nome'].lower()
            print(f"\nElaborazione elettrodomestico: {nome_elettro}")
            # Copia il template dell'elettrodomestico se presente nella mappatura
            if nome_elettro in APPLIANCE_DOC_IDS:
                copy_elettrodomestico = drive_service.files().copy(
                    fileId=APPLIANCE_DOC_IDS[nome_elettro],
                    body={'name': f"{nome_elettro.upper()} MANUALE ITA {apartment_name}"}
                ).execute()
                doc_ids[nome_elettro] = copy_elettrodomestico['id']
                print(f"Template {nome_elettro} copiato con ID: {doc_ids[nome_elettro]}")
                # Genera istruzioni
                istruzioni = generate_appliance_instructions(elettrodomestico['istruzioni'])
                # Sostituisce le istruzioni template con le nuove istruzioni
                requests_elettrodomestico = [
                    {
                        'replaceAllText': {
                            'containsText': {'text': 'Testo'},
                            'replaceText': istruzioni
                        }
                    }
                ]
                # Applica il link solo alla prima occorrenza di "Guarda video" DOPO l'inserimento delle istruzioni
                if elettrodomestico.get('url_video'):
                    # Applica prima le istruzioni
                    docs_service.documents().batchUpdate(
                        documentId=doc_ids[nome_elettro],
                        body={'requests': requests_elettrodomestico}
                    ).execute()
                    # Ora cerca "Guarda video" e applica il link
                    elettro_doc = docs_service.documents().get(documentId=doc_ids[nome_elettro]).execute()
                    requests_link = []
                    found = False
                    for element in elettro_doc.get('body', {}).get('content', []):
                        if 'paragraph' in element:
                            for el in element['paragraph'].get('elements', []):
                                if 'textRun' in el and 'Guarda video' in el['textRun'].get('content', ''):
                                    content = el['textRun']['content']
                                    start = el['startIndex']
                                    idx = content.find('Guarda video')
                                    if idx != -1 and not found:
                                        start_idx = start + idx
                                        end_idx = start_idx + len('Guarda video')
                                        requests_link.append({
                                            'updateTextStyle': {
                                                'range': {
                                                    'startIndex': start_idx,
                                                    'endIndex': end_idx
                                                },
                                                'textStyle': {
                                                    'link': {
                                                        'url': elettrodomestico['url_video']
                                                    }
                                                },
                                                'fields': 'link'
                                            }
                                        })
                                        found = True
                                        break
                            if found:
                                break
                    if requests_link:
                        docs_service.documents().batchUpdate(
                            documentId=doc_ids[nome_elettro],
                            body={'requests': requests_link}
                        ).execute()
                else:
                    # Se non c'è video, applica solo le istruzioni
                    docs_service.documents().batchUpdate(
                        documentId=doc_ids[nome_elettro],
                        body={'requests': requests_elettrodomestico}
                    ).execute()
                print(f"{nome_elettro.upper()} personalizzato con successo")
            else:
                print(f"Nessun template trovato per {nome_elettro}, saltato.")
        
        return doc_ids
        
    except Exception as e:
        print(f"Errore nella creazione del manuale: {e}")
        return None

def export_to_pdf(drive_service, doc_ids, apartment_name):
    """Sposta i documenti nella cartella giusta, esporta come PDF, elimina i doc"""
    print(f"\n=== Esportazione PDF per {apartment_name} ===")
    try:
        # ID della root fornita
        ROOT_FOLDER_ID = '1sZUHgHo1pv_0II8b7uRyzxfn87512q2V'
        folder_id = ROOT_FOLDER_ID
        print(f"Cerco cartella per l'appartamento: {apartment_name}")
        # 1. Trova la cartella dell'appartamento
        results = drive_service.files().list(
            q=f"'{ROOT_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="files(id, name)"
        ).execute()
        apartment_folder_id = None
        for f in results.get('files', []):
            if f['name'].strip().lower() == apartment_name.strip().lower():
                apartment_folder_id = f['id']
                break
        if apartment_folder_id:
            print(f"Trovata cartella appartamento: {apartment_folder_id}")
            # 2. Cerca la sottocartella "Guide e documenti"
            subresults = drive_service.files().list(
                q=f"'{apartment_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                fields="files(id, name)"
            ).execute()
            guide_folder_id = None
            for sf in subresults.get('files', []):
                if sf['name'].strip().lower() == 'guide e documenti':
                    guide_folder_id = sf['id']
                    break
            if guide_folder_id:
                print(f"Trovata sottocartella 'Guide e documenti': {guide_folder_id}")
                folder_id = guide_folder_id
            else:
                print("Nessuna sottocartella 'Guide e documenti', salvo nella cartella dell'appartamento.")
                folder_id = apartment_folder_id
        else:
            print("Nessuna cartella appartamento trovata, salvo nella root.")
            folder_id = ROOT_FOLDER_ID

        # Lista dei PDF da unire nell'ordine corretto
        pdf_files = []
        
        # Esporta ogni documento come PDF nell'ordine corretto
        ordered_docs = ['inizio'] + [k for k in doc_ids.keys() if k not in ['inizio', 'fine']] + ['fine']
        
        for doc_type in ordered_docs:
            doc_id = doc_ids[doc_type]
            print(f"\nEsportazione {doc_type} come PDF...")
            import io
            from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
            
            request = drive_service.files().export_media(
                fileId=doc_id,
                mimeType='application/pdf'
            )
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Download PDF {doc_type}: {int(status.progress() * 100)}%")
            fh.seek(0)
            
            # Salva il PDF localmente
            pdf_filename = f"{doc_type.upper()}_MANUALE_ITA_{apartment_name}.pdf"
            print(f"\nSalvataggio PDF locale: {pdf_filename}")
            with open(pdf_filename, "wb") as f:
                f.write(fh.read())
            
            pdf_files.append(pdf_filename)
            
            # Elimina il Google Doc
            print(f"\nRimozione documento Google {doc_type}...")
            drive_service.files().delete(fileId=doc_id).execute()
            print(f"Documento Google {doc_type} rimosso")
        
        # Unisci i PDF
        print("\nUnione dei PDF...")
        merger = PdfMerger()
        
        for pdf in pdf_files:
            merger.append(pdf)
        
        # Salva il PDF unito
        final_pdf = f"MANUALE_ITA_{apartment_name}.pdf"
        merger.write(final_pdf)
        merger.close()
        
        # Carica il PDF unito nella cartella giusta
        print(f"\nCaricamento PDF unito nella cartella Drive (ID: {folder_id})...")
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(final_pdf, mimetype='application/pdf', resumable=True)
        pdf_file = drive_service.files().create(
            body={
                'name': final_pdf,
                'parents': [folder_id]
            },
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        print(f"PDF unito caricato con successo. Link: {pdf_file['webViewLink']}")
        
        # Elimina i file temporanei
        print("\nPulizia file temporanei...")
        for pdf in pdf_files:
            os.remove(pdf)
        os.remove(final_pdf)
        print("File temporanei rimossi")
        
        return pdf_file['webViewLink']
        
    except Exception as e:
        print(f"Errore nell'esportazione del PDF: {e}")
        return None

def update_checkin_sheet(service, apartment_name, pdf_link):
    """Aggiorna il foglio check-in con il link del PDF"""
    print(f"\n=== Aggiornamento foglio check-in per {apartment_name} ===")
    try:
        # Trova la riga dell'appartamento
        print("\nRecupero dati dal foglio check-in...")
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='check-in!A:Z'
        ).execute()
        values = result.get('values', [])
        headers = values[0]
        print(f"Colonne trovate: {headers}")
        
        # Trova l'indice della colonna "Manuali ITA"
        col_index = headers.index("Manuali ITA")
        col_letter = chr(ord('A') + col_index)
        print(f"Colonna 'Manuali ITA' trovata: {col_letter}")
        
        for i, row in enumerate(values[1:], start=2):
            if row[0].lower() == apartment_name.lower():
                print(f"\nTrovata riga per {apartment_name} (riga {i})")
                # Aggiorna la colonna "Manuali ITA"
                range_name = f'check-in!{col_letter}{i}'
                print(f"Aggiornamento cella {range_name} con il link PDF")
                service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=range_name,
                    valueInputOption='RAW',
                    body={'values': [[pdf_link]]}
                ).execute()
                print("Link PDF aggiornato con successo")
                break
                
    except Exception as e:
        print(f"Errore nell'aggiornamento del foglio: {e}")

def generate_manual(apartment_name, return_link=False):
    """Funzione principale che coordina tutto il processo"""
    print(f"\n{'='*50}")
    print(f"INIZIO GENERAZIONE MANUALE PER: {apartment_name}")
    print(f"{'='*50}")
    
    try:
        # Inizializza i servizi
        print("\nInizializzazione servizi...")
        credentials = get_credentials()
        sheets_service = build('sheets', 'v4', credentials=credentials)
        docs_service = build('docs', 'v1', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)
        print("Servizi inizializzati con successo")
        
        # Recupera i dati dell'appartamento
        data = get_apartment_data(sheets_service, apartment_name)
        
        # Crea e personalizza il manuale
        doc_ids = create_manual_copy(drive_service, docs_service, apartment_name, data)
        if not doc_ids:
            print("Errore nella creazione del manuale")
            if return_link:
                return False, None, "Errore nella creazione del manuale"
            return False
        
        # Esporta come PDF e salva
        pdf_link = export_to_pdf(drive_service, doc_ids, apartment_name)
        if not pdf_link:
            print("Errore nell'esportazione del PDF")
            if return_link:
                return False, None, "Errore nell'esportazione del PDF"
            return False
        
        # Aggiorna il foglio check-in
        update_checkin_sheet(sheets_service, apartment_name, pdf_link)
        
        print(f"\n{'='*50}")
        print(f"MANUALE GENERATO CON SUCCESSO PER: {apartment_name}")
        print(f"Link PDF: {pdf_link}")
        print(f"{'='*50}")
        if return_link:
            return True, pdf_link, None
        return True
        
    except Exception as e:
        print(f"\n{'='*50}")
        print(f"ERRORE NELLA GENERAZIONE DEL MANUALE PER: {apartment_name}")
        print(f"Errore: {e}")
        print(f"{'='*50}")
        if return_link:
            return False, None, str(e)
        return False

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    if len(sys.argv) > 1 and sys.argv[1] == 'serve':
        print(f"Avvio server Flask sulla porta {port}")
        print(f"Directory corrente: {os.getcwd()}")
        print(f"File presenti: {os.listdir('.')}")
        app.run(host='0.0.0.0', port=port)
    else:
        apartment_name = sys.argv[1] if len(sys.argv) > 1 else "Bari"
        result = generate_manual(apartment_name)
        if isinstance(result, tuple):
            success, pdf_link, error = result
        else:
            success = result
            pdf_link = None
            error = None
        if success:
            print(f"Manuale generato con successo per {apartment_name}")
        else:
            print(f"Errore nella generazione del manuale per {apartment_name}")