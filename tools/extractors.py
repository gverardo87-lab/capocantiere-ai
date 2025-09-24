# tools/extractors.py - Aggiornato con supporto per colonna Ruolo
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

def normalize_role(role_str: str) -> str:
    """
    Normalizza i nomi dei ruoli per consistenza nel database.
    Gestisce variazioni comuni nei nomi dei ruoli.
    """
    if pd.isna(role_str) or not role_str:
        return "Non specificato"
    
    role_str = str(role_str).strip().lower()
    
    # Mapping delle variazioni comuni ai ruoli standard
    role_mapping = {
        'carpentiere': 'Carpentiere',
        'carp': 'Carpentiere',
        'aiutante carpentiere': 'Aiutante Carpentiere',
        'aiutante carp': 'Aiutante Carpentiere',
        'aiutante': 'Aiutante Carpentiere',
        'saldatore': 'Saldatore',
        'sald': 'Saldatore',
        'welder': 'Saldatore',
        'molatore': 'Molatore',
        'mol': 'Molatore',
        'grinder': 'Molatore',
        'verniciatore': 'Verniciatore',
        'vern': 'Verniciatore',
        'painter': 'Verniciatore',
        'pittore': 'Verniciatore',
        'elettricista': 'Elettricista',
        'elett': 'Elettricista',
        'elettrico': 'Elettricista',
        'tubista': 'Tubista',
        'tub': 'Tubista',
        'pipes': 'Tubista',
        'meccanico': 'Meccanico',
        'mecc': 'Meccanico',
        'mec': 'Meccanico',
        'montatore': 'Montatore',
        'mont': 'Montatore',
        'fabbricatore': 'Fabbricatore',
        'fabb': 'Fabbricatore',
        'fab': 'Fabbricatore'
    }
    
    # Cerca corrispondenze nel mapping
    for pattern, normalized in role_mapping.items():
        if pattern in role_str:
            return normalized
    
    # Se non trova corrispondenze, capitalizza la prima lettera
    return role_str.capitalize()

def parse_monthly_timesheet_excel(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Analizza il rapportino mensile nel formato specifico con supporto per colonna Ruolo:
    - Riga 1: "SETTEMBRE 2025"
    - Riga 2: "Operaio", "Ruolo", 1, 2, 3... 30
    - Righe successive: Nome operaio, Ruolo, ore per ogni giorno
    
    Il formato supporta sia con che senza colonna Ruolo per retrocompatibilità.
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

        # Validazione colonne obbligatorie
        if 'Operaio' not in df_data.columns:
            raise ExcelParsingError("La colonna 'Operaio' non è stata trovata (attesa in riga 2).")
        
        # Verifica se esiste la colonna Ruolo (nuova funzionalità)
        has_role_column = 'Ruolo' in df_data.columns
        
        if has_role_column:
            print(f"✅ Colonna 'Ruolo' trovata - lettura ruoli abilitata")
        else:
            print(f"ℹ️ Colonna 'Ruolo' non trovata - i ruoli verranno inferiti dai nomi")
        
        print(f"✅ Trovati {len(df_data)} operai nel rapportino")
        
        # Pulizia dati
        df_data.dropna(how='all', inplace=True)
        
        # Prepara i dati prima del melt
        if has_role_column:
            # Mantieni sia Operaio che Ruolo come colonne ID
            id_vars = ['Operaio', 'Ruolo']
            # Normalizza i ruoli
            df_data['Ruolo'] = df_data['Ruolo'].apply(normalize_role)
        else:
            # Solo Operaio come colonna ID
            id_vars = ['Operaio']
            # Aggiungi colonna Ruolo vuota che verrà popolata dopo
            df_data['Ruolo'] = 'Non specificato'
        
        # Converte da formato wide a long (una riga per ogni giorno/operaio)
        # Esclude le colonne non numeriche dal melt
        value_vars = [col for col in df_data.columns if col not in id_vars and str(col).isdigit()]
        
        df_melted = df_data.melt(
            id_vars=id_vars, 
            value_vars=value_vars,
            var_name='giorno', 
            value_name='ore'
        )
        
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
        
        # Se non c'è colonna Ruolo, prova a inferire dal nome (retrocompatibilità)
        if not has_role_column:
            print("ℹ️ Inferenza ruoli dai nomi operai...")
            df_melted['Ruolo'] = df_melted['Operaio'].apply(infer_role_from_name)

        # Creazione record finali con ruolo incluso
        records = []
        roles_found = set()
        
        for _, row in df_melted.iterrows():
            try:
                giorno_valido = date(year, month, row['giorno'])
                role = row['Ruolo']
                roles_found.add(role)
                
                records.append({
                    "data": giorno_valido.strftime('%Y-%m-%d'),
                    "operaio": row['Operaio'].strip(),
                    "ruolo": role,
                    "ore": float(row['ore'])
                })
            except ValueError:
                print(f"⚠️ Giorno '{row['giorno']}' non valido per {month}/{year}. Riga ignorata.")
                continue

        # Report sui ruoli trovati
        if roles_found:
            print(f"✅ Ruoli identificati: {', '.join(sorted(roles_found))}")
        
        print(f"✅ Processati {len(records)} record validi con informazioni sui ruoli")
        return records

    except Exception as e:
        if isinstance(e, ExcelParsingError):
            raise
        raise ExcelParsingError(f"Errore imprevisto durante l'analisi del rapportino: {e}")

def infer_role_from_name(operaio_name: str) -> str:
    """
    Funzione di fallback per inferire il ruolo dal nome dell'operaio
    quando la colonna Ruolo non è presente (retrocompatibilità).
    """
    if not operaio_name:
        return "Non specificato"
    
    name_lower = operaio_name.lower()
    
    # Pattern di riconoscimento basati sui cognomi tipici per ruolo
    # (questi sono esempi, andrebbero personalizzati per il cantiere specifico)
    role_patterns = {
        'Carpentiere': ['verardo', 'giacomo', 'romano', 'carpent'],
        'Saldatore': ['rossi', 'luca', 'florin', 'roman', 'allam', 'sald'],
        'Elettricista': ['kakhon', 'khan', 'billal', 'sarkar', 'elett'],
        'Montatore': ['verdi', 'marco', 'bianchi', 'anna', 'mont'],
        'Verniciatore': ['gialli', 'simone', 'vern', 'pitt'],
        'Molatore': ['mol', 'grind'],
        'Tubista': ['tub', 'pipe'],
        'Meccanico': ['mecc', 'mec'],
        'Fabbricatore': ['fabb', 'fab']
    }
    
    for role, patterns in role_patterns.items():
        if any(pattern in name_lower for pattern in patterns):
            return role
    
    return "Non specificato"