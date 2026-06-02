from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_absurdity_guard_worker as W


class TestStage3xAbsurdityGuardWorker(unittest.TestCase):

    def test_blocks_broad_gpu_when_no_stage_b_candidate_passes(self):
        fake = {
            W.STAT_REPORT: {
                "summary": {
                    "stage_c_allowed": False,
                    "candidate_gate_pass": 0,
                    "candidate_gate_fail": 10,
                    "dsr_fail_n_raw": 10,
                }
            },
            W.ACTION_AUDIT: {
                "feature_list_hash_missing_candidates": 0,
                "largest_identical_performance_group": 0,
            },
            W.DECISION_READINESS: {"cluster_summary": {"counts": {"running": 0}}},
            W.INPUT_PLAN: {"ok": True},
            W.PARAMETRIC_SCHEMA: {"ok": True},
            W.SELECTED_CONTRACTS: {"contracts": [{"contract_id": "c0"}]},
        }

        with patch.object(W, "load_json", side_effect=lambda path: fake.get(path, {})):
            payload = W.build_report()
        self.assertFalse(payload["broad_gpu_launch_allowed"])
        self.assertTrue(payload["small_sac_smoke_allowed"])
        self.assertIn("NO_STAGE_B_PROMOTION", {row["code"] for row in payload["issues"]})

    def test_stage_c_allowed_before_promotion_is_fatal(self):
        fake = {
            W.STAT_REPORT: {
                "summary": {
                    "stage_c_allowed": True,
                    "candidate_gate_pass": 0,
                    "candidate_gate_fail": 10,
                }
            },
            W.ACTION_AUDIT: {},
            W.DECISION_READINESS: {},
            W.INPUT_PLAN: {"ok": True},
            W.PARAMETRIC_SCHEMA: {"ok": True},
            W.SELECTED_CONTRACTS: {"contracts": [{"contract_id": "c0"}]},
        }

        with patch.object(W, "load_json", side_effect=lambda path: fake.get(path, {})):
            payload = W.build_report()
        self.assertTrue(payload["fatal_issue_present"])
        self.assertFalse(payload["broad_gpu_launch_allowed"])

    def test_allows_broad_gpu_when_required_guards_clear(self):
        fake = {
            W.STAT_REPORT: {
                "summary": {
                    "stage_c_allowed": False,
                    "candidate_gate_pass": 1,
                    "candidate_gate_fail": 0,
                }
            },
            W.ACTION_AUDIT: {
                "feature_list_hash_missing_candidates": 0,
                "largest_identical_performance_group": 1,
            },
            W.DECISION_READINESS: {"cluster_summary": {"counts": {"running": 0}}},
            W.INPUT_PLAN: {"ok": True},
            W.PARAMETRIC_SCHEMA: {"ok": True},
            W.SELECTED_CONTRACTS: {"contracts": [{"contract_id": "c0"}]},
        }

        with patch.object(W, "load_json", side_effect=lambda path: fake.get(path, {})):
            payload = W.build_report()
        self.assertTrue(payload["broad_gpu_launch_allowed"])
        self.assertTrue(payload["small_sac_smoke_allowed"])
        self.assertEqual(payload["issue_count"], 0)

    def test_missing_selected_contracts_blocks_smoke_only(self):
        fake = {
            W.STAT_REPORT: {
                "summary": {
                    "stage_c_allowed": False,
                    "candidate_gate_pass": 1,
                    "candidate_gate_fail": 0,
                }
            },
            W.ACTION_AUDIT: {},
            W.DECISION_READINESS: {"cluster_summary": {"counts": {"running": 0}}},
            W.INPUT_PLAN: {"ok": True},
            W.PARAMETRIC_SCHEMA: {"ok": True},
            W.SELECTED_CONTRACTS: {"contracts": []},
        }

        with patch.object(W, "load_json", side_effect=lambda path: fake.get(path, {})):
            payload = W.build_report()
        self.assertFalse(payload["small_sac_smoke_allowed"])
        self.assertIn("MISSING_SELECTED_FEATURE_CONTRACTS", {row["code"] for row in payload["issues"]})


if __name__ == "__main__":
    unittest.main()
