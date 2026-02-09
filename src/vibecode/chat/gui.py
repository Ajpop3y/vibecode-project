
"""
VibeChat GUI - PyQt6 Chat Interface for the VibeChat engine.
Provides message bubbles, source node panel, and threaded LLM interaction.
"""

import os
import re
import logging
import platform
import subprocess
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QEvent, QTimer
from PyQt6.QtGui import QPalette, QColor, QAction, QIcon, QFont, QDesktopServices, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QListWidget, QTextEdit, 
    QSplitter, QFrame, QSizePolicy, QListWidgetItem, QComboBox,
    QTextBrowser, QScrollArea, QToolButton, QDialog, QFormLayout,
    QDialogButtonBox, QMessageBox, QFileDialog, QTabWidget
)

from .engine import ChatEngine
from ..agents.mcp_agent import MCPAgent
from ..gui.dialogs import ModelSettingsDialog
from ..settings import get_settings

logger = logging.getLogger(__name__)

# Try to import markdown for rich text rendering
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    logger.warning("markdown not installed. Rich text disabled. Install with: pip install markdown")


# User Settings removed (using shared ModelSettingsDialog)

# --- Implementation Drafter: Patch Widget ---
class PatchWidget(QFrame):
    """
    A widget that displays code and an 'Apply' button.
    Writes changes directly to disk when clicked, with backup.
    """
    def __init__(self, filename: str, code_content: str, project_root: str = None, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.code_content = code_content.strip()
        self.project_root = project_root or os.getcwd()
        
        # Style
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #1E1E1E;
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                margin-top: 10px;
                margin-bottom: 10px;
            }
            QLabel {
                color: #888;
                font-family: 'Segoe UI', sans-serif;
                font-weight: bold;
                border: none;
            }
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                font-family: 'Consolas', monospace;
                border: none;
            }
            QPushButton {
                background-color: #2E8B57;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #3CB371;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- Header (Filename + Apply Button) ---
        header = QWidget()
        header.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3C3C3C; border-top-left-radius: 8px; border-top-right-radius: 8px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        lbl_file = QLabel(f"📄 {self.filename}")
        
        self.btn_apply = QPushButton("Apply Fix")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self.apply_patch)
        
        header_layout.addWidget(lbl_file)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_apply)
        
        layout.addWidget(header)
        
        # --- Code View ---
        self.code_view = QTextEdit()
        self.code_view.setPlainText(self.code_content)
        self.code_view.setReadOnly(True)
        # Auto-height heuristic
        line_count = self.code_content.count('\n') + 1
        height = min(300, max(100, line_count * 18))
        self.code_view.setFixedHeight(height)
        
        layout.addWidget(self.code_view)
    
    def apply_patch(self):
        """Writes the code to the file with backup."""
        # 1. Confirm
        reply = QMessageBox.question(
            self,
            "Apply Patch",
            f"Are you sure you want to overwrite '{self.filename}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return
        
        # 2. Safety Check: Path Traversal
        if ".." in self.filename or self.filename.startswith("/") or self.filename.startswith("\\"):
            QMessageBox.critical(self, "Error", "Invalid file path.")
            return
        
        # 3. Write File
        try:
            abs_path = os.path.join(self.project_root, self.filename)
            
            # Create backup
            if os.path.exists(abs_path):
                with open(abs_path, 'r', encoding='utf-8') as f:
                    backup = f.read()
                with open(abs_path + ".bak", 'w', encoding='utf-8') as f:
                    f.write(backup)
            
            # Write new content
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(self.code_content)
            
            QMessageBox.information(self, "Success", f"Updated {self.filename}.\n(Backup saved as .bak)")
            self.btn_apply.setText("Applied ✔")
            self.btn_apply.setDisabled(True)
            self.btn_apply.setStyleSheet("background-color: #555; color: #AAA;")
            
        except Exception as e:
            logger.error(f"Failed to apply patch: {e}")
            QMessageBox.critical(self, "Write Error", str(e))


# --- Background Worker with Streaming ---
class ChatWorker(QThread):
    """
    Runs AI inference in a background thread to keep UI responsive.
    Supports both blocking and streaming modes.
    """
    response_ready = pyqtSignal(str, str)  # query, response (blocking mode)
    chunk_received = pyqtSignal(str)  # partial text chunk (streaming mode)
    stream_finished = pyqtSignal(str)  # full response (streaming complete)
    error_occurred = pyqtSignal(str)  # error message

    def __init__(self, engine: ChatEngine, query: str, use_mock: bool = False, streaming: bool = False):
        super().__init__()
        self.engine = engine
        self.query = query
        self.use_mock = use_mock
        self.streaming = streaming

    def run(self):
        try:
            if self.use_mock:
                response = self.engine.mock_chat_response(self.query)
                self.response_ready.emit(self.query, response)
            elif self.streaming and self.engine.provider:
                # Streaming mode
                full_response = ""
                for chunk in self.engine.stream_message(self.query):
                    full_response += chunk
                    self.chunk_received.emit(chunk)
                self.stream_finished.emit(full_response)
            else:
                # Blocking mode
                response = self.engine.send_message(self.query)
                self.response_ready.emit(self.query, response)
        except Exception as e:
            logger.error(f"ChatWorker error: {e}")
            self.error_occurred.emit(str(e))


# --- Enhanced Chat Bubble with Markdown ---
# --- CUSTOM WIDGETS ---

class AutoResizingTextBrowser(QTextBrowser):
    """
    A QTextBrowser that automatically adjusts its height to fit its content.
    Fixes the truncation issue by recalculating height on resize and content change.
    """
    preferredHeightChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)  # Disable ALL internal navigation
        self.setOpenExternalLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.document().documentLayout().documentSizeChanged.connect(self._adjust_height)

    def _adjust_height(self):
        """Recalculate height based on document size."""
        doc_height = self.document().size().height()
        new_height = int(doc_height + 10)
        self.setFixedHeight(new_height)
        self.preferredHeightChanged.emit(new_height)

    def resizeEvent(self, event):
        """Handle resize events to adjust height."""
        super().resizeEvent(event)
        self._adjust_height()

    def setSource(self, url: QUrl):
        """
        Override default navigation to do NOTHING.
        This prevents the browser from clearing content when clicking a 'vibe://' link.
        """
        pass


