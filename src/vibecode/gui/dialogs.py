"""
Dialog windows for the VibeCode GUI.
Includes configuration, scanning, diff viewing, and export dialogs.
"""
import os
import hashlib
import pathspec
from pathspec.patterns import GitWildMatchPattern

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QPushButton, QScrollArea, QWidget, QGridLayout, 
                             QCheckBox, QLineEdit, QDialogButtonBox, QLabel, 
                             QComboBox, QPlainTextEdit, QTextEdit, QMessageBox, QListWidget,
                             QListWidgetItem, QProgressBar, QApplication, QSplitter, QFileDialog, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPalette

from ..discovery import discover_files
from ..engine import ProjectEngine
from .utils import DEFAULT_EXTENSIONS, EXTENSION_PRESETS
from .workers import RestorationWorker

# --- EXTENSION MANAGER DIALOG ---
class ExtensionManagerDialog(QDialog):
    """Dialog for managing file extensions to include in scans."""
    
    def __init__(self, current_extensions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extension Manager")
        self.resize(550, 500)
        self.result_extensions = None
        self.extensions = set(current_extensions) if current_extensions else set(DEFAULT_EXTENSIONS)
        
        layout = QVBoxLayout(self)
        
        # Presets
        preset_group = QGroupBox("Quick Presets")
        preset_layout = QHBoxLayout()
        for preset_name in EXTENSION_PRESETS:
            btn = QPushButton(preset_name)
            btn.clicked.connect(lambda checked, name=preset_name: self.apply_preset(name))
            preset_layout.addWidget(btn)
        btn_all = QPushButton("All")
        btn_all.setStyleSheet("background-color: #2E8B57;")
        btn_all.clicked.connect(self.select_all)
        preset_layout.addWidget(btn_all)
        btn_none = QPushButton("None")
        btn_none.setStyleSheet("background-color: #8B0000;")
        btn_none.clicked.connect(self.select_none)
        preset_layout.addWidget(btn_none)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)
        
        # Extension grid
        ext_group = QGroupBox("Included Extensions")
        ext_layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.ext_grid = QGridLayout(scroll_widget)
        self.ext_grid.setSpacing(5)
        self.checkboxes = {}
        self._populate_extension_grid()
        scroll.setWidget(scroll_widget)
        ext_layout.addWidget(scroll)
        ext_group.setLayout(ext_layout)
        layout.addWidget(ext_group)
        
        # Custom extension
        custom_group = QGroupBox("Custom Extensions")
        custom_layout = QHBoxLayout()
        self.input_ext = QLineEdit()
        self.input_ext.setPlaceholderText(".ext (e.g., .vue, .svelte)")
        self.input_ext.returnPressed.connect(self.add_custom)
        custom_layout.addWidget(self.input_ext)
        btn_add = QPushButton("Add")
        btn_add.clicked.connect(self.add_custom)
        custom_layout.addWidget(btn_add)
        btn_delete = QPushButton("Delete Selected")
        btn_delete.clicked.connect(self.delete_selected)
        custom_layout.addWidget(btn_delete)
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.save_and_close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
    
    def _populate_extension_grid(self):
        for i in reversed(range(self.ext_grid.count())):
            self.ext_grid.itemAt(i).widget().setParent(None)
        self.checkboxes.clear()
        all_exts = sorted(set(DEFAULT_EXTENSIONS) | self.extensions)
        cols = 5
        for i, ext in enumerate(all_exts):
            cb = QCheckBox(ext)
            cb.setChecked(ext in self.extensions)
            cb.stateChanged.connect(lambda state, e=ext: self._toggle_ext(e, state))
            self.checkboxes[ext] = cb
            row, col = divmod(i, cols)
            self.ext_grid.addWidget(cb, row, col)
    
    def _toggle_ext(self, ext, state):
        if state == Qt.CheckState.Checked.value:
            self.extensions.add(ext)
        else:
            self.extensions.discard(ext)
    
    def apply_preset(self, preset_name):
        preset_exts = EXTENSION_PRESETS.get(preset_name, [])
        self.extensions = set(preset_exts)
        for ext, cb in self.checkboxes.items():
            cb.setChecked(ext in self.extensions)
    
    def select_all(self):
        self.extensions = set(self.checkboxes.keys())
        for cb in self.checkboxes.values():
            cb.setChecked(True)
    
    def select_none(self):
        self.extensions.clear()
        for cb in self.checkboxes.values():
            cb.setChecked(False)
    
    def add_custom(self):
        ext = self.input_ext.text().strip()
        if not ext:
            return
        if not ext.startswith('.'):
            ext = '.' + ext
        ext = ext.lower()
        if ext in self.checkboxes:
            self.checkboxes[ext].setChecked(True)
            self.extensions.add(ext)
        else:
            self.extensions.add(ext)
            self._populate_extension_grid()
        self.input_ext.clear()
    
    def delete_selected(self):
        to_remove = [ext for ext, cb in self.checkboxes.items() 
                     if not cb.isChecked() and ext not in DEFAULT_EXTENSIONS]
        for ext in to_remove:
            self.extensions.discard(ext)
        self._populate_extension_grid()
    
    def save_and_close(self):
        self.result_extensions = sorted(self.extensions)
        self.accept()


