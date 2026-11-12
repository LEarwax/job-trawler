"""The port: the one interface every source adapter implements.

A Protocol (structural typing): any class with a matching `name` and `fetch`
counts as a Source. No inheritance needed, which keeps fakes in tests trivial.
"""

from typing import Protocol

from job_trawler.models import Posting, SearchRequest


class Source(Protocol):
    name: str

    def fetch(self, request: SearchRequest) -> list[Posting]:
        """Return postings for one request. Raise on failure; the pipeline isolates errors."""
        ...
