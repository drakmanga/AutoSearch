"""Progress of the current/last search, shared via a JSON file so the web UI also sees
searches started by the background timer."""
import json
import os
from pathlib import Path


class RunState:
    def __init__(self, db_path: str):
        self.path = Path(db_path).parent / "status.json"

    def read(self) -> dict:
        try:
            state = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {"running": False}
        if state.get("running") and not _alive(state.get("pid", 0)):
            state.update(running=False, error="ricerca interrotta")
        return state

    def busy(self) -> bool:
        return self.read().get("running", False)

    def save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        tmp.replace(self.path)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False
