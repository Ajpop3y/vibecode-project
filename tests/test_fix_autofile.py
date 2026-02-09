
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

# We need to mock PyQt6 modules BEFORE importing MainWindow
# because it subclasses QMainWindow and uses other Qt classes at module level
sys.modules['PyQt6'] = MagicMock()
sys.modules['PyQt6.QtWidgets'] = MagicMock()
sys.modules['PyQt6.QtCore'] = MagicMock()
sys.modules['PyQt6.QtGui'] = MagicMock()

# Mock specific classes MainWindow inherits from or uses
class MockQMainWindow:
    def __init__(self): pass
    def setWindowTitle(self, title): pass
    def resize(self, w, h): pass
    def setCentralWidget(self, widget): pass
    def addToolBar(self, toolbar): pass
    def setStatusBar(self, statusbar): pass

# Patch all the things MainWindow uses
sys.modules['PyQt6.QtWidgets'].QMainWindow = MockQMainWindow
sys.modules['PyQt6.QtWidgets'].QWidget = MagicMock()
sys.modules['PyQt6.QtWidgets'].QVBoxLayout = MagicMock()
sys.modules['PyQt6.QtWidgets'].QHBoxLayout = MagicMock()
sys.modules['PyQt6.QtWidgets'].QLabel = MagicMock()
sys.modules['PyQt6.QtWidgets'].QLineEdit = MagicMock()
sys.modules['PyQt6.QtWidgets'].QPushButton = MagicMock()
sys.modules['PyQt6.QtWidgets'].QListWidget = MagicMock()
sys.modules['PyQt6.QtWidgets'].QTextEdit = MagicMock()
sys.modules['PyQt6.QtWidgets'].QGroupBox = MagicMock()
sys.modules['PyQt6.QtWidgets'].QSplitter = MagicMock()
sys.modules['PyQt6.QtWidgets'].QStatusBar = MagicMock()
sys.modules['PyQt6.QtWidgets'].QCheckBox = MagicMock()
sys.modules['PyQt6.QtWidgets'].QProgressBar = MagicMock()
sys.modules['PyQt6.QtWidgets'].QToolBar = MagicMock()
sys.modules['PyQt6.QtWidgets'].QSizePolicy = MagicMock()
sys.modules['PyQt6.QtWidgets'].QListWidgetItem = MagicMock()
sys.modules['PyQt6.QtCore'].QFileSystemWatcher = MagicMock()
sys.modules['PyQt6.QtCore'].QTimer = MagicMock()
sys.modules['PyQt6.QtCore'].Qt = MagicMock()
sys.modules['PyQt6.QtGui'].QAction = MagicMock()
sys.modules['PyQt6.QtGui'].QShortcut = MagicMock()
sys.modules['PyQt6.QtGui'].QKeySequence = MagicMock()


sys.modules['PyQt6.QtGui'].QKeySequence = MagicMock()

# Mock internal vibecode modules
# Mock internal vibecode modules
sys.modules['vibecode.discovery'] = MagicMock()
sys.modules['vibecode.engine'] = MagicMock()
sys.modules['vibecode.registry'] = MagicMock()
# settings is already mocked in previous tests, but good to be sure if imported by MainWindow
sys.modules['vibecode.settings'] = MagicMock()
sys.modules['vibecode.chat'] = MagicMock()
sys.modules['vibecode.chat.gui'] = MagicMock()

# Now import the class to test
import vibecode.gui.main_window
from vibecode.gui.main_window import MainWindow

# Patch FileDropListWidget in the module namespace where MainWindow uses it
vibecode.gui.main_window.FileDropListWidget = MagicMock()


