"""Heartbeat: after every run-all, create one row in the Notion "Runs" database.

The alarm is NOT in this code. A dead trawler can't report that it's dead.
The Runs database has a formula ("Health") that Notion itself recomputes, so
when the newest row is over 26 hours old the warning appears even if this
program never runs again. The trawler only leaves the trail; Notion watches it.
"""

from dataclasses import dataclass, field
from datetime import datetime

TEXT_LIMIT = 2000


@dataclass
class RunAllResult:
    started: datetime
    finished: datetime | None = None
    lanes: list[str] = field(default_factory=list)
    fetched: int = 0
    new: int = 0
    pushed: int = 0
    errors: list[str] = field(default_factory=list)
    failed: bool = False        # an unexpected exception stopped the run

    @property
    def result(self) -> str:
        if self.failed:
            return "Failed"
        return "Errors" if self.errors else "OK"


def build_heartbeat(r: RunAllResult, db_id: str) -> dict:
    finished = r.finished or r.started
    local = finished.astimezone()   # title in your time zone, e.g. "Thu Nov 13, 06:30"
    title = f"{local:%a %b %d, %H:%M} · {r.new} new"
    details = "; ".join(r.errors) or f"lanes: {', '.join(r.lanes) or 'none'}"
    return {
        "parent": {"database_id": db_id},
        "properties": {
            "Run": {"title": [{"text": {"content": title}}]},
            "Finished": {"date": {"start": finished.isoformat(timespec="seconds")}},
            "Result": {"select": {"name": r.result}},
            "New": {"number": r.new},
            "Fetched": {"number": r.fetched},
            "Pushed": {"number": r.pushed},
            "Errors": {"number": len(r.errors)},
            "Details": {"rich_text": [{"text": {"content": details[:TEXT_LIMIT]}}]},
        },
    }
