import sqlite3
from datetime import datetime, timezone

import pytest

from job_trawler import storage
from job_trawler.models import Posting
from job_trawler.notion_guard import WriteRefused, check_create
from job_trawler.notion_sync import NotionClient, build_payload, sync

DB = "d89560eeedc1484d90c52ef93448ba65"
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
NO_SLEEP = lambda s: None  # noqa: E731


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}

    def json(self):
        return self._body


class FakeNotion:
    """Plays Notion: returns scripted responses in order, then 200s."""

    def __init__(self, script=()):
        self.script, self.calls = list(script), []

    def __call__(self, url, headers, json):
        self.calls.append(json)
        if self.script:
            r = self.script.pop(0)
            if isinstance(r, BaseException):
                raise r
            return r
        return Resp(200, {"id": f"page-{len(self.calls)}"})


@pytest.fixture
def conn(tmp_path):
    c = storage.connect(tmp_path / "t.db")
    posts = [Posting(source="jobspy:indeed", url=f"https://x/{n}", title=f"Bartender {n}",
                     company=f"Bar {n}") for n in range(3)]
    storage.save_postings(c, "bridge-hospitality", posts, NOW)
    return c


def client(fake):
    return NotionClient("secret", DB, post=fake, sleep=NO_SLEEP)


def page_ids(conn):
    return [r[0] for r in conn.execute("SELECT notion_page_id FROM postings ORDER BY id")]


# ---------- payload + guard ----------

def test_payload_leaves_out_missing_values_and_your_columns(conn):
    row = conn.execute("SELECT * FROM postings LIMIT 1").fetchone()
    props = build_payload(row, DB)["properties"]
    assert props["Title"]["title"][0]["text"]["content"] == "Bartender 0"
    assert "Pay" not in props and "Posted" not in props          # were NULL
    assert not {"Status", "Pass reason", "Notes"} & set(props)


def test_long_text_is_truncated_to_notion_limit():
    row = {"title": "x" * 5000, "url": "u", "lane": "l", "source": "s", "first_seen_at": "t",
           "company": None, "location": None, "pay": None, "posted_on": None}
    assert len(build_payload(row, DB)["properties"]["Title"]["title"][0]["text"]["content"]) == 2000


def test_guard_refuses_other_databases_page_parents_and_your_columns():
    with pytest.raises(WriteRefused):
        check_create({"parent": {"database_id": "someone-else"}, "properties": {}}, DB)
    with pytest.raises(WriteRefused):
        check_create({"parent": {"page_id": DB}, "properties": {}}, DB)
    with pytest.raises(WriteRefused, match="your columns"):
        check_create({"parent": {"database_id": DB}, "properties": {"Status": {}}}, DB)


def test_guard_runs_before_any_network_call():
    fake = FakeNotion()
    with pytest.raises(WriteRefused):
        client(fake).create_page({"parent": {"database_id": "nope"}, "properties": {}})
    assert fake.calls == []


# ---------- sync behavior ----------

def test_sync_pushes_everything_and_records_page_ids(conn):
    res = sync(conn, client(FakeNotion()), sleep=NO_SLEEP)
    assert res.pushed == 3 and all(page_ids(conn))


def test_second_sync_pushes_nothing(conn):
    sync(conn, client(FakeNotion()), sleep=NO_SLEEP)
    fake = FakeNotion()
    assert sync(conn, client(fake), sleep=NO_SLEEP).pushed == 0 and fake.calls == []


def test_rate_limit_is_retried_after_waiting(conn):
    waits = []
    fake = FakeNotion([Resp(429, headers={"Retry-After": "1.5"})])
    res = sync(conn, NotionClient("secret", DB, post=fake, sleep=waits.append), sleep=NO_SLEEP)
    assert res.pushed == 3 and waits == [1.5]


def test_bad_token_stops_the_sync_at_once(conn):
    fake = FakeNotion([Resp(401, {"message": "API token is invalid."})])
    res = sync(conn, client(fake), sleep=NO_SLEEP)
    assert res.stopped_early and res.pushed == 0 and len(fake.calls) == 1
    assert "NOTION_TOKEN" in res.errors[0]


def test_one_bad_row_is_skipped_and_retried_next_time(conn):
    fake = FakeNotion([Resp(200, {"id": "p1"}), Resp(400, {"message": "bad url"})])
    res = sync(conn, client(fake), sleep=NO_SLEEP)
    assert (res.pushed, res.failed) == (2, 1)
    assert page_ids(conn)[1] is None
    assert sync(conn, client(FakeNotion()), sleep=NO_SLEEP).pushed == 1   # picks up the leftover


def test_crash_mid_sync_keeps_what_notion_already_has(conn):
    """The opposite of save_postings: per-row commits. Row 0 reached Notion before the
    crash, so SQLite must still remember it, or the next sync would duplicate it."""
    fake = FakeNotion([Resp(200, {"id": "p1"}), KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        sync(conn, client(fake), sleep=NO_SLEEP)
    assert page_ids(conn) == ["p1", None, None]
    fake2 = FakeNotion()
    sync(conn, client(fake2), sleep=NO_SLEEP)
    assert len(fake2.calls) == 2                                          # no duplicate of row 0


# ---------- migration ----------

def test_slice2_database_gets_the_new_column(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE postings (id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE)")
    old.commit()
    old.close()
    cols = {r["name"] for r in storage.connect(path).execute("PRAGMA table_info(postings)")}
    assert "notion_page_id" in cols
