# core/chat_logic.py - Sistema Completo CapoCantiere AI
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

class CantiereRolesKnowledge:
    """
    Knowledge base completa dei ruoli e competenze del cantiere navale.
    Basata sui formati reali dei file forniti dall'utente.
    """
    
    # Keywords per identificare ruoli dalle domande
    ROLES_KEYWORDS = {
        "carpentieri": ["carpentiere", "carpentieri", "falegname", "legno", "strutture", "carpenteria"],
        "saldatori": ["saldatore", "saldatori", "saldatura", "tig", "mig", "elettrodo", "saldo", "welding"],
        "elettricisti": ["elettricista", "elettricisti", "elettrico", "impianti", "cavi", "quadri", "electrical"],
        "montatori": ["montatore", "montatori", "montaggio", "assemblaggio", "installazione", "montage"],
        "verniciatori": ["verniciatore", "verniciatori", "verniciatura", "pittura", "sabbiatura", "painting"],
        "fabbricatori": ["fabbricatore", "fabbricatori", "fabbricazione", "costruzione", "fabrication"],
        "tubisti": ["tubista", "tubisti", "tubazioni", "impianti", "raccordi"],
        "meccanici": ["meccanico", "meccanici", "motori", "meccanica", "manutenzione"]
    }
    
    # Mapping basato sui prefissi ID attività REALI dal cronoprogramma
    ACTIVITY_ID_TO_ROLE = {
        "MON": "montatori",      # MON-001, MON-002 = Montaggio, Raddrizzatura
        "FAM": "fabbricatori",   # FAM-001, FAM-002 = Fabbricazione, Installazione
        "ELE": "elettricisti",   # ELE-001, ELE-002 = Electrical, Impianti
        "PIT": "verniciatori",   # PIT-001, PIT-002 = Pittura, Ricariche
        "SAL": "saldatori",      # SAL-001 = Saldatura (se presente)
        "CAR": "carpentieri",    # CAR-001 = Carpenteria (se presente)
        "TUB": "tubisti",        # TUB-001 = Tubazioni (se presente)
        "MEC": "meccanici"       # MEC-001 = Meccanica (se presente)
    }
    
    # Mapping operai basato sui NOMI REALI dal rapportino
    NAME_ROLE_PATTERNS = {
        "carpentieri": ["verardo", "giacomo", "romano"],
        "saldatori": ["rossi", "luca", "florin", "roman", "allam"],
        "elettricisti": ["kakhon", "khan", "billal", "sarkar"],
        "montatori": ["verdi", "marco", "bianchi", "anna"],
        "verniciatori": ["gialli", "simone"],
        "fabbricatori": ["verardo", "giacomo"]  # Può avere doppio ruolo
    }
    
    @classmethod
    def identify_role_from_query(cls, query: str) -> str:
        """Identifica il ruolo richiesto nella domanda dell'utente."""
        query_lower = query.lower()
        
        for role, keywords in cls.ROLES_KEYWORDS.items():
            if any(keyword in query_lower for keyword in keywords):
                return role
        
        return "operai_generici"
    
    @classmethod
    def infer_worker_role(cls, worker_name: str) -> str:
        """Inferisce il ruolo di un operaio dal nome (basato su pattern reali)."""
        if not worker_name:
            return "ruolo_non_identificato"
            
        name_lower = worker_name.lower()
        
        for role, patterns in cls.NAME_ROLE_PATTERNS.items():
            if any(pattern in name_lower for pattern in patterns):
                return role
        
        return "ruolo_non_identificato"
    
    @classmethod
    def get_required_role_from_activity_id(cls, activity_id: str) -> str:
        """
        Determina il ruolo necessario dall'ID attività.
        Es: "MON-001" → "montatori", "ELE-002" → "elettricisti"
        """
        if not activity_id or '-' not in activity_id:
            return "ruolo_non_identificato"
        
        try:
            prefix = activity_id.split('-')[0].upper()
            return cls.ACTIVITY_ID_TO_ROLE.get(prefix, "ruolo_non_identificato")
        except Exception:
            return "ruolo_non_identificato"
    
    @classmethod
    def get_activities_by_role(cls, activities_list: List[Dict]) -> Dict[str, List]:
        """Raggruppa attività per ruolo necessario."""
        activities_by_role = {}
        
        for activity in activities_list:
            activity_id = activity.get('id_attivita', '')
            required_role = cls.get_required_role_from_activity_id(activity_id)
            
            if required_role not in activities_by_role:
                activities_by_role[required_role] = []
            
            activities_by_role[required_role].append(activity)
        
        return activities_by_role

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
            "specific_role": None,
            "specific_metric": None,
            "wants_count": False,
            "wants_assignment": False,
            "specific_activity": None
        }
        
        # Identifica ruoli specifici
        role = CantiereRolesKnowledge.identify_role_from_query(question)
        if role != "operai_generici":
            intent["type"] = "role_specific"
            intent["specific_role"] = role
        
        # Identifica metriche specifiche
        if any(word in question_lower for word in ["assenz", "ferie", "malattia"]):
            intent["specific_metric"] = "absences"
        elif any(word in question_lower for word in ["straordinari", "extra", "overtime"]):
            intent["specific_metric"] = "overtime"
        elif any(word in question_lower for word in ["ore lavorate", "ore totali", "tempo"]):
            intent["specific_metric"] = "total_hours"
        
        # Richiesta di conteggio
        if any(word in question_lower for word in ["quanti", "quante", "numero", "conta"]):
            intent["wants_count"] = True
        
        # Richiesta di assegnazione
        if any(word in question_lower for word in ["chi metto", "assegna", "sposta", "riassegna"]):
            intent["wants_assignment"] = True
        
        # Attività specifica menzionata
        if any(prefix in question_lower for prefix in ["mon-", "fam-", "ele-", "pit-", "sal-", "car-"]):
            # Estrae l'ID attività se presente
            words = question_lower.split()
            for word in words:
                if any(prefix in word for prefix in ["mon-", "fam-", "ele-", "pit-", "sal-", "car-"]):
                    intent["specific_activity"] = word.upper()
                    break
        
        return intent

