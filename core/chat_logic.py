# core/chat_logic.py - Versione Professionale con Workflow Engine
from __future__ import annotations
import sys
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from ollama import Client

# Import dei nostri moduli
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.config import OLLAMA_MODEL
from core.db import db_manager
from core.schedule_db import schedule_db_manager
from core.workflow_engine import workflow_engine, WorkRole, analyze_resource_allocation

class SmartQuestionRouter:
    """Router intelligente che analizza l'intento delle domande dell'utente."""
    
    @staticmethod
    def analyze_question_intent(question: str) -> Dict[str, Any]:
        """Analizza cosa sta chiedendo l'utente per fornire risposta mirata."""
        if not question:
            return {"type": "generic"}
            
        question_lower = question.lower()
        
        intent = {
            "type": "generic",
            "wants_workflow": False,
            "wants_bottleneck": False,
            "wants_role_analysis": False,
            "wants_optimization": False,
            "specific_activity": None,
            "specific_role": None
        }
        
        # Analisi workflow
        if any(word in question_lower for word in ["workflow", "fasi", "processo", "sequenza", "dipendenz"]):
            intent["type"] = "workflow_analysis"
            intent["wants_workflow"] = True
        
        # Analisi colli di bottiglia
        if any(word in question_lower for word in ["bottiglia", "bottleneck", "critic", "mancan", "carenz"]):
            intent["type"] = "bottleneck_analysis"
            intent["wants_bottleneck"] = True
        
        # Analisi ruoli
        if any(word in question_lower for word in ["carpentier", "saldator", "molator", "verniciator", "elettricist", "tubist", "meccanic", "montator", "fabbricator"]):
            intent["type"] = "role_analysis"
            intent["wants_role_analysis"] = True
            
            # Identifica il ruolo specifico
            role_keywords = {
                "carpentiere": ["carpentier"],
                "saldatore": ["saldator"],
                "molatore": ["molator"],
                "verniciatore": ["verniciator"],
                "elettricista": ["elettricist"],
                "tubista": ["tubist"],
                "meccanico": ["meccanic"],
                "montatore": ["montator"],
                "fabbricatore": ["fabbricator"]
            }
            
            for role, keywords in role_keywords.items():
                if any(kw in question_lower for kw in keywords):
                    intent["specific_role"] = role
                    break
        
        # Richiesta ottimizzazione
        if any(word in question_lower for word in ["ottimizz", "miglior", "efficien", "suggeriment", "consigli"]):
            intent["type"] = "optimization"
            intent["wants_optimization"] = True
        
        # Attività specifica
        activity_patterns = ["mon-", "fam-", "ele-"]
        for pattern in activity_patterns:
            if pattern in question_lower:
                # Estrai l'ID attività
                import re
                match = re.search(r'(mon|fam|ele)-\d+', question_lower)
                if match:
                    intent["specific_activity"] = match.group().upper()
                    intent["type"] = "activity_specific"
                break
        
        return intent

