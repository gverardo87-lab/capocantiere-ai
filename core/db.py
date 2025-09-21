from __future__ import annotations

import os
import sqlite3
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import DB_PATH

# This function creates a single, cached connection for the entire app session.
# check_same_thread=False is necessary for Streamlit's execution model.
@st.cache_resource
def get_db_connection(db_path: str) -> sqlite3.Connection:
    """Initializes and caches a single database connection."""
    print(f"INFO: Initializing new database connection to '{db_path}'...")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

class Database:
    def __init__(self, db_path: str):
        self.path = db_path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        # Get the cached connection
        self.conn = get_db_connection(db_path)
        # Initialize schema if needed
        self._init_schema()

    def _execute(self, sql: str, params: Iterable = ()):
        """Helper for executing a write query."""
        with self.conn: # Use the connection as a context manager for transactions
            self.conn.execute(sql, tuple(params))

    def _query(self, sql: str, params: Iterable = ()) -> List[sqlite3.Row]:
        """Helper for executing a read query."""
        cur = self.conn.cursor()
        cur.execute(sql, tuple(params))
        return cur.fetchall()

    def _init_schema(self):
        # We need a separate cursor for executescript, as it doesn't work with the main conn directly
        # in the same way. We use a transaction to ensure it's atomic.
        with self.conn:
            self.conn.executescript("""
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, filename TEXT NOT NULL,
                    content_type TEXT, size_bytes INTEGER, sha256 TEXT UNIQUE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS extractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    field_name TEXT NOT NULL, field_value TEXT, confidence TEXT, method TEXT,
                    UNIQUE(document_id, field_name)
                );
                CREATE TABLE IF NOT EXISTS personale (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, nome_completo TEXT UNIQUE NOT NULL,
                    qualifica TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS commesse (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE NOT NULL, cliente TEXT,
                    stato TEXT DEFAULT 'Attiva', created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS timesheet_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    data TEXT, ore REAL, descrizione TEXT, reparto TEXT,
                    personale_id INTEGER NOT NULL REFERENCES personale(id),
                    commessa_id INTEGER NOT NULL REFERENCES commesse(id)
                );
            """)

    def upsert_document(self, kind: str, filename: str, content_type: str, size_bytes: int, sha256: str) -> int:
        with self.conn:
            row = self.conn.execute("SELECT id FROM documents WHERE sha256 = ?", (sha256,)).fetchone()
            if row:
                doc_id = row['id']
                self.conn.execute("UPDATE documents SET kind = ?, filename = ? WHERE id = ?", (kind, filename, doc_id))
                return doc_id
            else:
                cursor = self.conn.execute(
                    "INSERT INTO documents (kind, filename, content_type, size_bytes, sha256) VALUES (?, ?, ?, ?, ?)",
                    (kind, filename, content_type, size_bytes, sha256))
                return cursor.lastrowid

    def bulk_upsert_extractions(self, document_id: int, items: Iterable[Tuple[str, Optional[str], str, str]]):
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO extractions (document_id, field_name, field_value, confidence, method)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(document_id, field_name) DO UPDATE SET
                field_value = excluded.field_value, confidence = excluded.confidence, method = excluded.method
                """,
                ((document_id, name, val, conf, meth) for name, val, conf, meth in items)
            )

    def get_or_create_personale(self, nome_completo: str) -> int:
        # This function needs to be atomic, so we wrap it in a transaction
        with self.conn:
            row = self.conn.execute("SELECT id FROM personale WHERE nome_completo = ?", (nome_completo,)).fetchone()
            if row:
                return row['id']
            cursor = self.conn.execute("INSERT INTO personale (nome_completo) VALUES (?)", (nome_completo,))
            return cursor.lastrowid

    def get_or_create_commessa(self, nome: str) -> int:
        with self.conn:
            row = self.conn.execute("SELECT id FROM commesse WHERE nome = ?", (nome,)).fetchone()
            if row:
                return row['id']
            cursor = self.conn.execute("INSERT INTO commesse (nome) VALUES (?)", (nome,))
            return cursor.lastrowid

    def replace_timesheet_rows(self, document_id: int, rows: List[Dict[str, Any]]):
        with self.conn: # A single transaction for the entire replacement operation
            self.conn.execute("DELETE FROM timesheet_rows WHERE document_id = ?", (document_id,))
            to_insert = []
            for r in rows:
                operaio = r.get('operaio')
                commessa = r.get('commessa')
                if not operaio or not commessa:
                    continue

                personale_id = self.get_or_create_personale(operaio)
                commessa_id = self.get_or_create_commessa(commessa)

                to_insert.append((
                    document_id, r.get('data'), r.get('ore'), r.get('descrizione'), r.get('reparto'),
                    personale_id, commessa_id
                ))

            if to_insert:
                self.conn.executemany(
                    "INSERT INTO timesheet_rows (document_id, data, ore, descrizione, reparto, personale_id, commessa_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    to_insert
                )

    def list_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._query("SELECT id, kind, filename, size_bytes, created_at FROM documents ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in rows]

    def timesheet_distincts(self) -> Dict[str, List[str]]:
        return {
            "commessa": [r["nome"] for r in self._query("SELECT nome FROM commesse ORDER BY nome ASC")],
            "operaio": [r["nome_completo"] for r in self._query("SELECT nome_completo FROM personale ORDER BY nome_completo ASC")],
            "reparto": [r["reparto"] for r in self._query("SELECT DISTINCT reparto FROM timesheet_rows WHERE reparto IS NOT NULL AND reparto <> '' ORDER BY reparto ASC")]
        }

    def timesheet_query(self, date_from: Optional[str] = None, date_to: Optional[str] = None, commesse: Optional[List[str]] = None, operai: Optional[List[str]] = None, reparti: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        sql = "SELECT t.id, t.document_id, t.data, p.nome_completo AS operaio, c.nome AS commessa, t.reparto, t.ore, t.descrizione FROM timesheet_rows t JOIN personale p ON t.personale_id = p.id JOIN commesse c ON t.commessa_id = c.id WHERE 1=1"
        params: List[Any] = []
        if date_from:
            sql += " AND t.data >= ?"; params.append(date_from)
        if date_to:
            sql += " AND t.data <= ?"; params.append(date_to)
        if commesse:
            sql += f" AND c.nome IN ({','.join('?' for _ in commesse)})"; params.extend(commesse)
        if operai:
            sql += f" AND p.nome_completo IN ({','.join('?' for _ in operai)})"; params.extend(operai)
        if reparti:
            sql += f" AND t.reparto IN ({','.join('?' for _ in reparti)})"; params.extend(reparti)
        sql += " ORDER BY t.data ASC, t.id ASC"
        rows = self._query(sql, params)
        return [dict(r) for r in rows]

    def list_personale(self) -> List[Dict[str, Any]]:
        rows = self._query("SELECT id, nome_completo, qualifica, created_at FROM personale ORDER BY nome_completo ASC")
        return [dict(row) for row in rows]

    def add_personale(self, nome_completo: str, qualifica: Optional[str] = None):
        self._execute("INSERT INTO personale (nome_completo, qualifica) VALUES (?, ?)", (nome_completo, qualifica))

    def list_commesse(self) -> List[Dict[str, Any]]:
        rows = self._query("SELECT id, nome, cliente, stato, created_at FROM commesse ORDER BY nome ASC")
        return [dict(row) for row in rows]

    def add_commessa(self, nome: str, cliente: Optional[str] = None):
        self._execute("INSERT INTO commesse (nome, cliente) VALUES (?, ?)", (nome, cliente))

    def update_commessa(self, commessa_id: int, updates: Dict[str, Any]):
        if not updates: return
        set_clauses = []
        params = []
        for key, value in updates.items():
            if key in ["nome", "cliente", "stato"]:
                set_clauses.append(f"{key} = ?")
                params.append(value)
        if not set_clauses: return
        params.append(commessa_id)
        sql = f"UPDATE commesse SET {', '.join(set_clauses)} WHERE id = ?"
        self._execute(sql, tuple(params))

    def get_summary_data(self) -> List[Dict[str, Any]]:
        sql = """
            SELECT p.nome_completo AS operaio, c.nome AS commessa, SUM(t.ore) AS ore_totali
            FROM timesheet_rows t
            JOIN personale p ON t.personale_id = p.id
            JOIN commesse c ON t.commessa_id = c.id
            GROUP BY p.nome_completo, c.nome ORDER BY p.nome_completo, c.nome;
        """
        rows = self._query(sql)
        return [dict(row) for row in rows]

    def delete_all_data(self):
        with self.conn:
            self.conn.execute("DELETE FROM timesheet_rows;")
            self.conn.execute("DELETE FROM extractions;")
            self.conn.execute("DELETE FROM documents;")
            self.conn.execute("DELETE FROM sqlite_sequence;")
        print("INFO: Tutti i dati sono stati cancellati dal database.")

db_manager = Database(db_path=DB_PATH)