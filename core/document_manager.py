# core/document_manager.py
from pathlib import Path
import shutil
import json
from datetime import datetime
from typing import Dict, List, Optional
import hashlib

class NavalDocumentManager:
    """
    Gestore documenti con struttura da cantiere navale.
    Semplice ma rigoroso.
    """
    
    def __init__(self, base_path: Path = Path("./naval_archive")):
        self.base_path = base_path
        self._init_structure()
        self.index_file = self.base_path / "index.json"
        self.index = self._load_index()
    
    def _init_structure(self):
        """Crea struttura cartelle standard cantieristica."""
        # Struttura principale per disciplina
        disciplines = [
            "HULL",      # Scafo
            "MACH",      # Machinery
            "ELEC",      # Electrical
            "HVAC",      # Heating, Ventilation, AC
            "PIPE",      # Piping
            "OUTF",      # Outfitting
            "PAINT",     # Painting
            "GENERAL"    # Documenti generali
        ]
        
        # Sottocartelle per tipo documento
        doc_types = [
            "SPEC",      # Specifiche
            "DWG",       # Disegni
            "PROC",      # Procedure
            "CALC",      # Calcoli
            "CERT",      # Certificati
            "ITP",       # Inspection Test Plans
            "MANUAL"     # Manuali
        ]
        
        for discipline in disciplines:
            for doc_type in doc_types:
                folder = self.base_path / discipline / doc_type
                folder.mkdir(parents=True, exist_ok=True)
    
    def register_document(
        self, 
        file_path: Path,
        discipline: str,
        doc_type: str,
        metadata: Dict
    ) -> str:
        """
        Registra e archivia un documento con metadati completi.
        Ritorna l'ID univoco del documento.
        """
        # Genera ID univoco ma leggibile
        # Es: "HULL-DWG-2024-001"
        doc_id = self._generate_doc_id(discipline, doc_type)
        
        # Calcola hash per deduplicazione
        file_hash = self._calculate_file_hash(file_path)
        
        # Controlla duplicati
        if self._is_duplicate(file_hash):
            print(f"⚠️ Documento già presente con hash {file_hash}")
            return self._get_doc_by_hash(file_hash)
        
        # Copia file nella struttura
        target_dir = self.base_path / discipline / doc_type
        target_path = target_dir / f"{doc_id}_{file_path.name}"
        shutil.copy2(file_path, target_path)
        
        # Aggiorna indice
        doc_entry = {
            "id": doc_id,
            "original_name": file_path.name,
            "path": str(target_path.relative_to(self.base_path)),
            "discipline": discipline,
            "doc_type": doc_type,
            "hash": file_hash,
            "size_bytes": file_path.stat().st_size,
            "registered_date": datetime.now().isoformat(),
            "metadata": metadata
        }
        
        self.index[doc_id] = doc_entry
        self._save_index()
        
        print(f"✅ Documento registrato: {doc_id}")
        return doc_id
    
    def search_documents(
        self,
        query: str = None,
        discipline: str = None,
        doc_type: str = None,
        metadata_filters: Dict = None
    ) -> List[Dict]:
        """Ricerca documenti con filtri multipli."""
        results = []
        
        for doc_id, doc in self.index.items():
            # Filtro per disciplina
            if discipline and doc['discipline'] != discipline:
                continue
            
            # Filtro per tipo
            if doc_type and doc['doc_type'] != doc_type:
                continue
            
            # Ricerca testuale nel nome e metadati
            if query:
                query_lower = query.lower()
                searchable = [
                    doc['original_name'].lower(),
                    doc['id'].lower(),
                    json.dumps(doc.get('metadata', {})).lower()
                ]
                if not any(query_lower in s for s in searchable):
                    continue
            
            # Filtri sui metadati
            if metadata_filters:
                doc_meta = doc.get('metadata', {})
                match = all(
                    doc_meta.get(k) == v 
                    for k, v in metadata_filters.items()
                )
                if not match:
                    continue
            
            results.append(doc)
        
        return sorted(results, key=lambda x: x['registered_date'], reverse=True)
    
    def get_document_path(self, doc_id: str) -> Optional[Path]:
        """Ottiene il path completo del documento."""
        if doc_id in self.index:
            relative_path = self.index[doc_id]['path']
            full_path = self.base_path / relative_path
            if full_path.exists():
                return full_path
        return None
    
    def _generate_doc_id(self, discipline: str, doc_type: str) -> str:
        """Genera ID progressivo per documento."""
        year = datetime.now().year
        prefix = f"{discipline}-{doc_type}-{year}"
        
        # Trova il numero progressivo
        existing = [
            doc_id for doc_id in self.index.keys()
            if doc_id.startswith(prefix)
        ]
        
        if existing:
            numbers = [
                int(doc_id.split('-')[-1]) 
                for doc_id in existing
            ]
            next_num = max(numbers) + 1
        else:
            next_num = 1
        
        return f"{prefix}-{next_num:03d}"
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calcola SHA-256 del file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _load_index(self) -> Dict:
        """Carica indice documenti."""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_index(self):
        """Salva indice documenti."""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)