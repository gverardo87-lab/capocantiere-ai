# core/shift_service.py (Versione 31.0 - Storicizzazione Squadra)
from __future__ import annotations
import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

from core.crm_db import CrmDBManager, DB_FILE, setup_initial_data
from core.logic import ShiftEngine

class ShiftService:
    def __init__(self, db_manager: CrmDBManager):
        self.db_manager = db_manager

    # --- CORE LOGIC ---
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

    # --- BATCH CON POLICY E STORICIZZAZIONE ---
    def create_shifts_batch(self, shifts_data: List[Dict[str, Any]], conflict_policy: str = 'error') -> Dict[str, Any]:
        """
        Crea batch di turni salvando anche l'ID SQUADRA.
        """
        if not shifts_data: return {'created': 0, 'skipped': [], 'overwritten': []}
        
        results = {'created': 0, 'skipped': [], 'overwritten': []}
        
        with self.db_manager.transaction() as cursor:
            for shift in shifts_data:
                id_dip = shift['id_dipendente']
                start = shift['data_ora_inizio']
                end = shift['data_ora_fine']

                # Verifica conflitto
                if self.db_manager.check_for_master_overlaps(id_dip, start, end):
                    if conflict_policy == 'error':
                        raise ValueError(f"CONFLITTO: Dipendente {id_dip} occupato in {start}-{end}")
                    
                    elif conflict_policy == 'skip':
                        results['skipped'].append(str(id_dip))
                        continue 
                    
                    elif conflict_policy == 'overwrite':
                        self.db_manager.delete_overlaps_on_cursor(cursor, id_dip, start, end)
                        results['overwritten'].append(str(id_dip))

                # CREAZIONE MASTER (Ora supporta id_squadra nel DAO)
                master_id = self.db_manager.create_turno_master(cursor, shift)
                
                # CREAZIONE SEGMENTI
                segments = self._split_and_prepare_segments(master_id, shift)
                self.db_manager.create_registrazioni_segments(cursor, segments)
                results['created'] += len(segments)
                
        return results

    # --- TRANSITION & HR (Con Squadra Target) ---
    def _generate_transition_shifts(self, id_dip: int, id_sq: int, protocol_type: str, date_change: datetime.date, note: str) -> List[Dict]:
        """Genera i turni di transizione associandoli alla NUOVA squadra (o quella di transizione)."""
        shifts = []
        if protocol_type == 'DAY_TO_NIGHT': 
            dt1_s = datetime.datetime.combine(date_change, datetime.time(8, 0))
            dt1_e = datetime.datetime.combine(date_change, datetime.time(14, 0))
            dt2_s = datetime.datetime.combine(date_change, datetime.time(20, 0))
            dt2_e = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(6, 0))
            
            # Nota: id_squadra viene passato qui
            shifts.append({"id_dipendente": id_dip, "id_squadra": id_sq, "data_ora_inizio": dt1_s, "data_ora_fine": dt1_e, "id_attivita": "-1", "note": f"G>N (Mattina) {note}"})
            shifts.append({"id_dipendente": id_dip, "id_squadra": id_sq, "data_ora_inizio": dt2_s, "data_ora_fine": dt2_e, "id_attivita": "-1", "note": f"G>N (Notte) {note}"})

        elif protocol_type == 'NIGHT_TO_DAY': 
            dt_s = datetime.datetime.combine(date_change, datetime.time(20, 0))
            dt_e = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(2, 0))
            dt_day_s = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(8, 0))
            dt_day_e = datetime.datetime.combine(date_change + datetime.timedelta(days=1), datetime.time(18, 0))
            
            shifts.append({"id_dipendente": id_dip, "id_squadra": id_sq, "data_ora_inizio": dt_s, "data_ora_fine": dt_e, "id_attivita": "-1", "note": f"N>G (Notte Corta) {note}"})
            shifts.append({"id_dipendente": id_dip, "id_squadra": id_sq, "data_ora_inizio": dt_day_s, "data_ora_fine": dt_day_e, "id_attivita": "-1", "note": f"N>G (Start Giorno) {note}"})
            
        return shifts

    def execute_team_transfer(self, id_dipendente: int, id_target_team: int, protocol_type: str, date_change: datetime.date):
        # 1. SMART DELETE
        days_to_check = [date_change, date_change + datetime.timedelta(days=1)]
        for day in days_to_check:
            ids = self.db_manager.get_turni_by_dipendente_date(id_dipendente, day)
            for old_id in ids:
                details = self.db_manager.get_turno_master_details(old_id)
                if details:
                    start = datetime.datetime.fromisoformat(details['data_ora_inizio_effettiva'])
                    if start.date() < date_change: continue
                    self.delete_master_shift(old_id)

        # 2. INSERT (Passiamo ID Squadra Target)
        shifts = self._generate_transition_shifts(id_dipendente, id_target_team, protocol_type, date_change, "[TRANSFER]")
        self.create_shifts_batch(shifts, conflict_policy='overwrite')

        # 3. TRANSFER
        self.db_manager.transfer_dipendente_to_squadra(id_dipendente, id_target_team)

    # --- STANDARD METHODS (Invariati) ---
    def update_master_shift(self, id_m, s, e, act, n):
        with self.db_manager.transaction() as cur:
            orig = self.db_manager.get_turno_master(cur, id_m)
            self.db_manager.update_turno_master(cur, id_m, s, e, act, n)
            segs = self._split_and_prepare_segments(id_m, {'id_dipendente': orig['id_dipendente'], 'data_ora_inizio': s, 'data_ora_fine': e, 'id_attivita': act, 'note': n})
            self.db_manager.create_registrazioni_segments(cur, segs)
    def delete_master_shift(self, id_m):
        with self.db_manager.transaction() as cur: self.db_manager.delete_turno_master(cur, id_m)
    def split_master_shift_for_interruption(self, id_m, s, e):
        with self.db_manager.transaction() as cur:
            orig = self.db_manager.get_turno_master(cur, id_m)
            self.db_manager.delete_turno_master(cur, id_m)
            s_orig = datetime.datetime.fromisoformat(orig['data_ora_inizio_effettiva'])
            e_orig = datetime.datetime.fromisoformat(orig['data_ora_fine_effettiva'])
            sq = orig.get('id_squadra') # Preserva squadra esistente
            
            if s_orig < s:
                mid = self.db_manager.create_turno_master(cur, {'id_dipendente':orig['id_dipendente'], 'id_squadra':sq, 'data_ora_inizio':s_orig, 'data_ora_fine':s, 'id_attivita':orig['id_attivita'], 'note':f"{orig.get('note')} (Ante)"})
                self.db_manager.create_registrazioni_segments(cur, self._split_and_prepare_segments(mid, {'id_dipendente':orig['id_dipendente'], 'data_ora_inizio':s_orig, 'data_ora_fine':s, 'id_attivita':orig['id_attivita'], 'note':f"{orig.get('note')} (Ante)"}))
            if e < e_orig:
                mid = self.db_manager.create_turno_master(cur, {'id_dipendente':orig['id_dipendente'], 'id_squadra':sq, 'data_ora_inizio':e, 'data_ora_fine':e_orig, 'id_attivita':orig['id_attivita'], 'note':f"{orig.get('note')} (Post)"})
                self.db_manager.create_registrazioni_segments(cur, self._split_and_prepare_segments(mid, {'id_dipendente':orig['id_dipendente'], 'data_ora_inizio':e, 'data_ora_fine':e_orig, 'id_attivita':orig['id_attivita'], 'note':f"{orig.get('note')} (Post)"}))

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