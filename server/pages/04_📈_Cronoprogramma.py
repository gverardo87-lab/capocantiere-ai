# server/pages/04_📈_Cronoprogramma.py (versione "Control Room" - Corretta e Pulita)

from __future__ import annotations
import os
import sys
from datetime import date, datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.schedule_db import schedule_db_manager
from tools.schedule_extractor import parse_schedule_excel, ScheduleParsingError

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Control Room Cronoprogramma", page_icon="📈", layout="wide")

st.title("📈 Control Room Cronoprogramma")
st.markdown("Dashboard avanzata per il monitoraggio e l'analisi delle attività di cantiere.")

def process_schedule_file_on_page():
    # ... (logica invariata) ...
    uploaded_file = st.session_state.get("cronoprogramma_uploader")
    if uploaded_file is None: return
    file_bytes = uploaded_file.getvalue()
    try:
        records = parse_schedule_excel(file_bytes)
        schedule_db_manager.update_schedule(records)
        st.success(f"Cronoprogramma '{uploaded_file.name}' importato!")
    except Exception as e:
        st.error(f"Errore durante l'elaborazione del file: {e}")

# --- SEZIONE DI CONTROLLO AVANZATA ---
with st.expander("Filtri e Opzioni di Caricamento", expanded=True):
    col_upload, col_date_filters = st.columns([1, 2])

    with col_upload:
        st.subheader("Carica File")
        st.file_uploader(
            "Seleziona un nuovo cronoprogramma", type=["xlsx"],
            key="cronoprogramma_uploader", on_change=process_schedule_file_on_page,
            label_visibility="collapsed"
        )

    with col_date_filters:
        st.subheader("Filtra per Intervallo di Date")
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
        
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            date_from = st.date_input("Da data", value=min_date, min_value=min_date, max_value=max_date)
        with dcol2:
            date_to = st.date_input("A data", value=max_date, min_value=min_date, max_value=max_date)

    if st.button("Analizza Cronoprogramma", type="primary", use_container_width=True):
        all_results = schedule_db_manager.get_schedule_data()
        if not all_results:
            st.warning("Nessun dato trovato nel database.")
            st.session_state['schedule_data'] = None
        else:
            df = pd.DataFrame(all_results)
            df['data_inizio'] = pd.to_datetime(df['data_inizio'])
            df['data_fine'] = pd.to_datetime(df['data_fine'])
            
            filtered_df = df[(df['data_inizio'].dt.date <= date_to) & (df['data_fine'].dt.date >= date_from)]
            st.session_state['schedule_data'] = filtered_df
            st.session_state['schedule_dates'] = (date_from, date_to)

# --- VISUALIZZAZIONE DATI ---
if 'schedule_data' in st.session_state and st.session_state['schedule_data'] is not None:
    df_schedule = st.session_state['schedule_data']
    
    if df_schedule.empty:
        st.info("Nessuna attività trovata nell'intervallo di date selezionato.")
    else:
        date_from, date_to = st.session_state['schedule_dates']
        st.header(f"Analisi dal {date_from.strftime('%d/%m/%Y')} al {date_to.strftime('%d/%m/%Y')}")
        st.divider()

        # --- LOGICA PREPARAZIONE DATI ---
        def get_status(progress):
            if progress >= 100: return "Completato"
            elif progress > 0: return "In Corso"
            else: return "Non Iniziato"
        df_schedule['stato'] = df_schedule['stato_avanzamento'].apply(get_status)

        # --- KPI DASHBOARD ---
        st.subheader("Metriche Chiave (KPIs)")
        total_activities = len(df_schedule)
        status_counts = df_schedule['stato'].value_counts()
        completed = status_counts.get("Completato", 0)
        in_progress = status_counts.get("In Corso", 0)
        not_started = status_counts.get("Non Iniziato", 0)
        
        df_schedule['durata'] = (df_schedule['data_fine'] - df_schedule['data_inizio']).apply(lambda x: x.days) + 1
        total_days = df_schedule['durata'].sum()
        weighted_progress = (df_schedule['stato_avanzamento'] * df_schedule['durata']).sum() / total_days if total_days > 0 else 0

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Totale Attività", f"{total_activities}")
        kpi2.metric("✅ Completate", f"{completed}", f"{round(completed/total_activities*100)}%")
        kpi3.metric("⏳ In Corso", f"{in_progress}", f"{round(in_progress/total_activities*100)}%")
        kpi4.metric("📅 Non Iniziate", f"{not_started}", f"{round(not_started/total_activities*100)}%")
        
        st.progress(int(weighted_progress), text=f"Avanzamento Medio Ponderato del Progetto: {weighted_progress:.1f}%")
        st.divider()

        # --- FILTRI INTERATTIVI E GRAFICO ---
        col_filter, col_gantt = st.columns([1, 3])
        
        with col_filter:
            st.subheader("Filtri di Visualizzazione")
            status_filter = st.multiselect(
                "Filtra per Stato",
                options=df_schedule['stato'].unique(),
                default=df_schedule['stato'].unique(),
                placeholder="Seleziona stati"
            )
            df_filtered_gantt = df_schedule[df_schedule['stato'].isin(status_filter)].copy()
            df_filtered_gantt['etichetta_avanzamento'] = df_filtered_gantt['stato_avanzamento'].astype(str) + '%'

        with col_gantt:
            st.subheader("Diagramma di Gantt Dettagliato")
            if df_filtered_gantt.empty:
                st.warning("Nessuna attività corrisponde ai filtri selezionati.")
            else:
                color_map = {
                    "Completato": "#28a745",
                    "In Corso": st.get_option("theme.primaryColor"),
                    "Non Iniziato": "#6c757d"
                }

                fig = px.timeline(
                    df_filtered_gantt, x_start="data_inizio", x_end="data_fine", y="descrizione",
                    color="stato", text="etichetta_avanzamento", color_discrete_map=color_map,
                    height=max(400, len(df_filtered_gantt) * 35),
                    labels={"descrizione": "Attività", "stato": "Stato"}
                )

                fig.update_traces(
                    textfont_size=12, textposition='inside',
                    marker_line_color='rgb(8,48,107)', marker_line_width=1.5, opacity=0.9
                )
                fig.update_yaxes(autorange="reversed", tickfont_size=12)
                fig.update_xaxes(tickfont_size=12, gridcolor='#31333F')
                fig.update_layout(
                    title_text=None, font_color=st.get_option("theme.textColor"),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=st.get_option("theme.secondaryBackgroundColor"),
                    xaxis_title="Linea del Tempo", yaxis_title=None,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )

                st.plotly_chart(fig, use_container_width=True)

        # La tabella di dettaglio rimane disponibile
        with st.expander("Mostra dettaglio tabellare completo (non filtrato)"):
            st.dataframe(df_schedule, use_container_width=True, hide_index=True, column_config={
                "data_inizio": st.column_config.DateColumn("Data Inizio", format="DD/MM/YYYY"),
                "data_fine": st.column_config.DateColumn("Data Fine", format="DD/MM/YYYY")
            })