# server/pages/01_📊_Reportistica.py (Versione Enterprise con Analisi Budget e Grafico Criticità)

from __future__ import annotations
import os
import sys
from datetime import datetime
import pandas as pd
import numpy as np # Importa numpy per il calcolo dei giorni lavorativi
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
                # --- CORREZIONE QUI ---
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
        tab_activity, tab_worker = st.tabs(["**Analisi Budget per Attività**", "**Consuntivo per Operaio**"])

        with tab_activity:
            activity_summary = df_filtered.groupby('id_attivita').agg(
                ore_totali=('ore_lavorate', 'sum')
            ).reset_index().round(1)
            
            if not df_schedule.empty:
                # --- INIZIO MIGLIORIA GRAFICA E LOGICA ---
                activity_summary = pd.merge(
                    activity_summary,
                    df_schedule[['id_attivita', 'descrizione', 'data_inizio', 'data_fine']],
                    on='id_attivita', how='left'
                )
                activity_summary.dropna(subset=['data_inizio', 'data_fine'], inplace=True)
                activity_summary['data_inizio'] = pd.to_datetime(activity_summary['data_inizio'])
                activity_summary['data_fine'] = pd.to_datetime(activity_summary['data_fine'])

                activity_summary['ore_previste'] = np.busday_count(
                    activity_summary['data_inizio'].values.astype('M8[D]'),
                    activity_summary['data_fine'].values.astype('M8[D]')
                ) * 20
                activity_summary['ore_previste'] = activity_summary['ore_previste'].replace(0, 20)

                activity_summary['scostamento'] = activity_summary['ore_totali'] - activity_summary['ore_previste']
                activity_summary['perc_consumo'] = (activity_summary['ore_totali'] / activity_summary['ore_previste'] * 100).astype(int)

                display_df = activity_summary[[
                    'id_attivita', 'descrizione', 'ore_previste',
                    'ore_totali', 'scostamento', 'perc_consumo'
                ]].sort_values(by='scostamento', ascending=False)

                st.subheader("Cruscotto di Controllo Budget")
                st.dataframe(
                    display_df,
                    use_container_width=True, hide_index=True,
                    column_config={
                        "id_attivita": "ID", "descrizione": "Descrizione Attività",
                        "ore_previste": st.column_config.NumberColumn("Ore Previste", format="%.1f h"),
                        "ore_totali": st.column_config.NumberColumn("Ore Consuntivate", format="%.1f h"),
                        "scostamento": st.column_config.NumberColumn("Scostamento", help="Ore in più (+) o in meno (-) rispetto al budget", format="%+.1f h"),
                        "perc_consumo": st.column_config.ProgressColumn(
                            "Consumo Budget",
                            help="Percentuale di ore usate. Diventa rosso sopra il 100%.",
                            format="%d%%", min_value=0, max_value=200,
                        ),
                    }
                )

                # --- NUOVO GRAFICO DI ANALISI CRITICITÀ ---
                st.subheader("Top 10 Attività per Sforamento Budget (Ore)")
                df_over_budget = display_df[display_df['scostamento'] > 0].head(10).sort_values(by='scostamento')
                
                if not df_over_budget.empty:
                    fig = px.bar(
                        df_over_budget,
                        x='scostamento',
                        y='descrizione',
                        orientation='h',
                        title="Attività che hanno richiesto più ore del previsto",
                        text='scostamento',
                        color='scostamento',
                        color_continuous_scale='Reds'
                    )
                    fig.update_traces(texttemplate='+%{text:.1f}h', textposition='outside')
                    fig.update_layout(
                        yaxis_title=None, xaxis_title="Ore di Sforamento",
                        showlegend=False,
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        font_color=st.get_option("theme.textColor")
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.success("✅ Ottimo! Nessuna attività ha sforato il budget nel periodo selezionato.")
                # --- FINE MIGLIORIA ---
            else:
                st.info("Carica un cronoprogramma per abilitare l'analisi del budget.")
                st.dataframe(activity_summary, use_container_width=True, hide_index=True, column_config={
                    "id_attivita": "ID Attività",
                    "ore_totali": st.column_config.BarChartColumn("Ore Totali Consuntivate"),
                })

        with tab_worker:
            worker_summary = df_filtered.groupby(['operaio', 'ruolo']).agg(
                ore_totali=('ore_lavorate', 'sum'),
                straordinari_totali=('ore_straordinario', 'sum'),
                attivita_lavorate=('id_attivita', 'nunique')
            ).reset_index().round(1).sort_values(by='ore_totali', ascending=False)
            
            st.dataframe(worker_summary, use_container_width=True, hide_index=True, column_config={
                "operaio": "Operaio", "ruolo": "Ruolo",
                "ore_totali": st.column_config.ProgressColumn(
                    "Ore Totali Lavorate", 
                    format="%.1f h", 
                    min_value=0, 
                    max_value=worker_summary['ore_totali'].max() if not worker_summary.empty else 1,
                ),
                "straordinari_totali": "Ore Straordinario",
                "attivita_lavorate": "N° Attività"
            })


# --- FINE FILE ---

