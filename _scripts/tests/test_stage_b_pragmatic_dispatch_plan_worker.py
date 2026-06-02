from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage_b_pragmatic_dispatch_plan_worker as W


class TestStageBPragmaticDispatchPlanWorker(unittest.TestCase):

    def test_variant_id_is_unique_for_candidate_and_baseline(self):
        candidate = W.variant_id(
            variant="tech_stat_full",
            entry={"role": "candidate", "seed": 0, "cost_scenario": "base"},
        )
        baseline = W.variant_id(
            variant="tech_stat_full",
            entry={
                "role": "baseline",
                "baseline_name": "random",
                "seed": 0,
                "cost_scenario": "base",
            },
        )
        self.assertEqual(candidate, "candidate_tech_stat_full_s0_base")
        self.assertEqual(baseline, "baseline_random_tech_stat_full_s0_base")
        self.assertNotEqual(candidate, baseline)

    def test_validate_locked_config_rejects_stage_c_flags(self):
        cfg = {
            "_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED": True,
            "stage_c_access": "DENIED",
            "final_stage_c_evaluation": True,
            "stage_c_acknowledged": False,
            "heldout_start": "2025-01-01",
            "progress_file": "/tmp/p.json",
            "training_progress_file": "/tmp/p.json",
            "return_trace_dir": "/tmp/traces",
            "return_trace_file": "/tmp/traces/evaluation_return_trace.csv",
        }
        with self.assertRaises(W.DispatchPlanError):
            W.validate_locked_config(Path("/tmp/cfg.json"), cfg)

    def test_write_outputs_assigns_machine_counts(self):
        old_plan_dir = W.PLAN_DIR
        old_json = W.PLAN_JSON
        old_csv = W.PLAN_CSV
        old_md = W.PLAN_MD
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                W.PLAN_DIR = root
                W.PLAN_JSON = root / "stage_b_locked_run_plan.json"
                W.PLAN_CSV = root / "stage_b_locked_run_plan.csv"
                W.PLAN_MD = root / "stage_b_locked_run_plan.md"
                entries = [
                    {"variant_id": "a", "machine_hint": "dragon", "role": "candidate", "baseline_name": "", "asset": "ethusdt", "timeframe": "4h", "algo": "sac", "preset": "x", "seed": "0", "cost_scenario": "base", "stage_b_timesteps": 1, "execution_status": "LOCKED_READY_FOR_STAGE_B_EXECUTION", "config_file": "/tmp/a.json", "progress_file": "/tmp/a_progress.json", "run_dir": "/tmp/a", "return_trace_file": "/tmp/a.csv", "return_trace_dir": "/tmp/tr", "expected_evidence_file": "/tmp/evidence.json", "input_data_file": "/tmp/train.csv", "input_max_ts": "2023-12-31 20:00:00", "stage_c_access": "DENIED"},
                    {"variant_id": "b", "machine_hint": "omega", "role": "baseline", "baseline_name": "no_trade", "asset": "ethusdt", "timeframe": "4h", "algo": "sac", "preset": "x", "seed": "0", "cost_scenario": "base", "stage_b_timesteps": 0, "execution_status": "LOCKED_READY_FOR_STAGE_B_EXECUTION", "config_file": "/tmp/b.json", "progress_file": "/tmp/b_progress.json", "run_dir": "/tmp/b", "return_trace_file": "/tmp/b.csv", "return_trace_dir": "/tmp/tr", "expected_evidence_file": "/tmp/evidence.json", "input_data_file": "/tmp/train.csv", "input_max_ts": "2023-12-31 20:00:00", "stage_c_access": "DENIED"},
                ]
                payload = W.write_outputs(entries, {"cost_scenarios": ["base"], "baselines": ["no_trade"]})
                self.assertEqual(payload["unique_config_count"], 2)
                self.assertEqual(payload["machine_assignment_counts"]["dragon"], 1)
                self.assertEqual(payload["machine_assignment_counts"]["omega"], 1)
                written = json.loads(W.PLAN_JSON.read_text())
                self.assertEqual(len(written["configs"]), 2)
        finally:
            W.PLAN_DIR = old_plan_dir
            W.PLAN_JSON = old_json
            W.PLAN_CSV = old_csv
            W.PLAN_MD = old_md


if __name__ == "__main__":
    unittest.main()
