# core/knowledge_chain.py (Versione Corretta e Robusta)

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
MAIN_LLM_MODEL = "llama3:8b-instruct-q2_K"

@st.cache_resource
def get_knowledge_chain():
    print("--- Caricamento della Knowledge Chain in corso... (avviene solo una volta) ---")
    if not os.path.exists(VECTORSTORE_DIR):
        st.warning(f"Database della conoscenza non trovato. Esegui 'knowledge_base/ingest.py' per crearlo.")
        return None, None
    try:
        embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
        vectorstore = Chroma(persist_directory=VECTORSTORE_DIR, embedding_function=embeddings)
        llm = OllamaLLM(model=MAIN_LLM_MODEL)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        print("--- Knowledge Chain caricata con successo. ---")
        return retriever, llm
    except Exception as e:
        st.error(f"Errore durante l'inizializzazione della Knowledge Chain: {e}")
        return None, None

def get_expert_response(user_query: str) -> Dict[str, Any]:
    retriever, llm = get_knowledge_chain()
    error_response = {"answer": "Errore: La base di conoscenza non è stata caricata.", "sources": []}
    if retriever is None or llm is None:
        return error_response
    try:
        docs = retriever.invoke(user_query)
    except Exception as e:
        return {"answer": f"Errore durante la ricerca nella base di conoscenza: {e}", "sources": []}
    if not docs:
        return {"answer": "Non ho trovato informazioni pertinenti.", "sources": []}

    sources = []
    unique_sources = set()
    for doc in docs:
        source_name = doc.metadata.get('source', 'Fonte Sconosciuta')
        page_num = doc.metadata.get('page', '?')
        source_id = f"{source_name}, pag. {page_num}"
        if source_id not in unique_sources:
            unique_sources.add(source_id)
            sources.append({"source": source_name, "page": page_num})

    context = "\n\n---\n\n".join([doc.page_content for doc in docs])

    # La logica "Refine" rimane invariata
    try:
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
        intermediate_answer = llm.invoke(initial_prompt)

        for i, doc in enumerate(docs[1:]):
            refine_context = doc.page_content
            refine_prompt = f"""
            RISPOSTA ESISTENTE:
            {intermediate_answer}
            ---
            NUOVE INFORMAZIONI DAL CONTESTO AGGIUNTIVO:
            {refine_context}
            ---
            Basandoti sulla risposta esistente e sulle nuove informazioni, perfezionala e arricchiscila.
            Se le nuove informazioni non aggiungono nulla di rilevante, mantieni la risposta esistente.
            Collega le informazioni in modo logico e coerente.
            RISPOSTA RAFFINATA:
            """
            intermediate_answer = llm.invoke(refine_prompt)
        final_answer = intermediate_answer
    except Exception as e:
        return {"answer": f"Errore durante la generazione della risposta: {e}", "sources": sources}
    return {"answer": final_answer, "sources": sources}