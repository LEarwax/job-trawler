"""The core. Knows about Lanes, SearchRequests and Postings, and nothing about
JobSpy, Notion, SQLite or the Anthropic API. Sources are passed in.

Slice 1 pipeline:  lane -> requests -> fetch (per source) -> dedup within this run -> newest first
"""

from dataclasses import dataclass, field
from datetime import date

from job_trawler.config import Lane, LocalConfig
from job_trawler.models import Posting, SearchRequest
from job_trawler.sources.base import Source


@dataclass
class LaneRun:
    lane: str
    postings: list[Posting] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)   # one bad source must not sink the run
    fetched: int = 0                                  # before dedup, to see how much dedup removed


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
    """Keep the first posting per URL. (Slice 2 adds cross-run memory and fuzzier keys.)"""
    seen: set[str] = set()
    out = []
    for p in postings:
        if p.url not in seen:
            seen.add(p.url)
            out.append(p)
    return out


def newest_first(postings: list[Posting]) -> list[Posting]:
    return sorted(postings, key=lambda p: p.posted_on or date.min, reverse=True)


def run_lane(lane: Lane, cfg: LocalConfig, sources: list[Source]) -> LaneRun:
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
    run.postings = newest_first(dedup(collected))
    return run
