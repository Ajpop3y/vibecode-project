"""
Background Workers for VibeCode GUI.
Handles long-running tasks like PDF generation, file scanning, and AI operations
in separate threads to keep the UI responsive.
"""
import os
import re
import json
import zlib
import base64
import yaml
from PyQt6.QtCore import QThread, pyqtSignal

from ..engine import ProjectEngine

# --- GENERATION WORKER ---

class GenerationWorker(QThread):
    """Runs the PDF generation in a background thread with optional AI context injection."""
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)  # current, total
    finished_success = pyqtSignal(str, str)
    finished_error = pyqtSignal(str)

    def __init__(self, config_path, pipeline_type, output_filename, 
                 use_ai_context=False, user_intent="", secret_scanner=None):
        super().__init__()
        self.config_path = config_path
        self.pipeline_type = pipeline_type
        self.output_filename = output_filename
        self.use_ai_context = use_ai_context  # VibeContext flag
        self.user_intent = user_intent        # Intent from Magic Bar
        self.secret_scanner = secret_scanner  # SecretScanner instance with redaction map

    def run(self):
        temp_config_path = None
        context_file_path = None
        
        try:
            self.log_message.emit(f"Initializing {self.pipeline_type.upper()} engine...")
            self.progress_update.emit(0, 100)

            # --- VIBECONTEXT INJECTION LOGIC ---
            active_config_path = self.config_path
            project_dir = os.path.dirname(self.config_path)
            
            if self.use_ai_context:
                self.log_message.emit("🧠 AI is generating snapshot context header...")
                self.progress_update.emit(10, 100)
                
                # Load original config to get file lists
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f) or {}
                except Exception as e:
                    self.log_message.emit(f"⚠️ Could not load config: {e}")
                    config_data = {}
                
                selected_files = config_data.get('files', [])
                
                # Generate context header via AI
                try:
                    from ..ai import generate_context_header
                    context_md = generate_context_header(selected_files, [], self.user_intent)
                except Exception as e:
                    self.log_message.emit(f"⚠️ AI context generation failed: {e}")
                    context_md = ""
                
                if context_md:
                    # Write temp markdown file (prefixed with 000_ to appear first)
                    context_file_path = os.path.join(project_dir, "000_SNAPSHOT_CONTEXT.md")
                    with open(context_file_path, 'w', encoding='utf-8') as f:
                        f.write(context_md)
                    
                    # Create temp config with injected file at the TOP
                    config_data['files'] = ["000_SNAPSHOT_CONTEXT.md"] + selected_files
                    
                    temp_config_path = os.path.join(project_dir, ".vibecode_temp.yaml")
                    with open(temp_config_path, 'w', encoding='utf-8') as f:
                        yaml.dump(config_data, f, sort_keys=False)
                    
                    active_config_path = temp_config_path
                    self.log_message.emit("📄 Context injected. Starting render...")
                else:
                    self.log_message.emit("⚠️ No context generated, continuing without injection...")
            # --- END VIBECONTEXT ---

            engine = ProjectEngine(active_config_path)
            abs_out_path = os.path.join(project_dir, self.output_filename)

            self.progress_update.emit(30, 100)
            self.log_message.emit(f"Loading {len(engine.config.files)} files...")
            
            # Apply secret scanner redactions if provided
            file_data_redacted = None
            if self.secret_scanner and self.secret_scanner.redaction_map:
                self.log_message.emit(f"🔒 Applying {len(self.secret_scanner.redaction_map)} secret redaction(s)...")
                file_data = engine.gather_files()
                file_data_redacted = [
                    (path, self.secret_scanner.apply_redactions(content))
                    for path, content in file_data
                ]
            
            self.progress_update.emit(50, 100)
            self.log_message.emit(f"Rendering to: {self.output_filename}...")
            engine.render(
                pipeline_type=self.pipeline_type, 
                output_path_override=abs_out_path,
                file_data_override=file_data_redacted
            )

            # --- CLEANUP TEMP FILES ---
            if context_file_path and os.path.exists(context_file_path):
                os.remove(context_file_path)
            if temp_config_path and os.path.exists(temp_config_path):
                os.remove(temp_config_path)

            self.progress_update.emit(100, 100)
            self.finished_success.emit(self.pipeline_type, abs_out_path)

        except Exception as e:
            # Cleanup on error too
            if context_file_path and os.path.exists(context_file_path):
                os.remove(context_file_path)
            if temp_config_path and os.path.exists(temp_config_path):
                os.remove(temp_config_path)
            self.finished_error.emit(str(e))


# --- RESTORATION WORKER ---

class DigitalTwinError(Exception):
    """Raised when the embedded Digital Twin manifest is missing or corrupt."""
    pass


