from __future__ import annotations
import json
import sys
import os
# Import custom per aggiungere la root del progetto al path, come da tua correzione
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pandas as pd
from ollama import Client

from core.config import OLLAMA_MODEL
from core.db import db_manager


def get_ai_response(chat_history: list[dict]) -> str:
    """
    Logica avanzata per la chat:
    1. L'AI interpreta la domanda dell'utente per capire quali filtri applicare.
    2. Esegue una query mirata al database con quei filtri.
    3. L'AI genera una risposta in linguaggio naturale basata sui risultati della query.
    """
    print("--- Avvio logica chat AVANZATA ---")
    client = Client()
    user_query = chat_history[-1]["content"]

    # --- FASE 1: RICONOSCIMENTO DELL'INTENTO E DEI PARAMETRI ---
    # Chiediamo all'AI di trasformare la domanda in un JSON che possiamo usare per la query
    
    # Prendiamo la lista degli operai e delle commesse esistenti dal DB per aiutare l'AI
    distincts = db_manager.timesheet_distincts()
    operai_disponibili = distincts.get('operaio', [])
    commesse_disponibili = distincts.get('commessa', [])

    intent_prompt = f"""
    Analizza la domanda dell'utente e trasformala in un JSON per interrogare un database.
    I campi possibili per il JSON sono: "operai" (una lista di nomi), "commesse" (una lista di nomi).
    Se l'utente non specifica un filtro, ometti la chiave dal JSON.

    Lista di operai conosciuti: {operai_disponibili}
    Lista di commesse conosciute: {commesse_disponibili}

    Esempi:
    - Domanda: "ore totali di Rossi Luca" -> {{"operai": ["Rossi Luca"]}}
    - Domanda: "quanto si è lavorato sulla commessa 24-015?" -> {{"commesse": ["24-015"]}}
    - Domanda: "ore di Bianchi Marco sulla commessa 24-015" -> {{"operai": ["Bianchi Marco"], "commesse": ["24-015"]}}
    - Domanda: "riepilogo generale" -> {{}}

    Domanda dell'utente da analizzare: "{user_query}"
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

    # --- FASE 2: ESECUZIONE DELLA QUERY SUL DATABASE ---
    try:
        # Usiamo i parametri estratti dall'AI per chiamare la nostra funzione esistente
        results = db_manager.timesheet_query(
            operai=query_params.get("operai"),
            commesse=query_params.get("commesse")
        )
        df = pd.DataFrame(results) if results else pd.DataFrame()
        
        context_data = "Non ho trovato dati corrispondenti ai filtri richiesti."
        if not df.empty:
            context_data = df.to_string() # Diamo all'AI i dati grezzi in formato testo

    except Exception as e:
        print(f"ERRORE nella fase di query al DB: {e}")
        return "Ho avuto un problema a interrogare il database."

    # --- FASE 3: GENERAZIONE DELLA RISPOSTA FINALE ---
    response_prompt = f"""
    Sei "CapoCantiere AI", un assistente virtuale.
    Rispondi alla domanda originale dell'utente in modo chiaro e conciso, usando i dati che ti fornisco.

    Dati estratti dal database:
    ---
    {context_data}
    ---

    Domanda originale dell'utente: "{user_query}"

    Formula la tua risposta finale.
    """

    try:
        final_response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': response_prompt}]
        )
        return final_response['message']['content']
    except Exception as e:
        print(f"ERRORE nella fase di generazione risposta: {e}")
        return "Ho trovato i dati ma ho avuto un problema a formulare la risposta."