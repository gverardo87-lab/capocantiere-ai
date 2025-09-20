from __future__ import annotations

import os
from pathlib import Path


# Carica le variabili dal file .env, se esiste
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Definiamo la radice del progetto una sola volta
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Definiamo la cartella dei dati, usando .env o un valore di default
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Definiamo il percorso del database, usando .env o un valore di default
DB_PATH = str(Path(os.getenv("DB_PATH", DATA_DIR / "capocantiere.db")).resolve())

# ... (variabili esistenti)
DB_PATH = str(Path(os.getenv("DB_PATH", DATA_DIR / "capocantiere.db")).resolve())

# --- NUOVE VARIABILI PER OLLAMA ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2:7b-instruct-q4_K_M")