from __future__ import annotations

import os
from datetime import date
import pandas as pd
import streamlit as st
import sys

# Import custom
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.db import db_manager
from tools.extractors import *
# NUOVO IMPORT per la logica della chat
from core.chat_logic import get_ai_response

st.set_page_config(page_title="CapoCantiere AI", layout="wide")

# --- SIDEBAR PER FILTRI E CONTROLLO (INVARIATA) ---
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

    st.divider()

    # Sezione di Upload (spostata qui per pulizia)
    with st.expander("➕ Carica Nuovi Documenti"):
        uploaded_file = st.file_uploader(
            "Seleziona un documento",
            type=["pdf", "docx", "xlsx", "csv"]
        )
        if uploaded_file is not None:
            # Tutta la logica di upload rimane la stessa
            file_bytes = uploaded_file.getvalue()
            filename = uploaded_file.name
            sha256_hash = file_sha256(file_bytes)
            with st.spinner(f"Analisi di '{filename}'..."):
                text, kind = read_text_and_kind(filename, file_bytes)
                document_id = db_manager.upsert_document(
                    kind=kind.replace("_CSV", ""), filename=filename,
                    content_type=uploaded_file.type, size_bytes=uploaded_file.size,
                    sha256=sha256_hash,
                )
                fields = []
                if kind == "RAPPORTO_CSV":
                    try:
                        rows, summary = parse_timesheet_csv(file_bytes)
                        fields.extend(summary)
                        db_manager.replace_timesheet_rows(document_id, rows)
                        st.success(f"Rapportino '{filename}' importato!")
                    except Exception as e:
                        st.error(f"Errore nel CSV: {e}")
                else:
                    fields.extend(extract_fields_from_text(text))

                if fields:
                    db_manager.bulk_upsert_extractions(
                        document_id,
                        [(f.name, f.value, f.confidence, f.method) for f in fields]
                    )
            st.rerun()

    # Sezione Archivio (spostata qui per pulizia)
    with st.expander("🗂️ Archivio Documenti Recenti"):
        recent_docs = db_manager.list_documents(limit=10)
        if not recent_docs:
            st.info("Nessun documento in archivio.")
        else:
            st.dataframe(pd.DataFrame(recent_docs), use_container_width=True)

# --- PAGINA PRINCIPALE ---
# --- SEZIONE 1: REPORTISTICA (INVARIATA) ---
st.header("📊 Reportistica Ore")

if 'filtered_timesheet' in st.session_state:
    df_filtered = st.session_state['filtered_timesheet']
    if not df_filtered.empty:
        st.dataframe(df_filtered.drop(columns=['id', 'document_id']), use_container_width=True)
        total_hours = df_filtered['ore'].sum()
        st.metric("📈 Totale Ore Filtrate", f"{total_hours:,.2f} ore")
    else:
        st.info("Nessun risultato per i filtri selezionati.")
else:
    st.info("Usa i filtri nella barra laterale per interrogare i rapportini.")

st.divider()

# --- SEZIONE 2: NUOVA CHAT CON OLLAMA ---
st.header("💬 Chiedi al tuo Assistente di Cantiere")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant",
                                  "content": "Ciao! Fammi una domanda sui dati generali o usa i filtri per analisi specifiche."}]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Es: 'Quante commesse ci sono in totale?'"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Sto pensando..."):
            response = get_ai_response(st.session_state.messages)
            st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})