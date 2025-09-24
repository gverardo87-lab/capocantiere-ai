# tools/schedule_extractor.py - Aggiornato per il TUO cronoprogramma
from __future__ import annotations
import io
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime

class ScheduleParsingError(Exception):
    pass

def parse_schedule_excel(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Analizza il cronoprogramma nel TUO formato specifico:
    - Headers: ID_Attivita, Descrizione, Data_Inizio, Data_Fine, Stato_Avanzamento, Commessa, Predecessori
    - Date formato: "01/09/25" (DD/MM/YY)
    - ID con prefissi tipo: MON-001, FAM-001, ELE-001
    """
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), engine='openpyxl')

        if df.empty:
            raise ScheduleParsingError("Il file Excel è vuoto o illeggibile.")

        # Pulizia nomi colonne
        df.columns = df.columns.str.strip()

        # Verifica colonne richieste
        required_columns = ['ID_Attivita', 'Descrizione', 'Data_Inizio', 'Data_Fine']
        for col in required_columns:
            if col not in df.columns:
                raise ScheduleParsingError(f"Colonna richiesta mancante: '{col}'.")

        print(f"✅ Trovate {len(df)} attività nel cronoprogramma")

        # Pulizia righe vuote
        df.dropna(how='all', inplace=True)

        # PARSING DATE SPECIFICO PER IL TUO FORMATO "DD/MM/YY"
        def parse_date_format(date_str):
            if pd.isna(date_str):
                return pd.NaT
            try:
                # Prova formato DD/MM/YY (il tuo formato)
                return pd.to_datetime(date_str, format='%d/%m/%y')
            except:
                try:
                    # Prova formato DD/MM/YYYY (alternativo)
                    return pd.to_datetime(date_str, format='%d/%m/%Y')
                except:
                    # Ultimo tentativo con parsing automatico
                    return pd.to_datetime(date_str, errors='coerce')

        df['Data_Inizio'] = df['Data_Inizio'].apply(parse_date_format)
        df['Data_Fine'] = df['Data_Fine'].apply(parse_date_format)

        # Filtra solo righe con date valide
        df.dropna(subset=['Data_Inizio', 'Data_Fine'], inplace=True)

        if df.empty:
            raise ScheduleParsingError("Nessuna attività con date valide trovata.")

        print(f"✅ {len(df)} attività con date valide processate")

        # Conversione finale per il database
        records = []
        for _, row in df.iterrows():
            record = {
                "id_attivita": str(row['ID_Attivita']),
                "descrizione": str(row['Descrizione']),
                "data_inizio": row['Data_Inizio'].strftime('%Y-%m-%d'),
                "data_fine": row['Data_Fine'].strftime('%Y-%m-%d'),
                "stato_avanzamento": int(row.get('Stato_Avanzamento', 0) or 0),
                "commessa": str(row.get('Commessa', '') or ''),
                "predecessori": str(row.get('Predecessori', '') or '')
            }
            records.append(record)

        return records

    except Exception as e:
        if isinstance(e, ScheduleParsingError):
            raise
        raise ScheduleParsingError(f"Errore durante la lettura del cronoprogramma: {e}")