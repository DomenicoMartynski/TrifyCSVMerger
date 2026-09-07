#!/usr/bin/env bash
#
# Build the macOS app: "Trify CSV Merger.app"
# Double-click this file (or run it in Terminal). The finished app lands in
# the `dist/` folder — drag it to /Applications.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Trify CSV Merger — macOS build"
echo

# Pick a Python that ships Tkinter. pyenv builds often lack it; the python.org
# framework build is preferred.
PYTHON_BIN=""
for cand in \
  "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" \
  "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" \
  "$(command -v python3 || true)"; do
  if [ -n "$cand" ] && [ -x "$cand" ] && "$cand" -c "import tkinter" >/dev/null 2>&1; then
    PYTHON_BIN="$cand"; break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: No Python with Tkinter found."
  echo "Install Python from https://www.python.org/downloads/ (it includes Tkinter),"
  echo "then run this script again."
  read -r -p "Press Enter to close..."
  exit 1
fi
echo "Using Python: $PYTHON_BIN"

# Fresh virtual environment for a clean build.
rm -rf .venv_build
"$PYTHON_BIN" -m venv .venv_build
# shellcheck disable=SC1091
source .venv_build/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt pyinstaller pillow

# Regenerate the icon (safe to re-run).
python build/make_icon.py

echo
echo "==> Packaging with PyInstaller…"
rm -rf build/CSVMerger build/__pycache__ "dist/Trify CSV Merger.app"
pyinstaller build/CSVMerger.spec --noconfirm --distpath dist --workpath build/_work

# onedir mode leaves a plain support folder next to the .app — remove it so
# only the self-contained app remains.
rm -rf "dist/Trify CSV Merger"

echo
echo "==================================================================="
echo " Done!  Your app is here:"
echo "   dist/Trify CSV Merger.app"
echo
echo " Drag it into your Applications folder, then open it normally."
echo " First launch: right-click the app → Open (to bypass Gatekeeper once)."
echo "==================================================================="
echo
read -r -p "Press Enter to close..."
