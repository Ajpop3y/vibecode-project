"""
Main Application Window for VibeCode.
Orchestrates the GUI, project management, and operation workflows.
"""
import os
import sys
import yaml
import shutil
import platform
import subprocess
import threading
import hashlib

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QListWidget, QTextEdit, QGroupBox, QFileDialog, 
                             QSplitter, QStatusBar, QDialog, QCheckBox, 
                             QComboBox, QDialogButtonBox, QPlainTextEdit, QMessageBox,
                             QListWidgetItem, QGridLayout, QFrame, QScrollArea,
                             QMenu, QInputDialog, QColorDialog, QProgressBar,
                             QToolBar, QSizePolicy, QAbstractItemView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QFileSystemWatcher, QTimer
from PyQt6.QtGui import QPalette, QColor, QAction, QShortcut, QKeySequence, QIcon

# --- ROBUST IMPORTS ---
try:
    from .utils import DEFAULT_EXTENSIONS, PROJECT_COLORS, apply_dark_theme, apply_light_theme
    from .workers import GenerationWorker, AISelectionWorker, VibeExpandWorker, SecurityScanWorker
    from .dialogs import ExtensionManagerDialog, ScanDialog, DiffViewDialog, BatchExportDialog, HelpDialog, RestoreDialog, SecretReviewDialog, MCPSettingsDialog, TimeTravelDialog, ModelSettingsDialog
    from ..config import get_active_model_id
    from ..discovery import discover_files
    from ..engine import ProjectEngine
    from ..registry import get_registry, ProjectRegistry
    from ..settings import get_settings
    from ..chat.gui import ChatWindow
except ImportError:
    # Use relative imports when running from installed package
    from .utils import DEFAULT_EXTENSIONS, PROJECT_COLORS, apply_dark_theme, apply_light_theme
    from .workers import GenerationWorker, AISelectionWorker, VibeExpandWorker, SecurityScanWorker
    from .dialogs import ExtensionManagerDialog, ScanDialog, DiffViewDialog, BatchExportDialog, HelpDialog, RestoreDialog, SecretReviewDialog, MCPSettingsDialog, TimeTravelDialog
    
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from discovery import discover_files
    from engine import ProjectEngine
    from registry import get_registry, ProjectRegistry
    from settings import get_settings
    from chat.gui import ChatWindow
    import pathspec
    from pathspec.patterns import GitWildMatchPattern

