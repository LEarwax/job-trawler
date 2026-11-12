"""End-to-end for slice 2, with a fake source and a temp database. This is the slice's
'done' check: the second run in a row finds nothing new."""

from datetime import date, datetime, timezone

from job_trawler import storage
from job_trawler.config import Lane, LocalConfig
from job_trawler.models import Posting, SearchRequest
from job_trawler.service import trawl_lane

CFG = LocalConfig(home="LA 90026")
LANE = Lane(name="t", intent="x", queries=["bartender"], sources=["fake"])
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)


class FakeSource:
    name = "fake"

    def __init__(self, postings):
        self.postings = postings

    def fetch(self, request: SearchRequest) -> list[Posting]:
        return list(self.postings)


def bar(company, day=12):
    return Posting(source="fake", url=f"https://x/{company}", title="Bartender", company=company,
                   location="Los Angeles, CA", posted_on=date(2026, 11, day))


def test_second_run_finds_nothing_new(tmp_path):
    conn = storage.connect(tmp_path / "t.db")
    src = FakeSource([bar("Crow"), bar("Owl")])
    first = trawl_lane(LANE, CFG, [src], conn, clock=lambda: NOW)
    second = trawl_lane(LANE, CFG, [src], conn, clock=lambda: NOW)
    assert len(first.new) == 2
    assert second.new == []
    assert [r["new"] for r in storage.recent_runs(conn)] == [0, 2]


def test_only_the_genuinely_new_posting_comes_through(tmp_path):
    conn = storage.connect(tmp_path / "t.db")
    trawl_lane(LANE, CFG, [FakeSource([bar("Crow")])], conn, clock=lambda: NOW)
    out = trawl_lane(LANE, CFG, [FakeSource([bar("Crow"), bar("Owl")])], conn, clock=lambda: NOW)
    assert [p.company for p in out.new] == ["Owl"]


def test_stale_postings_are_never_saved(tmp_path):
    conn = storage.connect(tmp_path / "t.db")
    out = trawl_lane(LANE, CFG, [FakeSource([bar("Crow", day=1)])], conn, clock=lambda: NOW)
    assert out.new == [] and out.run.stale == 1
    assert conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 0
