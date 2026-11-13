"""Command line. Development tool only; day-to-day use will be the Notion board."""

import json

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Job trawler", no_args_is_help=True)
console = Console(soft_wrap=True)  # never hard-wrap: printed commands must stay copy-pasteable


def _load(lane_name: str):
    from job_trawler.config import load_lanes, load_local_config

    cfg = load_local_config()
    all_lanes = load_lanes()
    if lane_name not in all_lanes:
        console.print(f"[red]No lane {lane_name!r}. Known: {', '.join(all_lanes)}[/red]")
        raise typer.Exit(1)
    return cfg, all_lanes[lane_name]


def _print_postings(title: str, postings) -> None:
    table = Table(title=title)
    for col in ("Posted", "Title", "Company", "Location", "Pay", "Source"):
        table.add_column(col)
    for p in postings:
        table.add_row(str(p.posted_on or "?"), p.title, p.company or "", p.location or "",
                      p.pay or "", p.source)
    console.print(table)
    if postings:
        console.print("\nLinks:")
        for i, p in enumerate(postings[:10], 1):
            console.print(f"  {i}. {p.url}")


@app.command()
def lanes() -> None:
    """List configured lanes."""
    from job_trawler.config import load_lanes, load_local_config

    cfg = load_local_config()
    for lane in load_lanes().values():
        state = "on " if lane.enabled else "off"
        console.print(f"\\[{state}] {lane.name}: {len(lane.queries)} queries, "
                      f"{lane.radius(cfg)} mi of {lane.location(cfg)}, <= {lane.max_age_hours}h old")


