# server/pages/04_📈_Cronoprogramma.py (Versione Definitiva e Completa)

from __future__ import annotations
import os
import sys
from datetime import date, datetime, timedelta
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

# --- FUNZIONE PER LA TUA LOGICA DEI COLORI ---
def get_progress_color(progress):
    progress = int(progress)
    if progress >= 100:
        return "#28a745"  # Verde (Completato)
    elif progress >= 70:
        return "#3B82F6"  # Azzurro (70-99%)
    elif progress >= 50:
        return "#EF4444"  # Rosso (50-69%)
    else: # 0-49
        return "#F59E0B"  # Arancione

# --- LEGGE I DATI DALLA MEMORIA CENTRALE ---
df_schedule_original = st.session_state.get('df_schedule', pd.DataFrame())

def process_schedule_file_on_page():
    uploaded_file = st.session_state.get("cronoprogramma_uploader")
    if uploaded_file:
        try:
            records = parse_schedule_excel(uploaded_file.getvalue())
            schedule_db_manager.update_schedule(records)
            st.session_state['force_rerun'] = True # Segnala alla Home Page che deve ricaricare tutto
            st.toast("✅ Cronoprogramma importato!", icon="📈")
        except Exception as e:
            st.error(f"Errore durante l'elaborazione del file: {e}")

if df_schedule_original.empty:
    with st.expander("➕ Carica un nuovo file di Cronoprogramma"):
        st.file_uploader("Seleziona file Excel", type=["xlsx"], key="cronoprogramma_uploader", on_change=process_schedule_file_on_page)
    st.warning("Nessun dato del cronoprogramma trovato. Carica un file per iniziare.")
