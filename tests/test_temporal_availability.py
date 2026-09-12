"""C83 fixtures (order 2026-09-12): temporal availability semantics.

Real truncated-bar and gap patterns are taken from the ETH H4 source
parquet (features/trading_asset_data/ethusdt/4h.parquet). The real data
files are only ever READ; digest-mismatch fixtures use temporary copies.
"""
from __future__ import annotations

import builtins
import hashlib
import importlib.util
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PREDICTOR = ROOT.parent / "predictor"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ta = _load("temporal_availability", "_scripts/temporal_availability.py")
mat = _load("materialize_eth_h4_temporal_contract",
            "_scripts/materialize_eth_h4_temporal_contract.py")

SHA = "a" * 64
OTHER_SHA = "b" * 64
H4 = 14_400_000


def ms(s: str) -> int:
    """'2018-01-04 03:00:14.849' (UTC) -> integer ms."""
    fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in s else "%Y-%m-%d %H:%M:%S"
    dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
    return int(round(dt.timestamp() * 1000))


def contract(**over):
    c = {
        "contract_id": "fixture.bar_open", "dataset_id": "fixture.eth_h4",
        "dataset_sha256": SHA, "timestamp_semantics": "BAR_OPEN",
        "information_complete_not_before": "PER_BAR_CLOSE_TIME",
        "nominal_bar_seconds": 14400,
        "bar_close_time_convention": "INCLUSIVE_LAST_MILLISECOND",
        "provider_delivery_latency": {"status": "UNOBSERVED", "seconds": None,
                                      "evidence": "none"},
        "provenance": {"status": "EVIDENCED_BY_EXACT_MATCH_NOT_BY_DECLARATION",
                       "basis": "fixture"},
    }
    c.update(over)
    return c


def bar_close_contract(**over):
    return contract(**{"contract_id": "fixture.bar_close", "timestamp_semantics": "BAR_CLOSE",
                       "information_complete_not_before": "TIMESTAMP_ITSELF",
                       "nominal_bar_seconds": None, **over})


def publication_contract(**over):
    return contract(**{"contract_id": "fixture.publication", "timestamp_semantics": "PUBLICATION",
                       "information_complete_not_before": "PUBLICATION_TIMESTAMP",
                       "nominal_bar_seconds": None, **over})


def declared_latency(seconds=2.5):
    return {"status": "DECLARED", "seconds": seconds, "evidence": "fixture SLA"}


EMITTED: set[str] = set()


def cib(c, row, sha=SHA):
    b = ta.causal_information_bound(c, row, observed_sha256=sha)
    EMITTED.update(r.split(":")[0] for r in b.reasons)
    return b


# ------------------------------------------------------------ BAR_OPEN
def test_bar_open_full_bar_completes_at_its_close_time():
    o = ms("2019-01-01 00:00:00")
    c = contract()
    b = cib(c, {"timestamp_ms": o, "close_time_ms": o + H4 - 1, "next_timestamp_ms": o + H4})
    assert (b.status, b.utc_ms, b.reasons) == ("RESOLVED", o + H4 - 1, ("PER_BAR_CLOSE_TIME",))
    assert ta.gate_e5a(c, b).is_open


def test_real_truncated_bar_completes_at_actual_close_not_open_plus_4h():
    # 2018-01-04 00:00 -> close_time 03:00:14.849 (span 10814.849 s)
    o, cl = ms("2018-01-04 00:00:00"), ms("2018-01-04 03:00:14.849")
    b = cib(contract(), {"timestamp_ms": o, "close_time_ms": cl,
                         "next_timestamp_ms": ms("2018-01-04 04:00:00")})
    assert b.status == "RESOLVED" and b.utc_ms == cl
    assert b.utc_ms != o + H4 - 1
    assert "TRUNCATED_BAR" in b.reasons and "FOLLOWED_BY_GAP" not in b.reasons


