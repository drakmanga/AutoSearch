from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Search:
    source: str = "linkedin"  # linkedin | inpa
    keywords: str = ""
    location: str = ""
    remote: list[str] = field(default_factory=list)      # onsite | remote | hybrid
    experience: list[str] = field(default_factory=list)  # internship | entry | associate | mid_senior | director | executive
    posted_within_hours: int = 24
    max_results: int = 50
    location_must_contain: list[str] = field(default_factory=list)  # LinkedIn search uses a radius; keep only these


@dataclass
class Filters:
    must_have: list[str] = field(default_factory=list)     # all required (title+description)
    nice_to_have: dict[str, int] = field(default_factory=dict)  # word -> weight (doubled if in title)
    exclude: list[str] = field(default_factory=list)       # discard if present (title+description)
    exclude_title: list[str] = field(default_factory=list) # discard if present in title
    exclude_required_languages: list[str] = field(default_factory=list)  # discard if required, ok if optional
    exclude_companies: list[str] = field(default_factory=list)
    min_score: int = 0
    max_years: int = 0              # 0 = off; jobs asking more years get grade C (or are dropped)
    years_action: str = "grade_c"   # grade_c | exclude


@dataclass
class Config:
    searches: list[Search]
    filters: Filters
    grades: dict[str, int] = field(default_factory=lambda: {"A": 10, "B": 5})  # min score per grade
    fetch_descriptions: bool = True
    request_delay_seconds: float = 3.0
    db_path: str = "data/jobs.db"


def _weights(value) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(k): int(v) for k, v in value.items()}
    return {str(w): 1 for w in value or []}


def _as_list(value) -> list[str]:
    return [value] if isinstance(value, str) else list(value or [])


def load(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    keywords = raw.get("keywords", [])
    filters = dict(raw.get("filters", {}))
    filters["nice_to_have"] = _weights(filters.get("nice_to_have"))
    return Config(
        # each search runs once per keyword; searches without keywords use the
        # top-level list for their source (keywords_<source>, else keywords)
        searches=[
            Search(**{**s, "keywords": kw,
                      "posted_within_hours": 24 * raw.get("posted_within_days", 0) or s.get("posted_within_hours", 24)})
            for s in raw.get("searches", [])
            for kw in _as_list(s.get("keywords") or raw.get(f"keywords_{s.get('source', 'linkedin')}", keywords))
        ],
        filters=Filters(**filters),
        grades=raw.get("grades", {"A": 10, "B": 5}),
        fetch_descriptions=raw.get("fetch_descriptions", True),
        request_delay_seconds=raw.get("request_delay_seconds", 3.0),
        db_path=raw.get("db_path", "data/jobs.db"),
    )


# --- settings editable from the web UI ---

LIST_FILTERS = ["exclude", "exclude_title", "exclude_companies", "exclude_required_languages", "must_have"]
HEADER = "# Modificabile anche dalla pagina web (Impostazioni). Salvando dalla pagina i commenti si perdono.\n\n"


def get_settings(path: str | Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    f = raw.get("filters", {})
    return {
        "keywords": _as_list(raw.get("keywords", [])),
        "keywords_inpa": _as_list(raw.get("keywords_inpa", [])),
        "posted_within_days": int(raw.get("posted_within_days", 7)),
        "nice_to_have": _weights(f.get("nice_to_have")),
        **{k: _as_list(f.get(k)) for k in LIST_FILTERS},
        "min_score": int(f.get("min_score", 0)),
        "max_years": int(f.get("max_years", 0)),
        "years_action": f.get("years_action", "grade_c"),
        "grades": raw.get("grades", {"A": 10, "B": 5}),
        **schedule(raw),
    }


def schedule(raw: dict) -> dict:
    """Automatic searches: on the given weekdays (0 = Monday) at the given HH:MM times."""
    sch = raw.get("schedule") or {}
    return {
        "schedule_enabled": bool(sch.get("enabled", False)),
        "schedule_days": sorted({int(d) for d in sch.get("days", range(7))}),
        "schedule_times": sorted({_hhmm(t) for t in _as_list(sch.get("times", []))}),
        "timezone": raw.get("timezone", "Europe/Rome"),
    }


def _hhmm(value) -> str:
    if isinstance(value, int):  # YAML reads an unquoted 18:30 as 1110 (base 60)
        value = f"{value // 60}:{value % 60}"
    h, m = (int(x) for x in str(value).strip().split(":"))
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"orario {value}")
    return f"{h:02d}:{m:02d}"


def save_settings(path: str | Path, data: dict) -> None:
    def clean(items):
        return list(dict.fromkeys(str(i).strip() for i in items if str(i).strip()))

    raw = yaml.safe_load(Path(path).read_text()) or {}
    raw["keywords"] = clean(data["keywords"])
    raw["keywords_inpa"] = clean(data.get("keywords_inpa", []))
    raw["posted_within_days"] = max(1, min(30, int(data.get("posted_within_days", 7))))
    for s in raw.get("searches", []):
        s.pop("posted_within_hours", None)  # the global setting applies to every search
    f = raw.setdefault("filters", {})
    f["nice_to_have"] = {k.strip(): max(1, min(3, int(v))) for k, v in data["nice_to_have"].items() if k.strip()}
    for k in LIST_FILTERS:
        f[k] = clean(data.get(k, []))
    f["min_score"] = max(0, int(data["min_score"]))
    f["max_years"] = max(0, int(data.get("max_years", 0)))
    if data.get("years_action", "grade_c") not in ("grade_c", "exclude"):
        raise ValueError("years_action")
    f["years_action"] = data.get("years_action", "grade_c")
    raw["grades"] = {"A": int(data["grades"]["A"]), "B": int(data["grades"]["B"])}
    if "schedule_enabled" in data:
        raw["schedule"] = {
            "enabled": bool(data["schedule_enabled"]),
            "days": sorted({int(d) for d in data.get("schedule_days", []) if 0 <= int(d) <= 6}),
            "times": sorted({_hhmm(t) for t in data.get("schedule_times", [])}),
        }

    # keep a readable key order
    order = ["keywords", "keywords_inpa", "posted_within_days", "schedule", "searches", "filters", "grades"]
    raw = {**{k: raw[k] for k in order if k in raw}, **{k: v for k, v in raw.items() if k not in order}}
    tmp = Path(path).with_suffix(".tmp")
    tmp.write_text(HEADER + yaml.safe_dump(raw, sort_keys=False, allow_unicode=True, width=100))
    tmp.replace(path)