class PureDataReader:
    """
    Lettore puro dei dati - ZERO calcoli, solo lettura dal database.
    Versione aggiornata con supporto per ruoli.
    """
    
    @staticmethod
    def read_processed_presence_data() -> Dict[str, Any]:
        """Legge dati presenze GIÀ PROCESSATI con ruoli inclusi."""
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        try:
            raw_data = db_manager.get_presence_data(current_year, current_month)
            
            if not raw_data:
                return {
                    "status": "no_data", 
                    "message": "Nessun rapportino caricato per questo mese"
                }
            
            # Aggrega statistiche per ruolo
            role_stats = {}
            for record in raw_data:
                role = record.get('ruolo', 'Non specificato')
                if role not in role_stats:
                    role_stats[role] = {
                        'count': 0,
                        'total_hours': 0,
                        'overtime': 0
                    }
                role_stats[role]['count'] += 1
                role_stats[role]['total_hours'] += record['ore_lavorate']
                role_stats[role]['overtime'] += record['ore_straordinario']
            
            return {
                "status": "data_available",
                "raw_records": raw_data,
                "role_statistics": role_stats,
                "summary": {
                    "total_records": len(raw_data),
                    "unique_workers": len(set(r['operaio'] for r in raw_data)),
                    "unique_roles": len(role_stats),
                    "date_range": f"{raw_data[0]['data']} - {raw_data[-1]['data']}" if raw_data else "N/A"
                }
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Errore lettura database presenze: {e}"}
    
    @staticmethod 
    def read_processed_schedule_data() -> Dict[str, Any]:
        """Legge cronoprogramma dal database."""
        try:
            raw_data = schedule_db_manager.get_schedule_data()
            
            if not raw_data:
                return {
                    "status": "no_data", 
                    "message": "Nessun cronoprogramma caricato"
                }
            
            # Analizza attività per tipo
            activity_by_type = {'MON': [], 'FAM': [], 'ELE': [], 'OTHER': []}
            for activity in raw_data:
                activity_id = activity.get('id_attivita', '')
                if activity_id.startswith('MON'):
                    activity_by_type['MON'].append(activity)
                elif activity_id.startswith('FAM'):
                    activity_by_type['FAM'].append(activity)
                elif activity_id.startswith('ELE'):
                    activity_by_type['ELE'].append(activity)
                else:
                    activity_by_type['OTHER'].append(activity)
            
            return {
                "status": "data_available", 
                "raw_records": raw_data,
                "by_type": activity_by_type,
                "summary": {
                    "total_activities": len(raw_data),
                    "mon_activities": len(activity_by_type['MON']),
                    "fam_activities": len(activity_by_type['FAM']),
                    "ele_activities": len(activity_by_type['ELE'])
                }
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Errore lettura database cronoprogramma: {e}"}

class WorkflowAwareResponseGenerator:
    """Generatore di risposte che integra l'analisi dei workflow."""
    
    def __init__(self):
        self.client = Client()
    
    def generate_workflow_response(self, question_intent: Dict, presence_data: Dict, schedule_data: Dict) -> str:
        """Genera risposta specifica per domande sui workflow."""
        
        response = "## 🔄 Analisi Workflow\n\n"
        
        # Se chiede di un'attività specifica
        if question_intent.get("specific_activity"):
            activity_id = question_intent["specific_activity"]
            workflow = workflow_engine.get_workflow_for_activity(activity_id)
            
            if workflow:
                response += f"### Workflow per {activity_id} - {workflow.name}\n\n"
                response += f"*{workflow.description}*\n\n"
                
                response += "**Fasi di lavoro:**\n"
                for phase in workflow.phases:
                    response += f"- **{phase.role.value}** ({phase.start_percentage}% → {phase.end_percentage}%)"
                    if phase.requires_roles:
                        response += f" - Richiede: {', '.join([r.value for r in phase.requires_roles])}"
                    response += "\n"
                
                # Trova stato attuale se disponibile
                if schedule_data["status"] == "data_available":
                    for activity in schedule_data["raw_records"]:
                        if activity['id_attivita'] == activity_id:
                            current_progress = activity.get('stato_avanzamento', 0)
                            active_roles = workflow.get_active_roles_at_percentage(current_progress)
                            
                            response += f"\n**Stato attuale**: {current_progress}%\n"
                            response += f"**Ruoli attualmente attivi**: {', '.join([r.value for r in active_roles])}\n"
                            
                            next_phase = workflow.get_next_phase(current_progress)
                            if next_phase:
                                response += f"**Prossima fase**: {next_phase.role.value} al {next_phase.start_percentage}%\n"
                            break
            else:
                response += f"❌ Nessun workflow definito per l'attività {activity_id}\n"
        
        # Analisi generale workflow
        else:
            response += "### Workflow Standard del Cantiere\n\n"
            
            workflows_info = {
                'MON': "**Montaggio Scafo**: Carpentiere → Saldatore → Molatore → Verniciatore",
                'FAM': "**Fuori Apparato Motore**: Fabbricatore → Carpentiere → Saldatore → Molatore → Verniciatore",
                'ELE': "**Impianti Elettrici**: Elettricista (0-100%)"
            }
            
            for code, description in workflows_info.items():
                response += f"- {description}\n"
            
            response += "\n💡 **Nota**: I workflow possono avere fasi sovrapposte per ottimizzare i tempi\n"
        
        return response
    
    def generate_bottleneck_response(self, presence_data: Dict, schedule_data: Dict) -> str:
        """Genera risposta per analisi colli di bottiglia."""
        
        response = "## 🚨 Analisi Colli di Bottiglia\n\n"
        
        if presence_data["status"] != "data_available" or schedule_data["status"] != "data_available":
            return response + "❌ Dati insufficienti per l'analisi. Carica presenze e cronoprogramma.\n"
        
        # Analizza con workflow engine
        analysis = analyze_resource_allocation(
            presence_data["raw_records"],
            schedule_data["raw_records"]
        )
        
        bottlenecks = analysis['bottleneck_analysis']['bottlenecks']
        
        if not bottlenecks:
            response += "✅ **Nessun collo di bottiglia identificato!**\n\n"
            response += "L'allocazione delle risorse è attualmente bilanciata.\n"
        else:
            critical = [b for b in bottlenecks if b['severity'] == 'CRITICO']
            high = [b for b in bottlenecks if b['severity'] == 'ALTO']
            
            if critical:
                response += "### 🔴 Criticità URGENTI\n"
                for bottleneck in critical:
                    response += f"- **{bottleneck['role']}**: MANCANO completamente ({bottleneck['demand_hours']:.0f} ore richieste)\n"
                response += "\n"
            
            if high:
                response += "### 🟡 Criticità ALTE\n"
                for bottleneck in high:
                    response += f"- **{bottleneck['role']}**: Carenza di {bottleneck['shortage_hours']:.0f} ore "
                    response += f"({bottleneck['available_workers']} operai disponibili)\n"
                response += "\n"
            
            # Suggerimenti
            response += "### 💡 Azioni Consigliate\n"
            if critical:
                response += f"1. **Assumere URGENTEMENTE**: {', '.join([b['role'] for b in critical])}\n"
            response += "2. Riorganizzare le priorità delle attività\n"
            response += "3. Considerare straordinari mirati per ruoli carenti\n"
        
        return response
    
    def generate_optimization_response(self, presence_data: Dict, schedule_data: Dict) -> str:
        """Genera suggerimenti di ottimizzazione."""
        
        response = "## 🎯 Suggerimenti Ottimizzazione\n\n"
        
        if presence_data["status"] != "data_available" or schedule_data["status"] != "data_available":
            return response + "❌ Dati insufficienti. Carica presenze e cronoprogramma.\n"
        
        # Genera suggerimenti con workflow engine
        suggestions = workflow_engine.suggest_optimal_schedule(
            schedule_data["raw_records"],
            presence_data["raw_records"]
        )
        
        if not suggestions:
            response += "✅ L'allocazione attuale è già ottimizzata!\n"
        else:
            response += f"### Top 5 Azioni Prioritarie\n\n"
            
            for i, suggestion in enumerate(suggestions[:5], 1):
                response += f"**{i}. {suggestion['activity_id']}** (Progresso: {suggestion['current_progress']}%)\n"
                
                if suggestion['action'] == 'INIZIA_FASE':
                    response += f"   → Iniziare fase **{suggestion['next_phase_role']}** "
                    response += f"(dal {suggestion['next_phase_start']}%)\n"
                elif suggestion['action'] == 'CONTINUA':
                    response += f"   → Continuare con: {', '.join(suggestion['required_roles'])}\n"
                
                if suggestion['workers_assigned']:
                    response += f"   → Operai consigliati: "
                    response += ", ".join([w['name'] for w in suggestion['workers_assigned']])
                    response += "\n"
                else:
                    response += "   → ⚠️ ATTENZIONE: Nessun operaio disponibile!\n"
                
                response += "\n"
        
        # Aggiungi metriche di efficienza
        if presence_data.get("role_statistics"):
            response += "### 📊 Efficienza Attuale per Ruolo\n"
            for role, stats in presence_data["role_statistics"].items():
                if stats['count'] > 0:
                    avg_overtime = stats['overtime'] / stats['count']
                    efficiency = "🟢 Ottima" if avg_overtime < 10 else "🟡 Media" if avg_overtime < 25 else "🔴 Bassa"
                    response += f"- **{role}**: {efficiency} (media straord: {avg_overtime:.1f}h)\n"
        
        return response
    
    def generate_ai_response(self, user_query: str, context_data: Dict) -> str:
        """Genera risposta AI con context workflow-aware."""
        
        # Prepara context includendo informazioni sui workflow
        context_lines = [f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}"]
        context_lines.append("SISTEMA: CapoCantiere AI con Workflow Engine Navale")
        
        # Dati presenze con ruoli
        presence_data = context_data.get("presence_data", {})
        if presence_data.get("status") == "data_available" and presence_data.get("role_statistics"):
            context_lines.append("\nDISTRIBUZIONE RUOLI:")
            for role, stats in presence_data["role_statistics"].items():
                context_lines.append(f"- {role}: {stats['count']} operai, {stats['total_hours']:.0f}h totali")
        
        # Informazioni workflow
        schedule_data = context_data.get("schedule_data", {})
        if schedule_data.get("status") == "data_available":
            context_lines.append("\nATTIVITÀ E WORKFLOW:")
            for activity_type, activities in schedule_data.get("by_type", {}).items():
                if activities and activity_type != 'OTHER':
                    context_lines.append(f"- {activity_type}: {len(activities)} attività")
        
        # Bottlenecks se presenti
        if "bottleneck_analysis" in context_data:
            bottlenecks = context_data["bottleneck_analysis"].get("bottlenecks", [])
            if bottlenecks:
                context_lines.append("\nCRITICITÀ:")
                for b in bottlenecks[:3]:
                    context_lines.append(f"- {b['role']}: {b['severity']}")
        
        context = "\n".join(context_lines)
        
        # Prompt ottimizzato per workflow
        prompt = f"""Sei CapoCantiere AI, esperto in gestione cantieri navali con workflow engine.

DOMANDA: "{user_query}"

CONTESTO SISTEMA:
{context}

CONOSCENZA WORKFLOW:
- MON (Montaggio Scafo): Carpentiere+Aiutante (0-50%) → Saldatore (25-75%) → Molatore (50-85%) → Verniciatore (75-100%)
- FAM (Fuori Apparato): Fabbricatore (0-40%) → Carpentiere+Aiutante (30-60%) → Saldatore (40-80%) → Molatore (60-90%) → Verniciatore (80-100%)
- ELE (Elettrico): Elettricista (0-100%)

ISTRUZIONI:
- Rispondi in ITALIANO, modo professionale ma chiaro
- Usa i dati reali del contesto
- Applica la conoscenza dei workflow navali
- Fornisci suggerimenti pratici e attuabili
- Massimo 10 righe, sii preciso

RISPOSTA:"""

        try:
            response = self.client.chat(
                model=OLLAMA_MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'temperature': 0.3,
                    'top_p': 0.8,
                    'repeat_penalty': 1.3
                }
            )
            
            return response['message']['content'].strip()
            
        except Exception as e:
            return f"❌ Errore elaborazione: {e}\n\nRiformula la domanda."

def get_ai_response(chat_history: list[dict]) -> str:
    """
    FUNZIONE PRINCIPALE - AI Assistant CapoCantiere con Workflow Engine.
    
    Features avanzate:
    - Workflow-aware responses
    - Bottleneck analysis 
    - Resource optimization
    - Role-based allocation
    """
    
    if not chat_history:
        return "Nessuna domanda ricevuta."
    
    user_query = chat_history[-1]["content"].strip()
    if not user_query:
        return "Fai una domanda sui dati del cantiere o sui workflow."
    
    try:
        # 1. ANALIZZA INTENTO
        question_intent = SmartQuestionRouter.analyze_question_intent(user_query)
        print(f"Intent rilevato: {question_intent}")
        
        # 2. LEGGI DATI
        presence_data = PureDataReader.read_processed_presence_data()
        schedule_data = PureDataReader.read_processed_schedule_data()
        
        # 3. GENERA RISPOSTA BASATA SU INTENTO
        response_generator = WorkflowAwareResponseGenerator()
        
        # WORKFLOW ANALYSIS
        if question_intent.get("wants_workflow"):
            return response_generator.generate_workflow_response(
                question_intent, presence_data, schedule_data
            ) + "\n\n---\n*🎯 CapoCantiere AI - Workflow Engine*"
        
        # BOTTLENECK ANALYSIS
        elif question_intent.get("wants_bottleneck"):
            return response_generator.generate_bottleneck_response(
                presence_data, schedule_data
            ) + "\n\n---\n*🎯 CapoCantiere AI - Analisi Criticità*"
        
        # OPTIMIZATION
        elif question_intent.get("wants_optimization"):
            return response_generator.generate_optimization_response(
                presence_data, schedule_data
            ) + "\n\n---\n*🎯 CapoCantiere AI - Ottimizzazione Risorse*"
        
        # NO DATA
        elif (presence_data["status"] == "no_data" and schedule_data["status"] == "no_data"):
            return """❌ **Nessun dato disponibile**

Per iniziare:
1. Carica il rapportino Excel con colonna 'Ruolo'
2. Carica il cronoprogramma Excel
3. Il sistema analizzerà automaticamente workflow e allocazioni

---
*🎯 CapoCantiere AI Professional - Workflow Engine Ready*"""
        
        # GENERIC AI RESPONSE
        else:
            # Prepara analisi se disponibili
            bottleneck_analysis = None
            if presence_data["status"] == "data_available" and schedule_data["status"] == "data_available":
                full_analysis = analyze_resource_allocation(
                    presence_data["raw_records"],
                    schedule_data["raw_records"]
                )
                bottleneck_analysis = full_analysis.get("bottleneck_analysis")
            
            context_data = {
                "presence_data": presence_data,
                "schedule_data": schedule_data,
                "question_intent": question_intent,
                "bottleneck_analysis": bottleneck_analysis
            }
            
            ai_response = response_generator.generate_ai_response(user_query, context_data)
            return ai_response + "\n\n---\n*🎯 CapoCantiere AI Professional*"
        
    except Exception as e:
        error_msg = f"""❌ **Errore**: {str(e)[:100]}

💡 **Prova a chiedere**:
- "Analizza il workflow per MON-001"
- "Quali sono i colli di bottiglia?"  
- "Come posso ottimizzare le risorse?"
- "Mostra situazione carpentieri"

---
*🎯 CapoCantiere AI - Error Recovery*"""
        
        print(f"Errore completo: {e}")
        return error_msg