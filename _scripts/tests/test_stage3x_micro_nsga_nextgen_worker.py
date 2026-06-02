from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_micro_nsga_nextgen_worker as W


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
        "broker_profile": "crypto_exchange_perp",
        "regulatory_profile": "none_or_external",
        "market_type": "crypto_perp",
        "stage_c_access": "DENIED",
        "training_launched": False,
    }


class TestStage3xMicroNsgaNextgenWorker(unittest.TestCase):

    def test_build_nextgen_from_completed_micro_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            synthesis = root / "micro_synthesis.json"
            selected = root / "selected.json"
            out = root / "out"
            agent_out = root / "agent_out"
            p03 = "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p03__selected"
            p04 = "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p04__selected"
            p05 = "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p05__selected"
            p06 = "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p06__selected"
            synthesis.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "stage_c_allowed": False,
                        "contract_summary": [
                            {
                                "contract_id": f"{p03}__micro_nsga_g00_i00_00",
                                "blockers": [],
                                "median_validation_return": -0.05,
                                "median_test_return": 0.04,
                                "median_test_trades": 100,
                                "median_test_trades_per_week": 2.5,
                                "warnings": ["NON_POSITIVE_MEDIAN_VALIDATION_RETURN"],
                            },
                            {
                                "contract_id": f"{p04}__micro_nsga_g00_i01_00",
                                "blockers": [],
                                "median_validation_return": 0.02,
                                "median_test_return": 0.01,
                                "median_test_trades": 60,
                                "median_test_trades_per_week": 3.0,
                                "warnings": [],
                            },
                            {
                                "contract_id": f"{p05}__micro_nsga_g00_i02_00",
                                "blockers": [],
                                "median_validation_return": -0.01,
                                "median_test_return": 0.02,
                                "median_test_trades": 90,
                                "median_test_trades_per_week": 3.5,
                                "warnings": [],
                            },
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
                        "contracts": [_selected_contract(cid) for cid in (p03, p04, p05, p06)],
                    }
                ),
                encoding="utf-8",
            )

            payload = W.build_payload(
                synthesis_file=synthesis,
                selected_contracts=selected,
                out_root=out,
                agent_multi_output_dir=agent_out,
            )
            W.write_payload(payload, out)
            selected_written = (out / "selected_feature_contracts_micro_nsga_g01.json").exists()

        self.assertTrue(payload["micro_nsga_plan_allowed"])
        self.assertEqual(payload["stage_c_access"], "DENIED")
        self.assertFalse(payload["training_launched"])
        self.assertEqual(len(payload["parent_contract_ids"]), 4)
        self.assertIn(p06, payload["parent_contract_ids"])
        self.assertNotIn(p03.replace("__p03__", "__p00__"), payload["parent_contract_ids"])
        self.assertEqual(payload["micro_nsga_contract_count"], 4 * len(W.GEN1_VARIANTS))
        self.assertEqual(payload["expected_config_count"], 4 * len(W.GEN1_VARIANTS) * 3)
        first = payload["selected_population"]["contracts"][0]
        self.assertEqual(first["micro_nsga_generation"], 1)
        self.assertEqual(first["train_days"], 28)
        self.assertEqual(first["val_days"], 14)
        self.assertEqual(first["test_days"], 14)
        self.assertEqual(first["total_timesteps"], 16000)
        self.assertEqual(first["window_size"], "16")
        self.assertEqual(first["learning_starts"], 1)
        self.assertEqual(first["buffer_size"], 20000)
        self.assertEqual(first["ent_coef"], 0.0001)
        self.assertFalse(first["use_sde"])
        self.assertEqual(first["net_arch"], [32, 32])
        self.assertEqual(first["epoch_timesteps"], 2000)
        self.assertEqual(first["max_epochs"], 8)
        self.assertEqual(first["l1_patience"], 7)
        self.assertEqual(first["l1_min_delta"], 0.0)
        self.assertEqual(first["stage_c_access"], "DENIED")
        self.assertTrue(selected_written)

    def test_stage_c_access_not_denied_raises(self):
        with self.assertRaises(W.MicroNsgaNextgenError):
            W.ranked_parent_ids({"stage_c_access": "ALLOWED", "stage_c_allowed": True})

    def test_generation_two_uses_completed_generation_one_individuals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            synthesis = root / "g01_synthesis.json"
            selected = root / "g01_selected.json"
            out = root / "g02_out"
            agent_out = root / "agent_g02_out"
            base = "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p03__selected"
            g01_ids = [f"{base}__micro_nsga_g01_i{i:02d}_00" for i in range(4)]
            synthesis.write_text(
                json.dumps(
                    {
                        "stage_c_access": "DENIED",
                        "stage_c_allowed": False,
                        "contract_summary": [
                            {
                                "contract_id": cid,
                                "blockers": [],
                                "median_validation_return": 0.001 * i,
                                "median_test_return": 0.0005 * i,
                                "median_test_trades": 3,
                                "median_test_trades_per_week": 3.0,
                                "warnings": [],
                            }
                            for i, cid in enumerate(g01_ids)
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
                        "contracts": [
                            {**_selected_contract(cid), "micro_nsga_generation": 1}
                            for cid in g01_ids
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = W.build_payload(
                synthesis_file=synthesis,
                selected_contracts=selected,
                out_root=out,
                agent_multi_output_dir=agent_out,
                generation=2,
                max_parents=4,
            )
            W.write_payload(payload, out)
            self.assertTrue((out / "selected_feature_contracts_micro_nsga_g02.json").exists())
            self.assertTrue((out / "stage3x_micro_nsga_g02_plan.json").exists())

            self.assertTrue(payload["micro_nsga_plan_allowed"])
            self.assertEqual(payload["micro_nsga_generation"], 2)
            self.assertEqual(payload["source_micro_nsga_generation"], 1)
            self.assertEqual(len(payload["parent_contract_ids"]), 4)
            self.assertTrue(all("__micro_nsga_g01_" in cid for cid in payload["parent_contract_ids"]))
            self.assertEqual(payload["micro_nsga_contract_count"], 4 * len(W.GEN1_VARIANTS))
            first = payload["selected_population"]["contracts"][0]
            self.assertIn("__micro_nsga_g02_", first["contract_id"])
            self.assertEqual(first["parent_contract_id"], payload["parent_contract_ids"][0])
            self.assertEqual(first["micro_nsga_generation"], 2)
            self.assertEqual(first["learning_starts"], 1)
            self.assertFalse(first["use_sde"])
            self.assertEqual(first["epoch_timesteps"], 2000)

    def test_seed_rows_rank_robust_parent_over_lucky_seed(self):
        robust = "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p03__selected__micro_nsga_g04_i00_00"
        lucky = "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p04__selected__micro_nsga_g04_i01_00"
        rows = []
        for seed in (0, 1, 2):
            rows.append(
                {
                    "contract_id": robust,
                    "seed": seed,
                    "status": "done",
                    "validation_return": 0.0005,
                    "test_return": 0.0003,
                    "test_trades": 2,
                    "test_trades_per_week": 3.0,
                }
            )
        rows.extend(
            [
                {
                    "contract_id": lucky,
                    "seed": 0,
                    "status": "done",
                    "validation_return": 0.01,
                    "test_return": 0.01,
                    "test_trades": 2,
                    "test_trades_per_week": 3.0,
                },
                {
                    "contract_id": lucky,
                    "seed": 1,
                    "status": "done",
                    "validation_return": -0.002,
                    "test_return": -0.001,
                    "test_trades": 3,
                    "test_trades_per_week": 3.0,
                },
                {
                    "contract_id": lucky,
                    "seed": 2,
                    "status": "done",
                    "validation_return": -0.002,
                    "test_return": -0.001,
                    "test_trades": 3,
                    "test_trades_per_week": 3.0,
                },
            ]
        )
        ranked = W.ranked_parent_ids(
            {"stage_c_access": "DENIED", "stage_c_allowed": False, "rows": rows},
            strip_micro_parent=False,
        )
        self.assertEqual(ranked[0], robust)

    def test_variants_do_not_emit_known_nan_prone_auto_entropy_setting(self):
        names = {variant["name"] for variant in W.GEN1_VARIANTS}
        ent_coefs = {variant["ent_coef"] for variant in W.GEN1_VARIANTS}

        self.assertNotIn("seed_robust_low_entropy_sparse_top50", names)
        self.assertIn("seed_robust_stable_mid_entropy_top50", names)
        self.assertNotIn("auto_0.001", ent_coefs)


if __name__ == "__main__":
    unittest.main()
