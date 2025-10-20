# server/pages/🤖_Expert_Chat_Enhanced.py
import streamlit as st
from pathlib import Path
import fitz # PyMuPDF
import os
import sys

# Aggiungiamo la root del progetto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Importa le funzioni e le classi necessarie
from core.knowledge_chain import get_knowledge_chain, generate_response_with_sources
from core.document_manager import NavalDocumentManager

# Placeholder per SmartNavalRetriever, assumendo che esista e sia importabile
# Se si trova in un altro file, modifica l'import.
try:
    from core.enhanced_knowledge_chain import SmartNavalRetriever
except ImportError:
    class SmartNavalRetriever:
        def __init__(self, retriever, doc_manager):
            self.retriever = retriever
            self.doc_manager = doc_manager
        
        def retrieve_with_context(self, query, k=5):
            # Logica placeholder, dovrai implementarla
            docs = self.retriever.invoke(query)
            
            # Simula il recupero del doc_id dai metadati, assicurati che il tuo ingest.py lo salvi
            results = []
            for doc in docs:
                source_name = doc.metadata.get("source", "")
                # Questo è un trucco per estrarre l'ID se non è salvato esplicitamente
                # Idealmente, l'ID del documento dovrebbe essere salvato durante l'ingestione
                doc_id_guess = doc_manager.search_documents(query=source_name)[0]['id'] if doc_manager.search_documents(query=source_name) else None
                if 'doc_id' not in doc.metadata and doc_id_guess:
                   doc.metadata['doc_id'] = doc_id_guess
                
                results.append((doc, self.doc_manager.get_document_path(doc.metadata.get("doc_id"))))
            return results

st.set_page_config(
    page_title="Naval Expert Assistant",
    page_icon="🤖",
    layout="wide"
)

# Inizializza i componenti principali tramite cache
@st.cache_resource
def get_doc_manager():
    return NavalDocumentManager()

@st.cache_resource
def init_retriever_and_llm():
    retriever, llm = get_knowledge_chain()
    doc_manager = get_doc_manager()
    smart_retriever = SmartNavalRetriever(retriever, doc_manager)
    return smart_retriever, llm

retriever, llm = init_retriever_and_llm()
doc_manager = get_doc_manager()

st.title("🤖 Assistente Esperto Navale")

# Due colonne: chat e documenti referenziati
col_chat, col_refs = st.columns([2, 1])

with col_chat:
    st.header("💬 Chat")
    
    # Container per i messaggi
    message_container = st.container(height=500, border=True)
    
    # Inizializza i messaggi se non esistono
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    with message_container:
        for i, message in enumerate(st.session_state.messages):
            with st.chat_message(message['role']):
                st.markdown(message['content'])
                
                if 'references' in message and message['references']:
                    st.divider()
                    st.caption("📎 Documenti Referenziati:")
                    for j, ref in enumerate(message['references']):
                        button_key = f"ref_{i}_{j}"
                        if st.button(
                            f"📄 {ref.get('doc_id', 'ID Sconosciuto')} - Pag. {ref.get('page', '?')}",
                            key=button_key
                        ):
                            st.session_state['viewing_doc'] = ref
                            st.rerun()
    
    # Input query
    query = st.chat_input(
        "Chiedi qualsiasi cosa sui documenti tecnici...",
        key="expert_chat"
    )
    
    if query:
        st.session_state.messages.append({"role": "user", "content": query})
        
        with st.spinner("Consultando documentazione..."):
            if retriever and llm:
                results = retriever.retrieve_with_context(query, k=5)
                response, references = generate_response_with_sources(llm, results, query)
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "references": references
                })
            else:
                st.error("Retriever o LLM non inizializzati correttamente.")

        st.rerun()

with col_refs:
    st.header("📚 Documento in Analisi")

    if 'viewing_doc' in st.session_state and st.session_state['viewing_doc']:
        doc_ref = st.session_state['viewing_doc']
        
        doc_id = doc_ref.get('doc_id', 'ID Sconosciuto')
        page_num = doc_ref.get('page')
        content_snippet = doc_ref.get('content', '')

        st.info(f"📄 **{doc_id}**")
        if page_num:
            st.caption(f"Visualizzando Pagina: **{page_num}**")

        doc_path = doc_manager.get_document_path(doc_id)

        if doc_path and doc_path.exists():
            try:
                # --- VISUALIZZATORE DELLA PAGINA SPECIFICA ---
                pdf_document = fitz.open(doc_path)
                
                page_index = int(page_num) - 1

                if 0 <= page_index < len(pdf_document):
                    page = pdf_document.load_page(page_index)
                    
                    # --- Evidenzia il testo di riferimento ---
                    if content_snippet:
                        # Cerca le istanze del testo (usa solo una porzione per robustezza)
                        search_text = " ".join(content_snippet.split()[:20])
                        areas = page.search_for(search_text)
                        for area in areas:
                            highlight = page.add_highlight_annot(area)
                            highlight.set_colors({"stroke": (1, 0.8, 0)}) # Colore giallo
                            highlight.update()
                    
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    
                    st.image(img_bytes, use_column_width=True)
                else:
                    st.warning(f"Pagina {page_num} non trovata nel documento.")
                
                pdf_document.close()

            except Exception as e:
                st.error(f"Errore nella visualizzazione del PDF: {e}")
            
            # Link per il download
            with open(doc_path, "rb") as f:
                st.download_button(
                    "📖 Apri PDF Completo",
                    data=f,
                    file_name=doc_path.name,
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.error(f"File del documento '{doc_id}' non trovato nel percorso atteso.")
    else:
        st.info("Clicca su un riferimento [📄...] nella chat per visualizzare qui la fonte originale.")