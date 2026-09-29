"""Local web UI: python -m autosearch.web  ->  http://127.0.0.1:8765"""
import argparse
import csv
import io
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, dedupe
from .filters import WORKPLACE_LABEL
from .__main__ import AlreadyRunning, run_tracked
from .runstate import RunState
from .storage import Store

log = logging.getLogger("autosearch.web")
INDEX = Path(__file__).with_name("index.html")
IDLE_SHUTDOWN_SECONDS = 15 * 60  # exit when page closed and no search running (unless a schedule is on)
FAVICON = Path(__file__).with_name("favicon.svg")
TOUCH_ICON = Path(__file__).with_name("icon-180.png")

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


def next_auto(cfg_path: str, after: datetime | None = None) -> datetime | None:
    """First scheduled search strictly after `after` (default: now), or None if the schedule is off."""
    s = config.get_settings(cfg_path)
    if not (s["schedule_enabled"] and s["schedule_days"] and s["schedule_times"]):
        return None
    tz = ZoneInfo(s["timezone"])
    after = (after or datetime.now(tz)).astimezone(tz)
    for d in range(8):
        day = after.date() + timedelta(days=d)
        if day.weekday() not in s["schedule_days"]:
            continue
        for t in s["schedule_times"]:
            h, m = map(int, t.split(":"))
            at = datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
            if at > after:
                return at
    return None


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
                nxt = next_auto(cfg_path)
                self._json({**status.read(), "next_auto": nxt.isoformat() if nxt else None})
            elif self.path == "/favicon.svg":
                self._send(FAVICON.read_bytes(), "image/svg+xml", headers={"Cache-Control": "max-age=86400"})
            elif self.path in ("/favicon.ico", "/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"):
                self._send(TOUCH_ICON.read_bytes(), "image/png", headers={"Cache-Control": "max-age=86400"})
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
    p.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to reach it from the LAN")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-idle-shutdown", action="store_true", help="keep running (for a systemd service)")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db_path = config.load(args.config).db_path
    store, status = Store(db_path), RunState(db_path)
    # run.sh restarts the server when the code is newer than this file
    (Path(db_path).parent / "server.pid").write_text(str(os.getpid()))
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.config, store, status))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("http://%s:%d", args.host, args.port)
    last_check = datetime.now().astimezone()
    while True:
        time.sleep(20)
        now = datetime.now().astimezone()
        try:
            due, upcoming = next_auto(args.config, last_check), next_auto(args.config, now)
        except Exception:  # bad schedule in config.yaml: log it, keep serving
            log.exception("schedule")
            due = upcoming = None
        last_check = now
        if due and due <= now:
            log.info("scheduled search (%s)", due.strftime("%a %H:%M"))
            start_search(args.config)
        if (not args.no_idle_shutdown and time.time() - last_request > IDLE_SHUTDOWN_SECONDS
                and not status.busy() and not upcoming):
            log.info("idle, shutting down")
            server.shutdown()
            return


if __name__ == "__main__":
    main()
