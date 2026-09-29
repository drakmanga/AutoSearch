"""Group duplicate postings: same job posted by several agencies, reposted with a new id,
or found on more than one site."""
import re

from .places import italian

NOISE = re.compile(r"\([^)]*\)|\[[^\]]*\]|\b[mfao]\s*/\s*[mfao]\b|[^\w\s]")
STOP = {"di", "e", "del", "della", "in", "per", "the", "and", "of", "a", "o", "il", "la", "settore", "sede"}


def _title_tokens(title: str) -> set[str]:
    words = NOISE.sub(" ", title.lower()).split()
    return {w for w in words if len(w) > 1 and w not in STOP}


def _desc_tokens(desc: str) -> set[str]:
    return {w for w in re.findall(r"\w{4,}", (desc or "").lower())}


REGIONS = {"abruzzo", "basilicata", "calabria", "campania", "emilia romagna", "emilia-romagna", "friuli venezia giulia",
           "friuli-venezia giulia", "lazio", "liguria", "lombardia", "marche", "molise", "piemonte", "puglia", "sardegna",
           "sicilia", "toscana", "trentino-alto adige", "trentino alto adige", "umbria", "valle d'aosta", "veneto"}


def _city(location: str) -> str:
    """First place that is not the country: "Rome, Latium, Italy" and "Italia, Roma" -> "roma"."""
    parts = [re.sub(r"\(.*?\)", "", p).strip().lower() for p in italian(location).split(",")]
    return next((p for p in parts if p and p != "italia" and p not in REGIONS), parts[0] if parts else "")


LEGAL = re.compile(r"\b(s\.?p\.?a|s\.?r\.?l|srls|s\.?a\.?s|group|gruppo|italia|italy)\b\.?|[^\w\s]")


def _company(name: str) -> str:
    return " ".join(LEGAL.sub(" ", (name or "").lower()).split())


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def same_job(a: dict, b: dict) -> bool:
    if _jaccard(a["_t"], b["_t"]) < 0.75:
        return False
    desc = _jaccard(a["_d"], b["_d"])
    if _company(a["company"]) == _company(b["company"]):
        # reposted, or the same posting published for several cities
        return _city(a["location"]) == _city(b["location"]) or desc >= 0.9
    # another agency posting the same job: same city and largely the same text.
    # A similar title alone is not enough ("Tender Specialist" at two different firms).
    return _city(a["location"]) == _city(b["location"]) and desc >= 0.5


def group(jobs: list[dict]) -> list[dict]:
    """Set job["group"] to the key of the best-scoring posting of its group (itself if unique).
    Only jobs with the same status are grouped, so tabs stay consistent."""
    for j in jobs:
        j["_t"], j["_d"] = _title_tokens(j["title"]), _desc_tokens(j["description"])
    groups: list[list[dict]] = []
    for j in sorted(jobs, key=lambda j: -j["score"]):
        for g in groups:
            if g[0]["status"] == j["status"] and same_job(g[0], j):
                g.append(j)
                break
        else:
            groups.append([j])
    for g in groups:
        for j in g:
            j["group"] = f'{g[0]["source"]}/{g[0]["id"]}'
    for j in jobs:
        del j["_t"], j["_d"]
    return jobs
