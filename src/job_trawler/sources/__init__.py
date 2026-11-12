"""Registry: lane files name sources by string; this maps the string to an adapter.

Same idea as HANDLERS in gtd-agent's runner. Adding a source = one new file + one line here.
"""

from job_trawler.sources.base import Source
from job_trawler.sources.jobspy_source import JobSpySource

SOURCES: dict[str, type] = {
    "jobspy": JobSpySource,
}


def build_sources(names: list[str]) -> list[Source]:
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        raise ValueError(f"unknown source(s) {unknown}; known: {sorted(SOURCES)}")
    return [SOURCES[n]() for n in names]
