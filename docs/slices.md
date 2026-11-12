# Slices

| # | Slice | Status |
|---|---|---|
| 1 | One lane, one source, print to terminal | Built 2026-11-12. Live run on Mac pending. |
| 2 | Persistence + cross-run dedup + freshness (decide: SQLite or Notion-only) | |
| 3 | Notion sync (unscored) | |
| 4 | launchd schedule + heartbeat | |
| 5 | LLM scoring + small eval | |
| 6 | Second lane with zero code changes | |

## Slice 1 notes
- Done when: `uv run trawl run --lane bridge-hospitality` on the Mac prints fresh bartender postings near home.
- JobSpy 1.4.1 facts: returns a pandas DataFrame (missing values may be NaN); `location` is a dict;
  `date_posted` is a date (no time), so freshness finer than a day depends on the board's own
  `hours_old` filter, which Indeed and LinkedIn honor by the hour.
- Indeed is not reachable from the Cowork VM (proxy 403), so live runs happen on the Mac.
- Only Indeed is enabled; more JobSpy sites become a lane option later.
