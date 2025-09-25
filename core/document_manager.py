# core/document_manager.py (Nuova versione "Scanner")
from pathlib import Path
import hashlib
from typing import Dict, List, Optional
import streamlit as st

# La cartella 'documents' è la nostra unica fonte di verità.
DOCUMENTS_ROOT = Path("./knowledge_base/documents")

def generate_doc_id(file_path: Path) -> str:
    """
    Crea un ID stabile e univoco basato sul nome del file.
    In questo modo, sia l'ingestione che il manager usano lo stesso ID.
    """
    s = str(file_path.name).encode('utf-8')
    return f"DOC-{hashlib.md5(s).hexdigest()[:8].upper()}"

class NavalDocumentManager:
    """
    Gestore che "scannerizza" la cartella 'knowledge_base/documents'
    e crea un indice in memoria dei file trovati.
    NON gestisce più un suo archivio separato.
    """
    
    def __init__(self, base_path: Path = DOCUMENTS_ROOT):
        self.base_path = base_path
        self.index = self._scan_and_index()
    
    def _scan_and_index(self) -> Dict[str, Dict]:
        """
        Analizza la cartella dei documenti e costruisce un indice.
        """
        index = {}
        if not self.base_path.is_dir():
            st.error(f"La cartella dei documenti non esiste: {self.base_path.resolve()}")
            return {}

        # Cerca tutti i file PDF, anche in sottocartelle
        for file_path in self.base_path.rglob("*.pdf"):
            doc_id = generate_doc_id(file_path)
            index[doc_id] = {
                "id": doc_id,
                "original_name": file_path.name,
                "path": str(file_path.resolve()), # Usiamo percorsi assoluti per robustezza
                "size_bytes": file_path.stat().st_size,
                # Questi campi non sono più rilevanti ma li teniamo per compatibilità con la UI
                "discipline": "Generale",
                "doc_type": "PDF",
                "registered_date": file_path.stat().st_mtime
            }
        
        return index
    
    def search_documents(
        self,
        query: str = None,
        discipline: str = None, # Filtri non più usati ma mantenuti per firma
        doc_type: str = None
    ) -> List[Dict]:
        """
        Ricerca documenti nell'indice in memoria.
        """
        # Se la query è vuota, restituisce tutti i documenti
        if not query:
            results = list(self.index.values())
        else:
            query_lower = query.lower()
            results = [
                doc for doc in self.index.values()
                if query_lower in doc['original_name'].lower() or query_lower in doc['id'].lower()
            ]
        
        return sorted(results, key=lambda x: x['original_name'])
    
    def get_document_path(self, doc_id: str) -> Optional[Path]:
        """
        Ottiene il percorso completo del documento dall'indice.
        """
        if doc_id in self.index:
            return Path(self.index[doc_id]['path'])
        return None