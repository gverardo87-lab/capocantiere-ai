# server/pages/01_📊_Reportistica.py
from __future__ import annotations
import os
from datetime import date
import pandas as pd
import streamlit as st
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.db import db_manager

st.set_page_config(page_title="Reportistica", page_icon="📊", layout="wide")

st.title("📊 Reportistica Ore")
st.markdown("Visualizza, filtra e analizza i dati dei rapportini caricati.")

def refresh_filtered_data(filters=None):
    if filters is None: filters = {}
    results = db_manager.timesheet_query(
        date_from=filters.get('date_from'), date_to=filters.get('date_to'),
        operai=filters.get('operai'), commesse=filters.get('commesse'),
        reparti=filters.get('reparti')
    )
    df = pd.DataFrame(results) if results else pd.DataFrame()
    st.session_state['filtered_timesheet'] = df
    if not df.empty and all(col in df.columns for col in ['ore_lavorate', 'ore_regolari', 'ore_straordinario', 'ore_assenza']):
        df_daily = df.groupby(['data', 'operaio']).agg(
            ore_lavorate=('ore_lavorate', 'sum'), ore_regolari=('ore_regolari', 'sum'),
            ore_straordinario=('ore_straordinario', 'sum'), ore_assenza=('ore_assenza', 'sum')
        ).reset_index().round(2)
        st.session_state['aggregated_timesheet'] = df_daily
    else:
        st.session_state['aggregated_timesheet'] = pd.DataFrame()

with st.expander("🔍 Filtra Dati", expanded=True):
    distincts = db_manager.timesheet_distincts()
    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("Da data", value=None)
        selected_operai = st.multiselect("Filtra per Operai", options=distincts.get('operaio', []))
    with col2:
        date_to = st.date_input("A data", value=None)
        selected_commesse = st.multiselect("Filtra per Commesse", options=distincts.get('commessa', []))
    selected_reparti = st.multiselect("Filtra per Reparti", options=distincts.get('reparto', []))
    if st.button("Esegui Filtro", type="primary"):
        filters = {
            "date_from": date_from.strftime('%Y-%m-%d') if date_from else None,
            "date_to": date_to.strftime('%Y-%m-%d') if date_to else None,
            "operai": selected_operai or None, "commesse": selected_commesse or None,
            "reparti": selected_reparti or None
        }
        refresh_filtered_data(filters)

if 'filtered_timesheet' not in st.session_state:
    refresh_filtered_data()

df_filtered = st.session_state.get('filtered_timesheet', pd.DataFrame())
df_aggregated = st.session_state.get('aggregated_timesheet', pd.DataFrame())

st.subheader("🗓️ Riepilogo Ore Giornaliero")
if not df_aggregated.empty:
    st.dataframe(df_aggregated, use_container_width=True)
else:
    st.info("Nessun dato aggregato. Filtra i dati per generare il riepilogo.")
st.divider()

st.subheader("Dettaglio Attività")
if not df_filtered.empty:
    st.dataframe(df_filtered, use_container_width=True)
else:
    st.info("Nessun dato dettagliato. Carica un rapportino o applica un filtro.")
st.divider()

st.subheader("Metriche Totali del Periodo Filtrato")
if not df_aggregated.empty:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📈 Totale Ore Lavorate", f"{df_aggregated['ore_lavorate'].sum():,.2f}")
    col2.metric("🕒 Ore Regolari", f"{df_aggregated['ore_regolari'].sum():,.2f}")
    col3.metric("🚀 Ore Straordinario", f"{df_aggregated['ore_straordinario'].sum():,.2f}")
    col4.metric("📉 Ore Assenza", f"{df_aggregated['ore_assenza'].sum():,.2f}")