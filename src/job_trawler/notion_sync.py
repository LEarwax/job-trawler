"""Notion adapter: pushes postings from SQLite to the Job Board. One-way.

Unpushed = `notion_page_id IS NULL`. Each row is committed to SQLite the moment
Notion confirms it, NOT in one big transaction like save_postings. Why the
difference? A Notion page can't be rolled back. If we wrapped 45 pushes in one
transaction and crashed on #21, SQLite would forget the 20 that DID reach Notion,
and the next sync would create them twice. So here, progress is saved per row,
and a crash just means the next sync continues where this one stopped.
"""

import sqlite3
import time
from dataclasses import dataclass, field
from typing import Callable

from job_trawler.notion_guard import check_create

NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"
TEXT_LIMIT = 2000           # Notion's per-text-object limit
PAUSE_SECONDS = 0.35        # stay under Notion's ~3 requests/second average
MAX_ATTEMPTS = 3            # per page, for 429 / 5xx
STOP_AFTER_FAILURES = 3     # consecutive failures -> stop, something is wrong


class NotionError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class AuthError(NotionError):
    """401/403/404: token wrong, or integration not connected to the database.
    Every row would fail the same way, so the sync stops immediately."""


# ---------- pure: SQLite row -> Notion payload ----------

def _text(value: str) -> list[dict]:
    return [{"text": {"content": value[:TEXT_LIMIT]}}]


def build_payload(row: sqlite3.Row | dict, db_id: str) -> dict:
    """Only trawler-owned columns. Missing values are left out rather than sent empty."""
    props: dict = {
        "Title": {"title": _text(row["title"])},
        "Link": {"url": row["url"]},
        "Lane": {"select": {"name": row["lane"]}},
        "Source": {"select": {"name": row["source"]}},
        "First seen": {"date": {"start": row["first_seen_at"]}},
    }
    if row["company"]:
        props["Company"] = {"rich_text": _text(row["company"])}
    if row["location"]:
        props["Location"] = {"rich_text": _text(row["location"])}
    if row["pay"]:
        props["Pay"] = {"rich_text": _text(row["pay"])}
    if row["posted_on"]:
        props["Posted"] = {"date": {"start": row["posted_on"]}}
    return {"parent": {"database_id": db_id}, "properties": props}


# ---------- I/O: talking to Notion ----------

def _http_post(url: str, headers: dict, json: dict):
    import httpx  # lazy: tests never import it
    return httpx.post(url, headers=headers, json=json, timeout=30)


class NotionClient:
    def __init__(self, token: str, db_id: str, post: Callable = _http_post,
                 sleep: Callable[[float], None] = time.sleep):
        self.db_id = db_id
        self._headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION,
                         "Content-Type": "application/json"}
        self._post, self._sleep = post, sleep

    def create_page(self, payload: dict) -> str:
        check_create(payload, self.db_id)            # refuse before any network call
        for attempt in range(1, MAX_ATTEMPTS + 1):
            r = self._post(f"{API}/pages", self._headers, payload)
            if r.status_code == 200:
                return r.json()["id"]
            message = _error_message(r)
            if r.status_code in (401, 403, 404):
                raise AuthError(r.status_code, message)
            retryable = r.status_code == 429 or r.status_code >= 500
            if not retryable or attempt == MAX_ATTEMPTS:
                raise NotionError(r.status_code, message)
            wait = float(r.headers.get("Retry-After", 2 ** attempt))
            self._sleep(wait)
        raise AssertionError("unreachable")


def _error_message(r) -> str:
    try:
        return r.json().get("message", "")[:300]
    except Exception:
        return ""


# ---------- the sync loop ----------

@dataclass
class SyncResult:
    pushed: int = 0
    failed: int = 0
    stopped_early: bool = False
    errors: list[str] = field(default_factory=list)


def unpushed(conn: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM postings WHERE notion_page_id IS NULL ORDER BY first_seen_at, id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql).fetchall()


def sync(conn: sqlite3.Connection, client: NotionClient, limit: int | None = None,
         sleep: Callable[[float], None] = time.sleep) -> SyncResult:
    result = SyncResult()
    consecutive = 0
    for i, row in enumerate(unpushed(conn, limit)):
        if i:
            sleep(PAUSE_SECONDS)
        try:
            page_id = client.create_page(build_payload(row, client.db_id))
        except AuthError as e:
            result.failed += 1
            result.errors.append(f"{e} (check NOTION_TOKEN and that the integration is "
                                 f"connected to the Job Board)")
            result.stopped_early = True
            break
        except Exception as e:
            result.failed += 1
            consecutive += 1
            result.errors.append(f"{row['title']!r}: {type(e).__name__}: {e}")
            if consecutive >= STOP_AFTER_FAILURES:
                result.stopped_early = True
                break
            continue
        with conn:  # commit THIS row now: Notion has it, so SQLite must remember that
            conn.execute("UPDATE postings SET notion_page_id = ? WHERE id = ?", (page_id, row["id"]))
        result.pushed += 1
        consecutive = 0
    return result
