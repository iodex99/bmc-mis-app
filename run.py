"""Launch script — also the PyInstaller entry point.

Run from source:  python run.py
"""

import sys

from app.main import main

if __name__ == "__main__":
    sys.exit(main())
