# debug_init.py
import sys
import os
import traceback
import pandas as pd

# Aggiungiamo la root del progetto al path per importare i moduli custom
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

def run_debug():
    print("="*50)
    print("🕵️  INIZIO DEBUG TATTICO CAPOCANTIERE AI 🕵️")
    print("="*50)

    # --- Test 1: Import dei moduli principali ---
    try:
        print("\n[TEST 1/4] Importazione moduli in corso...")
        from core.workflow_engine import workflow_engine, analyze_resource_allocation
        from core.db import db_manager
        from core.schedule_db import schedule_db_manager
        print("✅ [SUCCESS] Tutti i moduli principali sono stati importati correttamente.")
    except Exception:
        print(f"❌ [FALLITO] Errore CRITICO durante l'importazione dei moduli. Il problema è in uno dei file .py dentro la cartella 'core'.")
        traceback.print_exc()
        return

    # --- Test 2: Caricamento dati di esempio ---
    print("\n[TEST 2/4] Caricamento dati dai database...")
    try:
        presence_data = db_manager.get_all_presence_data()
        schedule_data = schedule_db_manager.get_schedule_data()
        df_presence = pd.DataFrame(presence_data)
        df_schedule = pd.DataFrame(schedule_data)
        print(f"✅ [SUCCESS] Dati caricati. {len(df_presence)} record di presenza, {len(df_schedule)} attività nel cronoprogramma.")
        if df_presence.empty or df_schedule.empty:
            print("⚠️  ATTENZIONE: Uno dei due database è vuoto. I test successivi potrebbero essere saltati.")
    except Exception:
        print(f"❌ [FALLITO] Errore durante il caricamento dei dati. Controlla i file 'capocantiere.db' e 'schedule.db' nella cartella 'data'.")
        traceback.print_exc()
        return

    # --- Test 3: Esecuzione dell'analisi delle risorse ---
    print("\n[TEST 3/4] Esecuzione della funzione 'analyze_resource_allocation'...")
    try:
        if presence_data and schedule_data:
            analysis_result = analyze_resource_allocation(presence_data, schedule_data)
            print("✅ [SUCCESS] L'analisi delle risorse ha funzionato correttamente.")
        else:
            print("⏩ [SALTATO] Test saltato perché i dati sono insufficienti.")
    except Exception:
        print(f"❌ [FALLITO] Errore CRITICO in 'analyze_resource_allocation' (file: core/workflow_engine.py).")
        traceback.print_exc()
        return

    # --- Test 4: Esecuzione dei suggerimenti di ottimizzazione ---
    print("\n[TEST 4/4] Esecuzione della funzione 'suggest_optimal_schedule'...")
    try:
        if presence_data and schedule_data:
            suggestions = workflow_engine.suggest_optimal_schedule(schedule_data, presence_data)
            print(f"✅ [SUCCESS] La generazione di suggerimenti ha funzionato. Trovati {len(suggestions)} suggerimenti.")
        else:
            print("⏩ [SALTATO] Test saltato perché i dati sono insufficienti.")
    except Exception:
        print(f"❌ [FALLITO] Errore CRITICO in 'suggest_optimal_schedule' (file: core/workflow_engine.py).")
        traceback.print_exc()
        return

    print("\n" + "="*50)
    print("🎉 DEBUG COMPLETATO 🎉")
    print("Tutte le funzioni principali del motore di workflow sembrano funzionare.")
    print("Se lo script arriva fin qui, l'errore non è nella logica ma nel codice della pagina Streamlit (05_...py).")
    print("="*50)

if __name__ == "__main__":
    run_debug()