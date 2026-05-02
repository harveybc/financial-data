#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))

COMPLETED = {
    "dragon": {
        "btcusdt_1h_baseline_12_ppo_s0_25000",
        "ethusdt_1h_tech_full_ppo_s0_25000",
    },
    "gamma": {
        "eurusd_1h_baseline_12_ppo_s0_25000",
        "usdjpy_1h_tech_full_ppo_s0_25000",
        "eurusd_4h_tech_stat_decomp_dqn_s0_25000",
    },
    "omega": {
        "btcusdt_4h_baseline_12_dqn_s0_8750",
        "eurusd_4h_baseline_12_ppo_s0_8750",
    },
}

EXTENDED = {
    "dragon": [
        {"asset": "ethusdt", "timeframe": "4h", "preset": "learned_lstm", "algo": "ppo", "seed": 0, "timesteps": 25000, "device": "cuda", "stage": "3.1_stage_a_extended_gpu"},
        {"asset": "btcusdt", "timeframe": "1h", "preset": "tech_stat_decomp", "algo": "dqn", "seed": 0, "timesteps": 25000, "device": "cuda", "stage": "3.1_stage_a_extended_gpu"},
        {"asset": "ethusdt", "timeframe": "4h", "preset": "baseline_12", "algo": "sac", "seed": 0, "timesteps": 25000, "device": "cuda", "stage": "3.1_stage_a_extended_gpu"},
    ],
    "gamma": [
        {"asset": "usdjpy", "timeframe": "4h", "preset": "baseline_12", "algo": "dqn", "seed": 0, "timesteps": 25000, "device": "cuda", "stage": "3.1_stage_a_extended_gpu"},
        {"asset": "eurusd", "timeframe": "1h", "preset": "learned_lstm", "algo": "ppo", "seed": 0, "timesteps": 25000, "device": "cuda", "stage": "3.1_stage_a_extended_gpu"},
        {"asset": "usdjpy", "timeframe": "4h", "preset": "tech_stat", "algo": "sac", "seed": 0, "timesteps": 25000, "device": "cuda", "stage": "3.1_stage_a_extended_gpu"},
    ],
    "omega": [
        {"asset": "ethusdt", "timeframe": "4h", "preset": "baseline_12", "algo": "dqn", "seed": 0, "timesteps": 8750, "device": "cpu", "stage": "3.1_stage_a_extended_cpu"},
        {"asset": "usdjpy", "timeframe": "4h", "preset": "baseline_12", "algo": "ppo", "seed": 0, "timesteps": 8750, "device": "cpu", "stage": "3.1_stage_a_extended_cpu"},
        {"asset": "btcusdt", "timeframe": "4h", "preset": "tech_full", "algo": "ppo", "seed": 0, "timesteps": 8750, "device": "cpu", "stage": "3.1_stage_a_extended_cpu"},
        {"asset": "eurusd", "timeframe": "1h", "preset": "baseline_12", "algo": "dqn", "seed": 0, "timesteps": 8750, "device": "cpu", "stage": "3.1_stage_a_extended_cpu"},
    ],
}


def run_id(job: dict) -> str:
    return f"{job['asset']}_{job['timeframe']}_{job['preset']}_{job['algo']}_s{job['seed']}_{job['timesteps']}"


def load_queue(machine: str) -> list[dict]:
    path = PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_queue(machine: str, queue: list[dict]) -> Path:
    path = PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def repair(machine: str) -> list[dict]:
    queue = load_queue(machine)
    completed = COMPLETED.get(machine, set())
    for job in queue:
        if job.get("run_id") in completed:
            job["status"] = "complete"
    seen = {job.get("run_id") for job in queue}
    for job in EXTENDED.get(machine, []):
        item = dict(job)
        item["run_id"] = run_id(item)
        item.setdefault("status", "pending")
        if item["run_id"] not in seen:
            queue.append(item)
            seen.add(item["run_id"])
    return queue


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair Stage 3.1 machine queue statuses and append extended work.")
    parser.add_argument("--machine", required=True, choices=sorted(EXTENDED))
    args = parser.parse_args()
    queue = repair(args.machine)
    path = save_queue(args.machine, queue)
    print(json.dumps({"path": str(path), "queue": [(j.get("run_id"), j.get("status")) for j in queue]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
