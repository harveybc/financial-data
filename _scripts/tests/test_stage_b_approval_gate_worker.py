"""
Tests for stage_b_approval_gate_worker.py

Pattern follows existing test files in this directory:
- unittest.TestCase classes
- self-contained mocked data (no real artifacts required)
- deterministic, no network, no GPU
"""
from __future__ import annotations

import csv
import json
import math
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd

# Make sure we can import the worker
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage_b_approval_gate_worker as W


# ---------------------------------------------------------------------------
# Helpers to build synthetic rows / evidence
# ---------------------------------------------------------------------------
def _row(overrides: dict | None = None) -> pd.Series:
    """Build a default PROMOTE_BLOCKED_HARDENING row."""
    defaults = {
        "run_slug": "ethusdt_4h_sac_tech_stat_s0_test",
        "asset": "ethusdt",
        "timeframe": "4h",
        "algo": "sac",
        "preset": "tech_stat",
        "seed": "0",
        "machine": "dragon",
        "total_return": "0.15",
        "sharpe_ratio": "0.01",
        "max_drawdown_pct": "11.0",
        "trades_total": "426",
        "cost_optimistic": "0.149",
        "cost_base": "0.136",
        "cost_pessimistic": "0.108",
        "asset_class": "crypto_spot",
        "has_baseline": "True",
        "baseline_slug": "",
        "baseline_return": "0.05",
        "baseline_sharpe": "0.80",
        "uplift_total_return": "0.28",
        "uplift_sharpe_ratio": "0.05",
        "n_seeds": "2",
        "dsr_approx": "-3.6",
        "dsr_status": "approximate_directional_only",
        "classification": "PROMOTE_BLOCKED_HARDENING",
        "watch_flags": "",
        "n_blockers": "2",
        "blockers": "B3_DSR: ...; B4_PBO: ...",
    }
    if overrides:
        defaults.update(overrides)
    return pd.Series(defaults)


def _leakage_pass(slug: str) -> dict:
    return {
        "run_slug": slug,
        "status": "PASS_HELDOUT_FIREWALL",
        "b1_overall": "B1_PARTIAL_PASS",
        "b10_firewall_cleared": True,
        "max_ts_before_boundary": True,
        "max_ts": "2023-12-31 20:00:00",
        "error": "",
    }


def _leakage_heldout_violation(slug: str) -> dict:
    return {
        "run_slug": slug,
        "status": "FAIL",
        "b1_overall": "FAIL",
        "b10_firewall_cleared": False,
        "max_ts_before_boundary": False,
        "max_ts": "2025-06-15 00:00:00",
        "error": "max timestamp exceeds heldout boundary",
    }


def _leakage_blocked_missing(slug: str) -> dict:
    return {
        "run_slug": slug,
        "status": "BLOCKED_INPUT_MISSING",
        "b1_overall": "BLOCKED_INPUT_MISSING",
        "b10_firewall_cleared": False,
        "max_ts_before_boundary": None,
        "max_ts": "",
        "error": "train.csv not found",
    }


def _baseline_pass(slug: str) -> dict:
    return {
        "run_slug": slug,
        "b8_evidence": "PASS",
        "baselines_available": True,
        "rl_beats_best_baseline_at_base_cost": True,
        "rl_beats_best_baseline_at_pessimistic_cost": True,
    }


def _baseline_fail(slug: str) -> dict:
    return {
        "run_slug": slug,
        "b8_evidence": "FAIL",
        "baselines_available": True,
        "rl_beats_best_baseline_at_base_cost": False,
        "rl_beats_best_baseline_at_pessimistic_cost": False,
    }


def _baseline_blocked(slug: str) -> dict:
    return {
        "run_slug": slug,
        "b8_evidence": "BLOCKED_NO_BASELINES",
        "baselines_available": False,
    }


def _ablation_pass(slug: str) -> dict:
    return {
        "run_slug": slug,
        "b9_evidence": "PASS",
        "reason": "all required matched family ablations pass",
        "n_comparisons": 2,
        "n_pass": 2,
        "n_fail": 0,
    }


def _ablation_fail(slug: str) -> dict:
    return {
        "run_slug": slug,
        "b9_evidence": "FAIL",
        "reason": "required matched family ablation fails",
        "n_comparisons": 1,
        "n_pass": 0,
        "n_fail": 1,
    }


def _ablation_not_applicable(slug: str) -> dict:
    return {
        "run_slug": slug,
        "b9_evidence": "NOT_APPLICABLE",
        "reason": "baseline preset has no narrower family ablation",
    }


