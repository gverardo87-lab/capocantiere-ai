from __future__ import annotations

import os
from datetime import date
import pandas as pd
import streamlit as st

# Questo è il "trucchetto" per gli import. Dice a Python di cercare i moduli
# anche nella cartella principale del progetto. Lo lasciamo qui per massima robustezza.
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db import db_manager
from tools.extractors import (
    read_text_and_kind,
    extract_fields_from_text,
    file_sha256,
    parse_timesheet_csv,
)

st.set_page_config(page_title="CapoCantiere AI", layout="wide")

# --- SIDEBAR PER FILTRI E CONTROLLO ---
with st.sidebar:
    st.title("🏗️ CapoCantiere AI")
    st.header("🔍 Filtra Ore Lavorate")

    distincts = db_manager.timesheet_distincts()

    date_from = st.date_input("Da data", value=date.today().replace(day=1))
    date_to = st.date_input("A data", value=date.today())

    selected_operai = st.multiselect("Filtra per Operai", options=distincts.get('operaio', []))
    selected_commesse = st.multiselect("Filtra per Commesse", options=distincts.get('commessa', []))

    if st.button("Esegui Filtro", type="primary", use_container_width=True):
        results = db_manager.timesheet_query(
            date_from=date_from.strftime('%Y-%m-%d'),
            date_to=date_to.strftime('%Y-%m-%d'),
            operai=selected_operai if selected_operai else None,
            commesse=selected_commesse if selected_commesse else None,
        )
        st.session_state['filtered_timesheet'] = pd.DataFrame(results) if results else pd.DataFrame()

# --- PAGINA PRINCIPALE ---
st.header("📊 Reportistica Ore")

# Sezione per mostrare i risultati del filtro
if 'filtered_timesheet' in st.session_state:
    df_filtered = st.session_state['filtered_timesheet']
    if not df_filtered.empty:
        st.dataframe(df_filtered.drop(columns=['id', 'document_id']), use_container_width=True)
        total_hours = df_filtered['ore'].sum()
        st.metric("📈 Totale Ore Filtrate", f"{total_hours:,.2f} ore")
    else:
        st.info("Nessun risultato trovato per i filtri selezionati. Prova a cambiare le date o a rimuovere i filtri.")
else:
    st.info("Usa i filtri nella barra laterale a sinistra per interrogare i rapportini.")

st.divider()

# Sezione di Upload
with st.expander("➕ Carica Nuovi Documenti / Rapportini"):
    uploaded_file = st.file_uploader(
        "Seleziona un documento (i rapportini devono essere in formato .CSV)",
        type=["pdf", "docx", "xlsx", "csv"]
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name
        sha256_hash = file_sha256(file_bytes)

        with st.spinner(f"Analisi di '{filename}' in corso..."):
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
                    structured_rows, summary_fields = parse_timesheet_csv(file_bytes)
                    fields.extend(summary_fields)
                    db_manager.replace_timesheet_rows(document_id, structured_rows)
                    st.success(f"Rapportino CSV '{filename}' importato! ({len(structured_rows)} righe)")
                except Exception as e:
                    st.error(f"Errore nell'analisi del rapportino CSV: {e}")
            else:
                fields.extend(extract_fields_from_text(text))

            if fields:
                db_manager.bulk_upsert_extractions(
                    document_id,
                    [(f.name, f.value, f.confidence, f.method) for f in fields]
                )
        st.rerun()

# Sezione Archivio Documenti
with st.expander("🗂️ Archivio Documenti Recenti"):
    recent_docs = db_manager.list_documents(limit=20)
    if not recent_docs:
        st.info("Nessun documento in archivio.")
    else:
        df_archive = pd.DataFrame(recent_docs)
        st.dataframe(df_archive, use_container_width=True)