#!/bin/sh
# Set up the project on macOS: Python 3 (via Homebrew if missing), venv, dependencies.
# Nothing is signed, notarized or installed system-wide beyond Homebrew's python (if needed).
set -e
cd "$(dirname "$0")/.."

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This script is for macOS (Darwin)." >&2; exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "python3 not found and Homebrew is missing. Install one of them first:" >&2
    echo "  https://brew.sh   or   https://www.python.org/downloads/macos/" >&2
    exit 1
  fi
  brew install python
fi

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

[ -f cache/manuscripts.json ] || .venv/bin/python scripts/fetch_labels.py || \
  echo "Warning: could not fetch shelfmarks (offline?); rerun scripts/fetch_labels.py later." >&2

chmod +x run.sh
echo "Done. Start with: ./run.sh   (then open http://localhost:8000)"