def test_real_zero_span_bar():
    # 2017-09-06 16:00 close_time == open time
    o = ms("2017-09-06 16:00:00")
    b = cib(contract(), {"timestamp_ms": o, "close_time_ms": o,
                         "next_timestamp_ms": o + H4})
    assert b.status == "RESOLVED" and b.utc_ms == o
    assert {"TRUNCATED_BAR", "ZERO_SPAN_BAR"} <= set(b.reasons)


def test_real_gap_after_truncated_bar_does_not_move_the_bound():
    # 2018-02-08 00:00 closes 00:28:14.799; next bar opens 2018-02-09 08:00 (115200 s)
    o, cl, n = ms("2018-02-08 00:00:00"), ms("2018-02-08 00:28:14.799"), ms("2018-02-09 08:00:00")
    b = cib(contract(), {"timestamp_ms": o, "close_time_ms": cl, "next_timestamp_ms": n})
    assert b.status == "RESOLVED" and b.utc_ms == cl
    assert {"TRUNCATED_BAR", "FOLLOWED_BY_GAP"} <= set(b.reasons)


def test_full_bar_before_gap_is_flagged_but_resolved():
    o = ms("2019-01-01 00:00:00")
    b = cib(contract(), {"timestamp_ms": o, "close_time_ms": o + H4 - 1,
                         "next_timestamp_ms": o + 2 * H4})
    assert b.status == "RESOLVED" and "FOLLOWED_BY_GAP" in b.reasons
    assert "TRUNCATED_BAR" not in b.reasons


def test_close_time_absent_is_not_inferred_from_nominal_bar():
    c = contract()
    b = cib(c, {"timestamp_ms": ms("2019-01-01 00:00:00")})
    assert b.status == "UNRESOLVED" and b.utc_ms is None
    assert b.reasons == ("CLOSE_TIME_ABSENT_NOT_INFERRED_FROM_NOMINAL_BAR",)
    assert not ta.gate_e5a(c, b).is_open


@pytest.mark.parametrize("close_off,next_off,reason", [
    (-1, H4, "CLOSE_TIME_BEFORE_OPEN_TIME"),
    (H4, 2 * H4, "CLOSE_TIME_EXCEEDS_NOMINAL_BAR"),
    (7_200_000, 7_200_000, "CLOSE_TIME_OVERLAPS_NEXT_BAR"),
])
def test_contradictory_close_time_is_refused(close_off, next_off, reason):
    o = ms("2019-01-01 00:00:00")
    c = contract()
    b = cib(c, {"timestamp_ms": o, "close_time_ms": o + close_off,
                "next_timestamp_ms": o + next_off})
    assert (b.status, b.reasons, b.utc_ms) == ("REFUSED", (reason,), None)
    assert not ta.gate_e5a(c, b).is_open


def test_non_increasing_timestamp_refused():
    o = ms("2019-01-01 00:00:00")
    b = cib(contract(), {"timestamp_ms": o, "close_time_ms": o + H4 - 1, "next_timestamp_ms": o})
    assert b.status == "REFUSED" and b.reasons == ("NON_INCREASING_TIMESTAMP",)


def test_exclusive_end_convention_accepts_exact_nominal_span():
    o = ms("2019-01-01 00:00:00")
    c = contract(bar_close_time_convention="EXCLUSIVE_END")
    b = cib(c, {"timestamp_ms": o, "close_time_ms": o + H4, "next_timestamp_ms": o + H4 + 1})
    assert b.status == "RESOLVED" and "TRUNCATED_BAR" not in b.reasons


# ----------------------------------------------------------- BAR_CLOSE
def test_bar_close_bound_is_the_timestamp():
    t = ms("2019-01-01 04:00:00")
    c = bar_close_contract()
    b = cib(c, {"timestamp_ms": t})
    assert (b.status, b.utc_ms, b.reasons) == ("RESOLVED", t, ("TIMESTAMP_IS_BAR_CLOSE",))
    assert ta.gate_e5a(c, b).is_open