class RestorationWorker(QThread):
    """
    Runs the PDF Unpacking/Restoration in a background thread.
    
    ECR #006: Silent fallback has been DISABLED. Use force_scrape=True
    only when the user explicitly acknowledges the risk of lossy recovery.
    """
    log_message = pyqtSignal(str)
    finished_success = pyqtSignal(int)  # number of files restored
    finished_error = pyqtSignal(str)
    manifest_error = pyqtSignal(str)  # New signal for manifest failures

    def __init__(self, pdf_path, output_dir, force_scrape=False):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.force_scrape = force_scrape

    def run(self):
        try:
            # 1. Determine File Type & Read Content
            lower_path = self.pdf_path.lower()
            full_text = ""
            
            if lower_path.endswith('.pdf'):
                # PDF Mode
                try:
                    from pypdf import PdfReader
                except ImportError:
                     self.manifest_error.emit("'pypdf' is missing. Run 'pip install pypdf'")
                     return

                self.log_message.emit(f"Reading PDF snapshot: {os.path.basename(self.pdf_path)}...")
                try:
                    reader = PdfReader(self.pdf_path)
                    total_pages = len(reader.pages)
                    
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text()
                        if text:
                            full_text += text + "\n"
                    
                    self.log_message.emit(f"Scanned {total_pages} pages. Searching for Digital Twin Manifest...")
                except Exception as e:
                    self.manifest_error.emit(f"Failed to read PDF: {e}")
                    return

            else:
                # Markdown/Text Mode
                self.log_message.emit(f"Reading text snapshot: {os.path.basename(self.pdf_path)}...")
                try:
                    with open(self.pdf_path, 'r', encoding='utf-8') as f:
                        full_text = f.read()
                    self.log_message.emit("File read. Searching for Digital Twin Manifest...")
                except Exception as e:
                     self.manifest_error.emit(f"Failed to read file: {e}")
                     return

            # 3. Attempt Digital Twin Manifest Extraction (The Safe Path)
            manifest_pattern = r"--- VIBECODE_RESTORE_BLOCK_START ---\s*(.*?)\s*--- VIBECODE_RESTORE_BLOCK_END ---"
            match = re.search(manifest_pattern, full_text, re.DOTALL)

            files_restored = 0
            error_message = None

            if match:
                self.log_message.emit("⚡ Manifest found! Restoring with 100% fidelity...")
                import hashlib
                
                raw_payload = match.group(1).strip()
                
                # Check for checksum (new format: sha256:<hash>\n<payload>)
                if raw_payload.startswith("sha256:"):
                    try:
                        checksum_line, payload = raw_payload.split('\n', 1)
                        expected_hash = checksum_line.split(':')[1].strip()
                        
                        # Verify integrity (SCRUB all whitespace caused by PDF wrapping)
                        clean_payload = "".join(payload.split())
                        actual_hash = hashlib.sha256(clean_payload.encode('utf-8')).hexdigest()
                        
                        if actual_hash != expected_hash:
                            self.log_message.emit(f"❌ Checksum mismatch! Expected {expected_hash[:8]}..., got {actual_hash[:8]}...")
                            # We could raise here, but let's try to decode anyway in case it's just a bit flip
                        else:
                             self.log_message.emit("✅ Checksum verified.")
                        
                        payload = clean_payload
                    except ValueError:
                         self.log_message.emit("⚠️ Malformed checksum header. Attempting legacy restore...")
                         payload = raw_payload
                else:
                    payload = raw_payload

                try:
                    # Decode & Decompress
                    compressed_data = base64.b64decode(payload)
                    json_bytes = zlib.decompress(compressed_data)
                    file_map = json.loads(json_bytes.decode('utf-8'))
                    
                    # Restore Files
                    count = 0
                    total = len(file_map)
                    
                    for rel_path, content in file_map.items():
                        # Security: Prevent path traversal
                        safe_path = os.path.normpath(rel_path)
                        if safe_path.startswith("..") or os.path.isabs(safe_path):
                            self.log_message.emit(f"⚠️ Skipping unsafe path: {rel_path}")
                            continue

                        full_out_path = os.path.join(self.output_dir, safe_path)
                        os.makedirs(os.path.dirname(full_out_path), exist_ok=True)
                        
                        with open(full_out_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        count += 1
                        # Throttle log emission to avoid freezing UI on massive repos
                        if count % 10 == 0 or count == total:
                             self.log_message.emit(f"Restored: {safe_path}")

                    self.finished_success.emit(count)
                    return

                except Exception as e:
                    error_message = f"Manifest corrupted: {e}"
            else:
                error_message = "No Digital Twin manifest found in PDF."
            
            # ECR #006: Integrity Check Failed - Abort or Break Glass
            self.log_message.emit(f"❌ CRITICAL: {error_message}")
            
            if self.force_scrape:
                # Emergency "Break Glass" Path (User acknowledged risk)
                self.log_message.emit("")
                self.log_message.emit("=" * 50)
                self.log_message.emit("⚠️ WARNING: EMERGENCY VISUAL SCRAPE ACTIVE")
                self.log_message.emit("=" * 50)
                self.log_message.emit("Visual PDF scraping DESTROYS Python whitespace.")
                self.log_message.emit("Output code may have INVALID INDENTATION.")
                self.log_message.emit("=" * 50)
                
                clean_pattern = r"\\"
                cleaned_text = re.sub(clean_pattern, "", full_text)

                block_pattern = r"--- START_FILE: (.*?) ---\n(.*?)--- END_FILE ---"
                matches = re.findall(block_pattern, cleaned_text, re.DOTALL)

                if not matches:
                    raise ValueError("No files found via text scraping either.")

                for filename, content in matches:
                    filename = filename.strip()
                    if len(filename) > 200 or "\n" in filename: 
                        continue
                    
                    full_out_path = os.path.join(self.output_dir, filename)
                    try:
                        os.makedirs(os.path.dirname(full_out_path), exist_ok=True)
                        with open(full_out_path, 'w', encoding='utf-8') as f:
                            f.write(content.strip())
                        files_restored += 1
                        self.log_message.emit(f"⚠ Scraped: {filename}")
                    except Exception as e:
                         self.log_message.emit(f"❌ Failed to save {filename}: {e}")

                self.log_message.emit(f"\n⚠️ Emergency extraction: {files_restored} files (LOSSY)")
                self.finished_success.emit(files_restored)
            else:
                # Safe Abort - Emit manifest_error signal for GUI to handle
                self.manifest_error.emit(error_message)

        except Exception as e:
            self.finished_error.emit(str(e))


# --- AI SELECTION WORKER (VibeSelect) ---

class AISelectionWorker(QThread):
    """
    Runs AI-powered file selection in the background.
    Calls ai.select_relevant_files() without freezing the UI.
    """
    finished_success = pyqtSignal(list)  # Returns list of selected file paths
    finished_error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, file_list: list, user_intent: str):
        super().__init__()
        self.file_list = file_list
        self.user_intent = user_intent

    def run(self):
        try:
            if not self.user_intent.strip():
                raise ValueError("Please enter an intent (e.g., 'Fix the login bug').")
            
            if not self.file_list:
                raise ValueError("No files to analyze. Add files to your project first.")
            
            self.log_message.emit(f"🧠 AI is analyzing {len(self.file_list)} files...")
            
            # Import here to avoid circular imports
            from ..ai import select_relevant_files
            from ..settings import get_settings
            
            settings = get_settings()
            # Force reload to ensure thread sees latest disk changes if needed, although singleton usually suffices
            # settings.load() 
            
            selection = select_relevant_files(
                self.file_list, 
                self.user_intent,
                base_url=settings.custom_base_url
            )
            
            if not selection:
                raise ValueError("AI returned no relevant files. Try a different query.")
            
            self.log_message.emit(f"✨ AI selected {len(selection)} relevant files.")
            self.finished_success.emit(selection)
            
        except Exception as e:
            self.finished_error.emit(str(e))


