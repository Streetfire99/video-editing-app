# 🎬 Video Editing App

Applicazione Streamlit per elaborazione video e gestione appartamenti.

## 🚀 Deploy su Hugging Face Spaces

### Configurazione richiesta:
- **Runtime**: Streamlit
- **App file**: `app.py`
- **Python version**: 3.13

### Dipendenze:
- Tutte le dipendenze sono in `requirements.txt`
- Dipendenze di sistema in `packages.txt`

### Note:
- L'app richiede variabili d'ambiente per API keys
- Configurazione Streamlit in `.streamlit/config.toml`
- Upload file fino a 500MB supportato

## 📁 Struttura:
- `app.py` - File principale dell'applicazione
- `pages/` - Pagine dell'applicazione
- `Elaborazione/` - Moduli di elaborazione video
- `utils.py` - Funzioni di utilità
- `data_manager.py` - Gestione dati
- `drive_manager.py` - Gestione Google Drive
- `youtube_manager.py` - Gestione YouTube 