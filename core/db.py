from __future__ import annotations

import os
import sqlite3
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple
import streamlit as st

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import DB_PATH

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
        self.conn = get_db_connection(db_path)
        self._init_schema()

    def _query(self, sql: str, params: Iterable = ()) -> List[sqlite3.Row]:
        """Helper for executing a read query."""
        cur = self.conn.cursor()
        cur.execute(sql, tuple(params))
        return cur.fetchall()

    def _init_schema(self):
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
                CREATE TABLE IF NOT EXISTS timesheet_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    data TEXT, commessa TEXT, operaio TEXT, reparto TEXT, ore REAL, descrizione TEXT
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

    def replace_timesheet_rows(self, document_id: int, rows: List[Dict[str, Any]]):
        with self.conn:
            self.conn.execute("DELETE FROM timesheet_rows WHERE document_id = ?", (document_id,))
            to_insert = [(document_id, r.get('data'), r.get('commessa'), r.get('operaio'), r.get('reparto'), r.get('ore'), r.get('descrizione')) for r in rows]
            if to_insert:
                self.conn.executemany(
                    "INSERT INTO timesheet_rows (document_id, data, commessa, operaio, reparto, ore, descrizione) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    to_insert
                )

    def list_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._query("SELECT id, kind, filename, size_bytes, created_at FROM documents ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in rows]

    def timesheet_distincts(self) -> Dict[str, List[str]]:
        out = {}
        for col in ("commessa", "operaio", "reparto"):
            rows = self._query(f"SELECT DISTINCT {col} AS v FROM timesheet_rows WHERE {col} IS NOT NULL AND {col} <> '' ORDER BY {col} ASC")
            out[col] = [r["v"] for r in rows]
        return out

    def timesheet_query(self, date_from: Optional[str] = None, date_to: Optional[str] = None, commesse: Optional[List[str]] = None, operai: Optional[List[str]] = None, reparti: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        sql = ["SELECT id, document_id, data, commessa, operaio, reparto, ore, descrizione FROM timesheet_rows WHERE 1=1"]
        params: List[Any] = []
        if date_from:
            sql.append("AND data >= ?"); params.append(date_from)
        if date_to:
            sql.append("AND data <= ?"); params.append(date_to)
        if commesse:
            sql.append(f"AND commessa IN ({','.join('?' for _ in commesse)})"); params.extend(commesse)
        if operai:
            sql.append(f"AND operaio IN ({','.join('?' for _ in operai)})"); params.extend(operai)
        if reparti:
            sql.append(f"AND reparto IN ({','.join('?' for _ in reparti)})"); params.extend(reparti)
        sql.append("ORDER BY data ASC, id ASC")
        rows = self._query(" ".join(sql), params)
        return [dict(r) for r in rows]

    def delete_all_data(self):
        with self.conn:
            self.conn.execute("DELETE FROM timesheet_rows;")
            self.conn.execute("DELETE FROM extractions;")
            self.conn.execute("DELETE FROM documents;")
            self.conn.execute("DELETE FROM sqlite_sequence;")
        print("INFO: Tutti i dati sono stati cancellati dal database.")

db_manager = Database(db_path=DB_PATH)