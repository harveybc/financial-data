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
NO_TRADE_ABORT_PROGRESS_PERCENT = float(os.environ.get("PROJECT3_NO_TRADE_ABORT_PROGRESS_PERCENT", "20"))


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


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def no_trade_abort_reason(job: dict) -> str:
    progress_path = job.get("training_progress_file")
    if not progress_path:
        return ""
    progress = read_json(Path(progress_path), {})
    if not isinstance(progress, dict):
        return ""
    pct = safe_float(progress.get("progress_percent"))
    if pct < NO_TRADE_ABORT_PROGRESS_PERCENT:
        return ""
    if "trades_total" not in progress or progress.get("trades_total") in (None, ""):
        return (
            f"progress {pct:.2f}% reached but trades_total is missing; "
            "telemetry contract violated"
        )
    trades = safe_float(progress.get("trades_total"))
    if trades > 0:
        return ""
    diagnosis = progress.get("no_trade_diagnosis") or "no_trade_detected"
    return (
        f"progress {pct:.2f}% reached with trades_total=0 "
        f"(diagnosis={diagnosis}); aborting to avoid wasting compute"
    )


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


def active_worker_running(machine: str) -> bool:
    proc = subprocess.run(
        "ps -eo args= | grep 'stage31_agent_multi_run_worker.py' | grep -v grep || true",
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
    )
    needle = f"--machine {machine}"
    return any(needle in line for line in proc.stdout.splitlines())


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
    worker_running = active_worker_running(machine)
    changed: list[str] = []
    stale_reset: list[str] = []
    no_trade_blocked: list[str] = []
    for job in jobs:
        status = str(job.get("status") or "pending")
        run_id = str(job.get("run_id") or "")
        if status not in ACTIVE_STATUSES or run_id in active:
            continue
        no_trade_reason = no_trade_abort_reason(job)
        if no_trade_reason:
            job["status"] = "blocked_no_trade_early_abort"
            job["exit_code"] = job.get("exit_code") or 124
            job["failure_reason"] = no_trade_reason
            job["no_trade_abort_reason"] = no_trade_reason
            job["reconciled_from_no_trade_progress"] = True
            no_trade_blocked.append(run_id)
            continue
        matches = summary_matches(machine, job)
        if matches:
            job["status"] = "complete"
            job["exit_code"] = 0
            job["reconciled_from_summary"] = True
            job["summary_path"] = str(matches[-1])
            changed.append(run_id)
            continue
        if not worker_running:
            job["status"] = "pending"
            job["reconciled_from_stale_active"] = True
            stale_reset.append(run_id)

    if changed or stale_reset or no_trade_blocked:
        write_json(queue_path, jobs)

    return {
        "machine": machine,
        "active": sorted(active),
        "reconciled": changed,
        "stale_active_reset": stale_reset,
        "no_trade_blocked": no_trade_blocked,
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