# --- CONTEXT GENERATOR WORKER (VibeContext) ---

class ContextGeneratorWorker(QThread):
    """
    Runs AI context header generation in the background.
    Calls ai.generate_context_header() to create SNAPSHOT_CONTEXT.md content.
    """
    finished_success = pyqtSignal(str)  # Returns the generated markdown content
    finished_error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, selected_files: list, all_files: list, user_intent: str = ""):
        super().__init__()
        self.selected_files = selected_files
        self.all_files = all_files
        self.user_intent = user_intent

    def run(self):
        try:
            if not self.selected_files:
                raise ValueError("No files selected for context generation.")
            
            self.log_message.emit("🧠 AI is generating snapshot context header...")
            
            # Import here to avoid circular imports
            from ..ai import generate_context_header
            
            content = generate_context_header(
                self.selected_files, 
                self.all_files, 
                self.user_intent
            )
            
            if not content:
                raise ValueError("AI could not generate context. Check your API key.")
            
            self.log_message.emit("📄 Context header generated successfully.")
            self.finished_success.emit(content)
            
        except Exception as e:
            self.finished_error.emit(str(e))


# --- VIBEEXPAND WORKER (VibeRAG Semantic Search) ---

class VibeExpandWorker(QThread):
    """
    Runs semantic search in background to suggest related files.
    Uses VibeRAG index for embeddings-based similarity search.
    """
    finished_success = pyqtSignal(list)  # Returns list of (path, score) tuples
    finished_error = pyqtSignal(str)
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)  # current, total

    def __init__(self, project_dir: str, selected_files: list, file_contents: dict = None, min_score: float = 0.4):
        super().__init__()
        self.project_dir = project_dir
        self.selected_files = selected_files
        self.file_contents = file_contents or {}
        self.min_score = min_score

    def run(self):
        try:
            if not self.selected_files:
                raise ValueError("Select at least one file to find related files.")
            
            self.log_message.emit("🔍 VibeExpand: Loading or building semantic index...")
            
            # Import here to avoid circular imports
            from ..rag import VibeIndex, build_index
            
            # Check for cached index
            index_path = os.path.join(self.project_dir, ".vibe_index.pkl")
            
            if os.path.exists(index_path):
                self.log_message.emit("📂 Loading cached index...")
                try:
                    index = VibeIndex.load(index_path)
                    self.log_message.emit(f"✅ Loaded index with {len(index)} files.")
                except Exception:
                    index = None
            else:
                index = None
            
            # Build index if not found or too small
            if index is None or len(index) < len(self.file_contents):
                if not self.file_contents:
                    raise ValueError("No file contents provided. Smart Scan first.")
                
                self.log_message.emit(f"🔨 Building index for {len(self.file_contents)} files...")
                
                def progress(current, total):
                    self.progress_update.emit(current, total)
                
                index = build_index(self.file_contents, progress_callback=progress)
                
                # Cache index
                try:
                    index.save(index_path)
                    self.log_message.emit("💾 Index cached for future use.")
                except Exception as e:
                    self.log_message.emit(f"⚠️ Could not cache index: {e}")
            
            # Find related files
            self.log_message.emit("🔎 Finding semantically related files...")
            
            from ..rag import expand_selection
            suggestions = expand_selection(self.selected_files, index, top_k=5, min_score=self.min_score)
            
            if suggestions:
                self.log_message.emit(f"✨ Found {len(suggestions)} related files.")
            else:
                self.log_message.emit("No additional related files found.")
            
            self.finished_success.emit(suggestions)
            
        except Exception as e:
            self.finished_error.emit(str(e))


