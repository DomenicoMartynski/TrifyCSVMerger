#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python is not installed. Please install Python 3."
  echo
  read -r -p "Press Enter to close..."
  exit 1
fi

"$PYTHON_BIN" "merge_txt_to_csv_format.py" || {
  echo
  echo "Merge failed. Check messages above."
  read -r -p "Press Enter to close..."
  exit 1
}

echo
echo "Merge completed successfully."
read -r -p "Press Enter to close..."
