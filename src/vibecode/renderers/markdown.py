"""
Markdown Renderer.
Generates a single Markdown file snapshot of the codebase.
"""
import os
import json
import zlib
import base64
import hashlib
from typing import List, Tuple, Dict

from .secrets import scrub_secrets

# --- UTILITIES ---

def generate_ascii_tree(file_paths: List[str]) -> str:
    """
    Generates a directory tree string from a list of file paths.
    Output mimics the unix 'tree' command.
    """
    tree_dict = {}
    for path in sorted(file_paths):
        parts = path.replace('\\', '/').split('/')
        current_level = tree_dict
        for part in parts:
            current_level = current_level.setdefault(part, {})

    lines = ["."]
    
    def _walk(node: Dict, prefix: str):
        keys = sorted(node.keys())
        total = len(keys)
        for i, key in enumerate(keys):
            is_last = (i == total - 1)
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{key}")
            child_prefix = prefix + ("    " if is_last else "│   ")
            if node[key]: 
                _walk(node[key], child_prefix)

    _walk(tree_dict, "")
    return "\n".join(lines)


# --- MAIN RENDERER ---

class MarkdownRenderer:
    def __init__(self):
        self.total_chars = 0

    def render(self, file_data: List[Tuple[str, str]], output_path: str):
        """Generates a single Markdown file containing the codebase snapshot."""
        
        print(f"Rendering Markdown to {output_path}...")
        
        # 1. Prepare Content
        md_lines = []
        md_lines.append(f"# Codebase Snapshot: {os.path.basename(os.path.dirname(output_path))}")
        md_lines.append("")
        
        # 2. File Tree
        print("Generating project tree...")
        paths = [x[0] for x in file_data]
        tree_text = generate_ascii_tree(paths)
        
        md_lines.append("## Project Structure")
        md_lines.append("```text")
        md_lines.append(tree_text)
        md_lines.append("```")
        md_lines.append("")
        
        # 3. File Contents
        md_lines.append("## File Contents")
        md_lines.append("")
        
        for rel_path, content in file_data:
            # Security Scrub
            scrubbed_content = scrub_secrets(content)
            self.total_chars += len(scrubbed_content)
            
            # Determine language for syntax highlighting
            ext = os.path.splitext(rel_path)[1].lower()
            lang = ext.lstrip('.') if ext else 'text'
            
            # Use 'python' for .py, 'javascript' for .js, etc.
            # Map common extensions if needed, but usually ext name works fine in markdown
            
            md_lines.append(f"### `{rel_path}`")
            md_lines.append(f"```{lang}")
            md_lines.append(scrubbed_content)
            md_lines.append("```")
            md_lines.append("")
            
        # 4. Inject Digital Twin Manifest (Hidden HTML Comment)
        print("Injecting restoration manifest...")
        try:
            # Create manifest with RAW content (perfect fidelity)
            manifest = {path: content for path, content in file_data}
            
            # Compress and Encode
            json_bytes = json.dumps(manifest).encode('utf-8')
            compressed = zlib.compress(json_bytes)
            b64_payload = base64.b64encode(compressed).decode('utf-8')
            
            # Calculate SHA-256 Checksum (Extension 1)
            checksum = hashlib.sha256(b64_payload.encode('utf-8')).hexdigest()
            
            # Restore Block in HTML Comment
            # This allows the file to be valid Markdown while still carrying the payload
            manifest_block = (
                "\n<!--\n"
                "--- VIBECODE_RESTORE_BLOCK_START ---\n"
                f"sha256:{checksum}\n"
                f"{b64_payload}\n"
                "--- VIBECODE_RESTORE_BLOCK_END ---\n"
                "-->"
            )
            md_lines.append(manifest_block)
            
        except Exception as e:
            print(f"Warning: Failed to inject manifest: {e}")
            
        # 5. Write to File
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(md_lines))
                
            est_tokens = self.total_chars // 4
            print("-" * 40)
            print(f"DONE. Markdown Stats:")
            print(f"   - Files: {len(file_data)}")
            print(f"   - Approx. Tokens: {est_tokens:,}")
            print("-" * 40)
            
        except Exception as e:
            print(f"Error writing Markdown: {e}")
