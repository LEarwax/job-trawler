"""SQLite adapter: the trawler's memory and source of truth.

Plain SQL with the standard library's sqlite3, so every query is readable.

Ownership rule (see docs/SPEC.md): the trawler owns everything in these tables.
Notion (slice 3) only ever receives copies; nothing flows back into these columns.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from job_trawler.fingerprint import fingerprint
from job_trawler.models import Posting

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    id            INTEGER PRIMARY KEY,
    fingerprint   TEXT    NOT NULL UNIQUE,   -- "same job" key, see fingerprint.py
    lane          TEXT    NOT NULL,          -- lane that found it first
    source        TEXT    NOT NULL,
    url           TEXT    NOT NULL,
    title         TEXT    NOT NULL,
    company       TEXT,
    location      TEXT,
    posted_on     TEXT,                      -- YYYY-MM-DD, as the board reports it
    pay           TEXT,
    remote        INTEGER,                   -- 0/1/NULL
    description   TEXT    NOT NULL DEFAULT '',
    first_seen_at TEXT    NOT NULL,          -- UTC ISO time we first saw it (hour precision)
    last_seen_at  TEXT    NOT NULL,          -- bumps on every re-sighting / re-post
    times_seen    INTEGER NOT NULL DEFAULT 1,
    notion_page_id TEXT                      -- NULL = not yet on the board (slice 3)
);

CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY,
    lane          TEXT    NOT NULL,
    started_at    TEXT    NOT NULL,
    finished_at   TEXT,                      -- NULL = crashed or still running
    fetched       INTEGER,                   -- raw rows from all sources
    kept          INTEGER,                   -- after in-run dedup and freshness filter
    new           INTEGER,                   -- never seen before
    errors        TEXT                       -- JSON list of source errors
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring databases created by older slices up to date. Each step is safe to re-run.
    (CREATE TABLE IF NOT EXISTS never adds columns to a table that already exists.)"""
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(postings)")}
    with conn:
        if "notion_page_id" not in columns:                                    # slice 3
            conn.execute("ALTER TABLE postings ADD COLUMN notion_page_id TEXT")


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def start_run(conn: sqlite3.Connection, lane: str, now: datetime) -> int:
    with conn:
        cur = conn.execute("INSERT INTO runs (lane, started_at) VALUES (?, ?)", (lane, _iso(now)))
    return cur.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, *, fetched: int, kept: int, new: int,
               errors: list[str], now: datetime) -> None:
    with conn:
        conn.execute(
            "UPDATE runs SET finished_at = ?, fetched = ?, kept = ?, new = ?, errors = ? WHERE id = ?",
            (_iso(now), fetched, kept, new, json.dumps(errors), run_id),
        )


def save_postings(conn: sqlite3.Connection, lane: str, postings: list[Posting],
                  now: datetime) -> list[Posting]:
    """Insert unseen postings, bump last_seen on known ones. Returns only the new ones.

    One transaction (`with conn:`): if anything fails halfway, NOTHING is saved,
    so re-running is always safe. That's what makes a crash mid-save harmless.
    """
    new: list[Posting] = []
    ts = _iso(now)
    with conn:
        for p in postings:
            cur = conn.execute(
                """INSERT OR IGNORE INTO postings
                   (fingerprint, lane, source, url, title, company, location, posted_on,
                    pay, remote, description, first_seen_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fingerprint(p), lane, p.source, p.url, p.title, p.company, p.location,
                 p.posted_on.isoformat() if p.posted_on else None, p.pay,
                 None if p.remote is None else int(p.remote), p.description, ts, ts),
            )
            if cur.rowcount == 1:
                new.append(p)
            else:
                conn.execute(
                    "UPDATE postings SET last_seen_at = ?, times_seen = times_seen + 1 "
                    "WHERE fingerprint = ?",
                    (ts, fingerprint(p)),
                )
    return new


def recent_runs(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
