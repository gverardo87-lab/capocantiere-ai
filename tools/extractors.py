# tools/extractors.py
from __future__ import annotations
import io
from datetime import date
from typing import List, Dict, Any, Tuple
import pandas as pd
import locale

# Impostiamo la lingua italiana per poter riconoscere i nomi dei mesi
# Questo blocco prova diverse configurazioni per la massima compatibilità
try:
    locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Italian_Italy')
    except locale.Error:
        print("Attenzione: Locale italiano non trovato. L'analisi dei mesi potrebbe fallire.")

class ExcelParsingError(Exception):
    """Eccezione personalizzata per errori durante il parsing dei file Excel."""
    pass

def _parse_month_year_from_header(header_string: str) -> Tuple[int, int]:
    """
    Estrae mese e anno da una stringa come "SETTEMBRE 2025".
    """
    parts = header_string.strip().split()
    if len(parts) != 2:
        raise ExcelParsingError(f"Formato intestazione non valido: '{header_string}'. Atteso 'MESE ANNO'.")
    
    month_str, year_str = parts
    
    # Converte il nome del mese in un numero (1-12)
    try:
        # Crea un oggetto data fittizio per estrarre il numero del mese
        month_num = list(map(str.lower, locale.nl_langinfo(locale.MONTH).split(';'))).index(month_str.lower()) + 1

    except (ValueError, AttributeError):
        # Fallback nel caso il locale non funzioni
        mesi = {
            'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
            'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
        }
        month_num = mesi.get(month_str.lower())
        if not month_num:
            raise ExcelParsingError(f"Mese non riconosciuto: '{month_str}'.")

    try:
        year_num = int(year_str)
    except ValueError:
        raise ExcelParsingError(f"Anno non valido: '{year_str}'.")
        
    return month_num, year_num

def parse_monthly_timesheet_excel(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Analizza un file Excel di rapportino mensile, estraendo automaticamente
    mese e anno dalla prima riga.

    La struttura attesa del file è:
    - Riga 1: Mese e Anno (es. "SETTEMBRE 2025").
    - Riga 2: Intestazioni delle colonne ('Operaio', 1, 2, 3...).
    - Dalla riga 3 in poi: Dati delle presenze.

    Args:
        file_bytes: Il contenuto del file Excel in formato bytes.

    Returns:
        Una lista di dizionari, ognuno rappresentante una presenza giornaliera.
        Esempio: {'data': '2025-09-01', 'operaio': 'Rossi Luca', 'ore': 8.0}

    Raises:
        ExcelParsingError: Per qualsiasi errore di formato nel file Excel.
    """
    try:
        # Leggiamo la prima riga per estrarre mese e anno
        df_header = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=1)
        if df_header.empty:
            raise ExcelParsingError("Il file Excel è vuoto o illeggibile.")
        
        month_year_string = str(df_header.iloc[0, 0])
        month, year = _parse_month_year_from_header(month_year_string)

        # Leggiamo il resto del file, usando la seconda riga (indice 1) come intestazione
        df_data = pd.read_excel(io.BytesIO(file_bytes), header=1)

        # --- VALIDAZIONE E TRASFORMAZIONE (come prima) ---
        if 'Operaio' not in df_data.columns:
            raise ExcelParsingError("La colonna 'Operaio' non è stata trovata (attesa in riga 2).")
        
        df_data.dropna(how='all', inplace=True)
        
        df_melted = df_data.melt(id_vars=['Operaio'], var_name='giorno', value_name='ore')
        
        df_melted.dropna(subset=['ore'], inplace=True)
        df_melted = df_melted[df_melted['ore'] > 0]
        
        df_melted['Operaio'] = df_melted['Operaio'].astype(str)
        df_melted['giorno'] = pd.to_numeric(df_melted['giorno'], errors='coerce')
        df_melted['ore'] = pd.to_numeric(df_melted['ore'], errors='coerce')
        
        df_melted.dropna(subset=['giorno', 'ore'], inplace=True)
        df_melted['giorno'] = df_melted['giorno'].astype(int)

        # --- CREAZIONE RECORD FINALI ---
        records = []
        for _, row in df_melted.iterrows():
            try:
                giorno_valido = date(year, month, row['giorno'])
                records.append({
                    "data": giorno_valido.strftime('%Y-%m-%d'),
                    "operaio": row['Operaio'].strip(),
                    "ore": float(row['ore'])
                })
            except ValueError:
                print(f"Attenzione: giorno '{row['giorno']}' non valido per {month}/{year}. Riga ignorata.")
                continue

        if not records:
             print("Attenzione: Nessun record valido trovato nel file dopo l'analisi.")

        return records

    except Exception as e:
        # Se l'errore è già del nostro tipo, lo rilanciamo, altrimenti lo "impacchettiamo"
        if isinstance(e, ExcelParsingError):
            raise
        raise ExcelParsingError(f"Errore imprevisto durante l'analisi del file Excel: {e}")