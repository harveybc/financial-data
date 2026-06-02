import json
import pathlib
import tempfile
import unittest

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "workers"))

import stage_b_locked_run_executor as E


class TestStageBLockedRunExecutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.run_dir = self.root / "run"
        self.progress = self.run_dir / "training_progress.json"
        self.trace_dir = self.run_dir / "traces"
        self.config_path = self.root / "config.json"
        self.entry = {
            "variant_id": "candidate_ethusdt_s0_base",
            "machine_hint": "dragon",
            "role": "candidate",
            "seed": "0",
            "cost_scenario": "base",
            "config_file": str(self.config_path),
            "run_dir": str(self.run_dir),
            "progress_file": str(self.progress),
            "return_trace_dir": str(self.trace_dir),
            "return_trace_file": str(self.trace_dir / "evaluation_return_trace.csv"),
            "expected_evidence_file": str(self.trace_dir / "evidence.json"),
        }
        self.config = {
            "_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED": True,
            "pipeline_plugin": "rl_pipeline",
            "stage_c_access": "DENIED",
            "final_stage_c_evaluation": False,
            "stage_c_acknowledged": False,
            "progress_file": str(self.progress),
            "training_progress_file": str(self.progress),
            "return_trace_dir": str(self.trace_dir),
            "return_trace_file": str(self.trace_dir / "evaluation_return_trace.csv"),
            "total_timesteps": 1_000_000,
        }
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_validate_entry_accepts_locked_stage_b_config(self):
        self.assertEqual(E.validate_entry(self.entry, self.config), [])

    def test_validate_entry_rejects_stage_c_flags(self):
        bad = dict(self.config)
        bad["final_stage_c_evaluation"] = True
        self.assertIn("STAGE_C_AUTH_FLAG_SET", E.validate_entry(self.entry, bad))

    def test_validate_entry_rejects_stale_progress_path(self):
        bad = dict(self.config)
        bad["training_progress_file"] = str(self.root / "stage_a_progress.json")
        issues = E.validate_entry(self.entry, bad)
        self.assertIn("CONFIG_TRAINING_PROGRESS_FILE_MISMATCH", issues)

    def test_validate_entry_rejects_missing_trace_file_for_rl_pipeline(self):
        bad = dict(self.config)
        bad.pop("return_trace_file")
        issues = E.validate_entry(self.entry, bad)
        self.assertIn("RETURN_TRACE_FILE_MISSING_FOR_RL_PIPELINE", issues)

    def test_no_trade_abort_reason_uses_progress_percent_alias(self):
        self.progress.parent.mkdir(parents=True)
        self.progress.write_text(json.dumps({
            "progress_percent": 20.0,
            "trades_total": 0,
            "no_trade_diagnosis": "training_policy_hold_collapse",
        }), encoding="utf-8")
        reason = E.no_trade_abort_reason(self.entry, self.progress)
        self.assertIn("trades_total=0", reason)
        self.assertIn("training_policy_hold_collapse", reason)

    def test_no_trade_abort_reason_allows_positive_trades(self):
        self.progress.parent.mkdir(parents=True)
        self.progress.write_text(json.dumps({
            "progress_pct": 80.0,
            "trades_total": 3,
        }), encoding="utf-8")
        self.assertEqual(E.no_trade_abort_reason(self.entry, self.progress), "")

    def test_build_dry_run_state_reports_ready_rows(self):
        state = E.build_dry_run_state([self.entry])
        self.assertEqual(state["selected_count"], 1)
        self.assertEqual(state["ready_count"], 1)
        self.assertEqual(state["blocked_count"], 0)
        self.assertTrue(state["rows"][0]["ready_to_execute"])

    def test_selected_entries_filters_machine_and_limit(self):
        plan = {"configs": [
            {**self.entry, "variant_id": "a", "machine_hint": "dragon"},
            {**self.entry, "variant_id": "b", "machine_hint": "gamma"},
        ]}
        rows = E.selected_entries(plan, machine="dragon", limit=1)
        self.assertEqual([row["variant_id"] for row in rows], ["a"])

    def test_existing_run_skip_reason_detects_summary(self):
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "summary.json").write_text("{}", encoding="utf-8")
        self.assertEqual(E.existing_run_skip_reason(self.entry), "summary_exists")

    def test_existing_run_skip_reason_detects_terminal_progress(self):
        self.progress.parent.mkdir(parents=True)
        self.progress.write_text(json.dumps({"status": "failed"}), encoding="utf-8")
        self.assertEqual(
            E.existing_run_skip_reason(self.entry),
            "terminal_progress_status:failed",
        )

    def test_existing_run_skip_reason_allows_force_rerun(self):
        self.progress.parent.mkdir(parents=True)
        self.progress.write_text(json.dumps({"status": "complete"}), encoding="utf-8")
        self.assertEqual(E.existing_run_skip_reason(self.entry, force_rerun=True), "")

    def test_existing_run_skip_reason_detects_stale_traceback(self):
        self.progress.parent.mkdir(parents=True)
        self.progress.write_text(json.dumps({"status": "training"}), encoding="utf-8")
        (self.run_dir / "agent_multi_stdout.log").write_text(
            "Traceback (most recent call last)\nValueError: Expected parameter scale [nan]\n",
            encoding="utf-8",
        )
        self.assertEqual(
            E.existing_run_skip_reason(self.entry),
            "stale_failed_stdout:SAC_NAN_SCALE",
        )


if __name__ == "__main__":
    unittest.main()
