#!/usr/bin/env python3
"""
Test script per la registrazione vocale
Verifica che tutte le dipendenze siano installate correttamente
"""

import sys
import importlib

def test_imports():
    """Testa l'importazione di tutte le librerie necessarie"""
    print("🔍 Test importazioni librerie...")
    
    required_packages = [
        "streamlit",
        "openai", 
        "streamlit_audio_recorder",
        "tempfile",
        "json",
        "os"
    ]
    
    failed_imports = []
    
    for package in required_packages:
        try:
            if package == "streamlit_audio_recorder":
                # Test specifico per streamlit-audio-recorder
                import streamlit_audio_recorder
                print(f"✅ {package}: OK")
            else:
                importlib.import_module(package)
                print(f"✅ {package}: OK")
        except ImportError as e:
            print(f"❌ {package}: FAILED - {e}")
            failed_imports.append(package)
    
    return failed_imports

def test_openai_client():
    """Testa la creazione del client OpenAI"""
    print("\n🤖 Test client OpenAI...")
    
    try:
        from openai import OpenAI
        
        # Test senza API key (dovrebbe fallire ma non crashare)
        client = OpenAI(api_key="test")
        print("✅ Client OpenAI: OK")
        return True
    except Exception as e:
        print(f"❌ Client OpenAI: FAILED - {e}")
        return False

def test_audio_recorder():
    """Testa la funzionalità audio recorder"""
    print("\n🎤 Test audio recorder...")
    
    try:
        from streamlit_audio_recorder import audio_recorder
        print("✅ Audio Recorder: OK")
        return True
    except Exception as e:
        print(f"❌ Audio Recorder: FAILED - {e}")
        return False

def main():
    """Funzione principale di test"""
    print("🚀 Test Registrazione Vocale")
    print("=" * 40)
    
    # Test importazioni
    failed_imports = test_imports()
    
    # Test client OpenAI
    openai_ok = test_openai_client()
    
    # Test audio recorder
    audio_ok = test_audio_recorder()
    
    # Riepilogo
    print("\n" + "=" * 40)
    print("📊 RIEPILOGO TEST")
    print("=" * 40)
    
    if not failed_imports and openai_ok and audio_ok:
        print("🎉 TUTTI I TEST SUPERATI!")
        print("✅ L'app di registrazione vocale dovrebbe funzionare correttamente")
    else:
        print("⚠️ ALCUNI TEST FALLITI:")
        
        if failed_imports:
            print(f"❌ Importazioni fallite: {', '.join(failed_imports)}")
            print("💡 Installa con: pip install " + " ".join(failed_imports))
        
        if not openai_ok:
            print("❌ Client OpenAI non funzionante")
            print("💡 Verifica l'installazione di openai")
        
        if not audio_ok:
            print("❌ Audio recorder non funzionante")
            print("💡 Installa con: pip install streamlit-audio-recorder")
    
    print("\n🔧 Per installare le dipendenze mancanti:")
    print("pip install streamlit-audio-recorder openai")
    
    print("\n🚀 Per avviare l'app:")
    print("streamlit run app.py")

if __name__ == "__main__":
    main()
