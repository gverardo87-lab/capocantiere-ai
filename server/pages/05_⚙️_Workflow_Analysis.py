# server/pages/05_⚙️_Workflow_Analysis.py
from __future__ import annotations
import os
import sys
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.db import db_manager
from core.schedule_db import schedule_db_manager
from core.workflow_engine import (
    workflow_engine, 
    get_workflow_info, 
    analyze_resource_allocation,
    WorkRole
)

# Configurazione della pagina
st.set_page_config(
    page_title="Analisi Workflow Navale",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ Analisi Workflow e Allocazione Risorse")
st.markdown("""
Analisi professionale dei flussi di lavoro navali con ottimizzazione dell'allocazione risorse
basata su ruoli, competenze e dipendenze tra fasi lavorative.
""")

# --- TABS PER ORGANIZZARE IL CONTENUTO ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard",
    "🔄 Workflow Templates", 
    "👥 Analisi Risorse",
    "🎯 Suggerimenti Ottimizzazione"
])

# --- TAB 1: DASHBOARD ---
with tab1:
    st.header("Dashboard Allocazione Risorse")
    
    # Carica dati
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    presence_data = db_manager.get_presence_data(current_year, current_month)
    schedule_data = schedule_db_manager.get_schedule_data()
    
    if not presence_data and not schedule_data:
        st.warning("⚠️ Carica i dati delle presenze e del cronoprogramma per visualizzare l'analisi.")
    else:
        # Analisi risorse
        analysis = analyze_resource_allocation(presence_data, schedule_data)
        
        # --- METRICHE PRINCIPALI ---
        col1, col2, col3, col4 = st.columns(4)
        
        total_workers = sum(analysis['workers_by_role'].values()) if analysis['workers_by_role'] else 0
        bottlenecks = analysis['bottleneck_analysis']['bottlenecks']
        critical_bottlenecks = [b for b in bottlenecks if b['severity'] == 'CRITICO']
        
        col1.metric("👷 Totale Operai", total_workers)
        col2.metric("🚨 Colli di Bottiglia Critici", len(critical_bottlenecks))
        col3.metric("📋 Attività in Corso", len([a for a in schedule_data if a.get('stato_avanzamento', 0) < 100]))
        col4.metric("✅ Attività Completate", len([a for a in schedule_data if a.get('stato_avanzamento', 0) >= 100]))
        
        st.divider()
        
        # --- DISTRIBUZIONE OPERAI PER RUOLO ---
        if analysis['workers_by_role']:
            st.subheader("Distribuzione Operai per Ruolo")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Grafico a barre
                roles_df = pd.DataFrame([
                    {'Ruolo': role, 'Numero Operai': count}
                    for role, count in analysis['workers_by_role'].items()
                ])
                
                fig = px.bar(
                    roles_df, 
                    x='Ruolo', 
                    y='Numero Operai',
                    color='Numero Operai',
                    color_continuous_scale='Blues',
                    title="Operai Disponibili per Ruolo"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Tabella riepilogativa
                st.dataframe(
                    roles_df,
                    use_container_width=True,
                    hide_index=True
                )
        
        st.divider()
        
        # --- ANALISI COLLI DI BOTTIGLIA ---
        if bottlenecks:
            st.subheader("🚨 Analisi Colli di Bottiglia")
            
            bottleneck_df = pd.DataFrame(bottlenecks)
            
            # Colora le righe in base alla severity
            def color_severity(val):
                if val == 'CRITICO':
                    return 'background-color: #ff4444'
                elif val == 'ALTO':
                    return 'background-color: #ff9944'
                return ''
            
            styled_df = bottleneck_df.style.applymap(
                color_severity, 
                subset=['severity']
            )
            
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Alert per bottlenecks critici
            if critical_bottlenecks:
                st.error(f"""
                ⚠️ **ATTENZIONE**: {len(critical_bottlenecks)} ruoli critici mancanti!
                
                Ruoli necessari urgentemente:
                {', '.join([b['role'] for b in critical_bottlenecks])}
                """)

# --- TAB 2: WORKFLOW TEMPLATES ---
with tab2:
    st.header("🔄 Templates Workflow Navali")
    st.markdown("Visualizzazione delle fasi di lavoro standard per ogni tipo di attività")
    
    # Selezione template
    template_type = st.selectbox(
        "Seleziona Tipo Attività",
        options=['MON', 'FAM'],
        format_func=lambda x: {
            'MON': 'MON - Montaggio Scafo',
            'FAM': 'FAM - Fuori Apparato Motore'
        }[x]
    )
    
    # Mostra workflow selezionato
    workflow_info = get_workflow_info(f"{template_type}-001")
    
    if 'error' not in workflow_info:
        st.subheader(workflow_info['name'])
        st.markdown(f"*{workflow_info['description']}*")
        
        # Visualizzazione Gantt delle fasi
        phases_data = []
        for phase in workflow_info['phases']:
            phases_data.append({
                'Ruolo': phase['role'],
                'Inizio': phase['start'],
                'Fine': phase['end'],
                'Durata': phase['end'] - phase['start'],
                'Parallelo': '✅' if phase['parallel'] else '❌',
                'Richiede': ', '.join(phase['requires']) if phase['requires'] else '-'
            })
        
        phases_df = pd.DataFrame(phases_data)
        
        # Grafico Gantt
        fig = go.Figure()
        
        colors = px.colors.qualitative.Set3
        
        for i, phase in enumerate(workflow_info['phases']):
            fig.add_trace(go.Bar(
                name=phase['role'],
                y=[phase['role']],
                x=[phase['end'] - phase['start']],
                base=[phase['start']],
                orientation='h',
                marker=dict(color=colors[i % len(colors)]),
                text=f"{phase['start']}-{phase['end']}%",
                textposition='inside',
                hovertemplate=f"<b>{phase['role']}</b><br>" +
                             f"Inizio: {phase['start']}%<br>" +
                             f"Fine: {phase['end']}%<br>" +
                             f"Durata: {phase['end']-phase['start']}%<br>" +
                             f"Parallelo: {'Sì' if phase['parallel'] else 'No'}<br>" +
                             f"Richiede: {', '.join(phase['requires']) if phase['requires'] else 'Nessuno'}" +
                             "<extra></extra>"
            ))
        
        fig.update_layout(
            title=f"Fasi Workflow {workflow_info['name']}",
            xaxis_title="Percentuale Completamento (%)",
            yaxis_title="Ruolo",
            barmode='overlay',
            height=400,
            showlegend=True,
            xaxis=dict(range=[0, 100]),
            hovermode='closest'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabella dettagli
        with st.expander("Dettagli Fasi"):
            st.dataframe(phases_df, use_container_width=True, hide_index=True)
        
        # Validazione workflow
        is_valid, errors = workflow_info['validation']
        if is_valid:
            st.success("✅ Workflow valido e coerente")
        else:
            st.error(f"❌ Errori nel workflow: {', '.join(errors)}")

# --- TAB 3: ANALISI RISORSE ---
with tab3:
    st.header("👥 Analisi Dettagliata Risorse Umane")
    
    # Statistiche per ruolo
    role_stats = db_manager.get_role_statistics(current_year, current_month)
    
    if role_stats['statistics']:
        st.subheader("Statistiche Mensili per Ruolo")
        
        stats_df = pd.DataFrame(role_stats['statistics'])
        stats_df = stats_df.round(2)
        
        # Grafico ore totali per ruolo
        fig = px.treemap(
            stats_df, 
            path=['ruolo'],
            values='totale_ore',
            color='totale_straordinari',
            hover_data=['num_operai', 'media_ore_giornaliere'],
            color_continuous_scale='Reds',
            title="Distribuzione Ore Lavorate per Ruolo (dimensione = ore totali, colore = straordinari)"
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabella dettagliata
        st.dataframe(
            stats_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ruolo": "Ruolo",
                "num_operai": st.column_config.NumberColumn("N° Operai", format="%d"),
                "totale_ore": st.column_config.NumberColumn("Ore Totali", format="%.1f"),
                "totale_ore_regolari": st.column_config.NumberColumn("Ore Regolari", format="%.1f"),
                "totale_straordinari": st.column_config.NumberColumn("Straordinari", format="%.1f"),
                "totale_assenze": st.column_config.NumberColumn("Assenze", format="%.1f"),
                "media_ore_giornaliere": st.column_config.NumberColumn("Media Ore/Giorno", format="%.2f")
            }
        )
        
        # Dettaglio operai per ruolo selezionato
        st.divider()
        selected_role = st.selectbox(
            "Seleziona un ruolo per vedere il dettaglio operai",
            options=['Tutti'] + [stat['ruolo'] for stat in role_stats['statistics']]
        )
        
        if selected_role != 'Tutti':
            workers = db_manager.get_workers_by_role(selected_role)
            if workers:
                st.subheader(f"Operai - {selected_role}")
                workers_df = pd.DataFrame(workers)
                workers_df = workers_df.round(2)
                
                st.dataframe(
                    workers_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "operaio": "Nome",
                        "ruolo": "Ruolo",
                        "totale_ore": st.column_config.ProgressColumn(
                            "Ore Lavorate",
                            format="%.1f h",
                            min_value=0,
                            max_value=200
                        ),
                        "totale_straordinari": st.column_config.NumberColumn(
                            "Straordinari",
                            format="%.1f h",
                            help="Ore di straordinario accumulate"
                        ),
                        "totale_assenze": st.column_config.NumberColumn(
                            "Assenze",
                            format="%.1f h"
                        )
                    }
                )

# --- TAB 4: SUGGERIMENTI OTTIMIZZAZIONE ---
with tab4:
    st.header("🎯 Suggerimenti per Ottimizzazione Allocazione")
    
    if presence_data and schedule_data:
        # Genera suggerimenti
        suggestions = workflow_engine.suggest_optimal_schedule(
            schedule_data,
            presence_data
        )
        
        if suggestions:
            st.info(f"📋 Trovati {len(suggestions)} suggerimenti di ottimizzazione")
            
            for i, suggestion in enumerate(suggestions[:10], 1):  # Mostra primi 10
                with st.expander(f"Suggerimento {i}: Attività {suggestion['activity_id']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**Progresso Attuale**: {suggestion['current_progress']}%")
                        st.markdown(f"**Azione Suggerita**: {suggestion['action']}")
                        
                        if 'required_roles' in suggestion:
                            st.markdown(f"**Ruoli Richiesti**: {', '.join(suggestion['required_roles'])}")
                        
                        if 'next_phase_role' in suggestion:
                            st.markdown(f"**Prossima Fase**: {suggestion['next_phase_role']} (dal {suggestion['next_phase_start']}%)")
                    
                    with col2:
                        if suggestion['workers_assigned']:
                            st.markdown("**Operai Consigliati**:")
                            for worker in suggestion['workers_assigned']:
                                st.markdown(f"- {worker['name']} ({worker['role']})")
                        else:
                            st.warning("⚠️ Nessun operaio disponibile con il ruolo richiesto")
                    
                    # Mostra workflow completo per questa attività
                    workflow_info = get_workflow_info(suggestion['activity_id'])
                    if 'error' not in workflow_info:
                        active_roles = workflow_engine.get_workflow_for_activity(
                            suggestion['activity_id']
                        ).get_active_roles_at_percentage(suggestion['current_progress'])
                        
                        if active_roles:
                            st.markdown(f"**Ruoli attualmente attivi**: {', '.join([r.value for r in active_roles])}")
        else:
            st.success("✅ Allocazione risorse già ottimizzata!")
    else:
        st.warning("⚠️ Carica i dati per generare suggerimenti di ottimizzazione")

# --- SIDEBAR PER QUICK ACTIONS ---
with st.sidebar:
    st.header("⚡ Azioni Rapide")
    
    if st.button("🔄 Aggiorna Analisi", use_container_width=True):
        st.rerun()
    
    st.divider()
    
    # Quick stats
    if presence_data:
        st.metric("Operai Totali", len(set(p['operaio'] for p in presence_data)))
    
    if schedule_data:
        active = len([a for a in schedule_data if 0 < a.get('stato_avanzamento', 0) < 100])
        st.metric("Attività Attive", active)
    
    # Export dati
    st.divider()
    st.subheader("📥 Export Dati")
    
    if st.button("📊 Esporta Report Excel", use_container_width=True):
        # Qui potresti aggiungere la logica per esportare in Excel
        st.info("Funzionalità in sviluppo")