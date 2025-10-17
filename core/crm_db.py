# file: core/crm_db.py (Versione 10.0 - FIX METODI MANCANTI)

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime
import pandas as pd

# Percorso DB
DB_FILE = Path(__file__).resolve().parents[1] / "data" / "crm.db"

class CrmDBManager:
    """
    Gestore dedicato a tutte le operazioni del database per il modulo CRM.
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
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            
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
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS registrazioni_ore (
                id_registrazione INTEGER PRIMARY KEY AUTOINCREMENT,
                id_dipendente INTEGER NOT NULL,
                id_attivita TEXT,
                data_ora_inizio DATETIME NOT NULL,
                data_ora_fine DATETIME NOT NULL,
                tipo_ore TEXT DEFAULT 'Cantiere',
                note TEXT,
                FOREIGN KEY (id_dipendente) REFERENCES anagrafica_dipendenti (id_dipendente)
            )""")
            conn.commit()
    
    # --- ANAGRAFICA DIPENDENTI ---
    def add_dipendente(self, nome: str, cognome: str, ruolo: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO anagrafica_dipendenti (nome, cognome, ruolo) VALUES (?, ?, ?)", 
                (nome, cognome, ruolo)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_dipendenti_df(self, solo_attivi: bool = False) -> pd.DataFrame:
        query = "SELECT id_dipendente, nome, cognome, ruolo, attivo FROM anagrafica_dipendenti"
        if solo_attivi:
            query += " WHERE attivo = 1"
        query += " ORDER BY cognome, nome"
        
        with self._connect() as conn:
            df = pd.read_sql_query(query, conn, index_col="id_dipendente")
            return df
    
    def update_dipendente_field(self, id_dipendente: int, field_name: str, new_value):
        """
        ✅ NUOVO METODO - Aggiorna un singolo campo di un dipendente.
        Usato dal data_editor dell'anagrafica.
        """
        allowed_fields = ['nome', 'cognome', 'ruolo', 'attivo']
        if field_name not in allowed_fields:
            raise ValueError(f"Campo '{field_name}' non modificabile")
        
        with self._connect() as conn:
            query = f"UPDATE anagrafica_dipendenti SET {field_name} = ? WHERE id_dipendente = ?"
            conn.execute(query, (new_value, id_dipendente))
            conn.commit()
    
    # --- GESTIONE SQUADRE ---
    def add_squadra(self, nome_squadra: str, id_caposquadra: Optional[int]) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute(
                    "INSERT INTO squadre (nome_squadra, id_caposquadra) VALUES (?, ?)", 
                    (nome_squadra, id_caposquadra)
                )
                new_squadra_id = cursor.lastrowid
                
                if id_caposquadra is not None:
                    cursor.execute(
                        "INSERT INTO membri_squadra (id_squadra, id_dipendente) VALUES (?, ?)", 
                        (new_squadra_id, id_caposquadra)
                    )
                
                conn.commit()
                return new_squadra_id
            except Exception as e:
                conn.rollback()
                raise e
    
    def update_squadra_details(self, id_squadra: int, nome_squadra: str, id_caposquadra: Optional[int]):
        with self._connect() as conn:
            conn.execute(
                "UPDATE squadre SET nome_squadra = ?, id_caposquadra = ? WHERE id_squadra = ?", 
                (nome_squadra, id_caposquadra, id_squadra)
            )
            conn.commit()
    
    def update_membri_squadra(self, id_squadra: int, membri_ids: List[int]):
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute("DELETE FROM membri_squadra WHERE id_squadra = ?", (id_squadra,))
                
                if membri_ids:
                    data_to_insert = [(id_squadra, id_dip) for id_dip in list(set(membri_ids))]
                    cursor.executemany(
                        "INSERT INTO membri_squadra (id_squadra, id_dipendente) VALUES (?, ?)", 
                        data_to_insert
                    )
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
    
    def delete_squadra(self, id_squadra: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM squadre WHERE id_squadra = ?", (id_squadra,))
            conn.commit()
    
    def get_squadre(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM squadre ORDER BY nome_squadra").fetchall()
            return [dict(row) for row in rows]
    
    def get_membri_squadra(self, id_squadra: int) -> List[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id_dipendente FROM membri_squadra WHERE id_squadra = ?", 
                (id_squadra,)
            ).fetchall()
            return [row['id_dipendente'] for row in rows]
    
    # --- TURNI STANDARD ---
    def get_turni_standard(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM turni_standard ORDER BY nome_turno").fetchall()
            return [dict(row) for row in rows]
    
    def insert_turno_standard(self, id_turno: str, nome: str, inizio: str, fine: str, scavalca: bool):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO turni_standard (id_turno, nome_turno, ora_inizio, ora_fine, scavalca_mezzanotte) VALUES (?, ?, ?, ?, ?)", 
                (id_turno, nome, inizio, fine, scavalca)
            )
            conn.commit()
    
    # --- REGISTRAZIONI ORE ---
    def check_for_overlaps(self, list_of_dipendente_ids: List[int], proposed_start: datetime.datetime, proposed_end: datetime.datetime) -> List[str]:
        """
        Controlla le sovrapposizioni.
        Ignora i record con date nulle (corrotti).
        """
        if not list_of_dipendente_ids:
            return []
            
        query = f"""
        SELECT 
            DISTINCT a.cognome || ' ' || a.nome AS nome_completo
        FROM 
            registrazioni_ore r
        JOIN 
            anagrafica_dipendenti a ON r.id_dipendente = a.id_dipendente
        WHERE 
            r.id_dipendente IN ({','.join(['?'] * len(list_of_dipendente_ids))})
            AND r.data_ora_inizio < ? 
            AND r.data_ora_fine > ?
            AND r.data_ora_inizio IS NOT NULL 
            AND r.data_ora_fine IS NOT NULL 
        """
        
        params = list(list_of_dipendente_ids)
        params.append(proposed_end.isoformat())
        params.append(proposed_start.isoformat())
        
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [row['nome_completo'] for row in rows]

    def crea_registrazioni_batch(self, registrazioni: List[Dict[str, Any]]) -> int:
        if not registrazioni:
            return 0
        
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                query = "INSERT INTO registrazioni_ore (id_dipendente, id_attivita, data_ora_inizio, data_ora_fine, note) VALUES (?, ?, ?, ?, ?)"
                tuple_list = [
                    (r['id_dipendente'], r['id_attivita'], r['data_ora_inizio'], r['data_ora_fine'], r.get('note', None)) 
                    for r in registrazioni
                ]
                cursor.executemany(query, tuple_list)
                conn.commit()
                return len(tuple_list)
            except Exception as e:
                conn.rollback()
                raise e
    
    def get_report_data_df(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        dt_start = datetime.datetime.combine(start_date, datetime.time.min)
        dt_end = datetime.datetime.combine(end_date, datetime.time.max)
        
        query = """
        SELECT 
            r.id_registrazione,
            r.data_ora_inizio,
            r.data_ora_fine,
            (julianday(r.data_ora_fine) - julianday(r.data_ora_inizio)) * 24.0 AS durata_ore,
            r.id_attivita,
            r.tipo_ore,
            a.id_dipendente,
            a.cognome || ' ' || a.nome AS dipendente_nome,
            a.ruolo
        FROM registrazioni_ore r
        JOIN anagrafica_dipendenti a ON r.id_dipendente = a.id_dipendente
        WHERE r.data_ora_inizio <= ? 
          AND r.data_ora_fine >= ?
          AND a.attivo = 1
          AND r.data_ora_inizio IS NOT NULL 
          AND r.data_ora_fine IS NOT NULL
        """
        
        with self._connect() as conn:
            df = pd.read_sql_query(
                query, 
                conn, 
                params=(dt_end, dt_start), 
                parse_dates=['data_ora_inizio', 'data_ora_fine']
            )
            return df
    
    def get_registrazioni_giorno_df(self, giorno: datetime.date) -> pd.DataFrame:
        start_day = datetime.datetime.combine(giorno, datetime.time.min)
        end_day = datetime.datetime.combine(giorno, datetime.time.max)
        
        query = """
        SELECT 
            r.id_registrazione,
            a.cognome,
            a.nome,
            r.data_ora_inizio,
            r.data_ora_fine,
            r.id_attivita,
            r.note,
            a.ruolo,
            r.id_dipendente
        FROM registrazioni_ore r
        JOIN anagrafica_dipendenti a ON r.id_dipendente = a.id_dipendente
        WHERE r.data_ora_inizio <= ? 
          AND r.data_ora_fine >= ?
          AND r.data_ora_inizio IS NOT NULL 
          AND r.data_ora_fine IS NOT NULL
        ORDER BY a.cognome, r.data_ora_inizio
        """
        
        with self._connect() as conn:
            df = pd.read_sql_query(
                query, 
                conn, 
                params=(end_day, start_day), 
                parse_dates=['data_ora_inizio', 'data_ora_fine']
            )
        
        if not df.empty:
            df['durata_ore'] = ((df['data_ora_fine'] - df['data_ora_inizio']).dt.total_seconds() / 3600).round(2)
        
        return df.set_index('id_registrazione')

    def update_full_registrazione(self, id_reg: int, start_time: datetime.datetime, 
                                   end_time: datetime.datetime, id_att: str, note: str):
        """
        ✅ NUOVO METODO - Aggiorna completamente una registrazione esistente.
        INCLUDE validazione sovrapposizioni ESCLUDENDO se stessa.
        """
        if not id_reg or not start_time or not end_time:
            raise ValueError("ID, data inizio e data fine sono obbligatori")
        
        if start_time >= end_time:
            raise ValueError("L'orario di inizio deve essere precedente alla fine")
        
        # Converti per il DB
        if hasattr(start_time, 'isoformat'):
            db_start = start_time.isoformat()
        else:
            db_start = str(start_time)
        
        if hasattr(end_time, 'isoformat'):
            db_end = end_time.isoformat()
        else:
            db_end = str(end_time)
        
        db_att = id_att if (id_att and id_att != "-1") else None
        db_note = note if note else None
        
        with self._connect() as conn:
            cursor = conn.cursor()
            
            # 1. Recupera id_dipendente per check sovrapposizioni
            cursor.execute(
                "SELECT id_dipendente FROM registrazioni_ore WHERE id_registrazione = ?", 
                (id_reg,)
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Registrazione {id_reg} non trovata")
            
            id_dipendente = row['id_dipendente']
            
            # 2. CHECK SOVRAPPOSIZIONI (ESCLUDENDO SE STESSA!)
            overlap_query = """
            SELECT COUNT(*) as conflicts
            FROM registrazioni_ore
            WHERE id_dipendente = ?
              AND id_registrazione != ?
              AND data_ora_inizio < ?
              AND data_ora_fine > ?
              AND data_ora_inizio IS NOT NULL
              AND data_ora_fine IS NOT NULL
            """
            cursor.execute(overlap_query, (id_dipendente, id_reg, db_end, db_start))
            conflicts = cursor.fetchone()['conflicts']
            
            if conflicts > 0:
                raise ValueError(
                    f"Sovrapposizione rilevata con altre {conflicts} registrazioni dello stesso dipendente"
                )
            
            # 3. UPDATE
            cursor.execute("""
                UPDATE registrazioni_ore 
                SET data_ora_inizio = ?, 
                    data_ora_fine = ?, 
                    id_attivita = ?, 
                    note = ?
                WHERE id_registrazione = ?
            """, (db_start, db_end, db_att, db_note, id_reg))
            
            conn.commit()

    def delete_registrazione(self, id_registrazione: int):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM registrazioni_ore WHERE id_registrazione = ?", 
                (id_registrazione,)
            )
            conn.commit()
            
    def split_registrazione_interruzione(self, id_registrazione: int, start_interruzione: datetime.datetime, end_interruzione: datetime.datetime):
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT * FROM registrazioni_ore WHERE id_registrazione = ?", 
                    (id_registrazione,)
                )
                record = cursor.fetchone()
                if not record:
                    raise Exception("Record non trovato")
                
                original_end_time = datetime.datetime.fromisoformat(record['data_ora_fine'])
                
                if start_interruzione >= end_interruzione or start_interruzione >= original_end_time:
                    raise Exception("Interruzione non valida")
                
                cursor.execute("BEGIN TRANSACTION")
                
                # Accorcia la prima parte
                cursor.execute(
                    "UPDATE registrazioni_ore SET data_ora_fine = ? WHERE id_registrazione = ?", 
                    (start_interruzione.isoformat(), id_registrazione)
                )
                
                # Crea la seconda parte (se esiste)
                if end_interruzione < original_end_time:
                    cursor.execute("""
                        INSERT INTO registrazioni_ore 
                        (id_dipendente, id_attivita, data_ora_inizio, data_ora_fine, tipo_ore, note) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        record['id_dipendente'], 
                        record['id_attivita'], 
                        end_interruzione.isoformat(), 
                        original_end_time.isoformat(), 
                        record['tipo_ore'], 
                        f"{record['note'] or ''} (post-interruzione)".strip()
                    ))
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

# --- Setup Dati Iniziali ---
def setup_initial_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM turni_standard")
    
    if cursor.fetchone()[0] == 0:
        print("Popolamento turni standard iniziali...")
        db_manager = CrmDBManager()
        db_manager.insert_turno_standard("GIORNO_08_18", "Turno di Giorno (8-18)", "08:00:00", "18:00:00", False)
        db_manager.insert_turno_standard("NOTTE_20_06", "Turno di Notte (20-06)", "20:00:00", "06:00:00", True)
    
    conn.close()

# Istanza globale
crm_db_manager = CrmDBManager()
setup_initial_data()