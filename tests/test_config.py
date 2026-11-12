import pytest
from pydantic import ValidationError

from job_trawler.config import Lane, LocalConfig, load_lanes

CFG = LocalConfig(home="Los Angeles, CA 90026", default_radius_mi=25)


def lane(**overrides) -> Lane:
    base = dict(name="t", intent="test", queries=["bartender"], sources=["jobspy"])
    return Lane.model_validate(base | overrides)


def test_home_resolves_from_local_config():
    assert lane().location(CFG) == "Los Angeles, CA 90026"


def test_literal_center_overrides_home():
    assert lane(geo={"center": "Pasadena, CA"}).location(CFG) == "Pasadena, CA"


def test_radius_falls_back_to_default():
    assert lane().radius(CFG) == 25
    assert lane(geo={"radius_mi": 10}).radius(CFG) == 10


def test_typo_in_lane_fails_loudly():
    with pytest.raises(ValidationError):
        lane(radius_mile=10)


def test_lane_needs_at_least_one_query():
    with pytest.raises(ValidationError):
        lane(queries=[])


def test_repo_lanes_all_load():
    lanes = load_lanes()
    assert "bridge-hospitality" in lanes


def test_lane_name_must_match_file(tmp_path):
    (tmp_path / "a.yaml").write_text("name: b\nintent: x\nqueries: [q]\nsources: [jobspy]\n")
    with pytest.raises(ValueError, match="must match"):
        load_lanes(tmp_path)
