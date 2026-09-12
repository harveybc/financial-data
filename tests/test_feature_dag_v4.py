"""C93, C96-C97 (order 2026-09-12): the v3 disposition, the successor
binding manifest v2 and FEATURE_DAG.v4."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prospective_rerun_fixture as fx  # noqa: E402

ROOT = fx.ROOT
CENSUS = ROOT / "features/census"
d4 = fx.load("derive_feature_dag_v4_under_test",
             ROOT / "_scripts/derive_feature_dag_v4.py")
d3 = d4.d3

#: digests of the protected census artifacts as committed at b24b22719
PINNED = {
    "FEATURE_DAG.v1.json":
        "4991e36862d42b8af5fa145e8a818bb4efe102b6f1c46f85aecce0182ab09a5b",
    "FEATURE_DAG.v2.json":
        "8fbe787a8b8279b5b1736665de447b4ddbfbdbe5a4c6c5d11e5c043236e9cb65",
    "FEATURE_DAG.v3.json":
        "cf2da14190236e3e267d9671e053b02bfa30dc5562aa78c179854e31e1b5e19a",
    "PRODUCER_BINDING_MANIFEST.v1.json":
        "5f24ff8545f96cdedc10bd9ab7acbf308ae3f16b0898cbf96657851beb6062d6",
    "ETH_H4_TEMPORAL_CONTRACT.v1.json":
        "6e3a0c8d67dd2ec64dcad8bd7bb7ca0154dd514b43e9e2990de83578cc794254",
}


def _digests():
    return {f: hashlib.sha256((CENSUS / f).read_bytes()).hexdigest()
            for f in PINNED}


@pytest.fixture(autouse=True)
def _cpu(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")


@pytest.fixture(scope="module")
def good_root(tmp_path_factory):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    w = fx.build_world(tmp_path_factory.mktemp("good"))
    fx.run_world(w)
    return w


# ------------------------------------------------------------ bindings
FULL = {"dataset_id": "succ.v1", "dataset_sha256": "a" * 64,
        "input_sha256": "b" * 64, "repository": "financial-data",
        "commit": "c" * 40, "tree": "d" * 40, "file": "x.py",
        "file_sha256": "e" * 64, "symbol": "f", "config_sha256": "0" * 64,
        "output_column": "atr_14"}


def test_a_full_binding_is_complete():
    assert d4.binding_complete(FULL) == (True, [])


@pytest.mark.parametrize("field", d4.BINDING_FIELDS)
def test_every_binding_field_is_required(field):
    for bad in (None, "", "  "):
        b = dict(FULL, **{field: bad})
        ok, codes = d4.binding_complete(b)
        assert not ok and codes == [f"FIELD_MISSING:{field}"]
    b = dict(FULL)
    del b[field]
    assert d4.binding_complete(b)[0] is False


@pytest.mark.parametrize("field,bad", [("commit", "abc"), ("tree", "z" * 40),
                                       ("dataset_sha256", "a" * 63),
                                       ("input_sha256", "B" * 64)])
def test_a_malformed_digest_is_not_a_binding(field, bad):
    ok, codes = d4.binding_complete(dict(FULL, **{field: bad}))
    assert not ok and codes == [f"FIELD_MALFORMED:{field}"]


# ------------------------------------------------------ classification
@pytest.mark.parametrize("binding,static,probe,expected", [
    (True, d3.STATIC_CAUSAL, "PASS", d3.CAUSAL),
    (False, d3.STATIC_CAUSAL, "PASS", d3.UNBOUND),
    (True, d3.STATIC_CAUSAL, None, d3.UNRESOLVED),
    (True, d3.STATIC_CAUSAL, "VACUOUS", d3.UNRESOLVED),
    (True, d3.STATIC_CAUSAL,
     "NOT_DEMONSTRATED_INSENSITIVE_TO_PERTURBATION", d3.UNRESOLVED),
    (True, d3.UNRESOLVED, "PASS", d3.UNRESOLVED),
    (True, d3.STATIC_CAUSAL, "FAIL", d3.NON_CAUSAL),
    (False, d3.STATIC_CAUSAL, "FAIL", d3.NON_CAUSAL),
    (True, d3.NON_CAUSAL, "PASS", d3.NON_CAUSAL),
])
def test_causal_active_requires_binding_and_probe_and_static(
        binding, static, probe, expected):
    assert d4.classify_successor(binding, static, probe)["class"] == expected


# ----------------------------------------------------------- derivation
def test_a_verified_successor_root_binds_every_column(good_root):
    doc, man = d4.derive(good_root["out"], good_root["repo"], "T")
    assert doc["columns_examined"] == 89
    assert doc["by_class"] == {d3.CAUSAL: 89}
    assert man["bindings_established"] == 89
    assert man["successor"]["verification_codes"] == []
    assert man["successor"]["git_verified"] is True
    for b in man["bindings"]:
        assert d4.binding_complete(b)[0]
        assert b["commit"] == good_root["commit"]
    renamed = next(b for b in man["bindings"]
                   if b["output_column"] == "statistical__log_return_1")
    assert renamed["producer_output_column"] == "log_return_1"
    assert renamed["symbol"] == "compute_statistical"
    tp = next(b for b in man["bindings"]
              if b["output_column"] == "typical_price")
    assert tp["symbol"] == "derive_bar_columns"
    text = json.dumps(doc) + json.dumps(man)
    assert "/home/" not in text and str(good_root["out"]) not in text


def test_the_historical_dataset_stays_at_zero_active(good_root):
    doc, man = d4.derive(good_root["out"], good_root["repo"], "T")
    v3 = json.loads((CENSUS / "FEATURE_DAG.v3.json").read_text())
    assert doc["historical_causal_active_columns"] == 0
    assert man["historical"]["bindings_established"] == 0
    assert [(n["dataset_id"], n["column"], n["class"])
            for n in doc["historical_nodes"]] == \
        [(n["dataset_id"], n["column"], n["class"]) for n in v3["nodes"]]
    assert all(n["dataset_id"] != d4.HISTORICAL_DATASET
               for n in doc["nodes"])


def test_without_the_repository_nothing_is_bound(good_root):
    doc, man = d4.derive(good_root["out"], None, "T")
    assert doc["causal_active_columns"] == 0
    assert man["bindings_established"] == 0
    assert "GIT_REPOSITORY_NOT_PROVIDED" in \
        man["successor"]["verification_codes"]
    assert doc["columns_examined"] == 89, "no column is dropped"


def test_a_tampered_successor_is_not_bound(tmp_path):
    w = fx.build_world(tmp_path)
    fx.run_world(w, seal_directories=False)
    p = w["out"] / d4.rr.SUCC_PARQUET
    os.chmod(p, 0o644)
    with open(p, "ab") as fh:
        fh.write(b"\0")
    doc, man = d4.derive(w["out"], w["repo"], "T")
    assert doc["causal_active_columns"] == 0 == man["bindings_established"]
    assert "SUCCESSOR_DIGEST_MISMATCH" in man["successor"][
        "verification_codes"]
    assert doc["by_class"] == {d3.UNBOUND: 89}


def test_a_stopped_run_is_never_bound(tmp_path):
    w = fx.build_world(tmp_path, worker_patch=lambda t: t.replace(
        "def compute_technical(df: pd.DataFrame) -> pd.DataFrame:\n",
        "def compute_technical(df: pd.DataFrame) -> pd.DataFrame:\n"
        "    raise RuntimeError('boom')\n", 1))
    h = fx.harness_of(w)
    with pytest.raises(h.RunStopped):
        fx.run_world(w, harness=h)
    doc, man = d4.derive(w["out"], w["repo"], "T")
    assert doc["causal_active_columns"] == 0 == man["bindings_established"]
    assert doc["columns_examined"] == 89
    assert "RUN_STOPPED" in man["successor"]["verification_codes"]


def test_a_committed_leaking_assembler_makes_its_column_non_causal(tmp_path):
    def leak(text):
        return text.replace(
            "                            + raw[\"close\"].astype(float)) / 3\n",
            "                            + raw[\"close\"].astype(float)) / 3\n"
            "    out[\"typical_price\"] = out[\"typical_price\"].shift(-1)\n",
            1)
    w = fx.build_world(tmp_path, assembler_patch=leak)
    fx.run_world(w)
    e2e = json.loads((w["out"] / d4.rr.E2E_NAME).read_text())
    # the lead makes the cut row's typical_price NaN when the future is
    # truncated; the own-row filter then drops that row, so the row set at
    # or before the cut changes and EVERY column of the complete output
    # moves. The probe reports that, and v4 activates nothing.
    assert "typical_price" in e2e["columns_fail"]
    assert len(e2e["columns_fail"]) == 89
    doc, man = d4.derive(w["out"], w["repo"], "T")
    nodes = {n["column"]: n for n in doc["nodes"]}
    assert nodes["typical_price"]["class"] == d3.NON_CAUSAL
    assert nodes["typical_price"]["static"]["class"] == d3.NON_CAUSAL
    assert nodes["atr_14"]["static"]["class"] == d3.STATIC_CAUSAL
    assert nodes["atr_14"]["class"] == d3.NON_CAUSAL
    assert "E2E_PREFIX_INVARIANCE_FAILED" in nodes["atr_14"]["reason_codes"]
    assert doc["causal_active_columns"] == 0


# -------------------------------------------------- protected artifacts
def test_v1_to_v3_are_byte_identical_before_and_after(good_root, tmp_path):
    before = _digests()
    assert before == PINNED
    rc = d4.main(["derive", "--successor-root", str(good_root["out"]),
                  "--repository", str(good_root["repo"]),
                  "--derived-at", "2026-09-12T00:00:00Z",
                  "--output", str(tmp_path / "FEATURE_DAG.v4.json"),
                  "--binding-output",
                  str(tmp_path / "PRODUCER_BINDING_MANIFEST.v2.json")])
    assert rc == 0
    assert _digests() == before
    assert "/home/" not in (tmp_path / "FEATURE_DAG.v4.json").read_text()
    with pytest.raises(FileExistsError):
        d4.write_new(tmp_path / "FEATURE_DAG.v4.json", {"x": 1})


# ------------------------------------------------------------------ C93
def test_the_v3_disposition_is_recorded_without_rewriting_v3():
    path = CENSUS / "FEATURE_DAG_V3_DISPOSITION.v1.json"
    built = d4.build_v3_disposition()
    assert built["disposition"] == "STATIC_CANDIDATE_INVENTORY_UNBOUND"
    assert built["causal_active_columns"] == 0
    assert built["licenses_granted"] == 0
    assert built["bindings_established"] == 0
    assert built["historical_dataset"]["causal_active_columns"] == 0
    assert built["subject"]["file_sha256"] == PINNED["FEATURE_DAG.v3.json"]
    assert built["declared_limitations"]["provenance"]
    assert json.loads(path.read_text()) == built
    assert "/home/" not in path.read_text()