# --- SMART SCAN DIALOG ---
class ScanDialog(QDialog):
    def __init__(self, project_root, current_excludes, included_extensions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Smart Scan Configuration")
        self.resize(500, 600)
        self.project_root = project_root
        self.included_extensions = included_extensions
        self.result_files = None
        self.result_excludes = None

        layout = QVBoxLayout(self)

        # Scope
        scope_group = QGroupBox("1. Scan Scope")
        scope_layout = QVBoxLayout()
        scope_layout.addWidget(QLabel("Where should we look for code?"))
        self.combo_target = QComboBox()
        self.combo_target.setEditable(True)
        self._populate_src_folders()
        scope_layout.addWidget(self.combo_target)
        scope_group.setLayout(scope_layout)
        layout.addWidget(scope_group)

        # Ignore Rules
        ignore_group = QGroupBox("2. Ignore Rules")
        ignore_layout = QVBoxLayout()
        self.defaults_map = {
            'venv': ['.venv/', 'venv/', 'env/'],
            'pycache': ['__pycache__/', '*.pyc', 'dist/', 'build/', '*.egg-info/'],
            'git': ['.git/', '.vscode/', '.idea/'],
            'node': ['node_modules/']
        }
        self.chk_venv = QCheckBox("Virtual Envs (.venv, venv)")
        self.chk_pycache = QCheckBox("Python Cache (__pycache__)")
        self.chk_git = QCheckBox("Git & IDE (.git, .idea)")
        self.chk_node = QCheckBox("Node Modules")
        self.chk_venv.setChecked(True)
        self.chk_pycache.setChecked(True)
        self.chk_git.setChecked(True)
        self.chk_node.setChecked(True)
        ignore_layout.addWidget(self.chk_venv)
        ignore_layout.addWidget(self.chk_pycache)
        ignore_layout.addWidget(self.chk_git)
        ignore_layout.addWidget(self.chk_node)
        ignore_group.setLayout(ignore_layout)
        layout.addWidget(ignore_group)

        ext_info = QLabel(f"📁 Scanning for: {len(self.included_extensions)} extension types")
        ext_info.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(ext_info)

        layout.addWidget(QLabel("Custom Patterns (Saved to config):"))
        self.txt_custom = QPlainTextEdit()
        self.txt_custom.setPlaceholderText("*.log\nsecrets.json")
        self.txt_custom.setStyleSheet("font-family: Courier New;")
        self._prefill_customs(current_excludes)
        layout.addWidget(self.txt_custom)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Start Scan")
        btn_box.accepted.connect(self.run_scan)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _populate_src_folders(self):
        common_names = ['src', 'lib', 'app', 'core', 'pkg']
        found = ['. (Root)']
        for name in common_names:
            if os.path.isdir(os.path.join(self.project_root, name)):
                found.append(name)
        self.combo_target.addItems(found)

    def _prefill_customs(self, current_excludes):
        default_set = set()
        for key in self.defaults_map:
            default_set.update(self.defaults_map[key])
        custom_lines = [x for x in current_excludes if x not in default_set]
        self.txt_custom.setPlainText("\n".join(custom_lines))

    def run_scan(self):
        selection = self.combo_target.currentText()
        scan_root = self.project_root
        if selection != '. (Root)':
            scan_root = os.path.join(self.project_root, selection)
        
        if not os.path.isdir(scan_root):
            QMessageBox.critical(self, "Error", f"Folder '{selection}' does not exist.")
            return

        active_defaults = []
        if self.chk_venv.isChecked(): active_defaults.extend(self.defaults_map['venv'])
        if self.chk_pycache.isChecked(): active_defaults.extend(self.defaults_map['pycache'])
        if self.chk_git.isChecked(): active_defaults.extend(self.defaults_map['git'])
        if self.chk_node.isChecked(): active_defaults.extend(self.defaults_map['node'])

        raw_custom = self.txt_custom.toPlainText().splitlines()
        customs = [line.strip() for line in raw_custom if line.strip()]
        full_exclude_list = active_defaults + customs
        
        patterns = []
        gitignore_path = os.path.join(self.project_root, '.gitignore')
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r') as f: patterns.extend(f.readlines())
            except: pass
        patterns.extend(full_exclude_list)
        
        spec = pathspec.PathSpec.from_lines(GitWildMatchPattern, patterns)

        try:
            all_files = discover_files(scan_root, spec)
            relevant_exts = tuple(self.included_extensions)
            found = []
            for f in all_files:
                if f.endswith(relevant_exts) and '.vibecode.yaml' not in f:
                    rel = os.path.relpath(f, self.project_root).replace(os.path.sep, '/')
                    found.append(rel)
            
            self.result_files = sorted(found)
            self.result_excludes = full_exclude_list
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", str(e))


# --- DIFF VIEW DIALOG ---
class DiffViewDialog(QDialog):
    """Shows changes in project files since last generation."""
    
    def __init__(self, project_root, current_files, last_snapshot, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Changes Since Last Generation")
        self.resize(1000, 700)
        self.project_root = project_root
        self.last_snapshot = last_snapshot
        
        main_layout = QVBoxLayout(self)
        
        # Splitter: File List | Diff Content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # LEFT: Lists
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        # Calculate diff
        current_set = set(current_files)
        last_set = set(last_snapshot.keys()) if last_snapshot else set()
        
        added = sorted(list(current_set - last_set))
        removed = sorted(list(last_set - current_set))
        
        # Check for modified files (hash changed)
        modified = []
        for f in current_set & last_set:
            file_path = os.path.join(project_root, f)
            if os.path.exists(file_path):
                current_hash = self._hash_file(file_path)
                if current_hash != last_snapshot.get(f, ''):
                    modified.append(f)
        modified.sort()
        
        # Summary Label
        summary = QLabel(f"📊 +{len(added)} | -{len(removed)} | ~{len(modified)}")
        summary.setStyleSheet("font-weight: bold; font-size: 11pt;")
        left_layout.addWidget(summary)
        
        # Tree/List of changes
        self.change_list = QListWidget()
        left_layout.addWidget(self.change_list)
        
        # Populate list
        for f in modified:
            item = QListWidgetItem(f"✏️ {f}")
            item.setData(Qt.ItemDataRole.UserRole, ('modified', f))
            item.setForeground(QColor("#F1C40F" if self._is_dark() else "#B7950B"))
            self.change_list.addItem(item)
            
        for f in added:
            item = QListWidgetItem(f"➕ {f}")
            item.setData(Qt.ItemDataRole.UserRole, ('added', f))
            item.setForeground(QColor("#2ECC71" if self._is_dark() else "#229954"))
            self.change_list.addItem(item)
            
        for f in removed:
            item = QListWidgetItem(f"➖ {f}")
            item.setData(Qt.ItemDataRole.UserRole, ('removed', f))
            item.setForeground(QColor("#E74C3C" if self._is_dark() else "#A93226"))
            self.change_list.addItem(item)
            
        if self.change_list.count() == 0:
            self.change_list.addItem("No changes detected.")
            
        self.change_list.currentItemChanged.connect(self.show_diff)
        
        splitter.addWidget(left_widget)
        
        # RIGHT: Diff Viewer
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        self.diff_viewer = QTextEdit()
        self.diff_viewer.setReadOnly(True)
        self.diff_viewer.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 10pt;")
        self.diff_viewer.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        right_layout.addWidget(QLabel("Unified Diff:"))
        right_layout.addWidget(self.diff_viewer)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 700])
        
        # Buttons
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        main_layout.addWidget(btn_close)
        
        # Select first item if any
        if self.change_list.count() > 0:
            self.change_list.setCurrentRow(0)

    def _hash_file(self, path):
        try:
            with open(path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except: return ''
    
    def _is_dark(self):
        # Heuristic: check window (dialog) background lightness
        bg = self.palette().color(QPalette.ColorRole.Window)
        return bg.lightness() < 128

    def show_diff(self, current_item, previous_item):
        if not current_item:
            self.diff_viewer.clear()
            return
            
        data = current_item.data(Qt.ItemDataRole.UserRole)
        if not data: return # "No changes detected" case
        
        status, rel_path = data
        self.diff_viewer.clear()
        
        if status == 'removed':
            self.diff_viewer.setText(f"File removed: {rel_path}")
            return
            
        abs_path = os.path.join(self.project_root, rel_path)
        if not os.path.exists(abs_path):
            self.diff_viewer.setText("Error: File not found on disk.")
            return

        # Read Current
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                current_lines = f.readlines()
        except Exception as e:
            self.diff_viewer.setText(f"Error reading file: {e}")
            return
            
        if status == 'added':
            # Just show the file content
            self.diff_viewer.setPlainText("".join(current_lines))
            return
        
        # MODIFIED: Try to find cached original
        # Cache is stored as MD5(rel_path) inside .vibecode/cache/
        cache_name = hashlib.md5(rel_path.encode()).hexdigest()
        cache_path = os.path.join(self.project_root, '.vibecode', 'cache', cache_name)
        
        old_lines = []
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8', errors='replace') as f:
                    old_lines = f.readlines()
            except:
                old_lines = []
                self.diff_viewer.append("<i>(Warning: Could not read cached original version)</i>")
        else:
            self.diff_viewer.append("<i>(No cached version found for diff. Generation required to seed cache.)</i>\n")
        
        # Generate Diff
        import difflib
        diff = difflib.unified_diff(
            old_lines, current_lines,
            fromfile=f"Old ({rel_path})",
            tofile=f"New ({rel_path})"
        )
        
        # Render with colors
        html = ""
        for line in diff:
            line = line.rstrip()
            if line.startswith('---') or line.startswith('+++'):
                color = "#888888" # Grey
            elif line.startswith('@@'):
                color = "#3498DB" # Blue
            elif line.startswith('+'):
                color = "#2ECC71" if self._is_dark() else "green"
            elif line.startswith('-'):
                color = "#E74C3C" if self._is_dark() else "red"
            else:
                color = "#FFFFFF" if self._is_dark() else "black"
            
            # Escape HTML characters
            line_esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html += f'<div style="color: {color}; white-space: pre;">{line_esc}</div>'
            
        self.diff_viewer.setHtml(html)


# --- BATCH EXPORT DIALOG ---
class BatchExportDialog(QDialog):
    """Dialog for batch exporting multiple projects."""
    
    log_message = pyqtSignal(str)
    
    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Export")
        self.resize(500, 400)
        self.registry = registry
        self.selected_projects = []
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select projects to export:"))
        
        self.project_list = QListWidget()
        self.project_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        
        for proj in registry.get_projects():
            if registry.project_exists(proj.path):
                item = QListWidgetItem(f"{proj.name} ({proj.file_count} files)")
                item.setData(Qt.ItemDataRole.UserRole, proj.path)
                self.project_list.addItem(item)
        
        layout.addWidget(self.project_list)
        
        # Export type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Export as:"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Human PDF", "LLM PDF", "Both"])
        type_layout.addWidget(self.combo_type)
        layout.addLayout(type_layout)
        
        # Progress
        self.progress_label = QLabel("")
        layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_export = QPushButton("Export Selected")
        self.btn_export.setStyleSheet("background-color: #2E8B57;")
        self.btn_export.clicked.connect(self.start_export)
        btn_layout.addWidget(self.btn_export)
        
        btn_cancel = QPushButton("Close")
        btn_cancel.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
    
    def start_export(self):
        """Start batch export of selected projects."""
        selected = self.project_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select at least one project.")
            return
        
        self.selected_projects = [item.data(Qt.ItemDataRole.UserRole) for item in selected]
        export_type = self.combo_type.currentText()
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.selected_projects))
        self.progress_bar.setValue(0)
        self.btn_export.setEnabled(False)
        
        errors = []
        for i, proj_path in enumerate(self.selected_projects):
            config_path = os.path.join(proj_path, '.vibecode.yaml')
            proj_name = os.path.basename(proj_path)
            
            self.progress_label.setText(f"Exporting: {proj_name}...")
            QApplication.processEvents()
            
            try:
                # Read config for output name preference
                import yaml
                base_name = proj_name # Default
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        data = yaml.safe_load(f) or {}
                        base_name = data.get('output_name', proj_name)

                engine = ProjectEngine(config_path)
                
                if export_type in ["Human PDF", "Both"]:
                    engine.render(pipeline_type='human', 
                                  output_path_override=os.path.join(proj_path, f'{base_name}_human.pdf'))
                
                if export_type in ["LLM PDF", "Both"]:
                    engine.render(pipeline_type='llm',
                                  output_path_override=os.path.join(proj_path, f'{base_name}_llm.pdf'))
                
            except Exception as e:
                errors.append(f"{proj_name}: {str(e)}")
            
            self.progress_bar.setValue(i + 1)
        
        self.btn_export.setEnabled(True)
        self.progress_label.setText(f"Completed {len(self.selected_projects)} projects")
        
        if errors:
            QMessageBox.warning(self, "Export Completed with Errors",
                f"Completed with {len(errors)} error(s):\n\n" + "\n".join(errors[:5]))
        else:
            QMessageBox.information(self, "Export Complete",
                f"Successfully exported {len(self.selected_projects)} projects!")


