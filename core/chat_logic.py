# core/chat_logic.py - Full AI Assistant per CapoCantiere
from __future__ import annotations
import json
import sys
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
from ollama import Client

# Import dei nostri moduli
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.config import OLLAMA_MODEL
from core.db import db_manager
from core.schedule_db import schedule_db_manager
from core.knowledge_chain import get_expert_response

class CapoCantiereEngine:
    """
    Motore AI avanzato che integra tutti i dati aziendali per fornire
    supporto decisionale intelligente al CapoCantiere.
    """
    
    def __init__(self):
        self.client = Client()
    
    def get_current_situation(self) -> Dict[str, Any]:
        """Raccoglie lo stato attuale completo del cantiere."""
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Dati dalle presenze
        presenze_data = db_manager.get_presence_data(current_year, current_month)
        presenze_df = pd.DataFrame(presenze_data) if presenze_data else pd.DataFrame()
        
        # Dati dal cronoprogramma
        schedule_data = schedule_db_manager.get_schedule_data()
        schedule_df = pd.DataFrame(schedule_data) if schedule_data else pd.DataFrame()
        
        # Calcola KPI in tempo reale
        situation = {
            "timestamp": datetime.now().isoformat(),
            "presenze_summary": self._analyze_presenze(presenze_df),
            "cronoprogramma_summary": self._analyze_schedule(schedule_df),
            "alerts": self._detect_alerts(presenze_df, schedule_df),
            "available_operai": self._get_available_workers(presenze_df),
            "critical_activities": self._get_critical_activities(schedule_df)
        }
        
        return situation
    
    def _analyze_presenze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analizza i dati delle presenze per KPI operativi."""
        if df.empty:
            return {"status": "no_data", "message": "Nessun dato presenze disponibile"}
        
        # Calcoli aggregati
        total_worked = df['ore_lavorate'].sum()
        total_overtime = df['ore_straordinario'].sum()
        avg_daily_hours = df.groupby('data')['ore_lavorate'].sum().mean()
        
        # Top performers e workload
        operai_stats = df.groupby('operaio').agg({
            'ore_lavorate': 'sum',
            'ore_straordinario': 'sum',
            'ore_assenza': 'sum'
        }).round(2)
        
        # Operai con troppo carico
        high_workload = operai_stats[operai_stats['ore_straordinario'] > 20].index.tolist()
        
        return {
            "total_hours_worked": round(total_worked, 2),
            "total_overtime": round(total_overtime, 2),
            "average_daily_productivity": round(avg_daily_hours, 2),
            "active_workers": len(operai_stats),
            "high_workload_workers": high_workload,
            "top_performers": operai_stats.sort_values('ore_lavorate', ascending=False).head(5).to_dict('index')
        }
    
    def _analyze_schedule(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analizza il cronoprogramma per identificare criticità."""
        if df.empty:
            return {"status": "no_data", "message": "Nessun cronoprogramma caricato"}
        
        today = date.today()
        df['data_inizio'] = pd.to_datetime(df['data_inizio']).dt.date
        df['data_fine'] = pd.to_datetime(df['data_fine']).dt.date
        
        # Attività in corso
        active_activities = df[
            (df['data_inizio'] <= today) & 
            (df['data_fine'] >= today) &
            (df['stato_avanzamento'] < 100)
        ]
        
        # Attività in ritardo (dovevano iniziare ma sono al 0%)
        delayed_activities = df[
            (df['data_inizio'] < today) & 
            (df['stato_avanzamento'] == 0)
        ]
        
        # Attività critiche (finiscono presto e non sono complete)
        critical_deadline = today + timedelta(days=7)  # Prossimi 7 giorni
        critical_activities = df[
            (df['data_fine'] <= critical_deadline) & 
            (df['stato_avanzamento'] < 100)
        ]
        
        return {
            "total_activities": len(df),
            "active_activities": len(active_activities),
            "delayed_activities": len(delayed_activities),
            "critical_activities": len(critical_activities),
            "completion_rate": df['stato_avanzamento'].mean(),
            "delayed_list": delayed_activities[['descrizione', 'data_inizio']].to_dict('records'),
            "critical_list": critical_activities[['descrizione', 'data_fine', 'stato_avanzamento']].to_dict('records')
        }
    
    def _detect_alerts(self, presenze_df: pd.DataFrame, schedule_df: pd.DataFrame) -> List[Dict[str, str]]:
        """Rileva automaticamente situazioni che richiedono attenzione."""
        alerts = []
        
        if not presenze_df.empty:
            # Alert straordinari eccessivi
            high_overtime = presenze_df.groupby('operaio')['ore_straordinario'].sum()
            for operaio, ore in high_overtime.items():
                if ore > 25:  # Soglia di alert
                    alerts.append({
                        "type": "workload_warning",
                        "message": f"⚠️ {operaio} ha {ore} ore di straordinario - rischio burnout",
                        "priority": "high"
                    })
        
        if not schedule_df.empty:
            # Alert ritardi critici  
            today = date.today()
            schedule_df['data_inizio'] = pd.to_datetime(schedule_df['data_inizio']).dt.date
            delayed = schedule_df[
                (schedule_df['data_inizio'] < today) & 
                (schedule_df['stato_avanzamento'] == 0)
            ]
            
            for _, activity in delayed.iterrows():
                days_late = (today - activity['data_inizio']).days
                alerts.append({
                    "type": "schedule_delay",
                    "message": f"🚨 Attività '{activity['descrizione']}' in ritardo di {days_late} giorni",
                    "priority": "critical"
                })
        
        return alerts
    
    def _get_available_workers(self, presenze_df: pd.DataFrame) -> List[str]:
        """Identifica operai disponibili per nuovi incarichi."""
        if presenze_df.empty:
            return []
        
        # Operai con basso carico di straordinari = più disponibilità
        operai_workload = presenze_df.groupby('operaio')['ore_straordinario'].sum()
        available = operai_workload[operai_workload < 10].index.tolist()  # Meno di 10 ore straordinario
        
        return available
    
    def _get_critical_activities(self, schedule_df: pd.DataFrame) -> List[Dict]:
        """Identifica attività che necessitano attenzione immediata."""
        if schedule_df.empty:
            return []
        
        today = date.today()
        schedule_df['data_fine'] = pd.to_datetime(schedule_df['data_fine']).dt.date
        
        # Attività che scadono nei prossimi 7 giorni e non sono complete
        critical = schedule_df[
            (schedule_df['data_fine'] <= today + timedelta(days=7)) & 
            (schedule_df['stato_avanzamento'] < 100)
        ]
        
        return critical[['descrizione', 'data_fine', 'stato_avanzamento']].to_dict('records')


