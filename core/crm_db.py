# file: core/crm_db.py (Versione 12.6 - Pulizia finale, rimossa update_full_registrazione)

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
        """Inizializza lo schema del database CRM."""
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

    # --- ANAGRAFICA ---
    def add_dipendente(self, nome: str, cognome: str, ruolo: str) -> int:
        """Aggiunge un nuovo dipendente."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO anagrafica_dipendenti (nome, cognome, ruolo) VALUES (?, ?, ?)",
                (nome, cognome, ruolo)
            )
            conn.commit()
            return cursor.lastrowid

    def get_dipendenti_df(self, solo_attivi: bool = False) -> pd.DataFrame:
        """Recupera i dipendenti come DataFrame."""
        query = "SELECT id_dipendente, nome, cognome, ruolo, attivo FROM anagrafica_dipendenti"
        if solo_attivi: query += " WHERE attivo = 1"
        query += " ORDER BY cognome, nome"
        with self._connect() as conn:
            df = pd.read_sql_query(query, conn, index_col="id_dipendente")
            return df

    def update_dipendente_field(self, id_dipendente: int, field_name: str, new_value):
        """Aggiorna un singolo campo di un dipendente."""
        allowed_fields = ['nome', 'cognome', 'ruolo', 'attivo']
        if field_name not in allowed_fields:
            raise ValueError(f"Campo '{field_name}' non modificabile")
        with self._connect() as conn:
            query = f"UPDATE anagrafica_dipendenti SET {field_name} = ? WHERE id_dipendente = ?"
            conn.execute(query, (new_value, id_dipendente))
            conn.commit()

    # --- GESTIONE SQUADRE ---
    def add_squadra(self, nome_squadra: str, id_caposquadra: Optional[int]) -> int:
        """Aggiunge una nuova squadra, includendo il caposquadra come membro."""
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
                    # Aggiunge automaticamente il caposquadra ai membri
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
        """Aggiorna nome e caposquadra di una squadra."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE squadre SET nome_squadra = ?, id_caposquadra = ? WHERE id_squadra = ?",
                (nome_squadra, id_caposquadra, id_squadra)
            )
            conn.commit()

    def update_membri_squadra(self, id_squadra: int, membri_ids: List[int]):
        """Sostituisce l'elenco dei membri di una squadra."""
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                # Pulisce i membri vecchi
                cursor.execute("DELETE FROM membri_squadra WHERE id_squadra = ?", (id_squadra,))
                # Inserisce i nuovi
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
        """Elimina una squadra (e i membri grazie a ON DELETE CASCADE)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM squadre WHERE id_squadra = ?", (id_squadra,))
            conn.commit()

    def get_squadre(self) -> List[Dict[str, Any]]:
        """Ottiene un elenco di tutte le squadre."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM squadre ORDER BY nome_squadra").fetchall()
            return [dict(row) for row in rows]

    def get_membri_squadra(self, id_squadra: int) -> List[int]:
        """Ottiene gli ID dei membri di una singola squadra."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id_dipendente FROM membri_squadra WHERE id_squadra = ?",
                (id_squadra,)
            ).fetchall()
            return [row['id_dipendente'] for row in rows]

    # --- TURNI STANDARD ---
    def get_turni_standard(self) -> List[Dict[str, Any]]:
         """Ottiene l'elenco dei turni standard."""
         with self._connect() as conn:
            rows = conn.execute("SELECT * FROM turni_standard ORDER BY nome_turno").fetchall()
            return [dict(row) for row in rows]

    def insert_turno_standard(self, id_turno: str, nome: str, inizio: str, fine: str, scavalca: bool):
         """Inserisce o aggiorna un turno standard."""
         with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO turni_standard (id_turno, nome_turno, ora_inizio, ora_fine, scavalca_mezzanotte) VALUES (?, ?, ?, ?, ?)",
                (id_turno, nome, inizio, fine, scavalca)
            )
            conn.commit()

    # --- REGISTRAZIONI ORE ---

    def check_for_overlaps(self, list_of_dipendente_ids: List[int], proposed_start: datetime.datetime, proposed_end: datetime.datetime, exclude_ids: Optional[List[int]] = None) -> List[str]:
        """
        Versione 12.7 - Esclusione multipla per gestire turni splittati.
        La logica SQL usa '<' e '>' (non '<=' e '>=') per permettere ai turni
        di "toccarsi" (es. uno finisce alle 00:00, l'altro inizia alle 00:00).
        """
        if not list_of_dipendente_ids: return []

        query = f"""
        SELECT
            a.cognome || ' ' || a.nome AS nome_completo,
            r.id_registrazione,
            r.data_ora_inizio,
            r.data_ora_fine
        FROM
            registrazioni_ore r
        JOIN
            anagrafica_dipendenti a ON r.id_dipendente = a.id_dipendente
        WHERE
            r.id_dipendente IN ({','.join(['?'] * len(list_of_dipendente_ids))})
            -- Logica di sovrapposizione (non inclusiva)
            AND r.data_ora_inizio < ?
            AND r.data_ora_fine > ?
            AND r.data_ora_inizio IS NOT NULL
            AND r.data_ora_fine IS NOT NULL
        """

        params = list(list_of_dipendente_ids)
        params.append(proposed_end.isoformat())
        params.append(proposed_start.isoformat())

        if exclude_ids:
            # Pulisce la lista per evitare SQL injection, anche se interna.
            clean_exclude_ids = [int(id) for id in exclude_ids if id is not None]
            if clean_exclude_ids:
                query += f" AND r.id_registrazione NOT IN ({','.join(['?'] * len(clean_exclude_ids))})"
                params.extend(clean_exclude_ids)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            
            error_strings = []
            for row in rows:
                try:
                    start_str = datetime.fromisoformat(row['data_ora_inizio']).strftime('%d/%m %H:%M')
                    end_str = datetime.fromisoformat(row['data_ora_fine']).strftime('%d/%m %H:%M')
                    error_strings.append(
                        f"{row['nome_completo']} è già impegnato nel turno ID: {row['id_registrazione']} ({start_str} - {end_str})"
                    )
                except:
                     error_strings.append(f"{row['nome_completo']} (ID: {row['id_registrazione']})")
            return error_strings

    def _split_and_prepare_records(self, record: Dict[str, Any]) -> List[tuple]:
        """
        Logica di split a mezzanotte.
        """
        start = record['data_ora_inizio']
        end = record['data_ora_fine']

        if start.date() == end.date():
            # Il turno non scavalca la mezzanotte
            return [(
                record['id_dipendente'], record.get('id_attivita'),
                start, end, record.get('note')
            )]
        else:
            # Il turno scavalca la mezzanotte
            mezzanotte = start.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            
            # Caso speciale: il turno finisce *esattamente* a mezzanotte
            if mezzanotte == end:
                return [(
                    record['id_dipendente'], record.get('id_attivita'),
                    start, end, record.get('note')
                )]

            # Creazione dei due segmenti
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
        """
        Crea una o più registrazioni, applicando la logica dello split.
        Usato dalla pagina di Pianificazione.
        """
        if not registrazioni:
            return 0
        tuple_list_finali = []
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION")
                for r in registrazioni:
                    # Controlla conflitti sull'intero intervallo (es. 20:00-06:00)
                    conflitti = self.check_for_overlaps(
                        [r['id_dipendente']], r['data_ora_inizio'], r['data_ora_fine']
                    )
                    if conflitti:
                        raise Exception(f"Sovrapposizione per {conflitti[0]}")
                    
                    # Splitta il record se necessario (es. in 20:00-00:00 e 00:00-06:00)
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
        """Estrae i dati grezzi per il report consuntivo."""
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
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
        with self._connect() as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(start_str, end_str),
                parse_dates=['data_ora_inizio', 'data_ora_fine']
            )
            return df

    def _get_registrazione(self, id_registrazione: int) -> Optional[sqlite3.Row]:
        """Recupera una singola registrazione dal DB."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM registrazioni_ore WHERE id_registrazione = ?",
                (id_registrazione,)
            )
            return cursor.fetchone()

    def get_registrazioni_giorno_df(self, giorno: datetime.date) -> pd.DataFrame:
        """
        Recupera i segmenti per un singolo giorno di competenza.
        """
        giorno_str = giorno.isoformat()
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
        with self._connect() as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(giorno_str,),
                parse_dates=['data_ora_inizio', 'data_ora_fine']
            )
        if not df.empty:
            df['durata_ore'] = df.apply(
                lambda row: calculate_duration_hours(row['data_ora_inizio'], row['data_ora_fine']),
                axis=1
            )
        # Imposta l'ID della registrazione come indice del DataFrame
        return df.set_index('id_registrazione')

    # --- ★ ★ ★ FUNZIONE CORRETTA PER LA CONTROL ROOM ★ ★ ★ ---
    def update_segmento_orari(self, id_reg: int, start_time: datetime.datetime,
                              end_time: datetime.datetime, id_att: str, note: str):
        """
        Versione 12.7 - Aggiorna un singolo segmento con logica avanzata per turni splittati.
        """
        if not id_reg or not start_time or not end_time:
            raise ValueError("ID, data inizio e data fine sono obbligatori")
        if start_time >= end_time:
            raise ValueError("L'orario di inizio deve essere precedente alla fine")

        db_att = id_att if (id_att and id_att != "-1") else None
        db_note = note if note else None

        with self._connect() as conn:
            cursor = conn.cursor()
            
            # 1. Recupera i dati del segmento attuale
            current_reg = self._get_registrazione(id_reg)
            if not current_reg:
                raise ValueError(f"Registrazione {id_reg} non trovata")
            
            id_dipendente = current_reg['id_dipendente']
            current_start = datetime.datetime.fromisoformat(current_reg['data_ora_inizio'])
            current_end = datetime.datetime.fromisoformat(current_reg['data_ora_fine'])

            # 2. Logica per identificare il "gemello" di un turno splittato
            sibling_reg_id = None

            # Caso 1: il segmento finisce a mezzanotte, cerca il gemello che inizia alla stessa ora
            if current_end.hour == 0 and current_end.minute == 0 and current_end.second == 0:
                query_sibling = "SELECT id_registrazione FROM registrazioni_ore WHERE id_dipendente = ? AND data_ora_inizio = ? AND id_registrazione != ?"
                params_sibling = (id_dipendente, current_end.isoformat(), id_reg)
                sibling_row = cursor.execute(query_sibling, params_sibling).fetchone()
                if sibling_row: sibling_reg_id = sibling_row['id_registrazione']

            # Caso 2: il segmento inizia a mezzanotte, cerca il gemello che finisce alla stessa ora
            elif current_start.hour == 0 and current_start.minute == 0 and current_start.second == 0:
                query_sibling = "SELECT id_registrazione FROM registrazioni_ore WHERE id_dipendente = ? AND data_ora_fine = ? AND id_registrazione != ?"
                params_sibling = (id_dipendente, current_start.isoformat(), id_reg)
                sibling_row = cursor.execute(query_sibling, params_sibling).fetchone()
                if sibling_row: sibling_reg_id = sibling_row['id_registrazione']

            # 3. Controlla le sovrapposizioni in modo intelligente
            ids_da_escludere = [id_reg]
            if sibling_reg_id:
                ids_da_escludere.append(sibling_reg_id)

            conflitti = self.check_for_overlaps(
                [id_dipendente], start_time, end_time, exclude_ids=ids_da_escludere
            )
            if conflitti:
                raise ValueError(f"Sovrapposizione rilevata: {conflitti[0]}")

            # 4. Se c'è un gemello, assicurati che la modifica non lo sovrapponga
            if sibling_reg_id:
                sibling_reg = self._get_registrazione(sibling_reg_id)
                sibling_start = datetime.datetime.fromisoformat(sibling_reg['data_ora_inizio'])
                sibling_end = datetime.datetime.fromisoformat(sibling_reg['data_ora_fine'])

                # Il nuovo orario non deve "invadere" lo spazio del gemello
                if start_time < sibling_end and end_time > sibling_start:
                     raise ValueError("La modifica entra in conflitto con l'altra parte del turno diviso a mezzanotte.")

            # 5. Esegui l'aggiornamento
            try:
                cursor.execute("""
                    UPDATE registrazioni_ore
                    SET data_ora_inizio = ?, data_ora_fine = ?, id_attivita = ?, note = ?
                    WHERE id_registrazione = ?
                """, (start_time.isoformat(), end_time.isoformat(), db_att, db_note, id_reg))
                
                conn.commit()
                
            except Exception as e:
                conn.rollback()
                raise e
    # --- ★ ★ ★ FINE FUNZIONE CORRETTA ★ ★ ★ ---

    def delete_registrazione(self, id_registrazione: int):
        """Elimina una singola registrazione."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM registrazioni_ore WHERE id_registrazione = ?",
                (id_registrazione,)
            )
            conn.commit()

    def split_registrazione_interruzione(self, id_registrazione: int, start_interruzione: datetime.datetime, end_interruzione: datetime.datetime):
        """Divide un turno esistente per inserire un'interruzione."""
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
                    raise Exception("Interruzione non valida (fuori dai limiti del turno o orari invertiti)")
                
                cursor.execute("BEGIN TRANSACTION")
                
                # Accorcia il turno originale
                cursor.execute(
                    "UPDATE registrazioni_ore SET data_ora_fine = ? WHERE id_registrazione = ?",
                    (start_interruzione.isoformat(), id_registrazione)
                )
                
                # Crea il nuovo segmento post-interruzione, se necessario
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

# --- Setup Dati Iniziali ---
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