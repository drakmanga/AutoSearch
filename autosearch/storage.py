import json
import sqlite3
from datetime import date
from pathlib import Path

from . import filters, places
from .config import Filters
from .models import Job

COLUMNS = {
    "source": "TEXT", "id": "TEXT", "title": "TEXT", "company": "TEXT", "location": "TEXT",
    "url": "TEXT", "posted": "TEXT", "score": "INTEGER", "matched": "INTEGER",
    "description": "TEXT", "reasons": "TEXT", "salary": "TEXT", "remote_only": "INTEGER DEFAULT 0",
    "deadline": "TEXT", "years": "INTEGER", "breakdown": "TEXT", "workplace": "TEXT",
    # set by the user
    "status": "TEXT DEFAULT 'new'", "notes": "TEXT DEFAULT ''", "applied_at": "TEXT", "status_at": "TEXT",
}
# new -> interested -> applied -> interview -> offer | rejected ; discarded at any point
STATUSES = {"new", "interested", "applied", "interview", "offer", "rejected", "discarded"}
APPLICATION = {"applied", "interview", "offer", "rejected"}


class Store:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        cols = ", ".join(f"{k} {v}" for k, v in COLUMNS.items())
        self.db.execute(
            f"CREATE TABLE IF NOT EXISTS jobs ({cols},"
            " seen_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (source, id))"
        )
        existing = {r["name"] for r in self.db.execute("PRAGMA table_info(jobs)")}
        for k, v in COLUMNS.items():
            if k not in existing:
                self.db.execute(f"ALTER TABLE jobs ADD COLUMN {k} {v}")
        self.db.commit()

    def seen(self, job: Job) -> bool:
        cur = self.db.execute("SELECT 1 FROM jobs WHERE source=? AND id=?", (job.source, job.id))
        return cur.fetchone() is not None

    def add(self, job: Job, matched: bool) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO jobs (source,id,title,company,location,url,posted,score,matched,"
            "description,reasons,salary,remote_only,deadline,years,breakdown,workplace)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (job.source, job.id, job.title, job.company, job.location, job.url, job.posted,
             job.score, int(matched), job.description, ", ".join(job.reasons), job.salary,
             int(job.remote_only), job.deadline, job.years, json.dumps(job.breakdown), job.workplace),
        )
        self.db.commit()

    def listed(self) -> list[dict]:
        """Jobs shown in the UI: matching ones plus anything the user has sorted."""
        rows = self.db.execute(
            "SELECT source,id,title,company,location,url,posted,score,description,reasons,salary,"
            "deadline,years,breakdown,workplace,status,notes,applied_at,status_at,seen_at"
            " FROM jobs WHERE matched=1 OR status!='new'"
        )
        return [{**dict(r), "breakdown": json.loads(r["breakdown"] or "[]"), "place": places.italian(r["location"])}
                for r in rows]

    def update(self, source: str, job_id: str, status: str | None = None, notes: str | None = None) -> None:
        if status is not None:
            if status not in STATUSES:
                raise ValueError(status)
            self.db.execute("UPDATE jobs SET status=?, status_at=datetime('now') WHERE source=? AND id=?",
                            (status, source, job_id))
            if status == "applied":  # first time only: keeps the real application date
                self.db.execute("UPDATE jobs SET applied_at=date('now','localtime')"
                                " WHERE source=? AND id=? AND applied_at IS NULL", (source, job_id))
        if notes is not None:
            self.db.execute("UPDATE jobs SET notes=? WHERE source=? AND id=?", (notes[:5000], source, job_id))
        self.db.commit()

    def rescore(self, f: Filters) -> int:
        """Re-apply filters to every stored job (after settings change). Return matching count."""
        rows = self.db.execute(
            "SELECT source,id,title,company,location,url,posted,description,salary,remote_only,deadline FROM jobs"
        ).fetchall()
        n = 0
        for r in rows:
            job = Job(**{**dict(r), "description": r["description"] or "", "salary": r["salary"] or "",
                         "remote_only": bool(r["remote_only"]), "deadline": r["deadline"] or ""})
            ok = filters.evaluate(job, f)
            n += ok
            self.db.execute(
                "UPDATE jobs SET score=?, reasons=?, salary=?, years=?, breakdown=?, workplace=?, matched=?"
                " WHERE source=? AND id=?",
                (job.score, ", ".join(job.reasons), job.salary, job.years, json.dumps(job.breakdown), job.workplace,
                 int(ok), job.source, job.id),
            )
        self.db.commit()
        return n

    def backup(self, keep: int = 10) -> Path:
        """Daily copy of the database in data/backup/, keeping the latest `keep`."""
        folder = self.path.parent / "backup"
        folder.mkdir(exist_ok=True)
        target = folder / f"jobs-{date.today():%Y-%m-%d}.db"
        dst = sqlite3.connect(target)
        with dst:
            self.db.backup(dst)
        dst.close()
        for old in sorted(folder.glob("jobs-*.db"))[:-keep]:
            old.unlink()
        return target
