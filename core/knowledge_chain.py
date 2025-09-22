# core/knowledge_chain.py (Versione con Logica "Refine")

import os
import sys
from pathlib import Path
from typing import Dict, Any

# Aggiungiamo la root del progetto al path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_ollama.llms import OllamaLLM
import streamlit as st

# --- CONFIGURAZIONE (invariata) ---
CURRENT_DIR = Path(__file__).parent
VECTORSTORE_DIR = str(CURRENT_DIR.parent / "knowledge_base/vectorstore")
EMBEDDING_MODEL = "nomic-embed-text"
MAIN_LLM_MODEL = "llama3"

@st.cache_resource
def get_knowledge_chain():
    print("--- Caricamento della Knowledge Chain in corso... (avviene solo una volta) ---")
    if not os.path.exists(VECTORSTORE_DIR):
        st.warning(f"Database della conoscenza non trovato. Esegui 'knowledge_base/ingest.py' per crearlo.")
        return None, None

    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = Chroma(persist_directory=VECTORSTORE_DIR, embedding_function=embeddings)
    llm = OllamaLLM(model=MAIN_LLM_MODEL)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5}) # Aumentiamo a 5 per avere più contesto
    print("--- Knowledge Chain caricata con successo. ---")
    return retriever, llm

def get_expert_response(user_query: str) -> Dict[str, Any]:
    """
    MODIFICATO: Ora la funzione usa una catena di "Refine" per risposte più complete.
    """
    retriever, llm = get_knowledge_chain()
    
    error_response = {"answer": "Errore: La base di conoscenza non è stata caricata.", "sources": []}
    if retriever is None or llm is None: return error_response

    # Step 1: Recupero dei documenti (come prima)
    docs = retriever.invoke(user_query)
    if not docs: return {"answer": "Non ho trovato informazioni pertinenti.", "sources": []}

    # Estraiamo le fonti per mostrarle all'utente
    sources = []
    unique_sources = set()
    for doc in docs:
        source_id = f"{doc.metadata['source']}, pag. {doc.metadata['page']}"
        if source_id not in unique_sources:
            unique_sources.add(source_id)
            sources.append({"source": doc.metadata['source'], "page": doc.metadata['page']})

    # --- NUOVA LOGICA "REFINE" ---
    
    # Step 2a: Creiamo una bozza di risposta usando solo il primo documento
    initial_context = docs[0].page_content
    initial_prompt = f"""
    CONTESTO:
    {initial_context}
    ---
    DOMANDA: {user_query}
    ---
    Basandoti ESCLUSIVAMENTE sul contesto fornito, fornisci una risposta iniziale e dettagliata.
    RISPOSTA INIZIALE:
    """
    print("--- Genero la risposta iniziale... ---")
    intermediate_answer = llm.invoke(initial_prompt)

    # Step 2b: Cicliamo sui documenti rimanenti per "raffinare" la risposta
    for i, doc in enumerate(docs[1:]):
        print(f"--- Ciclo di raffinamento {i+1}/{len(docs)-1}... ---")
        refine_context = doc.page_content
        refine_prompt = f"""
        RISPOSTA ESISTENTE:
        {intermediate_answer}
        ---
        NUOVE INFORMAZIONI DAL CONTESTO AGGIUNTIVO:
        {refine_context}
        ---
        Basandoti sulla risposta esistente e sulle nuove informazioni, perfezionala e arricchiscila.
        Se le nuove informazioni contraddicono o non aggiungono nulla di rilevante, mantieni la risposta esistente.
        Collega le informazioni in modo logico e coerente.
        RISPOSTA RAFFINATA:
        """
        intermediate_answer = llm.invoke(refine_prompt)

    # La risposta finale è l'ultima risposta raffinata
    final_answer = intermediate_answer
    
    return {"answer": final_answer, "sources": sources}