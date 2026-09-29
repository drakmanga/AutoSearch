"""LinkedIn public (guest) job search. No login, no account.

Endpoints are the ones the public jobs page uses; HTML may change without notice.
Keep request volume low: LinkedIn rate-limits (HTTP 429) aggressive clients.
"""
import logging
import re
import time
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from ..config import Search
from ..models import Job

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
PAGE_SIZE = 25

WORKPLACE = {"onsite": "1", "remote": "2", "hybrid": "3"}
EXPERIENCE = {
    "internship": "1", "entry": "2", "associate": "3",
    "mid_senior": "4", "director": "5", "executive": "6",
}


class LinkedIn:
    name = "linkedin"

    def __init__(self, delay: float = 3.0):
        self.delay = delay
        self.failed = 0        # requests that gave up (health check)
        self.rate_limited = 0  # HTTP 429 responses
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
        )

    def _get(self, url: str, params: dict | None = None) -> str | None:
        for attempt in range(3):
            time.sleep(self.delay * (attempt + 1))
            try:
                r = self.session.get(url, params=params, timeout=20)
            except requests.RequestException as e:  # e.g. network not up yet after boot
                log.warning("GET %s failed: %s", url, e)
                time.sleep(20 * (attempt + 1))
                continue
            if r.status_code == 200:
                return r.text
            if r.status_code == 429:
                self.rate_limited += 1
                log.warning("rate limited, backing off")
                time.sleep(30 * (attempt + 1))
                continue
            log.warning("GET %s -> %s", r.url, r.status_code)
            self.failed += 1
            return None
        self.failed += 1
        return None

    def search(self, search: Search) -> Iterable[Job]:
        params = {
            "keywords": search.keywords,
            "location": search.location,
            "f_TPR": f"r{search.posted_within_hours * 3600}",
        }
        if search.remote:
            params["f_WT"] = ",".join(WORKPLACE[w] for w in search.remote)
        if search.experience:
            params["f_E"] = ",".join(EXPERIENCE[e] for e in search.experience)

        found = 0
        for start in range(0, search.max_results, PAGE_SIZE):
            html = self._get(SEARCH_URL, {**params, "start": start})
            if not html:
                break
            cards = BeautifulSoup(html, "html.parser").select("div.base-card")
            if not cards:
                break
            for card in cards:
                job = _parse_card(card)
                if job:
                    found += 1
                    yield job
                if found >= search.max_results:
                    return

    def fetch_description(self, job: Job) -> str:
        """Return the description; also sets job.salary from LinkedIn's pay range when the company states it."""
        html = self._get(DETAIL_URL.format(id=job.id))
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        if pay := soup.select_one("div.compensation__salary"):
            job.salary = _pay_range(pay.get_text(" ", strip=True)) or job.salary
        node = soup.select_one("div.show-more-less-html__markup")
        return node.get_text("\n", strip=True) if node else ""


def _pay_range(text: str) -> str:
    """'€28,000.00/yr - €35,000.00/yr' -> '€ 28.000 – 35.000'; '/mo' -> ' /mese'."""
    amounts = [int(float(n.replace(",", ""))) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    if not amounts:
        return ""
    fmt = lambda n: f"{n:,}".replace(",", ".")
    value = " – ".join(dict.fromkeys(fmt(n) for n in amounts[:2]))
    currency = "€ " if "€" in text else ""
    return currency + value + (" /mese" if "/mo" in text else " /ora" if "/hr" in text else "")


def _text(card, selector: str) -> str:
    node = card.select_one(selector)
    return node.get_text(strip=True) if node else ""


def _parse_card(card) -> Job | None:
    urn = card.get("data-entity-urn", "")
    job_id = urn.rsplit(":", 1)[-1]
    if not job_id:
        return None
    link = card.select_one("a.base-card__full-link")
    posted = card.select_one("time")
    return Job(
        id=job_id,
        source="linkedin",
        title=_text(card, "h3.base-search-card__title"),
        company=_text(card, "h4.base-search-card__subtitle"),
        location=_text(card, "span.job-search-card__location"),
        url=(link["href"].split("?")[0] if link else f"https://www.linkedin.com/jobs/view/{job_id}"),
        posted=posted.get("datetime", "") if posted else "",
        salary=_text(card, "span.job-search-card__salary-info"),  # only when LinkedIn shows it
    )
