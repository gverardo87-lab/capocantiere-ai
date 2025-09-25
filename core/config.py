# core/config.py (Versione Definitiva e Centralizzata)

import os
from pathlib import Path
from dotenv import load_dotenv

# Carica le variabili d'ambiente da un file .env se presente.
# Questo permette di personalizzare le impostazioni senza modificare il codice.
load_dotenv()

# --- 1. PERCORSI FONDAMENTALI DEL PROGETTO ---
# La radice del progetto è la cartella che contiene 'core', 'server', etc.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Cartella principale per tutti i dati persistenti (database, archivi, etc.)
DATA_DIR = PROJECT_ROOT / os.getenv("DATA_DIR", "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)


# --- 2. CONFIGURAZIONE DATABASE ---
# Percorso del database per le presenze degli operai.
DB_PRESENCE_PATH = DATA_DIR / "capocantiere.db"

# Percorso del database per i dati del cronoprogramma.
DB_SCHEDULE_PATH = DATA_DIR / "schedule.db"


# --- 3. CONFIGURAZIONE KNOWLEDGE BASE E RAG ---
# Cartella che contiene i documenti e il vector store.
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"

# "Fonte della Verità": la cartella dove l'ufficio tecnico inserisce i PDF.
# Sia il DocumentManager che l'ingestione leggeranno da qui.
DOCUMENTS_DIR = KNOWLEDGE_BASE_DIR / "documents"

# Cartella dove ChromaDB salva gli embedding vettoriali.
VECTORSTORE_DIR = KNOWLEDGE_BASE_DIR / "vectorstore"


# --- 4. CONFIGURAZIONE MODELLI OLLAMA E AI ---
# Indirizzo del server Ollama in esecuzione.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Il modello LLM principale per la generazione di risposte (RAG, Chat).
# 'q4_K_M' è il miglior compromesso tra velocità e precisione.
MAIN_LLM_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b-instruct-q4_K_M")

# Modello specializzato per creare gli embedding (vettori numerici) dei documenti.
EMBEDDING_MODEL = "nomic-embed-text"

# Modello Cross-Encoder per il re-ranking dei risultati di ricerca.
# È cruciale per la precisione del sistema RAG.
CROSS_ENCODER_MODEL = 'cross-encoder/ms-marco-MiniLM-L-6-v2'