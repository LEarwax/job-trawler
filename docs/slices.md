# Slices

| # | Slice | Status |
|---|---|---|
| 1 | One lane, one source, print to terminal | Built 2026-11-12. Live run on Mac pending. |
| 2 | SQLite memory + fingerprint dedup + freshness | Built 2026-11-12. Live run on Mac pending. |
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

## Slice 2 notes
- Done when: two `trawl run --lane bridge-hospitality` in a row; the second says 0 new.
- Decisions (2026-11-12, discussed with Nick):
  - **SQLite is the source of truth; Notion is a read-only view.** Each field has exactly one owner:
    the trawler owns posting facts (title, pay, score, link); Nick owns status and pass reason in
    Notion, which the trawler will only read (slice 7). No field has two writers, so no conflicts.
  - **Duplicates are decided by a deterministic fingerprint**, not a human or LLM judge:
    normalized (company, title, city), or the URL when the company is missing. A miss costs a
    duplicate row; a false match would hide a job, so normalization stays conservative.
  - **Re-posts are the same job.** The date is not in the fingerprint; a re-post bumps
    `last_seen_at` and `times_seen` (a future "keeps re-posting" signal).
  - **Crash safety by transaction, not batch bookkeeping.** `save_postings` is one transaction;
    a failure saves nothing and a re-run is safe. The `runs` table exists for the heartbeat
    (slice 4), not for flow control. Slice 3 adds per-row `notion_page_id` (empty = not yet pushed).
- `first_seen_at` gives hour precision even though boards only report a date.
- Known limits: first lane to see a job owns it (cross-lane sharing comes when there are two lanes);
  "Bartender" vs "Lead Bartender" at the same bar are different jobs by design.
