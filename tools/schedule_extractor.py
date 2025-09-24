# tools/schedule_extractor.py
from __future__ import annotations
import io
from typing import List, Dict, Any
import pandas as pd

class ScheduleParsingError(Exception):
    """Eccezione personalizzata per errori durante il parsing dei file di cronoprogramma."""
    pass

def parse_schedule_excel(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Analizza un file Excel (.xlsx) di cronoprogramma in modo semplice e robusto.
    """
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), engine='openpyxl')

        if df.empty:
            raise ScheduleParsingError("Il file Excel è vuoto o illeggibile.")

        # 1. Pulizia dei nomi delle colonne (rimuove spazi extra)
        df.columns = df.columns.str.strip()

        # 2. Verifica delle colonne obbligatorie
        required_columns = ['ID_Attivita', 'Descrizione', 'Data_Inizio', 'Data_Fine']
        for col in required_columns:
            if col not in df.columns:
                raise ScheduleParsingError(f"Colonna richiesta mancante: '{col}'.")

        # 3. Rimuove righe completamente vuote che potrebbero dare problemi
        df.dropna(how='all', inplace=True)

        # 4. Gestione delle date: la parte più importante
        # Converte le colonne in date, e se una data non è valida, la cella diventa "NaT" (Not a Time)
        df['Data_Inizio'] = pd.to_datetime(df['Data_Inizio'], errors='coerce')
        df['Data_Fine'] = pd.to_datetime(df['Data_Fine'], errors='coerce')

        # 5. Filtro finale: teniamo solo le righe che hanno SIA una data di inizio VALIDA SIA una di fine VALIDA
        df.dropna(subset=['Data_Inizio', 'Data_Fine'], inplace=True)

        # Se dopo il filtro non resta nulla, lo segnaliamo
        if df.empty:
            raise ScheduleParsingError("Il file non contiene righe con date di inizio e fine valide.")
        
        # 6. Conversione finale dei dati per il database
        records = []
        for _, row in df.iterrows():
            record = {
                "id_attivita": str(row['ID_Attivita']),
                "descrizione": str(row['Descrizione']),
                "data_inizio": row['Data_Inizio'].strftime('%Y-%m-%d'),
                "data_fine": row['Data_Fine'].strftime('%Y-%m-%d'),
                # Gestione sicura delle colonne opzionali
                "stato_avanzamento": int(row.get('Stato_Avanzamento', 0) or 0),
                "commessa": str(row.get('Commessa', '') or ''),
                "predecessori": str(row.get('Predecessori', '') or '')
            }
            records.append(record)

        return records

    except Exception as e:
        if isinstance(e, ScheduleParsingError):
            raise
        # Rilancia un errore più chiaro
        raise ScheduleParsingError(f"Errore critico durante la lettura del file Excel. Dettagli: {e}")