class PureDataReader:
    """
    Lettore puro dei dati - ZERO calcoli, solo lettura dal database.
    Tutti i calcoli (ore_regolari, ore_straordinario, ore_assenza) 
    sono già stati fatti da logic.py durante l'importazione.
    """
    
    @staticmethod
    def read_processed_presence_data() -> Dict[str, Any]:
        """Legge dati presenze GIÀ PROCESSATI da logic.py - NO calcoli."""
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        try:
            # LEGGE DATI GIÀ COMPLETI (ore_regolari, ore_straordinario, ore_assenza già calcolate)
            raw_data = db_manager.get_presence_data(current_year, current_month)
            
            if not raw_data:
                return {
                    "status": "no_data", 
                    "message": "Nessun rapportino caricato per questo mese"
                }
            
            return {
                "status": "data_available",
                "raw_records": raw_data,  # Dati grezzi completi per l'AI
                "summary": {
                    "total_records": len(raw_data),
                    "unique_workers": len(set(r['operaio'] for r in raw_data)),
                    "date_range": f"{raw_data[0]['data']} - {raw_data[-1]['data']}" if raw_data else "N/A"
                }
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Errore lettura database presenze: {e}"}
    
    @staticmethod 
    def read_processed_schedule_data() -> Dict[str, Any]:
        """Legge cronoprogramma dal database - NO calcoli."""
        try:
            raw_data = schedule_db_manager.get_schedule_data()
            
            if not raw_data:
                return {
                    "status": "no_data", 
                    "message": "Nessun cronoprogramma caricato"
                }
            
            return {
                "status": "data_available", 
                "raw_records": raw_data,
                "summary": {
                    "total_activities": len(raw_data)
                }
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Errore lettura database cronoprogramma: {e}"}
    
    @staticmethod
    def get_critical_activities(days_ahead: int = 7) -> List[Dict]:
        """Identifica attività critiche (scadono presto e non complete)."""
        try:
            schedule_data = PureDataReader.read_processed_schedule_data()
            
            if schedule_data["status"] != "data_available":
                return []
            
            activities = schedule_data["raw_records"]
            today = date.today()
            critical_activities = []
            
            for activity in activities:
                try:
                    end_date = datetime.strptime(activity['data_fine'], '%Y-%m-%d').date()
                    completion = activity.get('stato_avanzamento', 0)
                    
                    # Considera critica se scade nei prossimi N giorni e non è completa
                    days_remaining = (end_date - today).days
                    
                    if days_remaining <= days_ahead and completion < 100:
                        activity_copy = activity.copy()
                        activity_copy['giorni_rimanenti'] = days_remaining
                        critical_activities.append(activity_copy)
                        
                except Exception as e:
                    print(f"Errore parsing attività {activity.get('id_attivita', 'N/A')}: {e}")
                    continue
            
            # Ordina per urgenza (meno giorni rimanenti prima)
            critical_activities.sort(key=lambda x: x.get('giorni_rimanenti', 999))
            return critical_activities
            
        except Exception as e:
            print(f"Errore identificazione attività critiche: {e}")
            return []

class IntelligentResponseGenerator:
    """Generatore di risposte intelligenti basato sui dati reali."""
    
    def __init__(self):
        self.client = Client()
    
    def generate_role_specific_response(self, question_intent: Dict, presence_data: Dict, schedule_data: Dict) -> str:
        """Genera risposta specifica per domande sui ruoli."""
        role_requested = question_intent["specific_role"]
        
        if presence_data["status"] != "data_available":
            return f"❌ **Dati presenze non disponibili**\n\nCarica i rapportini per vedere statistiche su {role_requested}."
        
        # Classifica operai per ruolo
        workers_by_role = self._classify_workers_by_role(presence_data["raw_records"])
        role_workers = workers_by_role.get(role_requested, [])
        
        if question_intent.get("wants_count", False):
            # Risposta di conteggio
            count = len(role_workers)
            response = f"🔍 **{role_requested.title()} identificati: {count}**\n\n"
            
            if count > 0:
                response += "**Elenco**:\n"
                for worker in role_workers:
                    response += f"- {worker['name']}: {worker['total_hours']}h lavorate ({worker['overtime_hours']}h straord.)\n"
            
            # Aggiungi breakdown totale
            response += f"\n📊 **Breakdown completo per ruolo**:\n"
            for role, workers in workers_by_role.items():
                if workers:  # Solo ruoli con operai
                    response += f"- **{role.replace('_', ' ').title()}**: {len(workers)}\n"
                    
            if schedule_data["status"] == "data_available":
                activities_by_role = CantiereRolesKnowledge.get_activities_by_role(schedule_data["raw_records"])
                role_activities = activities_by_role.get(role_requested, [])
                if role_activities:
                    response += f"\n🎯 **Attività per {role_requested}**: {len(role_activities)} in corso"
            
            return response
        
        else:
            # Risposta generale sui ruoli
            if not role_workers:
                return f"❌ **Nessun {role_requested} identificato** nei dati attuali.\n\n💡 **Suggerimento**: Verifica i nomi nei rapportini."
            
            response = f"👥 **Situazione {role_requested.title()}** ({len(role_workers)} operai):\n\n"
            
            # Ordina per disponibilità (meno straordinari = più disponibile)
            role_workers.sort(key=lambda x: x['overtime_hours'])
            
            for worker in role_workers:
                availability = "🟢 Disponibile" if worker['overtime_hours'] < 10 else "🟡 Carico medio" if worker['overtime_hours'] < 25 else "🔴 Sovraccarico"
                response += f"- **{worker['name']}**: {worker['total_hours']}h totali, {worker['overtime_hours']}h straord. {availability}\n"
            
            # Aggiungi attività correlate se disponibili
            if schedule_data["status"] == "data_available":
                activities_by_role = CantiereRolesKnowledge.get_activities_by_role(schedule_data["raw_records"])
                role_activities = activities_by_role.get(role_requested, [])
                if role_activities:
                    response += f"\n🎯 **Attività assegnate**:\n"
                    for activity in role_activities[:3]:  # Prime 3
                        response += f"- {activity.get('id_attivita', 'N/A')}: {activity.get('stato_avanzamento', 0)}% completata\n"
            
            return response
    
    def generate_assignment_response(self, question_intent: Dict, presence_data: Dict, schedule_data: Dict) -> str:
        """Genera risposta per domande di assegnazione ('chi metto su...')."""
        
        if presence_data["status"] != "data_available":
            return "❌ **Dati presenze non disponibili** per suggerimenti di assegnazione."
        
        # Se specifica un'attività particolare
        if question_intent.get("specific_activity"):
            activity_id = question_intent["specific_activity"]
            required_role = CantiereRolesKnowledge.get_required_role_from_activity_id(activity_id)
            
            workers_by_role = self._classify_workers_by_role(presence_data["raw_records"])
            available_workers = workers_by_role.get(required_role, [])
            
            if not available_workers:
                return f"❌ **Nessun {required_role} identificato** per l'attività {activity_id}."
            
            # Ordina per disponibilità
            available_workers.sort(key=lambda x: x['overtime_hours'])
            best_worker = available_workers[0]
            
            return f"""🎯 **Raccomandazione per {activity_id}**:

**Ruolo richiesto**: {required_role.title()}
**Operaio consigliato**: {best_worker['name']}
- Ore totali: {best_worker['total_hours']}h
- Straordinari: {best_worker['overtime_hours']}h
- **Rationale**: Minor carico di lavoro tra i {required_role}

💡 **Alternative**: {', '.join([w['name'] for w in available_workers[1:3]])}"""
        
        # Assegnazione generica - mostra attività critiche
        critical_activities = PureDataReader.get_critical_activities()
        
        if not critical_activities:
            return "✅ **Nessuna attività critica** al momento. Allocazione risorse ottimale."
        
        response = "🚨 **Attività critiche che richiedono assegnazioni**:\n\n"
        
        workers_by_role = self._classify_workers_by_role(presence_data["raw_records"])
        
        for activity in critical_activities[:3]:  # Top 3 più critiche
            activity_id = activity.get('id_attivita', 'N/A')
            required_role = CantiereRolesKnowledge.get_required_role_from_activity_id(activity_id)
            available_workers = workers_by_role.get(required_role, [])
            
            days_remaining = activity.get('giorni_rimanenti', 0)
            urgency = "🔥 URGENTISSIMA" if days_remaining <= 1 else "⚠️ URGENTE" if days_remaining <= 3 else "🟡 Da monitorare"
            
            response += f"**{activity_id}** - {activity.get('descrizione', 'N/A')[:50]}...\n"
            response += f"- Stato: {activity.get('stato_avanzamento', 0)}% | Giorni rimasti: {days_remaining} {urgency}\n"
            
            if available_workers:
                available_workers.sort(key=lambda x: x['overtime_hours'])
                best_worker = available_workers[0]
                response += f"- **Consigliato**: {best_worker['name']} ({best_worker['overtime_hours']}h straord.)\n"
            else:
                response += f"- **Problema**: Nessun {required_role} disponibile!\n"
            
            response += "\n"
        
        return response
    
    def generate_ai_response(self, user_query: str, context_data: Dict) -> str:
        """Genera risposta AI con context ottimizzato per evitare loop infiniti."""
        
        # Context compatto e strutturato
        context_lines = [f"AGGIORNAMENTO: {datetime.now().strftime('%d/%m/%Y %H:%M')}"]
        
        # Dati presenze
        presence_data = context_data.get("presence_data", {})
        if presence_data.get("status") == "data_available":
            raw_records = presence_data["raw_records"]
            
            # Aggrega per operaio (MINIMO processing necessario)
            operai_data = {}
            for record in raw_records:
                operaio = record['operaio']
                if operaio not in operai_data:
                    operai_data[operaio] = {'ore_lavorate': 0, 'ore_straordinario': 0, 'ore_assenza': 0}
                # USA DATI GIÀ PROCESSATI da logic.py
                operai_data[operaio]['ore_lavorate'] += record['ore_lavorate']
                operai_data[operaio]['ore_straordinario'] += record['ore_straordinario'] 
                operai_data[operaio]['ore_assenza'] += record['ore_assenza']
            
            context_lines.append(f"\nPRESENZE ({len(operai_data)} operai):")
            for operaio, data in sorted(operai_data.items()):
                inferred_role = CantiereRolesKnowledge.infer_worker_role(operaio)
                context_lines.append(f"- {operaio} ({inferred_role}): {data['ore_lavorate']}h, {data['ore_straordinario']}h straord, {data['ore_assenza']}h assenza")
        
        # Dati cronoprogramma (solo top critici per non sovraccaricare)
        schedule_data = context_data.get("schedule_data", {})
        critical_activities = context_data.get("critical_activities", [])
        if critical_activities:
            context_lines.append(f"\nATTIVITÀ CRITICHE ({len(critical_activities)}):")
            for activity in critical_activities[:3]:
                activity_id = activity.get('id_attivita', 'N/A')
                required_role = CantiereRolesKnowledge.get_required_role_from_activity_id(activity_id)
                context_lines.append(f"- {activity_id} ({required_role}): {activity.get('stato_avanzamento', 0)}%, {activity.get('giorni_rimanenti', 0)} giorni")
        
        context = "\n".join(context_lines)
        
        # Prompt ottimizzato anti-loop
        prompt = f"""Sei un assistente CapoCantiere esperto. Rispondi in ITALIANO in modo diretto e conciso.

DOMANDA: "{user_query}"

DATI REALI DISPONIBILI:
{context}

ISTRUZIONI:
- Usa SOLO i dati reali sopra forniti, mai inventare
- Se chiede operai specifici, usa i nomi esatti dai dati
- Se chiede ruoli, usa la classificazione (ruolo) mostrata
- Rispondi PRECISAMENTE alla domanda, non informazioni extra
- Massimo 8 righe, sii diretto
- Se non hai abbastanza dati, dillo chiaramente

RISPOSTA DIRETTA:"""

        try:
            response = self.client.chat(
                model=OLLAMA_MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'temperature': 0.05,  # Molto bassa per evitare creatività eccessiva
                    'top_p': 0.7,
                    'repeat_penalty': 1.5,  # Alto per evitare ripetizioni
                    'stop': ['\n\n\n']  # Stop a tripli newline
                }
            )
            
            ai_response = response['message']['content'].strip()
            
            # Controllo anti-loop e lunghezza
            lines = ai_response.split('\n')
            if len(lines) > 12:  # Troppo lungo
                ai_response = '\n'.join(lines[:8]) + "\n\n*[Risposta limitata per chiarezza]*"
            
            # Rimuovi ripetizioni evidenti
            if ai_response.count('Inoltre') > 2:
                parts = ai_response.split('Inoltre')
                ai_response = parts[0] + "*[Ulteriori dettagli disponibili su richiesta]*"
            
            return ai_response
            
        except Exception as e:
            return f"❌ Errore elaborazione AI: {e}\n\nProva a riformulare la domanda."
    
    def _classify_workers_by_role(self, raw_records: List[Dict]) -> Dict[str, List[Dict]]:
        """Classifica operai per ruolo inferito dai nomi."""
        workers_by_role = {}
        operai_data = {}
        
        # Aggrega dati per operaio
        for record in raw_records:
            operaio = record['operaio']
            if operaio not in operai_data:
                operai_data[operaio] = {'ore_lavorate': 0, 'ore_straordinario': 0, 'ore_assenza': 0}
            operai_data[operaio]['ore_lavorate'] += record['ore_lavorate']
            operai_data[operaio]['ore_straordinario'] += record['ore_straordinario'] 
            operai_data[operaio]['ore_assenza'] += record['ore_assenza']
        
        # Classifica per ruolo
        for operaio, data in operai_data.items():
            inferred_role = CantiereRolesKnowledge.infer_worker_role(operaio)
            
            if inferred_role not in workers_by_role:
                workers_by_role[inferred_role] = []
            
            workers_by_role[inferred_role].append({
                'name': operaio,
                'total_hours': data['ore_lavorate'],
                'overtime_hours': data['ore_straordinario'],
                'absence_hours': data['ore_assenza']
            })
        
        return workers_by_role

def get_ai_response(chat_history: list[dict]) -> str:
    """
    FUNZIONE PRINCIPALE - AI Assistant CapoCantiere completo e verificato.
    
    Features:
    - Single Source of Truth: legge solo dati già processati
    - Smart Question Routing: capisce l'intento delle domande
    - Role-aware: conosce ruoli cantiere e mapping attività
    - Anti-loop: previene risposte ripetitive infinite
    - Error handling robusto
    """
    
    # Validazione input
    if not chat_history:
        return "Nessuna domanda ricevuta."
    
    user_query = chat_history[-1]["content"].strip()
    if not user_query:
        return "Fai una domanda sui dati del cantiere."
    
    try:
        # 1. ANALIZZA INTENTO DELLA DOMANDA
        question_intent = SmartQuestionRouter.analyze_question_intent(user_query)
        print(f"Intent rilevato: {question_intent}")  # Debug
        
        # 2. LEGGI DATI REALI DAL DATABASE (no calcoli)
        presence_data = PureDataReader.read_processed_presence_data()
        schedule_data = PureDataReader.read_processed_schedule_data()
        critical_activities = PureDataReader.get_critical_activities()
        
        # 3. GESTIONE CASI SPECIFICI (prima dell'AI generica)
        response_generator = IntelligentResponseGenerator()
        
        # CASO: Domanda specifica sui ruoli
        if question_intent["type"] == "role_specific":
            return response_generator.generate_role_specific_response(
                question_intent, presence_data, schedule_data
            ) + "\n\n---\n*🎯 CapoCantiere AI - Analisi ruoli cantiere*"
        
        # CASO: Richiesta di assegnazione
        elif question_intent.get("wants_assignment", False):
            return response_generator.generate_assignment_response(
                question_intent, presence_data, schedule_data
            ) + "\n\n---\n*🎯 CapoCantiere AI - Raccomandazioni strategiche*"
        
        # CASO: Nessun dato disponibile
        elif (presence_data["status"] == "no_data" and schedule_data["status"] == "no_data"):
            return """❌ **Nessun dato disponibile per l'analisi**

🔧 **Per iniziare:**
1. Carica il rapportino Excel delle presenze mensili
2. Carica il cronoprogramma Excel delle attività
3. Torna qui per analisi e raccomandazioni strategiche

*I dati vengono processati automaticamente durante il caricamento.*

---
*🎯 CapoCantiere AI - Sistema pronto per i tuoi dati*"""
        
        # 4. RISPOSTA AI GENERICA per tutte le altre domande
        else:
            context_data = {
                "presence_data": presence_data,
                "schedule_data": schedule_data,
                "critical_activities": critical_activities,
                "question_intent": question_intent
            }
            
            ai_response = response_generator.generate_ai_response(user_query, context_data)
            return ai_response + "\n\n---\n*🎯 CapoCantiere AI - Analisi su dati reali*"
        
    except Exception as e:
        # Error handling robusto con informazioni utili
        error_msg = f"""❌ **Errore nell'elaborazione**: {str(e)[:100]}...

🔧 **Possibili soluzioni:**
- Verifica che i database siano accessibili
- Ricarica i rapportini se necessario
- Semplifica la domanda e riprova
- Riavvia l'applicazione se il problema persiste

💡 **Domande che funzionano bene:**
- "Situazione generale"
- "Chi ha più assenze?"  
- "Quanti elettricisti ho?"
- "Cosa devo fare oggi?"

---
*🎯 CapoCantiere AI - Errore gestito*"""
        
        print(f"Errore completo in get_ai_response: {e}")  # Log per debugging
        return error_msg