class ThinkingWidget(QFrame):
    """
    Collapsible widget to display AI reasoning traces (<think> tags).
    """
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ThinkingWidget {
                background-color: #252526;
                border: 1px solid #333;
                border-radius: 8px;
                margin-bottom: 8px;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header (Clickable to toggle)
        self.header = QPushButton()
        self.header.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                text-align: left;
                padding: 8px;
                color: #888;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #CCC;
                background-color: #2D2D2D;
            }
        """)
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.clicked.connect(self.toggle_content)
        self.layout.addWidget(self.header)
        
        # Content Area
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(12, 0, 12, 12)
        
        self.text_view = AutoResizingTextBrowser()
        self.text_view.setStyleSheet("color: #AAA; background-color: transparent; font-family: Consolas, monospace; font-size: 9pt;")
        self.text_view.setHtml(f"<pre style='white-space: pre-wrap;'>{text}</pre>")
        self.content_layout.addWidget(self.text_view)
        
        self.layout.addWidget(self.content_area)
        
        # Initial state: Collapsed
        self.is_expanded = False
        self.content_area.setVisible(False)
        self.update_header()

    def update_text(self, text: str):
        """Update reasoning text (for streaming)."""
        self.text_view.setHtml(f"<pre style='white-space: pre-wrap;'>{text}</pre>")

    def toggle_content(self):
        """Toggle visibility of the reasoning content."""
        self.is_expanded = not self.is_expanded
        self.content_area.setVisible(self.is_expanded)
        self.update_header()

    def update_header(self):
        """Update header text and icon based on state."""
        icon = "▼" if self.is_expanded else "▶"
        self.header.setText(f"{icon} Thinking Process")


class ChatBubble(QFrame):
    """
    A styled message bubble widget with markdown rendering.
    User messages appear on the right (green), AI messages on the left (gray).
    Supports clickable [[REF: path]] citations.
    """
    # Signal to open file (connect to parent)
    file_open_requested = pyqtSignal(str)
    # Signal to adjust size (connect to parent list item)
    adjust_size_signal = pyqtSignal(int)
    
    def __init__(self, text: str, is_user: bool = False, project_root: str = None, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.project_root = project_root or os.getcwd()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setLineWidth(0)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        if MARKDOWN_AVAILABLE and not is_user:
            # Use AutoResizingTextBrowser for rich text
            self.text_view = AutoResizingTextBrowser()
            self.text_view.anchorClicked.connect(self._handle_link_click)
            self.text_view.preferredHeightChanged.connect(self.adjust_size_signal.emit)
            
            # Render markdown to HTML
            html_content = self._render_markdown(text)
            self.text_view.setHtml(html_content)
            
            layout.addWidget(self.text_view)
        else:
            # Plain text label (for user messages mostly, or fallback)
            # PRO TIP: Even for user messages, AutoResizingTextBrowser is better for multiline
            if is_user:
                self.label = QLabel(text)
                self.label.setWordWrap(True)
                self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                font = QFont()
                font.setPointSize(10)
                self.label.setFont(font)
                layout.addWidget(self.label)
            else:
                 # Should theoretically be covered by the block above, but good fallback
                self.label = QLabel(text)
                layout.addWidget(self.label)
        
        # Apply styling
        if is_user:
            self.setStyleSheet("""
                QFrame {
                    background-color: #2E8B57; 
                    border-radius: 12px;
                }
                QLabel, QTextBrowser { color: white; background: transparent; }
            """)
            layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #3C3C3C; 
                    border-radius: 12px;
                }
                QLabel, QTextBrowser { color: #E0E0E0; background: transparent; }
            """)
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    
    def _render_markdown(self, text: str) -> str:
        """Convert markdown + [[REF:]] citations to HTML."""
        # 1. Convert [[REF: file.py]] to clickable links
        text = re.sub(r"\[\[REF:\s*(.*?)\]\]", r"[`\1`](vibe://\1)", text)
        
        # 2. Convert markdown to HTML
        html = markdown.markdown(text, extensions=['fenced_code', 'tables'])
        
        # 3. Inject CSS for code blocks
        css = """
        <style>
            code { 
                background-color: #1E1E1E; 
                color: #D4D4D4; 
                font-family: 'Consolas', 'Courier New', monospace;
                padding: 2px 4px;
                border-radius: 4px;
            }
            pre {
                background-color: #1E1E1E;
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #444;
                overflow-x: auto;
            }
            a {
                color: #4EC9B0;
                text-decoration: none;
                font-weight: bold;
            }
            p { margin: 5px 0; }
        </style>
        """
        return css + html
    
    def _handle_link_click(self, url: QUrl):
        """Handle clicks on links in the bubble."""
        path = url.toString()
        
        if path.startswith("vibe://"):
            # Custom file link
            file_path = path.replace("vibe://", "")
            self._open_file(file_path)
        else:
            # Normal web link
            QDesktopServices.openUrl(url)
    
    def _open_file(self, file_path: str):
        """Open file in default application."""
        abs_path = os.path.join(self.project_root, file_path)
        
        if not os.path.exists(abs_path):
            abs_path = os.path.abspath(file_path)
        
        if not os.path.exists(abs_path):
            logger.warning(f"File not found: {file_path}")
            return
        
        try:
            if platform.system() == "Windows":
                os.startfile(abs_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", abs_path])
            else:
                subprocess.Popen(["xdg-open", abs_path])
        except Exception as e:
            logger.error(f"Error opening file: {e}")
    
    def set_text(self, text: str):
        """Update bubble text (for streaming)."""
        if hasattr(self, 'text_view') and MARKDOWN_AVAILABLE:
            html = self._render_markdown(text)
            self.text_view.setHtml(html)
            doc_height = self.text_view.document().size().height()
            self.text_view.setFixedHeight(int(doc_height + 15))
        elif hasattr(self, 'label'):
            self.label.setText(text)


# --- Source Node Item ---
class SourceNodeItem(QListWidgetItem):
    """
    Custom list item representing a cited file (Source Node).
    Stores the filename and displays with a file icon.
    """
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self.setText(f"📄 {filename}")
        self.setToolTip(f"Click to open: {filename}")
        

# --- Main Chat Window ---
class ChatWindow(QMainWindow):
    """
    Main VibeChat interface window.
    Features:
    - Left panel: Chat history with message bubbles
    - Right panel: Source Nodes extracted from [[REF: path]] tags
    - Input area with send button
    - Status bar showing token count and mode
    """
    
    def __init__(self, pdf_path: str, project_root: str = None, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self.setWindowTitle("VibeChat: Project Assistant")
        self.resize(1400, 950)  # Larger default size
        self.pdf_path = pdf_path
        self.project_root = project_root or os.path.dirname(pdf_path)
        
        # Initialize Engine
        self.engine: Optional[ChatEngine] = None
        self.token_count = 0
        self.use_mock = True  # Default to mock mode for Phase 2
        
        try:
            logger.info(f"Initializing ChatEngine with PDF: {pdf_path}")
            self.engine = ChatEngine(pdf_path)
            self.token_count = self.engine.context.total_tokens
            # Check if we have a real provider
            self.use_mock = self.engine.provider is None
            logger.info(f"ChatWindow ready: {self.token_count} tokens, mock={self.use_mock}")
        except Exception as e:
            logger.error(f"Engine initialization failed: {e}")
            self.token_count = 0
            self.use_mock = True
        
        self.worker: Optional[ChatWorker] = None
        self.init_ui()
        
        # Set initial tab
        if hasattr(self, 'tabs'):
            self.tabs.setCurrentIndex(initial_tab)

    def init_ui(self):
        """Build the chat interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # --- SPLITTER: Chat | Sources ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # ================= LEFT: Chat Area =================
        chat_panel = QWidget()
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(0, 0, 5, 0)
        chat_layout.setSpacing(10)
        
        # --- TIME TRAVEL HEADER ---
        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(0, 0, 0, 0)
        
        self.btn_time_travel = QPushButton("⏱ Time Travel")
        self.btn_time_travel.setToolTip("Load a previous snapshot PDF to compare changes")
        self.btn_time_travel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_time_travel.setStyleSheet("""
            QPushButton {
                background-color: #3C3C3C;
                color: #88C;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
        """)
        self.btn_time_travel.clicked.connect(self.select_snapshot)
        header_bar.addWidget(self.btn_time_travel)
        
        self.lbl_comparison = QLabel("")
        self.lbl_comparison.setStyleSheet("color: #888; font-style: italic;")
        header_bar.addWidget(self.lbl_comparison)
        
        # --- PERSONA SELECTOR ---
        self.combo_persona = QComboBox()
        self.combo_persona.addItems([
            "General Assistant", 
            "The Architect", 
            "The Debugger", 
            "The Doc Writer"
        ])
        self.combo_persona.setToolTip("Select AI Persona")
        self.combo_persona.setStyleSheet("""
            QComboBox {
                background-color: #333;
                color: #EEE;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 10px;
                min-width: 130px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #333;
                color: #EEE;
                selection-background-color: #555;
            }
        """)
        self.combo_persona.currentTextChanged.connect(self.change_persona)
        header_bar.addWidget(self.combo_persona)
        
        header_bar.addStretch()
        
        chat_layout.addLayout(header_bar)
        
        # --- TABS (Project Chat vs MCP Expert) ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1E1E1E;
            }
            QTabBar::tab {
                background-color: #252526;
                color: #888;
                padding: 8px 15px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1E1E1E;
                color: #D4D4D4;
                font-weight: bold;
                border-top: 2px solid #007ACC;
            }
            QTabBar::tab:hover {
                background-color: #2D2D2D;
            }
        """)
        
        # Tab 1: Project Chat
        self.chat_list = QListWidget()
        self.chat_list.setStyleSheet("background-color: #1E1E1E; border: none;")
        self.chat_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.chat_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.tabs.addTab(self.chat_list, "Project Chat")
        
        # Tab 2: MCP Expert
        self.mcp_list = QListWidget()
        self.mcp_list.setStyleSheet("background-color: #1E1E1E; border: none;")
        self.mcp_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.mcp_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.tabs.addTab(self.mcp_list, "MCP Expert")
        
        chat_layout.addWidget(self.tabs)
        
        # Legacy reference for compatibility (points to main chat)
        self.msg_list = self.chat_list 
        
        # Initialize MCP Agent
        self.mcp_agent = MCPAgent()
        
        # 2. Input Area
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 5, 0, 0)
        input_layout.setSpacing(8)
        
        # Settings button
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(40, 60)
        self.btn_settings.setToolTip("Settings: Configure API keys")
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border-radius: 8px;
                font-size: 16pt;
            }
            QPushButton:hover { background-color: #666; }
        """)
        self.btn_settings.clicked.connect(self.open_settings)
        input_layout.addWidget(self.btn_settings)
        
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("Ask about your code... (Enter to send, Shift+Enter for new line)")
        self.txt_input.setFixedHeight(60)
        self.txt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #555;
                border-radius: 8px;
                padding: 8px;
                font-size: 10pt;
            }
        """)
        # Install event filter for Enter key handling
        self.txt_input.installEventFilter(self)
        
        self.btn_send = QPushButton("Send")
        self.btn_send.setFixedSize(70, 60)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #2E8B57; 
                color: white; 
                border-radius: 8px; 
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #3CB371;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        self.btn_send.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.txt_input)
        input_layout.addWidget(self.btn_send)
        chat_layout.addWidget(input_container)
        
        # 3. Status Bar
        mode_text = "Mock" if self.use_mock else "Live"
        self.lbl_status = QLabel(f"Context: {self.token_count:,} tokens | Mode: {mode_text}")
        self.lbl_status.setStyleSheet("color: #888; font-size: 9pt; margin-top: 5px;")
        chat_layout.addWidget(self.lbl_status)

        splitter.addWidget(chat_panel)
        
        # ================= RIGHT: Source Nodes Panel =================
        source_panel = QWidget()
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(5, 0, 0, 0)
        
        # Header
        lbl_sources = QLabel("📌 Source Nodes")
        lbl_sources.setStyleSheet("font-weight: bold; font-size: 11pt; color: #2E8B57;")
        source_layout.addWidget(lbl_sources)
        
        # Source list
        self.source_list = QListWidget()
        self.source_list.itemClicked.connect(self.on_source_clicked)
        self.source_list.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                border: 1px solid #333;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:hover {
                background-color: #3E3E42;
            }
        """)
        source_layout.addWidget(self.source_list)
        
        # Hint label
        lbl_hint = QLabel("💡 Click a node to open file.\nThese are files referenced\nin the last response.")
        lbl_hint.setStyleSheet("color: gray; font-style: italic; font-size: 9pt;")
        lbl_hint.setWordWrap(True)
        source_layout.addWidget(lbl_hint)
        
        splitter.addWidget(source_panel)
        splitter.setSizes([650, 250])  # ~72% chat, ~28% sources

        # Welcome message
        self.add_bubble(
            "👋 Hello! I've loaded your project snapshot.\n\n"
            f"📊 **{len(self.engine.context.files) if self.engine else 0} files** | "
            f"**~{self.token_count:,} tokens**\n\n"
            "Ask me anything about your codebase - how features work, debug issues, or explain architecture.",
            is_user=False
        )

    def eventFilter(self, obj, event):
        """Handle Enter key to send message (Shift+Enter for newline)."""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        
        if obj == self.txt_input and event.type() == QEvent.Type.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key.Key_Return:
                if key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter: insert newline
                    return False  # Let default handler process it
                else:
                    # Enter: send message
                    self.send_message()
                    return True
        return super().eventFilter(obj, event)

    def add_bubble(self, text: str, is_user: bool, target_list: QListWidget = None):
        """Add a message bubble (or sequence of bubbles/think-widgets/patches) to the chat history."""
        
        # default to active tab's list if not specified
        if target_list is None:
            if self.tabs.currentIndex() == 1:
                target_list = self.mcp_list
            else:
                target_list = self.chat_list
        
        # For user messages, just add a simple bubble
        if is_user:
            display_text = text.strip()
            item = QListWidgetItem()
            bubble = ChatBubble(display_text, is_user=True, project_root=self.project_root)
            
            # Initial size hint (approximate). The widget will adjust itself.
            item.setSizeHint(bubble.sizeHint())
            
            target_list.addItem(item)
            target_list.setItemWidget(item, bubble)
            
            # Connect resize signal
            bubble.adjust_size_signal.connect(lambda h: self.update_item_height(item, bubble))
            
            target_list.scrollToBottom()
            return

        # --- PARSE AI RESPONSE ---
        # 1. Extract <think>...</think> blocks
        parts = re.split(r'(<think>.*?</think>)', text, flags=re.DOTALL)
        
        for part in parts:
            if not part.strip():
                continue
                
            # Check for thinking block
            think_match = re.match(r'<think>(.*?)</think>', part, re.DOTALL)
            if think_match:
                # Add Thinking Widget
                think_text = think_match.group(1).strip()
                if think_text:
                    item = QListWidgetItem()
                    widget = ThinkingWidget(think_text)
                    item.setSizeHint(QSize(target_list.viewport().width() - 40, 50)) # Collapsed size
                    target_list.addItem(item)
                    target_list.setItemWidget(item, widget)
                continue

            # 2. Extract <patch> nodes from the remaining text
            sub_parts = re.split(r'(<patch file=".*?">.*?</patch>)', part, flags=re.DOTALL)
            
            for sub_part in sub_parts:
                if not sub_part.strip():
                    continue
                
                # Check for patch block
                patch_match = re.match(r'<patch file="(.*?)">(.*?)</patch>', sub_part, re.DOTALL)
                
                if patch_match:
                    # It's a patch! Add a PatchWidget
                    filename = patch_match.group(1)
                    code = patch_match.group(2)
                    
                    item = QListWidgetItem()
                    widget = PatchWidget(filename, code, project_root=self.project_root)
                    
                    # Calculate height based on code view
                    item.setSizeHint(QSize(
                        target_list.viewport().width() - 20,
                        widget.code_view.height() + 60
                    ))
                    
                    target_list.addItem(item)
                    target_list.setItemWidget(item, widget)
                    continue
                
                # It's a normal text bubble
                display_text = sub_part.strip()
                if not display_text:
                    continue
                    
                item = QListWidgetItem()
                bubble = ChatBubble(display_text, is_user=False, project_root=self.project_root)
                
                # MCP Expert: Add Save Button if content looks like data
                if target_list == self.mcp_list:
                    if "```" in display_text or "Content of" in display_text:
                        self._add_save_button_to_bubble(bubble, display_text)

                item.setSizeHint(bubble.sizeHint())
                target_list.addItem(item)
                target_list.setItemWidget(item, bubble)
                
                # Connect resize signal
                bubble.adjust_size_signal.connect(lambda h: self.update_item_height(item, bubble))
                # Extract sources from this part
                self.extract_sources(sub_part)
        
        target_list.scrollToBottom()

    def update_item_height(self, item: QListWidgetItem, widget: QWidget):
        # Update the item size hint based on the widget's new size
        item.setSizeHint(widget.sizeHint())
        if item.listWidget():
             item.listWidget().doItemsLayout()

    def _add_save_button_to_bubble(self, bubble, text):
        """Add a 'Save to Project' button to an MCP bubble."""
        btn = QPushButton("💾 Save to Project")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("background-color: #2E8B57; color: white; border-radius: 4px; padding: 4px; margin-top: 5px;")
        
        # Define the save logic locally to capture text
        def save_logic():
            # Extract content
            content = ""
            filename = "mcp_download.txt"
            
            name_match = re.search(r'(?:File|Reading|Content of)\s+[`"\']?([a-zA-Z0-9_./-]+)[`"\']?', text, re.IGNORECASE)
            if name_match:
                filename = os.path.basename(name_match.group(1))
            
            code_match = re.search(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
            if code_match:
                content = code_match.group(1)
            else:
                content = text

            if not content.strip():
                return

            default_path = os.path.join(self.project_root, filename)
            path, _ = QFileDialog.getSaveFileName(self, "Save File", default_path)
            if path:
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    QMessageBox.information(self, "Saved", f"File saved to {os.path.basename(path)}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not save: {e}")

        btn.clicked.connect(save_logic)
        bubble.layout().addWidget(btn)

    def extract_sources(self, text: str):
        """
        Parse [[REF: path]] tags from text and populate Source Nodes panel.
        Clears previous sources and shows unique references.
        """
        refs = re.findall(r"\[\[REF:\s*(.*?)\]\]", text)
        self.source_list.clear()
        
        unique_refs = sorted(set(refs))
        for ref in unique_refs:
            self.source_list.addItem(SourceNodeItem(ref))
        
        # Visual feedback when sources are found
        if unique_refs:
            self.source_list.setStyleSheet("""
                QListWidget {
                    background-color: #252526;
                    border: 2px solid #2E8B57;
                    border-radius: 5px;
                }
                QListWidget::item { padding: 5px; }
                QListWidget::item:hover { background-color: #3E3E42; }
            """)
            logger.info(f"Extracted {len(unique_refs)} source nodes")
        else:
            self.source_list.setStyleSheet("""
                QListWidget {
                    background-color: #252526;
                    border: 1px solid #333;
                    border-radius: 5px;
                }
            """)

    def open_settings(self):
        """Open the unified settings dialog."""
        # Settings are loaded internally by the dialog
        dlg = ModelSettingsDialog(self)
        if dlg.exec():
            # Settings updated!
            # ChatEngine auto-reloads provider on next message (thanks to previous fix),
            # but we might want to update status label immediately.
            
            # Re-check engine provider status (force a peek?)
            # Actually ChatEngine only reloads when sending message.
            # We can force invalidation or just assume active.
            
            # Update UI status
            is_mock = False # If they saved settings, assume live? 
            # Ideally ask engine to re-init NOW.
            if self.engine:
                self.engine._init_provider() # Force reload
                self.use_mock = self.engine.provider is None
                
            mode_text = "Mock" if self.use_mock else "Live"
            self.lbl_status.setText(f"Context: {self.token_count:,} tokens | Mode: {mode_text}")
    
    def select_snapshot(self):
        """Open file dialog to select a reference PDF for Time Travel comparison."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Snapshot PDF for Comparison",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        
        if not file_path:
            return
        
        if not self.engine:
            QMessageBox.warning(self, "Error", "Chat engine not initialized")
            return
        
        # Load the reference context
        success = self.engine.load_reference(file_path)
        
        if success:
            filename = os.path.basename(file_path)
            self.lbl_comparison.setText(f"Comparing vs: {filename}")
            self.btn_time_travel.setText("⏱ Active")
            self.btn_time_travel.setStyleSheet("""
                QPushButton {
                    background-color: #2E8B57;
                    color: white;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3CB371;
                }
            """)
            
            # Add system announcement
            self.add_bubble(
                f"⏱ **TIME TRAVEL MODE ACTIVATED**\n"
                f"Comparing current code against snapshot: **{filename}**\n"
                "Ask me about changes, regressions, or what's different!",
                is_user=False
            )
        else:
            QMessageBox.critical(self, "Error", f"Failed to load snapshot: {file_path}")
    
    def change_persona(self, text: str):
        """Handle persona dropdown change - update engine and provide visual feedback."""
        if not self.engine:
            return
        
        self.engine.set_persona(text)
        
        # Visual Feedback
        self.add_bubble(f"**Persona Switched:** I am now *{text}*. How can I help?", is_user=False)
        
        # Change status color based on persona
        if text == "The Debugger":
            self.lbl_status.setStyleSheet("color: #FF5555; font-weight: bold;")  # Red for bugs
        elif text == "The Architect":
            self.lbl_status.setStyleSheet("color: #55AAFF; font-weight: bold;")  # Blue for structure
        elif text == "The Doc Writer":
            self.lbl_status.setStyleSheet("color: #55FF55; font-weight: bold;")  # Green for docs
        else:
            self.lbl_status.setStyleSheet("color: #888; font-weight: normal;")

    def send_message(self):
        """Send user query to the engine."""
        query = self.txt_input.toPlainText().strip()
        if not query:
            return
            
        # Select Engine based on Tab
        if self.tabs.currentIndex() == 1:
            active_engine = self.mcp_agent
            target_list = self.mcp_list
        else:
            active_engine = self.engine
            target_list = self.chat_list
            
        # Add user message
        self.add_bubble(query, is_user=True, target_list=target_list)
        self.txt_input.clear()
        
        # Disable input while processing
        self.txt_input.setDisabled(True)
        self.btn_send.setDisabled(True)
        
        if self.tabs.currentIndex() == 0:
            # --- STACK TRACE DETECTION STATUS (Project Chat only) ---
            priority_files = self.engine.detect_stack_trace(query)
            if priority_files:
                file_list = ", ".join([os.path.basename(f) for f in priority_files[:3]])
                self.lbl_status.setText(f"🔥 Analyzing crash in: {file_list}")
                self.lbl_status.setStyleSheet("color: #FF5555; font-weight: bold;")
            else:
                self.lbl_status.setText("🤔 VibeChat is thinking...")
                self.lbl_status.setStyleSheet("color: #888; font-weight: normal;")
        else:
             self.lbl_status.setText("🛠️ MCP Agent is working...")
        
        # Determine if we should use streaming (only if we have a provider)
        use_streaming = not self.use_mock and self.engine.provider is not None
        
        if use_streaming:
            # Create streaming placeholder bubble
            self.current_stream_text = ""
            self.stream_bubble = ChatBubble("", is_user=False, project_root=self.project_root)
            item = QListWidgetItem()
            self.stream_item = item
            target_list.addItem(item)
            target_list.setItemWidget(item, self.stream_bubble)
            target_list.scrollToBottom()
        
        # Start background worker
        self.worker = ChatWorker(
            active_engine, query, 
            use_mock=self.use_mock, 
            streaming=use_streaming
        )
        self.worker.response_ready.connect(self.handle_response)
        self.worker.chunk_received.connect(self.handle_stream_chunk)
        self.worker.stream_finished.connect(self.handle_stream_finished)
        self.worker.error_occurred.connect(self.handle_error)
        self.worker.start()
    
    def run(self):
        try:
            if self.use_mock:
                # Simulate streaming for mock mode too, for better UI testing
                response = self.engine.mock_chat_response(self.query)
                # Split into chunks for simulation
                chunk_size = 10
                for i in range(0, len(response), chunk_size):
                    chunk = response[i:i+chunk_size]
                    self.chunk_received.emit(chunk)
                    self.msleep(50) # Simulate network delay
                self.stream_finished.emit(response)
                
            elif self.streaming and self.engine.provider:
                # Streaming mode
                full_response = ""
                for chunk in self.engine.stream_message(self.query):
                    full_response += chunk
                    self.chunk_received.emit(chunk)
                self.stream_finished.emit(full_response)
            else:
                # Blocking mode
                response = self.engine.send_message(self.query)
                self.response_ready.emit(self.query, response)
        except Exception as e:
            logger.error(f"ChatWorker error: {e}")
            self.error_occurred.emit(str(e))


    def handle_stream_chunk(self, chunk: str):
        """Handle incoming stream chunk - update streaming bubble."""
        if hasattr(self, 'stream_bubble') and self.stream_bubble:
            self.current_stream_text += chunk
            # If we are in the middle of a <think> block, we might want to suppress it or show it differently?
            # For now, just show raw text. usage of AutoResizingTextBrowser will keep it visible.
            self.stream_bubble.set_text(self.current_stream_text)
            
            # Update item size hint
            # self.stream_bubble.adjustSize() # Force layout update
            self.stream_item.setSizeHint(QSize(
                self.stream_item.listWidget().viewport().width() - 20,
                self.stream_bubble.sizeHint().height() + 10
            ))
            self.stream_item.listWidget().scrollToBottom()
    
    def handle_stream_finished(self, full_text: str):
        """Handle completion of streaming - parse patches and extract sources."""
        self.txt_input.setDisabled(False)
        self.btn_send.setDisabled(False)
        self.txt_input.setFocus()
        
        # Remove the temporary streaming bubble (it's the last item)
        if hasattr(self, 'stream_item') and self.stream_item:
            target_list = self.stream_item.listWidget()
            if target_list:
                row = target_list.row(self.stream_item)
                if row >= 0:
                    target_list.takeItem(row)
        
        # Re-add with parsed patches and proper widgets
        try:
            self.add_bubble(full_text, is_user=False)
        except Exception as e:
            logger.error(f"Error parsing final response: {e}")
            # Fallback: Just show the text as is
            self.msg_list.addItem(f"Error parsing response: {e}")
            # Try to add raw bubble
            try:
                item = QListWidgetItem()
                bubble = ChatBubble(full_text, is_user=False, project_root=self.project_root)
                item.setSizeHint(bubble.sizeHint())
                self.msg_list.addItem(item)
                self.msg_list.setItemWidget(item, bubble)
            except:
                pass
        
        mode_text = "Mock" if self.use_mock else "Live"
        self.lbl_status.setText(f"Context: {self.token_count:,} tokens | Mode: {mode_text}")
        
        # Clean up streaming state
        self.stream_bubble = None
        self.stream_item = None
        self.current_stream_text = ""
        
    def handle_response(self, query: str, response: str):
        """Handle successful LLM response (blocking mode)."""
        self.add_bubble(response, is_user=False)
        self.txt_input.setDisabled(False)
        self.btn_send.setDisabled(False)
        self.txt_input.setFocus()
        
        mode_text = "Mock" if self.use_mock else "Live"
        self.lbl_status.setText(f"Context: {self.token_count:,} tokens | Mode: {mode_text}")
        
    def handle_error(self, error_msg: str):
        """Handle LLM error."""
        self.add_bubble(f"❌ Error: {error_msg}", is_user=False)
        self.txt_input.setDisabled(False)
        self.btn_send.setDisabled(False)
        self.txt_input.setFocus()
        self.lbl_status.setText(f"Error occurred | Context: {self.token_count:,} tokens")

    def on_source_clicked(self, item: SourceNodeItem):
        """Open the clicked source file in the default application."""
        filename = item.filename
        
        # Try to resolve relative path from project root
        abs_path = os.path.join(self.project_root, filename)
        
        if not os.path.exists(abs_path):
            # Try from current working directory
            abs_path = os.path.abspath(filename)
        
        if not os.path.exists(abs_path):
            logger.warning(f"File not found: {filename}")
            self.lbl_status.setText(f"⚠ File not found: {filename}")
            return
        
        logger.info(f"Opening file: {abs_path}")
        
        try:
            if platform.system() == "Windows":
                os.startfile(abs_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", abs_path])
            else:
                subprocess.Popen(["xdg-open", abs_path])
                
            self.lbl_status.setText(f"Opened: {filename}")
        except Exception as e:
            logger.error(f"Error opening file: {e}")
            self.lbl_status.setText(f"⚠ Could not open: {filename}")

    def closeEvent(self, event):
        """Clean up when window closes."""
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        event.accept()

    def resizeEvent(self, event):
        """Handle window resize to update chat bubble widths."""
        super().resizeEvent(event)
        
        # Force update of all item widths in the chat list
        # This ensures bubbles expand to fill the new width
        if hasattr(self, 'msg_list'):
            viewport_width = self.msg_list.viewport().width()
            for i in range(self.msg_list.count()):
                item = self.msg_list.item(i)
                widget = self.msg_list.itemWidget(item)
                if widget:
                    # Keep height the same (or let it auto-calc), update width
                    current_hint = item.sizeHint()
                    # We might need to ask the widget for its preferred height at this new width?
                    # For now just updating width is usually enough if the widget is responsive.
                    # Ideally, we'd call widget.heightForWidth(viewport_width) if it supported it.
                    
                    # For AutoResizingTextBrowser, height might change with width (word wrap).
                    # We can trigger a layout update on the widget.
                    widget.setFixedWidth(viewport_width - 20) # Force widget width
                    # Then get new size hint
                    new_size = widget.sizeHint()
                    item.setSizeHint(QSize(viewport_width - 20, new_size.height() + 10))
            
            # self.msg_list.updateGeometry()
            
            # Update both lists if they exist
            if hasattr(self, 'chat_list'):
                 self.chat_list.updateGeometry()
            if hasattr(self, 'mcp_list'):
                 self.mcp_list.updateGeometry()

