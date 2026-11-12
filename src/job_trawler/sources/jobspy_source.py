"""Adapter: JobSpy (Indeed, LinkedIn, ZipRecruiter, Glassdoor, Google) -> Posting.

All JobSpy-specific knowledge lives in this file. That includes its quirks:
- results come back as a pandas DataFrame, where a missing value can be NaN (not None)
- `location` is a nested object (city/state/country), dumped as a dict
- `date_posted` is a date, not a datetime
"""

import math
from datetime import date
from typing import Any, Callable

from job_trawler.models import Posting, SearchRequest

INTERVAL_SUFFIX = {"hourly": "/hr", "daily": "/day", "weekly": "/wk", "monthly": "/mo", "yearly": "/yr"}


def _clean(value: Any) -> Any:
    """NaN, NaT and empty strings become None. Everything else passes through."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if type(value).__name__ == "NaTType":
        return None
    return value


def _format_location(loc: Any) -> str | None:
    loc = _clean(loc)
    if loc is None:
        return None
    if isinstance(loc, str):
        return loc
    if isinstance(loc, dict):
        parts = [_clean(loc.get("city")), _clean(loc.get("state"))]
        return ", ".join(str(p) for p in parts if p) or None
    return str(loc)


def _format_pay(row: dict) -> str | None:
    low, high = _clean(row.get("min_amount")), _clean(row.get("max_amount"))
    if low is None and high is None:
        return None
    interval = _clean(row.get("interval"))
    interval = getattr(interval, "value", interval)  # enum or plain string
    suffix = INTERVAL_SUFFIX.get(str(interval).lower(), "") if interval else ""
    def fmt(n: float) -> str:
        # $18/hr and $18.50/hr, but $90,000/yr (no cents on salaries)
        if suffix == "/hr" and n != int(n):
            return f"${n:,.2f}"
        return f"${n:,.0f}"

    if low is not None and high is not None and low != high:
        return f"{fmt(low)}-{fmt(high)}{suffix}"
    return f"{fmt(low if low is not None else high)}{suffix}"


def to_posting(row: dict) -> Posting | None:
    """Map one JobSpy row to a Posting. Pure function: no network, easy to test.
    Returns None for rows without the two fields we can't do without (url, title)."""
    url = _clean(row.get("job_url_direct")) or _clean(row.get("job_url"))
    title = _clean(row.get("title"))
    if not url or not title:
        return None
    posted = _clean(row.get("date_posted"))
    return Posting(
        source=f"jobspy:{_clean(row.get('site')) or 'unknown'}",
        url=str(url),
        title=str(title),
        company=_clean(row.get("company")),
        location=_format_location(row.get("location")),
        posted_on=posted if isinstance(posted, date) else None,
        pay=_format_pay(row),
        remote=_clean(row.get("is_remote")),
        description=str(_clean(row.get("description")) or ""),
    )


class JobSpySource:
    name = "jobspy"

    def __init__(self, sites: tuple[str, ...] = ("indeed",), scrape: Callable | None = None):
        self.sites = sites
        self._scrape = scrape  # injectable so tests never touch the network

    def fetch(self, request: SearchRequest) -> list[Posting]:
        scrape = self._scrape
        if scrape is None:
            from jobspy import scrape_jobs as scrape  # lazy: heavy import, network library

        df = scrape(
            site_name=list(self.sites),
            search_term=request.query,
            location=request.location,
            distance=request.radius_mi,
            hours_old=request.max_age_hours,
            results_wanted=request.limit,
            country_indeed="usa",
            verbose=0,
        )
        errors = getattr(df, "attrs", {}).get("errors") or {}
        if errors and len(df) == 0:
            raise RuntimeError(f"jobspy returned no rows; errors: {errors}")
        postings = (to_posting(row) for row in df.to_dict(orient="records"))
        return [p for p in postings if p is not None]
