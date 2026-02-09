"""
Entry point for running VibeCode as a module.
Usage: python -m vibecode [command]
"""
# This file enables running the tool via `python -m vibecode`
from .cli import app

if __name__ == "__main__":
    app()