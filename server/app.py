from __future__ import annotations

import os
from datetime import date
import pandas as pd
import streamlit as st
import sys

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db import db_manager
from tools.extractors import (
    read_text_and_kind,
    file_sha256,
    parse_timesheet_csv,
    extract_fields_with_ai
)
from core.chat_logic import get_ai_response

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="🏗️ CapoCantiere AI",
    page_icon="🏗️",
    layout="wide",
)

# --- NUOVA FUNZIONE DI CALLBACK PER LA GESTIONE DELL'UPLOAD ---
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
                # La funzione di parsing non restituisce più un riepilogo
                rows, _ = parse_timesheet_csv(file_bytes)
                db_manager.replace_timesheet_rows(document_id, rows)
                st.success(f"Rapportino '{filename}' importato!")
                refresh_filtered_data()
            except Exception as e:
                st.error(f"Errore nel CSV: {e}")
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

# --- FUNZIONE HELPER PER RICARICARE I DATI ---
def refresh_filtered_data(filters=None):
    """Esegue una query con i filtri forniti e aggiorna lo stato della sessione."""
    if filters is None:
        filters = {}
    results = db_manager.timesheet_query(
        date_from=filters.get('date_from'),
        date_to=filters.get('date_to'),
        operai=filters.get('operai'),
        commesse=filters.get('commesse'),
        reparti=filters.get('reparti')
    )

    df = pd.DataFrame(results) if results else pd.DataFrame()

    st.session_state['filtered_timesheet'] = df


# --- SIDEBAR ---
with st.sidebar:
    st.title("🏗️ CapoCantiere AI")

    with st.expander("➕ Carica Documenti", expanded=True):
        st.file_uploader(
            "Seleziona un documento",
            type=["pdf", "docx", "xlsx", "csv"],
            label_visibility="collapsed",
            key="file_uploader",
            on_change=process_uploaded_file
        )

    st.header("🔍 Filtra Ore Lavorate")
    distincts = db_manager.timesheet_distincts()
    date_from = st.date_input("Da data", value=date.today().replace(day=1))
    date_to = st.date_input("A data", value=date.today())
    selected_operai = st.multiselect("Filtra per Operai", options=distincts.get('operaio', []))
    selected_commesse = st.multiselect("Filtra per Commesse", options=distincts.get('commessa', []))
    selected_reparti = st.multiselect("Filtra per Reparti", options=distincts.get('reparto', []))

    if st.button("Esegui Filtro", type="primary", use_container_width=True):
        filters = {
            "date_from": date_from.strftime('%Y-%m-%d'),
            "date_to": date_to.strftime('%Y-%m-%d'),
            "operai": selected_operai if selected_operai else None,
            "commesse": selected_commesse if selected_commesse else None,
            "reparti": selected_reparti if selected_reparti else None
        }
        refresh_filtered_data(filters)

    st.divider()

    with st.expander("🗂️ Archivio Documenti Recenti"):
        st.dataframe(pd.DataFrame(db_manager.list_documents(limit=10)), use_container_width=True)

    st.divider()

    st.header("⚙️ Azioni Rapide")
    if st.button("🔄 Svuota Conversazione", use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": "Ciao! La conversazione è stata resettata."}]
        st.rerun()
    if st.button("⚠️ Svuota Memoria Dati", type="primary", use_container_width=True, help="ATTENZIONE: Cancella tutti i documenti e i dati caricati!"):
        with st.spinner("Cancellazione di tutti i dati in corso..."):
            db_manager.delete_all_data()
        st.session_state.clear()
        st.rerun()

# --- PAGINA PRINCIPALE ---
st.header("📊 Reportistica Ore")

if 'filtered_timesheet' not in st.session_state:
    refresh_filtered_data()

df_filtered = st.session_state.get('filtered_timesheet', pd.DataFrame())

if not df_filtered.empty:
    # Definiamo l'ordine desiderato delle colonne per la visualizzazione
    display_columns = [
        'data', 'operaio', 'commessa', 'orario_ingresso', 'orario_uscita', 'ore_lavorate', 'reparto', 'descrizione'
    ]
    # Rimuoviamo le colonne non desiderate e riordiniamo
    df_display = df_filtered[display_columns].copy()

    st.dataframe(df_display, use_container_width=True)

    total_hours = df_filtered['ore_lavorate'].sum()
    st.metric("📈 Totale Ore Filtrate", f"{total_hours:,.2f} ore")
else:
    st.info("Nessun dato da visualizzare. Carica un rapportino o prova a cambiare i filtri.")

st.divider()

# --- LOGICA CHAT ---
st.header("💬 Chiedi al tuo Assistente di Cantiere")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Ciao! Fammi una domanda sui dati dei rapportini."}]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Quante ore ha lavorato Rossi Luca?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Sto pensando..."):
            response = get_ai_response(st.session_state.messages)
            st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})