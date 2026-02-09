"""
VibeChat - RAG assistant for Vibecode projects.
Enables conversational interaction with codebase snapshots.
"""

from .ingest import parse_pdf, PDFContext
from .models import BaseLLMProvider, get_provider
from .memory import ChatMemory
from .engine import ChatEngine
from .gui import ChatWindow

__all__ = [
    'ChatEngine',
    'ChatWindow',
    'parse_pdf',
    'PDFContext',
    'BaseLLMProvider',
    'get_provider',
    'ChatMemory',
]
