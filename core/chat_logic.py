from __future__ import annotations
import ollama
from core.config import OLLAMA_MODEL
from core.db import db_manager
import pandas as pd


def get_ai_response(chat_history: list[dict]) -> str:
    """
    Prende la cronologia della chat, interroga il DB per dati rilevanti
    e genera una risposta con Ollama.
    """

    # Prendi l'ultima domanda dell'utente
    user_query = chat_history[-1]["content"]

    # --- Step 1: Cerca dati rilevanti nel database ---
    # Questa è una logica SEMPLICE. In futuro potremmo renderla più intelligente
    # per capire meglio cosa l'utente sta chiedendo e interrogare il db in modo più mirato.
    # Per ora, prendiamo un riassunto generale delle ore.

    try:
        # Eseguiamo una query generica per avere un contesto sui dati disponibili
        all_timesheet_data = db_manager.timesheet_query()
        df = pd.DataFrame(all_timesheet_data)

        context_data = "Nessun dato sui rapportini presente nel database."
        if not df.empty:
            total_ore = df['ore'].sum()
            operai = df['operaio'].unique()
            commesse = df['commessa'].unique()

            context_data = f"""
            Ecco un riepilogo dei dati attualmente presenti nel database:
            - Totale Ore Registrate: {total_ore:.2f}
            - Operai Coinvolti: {', '.join(operai)}
            - Commesse Attive: {', '.join(commesse)}

            Usa questi dati per rispondere alla domanda dell'utente. Se la domanda è specifica 
            (es. "ore di un operaio"), rispondi basandoti su questi dati aggregati 
            o suggerisci all'utente di usare i filtri per un'analisi dettagliata.
            """
    except Exception as e:
        context_data = f"Errore durante la connessione al database: {e}"

    # --- Step 2: Prepara il prompt per Ollama ---
    prompt = f"""
    Sei "CapoCantiere AI", un assistente virtuale per la gestione di dati di cantiere.
    Rispondi in modo conciso e professionale.

    CONTESTO DAI DATI DEL DATABASE:
    {context_data}

    DOMANDA DELL'UTENTE: "{user_query}"

    Rispondi alla domanda usando il contesto fornito.
    """

    # Aggiungiamo il prompt "di sistema" alla cronologia per dare istruzioni al modello
    messages_for_ollama = [
        {"role": "system", "content": prompt}
    ]

    # --- Step 3: Chiama Ollama per la risposta ---
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=messages_for_ollama,
            stream=False  # Per ora teniamolo semplice senza streaming
        )
        return response['message']['content']
    except Exception as e:
        print(f"ERRORE: Impossibile contattare Ollama: {e}")
        return "Scusa, non riesco a contattare il motore AI al momento. Assicurati che Ollama sia in esecuzione."