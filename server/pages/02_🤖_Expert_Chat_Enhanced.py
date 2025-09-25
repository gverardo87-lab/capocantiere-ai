# server/pages/🤖_Expert_Chat_Enhanced.py
import streamlit as st
from pathlib import Path

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
            return [(doc, self.doc_manager.get_document_path(doc.metadata.get("doc_id"))) for doc in docs]

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
    # Assumendo che SmartNavalRetriever sia la classe che vuoi usare
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
    message_container = st.container(height=500)
    
    # Inizializza i messaggi se non esistono
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    with message_container:
        for message in st.session_state.messages:
            with st.chat_message(message['role']):
                st.markdown(message['content'])
                
                # Se ci sono documenti referenziati
                if 'references' in message and message['references']:
                    st.divider()
                    st.caption("📎 Documenti Referenziati:")
                    for i, ref in enumerate(message['references']):
                        # Crea una chiave univoca per ogni bottone
                        button_key = f"ref_{ref.get('doc_id', 'N/A')}_{ref.get('page', 'N/A')}_{i}_{message['content'][:10]}"
                        if st.button(
                            f"📄 {ref.get('doc_id', 'ID Sconosciuto')} - Pag. {ref.get('page', '?')}",
                            key=button_key
                        ):
                            st.session_state['viewing_doc'] = ref
    
    # Input query
    query = st.chat_input(
        "Chiedi qualsiasi cosa sui documenti tecnici...",
        key="expert_chat"
    )
    
    if query:
        # Aggiungi messaggio utente
        st.session_state.messages.append({"role": "user", "content": query})
        
        # Ottieni risposta con retrieval
        with st.spinner("Consultando documentazione..."):
            if retriever and llm:
                results = retriever.retrieve_with_context(query, k=5)
                
                # Genera risposta
                response, references = generate_response_with_sources(llm, results, query)
                
                # Aggiungi risposta
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "references": references
                })
            else:
                st.error("Retriever o LLM non inizializzati correttamente.")

        st.rerun()

with col_refs:
    st.header("📚 Documento Corrente")
    
    if 'viewing_doc' in st.session_state:
        doc_ref = st.session_state['viewing_doc']
        
        st.info(f"📄 {doc_ref.get('doc_id', 'ID Sconosciuto')}")
        st.caption(f"Pagina {doc_ref.get('page', '?')}")
        
        # Ottieni path del documento
        doc_path = doc_manager.get_document_path(doc_ref.get('doc_id'))
        
        if doc_path and doc_path.exists():
            # Mini viewer del PDF alla pagina specifica
            st.success("✅ Documento disponibile")
            
            # Link per aprire in nuova finestra
            with open(doc_path, "rb") as f:
                st.download_button(
                    "📖 Apri PDF Completo",
                    data=f,
                    file_name=doc_path.name,
                    mime="application/pdf",
                    use_container_width=True
                )
            
            # Mostra estratto del contenuto referenziato
            if 'content' in doc_ref:
                st.divider()
                st.caption("📝 Estratto:")
                st.text(doc_ref['content'][:500] + "...")
    else:
        st.info("Clicca su un riferimento nella chat per visualizzare il documento")