def _ablation_no_match(slug: str) -> dict:
    return {
        "run_slug": slug,
        "b9_evidence": "BLOCKED_NO_MATCH",
        "reason": "no matched variant found",
    }


def _make_composite_index_for_row(row: pd.Series) -> dict:
    """Build a composite index with one entry matching the given row."""
    key = (
        str(row.get("asset", "")).lower(),
        str(row.get("timeframe", "")).lower(),
        str(row.get("algo", "")).lower(),
        str(row.get("preset", "")).lower(),
        int(float(row.get("seed", 0))),
    )
    entry = {
        "asset": str(row.get("asset", "")),
        "timeframe": str(row.get("timeframe", "")),
        "algorithm": str(row.get("algo", "")),
        "feature_preset": str(row.get("preset", "")),
        "seed": int(float(row.get("seed", 0))),
        "run_id": f"{row.get('asset')}_test_run_id",
        "trial_id": "abc123",
        "event_type": "complete",
    }
    return {key: [entry]}


def _run_classify(row_overrides=None,
                  ledger_raw_ids=None,       # set of raw run_id/trial_id strings
                  ledger_composite_index=None,  # composite key index
                  ledger_error="",
                  leakage_entry=None, leakage_available=True,
                  baseline_entry=None, baseline_available=True,
                  ablation_entry=None, ablation_available=True,
                  stageb_stat_index=None, stageb_stat_available=False):
    row = _row(row_overrides)
    slug = str(row["run_slug"])

    # Default: ledger contains the row via composite key (no direct ID match needed)
    if ledger_raw_ids is None:
        raw_ids = set()
    else:
        raw_ids = ledger_raw_ids
    if ledger_composite_index is None:
        composite_idx = _make_composite_index_for_row(row)
    else:
        composite_idx = ledger_composite_index

    leakage_idx = {slug: leakage_entry} if leakage_entry else {}
    baseline_idx = {slug: baseline_entry} if baseline_entry else {}
    ablation_idx = {slug: ablation_entry} if ablation_entry else {}
    return W.classify_candidate(
        row=row,
        ledger_raw_ids=raw_ids,
        ledger_composite_index=composite_idx,
        ledger_error=ledger_error,
        leakage_index=leakage_idx if leakage_available else {},
        leakage_available=leakage_available,
        baseline_index=baseline_idx if baseline_available else {},
        baseline_available=baseline_available,
        ablation_index=ablation_idx if ablation_available else {},
        ablation_available=ablation_available,
        stageb_stat_index=stageb_stat_index or {},
        stageb_stat_available=stageb_stat_available,
    )


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------
class TestKillChecks(unittest.TestCase):

    def test_kill_no_trades_from_hardening_classification(self):
        result = _run_classify({"classification": "KILL_NO_TRADES", "trades_total": "0"})
        self.assertEqual(result["stage_b_status"], "KILL_NO_TRADES")

    def test_kill_negative_sharpe_from_hardening_classification(self):
        result = _run_classify({"classification": "KILL_NEGATIVE_SHARPE",
                                "sharpe_ratio": "-0.05",
                                "total_return": "0.03"})
        self.assertEqual(result["stage_b_status"], "KILL_NEGATIVE_SHARPE")

    def test_kill_non_positive_return_from_hardening_classification(self):
        result = _run_classify({"classification": "KILL_NON_POSITIVE_RETURN",
                                "total_return": "-0.08",
                                "sharpe_ratio": "-0.07"})
        self.assertEqual(result["stage_b_status"], "KILL_NON_POSITIVE_RETURN")

    def test_kill_non_positive_return_does_not_become_kill_negative_sharpe(self):
        # A run with negative sharpe AND non-positive return must become
        # KILL_NON_POSITIVE_RETURN (hardening classification wins)
        result = _run_classify({"classification": "KILL_NON_POSITIVE_RETURN",
                                "total_return": "-0.02",
                                "sharpe_ratio": "-0.01"})
        self.assertNotEqual(result["stage_b_status"], "KILL_NEGATIVE_SHARPE")
        self.assertEqual(result["stage_b_status"], "KILL_NON_POSITIVE_RETURN")

    def test_kill_no_trades_short_circuits_all_other_checks(self):
        # Even if all evidence is absent, a KILL_NO_TRADES must not become BLOCKED_*
        result = _run_classify({"classification": "KILL_NO_TRADES"},
                               leakage_available=False,
                               baseline_available=False,
                               ablation_available=False)
        self.assertEqual(result["stage_b_status"], "KILL_NO_TRADES")

    def test_metric_based_zero_trades_kill(self):
        # No explicit hardening kill label but zero trades detected from metric
        result = _run_classify({"classification": "PROMOTE_BLOCKED_HARDENING",
                                "trades_total": "0"},
                               leakage_entry=_leakage_pass("ethusdt_4h_sac_tech_stat_s0_test"),
                               baseline_entry=_baseline_pass("ethusdt_4h_sac_tech_stat_s0_test"),
                               ablation_entry=_ablation_pass("ethusdt_4h_sac_tech_stat_s0_test"))
        self.assertEqual(result["stage_b_status"], "KILL_NO_TRADES")

    def test_metric_based_non_positive_return_kill(self):
        result = _run_classify({"classification": "PROMOTE_BLOCKED_HARDENING",
                                "total_return": "0.0",
                                "trades_total": "100"},
                               leakage_entry=_leakage_pass("ethusdt_4h_sac_tech_stat_s0_test"),
                               baseline_entry=_baseline_pass("ethusdt_4h_sac_tech_stat_s0_test"),
                               ablation_entry=_ablation_pass("ethusdt_4h_sac_tech_stat_s0_test"))
        self.assertEqual(result["stage_b_status"], "KILL_NON_POSITIVE_RETURN")


