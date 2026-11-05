# Lives ↔ manuscripts browser

**macOS:** `./scripts/install_mac.sh` does the setup below in one step (needs Python 3 or Homebrew; nothing is signed).

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python scripts/fetch_labels.py   # shelfmarks from Biblissima -> cache/manuscripts.json
    ./run.sh [port] [--lan]                    # default http://localhost:8000; --lan = reachable from the local network
    .venv/bin/python -m pytest tests

Browse lives/manuscripts (ranked candidate sources, folio order), or detect networks (Louvain on
weighted-Jaccard projections; tune cover/hits thresholds, drop hub manuscripts).
