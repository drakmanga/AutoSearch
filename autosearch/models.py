from dataclasses import dataclass, field


@dataclass
class Job:
    id: str
    source: str
    title: str
    company: str
    location: str
    url: str
    posted: str = ""
    description: str = ""
    salary: str = ""
    deadline: str = ""         # application deadline (public competitions)
    years: int | None = None   # years of experience required, if stated
    workplace: str = ""        # remote | hybrid | onsite | "" (inferred from text, see filters.workplace)
    remote_only: bool = False  # found by a remote-only search: must be remote to match
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    breakdown: list[dict] = field(default_factory=list)  # per-keyword points, see filters.score
