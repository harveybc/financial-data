"""A retrospective archive is delivered whole, with UNKNOWN availability, and never by date range.

These rules exist because the deployed provider refused the two public panels of the predictor
programme twice over: it parsed their local wall-clock labels ("unparseable time column") and, under
a holdout, refused the whole resource ("spans holdout: request a range"). An archive whose rows'
availability was never observed needs the opposite: the whole file, an UNDECLARED scope, and a
refusal for any request that would assert a publication time.

The source under test is the package this repository ships; it was re-based on the build that is
actually deployed, because no branch here matched that build.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

spec = importlib.util.spec_from_file_location("fds_inventory", SRC / "financial_data_store" / "inventory.py")
inventory = importlib.util.module_from_spec(spec)
sys.modules["fds_inventory"] = inventory
spec.loader.exec_module(inventory)

ARCHIVE = "panels/household.parquet"
CONTRACT = {"event_time_column": "timestamp_label", "available_time_column": "timestamp_label",
            "timezone": "NAIVE_WALL_CLOCK", "time_unit": None, "frequency": "60s"}


def _plugin():
    factory = getattr(inventory, "Plugin", None) or getattr(inventory, "Inventory", None)
    assert factory is not None, "the provider exposes no plugin class"
    return factory()


@pytest.fixture
def lake(tmp_path):
    frame = pd.DataFrame({"timestamp_label": ["16/12/2006 17:24:00", "16/12/2006 17:25:00"],
                          "Global_active_power": [4.216, 5.360]})
    path = tmp_path / ARCHIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path)
    plugin = _plugin()
    plugin.set_params(root_path=str(tmp_path), include_globs=[ARCHIVE], untimed=[ARCHIVE],
                      holdout_start="2006-12-16", resource_contracts={ARCHIVE: CONTRACT},
                      cuts_dir=str(tmp_path / "cuts"), spool_dir=str(tmp_path / "spool"))
    return plugin, path


def test_the_whole_archive_is_delivered_with_unknown_availability(lake):
    plugin, path = lake
    out = plugin.governed_download(ARCHIVE)
    try:
        assert out["delivery"] == "AS_IS" and out["bytes"] == path.stat().st_size
        assert out["availability"]["use_class"] == "UNDECLARED"
        assert out["availability"]["label"] == "UNKNOWN" and out["availability"]["completion_lag_max"] is None
        assert out["time_column"] == ""                       # nothing was parsed as a clock
        assert len(out["availability_contract_sha256"]) == 64
        body = out["handle"].read()
        assert len(body) == out["bytes"]
    finally:
        out["handle"].close()


def test_a_date_range_over_an_archive_is_refused_by_its_own_contract(lake):
    plugin, _ = lake
    with pytest.raises(inventory.UnsupportedError, match="retrospective archive"):
        plugin.governed_download(ARCHIVE, "2006-12-16", "2006-12-17")
    with pytest.raises(inventory.UnsupportedError, match="retrospective archive"):
        plugin.governed_download(ARCHIVE, "1999-01-01", "1999-01-02")     # before any holdout date, still refused
    with pytest.raises(ValueError, match="invalid from/to"):
        plugin.governed_download(ARCHIVE, "2006-12-16", None)


def test_a_timed_resource_keeps_its_previous_behaviour(tmp_path):
    frame = pd.DataFrame({"t": ["2024-01-01T00:00:00", "2024-01-02T00:00:00"], "v": [1.0, 2.0]})
    path = tmp_path / "timed.parquet"
    frame.to_parquet(path)
    plugin = _plugin()
    plugin.set_params(root_path=str(tmp_path), include_globs=["timed.parquet"], untimed=[],
                      holdout_start="2025-01-01",
                      resource_contracts={"timed.parquet": {"event_time_column": "t", "available_time_column": "t",
                                                            "timezone": "UTC", "time_unit": None, "frequency": "1d"}},
                      cuts_dir=str(tmp_path / "cuts"), spool_dir=str(tmp_path / "spool"))
    out = plugin.governed_download("timed.parquet")
    try:
        assert out["delivery"] == "AS_IS" and out["time_column"] == "t"
    finally:
        out["handle"].close()


def test_unknown_is_never_rewritten_as_a_number(lake):
    source = (SRC / "financial_data_store" / "inventory.py").read_text()
    assert "UNDECLARED_SCOPE" in source
    plugin, _ = lake
    out = plugin.governed_download(ARCHIVE)
    try:
        assert out["availability"]["completion_lag_max"] is None
        assert json.dumps(out["availability"]).count("null") >= 1      # the lag stays null, never 0
    finally:
        out["handle"].close()
