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
  - `pipeline.py`: the core (no I/O of its own)
  - `cli.py`: dev commands
- `tests/`: no network, no keys

## Setup (once, on the Mac)
    uv sync
    cp config.example.yaml config.local.yaml   # then edit home

## Run
    uv run trawl lanes
    uv run trawl run --lane bridge-hospitality
    uv run pytest
