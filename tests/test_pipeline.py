from datetime import date

import pytest

from job_trawler.config import Lane, LocalConfig
from job_trawler.models import Posting, SearchRequest
from job_trawler.pipeline import is_fresh, run_lane
from job_trawler.sources import build_sources

CFG = LocalConfig(home="LA 90026")
LANE = Lane(name="t", intent="x", queries=["bartender", "barback"], sources=["fake"])  # 48h default
TODAY = date(2026, 11, 12)


class FakeSource:
    """Satisfies the Source protocol without inheriting from anything."""

    name = "fake"

    def __init__(self, by_query: dict[str, list[Posting]], fail_on: str | None = None):
        self.by_query, self.fail_on, self.requests = by_query, fail_on, []

    def fetch(self, request: SearchRequest) -> list[Posting]:
        self.requests.append(request)
        if request.query == self.fail_on:
            raise TimeoutError("board is down")
        return self.by_query.get(request.query, [])


def post(url, day):
    return Posting(source="fake", url=url, title=url, posted_on=date(2026, 11, day))


def test_dedups_across_queries_and_sorts_newest_first():
    src = FakeSource({"bartender": [post("a", 10), post("b", 12)], "barback": [post("a", 10), post("c", 11)]})
    run = run_lane(LANE, CFG, [src], today=TODAY)
    assert [p.url for p in run.postings] == ["b", "c", "a"]
    assert run.fetched == 4


def test_one_failing_query_does_not_sink_the_run():
    src = FakeSource({"barback": [post("c", 11)]}, fail_on="bartender")
    run = run_lane(LANE, CFG, [src], today=TODAY)
    assert [p.url for p in run.postings] == ["c"]
    assert len(run.errors) == 1 and "TimeoutError" in run.errors[0]


def test_requests_carry_lane_and_home_settings():
    src = FakeSource({})
    run_lane(LANE, CFG, [src], today=TODAY)
    assert {r.location for r in src.requests} == {"LA 90026"}
    assert {r.radius_mi for r in src.requests} == {25}


def test_unknown_source_name_is_rejected():
    with pytest.raises(ValueError, match="unknown source"):
        build_sources(["craigslist"])


def test_freshness_works_in_whole_days_and_keeps_undated():
    assert is_fresh(post("a", 10), 48, TODAY)          # 2 days back is inside 48h
    assert not is_fresh(post("a", 9), 48, TODAY)
    assert is_fresh(Posting(source="f", url="u", title="t"), 48, TODAY)


def test_stale_postings_are_counted_and_dropped():
    src = FakeSource({"bartender": [post("old", 1), post("new", 12)]})
    run = run_lane(LANE, CFG, [src], today=TODAY)
    assert [p.url for p in run.postings] == ["new"] and run.stale == 1


def titled(title):
    return Posting(source="f", url=title, title=title, posted_on=TODAY)


def test_exclude_is_whole_word_and_case_insensitive():
    from job_trawler.pipeline import is_excluded
    words = ["manager", "line cook"]
    assert is_excluded(titled("F&B Manager"), words)
    assert is_excluded(titled("Assistant MANAGER - Restaurant"), words)
    assert is_excluded(titled("Line Cook (AM)"), words)
    assert not is_excluded(titled("Bartender"), words)
    assert not is_excluded(titled("Cook-Off Host"), ["line cook"])
    assert not is_excluded(titled("Barback"), ["bar"])


def test_excluded_postings_are_counted_and_dropped():
    lane = LANE.model_copy(update={"exclude_title_words": ["manager"]})
    src = FakeSource({"bartender": [titled("Bartender"), titled("General Manager")]})
    run = run_lane(lane, CFG, [src], today=TODAY)
    assert [p.title for p in run.postings] == ["Bartender"] and run.excluded == 1
