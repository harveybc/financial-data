"""C116 battery: characterization on a small temporary fixture."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ch = _load("characterize_eth_h4_successor", "_scripts/characterize_eth_h4_successor.py")
DS = "fixture.successor.v1"
POLICY = "ROW_DROPPED_IF_NON_FINITE"


@pytest.fixture
def fx(tmp_path):
    rng = np.random.default_rng(7)
    n = 200
    x = rng.normal(size=n)
    x[[3, 50]] = np.nan
    x[77] = np.inf
    table = pa.table({
        "DATE_TIME": pa.array(np.arange(n, dtype=np.int64) * 14_400_000, type=pa.timestamp("ms", tz="UTC")),
        "x": pa.array(x, type=pa.float64()),
        "f32": pa.array(rng.normal(size=n).astype(np.float32), type=pa.float32()),
        "date_int": pa.array(20240101 + np.arange(n, dtype=np.int64), type=pa.int64()),
        "plain_int_unknown": pa.array(np.arange(n, dtype=np.int64), type=pa.int64()),
        "u": pa.array(rng.normal(size=n), type=pa.float64()),
        "mp": pa.array(rng.normal(size=n), type=pa.float64()),
        "label": pa.array([str(i % 3) for i in range(n)], type=pa.string()),
        "ts": pa.array(np.arange(n, dtype=np.int64), type=pa.timestamp("ms", tz="UTC")),
    })
    pth = tmp_path / "ds.parquet"
    pq.write_table(table, pth)
    sha = hashlib.sha256(pth.read_bytes()).hexdigest()
    sem = {"x": ("measure", POLICY), "f32": ("measure", POLICY), "date_int": ("calendar_date", POLICY),
           "plain_int_unknown": ("UNKNOWN", POLICY), "u": ("UNKNOWN", POLICY), "mp": ("measure", "UNKNOWN"),
           "label": ("category", POLICY), "ts": ("measure", POLICY)}
    rows = [{"column": c, "dataset_id": DS, "dataset_sha256": sha,
             "variable_id": hashlib.sha256((DS + "\0" + c).encode()).hexdigest(),
             "physical_type": str(table.schema.field(c).type), "semantic_type": s, "missing_policy": mp}
            for c, (s, mp) in sem.items()]
    census = {"dataset_id": DS, "dataset_sha256": sha, "rows": rows}
    census["self_digest"] = ch.self_digest(census)
    cpath = tmp_path / "census.json"
    cpath.write_text(json.dumps(census))
    out = tmp_path / "succ" / "fixture_characterization_v1"
    (tmp_path / "succ").mkdir()
    protected = tmp_path / "succ" / "fixture_rerun"
    protected.mkdir()
    kw = dict(dataset_path=pth, dataset_sha256=sha, dataset_id=DS, census_path=cpath, out_root=out,
              summary_path=tmp_path / "summary.json", root_logical_id="fixture/characterization",
              protected_roots=(protected,))
    yield kw, x
    for p in [out, out / "terminals"]:
        if p.exists():
            os.chmod(p, 0o755)


def _terminal(kw, col):
    return json.loads((kw["out_root"] / "terminals" / f"{col}.json").read_text())


def test_run_writes_ledger_terminals_summary_and_states(fx):
    kw, x = fx
    s = ch.run(**kw)
    ledger = json.loads((kw["out_root"] / "PRE_LEDGER.json").read_text())
    assert [t["column"] for t in ledger["planned_terminals"]] == [t["column"] for t in s["terminals"]]
    assert s["pre_ledger"]["sha256"] == hashlib.sha256((kw["out_root"] / "PRE_LEDGER.json").read_bytes()).hexdigest()
    exp = {"x": ("NUMERIC_MEASURABLE", "INDEPENDENTLY_RECOMPUTED"),
           "f32": ("NUMERIC_MEASURABLE", "INDEPENDENTLY_RECOMPUTED"),
           "date_int": ("NON_NUMERIC", "PHYSICALLY_TYPED"),
           "plain_int_unknown": ("SEMANTIC_TYPE_UNRESOLVED", "SEMANTICALLY_UNRESOLVED"),
           "u": ("SEMANTIC_TYPE_UNRESOLVED", "SEMANTICALLY_UNRESOLVED"),
           "mp": ("MISSING_POLICY_UNRESOLVED", "PHYSICALLY_TYPED"),
           "label": ("NON_NUMERIC", "PHYSICALLY_TYPED"),
           "ts": ("NON_NUMERIC", "PHYSICALLY_TYPED")}
    for c, (state, layer) in exp.items():
        t = _terminal(kw, c)
        assert tuple(sorted(t)) == tuple(sorted(ch.TERMINAL_KEYS)), c
        assert (t["semantic_state"], t["layer"]) == (state, layer), c
        assert t["dataset_id"] == DS and t["source_sha256"] == kw["dataset_sha256"] == t["dataset_sha256"]
        if state != "NUMERIC_MEASURABLE":
            assert t["descriptors"]["mean"] is None
    assert s["counts_by_semantic_state"]["NUMERIC_MEASURABLE"] == 2
    assert s["self_digest"]["value"] == ch.self_digest(s)["value"]


def test_integer_date_never_numeric_measurable(fx):
    kw, _ = fx
    ch.run(**kw)
    t = _terminal(kw, "date_int")
    assert t["semantic_state"] != "NUMERIC_MEASURABLE" and t["layer"] != "INDEPENDENTLY_RECOMPUTED"
    assert ch.semantic_state(pa.int64(), {"semantic_type": "epoch_milliseconds", "missing_policy": POLICY}) == "NON_NUMERIC"
    assert ch.semantic_state(pa.int64(), {"semantic_type": "UNKNOWN", "missing_policy": POLICY}) == "SEMANTIC_TYPE_UNRESOLVED"


def test_descriptors_equal_numpy_recomputation(fx):
    kw, x = fx
    ch.run(**kw)
    t = _terminal(kw, "x")
    fin = x[np.isfinite(x)]
    d = t["descriptors"]
    assert d["count"] == 200 and d["missing_count"] == 2 and d["infinite_count"] == 1 and d["finite_count"] == 197
    assert t["observations"] == 197 and t["missing_fraction"] == 2 / 200
    assert d["mean"] == float(np.mean(fin)) and d["std"] == float(np.std(fin))
    assert d["min"] == float(fin.min()) and d["max"] == float(fin.max())
    for p in ch.QUANTILES:
        assert d["quantiles"][f"q{p:g}"] == float(np.quantile(fin, p))


def test_write_once_refusal(fx):
    kw, _ = fx
    ch.run(**kw)
    before = {p: p.read_bytes() for p in kw["out_root"].rglob("*") if p.is_file()}
    with pytest.raises(ch.Refusal, match="write-once"):
        ch.run(**kw)
    assert {p: p.read_bytes() for p in kw["out_root"].rglob("*") if p.is_file()} == before
    kw2 = dict(kw, out_root=kw["out_root"].parent / "other_root")
    with pytest.raises(ch.Refusal, match="write-once"):
        ch.run(**kw2)  # summary already exists
    assert not kw2["out_root"].exists()


def test_sha_mismatch_refuses_before_anything_is_created(fx):
    kw, _ = fx
    with pytest.raises(ch.DigestMismatch):
        ch.run(**dict(kw, dataset_sha256="0" * 64))
    assert not kw["out_root"].exists() and not kw["summary_path"].exists()


def test_protected_root_and_tampered_census_refuse(fx):
    kw, _ = fx
    with pytest.raises(ch.Refusal, match="protected"):
        ch.run(**dict(kw, out_root=kw["protected_roots"][0] / "inside"))
    census = json.loads(kw["census_path"].read_text())
    census["rows"][0]["semantic_type"] = "UNKNOWN"
    kw["census_path"].write_text(json.dumps(census))
    with pytest.raises(ch.Refusal, match="self digest"):
        ch.run(**kw)
    assert not kw["out_root"].exists()


def test_duplicate_census_column_refuses(fx):
    kw, _ = fx
    census = json.loads(kw["census_path"].read_text())
    census["rows"].append(dict(census["rows"][0]))
    census["self_digest"] = ch.self_digest(census)
    kw["census_path"].write_text(json.dumps(census))
    with pytest.raises(ch.Refusal, match="duplicate"):
        ch.run(**kw)
