"""
Knowledge Base for Vibecode RAG System.
Combines SQLite (content storage) and ChromaDB (vector embeddings).

ECR #007: Scalable RAG Persistence Layer
- Unified interface for ingestion and retrieval
- Incremental sync (only process modified files)
- Persistent vector store with ChromaDB
"""

import os
import logging
from typing import Dict, List, Optional

from .persistence import ContentDB

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    Unified Knowledge Base combining:
    1. SQLite for file content storage (via ContentDB)
    2. ChromaDB for semantic vector search
    
    Provides incremental sync - only processes files that have changed.
    """
    
    def __init__(self, project_root: str):
        """
        Initialize the Knowledge Base.
        
        Args:
            project_root: Root directory of the project
        """
        self.root = project_root
        self.persist_dir = os.path.join(project_root, ".vibecode")
        
        # 1. Init SQL Content Store
        self.sql_db = ContentDB(os.path.join(self.persist_dir, "codebase.db"))
        
        # 2. Init Vector Store (ChromaDB)
        self._init_vector_store()
    
    def _init_vector_store(self):
        """Initialize ChromaDB persistent client."""
        try:
            import chromadb
            
            vector_path = os.path.join(self.persist_dir, "vectors")
            os.makedirs(vector_path, exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(path=vector_path)
            self.collection = self.chroma_client.get_or_create_collection(
                name="vibecode_index",
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
            self._vector_enabled = True
            logger.info(f"ChromaDB initialized at {vector_path}")
            
        except ImportError:
            logger.warning("chromadb not installed. Vector search disabled. Install with: pip install chromadb")
            self.chroma_client = None
            self.collection = None
            self._vector_enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self._vector_enabled = False
    
    def ingest_codebase(self, files: Dict[str, str]) -> int:
        """
        Incremental Ingestion Strategy.
        Only processes files that have changed since last sync.
        
        Args:
            files: dict of {filepath: content} from PDF parsing or discovery
            
        Returns:
            Number of files updated
        """
        logger.info("Starting Knowledge Base sync...")
        
        ids_to_upsert = []
        docs_to_upsert = []
        metadatas = []
        updated_count = 0
        
        for fpath, content in files.items():
            # Optimization: Only process if content changed
            if self.sql_db.needs_update(fpath, content):
                logger.debug(f"Indexing: {fpath}")
                self.sql_db.upsert_file(fpath, content)
                updated_count += 1
                
                # Prepare for Vector DB (if enabled)
                if self._vector_enabled:
                    # Truncate for embedding (ChromaDB default limit)
                    truncated = content[:10000] if len(content) > 10000 else content
                    ids_to_upsert.append(fpath)
                    docs_to_upsert.append(truncated)
                    metadatas.append({"source": fpath, "chars": len(content)})
        
        # Batch insert to Chroma
        if self._vector_enabled and ids_to_upsert:
            try:
                self.collection.upsert(
                    ids=ids_to_upsert,
                    documents=docs_to_upsert,
                    metadatas=metadatas
                )
                logger.info(f"Synced {len(ids_to_upsert)} files to vector store.")
            except Exception as e:
                logger.error(f"Failed to sync to vector store: {e}")
        
        # Remove orphaned files (deleted from project but still in cache)
        self.sql_db.delete_missing_files(list(files.keys()))
        
        if updated_count > 0:
            logger.info(f"✓ Synced {updated_count} files to Knowledge Base.")
        else:
            logger.info("✓ Knowledge Base is up to date.")
        
        return updated_count
    
    def query(self, query_text: str, n_results: int = 5) -> List[Dict]:
        """
        Semantic search query.
        Returns content from SQL based on Vector Search IDs.
        
        Args:
            query_text: Natural language query
            n_results: Number of results to return
            
        Returns:
            List of dicts with 'path', 'content', and 'score'
        """
        if not self._vector_enabled:
            logger.warning("Vector search disabled. Falling back to path search.")
            return self._fallback_search(query_text, n_results)
        
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            context_results = []
            for i, file_path in enumerate(results['ids'][0]):
                # Retrieve full clean text from SQL
                full_content = self.sql_db.get_content(file_path)
                if full_content:
                    distance = results['distances'][0][i] if results.get('distances') else 0
                    context_results.append({
                        'path': file_path,
                        'content': full_content,
                        'score': 1 - distance  # Convert distance to similarity
                    })
            
            return context_results
            
        except Exception as e:
            logger.error(f"Vector query failed: {e}")
            return []
    
    def _fallback_search(self, query_text: str, n_results: int) -> List[Dict]:
        """Simple string matching fallback when vector search unavailable."""
        results = []
        query_lower = query_text.lower()
        
        for path in self.sql_db.get_all_paths():
            if query_lower in path.lower():
                content = self.sql_db.get_content(path)
                if content:
                    results.append({
                        'path': path,
                        'content': content,
                        'score': 0.5  # Default score for path match
                    })
        
        return results[:n_results]
    
    def get_file(self, file_path: str) -> Optional[str]:
        """
        Get content of a specific file from the knowledge base.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File content if found, None otherwise
        """
        return self.sql_db.get_content(file_path)
    
    def get_all_files(self) -> Dict[str, str]:
        """
        Get all files from the knowledge base.
        Use sparingly - for small projects or when full context needed.
        
        Returns:
            Dict of {path: content}
        """
        files = {}
        for path in self.sql_db.get_all_paths():
            content = self.sql_db.get_content(path)
            if content:
                files[path] = content
        return files
    
    def get_stats(self) -> Dict:
        """Get statistics about the knowledge base."""
        file_count = self.sql_db.get_file_count()
        total_size = self.sql_db.get_total_size()
        
        vector_count = 0
        if self._vector_enabled:
            try:
                vector_count = self.collection.count()
            except Exception:
                pass
        
        return {
            'file_count': file_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'vector_count': vector_count,
            'vector_enabled': self._vector_enabled
        }
    
    def clear(self):
        """Clear the entire knowledge base."""
        self.sql_db.clear()
        if self._vector_enabled:
            try:
                self.chroma_client.delete_collection("vibecode_index")
                self.collection = self.chroma_client.get_or_create_collection(
                    name="vibecode_index"
                )
            except Exception as e:
                logger.error(f"Failed to clear vector store: {e}")
    
    def close(self):
        """Close all connections."""
        self.sql_db.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