def test_bar_close_with_contradicting_close_time_refused():
    t = ms("2019-01-01 04:00:00")
    b = cib(bar_close_contract(), {"timestamp_ms": t, "close_time_ms": t + H4 - 1})
    assert b.status == "REFUSED"
    assert b.reasons == ("CLOSE_TIME_CONTRADICTS_BAR_CLOSE_SEMANTICS",)


def test_rule_that_contradicts_semantics_invalidates_contract():
    c = bar_close_contract(information_complete_not_before="PER_BAR_CLOSE_TIME")
    assert "RULE_CONTRADICTS_SEMANTICS" in ta.validate_contract(c)
    b = cib(c, {"timestamp_ms": 0})
    assert b.status == "REFUSED" and b.reasons[0] == "CONTRACT_INVALID"


# --------------------------------------------------------- PUBLICATION
def test_publication_bound_is_publication_time():
    ev, pub = ms("2019-01-31 00:00:00"), ms("2019-02-15 13:30:00")
    c = publication_contract()
    b = cib(c, {"timestamp_ms": ev, "publication_time_ms": pub})
    assert (b.status, b.utc_ms) == ("RESOLVED", pub)
    assert ta.gate_e5a(c, b).is_open


def test_publication_absent_unresolved_and_before_event_refused():
    ev = ms("2019-01-31 00:00:00")
    assert cib(publication_contract(), {"timestamp_ms": ev}).reasons == ("PUBLICATION_TIME_ABSENT",)
    b = cib(publication_contract(), {"timestamp_ms": ev, "publication_time_ms": ev - 1})
    assert b.status == "REFUSED" and b.reasons == ("PUBLICATION_BEFORE_EVENT_TIME",)


# ------------------------------------------------------------- latency
def test_unobserved_latency_is_never_zero_and_e5b_refuses():
    o = ms("2019-01-01 00:00:00")
    c = contract()
    cb = cib(c, {"timestamp_ms": o, "close_time_ms": o + H4 - 1})
    ob = ta.operational_delivery_bound(c, cb)
    assert ob.kind == "operational_delivery_bound"
    assert ob.status == "UNOBSERVED" and ob.utc_ms is None
    assert ob.reasons == ("PROVIDER_DELIVERY_LATENCY_UNOBSERVED",)
    assert ta.gate_e5a(c, cb).is_open
    g = ta.gate_e5b(c, cb, ob)
    assert not g.is_open and g.reasons[0] == "OPERATIONAL_DELIVERY_BOUND_NOT_RESOLVED"


@pytest.mark.parametrize("lat,defect", [
    ({"status": "UNOBSERVED", "seconds": 0, "evidence": "x"}, "LATENCY_UNOBSERVED_BUT_VALUED"),
    ({"status": "UNOBSERVED", "seconds": 0.0, "evidence": "x"}, "LATENCY_UNOBSERVED_BUT_VALUED"),
    ({"status": "OBSERVED", "seconds": None, "evidence": "x"}, "INVALID:provider_delivery_latency.seconds"),
    ({"status": "UNOBSERVED", "evidence": "x"}, "MISSING:provider_delivery_latency.seconds"),
    (None, "MISSING:provider_delivery_latency"),
])
def test_latency_contract_defects(lat, defect):
    c = contract(provider_delivery_latency=lat)
    if lat is None:
        del c["provider_delivery_latency"]
    assert defect in ta.validate_contract(c)
    o = ms("2019-01-01 00:00:00")
    cb = cib(c, {"timestamp_ms": o, "close_time_ms": o + H4 - 1})
    ob = ta.operational_delivery_bound(c, cb)
    assert cb.status == ob.status == "REFUSED"
    assert not ta.gate_e5b(c, cb, ob).is_open


def test_declared_latency_is_added_and_opens_e5b_positive_control():
    o = ms("2019-01-01 00:00:00")
    c = contract(provider_delivery_latency=declared_latency(2.5))
    cb = cib(c, {"timestamp_ms": o, "close_time_ms": o + H4 - 1})
    ob = ta.operational_delivery_bound(c, cb)
    assert ob.status == "RESOLVED" and ob.utc_ms == cb.utc_ms + 2500
    g = ta.gate_e5b(c, cb, ob)
    assert g.is_open
    assert "NECESSARY_CONDITIONS_ONLY_NOT_A_LIVE_VIABILITY_GRANT" in g.reasons


