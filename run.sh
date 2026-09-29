#!/usr/bin/env bash
# Avvio con un click: avvia l'interfaccia web (se non già attiva) e la apre nel browser.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
PORT=8765
URL="http://127.0.0.1:$PORT"
mkdir -p data

# server started before the last code change: restart it, unless a search is running
if curl -sf "$URL/api/status" >/dev/null && [ -f data/server.pid ] \
   && [ -n "$(find autosearch -newer data/server.pid -print -quit)" ] \
   && ! curl -sf "$URL/api/status" | grep -q '"running": true'; then
    kill "$(cat data/server.pid)" 2>/dev/null
    for _ in $(seq 25); do curl -sf "$URL/api/status" >/dev/null || break; sleep 0.2; done
fi

if ! curl -sf "$URL/api/status" >/dev/null; then
    nohup .venv/bin/python -m autosearch.web --port "$PORT" >> data/web.log 2>&1 &
    for _ in $(seq 50); do
        curl -sf "$URL/api/status" >/dev/null && break
        sleep 0.2
    done
fi
xdg-open "$URL" >/dev/null 2>&1
