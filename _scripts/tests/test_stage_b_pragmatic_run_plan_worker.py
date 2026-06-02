from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage_b_pragmatic_run_plan_worker as W


class TestStageBPragmaticRunPlanWorker(unittest.TestCase):

    def test_reference_config_is_locked_and_uses_variant_features(self):
        template = {
            "asset": "old",
            "input_data_file": "old.csv",
            "features_preset": "old",
            "feature_columns": ["old"],
            "feature_binary_columns": [],
            "stage_c_access": "DENIED",
            "final_stage_c_evaluation": False,
            "stage_c_acknowledged": False,
        }
        variant = {
            "variant": "tech_stat_volatility_only",
            "output_csv": "/tmp/variant/train.csv",
            "feature_columns": ["return_1", "vol_regime_high", "train_only_regime_prob_low"],
        }
        cfg = W.build_reference_config(template, variant)
        self.assertEqual(cfg["asset"], "ethusdt_4h")
        self.assertEqual(cfg["input_data_file"], "/tmp/variant/train.csv")
        self.assertEqual(cfg["features_preset"], "tech_stat_volatility_only")
        self.assertEqual(cfg["feature_columns"], variant["feature_columns"])
        self.assertEqual(cfg["stage_c_access"], "DENIED")
        self.assertFalse(cfg["final_stage_c_evaluation"])
        self.assertFalse(cfg["stage_c_acknowledged"])
        self.assertEqual(cfg["feature_binary_columns"], ["vol_regime_high", "train_only_regime_prob_low"])

    def test_write_summary_counts_locked_configs(self):
        results = [
            {
                "variant": "a",
                "agent_multi_stdout": {
                    "config_count": 90,
                    "promotion_blockers": [],
                    "manifest_file": "/tmp/a/manifest.json",
                },
            },
            {
                "variant": "b",
                "agent_multi_stdout": {
                    "config_count": 90,
                    "promotion_blockers": [],
                    "manifest_file": "/tmp/b/manifest.json",
                },
            },
        ]
        old_root = W.OUT_ROOT
        old_json = W.SUMMARY_JSON
        old_md = W.SUMMARY_MD
        try:
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                W.OUT_ROOT = root
                W.SUMMARY_JSON = root / "summary.json"
                W.SUMMARY_MD = root / "summary.md"
                payload = W.write_summary(results)
                self.assertEqual(payload["total_locked_configs"], 180)
                self.assertFalse(payload["training_launched"])
                self.assertEqual(payload["stage_c_access"], "DENIED")
                self.assertTrue(W.SUMMARY_JSON.exists())
                self.assertTrue(W.SUMMARY_MD.exists())
        finally:
            W.OUT_ROOT = old_root
            W.SUMMARY_JSON = old_json
            W.SUMMARY_MD = old_md


if __name__ == "__main__":
    unittest.main()
