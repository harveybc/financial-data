#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
ACTIVE_STATUSES = {"training", "running", "registered", "preparing_input"}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def active_config_stems() -> set[str]:
    proc = subprocess.run(
        "ps -eo args= | grep 'agent-multi/tools/seed_sweep.py' | grep -v grep || true",
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
    )
    stems: set[str] = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if "--config" not in parts:
            continue
        try:
            stems.add(Path(parts[parts.index("--config") + 1]).stem)
        except Exception:
            continue
    return stems


def summary_matches(machine: str, job: dict) -> list[Path]:
    asset = job.get("asset")
    timeframe = job.get("timeframe")
    algo = job.get("algo") or job.get("algorithm")
    preset = job.get("preset") or job.get("feature_preset")
    seed = job.get("seed")
    if not all([asset, timeframe, algo, preset]) or seed is None:
        return []
    run_root = PROJECT_ROOT / "experiments" / "stage_a_screening" / "runs" / machine
    pattern = f"{asset}_{timeframe}_{algo}_{preset}_*_s{seed}_*/summary.json"
    return sorted(run_root.glob(pattern))


def reconcile(machine: str) -> dict:
    queue_path = PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"
    jobs = read_json(queue_path, [])
    if not isinstance(jobs, list):
        return {"machine": machine, "error": "queue_not_list"}

    active = active_config_stems()
    changed: list[str] = []
    for job in jobs:
        status = str(job.get("status") or "pending")
        run_id = str(job.get("run_id") or "")
        if status not in ACTIVE_STATUSES or run_id in active:
            continue
        matches = summary_matches(machine, job)
        if not matches:
            continue
        job["status"] = "complete"
        job["exit_code"] = 0
        job["reconciled_from_summary"] = True
        job["summary_path"] = str(matches[-1])
        changed.append(run_id)

    if changed:
        write_json(queue_path, jobs)

    return {
        "machine": machine,
        "active": sorted(active),
        "reconciled": changed,
        "counts": dict(Counter((job.get("status") or "pending") for job in jobs)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile stale Stage 3.1 active queue rows from run summaries.")
    parser.add_argument("--machine", required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.machine), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
