"""inPA: public administration job portal (concorsi pubblici). Public JSON API used by inpa.gov.it."""
import logging
import time
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from ..config import Search
from ..models import Job

log = logging.getLogger(__name__)

SEARCH_URL = "https://portale.inpa.gov.it/concorsi-smart/api/concorso-public-area/search-better"
DETAIL_URL = "https://www.inpa.gov.it/bandi-e-avvisi/dettaglio-bando-avviso/?concorso_id={id}"
PAGE_SIZE = 50


def _euro(n) -> str:
    return f"€ {int(n):,}".replace(",", ".")


class InPA:
    name = "inpa"

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.failed = 0  # requests that failed (health check)
        self.rate_limited = 0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) Chrome/128.0"

    def search(self, search: Search) -> Iterable[Job]:
        found = 0
        for page in range(0, 1 + search.max_results // PAGE_SIZE):
            time.sleep(self.delay)
            try:
                r = self.session.post(SEARCH_URL, params={"page": page, "size": PAGE_SIZE},
                                      json={"text": search.keywords, "status": ["OPEN"]}, timeout=30)
                r.raise_for_status()
                data = r.json()
            except (requests.RequestException, ValueError) as e:
                log.warning("inPA search failed: %s", e)
                self.failed += 1
                return
            for x in data.get("content", []):
                yield _parse(x)
                found += 1
                if found >= search.max_results:
                    return
            if data.get("last", True):
                return

    def fetch_description(self, job: Job) -> str:
        return job.description  # already in the search result


def _parse(x: dict) -> Job:
    lo, hi = x.get("salaryMin"), x.get("salaryMax")
    salary = f"{_euro(lo)} – {_euro(hi)}" if lo and hi and lo != hi else _euro(lo or hi) if (lo or hi) else ""
    desc = BeautifulSoup(x.get("descrizione") or "", "html.parser").get_text("\n", strip=True)
    extra = [f"Posti: {x['numPosti']}" if x.get("numPosti") else "",
             f"Tipo: {x['tipoProcedura']}" if x.get("tipoProcedura") else "",
             f"Figura ricercata: {x['figuraRicercata']}" if x.get("figuraRicercata") else ""]
    return Job(
        id=x["id"],
        source="inpa",
        title=(x.get("titolo") or "").strip(),
        company=", ".join(x.get("entiRiferimento") or []),
        location=", ".join(x.get("sedi") or []),
        url=DETAIL_URL.format(id=x["id"]),
        posted=(x.get("dataPubblicazione") or "")[:10],
        deadline=(x.get("dataScadenza") or "")[:10],
        description="\n".join([e for e in extra if e] + [desc]),
        salary=salary,
    )
