# core/workflow_engine.py (Versione con Typo Corretto)
"""
Workflow Engine per CapoCantiere AI
Sistema professionale per la gestione delle fasi di lavoro navali
con dipendenze tra ruoli e calcolo strategico del fabbisogno di ore residue.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import pandas as pd

class WorkRole(Enum):
    CARPENTIERE = "Carpentiere"  # <-- ERRORE CORRETTO QUI
    AIUTANTE_CARPENTIERE = "Aiutante Carpentiere"
    SALDATORE = "Saldatore"
    MOLATORE = "Molatore"
    CAPOCANTIERE = "Capocantiere"
    
    @classmethod
    def from_string(cls, role_str: str) -> Optional['WorkRole']:
        if not isinstance(role_str, str): return None
        role_str_upper = role_str.upper().replace(' ', '_')
        for role in cls:
            if role.name == role_str_upper: return role
        return None

@dataclass
class WorkPhase:
    role: WorkRole
    hours_required: float
    can_parallel: bool = False
    requires_roles: List[WorkRole] = field(default_factory=list)

@dataclass
class WorkflowTemplate:
    name: str
    activity_type: str
    phases: List[WorkPhase]
    description: str = ""
    
    def get_total_hours(self) -> float:
        """Calcola il monte ore totale standard (considera la durata, non la somma delle ore parallele)."""
        total_duration = 0
        parallel_phase_duration = 0
        for p in self.phases:
            if p.can_parallel:
                parallel_phase_duration = max(parallel_phase_duration, p.hours_required)
            else:
                total_duration += p.hours_required
        return total_duration + parallel_phase_duration

class NavalWorkflowEngine:
    def __init__(self):
        self.templates: Dict[str, WorkflowTemplate] = {}
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        self.templates["MON"] = WorkflowTemplate(
            name="Montaggio Scafo", activity_type="MON",
            description="Workflow standard per il montaggio dello scafo basato su ore di lavoro per fase.",
            phases=[
                WorkPhase(role=WorkRole.CARPENTIERE, hours_required=80.0, can_parallel=True, requires_roles=[WorkRole.AIUTANTE_CARPENTIERE]),
                WorkPhase(role=WorkRole.AIUTANTE_CARPENTIERE, hours_required=80.0, can_parallel=True),
                WorkPhase(role=WorkRole.SALDATORE, hours_required=64.0, can_parallel=False),
                WorkPhase(role=WorkRole.MOLATORE, hours_required=40.0, can_parallel=False),
                WorkPhase(role=WorkRole.CAPOCANTIERE, hours_required=8.0, can_parallel=False)
            ]
        )
        self.templates["FAM"] = WorkflowTemplate(
            name="Fuori Apparato Motore", activity_type="FAM",
            description="Workflow standard per attività FAM, include collaudo.",
            phases=[
                WorkPhase(role=WorkRole.CARPENTIERE, hours_required=88.0, can_parallel=True, requires_roles=[WorkRole.AIUTANTE_CARPENTIERE]),
                WorkPhase(role=WorkRole.AIUTANTE_CARPENTIERE, hours_required=88.0, can_parallel=True),
                WorkPhase(role=WorkRole.SALDATORE, hours_required=72.0, can_parallel=False),
                WorkPhase(role=WorkRole.MOLATORE, hours_required=48.0, can_parallel=False),
                WorkPhase(role=WorkRole.CAPOCANTIERE, hours_required=16.0, can_parallel=False)
            ]
        )
    
    def get_workflow_for_activity(self, activity_id: str) -> Optional[WorkflowTemplate]:
        if not activity_id or '-' not in activity_id: return None
        prefix = activity_id.split('-')[0].upper()
        return self.templates.get(prefix)

    def calculate_remaining_hours_per_role(self, activity_id: str, hours_already_worked: float) -> Dict[WorkRole, float]:
        workflow = self.get_workflow_for_activity(activity_id)
        if not workflow: return {}

        remaining_hours: Dict[WorkRole, float] = {}
        accumulated_duration = 0.0
        
        # Gestione fasi parallele
        parallel_phase_duration = 0
        for p in workflow.phases:
            if p.can_parallel:
                parallel_phase_duration = max(parallel_phase_duration, p.hours_required)

        # Prima le fasi parallele, se esistono
        if parallel_phase_duration > 0:
            hours_covered = max(0, hours_already_worked - accumulated_duration)
            remaining_duration = max(0, parallel_phase_duration - hours_covered)
            if remaining_duration > 0:
                parallel_roles = [p.role for p in workflow.phases if p.can_parallel]
                for role in set(parallel_roles):
                    remaining_hours[role] = remaining_hours.get(role, 0) + remaining_duration
            accumulated_duration += parallel_phase_duration

        # Poi le fasi sequenziali
        for phase in workflow.phases:
            if not phase.can_parallel:
                hours_covered = max(0, hours_already_worked - accumulated_duration)
                remaining_duration = max(0, phase.hours_required - hours_covered)
                if remaining_duration > 0:
                    remaining_hours[phase.role] = remaining_hours.get(phase.role, 0) + remaining_duration
                accumulated_duration += phase.hours_required
        
        return remaining_hours

    def get_bottleneck_analysis(self, activities: List[Dict], available_workers: Dict[WorkRole, int], worked_hours: Dict[str, float]) -> Dict[str, Any]:
        demand = {role: 0.0 for role in WorkRole}
        for act in activities:
            act_id = act.get('id_attivita', '')
            wf = self.get_workflow_for_activity(act_id)
            if not wf or worked_hours.get(act_id, 0) >= wf.get_total_hours(): continue
            rem_hours = self.calculate_remaining_hours_per_role(act_id, worked_hours.get(act_id, 0))
            for role, hours in rem_hours.items():
                demand[role] += hours
        
        bottlenecks = []
        for role, demand_h in demand.items():
            if demand_h <= 0: continue
            workers = available_workers.get(role, 0)
            available_h = workers * 40
            if workers == 0:
                bottlenecks.append({'role': role.value, 'severity': 'CRITICO', 'demand_hours': demand_h, 'available_workers': 0, 'shortage_hours': demand_h})
            elif demand_h > available_h:
                bottlenecks.append({'role': role.value, 'severity': 'ALTO', 'demand_hours': demand_h, 'available_workers': workers, 'shortage_hours': demand_h - available_h})
        
        return {'bottlenecks': sorted(bottlenecks, key=lambda x: x['shortage_hours'], reverse=True), 'total_demand': {r.value: round(h) for r, h in demand.items() if h > 0}}

    def suggest_optimal_schedule(self, activities: List[Dict], workers: List[Dict], worked_hours: Dict[str, float]) -> List[Dict]:
        suggestions = []
        # Implementazione disabilitata per stabilità, da riattivare in futuro
        return suggestions

# Istanza globale
workflow_engine = NavalWorkflowEngine()

def get_workflow_info(activity_id: str) -> Dict[str, Any]:
    workflow = workflow_engine.get_workflow_for_activity(activity_id)
    if not workflow: return {'error': f'Nessun workflow trovato per {activity_id}'}
    return {
        'name': workflow.name, 'type': workflow.activity_type, 'description': workflow.description,
        'total_hours': workflow.get_total_hours(),
        'phases': [{'role': p.role.value, 'hours': p.hours_required, 'parallel': p.can_parallel, 'requires': [r.value for r in p.requires_roles]} for p in workflow.phases]
    }

def analyze_resource_allocation(presence_data: List[Dict], schedule_data: List[Dict]) -> Dict[str, Any]:
    if not presence_data or not schedule_data: return {'error': 'Dati mancanti.'}
    df_presence = pd.DataFrame(presence_data)
    worked_hours = df_presence.groupby('id_attivita')['ore_lavorate'].sum().to_dict()
    unique_workers = {(r.get('operaio'), r.get('ruolo')) for r in presence_data if r.get('operaio')}
    workers_count = {}
    for _, role_str in unique_workers:
        role = WorkRole.from_string(role_str)
        if role: workers_count[role] = workers_count.get(role, 0) + 1
    
    analysis = workflow_engine.get_bottleneck_analysis(schedule_data, workers_count, worked_hours)
    suggestions = workflow_engine.suggest_optimal_schedule(schedule_data, presence_data, worked_hours)
    
    return {
        'workers_by_role': {r.value: c for r, c in workers_count.items()},
        'bottleneck_analysis': analysis,
        'schedule_suggestions': suggestions
    }