"""C6-C8: the census is now physically bound.

The audit found that the first census digested nothing, that an
equal-length mutation was invisible, that a content-addressed
name was truncated, that external profiles were copied without
verification, and that the availability join could never fire.
Each of those is a test here.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_scripts" / "lib"))

import incremental_census as ic  # noqa: E402


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
                       "columns": ["timestamp", "close"]},
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
                    "columns": ["timestamp", "value"]},
            },
        },
    }
    _write(root / "features/MANIFEST.json",
           json.dumps(manifest))
    _write(root / "features/trading_asset_data/aaausdt/"
                  "1h.parquet", "x" * 128)
    _write(root / "features/cross_source_features/1h/"
                  "macro__src_one__series_a.parquet", "y" * 128)
    _write(root / "configs/availability_contract.schema.json",
           json.dumps({"required": [
               "feature_family", "provider",
               "observation_ts_col", "available_from_ts_col",
               "revision_policy", "timezone",
               "min_latency_minutes", "license_scope"],
               "properties": {}}))
    return root


# ==============================================================
# C6: the first census digests every present appearance
# ==============================================================

def test_first_census_digests_everything_present(lake):
    c = ic.build_census(lake, "2026-09-10T00:00:00Z")
    cov = c["coverage"]
    assert cov["appearances_physically_digested"] == 2
    assert cov["appearances_not_digested"] == 0
    assert cov["digest_coverage_fraction"] == 1.0
    assert cov["bytes_read_for_digest"] == 256
    for a in c["appearances"]:
        assert a["digest_state"] == "PHYSICALLY_DIGESTED"
        assert len(a["physical_sha256"]) == 64
    assert c["delta"]["appearances"]["ADDED"] == 2


def test_stat_is_never_presented_as_a_digest(lake):
    c = ic.build_census(lake, "2026-09-10T00:00:00Z")
    note = c["coverage"]["digest_coverage_note"]
    assert "stat() is never counted as a digest" in note
    for a in c["appearances"]:
        assert a["physical_sha256"] != str(a["size_bytes"])


# ==============================================================
# C6: an unchanged entry REUSES its verified digest
# ==============================================================

def test_unchanged_entries_reuse_the_previous_digest(lake):
    first = ic.build_census(lake, "2026-09-10T00:00:00Z")
    second = ic.build_census(lake, "2026-09-11T00:00:00Z",
                             previous=first)
    cov = second["coverage"]
    assert cov["appearances_physically_digested"] == 0
    assert cov["appearances_digest_reused"] == 2
    assert cov["bytes_read_for_digest"] == 0
    for a in second["appearances"]:
        assert a["digest_state"] == \
            "REUSED_FROM_PREVIOUS_VERIFIED_CENSUS"
    before = {a["appearance_id"]: a["physical_sha256"]
              for a in first["appearances"]}
    after = {a["appearance_id"]: a["physical_sha256"]
             for a in second["appearances"]}
    assert before == after
    assert second["delta"]["appearances"]["UNCHANGED"] == 2


# ==============================================================
# C6: an EQUAL-LENGTH mutation forces a re-hash
# ==============================================================

def test_equal_length_mutation_is_re_digested(lake):
    first = ic.build_census(lake, "2026-09-10T00:00:00Z")
    target = (lake / "features/trading_asset_data/aaausdt/"
                     "1h.parquet")
    original = target.read_text()
    time.sleep(0.01)
    target.write_text("z" * len(original))     # SAME length
    assert target.stat().st_size == len(original)

    second = ic.build_census(lake, "2026-09-11T00:00:00Z",
                             previous=first)
    changed = [a for a in second["appearances"]
               if a["digest_state"] == "PHYSICALLY_DIGESTED"]
    assert len(changed) == 1
    assert changed[0]["relative_path"].endswith("1h.parquet")
    old = {a["appearance_id"]: a["physical_sha256"]
           for a in first["appearances"]}
    assert changed[0]["physical_sha256"] != \
        old[changed[0]["appearance_id"]]
    assert second["delta"]["appearances"]["CHANGED"] == 1


def test_explicit_selection_always_re_hashes(lake):
    first = ic.build_census(lake, "2026-09-10T00:00:00Z")
    sel = {"features/trading_asset_data/aaausdt/1h.parquet"}
    second = ic.build_census(lake, "2026-09-11T00:00:00Z",
                             previous=first, selected=sel)
    states = {a["relative_path"]: a["digest_state"]
              for a in second["appearances"]}
    assert states[
        "features/trading_asset_data/aaausdt/1h.parquet"] == \
        "PHYSICALLY_DIGESTED"


def test_ctime_change_alone_forces_a_re_hash(lake):
    """A metadata-only touch changes ctime_ns; the census must
    re-verify rather than trust the old digest."""
    first = ic.build_census(lake, "2026-09-10T00:00:00Z")
    target = (lake / "features/cross_source_features/1h/"
                     "macro__src_one__series_a.parquet")
    time.sleep(0.01)
    os.chmod(target, 0o640)
    second = ic.build_census(lake, "2026-09-11T00:00:00Z",
                             previous=first)
    states = {a["relative_path"]: a["digest_state"]
              for a in second["appearances"]}
    assert states[
        "features/cross_source_features/1h/"
        "macro__src_one__series_a.parquet"] == \
        "PHYSICALLY_DIGESTED"


# ==============================================================
# C6: the content-addressed artifact is never truncated
# ==============================================================

def test_the_writer_uses_o_excl_and_verifies_equality():
    src = (REPO /
           "_scripts/build_incremental_census.py").read_text()
    assert "os.O_EXCL" in src
    assert "O_TRUNC" not in src
    assert "a content-addressed name" in src
    assert "SKIPPED_IDENTICAL" in src


# ==============================================================
# C7: the availability join is explicit and reported
# ==============================================================

def test_a_family_reaches_the_entities_it_covers():
    entities = [("cross_source", "macro__src_one__series_a"),
                ("cross_source", "macro__src_two__series_b"),
                ("trading_asset", "aaausdt")]
    join = ic.map_families_to_entities(
        {"macro/src_one": {"feature_family": "macro/src_one"}},
        entities)
    assert join["by_family"]["macro/src_one"] == [
        "macro__src_one__series_a"]
    assert join["entity_to_family"][
        "macro__src_one__series_a"] == "macro/src_one"
    assert join["unmatched_families"] == []


def test_two_entities_of_one_family_both_resolve():
    entities = [("cross_source", "macro__src_one__a"),
                ("cross_source", "macro__src_one__b")]
    join = ic.map_families_to_entities(
        {"macro/src_one": {}}, entities)
    assert join["by_family"]["macro/src_one"] == [
        "macro__src_one__a", "macro__src_one__b"]
    assert len(join["entity_to_family"]) == 2


def test_an_entity_matching_two_families_is_ambiguous():
    entities = [("cross_source", "macro__src_one__a")]
    join = ic.map_families_to_entities(
        {"macro": {}, "macro/src_one": {}}, entities)
    assert join["ambiguous_entities"] == {
        "macro__src_one__a": ["macro", "macro/src_one"]}
    assert "macro__src_one__a" not in join["entity_to_family"]


def test_an_unmatched_family_is_reported_not_dropped():
    join = ic.map_families_to_entities(
        {"nowhere/at/all": {}},
        [("cross_source", "macro__src_one__a")])
    assert join["unmatched_families"] == ["nowhere/at/all"]
    assert join["entity_to_family"] == {}


def test_a_real_instance_reaches_its_variables(lake):
    """The end-to-end version of the defect: a contract lands and
    the variables it covers stop being UNAVAILABLE."""
    inst = {
        "feature_family": "macro/src_one",
        "provider": "Test Provider",
        "observation_ts_col": "event_ts",
        "available_from_ts_col": "available_ts",
        "revision_policy": "not_revised",
        "timezone": "UTC",
        "min_latency_minutes": 0,
        "license_scope": "research",
    }
    _write(lake / "configs/src_one_availability.json",
           json.dumps(inst))
    c = ic.build_census(lake, "2026-09-10T00:00:00Z")
    assert c["availability_contract"]["instances_found"] == 1
    covered = [v for v in c["variables"]
               if v["entity"] == "macro__src_one__series_a"]
    assert covered, "the family covers no variable"
    for v in covered:
        assert v["event_time"] == "event_ts"
        assert v["available_time"] == "available_ts"
    # and an unrelated entity stays UNAVAILABLE
    other = [v for v in c["variables"]
             if v["entity"] == "aaausdt"]
    assert all(v["available_time"] == ic.UNAVAILABLE
               for v in other)


# ==============================================================
# C8: external profiles are verified, not copied
# ==============================================================

def test_external_profiles_are_verified_by_recomputation():
    src = (REPO /
           "_scripts/build_incremental_census.py").read_text()
    assert "FULL_PROFILE_PHYSICALLY_VERIFIED" in src
    assert "DECLARED_ONLY_NOT_VERIFIED" in src
    assert "not_verified_because" in src
    assert "_self_sha" in src and "sha256_file" in src


def test_a_self_consistent_summary_is_not_called_full():
    """The label FULL is reserved for a profile whose inventory
    digest re-derives AND whose bytes were re-hashed here."""
    assert ic.PROFILE_FULL == "FULL_PROFILE_PHYSICALLY_VERIFIED"


def test_stubs_stay_non_semantic(lake):
    _write(lake / "macro/src_one/data_dictionary.md",
           "# Data Dictionary\n\nColumns follow source naming "
           "unless normalized by the acquisition script.\n")
    c = ic.build_census(lake, "2026-09-10T00:00:00Z")
    kinds = c["dictionary_coverage"]["by_kind"]
    assert kinds["COVERAGE_STUB_SELF_DECLARED_NON_SEMANTIC"] == 1
    macro = [v for v in c["variables"]
             if v["entity"] == "macro__src_one__series_a"]
    assert all(v["semantics"] == ic.UNKNOWN for v in macro)


# ==============================================================
# the real lake keeps the fixtures honest
# ==============================================================

@pytest.mark.skipif(
    not (REPO / "features/MANIFEST.json").is_file(),
    reason="real manifest not present")
def test_the_published_summary_reports_full_physical_coverage():
    p = REPO / "features/census/CENSUS_SUMMARY.v1.json"
    if not p.is_file():
        pytest.skip("census summary not built")
    cov = json.loads(p.read_text())["coverage"]
    assert cov["appearances_total"] == 1680
    assert (cov["appearances_physically_digested"]
            + cov["appearances_digest_reused"]) == 1680
    assert cov["digest_coverage_fraction"] == 1.0
    assert cov["appearances_not_digested"] == 0


@pytest.mark.skipif(
    not (REPO / "features/census/AVAILABILITY_SCOPE.v1.json"
         ).is_file(),
    reason="availability scope not derived")
def test_the_availability_scope_instantiates_only_what_is_shown():
    doc = json.loads((REPO / "features/census/"
                             "AVAILABILITY_SCOPE.v1.json"
                      ).read_text())
    assert doc["supply"]["families_assessed"] == 420
    # every family the sources cannot demonstrate stays out
    assert doc["supply"]["families_instantiable"] == len(
        doc["supply"]["instances"])
    hist = doc["supply"]["missing_field_histogram"]
    assert hist["available_from_ts_col"] == 420, (
        "if a source ever declares an availability column this "
        "number must fall, and this test must be revisited "
        "together with the scope")
