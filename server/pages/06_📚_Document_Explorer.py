# server/pages/📚_Document_Explorer.py
import streamlit as st
from pathlib import Path
import base64
from typing import Optional

# Import nostri moduli
from core.document_manager import NavalDocumentManager
from core.knowledge_chain import get_knowledge_chain, VECTORSTORE_DIR, EMBEDDING_MODEL
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

# Definisci qui SmartNavalRetriever se non è in un altro file
# Se si trova in un altro file, assicurati che l'import sia corretto.
# Per ora, lo definisco qui come placeholder.
class SmartNavalRetriever:
    def __init__(self, vectorstore, doc_manager):
        self.vectorstore = vectorstore
        self.doc_manager = doc_manager

st.set_page_config(
    page_title="Naval Document Explorer",
    page_icon="📚",
    layout="wide"
)

# Inizializza manager
@st.cache_resource
def get_doc_manager():
    return NavalDocumentManager()

@st.cache_resource
def get_retriever():
    # Carica il vectorstore esistente
    try:
        embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
        vectorstore = Chroma(persist_directory=VECTORSTORE_DIR, embedding_function=embeddings)
        return SmartNavalRetriever(vectorstore, get_doc_manager())
    except Exception as e:
        st.error(f"Errore nel caricamento del retriever: {e}")
        return None

doc_manager = get_doc_manager()
retriever = get_retriever()

# --- LAYOUT A DUE COLONNE ---
col_left, col_right = st.columns([1, 2])

with col_left:
    st.header("📁 Archivio Documenti")
    
    # --- FILTRI ---
    with st.expander("🔍 Filtri", expanded=True):
        # Ricerca testuale
        search_query = st.text_input(
            "Ricerca rapida",
            placeholder="Codice, nome file, contenuto..."
        )
        
        # Filtro disciplina
        disciplines = ["Tutti", "HULL", "MACH", "ELEC", "PIPE", "HVAC", "OUTF", "PAINT", "GENERAL"]
        selected_discipline = st.selectbox(
            "Disciplina",
            disciplines
        )
        
        # Filtro tipo documento  
        doc_types = ["Tutti", "SPEC", "DWG", "PROC", "CALC", "CERT", "ITP", "MANUAL"]
        selected_type = st.selectbox(
            "Tipo Documento",
            doc_types
        )
    
    # --- RICERCA ---
    if st.button("🔍 Cerca", type="primary", use_container_width=True):
        discipline_filter = None if selected_discipline == "Tutti" else selected_discipline
        type_filter = None if selected_type == "Tutti" else selected_type
        
        results = doc_manager.search_documents(
            query=search_query,
            discipline=discipline_filter,
            doc_type=type_filter
        )
        
        st.session_state['search_results'] = results
    
    # --- RISULTATI ---
    if 'search_results' in st.session_state:
        st.divider()
        st.subheader(f"📋 Trovati {len(st.session_state['search_results'])} documenti")
        
        for doc in st.session_state['search_results']:
            with st.container():
                # Card del documento
                if st.button(
                    f"📄 **{doc['id']}**\n{doc['original_name'][:40]}...",
                    key=doc['id'],
                    use_container_width=True
                ):
                    st.session_state['selected_doc'] = doc
                
                # Metadata mini
                cols = st.columns(3)
                cols[0].caption(doc['discipline'])
                cols[1].caption(doc['doc_type'])
                cols[2].caption(f"{doc['size_bytes']//1024} KB")

with col_right:
    st.header("📖 Visualizzatore Documento")
    
    if 'selected_doc' in st.session_state:
        doc = st.session_state['selected_doc']
        
        # Info documento
        st.subheader(f"{doc['id']}")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Disciplina", doc['discipline'])
        col2.metric("Tipo", doc['doc_type'])
        col3.metric("Dimensione", f"{doc['size_bytes']//1024} KB")
        
        # Metadata aggiuntivi
        if doc.get('metadata'):
            with st.expander("ℹ️ Metadata"):
                for key, value in doc['metadata'].items():
                    st.write(f"**{key}**: {value}")
        
        st.divider()
        
        # Visualizza PDF
        doc_path = doc_manager.get_document_path(doc['id'])
        
        if doc_path and doc_path.suffix.lower() == '.pdf':
            # Mostra PDF embedded
            with open(doc_path, "rb") as pdf_file:
                base64_pdf = base64.b64encode(pdf_file.read()).decode('utf-8')
            
            pdf_display = f'''
                <iframe 
                    src="data:application/pdf;base64,{base64_pdf}" 
                    width="100%" 
                    height="800" 
                    type="application/pdf">
                </iframe>
            '''
            st.markdown(pdf_display, unsafe_allow_html=True)
            
            # Bottone download
            with open(doc_path, "rb") as file:
                st.download_button(
                    label="⬇️ Scarica PDF",
                    data=file,
                    file_name=doc['original_name'],
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.info("Seleziona un documento PDF per visualizzarlo")
    else:
        st.info("👈 Seleziona un documento dalla lista")

# --- SIDEBAR PER CARICAMENTO ---
with st.sidebar:
    st.header("📤 Carica Nuovo Documento")
    
    uploaded_file = st.file_uploader(
        "Seleziona file",
        type=['pdf', 'docx', 'xlsx'],
        help="Carica documenti tecnici"
    )
    
    if uploaded_file:
        upload_discipline = st.selectbox(
            "Disciplina",
            ["HULL", "MACH", "ELEC", "PIPE", "HVAC", "OUTF", "PAINT", "GENERAL"]
        )
        
        upload_type = st.selectbox(
            "Tipo",
            ["SPEC", "DWG", "PROC", "CALC", "CERT", "ITP", "MANUAL"]
        )
        
        # Metadata opzionali
        with st.expander("Metadata aggiuntivi"):
            rev = st.text_input("Revisione", "A")
            project = st.text_input("Progetto/Commessa")
            author = st.text_input("Autore")
        
        if st.button("📥 Registra Documento", type="primary"):
            # Salva temporaneamente
            temp_path = Path(f"/tmp/{uploaded_file.name}")
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Registra nel sistema
            metadata = {
                "revision": rev,
                "project": project,
                "author": author
            }
            
            doc_id = doc_manager.register_document(
                temp_path,
                upload_discipline,
                upload_type,
                metadata
            )
            
            st.success(f"✅ Documento registrato: {doc_id}")
            
            # Pulizia
            temp_path.unlink()