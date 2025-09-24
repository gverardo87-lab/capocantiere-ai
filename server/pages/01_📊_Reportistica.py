# server/pages/01_📊_Reportistica.py
from __future__ import annotations
import os
import sys
from datetime import datetime
import pandas as pd
import streamlit as st

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.db import db_manager

# Configurazione della pagina
st.set_page_config(page_title="Reportistica Presenze", page_icon="📊", layout="wide")

st.title("📊 Reportistica Presenze Mensile")
st.markdown("Visualizza e analizza i dati aggregati dei rapportini mensili caricati.")

# --- SELEZIONE DEL PERIODO ---
st.subheader("1. Seleziona il periodo da analizzare")

current_year = datetime.now().year
current_month = datetime.now().month

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    selected_year = st.number_input("Anno", min_value=2020, max_value=current_year + 5, value=current_year)
with col2:
    selected_month = st.selectbox(
        "Mese",
        options=range(1, 13),
        format_func=lambda month: datetime(current_year, month, 1).strftime("%B"),
        index=current_month - 1
    )

# Quando il bottone viene premuto, carichiamo i dati e li salviamo nella sessione
if st.button("Mostra Report", type="primary"):
    results = db_manager.get_presence_data(year=selected_year, month=selected_month)
    if not results:
        st.warning(f"Nessun dato trovato per {datetime(selected_year, selected_month, 1).strftime('%B %Y')}.")
        st.session_state['report_data'] = None # Pulisce i dati vecchi
    else:
        df = pd.DataFrame(results)
        df['data'] = pd.to_datetime(df['data']).dt.date
        st.session_state['report_data'] = df # SALVIAMO I DATI IN MEMORIA
        st.session_state['report_period'] = f"{datetime(selected_year, selected_month, 1).strftime('%B %Y')}"

# --- VISUALIZZAZIONE E FILTRAGGIO (ORA FUORI DAL BOTTONE) ---
# Controlliamo se ci sono dati in memoria da mostrare
if 'report_data' in st.session_state and st.session_state['report_data'] is not None:
    df_original = st.session_state['report_data']
    
    st.divider()
    st.subheader("2. Applica filtri (opzionale)")

    # --- FILTRI AGGIUNTIVI ---
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        operai_disponibili = sorted(df_original['operaio'].unique())
        selected_operai = st.multiselect("Filtra per Operaio", options=operai_disponibili)
    with fcol2:
        min_date = df_original['data'].min()
        max_date = df_original['data'].max()
        selected_date_range = st.date_input(
            "Filtra per intervallo di giorni",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    # --- APPLICAZIONE DEI FILTRI ---
    df_filtered = df_original.copy()
    if selected_operai:
        df_filtered = df_filtered[df_filtered['operaio'].isin(selected_operai)]
    if selected_date_range and len(selected_date_range) == 2:
        start_date, end_date = selected_date_range
        df_filtered = df_filtered[(df_filtered['data'] >= start_date) & (df_filtered['data'] <= end_date)]

    st.divider()
    st.header(f"Riepilogo per {st.session_state['report_period']}")
    
    # --- METRICHE TOTALI ---
    total_worked = df_filtered['ore_lavorate'].sum()
    total_regular = df_filtered['ore_regolari'].sum()
    total_overtime = df_filtered['ore_straordinario'].sum()
    total_absence = df_filtered['ore_assenza'].sum()

    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("📈 Totale Ore Lavorate", f"{total_worked:,.2f}")
    mcol2.metric("🕒 Ore Regolari", f"{total_regular:,.2f}")
    mcol3.metric("🚀 Ore Straordinario", f"{total_overtime:,.2f}")
    mcol4.metric("📉 Ore Assenza", f"{total_absence:,.2f}")
    
    st.divider()

    # --- TABELLA AGGREGATA ---
    st.subheader("Riepilogo per Operaio")
    summary_df = df_filtered.groupby('operaio').agg(
        ore_lavorate=('ore_lavorate', 'sum'),
        ore_regolari=('ore_regolari', 'sum'),
        ore_straordinario=('ore_straordinario', 'sum'),
        ore_assenza=('ore_assenza', 'sum')
    ).reset_index().round(2)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
    st.divider()

    # --- DETTAGLIO GIORNALIERO ---
    with st.expander("Mostra dettaglio giornaliero filtrato"):
        st.dataframe(df_filtered, use_container_width=True, hide_index=True,
                     column_config={"data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")})