from datetime import date

import pandas as pd

from job_trawler.models import SearchRequest
from job_trawler.sources.jobspy_source import JobSpySource, to_posting

ROW = {
    "site": "indeed",
    "job_url": "https://www.indeed.com/viewjob?jk=abc",
    "job_url_direct": None,
    "title": "Bartender",
    "company": "The Thirsty Crow",
    "location": {"city": "Los Angeles", "state": "CA", "country": "usa"},
    "date_posted": date(2026, 11, 12),
    "min_amount": 18.0,
    "max_amount": 20.5,
    "interval": "hourly",
    "is_remote": False,
    "description": "Craft cocktail bar...",
}


def test_maps_a_full_row():
    p = to_posting(ROW)
    assert p.source == "jobspy:indeed"
    assert p.location == "Los Angeles, CA"
    assert p.pay == "$18-$20.50/hr"
    assert p.posted_on == date(2026, 11, 12)


def test_prefers_direct_url_when_present():
    p = to_posting(ROW | {"job_url_direct": "https://bar.example/apply"})
    assert p.url == "https://bar.example/apply"


def test_nan_values_become_none():
    nan = float("nan")
    p = to_posting(ROW | {"company": nan, "min_amount": nan, "max_amount": nan, "location": nan})
    assert p.company is None and p.pay is None and p.location is None


def test_row_without_url_or_title_is_dropped():
    assert to_posting(ROW | {"job_url": None}) is None
    assert to_posting(ROW | {"title": float("nan")}) is None


def test_yearly_pay_has_no_cents():
    assert to_posting(ROW | {"min_amount": 90000.0, "max_amount": 120000.0, "interval": "yearly"}).pay \
        == "$90,000-$120,000/yr"


def test_fetch_passes_request_through_and_maps_rows():
    calls = {}

    def fake_scrape(**kwargs):
        calls.update(kwargs)
        return pd.DataFrame([ROW])

    req = SearchRequest(query="bartender", location="LA 90026", radius_mi=25, max_age_hours=48, limit=5)
    out = JobSpySource(scrape=fake_scrape).fetch(req)
    assert [p.title for p in out] == ["Bartender"]
    assert calls["distance"] == 25 and calls["hours_old"] == 48 and calls["search_term"] == "bartender"
