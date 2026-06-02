from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_input_preprocessing_optimization_plan_worker as W


class TestStage3xInputPreprocessingOptimizationPlanWorker(unittest.TestCase):

    def test_preprocess_profiles_cover_current_none_rolling_expanding(self):
        profiles = W.build_preprocess_profiles()
        modes = {row["scaling_mode"] for row in profiles}
        self.assertIn("rolling_zscore", modes)
        self.assertIn("none", modes)
        self.assertIn("expanding_zscore", modes)
        self.assertGreaterEqual(len(profiles), 6)

    def test_matrix_is_cpu_first_and_stage_c_denied(self):
        variants = [
            {
                "variant": "tech_stat_full",
                "available": True,
                "input_data_file": "/tmp/train.csv",
                "feature_count": 3,
            }
        ]
        profiles = W.build_preprocess_profiles()[:2]
        rows = W.build_matrix(variants, profiles)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertFalse(row["requires_training"])
            self.assertFalse(row["requires_gpu"])
            self.assertEqual(row["stage_c_access"], "DENIED")
            self.assertEqual(row["heldout_start"], "2025-01-01")
            self.assertIn("feature_hash_present", row["pass_to_gpu_only_if"])

    def test_write_outputs_writes_json_markdown_and_csv(self):
        payload = {
            "schema_version": "test",
            "generated_at": "2026-05-14T00:00:00+00:00",
            "stage_c_access": "DENIED",
            "training_launched": False,
            "matrix_count": 1,
            "variant_count": 1,
            "profile_count": 1,
            "diagnostic_tasks": W.diagnostic_tasks(),
            "matrix": [
                {
                    "cell_id": "a__p00",
                    "stage": "stage3x_pre_rl_input_screen",
                    "asset": "ethusdt",
                    "timeframe": "4h",
                    "algo_scope": "fixed",
                    "source_variant": "a",
                    "variant_available": True,
                    "input_data_file": "/tmp/train.csv",
                    "feature_count": 1,
                    "preprocess_profile": "p00",
                    "scaling_mode": "rolling_zscore",
                    "feature_scaling_window": 256,
                    "feature_clip": 10,
                    "window_size": 32,
                    "include_price_window": True,
                    "include_agent_state": True,
                    "requires_training": False,
                    "requires_gpu": False,
                    "stage_c_access": "DENIED",
                    "heldout_start": "2025-01-01",
                    "status": "PLANNED_CPU_DIAGNOSTIC",
                    "next_worker": "x",
                    "pass_to_gpu_only_if": "feature_hash_present",
                    "rationale": "test",
                }
            ],
        }
        old_root = W.OUT_ROOT
        old_json = W.SUMMARY_JSON
        old_md = W.SUMMARY_MD
        old_csv = W.MATRIX_CSV
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                W.OUT_ROOT = root
                W.SUMMARY_JSON = root / "summary.json"
                W.SUMMARY_MD = root / "summary.md"
                W.MATRIX_CSV = root / "matrix.csv"
                W.write_outputs(payload)
                written = json.loads(W.SUMMARY_JSON.read_text(encoding="utf-8"))
                self.assertEqual(written["stage_c_access"], "DENIED")
                self.assertTrue(W.SUMMARY_MD.exists())
                self.assertTrue(W.MATRIX_CSV.exists())
        finally:
            W.OUT_ROOT = old_root
            W.SUMMARY_JSON = old_json
            W.SUMMARY_MD = old_md
            W.MATRIX_CSV = old_csv


if __name__ == "__main__":
    unittest.main()