class TestLedgerChecks(unittest.TestCase):

    def test_missing_ledger_blocks_all_candidates(self):
        result = _run_classify(
            ledger_raw_ids=set(),
            ledger_composite_index={},
            ledger_error="Ledger not found",
        )
        self.assertEqual(result["stage_b_status"], "BLOCKED_LEDGER_ABSENT")

    def test_ledger_missing_entry_adds_blocker(self):
        # Ledger exists but has no matching entry for this slug
        result = _run_classify(
            ledger_raw_ids={"some_other_slug"},
            ledger_composite_index={},  # empty — no composite match
            leakage_entry=_leakage_pass("ethusdt_4h_sac_tech_stat_s0_test"),
            baseline_entry=_baseline_pass("ethusdt_4h_sac_tech_stat_s0_test"),
            ablation_entry=_ablation_pass("ethusdt_4h_sac_tech_stat_s0_test"),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("LEDGER_MISSING_ENTRY", codes)

    def test_slug_in_raw_ids_no_ledger_blocker(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            ledger_raw_ids={slug},
            ledger_composite_index={},
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertNotIn("LEDGER_MISSING_ENTRY", codes)
        self.assertNotIn("LEDGER_LOAD_ERROR", codes)

    def test_composite_key_match_no_ledger_blocker(self):
        # Default _run_classify uses composite index — no direct ID match needed
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            ledger_raw_ids=set(),  # no direct ID
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertNotIn("LEDGER_MISSING_ENTRY", codes)


class TestLeakageChecks(unittest.TestCase):

    def test_missing_leakage_report_blocks_candidate(self):
        result = _run_classify(
            leakage_available=False,
            baseline_entry=_baseline_pass("ethusdt_4h_sac_tech_stat_s0_test"),
            ablation_entry=_ablation_pass("ethusdt_4h_sac_tech_stat_s0_test"),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("LEAKAGE_REPORT_MISSING", codes)
        self.assertNotEqual(result["stage_b_status"], "PASS_STAGE_B_READY")

    def test_heldout_leakage_is_fatal(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_heldout_violation(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        self.assertEqual(result["stage_b_status"], "BLOCKED_HELDOUT_FIREWALL")
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("HELDOUT_DATA_IN_TRAIN", codes)

    def test_blocked_input_missing_leakage(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_blocked_missing(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("LEAKAGE_INPUT_MISSING", codes)

    def test_leakage_pass_no_blocker(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertNotIn("HELDOUT_DATA_IN_TRAIN", codes)
        self.assertNotIn("LEAKAGE_REPORT_MISSING", codes)
        self.assertNotIn("LEAKAGE_ENTRY_MISSING", codes)

    def test_leakage_entry_missing_adds_blocker(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        # leakage_entry=None with leakage_available=True → no index entry for slug
        result = _run_classify(
            leakage_entry=None,
            leakage_available=True,
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("LEAKAGE_ENTRY_MISSING", codes)

    def _run_classify_with_leakage_idx(self, leakage_idx, slug, baseline_entry, ablation_entry):
        row = _row({"run_slug": slug})
        composite = _make_composite_index_for_row(row)
        return W.classify_candidate(
            row=row,
            ledger_raw_ids={slug},
            ledger_composite_index=composite,
            ledger_error="",
            leakage_index=leakage_idx,
            leakage_available=True,
            baseline_index={slug: baseline_entry},
            baseline_available=True,
            ablation_index={slug: ablation_entry},
            ablation_available=True,
        )

    def test_leakage_entry_missing_adds_blocker_direct(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = self._run_classify_with_leakage_idx(
            {},  # empty index — no entry for slug
            slug,
            _baseline_pass(slug),
            _ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("LEAKAGE_ENTRY_MISSING", codes)


class TestBaselineChecks(unittest.TestCase):

    def test_missing_baseline_report_blocks_candidate(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_available=False,
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("BASELINE_REPORT_MISSING", codes)
        self.assertNotEqual(result["stage_b_status"], "PASS_STAGE_B_READY")

    def test_baseline_fail_blocks_candidate(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_fail(slug),
            ablation_entry=_ablation_pass(slug),
        )
        self.assertEqual(result["stage_b_status"], "BLOCKED_BASELINE_COMPARISON")
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("BASELINE_FAIL", codes)

    def test_baseline_input_missing_blocks_candidate(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_blocked(slug),
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("BASELINE_INPUT_MISSING", codes)

    def test_baseline_entry_missing_blocks_candidate(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=None,
            baseline_available=True,
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("BASELINE_ENTRY_MISSING", codes)

    def test_baseline_pass_no_baseline_blocker(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertNotIn("BASELINE_FAIL", codes)
        self.assertNotIn("BASELINE_REPORT_MISSING", codes)
        self.assertNotIn("BASELINE_ENTRY_MISSING", codes)


class TestAblationChecks(unittest.TestCase):

    def test_missing_ablation_report_blocks_candidate(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_available=False,
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("ABLATION_REPORT_MISSING", codes)

    def test_ablation_fail_blocks_candidate(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_fail(slug),
        )
        self.assertEqual(result["stage_b_status"], "BLOCKED_FAMILY_ABLATION")

    def test_ablation_not_applicable_no_blocker(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_not_applicable(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertNotIn("ABLATION_FAIL", codes)
        self.assertNotIn("ABLATION_NO_MATCH", codes)

    def test_ablation_no_match_blocks_candidate(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_no_match(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("ABLATION_NO_MATCH", codes)

    def test_ablation_entry_missing_blocks_candidate(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=None,
            ablation_available=True,
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("ABLATION_ENTRY_MISSING", codes)


class TestDSRAndPBODeferred(unittest.TestCase):

    def test_dsr_approximate_blocks_to_dsr_deferred(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            {"dsr_status": "approximate_directional_only"},
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        self.assertIn(result["stage_b_status"],
                      {"BLOCKED_DSR_DEFERRED", "BLOCKED_PBO_DEFERRED"})
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("DSR_APPROXIMATE_INSUFFICIENT", codes)

    def test_pbo_always_deferred_at_stage_a(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertIn("PBO_DEFERRED", codes)
        self.assertEqual(result["pbo_status"], "Stage_B_required")

    def test_dsr_status_classified_correctly(self):
        self.assertEqual(W._classify_dsr("approximate_directional_only"), "Stage_A_approximate")
        self.assertEqual(W._classify_dsr("not_run"), "missing")
        self.assertEqual(W._classify_dsr(""), "missing")
        self.assertEqual(W._classify_dsr("nan"), "missing")

    def test_best_possible_candidate_is_blocked_dsr(self):
        # With all evidence present, best stage-A candidate cannot pass
        # because DSR is approximate and PBO is deferred
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            ledger_raw_ids={slug},
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        self.assertNotEqual(result["stage_b_status"], "PASS_STAGE_B_READY")
        self.assertIn(result["stage_b_status"],
                      {"BLOCKED_DSR_DEFERRED", "BLOCKED_PBO_DEFERRED"})


class TestStageBStatGateIntegration(unittest.TestCase):

    def test_stageb_stat_pass_clears_dsr_pbo_deferred_blockers(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            ledger_raw_ids={slug},
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
            stageb_stat_available=True,
            stageb_stat_index={
                slug: {
                    "promotion_allowed": True,
                    "status": "PASS",
                    "blocking_reasons": [],
                }
            },
        )
        self.assertEqual(result["stage_b_status"], "PASS_STAGE_B_READY")
        self.assertEqual(result["dsr_status"], "Stage_B_rigorous_PASS")
        self.assertEqual(result["pbo_status"], "Stage_B_PBO_PASS")
        self.assertTrue(result["stageb_stat_promotion_allowed"])

    def test_stageb_stat_missing_gate_blocks_fail_closed(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            ledger_raw_ids={slug},
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
            stageb_stat_available=True,
            stageb_stat_index={},
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertEqual(result["stage_b_status"], "BLOCKED_MISSING_EVIDENCE")
        self.assertIn("STAGEB_STAT_EVIDENCE_MISSING", codes)

    def test_stageb_stat_dsr_failure_maps_to_dsr_blocker(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            ledger_raw_ids={slug},
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
            stageb_stat_available=True,
            stageb_stat_index={
                slug: {
                    "promotion_allowed": False,
                    "status": "FAIL",
                    "blocking_reasons": ["DSR_RIGOROUS_FAIL"],
                }
            },
        )
        codes = [b["blocker_code"] for b in result["blockers"]]
        self.assertEqual(result["stage_b_status"], "BLOCKED_DSR_DEFERRED")
        self.assertIn("DSR_RIGOROUS_FAIL", codes)


class TestOutputSchemaKeys(unittest.TestCase):

    def test_result_dict_has_required_keys(self):
        slug = "ethusdt_4h_sac_tech_stat_s0_test"
        result = _run_classify(
            leakage_entry=_leakage_pass(slug),
            baseline_entry=_baseline_pass(slug),
            ablation_entry=_ablation_pass(slug),
        )
        required = {
            "run_slug", "stage_b_status", "hardening_classification",
            "asset", "timeframe", "algo", "preset", "seed",
            "total_return", "sharpe_ratio", "dsr_status", "pbo_status",
            "blockers", "watch_flags", "n_blockers",
            # Ledger resolution evidence
            "ledger_match_status", "ledger_match_field",
            "ledger_match_value", "ledger_run_id", "ledger_trial_id",
            # Rigorous Stage B statistical evidence
            "stageb_stat_available", "stageb_stat_promotion_allowed",
            "stageb_stat_status", "stageb_stat_blocking_reasons",
        }
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_blocker_dict_has_required_keys(self):
        result = _run_classify(leakage_available=False)
        blockers = result["blockers"]
        self.assertTrue(len(blockers) > 0)
        for b in blockers:
            for key in ("blocker_code", "blocker_message", "evidence_file",
                        "candidate_id", "next_required_artifact_or_action"):
                self.assertIn(key, b, f"Blocker missing key: {key}")

    def test_stage_b_status_is_valid(self):
        for row_overrides, extra_kwargs in [
            ({"classification": "KILL_NO_TRADES"}, {}),
            ({"classification": "KILL_NEGATIVE_SHARPE", "total_return": "0.05"}, {}),
            ({"classification": "KILL_NON_POSITIVE_RETURN"}, {}),
            ({}, {"leakage_available": False}),
        ]:
            result = _run_classify(row_overrides, **extra_kwargs)
            self.assertIn(result["stage_b_status"], W.VALID_STATUSES,
                          f"Invalid status: {result['stage_b_status']}")

    def test_json_packet_has_schema_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "packet.json"
            results = [_run_classify()]
            counts = W.count_by_status(results)
            W.write_json_packet(results, counts, out_path)
            with open(out_path) as fh:
                data = json.load(fh)
            self.assertIn("schema_version", data)
            self.assertIn("project3_heldout_start", data)
            self.assertIn("generated_at", data)
            self.assertIn("summary", data)
            self.assertIn("all_candidates", data)

    def test_json_packet_summary_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "packet.json"
            results = [_run_classify()]
            counts = W.count_by_status(results)
            W.write_json_packet(results, counts, out_path)
            with open(out_path) as fh:
                data = json.load(fh)
            summary = data["summary"]
            self.assertIn("total_candidates", summary)
            self.assertIn("status_counts", summary)
            self.assertIn("any_stage_b_ready", summary)
            self.assertIn("n_stage_b_ready", summary)


class TestMarkdownReport(unittest.TestCase):

    def test_markdown_has_top_candidates_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "packet.md"
            results = [_run_classify()]
            counts = W.count_by_status(results)
            W.write_markdown(results, counts, out_path)
            md = out_path.read_text()
            self.assertIn("Stage B Ready Candidates", md)
            self.assertIn("Blocker Summary", md)

    def test_markdown_has_status_summary_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "packet.md"
            slug = "ethusdt_4h_sac_tech_stat_s0_test"
            results = [
                _run_classify(leakage_entry=_leakage_pass(slug),
                              baseline_entry=_baseline_pass(slug),
                              ablation_entry=_ablation_pass(slug)),
                _run_classify({"classification": "KILL_NO_TRADES"}),
            ]
            counts = W.count_by_status(results)
            W.write_markdown(results, counts, out_path)
            md = out_path.read_text()
            self.assertIn("| Status | Count |", md)
            self.assertIn("KILL_NO_TRADES", md)

    def test_markdown_no_ready_message_when_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "packet.md"
            results = [_run_classify()]
            counts = W.count_by_status(results)
            W.write_markdown(results, counts, out_path)
            md = out_path.read_text()
            self.assertIn("No candidates are currently Stage B ready", md)

    def test_markdown_includes_heldout_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "packet.md"
            results = [_run_classify()]
            counts = W.count_by_status(results)
            W.write_markdown(results, counts, out_path)
            md = out_path.read_text()
            self.assertIn("2025-01-01", md)


class TestCSVOutput(unittest.TestCase):

    def test_csv_has_required_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "candidates.csv"
            results = [_run_classify(), _run_classify({"classification": "KILL_NO_TRADES"})]
            W.write_csv(results, out_path)
            df = pd.read_csv(out_path)
            for col in ("run_slug", "stage_b_status", "total_return", "sharpe_ratio",
                        "dsr_status", "pbo_status", "n_blockers", "blocker_codes",
                        "stageb_stat_status"):
                self.assertIn(col, df.columns, f"Missing column: {col}")

    def test_csv_row_count_matches_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "candidates.csv"
            results = [
                _run_classify(),
                _run_classify({"classification": "KILL_NO_TRADES"}),
                _run_classify({"classification": "KILL_NON_POSITIVE_RETURN"}),
            ]
            W.write_csv(results, out_path)
            df = pd.read_csv(out_path)
            self.assertEqual(len(df), 3)

    def test_csv_blocker_codes_semicolon_separated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "candidates.csv"
            results = [_run_classify(leakage_available=False, baseline_available=False)]
            W.write_csv(results, out_path)
            df = pd.read_csv(out_path)
            codes_str = df["blocker_codes"].iloc[0]
            # should contain multiple codes separated by semicolon
            self.assertIn(";", str(codes_str))


class TestCountByStatus(unittest.TestCase):

    def test_count_correct(self):
        results = [
            {"stage_b_status": "KILL_NO_TRADES"},
            {"stage_b_status": "KILL_NO_TRADES"},
            {"stage_b_status": "KILL_NEGATIVE_SHARPE"},
            {"stage_b_status": "BLOCKED_DSR_DEFERRED"},
        ]
        counts = W.count_by_status(results)
        self.assertEqual(counts["KILL_NO_TRADES"], 2)
        self.assertEqual(counts["KILL_NEGATIVE_SHARPE"], 1)
        self.assertEqual(counts["BLOCKED_DSR_DEFERRED"], 1)

    def test_count_empty(self):
        self.assertEqual(W.count_by_status([]), {})


class TestLedgerLoading(unittest.TestCase):

    def test_load_ledger_data_returns_dataframe(self):
        df, err = W.load_ledger_data()
        if err:
            self.skipTest(f"Ledger unavailable in test env: {err}")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)

    def test_load_ledger_missing_returns_error(self):
        import unittest.mock as mock
        with mock.patch.object(W, "LEDGER_PARQUET", Path("/nonexistent/ledger.parquet")), \
             mock.patch.object(W, "LEDGER_JSONL", Path("/nonexistent/ledger.jsonl")):
            df, err = W.load_ledger_data()
        self.assertNotEqual(err, "")
        self.assertIsNone(df)

    def test_build_ledger_indexes_from_real_ledger(self):
        df, err = W.load_ledger_data()
        if err:
            self.skipTest(f"Ledger unavailable: {err}")
        raw_ids, composite = W.build_ledger_indexes(df)
        self.assertIsInstance(raw_ids, set)
        self.assertIsInstance(composite, dict)
        self.assertGreater(len(raw_ids), 0)
        self.assertGreater(len(composite), 0)


class TestLedgerResolution(unittest.TestCase):
    """Tests for resolve_ledger_membership() — exact and composite matching."""

    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def _make_ledger_row(self, asset, timeframe, algo, preset, seed,
                         run_id=None, trial_id=None, event_type="complete") -> dict:
        return {
            "asset": asset,
            "timeframe": timeframe,
            "algorithm": algo,
            "feature_preset": preset,
            "seed": seed,
            "run_id": run_id or f"{asset}_{timeframe}_{preset}_{algo}_s{seed}_50000",
            "trial_id": trial_id or "deadbeef0123456789abcdef",
            "event_type": event_type,
        }

    def test_exact_run_id_match(self):
        """Slug appears verbatim as a run_id in the ledger."""
        slug = "my_exact_run_id"
        raw_ids = {slug, "other_run"}
        composite = {}
        result = W.resolve_ledger_membership(
            slug, "ethusdt", "4h", "sac", "tech_stat", 0, raw_ids, composite
        )
        self.assertTrue(result["matched"])
        self.assertEqual(result["ledger_match_field"], W._MATCH_RUN_ID)
        self.assertEqual(result["ledger_match_value"], slug)
        self.assertEqual(result["ledger_match_status"], "MATCHED")

    def test_exact_trial_id_in_raw_ids_matches(self):
        """trial_ids are stored in raw_ids alongside run_ids; an exact match works."""
        trial_id = "abc123def456"
        raw_ids = {trial_id}
        composite = {}
        result = W.resolve_ledger_membership(
            trial_id, "ethusdt", "4h", "sac", "tech_stat", 0, raw_ids, composite
        )
        self.assertTrue(result["matched"])
        self.assertEqual(result["ledger_match_field"], W._MATCH_RUN_ID)

    def test_composite_key_match_clears_ledger_blocker(self):
        """Composite (asset, timeframe, algo, preset, seed) match resolves successfully."""
        df = self._make_df([
            self._make_ledger_row("ethusdt", "4h", "sac", "tech_stat", 0,
                                  run_id="ethusdt_4h_tech_stat_sac_s0_50000",
                                  trial_id="c76965f79c5dad1ca8bee650")
        ])
        raw_ids, composite = W.build_ledger_indexes(df)
        slug = "ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3"
        result = W.resolve_ledger_membership(
            slug, "ethusdt", "4h", "sac", "tech_stat", "0", raw_ids, composite
        )
        self.assertTrue(result["matched"])
        self.assertEqual(result["ledger_match_field"], W._MATCH_COMPOSITE)
        self.assertEqual(result["ledger_run_id"], "ethusdt_4h_tech_stat_sac_s0_50000")
        self.assertEqual(result["ledger_trial_id"], "c76965f79c5dad1ca8bee650")

    def test_composite_key_prefers_complete_event(self):
        """When multiple events exist for the same composite key, complete wins."""
        df = self._make_df([
            self._make_ledger_row("ethusdt", "4h", "sac", "tech_stat", 0,
                                  run_id="run_training", event_type="training"),
            self._make_ledger_row("ethusdt", "4h", "sac", "tech_stat", 0,
                                  run_id="run_complete", event_type="complete"),
        ])
        raw_ids, composite = W.build_ledger_indexes(df)
        result = W.resolve_ledger_membership(
            "any_slug", "ethusdt", "4h", "sac", "tech_stat", "0", raw_ids, composite
        )
        self.assertTrue(result["matched"])
        self.assertEqual(result["ledger_run_id"], "run_complete")

    def test_no_match_returns_not_matched(self):
        """When neither raw IDs nor composite key match, result is NOT_MATCHED."""
        raw_ids = {"some_other_slug"}
        composite = {("btcusdt", "4h", "sac", "tech_stat", 0): [{"run_id": "x"}]}
        result = W.resolve_ledger_membership(
            "ethusdt_4h_sac_tech_stat_s0_test", "ethusdt", "4h", "sac", "tech_stat", 0,
            raw_ids, composite
        )
        self.assertFalse(result["matched"])
        self.assertEqual(result["ledger_match_status"], "NOT_MATCHED")
        self.assertEqual(result["ledger_match_field"], W._MATCH_NONE)
        self.assertEqual(result["ledger_run_id"], "")
        self.assertEqual(result["ledger_trial_id"], "")

    def test_no_false_positive_different_seed(self):
        """Seed=1 entry does NOT match a seed=0 query."""
        df = self._make_df([
            self._make_ledger_row("ethusdt", "4h", "sac", "tech_stat", 1,
                                  run_id="ethusdt_4h_tech_stat_sac_s1_50000")
        ])
        raw_ids, composite = W.build_ledger_indexes(df)
        result = W.resolve_ledger_membership(
            "ethusdt_4h_sac_tech_stat_s0_test", "ethusdt", "4h", "sac", "tech_stat", 0,
            raw_ids, composite
        )
        self.assertFalse(result["matched"])

    def test_no_false_positive_different_algo(self):
        """A PPO entry does NOT match an SAC query."""
        df = self._make_df([
            self._make_ledger_row("ethusdt", "4h", "ppo", "tech_stat", 0,
                                  run_id="ethusdt_4h_tech_stat_ppo_s0_50000")
        ])
        raw_ids, composite = W.build_ledger_indexes(df)
        result = W.resolve_ledger_membership(
            "any_slug", "ethusdt", "4h", "sac", "tech_stat", 0, raw_ids, composite
        )
        self.assertFalse(result["matched"])

    def test_no_false_positive_different_preset(self):
        """A tech_full entry does NOT match a tech_stat query."""
        df = self._make_df([
            self._make_ledger_row("ethusdt", "4h", "sac", "tech_full", 0)
        ])
        raw_ids, composite = W.build_ledger_indexes(df)
        result = W.resolve_ledger_membership(
            "any_slug", "ethusdt", "4h", "sac", "tech_stat", 0, raw_ids, composite
        )
        self.assertFalse(result["matched"])

    def test_best_run_slug_matches_via_composite_key_real_ledger(self):
        """Integration: the actual best Stage A run slug resolves via composite key."""
        df, err = W.load_ledger_data()
        if err:
            self.skipTest(f"Ledger unavailable: {err}")
        raw_ids, composite = W.build_ledger_indexes(df)
        best_slug = (
            "ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_"
            "20260502T051413Z_project3_stage31_firstwave"
        )
        result = W.resolve_ledger_membership(
            best_slug,
            asset="ethusdt", timeframe="4h", algo="sac", preset="tech_stat", seed="0",
            raw_ids=raw_ids, composite_index=composite,
        )
        self.assertTrue(result["matched"],
                        f"Best run slug should match via composite key, got: {result}")
        self.assertEqual(result["ledger_match_field"], W._MATCH_COMPOSITE)
        self.assertNotEqual(result["ledger_run_id"], "")
        self.assertNotEqual(result["ledger_trial_id"], "")

    def test_resolve_returns_all_required_keys(self):
        """resolve_ledger_membership always returns all 6 required keys."""
        result = W.resolve_ledger_membership(
            "x", "a", "b", "c", "d", 0, set(), {}
        )
        for key in ("matched", "ledger_match_status", "ledger_match_field",
                    "ledger_match_value", "ledger_run_id", "ledger_trial_id"):
            self.assertIn(key, result, f"Missing key: {key}")


class TestSafeHelpers(unittest.TestCase):

    def test_safe_float_valid(self):
        self.assertEqual(W._safe_float("1.5"), 1.5)
        self.assertEqual(W._safe_float(0), 0.0)

    def test_safe_float_invalid(self):
        self.assertIsNone(W._safe_float("not_a_number"))
        self.assertIsNone(W._safe_float(None))
        self.assertIsNone(W._safe_float(float("nan")))
        self.assertIsNone(W._safe_float(float("inf")))

    def test_safe_bool(self):
        self.assertTrue(W._safe_bool(True))
        self.assertTrue(W._safe_bool("True"))
        self.assertTrue(W._safe_bool("true"))
        self.assertFalse(W._safe_bool(False))
        self.assertFalse(W._safe_bool("false"))
        self.assertIsNone(W._safe_bool(None))


class TestStatusValidSet(unittest.TestCase):

    def test_all_valid_statuses_defined(self):
        expected = {
            "PASS_STAGE_B_READY",
            "FAIL_ECONOMIC_OR_STATISTICAL",
            "BLOCKED_MISSING_EVIDENCE",
            "BLOCKED_LEDGER_ABSENT",
            "BLOCKED_LEAKAGE_AUDIT",
            "BLOCKED_HELDOUT_FIREWALL",
            "BLOCKED_BASELINE_COMPARISON",
            "BLOCKED_FAMILY_ABLATION",
            "BLOCKED_DSR_DEFERRED",
            "BLOCKED_PBO_DEFERRED",
            "KILL_NO_TRADES",
            "KILL_NEGATIVE_SHARPE",
            "KILL_NON_POSITIVE_RETURN",
        }
        self.assertEqual(W.VALID_STATUSES, expected)

    def test_final_always_asserts_valid_status(self):
        # _final should not accept an unknown status
        with self.assertRaises(AssertionError):
            W._final(
                "slug", "INVALID_STATUS",
                _row(), [], [], "missing", "Stage_B_required", "PROMOTE_BLOCKED_HARDENING"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
