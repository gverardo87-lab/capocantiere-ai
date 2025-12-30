# core/shift_service.py (Versione 27.0 - Workflow Enterprise)
from __future__ import annotations
import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

from core.crm_db import CrmDBManager, DB_FILE, setup_initial_data
from core.logic import ShiftEngine

class ShiftService:
    def __init__(self, db_manager: CrmDBManager):
        self.db_manager = db_manager

    # ... [Mantieni _split_and_prepare_segments e create_shifts_batch uguali a prima] ...
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
        
        if end == mezzanotte:
             return [create_segment_tuple(start, end, note)]

        segment1 = create_segment_tuple(start, mezzanotte, f"{note} (Parte 1)".strip())
        segment2 = create_segment_tuple(mezzanotte, end, f"{note} (Parte 2)".strip())
        
        return [segment1, segment2]

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
        
    # --- METODI DI SUPPORTO PER LA TRANSIZIONE ORARIA (Privati o Helper) ---
    def _generate_transition_shifts(self, id_dip: int, protocol_type: str, date_change: datetime.date, note: str) -> List[Dict]:
        """Genera solo i dizionari dei turni, senza salvarli."""
        shifts = []
        if protocol_type == 'DAY_TO_NIGHT':
            # G>N: 08-14 + 20-06
            dt1_s = datetime.datetime.combine(date_change, datetime.time(8, 0))
            dt1_e = datetime.datetime.combine(date_change, datetime.time(14, 0))
            dt2_s = datetime.datetime.combine(date_change, datetime.time(20, 0))
            dt2_e = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(6, 0))
            
            shifts.append({"id_dipendente": id_dip, "data_ora_inizio": dt1_s, "data_ora_fine": dt1_e, "id_attivita": "-1", "note": f"Transizione G>N (Mattina) {note}"})
            shifts.append({"id_dipendente": id_dip, "data_ora_inizio": dt2_s, "data_ora_fine": dt2_e, "id_attivita": "-1", "note": f"Transizione G>N (Start Notte) {note}"})

        elif protocol_type == 'NIGHT_TO_DAY':
            # N>G: 20-02 + 08-18 (Giorno Dopo)
            # Notte Corta
            dt_short_s = datetime.datetime.combine(date_change, datetime.time(20, 0))
            dt_short_e = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(2, 0))
            # Primo Giorno Nuovo Ciclo
            dt_day_s = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(8, 0))
            dt_day_e = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(18, 0))
            
            shifts.append({"id_dipendente": id_dip, "data_ora_inizio": dt_short_s, "data_ora_fine": dt_short_e, "id_attivita": "-1", "note": f"Transizione N>G (Notte Corta) {note}"})
            shifts.append({"id_dipendente": id_dip, "data_ora_inizio": dt_day_s, "data_ora_fine": dt_day_e, "id_attivita": "-1", "note": f"Inizio Ciclo Giorno (Nuova Squadra) {note}"})
            
        return shifts

    # --- IL METODO "SAP" DEFINITIVO ---
    def execute_team_transfer(self, id_dipendente: int, id_target_team: int, protocol_type: str, date_change: datetime.date):
        """
        Esegue un TRASFERIMENTO COMPLETO:
        1. Pulisce i turni del dipendente nel giorno del cambio (e indomani mattina).
        2. Inserisce i turni di transizione (6+4).
        3. SPOSTA strutturalmente il dipendente nella nuova squadra nel DB.
        """
        
        # 1. PULIZIA ORARIA (Override sul giorno del cambio)
        days_to_clean = [date_change, date_change + datetime.timedelta(days=1)]
        for day in days_to_clean:
            ids = self.db_manager.get_turni_by_dipendente_date(id_dipendente, day)
            for old in ids: self.delete_master_shift(old)

        # 2. GENERAZIONE TURNI DI RACCORDO
        shifts_to_create = self._generate_transition_shifts(id_dipendente, protocol_type, date_change, "[TRANSFER]")
        self.create_shifts_batch(shifts_to_create)

        # 3. CAMBIO SQUADRA STRUTTURALE (DB)
        # Questo è il cuore del CRM: da ora in poi, lui appartiene alla nuova squadra.
        self.db_manager.transfer_dipendente_to_squadra(id_dipendente, id_target_team)

        return len(shifts_to_create)

    # ... [Metodi pass-through CRUD e Getters standard] ...
    def update_master_shift(self, id_m, s, e, act, n):
        with self.db_manager.transaction() as cur:
            orig = self.db_manager.get_turno_master(cur, id_m)
            self.db_manager.update_turno_master(cur, id_m, s, e, act, n)
            segs = self._split_and_prepare_segments(id_m, {'id_dipendente': orig['id_dipendente'], 'data_ora_inizio': s, 'data_ora_fine': e, 'id_attivita': act, 'note': n})
            self.db_manager.create_registrazioni_segments(cur, segs)
    def delete_master_shift(self, id_m):
        with self.db_manager.transaction() as cur: self.db_manager.delete_turno_master(cur, id_m)
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
    # Aggiungi questo pass-through
    def get_turni_by_dipendente_date(self, d, t): return self.db_manager.get_turni_by_dipendente_date(d, t)

setup_initial_data()
_db_dao = CrmDBManager(DB_FILE)
shift_service = ShiftService(db_manager=_db_dao)