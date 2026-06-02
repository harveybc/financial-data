"""Tests for the Stage B feature/action diagnostic audit worker.

These tests pin the four properties the post-no-promotion spec calls out:

1. non-finite diagnostic scores get sanitized to a default;
2. identical action/performance signatures across distinct data hashes are
   flagged through ``identical_performance_signature_groups`` and
   ``largest_identical_performance_group``;
3. missing ``feature_list_hash`` surfaces as a warning, never as a Stage C
   pass — ``stage_c_allowed`` stays ``False``;
4. baseline / no-trade candidates cannot rise above trade-clean candidates in
   the diagnostic ranking that this audit consumes.
"""
from __future__ import annotations

import csv
import hashlib
import importlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"
sys.path.insert(0, str(WORKERS_DIR))


def _load_audit_module():
    if "stage_b_feature_action_audit_worker" in sys.modules:
        importlib.reload(sys.modules["stage_b_feature_action_audit_worker"])
    import stage_b_feature_action_audit_worker as audit  # type: ignore
    return audit


def _load_ranker_module():
    if "stage_b_diagnostic_ranker_worker" in sys.modules:
        importlib.reload(sys.modules["stage_b_diagnostic_ranker_worker"])
    import stage_b_diagnostic_ranker_worker as ranker  # type: ignore
    return ranker


def _trace_field_names() -> list[str]:
    return [
        "step", "timestamp", "asset", "timeframe", "split", "episode_id",
        "run_id", "seed", "bar_index", "price", "action_raw", "position",
        "reward", "gross_return", "net_return", "equity", "pnl",
        "commission_paid", "slippage_paid", "trade_cost", "trades",
    ]


def _write_trace_csv(path: Path, rows: list[dict[str, object]]) -> str:
    fields = _trace_field_names()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _trace_entry(path: Path, sha: str, split: str = "test") -> dict[str, object]:
    return {
        "split": split,
        "trace_file": str(path),
        "trace_file_sha256": sha,
        "metadata_file": "",
        "row_count": 0,
        "first_timestamp": "",
        "last_timestamp": "",
        "contains_heldout_rows": False,
        "stage_c_authorized": False,
    }


def _build_minimal_stat_report(
    *,
    candidate_slugs: list[str],
    blocking_by_slug: dict[str, list[str]] | None = None,
    feature_hash_by_slug: dict[str, str | None] | None = None,
    mean_return_by_slug: dict[str, float] | None = None,
    inject_record_trade_blockers: dict[str, list[str]] | None = None,
    data_file_by_slug: dict[str, str] | None = None,
    data_hash_by_slug: dict[str, str] | None = None,
    trace_entries_by_slug: dict[str, list[dict[str, object]]] | None = None,
    evidence_file_by_slug: dict[str, str] | None = None,
) -> dict[str, object]:
    """Synthesize the minimum fields the audit and ranker workers consume."""
    records = []
    candidate_gates = {}
    seed_uncertainty = {}
    blocking_by_slug = blocking_by_slug or {}
    feature_hash_by_slug = feature_hash_by_slug or {}
    mean_return_by_slug = mean_return_by_slug or {}
    inject_record_trade_blockers = inject_record_trade_blockers or {}
    data_file_by_slug = data_file_by_slug or {}
    data_hash_by_slug = data_hash_by_slug or {}
    trace_entries_by_slug = trace_entries_by_slug or {}
    evidence_file_by_slug = evidence_file_by_slug or {}
    for slug in candidate_slugs:
        seed_uncertainty[f"{slug}|base"] = {"status": "PASS", "n_seeds": 5}
        blockers = blocking_by_slug.get(slug, [])
        candidate_gates[slug] = {
            "candidate_slug": slug,
            "promotion_allowed": False,
            "status": "FAIL",
            "blocking_reasons": blockers,
            "cost_scenarios_present": ["base"],
            "record_count": 1,
            "records": [slug + "_base"],
        }
        trade_blockers = inject_record_trade_blockers.get(slug, [])
        records.append({
            "run_id": slug + "_base",
            "evidence_status": "PASS",
            "candidate_slug": slug,
            "cost_scenario": "base",
            "asset": "ethusdt",
            "timeframe": "4h",
            "algo": "sac",
            "preset": "",
            "seed": 0,
            "is_baseline": False,
            "data_file": data_file_by_slug.get(slug, ""),
            "data_file_hash": data_hash_by_slug.get(slug, f"hash-{slug}"),
            "evidence_file": evidence_file_by_slug.get(slug, ""),
            "feature_list_hash": feature_hash_by_slug.get(slug),
            "sr_period": 0.001,
            "n_returns": 100,
            "trace_entries": trace_entries_by_slug.get(slug, []),
            "trade_gate": {
                "status": "PASS" if not trade_blockers else "FAIL",
                "blockers": trade_blockers,
                "trades_total": 100 if not trade_blockers else 0,
                "years": 1.0,
                "trades_per_year": 100.0 if not trade_blockers else 0.0,
                "exposure_fraction": 0.5,
                "total_return_from_trace": mean_return_by_slug.get(slug, 0.001),
            },
            "dsr_n_raw": {"status": "FAIL", "dsr_p_value": 0.4},
        })
    return {
        "summary": {"evidence_files": len(records)},
        "records": records,
        "candidate_gates": candidate_gates,
        "family_tests": {},
        "pbo_groups": {},
        "seed_uncertainty": seed_uncertainty,
    }


