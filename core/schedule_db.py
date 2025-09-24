# core/schedule_db.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List, Dict, Any

# Definiamo un percorso dedicato per il database dei cronoprogrammi
DB_FILE = Path(__file__).resolve().parents[1] / "data" / "schedule.db"

class ScheduleDBManager:
    """
    Gestore dedicato esclusivamente alle operazioni sul database dei cronoprogrammi.
    """
    def __init__(self, db_path: str | Path = DB_FILE):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        """Stabilisce e restituisce una connessione al database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """
        Crea la tabella 'cronoprogramma' se non esiste.
        Questa tabella conterrà tutte le attività pianificate.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cronoprogramma (
                id_attivita TEXT PRIMARY KEY,
                descrizione TEXT NOT NULL,
                data_inizio DATE NOT NULL,
                data_fine DATE NOT NULL,
                stato_avanzamento INTEGER DEFAULT 0,
                commessa TEXT,
                predecessori TEXT
            )""")
            conn.commit()

    def update_schedule(self, records: List[Dict[str, Any]]):
        """
        Aggiorna il cronoprogramma in modo transazionale.
        Usa INSERT OR REPLACE per inserire nuove attività o aggiornare quelle esistenti
        basandosi sulla chiave primaria 'id_attivita'.
        """
        if not records:
            return

        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                for record in records:
                    cursor.execute("""
                        INSERT OR REPLACE INTO cronoprogramma (id_attivita, descrizione, data_inizio, data_fine, stato_avanzamento, commessa, predecessori)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record['id_attivita'],
                        record['descrizione'],
                        record['data_inizio'],
                        record['data_fine'],
                        record.get('stato_avanzamento', 0),
                        record.get('commessa'),
                        record.get('predecessori')
                    ))
                conn.commit()
                print(f"{len(records)} record del cronoprogramma sono stati aggiornati/inseriti.")
            except Exception as e:
                print(f"ERRORE: La transazione del cronoprogramma è stata annullata. {e}")
                conn.rollback()

    def get_schedule_data(self, commessa: str = None) -> List[Dict[str, Any]]:
        """
        Estrae i dati del cronoprogramma, opzionalmente filtrando per commessa.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM cronoprogramma"
            params = []
            if commessa:
                query += " WHERE commessa = ?"
                params.append(commessa)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

# Istanza globale per un facile accesso
schedule_db_manager = ScheduleDBManager()