@app.command()
def run(
    lane: str = typer.Option(..., "--lane", "-l", help="Lane name, e.g. bridge-hospitality"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Fetch and print, save nothing"),
    no_sync: bool = typer.Option(False, "--no-sync", help="Save, but don't push to Notion"),
) -> None:
    """Fetch one lane, remember what was found, and show only postings never seen before."""
    from datetime import date

    from job_trawler.pipeline import run_lane
    from job_trawler.service import trawl_lane
    from job_trawler.sources import build_sources
    from job_trawler import storage

    cfg, chosen = _load(lane)
    sources = build_sources(chosen.sources)

    if dry_run:
        result = run_lane(chosen, cfg, sources, today=date.today())
        _print_postings(f"{chosen.name} (dry run): {len(result.postings)} postings", result.postings)
        errors = result.errors
    else:
        conn = storage.connect(cfg.resolved_db_path())
        out = trawl_lane(chosen, cfg, sources, conn)
        r = out.run
        _print_postings(f"{chosen.name}: {len(out.new)} new", out.new)
        dupes = r.fetched - r.stale - r.excluded - len(r.postings)
        console.print(f"fetched {r.fetched} -> {dupes} in-run duplicates, {r.stale} stale, "
                      f"{r.excluded} excluded -> kept {len(r.postings)} -> "
                      f"[bold]{len(out.new)} new[/bold], {len(r.postings) - len(out.new)} seen before")
        errors = r.errors
    for err in errors:
        console.print(f"[yellow]source error:[/yellow] {err}")
    if not dry_run and not no_sync:
        _sync(cfg, conn)


def _sync(cfg, conn, limit: int | None = None) -> tuple[int, list[str]]:
    """Push unpushed postings. Returns (pushed, errors)."""
    from job_trawler.config import notion_token
    from job_trawler.notion_sync import NotionClient, sync, unpushed

    token = notion_token()
    if not cfg.notion_jobs_db or not token:
        missing = "notion_jobs_db in config.local.yaml" if not cfg.notion_jobs_db else "NOTION_TOKEN in .env"
        console.print(f"[dim]Notion sync skipped: no {missing}.[/dim]")
        return 0, []
    waiting = len(unpushed(conn, limit))
    if not waiting:
        console.print("Notion: board is up to date.")
        return 0, []
    console.print(f"Notion: pushing {waiting} posting(s)...")
    res = sync(conn, NotionClient(token, cfg.notion_jobs_db), limit=limit)
    console.print(f"Notion: [bold]{res.pushed} pushed[/bold], {res.failed} failed"
                  + (" [red](stopped early)[/red]" if res.stopped_early else ""))
    for err in res.errors:
        console.print(f"[yellow]notion error:[/yellow] {err}")
    return res.pushed, res.errors


@app.command(name="run-all")
def run_all_cmd() -> None:
    """The scheduled job: every enabled lane, then Notion sync, then a heartbeat row."""
    from datetime import datetime

    from job_trawler.config import load_lanes, load_local_config, notion_token
    from job_trawler.heartbeat import build_heartbeat
    from job_trawler.notion_sync import NotionClient
    from job_trawler.service import run_all
    from job_trawler.sources import build_sources
    from job_trawler import storage

    console.print(f"=== run-all {datetime.now().astimezone():%Y-%m-%d %H:%M %Z} ===")
    cfg = load_local_config()
    conn = storage.connect(cfg.resolved_db_path())
    token = notion_token()

    beat = None
    if cfg.notion_runs_db and token:
        runs_client = NotionClient(token, cfg.notion_runs_db)   # guard: allowlist = Runs db only
        beat = lambda r: runs_client.create_page(build_heartbeat(r, cfg.notion_runs_db))  # noqa: E731

    result = run_all(list(load_lanes().values()), cfg, conn, build_sources,
                     push=lambda: _sync(cfg, conn), beat=beat, log=console.print)
    console.print(f"=== {result.result}: {result.new} new, {result.pushed} pushed, "
                  f"{len(result.errors)} errors ===")
    for err in result.errors:
        console.print(f"[yellow]error:[/yellow] {err}")
    if result.failed:
        raise typer.Exit(1)


@app.command()
def schedule(
    at: str = typer.Option("06:30", "--at", help="Daily run time, 24h HH:MM, your local time"),
) -> None:
    """Write the launchd file that runs `trawl run-all` every day. Prints the command to turn it on."""
    import shutil

    from job_trawler.config import ROOT
    from job_trawler.schedule import LABEL, make_plist, plist_path

    try:
        hour, minute = (int(x) for x in at.split(":"))
        content = make_plist(shutil.which("uv") or "uv", ROOT, hour, minute)
    except ValueError:
        console.print(f"[red]--at must look like 06:30, got {at!r}[/red]")
        raise typer.Exit(1)
    if not shutil.which("uv"):
        console.print("[red]Can't find uv on PATH; run this from a terminal where `uv` works.[/red]")
        raise typer.Exit(1)

    (ROOT / "data" / "logs").mkdir(parents=True, exist_ok=True)   # launchd won't create it
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    console.print(f"Wrote {path} (daily at {hour:02d}:{minute:02d}).\n")
    console.print("Turn it on (also use this after changing the time):")
    console.print(f"  launchctl bootout gui/$(id -u)/{LABEL} 2>/dev/null; "
                  f"launchctl bootstrap gui/$(id -u) {path}")
    console.print("Run it once right now, as launchd would:")
    console.print(f"  launchctl kickstart gui/$(id -u)/{LABEL}")
    console.print("Turn it off:")
    console.print(f"  launchctl bootout gui/$(id -u)/{LABEL}")


@app.command(name="sync")
def sync_cmd(limit: int = typer.Option(None, help="Push at most this many (handy for a first test)")) -> None:
    """Push any postings not yet on the Notion board."""
    from job_trawler.config import load_local_config
    from job_trawler import storage

    cfg = load_local_config()
    _sync(cfg, storage.connect(cfg.resolved_db_path()), limit)


@app.command()
def runs(limit: int = typer.Option(10, help="How many recent runs to show")) -> None:
    """Show recent runs: when, how much was found, and any errors."""
    from job_trawler.config import load_local_config
    from job_trawler import storage

    conn = storage.connect(load_local_config().resolved_db_path())
    table = Table(title="Recent runs")
    for col in ("#", "Lane", "Started (UTC)", "Finished", "Fetched", "Kept", "New", "Errors"):
        table.add_column(col)
    for row in storage.recent_runs(conn, limit):
        n_err = len(json.loads(row["errors"])) if row["errors"] else 0
        finished = row["finished_at"] or "[red]never[/red]"
        table.add_row(str(row["id"]), row["lane"], row["started_at"], finished,
                      str(row["fetched"] or 0), str(row["kept"] or 0), str(row["new"] or 0),
                      f"[yellow]{n_err}[/yellow]" if n_err else "0")
    console.print(table)


if __name__ == "__main__":
    app()
