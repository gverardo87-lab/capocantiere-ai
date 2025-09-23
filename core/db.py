# core/db.py
from __future__ import annotations
import sqlite3
import os
import sys
from typing import List, Dict, Any
from pathlib import Path

# Assicuriamoci che il percorso del progetto sia nel path di Python
# per importare correttamente 'logic'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logic import split_hours

# Definiamo il percorso del database nella cartella 'data' del progetto
DB_FILE = Path(__file__).resolve().parents[1] / "data" / "capocantiere.db"

class DBManager:
    """
    Gestore per tutte le operazioni sul database SQLite.
    Questa versione è ottimizzata per la gestione delle sole presenze mensili.
    """
    def __init__(self, db_path: str | Path = DB_FILE):
        self.db_path = Path(db_path)
        # Assicuriamoci che la cartella 'data' dove risiede il DB esista
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        """Stabilisce e restituisce una connessione al database."""
        conn = sqlite3.connect(self.db_path)
        # Usiamo Row Factory per poter accedere ai risultati per nome di colonna
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """
        Crea la tabella 'presenze' e imposta le configurazioni iniziali.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS presenze (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                operaio TEXT NOT NULL,
                ore_lavorate REAL NOT NULL,
                ore_regolari REAL NOT NULL,
                ore_straordinario REAL NOT NULL,
                ore_assenza REAL NOT NULL,
                UNIQUE(data, operaio)
            )""")
            conn.commit()

    def update_monthly_timesheet(self, records: List[Dict[str, Any]]):
        """
        Aggiorna (sovrascrive) i dati di un intero mese in modo transazionale.
        """
        if not records:
            print("Nessun record da inserire. Operazione annullata.")
            return

        month_to_update = records[0]['data'][:7]

        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute("DELETE FROM presenze WHERE strftime('%Y-%m', data) = ?", (month_to_update,))
                for record in records:
                    total_hours = record['ore']
                    calculated_hours = split_hours(total_hours)
                    cursor.execute("""
                        INSERT INTO presenze (data, operaio, ore_lavorate, ore_regolari, ore_straordinario, ore_assenza)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        record['data'],
                        record['operaio'],
                        total_hours,
                        calculated_hours['regular'],
                        calculated_hours['overtime'],
                        calculated_hours['absence']
                    ))
                conn.commit()
                print(f"Dati per il mese {month_to_update} aggiornati con successo: {len(records)} record inseriti.")
            except Exception as e:
                print(f"ERRORE: La transazione per il mese {month_to_update} è stata annullata. {e}")
                conn.rollback()

    def get_presence_data(self, year: int, month: int) -> List[Dict[str, Any]]:
        """
        Estrae i dati delle presenze per un dato mese e anno.
        """
        month_str = f"{year}-{str(month).zfill(2)}"
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM presenze WHERE strftime('%Y-%m', data) = ? ORDER BY data, operaio",
                (month_str,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_all_presenze(self):
        """
        **FUNZIONE AGGIUNTA**
        Cancella tutti i record dalla tabella 'presenze'.
        Funzione di utilità per il bottone di reset.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute("DELETE FROM presenze")
                conn.commit()
                print("INFO: Tutti i dati delle presenze sono stati cancellati.")
            except Exception as e:
                print(f"ERRORE: Impossibile cancellare i dati. Transazione annullata. {e}")
                conn.rollback()

# Istanza globale, come nell'originale, per un facile accesso
db_manager = DBManager()