# server/pages/05_⚙️_Workflow_Analysis.py (Versione Stabile e Completa)

from __future__ import annotations
import os
import sys
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from core.workflow_engine import (
    workflow_engine,
    get_workflow_info,
    analyze_resource_allocation,
    WorkRole
)

st.set_page_config(page_title="Analisi Workflow", page_icon="⚙️", layout="wide")
st.title("⚙️ Analisi Workflow e Allocazione Risorse")
st.markdown("Dashboard per l'analisi dei flussi di lavoro, l'identificazione di colli di bottiglia e l'ottimizzazione delle risorse.")
st.divider()

# --- LEGGE I DATI DALLA MEMORIA CENTRALE ---
df_presence = st.session_state.get('df_presence', pd.DataFrame())
df_schedule = st.session_state.get('df_schedule', pd.DataFrame())

presence_data = df_presence.to_dict('records') if not df_presence.empty else None
schedule_data = df_schedule.to_dict('records') if not df_schedule.empty else None

tab1, tab2, tab3 = st.tabs(["📊 **Dashboard Riepilogativa**", "🔄 **Templates Workflow**", "🎯 **Suggerimenti di Ottimizzazione**"])

with tab1:
    if not presence_data or not schedule_data:
        st.warning("⚠️ Dati insufficienti. Carica un rapportino dalla Home e un cronoprogramma per abilitare l'analisi.")
    else:
        analysis = analyze_resource_allocation(presence_data, schedule_data)
        st.subheader("Panoramica Strategica")
        total_workers = sum(analysis['workers_by_role'].values()) if analysis.get('workers_by_role') else 0
        bottlenecks = analysis['bottleneck_analysis']['bottlenecks']
        critical_bottlenecks = [b for b in bottlenecks if b['severity'] == 'CRITICO']
        in_progress_activities = df_schedule[(df_schedule['stato_avanzamento'] > 0) & (df_schedule['stato_avanzamento'] < 100)]

        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("👷 Totale Operai Disponibili", total_workers)
        kpi2.metric("🚨 Colli di Bottiglia Critici", len(critical_bottlenecks), help="Ruoli richiesti ma senza personale.")
        kpi3.metric("📈 Attività in Corso", len(in_progress_activities))
        st.divider()

        col_dist, col_bottle = st.columns(2)
        with col_dist:
            st.subheader("Distribuzione Risorse per Ruolo")
            if analysis['workers_by_role']:
                roles_df = pd.DataFrame([{'Ruolo': role, 'Numero Operai': count} for role, count in analysis['workers_by_role'].items()])
                fig = px.treemap(roles_df, path=['Ruolo'], values='Numero Operai', color='Numero Operai', color_continuous_scale='Blues', title="Operai Disponibili per Ruolo")
                fig.update_layout(margin=dict(t=50, l=25, r=25, b=25))
                st.plotly_chart(fig, use_container_width=True)
        with col_bottle:
            st.subheader("Analisi Colli di Bottiglia")
            if bottlenecks:
                bottleneck_df = pd.DataFrame(bottlenecks)
                def highlight_severity(row):
                    color = ''
                    if row.severity == 'CRITICO': color = '#8B0000'
                    elif row.severity == 'ALTO': color = '#FF8C00'
                    return [f'background-color: {color}' for _ in row]
                st.dataframe(bottleneck_df.style.apply(highlight_severity, axis=1), use_container_width=True, hide_index=True,
                             column_config={"role": "Ruolo Richiesto", "severity": "Criticità", "demand_hours": st.column_config.NumberColumn("Ore Richieste", format="%.0f h"),
                                            "available_workers": "Operai Disp.", "shortage_hours": st.column_config.NumberColumn("Carenza Ore", format="%.0f h")})
            else:
                st.success("✅ Nessun collo di bottiglia rilevato.")

with tab2:
    st.subheader("Visualizzazione Fasi di Lavoro Standard")
    template_type = st.selectbox("Seleziona tipo attività", ['MON', 'FAM'], format_func=lambda x: {'MON': 'Montaggio Scafo', 'FAM': 'Fuori Apparato Motore'}[x])
    workflow_info = get_workflow_info(f"{template_type}-001")
    if 'error' not in workflow_info:
        st.markdown(f"#### {workflow_info['name']}")
        st.caption(f"_{workflow_info['description']}_")
        phases_df = pd.DataFrame(workflow_info['phases'])
        fig = go.Figure()
        colors = px.colors.qualitative.Plotly
        for i, phase in phases_df.iterrows():
            fig.add_trace(go.Bar(y=[phase['role']], x=[phase['end'] - phase['start']], base=[phase['start']], orientation='h', name=phase['role'], marker=dict(color=colors[i % len(colors)]), text=f"{phase['start']}% → {phase['end']}%", textposition='inside', insidetextanchor='middle'))
        fig.update_layout(title_text=f"Fasi Workflow per attività di tipo {template_type}", xaxis_title="Percentuale di Completamento Attività (%)", yaxis_title="Ruolo Coinvolto", barmode='stack', yaxis={'categoryorder':'total ascending'}, showlegend=False, plot_bgcolor=st.get_option("theme.secondaryBackgroundColor"), paper_bgcolor='rgba(0,0,0,0)', font_color=st.get_option("theme.textColor"), xaxis=dict(range=[0, 100]))
        st.plotly_chart(fig, use_container_width=True)
        is_valid, errors = workflow_info['validation']
        if is_valid:
            st.success("✅ Validazione workflow superata.")
        else:
            st.error(f"❌ Errori nel workflow: {', '.join(errors)}")

with tab3:
    st.subheader("Azioni Consigliate per Ottimizzare l'Allocazione")
    if presence_data and schedule_data:
        suggestions = workflow_engine.suggest_optimal_schedule(schedule_data, presence_data)
        if suggestions:
            st.info(f"Trovati **{len(suggestions)}** suggerimenti. Ecco i più importanti:")
            for i, suggestion in enumerate(suggestions[:5], 1):
                with st.container(border=True):
                    st.markdown(f"**Suggerimento #{i}: Attività `{suggestion['activity_id']}`** (Avanzamento: {suggestion['current_progress']}%)")
                    col_action, col_workers = st.columns(2)
                    with col_action:
                        st.markdown(f"**Azione:** `{suggestion['action']}`")
                        if 'next_phase_role' in suggestion: st.markdown(f"**Prossima Fase:** Iniziare lavoro del **{suggestion['next_phase_role']}**")
                        if 'required_roles' in suggestion: st.markdown(f"**Ruoli Richiesti:** {', '.join(suggestion['required_roles'])}")
                    with col_workers:
                        if suggestion['workers_assigned']:
                            st.markdown("**Operai Consigliati:**")
                            for worker in suggestion['workers_assigned']: st.markdown(f"- 👷 {worker['name']} ({worker['role']})")
                        else:
                            st.warning("⚠️ Nessun operaio disponibile con il ruolo richiesto.")
        else:
            st.success("✅ Allocazione risorse già ottimale!")
    else:
        st.warning("⚠️ Carica i dati per generare suggerimenti.")