import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from inventory_plugins.fs_inventory import (
    HoldoutError,
    Plugin,
    UnparseableError,
    UnsupportedError,
)

HOLDOUT = "2025-01-01"


def _lake(tmp_path, **params):
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    lake = Plugin()
    lake.set_params(
        root_path=str(root),
        include_globs=["**/*.csv", "**/*.parquet"],
        holdout_start=HOLDOUT,
        spool_dir=str(tmp_path / "var" / "spool"),
        cuts_dir=str(tmp_path / "var" / "cuts"),
        **params,
    )
    return lake


def _csv(tmp_path, name, text):
    path = tmp_path / "root" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode())
    return path


def _parquet(tmp_path, name, table, row_group_size=None):
    path = tmp_path / "root" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, row_group_size=row_group_size)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


PRE_HOLDOUT = "ts,v\n2024-12-30,1\n2024-12-31,2\n"
SPANNING = "ts,v\n2024-12-30,1\n2024-12-31 23:59:59,2\n2025-01-01 00:00:00,3\n2025-01-02,4\n"


def test_as_is_delivery_hash_equals_file_bytes(tmp_path):
    lake = _lake(tmp_path)
    path = _csv(tmp_path, "a.csv", PRE_HOLDOUT)
    info = lake.download("a.csv")
    assert info["delivery"] == "AS_IS"
    assert info["path"] == str(path)
    assert info["filename"] == "a.csv"
    assert info["sha256"] == _sha(path) == info["source_sha256"]
    assert info["bytes"] == path.stat().st_size
    assert info["time_column"] == "ts"
    assert not (tmp_path / "var" / "cuts").exists()


def test_cut_on_naive_csv_is_a_byte_subset(tmp_path):
    lake = _lake(tmp_path)
    path = _csv(tmp_path, "a.csv", SPANNING)
    info = lake.download("a.csv", start="2024-12-30", end="2024-12-31")
    assert info["delivery"] == "CUT"
    cut = tmp_path / "var" / "cuts" / _sha(path) / "2024-12-30_2024-12-31.csv"
    assert info["path"] == str(cut)
    assert info["filename"] == "2024-12-30_2024-12-31.csv"
    assert cut.read_bytes() == b"ts,v\n2024-12-30,1\n2024-12-31 23:59:59,2\n"
    assert info["sha256"] == _sha(cut)
    assert info["source_sha256"] == _sha(path)
    assert info["bytes"] == cut.stat().st_size
    assert info["time_column"] == "ts"


def test_cut_csv_with_offsets_uses_wall_clock(tmp_path):
    lake = _lake(tmp_path)
    _csv(
        tmp_path,
        "a.csv",
        "ts,v\n2024-12-31T23:00:00+09:00,1\n2025-01-01T00:00:00+09:00,2\n",
    )
    info = lake.download("a.csv", start="2024-12-31", end="2024-12-31")
    assert info["delivery"] == "CUT"
    # 2025-01-01 00:00+09:00 is 2024-12-31 15:00 UTC; the wall clock excludes it
    assert open(info["path"], "rb").read() == b"ts,v\n2024-12-31T23:00:00+09:00,1\n"


