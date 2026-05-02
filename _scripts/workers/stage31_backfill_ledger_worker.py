#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
sys.path.insert(0, str(PROJECT_ROOT / "_scripts" / "lib"))

from experiment_ledger import EVENT_ROOT, combine_ledgers, record_stage31_event, stable_json  # noqa: E402


FINAL_STATUSES = {
    "complete",
    "failed",
    "needs_review",
    "skipped_busy",
    "blocked_resolved_rerouted_to_dragon",
}


def existing_backfill_keys() -> set[str]:
    keys = set()
    for path in EVENT_ROOT.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not str(row.get("detail", "")).startswith("Backfilled from Stage 3.1 queue"):
                continue
            keys.add(
                stable_json(
                    {
                        "backfill": True,
                        "machine": row.get("machine"),
                        "run_id": row.get("run_id"),
                        "status": row.get("status"),
                    }
                )
            )
    return keys


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def backfill_machine(machine: str, existing: set[str]) -> Counter:
    queue = PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"
    jobs = read_json(queue, [])
    counts: Counter = Counter()
    for job in jobs:
        status = str(job.get("status") or "pending")
        if status not in FINAL_STATUSES:
            continue
        key = stable_json(
            {
                "backfill": True,
                "machine": machine,
                "run_id": job.get("run_id"),
                "status": status,
            }
        )
        if key in existing:
            continue
        event_type = "complete" if status == "complete" else ("failed" if status == "failed" else "needs_review")
        record_stage31_event(
            machine=machine,
            job=job,
            event_type=event_type,
            status=status,
            detail="Backfilled from Stage 3.1 queue after immutable ledger policy adoption.",
            failure_reason=None if status == "complete" else status,
        )
        job["ledger_backfilled"] = True
        existing.add(key)
        counts[status] += 1
    if counts:
        queue.write_text(json.dumps(jobs, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Stage 3.1 final queue states into the run ledger.")
    parser.add_argument("--machines", nargs="*", default=["omega", "dragon", "gamma"])
    args = parser.parse_args()

    existing = existing_backfill_keys()
    result = {machine: dict(backfill_machine(machine, existing)) for machine in args.machines}
    summary = combine_ledgers()
    print(json.dumps({"backfilled": result, "combined": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
