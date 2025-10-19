# core/logic.py (Versione 3.0 - Blindata per Buste Paga)

from __future__ import annotations
from datetime import datetime
from typing import Optional
import pandas as pd

def calculate_duration_hours(start_time: Optional[datetime], end_time: Optional[datetime]) -> float:
    """
    Calcola le ore lavorate da due oggetti datetime completi.
    Questa è la funzione centralizzata e unica fonte di verità per
    il calcolo della durata, a prova di turni notturni.
    """
    # Se manca uno dei due valori, la durata è 0
    if not start_time or not end_time or pd.isna(start_time) or pd.isna(end_time):
        return 0.0

    # Assicuriamoci che siano oggetti datetime
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        # Potrebbe succedere se il DB ritorna stringhe o Timestamp di Pandas
        try:
            start_time = pd.to_datetime(start_time).to_pydatetime()
            end_time = pd.to_datetime(end_time).to_pydatetime()
        except Exception:
            return 0.0 # Non riusciamo a parsare

    # L'orario di fine deve essere dopo l'inizio
    if end_time < start_time:
        print(f"ATTENZIONE: Trovato orario di fine precedente all'inizio. Inizio: {start_time}, Fine: {end_time}")
        return 0.0
    
    # Calcola la durata totale in ore
    duration_in_seconds = (end_time - start_time).total_seconds()
    total_hours = duration_in_seconds / 3600
    
    # Come da richiesta, questo è il totale.
    # Ritardi o ore in più sono gestiti modificando start_time/end_time
    # nella "Control Room", ma il calcolo matematico rimane questo.
    return round(total_hours, 2)

#
# --- LOGICA STRAORDINARI E ASSENZE RIMOSSA ---
# Il file ora contiene solo il calcolo puro della durata.
#