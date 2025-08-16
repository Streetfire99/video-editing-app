from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# The document ID from the URL
DOCUMENT_ID = '1OIzZ_E83EH1e3xB5W6ztztm6n05VFYE7HXBiao1q2PU'

# The scopes required for accessing Google Docs
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

def get_doc_content():
    # Create credentials from service account file
    credentials = service_account.Credentials.from_service_account_file(
        'service_account_key.json', scopes=SCOPES)

    try:
        # Build the Docs API service
        docs_service = build('docs', 'v1', credentials=credentials)
        
        # Get the document content
        doc = docs_service.documents().get(documentId=DOCUMENT_ID).execute()
        
        print("\n=== Document Content ===")
        
        # Extract and print the content with better formatting
        if 'body' in doc and 'content' in doc['body']:
            content = doc['body']['content']
            current_section = ""
            
            for element in content:
                if 'paragraph' in element:
                    # Check if this is a heading
                    if 'paragraphStyle' in element['paragraph']:
                        style = element['paragraph']['paragraphStyle']
                        if 'namedStyleType' in style:
                            if style['namedStyleType'].startswith('HEADING'):
                                print("\n" + "="*50)
                                current_section = ""
                                for para_element in element['paragraph']['elements']:
                                    if 'textRun' in para_element:
                                        current_section += para_element['textRun']['content']
                                print(f"\n{current_section}")
                                print("="*50 + "\n")
                                continue
                    
                    # Regular paragraph
                    paragraph_text = ""
                    for para_element in element['paragraph']['elements']:
                        if 'textRun' in para_element:
                            paragraph_text += para_element['textRun']['content']
                    if paragraph_text.strip():
                        print(paragraph_text)
        else:
            print("No content found in the document")
            
    except HttpError as error:
        print(f'Error reading document: {error}')
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    get_doc_content() 