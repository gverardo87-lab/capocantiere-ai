# core/db.py - Aggiornato con supporto per ruoli
from __future__ import annotations
import sqlite3
import os
import sys
from typing import List, Dict, Any
from pathlib import Path

# Assicuriamoci che il percorso del progetto sia nel path di Python
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logic import split_hours

# Definiamo il percorso del database nella cartella 'data' del progetto
DB_FILE = Path(__file__).resolve().parents[1] / "data" / "capocantiere.db"

class DBManager:
    """
    Gestore per tutte le operazioni sul database SQLite.
    Versione aggiornata con supporto per ruoli degli operai.
    """
    def __init__(self, db_path: str | Path = DB_FILE):
        self.db_path = Path(db_path)
        # Assicuriamoci che la cartella 'data' dove risiede il DB esista
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_schema()
        self._migrate_schema()

    def _connect(self) -> sqlite3.Connection:
        """Stabilisce e restituisce una connessione al database."""
        conn = sqlite3.connect(self.db_path)
        # Usiamo Row Factory per poter accedere ai risultati per nome di colonna
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """
        Crea la tabella 'presenze' e imposta le configurazioni iniziali.
        Include la nuova colonna 'ruolo' per tracciare il ruolo di ogni operaio.
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
                ruolo TEXT DEFAULT 'Non specificato',
                ore_lavorate REAL NOT NULL,
                ore_regolari REAL NOT NULL,
                ore_straordinario REAL NOT NULL,
                ore_assenza REAL NOT NULL,
                UNIQUE(data, operaio)
            )""")
            
            # Indici per performance ottimali
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_presenze_data 
            ON presenze(data)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_presenze_operaio 
            ON presenze(operaio)
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_presenze_ruolo 
            ON presenze(ruolo)
            """)
            
            conn.commit()

    def _migrate_schema(self):
        """
        Migra lo schema del database se necessario.
        Aggiunge la colonna 'ruolo' se non esiste già.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            
            # Verifica se la colonna ruolo esiste
            cursor.execute("PRAGMA table_info(presenze)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'ruolo' not in columns:
                print("📦 Migrazione database: aggiunta colonna 'ruolo'...")
                cursor.execute("""
                ALTER TABLE presenze 
                ADD COLUMN ruolo TEXT DEFAULT 'Non specificato'
                """)
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_presenze_ruolo 
                ON presenze(ruolo)
                """)
                conn.commit()
                print("✅ Migrazione completata con successo")

    def update_monthly_timesheet(self, records: List[Dict[str, Any]]):
        """
        Aggiorna (sovrascrive) i dati di un intero mese in modo transazionale.
        Ora include il ruolo di ogni operaio.
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
                    ruolo = record.get('ruolo', 'Non specificato')
                    
                    cursor.execute("""
                        INSERT INTO presenze (data, operaio, ruolo, ore_lavorate, ore_regolari, ore_straordinario, ore_assenza)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record['data'],
                        record['operaio'],
                        ruolo,
                        total_hours,
                        calculated_hours['regular'],
                        calculated_hours['overtime'],
                        calculated_hours['absence']
                    ))
                
                conn.commit()
                
                # Report sui ruoli inseriti
                cursor.execute("""
                    SELECT ruolo, COUNT(DISTINCT operaio) as num_operai
                    FROM presenze 
                    WHERE strftime('%Y-%m', data) = ?
                    GROUP BY ruolo
                """, (month_to_update,))
                
                role_stats = cursor.fetchall()
                print(f"✅ Dati per il mese {month_to_update} aggiornati: {len(records)} record inseriti")
                print("📊 Distribuzione ruoli:")
                for stat in role_stats:
                    print(f"   - {stat['ruolo']}: {stat['num_operai']} operai")
                    
            except Exception as e:
                print(f"ERRORE: La transazione per il mese {month_to_update} è stata annullata. {e}")
                conn.rollback()

    def get_presence_data(self, year: int, month: int) -> List[Dict[str, Any]]:
        """
        Estrae i dati delle presenze per un dato mese e anno.
        Include il ruolo di ogni operaio.
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

    def get_workers_by_role(self, role: str = None) -> List[Dict[str, Any]]:
        """
        Ottiene la lista di operai filtrata per ruolo.
        Se role è None, ritorna tutti gli operai con i loro ruoli.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            
            if role:
                cursor.execute("""
                    SELECT DISTINCT operaio, ruolo,
                           SUM(ore_lavorate) as totale_ore,
                           SUM(ore_straordinario) as totale_straordinari,
                           SUM(ore_assenza) as totale_assenze
                    FROM presenze
                    WHERE ruolo = ?
                    GROUP BY operaio, ruolo
                    ORDER BY operaio
                """, (role,))
            else:
                cursor.execute("""
                    SELECT DISTINCT operaio, ruolo,
                           SUM(ore_lavorate) as totale_ore,
                           SUM(ore_straordinario) as totale_straordinari,
                           SUM(ore_assenza) as totale_assenze
                    FROM presenze
                    GROUP BY operaio, ruolo
                    ORDER BY ruolo, operaio
                """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_role_statistics(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """
        Ottiene statistiche aggregate per ruolo.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            
            where_clause = ""
            params = []
            
            if year and month:
                where_clause = "WHERE strftime('%Y-%m', data) = ?"
                params.append(f"{year}-{str(month).zfill(2)}")
            elif year:
                where_clause = "WHERE strftime('%Y', data) = ?"
                params.append(str(year))
            
            query = f"""
                SELECT ruolo,
                       COUNT(DISTINCT operaio) as num_operai,
                       SUM(ore_lavorate) as totale_ore,
                       SUM(ore_regolari) as totale_ore_regolari,
                       SUM(ore_straordinario) as totale_straordinari,
                       SUM(ore_assenza) as totale_assenze,
                       AVG(ore_lavorate) as media_ore_giornaliere
                FROM presenze
                {where_clause}
                GROUP BY ruolo
                ORDER BY totale_ore DESC
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return {
                'statistics': [dict(row) for row in rows],
                'period': {
                    'year': year,
                    'month': month
                }
            }

    def delete_all_presenze(self):
        """
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