"""
LLM-optimized PDF Renderer.
Generates plain-text PDFs using FPDF, optimized for LLM context windows.
"""
import os
import json
import zlib
import base64
import hashlib
from fpdf import FPDF
from typing import List, Tuple, Dict

from .secrets import scrub_secrets

# --- CONFIGURATION ---
FONT_NAME = 'NotoSansMono-Regular.ttf'
FONT_PATH = os.path.join(os.path.dirname(__file__), FONT_NAME)


# --- UTILITIES ---
def generate_ascii_tree(file_paths: List[str]) -> str:
    """Generates a visual directory tree."""
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
class LLMRenderer:
    def __init__(self):
        self.pdf = FPDF()
        self.pdf.add_page()
        self.utf8_enabled = False
        self.total_chars = 0
        
        # Check if font file exists
        if not os.path.exists(FONT_PATH):
            print(f"Warning: Manual font file not found at: {FONT_PATH}")
            self._fallback_to_standard_font()
            return

        # Attempt to load
        try:
            self.pdf.add_font('NotoSansMono', '', FONT_PATH, uni=True)
            self.pdf.add_font('NotoSansMono', 'B', FONT_PATH, uni=True)
            self.pdf.set_font('NotoSansMono', size=10)
            self.utf8_enabled = True
            print(f"Success: Loaded local font {FONT_NAME}")
        except Exception as e:
            print(f"Error loading local font: {e}")
            self._fallback_to_standard_font()

    def _fallback_to_standard_font(self):
        self.pdf.set_font("Courier", size=10)
        self.utf8_enabled = False

    def _prepare_content(self, text: str) -> str:
        """Sanitizes, Scrubs, and Filters Unsupported Glyphs."""
        # 1. Security Scrub
        text = scrub_secrets(text)
        
        # 2. Track Volume
        self.total_chars += len(text)
        
        if self.utf8_enabled:
            # 3. Aggressive Glyph Filtering
            # We must filter characters that NotoSansMono doesn't support to prevent crashes.
            # This allows Code + Box Drawing (Tree) but kills Emojis/Dingbats.
            
            def is_safe_char(c):
                code = ord(c)
                # Filter SMP (Standard Emojis > 65535)
                if code > 0xFFFF: return False
                # Filter Dingbats & Symbols (Checkmarks, warnings, etc.)
                if 0x2600 <= code <= 0x26FF: return False  # Misc Symbols (e.g. ⚠)
                if 0x2700 <= code <= 0x27BF: return False  # Dingbats (e.g. ✅, ❌)
                if 0xFE00 <= code <= 0xFE0F: return False  # Variation Selectors
                return True

            text = ''.join(c if is_safe_char(c) else '?' for c in text)
            
            # 4. Safe Encode
            return text.replace('\0', '').encode('utf-8', 'replace').decode('utf-8')
            
        else:
            # Fallback for standard font
            return text.encode('latin-1', 'replace').decode('latin-1')

    def render(self, file_data: List[Tuple[str, str]], output_path: str):
        print(f"Initializing PDF generation for {len(file_data)} files...")
        effective_width = self.pdf.epw
        
        # --- 1. TREE VIEW ---
        print("Generating project tree...")
        paths_only = [f[0] for f in file_data]
        project_tree = generate_ascii_tree(paths_only)
        
        intro = (
            "CONTEXT: PROJECT STRUCTURE\n"
            "Below is the file tree. Use this to understand module relationships.\n\n"
        )
        self.pdf.set_x(self.pdf.l_margin)
        self.pdf.set_font(family=None, style='B')
        self.pdf.multi_cell(w=effective_width, h=5, txt=intro)
        
        self.pdf.set_font(family=None, style='')
        clean_tree = self._prepare_content(project_tree)
        self.pdf.multi_cell(w=effective_width, h=5, txt=clean_tree)
        self.pdf.add_page()

        # --- 2. FILE CONTENT ---
        for path, content in file_data:
            clean_content = self._prepare_content(content)
            header = f"\n--- START_FILE: {path} ---\n"
            
            if self.pdf.get_y() > (self.pdf.h - self.pdf.b_margin - 20):
                self.pdf.add_page()
            
            self.pdf.set_x(self.pdf.l_margin)
            self.pdf.set_font(family=None, style='B')
            self.pdf.multi_cell(w=effective_width, h=5, txt=header)
            self.pdf.set_font(family=None, style='')
            
            chunk_size = 10000 
            if len(clean_content) > chunk_size:
                for i in range(0, len(clean_content), chunk_size):
                    chunk = clean_content[i:i+chunk_size]
                    self.pdf.set_x(self.pdf.l_margin)
                    self.pdf.multi_cell(w=effective_width, h=5, txt=chunk)
            else:
                self.pdf.set_x(self.pdf.l_margin)
                self.pdf.multi_cell(w=effective_width, h=5, txt=clean_content)

            footer = "\n--- END_FILE ---\n"
            self.pdf.set_x(self.pdf.l_margin)
            self.pdf.multi_cell(w=effective_width, h=5, txt=footer)

        # --- 3. INJECT DIGITAL TWIN MANIFEST ---
        # Hidden but extractable for perfect fidelity restoration
        print("Injecting restoration manifest...")
        try:
            # Create a dictionary of { "rel/path": "raw_content" }
            # Use raw content to preserve perfect fidelity (no scrubbing/glyph filtering)
            manifest = {path: content for path, content in file_data}
            
            # Compress and Encode
            json_bytes = json.dumps(manifest).encode('utf-8')
            compressed = zlib.compress(json_bytes)
            b64_payload = base64.b64encode(compressed).decode('utf-8')
            
            # Append to PDF as a hidden block (white text, 1pt font)
            # This makes it invisible visually but still extractable from PDF text layer
            self.pdf.add_page()
            self.pdf.set_font("Courier", size=1)  # Tiny font
            self.pdf.set_text_color(255, 255, 255)  # White text (invisible on white background)
            
            # Compute SHA-256 checksum for integrity validation (ECR #006 enhancement)
            checksum = hashlib.sha256(b64_payload.encode('utf-8')).hexdigest()
            
            header = "--- VIBECODE_RESTORE_BLOCK_START ---\n"
            footer = "\n--- VIBECODE_RESTORE_BLOCK_END ---"
            
            # Format: sha256:<checksum>\n<payload>
            manifest_block = f"sha256:{checksum}\n{b64_payload}"
            
            # Write the hidden block
            self.pdf.multi_cell(w=effective_width, h=1, txt=header + manifest_block + footer)
            
            # Reset text color for any subsequent content
            self.pdf.set_text_color(0, 0, 0)
            
        except Exception as e:
            print(f"Warning: Failed to inject manifest: {e}")

        # --- 4. SUMMARY & SAVE ---
        print(f"Writing PDF to {output_path}...")
        try:
            self.pdf.output(output_path)
            
            est_tokens = self.total_chars // 4
            
            print("-" * 40)
            print(f"DONE. Snapshot Stats:")
            print(f"   - Files: {len(file_data)}")
            print(f"   - Approx. Tokens: {est_tokens:,}")
            
            if est_tokens > 128000:
                print("   WARNING: Exceeds typical 128k context window.")
            elif est_tokens > 32000:
                print("   INFO: Fits comfortably in GPT-4 / Claude 3.")
            else:
                print("   OK: Fits in nearly all modern LLMs.")
            print("-" * 40)
            
        except Exception as e:
            print(f"Error writing PDF: {e}")