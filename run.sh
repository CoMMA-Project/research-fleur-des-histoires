#!/bin/sh
# usage: ./run.sh [port] [--lan]
#   port   default 8000 (or set PORT)
#   --lan  listen on all interfaces so other machines on the local network can connect
cd "$(dirname "$0")"
PORT="${PORT:-8000}"; HOST=127.0.0.1
for a in "$@"; do
  case "$a" in
    --lan) HOST=0.0.0.0 ;;
    *) PORT="$a" ;;
  esac
done
if [ "$HOST" = 0.0.0.0 ]; then
  for ip in $(hostname -I 2>/dev/null); do echo "On the network: http://$ip:$PORT"; done
fi
exec .venv/bin/uvicorn backend.app:app --reload --host "$HOST" --port "$PORT"
