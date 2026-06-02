from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage_b_decision_readiness_worker as W


class TestStageBDecisionReadiness(unittest.TestCase):

    def test_stage_c_blocked_when_no_statistical_gate_passes(self):
        payload = W.build_readiness(
            stat={
                "summary": {
                    "stage_c_allowed": False,
                    "stage_c_blocked_reason": "NO_STAGE_B_CANDIDATE_PASSED_ALL_STATISTICAL_GATES",
                    "candidate_gate_pass": 0,
                    "candidate_gate_fail": 2,
                    "evidence_pass": 2,
                    "evidence_fail": 0,
                },
                "candidate_gates": {
                    "a": {"blocking_reasons": ["DSR_RIGOROUS_FAIL"]},
                    "b": {"blocking_reasons": ["SEED_UNCERTAINTY_BLOCKED"]},
                },
            },
            approval={
                "summary": {"n_stage_b_ready": 0},
                "all_candidates": [],
                "top_blocked_by_return": [],
            },
            cluster={"counts": {"running": 0}, "all_queries_ok": True},
            run_plan={"rows": []},
        )
        self.assertEqual(payload["stage_c_decision"], "BLOCK_STAGE_C")
        self.assertIn("NO_PASS_STAGE_B_READY_CANDIDATE", payload["hard_stop_reasons"])
        self.assertIn(
            "NO_STAGE_B_CANDIDATE_PASSED_ALL_STATISTICAL_GATES",
            payload["hard_stop_reasons"],
        )

    def test_stage_c_requires_both_stat_and_approval_pass(self):
        base = {
            "stat": {
                "summary": {"stage_c_allowed": True},
                "candidate_gates": {"a": {"blocking_reasons": []}},
            },
            "approval": {
                "summary": {"n_stage_b_ready": 1},
                "all_candidates": [],
                "top_blocked_by_return": [],
            },
            "cluster": {"counts": {"running": 0}, "all_queries_ok": True},
            "run_plan": {"rows": []},
        }
        self.assertEqual(W.build_readiness(**base)["stage_c_decision"], "ALLOW_STAGE_C")
        base["approval"] = {"summary": {"n_stage_b_ready": 0}}
        self.assertEqual(W.build_readiness(**base)["stage_c_decision"], "BLOCK_STAGE_C")

    def test_next_actions_are_derived_from_blockers(self):
        payload = W.build_readiness(
            stat={
                "summary": {"stage_c_allowed": False},
                "candidate_gates": {"a": {"blocking_reasons": ["PBO_DEFERRED_OR_FAIL"]}},
            },
            approval={
                "summary": {"n_stage_b_ready": 0},
                "all_candidates": [{
                    "blockers": [{"blocker_code": "FINAL_EXCESSIVE_TRADES_HARD"}],
                }],
            },
            cluster={"counts": {"running": 0}},
            run_plan={"rows": []},
        )
        action_codes = {row["blocker_code"] for row in payload["next_actions"]}
        self.assertIn("PBO_DEFERRED_OR_FAIL", action_codes)
        self.assertIn("FINAL_EXCESSIVE_TRADES_HARD", action_codes)

    def test_machine_counts_from_run_plan_rows(self):
        payload = W.build_readiness(
            stat={"summary": {"stage_c_allowed": False}},
            approval={"summary": {"n_stage_b_ready": 0}},
            cluster={"counts": {"running": 0}},
            run_plan={
                "rows": [
                    {"machine_hint": "dragon", "run_status": "DONE"},
                    {"machine_hint": "dragon", "run_status": "DONE"},
                    {"machine_hint": "omega", "run_status": "FAILED"},
                ]
            },
        )
        self.assertEqual(payload["machine_run_plan_counts"]["dragon"]["DONE"], 2)
        self.assertEqual(payload["machine_run_plan_counts"]["omega"]["FAILED"], 1)


if __name__ == "__main__":
    unittest.main()
