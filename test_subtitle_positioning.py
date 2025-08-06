#!/usr/bin/env python3
"""
Script di test per confrontare diversi metodi di posizionamento sottotitoli
"""

import os
import sys
import tempfile
from datetime import datetime

# Aggiungi il percorso per importare le funzioni
sys.path.append('Elaborazione')
from Elaborazione.prova import (
    test_subtitle_positioning_methods,
    create_dual_ass_with_custom_height,
    add_subtitles_with_fixed_position,
    modify_subtitle_height,
    get_video_info
)

def test_subtitle_methods():
    """Testa i diversi metodi di posizionamento sottotitoli"""
    print("🧪 TEST: Confronto metodi posizionamento sottotitoli")
    print("=" * 60)
    
    # Crea segmenti di test
    test_segments = [
        {
            'start': 0.0,
            'end': 3.0,
            'text': 'Apri lo sportello',
            'text_en': 'Open the door'
        },
        {
            'start': 3.0,
            'end': 6.0,
            'text': 'Inserisci il bucato',
            'text_en': 'Insert the laundry'
        },
        {
            'start': 6.0,
            'end': 9.0,
            'text': 'Aggiungi il detersivo',
            'text_en': 'Add the detergent'
        },
        {
            'start': 9.0,
            'end': 12.0,
            'text': 'Seleziona il programma',
            'text_en': 'Select the program'
        }
    ]
    
    # Cerca un video di test
    test_video = None
    possible_videos = [
        "output_lv_0_20250801134938.mp4",
        "output_lv_0_20250801135324.mp4", 
        "output_lv_0_20250801135450.mp4"
    ]
    
    for video in possible_videos:
        if os.path.exists(video):
            test_video = video
            break
    
    if not test_video:
        print("❌ Nessun video di test trovato")
        return
    
    print(f"📹 Video di test: {test_video}")
    
    # Crea directory di test
    test_dir = "test_subtitles"
    os.makedirs(test_dir, exist_ok=True)
    
    # Test 1: Confronto metodi
    print("\n🔧 TEST 1: Confronto metodi di posizionamento")
    try:
        results = test_subtitle_positioning_methods(test_video, test_segments, test_dir)
        print("✅ Test 1 completato")
    except Exception as e:
        print(f"❌ Test 1 fallito: {e}")
    
    # Test 2: Altezza personalizzabile
    print("\n🔧 TEST 2: Altezza personalizzabile")
    try:
        ass_file_it = os.path.join(test_dir, "custom_italian.ass")
        ass_file_en = os.path.join(test_dir, "custom_english.ass")
        output_video = os.path.join(test_dir, "custom_subtitles.mp4")
        
        # Ottieni dimensioni video
        video_info = get_video_info(test_video)
        video_width = video_info['width'] if video_info else 478
        video_height = video_info['height'] if video_info else 850
        
        # Crea file ASS con altezza personalizzabile
        create_dual_ass_with_custom_height(
            test_segments, 
            ass_file_it, 
            ass_file_en, 
            video_width, 
            video_height, 
            italian_height=120, 
            english_height=60, 
            font_size=16
        )
        
        # Aggiungi sottotitoli
        add_subtitles_with_fixed_position(test_video, ass_file_it, ass_file_en, output_video)
        print("✅ Test 2 completato")
        
        # Test 3: Modifica altezza in tempo reale
        print("\n🔧 TEST 3: Modifica altezza in tempo reale")
        
        # Modifica altezza italiano
        modify_subtitle_height(ass_file_it, 150, 18)  # Più alto e più grande
        modify_subtitle_height(ass_file_en, 90, 18)   # Più alto e più grande
        
        output_video_modified = os.path.join(test_dir, "modified_subtitles.mp4")
        add_subtitles_with_fixed_position(test_video, ass_file_it, ass_file_en, output_video_modified)
        print("✅ Test 3 completato")
        
    except Exception as e:
        print(f"❌ Test 2/3 fallito: {e}")
    
    print("\n📊 RISULTATI TEST:")
    print(f"📁 File di test in: {test_dir}")
    print("🎯 Controlla i video generati per confrontare i metodi")
    print("🔧 Il nuovo metodo ASS dovrebbe avere posizione più stabile")

if __name__ == "__main__":
    test_subtitle_methods() 