def _build_minimal_ranking(rows: list[dict[str, object]]) -> dict[str, object]:
    """Audit worker consumes only ``rows[*].candidate_slug``, ``diagnostic_rank``,
    ``diagnostic_score``, ``blocking_reasons``, ``mean_return``, ``min_return``,
    and ``mean_sharpe``."""
    return {"rows": rows}


class TestSafeFloatAndEntropy(unittest.TestCase):

    def test_safe_float_clamps_nan_and_inf_to_default(self):
        audit = _load_audit_module()
        self.assertEqual(audit.safe_float(float("nan")), 0.0)
        self.assertEqual(audit.safe_float(float("inf")), 0.0)
        self.assertEqual(audit.safe_float(float("-inf")), 0.0)
        self.assertEqual(audit.safe_float("not-a-number", default=-1.0), -1.0)
        self.assertEqual(audit.safe_float("3.5"), 3.5)

    def test_shannon_entropy_bits_on_uniform_two_bin_distribution(self):
        from collections import Counter
        audit = _load_audit_module()
        # Two equally likely buckets → 1 bit of entropy.
        self.assertAlmostEqual(audit._shannon_entropy_bits(Counter({-1.0: 10, 1.0: 10})), 1.0, places=6)
        # Constant action → 0 bits.
        self.assertEqual(audit._shannon_entropy_bits(Counter({0.0: 50})), 0.0)
        # Empty → 0 bits (no division by zero).
        self.assertEqual(audit._shannon_entropy_bits(Counter()), 0.0)


class TestTraceActionSummary(unittest.TestCase):

    def test_friday_late_exposure_and_flip_rate_are_computed(self):
        audit = _load_audit_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            trace = Path(tmpdir) / "test_return_trace.csv"
            # 2024-01-05 is a Friday. Rows alternate position 0/1 every bar,
            # creating consistent flips. Add a Friday-late bar with exposure.
            rows = [
                {"timestamp": "2024-01-05 12:00:00", "split": "test", "episode_id": "e0",
                 "action_raw": 0.0, "position": 0.0, "reward": 0.0, "net_return": 0.0,
                 "trades": 0, "equity": 1000.0},
                {"timestamp": "2024-01-05 16:00:00", "split": "test", "episode_id": "e0",
                 "action_raw": 1.0, "position": 1.0, "reward": 0.0, "net_return": 0.0,
                 "trades": 1, "equity": 1000.0},
                {"timestamp": "2024-01-05 20:00:00", "split": "test", "episode_id": "e0",
                 "action_raw": -1.0, "position": 0.0, "reward": 0.0, "net_return": 0.0,
                 "trades": 2, "equity": 1000.0},
                {"timestamp": "2024-01-06 00:00:00", "split": "test", "episode_id": "e0",
                 "action_raw": 1.0, "position": 1.0, "reward": 0.0, "net_return": 0.0,
                 "trades": 3, "equity": 1000.0},
            ]
            sha = _write_trace_csv(trace, rows)
            summary = audit.trace_action_summary([_trace_entry(trace, sha, "test")])
            self.assertEqual(summary["oos_row_count"], 4)
            # Friday-late bars: the two bars at Friday >=16:00.
            self.assertEqual(summary["friday_late_bar_count"], 2)
            # Of those, one has position != 0 (the 16:00 bar).
            self.assertEqual(summary["friday_late_exposed_bars"], 1)
            self.assertAlmostEqual(summary["friday_late_exposure_fraction"], 0.5)
            # Three position flips across 4 bars → flip rate 0.75.
            self.assertEqual(summary["position_changes"], 3)
            self.assertAlmostEqual(summary["position_flip_rate"], 0.75)
            # Action entropy non-zero given 3 distinct rounded actions.
            self.assertGreater(summary["action_entropy_bits_rounded_4dp"], 1.0)


