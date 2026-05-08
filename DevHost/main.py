"""
main.py — thin shim so the project can be run as `python main.py`
or as a PyInstaller onefile EXE compiled from app.py.
"""

import sys
from app import main

if __name__ == "__main__":
    sys.exit(main())
