# knowledge_base/ingest.py (Versione con Metadati)

import os
import sys
from pathlib import Path
from typing import List

# Aggiungiamo la root del progetto al path per futuri import
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    # CAMBIO LIBRERIA: PyMuPDF è più robusto per estrarre metadati come il numero di pagina
    import fitz  # PyMuPDF
    print("INFO: Libreria 'PyMuPDF' importata correttamente.")
except ImportError:
    print("ERRORE: La libreria 'PyMuPDF' non è installata.")
    print("È un lettore PDF più potente. Esegui: pip install PyMuPDF")
    sys.exit(1)

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    print("ERRORE: Esegui: pip install langchain-text-splitters")
    sys.exit(1)

try:
    from langchain_community.vectorstores import Chroma
    from langchain_ollama import OllamaEmbeddings
    # NUOVO IMPORT: La classe Document per gestire i metadati
    from langchain_core.documents import Document
    print("INFO: Librerie per il Vector Store importate correttamente.")
except ImportError:
    print("ERRORE: Esegui: pip install -U langchain-community langchain-chroma langchain-ollama langchain-core")
    sys.exit(1)


def extract_pages_from_pdf(pdf_path: Path) -> List[Document]:
    """
    MODIFICATO: Apre un PDF e crea un oggetto Document per ogni pagina,
    conservando il testo e i metadati (nome file, numero pagina).
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Il file specificato non esiste: {pdf_path}")

    print(f"--- Inizio estrazione pagine da: {pdf_path.name} ---")
    doc = fitz.open(pdf_path)  # Apre il file con PyMuPDF
    
    documents = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text:
            # Creiamo un oggetto Document per ogni pagina
            doc_obj = Document(
                page_content=text,
                metadata={
                    "source": pdf_path.name,
                    "page": page_num + 1  # I numeri di pagina partono da 1 per l'utente
                }
            )
            documents.append(doc_obj)
            
    print(f"  > Estratte {len(documents)} pagine con contenuto testuale.")
    return documents


def split_documents(documents: List[Document]) -> List[Document]:
    """
    MODIFICATO: Prende una lista di Document (pagine) e li divide in chunk più piccoli,
    mantenendo i metadati originali.
    """
    print("--- Inizio suddivisione dei documenti in chunk ---")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"--- Documenti suddivisi in {len(chunks)} chunk totali. ---")
    return chunks


def create_and_store_embeddings(chunks: List[Document], persist_directory: str) -> None:
    """
    MODIFICATO: Salva nel Vector Store i chunk, che ora contengono anche i metadati.
    """
    print("--- Inizio creazione degli embedding e del Vector Store ---")
    
    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    # Usiamo from_documents invece di from_texts. Questo salva automaticamente i metadati.
    vectorstore = Chroma.from_documents(
        documents=chunks, 
        embedding=embeddings,
        persist_directory=persist_directory
    )
    
    print(f"--- Vector Store creato e salvato con successo nella cartella: '{persist_directory}' ---")


# --- Esecuzione principale (leggermente modificata) ---
if __name__ == "__main__":
    DOCS_DIR = Path(__file__).parent / "documents"
    VECTORSTORE_DIR = str(Path(__file__).parent / "vectorstore")

    if not DOCS_DIR.is_dir():
        print(f"ERRORE: La cartella dei documenti non è stata trovata in: {DOCS_DIR}")
        sys.exit(1)

    pdf_files = list(DOCS_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"ATTENZIONE: Nessun file PDF trovato nella cartella {DOCS_DIR}.")
        sys.exit(0)

    print(f"Trovati {len(pdf_files)} file PDF da processare.")
    
    all_chunks = []
    for pdf_path in pdf_files:
        try:
            # Ora estraiamo una lista di "Document" per ogni file
            pages_as_docs = extract_pages_from_pdf(pdf_path)
            # E dividiamo questi "Document" in chunk più piccoli
            chunks = split_documents(pages_as_docs)
            all_chunks.extend(chunks)
            print(f"File '{pdf_path.name}' processato con successo.\n")
        except Exception as e:
            print(f"ATTENZIONE: Impossibile processare il file '{pdf_path.name}'. Errore: {e}\n")

    if all_chunks:
        create_and_store_embeddings(all_chunks, VECTORSTORE_DIR)
        print("\n\n*** PROCESSO COMPLETATO ***")
        print("La tua base di conoscenza è stata creata/aggiornata con metadati.")
    else:
        print("Nessun contenuto testuale è stato estratto.")