class TestBuildRowsAuditProperties(unittest.TestCase):

    def _run_build_rows(self, tmpdir: Path, *, ranking: dict, stat: dict) -> tuple[list[dict], dict]:
        audit = _load_audit_module()
        ranking_path = tmpdir / "stage_b_diagnostic_candidate_ranking.json"
        stat_path = tmpdir / "stageb_dsr_pbo_report.json"
        ranking_path.write_text(json.dumps(ranking), encoding="utf-8")
        stat_path.write_text(json.dumps(stat), encoding="utf-8")
        audit.RANKING = ranking_path
        audit.STAT_REPORT = stat_path
        return audit.build_rows()

    def test_identical_performance_signatures_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            slugs = ["x_full_candidate", "x_reduced_candidate", "x_momentum_candidate"]
            ranking_rows = []
            for idx, slug in enumerate(slugs, start=1):
                ranking_rows.append({
                    "diagnostic_rank": idx,
                    "candidate_slug": slug,
                    "diagnostic_score": 23.75,
                    "blocking_reasons": "DSR_RIGOROUS_FAIL",
                    "mean_return": 0.002380,
                    "min_return": -0.016487,
                    "mean_sharpe": 0.000839,
                })
            stat = _build_minimal_stat_report(
                candidate_slugs=slugs,
                blocking_by_slug={s: ["DSR_RIGOROUS_FAIL"] for s in slugs},
                # Distinct data hashes so the run plan didn't collapse to one file.
                data_hash_by_slug={s: f"hash-{i}" for i, s in enumerate(slugs)},
            )
            rows, summary = self._run_build_rows(tmp, ranking=_build_minimal_ranking(ranking_rows), stat=stat)
            self.assertEqual(summary["audited_candidates"], 3)
            self.assertEqual(summary["distinct_data_hashes"], 3)
            self.assertGreaterEqual(summary["identical_performance_signature_groups"], 1)
            self.assertEqual(summary["largest_identical_performance_group"], 3)

    def test_missing_feature_list_hash_emits_warning_not_stage_c_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            slugs = ["candidate_a_candidate", "candidate_b_candidate"]
            ranking_rows = [
                {"diagnostic_rank": i, "candidate_slug": slug, "diagnostic_score": 1.0 - 0.1 * i,
                 "blocking_reasons": "DSR_RIGOROUS_FAIL", "mean_return": 0.0,
                 "min_return": 0.0, "mean_sharpe": 0.0}
                for i, slug in enumerate(slugs, start=1)
            ]
            stat = _build_minimal_stat_report(
                candidate_slugs=slugs,
                # First slug has no hash, second has one — partial-missing case.
                feature_hash_by_slug={"candidate_a_candidate": None, "candidate_b_candidate": "abc"},
            )
            rows, summary = self._run_build_rows(tmp, ranking=_build_minimal_ranking(ranking_rows), stat=stat)
            self.assertFalse(summary["stage_c_allowed"])
            self.assertGreaterEqual(summary["feature_list_hash_missing_candidates"], 1)
            self.assertTrue(any("feature_list_hash" in w for w in summary["warnings"]))
            # The row for the candidate without a hash must flag it as missing.
            missing_row = next(r for r in rows if r["candidate_slug"] == "candidate_a_candidate")
            self.assertTrue(missing_row["feature_list_hash_missing"])
            present_row = next(r for r in rows if r["candidate_slug"] == "candidate_b_candidate")
            self.assertFalse(present_row["feature_list_hash_missing"])

    def test_paired_calendar_compare_flags_identical_signature(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            non_cal = "ethusdt_4h_sac_tech_stat_full_candidate"
            cal = "ethusdt_4h_sac_tech_stat_full_plus_session_calendar_candidate"
            ranking_rows = [
                {"diagnostic_rank": 1, "candidate_slug": non_cal, "diagnostic_score": 5.0,
                 "blocking_reasons": "DSR_RIGOROUS_FAIL", "mean_return": 0.001,
                 "min_return": -0.01, "mean_sharpe": 0.0005},
                {"diagnostic_rank": 2, "candidate_slug": cal, "diagnostic_score": 5.0,
                 "blocking_reasons": "DSR_RIGOROUS_FAIL", "mean_return": 0.001,
                 "min_return": -0.01, "mean_sharpe": 0.0005},
            ]
            stat = _build_minimal_stat_report(
                candidate_slugs=[non_cal, cal],
                feature_hash_by_slug={non_cal: "hash-A", cal: "hash-B"},
            )
            rows, summary = self._run_build_rows(tmp, ranking=_build_minimal_ranking(ranking_rows), stat=stat)
            self.assertEqual(summary["paired_calendar_pairs_count"], 1)
            self.assertEqual(summary["paired_calendar_identical_signature_count"], 1)
            self.assertTrue(any("calendar" in w.lower() for w in summary["warnings"]))

    def test_force_close_obs_slug_is_audited_even_outside_top_n(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            base = "ethusdt_4h_sac_tech_stat_full_candidate"
            cal = "ethusdt_4h_sac_tech_stat_full_plus_session_calendar_candidate"
            force = "ethusdt_4h_sac_tech_stat_full_plus_force_close_obs_candidate"
            filler = [f"filler_{i}_candidate" for i in range(20)]
            ranking_rows = [
                {"diagnostic_rank": 1, "candidate_slug": base, "diagnostic_score": 10.0,
                 "blocking_reasons": "DSR_RIGOROUS_FAIL", "mean_return": 0.001,
                 "min_return": -0.01, "mean_sharpe": 0.0005},
                {"diagnostic_rank": 2, "candidate_slug": cal, "diagnostic_score": 10.0,
                 "blocking_reasons": "DSR_RIGOROUS_FAIL", "mean_return": 0.001,
                 "min_return": -0.01, "mean_sharpe": 0.0005},
            ]
            for idx, slug in enumerate(filler, start=3):
                ranking_rows.append({
                    "diagnostic_rank": idx, "candidate_slug": slug, "diagnostic_score": 9.0,
                    "blocking_reasons": "DSR_RIGOROUS_FAIL", "mean_return": 0.0,
                    "min_return": -0.01, "mean_sharpe": 0.0,
                })
            ranking_rows.append({
                "diagnostic_rank": 30, "candidate_slug": force, "diagnostic_score": 1.0,
                "blocking_reasons": "DSR_RIGOROUS_FAIL", "mean_return": 0.002,
                "min_return": -0.02, "mean_sharpe": 0.0001,
            })

            base_trace = tmp / "base.csv"
            force_trace = tmp / "force.csv"
            base_sha = _write_trace_csv(base_trace, [
                {"timestamp": "2024-01-05 16:00:00", "split": "test", "episode_id": "e0",
                 "action_raw": 0.1, "position": 1.0, "reward": 0.0, "net_return": 0.0,
                 "trades": 1, "equity": 1000.0},
                {"timestamp": "2024-01-05 20:00:00", "split": "test", "episode_id": "e0",
                 "action_raw": 0.1, "position": 1.0, "reward": 0.0, "net_return": 0.0,
                 "trades": 1, "equity": 1000.0},
            ])
            force_sha = _write_trace_csv(force_trace, [
                {"timestamp": "2024-01-05 16:00:00", "split": "test", "episode_id": "e0",
                 "action_raw": -0.5, "position": 0.0, "reward": 0.0, "net_return": 0.0,
                 "trades": 2, "equity": 1000.0},
                {"timestamp": "2024-01-05 20:00:00", "split": "test", "episode_id": "e0",
                 "action_raw": 0.5, "position": 0.0, "reward": 0.0, "net_return": 0.0,
                 "trades": 2, "equity": 1000.0},
            ])
            evidence = tmp / "force_evidence.json"
            evidence.write_text(json.dumps({
                "observation_state_hash": "a" * 64,
                "observation_state_fields": [
                    "prices",
                    "bars_to_force_close",
                    "hours_to_force_close",
                    "is_force_close_zone",
                    "is_monday_entry_window",
                ],
            }), encoding="utf-8")
            stat = _build_minimal_stat_report(
                candidate_slugs=[base, cal, force],
                feature_hash_by_slug={base: "hash-A", cal: "hash-B", force: "hash-C"},
                trace_entries_by_slug={
                    base: [_trace_entry(base_trace, base_sha, "test")],
                    cal: [_trace_entry(base_trace, base_sha, "test")],
                    force: [_trace_entry(force_trace, force_sha, "test")],
                },
                evidence_file_by_slug={force: str(evidence)},
            )
            rows, summary = self._run_build_rows(tmp, ranking=_build_minimal_ranking(ranking_rows), stat=stat)
            self.assertIn(force, {row["candidate_slug"] for row in rows})
            self.assertEqual(summary["force_close_obs_pairs_count"], 2)
            self.assertEqual(summary["force_close_obs_behavior_changed_count"], 2)
            self.assertEqual(summary["force_close_obs_friday_exposure_improved_count"], 2)
            self.assertTrue(summary["force_close_obs_contract_ok"])
            force_row = next(row for row in rows if row["candidate_slug"] == force)
            self.assertTrue(force_row["force_close_obs_contract_ok"])


class TestDiagnosticRankerProperties(unittest.TestCase):

    def test_trade_clean_outranks_no_trade_with_higher_score(self):
        ranker = _load_ranker_module()
        # No-trade candidate has higher mean_return but FINAL_NO_TRADES blocker.
        stat = _build_minimal_stat_report(
            candidate_slugs=["lucky_holder_candidate", "honest_trader_candidate"],
            blocking_by_slug={
                "lucky_holder_candidate": ["FINAL_NO_TRADES", "DSR_RIGOROUS_FAIL"],
                "honest_trader_candidate": ["DSR_RIGOROUS_FAIL"],
            },
            mean_return_by_slug={
                "lucky_holder_candidate": 0.50,   # Big number; would dominate score.
                "honest_trader_candidate": 0.005,
            },
            inject_record_trade_blockers={
                "lucky_holder_candidate": ["FINAL_NO_TRADES"],
            },
        )
        rows = ranker.build_rows(stat)
        self.assertEqual(rows[0]["candidate_slug"], "honest_trader_candidate")
        self.assertEqual(rows[1]["candidate_slug"], "lucky_holder_candidate")
        # Trade-clean flag persisted into the row.
        self.assertTrue(rows[0]["trade_clean"])
        self.assertFalse(rows[1]["trade_clean"])

    def test_non_finite_inputs_sanitized_to_finite_score(self):
        ranker = _load_ranker_module()
        stat = _build_minimal_stat_report(candidate_slugs=["c_candidate"])
        # Corrupt the synthetic record with nan/inf in places the ranker reads.
        rec = stat["records"][0]
        rec["sr_period"] = float("nan")
        rec["trade_gate"]["total_return_from_trace"] = float("inf")
        rec["dsr_n_raw"]["dsr_p_value"] = float("-inf")
        rows = ranker.build_rows(stat)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(math.isfinite(row["diagnostic_score"]))
        self.assertTrue(math.isfinite(row["mean_return"]))
        self.assertTrue(math.isfinite(row["mean_sharpe"]))
        self.assertTrue(math.isfinite(row["best_dsr_p_value"]))


if __name__ == "__main__":
    unittest.main()
