# server/app.py (Nuova Versione Home Page)

from __future__ import annotations
import os
from datetime import date
import pandas as pd
import streamlit as st
import sys

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db import db_manager
from tools.extractors import read_text_and_kind, file_sha256, parse_timesheet_csv

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="🏗️ CapoCantiere AI - Home",
    page_icon="🏗️",
    layout="wide",
)

# Le funzioni di callback e di refresh rimangono qui perché la sidebar è globale
def process_uploaded_file():
    uploaded_file = st.session_state.get("file_uploader")
    if uploaded_file is None: return
    file_bytes = uploaded_file.getvalue()
    filename = uploaded_file.name
    sha256_hash = file_sha256(file_bytes)
    with st.spinner(f"Analisi di '{filename}'..."):
        text, kind = read_text_and_kind(filename, file_bytes)
        document_id = db_manager.upsert_document(
            kind=kind.replace("_CSV", ""), filename=filename, content_type=uploaded_file.type,
            size_bytes=uploaded_file.size, sha256=sha256_hash
        )
        if kind == "RAPPORTO_CSV":
            try:
                rows, _ = parse_timesheet_csv(file_bytes)
                db_manager.replace_timesheet_rows(document_id, rows)
                st.success(f"Rapportino '{filename}' importato!")
            except Exception as e:
                st.error(f"Errore nel CSV: {e}")

# --- SIDEBAR (Globale per tutta l'app) ---
with st.sidebar:
    st.title("🏗️ CapoCantiere AI")
    with st.expander("➕ Carica Rapportini", expanded=True):
        st.file_uploader(
            "Seleziona un rapportino CSV", type=["csv"],
            label_visibility="collapsed", key="file_uploader",
            on_change=process_uploaded_file
        )
    st.divider()
    with st.expander("🗂️ Archivio Documenti Recenti"):
        st.dataframe(pd.DataFrame(db_manager.list_documents(limit=10)), use_container_width=True, hide_index=True)
    st.divider()
    st.header("⚙️ Azioni Rapide")
    if st.button("⚠️ Svuota Memoria Dati", type="primary", use_container_width=True, help="ATTENZIONE: Cancella tutti i documenti e i dati caricati!"):
        with st.spinner("Cancellazione di tutti i dati in corso..."):
            db_manager.delete_all_data()
        st.session_state.clear()
        st.rerun()

# --- PAGINA PRINCIPALE (Home Page) ---
st.title("Benvenuto in CapoCantiere AI")
st.markdown(
    """
    Questa è la tua applicazione per la gestione semplificata del personale e dei lavori di cantiere.

    **Usa il menu a sinistra per navigare tra le sezioni:**

    - **`Reportistica`**: Visualizza e filtra i dati dei rapportini.
    - **`Assistente Dati`**: Chatta con l'AI per analizzare i dati dei rapportini.
    - **`Esperto Tecnico`**: Chatta con l'esperto AI che ha studiato la documentazione tecnica.
    """
)
st.info("Per iniziare, carica un rapportino CSV o naviga in una delle pagine qui a fianco.")