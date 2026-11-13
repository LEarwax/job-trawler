import plistlib
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from job_trawler import storage
from job_trawler.config import Lane, LocalConfig
from job_trawler.heartbeat import RunAllResult, build_heartbeat
from job_trawler.models import Posting
from job_trawler.notion_guard import check_create
from job_trawler.schedule import make_plist
from job_trawler.service import run_all

CFG = LocalConfig(home="LA 90026")
NOW = datetime(2026, 11, 13, 14, 30, tzinfo=timezone.utc)
RUNS_DB = "f916a8cb923d4218881d714dd672f02d"


def lane(name, enabled=True):
    return Lane(name=name, intent="x", queries=["q"], sources=["fake"], enabled=enabled)


class FakeSource:
    name = "fake"

    def __init__(self, company):
        self.company = company

    def fetch(self, request):
        return [Posting(source="fake", url=f"https://x/{self.company}", title="Bartender",
                        company=self.company, location="LA", posted_on=date(2026, 11, 13))]


@pytest.fixture
def conn(tmp_path):
    return storage.connect(tmp_path / "t.db")


def go(conn, lanes, push=None, beat=None, sources=None):
    sources = sources or (lambda names: [FakeSource("Crow")])
    return run_all(lanes, CFG, conn, sources, push=push, beat=beat, clock=lambda: NOW, log=lambda m: None)


# ---------- run_all ----------

def test_runs_enabled_lanes_then_pushes_then_beats(conn):
    order, beats = [], []
    r = go(conn, [lane("a"), lane("off", enabled=False)],
           push=lambda: (order.append("push"), (1, []))[1], beat=beats.append)
    assert r.lanes == ["a"] and r.new == 1 and r.pushed == 1 and r.result == "OK"
    assert order == ["push"] and beats == [r]


def test_one_lane_crashing_doesnt_stop_the_next(conn):
    def sources(names):
        if sources.calls == 0:
            sources.calls += 1
            raise RuntimeError("bad lane config")
        return [FakeSource("Owl")]
    sources.calls = 0
    r = go(conn, [lane("a"), lane("b")], sources=sources)
    assert r.new == 1 and r.result == "Errors" and "a: RuntimeError" in r.errors[0]


def test_heartbeat_is_written_even_when_the_run_blows_up(conn):
    beats = []

    def push():
        raise ConnectionError("notion down")
    r = go(conn, [lane("a")], push=push, beat=beats.append)
    assert r.failed and r.result == "Failed" and beats == [r]


def test_a_failing_heartbeat_does_not_crash_the_run(conn):
    def beat(_):
        raise ConnectionError("notion down")
    r = go(conn, [lane("a")], beat=beat)
    assert r.result == "OK"


# ---------- heartbeat payload ----------

def test_heartbeat_payload_passes_the_guard_and_says_what_happened():
    r = RunAllResult(started=NOW, finished=NOW, lanes=["bridge"], fetched=20, new=4, pushed=4,
                     errors=["bridge: jobspy timeout"])
    payload = build_heartbeat(r, RUNS_DB)
    check_create(payload, RUNS_DB)                        # allowlisted, none of your columns
    props = payload["properties"]
    assert props["Result"]["select"]["name"] == "Errors"
    assert props["New"]["number"] == 4 and props["Errors"]["number"] == 1
    assert "4 new" in props["Run"]["title"][0]["text"]["content"]
    assert props["Finished"]["date"]["start"].startswith("2026-11-13T14:30")


# ---------- launchd file ----------

def test_plist_runs_run_all_daily_at_the_given_time():
    data = plistlib.loads(make_plist("/opt/homebrew/bin/uv", Path("/Users/n/job-trawler"), 6, 30))
    assert data["ProgramArguments"] == ["/opt/homebrew/bin/uv", "run", "--project",
                                        "/Users/n/job-trawler", "trawl", "run-all"]
    assert data["StartCalendarInterval"] == {"Hour": 6, "Minute": 30}
    assert data["StandardOutPath"].endswith("data/logs/trawl.log")


def test_plist_rejects_impossible_times():
    with pytest.raises(ValueError):
        make_plist("uv", Path("/x"), 25, 0)