# --------------------------------------------------- offline never live
def test_offline_causal_availability_never_opens_the_live_gate():
    o = ms("2019-01-01 00:00:00")
    for c in (contract(), contract(provider_delivery_latency=declared_latency())):
        cb = cib(c, {"timestamp_ms": o, "close_time_ms": o + H4 - 1})
        assert ta.gate_e5a(c, cb).is_open
        # causal bound handed over in place of an operational one
        g = ta.gate_e5b(c, cb, cb)
        assert not g.is_open and g.reasons == ("OFFLINE_CAUSAL_BOUND_PRESENTED_AS_OPERATIONAL",)
        assert ta.gate_e5b(c, cb, None).reasons == ("OPERATIONAL_DELIVERY_BOUND_ABSENT",)
        # a causal bound cannot seed an operational bound as the wrong kind
        assert ta.operational_delivery_bound(
            c, ta.Bound("operational_delivery_bound", "RESOLVED", o, (), c["contract_id"], SHA)
        ).reasons == ("BOUND_KIND_MISMATCH",)
    # forged operational bound: right kind, earlier than the causal bound
    c = contract(provider_delivery_latency=declared_latency())
    cb = cib(c, {"timestamp_ms": o, "close_time_ms": o + H4 - 1})
    forged = ta.Bound("operational_delivery_bound", "RESOLVED", cb.utc_ms - 1, (),
                      c["contract_id"], SHA)
    assert ta.gate_e5b(c, cb, forged).reasons == ("OPERATIONAL_BOUND_PRECEDES_CAUSAL_BOUND",)
    # operational bound from another contract
    other = contract(contract_id="fixture.other", provider_delivery_latency=declared_latency())
    ob_other = ta.operational_delivery_bound(other, cib(other, {"timestamp_ms": o, "close_time_ms": o + H4 - 1}))
    assert ta.gate_e5b(c, cb, ob_other).reasons == ("BOUND_FROM_OTHER_CONTRACT",)


def test_dataset_level_unobserved_latency_opens_e5a_only():
    c = contract()
    o = ms("2019-01-01 00:00:00")
    rows = [{"timestamp_ms": o + i * H4, "close_time_ms": o + i * H4 + H4 - 1,
             "next_timestamp_ms": o + (i + 1) * H4} for i in range(10)]
    ev = ta.evaluate_rows(c, rows, observed_sha256=SHA)
    assert ev["E5a"]["status"] == "OPEN" and ev["E5b"]["status"] == "CLOSED"
    assert ev["operational_delivery_bound_status_counts"] == {"UNOBSERVED": 10}
    assert ta.evaluate_rows(c, [], observed_sha256=SHA)["E5a"]["status"] == "CLOSED"


# -------------------------------------------------- binding / provenance
def test_transplanted_dataset_refused():
    o = ms("2019-01-01 00:00:00")
    c = contract(provider_delivery_latency=declared_latency())
    row = {"timestamp_ms": o, "close_time_ms": o + H4 - 1}
    b = cib(c, row, sha=OTHER_SHA)
    assert (b.status, b.reasons) == ("REFUSED", ("DATASET_TRANSPLANTED",))
    ob = ta.operational_delivery_bound(c, b)
    assert not ta.gate_e5a(c, b).is_open and not ta.gate_e5b(c, b, ob).is_open
    assert cib(c, row, sha=None).reasons == ("DATASET_DIGEST_NOT_PRESENTED",)
    ev = ta.evaluate_rows(c, [row], observed_sha256=OTHER_SHA)
    assert ev["E5a"]["status"] == ev["E5b"]["status"] == "CLOSED"


