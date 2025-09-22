# 🏗️ CapoCantiere AI

**CapoCantiere AI** è un'applicazione web avanzata progettata per rivoluzionare la gestione dei dati in cantieri navali e contesti industriali. Sfrutta la potenza dei Large Language Models (LLM) locali attraverso Ollama per offrire due funzionalità principali:

1.  **Assistente Dati:** Un'interfaccia chat per analizzare e interrogare in linguaggio naturale i dati strutturati provenienti da rapportini ore.
2.  **Esperto Tecnico (RAG):** Un potente assistente basato su Retrieval-Augmented Generation (RAG) che "studia" documentazione tecnica (PDF, manuali, etc.) per fornire risposte precise e contestualizzate, citando le fonti esatte.

L'applicazione è costruita con Streamlit e pensata per essere modulare e scalabile.

## ✨ Funzionalità Principali

* **Architettura Multi-Pagina:** Interfaccia utente pulita e organizzata con pagine dedicate per ogni funzionalità.
* **Ingestione Documenti Dinamica:** Aggiungi nuova conoscenza all'Esperto Tecnico semplicemente aggiungendo file PDF in una cartella.
* **Parsing Intelligente di CSV:** Estrazione automatica dei dati dai rapportini ore.
* **Visualizzazione Dati Avanzata:** Dashboard interattiva con filtri, tabelle aggregate e metriche in tempo reale.
* **Doppio Assistente AI:**
    * **Assistente Dati:** Interroga i dati di cantiere (`ore`, `commesse`, `operai`).
    * **Esperto Tecnico:** Risponde a domande complesse basandosi su una knowledge base di documenti, con citazione delle fonti per la massima affidabilità.
* **100% Locale e Privato:** Tutta l'elaborazione AI avviene in locale tramite Ollama, garantendo la totale privacy dei dati.

## 🏛️ Architettura del Progetto

Il progetto è organizzato in moduli con responsabilità specifiche per garantire manutenibilità e scalabilità:

* **`/core`**: Contiene la logica di business principale.
    * `db.py`: Gestione del database SQLite.
    * `chat_logic.py`: Logica per l'assistente che interroga il database.
    * `knowledge_chain.py`: Contiene la pipeline RAG per l'Esperto Tecnico.
    * `logic.py`: Funzioni di calcolo (es. straordinari).
* **`/knowledge_base`**: Modulo per la gestione della base di conoscenza.
    * `documents/`: Cartella dove inserire i PDF da far "studiare" all'AI.
    * `vectorstore/`: Database vettoriale (ChromaDB) generato automaticamente.
    * `ingest.py`: Script per processare i documenti e creare il vector store.
    * `ask.py`: Script di utility per testare l'Esperto Tecnico da riga di comando.
* **`/server`**: Contiene l'applicazione web Streamlit.
    * `app.py`: La Home Page dell'applicazione.
    * `pages/`: Contiene ogni pagina dell'applicazione come file separato.
* **`/tools`**: Utility per l'estrazione dati da vari formati di file.

## 🚀 Installazione e Avvio

Segui questi passaggi per configurare e avviare il progetto in locale.

### 1. Prerequisiti

Assicurati di avere installato:
* [Python 3.9+](https://www.python.org/)
* [Git](https://git-scm.com/)
* [Ollama](https://ollama.com/): Segui le istruzioni sul sito ufficiale per installarlo.

### 2. Clona il Repository

```bash
git clone <url-del-tuo-repository>
cd capocantiere-ai
```

### 3. Configura l'Ambiente Python

Crea e attiva un ambiente virtuale per isolare le dipendenze.

```bash
# Crea l'ambiente virtuale
python -m venv venv

# Attiva l'ambiente (Windows)
.\venv\Scripts\activate

# Attiva l'ambiente (macOS/Linux)
# source venv/bin/activate
```

### 4. Installa le Dipendenze

Installa tutte le librerie necessarie con un solo comando.

```bash
pip install -r requirements.txt
```

### 5. Configura Ollama

L'applicazione necessita di due modelli per funzionare correttamente. Scaricali tramite Ollama dal tuo terminale:

```bash
# Modello principale per il ragionamento e la chat
ollama pull llama3

# Modello specializzato per creare gli "embeddings" (l'indice della conoscenza)
ollama pull nomic-embed-text