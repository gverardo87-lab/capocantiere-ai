# server/app.py (Versione Stabile con Caricamento Centralizzato e Grafica Intatta)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
# --- MODIFICA CHIAVE: IMPORTIAMO LA CONFIGURAZIONE ALL'AVVIO ---
# Questa riga esegue il codice in core/config.py, che a sua volta
# esegue load_dotenv() e carica la chiave API dal file .env
import core.config
# ----------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db import db_manager
from core.schedule_db import schedule_db_manager
from tools.extractors import parse_monthly_timesheet_excel, ExcelParsingError

st.set_page_config(
    page_title="🏗️ CapoCantiere AI",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FUNZIONE DI CARICAMENTO DATI CENTRALIZZATA ---
def initialize_data():
    """
    Carica tutti i dati necessari dai DB e li salva in session_state.
    Viene eseguita solo una volta per sessione o dopo un upload/cancellazione.
    """
    if 'data_loaded' not in st.session_state:
        print("--- Inizializzazione dati per l'applicazione ---")
        presence_data = db_manager.get_all_presence_data()
        st.session_state.df_presence = pd.DataFrame(presence_data) if presence_data else pd.DataFrame()
        
        schedule_data = schedule_db_manager.get_schedule_data()
        st.session_state.df_schedule = pd.DataFrame(schedule_data) if schedule_data else pd.DataFrame()
        
        st.session_state.data_loaded = True

# Esegui la funzione di caricamento all'avvio dell'app
initialize_data()

# Controlla se una sotto-pagina ha richiesto un refresh
if st.session_state.pop('force_rerun', False):
    st.session_state.pop('data_loaded', None)
    initialize_data() # Forza il ricaricamento dei dati
    st.rerun()

# --- FUNZIONI DI GESTIONE FILE (nella Sidebar) ---
def process_uploaded_file():
    uploaded_file = st.session_state.get("file_uploader")
    if uploaded_file is None: return
    
    with st.spinner(f"Elaborazione di '{uploaded_file.name}'..."):
        try:
            records = parse_monthly_timesheet_excel(uploaded_file.getvalue())
            if records:
                db_manager.update_monthly_timesheet(records)
                st.session_state['force_rerun'] = True # Segnala che serve un refresh
        except Exception as e:
            st.error(f"Errore durante l'elaborazione del file: {e}")

def delete_all_data():
    db_manager.delete_all_presenze()
    st.session_state['force_rerun'] = True # Segnala che serve un refresh

# --- SIDEBAR (Grafica Intatta) ---
with st.sidebar:
    st.image("https://img.icons8.com/plasticine/100/000000/crane-hook.png", width=80)
    st.title("🏗️ CapoCantiere AI")
    st.markdown("---")
    
    with st.expander("➕ **Carica Rapportino Mensile**", expanded=True):
        st.file_uploader(
            "Seleziona un file Excel", type=["xlsx"],
            label_visibility="collapsed", key="file_uploader",
            on_change=process_uploaded_file
        )
    
    st.markdown("---")
    st.header("⚙️ Azioni di Sistema")
    if st.button("⚠️ Svuota Archivio Presenze", on_click=delete_all_data, type="secondary", use_container_width=True):
        pass

# --- PAGINA PRINCIPALE (Dashboard di Benvenuto - Grafica Intatta) ---
st.title("Benvenuto in CapoCantiere AI")
st.markdown("La tua **piattaforma centralizzata** per la gestione intelligente del cantiere navale.")
st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    with st.container(border=True):
        st.subheader("📊 Reportistica")
        st.markdown("Analizza le **presenze** del personale, filtra per attività e visualizza i totali di ore lavorate.")
        st.page_link("pages/01_📊_Reportistica.py", label="Vai al Consuntivo", icon="📊")
with col2:
    with st.container(border=True):
        st.subheader("📈 Cronoprogramma")
        st.markdown("Visualizza il **diagramma di Gantt** delle attività, monitora l'avanzamento e i KPI di progetto.")
        st.page_link("pages/04_📈_Cronoprogramma.py", label="Visualizza Gantt", icon="📈")
with col3:
    with st.container(border=True):
        st.subheader("⚙️ Analisi Workflow")
        st.markdown("Ottimizza l'**allocazione delle risorse**, identifica i colli di bottiglia e ricevi suggerimenti.")
        st.page_link("pages/05_⚙️_Workflow_Analysis.py", label="Analizza Workflow", icon="⚙️")
st.divider()

st.header("🤖 I Tuoi Assistenti AI")
col_chat, col_expert = st.columns(2)
with col_chat:
    with st.container(border=True):
        st.subheader("👨‍🔧 Esperto Tecnico")
        st.markdown("Poni domande complesse sulla **documentazione tecnica**. L'AI risponderà citando le fonti esatte.")
        st.page_link("pages/03_👨‍🔧_Esperto_Tecnico.py", label="Interroga l'Esperto", icon="👨‍🔧")
with col_expert:
    with st.container(border=True):
        st.subheader("📚 Esplora Documenti")
        st.markdown("Naviga e visualizza l'**archivio documentale** tecnico (PDF) del tuo esperto AI.")
        st.page_link("pages/06_📚_Document_Explorer.py", label="Esplora Archivio", icon="📚")