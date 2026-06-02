from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage_b_pragmatic_root_cause_worker as W


class TestPragmaticRootCauseWorker(unittest.TestCase):

    def test_blocker_classification_core_cases(self):
        self.assertEqual(W.blocker_class("DSR_RIGOROUS_FAIL"), "statistical_non_significance")
        self.assertEqual(W.blocker_class("SEED_UNCERTAINTY_BLOCKED"), "insufficient_repetitions")
        self.assertEqual(W.blocker_class("FINAL_EXCESSIVE_TRADES_HARD"), "trade_behavior_failure")
        self.assertEqual(W.blocker_class("MISSING_COST_SCENARIO"), "infrastructure_missing")
        self.assertEqual(W.blocker_class("ABLATION_FAIL"), "feature_family_failure")

    def test_trade_rows_extract_flags(self):
        stat = {
            "records": [{
                "run_id": "r1",
                "candidate_slug": "c1",
                "cost_scenario": "base",
                "trade_gate": {
                    "trades_total": 0,
                    "years": 1,
                    "trades_per_year": 0,
                    "exposure_fraction": 0,
                    "total_return_from_trace": 0,
                    "status": "FAIL",
                    "blockers": ["FINAL_NO_TRADES"],
                    "warnings": [],
                },
            }]
        }
        rows = W.build_trade_rows(stat)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["no_trade_flag"])
        self.assertFalse(rows[0]["excessive_trade_flag"])

    def test_cost_rows_detect_missing_required_cost(self):
        stat = {
            "records": [{
                "candidate_slug": "c1",
                "is_baseline": False,
                "cost_scenario": "base",
                "trade_gate": {"total_return_from_trace": 0.1},
                "trace_entries": [],
            }]
        }
        rows = W.build_cost_rows(stat)
        self.assertEqual(rows[0]["missing_accepted_costs"], "plus_50pct;plus_100pct")
        self.assertTrue(rows[0]["cost_fragility_flag"])

    def test_cost_rows_accept_pragmatic_contract_without_pessimistic(self):
        stat = {
            "records": [
                {
                    "candidate_slug": "c1",
                    "is_baseline": False,
                    "cost_scenario": "base",
                    "trade_gate": {"total_return_from_trace": 0.1},
                    "trace_entries": [],
                },
                {
                    "candidate_slug": "c1",
                    "is_baseline": False,
                    "cost_scenario": "plus_50pct",
                    "trade_gate": {"total_return_from_trace": 0.08},
                    "trace_entries": [],
                },
                {
                    "candidate_slug": "c1",
                    "is_baseline": False,
                    "cost_scenario": "plus_100pct",
                    "trade_gate": {"total_return_from_trace": 0.07},
                    "trace_entries": [],
                },
            ]
        }
        rows = W.build_cost_rows(stat)
        self.assertEqual(rows[0]["accepted_cost_contract_status"], "PASS")
        self.assertEqual(rows[0]["missing_accepted_costs"], "")
        self.assertFalse(rows[0]["cost_fragility_flag"])

    def test_approval_blocker_counts_reads_nested_blockers(self):
        approval = {
            "all_candidates": [
                {"blockers": [{"blocker_code": "NO_TRADES"}, {"blocker_code": "NO_TRADES"}]},
                {"blockers": [{"blocker_code": "BASELINE_FAIL"}]},
            ]
        }
        counts = W.approval_blocker_counts(approval)
        self.assertEqual(counts["NO_TRADES"], 2)
        self.assertEqual(counts["BASELINE_FAIL"], 1)


if __name__ == "__main__":
    unittest.main()