def test_eurusd_without_provenance_closes_e5a():
    c = contract(contract_id="fixture.eurusd", dataset_id="predictor.legacy.eurusd_1h.phase1_test.v1",
                 timestamp_semantics="UNDECLARED", information_complete_not_before="UNDECLARED",
                 nominal_bar_seconds=None,
                 provenance={"status": "UNDECLARED", "basis": "provider not recorded"})
    assert ta.validate_contract(c) == ()
    b = cib(c, {"timestamp_ms": ms("2019-01-01 00:00:00"), "close_time_ms": ms("2019-01-01 00:59:59.999")})
    assert b.status == "UNRESOLVED"
    assert b.reasons == ("PROVENANCE_UNDECLARED", "TIMESTAMP_SEMANTICS_UNDECLARED")
    g = ta.gate_e5a(c, b)
    assert not g.is_open and "PROVENANCE_UNDECLARED" in g.reasons
    # a well-formed-looking BAR_OPEN claim without provenance still refuses
    c2 = contract(provenance={"status": "UNDECLARED", "basis": "provider not recorded"})
    b2 = cib(c2, {"timestamp_ms": 0, "close_time_ms": H4 - 1})
    assert b2.reasons == ("PROVENANCE_UNDECLARED",) and not ta.gate_e5a(c2, b2).is_open


def test_every_emitted_reason_is_a_declared_code():
    # runs last in file order; EMITTED filled by the fixtures above
    assert EMITTED and EMITTED <= set(ta.REASON_CODES)


# --------------------------------------------------------- materializer
DATA_PRESENT = all((mat.FD_ROOT if s.root_id == "financial-data" else mat.DEFAULT_PREDICTOR_ROOT)
                   .joinpath(s.relative_path).is_file() for s in mat.SOURCES)
needs_data = pytest.mark.skipif(not DATA_PRESENT, reason="local data lake not present")


