# core/knowledge_chain.py (Versione con Prompt da Ingegnere Esperto)

import os
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import (
    VECTORSTORE_DIR,
    EMBEDDING_MODEL,
    MAIN_LLM_MODEL,
    CROSS_ENCODER_MODEL
)
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_ollama.llms import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain_core.documents import Document
import streamlit as st
from sentence_transformers.cross_encoder import CrossEncoder

@st.cache_resource
def get_knowledge_chain():
    print("--- Caricamento della Knowledge Chain in corso... ---")
    try:
        if not Path(VECTORSTORE_DIR).is_dir():
            st.error(f"Database della conoscenza non trovato in '{VECTORSTORE_DIR}'.")
            st.warning("Azione richiesta: Esegui lo script 'knowledge_base/ingest.py' dal terminale.")
            return None, None
            
        embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
        vectorstore = Chroma(persist_directory=str(VECTORSTORE_DIR), embedding_function=embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
        
        # Aumentiamo leggermente la temperatura per permettere al modello di essere più "eloquente"
        llm = OllamaLLM(model=MAIN_LLM_MODEL, temperature=0.2)
        
        print("--- Knowledge Chain caricata. ---")
        return retriever, llm
    except Exception as e:
        st.error(f"Errore durante l'inizializzazione della Knowledge Chain: {e}")
        return None, None

@st.cache_resource
def get_cross_encoder():
    print("--- Caricamento del Cross-Encoder per il re-ranking... ---")
    try:
        encoder = CrossEncoder(CROSS_ENCODER_MODEL)
        print("--- Cross-Encoder caricato. ---")
        return encoder
    except Exception as e:
        st.error(f"Errore durante il caricamento del Cross-Encoder: {e}")
        return None

def rerank_documents(query: str, documents: List[Document], cross_encoder) -> List[Document]:
    if not documents or cross_encoder is None:
        return documents
    
    print(f"--- Riordino di {len(documents)} documenti... ---")
    pairs = [[query, doc.page_content] for doc in documents]
    scores = cross_encoder.predict(pairs)
    
    for i in range(len(documents)):
        documents[i].metadata['relevance_score'] = scores[i]
        
    reranked_docs = sorted(documents, key=lambda x: x.metadata['relevance_score'], reverse=True)
    
    print(f"--- Documenti riordinati. Top score: {reranked_docs[0].metadata['relevance_score']:.2f} ---")
    return reranked_docs[:4]

def get_expert_response(user_query: str) -> Dict[str, Any]:
    retriever, llm = get_knowledge_chain()
    cross_encoder = get_cross_encoder()
    
    error_response = {"answer": "Errore: La base di conoscenza o i modelli non sono stati caricati.", "sources": []}
    if retriever is None or llm is None or cross_encoder is None:
        return error_response

    retrieved_docs = retriever.invoke(user_query)
    if not retrieved_docs:
        return {"answer": "Non ho trovato informazioni pertinenti nei documenti.", "sources": []}

    reranked_docs = rerank_documents(user_query, retrieved_docs, cross_encoder)

    context = "\n\n---\n\n".join([f"Fonte: {doc.metadata['source']}, Pagina: {doc.metadata['page']}\nContenuto: {doc.page_content}" for doc in reranked_docs])
    
    # --- IL NUOVO PROMPT: DA ASSISTENTE A INGEGNERE CAPO ---
    prompt_template = """
    **PERSONA**: Sei un Ingegnere Capo Progetto di un cantiere navale, un massimo esperto con decenni di esperienza. Il tuo compito è fornire una consulenza tecnica dettagliata, chiara e autorevole.

    **OBIETTIVO**: Rispondere alla domanda dell'utente in modo esaustivo, andando oltre la semplice sintesi. Devi analizzare, sintetizzare e spiegare i concetti basandoti sulle informazioni estratte dalla documentazione tecnica fornita.

    **ISTRUZIONI**:
    1.  **Analisi Approfondita**: Leggi attentamente tutto il contesto fornito. Identifica i concetti chiave, le definizioni, le cause, gli effetti e le procedure pertinenti alla domanda.
    2.  **Sintesi e Struttura**: Non limitarti a copiare il testo. Sintetizza e riorganizza le informazioni in una risposta logica e ben strutturata. Usa titoli (es. `### Definizione`), punti elenco e testo in grassetto per evidenziare i punti cruciali.
    3.  **Spiegazione Dettagliata**: Quando presenti un concetto (es. "cricche a freddo"), non solo definirlo, ma spiega il "perché" e il "come" basandoti sul contesto. Fornisci dettagli tecnici rilevanti.
    4.  **Fedeltà al Contesto**: La tua risposta deve essere **interamente supportata** dalle informazioni presenti nel contesto. Se un'informazione non è presente, dichiara esplicitamente: "La documentazione non fornisce dettagli su [argomento specifico]". NON inventare informazioni.
    5.  **Citazioni Puntuali**: Al termine di ogni frase o punto elenco che contiene un'informazione specifica, cita la fonte con il formato `([Nome File], Pag. [Numero])`. È obbligatorio.
    6.  **Tono Autorevole**: Usa un linguaggio professionale, preciso e sicuro, come farebbe un vero esperto del settore.

    **CONTESTO ESTRATTO DALLA DOCUMENTAZIONE TECNICA**:
    {context}

    **DOMANDA DELL'UTENTE**:
    {question}

    **CONSULENZA TECNICA DETTAGLIATA**:
    """
    
    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
    chain = prompt | llm
    
    try:
        final_answer = chain.invoke({"context": context, "question": user_query})
    except Exception as e:
        return {"answer": f"Errore durante la generazione della risposta: {e}", "sources": []}
    
    sources = []
    for doc in reranked_docs:
        sources.append({
            "source": doc.metadata.get('source', 'Sconosciuta'),
            "page": doc.metadata.get('page', '?'),
            "doc_id": doc.metadata.get('doc_id')
        })

    # Le citazioni ora sono generate direttamente nel testo dall'LLM per una maggiore precisione.
    return {"answer": final_answer, "sources": sources}


def generate_response_with_sources(llm, results, query):
    docs_with_context = [res[0] for res in results]
    response_data = get_expert_response(query)
    response = response_data["answer"]
    
    unique_refs = {}
    for doc in docs_with_context:
        ref_id = f"{doc.metadata.get('doc_id')}-{doc.metadata.get('page')}"
        if ref_id not in unique_refs:
            unique_refs[ref_id] = {
                'doc_id': doc.metadata.get('doc_id'),
                'page': doc.metadata.get('page'),
                'content': doc.page_content
            }
    
    return response, list(unique_refs.values())