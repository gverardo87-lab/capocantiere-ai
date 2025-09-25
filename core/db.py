# core/db.py - Versione Finale con ID_Attivita

from __future__ import annotations
import sqlite3
import os
import sys
from typing import List, Dict, Any
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.logic import split_hours

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "capocantiere.db"

class DBManager:
    def __init__(self, db_path: str | Path = DB_FILE):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_schema()
        self._migrate_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executescript("PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS presenze (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                operaio TEXT NOT NULL,
                ruolo TEXT DEFAULT 'Non specificato',
                id_attivita TEXT, -- LA COLONNA CHIAVE
                ore_lavorate REAL NOT NULL,
                ore_regolari REAL NOT NULL,
                ore_straordinario REAL NOT NULL,
                ore_assenza REAL NOT NULL
            )""")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_presenze_data ON presenze(data)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_presenze_id_attivita ON presenze(id_attivita)")
            conn.commit()

    def _migrate_schema(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(presenze)")
            columns = [c[1] for c in cursor.fetchall()]
            
            if 'ruolo' not in columns:
                cursor.execute("ALTER TABLE presenze ADD COLUMN ruolo TEXT DEFAULT 'Non specificato'")
            if 'id_attivita' not in columns:
                cursor.execute("ALTER TABLE presenze ADD COLUMN id_attivita TEXT")
            if 'ore_regolari' not in columns:
                 cursor.execute("ALTER TABLE presenze ADD COLUMN ore_regolari REAL NOT NULL DEFAULT 0")
            if 'ore_straordinario' not in columns:
                 cursor.execute("ALTER TABLE presenze ADD COLUMN ore_straordinario REAL NOT NULL DEFAULT 0")
            if 'ore_assenza' not in columns:
                 cursor.execute("ALTER TABLE presenze ADD COLUMN ore_assenza REAL NOT NULL DEFAULT 0")
            
            conn.commit()

    def update_monthly_timesheet(self, records: List[Dict[str, Any]]):
        if not records: return
        month_to_update = records[0]['data'][:7]
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute("DELETE FROM presenze WHERE strftime('%Y-%m', data) = ?", (month_to_update,))
                for record in records:
                    total_hours = record['ore']
                    calculated_hours = split_hours(total_hours)
                    cursor.execute(
                        "INSERT INTO presenze (data, operaio, ruolo, id_attivita, ore_lavorate, ore_regolari, ore_straordinario, ore_assenza) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (record['data'], record['operaio'], record.get('ruolo'), record.get('id_attivita'),
                         total_hours, calculated_hours['regular'], calculated_hours['overtime'], calculated_hours['absence'])
                    )
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

    def get_all_presence_data(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.cursor().execute("SELECT * FROM presenze ORDER BY data").fetchall()]
            
    def delete_all_presenze(self):
        with self._connect() as conn:
            conn.cursor().execute("DELETE FROM presenze")
            conn.commit()

db_manager = DBManager()