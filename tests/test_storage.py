from datetime import datetime, timezone

import pytest

from job_trawler import storage
from job_trawler.models import Posting

T1 = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)


def post(url, company="Bar"):
    return Posting(source="t", url=url, title="Bartender " + url, company=company)


@pytest.fixture
def conn(tmp_path):
    return storage.connect(tmp_path / "t.db")


def test_first_save_returns_everything_as_new(conn):
    new = storage.save_postings(conn, "lane", [post("a"), post("b")], T1)
    assert [p.url for p in new] == ["a", "b"]


def test_second_save_returns_nothing_and_bumps_last_seen(conn):
    storage.save_postings(conn, "lane", [post("a")], T1)
    new = storage.save_postings(conn, "lane", [post("a")], T2)
    assert new == []
    row = conn.execute("SELECT first_seen_at, last_seen_at, times_seen FROM postings").fetchone()
    assert row["first_seen_at"].startswith("2026-11-12T09")
    assert row["last_seen_at"].startswith("2026-11-12T11")
    assert row["times_seen"] == 2


def test_crash_halfway_saves_nothing(conn, monkeypatch):
    """The whole save is one transaction: a failure on posting 2 rolls back posting 1 too."""
    from job_trawler import fingerprint as fp_mod

    calls = {"n": 0}
    real = fp_mod.fingerprint

    def flaky(p):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("disk full")
        return real(p)

    monkeypatch.setattr(storage, "fingerprint", flaky)
    with pytest.raises(RuntimeError):
        storage.save_postings(conn, "lane", [post("a"), post("b")], T1)
    assert conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 0

    monkeypatch.setattr(storage, "fingerprint", real)          # "re-run" after the crash
    assert len(storage.save_postings(conn, "lane", [post("a"), post("b")], T1)) == 2


def test_run_rows_record_start_and_finish(conn):
    run_id = storage.start_run(conn, "lane", T1)
    assert storage.recent_runs(conn)[0]["finished_at"] is None   # "never finished" is visible
    storage.finish_run(conn, run_id, fetched=10, kept=7, new=3, errors=["x"], now=T2)
    row = storage.recent_runs(conn)[0]
    assert (row["fetched"], row["kept"], row["new"]) == (10, 7, 3)
    assert row["errors"] == '["x"]'
