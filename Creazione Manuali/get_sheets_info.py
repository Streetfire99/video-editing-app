from google.oauth2 import service_account
from googleapiclient.discovery import build

# The ID of the spreadsheet
SPREADSHEET_ID = '1Jd0FpZKboNYsr2lX502yVFq2BBHqy8lZmiO1GOhNaY0'

# The scopes required for accessing Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def get_sheets_info():
    # Create credentials from service account file
    credentials = service_account.Credentials.from_service_account_file(
        'service_account_key.json', scopes=SCOPES)

    # Build the Sheets API service
    service = build('sheets', 'v4', credentials=credentials)

    try:
        # Get spreadsheet metadata
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        
        print("\n=== Spreadsheet Information ===")
        print(f"Title: {spreadsheet['properties']['title']}")
        print("\n=== Sheets ===")
        
        # Get information about each sheet
        for sheet in spreadsheet['sheets']:
            sheet_title = sheet['properties']['title']
            sheet_id = sheet['properties']['sheetId']
            
            # Get the first row (headers) of each sheet
            result = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_title}!1:1"
            ).execute()
            
            headers = result.get('values', [[]])[0] if result.get('values') else []
            
            print(f"\nSheet: {sheet_title} (ID: {sheet_id})")
            print("Headers:", headers)
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    get_sheets_info() 