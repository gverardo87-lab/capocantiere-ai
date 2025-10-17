# server/app.py (Versione Pulita - Solo CRM)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
# --- MODIFICA CHIAVE: IMPORTIAMO LA CONFIGURAZIONE ALL'AVVIO ---
import core.config
# ----------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- MODIFICA CHIAVE: Importiamo solo i gestori DB che usiamo ---
from core.schedule_db import schedule_db_manager
# from core.db import db_manager # RIMOSSO - OBSOLETO
# from tools.extractors import parse_monthly_timesheet_excel, ExcelParsingError # RIMOSSO - OBSOLETO

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
    Viene eseguita solo una volta per sessione o dopo un refresh.
    """
    if 'data_loaded' not in st.session_state:
        print("--- Inizializzazione dati per l'applicazione ---")
        
        # --- RIMOSSO CARICAMENTO VECCHIO DB ---
        # presence_data = db_manager.get_all_presence_data()
        # st.session_state.df_presence = pd.DataFrame(presence_data) if presence_data else pd.DataFrame()
        
        # Manteniamo il caricamento del cronoprogramma
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

# --- FUNZIONI DI GESTIONE FILE (RIMOSSE) ---
# Le vecchie funzioni 'process_uploaded_file' e 'delete_all_data' 
# sono state rimosse perché 'core/db.py' è obsoleto.

# --- SIDEBAR (Grafica Pulita) ---
with st.sidebar:
    st.image("https://img.icons8.com/plasticine/100/000000/crane-hook.png", width=80)
    st.title("🏗️ CapoCantiere AI")
    st.markdown("---")
    
    # --- RIMOSSO EXPANDER DI UPLOAD E BOTTONE CANCELLA ---
    # L'uploader Excel e il bottone "Svuota Archivio"
    # sono stati rimossi.
    
    st.markdown("Benvenuto nel sistema di gestione CRM.")
    st.page_link("pages/10_📅_Pianificazione_Turni.py", label="Pianifica Turni", icon="📅")
    st.page_link("pages/13_✏️_Control_Room_Ore.py", label="Control Room Ore", icon="✏️")
    
    st.markdown("---")
    st.header("Configurazione")
    st.page_link("pages/11_👨‍💼_Anagrafica.py", label="Gestisci Anagrafica", icon="👨‍💼")
    st.page_link("pages/12_👥_Gestione_Squadre.py", label="Gestisci Squadre", icon="👥")


# --- PAGINA PRINCIPALE (Dashboard di Benvenuto) ---
st.title("Benvenuto in CapoCantiere AI")
st.markdown("La tua **piattaforma centralizzata** per la gestione intelligente del cantiere navale.")
st.divider()

# --- KPI E ACCESSI RAPIDI AL CRM ---
st.header("Controllo Manodopera (CRM)")
col_crm1, col_crm2, col_crm3 = st.columns(3)
with col_crm1:
    with st.container(border=True):
        st.subheader("📅 Pianificazione")
        st.markdown("Assegna **squadre** ai turni e alle attività in pochi click.")
        st.page_link("pages/10_📅_Pianificazione_Turni.py", label="Vai alla Pianificazione", icon="📅")
with col_crm2:
    with st.container(border=True):
        st.subheader("✏️ Control Room")
        st.markdown("Gestisci **eccezioni**, interruzioni e modifica i singoli orari.")
        st.page_link("pages/13_✏️_Control_Room_Ore.py", label="Vai alla Control Room", icon="✏️")
with col_crm3:
    with st.container(border=True):
        st.subheader("📊 Consuntivo")
        st.markdown("Analizza le **ore totali** per dipendente, attività e commessa.")
        st.page_link("pages/01_📊_Reportistica.py", label="Vai al Consuntivo", icon="📊")

st.divider()

st.header("Strumenti di Progetto e AI")
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.subheader("📈 Cronoprogramma")
        st.markdown("Visualizza il **diagramma di Gantt** delle attività e monitora l'avanzamento.")
        st.page_link("pages/04_📈_Cronoprogramma.py", label="Visualizza Gantt", icon="📈")
with col2:
    with st.container(border=True):
        st.subheader("⚙️ Analisi Workflow")
        st.markdown("Ottimizza l'**allocazione delle risorse** e identifica i colli di bottiglia.")
        st.page_link("pages/05_⚙️_Workflow_Analysis.py", label="Analizza Workflow", icon="⚙️")

col_chat, col_expert = st.columns(2)
with col_chat:
    with st.container(border=True):
        st.subheader("👨‍🔧 Esperto Tecnico")
        st.markdown("Poni domande complesse sulla **documentazione tecnica**.")
        st.page_link("pages/03_👨‍🔧_Esperto_Tecnico.py", label="Interroga l'Esperto", icon="👨‍🔧")
with col_expert:
    with st.container(border=True):
        st.subheader("📚 Esplora Documenti")
        st.markdown("Naviga e visualizza l'**archivio documentale** tecnico.")
        st.page_link("pages/06_📚_Document_Explorer.py", label="Esplora Archivio", icon="📚")