"""C115 battery: successor semantic census."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cen = _load("build_eth_h4_successor_semantic_census", "_scripts/build_eth_h4_successor_semantic_census.py")
SUCC = cen.DEFAULT_SUCCESSORS_ROOT
ROOTS = {"financial-data": ROOT, cen.SUCC_ROOT_ID: SUCC / "eth_h4_stage22_rerun_v1"}
HAS_DATA = (ROOTS[cen.SUCC_ROOT_ID] / cen.PINNED["successor_parquet"][1]).is_file()


def _path(logical: str) -> Path:
    rid, rel = logical.split(":", 1)
    return ROOTS[rid] / rel


@pytest.fixture(scope="module")
def doc():
    if not HAS_DATA:
        pytest.skip("successor root not present")
    return cen.build()


@pytest.fixture(scope="module")
def files(doc):
    return {k: _path(k).read_bytes() for k in doc["evidence_files"]}


def test_89_rows_unique_exact_keys(doc):
    rows = doc["rows"]
    assert len(rows) == 89 == doc["counts"]["rows"]
    assert len({r["column"] for r in rows}) == 89
    assert len({r["variable_id"] for r in rows}) == 89
    for r in rows:
        assert set(r) == set(cen.ROW_KEYS) and len(r) == len(cen.ROW_KEYS)
        assert set(r["evidence"]) == set(cen.EVIDENCE_FIELDS)
        assert r["variable_id"] == hashlib.sha256((r["dataset_id"] + "\0" + r["column"]).encode()).hexdigest()
        assert r["semantics"] == r["semantic_type"]
        assert r["dataset_id"] == cen.DATASET_ID and r["dataset_sha256"] == cen.DATASET_SHA256
    dag = json.loads((ROOT / "features/census/FEATURE_DAG.v4.json").read_text())
    assert [r["column"] for r in rows] == [n["column"] for n in dag["nodes"] if n["class"] == "CAUSAL_ACTIVE"]


def test_every_declaration_has_real_matching_evidence(doc):
    for r in doc["rows"]:
        for f in cen.EVIDENCE_FIELDS:
            e = r["evidence"][f]
            if r[f] == cen.UNKNOWN:
                assert e == {"source": "NONE", "sha256": None}
                continue
            assert e["source"] != "NONE" and len(e["sha256"]) == 64
            p = _path(cen._file_key(e["source"]))
            assert p.is_file(), e["source"]
            assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"], (r["column"], f)


def test_validator_accepts_real_census(doc, files):
    assert cen.validate_census(doc, files) == []
    assert doc["self_digest"]["value"] == cen.self_digest(doc)["value"]
    assert "/home/" not in json.dumps(doc)


def test_license_unknown_everywhere_no_license_document(doc):
    assert doc["counts"]["license_state"] == {"UNKNOWN": 89}
    assert all(r["license_source"] == "NONE" for r in doc["rows"])
    assert doc["license_search"]["finding"] == "NO_LICENSE_DOCUMENT_FOR_THESE_BYTES"


def test_units_only_with_formula_proof(doc):
    byc = {r["column"]: r for r in doc["rows"]}
    for c, r in byc.items():
        assert (r["unit"] != cen.UNKNOWN) == (c in doc["unit_derivations"])
    # price-denominated columns are not given a unit
    for c in ("OPEN", "CLOSE", "VOLUME", "sma_10", "macd", "atr_14", "obv", "vwap_60"):
        assert byc[c]["unit"] == cen.UNKNOWN
    for c in ("return_1", "log_return_60", "rsi_14", "zscore_close_100"):
        assert byc[c]["unit"] == "1"


def _row(d, col):
    return next(r for r in d["rows"] if r["column"] == col)


def test_column_name_only_unit_is_refused(doc, files):
    d = copy.deepcopy(doc)
    r = _row(d, "sma_10")  # 'sma' says nothing about a unit; name-only inference
    r["unit"] = "1"
    r["evidence"]["unit"] = {"source": "column_name:sma_10", "sha256": None}
    assert "DECLARED_WITHOUT_EVIDENCE:sma_10.unit" in cen.validate_census(d, files)
    # evidence to a real file but no formula proof
    r["evidence"]["unit"] = dict(r["evidence"]["symbol"])
    defects = cen.validate_census(d, files)
    assert "UNIT_EVIDENCE_NOT_PRODUCER_CODE:sma_10" in defects and "UNIT_WITHOUT_FORMULA_PROOF:sma_10" in defects
    # producer code evidence with a fabricated proof expression
    r["evidence"]["unit"] = dict(r["evidence"]["semantic_type"])
    d["unit_derivations"]["sma_10"] = dict(d["unit_derivations"]["return_1"],
                                           expressions=['out[f"sma_{period}"] = close.rolling(period).mean() / close'])
    assert any(x.startswith("UNIT_PROOF_EXPRESSION_NOT_IN_SYMBOL:sma_10") for x in cen.validate_census(d, files))


def test_evidence_less_unit_refused_and_unknown_with_evidence_refused(doc, files):
    d = copy.deepcopy(doc)
    r = _row(d, "return_1")
    r["evidence"]["unit"] = {"source": "NONE", "sha256": None}
    assert "DECLARED_WITHOUT_EVIDENCE:return_1.unit" in cen.validate_census(d, files)
    d = copy.deepcopy(doc)
    r = _row(d, "OPEN")
    r["evidence"]["unit"] = dict(r["evidence"]["semantic_type"])
    assert "UNKNOWN_WITH_EVIDENCE:OPEN.unit" in cen.validate_census(d, files)


def test_license_without_source_and_sha_mismatch_refused(doc, files):
    d = copy.deepcopy(doc)
    r = _row(d, "rsi_14")
    r["license"] = "CC-BY-4.0"
    defects = cen.validate_census(d, files)
    assert "LICENSE_WITHOUT_SOURCE:rsi_14" in defects and "DECLARED_WITHOUT_EVIDENCE:rsi_14.license" in defects
    d = copy.deepcopy(doc)
    _row(d, "rsi_14")["evidence"]["lookback_bars"]["sha256"] = "f" * 64
    assert "EVIDENCE_SHA256_MISMATCH:rsi_14.lookback_bars" in cen.validate_census(d, files)


def test_duplicates_refuse(doc, files):
    d = copy.deepcopy(doc)
    d["rows"].append(copy.deepcopy(d["rows"][3]))
    defects = cen.validate_census(d, files)
    assert f"DUPLICATE_COLUMN:{d['rows'][3]['column']}" in defects
    assert f"DUPLICATE_VARIABLE_ID:{d['rows'][3]['variable_id']}" in defects
    d = copy.deepcopy(doc)
    d["rows"][5]["variable_id"] = d["rows"][6]["variable_id"]
    assert any(x.startswith("DUPLICATE_VARIABLE_ID") for x in cen.validate_census(d, files))


def test_extra_or_missing_row_key_refused(doc, files):
    d = copy.deepcopy(doc)
    d["rows"][0]["note"] = "x"
    assert f"ROW_KEYS:{d['rows'][0]['column']}" in cen.validate_census(d, files)


@pytest.mark.skipif(not HAS_DATA, reason="successor root not present")
def test_pinned_digest_mismatch_refuses(monkeypatch):
    bad = dict(cen.PINNED)
    rid, rel, _ = bad["worker"]
    bad["worker"] = (rid, rel, "0" * 64)
    monkeypatch.setattr(cen, "PINNED", bad)
    with pytest.raises(cen.DigestMismatch):
        cen.build()


def test_census_write_once(doc, tmp_path):
    out = tmp_path / cen.CENSUS_NAME
    cen.publish(doc, out)
    first = out.read_bytes()
    with pytest.raises(FileExistsError):
        cen.publish(doc, out)
    with pytest.raises(cen.CensusRefusal, match="write-once"):
        cen.main(["--output", str(out)])
    assert out.read_bytes() == first
