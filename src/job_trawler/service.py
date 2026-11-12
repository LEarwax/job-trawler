"""Application service: wires the pure core to the adapters for one lane run.

    record run start -> run_lane (core) -> save_postings (SQLite) -> record run end

The CLI and, later, the scheduler call this. The core stays free of I/O.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from job_trawler.config import Lane, LocalConfig
from job_trawler.models import Posting
from job_trawler.pipeline import LaneRun, run_lane
from job_trawler.sources.base import Source
from job_trawler import storage


@dataclass
class TrawlResult:
    run: LaneRun
    new: list[Posting]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def trawl_lane(lane: Lane, cfg: LocalConfig, sources: list[Source], conn: sqlite3.Connection,
               clock: Callable[[], datetime] = utc_now) -> TrawlResult:
    run_id = storage.start_run(conn, lane.name, clock())
    run = run_lane(lane, cfg, sources, today=clock().date())
    new = storage.save_postings(conn, lane.name, run.postings, clock())
    storage.finish_run(conn, run_id, fetched=run.fetched, kept=len(run.postings), new=len(new),
                       errors=run.errors, now=clock())
    return TrawlResult(run=run, new=new)
