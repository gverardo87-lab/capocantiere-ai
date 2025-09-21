from __future__ import annotations

import os
import sys
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.db import db_manager
from tools.extractors import (
    read_text_and_kind,
    file_sha256,
    parse_timesheet_csv,
    extract_fields_with_ai,
)

def process_file(uploaded_file):
    """Sposta la logica di elaborazione in una funzione separata per chiarezza."""
    file_bytes = uploaded_file.getvalue()
    filename = uploaded_file.name
    sha256_hash = file_sha256(file_bytes)

    with st.spinner(f"Analisi di '{filename}'..."):
        text, kind = read_text_and_kind(filename, file_bytes)
        document_id = db_manager.upsert_document(
            kind=kind.replace("_CSV", ""),
            filename=filename,
            content_type=uploaded_file.type,
            size_bytes=uploaded_file.size,
            sha256=sha256_hash,
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

st.title("➕ Carica Documenti")
st.markdown(
    "Usa questo modulo per caricare nuovi documenti nel sistema, come rapportini ore, fatture, o permessi."
)

uploaded_file = st.file_uploader(
    "Seleziona un documento da analizzare",
    type=["pdf", "docx", "xlsx", "csv"],
    label_visibility="collapsed",
)

if uploaded_file:
    if st.button("Elabora Documento", type="primary", width='stretch'):
        process_file(uploaded_file)
        # We can add a success message or clear the uploader state if needed,
        # but for now, keeping it simple is best.

st.divider()

st.subheader("🗂️ Archivio Documenti Recenti")
st.dataframe(pd.DataFrame(db_manager.list_documents(limit=10)), use_container_width=True, hide_index=True)
