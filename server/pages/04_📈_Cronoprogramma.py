# server/pages/04_📈_Cronoprogramma.py (Versione Definitiva Anti-Errore)

from __future__ import annotations
import os
import sys
from datetime import date, datetime
import streamlit as st
import pandas as pd
import plotly.express as px

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.schedule_db import schedule_db_manager
from tools.schedule_extractor import parse_schedule_excel

st.set_page_config(page_title="Control Room Cronoprogramma", page_icon="📈", layout="wide")

st.title("📈 Control Room Cronoprogramma")
st.markdown("Dashboard avanzata per il monitoraggio e l'analisi delle attività di cantiere.")

# --- LEGGE I DATI DALLA MEMORIA CENTRALE ---
df_schedule = st.session_state.get('df_schedule', pd.DataFrame())

def process_schedule_file_on_page():
    uploaded_file = st.session_state.get("cronoprogramma_uploader")
    if uploaded_file:
        try:
            records = parse_schedule_excel(uploaded_file.getvalue())
            schedule_db_manager.update_schedule(records)
            # Segnala alla Home Page che deve ricaricare tutto
            st.session_state['force_rerun'] = True
        except Exception as e:
            st.error(f"Errore durante l'elaborazione del file: {e}")

# --- UPLOADER ---
with st.expander("➕ Carica un nuovo file di Cronoprogramma"):
    st.file_uploader(
        "Seleziona file Excel del cronoprogramma",
        type=["xlsx"],
        key="cronoprogramma_uploader",
        on_change=process_schedule_file_on_page
    )

if df_schedule.empty:
    st.warning("Nessun dato del cronoprogramma trovato. Carica un file per iniziare.")
else:
    # --- GESTIONE DATE CORRETTA E DEFINITIVA ---
    # 1. Convertiamo in Timestamp di Pandas. Questo è il formato per i CALCOLI.
    df_schedule['data_inizio'] = pd.to_datetime(df_schedule['data_inizio'])
    df_schedule['data_fine'] = pd.to_datetime(df_schedule['data_fine'])
    
    # 2. Per il filtro dell'interfaccia utente, usiamo l'oggetto .date
    min_date_filter = df_schedule['data_inizio'].min().date()
    date_from_filter = st.date_input("Mostra attività a partire da:", min_date_filter)
    
    # 3. Filtriamo confrontando le parti 'date' dei nostri Timestamp
    df_schedule_filtered = df_schedule[df_schedule['data_fine'].dt.date >= date_from_filter].copy()

    st.header(f"Analisi dal {date_from_filter.strftime('%d/%m/%Y')}")
    st.divider()

    def get_status(progress):
        progress = int(progress)
        if progress >= 100: return "Completato"
        elif progress > 0: return "In Corso"
        else: return "Non Iniziato"
    df_schedule_filtered['stato'] = df_schedule_filtered['stato_avanzamento'].apply(get_status)

    st.subheader("Metriche Chiave (KPIs)")
    total_activities = len(df_schedule_filtered)
    status_counts = df_schedule_filtered['stato'].value_counts()
    completed = status_counts.get("Completato", 0)
    in_progress = status_counts.get("In Corso", 0)
    not_started = status_counts.get("Non Iniziato", 0)
    
    # --- CALCOLO DURATA CORRETTO E DEFINITIVO ---
    # 4. Usiamo .dt.days sui Timedelta risultanti. Ora FUNZIONA.
    df_schedule_filtered['durata'] = (df_schedule_filtered['data_fine'] - df_schedule_filtered['data_inizio']).dt.days + 1
    total_days = df_schedule_filtered['durata'].sum()
    weighted_progress = (df_schedule_filtered['stato_avanzamento'] * df_schedule_filtered['durata']).sum() / total_days if total_days > 0 else 0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Totale Attività", f"{total_activities}")
    kpi2.metric("✅ Completate", f"{completed}", f"{round(completed/total_activities*100)}%" if total_activities > 0 else "0%")
    kpi3.metric("⏳ In Corso", f"{in_progress}", f"{round(in_progress/total_activities*100)}%" if total_activities > 0 else "0%")
    kpi4.metric("📅 Non Iniziate", f"{not_started}", f"{round(not_started/total_activities*100)}%" if total_activities > 0 else "0%")
    
    st.progress(int(weighted_progress), text=f"Avanzamento Medio Ponderato: {weighted_progress:.1f}%")
    st.divider()

    st.subheader("Diagramma di Gantt Dettagliato")
    df_schedule_filtered['etichetta_avanzamento'] = df_schedule_filtered['stato_avanzamento'].astype(str) + '%'
    color_map = {"Completato": "#28a745", "In Corso": st.get_option("theme.primaryColor"), "Non Iniziato": "#6c757d"}
    
    # Il grafico viene creato usando le colonne Timestamp, che è corretto.
    fig = px.timeline(
        df_schedule_filtered, x_start="data_inizio", x_end="data_fine", 
        y="descrizione", color="stato", text="etichetta_avanzamento", 
        color_discrete_map=color_map, height=max(400, len(df_schedule_filtered) * 35)
    )
    
    fig.update_yaxes(autorange="reversed") # Le attività più recenti in alto
    fig.update_traces(textposition='inside', insidetextanchor='middle')
    fig.update_layout(margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, use_container_width=True)
    st.divider()
    st.subheader("Dettaglio Attività")
    st.dataframe(df_schedule_filtered.drop(columns=['etichetta_avanzamento', 'durata']), use_container_width=True)  
    st.markdown(f"**Totale Attività Visualizzate:** {len(df_schedule_filtered)}")
# --- INIZIALIZZAZIONE DATI ALL'AVVIO DELL'APP (Versione Definitiva Anti-Errore) ---
def initialize_data():
    if not st.session_state.get('data_loaded', False):
        schedule_data = schedule_db_manager.get_schedule_data()
        st.session_state.df_schedule = pd.DataFrame(schedule_data) if schedule_data else pd.DataFrame()
        
        st.session_state.data_loaded = True
        st.session_state['force_rerun'] = False
# Esegui la funzione di caricamento all'avvio dell'app
initialize_data()
# Controlla se una sotto-pagina ha richiesto un refresh
if st.session_state.pop('force_rerun', False):
    st.session_state.pop('data_loaded', None)
    initialize_data() # Forza il ricaricamento dei dati
    st.rerun()  

