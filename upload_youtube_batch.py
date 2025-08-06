#!/usr/bin/env python3
"""
Script per caricare video elaborati su YouTube e aggiornare il CSV
"""

import os
import csv
import json
from datetime import datetime
from youtube_manager import upload_to_youtube

def upload_to_youtube_with_retry(video_path, video_name, max_retries=3):
    """Carica video su YouTube con retry automatico"""
    for attempt in range(max_retries):
        try:
            print(f"📺 Tentativo {attempt + 1}/{max_retries} - Caricamento su YouTube: {video_name}")
            
            youtube_url = upload_to_youtube(
                video_path=video_path,
                title=f"{video_name} Mulinetti - Video Tutorial",
                privacy_status="unlisted",
                description=f"Video tutorial su {video_name} Mulinetti",
                tags="Mulinetti, tutorial, video, guida"
            )
            
            if youtube_url:
                print(f"✅ YouTube: {youtube_url}")
                return youtube_url
            else:
                print("❌ Errore caricamento YouTube")
                
        except Exception as e:
            error_msg = str(e).lower()
            print(f"❌ Errore YouTube (tentativo {attempt + 1}): {e}")
            
            # Se è un errore di autenticazione, forza riautenticazione
            if any(keyword in error_msg for keyword in ['insufficient', 'permission', 'scope', 'token', 'authentication']):
                print("🔄 Errore di autenticazione rilevato, forzando nuova autenticazione...")
                
                # Rimuovi il token YouTube esistente
                youtube_token_file = "youtube_token.pickle"
                if os.path.exists(youtube_token_file):
                    try:
                        os.remove(youtube_token_file)
                        print("🗑️ Token YouTube rimosso")
                    except:
                        pass
                
                # Aspetta un momento prima del prossimo tentativo
                import time
                time.sleep(2)
                
                if attempt < max_retries - 1:
                    print("🔄 Riprovo con nuova autenticazione...")
                    continue
                else:
                    print("❌ Impossibile caricare su YouTube dopo tutti i tentativi")
                    return None
            
            # Per altri errori, aspetta prima di riprovare
            if attempt < max_retries - 1:
                print(f"⏳ Attendo 5 secondi prima del prossimo tentativo...")
                import time
                time.sleep(5)
            else:
                print("❌ Impossibile caricare su YouTube dopo tutti i tentativi")
                return None
    
    return None

def update_csv_with_youtube_links(csv_file):
    """Aggiorna il CSV con i link di YouTube preservando i dati esistenti"""
    try:
        # Leggi il CSV esistente
        rows = []
        with open(csv_file, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            rows = list(reader)
        
        print(f"📊 Trovati {len(rows)} video nel CSV")
        
        # Conta quanti video hanno bisogno di upload
        videos_to_upload = [row for row in rows if not row.get('youtube_url') or not row['youtube_url'].strip()]
        print(f"📺 Video da caricare: {len(videos_to_upload)}")
        
        if not videos_to_upload:
            print("✅ Tutti i video hanno già un link YouTube!")
            return
        
        # Processa solo i video che non hanno già un link YouTube
        for i, row in enumerate(videos_to_upload, 1):
            video_name = row['video_name']
            processed_path = row['processed_path']
            
            print(f"\n🎬 Elaborazione {i}/{len(videos_to_upload)}: {video_name}")
            print(f"📁 File: {processed_path}")
            
            # Verifica che il file esista
            if not os.path.exists(processed_path):
                print(f"❌ File non trovato: {processed_path}")
                continue
            
            # Carica su YouTube con retry
            youtube_url = upload_to_youtube_with_retry(processed_path, video_name)
            
            if youtube_url:
                # Trova e aggiorna la riga corrispondente nel CSV originale
                for original_row in rows:
                    if original_row['video_name'] == video_name:
                        original_row['youtube_url'] = youtube_url
                        break
                print(f"✅ Aggiornato con link YouTube: {youtube_url}")
            else:
                print(f"❌ Fallito caricamento YouTube per {video_name}")
        
        # Salva il CSV aggiornato solo se ci sono stati cambiamenti
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as file:
                # Usa tutti i campi presenti nel CSV originale
                fieldnames = list(rows[0].keys()) if rows else []
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"✅ CSV aggiornato: {csv_file}")
            
        except Exception as e:
            print(f"⚠️  Attenzione: Errore nel salvataggio CSV ({e}), ma i link sono stati caricati con successo")
            print("📝 I link YouTube sono stati caricati ma non salvati nel CSV")
        
        # Mostra statistiche
        success_count = sum(1 for row in rows if row.get('youtube_url') and row['youtube_url'].strip())
        total_count = len(rows)
        print(f"📊 Statistiche:")
        print(f"   ✅ Successi YouTube: {success_count}/{total_count}")
        print(f"   ❌ Fallimenti: {total_count - success_count}/{total_count}")
        
    except Exception as e:
        print(f"❌ Errore aggiornamento CSV: {e}")
        print("📝 I dati esistenti nel CSV sono stati preservati")

def main():
    """Funzione principale"""
    csv_file = "processed_videos_Video_Mulinetti.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ File CSV non trovato: {csv_file}")
        return
    
    print("🎬 CARICAMENTO VIDEO SU YOUTUBE")
    print("=" * 50)
    print(f"📊 File CSV: {csv_file}")
    
    # Verifica che i file video esistano
    with open(csv_file, 'r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        
        missing_files = []
        for row in rows:
            if not os.path.exists(row['processed_path']):
                missing_files.append(row['processed_path'])
        
        if missing_files:
            print("⚠️  File video mancanti:")
            for file in missing_files:
                print(f"   ❌ {file}")
            print("\nAssicurati che tutti i file video esistano prima di procedere.")
            return
    
    print("✅ Tutti i file video trovati")
    
    # Chiedi conferma
    response = input("\nProcedere con il caricamento su YouTube? (y/n): ")
    if response.lower() != 'y':
        print("❌ Operazione annullata")
        return
    
    # Aggiorna il CSV con i link di YouTube
    update_csv_with_youtube_links(csv_file)

if __name__ == "__main__":
    main() 