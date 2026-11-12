"""DTOs: the shapes data takes as it moves through the pipeline.

Every source, whatever its own format, must hand back `Posting` objects.
That is the "canonical data model": the core only ever sees this one shape,
so adding a source never changes the core.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class SearchRequest(BaseModel):
    """What the pipeline asks a source for. One query, one place, one time window."""

    model_config = ConfigDict(frozen=True)

    query: str
    location: str
    radius_mi: int
    max_age_hours: int
    limit: int


class Posting(BaseModel):
    """One job posting, normalized. Frozen: stages build new objects, never edit old ones."""

    model_config = ConfigDict(frozen=True)

    source: str              # which adapter found it, e.g. "jobspy:indeed"
    url: str                 # the dedup key for now
    title: str
    company: str | None = None
    location: str | None = None
    posted_on: date | None = None   # many boards only give a date, not a time
    pay: str | None = None          # human-readable, e.g. "$18-22/hr"
    remote: bool | None = None
    description: str = ""
