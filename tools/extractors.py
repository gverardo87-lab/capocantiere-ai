# tools/extractors.py - Versione Definitiva per formato ORE/ID_ATTIVITA

from __future__ import annotations
import io
from datetime import date
from typing import List, Dict, Any, Tuple
import pandas as pd
import locale

try:
    locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Italian_Italy')
    except locale.Error:
        print("Attenzione: Locale italiano non trovato.")

class ExcelParsingError(Exception):
    pass

def _parse_month_year_from_header(header_string: str) -> Tuple[int, int]:
    parts = header_string.strip().split()
    if len(parts) != 2:
        raise ExcelParsingError(f"Formato intestazione non valido: '{header_string}'. Atteso 'MESE ANNO'.")
    month_str, year_str = parts
    try:
        mesi = {'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12}
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

def normalize_role(role_str: str) -> str:
    if pd.isna(role_str) or not role_str:
        return "Non specificato"
    role_str = str(role_str).strip().lower()
    role_mapping = {
        'aiutante carpentiere': 'Aiutante Carpentiere', 'aiutante carp': 'Aiutante Carpentiere', 'aiutante': 'Aiutante Carpentiere',
        'carpentiere': 'Carpentiere', 'carp': 'Carpentiere', 'saldatore': 'Saldatore', 'sald': 'Saldatore', 'welder': 'Saldatore',
        'molatore': 'Molatore', 'mol': 'Molatore', 'grinder': 'Molatore', 'verniciatore': 'Verniciatore', 'vern': 'Verniciatore',
        'painter': 'Verniciatore', 'pittore': 'Verniciatore', 'elettricista': 'Elettricista', 'elett': 'Elettricista',
        'elettrico': 'Elettricista', 'tubista': 'Tubista', 'tub': 'Tubista', 'pipes': 'Tubista', 'meccanico': 'Meccanico',
        'mecc': 'Meccanico', 'mec': 'Meccanico', 'montatore': 'Montatore', 'mont': 'Montatore', 'fabbricatore': 'Fabbricatore',
        'fabb': 'Fabbricatore', 'fab': 'Fabbricatore'
    }
    for pattern, normalized in role_mapping.items():
        if pattern in role_str:
            return normalized
    return role_str.capitalize()

def parse_monthly_timesheet_excel(file_bytes: bytes) -> List[Dict[str, Any]]:
    try:
        df_header = pd.read_excel(io.BytesIO(file_bytes), header=None, nrows=1)
        if df_header.empty: raise ExcelParsingError("File Excel vuoto.")
        
        month_year_string = str(df_header.iloc[0, 0])
        month, year = _parse_month_year_from_header(month_year_string)
        
        df_data = pd.read_excel(io.BytesIO(file_bytes), header=1)
        df_data.dropna(how='all', inplace=True)

        if 'Operaio' not in df_data.columns:
            raise ExcelParsingError("Colonna 'Operaio' non trovata.")

        records = []
        
        for index, row in df_data.iterrows():
            operaio = row['Operaio']
            ruolo = normalize_role(row.get('Ruolo', 'Non specificato'))

            for col_name in df_data.columns:
                if isinstance(col_name, int) and col_name >= 1 and col_name <= 31:
                    giorno = col_name
                    ore = row[giorno]

                    if pd.isna(ore) or ore <= 0:
                        continue
                    
                    # Cerca la colonna ID attività corrispondente
                    id_col_name = f'ID_attività'
                    if giorno > 1:
                        # Pandas aggiunge .N alle colonne duplicate
                        id_col_name_numbered = f'ID_attività.{giorno-1}'
                        if id_col_name_numbered in row:
                           id_col_name = id_col_name_numbered
                    
                    id_attivita = row.get(id_col_name)

                    try:
                        record = {
                            "data": date(year, month, giorno).strftime('%Y-%m-%d'),
                            "operaio": operaio.strip(),
                            "ruolo": ruolo,
                            "id_attivita": str(id_attivita) if pd.notna(id_attivita) else None,
                            "ore": float(ore)
                        }
                        records.append(record)
                    except (ValueError, TypeError):
                        continue
        
        print(f"✅ Processati {len(records)} record validi dal rapportino.")
        return records

    except Exception as e:
        if isinstance(e, ExcelParsingError):
            raise
        raise ExcelParsingError(f"Errore imprevisto durante l'analisi del rapportino: {e}")