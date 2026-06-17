from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import project3_weekly_pool_enqueue_plan as W


def _create_schema(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT NOT NULL UNIQUE,
            candidate_id TEXT NOT NULL,
            asset TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            model_family TEXT NOT NULL,
            train_years INTEGER NOT NULL,
            training_policy TEXT NOT NULL,
            input_data_file TEXT NOT NULL,
            feature_count INTEGER NOT NULL,
            config_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE subjobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT NOT NULL UNIQUE,
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            weekly_anchor_id TEXT NOT NULL,
            train_start TEXT NOT NULL,
            train_end TEXT NOT NULL,
            validation_start TEXT NOT NULL,
            validation_end TEXT NOT NULL,
            test_start TEXT NOT NULL,
            test_end TEXT NOT NULL,
            train_rows INTEGER,
            validation_rows INTEGER,
            test_rows INTEGER,
            depends_on_subjob_id TEXT,
            warm_start_parent_subjob_id TEXT,
            priority INTEGER NOT NULL DEFAULT 100,
            status TEXT NOT NULL DEFAULT 'pending',
            claimed_by TEXT,
            claimed_at TEXT,
            heartbeat_at TEXT,
            completed_at TEXT,
            config_path TEXT,
            run_dir TEXT,
            result_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    con.commit()
    con.close()


def _write_plan(path: Path) -> None:
    plan = {
        "schema_version": "test",
        "stage_c_access": "DENIED",
        "training_launched": False,
        "jobs": [
            {
                "job_id": "ethusdt_4h_event_sac_scratch_1y",
                "candidate_id": "ethusdt_4h_event_sac_scratch_1y",
                "asset": "ethusdt",
                "timeframe": "4h",
                "model_family": "sac",
                "train_years": 1,
                "training_policy": "scratch_n_years",
                "input_data_file": "/tmp/train.csv",
                "feature_columns": ["return_1", "event_upcoming_high_count_24h"],
                "subjobs": [
                    {
                        "subjob_id": "ethusdt_4h_sac_scratch_ty1_20231204",
                        "weekly_anchor_id": "2023-12-04",
                        "train_start": "2022-12-04 00:00:00",
                        "train_end": "2023-12-04 00:00:00",
                        "validation_start": "2023-12-04 00:00:00",
                        "validation_end": "2023-12-11 00:00:00",
                        "test_start": "2023-12-11 00:00:00",
                        "test_end": "2023-12-18 00:00:00",
                        "train_rows": 100,
                        "validation_rows": 10,
                        "test_rows": 10,
                        "priority": 100,
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(plan), encoding="utf-8")


class TestProject3WeeklyPoolEnqueuePlan(unittest.TestCase):

    def test_enqueue_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "pool.sqlite"
            plan = root / "plan.json"
            _create_schema(db)
            _write_plan(plan)

            first = W.enqueue_plan(db, plan)
            second = W.enqueue_plan(db, plan)
            con = sqlite3.connect(db)
            job_count = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            subjob_count = con.execute("SELECT COUNT(*) FROM subjobs").fetchone()[0]
            feature_count = con.execute("SELECT feature_count FROM jobs").fetchone()[0]
            con.close()

        self.assertEqual(first["inserted_jobs"], 1)
        self.assertEqual(first["inserted_subjobs"], 1)
        self.assertEqual(second["inserted_jobs"], 0)
        self.assertEqual(second["inserted_subjobs"], 0)
        self.assertEqual(second["skipped_existing_jobs"], 1)
        self.assertEqual(second["skipped_existing_subjobs"], 1)
        self.assertEqual(job_count, 1)
        self.assertEqual(subjob_count, 1)
        self.assertEqual(feature_count, 2)

    def test_refuses_plan_without_stage_c_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "pool.sqlite"
            plan = root / "plan.json"
            _create_schema(db)
            _write_plan(plan)
            payload = json.loads(plan.read_text(encoding="utf-8"))
            payload["stage_c_access"] = "ALLOWED"
            plan.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(RuntimeError):
                W.enqueue_plan(db, plan)


if __name__ == "__main__":
    unittest.main()
