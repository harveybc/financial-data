"""Temporal semantics of a financial resource: what is measured, and what is refused.

Successor of `test_ethusdt_4h_contract.py` after Musashi's review (2026-09-14). Three of its
tests did not test what their names claimed and are corrected here:

* the live-class test called the validator **without** expecting a refusal, then asserted a
  different refusal (a missing time zone). The refusal that matters for this resource is that
  its publication time was never observed, and it is now asserted as such;
* the time-zone test accepted `None` as well as UTC. It now requires exact UTC;
* the intrabar test accepted any `Exception`. It now requires the typed refusal.

Added, from the same review: reception on the following day, a late revision, a bar that is
explicitly not final, and the eligibility refusals each with its measurement.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RESOURCE = "market_data/crypto/spot_top50/ethusdt/4h.parquet"
#: The deployed lake's data root: read, never written, never checked out.
DATA_ROOT = Path(os.environ.get("FINANCIAL_DATA_ROOT", REPO))
REAL = DATA_ROOT / RESOURCE
sys.path.insert(0, str(REPO / "store" / "src"))

pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from financial_data_store import inventory as inv  # noqa: E402
from financial_data_store.provider import FinancialStore  # noqa: E402

TOOL = REPO / "store" / "tools" / "derive_availability_contract.py"
STEP = pd.Timedelta("4h")
LAST_MS = pd.Timedelta("1ms")

ARCHIVE = {
    "event_time_column": "open_time", "available_time_column": "close_time",
    "timezone": "UTC", "time_unit": None, "frequency": "4h",
    "availability": {"label": "WINDOW_END", "completion_lag_max": "UNKNOWN",
                     "timezone_evidence": "PRODUCER_STATEMENT",
                     "use_class": "ARCHIVE_RETROSPECTIVE"},
}
POINT_IN_TIME = {
    "event_time_column": "open_time", "available_time_column": "received_time",
    "timezone": "UTC", "time_unit": None, "frequency": "4h",
    "availability": {"label": "EVENT_INSTANT", "completion_lag_max": "0s",
                     "timezone_evidence": "PRODUCER_STATEMENT",
                     "use_class": "OFFLINE_DAY_GRANULAR"},
}


def load_tool():
    import importlib.util

    spec = importlib.util.spec_from_file_location("derive_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bar(open_time, *, span=STEP - LAST_MS, close=1.0, received=None, final=None):
    row = {"open_time": pd.Timestamp(open_time, tz="UTC"),
           "close_time": pd.Timestamp(open_time, tz="UTC") + span,
           "open": close, "high": close, "low": close, "close": close,
           "volume": 1.0, "trade_count": 1}
    if received is not None:
        row["received_time"] = pd.Timestamp(received, tz="UTC")
    if final is not None:
        row["is_final"] = final
    return row


def write(tmp_path, rows, name="4h.parquet"):
    root = tmp_path / "root" / "market_data"
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(root / name, index=False)
    return tmp_path / "root", f"market_data/{name}"


def store(root, resource, tmp_path, contract):
    backend = FinancialStore()
    backend.set_params(root_path=str(root), include_globs=["market_data/**/*.parquet"],
                       holdout_start=None, cuts_dir=str(tmp_path / "cuts"),
                       spool_dir=str(tmp_path / "spool"),
                       resource_contracts={resource: contract})
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


# ------------------------------------------------- the clocks, and what they may promise

def test_a_window_close_is_not_an_availability_claim(tmp_path):
    """The archive class exists because publication was never observed."""
    root, resource = write(tmp_path, [bar("2024-01-01T20:00:00Z")])
    backend = store(root, resource, tmp_path, ARCHIVE)
    body, info = delivered(backend, resource)          # whole resource: allowed
    assert info["delivery"] == "AS_IS"
    assert info["availability"]["use_class"] == "ARCHIVE_RETROSPECTIVE"
    assert info["availability"]["completion_lag_max"] == "UNKNOWN"
    assert len(rows_of(body, tmp_path)) == 1


def test_a_ranged_delivery_of_an_archive_is_refused_with_its_reason(tmp_path):
    root, resource = write(tmp_path, [bar("2024-01-01T20:00:00Z")])
    backend = store(root, resource, tmp_path, ARCHIVE)
    with pytest.raises(inv.UnsupportedError) as refusal:
        backend.governed_download(resource, start="2024-01-01", end="2024-01-01")
    assert "retrospective archive" in str(refusal.value)


def test_an_archive_may_not_declare_a_numeric_lag():
    """A number here would be the invention the class exists to prevent."""
    with pytest.raises(inv.UnsupportedError, match="completion_lag_max UNKNOWN"):
        inv.availability_scope(dict(ARCHIVE["availability"], completion_lag_max="0s"))


def test_this_resource_cannot_claim_live_or_point_in_time(tmp_path):
    """The refusal that matters here, asserted as a refusal — Musashi's finding 3."""
    tool = load_tool()
    root, resource = write(tmp_path, [bar("2024-01-01T00:00:00Z"), bar("2024-01-01T04:00:00Z")])
    facts = tool.measure(root / resource, "open_time", "close_time", "4h")
    clocks = tool.clocks(facts, {"acquired_at": "2026-05-01T15:58:56Z"})
    verdict = tool.eligibility(facts, clocks, {})
    assert verdict["installable_availability_contract"] is False
    assert verdict["kind"] == "ARCHIVE_RETROSPECTIVE"
    assert verdict["point_in_time_claim"] == "REFUSED" and verdict["live_claim"] == "REFUSED"
    reasons = {r["reason"] for r in verdict["refusals"]}
    assert "PUBLICATION_TIME_UNOBSERVED" in reasons
    assert "FINALITY_NOT_DEMONSTRATED" in reasons


