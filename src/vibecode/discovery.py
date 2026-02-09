"""
File discovery and gitignore handling.
"""
import os
import logging
from pathlib import Path
import pathspec
from pathspec.patterns import GitWildMatchPattern
from typing import List

logger = logging.getLogger(__name__)

def load_gitignore_spec(project_root: str) -> pathspec.PathSpec:
    """
    Loads .gitignore rules from the project root.
    Returns a PathSpec object for matching.
    """
    root = Path(project_root)
    gitignore_path = root / '.gitignore'
    patterns = []

    # 1. Load .gitignore if it exists
    if gitignore_path.exists():
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                patterns.extend(f.readlines())
        except Exception as e:
            logger.warning(f"Could not read .gitignore: {e}")

    # 2. Always add default patterns for Version Control Systems
    # This prevents the tool from accidentally scanning its own .git folder
    patterns.append('.git/')
    
    return pathspec.PathSpec.from_lines(GitWildMatchPattern, patterns)

def discover_files(project_root: str, spec: pathspec.PathSpec) -> List[str]:
    """
    Walks the project_root, respects the .gitignore spec,
    and returns a list of non-ignored ABSOLUTE file paths.
    """
    root_path = Path(project_root).resolve()
    discovered_files = []

    def on_walk_error(error: OSError):
        """Callback for os.walk errors (permission denied, etc.)"""
        logger.warning(f"Cannot access directory: {error.filename} - {error.strerror}")

    # We use os.walk() instead of Path.rglob() because os.walk allow us to 
    # modify 'dirs' in-place. This lets us efficiently PRUNE massive ignored 
    # directories (like node_modules or venv) effectively skipping them entirely.
    for current_root, dirs, files in os.walk(root_path, onerror=on_walk_error):
        current_root_path = Path(current_root)
        
        # Calculate relative path from project root for matching against spec
        try:
            rel_path_obj = current_root_path.relative_to(root_path)
        except ValueError as e:
            logger.warning(f"Skipping directory with unexpected path: {current_root} - {e}")
            continue
        
        # 1. Prune Directories (Optimization)
        # We iterate over a copy (list(dirs)) so we can modify the original 'dirs' list safely.
        for d in list(dirs):
            try:
                dir_rel_path = rel_path_obj / d
                
                # pathspec directory matching often requires a trailing slash 
                # to distinguish "temp" (file) from "temp/" (dir)
                # .as_posix() ensures we use '/' even on Windows
                check_path = f"{dir_rel_path.as_posix()}/"
                
                if spec.match_file(check_path):
                    dirs.remove(d)  # This stops os.walk from entering this directory
            except Exception as e:
                logger.warning(f"Error processing directory '{d}': {e}")
                dirs.remove(d)  # Skip problematic directories

        # 2. Collect Files
        for f in files:
            try:
                file_rel_path = rel_path_obj / f
                
                # Check if file is ignored
                if not spec.match_file(file_rel_path.as_posix()):
                    # Store absolute path for the engine to read later
                    full_path = current_root_path / f
                    discovered_files.append(str(full_path))
            except Exception as e:
                logger.warning(f"Skipping file '{f}' in '{current_root}': {e}")

    logger.debug(f"Discovered {len(discovered_files)} files in {project_root}")
    return discovered_files