# file: core/crm_db.py (Versione 12.3 - FIX Query SQL ... )

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime
import pandas as pd

# Importa la nostra fonte di verità per i calcoli
from core.logic import calculate_duration_hours

# Percorso DB
DB_FILE = Path(__file__).resolve().parents[1] / "data" / "crm.db"

class CrmDBManager:
    """
    Gestore dedicato a tutte le operazioni del database per il modulo CRM.
    Implementa la logica "Midnight Split" per la contabilità.
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
        # (Codice _init_schema omesso per brevità - è invariato)
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

    # --- ANAGRAFICA (Invariata, omessa per brevità) ---
    def add_dipendente(self, nome: str, cognome: str, ruolo: str) -> int:
        # ... (codice invariato)
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO anagrafica_dipendenti (nome, cognome, ruolo) VALUES (?, ?, ?)",
                (nome, cognome, ruolo)
            )
            conn.commit()
            return cursor.lastrowid
    def get_dipendenti_df(self, solo_attivi: bool = False) -> pd.DataFrame:
        # ... (codice invariato)
        query = "SELECT id_dipendente, nome, cognome, ruolo, attivo FROM anagrafica_dipendenti"
        if solo_attivi: query += " WHERE attivo = 1"
        query += " ORDER BY cognome, nome"
        with self._connect() as conn:
            df = pd.read_sql_query(query, conn, index_col="id_dipendente")
            return df
    def update_dipendente_field(self, id_dipendente: int, field_name: str, new_value):
        # ... (codice invariato)
        allowed_fields = ['nome', 'cognome', 'ruolo', 'attivo']
        if field_name not in allowed_fields:
            raise ValueError(f"Campo '{field_name}' non modificabile")
        with self._connect() as conn:
            query = f"UPDATE anagrafica_dipendenti SET {field_name} = ? WHERE id_dipendente = ?"
            conn.execute(query, (new_value, id_dipendente))
            conn.commit()

    # --- GESTIONE SQUADRE (Invariata, omessa per brevità) ---
    def add_squadra(self, nome_squadra: str, id_caposquadra: Optional[int]) -> int:
        # ... (codice invariato)
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
        # ... (codice invariato)
        with self._connect() as conn:
            conn.execute(
                "UPDATE squadre SET nome_squadra = ?, id_caposquadra = ? WHERE id_squadra = ?",
                (nome_squadra, id_caposquadra, id_squadra)
            )
            conn.commit()
    def update_membri_squadra(self, id_squadra: int, membri_ids: List[int]):
        # ... (codice invariato)
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
        # ... (codice invariato)
         with self._connect() as conn:
            conn.execute("DELETE FROM squadre WHERE id_squadra = ?", (id_squadra,))
            conn.commit()
    def get_squadre(self) -> List[Dict[str, Any]]:
        # ... (codice invariato)
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM squadre ORDER BY nome_squadra").fetchall()
            return [dict(row) for row in rows]
    def get_membri_squadra(self, id_squadra: int) -> List[int]:
        # ... (codice invariato)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id_dipendente FROM membri_squadra WHERE id_squadra = ?",
                (id_squadra,)
            ).fetchall()
            return [row['id_dipendente'] for row in rows]

    # --- TURNI STANDARD (Invariata, omessa per brevità) ---
    def get_turni_standard(self) -> List[Dict[str, Any]]:
         # ... (codice invariato)
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM turni_standard ORDER BY nome_turno").fetchall()
            return [dict(row) for row in rows]
    def insert_turno_standard(self, id_turno: str, nome: str, inizio: str, fine: str, scavalca: bool):
         # ... (codice invariato)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO turni_standard (id_turno, nome_turno, ora_inizio, ora_fine, scavalca_mezzanotte) VALUES (?, ?, ?, ?, ?)",
                (id_turno, nome, inizio, fine, scavalca)
            )
            conn.commit()

    # --- REGISTRAZIONI ORE (Logica Modificata) ---

    def check_for_overlaps(self, list_of_dipendente_ids: List[int], proposed_start: datetime.datetime, proposed_end: datetime.datetime, exclude_id: Optional[int] = None) -> List[str]:
        # (Codice check_for_overlaps omesso per brevità - è invariato dalla v12.2)
        if not list_of_dipendente_ids: return []

        query = f"""
        SELECT
            DISTINCT a.cognome || ' ' || a.nome AS nome_completo
        FROM
            registrazioni_ore r
        JOIN
            anagrafica_dipendenti a ON r.id_dipendente = a.id_dipendente
        WHERE
            r.id_dipendente IN ({','.join(['?'] * len(list_of_dipendente_ids))})
            -- Logica NON inclusiva per permettere turni che si toccano
            AND r.data_ora_inizio < ?
            AND r.data_ora_fine > ?
            AND r.data_ora_inizio IS NOT NULL
            AND r.data_ora_fine IS NOT NULL
        """

        params = list(list_of_dipendente_ids)
        params.append(proposed_end.isoformat())
        params.append(proposed_start.isoformat())

        if exclude_id is not None:
            query += " AND r.id_registrazione != ?"
            params.append(exclude_id)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [row['nome_completo'] for row in rows]

    def _split_and_prepare_records(self, record: Dict[str, Any]) -> List[tuple]:
        # (Codice _split_and_prepare_records omesso per brevità - è invariato dalla v12.1)
        start = record['data_ora_inizio']
        end = record['data_ora_fine']

        if start.date() == end.date():
            return [(
                record['id_dipendente'], record.get('id_attivita'),
                start, end, record.get('note')
            )]
        else:
            mezzanotte = start.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            if mezzanotte == end:
                return [(
                    record['id_dipendente'], record.get('id_attivita'),
                    start, end, record.get('note')
                )]
            record1 = (
                record['id_dipendente'], record.get('id_attivita'),
                start, mezzanotte, f"{record.get('note', '') or ''} (Parte 1)"
            )
            record2 = (
                record['id_dipendente'], record.get('id_attivita'),
                mezzanotte, end, f"{record.get('note', '') or ''} (Parte 2)"
            )
            return [record1, record2]

    def crea_registrazioni_batch(self, registrazioni: List[Dict[str, Any]]) -> int:
        # (Codice crea_registrazioni_batch omesso per brevità - è invariato dalla v12.1)
        if not registrazioni:
            return 0
        tuple_list_finali = []
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                for r in registrazioni:
                    conflitti = self.check_for_overlaps(
                        [r['id_dipendente']], r['data_ora_inizio'], r['data_ora_fine']
                    )
                    if conflitti:
                        raise Exception(f"Sovrapposizione per {conflitti[0]}")
                    record_splittati = self._split_and_prepare_records(r)
                    tuple_list_finali.extend(record_splittati)
                query = "INSERT INTO registrazioni_ore (id_dipendente, id_attivita, data_ora_inizio, data_ora_fine, note) VALUES (?, ?, ?, ?, ?)"
                cursor.executemany(query, tuple_list_finali)
                conn.commit()
                return len(tuple_list_finali)
            except Exception as e:
                conn.rollback()
                raise e

    def get_report_data_df(self, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """
        Query semplificata (ora corretta e completa)
        """
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        # --- QUERY COMPLETA ---
        query = """
        SELECT
            r.id_registrazione,
            r.data_ora_inizio,
            r.data_ora_fine,
            r.id_attivita,
            r.tipo_ore,
            a.id_dipendente,
            a.cognome || ' ' || a.nome AS dipendente_nome,
            a.ruolo
        FROM registrazioni_ore r
        JOIN anagrafica_dipendenti a ON r.id_dipendente = a.id_dipendente
        WHERE date(r.data_ora_inizio) BETWEEN ? AND ?
          AND a.attivo = 1
          AND r.data_ora_inizio IS NOT NULL
          AND r.data_ora_fine IS NOT NULL
        """
        # --- FINE QUERY COMPLETA ---

        with self._connect() as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(start_str, end_str),
                parse_dates=['data_ora_inizio', 'data_ora_fine']
            )
            # Il calcolo durata avviene nella pagina Reportistica
            return df

    def get_registrazioni_giorno_df(self, giorno: datetime.date) -> pd.DataFrame:
        """
        Query semplificata (ora corretta e completa)
        """
        giorno_str = giorno.isoformat()

        # --- QUERY COMPLETA ---
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
        WHERE date(r.data_ora_inizio) = ?
          AND r.data_ora_inizio IS NOT NULL
          AND r.data_ora_fine IS NOT NULL
        ORDER BY a.cognome, r.data_ora_inizio
        """
        # --- FINE QUERY COMPLETA ---

        with self._connect() as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(giorno_str,),
                parse_dates=['data_ora_inizio', 'data_ora_fine']
            )

        if not df.empty:
            # Calcolo durata usando la fonte di verità
            df['durata_ore'] = df.apply(
                lambda row: calculate_duration_hours(row['data_ora_inizio'], row['data_ora_fine']),
                axis=1
            )

        return df.set_index('id_registrazione')

    def update_full_registrazione(self, id_reg: int, start_time: datetime.datetime,
                                   end_time: datetime.datetime, id_att: str, note: str):
        # (Codice update_full_registrazione omesso per brevità - è invariato dalla v12.1)
        if not id_reg or not start_time or not end_time:
            raise ValueError("ID, data inizio e data fine sono obbligatori")
        if start_time >= end_time:
            raise ValueError("L'orario di inizio deve essere precedente alla fine")
        db_att = id_att if (id_att and id_att != "-1") else None
        db_note = note if note else None
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id_dipendente FROM registrazioni_ore WHERE id_registrazione = ?",
                (id_reg,)
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Registrazione {id_reg} non trovata")
            id_dipendente = row['id_dipendente']
            conflitti = self.check_for_overlaps(
                [id_dipendente], start_time, end_time, exclude_id=id_reg
            )
            if conflitti:
                raise ValueError(f"Sovrapposizione rilevata con un'altra registrazione per {conflitti[0]}")
            try:
                cursor.execute("BEGIN TRANSACTION")
                record_dict = {
                    "id_dipendente": id_dipendente, "id_attivita": db_att,
                    "data_ora_inizio": start_time, "data_ora_fine": end_time,
                    "note": db_note
                }
                record_splittati = self._split_and_prepare_records(record_dict)
                primo_record = record_splittati[0]
                cursor.execute("""
                    UPDATE registrazioni_ore
                    SET id_dipendente = ?, id_attivita = ?, data_ora_inizio = ?, data_ora_fine = ?, note = ?
                    WHERE id_registrazione = ?
                """, (*primo_record, id_reg))
                if len(record_splittati) > 1:
                    secondo_record = record_splittati[1]
                    cursor.execute("""
                        INSERT INTO registrazioni_ore
                        (id_dipendente, id_attivita, data_ora_inizio, data_ora_fine, note)
                        VALUES (?, ?, ?, ?, ?)
                    """, secondo_record)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

    def delete_registrazione(self, id_registrazione: int):
        # (Codice delete_registrazione omesso per brevità - è invariato)
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM registrazioni_ore WHERE id_registrazione = ?",
                (id_registrazione,)
            )
            conn.commit()

    def split_registrazione_interruzione(self, id_registrazione: int, start_interruzione: datetime.datetime, end_interruzione: datetime.datetime):
        # (Codice split_registrazione_interruzione omesso per brevità - è invariato dalla v12.1)
         with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT * FROM registrazioni_ore WHERE id_registrazione = ?",
                    (id_registrazione,)
                )
                record = cursor.fetchone()
                if not record: raise Exception("Record non trovato")
                original_start_time = datetime.datetime.fromisoformat(record['data_ora_inizio'])
                original_end_time = datetime.datetime.fromisoformat(record['data_ora_fine'])
                if start_interruzione >= end_interruzione or \
                   start_interruzione < original_start_time or \
                   end_interruzione > original_end_time:
                    raise Exception("Interruzione non valida (fuori dai limiti del turno)")
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute(
                    "UPDATE registrazioni_ore SET data_ora_fine = ? WHERE id_registrazione = ?",
                    (start_interruzione.isoformat(), id_registrazione)
                )
                if end_interruzione < original_end_time:
                    cursor.execute("""
                        INSERT INTO registrazioni_ore
                        (id_dipendente, id_attivita, data_ora_inizio, data_ora_fine, tipo_ore, note)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        record['id_dipendente'], record['id_attivita'],
                        end_interruzione.isoformat(), original_end_time.isoformat(),
                        record['tipo_ore'], f"{record['note'] or ''} (post-interruzione)".strip()
                    ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

# --- Setup Dati Iniziali (Invariato) ---
def setup_initial_data():
    """Popola i turni standard se il database è vuoto."""
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