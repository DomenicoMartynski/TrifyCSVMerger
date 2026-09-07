#!/usr/bin/env python3
"""Trify CSV Merger — desktop app entry point.

Run directly with `python app.py`, or build a standalone app/exe with the
scripts in `build/` (PyInstaller).
"""

from csvmerger.gui import main

if __name__ == "__main__":
    main()
