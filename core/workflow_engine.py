# core/workflow_engine.py
"""
Workflow Engine per CapoCantiere AI
Sistema professionale per la gestione delle fasi di lavoro navali
con dipendenze tra ruoli e calcolo automatico delle percentuali di completamento.
"""

from __future__ import annotations
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

class WorkRole(Enum):
    """Ruoli disponibili nel cantiere navale."""
    CARPENTIERE = "Carpentiere"
    AIUTANTE_CARPENTIERE = "Aiutante Carpentiere"
    SALDATORE = "Saldatore"
    MOLATORE = "Molatore"
    VERNICIATORE = "Verniciatore"
    ELETTRICISTA = "Elettricista"
    TUBISTA = "Tubista"
    MECCANICO = "Meccanico"
    MONTATORE = "Montatore"
    FABBRICATORE = "Fabbricatore"
    
    @classmethod
    def from_string(cls, role_str: str) -> Optional['WorkRole']:
        """Converte una stringa in WorkRole."""
        role_str_upper = role_str.upper().replace(' ', '_')
        for role in cls:
            if role.name == role_str_upper:
                return role
        return None

@dataclass
class WorkPhase:
    """Rappresenta una fase di lavoro con ruoli e percentuali."""
    role: WorkRole
    start_percentage: float
    end_percentage: float
    can_parallel: bool = False  # Se può lavorare in parallelo con altri
    requires_roles: List[WorkRole] = field(default_factory=list)  # Ruoli richiesti in parallelo
    
    def overlaps_with(self, other: 'WorkPhase') -> bool:
        """Verifica se due fasi si sovrappongono temporalmente."""
        return not (self.end_percentage <= other.start_percentage or 
                   self.start_percentage >= other.end_percentage)

@dataclass
class WorkflowTemplate:
    """Template di workflow per un tipo di attività."""
    name: str
    activity_type: str  # MON, FAM, ELE
    phases: List[WorkPhase]
    description: str = ""
    
    def get_active_roles_at_percentage(self, percentage: float) -> List[WorkRole]:
        """Ritorna i ruoli attivi a una certa percentuale di completamento."""
        active_roles = []
        for phase in self.phases:
            if phase.start_percentage <= percentage < phase.end_percentage:
                active_roles.append(phase.role)
                active_roles.extend(phase.requires_roles)
        return list(set(active_roles))
    
    def get_next_phase(self, current_percentage: float) -> Optional[WorkPhase]:
        """Ritorna la prossima fase da iniziare."""
        for phase in self.phases:
            if phase.start_percentage > current_percentage:
                return phase
        return None
    
    def validate_workflow(self) -> Tuple[bool, List[str]]:
        """Valida che il workflow sia coerente."""
        errors = []
        
        # Verifica copertura 0-100%
        covered = set()
        for phase in self.phases:
            for p in range(int(phase.start_percentage), int(phase.end_percentage)):
                covered.add(p)
        
        if 0 not in covered:
            errors.append("Il workflow non parte da 0%")
        if 99 not in covered:
            errors.append("Il workflow non arriva al 100%")
        
        # Verifica dipendenze
        for phase in self.phases:
            if phase.requires_roles:
                for required_role in phase.requires_roles:
                    # Verifica che il ruolo richiesto sia presente nel periodo
                    found = False
                    for other_phase in self.phases:
                        if other_phase.role == required_role and other_phase.overlaps_with(phase):
                            found = True
                            break
                    if not found:
                        errors.append(f"{phase.role.value} richiede {required_role.value} ma non è disponibile nel periodo {phase.start_percentage}-{phase.end_percentage}%")
        
        return len(errors) == 0, errors

