import csv
import json
import pathlib
import tempfile
import unittest

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "workers"))

import stage_b_locked_run_plan_worker as W


def write_csv(path: pathlib.Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class TestStageBLockedRunPlanWorker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.run_dir = self.root / "runs" / "candidate"
        self.run_dir.mkdir(parents=True)
        self.config_path = self.run_dir / "config.json"
        self.config = {
            "agent_plugin": "sac_agent",
            "pipeline_plugin": "rl_pipeline",
            "input_data_file": str(self.root / "inputs" / "train.csv"),
            "asset": "ethusdt_4h",
            "features_preset": "tech_stat",
            "total_timesteps": 50000,
            "eval_seed": 0,
            "train_seed": 0,
            "return_trace_file": str(self.run_dir / "return_trace.csv"),
            "results_file": str(self.run_dir / "summary.json"),
            "save_model": str(self.run_dir / "policy.zip"),
            "save_config": str(self.run_dir / "config_out.json"),
        }
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

        self.baseline_dir = self.root / "runs" / "baseline"
        self.baseline_dir.mkdir(parents=True)
        self.baseline_config = dict(self.config)
        self.baseline_config["features_preset"] = "baseline_12"
        (self.baseline_dir / "config.json").write_text(json.dumps(self.baseline_config), encoding="utf-8")

        self.approval_csv = self.root / "approval.csv"
        self.index_csv = self.root / "index.csv"
        self.leakage_csv = self.root / "leakage.csv"
        self.output_dir = self.root / "out"

        common_fields = [
            "run_slug", "stage_b_status", "asset", "timeframe", "algo", "preset",
            "seed", "total_return", "sharpe_ratio", "trades_total",
        ]
        write_csv(
            self.approval_csv,
            [
                {
                    "run_slug": "candidate_s0",
                    "stage_b_status": "BLOCKED_DSR_DEFERRED",
                    "asset": "ethusdt",
                    "timeframe": "4h",
                    "algo": "sac",
                    "preset": "tech_stat",
                    "seed": "0",
                    "total_return": "0.12",
                    "sharpe_ratio": "0.03",
                    "trades_total": "42",
                },
                {
                    "run_slug": "baseline_s0",
                    "stage_b_status": "KILL_NON_POSITIVE_RETURN",
                    "asset": "ethusdt",
                    "timeframe": "4h",
                    "algo": "sac",
                    "preset": "baseline_12",
                    "seed": "0",
                    "total_return": "-0.01",
                    "sharpe_ratio": "-0.02",
                    "trades_total": "30",
                },
            ],
            common_fields,
        )
        write_csv(
            self.index_csv,
            [
                {"run_slug": "candidate_s0", "run_dir": str(self.run_dir), "machine": "dragon"},
                {"run_slug": "baseline_s0", "run_dir": str(self.baseline_dir), "machine": "gamma"},
            ],
            ["run_slug", "run_dir", "machine"],
        )
        write_csv(
            self.leakage_csv,
            [
                {"run_slug": "candidate_s0", "status": "PASS_HELDOUT_FIREWALL", "max_ts": "2023-12-31 20:00:00"},
                {"run_slug": "baseline_s0", "status": "PASS_HELDOUT_FIREWALL", "max_ts": "2023-12-31 20:00:00"},
            ],
            ["run_slug", "status", "max_ts"],
        )

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, **kwargs):
        return W.build_plan(
            approval_csv=self.approval_csv,
            index_csv=self.index_csv,
            leakage_csv=self.leakage_csv,
            output_dir=self.output_dir,
            **kwargs,
        )

    def test_builds_locked_candidate_and_baseline_configs(self):
        manifest = self.build()
        self.assertEqual(manifest["selected_candidate_count"], 1)
        self.assertEqual(manifest["unique_config_count"], 4)
        roles = {item["role"] for item in manifest["configs"]}
        self.assertEqual(roles, {"candidate", "rl_baseline_12"})

    def test_generated_configs_are_locked_and_stage_c_denied(self):
        manifest = self.build()
        for item in manifest["configs"]:
            data = json.loads(pathlib.Path(item["config_file"]).read_text())
            self.assertTrue(data["_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED"])
            self.assertTrue(data["_project3_stage_b_lock"]["locked"])
            self.assertEqual(data["stage_c_access"], "DENIED")
            self.assertFalse(data["training_launched"] if "training_launched" in data else False)

    def test_return_trace_dir_and_progress_contract_are_present(self):
        manifest = self.build()
        for item in manifest["configs"]:
            data = json.loads(pathlib.Path(item["config_file"]).read_text())
            self.assertIn("return_trace_dir", data)
            self.assertIn("return_trace_file", data)
            self.assertTrue(str(data["return_trace_file"]).endswith("evaluation_return_trace.csv"))
            self.assertEqual(data["return_trace_file"], item["return_trace_file"])
            self.assertEqual(data["progress_file"], item["progress_file"])
            self.assertEqual(data["training_progress_file"], item["progress_file"])
            self.assertTrue(str(data["training_progress_file"]).endswith("training_progress.json"))
            self.assertEqual(data["progress_update_interval_steps"], 1000)
            self.assertEqual(data["no_trade_min_trades"], 1)
            self.assertIn("progress_file", data["_project3_progress_contract"])
            self.assertEqual(
                data["_project3_progress_contract"]["training_progress_file"],
                item["progress_file"],
            )
            self.assertIn("trades_total", data["_project3_progress_contract"]["required_live_fields"])
            self.assertIn("progress_percent", data["_project3_progress_contract"]["required_live_fields"])

    def test_stage_a_progress_paths_are_overwritten(self):
        stale = str(self.root / "stage_a" / "old_progress.json")
        original = json.loads(self.config_path.read_text(encoding="utf-8"))
        original["training_progress_file"] = stale
        original["progress_file"] = stale
        self.config_path.write_text(json.dumps(original), encoding="utf-8")

        manifest = self.build()
        for item in manifest["configs"]:
            if item["role"] != "candidate":
                continue
            data = json.loads(pathlib.Path(item["config_file"]).read_text())
            self.assertNotEqual(data["training_progress_file"], stale)
            self.assertEqual(data["training_progress_file"], item["progress_file"])

    def test_cost_scenarios_default_to_base_and_pessimistic(self):
        manifest = self.build()
        self.assertEqual(manifest["cost_scenarios"], ["base", "pessimistic"])
        self.assertEqual({item["cost_scenario"] for item in manifest["configs"]}, {"base", "pessimistic"})

    def test_stage_b_timesteps_replaces_stage_a_budget(self):
        manifest = self.build(stage_b_timesteps=123456)
        for item in manifest["configs"]:
            data = json.loads(pathlib.Path(item["config_file"]).read_text())
            self.assertEqual(data["total_timesteps"], 123456)

    def test_heldout_failure_blocks_plan(self):
        write_csv(
            self.leakage_csv,
            [
                {"run_slug": "candidate_s0", "status": "FAIL_HELDOUT_LEAKAGE", "max_ts": "2025-01-01 00:00:00"},
                {"run_slug": "baseline_s0", "status": "PASS_HELDOUT_FIREWALL", "max_ts": "2023-12-31 20:00:00"},
            ],
            ["run_slug", "status", "max_ts"],
        )
        with self.assertRaises(RuntimeError):
            self.build()

    def test_missing_required_source_config_field_blocks_plan(self):
        bad = dict(self.config)
        bad.pop("input_data_file")
        self.config_path.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.build()

    def test_no_matching_candidate_blocks_plan(self):
        write_csv(
            self.approval_csv,
            [{"run_slug": "x", "stage_b_status": "KILL_NO_TRADES", "asset": "a", "timeframe": "4h", "algo": "sac", "preset": "p", "seed": "0", "total_return": "0", "sharpe_ratio": "0", "trades_total": "0"}],
            ["run_slug", "stage_b_status", "asset", "timeframe", "algo", "preset", "seed", "total_return", "sharpe_ratio", "trades_total"],
        )
        with self.assertRaises(RuntimeError):
            self.build()


if __name__ == "__main__":
    unittest.main()