def test_an_observed_publication_column_is_what_supports_availability(tmp_path):
    """The positive case: when the producer records reception, the contract is supported."""
    tool = load_tool()
    rows = [bar("2024-01-01T00:00:00Z", received="2024-01-01T04:05:00Z"),
            bar("2024-01-01T04:00:00Z", received="2024-01-01T08:05:00Z")]
    root, resource = write(tmp_path, rows)
    facts = tool.measure(root / resource, "open_time", "close_time", "4h", "received_time")
    clocks = tool.clocks(facts, {"acquired_at": None}, "received_time")
    assert clocks["publication"]["status"] == "MEASURED"
    verdict = tool.eligibility(facts, clocks, {})
    # finality is still not demonstrated for a nominal-span file, so this stays an archive:
    # the publication clock alone does not make a bar final
    assert clocks["finalization"]["status"] == "NOT_DEMONSTRATED"
    assert verdict["kind"] == "ARCHIVE_RETROSPECTIVE"


def test_a_publication_column_before_the_window_end_is_refused(tmp_path):
    tool = load_tool()
    rows = [bar("2024-01-01T00:00:00Z", received="2024-01-01T00:00:01Z")]  # before the close
    root, resource = write(tmp_path, rows)
    facts = tool.measure(root / resource, "open_time", "close_time", "4h", "received_time")
    clocks = tool.clocks(facts, {}, "received_time")
    assert clocks["publication"]["status"] == "REFUSED"


# ------------------------------------------------- the counterexamples of the review

def test_reception_on_the_following_day_is_not_availability_on_the_first(tmp_path):
    """Musashi's counterexample: closes 23:59:59.999 on day 1, received 00:10 on day 2."""
    row = bar("2024-01-01T20:00:00Z", received="2024-01-02T00:10:00Z")
    root, resource = write(tmp_path, [row])
    # under a contract that uses the *observed* reception, the row is not in day 1
    backend = store(root, resource, tmp_path, POINT_IN_TIME)
    body, _info = delivered(backend, resource, start="2024-01-01", end="2024-01-01")
    assert len(rows_of(body, tmp_path, "day1.parquet")) == 0
    # and under the archive contract the question cannot even be asked
    archive = store(root, resource, tmp_path / "second", ARCHIVE)
    with pytest.raises(inv.UnsupportedError):
        archive.governed_download(resource, start="2024-01-01", end="2024-01-01")


