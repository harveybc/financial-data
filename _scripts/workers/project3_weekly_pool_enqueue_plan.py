#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "experiments" / "weekly_walkforward_pool" / "project3_weekly_pool.sqlite"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def enqueue_plan(db_path: Path, plan_path: Path) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("stage_c_access") != "DENIED":
        raise RuntimeError("Refusing to enqueue a plan that does not explicitly deny Stage C access.")
    if plan.get("training_launched") is not False:
        raise RuntimeError("Refusing to enqueue a plan that does not declare training_launched=false.")

    inserted_jobs = 0
    inserted_subjobs = 0
    skipped_jobs = 0
    skipped_subjobs = 0
    now = _utc_now()
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("BEGIN IMMEDIATE")
        for job in plan.get("jobs", []):
            existing = con.execute(
                "SELECT id FROM jobs WHERE external_id = ?",
                (job["job_id"],),
            ).fetchone()
            if existing:
                job_db_id = int(existing[0])
                skipped_jobs += 1
            else:
                cur = con.execute(
                    """
                    INSERT INTO jobs (
                      external_id, candidate_id, asset, timeframe, model_family,
                      train_years, training_policy, input_data_file, feature_count,
                      config_json, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)
                    """,
                    (
                        job["job_id"],
                        job.get("candidate_id", job["job_id"]),
                        job["asset"],
                        job["timeframe"],
                        job["model_family"],
                        int(job["train_years"]),
                        job["training_policy"],
                        job["input_data_file"],
                        len(job.get("feature_columns", [])),
                        json.dumps(job, sort_keys=True),
                        now,
                        now,
                    ),
                )
                job_db_id = int(cur.lastrowid)
                inserted_jobs += 1

            for subjob in job.get("subjobs", []):
                existing_subjob = con.execute(
                    "SELECT id FROM subjobs WHERE external_id = ?",
                    (subjob["subjob_id"],),
                ).fetchone()
                if existing_subjob:
                    skipped_subjobs += 1
                    continue
                con.execute(
                    """
                    INSERT INTO subjobs (
                      external_id, job_id, weekly_anchor_id,
                      train_start, train_end, validation_start, validation_end,
                      test_start, test_end, train_rows, validation_rows, test_rows,
                      depends_on_subjob_id, warm_start_parent_subjob_id, priority,
                      status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        subjob["subjob_id"],
                        job_db_id,
                        subjob["weekly_anchor_id"],
                        subjob["train_start"],
                        subjob["train_end"],
                        subjob["validation_start"],
                        subjob["validation_end"],
                        subjob["test_start"],
                        subjob["test_end"],
                        subjob.get("train_rows"),
                        subjob.get("validation_rows"),
                        subjob.get("test_rows"),
                        subjob.get("depends_on_subjob_id"),
                        subjob.get("warm_start_parent_subjob_id"),
                        int(subjob.get("priority", 100)),
                        now,
                        now,
                    ),
                )
                inserted_subjobs += 1
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    return {
        "plan_path": str(plan_path),
        "db_path": str(db_path),
        "inserted_jobs": inserted_jobs,
        "inserted_subjobs": inserted_subjobs,
        "skipped_existing_jobs": skipped_jobs,
        "skipped_existing_subjobs": skipped_subjobs,
        "stage_c_access": plan.get("stage_c_access"),
        "training_launched": plan.get("training_launched"),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Idempotently enqueue a Project 3 weekly pool plan.")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--plan", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = enqueue_plan(Path(args.db), Path(args.plan))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
