# tools/extractors.py - Aggiornato per i tuoi formati specifici
from __future__ import annotations
import io
from datetime import date
from typing import List, Dict, Any, Tuple
import pandas as pd
import locale

# Impostiamo la lingua italiana per i mesi
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
        # Fallback per i mesi italiani
        mesi = {
            'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
            'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
        }
        month_num = mesi.get(month_str.lower())
        if not month_num:
            raise ExcelParsingError(f"Mese non riconosciuto: '{month_str}'.")
    except Exception:
        raise ExcelParsingError(f"Errore nel parsing del mese: '{month_str}'.")

    try:
        year_num = int(year_str)
    except ValueError:
        raise ExcelParsingError(f"Anno non valido: '{year_str}'.")
        
    return month_num, year_num

def parse_monthly_timesheet_excel(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Analizza il rapportino mensile nel TUO formato specifico:
    - Riga 1: "SETTEMBRE 2025"
    - Riga 2: "Operaio", 1, 2, 3... 30
    - Righe successive: Nome operaio + ore per ogni giorno
    """
    try:
        # Leggiamo la prima riga per estrarre mese e anno
        df_header = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=1)
        if df_header.empty:
            raise ExcelParsingError("Il file Excel è vuoto o illeggibile.")
        
        month_year_string = str(df_header.iloc[0, 0])
        month, year = _parse_month_year_from_header(month_year_string)
        print(f"✅ Rilevato: {month_year_string} → Mese {month}, Anno {year}")

        # Leggiamo il resto del file, usando la seconda riga come intestazione
        df_data = pd.read_excel(io.BytesIO(file_bytes), header=1)

        # Validazione colonne
        if 'Operaio' not in df_data.columns:
            raise ExcelParsingError("La colonna 'Operaio' non è stata trovata (attesa in riga 2).")
        
        print(f"✅ Trovati {len(df_data)} operai nel rapportino")
        
        # Pulizia dati
        df_data.dropna(how='all', inplace=True)
        
        # Converte da formato wide a long (una riga per ogni giorno/operaio)
        df_melted = df_data.melt(id_vars=['Operaio'], var_name='giorno', value_name='ore')
        
        # Filtra solo righe con ore > 0
        df_melted.dropna(subset=['ore'], inplace=True)
        df_melted = df_melted[df_melted['ore'] > 0]
        
        # Pulizia tipi di dati
        df_melted['Operaio'] = df_melted['Operaio'].astype(str)
        df_melted['giorno'] = pd.to_numeric(df_melted['giorno'], errors='coerce')
        df_melted['ore'] = pd.to_numeric(df_melted['ore'], errors='coerce')
        
        # Rimuove righe con dati non validi
        df_melted.dropna(subset=['giorno', 'ore'], inplace=True)
        df_melted['giorno'] = df_melted['giorno'].astype(int)

        # Creazione record finali
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
                print(f"⚠️ Giorno '{row['giorno']}' non valido per {month}/{year}. Riga ignorata.")
                continue

        print(f"✅ Processati {len(records)} record validi")
        return records

    except Exception as e:
        if isinstance(e, ExcelParsingError):
            raise
        raise ExcelParsingError(f"Errore imprevisto durante l'analisi del rapportino: {e}")
