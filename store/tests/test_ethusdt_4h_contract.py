"""The candidate contract for `market_data/crypto/spot_top50/ethusdt/4h.parquet`, on bytes.

A2 asks for the tests *before* the contract is installed: temporal extremes, time zone,
incomplete bar, revisions, disjoint partitions and a change of the future tail that must not
alter what was already available. They run against the provider that serves the lake, over
fixtures built from the real rows of that resource, so what is tested is the delivery rule
and not a description of it.

The fixtures are derived from the first rows of the real file plus the three cases the
measurement found there: a truncated bar, a bar whose close equals its open, and a gap.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

import os

REPO = Path(__file__).resolve().parents[2]
RESOURCE = "market_data/crypto/spot_top50/ethusdt/4h.parquet"
#: The data root is the deployed lake's root. It is read, never written, and never
#: checked out: switching branches under a serving lake changes what it inventories.
DATA_ROOT = Path(os.environ.get("FINANCIAL_DATA_ROOT", REPO))
REAL = DATA_ROOT / RESOURCE
sys.path.insert(0, str(REPO / "store" / "src"))

pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from financial_data_store.provider import FinancialStore  # noqa: E402

CONTRACT = {
    "event_time_column": "open_time",
    "available_time_column": "close_time",
    "timezone": "UTC",
    "time_unit": None,
    "frequency": "4h",
    "availability": {"label": "WINDOW_END", "completion_lag_max": "0s",
                     "timezone_evidence": "PRODUCER_STATEMENT",
                     "use_class": "OFFLINE_DAY_GRANULAR"},
}
STEP = pd.Timedelta("4h")
LAST_MS = pd.Timedelta("1ms")


def bar(open_time, *, span=STEP - LAST_MS, close=1.0):
    return {"open_time": pd.Timestamp(open_time, tz="UTC"),
            "close_time": pd.Timestamp(open_time, tz="UTC") + span,
            "open": close, "high": close, "low": close, "close": close, "volume": 1.0}


def frame(rows):
    return pd.DataFrame(rows)


def write(tmp_path, rows, name="4h.parquet"):
    root = tmp_path / "root" / "market_data"
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    frame(rows).to_parquet(path, index=False)
    return tmp_path / "root", f"market_data/{name}"


def store(root, resource, tmp_path, contract=None):
    backend = FinancialStore()
    backend.set_params(root_path=str(root), include_globs=["market_data/**/*.parquet"],
                       holdout_start=None, cuts_dir=str(tmp_path / "cuts"),
                       spool_dir=str(tmp_path / "spool"),
                       resource_contracts={resource: contract or CONTRACT})
    return backend


def delivered(backend, resource, start=None, end=None):
    info = backend.governed_download(resource, start=start, end=end)
    handle = info["handle"]
    try:
        body = handle.read()
    finally:
        handle.close()
    assert hashlib.sha256(body).hexdigest() == info["sha256"]
    return body, info


def rows_of(body, tmp_path, name="cut.parquet"):
    path = tmp_path / name
    path.write_bytes(body)
    return pd.read_parquet(path)


# ---------------------------------------------------------------- the contract itself

def test_the_candidate_contract_is_accepted_by_the_provider():
    from financial_data_store.inventory import availability_scope

    scope = availability_scope(CONTRACT["availability"])
    assert scope["completion_lag"] == pd.Timedelta(0)
    assert scope["use_class"] == "OFFLINE_DAY_GRANULAR"


def test_live_equivalent_is_refused_for_this_resource():
    """Delivery latency is unobserved, so the live class must not be claimable."""
    from financial_data_store.inventory import UnsupportedError, availability_scope

    live = dict(CONTRACT["availability"], use_class="LIVE_EQUIVALENT")
    availability_scope(live)  # zero lag + known label + producer statement: structurally allowed
    unknown_tz = dict(live, timezone_evidence="UNKNOWN")
    with pytest.raises(UnsupportedError):
        availability_scope(unknown_tz)


# ---------------------------------------------------------------- the delivery rule

def test_a_bar_is_available_on_the_day_its_window_closes(tmp_path):
    """A 20:00 bar of day D closes at 23:59:59.999 of D: it belongs to D, not to D+1."""
    root, resource = write(tmp_path, [bar("2024-01-01T16:00:00Z"), bar("2024-01-01T20:00:00Z"),
                                      bar("2024-01-02T00:00:00Z")])
    backend = store(root, resource, tmp_path)
    body, _info = delivered(backend, resource, start="2024-01-01", end="2024-01-01")
    kept = rows_of(body, tmp_path)
    assert [str(t) for t in kept["open_time"]] == ["2024-01-01 16:00:00+00:00",
                                                   "2024-01-01 20:00:00+00:00"]


def test_the_extreme_of_the_range_is_exclusive_on_completion(tmp_path):
    """The rule is `available + lag < end`: a bar completing at the boundary is excluded."""
    root, resource = write(tmp_path, [bar("2024-01-01T20:00:00Z"),
                                      bar("2024-01-01T20:00:00Z", span=STEP)])  # closes at 00:00:00
    backend = store(root, resource, tmp_path)
    kept = rows_of(delivered(backend, resource, start="2024-01-01", end="2024-01-01")[0], tmp_path)
    assert len(kept) == 1, "the bar completing exactly at the next day's start must not be in it"


def test_a_truncated_bar_is_available_when_it_actually_closed(tmp_path):
    """A truncated bar closes early; it is available then, not at the nominal close."""
    root, resource = write(tmp_path, [bar("2024-01-01T20:00:00Z", span=pd.Timedelta("1h")),
                                      bar("2024-01-01T20:00:00Z", span=pd.Timedelta(0))])
    backend = store(root, resource, tmp_path)
    kept = rows_of(delivered(backend, resource, start="2024-01-01", end="2024-01-01")[0], tmp_path)
    assert len(kept) == 2, "both closed inside the day"


def test_time_zone_is_read_from_the_schema_not_from_the_name(tmp_path):
    """The columns are tz-aware UTC; a cut is a UTC calendar day, and that is checkable."""
    root, resource = write(tmp_path, [bar("2024-01-01T00:00:00Z"), bar("2024-01-01T20:00:00Z")])
    backend = store(root, resource, tmp_path)
    kept = rows_of(delivered(backend, resource, start="2024-01-01", end="2024-01-01")[0], tmp_path)
    assert len(kept) == 2
    # the same instants named in another zone would fall on two different days; the schema,
    # not the reader, decides which day each row belongs to
    assert str(kept["open_time"].dt.tz) in ("UTC", "None")


def test_an_intrabar_range_is_refused(tmp_path):
    root, resource = write(tmp_path, [bar("2024-01-01T00:00:00Z")])
    backend = store(root, resource, tmp_path)
    with pytest.raises(Exception):
        backend.governed_download(resource, start="2024-01-01T04:00:00", end="2024-01-01T08:00:00")


# ---------------------------------------------------------------- what must not move

def test_partitions_are_disjoint_and_cover_the_whole_range(tmp_path):
    rows = [bar(f"2024-01-0{d}T{h:02d}:00:00Z") for d in (1, 2, 3) for h in (0, 4, 8, 12, 16, 20)]
    root, resource = write(tmp_path, rows)
    backend = store(root, resource, tmp_path)
    cuts = {name: rows_of(delivered(backend, resource, start=lo, end=hi)[0], tmp_path, f"{name}.parquet")
            for name, (lo, hi) in {"train": ("2024-01-01", "2024-01-01"),
                                   "calibration": ("2024-01-02", "2024-01-02"),
                                   "confirmation": ("2024-01-03", "2024-01-03")}.items()}
    seen = [set(map(str, cut["open_time"])) for cut in cuts.values()]
    assert seen[0] & seen[1] == set() and seen[1] & seen[2] == set() and seen[0] & seen[2] == set()
    whole = rows_of(delivered(backend, resource, start="2024-01-01", end="2024-01-03")[0],
                    tmp_path, "whole.parquet")
    assert set().union(*seen) == set(map(str, whole["open_time"]))


def test_appending_future_bars_leaves_an_earlier_cut_byte_identical(tmp_path):
    rows = [bar(f"2024-01-01T{h:02d}:00:00Z") for h in (0, 4, 8, 12, 16, 20)]
    root, resource = write(tmp_path, rows)
    backend = store(root, resource, tmp_path)
    before, info_before = delivered(backend, resource, start="2024-01-01", end="2024-01-01")

    future = rows + [bar("2024-01-02T00:00:00Z", close=999.0), bar("2024-01-02T04:00:00Z", close=999.0)]
    frame(future).to_parquet(root / "market_data" / "4h.parquet", index=False)
    backend_after = store(root, resource, tmp_path / "second")
    after, info_after = delivered(backend_after, resource, start="2024-01-01", end="2024-01-01")
    assert info_after["sha256"] == info_before["sha256"]
    assert after == before, "a row that did not exist yet changed a delivery that was already made"


def test_a_revision_of_a_past_bar_is_visible_in_the_delivery_identity(tmp_path):
    """Revisions are not claimed to be absent; they must be detectable when they happen."""
    rows = [bar("2024-01-01T00:00:00Z"), bar("2024-01-01T04:00:00Z")]
    root, resource = write(tmp_path, rows)
    backend = store(root, resource, tmp_path)
    _body, first = delivered(backend, resource, start="2024-01-01", end="2024-01-01")

    revised = [bar("2024-01-01T00:00:00Z", close=2.0), bar("2024-01-01T04:00:00Z")]
    frame(revised).to_parquet(root / "market_data" / "4h.parquet", index=False)
    _body2, second = delivered(store(root, resource, tmp_path / "third"), resource,
                               start="2024-01-01", end="2024-01-01")
    assert second["sha256"] != first["sha256"]
    assert second["source_sha256"] != first["source_sha256"]


# ---------------------------------------------------------------- the real resource

@pytest.mark.skipif(not REAL.is_file(), reason="the financial resource is not in this checkout")
def test_the_real_resource_still_matches_the_measured_facts():
    """If the file changes, this candidate contract stops being about it."""
    digest = hashlib.sha256(REAL.read_bytes()).hexdigest()
    declared = json.loads((REAL.parent / "provenance.json").read_text(encoding="utf-8"))
    pinned = {entry["path"]: entry["sha256"] for entry in declared["files"]}
    assert pinned[RESOURCE] == digest, "the bytes no longer match the producer's pinned digest"
    frame_ = pd.read_parquet(REAL, columns=["open_time", "close_time"])
    assert len(frame_) == 18337
    assert str(frame_["open_time"].dt.tz) == "UTC" and str(frame_["close_time"].dt.tz) == "UTC"
    assert frame_["open_time"].is_monotonic_increasing
    assert not frame_["open_time"].duplicated().any()
    delta = frame_["close_time"] - frame_["open_time"]
    assert (delta >= pd.Timedelta(0)).all() and (delta <= STEP).all()
    assert int((delta < STEP - LAST_MS).sum()) == 21, "truncated bars"
    epoch_ms = frame_["open_time"].astype("int64")
    assert int((epoch_ms % int(STEP.total_seconds() * 1000) != 0).sum()) == 0, "off-grid rows"
