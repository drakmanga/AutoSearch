r"""Entry point of the packaged Windows build (AutoSearch.exe).

Same behaviour as run.sh: start the web server if it is not already
up, then open the page. Installed under Program Files the app cannot write next
to its own files, so the working directory moves to %LOCALAPPDATA%\AutoSearch
and every relative path downstream (config.yaml, data/jobs.db, data/web.log,
data/server.pid) lands there, exactly as it does on Linux.
"""
import os
import shutil
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"
STARTUP_TIMEOUT = 20  # seconds to wait for the server before opening the page anyway


def data_home() -> Path:
    """Per-user folder holding config.yaml and data/ (survives updates and uninstall)."""
    base = os.environ.get("LOCALAPPDATA") or Path.home()
    return Path(base) / "AutoSearch"


def repo_root() -> Path:
    """Checkout root, one level above this file."""
    return Path(__file__).resolve().parent.parent


def bundled(name: str) -> Path:
    """A file shipped inside the build (PyInstaller unpacks it under sys._MEIPASS)."""
    root = getattr(sys, "_MEIPASS", None)
    return Path(root) / name if root else repo_root() / name


def server_up() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/status", timeout=1):
            return True
    except Exception:
        return False


def open_when_ready() -> None:
    for _ in range(STARTUP_TIMEOUT):
        if server_up():
            break
        time.sleep(1)
    webbrowser.open(URL)


def main() -> int:
    home = data_home()
    (home / "data").mkdir(parents=True, exist_ok=True)
    os.chdir(home)

    config = home / "config.yaml"
    if not config.exists():  # first run: start from the shipped example
        shutil.copyfile(bundled("config.example.yaml"), config)

    if server_up():  # already running (e.g. second double click): just show the page
        webbrowser.open(URL)
        return 0

    # windowed build has no console: logging and tracebacks would hit a None
    # stream, so send both to data/web.log
    log = open(home / "data" / "web.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log

    threading.Thread(target=open_when_ready, daemon=True).start()

    if not getattr(sys, "frozen", False):  # run from source: importable without PYTHONPATH
        sys.path.insert(0, str(repo_root()))

    from autosearch.web import main as serve

    sys.argv = ["autosearch.web", "--config", str(config), "--port", str(PORT)]
    serve()  # returns on idle shutdown, 15 min after the page is closed
    return 0


if __name__ == "__main__":
    sys.exit(main())
