from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_sac_smoke_plan_acceptance_worker as W


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestStage3xSacSmokePlanAcceptanceWorker(unittest.TestCase):

    def _fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        request = root / "financial" / "request.json"
        manifest = root / "agent" / "manifest.json"
        selected = root / "financial" / "selected.json"
        input_file = root / "data" / "train.csv"
        input_file.parent.mkdir(parents=True, exist_ok=True)
        input_file.write_text("DATE_TIME,CLOSE,f1\n2024-01-01,100,1\n", encoding="utf-8")
        _write_json(
            selected,
            {
                "stage_c_access": "DENIED",
                "training_launched": False,
                "contracts": [{"contract_id": "c0"}],
            },
        )
        _write_json(
            request,
            {
                "expected_config_count": 1,
                "selected_contracts_sha256": _sha(selected),
                "selected_contract_ids": ["c0"],
            },
        )
        config = root / "agent" / "configs" / "c0_s0_base.json"
        _write_json(
            config,
            {
                "_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED": True,
                "_cost_scenario": "base",
                "_project3_stage3x_sac_smoke": True,
                "_stage3x_contract_id": "c0",
                "agent_plugin": "project3_sac_actor_critic_agent",
                "_cost_multiplier": 1.0,
                "commission": 0.0002,
                "feature_columns": ["f1"],
                "feature_list": ["f1"],
                "final_stage_c_evaluation": False,
                "input_data_file": str(input_file),
                "progress_file": str(root / "agent" / "runs" / "c0" / "training_progress.json"),
                "return_trace_dir": str(root / "agent" / "runs" / "c0" / "return_traces"),
                "return_trace_file": str(root / "agent" / "runs" / "c0" / "return_traces" / "evaluation_return_trace.csv"),
                "stage_c_access": "DENIED",
                "stage_c_acknowledged": False,
            },
        )
        _write_json(
            manifest,
            {
                "_project3_stage3x_sac_smoke": True,
                "config_count": 1,
                "configs": [
                    {
                        "config_file": str(config),
                        "contract_id": "c0",
                        "cost_scenario": "base",
                    }
                ],
                "final_stage_c_evaluation": False,
                "heldout_start": "2025-01-01",
                "rules": {
                    "broad_gpu_launch_allowed": False,
                    "sac_only": True,
                },
                "schema_version": "project3_stage3x_sac_smoke_plan_v1",
                "selected_contract_ids": ["c0"],
                "selected_contracts_file": str(selected),
                "selected_contracts_sha256": _sha(selected),
                "stage_c_access": "DENIED",
                "stage_c_acknowledged": False,
                "training_launched": False,
            },
        )
        return request, manifest, selected, config

    def test_missing_manifest_reports_waiting_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = root / "request.json"
            _write_json(request, {"expected_config_count": 1, "selected_contract_ids": ["c0"]})
            manifest = root / "missing.json"
            with patch.object(W, "REQUEST_JSON", request), patch.object(W, "MANIFEST_JSON", manifest):
                payload = W.build_acceptance()

        self.assertFalse(payload["accepted"])
        self.assertEqual(payload["status"], "WAITING_FOR_COPILOT_MANIFEST")
        self.assertIn("WAITING_FOR_COPILOT_MANIFEST", {row["code"] for row in payload["issues"]})

    def test_accepts_good_locked_smoke_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            request, manifest, _selected, _config = self._fixture(Path(tmp))
            with patch.object(W, "REQUEST_JSON", request), patch.object(W, "MANIFEST_JSON", manifest):
                payload = W.build_acceptance()

        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["status"], "ACCEPTED_LOCKED_SMOKE_PLAN")
        self.assertEqual(payload["config_count"], 1)
        self.assertEqual(payload["stage_c_access"], "DENIED")
        self.assertFalse(payload["training_launched"])

    def test_rejects_manifest_that_authorizes_stage_c(self):
        with tempfile.TemporaryDirectory() as tmp:
            request, manifest, _selected, config = self._fixture(Path(tmp))
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            doc["stage_c_access"] = "ALLOWED"
            _write_json(manifest, doc)
            cfg = json.loads(config.read_text(encoding="utf-8"))
            cfg["final_stage_c_evaluation"] = True
            _write_json(config, cfg)
            with patch.object(W, "REQUEST_JSON", request), patch.object(W, "MANIFEST_JSON", manifest):
                payload = W.build_acceptance()

        self.assertFalse(payload["accepted"])
        codes = {row["code"] for row in payload["issues"]}
        self.assertIn("MANIFEST_STAGE_C_NOT_DENIED", codes)
        self.assertIn("CONFIG_FINAL_STAGE_C_FLAG_NOT_FALSE", codes)

    def test_rejects_bad_feature_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            request, manifest, _selected, config = self._fixture(Path(tmp))
            cfg = json.loads(config.read_text(encoding="utf-8"))
            cfg["feature_columns"] = ["different"]
            _write_json(config, cfg)
            with patch.object(W, "REQUEST_JSON", request), patch.object(W, "MANIFEST_JSON", manifest):
                payload = W.build_acceptance()

        self.assertFalse(payload["accepted"])
        self.assertIn("CONFIG_FEATURE_LIST_COLUMNS_MISMATCH", {row["code"] for row in payload["issues"]})

    def test_rejects_unmanifested_config_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            request, manifest, _selected, config = self._fixture(Path(tmp))
            stale = config.parent / "stale_not_in_manifest.json"
            _write_json(
                stale,
                {
                    "stage_c_access": "DENIED",
                    "final_stage_c_evaluation": False,
                    "stage_c_acknowledged": False,
                },
            )
            with patch.object(W, "REQUEST_JSON", request), patch.object(W, "MANIFEST_JSON", manifest):
                payload = W.build_acceptance()

        self.assertFalse(payload["accepted"])
        self.assertIn("UNMANIFESTED_CONFIG_FILES_PRESENT", {row["code"] for row in payload["issues"]})

    def test_rejects_zero_commission_cost_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            request, manifest, _selected, config = self._fixture(Path(tmp))
            cfg = json.loads(config.read_text(encoding="utf-8"))
            cfg["commission"] = 0.0
            _write_json(config, cfg)
            with patch.object(W, "REQUEST_JSON", request), patch.object(W, "MANIFEST_JSON", manifest):
                payload = W.build_acceptance()

        self.assertFalse(payload["accepted"])
        self.assertIn("CONFIG_NON_POSITIVE_COMMISSION", {row["code"] for row in payload["issues"]})


if __name__ == "__main__":
    unittest.main()
