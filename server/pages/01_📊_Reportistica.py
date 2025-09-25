# server/pages/01_📊_Reportistica.py (Versione Stabile e Completa)

from __future__ import annotations
import os
import sys
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.express as px

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

st.set_page_config(page_title="Consuntivo Attività", page_icon="📊", layout="wide")
st.title("📊 Consuntivo Ore per Attività")
st.markdown("Dashboard per l'analisi e la consuntivazione delle ore di lavoro per singola attività.")

# --- LEGGE I DATI DALLA MEMORIA CENTRALE ---
df_presence = st.session_state.get('df_presence', pd.DataFrame())
df_schedule = st.session_state.get('df_schedule', pd.DataFrame())

if df_presence.empty or 'id_attivita' not in df_presence.columns:
    st.warning("Nessun dato di consuntivo presente. Carica un rapportino dalla Home Page per iniziare.")
else:
    df_presence['data'] = pd.to_datetime(df_presence['data'])
    df_presence.dropna(subset=['id_attivita'], inplace=True)
    df_presence = df_presence[df_presence['id_attivita'] != 'None']

    st.subheader("Pannello di Controllo")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            min_date, max_date = df_presence['data'].min().date(), df_presence['data'].max().date()
            selected_date_range = st.date_input(
                "**Seleziona intervallo di date**",
                value=(min_date, max_date), min_value=min_date, max_value=max_date
            )
        
        with c2:
            if not df_schedule.empty:
                id_to_desc = pd.Series(df_schedule.descrizione.values, index=df_schedule.id_attivita).to_dict()
                available_ids = sorted(df_presence['id_attivita'].unique())
                options_with_desc = {f"{id_}: {id_to_desc.get(id_, 'N/A')}": id_ for id_ in available_ids}
                selected_options = st.multiselect(
                    "**Filtra per ID Attività**", 
                    options=options_with_desc.keys(),
                    placeholder="Tutte le attività"
                )
                selected_ids = [options_with_desc[opt] for opt in selected_options]
            else:
                selected_ids = st.multiselect("**Filtra per ID Attività**", options=sorted(df_presence['id_attivita'].unique()))

        with c3:
            unique_workers = sorted(df_presence['operaio'].unique())
            selected_operai = st.multiselect("**Filtra per Operaio**", options=unique_workers, placeholder="Tutti gli operai")

    start_date, end_date = selected_date_range
    df_filtered = df_presence[(df_presence['data'].dt.date >= start_date) & (df_presence['data'].dt.date <= end_date)]
    if selected_ids:
        df_filtered = df_filtered[df_filtered['id_attivita'].isin(selected_ids)]
    if selected_operai:
        df_filtered = df_filtered[df_filtered['operaio'].isin(selected_operai)]
    st.divider()

    if df_filtered.empty:
        st.info("Nessun dato trovato per i filtri selezionati.")
    else:
        st.header("Riepilogo Consuntivo")
        kpi1, kpi2, kpi3 = st.columns(3)
        total_worked = df_filtered['ore_lavorate'].sum()
        total_activities = df_filtered['id_attivita'].nunique()
        total_workers = df_filtered['operaio'].nunique()
        
        kpi1.metric("Ore Totali Consuntivate", f"{total_worked:,.1f} h")
        kpi2.metric("N° Attività Lavorate", f"{total_activities}")
        kpi3.metric("N° Operai Coinvolti", f"{total_workers}")
        st.divider()

        st.header("Dettaglio Analisi")
        tab_activity, tab_worker = st.tabs(["**Consuntivo per Attività**", "**Consuntivo per Operaio**"])

        with tab_activity:
            activity_summary = df_filtered.groupby('id_attivita').agg(
                ore_totali=('ore_lavorate', 'sum'),
                straordinari_totali=('ore_straordinario', 'sum'),
                operai_unici=('operaio', 'nunique')
            ).reset_index().round(1)
            
            if not df_schedule.empty:
                activity_summary = pd.merge(activity_summary, df_schedule[['id_attivita', 'descrizione']], on='id_attivita', how='left')
            
            st.dataframe(activity_summary, use_container_width=True, hide_index=True, column_config={
                "id_attivita": "ID Attività", "descrizione": "Descrizione",
                "ore_totali": st.column_config.BarChartColumn("Ore Totali Consuntivate"),
                "operai_unici": "N° Operai"
            })

        with tab_worker:
            worker_summary = df_filtered.groupby(['operaio', 'ruolo']).agg(
                ore_totali=('ore_lavorate', 'sum'),
                straordinari_totali=('ore_straordinario', 'sum'),
                attivita_lavorate=('id_attivita', 'nunique')
            ).reset_index().round(1)
            
            st.dataframe(worker_summary, use_container_width=True, hide_index=True, column_config={
                "operaio": "Operaio", "ruolo": "Ruolo",
                "ore_totali": st.column_config.ProgressColumn("Ore Totali Lavorate", format="%.1f h", min_value=0),
                "attivita_lavorate": "N° Attività"
            })