else:
    df_schedule = df_schedule_original.copy()
    df_schedule['data_inizio'] = pd.to_datetime(df_schedule['data_inizio'])
    df_schedule['data_fine'] = pd.to_datetime(df_schedule['data_fine'])

    # --- PANNELLO DI CONTROLLO CON BOTTONE "APPLICA" ---
    st.subheader("Pannello di Controllo")
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 1, 2])
        min_date_filter = df_schedule['data_inizio'].min().date()
        max_date_filter = df_schedule['data_fine'].max().date()

        if 'cron_date_from' not in st.session_state or st.session_state.cron_date_from < min_date_filter:
            st.session_state.cron_date_from = min_date_filter
        if 'cron_date_to' not in st.session_state or st.session_state.cron_date_to > max_date_filter:
            st.session_state.cron_date_to = max_date_filter

        with c1:
            date_from = st.date_input("Da data", st.session_state.cron_date_from, min_value=min_date_filter, max_value=max_date_filter)
        with c2:
            date_to = st.date_input("A data", st.session_state.cron_date_to, min_value=min_date_filter, max_value=max_date_filter)

        with c3:
            st.write("")
            st.write("")
            if st.button("Applica Filtri", type="primary", use_container_width=True):
                st.session_state.cron_date_from = date_from
                st.session_state.cron_date_to = date_to
                st.rerun()

    # --- FILTRAGGIO DATI BASATO SUI VALORI IN SESSIONE ---
    df_filtered = df_schedule[
        (df_schedule['data_inizio'].dt.date <= st.session_state.cron_date_to) &
        (df_schedule['data_fine'].dt.date >= st.session_state.cron_date_from)
    ].copy()

    st.header(f"Analisi dal {st.session_state.cron_date_from.strftime('%d/%m/%Y')} al {st.session_state.cron_date_to.strftime('%d/%m/%Y')}")
    st.divider()

    if df_filtered.empty:
        st.info("Nessuna attività trovata nell'intervallo di date selezionato.")
    else:
        # --- PREPARAZIONE DATI PER IL GRAFICO E KPI ---
        def get_status(p): return "Completato" if int(p) >= 100 else "In Corso" if int(p) > 0 else "Non Iniziato"
        df_filtered['stato'] = df_filtered['stato_avanzamento'].apply(get_status)

        # --- GANTT CHART CON NUOVA LOGICA STABILE ---
        st.subheader("Gantt Chart Interattivo con Avanzamento")
        
        gantt_data = []
        for _, row in df_filtered.iterrows():
            desc = row['descrizione']
            start = row['data_inizio']
            end = row['data_fine']
            progress = row['stato_avanzamento']
            
            # Calcolo corretto della data di fine del progresso
            duration = (end - start).total_seconds()
            if duration > 0:
                progress_end_date = start + timedelta(seconds=(duration * (progress / 100)))
            else:
                progress_end_date = start

            # Segmento AVANZAMENTO (con il colore personalizzato)
            if progress > 0:
                gantt_data.append(dict(Task=desc, Start=start, Finish=progress_end_date, Segmento=f'Avanzamento', Color=get_progress_color(progress), Progress=progress))
            # Segmento RIMANENTE (sempre grigio)
            if progress < 100:
                gantt_data.append(dict(Task=desc, Start=progress_end_date, Finish=end, Segmento='Rimanente', Color='rgba(108, 117, 125, 0.5)', Progress=progress))
            # Se un'attività è a 0%, disegna solo la barra grigia per l'intera durata
            if progress == 0:
                gantt_data.append(dict(Task=desc, Start=start, Finish=end, Segmento='Rimanente', Color='rgba(108, 117, 125, 0.5)', Progress=progress))

        if gantt_data:
            df_gantt = pd.DataFrame(gantt_data)
            
            fig = px.timeline(
                df_gantt,
                x_start="Start", x_end="Finish", y="Task",
                color="Color",
                custom_data=['Progress']
            )
            
            # Forziamo Plotly a usare i colori esatti che gli passiamo
            fig.for_each_trace(lambda t: t.update(name=t.name.split("=")[-1]))
            
            fig.update_traces(hovertemplate="<b>%{y}</b><br>Progresso: %{customdata[0]}%<extra></extra>")
            fig.update_layout(
                height=max(400, len(df_filtered['descrizione'].unique()) * 35),
                yaxis_title=None, xaxis_title="Linea del Tempo",
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor=st.get_option("theme.secondaryBackgroundColor"),
                font_color=st.get_option("theme.textColor"),
                showlegend=False,
                xaxis_type='date'
            )
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nessuna attività da visualizzare nel grafico.")
            
        st.divider()

        # --- KPI E TABELLA DETTAGLIO (CODICE COMPLETO) ---
        st.subheader("Metriche Chiave e Dettaglio")

        total_tasks = len(df_filtered)
        completed = len(df_filtered[df_filtered['stato'] == 'Completato'])
        in_progress = len(df_filtered[df_filtered['stato'] == 'In Corso'])
        oggi = pd.Timestamp.now(tz=df_filtered['data_inizio'].dt.tz)
        delayed = len(df_filtered[
            ((df_filtered['stato'] == 'In Corso') & (df_filtered['data_fine'] < oggi)) |
            ((df_filtered['stato'] == 'Non Iniziato') & (df_filtered['data_inizio'] < oggi))
        ])

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Totale Attività", total_tasks)
        kpi2.metric("✅ Completate", completed, f"{round(completed/total_tasks*100) if total_tasks > 0 else 0}%")
        kpi3.metric("⏳ In Corso", in_progress, f"{round(in_progress/total_tasks*100) if total_tasks > 0 else 0}%")
        kpi4.metric("🚨 In Ritardo", delayed, delta_color="inverse")

        with st.expander("Mostra dettaglio tabellare"):
            st.dataframe(
                df_filtered, use_container_width=True, hide_index=True,
                column_config={
                    "data_inizio": st.column_config.DateColumn("Data Inizio", format="DD/MM/YYYY"),
                    "data_fine": st.column_config.DateColumn("Data Fine", format="DD/MM/YYYY"),
                    "stato_avanzamento": st.column_config.ProgressColumn("Avanzamento", format="%d%%")
                }
            )

    # --- UPLOADER IN FONDO ALLA PAGINA ---
    with st.expander("➕ Carica un nuovo file di Cronoprogramma", expanded=False):
        st.file_uploader("Seleziona file", type=["xlsx"], key="cronoprogramma_uploader_bottom", on_change=process_schedule_file_on_page)