def _mirror(tmp_path, corrupt: str):
    """Symlink every source into tmp roots; the one named `corrupt` is a
    COPY with one byte changed. The real file is never written."""
    roots = {"financial-data": tmp_path / "financial-data", "predictor": tmp_path / "predictor"}
    real = {"financial-data": mat.FD_ROOT, "predictor": mat.DEFAULT_PREDICTOR_ROOT}
    for s in mat.SOURCES:
        dst = roots[s.root_id] / s.relative_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        src = real[s.root_id] / s.relative_path
        if s.name == corrupt:
            data = bytearray(src.read_bytes())
            data[len(data) // 2] ^= 0x01
            dst.write_bytes(bytes(data))
        else:
            os.symlink(src, dst)
    return roots


@needs_data
@pytest.mark.parametrize("corrupt", ["model_ready_csv", "candidate_source_parquet",
                                     "declared_upstream_parquet"])
def test_materializer_refuses_on_digest_mismatch(tmp_path, corrupt):
    before = {s.name: hashlib.sha256(
        (mat.FD_ROOT if s.root_id == "financial-data" else mat.DEFAULT_PREDICTOR_ROOT)
        .joinpath(s.relative_path).read_bytes()).hexdigest()
        for s in mat.SOURCES if s.expected_sha256}
    roots = _mirror(tmp_path, corrupt)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(mat.DigestMismatch):
        mat.main(["--financial-data-root", str(roots["financial-data"]),
                  "--predictor-root", str(roots["predictor"]), "--out-dir", str(out)])
    assert list(out.iterdir()) == []
    for s in mat.SOURCES:
        if s.expected_sha256:
            assert before[s.name] == s.expected_sha256  # real files untouched


@needs_data
def test_materializer_opens_each_file_once_and_parses_the_hashed_bytes(monkeypatch):
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    real = {s.name: ((mat.FD_ROOT if s.root_id == "financial-data" else mat.DEFAULT_PREDICTOR_ROOT)
                     / s.relative_path).resolve() for s in mat.SOURCES}
    watched = {str(p): n for n, p in real.items()}
    opens: dict[str, int] = {}
    orig_open = builtins.open

    def counting_open(file, *a, **k):
        try:
            key = str(Path(file).resolve())
        except TypeError:
            key = None
        if key in watched:
            opens[watched[key]] = opens.get(watched[key], 0) + 1
        return orig_open(file, *a, **k)

    parsed: dict[str, list[str]] = {"csv": [], "parquet": []}
    orig_read_csv, orig_read_table = pd.read_csv, pq.read_table

    def spy_read_csv(buf, *a, **k):
        assert isinstance(buf, io.BytesIO), "CSV must be parsed from the hashed buffer"
        parsed["csv"].append(hashlib.sha256(buf.getvalue()).hexdigest())
        return orig_read_csv(buf, *a, **k)

    def spy_read_table(src, *a, **k):
        assert isinstance(src, pa.BufferReader), "parquet must be parsed from the hashed buffer"
        src.seek(0)
        parsed["parquet"].append(hashlib.sha256(src.read()).hexdigest())
        src.seek(0)
        return orig_read_table(src, *a, **k)

    monkeypatch.setattr(builtins, "open", counting_open)
    monkeypatch.setattr(mat.pd, "read_csv", spy_read_csv)
    monkeypatch.setattr(mat.pq, "read_table", spy_read_table)
    schema, doc = mat.materialize()

    assert opens == {s.name: 1 for s in mat.SOURCES}
    b = doc["bound_files"]
    assert parsed["csv"] == [b["model_ready_csv"]["sha256"]]
    assert parsed["parquet"] == [b["candidate_source_parquet"]["sha256"],
                                 b["declared_upstream_parquet"]["sha256"]]
    for s in mat.SOURCES:
        if s.expected_sha256:
            assert b[s.name]["sha256"] == s.expected_sha256


# --------------------------------------------------- published artifacts
CONTRACT_PATH = ROOT / "features/census/ETH_H4_TEMPORAL_CONTRACT.v1.json"
SCHEMA_PATH = ROOT / "features/census/TEMPORAL_AVAILABILITY_SCHEMA.v1.json"
needs_artifacts = pytest.mark.skipif(not CONTRACT_PATH.is_file(), reason="artifact not materialized")


@needs_artifacts
def test_published_artifacts_self_digest_schema_and_no_home_paths():
    for p in (CONTRACT_PATH, SCHEMA_PATH):
        text = p.read_text(encoding="utf-8")
        assert "/home/" not in text
        d = json.loads(text)
        assert d["self_digest"]["value"] == mat.self_digest(d)["value"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert {k: v for k, v in schema.items() if k != "self_digest"} == ta.schema_document()
    doc = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert doc["schema"]["self_digest"] == schema["self_digest"]["value"]
    assert ta.validate_contract(doc["contract"]) == ()


@needs_artifacts
def test_published_contract_pins_measured_facts():
    doc = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    c, m, s = doc["contract"], doc["measurements"], doc["source_bar_structure"]
    assert c["timestamp_semantics"] == "BAR_OPEN" and c["nominal_bar_seconds"] == 14400
    assert c["information_complete_not_before"] == "PER_BAR_CLOSE_TIME"
    assert c["provider_delivery_latency"] == {**c["provider_delivery_latency"], "status": "UNOBSERVED", "seconds": None}
    assert m["csv_rows"] == m["rows_matched"] == 18085
    assert set(m["ohlcv_max_abs_error"].values()) == {0.0}
    assert s["truncated_bars_total"] == 21 and s["truncated_bars_in_model_ready_csv"] == 20
    assert s["gaps_greater_than_nominal_total"] == 8
    assert doc["gates"]["E5a"]["status"] == "OPEN" and doc["gates"]["E5b"]["status"] == "CLOSED"
    ids = {u["dataset_id"]: u for u in doc["undeclared_datasets"]}
    assert "predictor.legacy.eurusd_1h.phase1_test.v1" in ids
    for u in ids.values():
        assert u["contract"]["timestamp_semantics"] == "UNDECLARED"
        assert u["E5a"]["status"] == u["E5b"]["status"] == "CLOSED"
