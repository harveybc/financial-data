"""C114 battery: successor temporal contract v3 and mask.

Real files are only READ. Mutants use temporary copies or in-memory tables.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ta = _load("temporal_availability", "_scripts/temporal_availability.py")
tq = _load("temporal_quality", "_scripts/temporal_quality.py")
m = _load("materialize_eth_h4_successor_temporal_quality",
          "_scripts/materialize_eth_h4_successor_temporal_quality.py")

SUCC_ROOT = m.DEFAULT_SUCCESSORS_ROOT / "eth_h4_stage22_rerun_v1"
needs_data = pytest.mark.skipif(not (SUCC_ROOT / m.SOURCES[0].relative_path).is_file(),
                                reason="successor root not present")
PRESERVED = {
    "features/census/ETH_H4_TEMPORAL_CONTRACT.v1.json": "6e3a0c8d67dd2ec64dcad8bd7bb7ca0154dd514b43e9e2990de83578cc794254",
    "features/census/ETH_H4_TEMPORAL_CONTRACT.v2.json": "43b9f2b6650205ec30c4cd000b174ad5db9b321c6efcd356aaf1398904f4d6f1",
    "features/census/ETH_H4_SAMPLE_ELIGIBILITY_MASK.v1.parquet": "b5c2e3b5811c11c4bdf32c7736037ecc68bff50f0edf59e40a0bfdc185939e85",
    "features/census/FEATURE_DAG.v4.json": "4fa4d1341e51fc4ff0576834fb0455297f177ec319ecd05b3429fa74c8249204",
    "features/census/PRODUCER_BINDING_MANIFEST.v2.json": "7d2b7d38c2e3be3e99f3aa06606cbc36825cd653974f8d4068f215de618f34bc",
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def real():
    if not (SUCC_ROOT / m.SOURCES[0].relative_path).is_file():
        pytest.skip("successor root not present")
    return m.materialize()


@pytest.fixture(scope="module")
def tables():
    if not (SUCC_ROOT / m.SOURCES[0].relative_path).is_file():
        pytest.skip("successor root not present")
    succ = pq.read_table(SUCC_ROOT / m.SOURCES[0].relative_path, columns=["DATE_TIME", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"])
    raw = pq.read_table(SUCC_ROOT / m.SOURCES[1].relative_path)
    return succ, raw


def _contract():
    return m.availability_contract(m.SUCCESSOR_DATASET_ID, m.SUCCESSOR_DATASET_SHA256,
                                   {"timestamp_semantics": "BAR_OPEN",
                                    "information_complete_not_before": "PER_BAR_CLOSE_TIME",
                                    "nominal_bar_seconds": 14400,
                                    "bar_close_time_convention": "INCLUSIVE_LAST_MILLISECOND"})


# ------------------------------------------------------------ happy path
@needs_data
def test_real_counts_geometry_equal_identity_differs(real):
    doc, mask_bytes = real
    bs, s = doc["bar_structure"], doc["sample_summary"]
    assert doc["dataset"]["rows"] == s["total"] == 18085
    assert bs["truncated_bars_inside_dataset"] == 20
    assert bs["truncated_bars_outside_dataset_count"] == 1
    assert bs["truncated_bars_outside_dataset"][0]["position"] == "BEFORE_FIRST_SUCCESSOR_ROW"
    assert bs["truncated_bars_in_raw_input_total"] == 21
    assert bs["gaps_inside_dataset"] == 8
    assert s["eligible"] + s["ineligible"] == 18085
    c = doc["comparison_with_v2"]
    assert c["kind"] == "GEOMETRY_EQUALITY_NOT_IDENTITY_EQUALITY"
    for k in ("truncated_open_times_equal", "gap_positions_equal", "per_row_eligibility_vector_equal",
              "per_row_reasons_equal", "origin_boundaries_equal", "sample_summary_equal"):
        assert c["geometry"][k] is True, k
    assert c["identity_equal"] is False
    assert c["identity"]["this_contract"]["dataset_id"] != c["identity"]["v2"]["dataset_id"]
    assert c["identity"]["this_contract"]["dataset_sha256"] != c["identity"]["v2"]["dataset_sha256"]


@needs_data
def test_real_identity_bindings_mask_and_digest(real):
    doc, mask_bytes = real
    ac = doc["availability_contract"]
    assert ac["dataset_id"] == doc["dataset"]["dataset_id"] == m.SUCCESSOR_DATASET_ID
    assert ac["dataset_sha256"] == m.SUCCESSOR_DATASET_SHA256
    assert ac["contract_id"] == doc["contract_id"] == m.CONTRACT_ID
    assert m.HISTORICAL_DATASET_ID not in json.dumps(doc["identity"])
    assert m.identity_defects(doc) == []
    assert doc["availability_parameter_provenance"]["carried_from"]["role"] == "PROVENANCE_OF_PARAMETERS_NOT_IDENTITY"
    b = doc["bindings"]
    assert b["feature_dag_v4"]["dag_sha256_verified"] and b["binding_manifest_v2"]["manifest_sha256_verified"]
    assert b["feature_dag_v4"]["binding_manifest_sha256"] == b["binding_manifest_v2"]["manifest_sha256"]
    ma = doc["mask_artifact"]
    assert ma["dataset_id"] == m.SUCCESSOR_DATASET_ID and ma["dataset_sha256"] == m.SUCCESSOR_DATASET_SHA256
    assert hashlib.sha256(mask_bytes).hexdigest() == ma["sha256"]
    t = pq.read_table(pa.BufferReader(mask_bytes))
    assert t.num_rows == ma["rows"] == 18085 and t.column_names == ma["columns"]
    assert m.content_digest(t) == ma["content_sha256"]
    assert t.schema.metadata[b"dataset_id"].decode() == m.SUCCESSOR_DATASET_ID
    assert doc["self_digest"]["value"] == m.self_digest(doc)["value"]
    assert "/home/" not in json.dumps(doc)
    # rolling origins re-derived: roles in the mask match the origin reports
    d = t.to_pydict()
    for o in doc["rolling_origins"]["origins"]:
        roles = d[f"origin_{o['origin']}_role"]
        assert roles.count("TEST") == o["role_counts"]["TEST"]


@needs_data
def test_self_digest_canonicalization_equals_v2():
    v2 = json.loads((ROOT / "features/census/ETH_H4_TEMPORAL_CONTRACT.v2.json").read_text())
    assert m.self_digest(v2) == v2["self_digest"]


# --------------------------------------------------------------- refusals
@needs_data
def test_wrong_successor_sha_refuses(monkeypatch, tmp_path):
    bad = list(m.SOURCES)
    bad[0] = m.Source(bad[0].name, bad[0].root_id, bad[0].relative_path, "0" * 64)
    monkeypatch.setattr(m, "SOURCES", tuple(bad))
    with pytest.raises(m.DigestMismatch):
        m.main(["--out-dir", str(tmp_path)])
    assert list(tmp_path.iterdir()) == []


@needs_data
def test_historical_dataset_id_transplanted_refuses(real):
    with pytest.raises(m.Refusal):
        m.materialize(dataset_id=m.HISTORICAL_DATASET_ID)
    doc = json.loads(json.dumps(real[0]))
    doc["availability_contract"]["dataset_id"] = m.HISTORICAL_DATASET_ID
    assert "HISTORICAL_DATASET_ID_TRANSPLANTED:availability_contract" in m.identity_defects(doc)
    doc = json.loads(json.dumps(real[0]))
    doc["dataset"]["dataset_sha256"] = m.HISTORICAL_DATASET_SHA256
    assert any(x.startswith("HISTORICAL_DATASET_SHA256_TRANSPLANTED") for x in m.identity_defects(doc))
    doc = json.loads(json.dumps(real[0]))
    doc["contract_id"] = "financial_data.eth_h4_temporal_contract.v2"
    assert "HISTORICAL_CONTRACT_ID_AS_IDENTITY" in m.identity_defects(doc)


def test_contract_bound_to_historical_bytes_refuses_on_successor_bytes():
    c = _contract()
    c["dataset_sha256"] = m.HISTORICAL_DATASET_SHA256
    opens = [1546300800000 + i * 14_400_000 for i in range(3)]
    closes = [o + 14_400_000 - 1 for o in opens]
    with pytest.raises(tq.StructuralRefusal) as e:
        tq.evaluate_bars(c, opens, closes, observed_sha256=m.SUCCESSOR_DATASET_SHA256)
    assert "AVAILABILITY_REFUSED" in e.value.codes


def _mirror(tmp_path, mutate_raw=None):
    """tmp successors root + tmp financial-data root; unmutated files are symlinks."""
    sroot = tmp_path / "succ"
    (sroot / "eth_h4_stage22_rerun_v1" / "successor").mkdir(parents=True)
    (sroot / "eth_h4_stage22_rerun_v1" / "inputs").mkdir()
    fd = tmp_path / "fd"
    (fd / "features/census").mkdir(parents=True)
    for s in m.SOURCES:
        base = SUCC_ROOT if s.root_id == m.SUCCESSOR_ROOT_ID else ROOT
        dst_base = sroot / "eth_h4_stage22_rerun_v1" if s.root_id == m.SUCCESSOR_ROOT_ID else fd
        src, dst = base / s.relative_path, dst_base / s.relative_path
        if s.name == "raw_ohlcv_parquet" and mutate_raw is not None:
            pq.write_table(mutate_raw(pq.read_table(src)), dst)
        else:
            os.symlink(src, dst)
    return fd, sroot


def _set(table, name, i, value, typ):
    arr = table.column(name).to_pylist()
    arr[i] = value
    return table.set_column(table.schema.get_field_index(name), name, pa.array(arr, type=typ))


@needs_data
def test_raw_close_time_mismatch_on_tmp_copy_refuses(tmp_path):
    ts = pa.timestamp("ms", tz="UTC")

    def mutate(t):
        ct = t.column("close_time").cast(pa.int64()).to_pylist()
        return _set(t, "close_time", 5000, pa.scalar(ct[5000] - 60_000, pa.int64()).cast(ts).as_py(), ts)

    fd, sroot = _mirror(tmp_path, mutate)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(m.DigestMismatch):
        m.main(["--financial-data-root", str(fd), "--successors-root", str(sroot), "--out-dir", str(out)])
    assert list(out.iterdir()) == []


@needs_data
def test_raw_ohlcv_mismatch_on_tmp_copy_refuses(tmp_path):
    fd, sroot = _mirror(tmp_path, lambda t: _set(t, "close", 5000, t.column("close")[5000].as_py() + 0.01, pa.float64()))
    with pytest.raises(m.DigestMismatch):
        m.materialize(fd, sroot)


@needs_data
def test_join_refuses_ohlcv_difference(tables):
    succ, raw = tables
    for col in ("open", "high", "low", "close", "volume"):
        bad = _set(raw, col, 3000, raw.column(col)[3000].as_py() * 1.0000001, pa.float64())
        with pytest.raises(m.Refusal, match="differs"):
            m.join_successor_to_raw(succ, bad)


@needs_data
def test_join_refuses_successor_row_without_raw_bar(tables):
    succ, raw = tables
    keep = np.ones(raw.num_rows, dtype=bool)
    keep[4000] = False
    with pytest.raises(m.Refusal, match="no raw bar"):
        m.join_successor_to_raw(succ, raw.filter(pa.array(keep)))


@needs_data
def test_raw_close_time_changes_propagate_never_masked(tables):
    succ, raw = tables
    ts = pa.timestamp("ms", tz="UTC")
    j = m.join_successor_to_raw(succ, raw)
    i = int(j["idx"][5000])
    ct = raw.column("close_time").cast(pa.int64()).to_pylist()
    longer = _set(raw, "close_time", i, pa.scalar(ct[i] + 1, pa.int64()).cast(ts).as_py(), ts)
    jl = m.join_successor_to_raw(succ, longer)
    with pytest.raises(tq.StructuralRefusal) as e:
        tq.evaluate_bars(_contract(), jl["open_ms"].tolist(), jl["close_ms"].tolist(),
                         observed_sha256=m.SUCCESSOR_DATASET_SHA256)
    assert "CLOSE_TIME_EXCEEDS_NOMINAL_BAR" in e.value.codes
    shorter = _set(raw, "close_time", i, pa.scalar(ct[i] - 1, pa.int64()).cast(ts).as_py(), ts)
    js = m.join_successor_to_raw(succ, shorter)
    bars = tq.evaluate_bars(_contract(), js["open_ms"].tolist(), js["close_ms"].tolist(),
                            observed_sha256=m.SUCCESSOR_DATASET_SHA256)
    assert int(bars.truncated.sum()) == 21 and bool(bars.truncated[5000])


@needs_data
def test_gap_is_never_filled(tables):
    succ, raw = tables
    sub = succ.slice(6000, 800)
    keep = np.ones(sub.num_rows, dtype=bool)
    keep[400] = False
    holed = sub.filter(pa.array(keep))
    j = m.join_successor_to_raw(holed, raw)
    bars = tq.evaluate_bars(_contract(), j["open_ms"].tolist(), j["close_ms"].tolist(),
                            observed_sha256=m.SUCCESSOR_DATASET_SHA256)
    assert bars.n == sub.num_rows - 1
    removed = sub.column("DATE_TIME").cast(pa.int64())[400].as_py()
    assert removed not in set(bars.open_ms.tolist())
    assert tq.STEP_STATES[bars.next_step_state[399]] == "GAP" and bars.missing_nominal_bars_after[399] == 1
    p = tq.EligibilityParams(model_lookback_bars=24, max_operator_warmup_bars=24, n_rolling_origins=1, test_block_bars=10)
    mask = tq.sample_eligibility(bars, p)
    assert "TARGET_NOMINAL_BAR_ABSENT" in mask.reasons(399)
    assert not mask.eligible[399]
    # the next observed row is not the target: its own sample reports the gap in its lookback
    assert "LOOKBACK_CROSSES_GAP" in mask.reasons(400)


# ------------------------------------------------------------- write-once
@needs_data
def test_outputs_refuse_overwrite(real, tmp_path):
    doc, mask_bytes = real
    m.publish(doc, mask_bytes, tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert set(before) == {m.CONTRACT_NAME, m.MASK_NAME}
    with pytest.raises(m.Refusal, match="write-once"):
        m.publish(doc, mask_bytes, tmp_path)
    (tmp_path / m.CONTRACT_NAME).unlink()
    with pytest.raises(m.Refusal, match="write-once"):
        m.publish(doc, mask_bytes, tmp_path)
    assert (tmp_path / m.MASK_NAME).read_bytes() == before[m.MASK_NAME]
    written = json.loads(before[m.CONTRACT_NAME])
    assert written["self_digest"]["value"] == m.self_digest(written)["value"]


def test_home_path_refused(real, tmp_path, monkeypatch):
    doc, mask_bytes = real
    bad = json.loads(json.dumps(doc))
    bad["note"] = "/home/someone/x"
    with pytest.raises(m.Refusal, match="home"):
        m.publish(bad, mask_bytes, tmp_path)


# ---------------------------------------------------- preserved artifacts
def test_preserved_contracts_and_mask_byte_unchanged(real):
    for rel, sha in PRESERVED.items():
        assert _sha(ROOT / rel) == sha, rel
