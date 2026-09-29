"""Local web UI: python -m autosearch.web  ->  http://127.0.0.1:8765"""
import argparse
import csv
import io
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config, dedupe
from .filters import WORKPLACE_LABEL
from .__main__ import AlreadyRunning, run_tracked
from .runstate import RunState
from .storage import Store

log = logging.getLogger("autosearch.web")
INDEX = Path(__file__).with_name("index.html")
IDLE_SHUTDOWN_SECONDS = 15 * 60  # exit when page closed and no search running

last_request = time.time()


def start_search(cfg_path: str) -> bool:
    cfg = config.load(cfg_path)
    if RunState(cfg.db_path).busy():
        return False

    def worker():
        try:
            run_tracked(cfg)
        except AlreadyRunning:
            pass
        except Exception:  # error is saved in status.json and shown in the page
            log.exception("search failed")

    threading.Thread(target=worker, daemon=True).start()
    time.sleep(0.3)  # let the worker write status.json before the page polls
    return True


STATUS_LABEL = {"new": "Da valutare", "interested": "Interessante", "applied": "Candidatura inviata",
                "interview": "Colloquio", "offer": "Offerta ricevuta", "rejected": "Rifiutata", "discarded": "Scartata"}
CSV_FIELDS = [("Stato", "status"), ("Titolo", "title"), ("Azienda/Ente", "company"), ("Luogo", "place"), ("Modalità", "workplace"),
              ("RAL", "salary"), ("Punteggio", "score"), ("Anni richiesti", "years"), ("Pubblicata", "posted"),
              ("Scadenza", "deadline"), ("Candidatura inviata il", "applied_at"), ("Note", "notes"),
              ("Fonte", "source"), ("Link", "url")]


def export_csv(jobs: list[dict]) -> bytes:
    """CSV for Excel (Italian locale: ';' separator, BOM so accents show correctly)."""
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow([h for h, _ in CSV_FIELDS])
    order = list(STATUS_LABEL)
    for j in sorted(jobs, key=lambda j: (order.index(j["status"]), -j["score"])):
        w.writerow([STATUS_LABEL[j["status"]] if k == "status"
                    else WORKPLACE_LABEL.get(j[k] or "", "") if k == "workplace"
                    else ("" if j[k] is None else j[k]) for _, k in CSV_FIELDS])
    return ("\ufeff" + out.getvalue()).encode("utf-8")


def make_handler(cfg_path: str, store: Store, status: RunState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body: bytes, ctype: str, code: int = 200, headers: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, code: int = 200):
            self._send(json.dumps(data).encode(), "application/json", code)

        def _body(self) -> dict:
            return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

        def do_GET(self):
            global last_request
            last_request = time.time()
            if self.path == "/":
                self._send(INDEX.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/jobs":
                self._json(dedupe.group(store.listed()))
            elif self.path == "/api/export.csv":
                self._send(export_csv(store.listed()), "text/csv; charset=utf-8",
                           headers={"Content-Disposition": 'attachment; filename="offerte.csv"'})
            elif self.path == "/api/status":
                self._json(status.read())
            elif self.path == "/api/settings":
                self._json(config.get_settings(cfg_path))
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            global last_request
            last_request = time.time()
            parts = self.path.strip("/").split("/")
            try:
                if self.path == "/api/search":
                    self._json({"started": start_search(cfg_path)})
                elif self.path == "/api/settings":
                    config.save_settings(cfg_path, self._body())
                    self._json({"ok": True, "matched": store.rescore(config.load(cfg_path).filters)})
                elif len(parts) == 4 and parts[:2] == ["api", "job"]:
                    # /api/job/<source>/<id>  body: {"status"?: ..., "notes"?: ...}
                    body = self._body()
                    store.update(parts[2], parts[3], status=body.get("status"), notes=body.get("notes"))
                    self._json({"ok": True})
                else:
                    self._json({"error": "not found"}, 404)
            except (ValueError, KeyError, TypeError) as e:
                self._json({"error": f"richiesta non valida: {e}"}, 400)

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(prog="autosearch.web")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db_path = config.load(args.config).db_path
    store, status = Store(db_path), RunState(db_path)
    # run.sh restarts the server when the code is newer than this file
    (Path(db_path).parent / "server.pid").write_text(str(os.getpid()))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.config, store, status))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("http://127.0.0.1:%d", args.port)
    while True:
        time.sleep(30)
        if time.time() - last_request > IDLE_SHUTDOWN_SECONDS and not status.busy():
            log.info("idle, shutting down")
            server.shutdown()
            return


if __name__ == "__main__":
    main()
