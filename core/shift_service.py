# core/shift_service.py (Versione 14.0 - Enterprise Logic)
from __future__ import annotations
import datetime
from typing import List, Dict, Any, Optional

from core.crm_db import CrmDBManager

class ShiftService:
    """
    Service Layer per la gestione centralizzata della logica di business dei turni.
    Questa classe è l'unica fonte di verità per le operazioni complesse sui turni,
    garantendo una netta separazione tra logica di business e accesso ai dati.
    """
    def __init__(self, db_manager: CrmDBManager):
        self.db_manager = db_manager

    def _split_and_prepare_segments(self, id_turno_master: int, shift_data: Dict[str, Any]) -> List[tuple]:
        """
        Divide un turno master nei suoi segmenti contabili (es. a mezzanotte).
        Questa logica ora vive nel service layer, vicino al business process.
        """
        start = shift_data['data_ora_inizio']
        end = shift_data['data_ora_fine']
        note = shift_data.get('note') or ''

        # Caso 1: il turno non scavalca la mezzanotte
        if start.date() == end.date():
            return [(
                id_turno_master,
                shift_data['id_dipendente'], shift_data.get('id_attivita'),
                start, end, note
            )]

        # Caso 2: il turno scavalca la mezzanotte
        mezzanotte = (start + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        # Caso speciale in cui il turno finisce esattamente a mezzanotte del giorno dopo
        if end == mezzanotte:
             return [(
                id_turno_master,
                shift_data['id_dipendente'], shift_data.get('id_attivita'),
                start, end, note
            )]

        # Creazione dei due segmenti
        segment1 = (
            id_turno_master,
            shift_data['id_dipendente'], shift_data.get('id_attivita'),
            start, mezzanotte, f"{note} (Parte 1)".strip()
        )
        segment2 = (
            id_turno_master,
            shift_data['id_dipendente'], shift_data.get('id_attivita'),
            mezzanotte, end, f"{note} (Parte 2)".strip()
        )
        return [segment1, segment2]

    def create_shifts_batch(self, shifts_data: List[Dict[str, Any]]) -> int:
        """
        Crea uno o più turni in modo transazionale e sicuro.
        Sostituisce la vecchia `crea_registrazioni_batch`.
        """
        if not shifts_data:
            return 0

        total_segments_created = 0
        with self.db_manager.transaction() as cursor:
            for shift in shifts_data:
                id_dipendente = shift['id_dipendente']
                start_time = shift['data_ora_inizio']
                end_time = shift['data_ora_fine']

                # 1. Validazione: controlla sovrapposizioni sul master
                if self.db_manager.check_for_master_overlaps(id_dipendente, start_time, end_time):
                    # Idealmente, qui si dovrebbe fornire un feedback più granulare
                    raise ValueError(f"Sovrapposizione rilevata per il dipendente {id_dipendente} nell'intervallo {start_time} - {end_time}")

                # 2. Crea il record master
                master_id = self.db_manager.create_turno_master(cursor, shift)

                # 3. Crea i segmenti contabili
                segments = self._split_and_prepare_segments(master_id, shift)
                self.db_manager.create_registrazioni_segments(cursor, segments)
                total_segments_created += len(segments)

        return total_segments_created

    def update_shift_from_segment(
        self, id_registrazione: int, new_segment_start: datetime.datetime,
        new_segment_end: datetime.datetime, new_id_attivita: Optional[str], new_note: Optional[str]):
        """
        Aggiorna un intero turno (anche splittato) partendo dalla modifica di un suo segmento.
        Questa è la soluzione definitiva e robusta al problema originale.
        """
        with self.db_manager.transaction() as cursor:
            # 1. Trova il master dal segmento che si sta modificando
            segmento_originale = self.db_manager.get_registrazione(cursor, id_registrazione)
            if not segmento_originale or not segmento_originale['id_turno_master']:
                raise ValueError(f"Impossibile aggiornare: il segmento {id_registrazione} non è valido o è un record obsoleto.")

            id_master = segmento_originale['id_turno_master']
            master_originale = self.db_manager.get_turno_master(cursor, id_master)
            if not master_originale:
                 raise ValueError(f"Inconsistenza del database: master non trovato per il segmento {id_registrazione}.")

            # 2. Ricostruisci l'intervallo del nuovo turno completo
            master_start_originale = datetime.datetime.fromisoformat(master_originale['data_ora_inizio_effettiva'])

            # Se il segmento originale finiva a mezzanotte, era la "Parte 1"
            segmento_originale_end = datetime.datetime.fromisoformat(segmento_originale['data_ora_fine'])
            era_parte_1 = (segmento_originale_end.time() == datetime.time(0, 0))

            if era_parte_1:
                full_new_start = new_segment_start
                full_new_end = datetime.datetime.fromisoformat(master_originale['data_ora_fine_effettiva'])
            else: # Era la "Parte 2" o un turno non splittato
                full_new_start = master_start_originale
                full_new_end = new_segment_end

            # 3. Validazione: controlla sovrapposizioni per il nuovo turno completo, escludendo se stesso
            if self.db_manager.check_for_master_overlaps(
                master_originale['id_dipendente'], full_new_start, full_new_end, exclude_master_id=id_master):
                raise ValueError("La modifica causa una sovrapposizione con un altro turno.")

            # 4. Aggiorna il master (i segmenti verranno cancellati in cascata grazie a ON DELETE CASCADE)
            self.db_manager.update_turno_master(
                cursor, id_master, full_new_start, full_new_end, new_id_attivita, new_note)

            # 5. Ricrea i segmenti a partire dal master aggiornato
            new_master_data = {
                'id_dipendente': master_originale['id_dipendente'],
                'data_ora_inizio': full_new_start,
                'data_ora_fine': full_new_end,
                'id_attivita': new_id_attivita,
                'note': new_note
            }
            new_segments = self._split_and_prepare_segments(id_master, new_master_data)
            self.db_manager.create_registrazioni_segments(cursor, new_segments)

    def delete_shift_from_segment(self, id_registrazione: int):
        """
        Elimina un intero turno (master e segmenti) partendo dall'ID di un suo segmento.
        """
        with self.db_manager.transaction() as cursor:
            segmento = self.db_manager.get_registrazione(cursor, id_registrazione)
            if not segmento or not segmento['id_turno_master']:
                # Record vecchio o orfano, lo eliminiamo direttamente
                self.db_manager.delete_registrazione(cursor, id_registrazione)
                return

            # Elimina il master, i segmenti verranno rimossi in cascata
            self.db_manager.delete_turno_master(cursor, segmento['id_turno_master'])

# Istanza globale del servizio per un facile accesso dall'UI
shift_service = ShiftService(db_manager=CrmDBManager())
