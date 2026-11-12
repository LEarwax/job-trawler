"""Command line. Development tool only; day-to-day use will be the Notion board."""

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Job trawler", no_args_is_help=True)
console = Console()


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
def run(lane: str = typer.Option(..., "--lane", "-l", help="Lane name, e.g. bridge-hospitality")) -> None:
    """Fetch one lane and print the results. Nothing is saved yet (slice 1)."""
    from job_trawler.config import load_lanes, load_local_config
    from job_trawler.pipeline import run_lane
    from job_trawler.sources import build_sources

    cfg = load_local_config()
    all_lanes = load_lanes()
    if lane not in all_lanes:
        console.print(f"[red]No lane {lane!r}. Known: {', '.join(all_lanes)}[/red]")
        raise typer.Exit(1)
    chosen = all_lanes[lane]

    result = run_lane(chosen, cfg, build_sources(chosen.sources))

    table = Table(title=f"{chosen.name}: {len(result.postings)} postings "
                        f"({result.fetched} fetched before dedup)")
    for col in ("Posted", "Title", "Company", "Location", "Pay", "Source"):
        table.add_column(col)
    for p in result.postings:
        table.add_row(str(p.posted_on or "?"), p.title, p.company or "", p.location or "",
                      p.pay or "", p.source)
    console.print(table)
    for err in result.errors:
        console.print(f"[yellow]source error:[/yellow] {err}")
    if result.postings:
        console.print("\nLinks:")
        for i, p in enumerate(result.postings[:10], 1):
            console.print(f"  {i}. {p.url}")


if __name__ == "__main__":
    app()
