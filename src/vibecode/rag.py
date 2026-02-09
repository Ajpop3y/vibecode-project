"""
VibeRAG Module - Semantic Search for Codebase Files.

Provides embeddings-based similarity search using:
1. Gemini (preferred cloud)
2. OpenAI (cloud fallback)
3. Ollama (offline/local fallback)

Used by VibeExpand to auto-suggest related files.
"""

import os
import json
import math
import logging
import pickle
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# --- Configuration ---

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")  # Default embedding model

# --- API Key Resolution (shared with ai.py) ---

def _get_api_key(provider: str) -> Optional[str]:
    """Get API key for a provider, checking settings first, then environment."""
    # Special case for Ollama - no key needed
    if provider.lower() == 'ollama':
        return _check_ollama_available()
    
    try:
        from .settings import get_settings
        settings = get_settings()
        key = settings.get_api_key(provider)
        if key:
            return key
    except ImportError:
        pass
    
    env_map = {
        'google': 'GOOGLE_API_KEY',
        'openai': 'OPENAI_API_KEY',
    }
    
    env_var = env_map.get(provider.lower())
    if env_var:
        return os.getenv(env_var)
    
    return None


def _check_ollama_available() -> Optional[str]:
    """Check if Ollama server is running and return 'local' if so."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method='GET')
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return "local"
    except Exception:
        pass
    return None


# --- Vector Math Utilities (no numpy required) ---

def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(vec_a) != len(vec_b):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


def _normalize_vector(vec: List[float]) -> List[float]:
    """Normalize a vector to unit length."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


# --- Embedding Generation ---

def get_embedding(text: str, model: str = "auto") -> Optional[List[float]]:
    """
    Get embedding vector for text using Gemini, OpenAI, or Ollama.
    
    Args:
        text: Text to embed
        model: "gemini", "openai", "ollama", or "auto" (tries all in order)
        
    Returns:
        Embedding vector or None on failure
    """
    if model == "auto" or model == "gemini":
        google_key = _get_api_key('google')
        if google_key:
            try:
                return _gemini_embed(google_key, text)
            except Exception as e:
                logger.warning(f"Gemini embedding failed: {e}")
                if model == "gemini":
                    return None
    
    if model == "auto" or model == "openai":
        openai_key = _get_api_key('openai')
        if openai_key:
            try:
                return _openai_embed(openai_key, text)
            except Exception as e:
                logger.warning(f"OpenAI embedding failed: {e}")
                if model == "openai":
                    return None
    
    # Final fallback: Ollama (local)
    if model == "auto" or model == "ollama":
        ollama_available = _get_api_key('ollama')
        if ollama_available:
            try:
                return _ollama_embed(text)
            except Exception as e:
                logger.warning(f"Ollama embedding failed: {e}")
    
    return None


def _gemini_embed(api_key: str, text: str) -> List[float]:
    """Generate embedding using Gemini API (using new google-genai SDK)."""
    try:
        from google import genai
    except ImportError:
        raise ImportError("google-genai not installed")
    
    client = genai.Client(api_key=api_key)
    
    # Truncate text if too long (Gemini has limits)
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars]
    
    response = client.models.embed_content(
        model='gemini-embedding-001',
        contents=text,
    )
    
    # New SDK returns embeddings as a list of ContentEmbedding objects
    return response.embeddings[0].values


