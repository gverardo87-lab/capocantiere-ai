# Debug Script per trovare dove si blocca l'inizializzazione
# Salva questo come debug_init.py e usa per testare i moduli uno alla volta

import sys
import time
import traceback

def test_import_with_timing(module_name, from_module=None):
    """Testa l'import di un modulo con timing"""
    print(f"🔄 Testando import: {module_name}...")
    start_time = time.time()
    
    try:
        if from_module:
            exec(f"from {from_module} import {module_name}")
        else:
            exec(f"import {module_name}")
        
        elapsed = time.time() - start_time
        print(f"✅ {module_name} importato in {elapsed:.2f}s")
        return True
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Errore importing {module_name} dopo {elapsed:.2f}s: {e}")
        traceback.print_exc()
        return False

def debug_capocantiere_initialization():
    """Debug dell'inizializzazione dell'app Capocantiere"""
    print("=" * 60)
    print("🕵️ DEBUG INIZIALIZZAZIONE CAPOCANTIERE-AI")
    print("=" * 60)
    
    # Test import base Python
    print("\n📦 TESTING PYTHON BASE MODULES...")
    basic_modules = ['os', 'sys', 'datetime', 'pathlib']
    for module in basic_modules:
        test_import_with_timing(module)
    
    # Test import Streamlit
    print("\n🎨 TESTING STREAMLIT...")
    test_import_with_timing('streamlit')
    
    # Test import data science
    print("\n📊 TESTING DATA SCIENCE MODULES...")
    ds_modules = ['pandas', 'numpy']
    for module in ds_modules:
        test_import_with_timing(module)
    
    # Test import Plotly
    print("\n📈 TESTING PLOTLY...")
    plotly_modules = ['plotly.graph_objects', 'plotly.subplots', 'plotly.express']
    for module in plotly_modules:
        test_import_with_timing(module)
    
    # Test path del progetto
    print("\n📁 TESTING PROJECT PATHS...")
    print(f"Current working directory: {os.getcwd()}")
    
    # Test import moduli custom
    print("\n🏗️ TESTING CUSTOM MODULES...")
    
    # Testa il path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        print(f"✅ Added project root to path: {project_root}")
    
    # Test import database modules
    custom_modules = [
        ('schedule_db_manager', 'core.schedule_db'),
        ('parse_schedule_excel', 'tools.schedule_extractor')
    ]
    
    for module_name, from_module in custom_modules:
        test_import_with_timing(module_name, from_module)
    
    # Test database connections
    print("\n🗄️ TESTING DATABASE CONNECTIONS...")
    try:
        print("🔄 Testing database connection...")
        start_time = time.time()
        
        from core.schedule_db import schedule_db_manager
        
        # Test basic database operation
        test_data = schedule_db_manager.get_schedule()
        elapsed = time.time() - start_time
        
        print(f"✅ Database connection OK in {elapsed:.2f}s")
        print(f"📊 Records in database: {len(test_data) if test_data is not None else 0}")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Database connection failed after {elapsed:.2f}s: {e}")
        traceback.print_exc()
    
    # Test session state initialization
    print("\n🧠 TESTING STREAMLIT SESSION STATE...")
    try:
        import streamlit as st
        
        # Simula inizializzazione session state
        print("🔄 Testing session state initialization...")
        
        if 'test_var' not in st.session_state:
            st.session_state.test_var = "test"
            
        print("✅ Session state working")
        
    except Exception as e:
        print(f"❌ Session state error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    import os
    
    debug_capocantiere_initialization()
    
    print("\n" + "=" * 60)
    print("🎯 DEBUG COMPLETATO")
    print("=" * 60)
    print("\n💡 SUGGERIMENTI:")
    print("1. Se un modulo impiega >5s, potrebbe essere lì il problema")
    print("2. Se database connection fallisce, controlla i file di database")
    print("3. Se session state fallisce, controlla se Streamlit è installato correttamente")
    print("4. Controlla i file core/schedule_db.py e tools/schedule_extractor.py")
    
    # Chiedi all'utente cosa fare dopo
    print("\n🚀 PROSSIMI PASSI:")
    print("1. Esegui questo script: python debug_init.py")
    print("2. Identifica dove si blocca")
    print("3. Controlla i file segnalati come problematici")