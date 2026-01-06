# 🏗️ CapoCantiere AI 2.0
## **The Future of Naval Shipyard Management**

[![Status](https://img.shields.io/badge/Status-Production%20Ready-green)]()
[![Tech Stack](https://img.shields.io/badge/Stack-Streamlit%20%7C%20Python%20%7C%20SQLite-blue)]()
[![AI Engine](https://img.shields.io/badge/AI-Ollama%20%7C%20Llama3%20%7C%20RAG-purple)]()
[![License](https://img.shields.io/badge/License-Proprietary-orange)]()

> **"Unire la precisione dell'ERP con l'intelligenza predittiva dell'AI per eliminare le inefficienze operative nei cantieri navali."**

---

## 🚀 **Executive Summary**

**CapoCantiere AI** è una piattaforma *Vertical SaaS* progettata specificamente per le esigenze uniche della cantieristica navale. Risolve il problema critico della **discrepanza tra pianificazione (Gantt) e realtà operativa (Cantiere)**.

A differenza dei gestionali generici, CapoCantiere integra:
1.  **AI Generativa Locale**: Per interrogare manuali tecnici e normative in secondi (RAG).
2.  **Algoritmi Predittivi**: Per anticipare ritardi e colli di bottiglia nel cronoprogramma.
3.  **Psicologia Operativa**: Strumenti di stampa e reportistica studiati per ridurre le contestazioni con la forza lavoro.

---

## 💎 **Core Features**

### **1. Pianificazione Intelligente & HR**
* **Logic-Driven Shifts**: Gestione complessa di turni (Giorno/Notte/Sera) con controllo automatico dei protocolli di riposo.
* **Smart Merge Technology**: Visualizzazione intelligente dei turni notturni (es. 20:00-06:00 uniti visivamente).
* **Visual Badging**: Rilevamento automatico dei cambi di ritmo circadiano (es. passaggio Giorno ➔ Notte) per monitorare lo stress operativo.

### **2. Controllo di Gestione ("Modello Marsiglia")**
* **Real-Time Margin Audit**: Calcolo istantaneo del margine operativo giornaliero per squadra (*Costo Vivo* vs *Tariffa Riconosciuta*).
* **Financial Alerting**: Notifiche automatiche per scostamenti negativi (>5%).

### **3. Workflow Intelligence (AI)**
* **BottleNeck Detection**: L'AI analizza il cronoprogramma e incrocia i dati con la capacità produttiva per predire ritardi futuri.
* **Naval Templates**: Libreria precaricata di cicli di lavoro navali (es. *Montaggio Scafo*, *Fuori Apparato Motore*).

### **4. Knowledge Base Attiva (RAG)**
* **Expert Technical Chat**: Assistente virtuale addestrato su PDF tecnici (normative, schemi, datasheet) con citazione delle fonti.
* **Privacy-First**: Utilizza LLM locali (Ollama/Llama3) garantendo che i dati sensibili non lascino mai il server aziendale.

---

## 📂 **Mappa dei Moduli (Sitemap)**

L'applicazione è strutturata in moduli verticali accessibili via sidebar:

### **📊 Area Direzionale**
* **`01_Reportistica.py`**: Dashboard KPI finanziari, margini e analisi trend.
* **`04_Cronoprogramma.py`**: Visualizzazione Gantt interattiva e importazione Excel.
* **`05_Workflow_Analysis.py`**: Motore AI per l'analisi predittiva dei processi.

### **🛠️ Area Operativa**
* **`10_Pianificazione_Turni.py`**: Griglia principale per l'assegnazione turni (Drag & Drop).
* **`11_Anagrafica.py`**: Gestione personale, costi orari, livelli skill e scadenze certificati.
* **`12_Gestione_Squadre.py`**: Composizione dinamica dei team di lavoro.
* **`13_Control_Room_Ore.py`**: Pannello di verifica e validazione grezza delle presenze.
* **`14_Riepilogo_Calendario.py`**: Vista a calendario (Settimanale/Mensile) per l'allocazione risorse.
* **`15_Stampe_Operative.py`**: Generatore di cedolini e fogli firma "Anti-Contestazione" (Dark Mode Compatible).

### **🧠 Area Intelligence & Supporto**
* **`02_Expert_Chat_Enhanced.py`**: Interfaccia Chat RAG per interrogare la documentazione tecnica.
* **`03_Esperto_Tecnico.py`**: Modulo legacy per query specifiche (in fase di merge).
* **`06_Document_Explorer.py`**: Gestione file PDF e stato dell'indicizzazione vettoriale.

### **🌤️ Moduli Ambientali**
* **`07_Meteo_Cantiere.py`**: Previsioni operative localizzate per pianificazione outdoor.
* **`08_Bollettino_Mare.py`**: Dati specifici (onda, vento) per operazioni in bacino o movimentazioni.

---

## 🏗️ **Architettura Tecnica**

Il progetto adotta un'architettura **Service-Oriented** modulare, pronta per la scalabilità.

```text
/capocantiere-ai-2.0
├── core/                       # BACKEND & BUSINESS LOGIC
│   ├── shift_service.py        # Gestore Turni, Validazione e Calcoli
│   ├── crm_db.py               # Data Access Layer (SQLite - Dati Operativi)
│   ├── schedule_db.py          # Data Access Layer (SQLite - Cronoprogramma)
│   ├── workflow_engine.py      # Motore AI Predittivo
│   ├── knowledge_chain.py      # Motore RAG (LangChain + ChromaDB)
│   └── weather_api.py          # Integrazione OpenWeatherMap
│
├── server/                     # FRONTEND (Streamlit)
│   ├── app.py                  # Entry Point & Navigation
│   └── pages/                  # Moduli Applicativi (Vedi Sitemap)
│
├── data/                       # PERSISTENCE
│   ├── crm.db                  # Database Relazionale Operai/Turni
│   └── schedule.db             # Database Cronoprogramma
│
└── knowledge_base/             # AI MEMORY
    ├── chroma_db/              # Vector Store
    └── documents/              # PDF Source Files
⚙️ Installazione Rapida (Dev)
Prerequisiti
Python 3.9+

Ollama (installato e running con ollama serve).

Modello AI: ollama pull llama3 (o mistral).

Setup
Clona il repo:

Bash

git clone [https://github.com/tuo-org/capocantiere-ai.git](https://github.com/tuo-org/capocantiere-ai.git)
cd capocantiere-ai
Virtual Env:

Bash

python -m venv venv
source venv/bin/activate  # o .\venv\Scripts\activate su Windows
Installa Dipendenze:

Bash

pip install -r requirements.txt
Avvia:

Bash

streamlit run server/app.py
🔮 Roadmap & Vision
[ ] Q3 2026: Migrazione Database a PostgreSQL per supporto multi-utente concorrente.

[ ] Q4 2026: Rilascio App Mobile "Read-Only" per Capisquadra (Tablet).

[ ] Q1 2027: Modulo IoT per integrazione timbrature automatiche.

Contatti & Sviluppo Lead Developer: G. Verardo Versione: 2.1 Stable (Gennaio 2026)