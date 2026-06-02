from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_parametric_data_space_worker as W


class TestStage3xParametricDataSpaceWorker(unittest.TestCase):

    def test_source_family_classification(self):
        self.assertEqual(W.source_family("learned_lstm"), "learned_representation")
        self.assertEqual(W.source_family("tech_stat"), "technical_statistical")
        self.assertEqual(W.source_family("crypto_full"), "crypto_source_family")
        self.assertEqual(W.source_family("fx_full"), "fx_source_family")
        self.assertEqual(W.source_family("kitchen_sink_guarded"), "mixed_guarded")

    def test_schema_is_stage_c_denied_and_sac_first(self):
        inputs = [
            {"asset": "ethusdt", "timeframe": "4h", "feature_preset": "tech_stat"},
            {"asset": "btcusdt", "timeframe": "1h", "feature_preset": "learned_lstm"},
        ]
        schema = W.build_schema(inputs)
        self.assertEqual(schema["stage_c_access"], "DENIED")
        self.assertFalse(schema["training_launched"])
        self.assertEqual(schema["optimizer"]["library"], "deap")
        self.assertEqual(schema["optimizer"]["primary_model"], "SAC")
        self.assertIn("cpu_target_relation_screen_before_gpu", schema["hard_constraints"])

    def test_seed_population_is_cpu_only(self):
        inputs = [
            {
                "asset": "ethusdt",
                "timeframe": "4h",
                "feature_preset": "tech_stat",
                "input_data_file": "/tmp/train.csv",
                "feature_count": 83,
            }
        ]
        population = W.seed_population(inputs)
        self.assertEqual(
            len(population),
            len(W.CPU_SCREENING_FEATURE_SELECTION_METHODS) * len(W.PREPROCESSING_PROFILES),
        )
        self.assertIn("__p00", population[0]["genome_id"])
        self.assertTrue(any(row["preprocessing_profile"] == "p06_wide_observation_64" for row in population))
        self.assertTrue(any(row["preprocessing_profile"] == "p11_tight_force_close_2h" for row in population))
        self.assertTrue(any(row["feature_selection_method"] == "mutual_info_topk" for row in population))
        for row in population:
            self.assertFalse(row["requires_training"])
            self.assertFalse(row["requires_gpu"])
            self.assertEqual(row["stage_c_access"], "DENIED")
            self.assertEqual(row["status"], "CPU_SCREENING_SEED")
            self.assertIn("scaling_mode", row)
            self.assertIn("window_size", row)
            self.assertTrue(row["stage_b_force_close_obs"])

    def test_seed_population_uses_expanded_family_budget(self):
        inputs = [
            {
                "asset": f"asset{i}",
                "timeframe": "4h",
                "feature_preset": "tech_stat",
                "input_data_file": f"/tmp/train_{i}.csv",
                "feature_count": 80 - i,
            }
            for i in range(7)
        ]

        population = W.seed_population(inputs)
        seen_assets = {row["asset"] for row in population}

        self.assertEqual(len(seen_assets), 6)
        self.assertNotIn("asset6", seen_assets)


if __name__ == "__main__":
    unittest.main()
