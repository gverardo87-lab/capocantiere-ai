# core/shift_service.py (Versione 17.0 - Integrazione Doppio Binario Presenza/Lavoro)
from __future__ import annotations
import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

# Importa il DAO e la logica professionale
from core.crm_db import CrmDBManager, DB_FILE, setup_initial_data
from core.logic import ShiftEngine

class ShiftService:
    """
    Service Layer per la gestione centralizzata della logica di business dei turni.
    Questa classe è l'UNICA che l'interfaccia utente (Streamlit) deve chiamare.
    Implementa la logica a doppio binario: Presenza (Busta) e Lavoro (Cantiere).
    """
    def __init__(self, db_manager: CrmDBManager):
        self.db_manager = db_manager # Questo è il nostro DAO

    # --- 1. LOGICA DI BUSINESS (SCRITTURA) ---

    def _split_and_prepare_segments(self, id_turno_master: int, shift_data: Dict[str, Any]) -> List[tuple]:
        """
        Logica interna per splittare i turni a mezzanotte e calcolare le ore professionali.
        Restituisce una lista di tuple pronte per l'inserimento nel DB (8 campi).
        """
        start = shift_data['data_ora_inizio']
        end = shift_data['data_ora_fine']
        note = shift_data.get('note') or ''
        id_dip = shift_data['id_dipendente']
        id_att = shift_data.get('id_attivita')

        def create_segment_tuple(s: datetime.datetime, e: datetime.datetime, n: str):
            """Helper per calcolare le ore e creare la tupla per il DAO."""
            # Calcolo professionale a due binari tramite il motore logico
            presenza, lavoro = ShiftEngine.calculate_professional_hours(s, e)
            return (
                id_turno_master, id_dip, id_att, 
                s.isoformat(), e.isoformat(), 
                presenza, lavoro, n
            )

        # Caso A: Il turno inizia e finisce nello stesso giorno solare
        if start.date() == end.date():
            return [create_segment_tuple(start, end, note)]

        # Caso B: Il turno scavalca la mezzanotte
        mezzanotte = (start + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Se finisce esattamente a mezzanotte, trattalo come segmento unico
        if end == mezzanotte:
             return [create_segment_tuple(start, end, note)]

        # Split obbligatorio per la quadratura solare (Payroll/INAIL)
        segment1 = create_segment_tuple(start, mezzanotte, f"{note} (Parte 1)".strip())
        segment2 = create_segment_tuple(mezzanotte, end, f"{note} (Parte 2)".strip())
        
        return [segment1, segment2]

    def create_shifts_batch(self, shifts_data: List[Dict[str, Any]]) -> int:
        """Crea uno o più turni master e calcola i relativi segmenti professionali."""
        if not shifts_data:
            return 0
        total_segments_created = 0
        with self.db_manager.transaction() as cursor:
            for shift in shifts_data:
                id_dipendente = shift['id_dipendente']
                start_time = shift['data_ora_inizio']
                end_time = shift['data_ora_fine']

                # Verifica sovrapposizioni prima dell'inserimento
                if self.db_manager.check_for_master_overlaps(id_dipendente, start_time, end_time):
                    raise ValueError(f"Sovrapposizione rilevata per il dipendente {id_dipendente} nell'intervallo {start_time} - {end_time}")

                # 1. Crea il record Master (L'evento logico)
                master_id = self.db_manager.create_turno_master(cursor, shift)
                
                # 2. Genera i segmenti fisici (con calcolo ore Presenza/Lavoro)
                segments = self._split_and_prepare_segments(master_id, shift)
                
                # 3. Salva i segmenti arricchiti nel DB
                self.db_manager.create_registrazioni_segments(cursor, segments)
                total_segments_created += len(segments)
                
        return total_segments_created

    def update_master_shift(
        self, id_turno_master: int, new_start: datetime.datetime,
        new_end: datetime.datetime, new_id_attivita: Optional[str], new_note: Optional[str]):
        """Aggiorna un intero turno master e ricalcola i suoi segmenti professionali."""
        with self.db_manager.transaction() as cursor:
            master_originale = self.db_manager.get_turno_master(cursor, id_turno_master)
            if not master_originale:
                 raise ValueError(f"Turno master {id_turno_master} non trovato.")

            if self.db_manager.check_for_master_overlaps(
                master_originale['id_dipendente'], new_start, new_end, exclude_master_id=id_turno_master):
                raise ValueError("La modifica causa una sovrapposizione con un altro turno.")

            # Aggiorna il master e cancella i vecchi segmenti (gestito internamente dal DAO)
            self.db_manager.update_turno_master(
                cursor, id_turno_master, new_start, new_end, new_id_attivita, new_note)

            new_master_data = {
                'id_dipendente': master_originale['id_dipendente'],
                'data_ora_inizio': new_start,
                'data_ora_fine': new_end,
                'id_attivita': new_id_attivita,
                'note': new_note
            }
            # Rigenera i segmenti con i nuovi calcoli Presenza/Lavoro
            new_segments = self._split_and_prepare_segments(id_turno_master, new_master_data)
            self.db_manager.create_registrazioni_segments(cursor, new_segments)

    def delete_master_shift(self, id_turno_master: int):
        """Elimina un intero turno master e tutti i suoi segmenti in cascata."""
        with self.db_manager.transaction() as cursor:
            self.db_manager.delete_turno_master(cursor, id_turno_master)

    def split_master_shift_for_interruption(
        self, id_turno_master: int, start_interruzione: datetime.datetime, end_interruzione: datetime.datetime
    ):
        """Gestisce un'interruzione di cantiere dividendo il turno in due nuovi master."""
        with self.db_manager.transaction() as cursor:
            master_originale = self.db_manager.get_turno_master(cursor, id_turno_master)
            if not master_originale:
                raise ValueError(f"Turno master {id_turno_master} non trovato.")

            original_start = datetime.datetime.fromisoformat(master_originale['data_ora_inizio_effettiva'])
            original_end = datetime.datetime.fromisoformat(master_originale['data_ora_fine_effettiva'])
            
            if start_interruzione >= end_interruzione or \
               start_interruzione < original_start or \
               end_interruzione > original_end:
                raise ValueError("Interruzione non valida (fuori dai limiti del turno o orari invertiti)")

            # Elimina il vecchio master e ricrea i pezzi come nuovi master indipendenti
            self.db_manager.delete_turno_master(cursor, id_turno_master)
            
            shifts_to_create = []
            if original_start < start_interruzione:
                shifts_to_create.append({
                    "id_dipendente": master_originale['id_dipendente'], "id_attivita": master_originale.get('id_attivita'),
                    "data_ora_inizio": original_start, "data_ora_fine": start_interruzione,
                    "note": f"{master_originale.get('note') or ''} (Ante Interruzione)".strip()
                })
            if end_interruzione < original_end:
                shifts_to_create.append({
                    "id_dipendente": master_originale['id_dipendente'], "id_attivita": master_originale.get('id_attivita'),
                    "data_ora_inizio": end_interruzione, "data_ora_fine": original_end,
                    "note": f"{master_originale.get('note') or ''} (Post Interruzione)".strip()
                })
        
        if shifts_to_create:
            self.create_shifts_batch(shifts_to_create)

    # --- 2. METODI PASS-THROUGH (LETTURA) PER LA UI ---

    def get_turni_standard(self) -> List[Dict[str, Any]]:
        return self.db_manager.get_turni_standard()

    def get_squadre(self) -> List[Dict[str, Any]]:
        return self.db_manager.get_squadre()

    def get_dipendenti_df(self, solo_attivi: bool = False) -> pd.DataFrame:
        return self.db_manager.get_dipendenti_df(solo_attivi)

    def get_membri_squadra(self, id_squadra: int) -> List[int]:
        return self.db_manager.get_membri_squadra(id_squadra)

    def check_for_master_overlaps(self, id_dipendente: int, start_time: datetime.datetime, end_time: datetime.datetime, exclude_master_id: Optional[int] = None) -> bool:
        return self.db_manager.check_for_master_overlaps(id_dipendente, start_time, end_time, exclude_master_id)

    def get_turni_master_giorno_df(self, giorno: datetime.date) -> pd.DataFrame:
        return self.db_manager.get_turni_master_giorno_df(giorno)
    
    def get_turni_master_range_df(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        return self.db_manager.get_turni_master_range_df(start_date, end_date)
        
    def get_report_data_df(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        return self.db_manager.get_report_data_df(start_date, end_date)
        
    def add_dipendente(self, nome: str, cognome: str, ruolo: str) -> int:
        return self.db_manager.add_dipendente(nome, cognome, ruolo)
        
    def update_dipendente_field(self, id_dipendente: int, field_name: str, new_value):
        return self.db_manager.update_dipendente_field(id_dipendente, field_name, new_value)
        
    def add_squadra(self, nome_squadra: str, id_caposquadra: Optional[int]) -> int:
        return self.db_manager.add_squadra(nome_squadra, id_caposquadra)
        
    def update_membri_squadra(self, id_squadra: int, membri_ids: List[int]):
        return self.db_manager.update_membri_squadra(id_squadra, membri_ids)
        
    def update_squadra_details(self, id_squadra: int, nome_squadra: str, id_caposquadra: Optional[int]):
        return self.db_manager.update_squadra_details(id_squadra, nome_squadra, id_caposquadra)
        
    def delete_squadra(self, id_squadra: int):
        return self.db_manager.delete_squadra(id_squadra)


# --- 3. CREAZIONE ISTANZE GLOBALI ---

# 1. Assicura che i dati iniziali esistano
setup_initial_data()

# 2. Crea l'istanza del DAO
_db_dao = CrmDBManager(DB_FILE)

# 3. Crea l'istanza del Service Layer
shift_service = ShiftService(db_manager=_db_dao)

print("✅ ShiftService 17.0 configurato con successo (Logica Presenza/Lavoro attiva)")