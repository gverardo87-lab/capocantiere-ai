from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

import ollama
import pandas as pd
from docx import Document as DocxDocument
from openpyxl import load_workbook
from pypdf import PdfReader

# Importa le nuove variabili di configurazione
from core.config import OLLAMA_HOST, OLLAMA_MODEL


# --- Strutture Dati di Base (invariato) ---
@dataclass
class ExtractedField:
    name: str
    value: Optional[str]
    confidence: str
    method: str


# --- Funzioni di Utilità (invariato) ---
def file_sha256(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def sniff_mime(filename: str) -> str:
    m, _ = mimetypes.guess_type(filename)
    return m or "application/octet-stream"


# --- Motore di Estrazione Testo (invariato) ---
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

def parse_timesheet_csv(data: bytes) -> Tuple[List[Dict[str, Any]], List[ExtractedField]]:
    # ... (questa funzione rimane uguale al tuo codice originale)
    EXPECTED_COLUMNS = {"data", "commessa", "operaio", "reparto", "ore", "descrizione"}
    with io.BytesIO(data) as f:
        df = pd.read_csv(f)
    actual_columns = set(c.lower() for c in df.columns)
    if not EXPECTED_COLUMNS.issubset(actual_columns):
        raise ValueError(f"Colonne mancanti: {EXPECTED_COLUMNS - actual_columns}")
    df.columns = df.columns.str.lower()
    df['data'] = pd.to_datetime(df['data'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['ore'] = pd.to_numeric(df['ore'], errors='coerce').fillna(0)
    df = df.dropna(subset=['data'])
    summary_fields = [
        ExtractedField("periodo_dal", df['data'].min(), "green", "csv-summary"),
        ExtractedField("periodo_al", df['data'].max(), "green", "csv-summary"),
        ExtractedField("totale_ore", str(df['ore'].sum()), "green", "csv-summary"),
        ExtractedField("numero_operai", str(df['operaio'].nunique()), "green", "csv-summary"),
    ]
    return df.to_dict('records'), summary_fields


# --- NUOVA FUNZIONE PER ESTRAZIONE CON OLLAMA ---
def extract_fields_with_ai(text: str) -> List[ExtractedField]:
    """Usa Ollama per estrarre campi chiave-valore da un testo."""
    if not text or len(text.strip()) < 20:
        return []
    print(f"INFO: Sto contattando Ollama (modello: {OLLAMA_MODEL}) per l'analisi del testo...")
    prompt = f"""
    Analizza il seguente testo e estrai le informazioni chiave in formato JSON.
    Cerca di identificare etichette (come 'Numero Fattura', 'Data', 'Totale') e i loro valori.
    Restituisci SOLO un oggetto JSON. Esempio: {{"numero_fattura": "123", "data_documento": "10/09/2025"}}

    Testo da analizzare:
    ---
    {text[:4000]}
    ---
    """
    try:
        response = ollama.generate(model=OLLAMA_MODEL, prompt=prompt, format="json", stream=False)
        data = json.loads(response.get('response', '{}'))
        fields = []
        if isinstance(data, dict):
            for key, value in data.items():
                field_name = key.strip().replace(" ", "_").lower()
                field_value = str(value).strip() if value else None
                fields.append(ExtractedField(name=field_name, value=field_value, confidence="yellow", method="ollama"))
        print(f"INFO: Ollama ha estratto {len(fields)} campi.")
        return fields
    except Exception as e:
        print(f"ERRORE: Impossibile contattare o analizzare la risposta di Ollama: {e}")
        return []

# --- Logica di Classificazione (invariato) ---
def classify_kind(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["fattura", "imponibile", "iva"]): return "FATTURA"
    if any(k in t for k in ["rapporto", "rapportino", "ore lavorate"]): return "RAPPORTO"
    if any(k in t for k in ["permesso di lavoro", "work permit"]): return "PERMESSO"
    return "ALTRO"


# --- Funzione di Estrazione Campi (MODIFICATA) ---
def extract_fields_from_text(text: str) -> List[ExtractedField]:
    fields = []
    # 1. Estrazione con Regex (logica esistente)
    match_piva = re.search(r"p\.?\s?iva\s*:?\s*(\d{11})", text, re.IGNORECASE)
    fields.append(ExtractedField("p_iva", match_piva.group(1) if match_piva else None, "green" if match_piva else "red", "regex"))
    match_data = re.search(r"(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})", text)
    fields.append(ExtractedField("data_documento", match_data.group(1) if match_data else None, "yellow" if match_data else "red", "regex"))

    # --- INTEGRAZIONE OLLAMA ---
    # 2. Estrazione con AI (nuova logica)
    try:
        ai_fields = extract_fields_with_ai(text)
        existing_field_names = {f.name for f in fields}
        for field in ai_fields:
            if field.name not in existing_field_names:
                fields.append(field)
    except Exception as e:
        print(f"ERRORE durante l'estrazione AI: {e}")
    # --- FINE INTEGRAZIONE ---
    return fields


# --- Funzione Principale di Orchestrazione (invariato) ---
def read_text_and_kind(filename: str, data: bytes) -> Tuple[str, str]:
    # ... (questa funzione rimane uguale al tuo codice originale)
    mime_type = sniff_mime(filename)
    text = ""
    if filename.lower().endswith('.csv'):
        try:
            with io.BytesIO(data) as f:
                header = pd.read_csv(f, nrows=0).columns.str.lower().to_list()
            if {"data", "commessa", "operaio", "ore"}.issubset(set(header)):
                return data.decode('utf-8', errors='ignore'), "RAPPORTO_CSV"
        except Exception:
            pass
    if mime_type == "application/pdf": text = extract_text_from_pdf(data)
    elif "wordprocessingml" in mime_type or filename.endswith(".docx"): text = extract_text_from_docx(data)
    elif "spreadsheetml" in mime_type or filename.endswith(".xlsx"): text = extract_text_from_xlsx(data)
    else:
        try: text = data.decode("utf-8")
        except UnicodeDecodeError: text = data.decode("latin-1", errors="ignore")
    kind = classify_kind(text)
    return text, kind