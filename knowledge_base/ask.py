import os
import sys
from pathlib import Path

# Aggiungiamo la root del progetto al path per futuri import
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from langchain_community.vectorstores import Chroma
    from langchain_ollama import OllamaEmbeddings
    from langchain_ollama.llms import OllamaLLM
    print("INFO: Librerie LangChain importate correttamente.")
except ImportError:
    print("ERRORE: Mancano delle librerie LangChain.")
    print("Esegui: pip install -U langchain-community langchain-chroma langchain-ollama")
    sys.exit(1)

# --- CONFIGURAZIONE ---
VECTORSTORE_DIR = str(Path(__file__).parent / "vectorstore")
EMBEDDING_MODEL = "nomic-embed-text"
MAIN_LLM_MODEL = "llama3"

# Controlliamo se il Vector Store esiste
if not os.path.exists(VECTORSTORE_DIR):
    print(f"ERRORE: La cartella del Vector Store non è stata trovata in: {VECTORSTORE_DIR}")
    print("Assicurati di aver prima eseguito lo script 'ingest.py' con successo.")
    sys.exit(1)

# --- CARICAMENTO DEI COMPONENTI DELLA PIPELINE RAG ---

print("--- 1. Caricamento del modello di Embedding ---")
embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

print(f"--- 2. Caricamento del Vector Store da '{VECTORSTORE_DIR}' ---")
vectorstore = Chroma(persist_directory=VECTORSTORE_DIR, embedding_function=embeddings)

print("--- 3. Inizializzazione del Modello LLM Principale ---")
llm = OllamaLLM(model=MAIN_LLM_MODEL)

# Creiamo il "retriever", specializzato per le ricerche nel Vector Store
# k=5 significa che cercherà i 5 chunk più pertinenti, per dare più contesto
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

def ask_question(query: str) -> str:
    """
    Funzione principale che esegue la pipeline RAG.
    """
    print("\n--- Inizio ricerca dei documenti pertinenti... ---")
    docs = retriever.invoke(query)
    
    # Se la ricerca non produce risultati, lo diciamo subito.
    if not docs:
        return "Non ho trovato informazioni pertinenti nei documenti a mia disposizione per rispondere a questa domanda."

    context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    
    print("--- Documenti trovati. Costruzione del prompt per l'LLM... ---")

    # MODIFICA: Il template ora è generico
    template = f"""
    Sei un assistente tecnico esperto. Il tuo compito è rispondere in modo chiaro e preciso alla domanda dell'utente.
    Usa un tono professionale e vai dritto al punto.
    Rispondi basandoti ESCLUSIVAMENTE sul contesto fornito qui sotto.
    Se le informazioni non sono presenti nel contesto, rispondi "Non ho trovato informazioni sufficienti nei documenti a mia disposizione per rispondere a questa domanda."
    Non usare mai le tue conoscenze pregresse.

    CONTESTO FORNITO:
    {context}

    DOMANDA DELL'UTENTE: {query}

    RISPOSTA PRECISA E CONCISA:
    """
    
    print("--- Prompt inviato all'LLM. Attendo la risposta... ---")
    
    response = llm.invoke(template)
    return response

# --- Esecuzione principale dello script ---
if __name__ == "__main__":
    print("\n\n*** Assistente Tecnico da Documentazione Attivo ***")
    while True:
        user_query = input("\nInserisci la tua domanda (o scrivi 'esci' per terminare): \n> ")
        if user_query.lower() == 'esci':
            break
        if not user_query.strip():
            continue
            
        answer = ask_question(user_query)
        
        print("\n*** RISPOSTA DELL'ESPERTO ***")
        print(answer)