from __future__ import annotations

import os
import sys
from datetime import date
import pandas as pd
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.db import db_manager

st.title("📈 Dashboard Reportistica Ore")
st.markdown("Visualizza e filtra le ore lavorate registrate nel sistema.")

# --- FUNZIONE HELPER PER RICARICARE I DATI ---
def refresh_filtered_data(date_from=None, date_to=None, operai=None, commesse=None):
    """Esegue una query con i filtri forniti e aggiorna lo stato della sessione."""
    results = db_manager.timesheet_query(
        date_from=date_from.strftime('%Y-%m-%d') if date_from else None,
        date_to=date_to.strftime('%Y-%m-%d') if date_to else None,
        operai=operai if operai else None,
        commesse=commesse if commesse else None,
    )
    st.session_state['filtered_timesheet'] = pd.DataFrame(results) if results else pd.DataFrame()

# --- LOGICA DEI FILTRI ---
with st.expander("🔍 Filtra Dati", expanded=True):
    distincts = db_manager.timesheet_distincts()

    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("Da data", value=date.today().replace(day=1))
        selected_operai = st.multiselect("Filtra per Operai", options=distincts.get('operaio', []))
    with col2:
        date_to = st.date_input("A data", value=date.today())
        selected_commesse = st.multiselect("Filtra per Commesse", options=distincts.get('commessa', []))

    if st.button("Esegui Filtro", type="primary", use_container_width=True):
        refresh_filtered_data(date_from, date_to, selected_operai, selected_commesse)

# Inizializza i dati al primo caricamento
if 'filtered_timesheet' not in st.session_state:
    refresh_filtered_data(date.today().replace(day=1), date.today())


st.divider()

# --- VISUALIZZAZIONE DATI ---
st.header("📊 Risultati Filtrati")
df_filtered = st.session_state.get('filtered_timesheet', pd.DataFrame())

if not df_filtered.empty:
    # Rimuoviamo le colonne ID che non servono all'utente
    display_df = df_filtered.drop(columns=['id', 'document_id'], errors='ignore')
    st.dataframe(display_df, use_container_width=True)

    total_hours = df_filtered['ore'].sum()
    st.metric("📈 Totale Ore Filtrate", f"{total_hours:,.2f} ore")
else:
    st.info("Nessun dato da visualizzare. Carica un rapportino o prova a cambiare i filtri.")