def _openai_embed(api_key: str, text: str) -> List[float]:
    """Generate embedding using OpenAI API."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai not installed")
    
    client = OpenAI(api_key=api_key)
    
    # Truncate if needed
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars]
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    
    return response.data[0].embedding


def _ollama_embed(text: str) -> List[float]:
    """Generate embedding using local Ollama server."""
    import urllib.request
    
    # Truncate if needed
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars]
    
    payload = json.dumps({
        "model": OLLAMA_EMBED_MODEL,
        "prompt": text
    }).encode('utf-8')
    
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    
    embedding = result.get('embedding', [])
    if not embedding:
        raise ValueError("Ollama returned empty embedding")
    
    logger.debug(f"Ollama generated embedding (dim={len(embedding)})")
    return embedding


# --- Index Building & Searching ---

class VibeIndex:
    """
    Simple vector index for semantic file search.
    Stores file embeddings and provides similarity search.
    """
    
    def __init__(self):
        self.embeddings: Dict[str, List[float]] = {}  # path -> embedding
        self.metadata: Dict[str, dict] = {}  # path -> {size, lines, etc.}
    
    def add_file(self, path: str, content: str, metadata: dict = None):
        """Add a file to the index."""
        embedding = get_embedding(content)
        if embedding:
            self.embeddings[path] = _normalize_vector(embedding)
            self.metadata[path] = metadata or {}
            logger.debug(f"Indexed: {path}")
        else:
            logger.warning(f"Could not embed: {path}")
    
    def search(self, query: str, top_k: int = 5, min_score: float = 0.0) -> List[Tuple[str, float]]:
        """
        Search for files similar to a query.
        
        Args:
            query: Search query (text or file content)
            top_k: Number of results to return
            
        Returns:
            List of (path, similarity_score) tuples, sorted by score descending
        """
        query_embedding = get_embedding(query)
        if not query_embedding:
            return []
        
        query_embedding = _normalize_vector(query_embedding)
        
        similarities = []
        for path, file_embedding in self.embeddings.items():
            score = _cosine_similarity(query_embedding, file_embedding)
            similarities.append((path, score))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by threshold
        filtered = [x for x in similarities if x[1] >= min_score]
        
        return filtered[:top_k]
    
    def find_related(self, file_path: str, top_k: int = 5, min_score: float = 0.0) -> List[Tuple[str, float]]:
        """
        Find files related to a given file.
        
        Args:
            file_path: Path of the file to find relatives for
            top_k: Number of results
            
        Returns:
            List of (path, similarity_score) tuples, excluding the source file
        """
        if file_path not in self.embeddings:
            return []
        
        source_embedding = self.embeddings[file_path]
        
        similarities = []
        for path, file_embedding in self.embeddings.items():
            if path == file_path:
                continue  # Skip self
            score = _cosine_similarity(source_embedding, file_embedding)
            similarities.append((path, score))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by threshold
        filtered = [x for x in similarities if x[1] >= min_score]
        
        return filtered[:top_k]
    
    def save(self, path: str):
        """Save index to file."""
        data = {
            'embeddings': self.embeddings,
            'metadata': self.metadata,
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"Index saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> 'VibeIndex':
        """Load index from file."""
        index = cls()
        with open(path, 'rb') as f:
            data = pickle.load(f)
        index.embeddings = data.get('embeddings', {})
        index.metadata = data.get('metadata', {})
        logger.info(f"Index loaded from {path} ({len(index.embeddings)} files)")
        return index
    
    def __len__(self):
        return len(self.embeddings)


# --- High-Level Functions ---

def build_index(files: Dict[str, str], progress_callback=None) -> VibeIndex:
    """
    Build a semantic index from a dictionary of files.
    
    Args:
        files: Dict of {relative_path: file_content}
        progress_callback: Optional function(current, total) for progress updates
        
    Returns:
        VibeIndex object
    """
    index = VibeIndex()
    total = len(files)
    
    for i, (path, content) in enumerate(files.items()):
        if progress_callback:
            progress_callback(i + 1, total)
        
        # Skip empty or very large files
        if not content or len(content) > 50000:
            continue
        
        # Create a summary for embedding (first 2000 chars + structure hints)
        summary = f"File: {path}\n\n{content[:2000]}"
        
        index.add_file(path, summary, metadata={'size': len(content)})
    
    logger.info(f"Built index with {len(index)} files")
    return index


def expand_selection(
    selected_files: List[str], 
    index: VibeIndex, 
    top_k: int = 3,
    min_score: float = 0.4
) -> List[Tuple[str, float]]:
    """
    Suggest additional files related to the current selection.
    
    Args:
        selected_files: Currently selected file paths
        index: VibeIndex to search
        top_k: Number of suggestions per file
        
    Returns:
        List of (path, score) tuples for suggested files
    """
    suggestions = {}
    
    for path in selected_files:
        related = index.find_related(path, top_k=top_k, min_score=min_score)
        for rel_path, score in related:
            if rel_path not in selected_files:
                # Aggregate scores if file appears multiple times
                if rel_path in suggestions:
                    suggestions[rel_path] = max(suggestions[rel_path], score)
                else:
                    suggestions[rel_path] = score
    
    # Sort by aggregated score
    sorted_suggestions = sorted(suggestions.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_suggestions[:top_k * 2]  # Return more than k since we aggregated