class NavalWorkflowEngine:
    """
    Motore principale per la gestione dei workflow navali.
    Gestisce le dipendenze tra ruoli e calcola le allocazioni ottimali.
    """
    
    def __init__(self):
        self.templates: Dict[str, WorkflowTemplate] = {}
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        """Inizializza i template di workflow standard per il cantiere navale."""
        
        # WORKFLOW MONTAGGIO SCAFO (MON)
        self.templates["MON"] = WorkflowTemplate(
            name="Montaggio Scafo",
            activity_type="MON",
            description="Workflow standard per attività di montaggio scafo",
            phases=[
                WorkPhase(
                    role=WorkRole.CARPENTIERE,
                    start_percentage=0,
                    end_percentage=50,
                    can_parallel=True,
                    requires_roles=[WorkRole.AIUTANTE_CARPENTIERE]
                ),
                WorkPhase(
                    role=WorkRole.AIUTANTE_CARPENTIERE,
                    start_percentage=0,
                    end_percentage=50,
                    can_parallel=True
                ),
                WorkPhase(
                    role=WorkRole.SALDATORE,
                    start_percentage=25,  # Può iniziare prima che il carpentiere finisca
                    end_percentage=75,
                    can_parallel=False
                ),
                WorkPhase(
                    role=WorkRole.MOLATORE,
                    start_percentage=50,  # Inizia mentre il saldatore sta ancora lavorando
                    end_percentage=85,
                    can_parallel=False
                ),
                WorkPhase(
                    role=WorkRole.VERNICIATORE,
                    start_percentage=75,
                    end_percentage=100,
                    can_parallel=False
                )
            ]
        )
        
        # WORKFLOW FUORI APPARATO MOTORE (FAM)
        self.templates["FAM"] = WorkflowTemplate(
            name="Fuori Apparato Motore",
            activity_type="FAM",
            description="Workflow per lavorazioni fuori apparato motore",
            phases=[
                WorkPhase(
                    role=WorkRole.FABBRICATORE,
                    start_percentage=0,
                    end_percentage=40,
                    can_parallel=False
                ),
                WorkPhase(
                    role=WorkRole.CARPENTIERE,
                    start_percentage=30,
                    end_percentage=60,
                    can_parallel=True,
                    requires_roles=[WorkRole.AIUTANTE_CARPENTIERE]
                ),
                WorkPhase(
                    role=WorkRole.AIUTANTE_CARPENTIERE,
                    start_percentage=30,
                    end_percentage=60,
                    can_parallel=True
                ),
                WorkPhase(
                    role=WorkRole.SALDATORE,
                    start_percentage=40,
                    end_percentage=80,
                    can_parallel=False
                ),
                WorkPhase(
                    role=WorkRole.MOLATORE,
                    start_percentage=60,
                    end_percentage=90,
                    can_parallel=False
                ),
                WorkPhase(
                    role=WorkRole.VERNICIATORE,
                    start_percentage=80,
                    end_percentage=100,
                    can_parallel=False
                )
            ]
        )
        
        # WORKFLOW ELETTRICO (ELE)
        self.templates["ELE"] = WorkflowTemplate(
            name="Impianti Elettrici",
            activity_type="ELE",
            description="Workflow per impianti elettrici",
            phases=[
                WorkPhase(
                    role=WorkRole.ELETTRICISTA,
                    start_percentage=0,
                    end_percentage=100,
                    can_parallel=False
                )
            ]
        )
    
    def get_workflow_for_activity(self, activity_id: str) -> Optional[WorkflowTemplate]:
        """
        Ritorna il workflow appropriato basato sull'ID attività.
        Es: MON-001 -> workflow MON
        """
        if not activity_id or '-' not in activity_id:
            return None
        
        prefix = activity_id.split('-')[0].upper()
        return self.templates.get(prefix)
    
    def calculate_required_resources(
        self, 
        activity_id: str, 
        current_percentage: float,
        target_percentage: float
    ) -> Dict[WorkRole, float]:
        """
        Calcola le risorse (ore/uomo) richieste per portare un'attività
        da current_percentage a target_percentage.
        """
        workflow = self.get_workflow_for_activity(activity_id)
        if not workflow:
            return {}
        
        required_resources = {}
        
        for phase in workflow.phases:
            # Calcola la sovrapposizione tra la fase e il range richiesto
            overlap_start = max(phase.start_percentage, current_percentage)
            overlap_end = min(phase.end_percentage, target_percentage)
            
            if overlap_start < overlap_end:
                # C'è sovrapposizione, calcola le ore richieste
                percentage_coverage = overlap_end - overlap_start
                # Assumiamo 8 ore per ogni 1% di avanzamento (configurabile)
                hours_required = percentage_coverage * 8
                
                # Aggiungi il ruolo principale
                if phase.role not in required_resources:
                    required_resources[phase.role] = 0
                required_resources[phase.role] += hours_required
                
                # Aggiungi i ruoli richiesti in parallelo
                for required_role in phase.requires_roles:
                    if required_role not in required_resources:
                        required_resources[required_role] = 0
                    required_resources[required_role] += hours_required
        
        return required_resources
    
    def get_bottleneck_analysis(
        self,
        activities: List[Dict[str, Any]],
        available_workers: Dict[WorkRole, int]
    ) -> Dict[str, Any]:
        """
        Analizza i colli di bottiglia basandosi sulle attività e i lavoratori disponibili.
        """
        bottlenecks = []
        total_demand = {role: 0 for role in WorkRole}
        
        for activity in activities:
            activity_id = activity.get('id_attivita', '')
            current_progress = activity.get('stato_avanzamento', 0)
            
            if current_progress >= 100:
                continue  # Attività già completata
            
            # Calcola risorse richieste per completare l'attività
            required = self.calculate_required_resources(
                activity_id, 
                current_progress, 
                100
            )
            
            for role, hours in required.items():
                total_demand[role] += hours
        
        # Confronta domanda con disponibilità
        for role, demand_hours in total_demand.items():
            available = available_workers.get(role, 0)
            if available == 0 and demand_hours > 0:
                bottlenecks.append({
                    'role': role.value,
                    'severity': 'CRITICO',
                    'demand_hours': demand_hours,
                    'available_workers': 0,
                    'shortage_hours': demand_hours
                })
            elif available > 0 and demand_hours > 0:
                # Assumiamo 40 ore settimanali per lavoratore
                available_hours = available * 40
                if demand_hours > available_hours:
                    bottlenecks.append({
                        'role': role.value,
                        'severity': 'ALTO',
                        'demand_hours': demand_hours,
                        'available_workers': available,
                        'shortage_hours': demand_hours - available_hours
                    })
        
        return {
            'bottlenecks': bottlenecks,
            'total_demand': {role.value: hours for role, hours in total_demand.items() if hours > 0},
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    def suggest_optimal_schedule(
        self,
        activities: List[Dict[str, Any]],
        workers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Suggerisce una pianificazione ottimale basata su workflow e disponibilità.
        """
        suggestions = []
        
        # Raggruppa lavoratori per ruolo
        workers_by_role = {}
        for worker in workers:
            role_str = worker.get('ruolo', '')
            role = WorkRole.from_string(role_str)
            if role:
                if role not in workers_by_role:
                    workers_by_role[role] = []
                workers_by_role[role].append(worker)
        
        # Analizza ogni attività
        for activity in activities:
            activity_id = activity.get('id_attivita', '')
            current_progress = activity.get('stato_avanzamento', 0)
            
            if current_progress >= 100:
                continue
            
            workflow = self.get_workflow_for_activity(activity_id)
            if not workflow:
                continue
            
            # Trova la prossima fase
            next_phase = workflow.get_next_phase(current_progress)
            if not next_phase:
                # Trova fase attuale
                active_roles = workflow.get_active_roles_at_percentage(current_progress)
                suggestion = {
                    'activity_id': activity_id,
                    'current_progress': current_progress,
                    'action': 'CONTINUA',
                    'required_roles': [role.value for role in active_roles],
                    'workers_assigned': []
                }
            else:
                suggestion = {
                    'activity_id': activity_id,
                    'current_progress': current_progress,
                    'action': 'INIZIA_FASE',
                    'next_phase_role': next_phase.role.value,
                    'next_phase_start': next_phase.start_percentage,
                    'workers_assigned': []
                }
            
            # Assegna lavoratori ottimali
            if 'required_roles' in suggestion:
                for role_value in suggestion['required_roles']:
                    role = WorkRole(role_value)
                    if role in workers_by_role:
                        # Prendi il lavoratore con meno straordinari
                        available = sorted(
                            workers_by_role[role], 
                            key=lambda w: w.get('ore_straordinario', 0)
                        )
                        if available:
                            suggestion['workers_assigned'].append({
                                'name': available[0]['operaio'],
                                'role': role_value
                            })
            
            suggestions.append(suggestion)
        
        return suggestions

# Istanza globale del workflow engine
workflow_engine = NavalWorkflowEngine()

# Funzioni di utilità per integrazione con il resto del sistema
def get_workflow_info(activity_id: str) -> Dict[str, Any]:
    """Ritorna informazioni sul workflow per un'attività specifica."""
    workflow = workflow_engine.get_workflow_for_activity(activity_id)
    if not workflow:
        return {'error': f'Nessun workflow trovato per {activity_id}'}
    
    return {
        'name': workflow.name,
        'type': workflow.activity_type,
        'description': workflow.description,
        'phases': [
            {
                'role': phase.role.value,
                'start': phase.start_percentage,
                'end': phase.end_percentage,
                'parallel': phase.can_parallel,
                'requires': [r.value for r in phase.requires_roles]
            }
            for phase in workflow.phases
        ],
        'validation': workflow.validate_workflow()
    }

def analyze_resource_allocation(
    presence_data: List[Dict],
    schedule_data: List[Dict]
) -> Dict[str, Any]:
    """
    Analizza l'allocazione delle risorse confrontando presenze e cronoprogramma.
    """
    # Conta lavoratori per ruolo dalle presenze
    workers_count = {}
    for record in presence_data:
        role_str = record.get('ruolo', 'Non specificato')
        role = WorkRole.from_string(role_str)
        if role:
            workers_count[role] = workers_count.get(role, 0) + 1
    
    # Analizza colli di bottiglia
    bottleneck_analysis = workflow_engine.get_bottleneck_analysis(
        schedule_data,
        workers_count
    )
    
    # Suggerimenti di pianificazione
    schedule_suggestions = workflow_engine.suggest_optimal_schedule(
        schedule_data,
        presence_data
    )
    
    return {
        'workers_by_role': {role.value: count for role, count in workers_count.items()},
        'bottleneck_analysis': bottleneck_analysis,
        'schedule_suggestions': schedule_suggestions[:5],  # Top 5 suggerimenti
        'timestamp': datetime.now().isoformat()
    }