# server/app.py
from __future__ import annotations
import os
import sys
import streamlit as st

# Aggiungiamo la root del progetto al path per trovare i nostri moduli
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importiamo i nostri motori: il db_manager e l'estrattore Excel
from core.db import db_manager
from tools.extractors import parse_monthly_timesheet_excel, ExcelParsingError

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="🏗️ CapoCantiere AI - Home",
    page_icon="🏗️",
    layout="wide",
)

def process_uploaded_file():
    """
    Funzione centrale che gestisce il file Excel caricato.
    Chiama l'estrattore, poi il gestore del DB, e fornisce feedback all'utente.
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
    """ Funzione per cancellare tutti i dati delle presenze. """
    # Nota: questa funzione ora dovrà chiamare un metodo specifico in db.py
    # che aggiungeremo se non presente, es: db_manager.delete_all_presenze()
    try:
        # Assumiamo di avere una funzione db_manager.delete_all_presenze()
        db_manager.delete_all_presenze()
        st.success("Tutti i dati delle presenze sono stati cancellati.")
    except Exception as e:
        st.error(f"Errore durante la cancellazione dei dati: {e}")


# --- SIDEBAR (Globale e semplificata) ---
with st.sidebar:
    st.title("🏗️ CapoCantiere AI")
    
    with st.expander("➕ Carica Rapportino Mensile", expanded=True):
        st.file_uploader(
            "Seleziona un file Excel",
            type=["xlsx"],
            label_visibility="collapsed",
            key="file_uploader",
            on_change=process_uploaded_file,
            help="Carica il file Excel con le presenze del mese. Il sistema leggerà il mese e l'anno dalla prima riga."
        )
    
    st.divider()
    st.header("⚙️ Azioni Rapide")
    if st.button("⚠️ Svuota Archivio Presenze", type="primary", use_container_width=True, help="ATTENZIONE: Cancella tutti i dati delle presenze caricate!"):
        delete_all_data()
        st.rerun()

# --- PAGINA PRINCIPALE ---
st.title("Benvenuto in CapoCantiere AI")
st.markdown(
    """
    La tua applicazione per la gestione semplificata delle presenze in cantiere.
    
    **Come funziona:**

    1.  **Carica i Dati**: Usa il pannello a sinistra per caricare il tuo
        `Rapportino Mensile.xlsx`.
        
    2.  **Visualizza i Risultati**: Vai alla pagina **`Reportistica`** dal menu per visualizzare e analizzare i dati che hai caricato.
    """
)
st.info("Per iniziare, carica il tuo rapportino mensile usando il menu a sinistra.")