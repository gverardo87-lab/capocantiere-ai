# file: core/crm_db.py (Versione 16.4 - BUG FIX Corretto per ON DELETE CASCADE)
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime
import pandas as pd
from contextlib import contextmanager

# Importa la nostra fonte di verità per i calcoli
from core.logic import calculate_duration_hours

# Percorso DB (esportato per il service)
DB_FILE = Path(__file__).resolve().parents[1] / "data" / "crm.db"

class CrmDBManager:
    """
    Data Access Layer (DAO) per il modulo CRM.
    Questa classe gestisce ESCLUSIVAMENTE le query SQL dirette.
    NON contiene logica di business (che si trova in ShiftService).
    """
    def __init__(self, db_path: str | Path = DB_FILE):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        """
        Stabilisce e restituisce una connessione al database.
        ★ BUG FIX: Abilita il supporto alle foreign key (per ON DELETE CASCADE)
        su OGNI connessione, non solo all'init.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;") # <-- ★ BUG FIX ★
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """Inizializza lo schema del database."""
        with self._connect() as conn:
            cursor = conn.cursor()
            # La PRAGMA foreign_keys = ON è ora gestita in _connect()
            # Non è più necessario eseguirla qui.

            # --- Tabelle Principali ---
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS anagrafica_dipendenti (
                id_dipendente INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cognome TEXT NOT NULL,
                ruolo TEXT,
                attivo BOOLEAN DEFAULT 1 NOT NULL
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS squadre (
                id_squadra INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_squadra TEXT UNIQUE NOT NULL,
                id_caposquadra INTEGER,
                FOREIGN KEY (id_caposquadra) REFERENCES anagrafica_dipendenti (id_dipendente)
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS membri_squadra (
                id_squadra INTEGER,
                id_dipendente INTEGER,
                PRIMARY KEY (id_squadra, id_dipendente),
                FOREIGN KEY (id_squadra) REFERENCES squadre (id_squadra) ON DELETE CASCADE,
                FOREIGN KEY (id_dipendente) REFERENCES anagrafica_dipendenti (id_dipendente)
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS turni_standard (
                id_turno TEXT PRIMARY KEY,
                nome_turno TEXT NOT NULL,
                ora_inizio TIME NOT NULL,
                ora_fine TIME NOT NULL,
                scavalca_mezzanotte BOOLEAN NOT NULL
            )""")

            # --- ★ ARCHITETTURA TURNI ★ ---
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS turni_master (
                id_turno_master INTEGER PRIMARY KEY AUTOINCREMENT,
                id_dipendente INTEGER NOT NULL,
                data_ora_inizio_effettiva DATETIME NOT NULL,
                data_ora_fine_effettiva DATETIME NOT NULL,
                note TEXT,
                id_attivita TEXT,
                FOREIGN KEY (id_dipendente) REFERENCES anagrafica_dipendenti (id_dipendente)
            )""")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS registrazioni_ore (
                id_registrazione INTEGER PRIMARY KEY AUTOINCREMENT,
                id_turno_master INTEGER,
                id_dipendente INTEGER NOT NULL,
                id_attivita TEXT,
                data_ora_inizio DATETIME NOT NULL,
                data_ora_fine DATETIME NOT NULL,
                tipo_ore TEXT DEFAULT 'Cantiere',
                note TEXT,
                FOREIGN KEY (id_dipendente) REFERENCES anagrafica_dipendenti (id_dipendente),
                FOREIGN KEY (id_turno_master) REFERENCES turni_master (id_turno_master) ON DELETE CASCADE
            )""")

            conn.commit()

    @contextmanager
    def transaction(self):
        """Fornisce un context manager per le transazioni atomiche."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # --- METODI DAO PER ANAGRAFICA, SQUADRE, TURNI STANDARD ---
    
    def add_dipendente(self, nome: str, cognome: str, ruolo: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute("INSERT INTO anagrafica_dipendenti (nome, cognome, ruolo) VALUES (?, ?, ?)", (nome, cognome, ruolo))
            conn.commit()
            return cursor.lastrowid

    def get_dipendenti_df(self, solo_attivi: bool = False) -> pd.DataFrame:
        query = "SELECT id_dipendente, nome, cognome, ruolo, attivo FROM anagrafica_dipendenti"
        if solo_attivi: query += " WHERE attivo = 1"
        query += " ORDER BY cognome, nome"
        with self._connect() as conn:
            return pd.read_sql_query(query, conn, index_col="id_dipendente")

    def update_dipendente_field(self, id_dipendente: int, field_name: str, new_value):
        allowed_fields = ['nome', 'cognome', 'ruolo', 'attivo']
        if field_name not in allowed_fields:
            raise ValueError(f"Campo '{field_name}' non modificabile")
        with self._connect() as conn:
            query = f"UPDATE anagrafica_dipendenti SET {field_name} = ? WHERE id_dipendente = ?"
            conn.execute(query, (new_value, id_dipendente))
            conn.commit()

    def add_squadra(self, nome_squadra: str, id_caposquadra: Optional[int]) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute("INSERT INTO squadre (nome_squadra, id_caposquadra) VALUES (?, ?)", (nome_squadra, id_caposquadra))
                new_squadra_id = cursor.lastrowid
                if id_caposquadra is not None:
                    cursor.execute("INSERT INTO membri_squadra (id_squadra, id_dipendente) VALUES (?, ?)", (new_squadra_id, id_caposquadra))
                conn.commit()
                return new_squadra_id
            except Exception as e:
                conn.rollback()
                raise e

    def update_membri_squadra(self, id_squadra: int, membri_ids: List[int]):
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute("DELETE FROM membri_squadra WHERE id_squadra = ?", (id_squadra,))
                if membri_ids:
                    data_to_insert = [(id_squadra, id_dip) for id_dip in list(set(membri_ids))]
                    cursor.executemany("INSERT INTO membri_squadra (id_squadra, id_dipendente) VALUES (?, ?)", data_to_insert)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

    def get_turni_standard(self) -> List[Dict[str, Any]]:
         with self._connect() as conn:
            rows = conn.execute("SELECT * FROM turni_standard ORDER BY nome_turno").fetchall()
            return [dict(row) for row in rows]
            
    def get_squadre(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM squadre ORDER BY nome_squadra").fetchall()
            return [dict(row) for row in rows]

    def insert_turno_standard(self, id_turno: str, nome: str, inizio: str, fine: str, scavalca: bool):
         with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO turni_standard (id_turno, nome_turno, ora_inizio, ora_fine, scavalca_mezzanotte) VALUES (?, ?, ?, ?, ?)",
                (id_turno, nome, inizio, fine, scavalca)
            )
            conn.commit()

    def update_squadra_details(self, id_squadra: int, nome_squadra: str, id_caposquadra: Optional[int]):
        with self._connect() as conn:
            conn.execute(
                "UPDATE squadre SET nome_squadra = ?, id_caposquadra = ? WHERE id_squadra = ?",
                (nome_squadra, id_caposquadra, id_squadra)
            )
            conn.commit()

    def delete_squadra(self, id_squadra: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM squadre WHERE id_squadra = ?", (id_squadra,))
            conn.commit()

    def get_membri_squadra(self, id_squadra: int) -> List[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id_dipendente FROM membri_squadra WHERE id_squadra = ?",
                (id_squadra,)
            ).fetchall()
            return [row['id_dipendente'] for row in rows]

    # --- METODI DAO PER TURNI MASTER E SEGMENTI ---
    
    def get_registrazione(self, cursor: sqlite3.Cursor, id_registrazione: int) -> Optional[sqlite3.Row]:
        cursor.execute("SELECT * FROM registrazioni_ore WHERE id_registrazione = ?", (id_registrazione,))
        return cursor.fetchone()

    def get_turno_master(self, cursor: sqlite3.Cursor, id_turno_master: int) -> Optional[sqlite3.Row]:
        cursor.execute("SELECT * FROM turni_master WHERE id_turno_master = ?", (id_turno_master,))
        return cursor.fetchone()

    def check_for_master_overlaps(self, id_dipendente: int, start_time: datetime.datetime, end_time: datetime.datetime, exclude_master_id: Optional[int] = None) -> bool:
        query = "SELECT 1 FROM turni_master WHERE id_dipendente = ? AND data_ora_inizio_effettiva < ? AND data_ora_fine_effettiva > ?"
        params = [id_dipendente, end_time.isoformat(), start_time.isoformat()]
        if exclude_master_id is not None:
            query += " AND id_turno_master != ?"
            params.append(exclude_master_id)
        with self._connect() as conn:
            return conn.execute(query, tuple(params)).fetchone() is not None

    def create_turno_master(self, cursor: sqlite3.Cursor, shift_data: Dict[str, Any]) -> int:
        query = "INSERT INTO turni_master (id_dipendente, data_ora_inizio_effettiva, data_ora_fine_effettiva, id_attivita, note) VALUES (?, ?, ?, ?, ?)"
        params = (shift_data['id_dipendente'], shift_data['data_ora_inizio'].isoformat(), shift_data['data_ora_fine'].isoformat(), shift_data.get('id_attivita'), shift_data.get('note'))
        cursor.execute(query, params)
        return cursor.lastrowid

    def update_turno_master(self, cursor: sqlite3.Cursor, id_master: int, start_time: datetime.datetime, end_time: datetime.datetime, id_attivita: Optional[str], note: Optional[str]):
        cursor.execute("DELETE FROM registrazioni_ore WHERE id_turno_master = ?", (id_master,))
        query = "UPDATE turni_master SET data_ora_inizio_effettiva = ?, data_ora_fine_effettiva = ?, id_attivita = ?, note = ? WHERE id_turno_master = ?"
        params = (start_time.isoformat(), end_time.isoformat(), id_attivita, note, id_master)
        cursor.execute(query, params)

    def create_registrazioni_segments(self, cursor: sqlite3.Cursor, segments: List[tuple]):
        query = "INSERT INTO registrazioni_ore (id_turno_master, id_dipendente, id_attivita, data_ora_inizio, data_ora_fine, note) VALUES (?, ?, ?, ?, ?, ?)"
        cursor.executemany(query, segments)

    def delete_turno_master(self, cursor: sqlite3.Cursor, id_turno_master: int):
        cursor.execute("DELETE FROM turni_master WHERE id_turno_master = ?", (id_turno_master,))

    def delete_registrazione(self, cursor: sqlite3.Cursor, id_registrazione: int):
        cursor.execute("DELETE FROM registrazioni_ore WHERE id_registrazione = ?", (id_registrazione,))

    # --- METODI DAO PER LEGGERE I DATI (PER UI E REPORT) ---
    
    def get_turni_master_giorno_df(self, giorno: datetime.date) -> pd.DataFrame:
        giorno_str = giorno.isoformat()
        query = """
        SELECT 
            m.id_turno_master, a.cognome, a.nome,
            m.data_ora_inizio_effettiva, m.data_ora_fine_effettiva,
            m.id_attivita, m.note, a.ruolo, m.id_dipendente,
            a.cognome || ' ' || a.nome AS dipendente_nome
        FROM turni_master m
        JOIN anagrafica_dipendenti a ON m.id_dipendente = a.id_dipendente
        WHERE (date(m.data_ora_inizio_effettiva) = ? OR date(m.data_ora_fine_effettiva) = ?)
        ORDER BY a.cognome, m.data_ora_inizio_effettiva
        """
        with self._connect() as conn:
            df = pd.read_sql_query(
                query, 
                conn, 
                params=(giorno_str, giorno_str), 
                parse_dates=['data_ora_inizio_effettiva', 'data_ora_fine_effettiva']
            )
        if not df.empty:
            df['durata_ore'] = df.apply(lambda row: calculate_duration_hours(
                row['data_ora_inizio_effettiva'], row['data_ora_fine_effettiva']
            ), axis=1)
        return df.set_index('id_turno_master')

    # ★ NUOVO METODO PER IL CALENDARIO ★
    def get_turni_master_range_df(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Estrae tutti i turni master che INIZIANO in un intervallo di date."""
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        query = """
        SELECT 
            m.id_turno_master, a.cognome, a.nome,
            m.data_ora_inizio_effettiva, m.data_ora_fine_effettiva,
            m.id_attivita, m.note, a.ruolo, m.id_dipendente,
            a.cognome || ' ' || a.nome AS dipendente_nome
        FROM turni_master m
        JOIN anagrafica_dipendenti a ON m.id_dipendente = a.id_dipendente
        WHERE date(m.data_ora_inizio_effettiva) BETWEEN ? AND ?
        ORDER BY a.cognome, m.data_ora_inizio_effettiva
        """
        with self._connect() as conn:
            df = pd.read_sql_query(
                query, 
                conn, 
                params=(start_str, end_str), 
                parse_dates=['data_ora_inizio_effettiva', 'data_ora_fine_effettiva']
            )
        if not df.empty:
            df['durata_ore'] = df.apply(lambda row: calculate_duration_hours(
                row['data_ora_inizio_effettiva'], row['data_ora_fine_effettiva']
            ), axis=1)
        return df

    def get_report_data_df(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        query = """
        SELECT
            r.id_registrazione, r.data_ora_inizio, r.data_ora_fine, r.id_attivita,
            r.tipo_ore, a.id_dipendente, a.cognome || ' ' || a.nome AS dipendente_nome,
            a.ruolo, r.id_turno_master
        FROM registrazioni_ore r
        JOIN anagrafica_dipendenti a ON r.id_dipendente = a.id_dipendente
        WHERE date(r.data_ora_inizio) BETWEEN ? AND ?
          AND a.attivo = 1
          AND r.data_ora_inizio IS NOT NULL
          AND r.data_ora_fine IS NOT NULL
        """
        with self._connect() as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(start_str, end_str),
                parse_dates=['data_ora_inizio', 'data_ora_fine']
            )
            return df

def setup_initial_data():
    """Popola i turni standard se il database è vuoto."""
    # Crea un'istanza temporanea solo per questa operazione
    try:
        conn = sqlite3.connect(DB_FILE)
        # Abilita foreign keys anche qui per sicurezza
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM turni_standard")

        if cursor.fetchone()[0] == 0:
            print("Popolamento turni standard iniziali...")
            # Non possiamo usare l'istanza qui, quindi creiamo una temp
            db_manager_temp = CrmDBManager(DB_FILE)
            db_manager_temp.insert_turno_standard("GIORNO_08_18", "Turno di Giorno (8-18)", "08:00:00", "18:00:00", False)
            db_manager_temp.insert_turno_standard("NOTTE_20_06", "Turno di Notte (20-06)", "20:00:00", "06:00:00", True)
        conn.close()
    except Exception as e:
        print(f"Errore durante setup_initial_data: {e}")