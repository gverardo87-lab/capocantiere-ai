# file: server/pages/01_Reportistica.py (Versione 16.4 - Mappatura Attività Speciali)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

# Aggiungiamo la root del progetto al path per importare i moduli 'core'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    # ★ IMPORT CORRETTO ★
    from core.shift_service import shift_service
    from core.schedule_db import schedule_db_manager
    from core.logic import calculate_duration_hours
except ImportError as e:
    st.error(f"Errore critico: Impossibile importare i moduli: {e}")
    st.stop()

st.set_page_config(page_title="Consuntivo Ore Lavorate", page_icon="📊", layout="wide")
st.title("📊 Consuntivo Ore Lavorate")
st.markdown("Dashboard di analisi aggregata delle ore per la contabilità giornaliera (buste paga).")

# --- 1. CARICAMENTO DATI E FILTRI ---

@st.cache_data(ttl=60)
def load_activities_map():
    """Crea un dizionario (mappa) di ID Attività -> Descrizione."""
    # ★ NUOVO: Mappa di base per attività speciali ★
    activities_map = {
        "VIAGGIO": "VIAGGIO (Trasferta)",
        "STRAORDINARIO": "STRAORDINARIO (Generico)",
        "OFFICINA": "OFFICINA (Lavoro Interno)"
    }
    
    try:
        schedule_data = schedule_db_manager.get_schedule_data()
        df_schedule = pd.DataFrame(schedule_data)
        if not df_schedule.empty:
            # Sovrascrive la mappa di base solo con le attività di schedule
            schedule_map = df_schedule.set_index('id_attivita')['descrizione'].to_dict()
            activities_map.update(schedule_map)
    except Exception as e:
        print(f"Errore caricamento cronoprogramma: {e}")
        
    return activities_map

activities_map_cached = load_activities_map()

def map_activity_id(id_att):
    if pd.isna(id_att) or id_att == "-1":
        return "N/A (Non Specificato)"
    # Usa la mappa cache per trovare la descrizione
    return activities_map_cached.get(id_att, f"Attività Sconosciuta ({id_att})")

st.subheader("Pannello di Controllo")
with st.container(border=True):
    col1, col2, col3 = st.columns([1, 1, 2])
    today = date.today()
    default_start = today.replace(day=1)
    
    with col1:
        date_from = st.date_input("Da data", default_start)
    with col2:
        date_to = st.date_input("A data", today)
    with col3:
        st.write("")
        st.write("")
        run_report = st.button("Applica Filtri e Aggiorna Report", type="primary", use_container_width=True)

if not run_report:
    st.info("Imposta un intervallo di date e clicca 'Applica Filtri' per caricare il report.")
    st.stop()

if date_from > date_to:
    st.error("Errore: La data 'Da' deve essere precedente alla data 'A'.")
    st.stop()

# --- 2. ESECUZIONE QUERY E CALCOLO DATI ---
try:
    with st.spinner("Caricamento e aggregazione dati in corso..."):
        # ★ CHIAMATA CORRETTA al service ★
        df_raw_report = shift_service.get_report_data_df(date_from, date_to)

        if df_raw_report.empty:
            st.warning("Nessuna registrazione trovata nell'intervallo di date selezionato.")
            st.stop()
        
        # Calcoliamo la durata usando la fonte di verità
        df_raw_report['durata_ore'] = df_raw_report.apply(
            lambda row: calculate_duration_hours(row['data_ora_inizio'], row['data_ora_fine']),
            axis=1
        )

        # ★ MODIFICATO: Usa la nuova funzione di mappatura ★
        df_raw_report['desc_attivita'] = df_raw_report['id_attivita'].apply(map_activity_id)
        
        # Aggregazioni
        df_dipendente = df_raw_report.groupby(['dipendente_nome', 'ruolo'])['durata_ore'].sum().reset_index()
        df_dipendente = df_dipendente.sort_values(by="durata_ore", ascending=False).rename(columns={'durata_ore': 'Ore Totali'})
        
        df_attivita = df_raw_report.groupby('desc_attivita')['durata_ore'].sum().reset_index()
        df_attivita = df_attivita.sort_values(by="durata_ore", ascending=False).rename(columns={'durata_ore': 'Ore Totali'})
        
        df_raw_report['giorno'] = df_raw_report['data_ora_inizio'].dt.date
        df_giornaliero = df_raw_report.groupby('giorno')['durata_ore'].sum().reset_index()
        
        total_hours = df_raw_report['durata_ore'].sum()
        total_dipendenti = df_raw_report['id_dipendente'].nunique()

except Exception as e:
    st.error(f"Si è verificato un errore durante la generazione del report: {e}")
    st.stop()

# --- 3. VISUALIZZAZIONE E KPI ---
st.header(f"Report dal {date_from.strftime('%d/%m/%Y')} al {date_to.strftime('%d/%m/%Y')}")

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Ore Totali Rendicontate", f"{total_hours:,.2f} h")
kpi2.metric("Dipendenti Attivi", total_dipendenti)
kpi3.metric("Giorni di Lavoro nel Periodo", df_raw_report['giorno'].nunique())

st.divider()

col_chart, col_table = st.columns([1, 1])

with col_chart:
    st.subheader("Andamento Ore Giornaliere (per Competenza)")
    fig = px.line(
        df_giornaliero, 
        x='giorno', 
        y='durata_ore',
        title="Totale Ore Lavorate per Giorno (00:00-00:00)",
        labels={'giorno': 'Data di Competenza', 'durata_ore': 'Ore Totali'}
    )
    fig.update_traces(mode='lines+markers', line_shape='spline')
    st.plotly_chart(fig, use_container_width=True)

with col_table:
    st.subheader("Ore per Attività")
    st.markdown("Ora include 'VIAGGIO' e 'STRAORDINARIO' se registrati.")
    st.dataframe(
        df_attivita,
        use_container_width=True,
        hide_index=True,
        column_config={
            "desc_attivita": "Attività",
            "Ore Totali": st.column_config.NumberColumn("Ore Totali", format="%.2f h")
        }
    )

st.divider()

col_dip, col_raw = st.columns(2)

with col_dip:
    st.subheader("Ore per Dipendente (per Busta Paga)")
    st.dataframe(
        df_dipendente,
        use_container_width=True,
        hide_index=True,
        column_config={
            "dipendente_nome": "Dipendente",
            "ruolo": "Ruolo",
            "Ore Totali": st.column_config.NumberColumn("Ore Totali", format="%.2f h")
        }
    )

with col_raw:
    st.subheader("Dettaglio Segmenti di Lavoro")
    with st.expander("Mostra tutti i segmenti (per verifica)"):
        st.dataframe(
            df_raw_report.sort_values(by="data_ora_inizio"),
            use_container_width=True,
            hide_index=True,
            column_config={
                "data_ora_inizio": "Inizio Segmento",
                "data_ora_fine": "Fine Segmento",
                "durata_ore": "Ore",
                "desc_attivita": "Attività",
                "dipendente_nome": "Dipendente"
            }
        )