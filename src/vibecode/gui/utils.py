"""
GUI Utilities and Constants.
Contains default extensions, color presets, and theme helpers.
"""

import os
import sys
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

# --- DEFAULT EXTENSIONS ---
DEFAULT_EXTENSIONS = [
    '.py', '.md', '.yaml', '.yml', '.json', '.js', '.ts',
    '.jsx', '.tsx', '.cpp', '.c', '.h', '.hpp', '.cs',
    '.java', '.go', '.rs', '.rb', '.php', '.swift', '.kt',
    '.css', '.scss', '.sass', '.html', '.xml', '.sql',
    '.txt', '.toml', '.ini', '.cfg', '.sh', '.bat', '.ps1'
]

EXTENSION_PRESETS = {
    'Python': ['.py', '.md', '.yaml', '.yml', '.json', '.txt', '.toml', '.ini', '.cfg', '.sh'],
    'Web': ['.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss', '.sass', '.json', '.md'],
    'C/C++': ['.c', '.cpp', '.h', '.hpp', '.md', '.txt', '.cmake'],
    'Java': ['.java', '.xml', '.json', '.md', '.properties', '.yaml', '.yml'],
    'Go': ['.go', '.mod', '.sum', '.md', '.yaml', '.yml', '.json'],
    'Rust': ['.rs', '.toml', '.md', '.json'],
}

# --- COLOR PRESETS ---
PROJECT_COLORS = {
    'None': '',
    'Red': '#E74C3C',
    'Orange': '#E67E22', 
    'Yellow': '#F1C40F',
    'Green': '#2ECC71',
    'Blue': '#3498DB',
    'Purple': '#9B59B6',
    'Pink': '#E91E63',
    'Cyan': '#00BCD4',
}

# --- THEME FUNCTIONS ---
def apply_dark_theme(app):
    """Apply dark theme to the application."""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)


def apply_light_theme(app):
    """Apply light theme to the application."""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 100, 200))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    app.setPalette(palette)
