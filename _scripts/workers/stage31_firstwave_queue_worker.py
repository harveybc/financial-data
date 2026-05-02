#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
AGENT_MULTI_ROOT = Path(os.environ.get("AGENT_MULTI_ROOT", "/home/harveybc/Documents/GitHub/agent-multi"))

FIRST_WAVE = {
    "dragon": [
        {"asset": "btcusdt", "timeframe": "1h", "preset": "baseline_12", "algo": "ppo", "seed": 0, "timesteps": 100_000, "device": "cuda"},
        {"asset": "ethusdt", "timeframe": "1h", "preset": "tech_full", "algo": "ppo", "seed": 0, "timesteps": 100_000, "device": "cuda"},
        {"asset": "btcusdt", "timeframe": "4h", "preset": "sota_low_cost", "algo": "sac", "seed": 0, "timesteps": 100_000, "device": "cuda"},
    ],
    "gamma": [
        {"asset": "eurusd", "timeframe": "1h", "preset": "baseline_12", "algo": "ppo", "seed": 0, "timesteps": 100_000, "device": "cuda"},
        {"asset": "usdjpy", "timeframe": "1h", "preset": "tech_full", "algo": "ppo", "seed": 0, "timesteps": 100_000, "device": "cuda"},
        {"asset": "eurusd", "timeframe": "4h", "preset": "tech_stat_decomp", "algo": "dqn", "seed": 0, "timesteps": 100_000, "device": "cuda"},
    ],
    "omega": [
        {"asset": "btcusdt", "timeframe": "4h", "preset": "baseline_12", "algo": "dqn", "seed": 0, "timesteps": 35_000, "device": "cpu"},
        {"asset": "eurusd", "timeframe": "4h", "preset": "baseline_12", "algo": "ppo", "seed": 0, "timesteps": 35_000, "device": "cpu"},
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def git_sha(path: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    except Exception:
        return "unknown"


def run_id(job: dict) -> str:
    return (
        f"{job['asset']}_{job['timeframe']}_{job['preset']}_"
        f"{job['algo']}_s{job['seed']}_{job['timesteps']}"
    )


def generate_full_matrix() -> list[dict]:
    assets = ["btcusdt", "ethusdt", "eurusd", "usdjpy"]
    timeframes = ["1h", "4h"]
    presets = [
        "baseline_12",
        "tech_full",
        "tech_stat",
        "tech_stat_decomp",
        "learned_lstm",
        "learned_cnn",
        "sota_low_cost",
        "crypto_full",
        "fx_full",
        "kitchen_sink_guarded",
    ]
    algos = ["ppo", "sac", "dqn"]
    seeds = [0, 1]
    rows = []
    for asset in assets:
        for timeframe in timeframes:
            for preset in presets:
                if preset == "crypto_full" and asset in {"eurusd", "usdjpy"}:
                    continue
                if preset == "fx_full" and asset in {"btcusdt", "ethusdt"}:
                    continue
                for algo in algos:
                    for seed in seeds:
                        rows.append(
                            {
                                "run_id": f"{asset}_{timeframe}_{preset}_{algo}_s{seed}",
                                "asset": asset,
                                "timeframe": timeframe,
                                "preset": preset,
                                "algo": algo,
                                "seed": seed,
                                "timesteps": 100_000,
                            }
                        )
    return rows


def write_queue_files(timesteps_scale: float, dry_smoke: bool) -> dict:
    queues_dir = PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues"
    queues_dir.mkdir(parents=True, exist_ok=True)
    queues = {}
    for machine, jobs in FIRST_WAVE.items():
        machine_jobs = []
        for job in jobs:
            item = dict(job)
            if dry_smoke:
                item["timesteps"] = min(int(item["timesteps"] * timesteps_scale), 2_000)
            else:
                item["timesteps"] = max(1_000, int(item["timesteps"] * timesteps_scale))
            item["run_id"] = run_id(item)
            item["status"] = "pending"
            item["stage"] = "3.1_stage_a_first_wave"
            machine_jobs.append(item)
        queues[machine] = machine_jobs
        write_json(queues_dir / f"{machine}.json", machine_jobs)
    return queues


def write_matrix(rows: list[dict]) -> None:
    out = PROJECT_ROOT / "experiments" / "stage_a_screening" / "run_matrix.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["run_id", "asset", "timeframe", "preset", "algo", "seed", "timesteps"])
        writer.writeheader()
        writer.writerows(rows)
    write_json(PROJECT_ROOT / "_metadata" / "stage31_run_matrix.json", {"generated_at": utc_now(), "rows": len(rows), "run_matrix_csv": str(out), "stage": "3.1"})


def write_dispatch_report(queues: dict, matrix_rows: list[dict]) -> None:
    generated = utc_now()
    payload = {
        "status": "active",
        "stage": "3.1",
        "machine": socket.gethostname(),
        "generated_at": generated,
        "financial_data_git_sha": git_sha(PROJECT_ROOT),
        "agent_multi_git_sha": git_sha(AGENT_MULTI_ROOT),
        "full_stage_a_matrix_runs": len(matrix_rows),
        "first_wave_jobs": queues,
        "deliverables": [
            "experiments/stage_a_screening/run_matrix.csv",
            "experiments/stage_a_screening/queues/*.json",
            "_logs/supervisor_reports/stage31_worker_<machine>.md",
        ],
    }
    write_json(PROJECT_ROOT / "_metadata" / "stage31_active_dispatch.json", payload)
    lines = [
        "# Stage 3.1 Active Dispatch",
        "",
        f"Generated: {generated}",
        "",
        "## Supervisor Decision",
        "",
        "Phase 3.1 is active. The first wave starts real RL smoke/screening runs while the full Stage A matrix is registered.",
        "",
        "## First-Wave Assignments",
        "",
        "| Machine | Stage | Jobs | Expected deliverable |",
        "| --- | --- | --- | --- |",
    ]
    for machine, jobs in queues.items():
        labels = ", ".join(f"{j['asset']} {j['timeframe']} {j['preset']} {j['algo']} s{j['seed']} {j['timesteps']} steps" for j in jobs)
        lines.append(
            f"| {machine} | 3.1 Stage A first wave | {labels} | "
            f"`_logs/supervisor_reports/stage31_worker_{machine}.md` + run summaries |"
        )
    lines.extend(
        [
            "",
            "## Full Stage A Registry",
            "",
            f"- Registered runs: {len(matrix_rows)}",
            "- Reduced matrix matches the Stage 3.1 design: 4 assets, 2 timeframes, feature-preset sweep, PPO/SAC/DQN, 2 seeds.",
            "- Held-out 2025 data is not used by these first-wave training inputs.",
        ]
    )
    report_path = PROJECT_ROOT / "_logs" / "supervisor_reports" / "stage31_active_dispatch.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register Stage 3.1 run matrix and first-wave queues.")
    parser.add_argument("--timesteps-scale", type=float, default=1.0)
    parser.add_argument("--dry-smoke", action="store_true", help="Use very short 2k-step queues for infrastructure validation.")
    args = parser.parse_args()

    matrix_rows = generate_full_matrix()
    write_matrix(matrix_rows)
    queues = write_queue_files(args.timesteps_scale, args.dry_smoke)
    write_dispatch_report(queues, matrix_rows)
    print(json.dumps({"ok": True, "matrix_rows": len(matrix_rows), "queues": queues}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
