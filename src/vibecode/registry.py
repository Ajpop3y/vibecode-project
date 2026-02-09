"""
Project Registry - Tracks saved Vibecode projects globally.
Stored at ~/.vibecode/projects.json
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ProjectEntry:
    """A registered project entry."""
    name: str
    path: str
    last_opened: str
    file_count: int = 0
    color: str = ""  # Hex color like "#FF5733" or empty for default
    tag: str = ""    # Optional tag like "Work", "Personal"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ProjectEntry':
        # Handle older entries without color/tag
        data.setdefault('color', '')
        data.setdefault('tag', '')
        return cls(**data)


class ProjectRegistry:
    """
    Manages a global registry of Vibecode projects.
    Persisted to ~/.vibecode/projects.json
    """
    
    def __init__(self):
        self.config_dir = Path.home() / '.vibecode'
        self.registry_path = self.config_dir / 'projects.json'
        self.projects: List[ProjectEntry] = []
        self.recent_limit = 20
        self._ensure_config_dir()
        self.load()
    
    def _ensure_config_dir(self):
        """Create config directory if needed."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load(self):
        """Load projects from JSON file."""
        if not self.registry_path.exists():
            self.projects = []
            return
        
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.projects = [ProjectEntry.from_dict(p) for p in data.get('projects', [])]
                self.recent_limit = data.get('recent_limit', 20)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Warning: Could not load project registry: {e}")
            self.projects = []
    
    def save(self):
        """Save projects to JSON file."""
        data = {
            'projects': [p.to_dict() for p in self.projects],
            'recent_limit': self.recent_limit
        }
        try:
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving project registry: {e}")
    
    def add_project(self, path: str, name: Optional[str] = None, file_count: int = 0) -> ProjectEntry:
        """
        Add or update a project in the registry.
        If project already exists, updates last_opened.
        """
        path = os.path.normpath(os.path.abspath(path))
        
        # Check if already exists
        existing = self.get_project_by_path(path)
        if existing:
            existing.last_opened = datetime.now().isoformat()
            existing.file_count = file_count
            if name:
                existing.name = name
            self._move_to_top(existing)
            self.save()
            return existing
        
        # Create new entry
        if not name:
            name = os.path.basename(path)
        
        entry = ProjectEntry(
            name=name,
            path=path,
            last_opened=datetime.now().isoformat(),
            file_count=file_count
        )
        
        # Add to front of list
        self.projects.insert(0, entry)
        
        # Enforce limit
        if len(self.projects) > self.recent_limit:
            self.projects = self.projects[:self.recent_limit]
        
        self.save()
        return entry
    
    def remove_project(self, path: str) -> bool:
        """Remove a project from the registry."""
        path = os.path.normpath(os.path.abspath(path))
        for i, p in enumerate(self.projects):
            if os.path.normpath(p.path) == path:
                self.projects.pop(i)
                self.save()
                return True
        return False
    
    def get_project_by_path(self, path: str) -> Optional[ProjectEntry]:
        """Find a project by its path."""
        path = os.path.normpath(os.path.abspath(path))
        for p in self.projects:
            if os.path.normpath(p.path) == path:
                return p
        return None
    
    def get_projects(self) -> List[ProjectEntry]:
        """Get all registered projects, most recent first."""
        return self.projects.copy()
    
    def _move_to_top(self, entry: ProjectEntry):
        """Move an entry to the top of the list."""
        if entry in self.projects:
            self.projects.remove(entry)
            self.projects.insert(0, entry)
    
    def update_last_opened(self, path: str, file_count: int = 0):
        """Update the last_opened timestamp for a project."""
        entry = self.get_project_by_path(path)
        if entry:
            entry.last_opened = datetime.now().isoformat()
            if file_count > 0:
                entry.file_count = file_count
            self._move_to_top(entry)
            self.save()

    def update_file_count(self, path: str, count: int):
        """Update the file count for a project."""
        entry = self.get_project_by_path(path)
        if entry:
            entry.file_count = count
            self.save()
    
    def rename_project(self, path: str, new_name: str) -> bool:
        """Rename a project in the registry."""
        entry = self.get_project_by_path(path)
        if entry:
            entry.name = new_name
            self.save()
            return True
        return False
    
    def set_project_color(self, path: str, color: str) -> bool:
        """Set the color for a project."""
        entry = self.get_project_by_path(path)
        if entry:
            entry.color = color
            self.save()
            return True
        return False
    
    def set_project_tag(self, path: str, tag: str) -> bool:
        """Set the tag for a project."""
        entry = self.get_project_by_path(path)
        if entry:
            entry.tag = tag
            self.save()
            return True
        return False
    
    def project_exists(self, path: str) -> bool:
        """Check if a project path still exists on disk."""
        config_file = os.path.join(path, '.vibecode.yaml')
        return os.path.isdir(path) and os.path.exists(config_file)
    
    def cleanup_missing(self) -> int:
        """Remove projects whose paths no longer exist. Returns count removed."""
        to_remove = [p for p in self.projects if not self.project_exists(p.path)]
        for p in to_remove:
            self.projects.remove(p)
        if to_remove:
            self.save()
        return len(to_remove)
    
    def scan_for_projects(self, search_root: str, max_depth: int = 3) -> List[ProjectEntry]:
        """
        Scan a directory for folders containing .vibecode.yaml files.
        Reads project metadata from the YAML and adds to registry.
        
        Args:
            search_root: Root folder to scan
            max_depth: How deep to search for projects
            
        Returns:
            List of newly discovered ProjectEntry objects
        """
        import yaml
        
        discovered = []
        search_root = os.path.normpath(os.path.abspath(search_root))
        
        for root, dirs, files in os.walk(search_root):
            # Calculate depth
            depth = root.replace(search_root, '').count(os.path.sep)
            if depth >= max_depth:
                dirs.clear()  # Don't go deeper
                continue
            
            # Skip common ignore folders
            dirs[:] = [d for d in dirs if d not in {
                '.git', '.venv', 'venv', 'node_modules', '__pycache__', 
                '.idea', '.vscode', 'dist', 'build'
            }]
            
            # Check for config file
            if '.vibecode.yaml' in files:
                config_path = os.path.join(root, '.vibecode.yaml')
                
                # Skip if already in registry
                if self.get_project_by_path(root):
                    continue
                
                # Read metadata from YAML
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                    
                    name = data.get('project_name', os.path.basename(root))
                    files_list = data.get('files', [])
                    file_count = len(files_list)
                    
                    entry = self.add_project(root, name, file_count)
                    discovered.append(entry)
                    
                except Exception as e:
                    print(f"Warning: Could not read {config_path}: {e}")
                    # Still add with folder name
                    entry = self.add_project(root, os.path.basename(root), 0)
                    discovered.append(entry)
        
        return discovered


# Singleton instance
_registry: Optional[ProjectRegistry] = None

def get_registry() -> ProjectRegistry:
    """Get the global project registry instance."""
    global _registry
    if _registry is None:
        _registry = ProjectRegistry()
    return _registry
