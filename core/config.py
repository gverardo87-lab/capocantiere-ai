from __future__ import annotations
import os
import sys
from pathlib import Path

# Import custom per aggiungere la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # dotenv non è installato, procediamo comunque
# --- CONFIGURAZIONE DEL DATABASE E DELLA CARTELLA DATI ---


PROJECT_ROOT = Path(__file__).resolve().parents[1] # Due livelli sopra questo file
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data")) 
DATA_DIR.mkdir(parents=True, exist_ok=True) # Crea la cartella se non esiste
DB_PATH = str(Path(os.getenv("DB_PATH", DATA_DIR / "capocantiere.db")).resolve()) 

# --- VARIABILI PER OLLAMA (DEFINITE UNA SOLA VOLTA) ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2:7b-instruct-q4_K_M")