def test_a_bar_that_is_not_final_is_reported_as_such(tmp_path):
    """Musashi's counterexample: a zero-span bar with is_final=False was delivered anyway."""
    tool = load_tool()
    rows = [bar("2024-01-01T20:00:00Z", span=pd.Timedelta(0), final=False),
            bar("2024-01-01T00:00:00Z")]
    root, resource = write(tmp_path, sorted(rows, key=lambda r: r["open_time"]))
    facts = tool.measure(root / resource, "open_time", "close_time", "4h")
    anomalies = facts["anomalous_bars"]
    assert anomalies["count"] == 1
    assert anomalies["finality_demonstrated"] is False
    assert anomalies["rows"][0]["kind"] in ("ZERO_SPAN", "EMPTY_PLACEHOLDER")
    verdict = tool.eligibility(facts, tool.clocks(facts, {}), {})
    assert "FINALITY_NOT_DEMONSTRATED" in {r["reason"] for r in verdict["refusals"]}


def test_a_late_revision_changes_the_delivery_identity(tmp_path):
    rows = [bar("2024-01-01T00:00:00Z"), bar("2024-01-01T04:00:00Z")]
    root, resource = write(tmp_path, rows)
    _body, first = delivered(store(root, resource, tmp_path, ARCHIVE), resource)
    revised = [bar("2024-01-01T00:00:00Z", close=2.0), bar("2024-01-01T04:00:00Z")]
    pd.DataFrame(revised).to_parquet(root / "market_data" / "4h.parquet", index=False)
    _body2, second = delivered(store(root, resource, tmp_path / "third", ARCHIVE), resource)
    assert second["sha256"] != first["sha256"]
    assert second["source_sha256"] != first["source_sha256"]


# ------------------------------------------------- eligibility refuses invalidating facts

@pytest.mark.parametrize("facts,expected", [
    ({"measured": False, "why": "unreadable"}, "MEASUREMENT_FAILED"),
    ({"measured": True, "event_monotonic_increasing": False, "event_duplicates": 0,
      "window_end_at_or_after_start_always": True, "event_column": {"timezone_in_schema": "UTC",
                                                                    "is_datetime": True}},
     "EVENT_CLOCK_NOT_MONOTONIC"),
    ({"measured": True, "event_monotonic_increasing": True, "event_duplicates": 9,
      "window_end_at_or_after_start_always": True, "event_column": {"timezone_in_schema": "UTC",
                                                                    "is_datetime": True}},
     "DUPLICATE_EVENT_TIMES"),
    ({"measured": True, "event_monotonic_increasing": True, "event_duplicates": 0,
      "window_end_at_or_after_start_always": False, "event_column": {"timezone_in_schema": "UTC",
                                                                     "is_datetime": True}},
     "WINDOW_END_BEFORE_START"),
])
def test_invalidating_measurements_refuse_instead_of_producing_a_contract(facts, expected):
    """Musashi's finding 4, reproduced without real data and now stopped."""
    tool = load_tool()
    verdict = tool.eligibility(facts, tool.clocks(facts, {}), {})
    assert verdict["installable_availability_contract"] is False
    assert expected in {r["reason"] for r in verdict["refusals"]}
    assert verdict["kind"] == "UNUSABLE"
    assert tool.archive_contract("open_time", "close_time", "4h", facts, verdict) is None


def test_bytes_that_are_not_the_producers_are_refused():
    tool = load_tool()
    facts = {"measured": True, "event_monotonic_increasing": True, "event_duplicates": 0,
             "window_end_at_or_after_start_always": True,
             "event_column": {"timezone_in_schema": "UTC", "is_datetime": True}}
    verdict = tool.eligibility(facts, tool.clocks(facts, {}),
                               {"declared_sha256": "a" * 64, "digest_matches": False})
    assert "DIGEST_DOES_NOT_MATCH_PRODUCER" in {r["reason"] for r in verdict["refusals"]}


# ------------------------------------------------- the delivery rule, where it still applies

