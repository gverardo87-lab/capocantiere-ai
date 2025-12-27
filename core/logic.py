# core/logic.py (Versione 7.0 - Logica di Squadra & Eccezioni)
from __future__ import annotations
from datetime import datetime, time
from typing import Dict, Tuple, Optional
import pandas as pd

class ShiftEngine:
    # Finestre di pausa fisse del cantiere (Blindate)
    PAUSE = {
        "GIORNO": (time(12, 0), time(13, 0)),
        "NOTTE": (time(0, 0), time(1, 0))
    }

    @classmethod
    def calculate_professional_hours(cls, start: datetime, end: datetime) -> Tuple[float, float]:
        """
        Calcola Ore Presenza (Busta) e Ore Lavoro (Cantiere).
        Rileva automaticamente se il turno attraversa le finestre di pausa.
        """
        if not start or not end or end <= start:
            return 0.0, 0.0

        # 1. Ore Presenza (Tempo totale in cantiere per la Busta Paga)
        presenza = round((end - start).total_seconds() / 3600, 2)
        
        # 2. Ore Lavoro (Presenza meno pause per la Fatturazione Cantiere)
        lavoro = presenza
        for p_name, (p_start, p_end) in cls.PAUSE.items():
            # Creiamo datetime di confronto sulla data del turno
            dt_p_start = datetime.combine(start.date(), p_start)
            dt_p_end = datetime.combine(start.date(), p_end)
            
            # Calcolo intersezione reale tra il turno e la finestra pausa
            overlap = min(end, dt_p_end) - max(start, dt_p_start)
            overlap_h = max(0, overlap.total_seconds() / 3600)
            
            if overlap_h > 0:
                lavoro -= overlap_h # Sottrae solo la porzione di pausa effettivamente vissuta
        
        return presenza, round(max(0, lavoro), 2)

# Funzione di compatibilità per mantenere il vecchio calcolo se necessario
def calculate_duration_hours(start_time, end_time) -> float:
    presenza, _ = ShiftEngine.calculate_professional_hours(start_time, end_time)
    return presenza