# --- MAIN WINDOW ---
class FileDropListWidget(QListWidget):
    """ListWidget that accepts file drops from the OS."""
    
    file_dropped = pyqtSignal(list)  # Emits list of file paths
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)  # Fix internal reordering duplication
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragEnterEvent(event)
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragMoveEvent(event)
            
    def dropEvent(self, event):
        # Check if this is an external drop (URLs) AND not from self (to avoid internal moves looking like external drops if they somehow have URLs)
        if event.mimeData().hasUrls() and event.source() != self:
            event.accept()
            files = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    files.append(url.toLocalFile())
            if files:
                self.file_dropped.emit(files)
        else:
            # Internal move or other data
            event.setDropAction(Qt.DropAction.MoveAction)
            super().dropEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vibecode Dashboard")
        self.resize(1000, 650)
        
        self.current_project_root = os.getcwd()
        self.current_config_path = ""
        self.file_list = []
        self.exclude_list = []
        self.included_extensions = DEFAULT_EXTENSIONS.copy()
        
        self.registry = get_registry()
        self.settings = get_settings()
        
        # File System Watcher for Sync
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self.on_config_changed)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 0. Toolbar with Theme Toggle
        self.create_toolbar()

        # 1. Project Section
        self.create_project_section(main_layout)

        # 2. Main Splitter (3-way: Projects | Files | Operations)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left: Saved Projects Panel
        projects_panel = QWidget()
        projects_layout = QVBoxLayout(projects_panel)
        projects_layout.setContentsMargins(0, 0, 5, 0)
        self.create_projects_section(projects_layout)
        splitter.addWidget(projects_panel)

        # Center: Files List
        files_panel = QWidget()
        files_layout = QVBoxLayout(files_panel)
        files_layout.setContentsMargins(5, 0, 5, 0)
        self.create_file_list_section(files_layout)
        splitter.addWidget(files_panel)

        # Right: Operations
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 0, 0, 0)
        self.create_operations_section(right_layout)
        splitter.addWidget(right_panel)
        
        splitter.setSizes([200, 450, 300])

        # 3. Status
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 4. Connections
        self.btn_browse.clicked.connect(self.browse_folder)
        self.btn_reload.clicked.connect(self.load_project)
        self.btn_save.clicked.connect(self.save_project)
        self.btn_add.clicked.connect(self.add_file)
        self.btn_remove.clicked.connect(self.remove_file)
        self.btn_up.clicked.connect(lambda: self.move_item(-1))
        self.btn_down.clicked.connect(lambda: self.move_item(1))
        self.btn_scan.clicked.connect(self.launch_scan)
        self.btn_extensions.clicked.connect(self.open_extension_manager)
        self.btn_human.clicked.connect(lambda: self.run_generation('human'))
        self.btn_llm.clicked.connect(lambda: self.run_generation('llm'))
        
        # Project sidebar connections
        self.btn_add_project.clicked.connect(self.add_current_to_registry)
        self.btn_remove_project.clicked.connect(self.remove_from_registry)
        self.btn_scan_projects.clicked.connect(self.scan_projects_dialog)
        self.list_projects.itemDoubleClicked.connect(self.load_project_from_list)
        self.list_projects.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_projects.customContextMenuRequested.connect(self.show_project_context_menu)
        
        # 5. Keyboard Shortcuts
        self.setup_shortcuts()

        # Init
        self.refresh_project_list()
        self.load_project()

    def on_config_changed(self, path):
        """Handle external changes to .vibecode.yaml."""
        if path == self.current_config_path:
            self.text_log.append("Configuration changed externally. Reloading...")
            self.status_bar.showMessage("Reloading configuration...", 2000)
            # Use QTimer to debounce slightly (editors might write twice)
            QTimer.singleShot(100, self.load_yaml_config)

    def create_toolbar(self):
        """Create toolbar with theme toggle."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Theme toggle
        self.btn_theme = QPushButton("[Dark]" if self.settings.theme == 'dark' else "[Light]")
        self.btn_theme.setToolTip("Toggle dark/light theme (Ctrl+T)")
        self.btn_theme.clicked.connect(self.toggle_theme)
        toolbar.addWidget(self.btn_theme)
        
        toolbar.addSeparator()
        
        # Quick actions
        toolbar.addWidget(QLabel(" Quick: "))
        btn_quick_save = QPushButton("Save (Ctrl+S)")
        btn_quick_save.clicked.connect(self.save_project)
        toolbar.addWidget(btn_quick_save)
        
        btn_quick_gen = QPushButton("Generate (Ctrl+G)")
        btn_quick_gen.clicked.connect(lambda: self.run_generation('human'))
        toolbar.addWidget(btn_quick_gen)
        
        toolbar.addSeparator()
        
        # Advanced features
        self.btn_diff = QPushButton("Diff View")
        self.btn_diff.setToolTip("Show changes since last generation (Ctrl+D)")
        self.btn_diff.clicked.connect(self.show_diff_view)
        toolbar.addWidget(self.btn_diff)
        
        self.btn_batch = QPushButton("Batch Export")
        self.btn_batch.setToolTip("Export multiple projects at once")
        self.btn_batch.clicked.connect(self.show_batch_export)
        toolbar.addWidget(self.btn_batch)

        # Restore / Unpack Button
        self.btn_restore = QPushButton("Restore Snapshot")
        self.btn_restore.setToolTip("Unpack a Vibecode PDF back into source code")
        self.btn_restore.clicked.connect(self.show_restore_dialog)
        toolbar.addWidget(self.btn_restore)
        
        toolbar.addSeparator()
        
        # VibeChat Button
        self.btn_chat = QPushButton("💬 VibeChat")
        self.btn_chat.setToolTip("Chat with your codebase using AI (Ctrl+Shift+C)")
        self.btn_chat.setStyleSheet("font-weight: bold; background-color: #9B59B6; color: white;")
        self.btn_chat.clicked.connect(lambda: self.launch_chat(0))
        toolbar.addWidget(self.btn_chat)

        # MCP Expert Button
        self.btn_mcp_expert = QPushButton("🛠️ MCP Expert")
        self.btn_mcp_expert.setToolTip("Launch directly into MCP Expert mode (Google Drive, etc)")
        self.btn_mcp_expert.setStyleSheet("font-weight: bold; background-color: #2E8B57; color: white;")
        self.btn_mcp_expert.clicked.connect(lambda: self.launch_chat(1))
        toolbar.addWidget(self.btn_mcp_expert)
        
        # MCP Settings Button (Extension 3)
        self.btn_mcp = QPushButton("🔌 MCP")
        self.btn_mcp.setToolTip("Configure MCP server connections (external tools)")
        self.btn_mcp.clicked.connect(self.show_mcp_settings)
        toolbar.addWidget(self.btn_mcp)
        
        # Time Travel Button (Extension 4)
        self.btn_timetravel = QPushButton("⏰ Time Travel")
        self.btn_timetravel.setToolTip("Compare snapshot versions side-by-side")
        self.btn_timetravel.clicked.connect(self.show_time_travel)
        toolbar.addWidget(self.btn_timetravel)
        
        # Model Settings Button (ECR #005)
        self.btn_models = QPushButton("🤖 Models")
        self.btn_models.setToolTip("Configure AI models (Gemini, Ollama, etc.)")
        self.btn_models.clicked.connect(self.show_model_settings)
        toolbar.addWidget(self.btn_models)
        
        # Spacer
        empty = QWidget()
        empty.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        )
        toolbar.addWidget(empty)
        
        # Help Button
        self.btn_help = QPushButton("?")
        self.btn_help.setFixedWidth(30)
        self.btn_help.setToolTip("How to use Vibecode")
        self.btn_help.setStyleSheet("font-weight: bold; background-color: #2E8B57; color: white;")
        self.btn_help.clicked.connect(self.show_help_dialog)
        toolbar.addWidget(self.btn_help)

    def show_help_dialog(self):
        """Show the help dialog."""
        dlg = HelpDialog(self)
        dlg.exec()

    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Save: Ctrl+S
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_project)
        # Generate Human: Ctrl+G
        QShortcut(QKeySequence("Ctrl+G"), self, lambda: self.run_generation('human'))
        # Generate LLM: Ctrl+Shift+G
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, lambda: self.run_generation('llm'))
        # Open/Browse: Ctrl+O
        QShortcut(QKeySequence("Ctrl+O"), self, self.browse_folder)
        # Reload: F5
        QShortcut(QKeySequence("F5"), self, self.load_project)
        # Toggle Theme: Ctrl+T
        QShortcut(QKeySequence("Ctrl+T"), self, self.toggle_theme)
        # Scan: Ctrl+Shift+S
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.launch_scan)
        # Diff View: Ctrl+D
        QShortcut(QKeySequence("Ctrl+D"), self, self.show_diff_view)
        # VibeChat: Ctrl+Shift+C
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self.launch_chat)

    def toggle_theme(self):
        """Toggle between dark and light theme."""
        if self.settings.theme == 'dark':
            self.settings.theme = 'light'
            self.btn_theme.setText("[Light]")
            apply_light_theme(QApplication.instance())
        else:
            self.settings.theme = 'dark'
            self.btn_theme.setText("[Dark]")
            apply_dark_theme(QApplication.instance())
        self.text_log.append(f"Theme switched to {self.settings.theme}")

    def create_project_section(self, parent_layout):
        group = QGroupBox("Target Project Folder")
        layout = QHBoxLayout()
        
        self.input_proj_root = QLineEdit()
        self.input_proj_root.setText(os.getcwd())
        
        self.btn_browse = QPushButton("Browse...")
        self.btn_reload = QPushButton("Reload")
        
        layout.addWidget(self.input_proj_root)
        layout.addWidget(self.btn_browse)
        layout.addWidget(self.btn_reload)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_projects_section(self, parent_layout):
        """Create saved projects sidebar."""
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Saved Projects"))
        self.btn_scan_projects = QPushButton("Scan")
        self.btn_scan_projects.setFixedWidth(50)
        header_layout.addWidget(self.btn_scan_projects)
        parent_layout.addLayout(header_layout)
        
        self.list_projects = QListWidget()
        parent_layout.addWidget(self.list_projects)
        
        btn_layout = QHBoxLayout()
        self.btn_add_project = QPushButton("This ->")
        self.btn_remove_project = QPushButton("<- Remove")
        btn_layout.addWidget(self.btn_add_project)
        btn_layout.addWidget(self.btn_remove_project)
        parent_layout.addLayout(btn_layout)

    def create_file_list_section(self, parent_layout):
        # --- VIBESELECT: Magic Bar (AI Context Scoping) ---
        ai_group = QGroupBox("✨ VibeSelect (AI Context Scoping)")
        ai_layout = QHBoxLayout()
        
        self.input_ai_intent = QLineEdit()
        self.input_ai_intent.setPlaceholderText("Describe your task (e.g., 'Fix PDF rendering')...")
        self.input_ai_intent.setToolTip("Let AI guess which files you need for this task.")
        self.input_ai_intent.returnPressed.connect(self.run_ai_selection)
        
        self.btn_ai_select = QPushButton("Auto-Select")
        self.btn_ai_select.setStyleSheet("""
            QPushButton {
                background-color: #8E44AD; 
                color: white; 
                font-weight: bold;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #9B59B6; }
            QPushButton:disabled { background-color: #666; }
        """)
        self.btn_ai_select.clicked.connect(self.run_ai_selection)
        
        ai_layout.addWidget(self.input_ai_intent)
        ai_layout.addWidget(self.btn_ai_select)
        ai_group.setLayout(ai_layout)
        parent_layout.addWidget(ai_group)
        # --- END VIBESELECT ---
        
        lbl = QLabel("Included Files (Drag to Reorder)")
        lbl.setStyleSheet("font-weight: bold;")
        parent_layout.addWidget(lbl)
        
        self.list_files = FileDropListWidget()
        self.list_files.file_dropped.connect(self.handle_dropped_files)
        # Internal move is handled by the custom widget's dropEvent calling super()
        # when no URLs are present, but we need to ensure DragDropMode is set correctly.
        # The custom widget sets DragDropMode.DragDrop and AcceptDrops(True) in init.
        parent_layout.addWidget(self.list_files)
        
        controls_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add File(s)")
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_scan = QPushButton("Smart Scan")
        self.btn_scan.setStyleSheet("background-color: #4CAF50; color: white;")
        self.btn_extensions = QPushButton("Extensions...")
        
        controls_layout.addWidget(self.btn_add)
        controls_layout.addWidget(self.btn_remove)
        controls_layout.addWidget(self.btn_scan)
        controls_layout.addWidget(self.btn_extensions)
        parent_layout.addLayout(controls_layout)
        
        # --- VIBEEXPAND: Semantic Search Button ---
        expand_layout = QHBoxLayout()
        self.btn_expand = QPushButton("🔍 VibeExpand")
        self.btn_expand.setStyleSheet("""
            QPushButton {
                background-color: #E67E22;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #D35400; }
            QPushButton:disabled { background-color: #666; }
        """)
        self.btn_expand.setToolTip("Find semantically related files using AI embeddings")
        self.btn_expand.clicked.connect(self.run_vibe_expand)
        expand_layout.addStretch()
        expand_layout.addWidget(self.btn_expand)
        parent_layout.addLayout(expand_layout)
        # --- END VIBEEXPAND ---
        
        reorder_layout = QHBoxLayout()
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        self.btn_up.setFixedWidth(30)
        self.btn_down.setFixedWidth(30)
        reorder_layout.addStretch()
        reorder_layout.addWidget(self.btn_up)
        reorder_layout.addWidget(self.btn_down)
        parent_layout.addLayout(reorder_layout)

    def create_operations_section(self, parent_layout):
        lbl = QLabel("Operations")
        lbl.setStyleSheet("font-weight: bold;")
        parent_layout.addWidget(lbl)
        
        action_group = QGroupBox("Generate")
        action_layout = QVBoxLayout()
        
        # Output Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Output Name:"))
        self.input_output_name = QLineEdit()
        self.input_output_name.setPlaceholderText("default: folder name")
        name_layout.addWidget(self.input_output_name)
        action_layout.addLayout(name_layout)
        
        self.btn_save = QPushButton("Save Configuration")
        self.btn_save.setStyleSheet("background-color: #2E8B57; color: white; font-weight: bold;")
        
        self.btn_human = QPushButton("Generate Human PDF")
        self.btn_human.setMinimumHeight(40)
        self.btn_llm = QPushButton("Generate LLM PDF")
        self.btn_llm.setMinimumHeight(40)
        
        action_layout.addWidget(self.btn_save)
        action_layout.addWidget(self.btn_human)
        action_layout.addWidget(self.btn_llm)
        
        # --- VIBECONTEXT: AI Context Checkbox ---
        self.chk_ai_context = QCheckBox("Inject AI Context Header")
        self.chk_ai_context.setToolTip("Auto-generates a README explaining this snapshot to the AI agent.")
        self.chk_ai_context.setStyleSheet("color: #8E44AD; font-weight: bold;")
        action_layout.addWidget(self.chk_ai_context)
        
        # Extension 7: Markdown Export Checkbox
        self.chk_markdown = QCheckBox("Export as Markdown")
        self.chk_markdown.setToolTip("Generate a .md file instead of PDF (easier for copy-pasting code).")
        self.chk_markdown.setStyleSheet("color: #2980B9; font-weight: bold;")
        action_layout.addWidget(self.chk_markdown)
        # --- END VIBECONTEXT ---
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - Generating...")
        action_layout.addWidget(self.progress_bar)
        
        action_group.setLayout(action_layout)
        parent_layout.addWidget(action_group)
        
        parent_layout.addSpacing(10)
        parent_layout.addWidget(QLabel("Log:"))
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet("font-family: Courier New; font-size: 10pt;")
        parent_layout.addWidget(self.text_log)

    # --- PROJECT REGISTRY LOGIC ---
    
    def refresh_project_list(self):
        """Refresh the saved projects sidebar with colors and tags."""
        self.list_projects.clear()
        self.registry.cleanup_missing()
        
        for proj in self.registry.get_projects():
            # Build display text with optional tag
            display_name = proj.name
            if proj.tag:
                display_name = f"[{proj.tag}] {proj.name}"
            
            item = QListWidgetItem(display_name)
            item.setToolTip(f"{proj.path}\n{proj.file_count} files")
            item.setData(Qt.ItemDataRole.UserRole, proj.path)
            
            # Apply color if set
            if proj.color:
                item.setForeground(QColor(proj.color))
            
            # Highlight active project
            if os.path.normpath(proj.path) == os.path.normpath(self.current_project_root):
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setBackground(QColor("#404040" if self.settings.theme == 'dark' else "#E0E0E0"))
                item.setText(f"➤ {item.text()}") # Add indicator only for active
            
            self.list_projects.addItem(item)

    def add_current_to_registry(self):
        """Add the current project to the registry."""
        if not self.current_project_root or not os.path.isdir(self.current_project_root):
            QMessageBox.warning(self, "No Project", "No valid project is currently loaded.")
            return
        
        path = self.current_project_root
        name = os.path.basename(path)
        file_count = self.list_files.count()
        
        if self.registry.add_project(path, name, file_count):
            self.refresh_project_list()
            self.text_log.append(f"Added to saved projects: {name}")
        else:
            self.text_log.append(f"Updated project: {name}")
            self.refresh_project_list()
            
    def remove_from_registry(self):
        """Remove selected project from registry."""
        item = self.list_projects.currentItem()
        if not item:
            return
        
        path = item.data(Qt.ItemDataRole.UserRole)
        name = item.text().replace("★ ", "")
        
        reply = QMessageBox.question(self, "Remove Project", 
                                     f"Remove '{name}' from saved projects?\n(This doesn't delete any files)",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.registry.remove_project(path)
            self.refresh_project_list()
            self.text_log.append(f"Removed from saved list: {name}")

    def scan_projects_dialog(self):
        """Open folder picker and scan for projects with .vibecode.yaml files."""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Folder to Scan for Projects",
            os.path.expanduser("~")
        )
        if not folder:
            return
        
        self.text_log.append(f"Scanning {folder} for projects...")
        self.status_bar.showMessage("Scanning...")
        
        # Scan for projects
        discovered = self.registry.scan_for_projects(folder, max_depth=4)
        
        if discovered:
            self.refresh_project_list()
            names = [p.name for p in discovered]
            self.text_log.append(f"Found {len(discovered)} projects: {', '.join(names)}")
            QMessageBox.information(
                self, "Scan Complete",
                f"Discovered {len(discovered)} new projects:\n\n" + "\n".join(f"• {p.name}" for p in discovered[:10]) +
                ("\n..." if len(discovered) > 10 else "")
            )
        else:
            self.text_log.append("No new projects found.")
            QMessageBox.information(self, "Scan Complete", "No new projects found in this folder.")
        
        self.status_bar.showMessage("Ready")

    def load_project_from_list(self, item):
        """Load a project from the sidebar list."""
        path = item.data(Qt.ItemDataRole.UserRole)
        if os.path.isdir(path):
            self.input_proj_root.setText(path)
            self.load_project()
        else:
            QMessageBox.warning(self, "Not Found", f"Project folder not found:\n{path}")
            self.registry.remove_project(path)
            self.refresh_project_list()

    def show_project_context_menu(self, pos):
        """Show context menu for project list."""
        item = self.list_projects.itemAt(pos)
        if not item:
            return
        
        path = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        
        action_open = QAction("Open Project", self)
        action_open.triggered.connect(lambda: self.load_project_from_list(item))
        menu.addAction(action_open)
        
        action_rename = QAction("Rename...", self)
        action_rename.triggered.connect(lambda: self.rename_project(item))
        menu.addAction(action_rename)
        
        # Color submenu
        color_menu = menu.addMenu("Set Color")
        for color_name, color_hex in PROJECT_COLORS.items():
            action = QAction(color_name, self)
            if color_hex:
                action.setIcon(self._create_color_icon(color_hex))
            action.triggered.connect(lambda checked, c=color_hex, p=path: self.set_project_color(p, c))
            color_menu.addAction(action)
            
        # Tag option
        action_tag = QAction("Set Tag...", self)
        action_tag.triggered.connect(lambda: self.set_project_tag_dialog(path))
        menu.addAction(action_tag)
        
        action_explorer = QAction("Show in Explorer", self)
        action_explorer.triggered.connect(lambda: self.open_file_explorer(path))
        menu.addAction(action_explorer)
        
        menu.addSeparator()
        
        action_remove = QAction("Remove from List", self)
        action_remove.triggered.connect(self.remove_from_registry)
        menu.addAction(action_remove)
        
        menu.exec(self.list_projects.mapToGlobal(pos))
    
    def _create_color_icon(self, hex_color):
        """Create a colored icon for menu items."""
        from PyQt6.QtGui import QPixmap, QPainter, QBrush
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(hex_color))
        return QIcon(pixmap)

    def set_project_color(self, path, color):
        """Set color for a project."""
        self.registry.set_project_color(path, color)
        self.refresh_project_list()

    def set_project_tag_dialog(self, path):
        """Open dialog to set project tag."""
        proj = self.registry.get_project_by_path(path)
        current_tag = proj.tag if proj else ""
        tag, ok = QInputDialog.getText(self, "Set Project Tag", 
                                     "Enter tag (e.g., Work, Personal, Archive):",
                                     QLineEdit.EchoMode.Normal, current_tag)
        if ok:
            self.registry.set_project_tag(path, tag.strip())
            self.refresh_project_list()

    def rename_project(self, item):
        """Rename a project in the registry."""
        path = item.data(Qt.ItemDataRole.UserRole)
        current_name = item.text().replace("★ ", "")
        
        new_name, ok = QInputDialog.getText(self, "Rename Project", 
                                          "Enter new name:", QLineEdit.EchoMode.Normal, current_name)
        if ok and new_name.strip():
            if self.registry.rename_project(path, new_name.strip()):
                self.refresh_project_list()

    # --- CORE FILE LOGIC ---

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Root", self.current_project_root)
        if folder:
            self.input_proj_root.setText(folder)
            self.load_project()

    def load_project(self):
        path = self.input_proj_root.text().strip()
        if not os.path.isdir(path):
            QMessageBox.critical(self, "Error", "Directory does not exist.")
            return
        
        self.current_project_root = os.path.abspath(path)
        self.text_log.append(f"Loaded project root: {self.current_project_root}")
        self.status_bar.showMessage(f"Project: {self.current_project_root}")
        
        os.chdir(self.current_project_root)
        
        # Update registry last_opened
        project_name = os.path.basename(self.current_project_root)
        self.registry.update_last_opened(self.current_project_root)
        
        # Also refresh settings recent list
        self.settings.add_recent_project(self.current_project_root)
        
        self.refresh_project_list()
        
        # Try to load existing config
        self.current_config_path = os.path.join(self.current_project_root, '.vibecode.yaml')
        if os.path.exists(self.current_config_path):
            # Update watcher
            if self.watcher.files():
                self.watcher.removePaths(self.watcher.files())
            self.watcher.addPath(self.current_config_path)
            
            self.load_yaml_config()
        else:
            self.text_log.append("No .vibecode.yaml found. Defaulting to empty state.")
            self.file_list = []
            self.exclude_list = []
            self.list_files.clear()
            self.input_output_name.setText(project_name)

    def load_yaml_config(self):
        try:
            with open(self.current_config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                
            if not data:
                data = {}
                
            self.file_list = data.get('files', [])
            self.exclude_list = data.get('exclude', [])
            output_name = data.get('output_name', '')
            
            if not output_name:
                output_name = os.path.basename(self.current_project_root)
                
            self.input_output_name.setText(output_name)
            
            self.list_files.clear()
            self.list_files.addItems(self.file_list)
            self.text_log.append(f"Loaded {len(self.file_list)} files from configuration.")
            
            # Update registry file count
            self.registry.update_file_count(self.current_project_root, len(self.file_list))
            self.refresh_project_list()
            
        except Exception as e:
            self.text_log.append(f"Error loading YAML: {str(e)}")

    def save_project(self):
        if not self.current_config_path:
            self.current_config_path = os.path.join(self.current_project_root, '.vibecode.yaml')
            
        # Get current order from list widget
        ordered_files = []
        for i in range(self.list_files.count()):
            ordered_files.append(self.list_files.item(i).text())
            
        data = {
            'project_name': os.path.basename(self.current_project_root),
            'files': ordered_files,
            'exclude': self.exclude_list,
            'output_name': self.input_output_name.text().strip()
        }
        
        # Preserve existing snapshot if any
        if os.path.exists(self.current_config_path):
            try:
                with open(self.current_config_path, 'r') as f:
                    old_data = yaml.safe_load(f) or {}
                if 'last_snapshot' in old_data:
                    data['last_snapshot'] = old_data['last_snapshot']
            except: pass

        try:
            # Block watcher to avoid reloading our own save (which would kill selection)
            if hasattr(self, 'watcher'):
                self.watcher.blockSignals(True)
                
            with open(self.current_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, sort_keys=False)
                
            if hasattr(self, 'watcher'):
                self.watcher.blockSignals(False)
                
            self.text_log.append(f"Configuration saved to {self.current_config_path}")
            self.status_bar.showMessage("Configuration saved.", 3000)
            
            # Update registry
            self.registry.update_file_count(self.current_project_root, len(ordered_files))
            self.refresh_project_list()
            
        except Exception as e:
            if hasattr(self, 'watcher'):
                self.watcher.blockSignals(False)
            self.text_log.append(f"Error saving YAML: {str(e)}")

    def add_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", self.current_project_root)
        if files:
            added_count = 0
            for f in files:
                try:
                    rel_path = os.path.relpath(f, self.current_project_root).replace(os.path.sep, '/')
                    if not self.list_files.findItems(rel_path, Qt.MatchFlag.MatchExactly):
                        self.list_files.addItem(rel_path)
                        added_count += 1
                except ValueError:
                    self.text_log.append(f"Skipping {f} (outside project root)")
            
            if added_count > 0:
                self.text_log.append(f"Added {added_count} files.")
                self.save_project()

    def remove_file(self):
        selected_items = self.list_files.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.list_files.takeItem(self.list_files.row(item))
        self.save_project()

    def move_item(self, direction):
        row = self.list_files.currentRow()
        item = self.list_files.currentItem()
        
        if row < 0: return
        new_row = row + direction
        
        if 0 <= new_row < self.list_files.count():
            current_item = self.list_files.takeItem(row)
            self.list_files.insertItem(new_row, current_item)
            self.list_files.setCurrentItem(current_item)
            current_item.setSelected(True)
            self.save_project()

    def open_extension_manager(self):
        dlg = ExtensionManagerDialog(self.included_extensions, self)
        if dlg.exec():
            self.included_extensions = dlg.result_extensions
            self.text_log.append(f"Updated extensions: {len(self.included_extensions)} types")

    def launch_scan(self):
        dlg = ScanDialog(self.current_project_root, self.exclude_list, self.included_extensions, self)
        if dlg.exec():
            new_files = dlg.result_files
            new_excludes = dlg.result_excludes
            
            if new_files:
                reply = QMessageBox.question(self, "Scan Results", 
                                             f"Found {len(new_files)} files. Overwrite current list?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.list_files.clear()
                    self.list_files.addItems(new_files)
                    self.exclude_list = new_excludes
                    self.save_project()
                    self.text_log.append(f"Scanned: {len(new_files)} files.")

    def run_generation(self, pipeline_type):
        """Start PDF generation with pre-flight security scan."""
        self.save_project()
        self.btn_human.setEnabled(False)
        self.btn_llm.setEnabled(False)
        
        # Show progress bar
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        base_name = self.input_output_name.text().strip()
        if not base_name:
            base_name = "snapshot"
            
        suffix = "_human.pdf" if pipeline_type == 'human' else "_llm.pdf"
        
        # Extension 7: Markdown Override
        if hasattr(self, 'chk_markdown') and self.chk_markdown.isChecked():
            # Switch pipeline to markdown
            original_type = pipeline_type
            pipeline_type = 'markdown'
            # Preserve the 'human' or 'llm' distinction in filename if we wanted, 
            # but MarkdownRenderer is currently unified. Let's just use .md extension.
            suffix = f"_{original_type}.md"

        self._pending_filename = base_name + suffix
        self._pending_pipeline_type = pipeline_type
        
        # Get VibeContext settings
        self._pending_use_ai_context = self.chk_ai_context.isChecked()
        self._pending_user_intent = self.input_ai_intent.text().strip() if hasattr(self, 'input_ai_intent') else ""
        
        # First, gather files and run security scan
        self.text_log.append("Starting pre-generation security scan...")
        
        try:
            # Gather files using engine
            engine = ProjectEngine(self.current_config_path)
            file_data = engine.gather_files()
            self._pending_file_data = file_data
            
            # Start security scan worker
            self.security_worker = SecurityScanWorker(file_data)
            self.security_worker.log_message.connect(self.text_log.append)
            self.security_worker.finished_success.connect(self._on_security_scan_complete)
            self.security_worker.finished_error.connect(self.on_generation_error)
            self.security_worker.start()
        except Exception as e:
            self.on_generation_error(str(e))
    
    def _on_security_scan_complete(self, scanner, candidates):
        """Handle security scan completion - show dialog if secrets found."""
        if candidates:
            # Show the quarantine dialog
            dialog = SecretReviewDialog(scanner, candidates, self)
            result = dialog.exec()
            
            if result != QDialog.DialogCode.Accepted:
                # User cancelled - abort generation
                self.text_log.append("❌ Generation cancelled by user.")
                self.btn_human.setEnabled(True)
                self.btn_llm.setEnabled(True)
                self.progress_bar.setVisible(False)
                return
            
            self.text_log.append(f"✅ Security review complete. {len(scanner.redaction_map)} value(s) marked for redaction.")
            self._pending_scanner = scanner
        else:
            self.text_log.append("✅ No secrets detected. Proceeding with generation.")
            self._pending_scanner = None
        
        # Proceed with generation
        self._start_generation_worker()
    
    def _start_generation_worker(self):
        """Actually start the PDF generation worker."""
        self.worker = GenerationWorker(
            self.current_config_path, 
            self._pending_pipeline_type, 
            self._pending_filename,
            use_ai_context=self._pending_use_ai_context,
            user_intent=self._pending_user_intent,
            secret_scanner=getattr(self, '_pending_scanner', None)
        )
        self.worker.log_message.connect(self.text_log.append)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished_success.connect(self.on_generation_success)
        self.worker.finished_error.connect(self.on_generation_error)
        self.worker.start()

    def update_progress(self, current, total):
        """Update progress bar value."""
        self.progress_bar.setValue(int(current * 100 / total) if total > 0 else 0)

    def on_generation_success(self, p_type, path):
        self.text_log.append(f"SUCCESS: {p_type.upper()} PDF generated.")
        self.progress_bar.setVisible(False)
        self.btn_human.setEnabled(True)
        self.btn_llm.setEnabled(True)
        
        # Save file snapshot for diff tracking
        self.save_file_snapshot()
        
        reply = QMessageBox.question(self, "Generation Complete", 
                                     f"Successfully created:\n{path}\n\nOpen folder now?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.open_file_explorer(os.path.dirname(path))

    def on_generation_error(self, err_msg):
        self.text_log.append(f"ERROR: {err_msg}")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Generation Failed", err_msg)
        self.btn_human.setEnabled(True)
        self.btn_llm.setEnabled(True)

    def show_diff_view(self):
        """Show dialog with changes since last generation."""
        if not self.current_project_root:
            QMessageBox.warning(self, "No Project", "Please load a project first.")
            return
            
        # Get current files from the list
        current_files = [self.list_files.item(i).text() 
                         for i in range(self.list_files.count())]
        
        # Load last snapshot from config
        last_snapshot = {}
        if os.path.exists(self.current_config_path):
            try:
                with open(self.current_config_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
                last_snapshot = data.get('last_snapshot', {})
            except:
                pass
            
        dlg = DiffViewDialog(self.current_project_root, current_files, last_snapshot, self)
        dlg.exec()

    def show_batch_export(self):
        """Show batch export dialog."""
        dlg = BatchExportDialog(self.registry, self)
        dlg.exec()
        self.text_log.append("Batch export dialog closed.")

    def show_restore_dialog(self):
        """Show the restore/unpack dialog."""
        dlg = RestoreDialog(self)
        dlg.exec()
        self.text_log.append("Restore dialog closed.")

    def show_mcp_settings(self):
        """Show the MCP server configuration dialog (Extension 3)."""
        dlg = MCPSettingsDialog(parent=self)
        dlg.exec()
        self.text_log.append("MCP Settings dialog closed.")

    def show_time_travel(self):
        """Show the Time Travel snapshot comparison dialog (Extension 4)."""
        dlg = TimeTravelDialog(parent=self)
        dlg.exec()
        self.text_log.append("Time Travel dialog closed.")

    def show_model_settings(self):
        """Show the Model Settings dialog (ECR #005)."""
        dlg = ModelSettingsDialog(self)
        dlg.exec()
        # Refresh model ID? The dialog saves to settings, which config reads. 
        # Active model ID is fetched dynamically from config.
        # UserSettings object has .data dict
        active_model = get_active_model_id(self.settings.data)
        self.text_log.append(f"Model settings updated. Active: {active_model}")

    def handle_dropped_files(self, file_paths):
        """Handle files dropped onto the list widget (robust duplicate normalization)."""
        added_count = 0
        root = (self.current_project_root or os.getcwd())
        root = os.path.normpath(root)

        # Build set of existing real paths for duplicate checks (case-insensitive + canonical)
        existing_real = set()
        for i in range(self.list_files.count()):
            it = self.list_files.item(i).text()
            if os.path.isabs(it):
                path = os.path.normpath(it)
            else:
                path = os.path.normpath(os.path.join(root, it))
            # Resolve symlinks/subst to canonical path
            try:
                real_path = os.path.realpath(path)
            except Exception:
                real_path = path
            existing_real.add(os.path.normcase(real_path))

        for path in file_paths:
            try:
                if not os.path.isfile(path):
                    continue
                
                # Get canonical path for duplicate check
                abs_path = os.path.normpath(os.path.abspath(path))
                try:
                    real_path = os.path.realpath(abs_path)
                except Exception:
                    real_path = abs_path
                
                comp_path = os.path.normcase(real_path)

                # Attempt to compute a project-relative path (use relative only if inside root)
                try:
                    rel_path = os.path.relpath(abs_path, root).replace(os.path.sep, '/')
                except Exception:
                    rel_path = abs_path

                # If rel_path escapes the project folder, use absolute path for storing
                if rel_path.startswith('..'):
                    store_text = abs_path
                else:
                    store_text = rel_path

                # Duplicate check by canonical real path
                if comp_path not in existing_real:
                    self.list_files.addItem(store_text)
                    existing_real.add(comp_path)
                    added_count += 1

            except Exception as e:
                # Don't crash the UI on a single bad file
                self.text_log.append(f"⚠️ Failed to add dropped file {path}: {e}")

        if added_count > 0:
            self.text_log.append(f"Dropped {added_count} files.")
            self.save_project()

    def launch_chat(self, initial_tab: int = 0):
        """
        Launch the VibeChat window.
        Requires an LLM PDF snapshot to be present (unless in MCP mode).
        """
        # 1. Check if project is loaded
        if not self.current_project_root:
            QMessageBox.warning(self, "No Project", "Please load a project first.")
            return
        
        # 2. Look for LLM PDF
        # Try configured output name first, then default patterns
        output_name = self.input_output_name.text().strip() or os.path.basename(self.current_project_root)
        
        possible_paths = [
            os.path.join(self.current_project_root, f"{output_name}_llm.pdf"),
            os.path.join(self.current_project_root, "snapshot_llm.pdf"),
            os.path.join(self.current_project_root, f"{os.path.basename(self.current_project_root)}_llm.pdf"),
        ]
        
        pdf_path = None
        for path in possible_paths:
            if os.path.exists(path):
                pdf_path = path
                break
        
        if not pdf_path:
            # If strictly project chat, insist on PDF.
            # If MCP Expert, we can proceed with empty string (ChatWindow handles it).
            if initial_tab == 0:
                reply = QMessageBox.question(
                    self, 
                    "Snapshot Missing", 
                    "VibeChat requires an LLM PDF snapshot for Project Chat.\n\n"
                    "Generate one now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.run_generation('llm')
                return
            else:
                pdf_path = "" # Empty path for MCP
        
        # 3. Launch Chat Window
        self.text_log.append(f"Launching VibeChat with: {os.path.basename(pdf_path) if pdf_path else 'No Context (MCP Only)'}")
        self.chat_window = ChatWindow(pdf_path, self.current_project_root, self, initial_tab=initial_tab)
        self.chat_window.show()

    def save_file_snapshot(self):
        """Save current file hashes and content cache for diff tracking."""
        if not self.current_config_path:
            return
            
        snapshot = {}
        cache_dir = os.path.join(self.current_project_root, '.vibecode', 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        for i in range(self.list_files.count()):
            rel_path = self.list_files.item(i).text()
            abs_path = os.path.join(self.current_project_root, rel_path)
            
            if os.path.exists(abs_path):
                try:
                    # Calculate hash
                    with open(abs_path, 'rb') as f:
                        content = f.read()
                    snapshot[rel_path] = hashlib.md5(content).hexdigest()
                    
                    # Cache content (hashed filename to avoid path issues)
                    safe_name = hashlib.md5(rel_path.encode()).hexdigest()
                    cache_path = os.path.join(cache_dir, safe_name)
                    with open(cache_path, 'wb') as f:
                        f.write(content)
                        
                except Exception as e:
                    print(f"Failed to cache {rel_path}: {e}")
                    snapshot[rel_path] = ''
        
        # Update config with snapshot
        try:
            # Temporarily block watcher to avoid self-triggering
            if hasattr(self, 'watcher'):
                self.watcher.blockSignals(True)
                
            data = {}
            if os.path.exists(self.current_config_path):
                with open(self.current_config_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
            data['last_snapshot'] = snapshot
            with open(self.current_config_path, 'w') as f:
                yaml.dump(data, f, sort_keys=False)
                
            if hasattr(self, 'watcher'):
                self.watcher.blockSignals(False)
                
        except Exception as e:
            self.text_log.append(f"Warning: Could not save snapshot: {e}")

    def open_file_explorer(self, path):
        try:
            if platform.system() == "Windows": os.startfile(path)
            elif platform.system() == "Darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.text_log.append(f"Error opening folder: {e}")

    # --- VIBESELECT: AI Selection Methods ---
    
    def run_ai_selection(self):
        """Trigger AI-powered file selection based on user intent."""
        intent = self.input_ai_intent.text().strip()
        if not intent:
            QMessageBox.warning(self, "Input Required", "Please describe what you want to work on.")
            return
        
        # Get all currently listed files
        current_files = [self.list_files.item(i).text() for i in range(self.list_files.count())]
        
        if not current_files:
            QMessageBox.warning(self, "No Files", "Add files to your project list first (use Smart Scan).")
            return
        
        # Disable UI during processing
        self.status_bar.showMessage("🧠 AI is analyzing your codebase structure...")
        self.input_ai_intent.setEnabled(False)
        self.btn_ai_select.setEnabled(False)
        self.btn_ai_select.setText("Thinking...")
        
        # Start worker
        self.ai_worker = AISelectionWorker(current_files, intent)
        self.ai_worker.log_message.connect(self.text_log.append)
        self.ai_worker.finished_success.connect(self.on_ai_selection_success)
        self.ai_worker.finished_error.connect(self.on_ai_selection_error)
        self.ai_worker.start()
    
    def on_ai_selection_success(self, selected_files):
        """Handle successful AI file selection (robust path matching)."""
        self.status_bar.showMessage(f"✨ AI selected {len(selected_files)} relevant files.")
        self.input_ai_intent.setEnabled(True)
        self.btn_ai_select.setEnabled(True)
        self.btn_ai_select.setText("Auto-Select")

        # Clear current selection
        self.list_files.clearSelection()
        match_count = 0

        # Normalize selected_files to absolute paths for robust matching
        root = (self.current_project_root or os.getcwd())
        root = os.path.normpath(root)

        sel_real = set()
        for sf in selected_files:
            if os.path.isabs(sf):
                path = os.path.normpath(sf)
            else:
                # If the AI returned a path that is relative, assume it's relative to project root
                path = os.path.normpath(os.path.join(root, sf))
            
            try:
                real = os.path.realpath(path)
            except:
                real = path
            sel_real.add(os.path.normcase(real))

        # Walk list items and mark selected items
        for i in range(self.list_files.count()):
            item = self.list_files.item(i)
            item_text = item.text()
            if os.path.isabs(item_text):
                path = os.path.normpath(item_text)
            else:
                path = os.path.normpath(os.path.join(root, item_text))
            
            try:
                real = os.path.realpath(path)
            except:
                real = path
            it_real = os.path.normcase(real)

            if it_real in sel_real:
                item.setSelected(True)
                match_count += 1

        # Ask user what to do with the selection
        if match_count > 0:
            reply = QMessageBox.question(
                self, "AI Suggestion",
                f"AI identified {match_count} relevant files for this task.\n\n"
                "Do you want to REMOVE the irrelevant files from the list?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Remove items that are NOT selected (iterate backwards)
                for i in range(self.list_files.count() - 1, -1, -1):
                    if not self.list_files.item(i).isSelected():
                        self.list_files.takeItem(i)
                self.save_project()
                self.text_log.append(f"🎯 AI narrowed context to {match_count} files.")
        else:
            QMessageBox.information(
                self, "AI Result",
                "AI could not find exact matches in your file list.\n"
                "Try a different query or check file paths."
            )
    
    def on_ai_selection_error(self, err):
        """Handle AI selection error."""
        self.status_bar.showMessage("AI Error")
        self.input_ai_intent.setEnabled(True)
        self.btn_ai_select.setEnabled(True)
        self.btn_ai_select.setText("Auto-Select")
        self.text_log.append(f"❌ AI Selection Error: {err}")
        QMessageBox.warning(self, "AI Error", f"Could not complete selection:\n\n{err}")

    # --- VIBEEXPAND: Semantic Search Methods ---
    
    def run_vibe_expand(self):
        """Run VibeExpand to find semantically related files."""
        selected_items = self.list_files.selectedItems()
        
        if not selected_items:
            # If no selection, maybe use ALL files? Or warn?
            # User might expect "find related to project" -> selects all?
            # But "Expansion" usually implies "Find related to X".
            # If X is nothing, it's ambiguous.
            # Let's stick to warning for now, user needs to pick a seed.
            QMessageBox.warning(
                self, "Selection Required", 
                "Select one or more files to use as a seed for finding related files."
            )
            return
        
        if not hasattr(self, 'current_config_path') or not self.current_config_path:
            QMessageBox.warning(self, "No Project", "Open or create a project first.")
            return
        
        selected_files = [item.text() for item in selected_items]
        project_dir = os.path.dirname(self.current_config_path)
        
        # Build file contents dict
        file_contents = {}
        for i in range(self.list_files.count()):
            rel_path = self.list_files.item(i).text()
            abs_path = os.path.join(project_dir, rel_path)
            try:
                with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                    file_contents[rel_path] = f.read()
            except Exception:
                pass  # Skip unreadable files
        
        # Disable UI
        self.status_bar.showMessage("🔍 VibeExpand: Analyzing codebase semantics...")
        self.btn_expand.setEnabled(False)
        self.btn_expand.setText("Analyzing...")
        
        # Start worker
        self.expand_worker = VibeExpandWorker(project_dir, selected_files, file_contents, min_score=0.4)
        self.expand_worker.log_message.connect(self.text_log.append)
        self.expand_worker.progress_update.connect(self.update_progress)
        self.expand_worker.finished_success.connect(self.on_expand_success)
        self.expand_worker.finished_error.connect(self.on_expand_error)
        self.expand_worker.start()
    
    def on_expand_success(self, suggestions):
        """Handle successful VibeExpand results."""
        self.status_bar.showMessage(f"✨ Found {len(suggestions)} related files.")
        self.btn_expand.setEnabled(True)
        self.btn_expand.setText("🔍 VibeExpand")
        
        if not suggestions:
            QMessageBox.information(
                self, "VibeExpand",
                "No additional related files found.\n"
                "Try selecting different files or adding more to the project."
            )
            return
        
        # Format suggestions for display
        msg_lines = ["AI found these related files:\n"]
        for path, score in suggestions[:10]:
            msg_lines.append(f"• {path} ({score:.0%} similar)")
        
        msg_lines.append("\nAdd these files to your selection?")
        
        reply = QMessageBox.question(
            self, "VibeExpand Suggestions",
            "\n".join(msg_lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # --- PRUNING LOGIC (AI Select Style) ---
            # 1. Keep Seed Files
            # 2. Keep Suggested Files (High Confidence)
            # 3. Remove everything else
            
            root = (self.current_project_root or os.getcwd())
            root = os.path.normpath(root)
            
            # Identify Seed Files (absolute paths)
            seed_files_abs = set()
            for path in self.expand_worker.selected_files:
                 if os.path.isabs(path):
                     seed_files_abs.add(os.path.normpath(path))
                 else:
                     seed_files_abs.add(os.path.normpath(os.path.join(root, path)))

            # Identify Suggested Files (absolute paths)
            suggested_files_abs = set()
            for path, score in suggestions:
                if os.path.isabs(path):
                     suggested_files_abs.add(os.path.normpath(path))
                else:
                     suggested_files_abs.add(os.path.normpath(os.path.join(root, path)))

            # Valid Set = Seeds + Suggestions
            valid_set = seed_files_abs.union(suggested_files_abs)
            
            # Rebuild List Widget
            self.list_files.clear()
            
            added_count = 0
            
            # Add files to list (store as relative if possible)
            for abs_path in valid_set:
                # Security Check: Must be within project root
                # (unless it's a seed file user manually added from outside, but VibeCode usually restricts this)
                
                try:
                    rel = os.path.relpath(abs_path, root).replace(os.path.sep, '/')
                    if rel.startswith('..'):
                        # Outside project root? Only allow if it was a seed.
                        if abs_path not in seed_files_abs:
                            continue
                        store_text = abs_path
                    else:
                        store_text = rel
                except Exception:
                    store_text = abs_path
                
                item = QListWidgetItem(store_text)
                self.list_files.addItem(item)
                item.setSelected(True)
                added_count += 1

            self.save_project()
            self.text_log.append(f"✨ VibeExpand Refined Context: {len(seed_files_abs)} seeds + {len(suggested_files_abs)} related files.")
    
    def on_expand_error(self, err):
        """Handle VibeExpand error."""
        self.status_bar.showMessage("VibeExpand Error")
        self.btn_expand.setEnabled(True)
        self.btn_expand.setText("🔍 VibeExpand")
        self.text_log.append(f"❌ VibeExpand Error: {err}")
        QMessageBox.warning(self, "VibeExpand Error", f"Semantic search failed:\n\n{err}")