# --- RESTORE / UNPACK DIALOG ---
class RestoreDialog(QDialog):
    """
    Dialog to handle restoring a project from a PDF snapshot.
    Uses the Digital Twin manifest via RestorationWorker.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restore Project from Snapshot")
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # 1. Source PDF
        pdf_group = QGroupBox("1. Source Snapshot")
        pdf_layout = QHBoxLayout()
        self.input_pdf = QLineEdit()
        self.input_pdf.setPlaceholderText("Select the .pdf file to unpack...")
        self.input_pdf.setReadOnly(True)
        btn_browse_pdf = QPushButton("Browse...")
        btn_browse_pdf.clicked.connect(self.browse_pdf)
        pdf_layout.addWidget(self.input_pdf)
        pdf_layout.addWidget(btn_browse_pdf)
        pdf_group.setLayout(pdf_layout)
        layout.addWidget(pdf_group)
        
        # 2. Target Directory
        target_group = QGroupBox("2. Target Directory")
        target_layout = QHBoxLayout()
        self.input_target = QLineEdit()
        self.input_target.setPlaceholderText("Select folder to extract files into...")
        btn_browse_target = QPushButton("Browse...")
        btn_browse_target.clicked.connect(self.browse_target)
        target_layout.addWidget(self.input_target)
        target_layout.addWidget(btn_browse_target)
        target_group.setLayout(target_layout)
        layout.addWidget(target_group)
        
        # 3. Log Output
        log_group = QGroupBox("3. Restoration Log")
        log_layout = QVBoxLayout()
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet("font-family: Courier New; font-size: 9pt; background-color: #1e1e1e; color: #dcdcdc;")
        log_layout.addWidget(self.text_log)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Buttons
        btn_box = QHBoxLayout()
        self.btn_restore = QPushButton("Restore Project")
        self.btn_restore.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold; padding: 6px;")
        self.btn_restore.clicked.connect(self.start_restore)
        self.btn_restore.setEnabled(False)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        
        btn_box.addStretch()
        btn_box.addWidget(self.btn_restore)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def browse_pdf(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select PDF Snapshot", "", "PDF Files (*.pdf)")
        if fname:
            self.input_pdf.setText(fname)
            self._validate_inputs()

    def browse_target(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.input_target.setText(folder)
            self._validate_inputs()

    def _validate_inputs(self):
        has_pdf = bool(self.input_pdf.text())
        has_target = bool(self.input_target.text())
        self.btn_restore.setEnabled(has_pdf and has_target)

    def start_restore(self):
        pdf_path = self.input_pdf.text()
        out_dir = self.input_target.text()
        
        # Check output directory safety
        if os.listdir(out_dir):
            reply = QMessageBox.question(
                self, "Directory Not Empty",
                "The target directory is not empty.\nExisting files may be overwritten.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        self.text_log.clear()
        self.text_log.append(f"Starting restoration...")
        self.text_log.append(f"Source: {os.path.basename(pdf_path)}")
        self.text_log.append(f"Target: {out_dir}\n")
        
        self.btn_restore.setEnabled(False)
        self.input_pdf.setEnabled(False)
        self.input_target.setEnabled(False)
        
        # Start Worker
        self.worker = RestorationWorker(pdf_path, out_dir)
        self.worker.log_message.connect(self.text_log.append)
        self.worker.finished_success.connect(self.on_success)
        self.worker.finished_error.connect(self.on_error)
        self.worker.start()

    def on_success(self, count):
        self.text_log.append(f"\n✅ DONE. Successfully restored {count} files.")
        QMessageBox.information(self, "Restoration Complete", f"Successfully restored {count} files!")
        self._reset_ui()

    def on_error(self, err_msg):
        self.text_log.append(f"\n❌ ERROR: {err_msg}")
        QMessageBox.critical(self, "Restoration Failed", err_msg)
        self._reset_ui()

    def _reset_ui(self):
        self.btn_restore.setEnabled(True)
        self.input_pdf.setEnabled(True)
        self.input_target.setEnabled(True)


# --- SECRET REVIEW DIALOG ---
class SecretReviewDialog(QDialog):
    """
    Interactive 'Quarantine' interface for reviewing potential secrets.
    Users must review and decide on each candidate before PDF generation proceeds.
    """
    
    def __init__(self, scanner, candidates: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔒 Security Quarantine: Potential Secrets Detected")
        self.resize(900, 600)
        self.scanner = scanner
        self.candidates = candidates
        self.item_widgets = {}  # Track widgets by value
        
        layout = QVBoxLayout(self)
        
        # Header Alert
        alert_box = QLabel(
            f"⚠️ Found {len(candidates)} potential secret(s).\n"
            "Please review each item before generating the PDF."
        )
        alert_box.setStyleSheet(
            "background-color: #4A1818; color: #FF9999; "
            "padding: 15px; border-radius: 5px; font-weight: bold;"
        )
        layout.addWidget(alert_box)
        
        # Legend
        legend = QLabel(
            "🔴 Redact = Replace with [REDACTED SECRET]  |  "
            "🟢 Ignore = Keep original value"
        )
        legend.setStyleSheet("color: #888; font-style: italic; padding: 5px;")
        layout.addWidget(legend)
        
        # Scroll area for candidates
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.list_layout = QVBoxLayout(scroll_widget)
        self.list_layout.setSpacing(8)
        
        for item in self.candidates:
            self._add_item(item)
        
        self.list_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Button Bar
        btn_box = QHBoxLayout()
        
        btn_redact_all = QPushButton("🔴 Redact All")
        btn_redact_all.clicked.connect(self.redact_all)
        btn_redact_all.setStyleSheet("color: #FF5555; border: 1px solid #FF5555; padding: 8px;")
        
        btn_ignore_all = QPushButton("🟢 Ignore All")
        btn_ignore_all.clicked.connect(self.ignore_all)
        btn_ignore_all.setStyleSheet("color: #55FF55; border: 1px solid #55FF55; padding: 8px;")
        
        btn_proceed = QPushButton("✅ Proceed with Generation")
        btn_proceed.setStyleSheet(
            "background-color: #2E8B57; color: white; "
            "font-weight: bold; padding: 10px;"
        )
        btn_proceed.clicked.connect(self.accept)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_box.addWidget(btn_redact_all)
        btn_box.addWidget(btn_ignore_all)
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_proceed)
        layout.addLayout(btn_box)
    
    def _add_item(self, item):
        """Create a row widget for a secret candidate."""
        widget = QWidget()
        widget.setStyleSheet(
            "background-color: #252526; border: 1px solid #444; "
            "border-radius: 4px; padding: 8px;"
        )
        row_layout = QHBoxLayout(widget)
        row_layout.setContentsMargins(10, 8, 10, 8)
        
        # Info section
        info_layout = QVBoxLayout()
        
        # Type and confidence
        type_label = QLabel(f"<b>{item['type']}</b>")
        type_label.setStyleSheet("color: #FF9999;")
        
        # File and line
        file_info = item.get('file', 'Unknown')
        location = QLabel(f"📄 {file_info} : Line {item['line']}")
        location.setStyleSheet("color: #888; font-size: 9pt;")
        
        # Context (truncated)
        context = QLabel(f"<code>{item['context']}</code>")
        context.setStyleSheet("font-family: Consolas; color: #CCCCCC;")
        context.setWordWrap(True)
        
        # Value preview (partially masked)
        val = item['value']
        masked = val[:8] + '...' + val[-4:] if len(val) > 16 else val
        value_label = QLabel(f"Value: <code>{masked}</code>")
        value_label.setStyleSheet("color: #AAAAAA;")
        
        info_layout.addWidget(type_label)
        info_layout.addWidget(location)
        info_layout.addWidget(context)
        info_layout.addWidget(value_label)
        
        row_layout.addLayout(info_layout, stretch=1)
        
        # Action buttons
        btn_layout = QVBoxLayout()
        
        btn_redact = QPushButton("🔴 Redact")
        btn_redact.setCheckable(True)
        btn_redact.setChecked(True)  # Default to redact (secure)
        btn_redact.setStyleSheet(
            "QPushButton { padding: 6px 12px; }"
            "QPushButton:checked { background-color: #D32F2F; color: white; }"
        )
        
        btn_ignore = QPushButton("🟢 Ignore")
        btn_ignore.setCheckable(True)
        btn_ignore.setStyleSheet(
            "QPushButton { padding: 6px 12px; }"
            "QPushButton:checked { background-color: #388E3C; color: white; }"
        )
        
        # Mutual exclusivity
        btn_redact.clicked.connect(lambda: self._set_action(item['value'], 'redact', btn_redact, btn_ignore))
        btn_ignore.clicked.connect(lambda: self._set_action(item['value'], 'ignore', btn_redact, btn_ignore))
        
        btn_layout.addWidget(btn_redact)
        btn_layout.addWidget(btn_ignore)
        btn_layout.addStretch()
        
        row_layout.addLayout(btn_layout)
        
        self.list_layout.addWidget(widget)
        self.item_widgets[item['value']] = (btn_redact, btn_ignore)
        
        # Pre-register as redaction (default secure state)
        self.scanner.add_redaction(item['value'])
    
    def _set_action(self, value: str, action: str, btn_redact, btn_ignore):
        """Handle toggling between Redact and Ignore for a value."""
        if action == 'redact':
            btn_redact.setChecked(True)
            btn_ignore.setChecked(False)
            self.scanner.add_redaction(value)
        else:
            btn_redact.setChecked(False)
            btn_ignore.setChecked(True)
            self.scanner.add_to_whitelist(value)
    
    def redact_all(self):
        """Mark all candidates for redaction."""
        for value, (btn_redact, btn_ignore) in self.item_widgets.items():
            btn_redact.setChecked(True)
            btn_ignore.setChecked(False)
            self.scanner.add_redaction(value)
    
    def ignore_all(self):
        """Whitelist all candidates."""
        for value, (btn_redact, btn_ignore) in self.item_widgets.items():
            btn_redact.setChecked(False)
            btn_ignore.setChecked(True)
            self.scanner.add_to_whitelist(value)


# --- MODEL SETTINGS DIALOG (ECR #005) ---
class ModelSettingsDialog(QDialog):
    """
    Dialog for configuring the AI model used by VibeSelect/VibeContext/VibeChat.
    Implements Hybrid Registry Pattern: dropdown + custom override.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🤖 AI Model Settings")
        self.resize(500, 300)
        
        from ..settings import get_settings
        from ..settings import get_settings
        from ..config import KNOWN_MODELS, DEFAULT_MODEL_ID, get_active_model_id, CUSTOM_PROVIDER_PRESETS
        from openai import OpenAI
        
        self.settings = get_settings()
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Configure the AI model used for intelligent features.")
        header.setStyleSheet("color: #888; font-style: italic; padding: 5px;")
        layout.addWidget(header)
        
        # Model Dropdown
        layout.addWidget(QLabel("Select AI Model:"))
        self.combo_models = QComboBox()
        
        # Populate dropdown with known models
        for display_name, model_id in KNOWN_MODELS:
            self.combo_models.addItem(display_name, userData=model_id)
        
        # Add custom option
        self.combo_models.addItem("✏️ Custom / Experimental...", userData="custom")
        
        # Set current selection
        current_key = self.settings.selected_model_key
        if current_key == "custom" or self.settings.custom_model_string:
            # Custom mode
            index = self.combo_models.findData("custom")
        else:
            index = self.combo_models.findData(current_key)
        
        if index >= 0:
            self.combo_models.setCurrentIndex(index)
        
        layout.addWidget(self.combo_models)
        
        # Custom Model Input
        self.group_custom = QGroupBox("Custom Model ID")
        custom_layout = QVBoxLayout()
        
        self.txt_custom = QLineEdit()
        self.txt_custom.setPlaceholderText("e.g. gemini-1.5-pro-002 or claude-3-opus-20240229")
        self.txt_custom.setText(self.settings.custom_model_string)
        
        hint = QLabel("Enter the exact model ID as specified by the provider's API.")
        hint.setStyleSheet("color: #666; font-size: 9pt;")
        
        custom_layout.addWidget(self.txt_custom)
        custom_layout.addWidget(self.txt_custom)
        custom_layout.addWidget(hint)
        self.group_custom.setLayout(custom_layout)
        layout.addWidget(self.group_custom)
        
        # --- Custom Presets (ECR #006) ---
        self.combo_preset = QComboBox()
        self.combo_preset.addItem("Select a Preset...")
        self.combo_preset.addItems(CUSTOM_PROVIDER_PRESETS.keys())
        self.combo_preset.currentTextChanged.connect(self.apply_preset)
        
        # Add to form layout style within group_custom if possible, or just add to custom_layout
        # reusing custom_layout from above which is QVBoxLayout
        custom_layout.addWidget(QLabel("Quick Preset:"))
        custom_layout.addWidget(self.combo_preset)
        
        self.btn_test = QPushButton("Test Connection")
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.clicked.connect(self.test_connection)
        custom_layout.addWidget(self.btn_test)
        
        # Toggle custom visibility
        self.combo_models.currentIndexChanged.connect(self._toggle_custom)
        self._toggle_custom()
        
        # Current Model Display
        self.lbl_active = QLabel()
        self.lbl_active.setStyleSheet(
            "background-color: #2E8B57; color: white; "
            "padding: 10px; border-radius: 5px; font-weight: bold;"
        )
        self._update_active_label()
        layout.addWidget(self.lbl_active)
        
        # Connect to update label on change
        self.combo_models.currentIndexChanged.connect(self._update_active_label)
        self.txt_custom.textChanged.connect(self._update_active_label)
        
        # --- API Key Section ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        api_header = QLabel("🔑 API Keys & Provider")
        api_header.setStyleSheet("font-weight: bold; margin-top: 10px; font-size: 11pt;")
        layout.addWidget(api_header)
        
        api_layout = QGridLayout()
        
        # Provider Selection
        api_layout.addWidget(QLabel("Provider:"), 0, 0)
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(['google', 'openai', 'anthropic', 'ollama', 'custom'])
        # Set current provider
        curr_provider = self.settings.chat_provider
        idx = self.combo_provider.findText(curr_provider)
        if idx >= 0:
            self.combo_provider.setCurrentIndex(idx)
        self.combo_provider.currentTextChanged.connect(self._on_provider_changed)
        api_layout.addWidget(self.combo_provider, 0, 1)
        
        # API Key Input
        self.lbl_api_key = QLabel("API Key:")
        api_layout.addWidget(self.lbl_api_key, 1, 0)
        
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("Enter API key...")
        api_layout.addWidget(self.txt_api_key, 1, 1)
        
        # Base URL Input (for custom providers)
        self.lbl_base_url = QLabel("Base URL:")
        api_layout.addWidget(self.lbl_base_url, 2, 0)
        
        self.txt_base_url = QLineEdit()
        self.txt_base_url.setPlaceholderText("e.g. http://localhost:1234/v1")
        self.txt_base_url.setText(self.settings.custom_base_url)
        api_layout.addWidget(self.txt_base_url, 2, 1)
        
        # Initial state update
        self._on_provider_changed(self.combo_provider.currentText())
        
        layout.addLayout(api_layout)
        
        # Info note
        note = QLabel("💡 Keys are stored securely in your system keyring.")
        note.setStyleSheet("color: #666; font-size: 8pt; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(note)
        
        layout.addStretch()
        
        # Buttons
        btn_box = QHBoxLayout()
        
        btn_save = QPushButton("💾 Save")
        btn_save.setStyleSheet("background-color: #2E8B57; color: white; padding: 8px 20px;")
        btn_save.clicked.connect(self._save_and_close)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)
    
    def _save_and_close(self):
        """Save settings and close."""
        provider = self.combo_provider.currentText()
        api_key = self.txt_api_key.text().strip()
        custom_base_url = self.txt_base_url.text().strip()
        
        # Save provider
        self.settings.chat_provider = provider
        
        # Save Base URL
        self.settings.custom_base_url = custom_base_url
        
        # Save API key (if provided)
        if api_key:
            if not self.settings.set_api_key(provider, api_key):
                QMessageBox.warning(self, "Keyring Error", "Could not save API key to system keyring.")
                return # Prevent closing if key storage fails
        
        # Update model selection
        if self.combo_models.currentData() == "custom":
            custom_model = self.txt_custom.text().strip()
            if custom_model:
                self.settings.selected_model_key = "custom"
                self.settings.custom_model_string = custom_model
            else:
                QMessageBox.warning(self, "Invalid Input", "Please enter a Custom Model ID.")
                return
        else:
            self.settings.selected_model_key = self.combo_models.currentData()
            self.settings.custom_model_string = ""
            
        self.accept()

    def _toggle_custom(self):
        """Show/hide custom input based on dropdown selection."""
        is_custom = (self.combo_models.currentData() == "custom")
        self.group_custom.setVisible(is_custom)
    
    def _update_active_label(self):
        """Update the display showing which model will be used."""
        from ..config import get_active_model_id
        
        # Simulate what would be saved
        if self.combo_models.currentData() == "custom":
            model_id = self.txt_custom.text().strip()
            if not model_id:
                model_id = "(enter a model ID)"
        else:
            model_id = self.combo_models.currentData()
        
        self.lbl_active.setText(f"Active Model: {model_id}")
    
    def _on_provider_changed(self, provider_name):
        """Update UI when provider changes."""
        is_ollama = (provider_name == 'ollama')
        is_custom = (provider_name == 'custom')
        
        # API Key visibility
        self.lbl_api_key.setVisible(not is_ollama)
        self.txt_api_key.setVisible(not is_ollama)
        
        # Base URL visibility (only for Custom)
        self.lbl_base_url.setVisible(is_custom)
        self.txt_base_url.setVisible(is_custom)
        
        if not is_ollama:
            self._update_key_placeholder()
        
    def _update_key_placeholder(self):
        """Update API key placeholder based on whether key exists."""
        provider = self.combo_provider.currentText()
        if self.settings.get_api_key(provider):
            self.txt_api_key.setPlaceholderText("••••••••• (Key Saved)")
            self.txt_api_key.setText("")
        else:
            self.txt_api_key.setPlaceholderText(f"Enter {provider} API key...")
    
    def _save_and_close(self):
        """Save settings and close dialog."""
        # 1. Save Model Selection
        if self.combo_models.currentData() == "custom":
            custom_text = self.txt_custom.text().strip()
            if not custom_text:
                QMessageBox.warning(self, "Error", "Please enter a custom model ID.")
                return
            self.settings.selected_model_key = "custom"
            self.settings.custom_model_string = custom_text
        else:
            self.settings.selected_model_key = self.combo_models.currentData()
            self.settings.custom_model_string = ""
        
        # 2. Save Provider Preference
        provider = self.combo_provider.currentText()
        self.settings.chat_provider = provider
        
        # 3. Save API Key (if provided)
        new_key = self.txt_api_key.text().strip()
        if new_key:
            if not self.settings.set_api_key(provider, new_key):
                QMessageBox.warning(self, "Keyring Error", 
                    "Could not securely store API key. Is 'keyring' installed?")
                return
        
        self.accept()



    def apply_preset(self, name: str):
        """Auto-fill settings from selected preset."""
        from ..config import CUSTOM_PROVIDER_PRESETS
        
        if name not in CUSTOM_PROVIDER_PRESETS:
            return
            
        preset = CUSTOM_PROVIDER_PRESETS[name]
        
        # 1. Fill Base URL
        self.txt_base_url.setText(preset["base_url"])
        
        # 2. Fill Model ID (if empty or we want to overwrite? Let's be smart)
        # If user hasn't typed anything custom, fill it.
        if not self.txt_custom.text().strip():
            self.txt_custom.setText(preset["model_hint"])
            
    def test_connection(self):
        """Test the custom connection using OpenAI client."""
        from openai import OpenAI
        
        try:
            # We enforce testing only for what's currently in the fields
            key = self.txt_api_key.text().strip()
            base_url = self.txt_base_url.text().strip()
            model = self.txt_custom.text().strip()
            
            # If masking is active (placeholder), try to fetch from settings
            if not key:
                provider = self.combo_provider.currentText()
                key = self.settings.get_api_key(provider)
            
            if not all([key, base_url, model]):
                raise ValueError("API key, base URL, and model are required for testing.")

            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            
            client = OpenAI(api_key=key, base_url=base_url)
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1
            )
            
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Success", "Connection successful! ✅\nThe provider is reachable and authenticated.")

        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Connection Failed", f"Could not connect:\n{str(e)}")


