"""Loads the two kinds of configuration: local (personal) and lanes (search types).

Config is data, validated on load. `extra="forbid"` means a typo such as
`radius_mile:` fails loudly instead of being silently ignored.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]
LOCAL_CONFIG_PATH = ROOT / "config.local.yaml"
LANES_DIR = ROOT / "lanes"


class LocalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    home: str
    default_radius_mi: int = Field(default=25, gt=0)


class Geo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    center: str = "home"          # "home" or a literal place, e.g. "Pasadena, CA"
    radius_mi: int | None = Field(default=None, gt=0)


class Lane(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    intent: str
    enabled: bool = True
    queries: list[str] = Field(min_length=1)
    sources: list[str] = Field(min_length=1)
    geo: Geo = Geo()
    max_age_hours: int = Field(default=48, gt=0)
    results_per_query: int = Field(default=15, gt=0, le=100)

    def location(self, cfg: LocalConfig) -> str:
        return cfg.home if self.geo.center == "home" else self.geo.center

    def radius(self, cfg: LocalConfig) -> int:
        return self.geo.radius_mi or cfg.default_radius_mi


def _read_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a YAML mapping at the top level")
    return data


def load_local_config(path: Path = LOCAL_CONFIG_PATH) -> LocalConfig:
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} not found. Copy config.example.yaml to config.local.yaml and edit it."
        )
    return LocalConfig.model_validate(_read_yaml(path))


def load_lanes(lanes_dir: Path = LANES_DIR) -> dict[str, Lane]:
    lanes: dict[str, Lane] = {}
    for path in sorted(lanes_dir.glob("*.yaml")):
        lane = Lane.model_validate(_read_yaml(path))
        if lane.name != path.stem:
            raise ValueError(f"{path.name}: lane name {lane.name!r} must match the file name")
        lanes[lane.name] = lane
    return lanes
