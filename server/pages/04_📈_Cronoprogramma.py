# server/pages/04_📈_Cronoprogramma.py
from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px

# ... (import e configurazione pagina, tutto come prima) ...
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.schedule_db import schedule_db_manager
from tools.schedule_extractor import parse_schedule_excel, ScheduleParsingError
st.set_page_config(page_title="Cronoprogramma", page_icon="📈", layout="wide")
st.title("📈 Gestione e Visualizzazione Cronoprogramma")

# --- FUNZIONE DI CARICAMENTO E TASTINO UPLOADER (INTATTI) ---
def process_schedule_file_on_page():
    # ... (questa funzione rimane identica)
    uploaded_file = st.session_state.get("cronoprogramma_uploader")
    if uploaded_file is None: return
    file_bytes = uploaded_file.getvalue()
    filename = uploaded_file.name
    with st.spinner(f"Elaborazione di '{filename}'..."):
        try:
            records = parse_schedule_excel(file_bytes)
            schedule_db_manager.update_schedule(records)
            st.success(f"Cronoprogramma '{filename}' importato!")
        except Exception as e:
            st.error(f"Errore: {e}")

with st.expander("➕ Carica un nuovo file di Cronoprogramma"):
    st.file_uploader("Seleziona file", type=["xlsx"], key="cronoprogramma_uploader", on_change=process_schedule_file_on_page, label_visibility="collapsed")
st.divider()

# --- FILTRI E BOTTONE "MOSTRA" (INTATTI) ---
st.subheader("1. Seleziona i filtri")
try:
    available_data = schedule_db_manager.get_schedule_data()
    commesse_options = sorted(pd.DataFrame(available_data)['commessa'].unique()) if available_data else []
except Exception:
    commesse_options = []
selected_commessa = st.selectbox("Filtra per Commessa", options=["Tutte"] + commesse_options)

if st.button("Mostra Cronoprogramma", type="primary"):
    commessa_filter = None if selected_commessa == "Tutte" else selected_commessa
    results = schedule_db_manager.get_schedule_data(commessa=commessa_filter)
    if not results:
        st.warning("Nessun dato trovato.")
        st.session_state['schedule_data'] = None
    else:
        st.session_state['schedule_data'] = pd.DataFrame(results)

# --- VISUALIZZAZIONE DATI (CON LA NUOVA LOGICA PER IL GRAFICO) ---
if 'schedule_data' in st.session_state and st.session_state['schedule_data'] is not None:
    df_schedule = st.session_state['schedule_data']
    st.divider()
    st.header(f"Visualizzazione per: {selected_commessa}")
    
    # --- NUOVA SEZIONE: PREPARAZIONE DATI PER IL GRAFICO ---
    # 1. Creiamo la colonna "Stato" in base alla percentuale
    def get_status(progress):
        if progress >= 100:
            return "Completato"
        elif progress > 0:
            return "In Corso"
        else:
            return "Non Iniziato"
    df_schedule['stato'] = df_schedule['stato_avanzamento'].apply(get_status)

    # 2. Creiamo un'etichetta testuale con la percentuale da mostrare sulla barra
    df_schedule['etichetta_avanzamento'] = df_schedule['stato_avanzamento'].astype(str) + '%'

    # 3. Definiamo i colori per ogni stato
    color_map = {
        "Completato": "#2ca02c",  # Verde
        "In Corso": "#ff7f0e",   # Arancione
        "Non Iniziato": "#7f7f7f" # Grigio
    }
    # -----------------------------------------------------------

    st.subheader("Diagramma di Gantt con Avanzamento")
    df_schedule['data_inizio'] = pd.to_datetime(df_schedule['data_inizio'])
    df_schedule['data_fine'] = pd.to_datetime(df_schedule['data_fine'])

    # --- GRAFICO GANTT AGGIORNATO ---
    fig = px.timeline(
        df_schedule,
        x_start="data_inizio",
        x_end="data_fine",
        y="descrizione",
        color="stato",                   # MODIFICA: il colore ora dipende dallo stato
        text="etichetta_avanzamento",    # NUOVO: aggiunge la percentuale sulla barra
        color_discrete_map=color_map,    # NUOVO: applica i nostri colori personalizzati
        title="Stato Avanzamento Attività",
        labels={"descrizione": "Attività", "stato": "Stato"}
    )
    
    # Miglioriamo la leggibilità generale
    fig.update_yaxes(autorange="reversed")
    fig.update_traces(textposition='inside') # Posiziona il testo dentro la barra
    
    # NUOVO: Aggiungiamo la griglia per una lettura più facile
    fig.update_layout(
        xaxis=dict(showgrid=True, gridcolor='lightgrey'),
        yaxis=dict(showgrid=True, gridcolor='lightgrey')
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Mostra dettaglio attività"):
        st.dataframe(df_schedule, use_container_width=True, hide_index=True)