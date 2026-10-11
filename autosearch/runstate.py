"""Progress of the current/last search, shared via a JSON file so the web UI also sees
searches started by the background timer."""
import json
import os
import sys
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


STILL_ACTIVE = 259  # GetExitCodeProcess code for a process that has not exited
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _alive(pid: int) -> bool:
    if not pid:
        return False
    if sys.platform == "win32":
        return _alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def _alive_windows(pid: int) -> bool:
    """On Windows os.kill() goes through TerminateProcess and raises WinError 87
    for signal 0 instead of reporting the state, which made a running search
    look interrupted. Ask the OS for the exit code instead."""
    import ctypes

    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    except (OSError, TypeError, ValueError):
        return False
    if not handle:
        return False  # no such process (or not ours to look at)
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        # a process exiting with 259 reads as alive: harmless here, the search
        # only ever ends by finishing or dying
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
