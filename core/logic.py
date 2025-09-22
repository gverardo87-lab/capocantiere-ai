from __future__ import annotations
from datetime import datetime, timedelta

def calculate_worked_hours(start_time: str | None, end_time: str | None, break_duration_hours: float = 1.0) -> float:
    """
    Calcola le ore lavorate da un orario di inizio e fine, sottraendo una pausa.

    Args:
        start_time: Orario di inizio nel formato "HH:MM".
        end_time: Orario di fine nel formato "HH:MM".
        break_duration_hours: Durata della pausa in ore (es. 1.0 per un'ora).

    Returns:
        Le ore lavorate come numero decimale. Ritorna 0.0 se gli orari non sono validi.
    """
    if not start_time or not end_time:
        return 0.0

    try:
        # Usiamo un formato standard per il parsing.
        # La data (1900-01-01) è irrilevante, serve solo per creare oggetti datetime validi.
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")
    except ValueError:
        # Se il formato dell'ora non è valido, ritorna 0 ore e non sollevare un'eccezione
        print(f"ATTENZIONE: Formato ora non valido rilevato. Inizio: '{start_time}', Fine: '{end_time}'")
        return 0.0

    # Gestisce i casi in cui il turno finisce il giorno dopo (es. 22:00 - 06:00)
    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    # Calcola la durata totale in ore
    duration_in_seconds = (end_dt - start_dt).total_seconds()
    total_hours = duration_in_seconds / 3600

    # Sottrae la pausa e si assicura che il risultato non sia negativo
    worked_hours = max(0, total_hours - break_duration_hours)

    return round(worked_hours, 2)
