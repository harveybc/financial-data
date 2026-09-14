from pathlib import Path

from inventory_plugins.fs_inventory import Plugin


def test_discover_does_not_require_hash(tmp_path):
    (tmp_path / "market_data").mkdir()
    csv = tmp_path / "market_data" / "a.csv"
    csv.write_text("ts,v\n2020-01-01,1\n2025-06-01,9\n")
    lake = Plugin()
    lake.set_params(
        root_path=str(tmp_path),
        include_globs=["market_data/**/*.csv"],
        holdout_start="2025-01-01",
    )
    found = lake.discover()
    assert found[0]["resource_id"] == "market_data/a.csv"
    assert "sha256" not in found[0]
    cov = lake.coverage("market_data/a.csv")
    assert cov["rows"] == 2
    sliced = lake.read("market_data/a.csv", start="2020-01-01", end="2020-12-31")
    assert sliced["sha256"]
    assert len(sliced["rows"]) == 1
