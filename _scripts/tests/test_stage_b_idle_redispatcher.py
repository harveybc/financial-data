import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "workers"))

import stage_b_idle_redispatcher as R


class TestStageBIdleRedispatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def entry(self, variant_id: str, machine: str, *, progress_status: str | None = None):
        run_dir = self.root / variant_id
        progress = run_dir / "training_progress.json"
        entry = {
            "variant_id": variant_id,
            "machine_hint": machine,
            "run_dir": str(run_dir),
            "progress_file": str(progress),
            "expected_evidence_file": str(run_dir / "traces" / "evidence.json"),
            "config_file": str(self.root / f"{variant_id}.json"),
            "input_data_file": str(self.root / "input.csv"),
        }
        if progress_status is not None:
            progress.parent.mkdir(parents=True)
            progress.write_text(json.dumps({"status": progress_status}), encoding="utf-8")
        return entry

    def test_idle_targets_require_query_ok_no_active_and_no_own_backlog(self):
        payloads = {
            "dragon": {"query_ok": True, "active": [], "counts": {"not_started": 0}},
            "gamma": {"query_ok": True, "active": ["job"], "counts": {"not_started": 0}},
            "omega": {"query_ok": True, "active": [], "counts": {"not_started": 5}},
        }
        self.assertEqual(R.idle_targets(payloads), ["dragon"])

    def test_choose_moves_pulls_from_largest_backlog_to_idle_machine(self):
        entries = [
            self.entry("d_done", "dragon", progress_status="complete"),
            self.entry("o1", "omega"),
            self.entry("o2", "omega"),
            self.entry("o3", "omega"),
            self.entry("g1", "gamma"),
        ]
        payloads = {
            "dragon": {"query_ok": True, "active": [], "counts": {"not_started": 0}},
            "gamma": {"query_ok": True, "active": ["busy"], "counts": {"not_started": 1}},
            "omega": {"query_ok": True, "active": ["busy"], "counts": {"not_started": 3}},
        }
        moves = R.choose_moves(entries, payloads, max_moves=1)
        self.assertEqual(moves, [{"variant_id": "o1", "source": "omega", "target": "dragon"}])

    def test_choose_moves_moves_final_leftover_task_to_idle_machine(self):
        entries = [self.entry("o_last", "omega")]
        payloads = {
            "dragon": {"query_ok": True, "active": [], "counts": {"not_started": 0}},
            "gamma": {"query_ok": True, "active": [], "counts": {"not_started": 0}},
            "omega": {"query_ok": True, "active": ["busy"], "counts": {"not_started": 1}},
        }
        moves = R.choose_moves(entries, payloads, max_moves=2)
        self.assertEqual(moves, [{"variant_id": "o_last", "source": "omega", "target": "dragon"}])

    def test_apply_moves_records_original_machine_and_history(self):
        plan = {"configs": [self.entry("o1", "omega")]}
        R.apply_moves(plan, [{"variant_id": "o1", "source": "omega", "target": "dragon"}])
        entry = plan["configs"][0]
        self.assertEqual(entry["machine_hint"], "dragon")
        self.assertEqual(entry["original_machine_hint"], "omega")
        self.assertEqual(entry["redispatched_from"], "omega")
        self.assertEqual(entry["redispatched_to"], "dragon")
        self.assertEqual(len(plan["redispatch_history"]), 1)

    def test_progress_status_distinguishes_not_started_and_terminal(self):
        self.assertEqual(R.progress_status(self.entry("fresh", "omega")), "not_started")
        self.assertEqual(R.progress_status(self.entry("done", "omega", progress_status="complete")), "done")
        self.assertEqual(R.progress_status(self.entry("failed", "omega", progress_status="failed")), "failed")

    def test_launch_move_treats_timeout_as_success_when_remote_process_is_active(self):
        move = {"variant_id": "v1", "target": "gamma"}
        timeout = subprocess.TimeoutExpired(cmd=["ssh"], timeout=20)
        with mock.patch.object(R, "run_text", side_effect=timeout), mock.patch.object(
            R, "remote_variant_active", return_value="123 1 99 agent-multi --load_config v1.json"
        ):
            result = R.launch_move(move)
        self.assertEqual(result["pid"], "unknown_after_ssh_timeout")
        self.assertIn("remote process is active", result["launch_warning"])
        self.assertIn("agent-multi", result["active_process"])

    def test_launch_move_reraises_timeout_when_remote_process_is_not_active(self):
        move = {"variant_id": "v1", "target": "gamma"}
        timeout = subprocess.TimeoutExpired(cmd=["ssh"], timeout=20)
        with mock.patch.object(R, "run_text", side_effect=timeout), mock.patch.object(
            R, "remote_variant_active", return_value=""
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                R.launch_move(move)


if __name__ == "__main__":
    unittest.main()
