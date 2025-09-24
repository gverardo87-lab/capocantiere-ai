# server/pages/04_📈_Cronoprogramma.py
from __future__ import annotations
import os
import sys
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
st.markdown("Carica e visualizza i dati dei cronoprogrammi.")

# --- FUNZIONE DI CARICAMENTO (per il nuovo uploader) ---
def process_schedule_file_on_page():
    uploaded_file = st.session_state.get("cronoprogramma_uploader")
    if uploaded_file is None: return
    
    file_bytes = uploaded_file.getvalue()
    filename = uploaded_file.name

    with st.spinner(f"Elaborazione di '{filename}'..."):
        try:
            records = parse_schedule_excel(file_bytes)
            if not records:
                st.warning("File letto, ma nessuna attività trovata.")
                return
            schedule_db_manager.update_schedule(records)
            st.success(f"Cronoprogramma '{filename}' importato! {len(records)} attività salvate.")
        except ScheduleParsingError as e:
            st.error(f"❌ Errore nel formato del file: {e}")
        except Exception as e:
            st.error(f"Si è verificato un errore imprevisto: {e}")

# --- SEZIONE DI CARICAMENTO FILE (IL "TASTINO") ---
with st.expander("➕ Carica un nuovo file di Cronoprogramma"):
    st.file_uploader(
        "Seleziona il file da caricare",
        type=["xlsx"],  # MODIFICA: Solo .xlsx è permesso
        key="cronoprogramma_uploader",
        on_change=process_schedule_file_on_page,
        label_visibility="collapsed"
    )

st.divider()

# ###############################################################
# --- TUTTO IL CODICE DA QUI IN POI RIMANE UGUALE E INTATTO --- #
# ###############################################################

# --- SELEZIONE DEI FILTRI ---
st.subheader("1. Seleziona i filtri")

try:
    available_data = schedule_db_manager.get_schedule_data()
    commesse_options = sorted(pd.DataFrame(available_data)['commessa'].unique()) if available_data else []
except Exception:
    commesse_options = []

selected_commessa = st.selectbox(
    "Filtra per Commessa",
    options=["Tutte"] + commesse_options
)

# --- BOTTONE PER CARICARE I DATI ---
if st.button("Mostra Cronoprogramma", type="primary"):
    commessa_filter = None if selected_commessa == "Tutte" else selected_commessa
    results = schedule_db_manager.get_schedule_data(commessa=commessa_filter)
    
    if not results:
        st.warning(f"Nessun dato trovato per la selezione.")
        st.session_state['schedule_data'] = None
    else:
        st.session_state['schedule_data'] = pd.DataFrame(results)

# --- VISUALIZZAZIONE DATI ---
if 'schedule_data' in st.session_state and st.session_state['schedule_data'] is not None:
    df_schedule = st.session_state['schedule_data']
    st.divider()
    st.header(f"Visualizzazione per: {selected_commessa}")
    
    st.subheader("Diagramma di Gantt")
    df_schedule['data_inizio'] = pd.to_datetime(df_schedule['data_inizio'])
    df_schedule['data_fine'] = pd.to_datetime(df_schedule['data_fine'])

    fig = px.timeline(
        df_schedule,
        x_start="data_inizio",
        x_end="data_fine",
        y="descrizione",
        color="commessa",
        labels={"descrizione": "Attività"}
    )
    
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Mostra dettaglio attività"):
        st.dataframe(df_schedule, use_container_width=True, hide_index=True)