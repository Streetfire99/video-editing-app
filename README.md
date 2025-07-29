# Video Editing App

Un'applicazione Streamlit per l'elaborazione automatica di video con sottotitoli in italiano e inglese.

## Funzionalità

- Caricamento e elaborazione di video
- Trascrizione automatica dell'audio
- Generazione di sottotitoli in italiano e inglese
- Aggiunta di musica di sottofondo
- Upload su YouTube
- Gestione di appartamenti e tipologie video

## Setup

1. Clona il repository
2. Installa le dipendenze: `pip install -r requirements.txt`
3. Configura le variabili d'ambiente (vedi sezione Configurazione)
4. Esegui: `streamlit run app.py`

## Configurazione

### Variabili d'ambiente necessarie:

- `OPENAI_API_KEY`: Chiave API OpenAI per trascrizione e traduzione
- `GOOGLE_SHEETS_CREDENTIALS`: Credenziali Google Sheets (JSON)
- `YOUTUBE_CLIENT_SECRETS`: Credenziali YouTube API (JSON)

### Per Streamlit Cloud:

Configura le variabili d'ambiente nella sezione "Secrets" di Streamlit Cloud.

## Struttura del progetto

```
├── app.py                 # App principale
├── data_manager.py        # Gestione dati Google Sheets
├── youtube_upload.py      # Upload YouTube
├── Elaborazione/
│   ├── prova.py          # Logica di elaborazione video
│   └── audio.mp3         # Musica di sottofondo
└── requirements.txt       # Dipendenze Python
``` 