# server/pages/05_⚙️_Workflow_Analysis.py (VERSIONE SINCRONIZZATA E STABILE)

from __future__ import annotations
import os
import sys
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.workflow_engine import get_workflow_info, analyze_resource_allocation

st.set_page_config(page_title="Analisi Strategica Workflow", page_icon="⚙️", layout="wide")
st.title("⚙️ Analisi Strategica Workflow e Risorse")
st.markdown("Dashboard per l'analisi strategica del fabbisogno di ore, l'identificazione di colli di bottiglia futuri e l'ottimizzazione delle risorse.")
st.divider()

df_presence = st.session_state.get('df_presence', pd.DataFrame())
df_schedule = st.session_state.get('df_schedule', pd.DataFrame())
presence_data = df_presence.to_dict('records') if not df_presence.empty else []
schedule_data = df_schedule.to_dict('records') if not df_schedule.empty else []

analysis_results = None
if presence_data and schedule_data:
    try:
        analysis_results = analyze_resource_allocation(presence_data, schedule_data)
    except Exception as e:
        st.error(f"Errore critico durante l'analisi: {e}")
        st.info("Controllare la logica in 'core/workflow_engine.py'.")

tab1, tab2, tab3 = st.tabs(["📊 **Dashboard Strategica**", "🔄 **Templates Workflow**", "🎯 **Suggerimenti**"])

with tab1:
    st.header("Dashboard di Analisi Strategica")
    if analysis_results and 'error' not in analysis_results:
        b_info = analysis_results.get('bottleneck_analysis', {})
        bottlenecks = b_info.get('bottlenecks', [])
        demand = b_info.get('total_demand', {})
        workers = analysis_results.get('workers_by_role', {})
        
        st.subheader("Panoramica Fabbisogno Futuro")
        crit_b = [b for b in bottlenecks if b.get('severity') == 'CRITICO']
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("⏱️ Fabbisogno Ore Residue", f"{sum(demand.values()):,.0f} h")
        kpi2.metric("🚨 Colli di Bottiglia Critici", len(crit_b))
        kpi3.metric("👷 Operai Disponibili", sum(workers.values()))
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Domanda di Lavoro per Ruolo (Ore)")
            if demand:
                df = pd.DataFrame(list(demand.items()), columns=['Ruolo', 'Ore']).sort_values('Ore', ascending=False)
                fig = px.bar(df, x='Ruolo', y='Ore', title="Fabbisogno ore per completare i lavori", text_auto='.2s')
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Analisi Colli di Bottiglia")
            if bottlenecks:
                st.dataframe(pd.DataFrame(bottlenecks), use_container_width=True, hide_index=True, column_config={"role": "Ruolo", "severity": "Criticità", "demand_hours": "Ore Richieste", "available_workers": "Operai Disp.", "shortage_hours": "Carenza Ore"})
            else:
                st.success("✅ Nessun collo di bottiglia rilevato.")
    else:
        st.warning("⚠️ Dati insufficienti. Carica rapportino e cronoprogramma.")

with tab2:
    st.header("Visualizzazione Workflow Standard")
    template_type = st.selectbox("Seleziona tipo attività", ['MON', 'FAM'], format_func=lambda x: {'MON': 'Montaggio Scafo', 'FAM': 'Fuori Apparato Motore'}[x])
    wf_info = get_workflow_info(f"{template_type}-001")
    if 'error' not in wf_info:
        st.markdown(f"#### {wf_info.get('name', 'N/D')} (Monte Ore Standard: {wf_info.get('total_hours', 0)}h)")
        df = pd.DataFrame(wf_info.get('phases', []))
        if not df.empty and 'hours' in df.columns:
            fig = px.bar(df, x="hours", y="role", orientation='h', title=f"Fasi per Attività '{template_type}'", text="hours", color="role")
            fig.update_layout(yaxis_title="Ruolo", xaxis_title="Ore Standard", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(f"Impossibile caricare info workflow: {wf_info.get('error')}")

with tab3:
    st.header("Suggerimenti Allocazione Risorse")
    st.info("Funzionalità in fase di sviluppo.")