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
from core.chat_logic import get_ai_response

st.set_page_config(page_title="CapoCantiere AI", layout="wide")


# --- FUNZIONE HELPER PER RICARICARE I DATI FILTRATI ---
# L'abbiamo messa in una funzione per poterla richiamare facilmente
def refresh_filtered_data():
    """Esegue una query con tutti i dati e aggiorna lo stato della sessione."""
    results = db_manager.timesheet_query()
    st.session_state['filtered_timesheet'] = pd.DataFrame(results) if results else pd.DataFrame()


# --- SIDEBAR PER FILTRI E CONTROLLO ---
with st.sidebar:
    st.title("🏗️ CapoCantiere AI")

    # Sezione di Upload (ora più pulita)
    with st.expander("➕ Carica Documenti", expanded=True):
        uploaded_file = st.file_uploader("Seleziona un documento", type=["pdf", "docx", "xlsx", "csv"],
                                         label_visibility="collapsed")
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            filename = uploaded_file.name
            sha256_hash = file_sha256(file_bytes)
            with st.spinner(f"Analisi di '{filename}'..."):
                text, kind = read_text_and_kind(filename, file_bytes)
                document_id = db_manager.upsert_document(kind=kind.replace("_CSV", ""), filename=filename,
                                                         content_type=uploaded_file.type, size_bytes=uploaded_file.size,
                                                         sha256=sha256_hash)
                fields = []
                if kind == "RAPPORTO_CSV":
                    try:
                        rows, summary = parse_timesheet_csv(file_bytes)
                        fields.extend(summary)
                        db_manager.replace_timesheet_rows(document_id, rows)
                        st.success(f"Rapportino '{filename}' importato!")
                        # CORREZIONE: Aggiorniamo i dati della tabella dopo l'upload
                        refresh_filtered_data()
                    except Exception as e:
                        st.error(f"Errore nel CSV: {e}")
                else:
                    fields.extend(extract_fields_from_text(text))
                    st.success(f"Documento '{filename}' analizzato!")

                if fields: db_manager.bulk_upsert_extractions(document_id,
                                                              [(f.name, f.value, f.confidence, f.method) for f in
                                                               fields])
            # Rimosso st.rerun() che causava problemi. Streamlit gestisce l'aggiornamento.

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

    with st.expander("🗂️ Archivio Documenti Recenti"):
        st.dataframe(pd.DataFrame(db_manager.list_documents(limit=10)), use_container_width=True)

    st.divider()
    st.header("⚙️ Azioni Rapide")
    if st.button("🔄 Svuota Conversazione", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "Ciao! La conversazione è stata resettata. Come posso aiutarti?"}]
        st.rerun()

    if st.button("⚠️ Svuota Memoria Dati", type="primary", use_container_width=True,
                 help="ATTENZIONE: Cancella tutti i documenti e i dati caricati!"):
        with st.spinner("Cancellazione di tutti i dati in corso..."):
            db_manager.delete_all_data()
        st.session_state.clear()
        st.rerun()

# --- PAGINA PRINCIPALE ---
st.header("📊 Reportistica Ore")

# Se non ci sono dati filtrati, proviamo a caricarli tutti all'avvio
if 'filtered_timesheet' not in st.session_state:
    refresh_filtered_data()

df_filtered = st.session_state.get('filtered_timesheet', pd.DataFrame())
if not df_filtered.empty:
    st.dataframe(df_filtered.drop(columns=['id', 'document_id'], errors='ignore'), use_container_width=True)
    total_hours = df_filtered['ore'].sum()
    st.metric("📈 Totale Ore Filtrate", f"{total_hours:,.2f} ore")
else:
    st.info("Nessun dato da visualizzare. Carica un rapportino o prova a cambiare i filtri.")

st.divider()

st.header("💬 Chiedi al tuo Assistente di Cantiere")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Ciao! Fammi una domanda sui dati generali."}]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- LOGICA CHAT CORRETTA ---
if prompt := st.chat_input("Scrivi la tua domanda qui..."):
    # 1. Aggiungi e mostra subito il messaggio dell'utente
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Genera la risposta dell'assistente
    with st.chat_message("assistant"):
        with st.spinner("Sto pensando..."):
            response = get_ai_response(st.session_state.messages)
            st.markdown(response)

    # 3. Solo alla fine, aggiungi la risposta dell'assistente alla cronologia
    st.session_state.messages.append({"role": "assistant", "content": response})