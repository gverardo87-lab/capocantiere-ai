# server/pages/06_📚_Document_Explorer.py (Versione Solo Lettura)
import streamlit as st
from pathlib import Path
import fitz

# Importiamo il nuovo DocumentManager "Scanner"
from core.document_manager import NavalDocumentManager

st.set_page_config(page_title="Naval Document Explorer", page_icon="📚", layout="wide")

# Inizializza il manager che scannerizzerà la cartella 'documents'
# st.cache_resource garantisce che la scansione avvenga solo una volta.
@st.cache_resource
def get_doc_manager():
    return NavalDocumentManager()

doc_manager = get_doc_manager()

st.title("📚 Esplora Documentazione Tecnica")
st.markdown("Visualizza i documenti tecnici disponibili nel sistema (`knowledge_base/documents`)")

col_left, col_right = st.columns([1, 2])

with col_left:
    st.header("📁 Archivio Documenti")
    
    search_query = st.text_input(
        "Ricerca per nome file o ID",
        placeholder="Codice, nome file..."
    )
    
    # La ricerca ora avviene in tempo reale
    search_results = doc_manager.search_documents(query=search_query)
    
    st.divider()
    st.subheader(f"📋 Trovati {len(search_results)} documenti")
    
    if not search_results:
        st.warning("Nessun documento trovato. Assicurati di aver inserito dei file PDF nella cartella `knowledge_base/documents`.")
    else:
        for doc in search_results:
            with st.container():
                if st.button(
                    f"📄 **{doc['id']}**\n_{doc['original_name'][:40]}..._",
                    key=doc['id'],
                    use_container_width=True
                ):
                    st.session_state['selected_doc'] = doc
                    st.rerun()

with col_right:
    st.header("📖 Visualizzatore Documento")

    if 'selected_doc' in st.session_state:
        doc = st.session_state['selected_doc']
        doc_path = doc_manager.get_document_path(doc['id'])

        st.subheader(f"{doc['original_name']}")
        st.caption(f"ID: {doc['id']} | Dimensione: {doc['size_bytes']//1024} KB")
        st.divider()

        if doc_path and doc_path.exists():
            try:
                pdf_document = fitz.open(doc_path)
                
                if 'current_page' not in st.session_state or st.session_state.get('current_doc_id') != doc['id']:
                    st.session_state.current_page = 0
                    st.session_state.current_doc_id = doc['id']

                total_pages = len(pdf_document)
                
                nav_cols = st.columns([2, 1, 1, 3])
                if nav_cols[1].button("⬅️ Prec.", use_container_width=True, disabled=(st.session_state.current_page == 0)):
                    st.session_state.current_page -= 1
                    st.rerun()
                if nav_cols[2].button("Succ. ➡️", use_container_width=True, disabled=(st.session_state.current_page >= total_pages - 1)):
                    st.session_state.current_page += 1
                    st.rerun()
                
                nav_cols[3].write(f"Pagina **{st.session_state.current_page + 1}** di **{total_pages}**")

                page = pdf_document.load_page(st.session_state.current_page)
                pix = page.get_pixmap(dpi=150)
                st.image(pix.tobytes("png"), use_column_width=True)

                with open(doc_path, "rb") as file:
                    st.download_button(
                        "⬇️ Scarica PDF Completo", file, file_name=doc['original_name'],
                        mime="application/pdf", use_container_width=True
                    )
                pdf_document.close()
            except Exception as e:
                st.error(f"Impossibile visualizzare il PDF: {e}")
        else:
            st.error(f"File non trovato: {doc_path}")
    else:
        st.info("👈 Seleziona un documento dalla lista a sinistra per visualizzarlo.")