import sys
import os

# Force 'src' to be the first path in sys.path to take precedence over installed packages
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

print(f"Running Vibecode from: {src_dir}")

from vibecode.gui import run_gui

if __name__ == "__main__":
    run_gui()
