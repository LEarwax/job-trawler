# job-trawler

Trawls fresh job postings across configurable **lanes** (kinds of search) and, from slice 3 on,
puts them on a Notion board. The design is in `docs/SPEC.md`. Progress is tracked slice by slice in `docs/slices.md`.

## Layout
- `lanes/*.yaml`: one file per kind of search (queries, sources, radius, freshness)
- `config.local.yaml`: personal settings like home location (gitignored; copy `config.example.yaml`)
- `src/job_trawler/`
  - `models.py`: DTOs (`SearchRequest`, `Posting`)
  - `config.py`: loads and validates lanes and local config
  - `sources/`: one adapter per source behind the `Source` protocol, plus the registry
  - `pipeline.py`: the core (no I/O of its own): fetch, in-run dedup, freshness
  - `fingerprint.py`: the "same job" rule (pure)
  - `storage.py`: SQLite adapter, the trawler's memory and source of truth
  - `notion_sync.py`, `notion_guard.py`: one-way push to the Notion Job Board, behind a write guard
  - `service.py`: wires core + adapters for one lane run
  - `cli.py`: dev commands
- `data/trawler.db`: created on first run (gitignored)
- `tests/`: no network, no keys

## Setup (once, on the Mac)
    uv sync
    cp config.example.yaml config.local.yaml   # then edit home

## Run
    uv run trawl lanes
    uv run trawl run --lane bridge-hospitality            # saves; shows only new postings
    uv run trawl run --lane bridge-hospitality --dry-run  # fetch and print, save nothing
    uv run trawl runs                                     # recent run history
    uv run trawl sync [--limit 3]                         # push anything not yet on the Notion board

`run` also syncs at the end unless you pass `--no-sync`. Notion needs `notion_jobs_db` in
`config.local.yaml` and `NOTION_TOKEN=...` in `.env` (gitignored); without them, sync is skipped.
    uv run pytest

Look inside the database any time:

    sqlite3 data/trawler.db "SELECT title, company, first_seen_at, times_seen FROM postings ORDER BY first_seen_at DESC LIMIT 20"
