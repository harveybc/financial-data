"""Adversarial battery for the incremental canonical census.

Each test names the specific failure the census exists to
prevent; a passing suite is the evidence that the failure cannot
occur silently. Hermetic fixtures build a tiny lake so the tests
are fast and independent of the real 14 GB tree; two tests bind
the real repository to keep the fixtures honest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_scripts" / "lib"))

import incremental_census as ic  # noqa: E402


# --------------------------------------------------------------
# fixtures: a tiny synthetic lake
# --------------------------------------------------------------

def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture()
def lake(tmp_path: Path) -> Path:
    root = tmp_path / "lake"
    manifest = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "stage": "test",
        "trading_assets": {
            "aaausdt": {"timeframes": {
                "1h": {"path": "features/trading_asset_data/"
                               "aaausdt/1h.parquet",
                       "status": "ok", "rows": 10,
                       "start": "2020-01-01T00:00:00+00:00",
                       "end": "2020-01-02T00:00:00+00:00",
                       "columns": ["timestamp", "close",
                                   "volume"]},
                "4h": {"path": "features/trading_asset_data/"
                               "aaausdt/4h.parquet",
                       "status": "ok", "rows": 3,
                       "start": "2020-01-01T00:00:00+00:00",
                       "end": "2020-01-02T00:00:00+00:00",
                       "columns": ["timestamp", "close",
                                   "volume"]},
            }},
        },
        "cross_source_features": {
            "1h": {
                "macro__src_one__series_a": {
                    "path": "features/cross_source_features/1h/"
                            "macro__src_one__series_a.parquet",
                    "status": "ok", "rows": 5,
                    "start": "2021-01-01T00:00:00+00:00",
                    "end": "2021-02-01T00:00:00+00:00",
                    "columns": ["timestamp", "Close"]},
            },
        },
    }
    _write(root / "features/MANIFEST.json",
           json.dumps(manifest))
    for rel in ("features/trading_asset_data/aaausdt/1h.parquet",
                "features/trading_asset_data/aaausdt/4h.parquet",
                "features/cross_source_features/1h/"
                "macro__src_one__series_a.parquet"):
        _write(root / rel, "x" * 128)
    # a SEMANTIC dictionary for the trading asset
    _write(root / "features/trading_asset_data/aaausdt/"
                  "data_dictionary.md",
           "# Data Dictionary\n\n"
           "- `timestamp`: UTC bar timestamp.\n"
           "- `close`: closing price.\n")
    # a self-declared COVERAGE STUB upstream
    _write(root / "macro/src_one/data_dictionary.md",
           "# Data Dictionary\n\nColumns follow source naming "
           "unless normalized by the acquisition script.\n")
    _write(root / "macro/src_one/provenance.json",
           json.dumps({"source": "Test Source",
                       "acquired_at": "2026-01-01T00:00:00Z"}))
    _write(root / "features/trading_asset_data/aaausdt/"
                  "provenance.json",
           json.dumps({"source": "Exchange",
                       "acquired_at": "2026-01-01T00:00:00Z"}))
    _write(root / "configs/availability_contract.schema.json",
           json.dumps({"required": ["feature_family", "provider",
                                    "observation_ts_col",
                                    "available_from_ts_col",
                                    "revision_policy",
                                    "timezone",
                                    "min_latency_minutes",
                                    "license_scope"],
                       "properties": {}}))
    return root


@pytest.fixture()
def census(lake: Path) -> dict:
    return ic.build_census(lake, "2026-09-10T00:00:00Z")


# --------------------------------------------------------------
# the two grains
# --------------------------------------------------------------

def test_appearance_is_never_counted_as_a_variable(census):
    """3 slices, 8 column occurrences, but only 5 conceptual
    variables: `close` at 1h and 4h is ONE variable."""
    assert census["coverage"]["appearances_total"] == 3
    assert census["coverage"]["declared_column_occurrences"] == 8
    assert census["coverage"]["conceptual_variables"] == 5
    close = [v for v in census["variables"]
             if v["entity"] == "aaausdt"
             and v["concept_name"] == "close"]
    assert len(close) == 1
    assert close[0]["appearance_count"] == 2
    assert sorted(close[0]["frequencies"]) == ["1h", "4h"]


def test_path_is_never_the_logical_identity(lake, census):
    """Moving a file keeps the appearance id; the path is an
    attribute, so a rename is a CHANGE, never a new appearance."""
    before = {a["appearance_id"]: a["relative_path"]
              for a in census["appearances"]}
    m = json.loads((lake / "features/MANIFEST.json").read_text())
    slot = m["trading_assets"]["aaausdt"]["timeframes"]["1h"]
    moved = "features/relocated/aaausdt_1h.parquet"
    (lake / moved).parent.mkdir(parents=True, exist_ok=True)
    (lake / moved).write_text("x" * 128)
    slot["path"] = moved
    (lake / "features/MANIFEST.json").write_text(json.dumps(m))
    after = ic.build_census(lake, "2026-09-10T00:00:00Z")
    ids_before, ids_after = set(before), {
        a["appearance_id"] for a in after["appearances"]}
    assert ids_before == ids_after, "a move invented an identity"
    delta = ic.compute_delta(census, after["appearances"],
                             after["variables"])
    assert delta["appearances"]["CHANGED"] == 1
    assert delta["appearances"]["ADDED"] == 0
    assert delta["appearances"]["MISSING"] == 0


def test_same_concept_different_entities_stay_distinct(census):
    """`close` on a trading asset and `Close` on a macro family
    are never merged into one variable by name."""
    ids = {(v["entity"], v["concept_name"]): v["variable_id"]
           for v in census["variables"]}
    a = ids[("aaausdt", "close")]
    b = ids[("macro__src_one__series_a", "Close")]
    assert a != b


# --------------------------------------------------------------
# equivalences and conflicts are DECLARED, never resolved
# --------------------------------------------------------------

def test_equivalence_is_declared_not_resolved(census):
    classes = {c["normalized_concept"]: c
               for c in census["equivalence_classes"]}
    close = classes["close"]
    assert close["distinct_spellings"] == ["Close", "close"]
    assert close["status"].startswith("DECLARED_CANDIDATE")
    assert close["member_variable_count"] == 2
    conflicts = [c for c in census["conflicts"]
                 if c["normalized_concept"] == "close"]
    assert conflicts and conflicts[0]["kind"] == \
        "SPELLING_VARIANTS_UNDER_ONE_NORMAL_FORM"
    # and the two members still exist separately
    assert census["coverage"]["conceptual_variables"] == 5


def test_ambiguous_provenance_is_declared_not_picked(lake):
    """Two upstream candidates carrying provenance must leave the
    variable WITHOUT provenance and declare the ambiguity."""
    _write(lake / "macro/provenance.json",
           json.dumps({"source": "Other Source"}))
    c = ic.build_census(lake, "2026-09-10T00:00:00Z")
    v = [x for x in c["variables"]
         if x["entity"] == "macro__src_one__series_a"][0]
    assert v["lineage"]["provenance_files"] == []
    assert sorted(
        v["lineage"]["ambiguous_provenance_candidates"]) == [
            "macro", "macro/src_one"]
    assert c["gaps"]["ambiguous_provenance"]["variable_count"] >= 1


# --------------------------------------------------------------
# metadata is never invented
# --------------------------------------------------------------

def test_event_and_available_time_are_separate_and_unavailable(
        census):
    for v in census["variables"]:
        assert "event_time" in v and "available_time" in v
        assert v["event_time"] == ic.UNAVAILABLE
        assert v["available_time"] == ic.UNAVAILABLE
    assert census["availability_contract"]["instances_found"] == 0
    assert census["availability_contract"]["schema_present"]


def test_unit_role_and_license_are_never_inferred(census):
    for v in census["variables"]:
        assert v["unit"] == ic.UNKNOWN
        assert v["role"] == ic.UNKNOWN
    gaps = census["gaps"]
    assert gaps["unit_gap"]["variable_count"] == 5
    assert gaps["role_gap"]["variable_count"] == 5
    assert gaps["availability_gap"]["variable_count"] == 5


def test_coverage_stub_never_counts_as_semantics(census):
    """The upstream dictionary self-declares it is not a semantic
    schema: the macro variables must stay semantics-UNKNOWN."""
    kinds = census["dictionary_coverage"]["by_kind"]
    assert kinds["COVERAGE_STUB_SELF_DECLARED_NON_SEMANTIC"] == 1
    assert kinds["SEMANTIC_DICTIONARY"] == 1
    macro = [v for v in census["variables"]
             if v["entity"] == "macro__src_one__series_a"]
    assert macro and all(v["semantics"] == ic.UNKNOWN
                         for v in macro)
    # while the real bullet dictionary DOES declare semantics
    close = [v for v in census["variables"]
             if v["entity"] == "aaausdt"
             and v["concept_name"] == "close"][0]
    assert close["semantics"] == "closing price."
    assert close["semantics_source"].endswith(
        "data_dictionary.md")


def test_gaps_are_listed_exactly_in_both_grains(census):
    for kind in ("license_gap", "unit_gap", "provenance_gap",
                 "availability_gap", "role_gap", "semantics_gap"):
        g = census["gaps"][kind]
        assert set(g) >= {"variable_count", "entity_count",
                          "entities", "variable_fraction"}
        assert len(g["entities"]) == g["entity_count"]


# --------------------------------------------------------------
# delta
# --------------------------------------------------------------

def test_first_census_declares_it_has_no_predecessor(census):
    d = census["delta"]
    assert d["basis"] == "FIRST_CENSUS_NO_PREDECESSOR"
    assert d["appearances"]["ADDED"] == 3
    assert d["appearances"]["UNCHANGED"] == 0


def test_delta_emits_added_unchanged_changed_missing(lake,
                                                     census):
    m = json.loads((lake / "features/MANIFEST.json").read_text())
    # ADDED: a new frequency
    m["trading_assets"]["aaausdt"]["timeframes"]["1d"] = {
        "path": "features/trading_asset_data/aaausdt/1d.parquet",
        "status": "ok", "rows": 1,
        "start": "2020-01-01T00:00:00+00:00",
        "end": "2020-01-02T00:00:00+00:00",
        "columns": ["timestamp", "close"]}
    _write(lake / "features/trading_asset_data/aaausdt/"
                  "1d.parquet", "y" * 64)
    # CHANGED: more rows and a new column on an existing slice
    m["trading_assets"]["aaausdt"]["timeframes"]["4h"][
        "rows"] = 99
    # MISSING: a family disappears from the manifest
    del m["cross_source_features"]["1h"][
        "macro__src_one__series_a"]
    (lake / "features/MANIFEST.json").write_text(json.dumps(m))
    after = ic.build_census(lake, "2026-09-11T00:00:00Z",
                            previous=census)
    d = after["delta"]
    assert d["basis"] == "COMPARED_BY_LOGICAL_IDENTITY"
    assert d["appearances"] == {"ADDED": 1, "UNCHANGED": 1,
                                "CHANGED": 1, "MISSING": 1}
    assert d["variables"]["MISSING"] == 2
    assert d["previous_census"] == census["census_sha256"]


def test_unchanged_lake_reports_everything_unchanged(lake,
                                                     census):
    again = ic.build_census(lake, "2026-09-11T00:00:00Z",
                            previous=census)
    assert again["delta"]["appearances"] == {
        "ADDED": 0, "UNCHANGED": 3, "CHANGED": 0, "MISSING": 0}
    assert again["delta"]["variables"]["UNCHANGED"] == 5


# --------------------------------------------------------------
# honesty of the sweep and of the digest policy
# --------------------------------------------------------------

def test_first_census_binds_every_appearance_to_bytes(census):
    """CORRECTED (order C6). This test previously asserted the
    opposite — that a first census digested NOTHING — which is
    the defect the audit found: stat() was standing in for a
    digest. A first census now hashes every present appearance,
    and the SECOND census is the one that reads no bytes."""
    cov = census["coverage"]
    assert cov["appearances_physically_digested"] == 3
    assert cov["digest_coverage_fraction"] == 1.0
    assert all(a["digest_state"] == "PHYSICALLY_DIGESTED"
               for a in census["appearances"])
    assert all(len(a["physical_sha256"]) == 64
               for a in census["appearances"])


def test_the_second_census_is_the_one_that_reads_no_bytes(
        lake, census):
    again = ic.build_census(lake, "2026-09-11T00:00:00Z",
                            previous=census)
    cov = again["coverage"]
    assert cov["bytes_read_for_digest"] == 0
    assert cov["appearances_digest_reused"] == 3
    assert cov["appearances_physically_digested"] == 0


def test_an_explicit_selection_re_hashes_even_when_unchanged(
        lake):
    """CORRECTED (order C6): a first census digests everything,
    so selection is only distinguishable on a LATER census, where
    it must re-hash a slice that every physical signal says is
    unchanged."""
    first = ic.build_census(lake, "2026-09-10T00:00:00Z")
    assert first["coverage"][
        "appearances_physically_digested"] == 3
    sel = {"features/trading_asset_data/aaausdt/1h.parquet"}
    second = ic.build_census(lake, "2026-09-11T00:00:00Z",
                             previous=first, selected=sel)
    states = {a["relative_path"]: a["digest_state"]
              for a in second["appearances"]}
    assert states[
        "features/trading_asset_data/aaausdt/1h.parquet"] == \
        "PHYSICALLY_DIGESTED"
    assert second["coverage"][
        "appearances_physically_digested"] == 1
    assert second["coverage"]["appearances_digest_reused"] == 2


def test_changed_bytes_are_re_digested_incrementally(lake,
                                                     census):
    p = lake / "features/trading_asset_data/aaausdt/4h.parquet"
    p.write_text("x" * 4096)
    after = ic.build_census(lake, "2026-09-11T00:00:00Z",
                            previous=census)
    digested = [a for a in after["appearances"]
                if a["digest_state"] == "PHYSICALLY_DIGESTED"]
    assert len(digested) == 1
    assert digested[0]["relative_path"].endswith("4h.parquet")


def test_sampled_profile_never_claims_a_full_census(tmp_path):
    import pandas as pd
    p = tmp_path / "s.csv"
    pd.DataFrame({"a": range(100), "b": ["z"] * 100}).to_csv(
        p, index=False)
    prof = ic.value_profile_slice(p, row_cap=10)
    assert prof["profile_depth"] == ic.PROFILE_SAMPLED
    assert prof["read_was_capped"] is True
    assert prof["completeness"] == \
        "SAMPLED_HEAD_NOT_A_COMPLETE_PHYSICAL_CENSUS"
    assert prof["columns"]["a"]["rows_read"] == 10
    full = ic.value_profile_slice(p, row_cap=1000)
    assert full["completeness"] == "COMPLETE_SLICE_READ"


def test_missing_slice_is_reported_not_dropped(lake, census):
    (lake / "features/trading_asset_data/aaausdt/"
            "4h.parquet").unlink()
    c = ic.build_census(lake, "2026-09-11T00:00:00Z")
    assert c["coverage"]["appearances_missing"] == 1
    assert c["coverage"]["appearances_total"] == 3
    assert len(c["gaps"]["physically_missing_appearances"]) == 1


def test_absent_manifest_refuses(tmp_path):
    with pytest.raises(SystemExit, match="never guesses"):
        ic.build_census(tmp_path, "2026-09-10T00:00:00Z")


# --------------------------------------------------------------
# receipt and identity
# --------------------------------------------------------------

def test_receipt_binds_code_and_grants_nothing(lake, census,
                                               tmp_path):
    cp = tmp_path / "census.json"
    cp.write_text(json.dumps(census))
    sp = tmp_path / "summary.json"
    sp.write_text(json.dumps(ic.summarize(census)))
    code = [REPO / "_scripts/lib/incremental_census.py"]
    r = ic.receipt(census, cp, sp, lake, code)
    assert r["census_sha256"] == census["census_sha256"]
    assert "grants_nothing" in r
    assert list(r["code_identity"]) == [
        "incremental_census.py"]
    assert ic._self_sha(r, "receipt_sha256") == \
        r["receipt_sha256"]


def test_census_self_digest_re_derives(census):
    assert ic._self_sha(census) == census["census_sha256"]
    mutated = dict(census)
    mutated["coverage"] = {**census["coverage"],
                           "conceptual_variables": 999}
    assert ic._self_sha(mutated) != census["census_sha256"]


def test_summary_is_small_and_carries_no_row_level_data(census):
    s = ic.summarize(census)
    blob = json.dumps(s)
    assert "appearances" not in s
    assert "variables" not in s
    assert len(blob) < 200_000
    assert s["census_sha256"] == census["census_sha256"]


# --------------------------------------------------------------
# the real repository (keeps the fixtures honest)
# --------------------------------------------------------------

@pytest.mark.skipif(
    not (REPO / "features/MANIFEST.json").is_file(),
    reason="real manifest not present")
def test_real_lake_matches_the_reviewed_reconciliation():
    c = ic.build_census(REPO, "2026-09-10T00:00:00Z")
    cov = c["coverage"]
    # the numbers Musashi's reviewed reconciliation published
    assert cov["appearances_total"] == 1680
    assert cov["appearances_missing"] == 0
    assert cov["declared_column_occurrences"] == 7860
    assert cov["declared_bytes_from_stat"] == 14436534039
    # and the knowledge the reconciliation could not have:
    # occurrences are NOT variables
    assert cov["conceptual_variables"] == 1965
    assert cov["entities"] == 420


@pytest.mark.skipif(
    not (REPO / "features/MANIFEST.json").is_file(),
    reason="real manifest not present")
def test_real_lake_availability_is_wholly_undeclared():
    c = ic.build_census(REPO, "2026-09-10T00:00:00Z")
    ac = c["availability_contract"]
    assert ac["schema_present"] is True
    assert ac["instances_found"] == 0
    assert c["gaps"]["availability_gap"]["variable_count"] == \
        c["coverage"]["conceptual_variables"]
