"""Regression tests for the review blockers of the download verb: ids that escape the lake, read() under holdout."""

import os

import pytest

from inventory_plugins.fs_inventory import HoldoutError, Plugin


def _lake(tmp_path, **params):
    root = tmp_path / "lake"
    (root / "market_data").mkdir(parents=True)
    (root / "market_data" / "hourly.csv").write_text("ts,v\n2024-12-30 00:00:00,1\n2024-12-31 00:00:00,2\n")
    (root / "market_data" / "untimed.csv").write_text("name,value\na,1\nb,2\n")
    (tmp_path / "secret.csv").write_text("ts,v\n2025-06-01 00:00:00,9\n")
    os.symlink(tmp_path / "secret.csv", root / "market_data" / "link.csv")
    lake = Plugin()
    lake.set_params(root_path=str(root), include_globs=["market_data/**/*.csv"], holdout_start="2025-01-01",
                    spool_dir=str(tmp_path / "spool"), cuts_dir=str(tmp_path / "cuts"), **params)
    return lake


@pytest.mark.parametrize("rid", ["../secret.csv", "market_data/../../secret.csv", "/etc/hostname", "", ".",
                                 "market_data//hourly.csv", "market_data\\hourly.csv", "market_data/link.csv"])
def test_an_id_outside_the_lake_is_unknown_on_every_verb(tmp_path, rid):
    lake = _lake(tmp_path)
    with pytest.raises(FileNotFoundError):
        lake.download(rid)
    with pytest.raises(FileNotFoundError):
        lake.coverage(rid)
    with pytest.raises(FileNotFoundError):
        lake.read(rid, start="2024-12-30", end="2024-12-31")


def test_read_without_a_time_column_under_holdout_is_refused(tmp_path):
    lake = _lake(tmp_path)
    with pytest.raises(HoldoutError):
        lake.read("market_data/untimed.csv", start="2020-01-01", end="2020-01-02")


def test_read_of_a_declared_untimed_resource_is_allowed(tmp_path):
    lake = _lake(tmp_path, untimed=["market_data/untimed.csv"])
    assert len(lake.read("market_data/untimed.csv")["rows"]) == 2
