# Slices

| # | Slice | Status |
|---|---|---|
| 1 | One lane, one source, print to terminal | Done 2026-11-12 (live: 20 fetched, 19 kept) |
| 2 | SQLite memory + fingerprint dedup + freshness | Done 2026-11-12 (live: run 2 = 0 new) |
| 2.5 | `exclude_title_words` per lane; bridge radius 15 mi | Built 2026-11-12 |
| 3 | Notion sync (unscored) to Job Trawler > Job Board | Built 2026-11-12. First live sync pending (needs token). |
| 4 | launchd schedule + heartbeat | |
| 5 | LLM scoring + small eval | |
| 6 | Second lane with zero code changes | |
| later | `trawl lane new "<what you want>"`: drafts a lane YAML from a phrase, you review | Nick's idea, 2026-11-12 |

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
- Live result: run 1 fetched 20 -> 19 new (18 with pay); run 2 -> 0 new. Noise seen: manager roles
  (fixed by exclude_title_words in 2.5) and long commutes (radius 25 -> 15).
- Known limits: first lane to see a job owns it (cross-lane sharing comes when there are two lanes);
  "Bartender" vs "Lead Bartender" at the same bar are different jobs by design.

## Slice 3 notes
- Done when: `uv run trawl sync` puts the saved postings on the Job Board, and a second
  `trawl sync` says the board is up to date.
- Notion: private page "Job Trawler" (416f4edf534381f7a781ef58f926288a) containing the
  "Job Board" database (d89560eeedc1484d90c52ef93448ba65, data source b193010f-4eb7-47dd-a81f-b3ecfa68998c).
  Created 2026-11-12 through Claude's Notion connection; the program writes with its own
  integration token (`job-trawler`, NOTION_TOKEN in .env).
- Status is a plain select, not Notion's Status type: the Status type always has a value,
  and "empty = new" keeps Status single-owner (yours).
- Per-row commits in `notion_sync.sync`, unlike the single transaction in `save_postings`:
  a Notion page can't be rolled back, so SQLite must record each push the moment it succeeds.
- Guard: create-only, Job Board only, and refuses any payload containing Status / Pass reason / Notes.
- Stops at once on 401/403/404 (token or connection problem); stops after 3 consecutive
  other failures; retries 429/5xx up to 3 times honoring Retry-After; 0.35 s between writes.
- api.notion.com is not reachable from the Cowork VM, so live syncs happen on the Mac.
