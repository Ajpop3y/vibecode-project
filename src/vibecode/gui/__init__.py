
import sys
from PyQt6.QtWidgets import QApplication
from .utils import apply_dark_theme
from .main_window import MainWindow

def run_gui():
    """Entry point for the GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Vibecode")
    
    # Load settings to check theme preference
    # We create a temporary window instance or just load settings directly 
    # But MainWindow handles its own settings loading, so we just set defaults.
    # To properly set theme at startup before showing window:
    from ..settings import get_settings
    settings = get_settings()
    
    if settings.theme == 'dark':
        apply_dark_theme(app)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
