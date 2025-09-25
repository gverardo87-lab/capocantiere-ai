# knowledge_base/ingest.py (Versione Sincronizzata)

import os
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import fitz
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma
    from langchain_ollama import OllamaEmbeddings
    from langchain_core.documents import Document
    
    # Importiamo la funzione per generare ID consistenti
    from core.document_manager import generate_doc_id
    print("INFO: Librerie importate correttamente.")
except ImportError as e:
    print(f"ERRORE: Manca una libreria: {e}")
    sys.exit(1)


def extract_pages_from_pdf(pdf_path: Path) -> List[Document]:
    """
    Estrae le pagine da un PDF e assegna l'ID corretto ai metadati.
    """
    if not pdf_path.is_file():
        return []

    print(f"--- Estrazione da: {pdf_path.name} ---")
    doc_id = generate_doc_id(pdf_path) # Genera l'ID standard
    
    documents = []
    try:
        with fitz.open(pdf_path) as doc:
            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text:
                    documents.append(Document(
                        page_content=text,
                        metadata={
                            "doc_id": doc_id, # Inseriamo l'ID corretto
                            "source": pdf_path.name,
                            "page": page_num + 1
                        }
                    ))
        print(f"  > Estratte {len(documents)} pagine.")
    except Exception as e:
        print(f"  > ERRORE durante la lettura di {pdf_path.name}: {e}")
    return documents


def split_documents(documents: List[Document]) -> List[Document]:
    """Divide i documenti in chunk, mantenendo i metadati."""
    if not documents:
        return []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    return text_splitter.split_documents(documents)


def create_and_store_embeddings(chunks: List[Document], persist_directory: str):
    """Crea e salva gli embedding nel Vector Store."""
    if not chunks:
        print("ATTENZIONE: Nessun chunk da processare.")
        return
        
    print("--- Inizio creazione del Vector Store ---")
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    vectorstore = Chroma.from_documents(
        documents=chunks, 
        embedding=embeddings,
        persist_directory=persist_directory
    )
    print(f"--- Vector Store creato in: '{persist_directory}' ---")


if __name__ == "__main__":
    DOCS_DIR = Path(__file__).parent / "documents"
    VECTORSTORE_DIR = str(Path(__file__).parent / "vectorstore")

    if not DOCS_DIR.is_dir():
        print(f"ERRORE: La cartella dei documenti non esiste: {DOCS_DIR}")
        sys.exit(1)

    pdf_files = list(DOCS_DIR.rglob("*.pdf"))

    if not pdf_files:
        print(f"ATTENZIONE: Nessun file PDF trovato in {DOCS_DIR}.")
        sys.exit(0)

    print(f"Trovati {len(pdf_files)} file PDF da processare.")
    
    all_chunks = []
    for pdf_path in pdf_files:
        pages_as_docs = extract_pages_from_pdf(pdf_path)
        chunks = split_documents(pages_as_docs)
        all_chunks.extend(chunks)

    create_and_store_embeddings(all_chunks, VECTORSTORE_DIR)
    print("\n\n*** PROCESSO COMPLETATO ***")