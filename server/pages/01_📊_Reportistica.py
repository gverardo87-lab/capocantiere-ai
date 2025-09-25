# server/pages/01_📊_Reportistica.py (versione potenziata)

from __future__ import annotations
import os
import sys
from datetime import datetime
import pandas as pd
import streamlit as st

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.db import db_manager

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Reportistica Presenze", page_icon="📊", layout="wide")

st.title("📊 Dashboard Reportistica")
st.markdown("Analizza i dati aggregati dei rapportini mensili.")

# --- SELEZIONE PERIODO E FILTRI IN UNA SOLA SEZIONE ---
with st.container(border=True):
    st.subheader("Filtra Dati")
    
    current_year = datetime.now().year
    current_month = datetime.now().month

    col1, col2 = st.columns([1, 2])
    with col1:
        selected_year = st.number_input("Anno", min_value=2020, max_value=current_year + 5, value=current_year)
    with col2:
        selected_month = st.selectbox(
            "Mese",
            options=range(1, 13),
            format_func=lambda month: datetime(current_year, month, 1).strftime("%B"),
            index=current_month - 1
        )
    
    if st.button("Mostra Report", type="primary", use_container_width=True):
        results = db_manager.get_presence_data(year=selected_year, month=selected_month)
        if not results:
            st.warning(f"Nessun dato trovato per {datetime(selected_year, selected_month, 1).strftime('%B %Y')}.")
            st.session_state['report_data'] = None # Pulisce i dati vecchi
        else:
            df = pd.DataFrame(results)
            df['data'] = pd.to_datetime(df['data']).dt.date
            st.session_state['report_data'] = df # SALVIAMO I DATI IN MEMORIA
            st.session_state['report_period'] = f"{datetime(selected_year, selected_month, 1).strftime('%B %Y')}"

# --- VISUALIZZAZIONE DATI (se disponibili) ---
if 'report_data' in st.session_state and st.session_state['report_data'] is not None:
    df_original = st.session_state['report_data']
    
    st.header(f"Riepilogo per: {st.session_state['report_period']}")
    st.divider()

    # --- METRICHE E FILTRI AVANZATI IN COLONNE ---
    col_metrics, col_filters = st.columns([2, 1])

    with col_filters:
        with st.expander("Filtri Aggiuntivi", expanded=True):
            operai_disponibili = sorted(df_original['operaio'].unique())
            selected_operai = st.multiselect("Filtra per Operaio", options=operai_disponibili, placeholder="Seleziona operai...")
            
            min_date = df_original['data'].min()
            max_date = df_original['data'].max()
            selected_date_range = st.date_input(
                "Filtra per intervallo giorni",
                value=(min_date, max_date), min_value=min_date, max_value=max_date
            )
    
    # --- APPLICAZIONE DEI FILTRI (logica invariata) ---
    df_filtered = df_original.copy()
    if selected_operai:
        df_filtered = df_filtered[df_filtered['operaio'].isin(selected_operai)]
    if selected_date_range and len(selected_date_range) == 2:
        start_date, end_date = selected_date_range
        df_filtered = df_filtered[(df_filtered['data'] >= start_date) & (df_filtered['data'] <= end_date)]
    
    with col_metrics:
        st.subheader("Metriche Chiave del Periodo")
        total_worked = df_filtered['ore_lavorate'].sum()
        total_regular = df_filtered['ore_regolari'].sum()
        total_overtime = df_filtered['ore_straordinario'].sum()
        total_absence = df_filtered['ore_assenza'].sum()
        
        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
        mcol1.metric("👷 Totale Ore Lavorate", f"{total_worked:,.2f} h")
        mcol2.metric("✔️ Ore Regolari", f"{total_regular:,.2f} h")
        # Calcolo % straordinari sul totale, con protezione per divisione per zero
        overtime_percentage = (total_overtime / total_worked * 100) if total_worked > 0 else 0
        mcol3.metric("🔥 Ore Straordinario", f"{total_overtime:,.2f} h", delta=f"{overtime_percentage:.1f}% del totale", delta_color="inverse")
        mcol4.metric("❌ Ore Assenza", f"{total_absence:,.2f} h")

    st.divider()

    # --- TABELLE CON TAB ---
    st.subheader("Dettaglio Dati")
    tab1, tab2 = st.tabs(["📊 Riepilogo per Operaio", "📅 Dettaglio Giornaliero"])
    
    with tab1:
        if df_filtered.empty:
            st.info("Nessun dato da visualizzare con i filtri correnti.")
        else:
            summary_df = df_filtered.groupby('operaio').agg(
                ore_lavorate=('ore_lavorate', 'sum'),
                ore_regolari=('ore_regolari', 'sum'),
                ore_straordinario=('ore_straordinario', 'sum'),
                ore_assenza=('ore_assenza', 'sum')
            ).reset_index().round(2)
            
            # Arricchiamo la tabella con visualizzazioni
            st.dataframe(summary_df, use_container_width=True, hide_index=True, column_config={
                "ore_lavorate": st.column_config.ProgressColumn(
                    "Ore Lavorate Totali",
                    help="Le ore totali lavorate dall'operaio nel periodo filtrato.",
                    format="%.1f h",
                    min_value=0,
                    max_value=float(summary_df['ore_lavorate'].max())
                ),
                 "ore_straordinario": st.column_config.BarChartColumn(
                    "Straordinari",
                    help="Le ore di straordinario totali.",
                    y_min=0,
                    y_max=float(summary_df['ore_straordinario'].max())
                ),
                 "ore_assenza": st.column_config.NumberColumn(
                    "Ore di Assenza", format="%.1f h"
                 ),
            })
    
    with tab2:
        st.dataframe(df_filtered, use_container_width=True, hide_index=True,
                     column_config={"data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")})
else:
    st.info("👈 Seleziona un periodo e clicca su 'Mostra Report' per iniziare l'analisi.")