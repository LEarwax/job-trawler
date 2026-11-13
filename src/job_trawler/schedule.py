"""Generates the launchd file (a "LaunchAgent") that runs `trawl run-all` every morning.

Remember the scheduler gotcha: launchd does NOT load your shell setup. So the
file spells everything out: the full path to uv, the repo folder, PATH, and where
output goes. Secrets are not in it; the trawler reads them from .env itself.

If the Mac is asleep at the scheduled time, launchd runs the job when it wakes.
If the Mac is fully shut down, that day's run is skipped (the heartbeat will show it).
"""

import plistlib
from pathlib import Path

LABEL = "local.job-trawler"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def make_plist(uv: str, repo: Path, hour: int, minute: int) -> bytes:
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"invalid time {hour}:{minute:02d}")
    log = repo / "data" / "logs" / "trawl.log"
    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [uv, "run", "--project", str(repo), "trawl", "run-all"],
        "WorkingDirectory": str(repo),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
        "RunAtLoad": False,
    })
