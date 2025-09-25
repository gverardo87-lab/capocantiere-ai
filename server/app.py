# server/app.py (versione potenziata e strutturata)

from __future__ import annotations
import os
import sys
import streamlit as st

# Aggiungiamo la root del progetto al path per trovare i nostri moduli
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importiamo i nostri motori: il db_manager e l'estrattore Excel
from core.db import db_manager
from tools.extractors import parse_monthly_timesheet_excel, ExcelParsingError

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="🏗️ CapoCantiere AI - Home",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded" # Sidebar aperta di default
)

def process_uploaded_file():
    """
    Funzione centrale che gestisce il file Excel caricato.
    Chiama l'estrattore, poi il gestore del DB, e fornisce feedback all'utente.
    (LOGICA INVARIATA)
    """
    uploaded_file = st.session_state.get("file_uploader")
    if uploaded_file is None:
        return

    file_bytes = uploaded_file.getvalue()
    filename = uploaded_file.name

    with st.spinner(f"Elaborazione di '{filename}'..."):
        try:
            records = parse_monthly_timesheet_excel(file_bytes)
            
            if not records:
                st.warning("Il file è stato letto, ma non sono state trovate ore lavorate da importare.")
                return

            db_manager.update_monthly_timesheet(records)
            
            st.success(f"Rapportino '{filename}' importato! {len(records)} record di presenze sono stati salvati.")
            st.info("Vai alla pagina 'Reportistica' per visualizzare i dati aggiornati.")
        
        except ExcelParsingError as e:
            st.error(f"❌ Errore nel formato del file Excel: {e}")
        except Exception as e:
            st.error(f"Si è verificato un errore imprevisto: {e}")

def delete_all_data():
    """ 
    Funzione per cancellare tutti i dati delle presenze.
    (LOGICA INVARIATA)
    """
    try:
        db_manager.delete_all_presenze()
        st.success("Tutti i dati delle presenze sono stati cancellati.")
    except Exception as e:
        st.error(f"Errore durante la cancellazione dei dati: {e}")

# --- SIDEBAR (Potenziata) ---
with st.sidebar:
    # Puoi personalizzare l'URL dell'icona se preferisci
    st.image("https://img.icons8.com/plasticine/100/000000/crane-hook.png", width=80)
    st.title("🏗️ CapoCantiere AI")
    st.markdown("---")
    
    with st.expander("➕ **Carica Rapportino Mensile**", expanded=True):
        st.file_uploader(
            "Seleziona un file Excel",
            type=["xlsx"],
            label_visibility="collapsed",
            key="file_uploader",
            on_change=process_uploaded_file,
            help="Carica il file Excel con le presenze del mese."
        )
    
    st.markdown("---")
    st.header("⚙️ Azioni di Sistema")
    if st.button("⚠️ Svuota Archivio Presenze", type="secondary", use_container_width=True, help="ATTENZIONE: Cancella tutti i dati!"):
        delete_all_data()
        st.rerun()

# --- PAGINA PRINCIPALE (Dashboard di Benvenuto) ---
st.title("Benvenuto in CapoCantiere AI")
st.markdown("La tua **piattaforma centralizzata** per la gestione intelligente del cantiere navale.")
st.divider()

# --- CARD RIASSUNTIVE ---
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("📊 Reportistica")
        st.markdown("Analizza le **presenze** del personale, filtra per operaio e visualizza i totali di ore lavorate, straordinari e assenze.")
        st.page_link("pages/01_📊_Reportistica.py", label="Vai ai Report", icon="📊")

with col2:
    with st.container(border=True):
        st.subheader("📈 Cronoprogramma")
        st.markdown("Visualizza il **diagramma di Gantt** delle attività, monitora l'avanzamento e filtra per intervalli di date specifiche.")
        st.page_link("pages/04_📈_Cronoprogramma.py", label="Visualizza Gantt", icon="📈")

with col3:
    with st.container(border=True):
        st.subheader("⚙️ Analisi Workflow")
        st.markdown("Ottimizza l'**allocazione delle risorse**, identifica i colli di bottiglia e ricevi suggerimenti basati sui workflow.")
        st.page_link("pages/05_⚙️_Workflow_Analysis.py", label="Analizza Workflow", icon="⚙️")

st.divider()

# --- SEZIONE ASSISTENTI AI ---
st.header("🤖 I Tuoi Assistenti AI")
col_chat, col_expert = st.columns(2)

with col_chat:
    with st.container(border=True):
        st.subheader("👨‍🔧 Esperto Tecnico")
        st.markdown("Poni domande complesse sulla **documentazione tecnica**. L'AI risponderà citando le fonti esatte dai manuali PDF.")
        st.page_link("pages/03_👨‍🔧_Esperto_Tecnico.py", label="Interroga l'Esperto", icon="👨‍🔧")

with col_expert:
    with st.container(border=True):
        st.subheader("📚 Esplora Documenti")
        st.markdown("Naviga e visualizza l'**archivio documentale** tecnico (PDF) che costituisce la base di conoscenza del tuo esperto AI.")
        st.page_link("pages/06_📚_Document_Explorer.py", label="Esplora Archivio", icon="📚")


# --- NUOVA SEZIONE PER L'ESECUZIONE (per pyproject.toml) ---
def main():
    """
    Funzione principale per servire come "entry point" per il comando 
    definito in pyproject.toml.
    """
    pass

if __name__ == "__main__":
    # Questo blocco viene eseguito solo se lanci il file direttamente.
    # L'avvio corretto avviene tramite `streamlit run server/app.py`.
    print("Per avviare l'applicazione, esegui dal terminale:")
    print("streamlit run server/app.py")