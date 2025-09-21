from __future__ import annotations

import os
import sys
# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import hashlib
import io
import json
import mimetypes
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

import pandas as pd
from docx import Document as DocxDocument
from openpyxl import load_workbook
from pypdf import PdfReader
from ollama import Client

from core.config import OLLAMA_MODEL


# --- Strutture Dati di Base ---
@dataclass
class ExtractedField:
    name: str
    value: Optional[str]
    confidence: str
    method: str


# --- Funzioni di Utilità ---
def file_sha256(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def sniff_mime(filename: str) -> str:
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


# --- FUNZIONE CORRETTA PER IL PARSING DEL CSV ---
def parse_timesheet_csv(data: bytes) -> Tuple[List[Dict[str, Any]], List[ExtractedField]]:
    """Legge un rapportino ore da un file CSV, lo valida e lo struttura."""
    # Definiamo solo le colonne assolutamente necessarie
    REQUIRED_COLUMNS = {"data", "commessa", "operaio", "ore"}
    
    with io.BytesIO(data) as f:
        df = pd.read_csv(f)

    # Convertiamo i nomi delle colonne in minuscolo per un controllo robusto
    df.columns = df.columns.str.lower()
    
    actual_columns = set(df.columns)
    if not REQUIRED_COLUMNS.issubset(actual_columns):
        raise ValueError(f"Il file CSV non è un rapportino valido. Colonne obbligatorie mancanti: {REQUIRED_COLUMNS - actual_columns}")

    # Standardizzazione dei dati
    df['data'] = pd.to_datetime(df['data'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['ore'] = pd.to_numeric(df['ore'], errors='coerce').fillna(0)
    df = df.dropna(subset=['data'])
    
    # Assicuriamo che le colonne opzionali esistano, riempiendole con un valore vuoto se mancano
    for col in ['reparto', 'descrizione']:
        if col not in df.columns:
            df[col] = ''

    # Creazione dei campi di riepilogo
    summary_fields = [
        ExtractedField("periodo_dal", df['data'].min(), "green", "csv-summary"),
        ExtractedField("periodo_al", df['data'].max(), "green", "csv-summary"),
        ExtractedField("totale_ore", str(df['ore'].sum()), "green", "csv-summary"),
        ExtractedField("numero_operai", str(df['operaio'].nunique()), "green", "csv-summary"),
    ]
    
    # Selezioniamo solo le colonne che ci interessano per il database
    final_columns = ['data', 'commessa', 'operaio', 'reparto', 'ore', 'descrizione']
    structured_rows = df[final_columns].to_dict('records')
    
    return structured_rows, summary_fields


# --- Funzione di Estrazione con AI (invariata) ---
def extract_fields_with_ai(text: str, kind: str) -> List[ExtractedField]:
    # ... (il resto di questa funzione rimane uguale)
    if not text or len(text.strip()) < 10:
        return []
    print(f"--- Avvio estrazione AI (Modello: {OLLAMA_MODEL}, Tipo Doc: {kind}) ---")
    client = Client()
    if kind == "FATTURA":
        prompt_fields = "'numero_fattura', 'data_documento', 'totale_imponibile', 'totale_iva', 'totale_fattura', 'partita_iva_fornitore'"
    else:
        prompt_fields = "'oggetto_documento', 'data_documento', 'nome_cliente', 'riferimento_interno'"
    prompt = f"""
    Sei un assistente AI specializzato nell'analisi di documenti aziendali.
    Dal testo fornito, estrai i seguenti campi: {prompt_fields}.
    Rispondi ESCLUSIVAMENTE con un oggetto JSON valido. Non aggiungere spiegazioni o testo introduttivo.
    Se un valore non viene trovato, assegna il valore null a quel campo.

    Testo da analizzare:
    ---
    {text[:4000]}
    ---
    """
    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            format="json",
            options={'temperature': 0.0}
        )
        content = response['message']['content']
        print(f"Risposta JSON grezza dal modello: {content}")
        data = json.loads(content)
        fields = []
        if isinstance(data, dict):
            for key, value in data.items():
                if value:
                    fields.append(ExtractedField(
                        name=key.strip().lower(),
                        value=str(value).strip(),
                        confidence="yellow",
                        method=OLLAMA_MODEL.split(":")[0]
                    ))
        print(f"--- Estrazione AI completata. Trovati {len(fields)} campi. ---")
        return fields
    except Exception as e:
        print(f"ERRORE: Impossibile completare l'estrazione AI: {e}")
        return []


# --- Logica di Classificazione (invariata) ---
def classify_kind(text: str) -> str:
    # ... (il resto di questa funzione rimane uguale)
    t = (text or "").lower()
    if any(k in t for k in ["fattura", "imponibile", "iva"]):
        return "FATTURA"
    if any(k in t for k in ["rapporto", "rapportino", "ore lavorate"]):
        return "RAPPORTO"
    if any(k in t for k in ["permesso di lavoro", "work permit"]):
        return "PERMESSO"
    return "ALTRO"


# --- Funzione Principale di Orchestrazione (invariata) ---
def read_text_and_kind(filename: str, data: bytes) -> Tuple[str, str]:
    # ... (il resto di questa funzione rimane uguale)
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