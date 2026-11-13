"""Write guard: the ONLY door through which this program creates Notion pages.

Same idea as gtd-agent's notion_guard.py. A Notion integration token can write to
every database it's connected to, so "the trawler only writes to the Job Board"
has to be enforced in our code, before any network call:

  * Deny by default: the parent must be exactly {"database_id": <the Job Board>}.
  * The target is chosen by our code (from config), never by data or a model.
  * Updates to existing pages are not offered at all: the trawler creates rows,
    and the columns you own (Status, Pass reason, Notes) are never written.
"""


class WriteRefused(Exception):
    """Raised BEFORE any network call when a write is not allowed."""


def _norm(i: str) -> str:
    return i.replace("-", "").lower()


def check_create(payload: dict, allowed_db: str) -> None:
    parent = payload.get("parent")
    if not isinstance(parent, dict) or set(parent) != {"database_id"}:
        raise WriteRefused(f"parent must be exactly {{'database_id': ...}}, got {parent!r}")
    if _norm(str(parent["database_id"])) != _norm(allowed_db):
        raise WriteRefused(f"database {parent['database_id']} is not the Job Board")
    owned_by_you = {"Status", "Pass reason", "Notes"} & set(payload.get("properties", {}))
    if owned_by_you:
        raise WriteRefused(f"trawler may not write your columns: {sorted(owned_by_you)}")
