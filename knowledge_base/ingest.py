import os
import sys
from pathlib import Path
from typing import List

# Aggiungiamo la root del progetto al path per futuri import
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from pypdf import PdfReader
except ImportError:
    print("ERRORE: La libreria 'pypdf' non è installata. Esegui: pip install pypdf")
    sys.exit(1)

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    print("ERRORE: La libreria 'langchain_text_splitters' non è installata. Esegui: pip install langchain-text-splitters")
    sys.exit(1)

try:
    # IMPORT PER L'INDICIZZAZIONE (CORRETTI)
    from langchain_community.vectorstores import Chroma
    from langchain_ollama import OllamaEmbeddings # <-- IMPORT AGGIORNATO
    print("INFO: Librerie per il Vector Store importate correttamente.")
except ImportError:
    print("ERRORE: Mancano delle librerie fondamentali per il Vector Store.")
    print("Esegui questo comando nel tuo terminale con l'ambiente virtuale attivo:")
    print("pip install -U langchain-community langchain-chroma langchain-ollama")
    sys.exit(1)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Apre un file PDF e ne estrae tutto il testo contenuto.
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Il file specificato non esiste: {pdf_path}")

    print(f"--- Inizio estrazione testo da: {pdf_path.name} ---")
    reader = PdfReader(pdf_path)
    text_parts = []
    for i, page in enumerate(reader.pages):
        extracted_text = page.extract_text()
        if extracted_text:
            text_parts.append(extracted_text)
    print(f"  > Lette {len(reader.pages)} pagine.")
    return "\n".join(text_parts)


def chunk_text(full_text: str) -> List[str]:
    """
    Prende un testo lungo e lo divide in chunk (pezzi) più piccoli.
    """
    print("--- Inizio suddivisione del testo in chunk ---")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
    )
    chunks = text_splitter.split_text(full_text)
    print(f"--- Testo suddiviso in {len(chunks)} chunk. ---")
    return chunks

def create_and_store_embeddings(chunks: List[str], persist_directory: str) -> None:
    """
    Crea gli embedding per ogni chunk e li salva nel Vector Store.
    """
    print("--- Inizio creazione degli embedding e del Vector Store ---")
    
    # Assicurati di aver scaricato il modello: ollama pull nomic-embed-text
    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    # Creiamo il Vector Store (la nostra biblioteca indicizzata)
    vectorstore = Chroma.from_texts(
        texts=chunks, 
        embedding=embeddings,
        persist_directory=persist_directory
    )
    
    print(f"--- Vector Store creato e salvato con successo nella cartella: '{persist_directory}' ---")


# --- Esecuzione principale dello script ---
if __name__ == "__main__":
    DOCS_DIR = Path(__file__).parent / "documents"
    VECTORSTORE_DIR = str(Path(__file__).parent / "vectorstore")

    # Controlliamo se la cartella dei documenti esiste
    if not DOCS_DIR.is_dir():
        print(f"ERRORE: La cartella dei documenti non è stata trovata in: {DOCS_DIR}")
        print("Crea la cartella 'documents' dentro 'knowledge_base' e inserisci i tuoi file PDF.")
        sys.exit(1)

    # Troviamo tutti i file PDF nella cartella
    pdf_files = list(DOCS_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"ATTENZIONE: Nessun file PDF trovato nella cartella {DOCS_DIR}.")
        sys.exit(0)

    print(f"Trovati {len(pdf_files)} file PDF da processare.")
    
    # Raccogliamo i chunk da TUTTI i documenti prima di creare il Vector Store
    all_chunks = []
    
    for pdf_path in pdf_files:
        try:
            # Step 1 & 2 per ogni file
            contenuto_testuale = extract_text_from_pdf(pdf_path)
            lista_di_chunk = chunk_text(contenuto_testuale)
            all_chunks.extend(lista_di_chunk)
            print(f"File '{pdf_path.name}' processato con successo.\n")
        except Exception as e:
            print(f"ATTENZIONE: Impossibile processare il file '{pdf_path.name}'. Errore: {e}\n")

    # Step 3: Creiamo il Vector Store una sola volta con i chunk di tutti i file
    if all_chunks:
        create_and_store_embeddings(all_chunks, VECTORSTORE_DIR)
        
        print("\n\n*** PROCESSO COMPLETATO ***")
        print("La tua base di conoscenza è stata creata/aggiornata con tutti i documenti trovati.")
        print(f"Ora la cartella '{VECTORSTORE_DIR}' contiene l'intelligenza combinata di {len(pdf_files)} documenti.")
    else:
        print("Nessun contenuto testuale è stato estratto, il Vector Store non è stato aggiornato.")