# --- HELP DIALOG ---
class HelpDialog(QDialog):
    """Robust help dialog explaining how the app works."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("How to Use Vibecode")
        self.resize(700, 600)
        
        layout = QVBoxLayout(self)
        
        # Help Content
        content = QTextEdit()
        content.setReadOnly(True)
        content.setHtml("""
        <h2 style="color: #2E8B57;">🚀 Welcome to Vibecode!</h2>
        <p>Vibecode helps you turn your codebases into AI-ready snapshots. Here is the workflow:</p>
        
        <h3>1. Select a Project 📂</h3>
        <ul>
            <li>Click <b>Browse...</b> to open a project folder.</li>
            <li>Or select a project from <b>Saved Projects</b> sidebar.</li>
        </ul>
        
        <h3>2. Choose Your Files 📝</h3>
        <ul>
            <li><b>✨ Magic Bar (VibeSelect):</b> Type your intent (e.g., "Fix auth bug") -> AI picks the files!</li>
            <li><b>🔍 VibeExpand:</b> Find semantically related code suitable for the context.</li>
            <li><b>Smart Scan:</b> Automatically finds code files while ignoring junk (node_modules, venv).</li>
            <li><b>Extension Manager:</b> Configure file types (.py, .js, .cpp) to include.</li>
        </ul>
        
        <h3>3. Generate Snapshot ⚡</h3>
        <ul>
            <li><b>Inject AI Context:</b> Auto-generates a high-level "Handoff Note".</li>
            <li><b>Export as Markdown:</b> Generate copy-paste friendly <code>.md</code> files instead of PDF.</li>
            <li><b>Human PDF (Ctrl+G):</b> For YOU. Syntax highlighting, line numbers, readable.</li>
            <li><b>LLM PDF (Ctrl+Shift+G):</b> For AI. Token-optimized, minimal formatting.</li>
        </ul>
        
        <h3>4. VibeChat & MCP 🤖</h3>
        <ul>
            <li><b>Chat with Codebase (Ctrl+J):</b> Query your project with context-aware AI.</li>
            <li><b>MCP Client:</b> Connect to external MCP servers (Brave Search, PostgreSQL, etc.) via <b>Settings > MCP Servers</b>.</li>
            <li><b>RAG Auto-Ingest:</b> MCP tool results are automatically indexed into the knowledge base.</li>
            <li><b>MCP Server Mode:</b> Vibecode can serve THIS project to other AI agents (e.g., Claude Desktop) via <code>vibecode serve</code>.</li>
        </ul>

        <h3>5. Advanced Tools 🛠️</h3>
        <ul>
            <li><b>⏰ Time Travel v2:</b> Visual side-by-side snapshot comparison with unified diffs.</li>
            <li><b>Restore / Unpack:</b> Recover any Vibecode snapshot (PDF or MD) back to source code with 100% fidelity using the hidden Digital Twin manifest.</li>
            <li><b>Batch Export:</b> Process multiple projects at once.</li>
        </ul>
        
        <hr>
        <h3>⌨️ Keyboard Shortcuts</h3>
        <table border="0" cellpadding="5" cellspacing="0">
            <tr><td><b>Ctrl+S</b></td><td>Save Configuration</td></tr>
            <tr><td><b>Ctrl+G</b></td><td>Generate Human PDF</td></tr>
            <tr><td><b>Ctrl+Shift+G</b></td><td>Generate LLM PDF</td></tr>
            <tr><td><b>Ctrl+D</b></td><td>Open Diff View</td></tr>
            <tr><td><b>Ctrl+J</b></td><td>Open VibeChat</td></tr>
            <tr><td><b>Ctrl+T</b></td><td>Toggle Dark/Light Mode</td></tr>
            <tr><td><b>F5</b></td><td>Reload Project</td></tr>
        </table>
        """)
        layout.addWidget(content)
        
        # Close Button
        btn_close = QPushButton("Got it! 🚀")
        btn_close.setStyleSheet("background-color: #2E8B57; color: white; font-weight: bold; padding: 8px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


# --- MCP SETTINGS DIALOG ---

class MCPSettingsDialog(QDialog):
    """
    Dialog for managing MCP server connections.
    
    Extension 3: Visual MCP server management with connection status.
    
    Features:
        - View configured servers
        - Show connection status (✅/❌)
        - View available tools per server
    """
    
    def __init__(self, mcp_host=None, parent=None):
        """
        Initialize the MCP settings dialog.
        
        Args:
            mcp_host: Optional MCPHost instance to display status from
            parent: Parent widget
        """
        super().__init__(parent)
        self.mcp_host = mcp_host
        self.setWindowTitle("MCP Server Management")
        self.setMinimumSize(500, 400)
        self._setup_ui()
    
    def _setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>🔌 MCP External Connections</h2>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Description
        desc = QLabel(
            "Model Context Protocol (MCP) connects Vibecode to external services "
            "like GitHub, Google Drive, and Slack. Configure servers in "
            "<code>config/mcp_servers.json</code>."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: gray; padding: 10px;")
        layout.addWidget(desc)
        
        # Server List Group
        server_group = QGroupBox("Configured Servers")
        server_layout = QVBoxLayout(server_group)
        
        # Scroll area for server list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.server_list_layout = QVBoxLayout(scroll_content)
        self.server_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(scroll_content)
        server_layout.addWidget(scroll)
        
        layout.addWidget(server_group)
        
        # Populate servers
        self._populate_servers()
        
        # Tools Summary
        if self.mcp_host and self.mcp_host.available_tools:
            tools_group = QGroupBox(f"Available Tools ({len(self.mcp_host.available_tools)})")
            tools_layout = QVBoxLayout(tools_group)
            
            tools_text = QLabel("<br>".join([
                f"• <b>{tool['name']}</b>: {tool.get('description', 'No description')[:50]}..."
                for tool in self.mcp_host.available_tools[:10]
            ]))
            tools_text.setWordWrap(True)
            tools_layout.addWidget(tools_text)
            
            if len(self.mcp_host.available_tools) > 10:
                more_label = QLabel(f"<i>...and {len(self.mcp_host.available_tools) - 10} more</i>")
                more_label.setStyleSheet("color: gray;")
                tools_layout.addWidget(more_label)
            
            layout.addWidget(tools_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_open_config = QPushButton("📁 Open Config")
        btn_open_config.clicked.connect(self._open_config)
        btn_layout.addWidget(btn_open_config)
        
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self._refresh)
        btn_layout.addWidget(btn_refresh)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
    
    def _populate_servers(self):
        """Populate the server list from config."""
        import json
        from pathlib import Path
        
        # Clear existing
        while self.server_list_layout.count():
            child = self.server_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "mcp_servers.json"
        
        if not config_path.exists():
            no_config = QLabel("⚠️ No configuration file found. Create config/mcp_servers.json")
            no_config.setStyleSheet("color: orange; padding: 20px;")
            self.server_list_layout.addWidget(no_config)
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            error_label = QLabel(f"❌ Config error: {e}")
            error_label.setStyleSheet("color: red; padding: 20px;")
            self.server_list_layout.addWidget(error_label)
            return
        
        servers = config.get('mcpServers', {})
        
        if not servers:
            empty_label = QLabel("No servers configured. Add servers to mcp_servers.json")
            empty_label.setStyleSheet("color: gray; padding: 20px;")
            self.server_list_layout.addWidget(empty_label)
            return
        
        # Build server rows
        connected_servers = self.mcp_host.connected_servers if self.mcp_host else []
        
        for name, conf in servers.items():
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(5, 5, 5, 5)
            
            # Status indicator
            is_connected = name in connected_servers
            status = "✅" if is_connected else "⚫"
            status_label = QLabel(status)
            status_label.setFixedWidth(30)
            row_layout.addWidget(status_label)
            
            # Server name
            name_label = QLabel(f"<b>{name}</b>")
            name_label.setFixedWidth(120)
            row_layout.addWidget(name_label)
            
            # Command
            cmd = conf.get('command', 'N/A')
            cmd_label = QLabel(f"<code>{cmd}</code>")
            cmd_label.setStyleSheet("color: gray;")
            row_layout.addWidget(cmd_label, 1)
            
            # Tool count (if connected)
            if is_connected and self.mcp_host:
                tool_count = sum(1 for t in self.mcp_host.available_tools if t.get('server_name') == name)
                tools_label = QLabel(f"{tool_count} tools")
                tools_label.setStyleSheet("color: green;")
                row_layout.addWidget(tools_label)
            
            self.server_list_layout.addWidget(row)
    
    def _open_config(self):
        """Open the MCP config file in system editor."""
        import subprocess
        from pathlib import Path
        
        config_path = Path(__file__).parent.parent / "config" / "mcp_servers.json"
        
        if config_path.exists():
            import sys
            if sys.platform == 'win32':
                subprocess.Popen(['notepad', str(config_path)])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(config_path)])
            else:
                subprocess.Popen(['xdg-open', str(config_path)])
    
    def _refresh(self):
        """Refresh the server list."""
        self._populate_servers()


# --- TIME TRAVEL DIALOG ---

class TimeTravelDialog(QDialog):
    """
    Dialog for comparing two Vibecode PDF snapshots.
    
    Extension 4: Visual side-by-side snapshot version comparison.
    
    Features:
        - Load two PDF snapshots
        - Show file-level changes
        - Display unified diff for each file
    """
    
    def __init__(self, chat_engine=None, parent=None):
        """
        Initialize the Time Travel dialog.
        
        Args:
            chat_engine: Optional ChatEngine instance with loaded context
            parent: Parent widget
        """
        super().__init__(parent)
        self.chat_engine = chat_engine
        self.setWindowTitle("⏰ Time Travel - Snapshot Comparison")
        self.setMinimumSize(1000, 700)
        self._setup_ui()
    
    def _setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header and description
        header = QLabel("<h2>⏰ Time Travel - Compare Snapshots</h2>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        desc = QLabel(
            "Compare your current snapshot with a previous version to see what changed. "
            "Select a reference PDF snapshot to compare against."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(desc)
        
        # Reference selector
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel("Reference Snapshot:"))
        self.ref_path_label = QLabel("<i>No reference loaded</i>")
        self.ref_path_label.setStyleSheet("color: gray;")
        ref_layout.addWidget(self.ref_path_label, 1)
        
        btn_load_ref = QPushButton("📂 Load Reference")
        btn_load_ref.clicked.connect(self._load_reference)
        ref_layout.addWidget(btn_load_ref)
        layout.addLayout(ref_layout)
        
        # Splitter for file list and diff
        from PyQt6.QtWidgets import QSplitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Changed files list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        self.summary_label = QLabel("Load a reference snapshot to compare")
        self.summary_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(self.summary_label)
        
        self.file_list = QListWidget()
        self.file_list.currentItemChanged.connect(self._show_file_diff)
        left_layout.addWidget(self.file_list)
        
        splitter.addWidget(left_widget)
        
        # Right: Diff viewer
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        right_layout.addWidget(QLabel("Unified Diff:"))
        self.diff_viewer = QTextEdit()
        self.diff_viewer.setReadOnly(True)
        self.diff_viewer.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 10pt;"
        )
        self.diff_viewer.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        right_layout.addWidget(self.diff_viewer)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
    
    def _load_reference(self):
        """Load a reference PDF snapshot for comparison."""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Snapshot",
            "",
            "PDF Files (*.pdf)"
        )
        
        if not file_path:
            return
        
        if not self.chat_engine:
            self.summary_label.setText("❌ No ChatEngine available")
            return
        
        # Load reference using ChatEngine
        success = self.chat_engine.load_reference(file_path)
        
        if success:
            self.ref_path_label.setText(file_path)
            self._compare_snapshots()
        else:
            self.summary_label.setText("❌ Failed to load reference")
    
    def _compare_snapshots(self):
        """Compare current context with reference."""
        if not self.chat_engine or not self.chat_engine.reference_context:
            return
        
        self.file_list.clear()
        
        current_files = set(self.chat_engine.context.files.keys())
        ref_files = set(self.chat_engine.reference_context.files.keys())
        
        added = sorted(current_files - ref_files)
        removed = sorted(ref_files - current_files)
        
        # Check modified files
        modified = []
        for f in current_files & ref_files:
            current_content = self.chat_engine.context.files.get(f, '')
            ref_content = self.chat_engine.reference_context.files.get(f, '')
            if current_content != ref_content:
                modified.append(f)
        modified.sort()
        
        self.summary_label.setText(f"📊 +{len(added)} | ~{len(modified)} | -{len(removed)}")
        
        # Populate list
        for f in modified:
            item = QListWidgetItem(f"✏️ {f}")
            item.setData(Qt.ItemDataRole.UserRole, ('modified', f))
            item.setForeground(QColor("#F1C40F"))
            self.file_list.addItem(item)
        
        for f in added:
            item = QListWidgetItem(f"➕ {f}")
            item.setData(Qt.ItemDataRole.UserRole, ('added', f))
            item.setForeground(QColor("#2ECC71"))
            self.file_list.addItem(item)
        
        for f in removed:
            item = QListWidgetItem(f"➖ {f}")
            item.setData(Qt.ItemDataRole.UserRole, ('removed', f))
            item.setForeground(QColor("#E74C3C"))
            self.file_list.addItem(item)
        
        if self.file_list.count() == 0:
            self.file_list.addItem("✅ No changes between snapshots")
        elif self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
    
    def _show_file_diff(self, current, previous):
        """Show diff for selected file."""
        if not current:
            return
        
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data:
            self.diff_viewer.clear()
            return
        
        change_type, filename = data
        
        if not self.chat_engine:
            return
        
        diff_text = self.chat_engine.get_file_diff(filename)
        
        if diff_text:
            # Simple colorization
            lines = diff_text.split('\n')
            colored = []
            for line in lines:
                if line.startswith('+') and not line.startswith('+++'):
                    colored.append(f'<span style="color: #2ECC71;">{self._escape_html(line)}</span>')
                elif line.startswith('-') and not line.startswith('---'):
                    colored.append(f'<span style="color: #E74C3C;">{self._escape_html(line)}</span>')
                elif line.startswith('@@'):
                    colored.append(f'<span style="color: #3498DB;">{self._escape_html(line)}</span>')
                else:
                    colored.append(self._escape_html(line))
            
            self.diff_viewer.setHtml(f'<pre>{"<br>".join(colored)}</pre>')
        else:
            if change_type == 'added':
                self.diff_viewer.setPlainText("(New file - no previous version)")
            elif change_type == 'removed':
                self.diff_viewer.setPlainText("(Deleted file - only in reference)")
            else:
                self.diff_viewer.setPlainText("(No diff available)")
    
    def _escape_html(self, text):
        """Escape HTML special characters."""
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')