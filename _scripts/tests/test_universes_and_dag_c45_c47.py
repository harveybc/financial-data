"""C45-C47 (order 2026-09-12): demand, grains and a real causal DAG.

The previous derivation called every header of two registry datasets
"ACTIVE consumer demand", reported 93 unique names beside 97
(dataset, column) subjects without distinguishing them, and gave all 84
derived features one sentence and one availability formula.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_scripts"))

import derive_demand_universes as U                           # noqa: E402
import derive_feature_dag as D                                # noqa: E402


# ================================================================ C45
def build_world(tmp: Path):
    pred = tmp / "predictor"
    am = tmp / "agent-multi"
    (pred / "examples/config").mkdir(parents=True)
    (pred / "examples/research").mkdir(parents=True)
    (pred / "data").mkdir(parents=True)
    for role in ("train", "validation", "test"):
        (pred / f"data/x_{role}.csv").write_text("DATE_TIME,f1,f2\n1,2,3\n")
        (pred / f"data/y_{role}.csv").write_text("DATE_TIME,TARGET\n1,9\n")
    runnable = {"target_column": "TARGET"}
    for role in ("train", "validation", "test"):
        runnable[f"x_{role}_file"] = f"data/x_{role}.csv"
        runnable[f"y_{role}_file"] = f"data/y_{role}.csv"
    (pred / "examples/config/runnable.json").write_text(
        json.dumps(runnable))
    (pred / "examples/config/broken.json").write_text(json.dumps(
        {"x_train_file": "data/does_not_exist.csv"}))
    (pred / "examples/research/crispdm_dataset_inventory.v1.json"
     ).write_text(json.dumps({
         "inventory_sha256": "i" * 64,
         "datasets": [{"dataset_id": "registry.only.v1",
                       "relative_path": "data/x_train.csv",
                       "provider": "p", "domain": "d"}]}))
    (am / "examples/config").mkdir(parents=True)
    (am / "examples/config/draft.json").write_text(json.dumps(
        {"feature_columns": ["f1"]}))
    (am / "data").mkdir(parents=True)
    (am / "data/in.csv").write_text("f1\n1\n")
    (am / "examples/config/active.json").write_text(json.dumps(
        {"feature_columns": ["f1"], "observation_contract": {"v": 1},
         "input_data_file": "data/in.csv"}))
    return pred, am


def test_only_runnable_configs_are_demand(tmp_path):
    pred, am = build_world(tmp_path)
    sup = U.supervised_demand(pred)
    assert [c["config"] for c in sup["executable_configs"]] == \
        ["examples/config/runnable.json"]
    assert sup["unreachable_configs"][0]["config"] == \
        "examples/config/broken.json"
    assert "cannot run this config" in \
        sup["unreachable_configs"][0]["reason"]


def test_a_registry_entry_is_not_demand(tmp_path):
    pred, am = build_world(tmp_path)
    sup = U.supervised_demand(pred)
    research = U.research_candidates(
        pred, {s["dataset"] for s in sup["subjects"]})
    assert research["state"] == "REGISTERED_FOR_DEVELOPMENT"
    entry = research["datasets"][0]
    assert entry["dataset_id"] == "registry.only.v1"
    assert "CANDIDATE" in research["note"]


def test_an_rl_config_needs_a_contract_and_its_data(tmp_path):
    pred, am = build_world(tmp_path)
    rl = U.rl_demand(am)
    assert [c["config"] for c in rl["active_configs"]] == \
        ["examples/config/active.json"]
    assert [c["config"] for c in rl["rejected_configs"]] == \
        ["examples/config/draft.json"]
    assert set(rl["columns"]) == {"f1"}


# ================================================================ C46
def test_the_grains_are_different_numbers(tmp_path):
    pred, am = build_world(tmp_path)
    sup = U.supervised_demand(pred)
    names = {s["column"] for s in sup["subjects"]}
    pairs = {(s["dataset"], s["column"]) for s in sup["subjects"]}
    assert len(names) < len(pairs), (
        "one column name appearing in several datasets is several "
        "subjects and one name")


def test_targets_never_enter_as_inputs(tmp_path):
    pred, am = build_world(tmp_path)
    sup = U.supervised_demand(pred)
    for s in sup["subjects"]:
        if s["column"] == "TARGET":
            assert s["contract_role"] == "target"
    assert "TARGET" in sup["targets"]


def test_temporal_identifiers_are_never_subjects(tmp_path):
    pred, am = build_world(tmp_path)
    sup = U.supervised_demand(pred)
    assert not [s for s in sup["subjects"]
                if U.is_temporal(s["column"])]


def test_an_empty_set_is_not_applicable():
    src = (ROOT / "_scripts/derive_demand_universes.py").read_text()
    assert "NOT_APPLICABLE" in src
    ns: dict = {}
    exec(compile(src[src.index("    def subset_claim("):
                     src.index("    grains = {")].replace(
        "    def subset_claim", "def subset_claim").replace(
        "\n        ", "\n    "), "<x>", "exec"), {"NOT_APPLICABLE":
                                                  U.NOT_APPLICABLE}, ns)
    claim = ns["subset_claim"]
    assert claim(set(), {"a"}) == U.NOT_APPLICABLE
    assert claim({"a"}, {"a", "b"}) is True
    assert claim({"z"}, {"a"}) is False


# ================================================================ C47
def producer_world(tmp: Path) -> Path:
    repo = tmp / "producer"
    (repo / "pkg").mkdir(parents=True)
    subprocess.run(("git", "init", "-q", str(repo)), check=True)
    (repo / "pkg/features.py").write_text(
        "def compute(df):\n"
        "    df['return_5'] = df['CLOSE'].pct_change(5)\n"
        "    df['sma_20'] = df['CLOSE'].rolling(window=20).mean()\n"
        "    df['rsi_14'] = rsi(df['CLOSE'], 14)\n"
        "    df['centred'] = df['CLOSE'].rolling(10, center=True).mean()\n"
        "    df['peek'] = df['CLOSE'].shift(-1)\n"
        "    return df\n")
    return repo


def test_each_shape_gets_its_own_graph(tmp_path):
    repo = producer_world(tmp_path)
    found = D.index_producers({"producer": repo})
    index = found["index"]
    assert {"return_5", "sma_20", "rsi_14", "centred", "peek"} <= \
        set(index)
    sma = index["sma_20"][0]
    assert sma["window_hint"]["lookback"] == 20
    assert "rolling" in sma["window_hint"]["calls"]
    assert sma["inputs"] == ["CLOSE"]
    assert sma["symbol"] == "compute"
    assert sma["line"] > 0 and len(sma["code_sha256"]) == 64


def test_a_centred_window_is_non_causal(tmp_path):
    repo = producer_world(tmp_path)
    index = D.index_producers({"producer": repo})["index"]
    node = D.classify("centred", index["centred"], {})
    assert node["klass"] == D.NON_CAUSAL
    assert "centred" in node["why"]
    avail = D.availability(node, 3600, "FEATURES_COMPUTED_CAUSALLY_"
                                       "THROUGH_BAR_CLOSE")
    assert avail["earliest_available_time"] == "UNAVAILABLE"
    assert "leakage" in avail["reason"]


def test_a_forward_shift_is_non_causal(tmp_path):
    repo = producer_world(tmp_path)
    index = D.index_producers({"producer": repo})["index"]
    node = D.classify("peek", index["peek"], {})
    assert node["klass"] == D.NON_CAUSAL
    assert node["shift"] == -1


def test_raw_ohlcv_is_causal_at_the_bar_close():
    node = D.classify("CLOSE", [], {})
    assert node["klass"] == D.CAUSAL
    assert node["lookback"] == 1
    avail = D.availability(node, 14400,
                           "FEATURES_COMPUTED_CAUSALLY_THROUGH_BAR_CLOSE")
    assert avail["causal_latency_seconds"] == 14400


def test_a_feature_nobody_produces_is_unresolved():
    node = D.classify("a_feature_nobody_makes", [], {})
    assert node["klass"] == D.UNRESOLVED
    assert "Nothing is asserted" in node["why"]
    avail = D.availability(node, 3600, "FEATURES_COMPUTED_CAUSALLY_"
                                       "THROUGH_BAR_CLOSE")
    assert avail["earliest_available_time"] == "UNAVAILABLE"
    assert avail["reason"] == "the producer was not located"


def test_a_retired_producer_is_demoted_and_declared(tmp_path):
    live = {"file": "pkg/features.py", "window_hint": {"calls": [],
            "lookback": 10, "shift": None, "center": None},
            "inputs": ["CLOSE"]}
    retired = {"file": "project2/part_II_invalidated/old.py",
               "window_hint": {"calls": [], "lookback": 99,
                               "shift": None, "center": None},
               "inputs": ["CLOSE"]}
    ranked = D.rank_producers([retired, live])
    assert ranked[0] is live, "a live producer outranks a retired one"
    node = D.classify("x", [retired], {})
    assert node["producer_is_retired_path"] is True
    assert "retired or" in node["why"]


def test_availability_refuses_without_a_declared_policy():
    node = D.classify("CLOSE", [], {})
    out = D.availability(node, 3600, "UNDECLARED")
    assert out["earliest_available_time"] == "UNAVAILABLE"
    assert "never copied" in out["reason"]


# ================================================================ C48
def test_the_supersession_keeps_the_old_artifacts():
    out = ROOT / "features/census/AVAILABILITY_SUPERSESSION.v1.json"
    if not out.is_file():
        pytest.skip("the supersession has not been derived here")
    doc = json.loads(out.read_text())
    for s in doc["superseded"]:
        assert s["kept"] == "BYTE_INTACT"
        assert len(s["sha256"]) == 64
        assert (ROOT / "features/census" / s["artifact"]).is_file()
    assert "mandatory" in doc["external_review"]