def test_the_time_zone_is_exactly_utc(tmp_path):
    """Corrected: `None` is no longer accepted as if it were UTC."""
    root, resource = write(tmp_path, [bar("2024-01-01T00:00:00Z", received="2024-01-01T04:01:00Z")])
    backend = store(root, resource, tmp_path, POINT_IN_TIME)
    body, _info = delivered(backend, resource, start="2024-01-01", end="2024-01-01")
    kept = rows_of(body, tmp_path)
    assert str(kept["open_time"].dt.tz) == "UTC"
    assert str(kept["received_time"].dt.tz) == "UTC"


def test_an_intrabar_range_is_refused_with_its_type(tmp_path):
    """Corrected: the typed refusal, not `any Exception`."""
    root, resource = write(tmp_path, [bar("2024-01-01T00:00:00Z", received="2024-01-01T04:01:00Z")])
    backend = store(root, resource, tmp_path, POINT_IN_TIME)
    with pytest.raises(ValueError):
        backend.governed_download(resource, start="2024-01-01T04:00:00", end="2024-01-01T08:00:00")


def test_partitions_stay_disjoint_under_an_observed_availability_column(tmp_path):
    rows = [bar(f"2024-01-0{d}T{h:02d}:00:00Z", received=f"2024-01-0{d}T{h + 1:02d}:05:00Z")
            for d in (1, 2) for h in (0, 4, 8, 12, 16)]
    root, resource = write(tmp_path, rows)
    backend = store(root, resource, tmp_path, POINT_IN_TIME)
    first = rows_of(delivered(backend, resource, start="2024-01-01", end="2024-01-01")[0],
                    tmp_path, "a.parquet")
    second = rows_of(delivered(backend, resource, start="2024-01-02", end="2024-01-02")[0],
                     tmp_path, "b.parquet")
    assert set(map(str, first["open_time"])) & set(map(str, second["open_time"])) == set()


# ------------------------------------------------- the real resource

@pytest.mark.skipif(not REAL.is_file(), reason="the financial resource is not in this checkout")
def test_the_real_resource_is_characterised_as_a_retrospective_archive():
    tool = load_tool()
    facts = tool.measure(REAL, "open_time", "close_time", "4h")
    declaration = tool.producer_declaration(DATA_ROOT, RESOURCE)
    declaration["digest_matches"] = (declaration["declared_sha256"]
                                     == hashlib.sha256(REAL.read_bytes()).hexdigest())
    clocks = tool.clocks(facts, declaration)
    verdict = tool.eligibility(facts, clocks, declaration)
    assert declaration["digest_matches"] is True
    assert facts["rows"] == 18337
    assert facts["event_column"]["timezone_in_schema"] == "UTC"
    assert facts["anomalous_bars"]["count"] == 21
    assert facts["anomalous_bars"]["by_kind"] == {"EMPTY_PLACEHOLDER": 1,
                                                  "SHORTER_NOMINAL_INTERVAL": 12,
                                                  "PARTIAL_AGGREGATE": 8}
    assert clocks["publication"]["status"] == "UNOBSERVED"
    assert clocks["reception"]["status"] == "UNOBSERVED"
    assert verdict["kind"] == "ARCHIVE_RETROSPECTIVE"
    assert verdict["installable_availability_contract"] is False


@pytest.mark.skipif(not REAL.is_file(), reason="the financial resource is not in this checkout")
def test_the_withdrawn_candidate_is_not_reachable_from_the_tool():
    """The v1 candidate promised zero lag against close_time. Nothing emits that any more."""
    tool = load_tool()
    facts = tool.measure(REAL, "open_time", "close_time", "4h")
    verdict = tool.eligibility(facts, tool.clocks(facts, {}), {})
    contract = tool.archive_contract("open_time", "close_time", "4h", facts, verdict)
    assert contract["availability"]["completion_lag_max"] == "UNKNOWN"
    assert contract["availability"]["use_class"] == "ARCHIVE_RETROSPECTIVE"
    body = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    assert "0s" not in body
