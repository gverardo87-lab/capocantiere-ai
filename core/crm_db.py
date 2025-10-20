# file: core/crm_db.py (Versione 14.0 - Enterprise Architecture)
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime
import pandas as pd
from contextlib import contextmanager

# Importa la nostra fonte di verità per i calcoli
from core.logic import calculate_duration_hours

# Percorso DB
DB_FILE = Path(__file__).resolve().parents[1] / "data" / "crm.db"

class CrmDBManager:
    """
    Data Access Layer per il modulo CRM.
    Questa classe gestisce esclusivamente le interazioni dirette con il database.
    Tutta la logica di business è delegata al ShiftService.
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
        Versione 14.0 - Schema Enterprise con Turni Master.
        Inizializza e migra lo schema del database se necessario.
        """
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")

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

            # --- ★ NUOVA ARCHITETTURA TURNI ★ ---
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

            # --- Migrazione Schema (per database esistenti) ---
            cursor.execute("PRAGMA table_info(registrazioni_ore)")
            columns = [col['name'] for col in cursor.fetchall()]
            if 'id_turno_master' not in columns:
                print("Eseguo migrazione schema: aggiungo 'id_turno_master' a 'registrazioni_ore'")
                cursor.execute("ALTER TABLE registrazioni_ore ADD COLUMN id_turno_master INTEGER REFERENCES turni_master(id_turno_master) ON DELETE CASCADE")

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

    # --- ANAGRAFICA, SQUADRE, TURNI STANDARD (Invariati) ---
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

    # ... altri metodi invariati ...

    # --- ★ METODI DI ACCESSO AI DATI (DAO) PER TURNI ★ ---
    # Questi metodi sono a basso livello e usati solo dal ShiftService

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

    # --- METODI PUBBLICI DELEGATI AL SERVICE LAYER ---

    def crea_registrazioni_batch(self, registrazioni: List[Dict[str, Any]]) -> int:
        """DEPRECATO in v14.0. Delega la creazione dei turni al service layer."""
        from core.shift_service import shift_service
        return shift_service.create_shifts_batch(registrazioni)

    def update_segmento_orari(self, id_reg: int, start_time: datetime.datetime, end_time: datetime.datetime, id_att: str, note: str):
        """DEPRECATO in v14.0. Delega l'aggiornamento del turno al service layer."""
        from core.shift_service import shift_service
        shift_service.update_shift_from_segment(
            id_registrazione=id_reg,
            new_segment_start=start_time,
            new_segment_end=end_time,
            new_id_attivita=id_att,
            new_note=note
        )

    def delete_registrazione_e_master(self, id_registrazione: int):
        """DEPRECATO in v14.0. Delega l'eliminazione del turno al service layer."""
        from core.shift_service import shift_service
        shift_service.delete_shift_from_segment(id_registrazione)

    # --- METODI DI VISUALIZZAZIONE (Invariati) ---

    def get_registrazioni_giorno_df(self, giorno: datetime.date) -> pd.DataFrame:
        giorno_str = giorno.isoformat()
        query = """
        SELECT r.id_registrazione, a.cognome, a.nome, r.data_ora_inizio, r.data_ora_fine,
               r.id_attivita, r.note, a.ruolo, r.id_dipendente, r.id_turno_master
        FROM registrazioni_ore r
        JOIN anagrafica_dipendenti a ON r.id_dipendente = a.id_dipendente
        WHERE date(r.data_ora_inizio) = ? AND r.data_ora_inizio IS NOT NULL AND r.data_ora_fine IS NOT NULL
        ORDER BY a.cognome, r.data_ora_inizio
        """
        with self._connect() as conn:
            df = pd.read_sql_query(query, conn, params=(giorno_str,), parse_dates=['data_ora_inizio', 'data_ora_fine'])
        if not df.empty:
            df['durata_ore'] = df.apply(lambda row: calculate_duration_hours(row['data_ora_inizio'], row['data_ora_fine']), axis=1)
        return df.set_index('id_registrazione')

# ... (setup_initial_data e istanza globale) ...
crm_db_manager = CrmDBManager()
