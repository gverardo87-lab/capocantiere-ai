# 🏗️ CapoCantiere AI

CapoCantiere AI is a web-based application designed to assist shipyard managers in handling personnel and project data. It leverages AI to extract information from uploaded documents, providing a centralized dashboard for monitoring work hours and an AI assistant to answer questions about your data.

## ✨ Features

*   **📄 Document Upload:** Upload various document types (`.pdf`, `.docx`, `.xlsx`, `.csv`).
*   **🤖 AI-Powered Data Extraction:** Automatically extracts key information from documents. Specialized parser for CSV timesheets.
*   **📊 Interactive Dashboard:** View and filter timesheet data by date, worker, and project.
*   **💬 AI Assistant:** A chat interface to ask natural language questions about your project data.
*   **🗂️ Centralized Data Management:** Master records for personnel and projects (commesse).

## 🚀 How to Run

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up the local LLM (Ollama):**
    This application requires Ollama to be running with a suitable model (e.g., `llama3`). Please follow the instructions on the [Ollama website](https://ollama.com/) to install it and pull a model.

5.  **Run the Streamlit application:**
    ```bash
    streamlit run server/app.py
    ```

The application will then be available in your web browser.
