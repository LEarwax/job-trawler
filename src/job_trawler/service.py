"""Application service: wires the pure core to the adapters.

    trawl_lane:  record run start -> run_lane (core) -> save_postings (SQLite) -> record run end
    run_all:     trawl_lane for every enabled lane -> Notion sync -> heartbeat

The CLI and the launchd schedule call these. The core stays free of I/O.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from job_trawler.config import Lane, LocalConfig
from job_trawler.heartbeat import RunAllResult
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


def run_all(lanes: list[Lane], cfg: LocalConfig, conn: sqlite3.Connection,
            build_sources: Callable[[list[str]], list[Source]],
            push: Callable[[], tuple[int, list[str]]] | None,
            beat: Callable[[RunAllResult], None] | None,
            clock: Callable[[], datetime] = utc_now,
            log: Callable[[str], None] = print) -> RunAllResult:
    """The scheduled job: every enabled lane -> one Notion sync -> one heartbeat.

    `push` and `beat` are passed in (None = Notion not configured), so this
    function is testable without Notion. One lane failing never stops the others,
    and the heartbeat is written even when something blew up (that's when you
    most need to know)."""
    result = RunAllResult(started=clock())
    try:
        for lane in lanes:
            if not lane.enabled:
                continue
            result.lanes.append(lane.name)
            try:
                out = trawl_lane(lane, cfg, build_sources(lane.sources), conn, clock)
            except Exception as e:
                result.errors.append(f"{lane.name}: {type(e).__name__}: {e}")
                log(f"lane {lane.name}: FAILED {type(e).__name__}: {e}")
                continue
            result.fetched += out.run.fetched
            result.new += len(out.new)
            result.errors += [f"{lane.name}: {err}" for err in out.run.errors]
            log(f"lane {lane.name}: fetched {out.run.fetched}, new {len(out.new)}, "
                f"errors {len(out.run.errors)}")
        if push:
            pushed, push_errors = push()
            result.pushed = pushed
            result.errors += [f"notion: {e}" for e in push_errors]
            log(f"notion: pushed {pushed}, errors {len(push_errors)}")
    except Exception as e:
        result.failed = True
        result.errors.append(f"run-all: {type(e).__name__}: {e}")
        log(f"run-all FAILED: {type(e).__name__}: {e}")
    finally:
        result.finished = clock()
        if beat:
            try:
                beat(result)
                log(f"heartbeat: {result.result}")
            except Exception as e:  # can't report to Notion; the log file is the last resort
                log(f"heartbeat FAILED: {type(e).__name__}: {e}")
    return result
