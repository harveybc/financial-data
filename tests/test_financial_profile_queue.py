"""C127 (order 2026-09-12): the financial bank profile queue.

Hermetic fixtures build a tiny lake of metadata (no data bytes at all);
two tests bind the real repository so the fixtures stay honest.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "_scripts" / "build_financial_profile_queue.py"
CONTRACT_MODULE = ROOT.parent / "predictor" / "tools" / "df_contract.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


q = _load("build_financial_profile_queue_under_test", SCRIPT)
if not CONTRACT_MODULE.is_file():
    pytest.skip("the common contract module (predictor tools/df_contract.py) is absent",
                allow_module_level=True)
dfc = q.load_contract_module(CONTRACT_MODULE)
MOD_SHA = q.sha_bytes(CONTRACT_MODULE.read_bytes())
FORBIDDEN = ("PUBLICLY_ELIGIBLE", "LIVE_ELIGIBLE")


# ------------------------------------------------------------- fixture lake
def _w(root: Path, rel: str, obj) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj))


def _hex(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _app(aid, sc, entity, freq, rel, cols, rows, size):
    return {"appearance_id": aid, "source_class": sc, "entity": entity, "frequency": freq,
            "relative_path": rel, "manifest_status": "ok", "presence": "PRESENT",
            "period_start": "2020-01-01T00:00:00+00:00", "period_end": "2021-01-01T00:00:00+00:00",
            "declared_rows": rows, "declared_columns": cols, "size_bytes": size,
            "mtime_ns": 1, "ctime_ns": 1, "physical_sha256": _hex(aid),
            "digest_state": "PHYSICALLY_DIGESTED", "bytes_read_for_digest": size,
            "provenance": "UNAVAILABLE", "profile_depth": "DECLARED_SCHEMA_ONLY"}


def _var(vid, sc, entity, concept, apps, prov_files=(), sources=(), dirs=(), ambiguous=None,
         semantics="UNKNOWN", semantics_source="UNAVAILABLE"):
    lin = {"provenance_files": list(prov_files), "source_declarations": list(sources),
           "upstream_source_dirs": list(dirs),
           "upstream_join_rule": "entity name encodes the source path by repository convention"
           if dirs else "UNAVAILABLE"}
    if ambiguous:
        lin["ambiguous_provenance_candidates"] = ambiguous
    return {"variable_id": vid, "source_class": sc, "entity": entity, "concept_name": concept,
            "semantics": semantics, "semantics_source": semantics_source, "unit": "UNKNOWN",
            "physical_type": "UNKNOWN", "role": "UNKNOWN", "event_time": "UNAVAILABLE",
            "available_time": "UNAVAILABLE", "availability_contract": "UNAVAILABLE",
            "license": "UNKNOWN", "lineage": lin, "appearances": sorted(apps),
            "frequencies": [], "profile_depth": "DECLARED_SCHEMA_ONLY", "appearance_count": len(apps)}


def build_lake(root: Path, eth_input_sha: str | None = None) -> str:
    cs = "features/cross_source_features"
    apps, variables = [], []
    # A: declared provenance with file digests (Yahoo), two frequencies
    for f, size in (("1h", 300), ("4h", 100)):
        apps.append(_app(f"app_a_{f}", "cross_source", "market_data__equities__idx__aaa", f,
                         f"{cs}/{f}/market_data__equities__idx__aaa.parquet",
                         ["timestamp", "Close"], 50, size))
    for col in ("timestamp", "Close"):
        variables.append(_var(f"var_a_{col}", "cross_source", "market_data__equities__idx__aaa", col,
                              ["app_a_1h", "app_a_4h"],
                              prov_files=["market_data/equities/idx/aaa/provenance.json"],
                              sources=["Yahoo Finance"],
                              dirs=["market_data/equities/idx/aaa", "market_data/equities/idx",
                                    "market_data/equities", "market_data"],
                              semantics="closing price" if col == "Close" else "UNKNOWN",
                              semantics_source="market_data/equities/idx/aaa/data_dictionary.md"
                              if col == "Close" else "UNAVAILABLE"))
    _w(root, "market_data/equities/idx/aaa/provenance.json",
       {"source": "Yahoo Finance", "files": [{"path": "market_data/equities/idx/aaa/daily.parquet",
                                              "sha256": _hex("upstream-aaa")}]})
    _w(root, "market_data/equities/idx/aaa/data_dictionary.md", "| `Close` | closing price |\n")
    # B: ambiguous provenance -> producer UNRESOLVED, family from declared dirs
    for f, size in (("1h", 200), ("4h", 50)):
        apps.append(_app(f"app_b_{f}", "cross_source", "alternative_data__vendor__flows__x", f,
                         f"{cs}/{f}/alternative_data__vendor__flows__x.parquet", ["value"], 40, size))
    variables.append(_var("var_b_value", "cross_source", "alternative_data__vendor__flows__x", "value",
                          ["app_b_1h", "app_b_4h"],
                          dirs=["alternative_data/vendor/flows", "alternative_data/vendor", "alternative_data"],
                          ambiguous=["alternative_data/vendor/flows", "alternative_data/vendor"]))
    # C: a name that LOOKS like a known feature, with no declared lineage at all
    apps.append(_app("app_c_4h", "trading_asset", "ethusdt", "4h",
                     "features/trading_asset_data/ethusdt_like/4h.parquet", ["close", "log_return_1"], 30, 10))
    for col in ("close", "log_return_1"):
        variables.append(_var(f"var_c_{col}", "trading_asset", "ethusdt", col, ["app_c_4h"]))
    # D: trading asset whose provenance declares source_dir -> upstream provenance
    apps.append(_app("app_d_1h", "trading_asset", "dddusdt", "1h",
                     "features/trading_asset_data/dddusdt/1h.parquet", ["open"], 60, 120))
    apps.append(_app("app_d_4h", "trading_asset", "dddusdt", "4h",
                     "features/trading_asset_data/dddusdt/4h.parquet", ["open"], 2, 30))
    variables.append(_var("var_d_open", "trading_asset", "dddusdt", "open", ["app_d_1h", "app_d_4h"],
                          prov_files=["features/trading_asset_data/dddusdt/provenance.json"],
                          sources=["UNKNOWN"]))
    _w(root, "features/trading_asset_data/dddusdt/provenance.json",
       {"stage": "Stage 2.1", "asset": "dddusdt", "source_dir": "market_data/crypto/spot/dddusdt"})
    _w(root, "market_data/crypto/spot/dddusdt/provenance.json",
       {"source": "Binance Spot", "files": [{"path": "x/1h.parquet", "sha256": _hex("upstream-ddd")}]})
    if eth_input_sha == "app_d_1h":
        eth_input_sha = _hex("app_d_1h")

    census = {"schema": "financial_data.incremental_census.v1", "censused_at": "2026-09-12T00:00:00Z",
              "appearances": apps, "variables": variables}
    census["census_sha256"] = q.census_self_sha(census)
    rel = f"features/census/artifacts/census-{census['census_sha256']}.json"
    _w(root, rel, census)
    _w(root, q.CENSUS_ARTIFACTS["binding_manifest"],
       {"bindings": [], "successor": {"input_sha256": eth_input_sha or _hex("elsewhere"),
                                      "input_recorded_as": {}}})
    _w(root, q.CENSUS_ARTIFACTS["feature_lineage"], {"lineage": []})
    _w(root, q.CENSUS_ARTIFACTS["feature_dag"], {"nodes": []})
    _w(root, q.CENSUS_ARTIFACTS["demand_universes"],
       {k: {} for k in q.DEMAND_KEYS})
    return rel


@pytest.fixture()
def lake(tmp_path):
    root = tmp_path / "lake"
    rel = build_lake(root, eth_input_sha="app_d_1h")
    return root, rel


def _build(root, rel, budget=10_000):
    return q.build(root, rel, dfc, MOD_SHA, budget=budget)


def _vars(doc):
    return {v["variable_id"]: v for v in doc["variables"]}


# ------------------------------------------------------------------ tests
def test_deterministic_across_runs(lake):
    root, rel = lake
    a, ca = _build(root, rel)
    b, cb = _build(root, rel)
    assert q.canonical(a) == q.canonical(b) and q.canonical(ca) == q.canonical(cb)
    body = {k: v for k, v in a.items() if k != "queue_sha256"}
    assert a["queue_sha256"] == q.sha_obj(body)


def test_tier_ordering_respected(lake):
    root, rel = lake
    doc, _ = _build(root, rel)
    tiers = [row[3] for row in doc["queue"]]
    assert tiers == sorted(tiers)
    v = _vars(doc)
    assert v["var_a_Close"]["tier"] == 1 and v["var_d_open"]["tier"] == 1
    assert v["var_b_value"]["tier"] == 2 and v["var_c_close"]["tier"] == 2


def test_missing_bytes_fall_to_tier_three(tmp_path):
    root = tmp_path / "lake"
    rel = build_lake(root)
    census = json.loads((root / rel).read_text())
    for a in census["appearances"]:
        if a["appearance_id"] == "app_a_4h":
            a["presence"], a["physical_sha256"], a["digest_state"] = "MISSING", "UNAVAILABLE", \
                "DECLARED_ONLY_NOT_DIGESTED"
    census["census_sha256"] = q.census_self_sha(census)
    rel2 = f"features/census/artifacts/census-{census['census_sha256']}.json"
    _w(root, rel2, census)
    doc, contracts = _build(root, rel2)
    assert _vars(doc)["var_a_Close"]["tier"] == 3
    assert "app_a_4h" in doc["first_batch"]["appearances_skipped_bytes_not_present"]
    assert "app_a_4h" not in doc["first_batch"]["appearance_ids"]
    assert all(dfc.validate(c) == [] for c in contracts["contracts"])
    assert [r[3] for r in doc["queue"]] == sorted(r[3] for r in doc["queue"])


def test_round_robin_across_strata(lake):
    root, rel = lake
    doc, _ = _build(root, rel)
    for tier in {r[3] for r in doc["queue"]}:
        rows = [r for r in doc["queue"] if r[3] == tier]
        strata = sorted({r[4] for r in rows})
        # the first pass visits every stratum once, in sorted order
        assert [r[4] for r in rows[:len(strata)]] == strata
        # inside a stratum, variable_id then appearance_id ascend
        for s in strata:
            lane = [(r[1], r[2]) for r in rows if r[4] == s]
            assert lane == sorted(lane)
    # strata are indexed in sorted tuple order
    keys = [(s["producer"], s["frequency"], s["feature_family"], s["consumer"]) for s in doc["strata"]]
    assert keys == sorted(keys)


def test_round_robin_interleaves_a_large_stratum():
    items = [{"variable_id": f"v{n:02d}", "appearance_id": "a", "tier": 1, "stratum": ("P", "1h", "F", "NONE")}
             for n in range(3)] + [{"variable_id": "w0", "appearance_id": "a", "tier": 1,
                                    "stratum": ("Q", "1h", "F", "NONE")}]
    order = [i["variable_id"] for i in q.order_queue(items)]
    assert order == ["v00", "w0", "v01", "v02"]


def test_no_name_based_inference(lake):
    root, rel = lake
    doc, _ = _build(root, rel)
    v = _vars(doc)
    for vid in ("var_c_close", "var_c_log_return_1"):
        assert v[vid]["producer"]["state"] == "UNRESOLVED" and v[vid]["producer"]["value"] == "UNRESOLVED"
        assert v[vid]["feature_family"]["state"] == "UNRESOLVED"
        assert v[vid]["lineage_verifiable"]["value"] is False
    # ambiguous provenance is not resolved by picking a candidate
    assert v["var_b_value"]["producer"]["state"] == "UNRESOLVED"
    assert v["var_b_value"]["feature_family"]["value"] == "alternative_data/vendor"
    # declared chains do resolve
    assert v["var_a_Close"]["producer"]["value"] == "Yahoo Finance"
    assert v["var_d_open"]["producer"] == {
        "state": "DECLARED_VIA_PROVENANCE_SOURCE_DIR", "value": "Binance Spot",
        "evidence": v["var_d_open"]["producer"]["evidence"]}
    assert v["var_d_open"]["feature_family"]["value"] == "market_data/crypto"


def test_consumer_only_from_declared_digest(lake):
    root, rel = lake
    doc, _ = _build(root, rel)
    v = _vars(doc)
    assert v["var_d_open"]["consumer"] == ["BOUND_PRODUCER_INPUT"]
    assert all(v[x]["consumer"] == ["NONE"] for x in v if x != "var_d_open")


def test_license_never_public_or_eligible(lake):
    root, rel = lake
    doc, contracts = _build(root, rel)
    assert {v["license_state"] for v in doc["variables"]} == {q.LICENSE_STATE}
    assert doc["license"] == {"state": q.LICENSE_STATE, "evidence": []}
    for c in contracts["contracts"]:
        assert c["license"]["state"] == q.LICENSE_STATE and c["license"]["evidence"] == []
        assert {x["license_state"] for x in c["variables"]} == {q.LICENSE_STATE}
    text = json.dumps([doc, contracts])
    for word in FORBIDDEN:
        assert word not in text
    assert "OPEN_ATTRIBUTION" not in text and "OPEN_PUBLIC_DOMAIN" not in text


@pytest.mark.parametrize("budget", [0, 100, 250, 450, 10_000])
def test_byte_budget_respected(lake, budget):
    root, rel = lake
    doc, contracts = _build(root, rel, budget=budget)
    census = json.loads((root / rel).read_text())
    size = {a["appearance_id"]: a["size_bytes"] for a in census["appearances"]}
    fb = doc["first_batch"]
    assert fb["bytes"] == sum(size[a] for a in fb["appearance_ids"]) <= budget
    assert len(set(fb["appearance_ids"])) == fb["appearances"] == contracts["contracts_count"]
    # a 2-row appearance cannot be partitioned and is never in a batch
    assert "app_d_4h" not in fb["appearance_ids"]
    assert "app_d_4h" in fb["appearances_skipped_unpartitionable"]
    taken = {r[2] for r in doc["queue"] if r[5]}
    assert taken == set(fb["appearance_ids"])
    assert fb["strata_covered"] + fb["strata_uncovered"] == doc["counts"]["strata"]


def test_contracts_pass_seal_and_mutation_refuses(lake):
    root, rel = lake
    _, contracts = _build(root, rel)
    assert contracts["contracts"]
    for c in contracts["contracts"]:
        assert dfc.validate(c) == []
        assert dfc.seal(c) == c
        assert c["bank"] == "FINANCIAL" and len(c["files"]) == 1
        assert c["files"][0]["role"] == "DATA"
        assert c["partitions"]["frozen_before_profile"] is True
        assert c["partitions"]["boundaries"] == dfc.chronological_partitions(
            c["original_fields"]["census_appearance"]["declared_rows"])
        assert c["original_fields"]["census_appearance"]["appearance_id"] in c["dataset_id"]
    c = contracts["contracts"][0]
    bad = copy.deepcopy(c)
    bad["files"][0]["sha256"] = "0" * 64
    assert dfc.validate(bad) != []
    bad2 = copy.deepcopy(c)
    bad2["license"]["state"] = "OPEN_ATTRIBUTION"
    with pytest.raises(dfc.ContractRefusal):
        dfc.seal(bad2)
    bad3 = copy.deepcopy(c)
    bad3["source"]["provider"] = "PUBLICLY_" + "ELIGIBLE"
    with pytest.raises(dfc.ContractRefusal):
        dfc.seal(bad3)
    body = {k: v for k, v in contracts.items() if k != "contracts_file_sha256"}
    assert contracts["contracts_file_sha256"] == q.sha_obj(body)


def test_semantics_only_with_evidence(lake):
    root, rel = lake
    _, contracts = _build(root, rel)
    for c in contracts["contracts"]:
        for v in c["variables"]:
            assert v["unit"]["value"] == "UNKNOWN" and v["role"] == "UNKNOWN"
            if v["semantics"]["description"] != "UNKNOWN":
                assert v["semantics"]["evidence"] and q.HEX64.fullmatch(v["semantics"]["evidence"][0]["sha256"])


def test_write_once(lake):
    root, rel = lake
    args = ["--root", str(root), "--census", rel, "--contract-module", str(CONTRACT_MODULE),
            "--budget-bytes", "10000"]
    assert q.main(args) == 0
    first = (root / q.DEFAULT_OUT).read_bytes()
    assert q.main(args) == 2
    assert (root / q.DEFAULT_OUT).read_bytes() == first
    with pytest.raises(q.QueueRefusal):
        q.write_once(root / q.DEFAULT_OUT, {"x": 1})


def test_no_home_paths(lake):
    root, rel = lake
    args = ["--root", str(root), "--census", rel, "--contract-module", str(CONTRACT_MODULE)]
    assert q.main(args) == 0
    for out in (q.DEFAULT_OUT, q.DEFAULT_CONTRACTS_OUT):
        text = (root / out).read_text()
        assert str(Path.home()) not in text and "/home/" not in text and str(root) not in text


def test_metadata_only_and_census_digest(lake):
    root, rel = lake
    with pytest.raises(q.QueueRefusal):
        q.read_metadata(root, "features/cross_source_features/1h/x.parquet")
    with pytest.raises(q.QueueRefusal):
        q.read_metadata(root, "../outside.json")
    census = json.loads((root / rel).read_text())
    census["variables"][0]["license"] = "CC-BY"
    (root / rel).write_text(json.dumps(census))
    with pytest.raises(q.QueueRefusal):
        _build(root, rel)


# ----------------------------------------------------------- real repository
REAL_CENSUS = ROOT / q.DEFAULT_CENSUS


@pytest.mark.skipif(not REAL_CENSUS.is_file(), reason="the real census artifact is absent")
def test_real_repository_queue():
    doc, contracts = q.build(ROOT, q.DEFAULT_CENSUS, dfc, MOD_SHA)
    c = doc["counts"]
    assert c["variables"] == 1965 and c["items"] == sum(len(v["appearances"]) for v in doc["variables"])
    assert doc["inputs"]["census"]["appearances"] == 1680
    assert doc["first_batch"]["bytes"] <= q.DEFAULT_BUDGET_BYTES < c["lake_bytes_unique_appearances"]
    assert c["license_state"] == {q.LICENSE_STATE: 1965}
    assert contracts["contracts_count"] == doc["first_batch"]["appearances"] > 0
    for k in contracts["contracts"]:
        assert dfc.validate(k) == []
    text = json.dumps([doc, contracts])
    assert "/home/" not in text and all(w not in text for w in FORBIDDEN)
    for path, sha in doc["inputs"]["provenance_and_dictionary_files"].items():
        assert Path(path).suffix in q.METADATA_SUFFIXES


@pytest.mark.skipif(not (ROOT / q.DEFAULT_OUT).is_file(), reason="the queue artifact is not written yet")
def test_committed_artifact_rederives():
    doc, contracts = q.build(ROOT, q.DEFAULT_CENSUS, dfc, MOD_SHA)
    on_disk = json.loads((ROOT / q.DEFAULT_OUT).read_text())
    assert on_disk["queue_sha256"] == doc["queue_sha256"] == q.sha_obj(
        {k: v for k, v in on_disk.items() if k != "queue_sha256"})
    cdisk = json.loads((ROOT / q.DEFAULT_CONTRACTS_OUT).read_text())
    assert cdisk["contracts_file_sha256"] == contracts["contracts_file_sha256"] \
        == on_disk["first_batch_contracts"]["contracts_file_sha256"]