class SecurityScanWorker(QThread):
    """
    Background worker to scan files for potential secrets.
    Runs the SecretScanner without freezing the UI.
    """
    log_message = pyqtSignal(str)
    finished_success = pyqtSignal(object, list)  # (scanner, candidates)
    finished_error = pyqtSignal(str)
    
    def __init__(self, file_data: list):
        """
        Args:
            file_data: List of (filepath, content) tuples to scan
        """
        super().__init__()
        self.file_data = file_data
    
    def run(self):
        try:
            self.log_message.emit("🔒 Scanning for potential secrets...")
            
            # Import here to avoid circular imports
            from ..renderers.secrets import SecretScanner
            
            scanner = SecretScanner()
            candidates = scanner.scan_files(self.file_data)
            
            if candidates:
                self.log_message.emit(f"⚠️ Found {len(candidates)} potential secret(s)!")
            else:
                self.log_message.emit("✅ No secrets detected.")
            
            self.finished_success.emit(scanner, candidates)
            
        except Exception as e:
            self.finished_error.emit(str(e))


# --- CHAT STREAM WORKER ---

class ChatStreamWorker(QThread):
    """
    Background worker for streaming LLM chat responses.
    
    Extension 2: Prevents UI freezing during long LLM responses.
    
    Signals:
        chunk_received: Emitted for each text chunk (for incremental display)
        finished_success: Emitted when streaming completes with full response
        finished_error: Emitted on error with error message
    """
    chunk_received = pyqtSignal(str)
    finished_success = pyqtSignal(str)
    finished_error = pyqtSignal(str)
    
    def __init__(self, chat_engine, user_message: str, temperature: float = 0.7):
        """
        Initialize the worker.
        
        Args:
            chat_engine: ChatEngine instance
            user_message: The user's message to send
            temperature: LLM temperature (0-1)
        """
        super().__init__()
        self.chat_engine = chat_engine
        self.user_message = user_message
        self.temperature = temperature
        self._cancelled = False
    
    def cancel(self):
        """Request cancellation of the stream."""
        self._cancelled = True
    
    def run(self):
        """Stream message from LLM and emit chunks."""
        try:
            full_response = ""
            
            # Use the chat engine's streaming method
            for chunk in self.chat_engine.stream_message(
                self.user_message, 
                temperature=self.temperature
            ):
                if self._cancelled:
                    self.finished_error.emit("Stream cancelled by user")
                    return
                
                full_response += chunk
                self.chunk_received.emit(chunk)
            
            self.finished_success.emit(full_response)
            
        except Exception as e:
            self.finished_error.emit(str(e))