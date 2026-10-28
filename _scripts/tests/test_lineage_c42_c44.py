"""C42-C44 (order 2026-09-11): demand from real consumers, lineage from
real provenance.

The bridge counted as "demand" every header of every declared view —
including `DATE_TIME` — and every JSON under `examples/config`,
including drafts that bind no observation contract. It then reported
94 supervised and 83 RL columns and concluded the RL set was a strict
subset. The subset was true and the premise was not: those 83 columns
came from configurations that are not consumers.

And the bridge's honest zero was not the end of the story. The
model-ready view carries its own provenance — domain, provider, and a
dataset id naming symbol and timeframe — so the entity does not have
to be guessed from 128 candidates, and the producer's declared
availability policy gives the causal latency.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_scripts"))

import derive_availability_bridge as bridge                    # noqa: E402
import derive_feature_lineage as lineage                       # noqa: E402


# ================================================================ C42
def test_temporal_identifiers_are_not_demand():
    for c in ("DATE_TIME", "date", "timestamp", "TIME", "index"):
        assert bridge._is_temporal(c), c
    for c in ("CLOSE", "rsi_14", "typical_price"):
        assert not bridge._is_temporal(c), c


def build_world(tmp: Path):
    pred = tmp / "predictor"
    am = tmp / "agent-multi"
    (pred / "examples/research").mkdir(parents=True)
    (pred / "data").mkdir(parents=True)
    view = pred / "data/view.csv"
    view.write_text("DATE_TIME,f1,f2,TARGET\n1,2,3,4\n")
    (pred / "examples/research/crispdm_dataset_inventory.v1.json"
     ).write_text(json.dumps({
         "inventory_sha256": "i" * 64,
         "datasets": [{
             "dataset_id": "x.project3.ethusdt_4h_tech.model_ready.v1",
             "relative_path": "data/view.csv",
             "provider": "Binance-derived export",
             "domain": "crypto_spot",
             "availability_policy":
                 "FEATURES_COMPUTED_CAUSALLY_THROUGH_BAR_CLOSE",
             "target_columns": ["TARGET"]}]}))
    cfgdir = am / "examples/config"
    cfgdir.mkdir(parents=True)
    (cfgdir / "draft.json").write_text(json.dumps(
        {"feature_columns": ["f1", "f2"]}))
    (cfgdir / "active.json").write_text(json.dumps(
        {"feature_columns": ["f1"], "observation_contract": {"v": 1}}))
    return pred, am


def test_a_draft_config_is_not_an_active_consumer(tmp_path):
    pred, am = build_world(tmp_path)
    demand = bridge.demand_columns(pred, am)
    active = [c["config"] for c in demand["rl_configs"]]
    rejected = [c["config"] for c in demand["rl_configs_rejected"]]
    assert active == ["examples/config/active.json"]
    assert rejected == ["examples/config/draft.json"]
    assert set(demand["rl_columns"]) == {"f1"}


def test_targets_and_timestamps_leave_input_demand(tmp_path):
    pred, am = build_world(tmp_path)
    demand = bridge.demand_columns(pred, am)
    assert set(demand["supervised_columns"]) == {"f1", "f2"}
    assert set(demand["supervised_targets"]) == {"TARGET"}
    excluded = {e["column"]: e["reason"]
                for s in demand["supervised_sources"]
                for e in s["columns_excluded"]}
    assert excluded == {"DATE_TIME": "ROW_IDENTIFIER",
                        "TARGET": "DECLARED_TARGET"}


def test_every_consumer_is_bound_by_digest(tmp_path):
    pred, am = build_world(tmp_path)
    demand = bridge.demand_columns(pred, am)
    for s in demand["supervised_sources"]:
        assert len(s["sha256"]) == 64
    for c in demand["rl_configs"]:
        assert len(c["sha256"]) == 64
    for entry in demand["rl_columns"]["f1"]:
        assert len(entry["sha256"]) == 64


# ================================================================ C43
def test_the_entity_is_derived_from_the_view_not_chosen():
    ds = {"dataset_id": "fd.project3.ethusdt_4h_tech.model_ready.v1",
          "provider": "Binance-derived Project 3 export",
          "domain": "crypto_spot"}
    b = lineage.entity_binding(ds)
    assert b["symbol"] == "ETHUSDT"
    assert b["timeframe"] == "4h"
    assert b["state"] == lineage.RESOLVED
    assert "no candidate entity was chosen by name" in b["derivation"]


def test_a_view_without_provenance_is_a_named_deficit():
    ds = {"dataset_id": "predictor.legacy.eurusd_1h.phase1_test.v1",
          "provider": "legacy predictor dataset; provider not recorded",
          "domain": "forex"}
    b = lineage.entity_binding(ds)
    assert b["state"] == lineage.DEFICIT
    assert "provider" in b["missing"]


def test_available_time_is_never_event_time():
    ds = {"dataset_id": "fd.p.ethusdt_4h_t.model_ready.v1",
          "availability_policy": "UNDECLARED"}
    b = lineage.entity_binding(ds)
    c = lineage.availability_contract(ds, b)
    assert c["state"] == lineage.DEFICIT
    assert c["earliest_available_time"] == "UNAVAILABLE"
    assert "event_time is NOT copied" in c["refusal"]


def test_a_declared_causal_policy_yields_the_latency():
    ds = {"dataset_id": "fd.p.ethusdt_4h_t.model_ready.v1",
          "availability_policy":
              "FEATURES_COMPUTED_CAUSALLY_THROUGH_BAR_CLOSE; "
              "DECISION_AT_CLOSE"}
    b = lineage.entity_binding(ds)
    c = lineage.availability_contract(ds, b)
    assert c["state"] == lineage.RESOLVED
    assert c["causal_latency_seconds"] == 4 * 3600
    assert "max(input event times)" in c["derivation"]


@pytest.mark.parametrize("tf,seconds", [
    ("1m", 60), ("4h", 14400), ("1d", 86400), ("1w", 604800),
    ("", None), ("nonsense", None)])
def test_timeframe_parsing(tf, seconds):
    assert lineage.timeframe_seconds(tf) == seconds


# ================================================================ C44
def test_the_candidate_submission_grants_nothing():
    out = (ROOT / "features/census"
           / "FINANCIAL_AVAILABILITY_CANDIDATE.v1.json")
    if not out.is_file():
        pytest.skip("the candidate has not been derived on this host")
    doc = json.loads(out.read_text())
    assert doc["requires"] == "EXTERNAL_REVIEW"
    assert "confers no eligibility" in doc["grants_nothing"]
    assert doc["columns_total"] == len(doc["columns"])
    assert doc["columns_total"] > 0
    for c in doc["columns"]:
        assert c["symbol"] != "UNDERIVABLE"
        assert c["earliest_available_time"] != "UNAVAILABLE"


def test_the_deficit_names_its_holder_and_needs_no_owner():
    out = ROOT / "features/census/FEATURE_LINEAGE.v1.json"
    if not out.is_file():
        pytest.skip("the lineage has not been derived on this host")
    doc = json.loads(out.read_text())
    assert doc["columns_resolved"] + doc["columns_unresolved"] == \
        doc["columns_examined"]
    for d in doc["producer_deficits"]:
        assert d["holder"]
        assert d["requires_owner_decision"] is False
        assert d["missing_entity_fields"] or \
            d["missing_availability_fields"]
