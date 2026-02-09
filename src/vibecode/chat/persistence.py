"""
Persistence Layer for Vibecode RAG System.
Implements SQLite storage for file content and metadata.

ECR #007: Scalable RAG Persistence Layer
- Prevents loading massive codebases into RAM
- Content is flushed to disk and loaded on-demand
- Hash-based change detection for incremental syncing
"""

import sqlite3
import os
import hashlib
from typing import Optional, List, Tuple
from datetime import datetime


class ContentDB:
    """
    Manages the 'Cold Storage' of file contents and metadata.
    Prevents loading massive codebases into RAM by storing in SQLite.
    
    Features:
    - Hash-based change detection (skip unchanged files)
    - On-demand content retrieval (lazy loading)
    - Thread-safe connections
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str):
        """
        Initialize the content database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Schema: Path is ID, Hash for change detection, Content for RAG retrieval
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_cache (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                content TEXT NOT NULL,
                file_size INTEGER,
                line_count INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Metadata table for version tracking
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Set schema version
        self.cursor.execute("""
            INSERT OR IGNORE INTO metadata (key, value) VALUES ('schema_version', ?)
        """, (str(self.SCHEMA_VERSION),))
        
        self.conn.commit()
    
    def needs_update(self, file_path: str, content: str) -> bool:
        """
        Checks if file has changed since last ingest.
        
        Args:
            file_path: Relative path to the file
            content: Current file content
            
        Returns:
            True if file needs to be updated, False if unchanged
        """
        current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        row = self.cursor.execute(
            "SELECT file_hash FROM file_cache WHERE file_path=?", 
            (file_path,)
        ).fetchone()
        
        if row and row[0] == current_hash:
            return False  # No update needed
        return True
    
    def upsert_file(self, file_path: str, content: str):
        """
        Insert or Update file content.
        
        Args:
            file_path: Relative path to the file
            content: File content to store
        """
        file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        file_size = len(content)
        line_count = content.count('\n') + 1
        
        self.cursor.execute("""
            INSERT OR REPLACE INTO file_cache 
            (file_path, file_hash, content, file_size, line_count, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (file_path, file_hash, content, file_size, line_count, datetime.now()))
        self.conn.commit()
    
    def get_content(self, file_path: str) -> Optional[str]:
        """
        Lazy load content only when requested by RAG.
        
        Args:
            file_path: Relative path to the file
            
        Returns:
            File content if found, None otherwise
        """
        row = self.cursor.execute(
            "SELECT content FROM file_cache WHERE file_path=?", 
            (file_path,)
        ).fetchone()
        return row[0] if row else None
    
    def get_all_paths(self) -> List[str]:
        """Get all file paths in the cache."""
        rows = self.cursor.execute("SELECT file_path FROM file_cache").fetchall()
        return [row[0] for row in rows]
    
    def get_file_count(self) -> int:
        """Get the number of files in the cache."""
        row = self.cursor.execute("SELECT COUNT(*) FROM file_cache").fetchone()
        return row[0] if row else 0
    
    def get_total_size(self) -> int:
        """Get total size of all cached content in bytes."""
        row = self.cursor.execute("SELECT SUM(file_size) FROM file_cache").fetchone()
        return row[0] or 0
    
    def delete_file(self, file_path: str):
        """Remove a file from the cache."""
        self.cursor.execute("DELETE FROM file_cache WHERE file_path=?", (file_path,))
        self.conn.commit()
    
    def delete_missing_files(self, existing_paths: List[str]):
        """
        Remove files from cache that no longer exist in the project.
        
        Args:
            existing_paths: List of currently existing file paths
        """
        if not existing_paths:
            return
            
        cached_paths = set(self.get_all_paths())
        existing_set = set(existing_paths)
        orphaned = cached_paths - existing_set
        
        for path in orphaned:
            self.delete_file(path)
    
    def clear(self):
        """Clear all cached content."""
        self.cursor.execute("DELETE FROM file_cache")
        self.conn.commit()
    
    def close(self):
        """Close the database connection."""
        self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