class TestAutofileFix(unittest.TestCase):
    
    def setUp(self):
        # Instantiate MainWindow with mocked dependencies
        self.mw = MainWindow()
        
        # Mock internal attributes used in handle_dropped_files
        self.mw.current_project_root = os.path.abspath("/project/root")
        self.mw.list_files = MagicMock()
        self.mw.list_files.count.return_value = 0
        self.mw.text_log = MagicMock()
        self.mw.save_project = MagicMock()
        
        # Initial list state is empty
        self.mw.list_files.item = MagicMock()

    def test_handle_dropped_files_no_duplicates(self):
        """Test dropping the same file twice (relative and absolute) results in unique entry."""
        
        # Setup: Project root is /project/root
        # File to drop: /project/root/src/main.py
        abs_path = os.path.abspath("/project/root/src/main.py") # Use OS sep
        
        # 1. First Drop
        # We need to mock os.path.isfile and friends because we are using fake paths
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True):
            
            self.mw.handle_dropped_files([abs_path])
            
            # Verify it was added
            self.mw.list_files.addItem.assert_called()
            # It should add relative path: src/main.py
            args, _ = self.mw.list_files.addItem.call_args
            added_text = args[0]
            # Normalize to forward slash for comparison as per our fix
            self.assertTrue(added_text.replace('\\', '/').endswith('src/main.py'))
            
            # 2. Setup state as if it's currently in the list
            self.mw.list_files.count.return_value = 1
            mock_item = MagicMock()
            mock_item.text.return_value = added_text
            self.mw.list_files.item.side_effect = lambda i: mock_item
            
            self.mw.list_files.addItem.reset_mock()
            
            # 3. Second Drop (Same file)
            self.mw.handle_dropped_files([abs_path])
            
            # Verify NOT added again
            self.mw.list_files.addItem.assert_not_called()

    def test_ai_selection_matching(self):
        """Test AI selection matches relative items with absolute AI suggestions."""
        
        # Setup list with relative path "src/main.py"
        self.mw.list_files.count.return_value = 1
        mock_item = MagicMock()
        mock_item.text.return_value = "src/main.py" 
        self.mw.list_files.item.side_effect = lambda i: mock_item
        
        # AI returns absolute path
        selected_files = [os.path.abspath("/project/root/src/main.py")]
        
        self.mw.current_project_root = os.path.abspath("/project/root")
        self.mw.input_ai_intent = MagicMock()
        self.mw.btn_ai_select = MagicMock()
        self.mw.status_bar = MagicMock()
        
        with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=MagicMock()) as mock_msg:
            # We don't care about the user reply, just that it found matches
            self.mw.on_ai_selection_success(selected_files)
            
            # Verify items were selected
            mock_item.setSelected.assert_called_with(True)

    def test_handle_dropped_files_case_insensitive(self):
        """Test dropping the same file with different casing resulted in unique entry."""
        
        # Setup: Project root is /project/root
        # Existing file in list: src/main.py
        self.mw.list_files.count.return_value = 1
        mock_item = MagicMock()
        mock_item.text.return_value = "src/main.py"
        self.mw.list_files.item.side_effect = lambda i: mock_item
        
        # File to drop: /project/root/SRC/MAIN.PY (different case)
        abs_path_upper = os.path.abspath("/project/root/SRC/MAIN.PY")
        
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True):
             
             # We rely on os.path.abspath/normpath. On Windows, they might not change case unless file exists on disk,
             # but our logic uses os.path.normcase explictly.
             # So dropping the UPPER case file should NOT add it if 'src/main.py' is already there.
             
             self.mw.handle_dropped_files([abs_path_upper])
             
             # Should NOT be added
             self.mw.list_files.addItem.assert_not_called()

    def test_handle_dropped_files_symlink(self):
        """Test dropping a file that is a symlink/alias to an existing file."""
        
        # Setup: Project root is /project/root
        # Existing file in list: src/main.py
        # Real path: /project/root/src/main.py
        
        self.mw.list_files.count.return_value = 1
        mock_item = MagicMock()
        mock_item.text.return_value = "src/main.py"
        self.mw.list_files.item.side_effect = lambda i: mock_item
        
        # Dropped file: /alias/src/main.py
        dropped_path = os.path.abspath("/alias/src/main.py")
        canonical_path = os.path.abspath("/project/root/src/main.py")
        
        # Mock os.path.realpath to resolve /alias/... to /project/root/...
        def side_effect_realpath(path):
            # Normalize for comparison
            p = path.replace('\\', '/')
            if '/alias/src/main.py' in p:
                return canonical_path
            return path
            
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.exists', return_value=True), \
             patch('vibecode.gui.main_window.os.path.realpath', side_effect=side_effect_realpath):
             
             self.mw.handle_dropped_files([dropped_path])
             
             # Should NOT be added because realpath matches existing
             self.mw.list_files.addItem.assert_not_called()

if __name__ == '__main__':
    unittest.main()