def get_ai_response(chat_history: list[dict]) -> str:
    """
    🤖 Full AI Assistant che fornisce supporto decisionale strategico.
    Integra dati operativi, cronoprogrammi e knowledge base tecnica.
    """
    print("--- CapoCantiere AI Full Assistant Activated ---")
    
    if not chat_history:
        return "Errore: Cronologia chat non disponibile."
    
    user_query = chat_history[-1]["content"]
    engine = CapoCantiereEngine()
    
    # FASE 1: Raccogli situazione completa cantiere
    try:
        current_situation = engine.get_current_situation()
        print(f"Situazione cantiere caricata: {len(current_situation)} data sources")
    except Exception as e:
        print(f"Errore caricamento dati: {e}")
        return "Non riesco ad accedere ai dati del cantiere. Verifica che i database siano disponibili."
    
    # FASE 2: Determina se serve knowledge base tecnica
    technical_keywords = ['procedura', 'manuale', 'tecnica', 'saldatura', 'normativa', 'sicurezza', 'materiale']
    needs_technical_info = any(keyword in user_query.lower() for keyword in technical_keywords)
    
    technical_context = ""
    if needs_technical_info:
        try:
            print("Consultando knowledge base tecnica...")
            tech_response = get_expert_response(user_query)
            technical_context = f"\nCONTESTO TECNICO:\n{tech_response['answer']}\nFONTI: {tech_response['sources']}\n"
        except Exception as e:
            print(f"Knowledge base non disponibile: {e}")
    
    # FASE 3: Costruisci contesto completo per l'AI
    context_for_ai = f"""
SITUAZIONE CANTIERE AGGIORNATA:
{json.dumps(current_situation, indent=2, default=str, ensure_ascii=False)}

{technical_context}

CRONOLOGIA CONVERSAZIONE RECENTE:
{json.dumps(chat_history[-3:], indent=2, ensure_ascii=False) if len(chat_history) > 1 else "Prima interazione"}
"""
    
    # FASE 4: Prompt avanzato per risposta strategica
    advanced_prompt = f"""
Sei il "CapoCantiere AI", un assistente strategico esperto in gestione cantieri navali.

Il tuo ruolo è fornire supporto decisionale di alto livello, non solo informazioni base.
- Analizza la situazione completa
- Identifica rischi e opportunità  
- Fornisci raccomandazioni concrete e actionable
- Usa un tono professionale ma diretto
- Se ci sono alert critici, mettili in evidenza

DATI COMPLETI DEL CANTIERE:
---
{context_for_ai}
---

DOMANDA DEL CAPO CANTIERE: "{user_query}"

Formula una risposta strategica che aiuti davvero nelle decisioni operative.
Se la domanda riguarda spostamenti di personale, analizza impatti su cronoprogramma e workload.
Se riguarda ritardi, calcola opzioni concrete per recuperare.
Se riguarda la situazione generale, evidenzia le 3 cose più importanti da sapere oggi.
"""
    
    # FASE 5: Genera risposta finale
    try:
        response = engine.client.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': advanced_prompt}],
            options={'temperature': 0.1}  # Bassa creatività, alta coerenza
        )
        
        final_answer = response['message']['content']
        
        # Aggiungi signature del sistema
        final_answer += "\n\n---\n*🤖 CapoCantiere AI - Analisi basata su dati in tempo reale*"
        
        return final_answer
        
    except Exception as e:
        print(f"Errore generazione risposta: {e}")
        return f"Ho analizzato la situazione ma ho avuto un problema nella generazione della risposta. Dettagli tecnici: {e}"