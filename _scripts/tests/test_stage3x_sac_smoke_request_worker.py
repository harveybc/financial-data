from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_sac_smoke_request_worker as W


def _contract(idx: int, score: float) -> dict:
    return {
        "contract_id": f"contract_{idx}",
        "genome_id": f"genome_{idx}",
        "asset": "btcusdt",
        "timeframe": "1h",
        "feature_preset": "learned_cnn",
        "preprocessing_profile": "p00_current_contract",
        "input_data_file": f"/tmp/input_{idx}.csv",
        "selected_features": ["f1", "f2"],
        "screen_score": score,
        "proxy_net_return": score / 10.0,
        "best_abs_validation_ic": score / 100.0,
        "stage_c_access": "DENIED",
        "training_launched": False,
    }


class TestStage3xSacSmokeRequestWorker(unittest.TestCase):

    def test_build_request_allows_small_smoke_and_uses_research_shortlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected.json"
            guard = root / "guard.json"
            preferred = [
                {**_contract(idx, score), "contract_id": cid}
                for idx, (cid, score) in enumerate(
                    zip(W.PREFERRED_SMOKE_CONTRACT_IDS, (0.1, 0.9, 0.5, 0.7))
                )
            ]
            selected.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "training_launched": False,
                        "contracts": preferred,
                    }
                ),
                encoding="utf-8",
            )
            guard.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "broad_gpu_launch_allowed": False,
                        "small_sac_smoke_allowed": True,
                        "issue_count": 1,
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(W, "SELECTED_CONTRACTS", selected),
                patch.object(W, "ABSURDITY_GUARD", guard),
                patch.object(W, "SMOKE_SYNTHESIS", root / "missing_synthesis.json"),
            ):
                payload = W.build_request()

        self.assertTrue(payload["request_allowed"])
        self.assertEqual(payload["expected_config_count"], len(payload["selected_contract_ids"]) * 3)
        self.assertEqual(payload["request_mode"], "small_sac_smoke")
        self.assertEqual(payload["selected_contract_ids"], list(W.PREFERRED_SMOKE_CONTRACT_IDS))
        self.assertEqual(payload["stage_c_access"], "DENIED")
        self.assertFalse(payload["training_launched"])
        self.assertIn("--validate-only", payload["commands"]["validate_only"])
        self.assertEqual(payload["selected_contracts_file"], str(W.SMOKE_SHORTLIST_JSON))
        self.assertEqual(len(payload["selected_contracts_sha256"]), 64)

    def test_guard_blocks_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected.json"
            guard = root / "guard.json"
            selected.write_text(
                json.dumps({"stage_c_access": "DENIED", "training_launched": False, "contracts": [_contract(0, 1.0)]}),
                encoding="utf-8",
            )
            guard.write_text(
                json.dumps({"stage_c_access": "DENIED", "small_sac_smoke_allowed": False}),
                encoding="utf-8",
            )

            with (
                patch.object(W, "SELECTED_CONTRACTS", selected),
                patch.object(W, "ABSURDITY_GUARD", guard),
                patch.object(W, "SMOKE_SYNTHESIS", root / "missing_synthesis.json"),
            ):
                payload = W.build_request()

        self.assertFalse(payload["request_allowed"])
        self.assertIn("SMALL_SAC_SMOKE_BLOCKED_BY_GUARD", {row["code"] for row in payload["blockers"]})

    def test_selected_contracts_stage_c_flag_blocks_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected.json"
            guard = root / "guard.json"
            selected.write_text(
                json.dumps({"stage_c_access": "ALLOWED", "training_launched": False, "contracts": [_contract(0, 1.0)]}),
                encoding="utf-8",
            )
            guard.write_text(
                json.dumps({"stage_c_access": "DENIED", "small_sac_smoke_allowed": True}),
                encoding="utf-8",
            )

            with (
                patch.object(W, "SELECTED_CONTRACTS", selected),
                patch.object(W, "ABSURDITY_GUARD", guard),
                patch.object(W, "SMOKE_SYNTHESIS", root / "missing_synthesis.json"),
            ):
                payload = W.build_request()

        self.assertFalse(payload["request_allowed"])
        self.assertIn("SELECTED_CONTRACTS_STAGE_C_NOT_DENIED", {row["code"] for row in payload["blockers"]})

    def test_followup_mode_uses_eligible_contracts_five_seeds_and_three_costs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected.json"
            guard = root / "guard.json"
            synthesis = root / "synthesis.json"
            contracts = [_contract(idx, score=1.0 - idx / 10.0) for idx in range(3)]
            eligible = [contracts[2]["contract_id"], contracts[0]["contract_id"]]
            selected.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "training_launched": False,
                        "contracts": contracts,
                    }
                ),
                encoding="utf-8",
            )
            guard.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "broad_gpu_launch_allowed": False,
                        "small_sac_smoke_allowed": True,
                        "issue_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            synthesis.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "next_action": "select_targeted_cost_seed_followup",
                        "contract_summary": [
                            {
                                "contract_id": eligible[0],
                                "recommended_action": "eligible_for_targeted_cost_seed_followup",
                            },
                            {
                                "contract_id": eligible[1],
                                "recommended_action": "eligible_for_targeted_cost_seed_followup",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(W, "SELECTED_CONTRACTS", selected),
                patch.object(W, "ABSURDITY_GUARD", guard),
                patch.object(W, "SMOKE_SYNTHESIS", synthesis),
            ):
                payload = W.build_request()

        self.assertTrue(payload["request_allowed"])
        self.assertEqual(payload["request_mode"], "targeted_cost_seed_followup")
        self.assertEqual(payload["selected_contract_ids"], eligible)
        self.assertEqual(payload["requested_seeds"], [0, 1, 2, 3, 4])
        self.assertEqual(payload["requested_cost_scenarios"], ["base", "plus_50pct", "plus_100pct"])
        self.assertEqual(payload["expected_config_count"], 30)
        self.assertIn("--cost-scenarios", payload["commands"]["write_locked_plan"])

    def test_secondary_smoke_excludes_completed_blocked_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "selected.json"
            guard = root / "guard.json"
            synthesis = root / "synthesis.json"
            agent_plan = root / "agent_plan"
            contracts = [_contract(idx, score=10.0 - idx) for idx in range(6)]
            completed = {contracts[0]["contract_id"], contracts[2]["contract_id"]}
            archived_completed = {contracts[1]["contract_id"]}
            selected.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "training_launched": False,
                        "contracts": contracts,
                    }
                ),
                encoding="utf-8",
            )
            guard.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "broad_gpu_launch_allowed": False,
                        "small_sac_smoke_allowed": True,
                        "issue_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            synthesis.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "next_action": "return_to_cpu_feature_screen_or_next_smoke_subset",
                        "contract_summary": [
                            {
                                "contract_id": cid,
                                "recommended_action": "defer_blocked_by_smoke_evidence",
                            }
                            for cid in completed
                        ],
                    }
                ),
                encoding="utf-8",
            )
            archived_state = agent_plan / "archive_completed_batch" / "stage3x_sac_smoke_dispatch_state.json"
            archived_state.parent.mkdir(parents=True, exist_ok=True)
            archived_state.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "tasks": [
                            {
                                "contract_id": next(iter(archived_completed)),
                                "status": "done",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            invalid_state = agent_plan / "archive_invalid_zero_cost" / "stage3x_sac_smoke_dispatch_state.json"
            invalid_state.parent.mkdir(parents=True, exist_ok=True)
            invalid_state.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "tasks": [
                            {
                                "contract_id": contracts[5]["contract_id"],
                                "status": "done",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(W, "SELECTED_CONTRACTS", selected),
                patch.object(W, "ABSURDITY_GUARD", guard),
                patch.object(W, "SMOKE_SYNTHESIS", synthesis),
                patch.object(W, "AGENT_MULTI_OUTPUT_DIR", agent_plan),
            ):
                payload = W.build_request()

        self.assertTrue(payload["request_allowed"])
        self.assertEqual(payload["request_mode"], "secondary_sac_smoke")
        self.assertEqual(payload["requested_seeds"], [0, 1, 2])
        self.assertEqual(payload["requested_cost_scenarios"], ["base"])
        self.assertEqual(payload["excluded_contract_ids"], sorted(completed | archived_completed))
        self.assertFalse((completed | archived_completed).intersection(payload["selected_contract_ids"]))
        self.assertIn(contracts[5]["contract_id"], payload["selected_contract_ids"])
        self.assertEqual(payload["expected_config_count"], len(payload["selected_contract_ids"]) * 3)


if __name__ == "__main__":
    unittest.main()
