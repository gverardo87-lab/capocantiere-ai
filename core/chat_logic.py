from __future__ import annotations
import json
import sys
import os
# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pandas as pd
from ollama import Client

from core.config import OLLAMA_MODEL
from core.db import db_manager


def get_ai_response(chat_history: list[dict]) -> str:
    """
    Logica di chat basata su un'unica fonte di verità per i calcoli.
    1. L'AI interpreta la domanda con contesto per definire i filtri di query.
    2. Il database esegue la query e restituisce dati GIÀ CALCOLATI.
    3. Il codice Python AGGREGA questi dati corretti usando Pandas.
    4. L'AI usa il riepilogo aggregato per formulare una risposta in linguaggio naturale.
    """
    print("--- Avvio logica chat con Single Source of Truth ---")
    client = Client()
    user_query = chat_history[-1]["content"]

    # --- FASE 1: RICONOSCIMENTO DELL'INTENTO (con memoria) ---
    distincts = db_manager.timesheet_distincts()
    operai_disponibili = distincts.get('operaio', [])
    commesse_disponibili = distincts.get('commessa', [])

    context_history = ""
    if len(chat_history) > 2:
        last_user_question = chat_history[-3]['content']
        last_ai_answer = chat_history[-2]['content']
        context_history = f"""
        Contesto dell'ultima interazione:
        - Domanda precedente: "{last_user_question}"
        - Tua risposta precedente: "{last_ai_answer}"
        ---
        """

    intent_prompt = f"""
    Analizza la NUOVA domanda dell'utente, usando il contesto se necessario, e trasformala in un JSON per filtrare un database.
    {context_history}
    I campi JSON possibili sono "operai" (lista di nomi) e "commesse" (lista di nomi). Ometti le chiavi non specificate.

    Operai conosciuti: {operai_disponibili}
    Commesse conosciute: {commesse_disponibili}

    NUOVA Domanda: "{user_query}"
    """
    
    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': intent_prompt}],
            format="json",
            options={'temperature': 0.0}
        )
        query_params_str = response['message']['content']
        print(f"Parametri JSON estratti dall'AI: {query_params_str}")
        query_params = json.loads(query_params_str)
    except Exception as e:
        print(f"ERRORE nella fase di intent recognition: {e}")
        return "Mi dispiace, non sono riuscito a capire la tua domanda. Prova a riformularla."

    # --- FASE 2: RECUPERO DATI E AGGREGAZIONE SICURA ---
    try:
        # Chiamiamo la nostra unica fonte di verità per i dati calcolati
        results = db_manager.timesheet_query(
            operai=query_params.get("operai"),
            commesse=query_params.get("commesse")
        )
        
        if not results:
            context_data = "Non ho trovato dati che corrispondono alla tua richiesta."
        else:
            df = pd.DataFrame(results)
            
            # --- AGGREGAZIONE 100% PRECISA CON PANDAS ---
            total_worked_hours = df['ore_lavorate'].sum()
            
            summary = {
                "totale_record": len(df),
                "ore_lavorate_totali": round(total_worked_hours, 2),
                "ore_regolari_totali": round(df['ore_regolari'].sum(), 2),
                "ore_straordinario_totali": round(df['ore_straordinario'].sum(), 2),
                "dettaglio_per_operaio": None,
                "dettaglio_per_commessa": None
            }

            # Raggruppiamo solo se ha senso farlo
            if df['operaio'].nunique() > 1 and not query_params.get("operai"):
                summary["dettaglio_per_operaio"] = df.groupby('operaio')['ore_lavorate'].sum().round(2).to_dict()
            
            if df['commessa'].nunique() > 1 and not query_params.get("commesse"):
                summary["dettaglio_per_commessa"] = df.groupby('commessa')['ore_lavorate'].sum().round(2).to_dict()

            # Convertiamo il riepilogo in una stringa JSON pulita per l'AI
            context_data = json.dumps(summary, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"ERRORE nella fase di query e aggregazione: {e}")
        return "Ho avuto un problema a recuperare e aggregare i dati."

    # --- FASE 3: GENERAZIONE DELLA RISPOSTA FINALE ---
    response_prompt = f"""
    Sei "CapoCantiere AI". Il tuo unico compito è presentare in modo chiaro e in italiano i dati numerici di un riepilogo JSON che ti viene fornito.
    NON DEVI FARE CALCOLI. Devi solo leggere e riportare i numeri dal JSON.

    Dati da presentare (in formato JSON):
    ---
    {context_data}
    ---

    Domanda originale dell'utente a cui stai rispondendo: "{user_query}"

    Formula la tua risposta finale in modo naturale e conciso.
    """

    try:
        final_response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': response_prompt}]
        )
        return final_response['message']['content']
    except Exception as e:
        print(f"ERRORE nella fase di generazione risposta: {e}")
        return "Ho aggregato i dati, ma ho avuto un problema a formulare la risposta."