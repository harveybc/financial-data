from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage_b_pragmatic_diagnostic_manifest_worker as W


class TestPragmaticDiagnosticManifestWorker(unittest.TestCase):

    def test_manifest_locks_stage_c_and_training(self):
        manifest = W.build_manifest()
        self.assertFalse(manifest["project_rules"]["stage_c_allowed"])
        self.assertEqual(manifest["project_rules"]["stage_c_access"], "DENIED")
        self.assertFalse(manifest["project_rules"]["training_launch_allowed_by_this_manifest"])
        self.assertEqual(manifest["project_rules"]["heldout_start"], "2025-01-01")

    def test_matrix_matches_pragmatic_spec(self):
        manifest = W.build_manifest()
        self.assertEqual(manifest["target"]["asset"], "ETHUSDT")
        self.assertEqual(manifest["target"]["timeframe"], "4h")
        self.assertEqual(manifest["target"]["algorithm"], "SAC")
        self.assertEqual(manifest["seeds"], [0, 1, 2, 3, 4])
        self.assertEqual(len(manifest["feature_variants"]), 10)
        self.assertEqual(manifest["matrix"]["planned_run_cells"], 150)
        self.assertTrue(manifest["external_infrastructure_status"]["feature_variants_materialized"])
        self.assertTrue(manifest["external_infrastructure_status"]["agent_multi_cost_scenarios_supported"])
        self.assertTrue(manifest["external_infrastructure_status"]["agent_multi_known_baseline_plugins_supported"])
        self.assertNotIn("feature_variants_not_materialized", manifest["hard_blocks_before_training"])
        self.assertNotIn("agent_multi_cost_scenarios_not_supported", manifest["hard_blocks_before_training"])
        self.assertNotIn("baseline_plugins_template_only", manifest["hard_blocks_before_training"])
        self.assertEqual(manifest["hard_blocks_before_training"], ["stage_b_operator_approval_missing"])

    def test_cost_manifest_requires_stress_costs(self):
        manifest = W.build_cost_manifest()
        names = [item["name"] for item in manifest["cost_scenarios"]]
        self.assertEqual(names, ["base", "plus_50pct", "plus_100pct"])
        self.assertEqual(manifest["required_for_stage_b_promotion"], names)
        self.assertFalse(manifest["stage_c_allowed"])

    def test_outputs_are_written_and_json_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_dir = W.OUT_DIR
            old_json = W.OUT_JSON
            old_yaml = W.OUT_YAML
            old_md = W.OUT_MD
            old_cost_yaml = W.OUT_COST_YAML
            old_cost_json = W.OUT_COST_JSON
            try:
                root = Path(tmp)
                W.OUT_DIR = root
                W.OUT_JSON = root / "manifest.json"
                W.OUT_YAML = root / "manifest.yaml"
                W.OUT_MD = root / "manifest.md"
                W.OUT_COST_YAML = root / "cost.yaml"
                W.OUT_COST_JSON = root / "cost.json"
                outputs = W.write_outputs()
                self.assertTrue(Path(outputs["manifest_json"]).exists())
                self.assertTrue(Path(outputs["manifest_yaml"]).exists())
                self.assertTrue(Path(outputs["manifest_md"]).exists())
                payload = json.loads(Path(outputs["manifest_json"]).read_text(encoding="utf-8"))
                self.assertEqual(payload["matrix"]["planned_run_cells"], 150)
                self.assertIn("stage_c_allowed: false", Path(outputs["manifest_yaml"]).read_text(encoding="utf-8"))
                self.assertIn("Training launch allowed by this manifest: `False`", Path(outputs["manifest_md"]).read_text(encoding="utf-8"))
            finally:
                W.OUT_DIR = old_dir
                W.OUT_JSON = old_json
                W.OUT_YAML = old_yaml
                W.OUT_MD = old_md
                W.OUT_COST_YAML = old_cost_yaml
                W.OUT_COST_JSON = old_cost_json


if __name__ == "__main__":
    unittest.main()
