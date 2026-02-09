"""
Human-readable PDF Renderer.
Generates syntax-highlighted PDFs using WeasyPrint for human consumption.
"""
import os
import json
import zlib
import base64
import concurrent.futures
import mistune
import pygments
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound
from weasyprint import HTML, CSS
from typing import List, Tuple, Dict

from .secrets import scrub_secrets

# --- STANDALONE HELPERS ---

def generate_ascii_tree(file_paths: List[str]) -> str:
    """
    Generates a directory tree string from a list of file paths.
    Output mimics the unix 'tree' command.
    """
    # 1. Build nested dictionary structure
    tree_dict = {}
    for path in sorted(file_paths):
        # normalize path separators
        parts = path.replace('\\', '/').split('/')
        current_level = tree_dict
        for part in parts:
            current_level = current_level.setdefault(part, {})

    # 2. Recursive string builder
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

def _sanitize_utf8(text: str) -> str:
    """Sanitizes text to ensure valid UTF-8."""
    text = text.replace('\0', '')
    return text.encode('utf-8', 'replace').decode('utf-8')

def _render_worker(payload) -> str:
    """
    The heavy lifting function executed by worker processes.
    Applies secret scrubbing before rendering.
    """
    # Import here to avoid multiprocessing issues
    from .secrets import scrub_secrets
    
    path, raw_content, pygments_style = payload
    # Scrub secrets first, then sanitize
    scrubbed_content = scrub_secrets(raw_content)
    content = _sanitize_utf8(scrubbed_content)
    
    html_parts = []
    
    # Header with Page Break
    html_parts.append(f'<h1 style="page-break-before: always;">{path}</h1>')

    try:
        if path.endswith(".md"):
            html_parts.append(mistune.html(content))
        elif path.endswith((".txt", ".log", ".gitignore", ".env")) or '.' not in path:
            html_parts.append(f"<pre>{content}</pre>")
        else:
            try:
                lexer = guess_lexer_for_filename(path, content)
            except ClassNotFound:
                lexer = get_lexer_by_name("text")
            
            formatter = HtmlFormatter(style=pygments_style, full=False, cssclass="highlight")
            html_content = pygments.highlight(content, lexer, formatter)
            html_parts.append(html_content)

    except Exception as e:
        error_msg = f"Error rendering {path}: {str(e)}"
        html_parts.append(f"<pre style='color: red;'>{error_msg}</pre>")
        html_parts.append(f"<pre>{content}</pre>")

    return "".join(html_parts)


# --- MAIN RENDERER CLASS ---

class HumanRenderer:
    def __init__(self, style: str = 'monokai'):
        self.pygments_style = style

    def _generate_css(self) -> str:
        """Generates the Pygments CSS definitions explicitly."""
        formatter = HtmlFormatter(style=self.pygments_style, cssclass="highlight")
        return formatter.get_style_defs('.highlight')

    def _generate_html_content(self, file_data: List[Tuple[str, str]]) -> str:
        """
        Orchestrates parallel rendering of all files.
        """
        print(f"Processing {len(file_data)} files using Parallel Execution...")

        # 1. Generate Tree View (Main Thread)
        print("Generating project tree...")
        paths = [x[0] for x in file_data]
        tree_text = generate_ascii_tree(paths)
        
        # HTML for the tree
        tree_html = (
            '<div class="tree-container">'
            '<h1>Project Structure</h1>'
            f'<pre class="tree-view">{tree_text}</pre>'
            '</div>'
        )

        # 2. Render Files (Parallel Workers)
        tasks = [
            (path, content, self.pygments_style) 
            for path, content in file_data
        ]

        results = []
        with concurrent.futures.ProcessPoolExecutor() as executor:
            results = list(executor.map(_render_worker, tasks))

        body_content = "".join(results)
        
        # 3. Generate Digital Twin Manifest (The Restore Block)
        print("Injecting restoration manifest...")
        try:
            import hashlib
            
            # Create manifest with RAW content (perfect fidelity)
            manifest = {path: content for path, content in file_data}
            
            # Compress and Encode
            json_bytes = json.dumps(manifest).encode('utf-8')
            compressed = zlib.compress(json_bytes)
            b64_payload = base64.b64encode(compressed).decode('utf-8')
            
            # Calculate SHA-256 Checksum (Extension 1)
            checksum = hashlib.sha256(b64_payload.encode('utf-8')).hexdigest()
            final_payload = f"sha256:{checksum}\n{b64_payload}"
            
            # Create HTML block - Hidden visually (tiny font/white color) but present in text layer
            manifest_html = f"""
            <div style="page-break-before: always; font-size: 1pt; color: #ffffff; overflow: hidden;">
                --- VIBECODE_RESTORE_BLOCK_START ---
                {final_payload}
                --- VIBECODE_RESTORE_BLOCK_END ---
            </div>
            """
        except Exception as e:
            print(f"Warning: Failed to generate manifest: {e}")
            manifest_html = ""

        # 4. Generate CSS
        pygments_css = self._generate_css()

        # 5. Assemble Master HTML
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                /* Pygments Styles */
                {pygments_css}
                
                /* Global Layout Styles */
                body {{ font-family: sans-serif; }}
                pre {{ 
                    white-space: pre-wrap !important;
                    word-break: break-all !important;
                    overflow-wrap: anywhere !important;
                }}
                
                /* Tree View Specifics */
                .tree-view {{
                    font-family: 'Courier New', monospace;
                    background-color: #272822; /* Monokai Background */
                    color: #a6e22e; /* Monokai Green */
                    padding: 15px;
                    border-radius: 8px;
                    border: 1px solid #49483e;
                    page-break-after: always; /* Ensure code starts on next page */
                }}
            </style>
        </head>
        <body>
            {tree_html}
            {body_content}
            {manifest_html}
        </body>
        </html>
        """

    def render(self, file_data: List[Tuple[str, str]], output_path: str):
        """Generates the high-fidelity PDF using WeasyPrint."""
        
        # 1. Generate Master HTML
        master_html = self._generate_html_content(file_data)

        # 2. Define PDF-Specific CSS
        pdf_css_string = """
        pre {
            page-break-inside: auto !important;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
            margin-top: 0;
            padding: 10px;
            background-color: #2e2e2e;
            color: #f8f8f2;
            border-radius: 5px;
        }
        h1 {
            font-family: sans-serif;
            font-size: 14pt;
            font-weight: bold;
            margin-bottom: 5px;
            border-bottom: 2px solid #333;
            page-break-after: avoid !important;
            color: #333;
        }
        table {
            width: 100%;
            table-layout: fixed;
            word-wrap: break-word;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
        }
        """

        # 3. Render with WeasyPrint
        print(f"Rendering HTML to PDF at {output_path}...")
        try:
            pdf_css = CSS(string=pdf_css_string)
            HTML(string=master_html, base_url=os.getcwd()).write_pdf(
                output_path,
                stylesheets=[pdf_css]
            )
            print("Done.")
        except Exception as e:
            print(f"Critical WeasyPrint Error: {e}")
            raise e