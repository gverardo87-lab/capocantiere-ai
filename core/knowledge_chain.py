# core/knowledge_chain.py

import os
import sys
from pathlib import Path

# Aggiungiamo la root del progetto al path per importare da altre cartelle
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_ollama.llms import OllamaLLM
import streamlit as st

# --- CONFIGURAZIONE ---
CURRENT_DIR = Path(__file__).parent
VECTORSTORE_DIR = str(CURRENT_DIR.parent / "knowledge_base/vectorstore")
EMBEDDING_MODEL = "nomic-embed-text"
MAIN_LLM_MODEL = "llama3"

@st.cache_resource
def get_knowledge_chain():
    """
    Carica tutti i componenti della pipeline RAG e li mette in cache.
    Ritorna un "retriever" e un "llm" pronti all'uso.
    """
    print("--- Caricamento della Knowledge Chain in corso... (avviene solo una volta) ---")
    if not os.path.exists(VECTORSTORE_DIR):
        st.warning(f"Database della conoscenza non trovato. Esegui 'knowledge_base/ingest.py' per crearlo.")
        return None, None

    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = Chroma(persist_directory=VECTORSTORE_DIR, embedding_function=embeddings)
    llm = OllamaLLM(model=MAIN_LLM_MODEL)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    print("--- Knowledge Chain caricata con successo. ---")
    return retriever, llm

def get_expert_response(user_query: str) -> str:
    """
    Funzione principale che prende la domanda dell'utente ed esegue la pipeline RAG.
    """
    retriever, llm = get_knowledge_chain()
    
    if retriever is None or llm is None:
        return "Errore: La base di conoscenza non è stata caricata correttamente."

    docs = retriever.invoke(user_query)

    if not docs:
        return "Non ho trovato informazioni pertinenti nei documenti a mia disposizione per rispondere a questa domanda."

    context = "\n\n---\n\n".join([doc.page_content for doc in docs])

    template = f"""
    Sei un assistente tecnico esperto. Il tuo compito è rispondere in modo chiaro e preciso alla domanda dell'utente.
    Usa un tono professionale e vai dritto al punto.
    Rispondi basandoti ESCLUSIVAMENTE sul contesto fornito qui sotto.
    Se le informazioni non sono presenti nel contesto, rispondi "Non ho trovato informazioni sufficienti nei documenti a mia disposizione."
    Non usare mai le tue conoscenze pregresse.

    CONTESTO FORNITO:
    {context}

    DOMANDA DELL'UTENTE: {user_query}

    RISPOSTA PRECISA E CONCISA:
    """
    
    response = llm.invoke(template)
    return response