def test_cut_parquet_tokyo_daily_bars(tmp_path):
    lake = _lake(tmp_path)
    days = pd.date_range("2024-12-29", periods=5, freq="D", tz="Asia/Tokyo")
    table = pa.table({"ts": pa.array(days), "close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    source = _parquet(tmp_path, "bars.parquet", table)
    info = lake.download("bars.parquet", start="2024-12-29", end="2024-12-31")
    assert info["delivery"] == "CUT"
    got = pq.read_table(info["path"])
    assert got.schema.field("ts").type == table.schema.field("ts").type
    kept = got.column("ts").to_pandas().dt.tz_localize(None).tolist()
    assert kept == [pd.Timestamp("2024-12-29"), pd.Timestamp("2024-12-30"), pd.Timestamp("2024-12-31")]
    assert got.column("close").to_pylist() == [1.0, 2.0, 3.0]
    meta = pq.read_metadata(info["path"])
    assert meta.num_row_groups == 1
    assert meta.row_group(0).column(0).compression == "SNAPPY"
    assert info["source_sha256"] == _sha(source)
    assert info["sha256"] == _sha(Path(info["path"]))


def test_cut_parquet_new_york_keeps_last_allowed_bar(tmp_path):
    lake = _lake(tmp_path)
    stamps = pd.DatetimeIndex(
        ["2024-12-31 22:00", "2024-12-31 23:00", "2025-01-01 00:00"], tz="America/New_York"
    )
    table = pa.table({"time": pa.array(stamps), "v": [1, 2, 3]})
    _parquet(tmp_path, "ny.parquet", table)
    info = lake.download("ny.parquet", start="2024-12-31", end="2024-12-31")
    assert info["delivery"] == "CUT"
    got = pq.read_table(info["path"])
    # 23:00 New York is 04:00 UTC on 2025-01-01; the wall clock keeps it
    assert got.column("v").to_pylist() == [1, 2]
    assert got.column("time").to_pandas().dt.tz_localize(None).iloc[-1] == pd.Timestamp("2024-12-31 23:00")


def test_multi_line_quoted_csv_is_unsupported(tmp_path):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", 'ts,note\n2024-12-30,"a\nb"\n2024-12-31,c\n2025-01-02,d\n')
    with pytest.raises(UnsupportedError, match="unsupported csv"):
        lake.download("a.csv", start="2024-12-30", end="2024-12-31")
    assert [p for p in (tmp_path / "var" / "cuts").rglob("*") if p.is_file()] == []


def test_malformed_csv_is_unsupported(tmp_path):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", 'ts,v\n2024-12-30,1\n"2024-12-31,2\n')
    with pytest.raises(UnsupportedError, match="unsupported csv"):
        lake.download("a.csv", start="2024-12-30", end="2024-12-31")


def test_cut_parquet_across_row_groups(tmp_path):
    lake = _lake(tmp_path)
    days = pd.date_range("2024-12-27", periods=7, freq="D")
    table = pa.table({"date": pa.array(days), "v": list(range(7))})
    source = _parquet(tmp_path, "rg.parquet", table, row_group_size=3)
    assert pq.read_metadata(source).num_row_groups == 3
    info = lake.download("rg.parquet", start="2024-12-28", end="2024-12-31")
    got = pq.read_table(info["path"])
    assert got.column("v").to_pylist() == [1, 2, 3, 4]
    meta = pq.read_metadata(info["path"])
    assert [meta.row_group(i).num_rows for i in range(meta.num_row_groups)] == [4]
    assert lake.coverage("rg.parquet") == {
        "resource_id": "rg.parquet",
        "rows": 7,
        "t_min": "2024-12-27 00:00:00",
        "t_max": "2025-01-02 00:00:00",
        "time_column": "date",
    }


def test_cut_parquet_never_reads_an_unbounded_row_group(tmp_path, monkeypatch):
    lake = _lake(tmp_path)
    days = pd.date_range("2024-01-01", periods=12, freq="D")
    _parquet(
        tmp_path,
        "bounded.parquet",
        pa.table({"date": pa.array(days), "v": list(range(12))}),
        row_group_size=12,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("governed cuts must use bounded record batches")

    monkeypatch.setattr(pq.ParquetFile, "read_row_group", forbidden)
    info = lake.download("bounded.parquet", start="2024-01-03", end="2024-01-05")
    assert pq.read_table(info["path"]).column("v").to_pylist() == [2, 3, 4]


REAL_TZ_PARQUET = (
    Path(__file__).resolve().parents[2]
    / "market_data"
    / "crypto"
    / "funding_rates"
    / "btcusdt"
    / "funding_rates.parquet"
)


@pytest.mark.skipif(not REAL_TZ_PARQUET.is_file(), reason="real root file not in checkout")
def test_coverage_on_a_real_tz_aware_parquet_reads_one_column(tmp_path, monkeypatch):
    # read-only against one small file of the real roots: timestamp[ms, tz=UTC]
    lake = _lake(tmp_path)
    lake.set_params(root_path=str(REAL_TZ_PARQUET.parents[3]))
    monkeypatch.setattr(pd, "read_parquet", lambda *a, **k: pytest.fail("whole frame"))
    cov = lake.coverage("crypto/funding_rates/btcusdt/funding_rates.parquet")
    assert cov["time_column"] == "fundingTime"
    assert cov["rows"] == pq.read_metadata(REAL_TZ_PARQUET).num_rows
    assert pd.Timestamp(cov["t_min"]) < pd.Timestamp(cov["t_max"])
    assert pd.Timestamp(cov["t_max"]).tz is None


@pytest.mark.parametrize(
    "text",
    [
        "ts,v\n2024-12-30,1\n12/31/2024,2\n",  # mixed formats
        "ts,v\n1735516800,1\n1735603200,2\n",  # epoch integers, no time_unit
        "ts,v\n2024-12-30,1\n,2\n",  # blank
    ],
)
def test_unparseable_time_column(tmp_path, text):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", text)
    with pytest.raises(UnparseableError, match="unparseable time column"):
        lake.download("a.csv", start="2024-12-30", end="2024-12-31")
    with pytest.raises(UnparseableError):
        lake.coverage("a.csv")


def test_zero_rows_removed_is_as_is(tmp_path):
    lake = _lake(tmp_path)
    path = _csv(tmp_path, "a.csv", PRE_HOLDOUT)
    info = lake.download("a.csv", start="2024-12-01", end="2024-12-31")
    assert info["delivery"] == "AS_IS"
    assert info["path"] == str(path)
    assert info["sha256"] == info["source_sha256"] == _sha(path)
    assert list((tmp_path / "var" / "cuts").rglob("*.csv")) == []


def test_cut_written_once_and_reserved_byte_identical(tmp_path):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", SPANNING)
    first = lake.download("a.csv", start="2024-12-30", end="2024-12-31")
    cut = Path(first["path"])
    stamp = cut.stat().st_mtime_ns
    payload = cut.read_bytes()
    again = lake.download("a.csv", start="2024-12-30", end="2024-12-31")
    assert again == first
    assert cut.stat().st_mtime_ns == stamp
    assert cut.read_bytes() == payload
    assert list(cut.parent.glob("*.part")) == []


def test_post_cut_holdout_assertion_discards_the_cut(tmp_path, monkeypatch):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", SPANNING)

    def leaky(path, col, lo, hi):
        return np.array([True, True, True, False]), pd.Timestamp("2025-01-01")

    monkeypatch.setattr(lake, "_keep_mask", leaky)
    with pytest.raises(HoldoutError, match="^holdout$"):
        lake.download("a.csv", start="2024-12-30", end="2024-12-31")
    assert list((tmp_path / "var").rglob("*.csv")) == []


def test_range_reaching_holdout_is_refused(tmp_path):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", SPANNING)
    with pytest.raises(HoldoutError, match="^holdout$"):
        lake.download("a.csv", start="2024-12-30", end="2025-01-01")


def test_as_is_refused_when_resource_spans_holdout(tmp_path):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", SPANNING)
    with pytest.raises(HoldoutError, match="spans holdout: request a range"):
        lake.download("a.csv")


def test_no_time_column_under_holdout_is_refused(tmp_path):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", "k,v\n1,2\n")
    with pytest.raises(HoldoutError, match="no time column under holdout"):
        lake.download("a.csv")
    cov = lake.coverage("a.csv")
    assert cov["rows"] == 1 and cov["t_max"] is None


def test_untimed_resource_served_as_is(tmp_path):
    lake = _lake(tmp_path, untimed=["ref/holidays.csv"])
    path = _csv(tmp_path, "ref/holidays.csv", "date,name\n2025-12-25,xmas\n")
    info = lake.download("ref/holidays.csv")
    assert info["delivery"] == "AS_IS"
    assert info["time_column"] == ""
    assert info["sha256"] == _sha(path)
    ranged = lake.download("ref/holidays.csv", start="2024-01-01", end="2024-12-31")
    assert ranged["delivery"] == "AS_IS"
    assert lake.coverage("ref/holidays.csv")["t_max"] is None


def test_time_columns_override_selects_column(tmp_path):
    lake = _lake(tmp_path, time_columns={"a.csv": "settle_time"})
    _csv(
        tmp_path,
        "a.csv",
        "trade_date,settle_time,v\n2024-12-30,2024-12-31,1\n2024-12-31,2025-01-02,2\n",
    )
    info = lake.download("a.csv", start="2024-12-30", end="2024-12-31")
    assert info["time_column"] == "settle_time"
    assert open(info["path"], "rb").read() == b"trade_date,settle_time,v\n2024-12-30,2024-12-31,1\n"
    assert lake.coverage("a.csv")["time_column"] == "settle_time"


def test_day_only_range_validation(tmp_path):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", PRE_HOLDOUT)
    for start, end in [
        ("2024-12-30", None),
        (None, "2024-12-31"),
        ("2024-12-30T00:00:00", "2024-12-31"),
        ("2024-12-31", "2024-12-30"),
        ("2024-13-01", "2024-12-31"),
        ("20241230", "20241231"),
    ]:
        with pytest.raises(ValueError, match="invalid from/to"):
            lake.download("a.csv", start=start, end=end)
        with pytest.raises(ValueError, match="invalid from/to"):
            lake.read("a.csv", start=start, end=end)


def test_read_uses_strict_upper_bound(tmp_path):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", SPANNING)
    rows = lake.read("a.csv", start="2024-12-30", end="2024-12-31")["rows"]
    assert [row["v"] for row in rows] == [1, 2]


def test_coverage_reads_the_time_column_only(tmp_path, monkeypatch):
    lake = _lake(tmp_path)
    _csv(tmp_path, "a.csv", SPANNING)
    days = pd.date_range("2024-12-29", periods=3, freq="D", tz="UTC")
    _parquet(tmp_path, "b.parquet", pa.table({"ts": pa.array(days), "v": [1, 2, 3]}))
    real_read_csv = pd.read_csv
    calls = []

    def guarded_read_csv(*args, **kwargs):
        calls.append(kwargs)
        assert kwargs.get("nrows") == 0 or "usecols" in kwargs, "whole frame requested"
        return real_read_csv(*args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("pandas.read_parquet loads the whole frame")

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)
    monkeypatch.setattr(pd, "read_parquet", forbidden)
    cov = lake.coverage("a.csv")
    assert cov["rows"] == 4 and cov["t_min"] == "2024-12-30 00:00:00"
    assert cov["t_max"] == "2025-01-02 00:00:00" and cov["time_column"] == "ts"
    assert any("usecols" in call for call in calls)
    cov = lake.coverage("b.parquet")
    assert cov["rows"] == 3 and cov["t_max"] == "2024-12-31 00:00:00"
    info = lake.download("a.csv", start="2024-12-30", end="2024-12-31")
    assert info["delivery"] == "CUT"


def test_source_sha256_memo(tmp_path):
    lake = _lake(tmp_path)
    path = _csv(tmp_path, "a.csv", PRE_HOLDOUT)
    first = lake.download("a.csv")
    memo = json.loads((tmp_path / "var" / "source_sha256.json").read_text())
    entry = memo[str(path)]
    st = path.stat()
    assert entry == {
        "dev": st.st_dev,
        "ino": st.st_ino,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "ctime_ns": st.st_ctime_ns,
        "sha256": first["sha256"],
    }
    path.write_bytes(b"ts,v\n2024-12-30,9\n2024-12-31,8\n")
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    second = lake.download("a.csv")
    assert second["sha256"] == _sha(path) != first["sha256"]


def test_sweep_removes_spool_files_and_parts(tmp_path):
    lake = _lake(tmp_path)
    spool = tmp_path / "var" / "spool"
    spool.mkdir(parents=True)
    (spool / "left.over").write_bytes(b"x")
    part = tmp_path / "var" / "cuts" / "abc" / "2024-01-01_2024-01-02.csv.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(b"x")
    done = part.with_name("2024-01-01_2024-01-02.csv")
    done.write_bytes(b"y")
    lake.sweep()
    assert list(spool.iterdir()) == []
    assert not part.exists() and done.exists()
    assert lake.is_spool(spool / "anything") and not lake.is_spool(done)
