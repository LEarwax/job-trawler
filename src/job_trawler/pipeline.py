"""The core. Knows about Lanes, SearchRequests and Postings, and nothing about
JobSpy, Notion, SQLite or the Anthropic API. Sources are passed in; "today" is
passed in too, so nothing here depends on the real clock.

Pipeline:  lane -> requests -> fetch (per source) -> dedup within this run
           -> drop stale -> drop excluded titles -> newest first
"""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from job_trawler.config import Lane, LocalConfig
from job_trawler.fingerprint import fingerprint, normalize
from job_trawler.models import Posting, SearchRequest
from job_trawler.sources.base import Source


@dataclass
class LaneRun:
    lane: str
    postings: list[Posting] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)   # one bad source must not sink the run
    fetched: int = 0                                  # raw count, before dedup
    stale: int = 0                                    # dropped as too old
    excluded: int = 0                                 # dropped by exclude_title_words


def build_requests(lane: Lane, cfg: LocalConfig) -> list[SearchRequest]:
    return [
        SearchRequest(
            query=q,
            location=lane.location(cfg),
            radius_mi=lane.radius(cfg),
            max_age_hours=lane.max_age_hours,
            limit=lane.results_per_query,
        )
        for q in lane.queries
    ]


def dedup(postings: list[Posting]) -> list[Posting]:
    """Keep the first posting per fingerprint (same company + title + city, or same URL)."""
    seen: set[str] = set()
    out = []
    for p in postings:
        fp = fingerprint(p)
        if fp not in seen:
            seen.add(fp)
            out.append(p)
    return out


def is_fresh(p: Posting, max_age_hours: int, today: date) -> bool:
    """Boards mostly report a date, not a time, so this works in whole days and errs
    on the side of keeping: 48h allows today and the two days before.
    Postings with no date are kept; the source's own hours_old filter already applied."""
    if p.posted_on is None:
        return True
    oldest_ok = today - timedelta(days=math.ceil(max_age_hours / 24))
    return p.posted_on >= oldest_ok


def is_excluded(p: Posting, exclude_words: list[str]) -> bool:
    """Whole-word match on the normalized title, so 'manager' drops 'F&B Manager'
    but 'bar' would not drop 'Barback'. Multi-word phrases work too ('line cook')."""
    title = f" {normalize(p.title)} "
    return any(f" {normalize(w)} " in title for w in exclude_words if normalize(w))


def newest_first(postings: list[Posting]) -> list[Posting]:
    return sorted(postings, key=lambda p: p.posted_on or date.min, reverse=True)


def run_lane(lane: Lane, cfg: LocalConfig, sources: list[Source], today: date) -> LaneRun:
    run = LaneRun(lane=lane.name)
    collected: list[Posting] = []
    for source in sources:
        for request in build_requests(lane, cfg):
            try:
                found = source.fetch(request)
            except Exception as e:  # isolate: record and keep going
                run.errors.append(f"{source.name} {request.query!r}: {type(e).__name__}: {e}")
                continue
            collected.extend(found)
    run.fetched = len(collected)
    unique = dedup(collected)
    fresh = [p for p in unique if is_fresh(p, lane.max_age_hours, today)]
    run.stale = len(unique) - len(fresh)
    wanted = [p for p in fresh if not is_excluded(p, lane.exclude_title_words)]
    run.excluded = len(fresh) - len(wanted)
    run.postings = newest_first(wanted)
    return run
