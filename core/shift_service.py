# core/shift_service.py (Versione 28.1 - Fix Interruzioni & Smart Delete)
from __future__ import annotations
import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

from core.crm_db import CrmDBManager, DB_FILE, setup_initial_data
from core.logic import ShiftEngine

class ShiftService:
    def __init__(self, db_manager: CrmDBManager):
        self.db_manager = db_manager

    # --- 1. CORE LOGIC ---
    def _split_and_prepare_segments(self, id_turno_master: int, shift_data: Dict[str, Any]) -> List[tuple]:
        start = shift_data['data_ora_inizio']
        end = shift_data['data_ora_fine']
        note = shift_data.get('note') or ''
        id_dip = shift_data['id_dipendente']
        id_att = shift_data.get('id_attivita')

        def create_segment_tuple(s, e, n):
            presenza, lavoro = ShiftEngine.calculate_professional_hours(s, e)
            return (id_turno_master, id_dip, id_att, s.isoformat(), e.isoformat(), presenza, lavoro, n)

        if start.date() == end.date():
            return [create_segment_tuple(start, end, note)]

        mezzanotte = (start + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if end == mezzanotte: return [create_segment_tuple(start, end, note)]

        return [
            create_segment_tuple(start, mezzanotte, f"{note} (Parte 1)".strip()),
            create_segment_tuple(mezzanotte, end, f"{note} (Parte 2)".strip())
        ]

    def create_shifts_batch(self, shifts_data: List[Dict[str, Any]]) -> int:
        if not shifts_data: return 0
        total_segments_created = 0
        with self.db_manager.transaction() as cursor:
            for shift in shifts_data:
                id_dipendente = shift['id_dipendente']
                start_time = shift['data_ora_inizio']
                end_time = shift['data_ora_fine']

                if self.db_manager.check_for_master_overlaps(id_dipendente, start_time, end_time):
                    raise ValueError(f"CONFLITTO: Dipendente {id_dipendente} occupato in {start_time}-{end_time}")

                master_id = self.db_manager.create_turno_master(cursor, shift)
                segments = self._split_and_prepare_segments(master_id, shift)
                self.db_manager.create_registrazioni_segments(cursor, segments)
                total_segments_created += len(segments)
        return total_segments_created

    # --- 2. MODIFICHE E INTERRUZIONI ---
    def update_master_shift(self, id_turno_master: int, new_start: datetime.datetime, new_end: datetime.datetime, new_id_attivita: Optional[str], new_note: Optional[str]):
        with self.db_manager.transaction() as cursor:
            master_originale = self.db_manager.get_turno_master(cursor, id_turno_master)
            if not master_originale: raise ValueError(f"Turno master {id_turno_master} non trovato.")

            if self.db_manager.check_for_master_overlaps(master_originale['id_dipendente'], new_start, new_end, exclude_master_id=id_turno_master):
                raise ValueError("La modifica causa una sovrapposizione.")

            self.db_manager.update_turno_master(cursor, id_turno_master, new_start, new_end, new_id_attivita, new_note)
            
            new_data = {'id_dipendente': master_originale['id_dipendente'], 'data_ora_inizio': new_start, 'data_ora_fine': new_end, 'id_attivita': new_id_attivita, 'note': new_note}
            new_segs = self._split_and_prepare_segments(id_turno_master, new_data)
            self.db_manager.create_registrazioni_segments(cursor, new_segs)

    def delete_master_shift(self, id_turno_master: int):
        with self.db_manager.transaction() as cursor: self.db_manager.delete_turno_master(cursor, id_turno_master)

    def split_master_shift_for_interruption(self, id_turno_master: int, start_interruzione: datetime.datetime, end_interruzione: datetime.datetime):
        with self.db_manager.transaction() as cursor:
            master_originale = self.db_manager.get_turno_master(cursor, id_turno_master)
            if not master_originale: raise ValueError("Turno non trovato.")

            original_start = datetime.datetime.fromisoformat(master_originale['data_ora_inizio_effettiva'])
            original_end = datetime.datetime.fromisoformat(master_originale['data_ora_fine_effettiva'])
            
            if start_interruzione >= end_interruzione or start_interruzione < original_start or end_interruzione > original_end:
                raise ValueError("Interruzione non valida")

            self.db_manager.delete_turno_master(cursor, id_turno_master)
            
            to_create = []
            if original_start < start_interruzione:
                to_create.append({"id_dipendente": master_originale['id_dipendente'], "id_attivita": master_originale['id_attivita'], "data_ora_inizio": original_start, "data_ora_fine": start_interruzione, "note": f"{master_originale.get('note') or ''} (Ante)".strip()})
            if end_interruzione < original_end:
                to_create.append({"id_dipendente": master_originale['id_dipendente'], "id_attivita": master_originale['id_attivita'], "data_ora_inizio": end_interruzione, "data_ora_fine": original_end, "note": f"{master_originale.get('note') or ''} (Post)".strip()})
            
            if to_create:
                for s in to_create:
                    mid = self.db_manager.create_turno_master(cursor, s)
                    segs = self._split_and_prepare_segments(mid, s)
                    self.db_manager.create_registrazioni_segments(cursor, segs)

    # --- 3. LOGICA ENTERPRISE ---
    def _generate_transition_shifts(self, id_dip: int, protocol_type: str, date_change: datetime.date, note: str) -> List[Dict]:
        shifts = []
        if protocol_type == 'DAY_TO_NIGHT': 
            dt1_s = datetime.datetime.combine(date_change, datetime.time(8, 0))
            dt1_e = datetime.datetime.combine(date_change, datetime.time(14, 0))
            dt2_s = datetime.datetime.combine(date_change, datetime.time(20, 0))
            dt2_e = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(6, 0))
            shifts.append({"id_dipendente": id_dip, "data_ora_inizio": dt1_s, "data_ora_fine": dt1_e, "id_attivita": "-1", "note": f"G>N (Mattina) {note}"})
            shifts.append({"id_dipendente": id_dip, "data_ora_inizio": dt2_s, "data_ora_fine": dt2_e, "id_attivita": "-1", "note": f"G>N (Notte) {note}"})

        elif protocol_type == 'NIGHT_TO_DAY': 
            dt_s = datetime.datetime.combine(date_change, datetime.time(20, 0))
            dt_e = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(2, 0))
            dt_day_s = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(8, 0))
            dt_day_e = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(18, 0))
            shifts.append({"id_dipendente": id_dip, "data_ora_inizio": dt_s, "data_ora_fine": dt_e, "id_attivita": "-1", "note": f"N>G (Notte Corta) {note}"})
            shifts.append({"id_dipendente": id_dip, "data_ora_inizio": dt_day_s, "data_ora_fine": dt_day_e, "id_attivita": "-1", "note": f"N>G (Start Giorno) {note}"})
            
        return shifts

    def execute_team_transfer(self, id_dipendente: int, id_target_team: int, protocol_type: str, date_change: datetime.date):
        # 1. SMART DELETE: Cancella SOLO i turni che iniziano DAL giorno del cambio in poi
        days_to_check = [date_change, date_change + datetime.timedelta(days=1)]
        
        for day in days_to_check:
            ids = self.db_manager.get_turni_by_dipendente_date(id_dipendente, day)
            for old_id in ids:
                # Recupera dettagli per verificare la data di inizio
                shift_details = self.db_manager.get_turno_master_details(old_id)
                if shift_details:
                    start_dt = datetime.datetime.fromisoformat(shift_details['data_ora_inizio_effettiva'])
                    
                    # REGOLA D'ORO: Se il turno è iniziato IERI (es. 30 Gen), NON TOCCARLO.
                    # Tocca solo se inizia OGGI (31 Gen) o dopo.
                    if start_dt.date() < date_change:
                        continue 
                    
                    self.delete_master_shift(old_id)

        # 2. Inserimento Raccordo
        shifts = self._generate_transition_shifts(id_dipendente, protocol_type, date_change, "[TRANSFER]")
        self.create_shifts_batch(shifts)

        # 3. HR Transfer
        self.db_manager.transfer_dipendente_to_squadra(id_dipendente, id_target_team)

    # --- 4. READ METHODS ---
    def get_turni_standard(self): return self.db_manager.get_turni_standard()
    def get_squadre(self): return self.db_manager.get_squadre()
    def get_dipendenti_df(self, solo_attivi=False): return self.db_manager.get_dipendenti_df(solo_attivi)
    def get_membri_squadra(self, id_s): return self.db_manager.get_membri_squadra(id_s)
    def check_for_master_overlaps(self, id_d, s, e, ex=None): return self.db_manager.check_for_master_overlaps(id_d, s, e, ex)
    def get_turni_master_giorno_df(self, g): return self.db_manager.get_turni_master_giorno_df(g)
    def get_turni_master_range_df(self, s, e): return self.db_manager.get_turni_master_range_df(s, e)
    def get_report_data_df(self, s, e): return self.db_manager.get_report_data_df(s, e)
    def add_dipendente(self, n, c, r): return self.db_manager.add_dipendente(n, c, r)
    def update_dipendente_field(self, i, f, v): return self.db_manager.update_dipendente_field(i, f, v)
    def add_squadra(self, n, c): return self.db_manager.add_squadra(n, c)
    def update_membri_squadra(self, i, m): return self.db_manager.update_membri_squadra(i, m)
    def update_squadra_details(self, i, n, c): return self.db_manager.update_squadra_details(i, n, c)
    def delete_squadra(self, i): return self.db_manager.delete_squadra(i)
    def get_turni_by_dipendente_date(self, d, t): return self.db_manager.get_turni_by_dipendente_date(d, t)

setup_initial_data()
_db_dao = CrmDBManager(DB_FILE)
shift_service = ShiftService(db_manager=_db_dao)