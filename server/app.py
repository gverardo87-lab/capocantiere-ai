from __future__ import annotations

import os
import sys
import pandas as pd
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db import db_manager
from tools.extractors import (
    read_text_and_kind,
    file_sha256,
    parse_timesheet_csv,
    extract_fields_with_ai
)

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="🏗️ CapoCantiere AI",
    page_icon="🏗️",
    layout="wide",
)

# --- FUNZIONE DI CALLBACK PER LA GESTIONE DELL'UPLOAD ---
def process_uploaded_file():
    """
    Questa funzione viene chiamata automaticamente da Streamlit ogni volta
    che un nuovo file viene caricato nel file_uploader.
    """
    uploaded_file = st.session_state.get("file_uploader")
    if uploaded_file is None:
        return

    file_bytes = uploaded_file.getvalue()
    filename = uploaded_file.name
    sha256_hash = file_sha256(file_bytes)

    with st.spinner(f"Analisi di '{filename}'..."):
        text, kind = read_text_and_kind(filename, file_bytes)
        document_id = db_manager.upsert_document(
            kind=kind.replace("_CSV", ""), filename=filename, content_type=uploaded_file.type,
            size_bytes=uploaded_file.size, sha256=sha256_hash
        )

        fields = []
        if kind == "RAPPORTO_CSV":
            try:
                rows, summary = parse_timesheet_csv(file_bytes)
                fields.extend(summary)
                db_manager.replace_timesheet_rows(document_id, rows)
                st.success(f"Rapportino '{filename}' importato con successo!")
            except Exception as e:
                st.error(f"Errore nell'elaborazione del CSV: {e}")
        else:
            st.info(f"Documento classificato come '{kind}'. Avvio estrazione con AI...")
            ai_fields = extract_fields_with_ai(text, kind)
            if ai_fields:
                fields.extend(ai_fields)
                st.success(f"Estrazione AI completata! Trovati {len(ai_fields)} campi.")
            else:
                st.warning("L'estrazione AI non ha prodotto risultati validi.")

        if fields:
            db_manager.bulk_upsert_extractions(
                document_id, [(f.name, f.value, f.confidence, f.method) for f in fields]
            )

    # L'uploader si svuota da solo grazie alla gestione "on_change".
    # Rimuoviamo le righe che causavano l'errore.


# --- SIDEBAR ---
with st.sidebar:
    st.title("🏗️ CapoCantiere AI")

    with st.expander("➕ Carica Documenti", expanded=True):
        st.file_uploader(
            "Seleziona un documento da analizzare",
            type=["pdf", "docx", "xlsx", "csv"],
            label_visibility="collapsed",
            key="file_uploader",
            on_change=process_uploaded_file
        )
    
    st.divider()

    with st.expander("🗂️ Archivio Documenti Recenti"):
        st.dataframe(pd.DataFrame(db_manager.list_documents(limit=10)), use_container_width=True, hide_index=True)

    st.divider()
    
    if st.button("⚠️ Svuota Memoria Dati", type="primary", use_container_width=True, help="ATTENZIONE: Cancella tutti i documenti e i dati caricati!"):
        with st.spinner("Cancellazione di tutti i dati in corso..."):
            db_manager.delete_all_data()
        st.session_state.clear()
        st.rerun()

# --- PAGINA PRINCIPALE ---
st.title("Benvenuto in CapoCantiere AI")
st.markdown(
    """
    Questa è la tua applicazione per la gestione semplificata del personale e dei lavori di cantiere.

    **Usa il menu a sinistra per navigare tra le sezioni:**

    - **`Dashboard`**: Visualizza la reportistica delle ore lavorate.
    - **`Assistente AI`**: Chatta con l'intelligenza artificiale per analizzare i tuoi dati.

    Per iniziare, carica un documento (come un rapportino ore in formato CSV) usando il pannello **Carica Documenti** nella barra laterale.
    """
)