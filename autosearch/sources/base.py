from typing import Iterable, Protocol

from ..config import Search
from ..models import Job


class Source(Protocol):
    name: str
    failed: int        # requests that failed, for the health warnings
    rate_limited: int  # times the site throttled us

    def search(self, search: Search) -> Iterable[Job]: ...

    def fetch_description(self, job: Job) -> str: ...
