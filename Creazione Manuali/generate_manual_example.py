from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = '1Jd0FpZKboNYsr2lX502yVFq2BBHqy8lZmiO1GOhNaY0'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SERVICE_ACCOUNT_FILE = 'service_account_key.json'

def get_google_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=credentials)
    return service

def get_sheet_data(service, sheet_name, apartment_name, apartment_column_index=0):
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=sheet_name
        ).execute()
        values = result.get('values', [])
        if not values:
            return None, [] # No data or headers
        
        headers = values[0]
        matched_rows = []
        for row in values[1:]:
            if len(row) > apartment_column_index and row[apartment_column_index].strip().lower() == apartment_name.strip().lower():
                matched_rows.append(row)
        return headers, matched_rows
    except Exception as e:
        print(f"Errore durante il recupero dei dati dal foglio {sheet_name}: {e}")
        return None, []

def main(apartment_name):
    service = get_google_sheets_service()
    manual_content = {}

    print(f"--- Generazione Esempio Manuale per: {apartment_name} ---")

    # 1. Foto Principale
    # Foglio: foto, Colonna: Link Foto (assumiamo che la colonna "Appartamento" sia la prima, indice 0)
    # e "Link Foto" sia la terza, indice 2
    foto_headers, foto_rows = get_sheet_data(service, "foto", apartment_name, apartment_column_index=0)
    if foto_rows and len(foto_rows[0]) > 2:
        manual_content['Foto principale'] = foto_rows[0][2] # Assumendo Link Foto sia la terza colonna
    else:
        manual_content['Foto principale'] = "N/A (Foto non trovata)"

    # 2. Descrizione how to reach the flat
    # Foglio: Check-in, Colonna: Messaggio Come arrivare da MPX/BGY (assumendo appartamento indice 0, Messaggio indice 16)
    checkin_headers, checkin_rows = get_sheet_data(service, "Check-in", apartment_name, apartment_column_index=0)
    if checkin_headers:
        try:
            msg_index = checkin_headers.index("Messaggio Come arrivare da MPX/BGY")
            if checkin_rows and len(checkin_rows[0]) > msg_index and checkin_rows[0][msg_index]:
                manual_content['Descrizione how to reach'] = checkin_rows[0][msg_index]
            else: # Fallback
                apt_headers, apt_rows = get_sheet_data(service, "appartamenti", apartment_name, apartment_column_index=0)
                if apt_headers:
                    try:
                        desc_index = apt_headers.index("descrizioneAppartamento") # o altro campo descrizione idoneo
                        if apt_rows and len(apt_rows[0]) > desc_index:
                             manual_content['Descrizione how to reach'] = apt_rows[0][desc_index]
                        else:
                            manual_content['Descrizione how to reach'] = "N/A (Descrizione non trovata)"
                    except ValueError: # Colonna descrizione non trovata in appartamenti
                         manual_content['Descrizione how to reach'] = "N/A (Colonna descrizione non trovata nel fallback)"
                else:
                    manual_content['Descrizione how to reach'] = "N/A (Fallback sheet 'appartamenti' non trovato o vuoto)"

        except ValueError: # Colonna "Messaggio Come arrivare da MPX/BGY" non trovata
            manual_content['Descrizione how to reach'] = "N/A (Colonna messaggio non trovata in Check-in)"
    else:
        manual_content['Descrizione how to reach'] = "N/A (Foglio Check-in non trovato o vuoto)"


    # 3. Wi-Fi
    # Foglio: wi-fi, Colonne: nome_rete, password, posizione_router (assumendo appartamento indice 0)
    wifi_headers, wifi_rows = get_sheet_data(service, "wi-fi", apartment_name, apartment_column_index=0)
    if wifi_headers and wifi_rows:
        try:
            nome_rete_idx = wifi_headers.index("nome_rete")
            password_idx = wifi_headers.index("password")
            posizione_idx = wifi_headers.index("posizione_router")
            row = wifi_rows[0] # Prendo la prima corrispondenza
            manual_content['Wi-Fi'] = f"Rete: {row[nome_rete_idx]}\nPassword: {row[password_idx]}\nPosizione Router: {row[posizione_idx]}"
        except (ValueError, IndexError):
            manual_content['Wi-Fi'] = "N/A (Dati Wi-Fi incompleti o colonne non trovate)"
    else:
        manual_content['Wi-Fi'] = "N/A (Dati Wi-Fi non trovati)"

    # 4. Appliances
    # Foglio: elettrodomestici, Colonne: nome_elettrodomestico, modello, ecc. (assumendo appartamento indice 0)
    elet_headers, elet_rows = get_sheet_data(service, "elettrodomestici", apartment_name, apartment_column_index=0)
    if elet_headers and elet_rows:
        manual_content['Appliances'] = []
        try:
            nome_idx = elet_headers.index("nome_elettrodomestico")
            desc_idx = elet_headers.index("descrizione")
            # Aggiungi altri indici se necessario (modello, marca_serial, anno, posizione)
            # modello_idx = elet_headers.index("modello")
            # marca_idx = elet_headers.index("marca_serial")

            for row in elet_rows:
                appliance_info = f"- {row[nome_idx]}"
                if len(row) > desc_idx and row[desc_idx]:
                    appliance_info += f": {row[desc_idx]}"
                # if len(row) > modello_idx and row[modello_idx]:
                #     appliance_info += f" (Modello: {row[modello_idx]})"
                # if len(row) > marca_idx and row[marca_idx]:
                #     appliance_info += f" (Marca/Seriale: {row[marca_idx]})"
                manual_content['Appliances'].append(appliance_info)
        except (ValueError, IndexError):
             manual_content['Appliances'] = ["N/A (Dati elettrodomestici incompleti o colonne non trovate)"]
    else:
        manual_content['Appliances'] = ["N/A (Elettrodomestici non trovati)"]

    # 5. Imprevisti
    # Foglio: contatti (idraulico, elettricista, tuttofare)
    # Foglio: climatizzazione (tipologia_sistema)
    # Foglio: utenze (nome_utenza tipo "Luce" o "Gas")
    imprevisti_data = []
    cont_headers, cont_rows = get_sheet_data(service, "contatti", apartment_name, apartment_column_index=0)
    if cont_headers and cont_rows:
        row = cont_rows[0]
        try:
            idr_idx = cont_headers.index("idraulico")
            idr_num_idx = cont_headers.index("numero_idraulico")
            ele_idx = cont_headers.index("elettricista")
            ele_num_idx = cont_headers.index("numero_elettricista")
            tut_idx = cont_headers.index("tuttofare")
            tut_num_idx = cont_headers.index("numero_tuttofare")

            if len(row) > idr_num_idx and row[idr_idx] and row[idr_num_idx]:
                imprevisti_data.append(f"Idraulico: {row[idr_idx]} ({row[idr_num_idx]})")
            if len(row) > ele_num_idx and row[ele_idx] and row[ele_num_idx]:
                imprevisti_data.append(f"Elettricista: {row[ele_idx]} ({row[ele_num_idx]})")
            if len(row) > tut_num_idx and row[tut_idx] and row[tut_num_idx]:
                imprevisti_data.append(f"Tuttofare: {row[tut_idx]} ({row[tut_num_idx]})")
        except (ValueError, IndexError):
            imprevisti_data.append("N/A (Contatti assistenza incompleti o colonne non trovate)")
    else:
        imprevisti_data.append("N/A (Contatti assistenza non trovati)")

    # Aggiungi info da climatizzazione e utenze se necessario per "Imprevisti"
    # Per ora mi concentro sui contatti, come da mappatura CSV più semplice.

    manual_content['Imprevisti'] = imprevisti_data if imprevisti_data else ["Nessuna informazione specifica per imprevisti."]
    
    # Stampa il contenuto del manuale
    print("\n=== CONTENUTO MANUALE (ESEMPIO TESTUALE) ===")
    print(f"Appartamento: {apartment_name}\n")

    print(f"1. Foto Principale:\n   {manual_content.get('Foto principale', 'N/A')}\n")
    print(f"2. Come Raggiungere l'Appartamento:\n   {manual_content.get('Descrizione how to reach', 'N/A')}\n")
    print(f"3. Wi-Fi:\n   {manual_content.get('Wi-Fi', 'N/A').replace('\\n', '\n   ')}\n") # Gestisce i newline per il Wi-Fi
    
    print("4. Elettrodomestici:")
    if isinstance(manual_content.get('Appliances'), list) and manual_content.get('Appliances'):
        for item in manual_content['Appliances']:
            print(f"   {item}")
    else:
        print("   N/A")
    print("")

    print("5. Imprevisti:")
    if isinstance(manual_content.get('Imprevisti'), list) and manual_content.get('Imprevisti'):
        for item in manual_content['Imprevisti']:
            print(f"   {item}")
    else:
        print("   N/A")
    print("\n--- Fine Esempio ---")

if __name__ == '__main__':
    target_apartment = "Bixio" # Puoi cambiare questo per testare altri appartamenti
    main(target_apartment) 