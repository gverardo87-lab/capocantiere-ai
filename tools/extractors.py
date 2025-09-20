from __future__ import annotations

import hashlib
import io
import mimetypes
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

import pandas as pd
from docx import Document as DocxDocument
from openpyxl import load_workbook
from pypdf import PdfReader


# --- Strutture Dati di Base ---

@dataclass
class ExtractedField:
    """Rappresenta un singolo campo estratto da un documento."""
    name: str
    value: Optional[str]
    confidence: str
    method: str


# --- Funzioni di Utilità ---

def file_sha256(data: bytes) -> str:
    """Calcola l'hash SHA256 di un blocco di dati."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sniff_mime(filename: str) -> str:
    """Indovina il tipo MIME di un file dal suo nome."""
    m, _ = mimetypes.guess_type(filename)
    return m or "application/octet-stream"


# --- Motore di Estrazione Testo dai File ---

def extract_text_from_pdf(data: bytes) -> str:
    with io.BytesIO(data) as f:
        reader = PdfReader(f)
        return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_docx(data: bytes) -> str:
    with io.BytesIO(data) as f:
        doc = DocxDocument(f)
        return "\n".join(p.text for p in doc.paragraphs if p.text)


def extract_text_from_xlsx(data: bytes, max_cells: int = 2000) -> str:
    with io.BytesIO(data) as f:
        wb = load_workbook(f, data_only=True)
        text_chunks = []
        cell_count = 0
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for value in row:
                    if value is not None:
                        text_chunks.append(str(value))
                        cell_count += 1
                        if cell_count >= max_cells:
                            return "\n".join(text_chunks)
        return "\n".join(text_chunks)


# --- NUOVA FUNZIONE SPECIALIZZATA PER RAPPORTINI CSV ---

def parse_timesheet_csv(data: bytes) -> Tuple[List[Dict[str, Any]], List[ExtractedField]]:
    """
    Legge un rapportino ore da un file CSV, lo valida e lo struttura.
    Restituisce sia le righe di dati strutturate per il DB, sia i campi di riepilogo.
    """
    EXPECTED_COLUMNS = {"data", "commessa", "operaio", "reparto", "ore", "descrizione"}

    with io.BytesIO(data) as f:
        df = pd.read_csv(f)

    actual_columns = set(c.lower() for c in df.columns)
    if not EXPECTED_COLUMNS.issubset(actual_columns):
        raise ValueError(
            f"Il file CSV non è un rapportino valido. Colonne mancanti: {EXPECTED_COLUMNS - actual_columns}")

    df.columns = df.columns.str.lower()
    df['data'] = pd.to_datetime(df['data'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['ore'] = pd.to_numeric(df['ore'], errors='coerce').fillna(0)
    df = df.dropna(subset=['data'])  # Rimuove righe senza data valida

    total_hours = df['ore'].sum()
    start_date = df['data'].min()
    end_date = df['data'].max()
    unique_workers = df['operaio'].nunique()

    summary_fields = [
        ExtractedField("periodo_dal", start_date, "green", "csv-summary"),
        ExtractedField("periodo_al", end_date, "green", "csv-summary"),
        ExtractedField("totale_ore", str(total_hours), "green", "csv-summary"),
        ExtractedField("numero_operai", str(unique_workers), "green", "csv-summary"),
    ]

    structured_rows = df.to_dict('records')
    return structured_rows, summary_fields


# --- Logica di Classificazione e Estrazione Campi ---

def classify_kind(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["fattura", "imponibile", "iva"]):
        return "FATTURA"
    if any(k in t for k in ["rapporto", "rapportino", "ore lavorate"]):
        return "RAPPORTO"
    if any(k in t for k in ["permesso di lavoro", "work permit"]):
        return "PERMESSO"
    return "ALTRO"


def extract_fields_from_text(text: str) -> List[ExtractedField]:
    fields = []

    match_piva = re.search(r"p\.?\s?iva\s*:?\s*(\d{11})", text, re.IGNORECASE)
    fields.append(
        ExtractedField("p_iva", match_piva.group(1) if match_piva else None, "green" if match_piva else "red", "regex"))

    match_data = re.search(r"(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})", text)
    fields.append(
        ExtractedField("data_documento", match_data.group(1) if match_data else None, "yellow" if match_data else "red",
                       "regex"))

    return fields


# --- Funzione Principale di Orchestrazione ---

def read_text_and_kind(filename: str, data: bytes) -> Tuple[str, str]:
    mime_type = sniff_mime(filename)
    text = ""

    if filename.lower().endswith('.csv'):
        try:
            with io.BytesIO(data) as f:
                # Leggiamo solo l'header per una classificazione veloce
                header = pd.read_csv(f, nrows=0).columns.str.lower().to_list()
            if {"data", "commessa", "operaio", "ore"}.issubset(set(header)):
                return data.decode('utf-8', errors='ignore'), "RAPPORTO_CSV"
        except Exception:
            pass  # Se fallisce, trattalo come un file di testo normale

    if mime_type == "application/pdf":
        text = extract_text_from_pdf(data)
    elif "wordprocessingml" in mime_type or filename.endswith(".docx"):
        text = extract_text_from_docx(data)
    elif "spreadsheetml" in mime_type or filename.endswith(".xlsx"):
        text = extract_text_from_xlsx(data)
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1", errors="ignore")

    kind = classify_kind(text)
    return text, kind