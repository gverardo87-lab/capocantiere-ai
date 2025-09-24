# server/pages/04_📈_Cronoprogramma.py
from __future__ import annotations
import os
import sys
from datetime import date
import streamlit as st
import pandas as pd
import plotly.express as px

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.schedule_db import schedule_db_manager
from tools.schedule_extractor import parse_schedule_excel, ScheduleParsingError

# Configurazione della pagina
st.set_page_config(page_title="Cronoprogramma", page_icon="📈", layout="wide")

st.title("📈 Gestione e Visualizzazione Cronoprogramma")

# --- FUNZIONE DI CARICAMENTO E UPLOADER (INTATTI) ---
def process_schedule_file_on_page():
    uploaded_file = st.session_state.get("cronoprogramma_uploader")
    if uploaded_file is None: return
    file_bytes = uploaded_file.getvalue()
    try:
        records = parse_schedule_excel(file_bytes)
        schedule_db_manager.update_schedule(records)
        st.success(f"Cronoprogramma '{uploaded_file.name}' importato!")
    except Exception as e:
        st.error(f"Errore durante l'elaborazione del file: {e}")

with st.expander("➕ Carica un nuovo file di Cronoprogramma"):
    st.file_uploader("Seleziona file", type=["xlsx"], key="cronoprogramma_uploader", on_change=process_schedule_file_on_page, label_visibility="collapsed")
st.divider()

# --- FILTRO ESCLUSIVAMENTE PER DATA ---
st.subheader("1. Seleziona l'intervallo di date")

# Determiniamo il range di date disponibili per i selettori
try:
    all_data = schedule_db_manager.get_schedule_data()
    if all_data:
        df_all = pd.DataFrame(all_data)
        min_date = pd.to_datetime(df_all['data_inizio']).min().date()
        max_date = pd.to_datetime(df_all['data_fine']).max().date()
    else:
        min_date, max_date = date.today(), date.today()
except Exception:
    min_date, max_date = date.today(), date.today()

col1, col2 = st.columns(2)
with col1:
    date_from = st.date_input("Da data", value=min_date, min_value=min_date, max_value=max_date)
with col2:
    date_to = st.date_input("A data", value=max_date, min_value=min_date, max_value=max_date)

# --- BOTTONE "MOSTRA" ---
if st.button("Mostra Cronoprogramma", type="primary"):
    all_results = schedule_db_manager.get_schedule_data()
    if not all_results:
        st.warning("Nessun dato trovato nel database.")
        st.session_state['schedule_data'] = None
    else:
        df = pd.DataFrame(all_results)
        df['data_inizio'] = pd.to_datetime(df['data_inizio']).dt.date
        df['data_fine'] = pd.to_datetime(df['data_fine']).dt.date
        
        # Filtriamo il dataframe in base alle date selezionate
        filtered_df = df[
            (df['data_inizio'] <= date_to) & (df['data_fine'] >= date_from)
        ]
        st.session_state['schedule_data'] = filtered_df

# --- VISUALIZZAZIONE DATI (INVARIATA) ---
if 'schedule_data' in st.session_state and st.session_state['schedule_data'] is not None:
    df_schedule = st.session_state['schedule_data']
    
    if df_schedule.empty:
        st.info("Nessuna attività trovata nell'intervallo di date selezionato.")
    else:
        st.divider()
        st.header(f"Visualizzazione dal {date_from.strftime('%d/%m/%Y')} al {date_to.strftime('%d/%m/%Y')}")

        def get_status(progress):
            if progress >= 100: return "Completato"
            elif progress > 0: return "In Corso"
            else: return "Non Iniziato"
        df_schedule['stato'] = df_schedule['stato_avanzamento'].apply(get_status)
        df_schedule['etichetta_avanzamento'] = df_schedule['stato_avanzamento'].astype(str) + '%'
        color_map = {"Completato": "green", "In Corso": "orange", "Non Iniziato": "grey"}

        st.subheader("Diagramma di Gantt con Avanzamento")
        num_activities = len(df_schedule)
        chart_height = max(600, num_activities * 50)

        fig = px.timeline(
            df_schedule, x_start="data_inizio", x_end="data_fine", y="descrizione",
            color="stato", text="etichetta_avanzamento", color_discrete_map=color_map, height=chart_height
        )
        
        fig.update_traces(textfont_size=16, textposition='inside')
        fig.update_yaxes(autorange="reversed")
        
        fig.update_layout(
            title_text='Stato Avanzamento Attività', title_font_size=30, font_size=18,
            xaxis=dict(title="Linea del Tempo", title_font_size=20, tickfont_size=16),
            yaxis=dict(title="Attività", title_font_size=20, tickfont_size=16),
            legend=dict(font_size=18)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Mostra dettaglio attività"):
            st.dataframe(df_schedule, use_container_width=True, hide_index=True)