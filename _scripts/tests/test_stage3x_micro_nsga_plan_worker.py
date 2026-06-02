from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_micro_nsga_plan_worker as W


def _selected_contract(contract_id: str) -> dict:
    return {
        "contract_id": contract_id,
        "genome_id": contract_id.replace("__selected", ""),
        "asset": "btcusdt_perp",
        "timeframe": "4h",
        "feature_preset": "sota_low_cost",
        "feature_selection_method": "mutual_info_topk",
        "preprocessing_profile": "p03_rolling_long_512",
        "input_data_file": "/tmp/train.csv",
        "selected_features": [f"f{i}" for i in range(32)],
        "screen_score": 1.0,
        "proxy_net_return": 0.1,
        "proxy_trades": 10,
        "best_abs_validation_ic": 0.05,
        "stage_c_access": "DENIED",
        "training_launched": False,
    }


class TestStage3xMicroNsgaPlanWorker(unittest.TestCase):

    def test_build_plan_from_existing_micro_nsga_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            synthesis = root / "synthesis.json"
            selected = root / "selected.json"
            out = root / "out"
            cid = "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p03__selected"
            synthesis.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "stage_c_allowed": False,
                        "next_action": "prepare_stage3x_micro_nsga_plan",
                        "contract_summary": [
                            {
                                "contract_id": cid,
                                "recommended_action": "eligible_for_stage3x_micro_nsga",
                                "blockers": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            selected.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "training_launched": False,
                        "contracts": [_selected_contract(cid)],
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(W, "SYNTHESIS", synthesis),
                patch.object(W, "SELECTED_CONTRACTS", selected),
                patch.object(W, "OUT_ROOT", out),
                patch.object(W, "OUT_JSON", out / "plan.json"),
                patch.object(W, "OUT_MD", out / "plan.md"),
                patch.object(W, "OUT_SELECTED", out / "selected_micro.json"),
            ):
                payload = W.build_plan()
                W.write_plan(payload)
                selected_written = (out / "selected_micro.json").exists()

        self.assertTrue(payload["micro_nsga_plan_allowed"])
        self.assertEqual(payload["next_action"], "write_locked_stage3x_micro_nsga_configs")
        self.assertEqual(payload["micro_nsga_contract_count"], len(W.SAC_VARIANTS))
        self.assertEqual(payload["expected_config_count"], len(W.SAC_VARIANTS) * 3)
        first = payload["selected_population"]["contracts"][0]
        self.assertEqual(first["parent_contract_id"], cid)
        self.assertEqual(first["stage_c_access"], "DENIED")
        self.assertFalse(first["training_launched"])
        self.assertIn("learning_rate", first)
        self.assertIn("continuous_action_threshold", first)
        self.assertEqual(first["train_days"], 14)
        self.assertEqual(first["val_days"], 7)
        self.assertEqual(first["test_days"], 7)
        self.assertEqual(first["min_split_rows"], 30)
        self.assertEqual(first["total_timesteps"], 5000)
        self.assertTrue(selected_written)

    def test_stage_c_not_denied_raises(self):
        with self.assertRaises(W.MicroNsgaPlanError):
            W.eligible_contract_ids(
                {
                    "stage_c_access": "ALLOWED",
                    "stage_c_allowed": True,
                    "next_action": "prepare_stage3x_micro_nsga_plan",
                    "contract_summary": [],
                }
            )

    def test_no_existing_action_blocks_plan(self):
        synthesis = {
            "stage_c_access": "DENIED",
            "stage_c_allowed": False,
            "next_action": "return_to_cpu_feature_screen_or_next_smoke_subset",
            "contract_summary": [],
        }
        self.assertEqual(W.eligible_contract_ids(synthesis), [])


if __name__ == "__main__":
    unittest.main()
