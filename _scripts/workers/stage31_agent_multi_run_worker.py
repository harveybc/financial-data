#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
AGENT_MULTI_ROOT = Path(os.environ.get("AGENT_MULTI_ROOT", "/home/harveybc/Documents/GitHub/agent-multi"))

sys.path.insert(0, str(PROJECT_ROOT / "_scripts" / "lib"))
from gpu_lock import acquire_gpu_lock, release_gpu_lock  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def acquire_worker_lock(machine: str):
    lock_path = PROJECT_ROOT / "_metadata" / f"stage31_worker_{machine}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(json.dumps({"skipped": "worker_already_running", "machine": machine}, indent=2))
        lock_file.close()
        return None
    lock_file.write(f"pid={os.getpid()}\nstarted_at={utc_now()}\n")
    lock_file.flush()
    return lock_file


def is_runnable_status(status: object) -> bool:
    value = str(status or "pending").lower()
    if value in {"", "pending", "queued", "retry", "needs_retry"}:
        return True
    if value in {"complete", "training", "running", "preparing_input", "skipped_busy"}:
        return False
    if value.startswith("blocked") or value.startswith("failed") or value.startswith("skipped"):
        return False
    return True


def merge_queue_and_write(path: Path, jobs: list[dict]) -> list[dict]:
    """Persist statuses without dropping jobs appended by the supervisor while this worker ran."""
    current = read_json(path, [])
    if not isinstance(current, list):
        current = []
    updates = {job.get("run_id"): job for job in jobs if job.get("run_id")}
    merged = []
    seen = set()
    for item in current:
        run_id = item.get("run_id")
        if run_id in updates:
            merged.append(updates[run_id])
            seen.add(run_id)
        else:
            merged.append(item)
    for job in jobs:
        run_id = job.get("run_id")
        if run_id not in seen:
            merged.append(job)
    write_json(path, merged)
    return merged


def git_sha(path: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    except Exception:
        return "unknown"


def algo_defaults(job: dict) -> dict:
    algo = job["algo"].lower()
    common = {
        "mode": "train",
        "env_plugin": "gym_fx_env",
        "pipeline_plugin": "rl_pipeline",
        "optimizer_plugin": "default_optimizer",
        "env_mode": "training",
        "input_data_file": job["input_csv"],
        "date_column": "DATE_TIME",
        "price_column": "CLOSE",
        "headers": True,
        "window_size": 32,
        "initial_cash": 10000.0,
        "commission": 0.0002 if "usdt" in job["asset"] else 0.00005,
        "slippage": 0.0,
        "data_feed_plugin": "default_data_feed",
        "broker_plugin": "default_broker",
        "strategy_plugin": "direct_atr_sltp",
        "atr_period": 14,
        "k_sl": 2.0,
        "k_tp": 3.0,
        "preprocessor_plugin": "default_preprocessor",
        "reward_plugin": "pnl_reward",
        "metrics_plugin": "default_metrics",
        "features_preset": job["preset"],
        "asset": f"{job['asset']}_{job['timeframe']}",
        "total_timesteps": int(job["timesteps"]),
        "eval_seed": int(job["seed"]),
        "train_seed": int(job["seed"]),
        "device": job.get("device", "cuda"),
        "agent_verbose": 0,
        "quiet_mode": True,
    }
    if algo == "ppo":
        common.update(
            {
                "agent_plugin": "ppo_agent",
                "position_size": 1.0 if "usdt" not in job["asset"] else 0.01,
                "learning_rate": 0.0003,
                "n_steps": 1024,
                "batch_size": 128,
                "n_epochs": 10,
                "gamma": 0.99,
                "gae_lambda": 0.95,
                "clip_range": 0.2,
                "ent_coef": 0.01,
                "vf_coef": 0.5,
            }
        )
    elif algo == "sac":
        common.update(
            {
                "agent_plugin": "sac_agent",
                "position_size": 0.01 if "usdt" in job["asset"] else 1.0,
                "rel_volume": 0.05,
                "leverage": 1.0,
                "size_mode": "notional",
                "min_order_volume": 0.0,
                "max_order_volume": 100.0,
                "action_space_mode": "continuous",
                "continuous_action_threshold": 0.10,
                "learning_rate": 0.0001,
                "buffer_size": 200000,
                "learning_starts": min(20000, max(1000, int(job["timesteps"]) // 5)),
                "batch_size": 256,
                "tau": 0.005,
                "gamma": 0.99,
                "train_freq": 1,
                "gradient_steps": 1,
                "ent_coef": "auto",
                "use_sde": True,
            }
        )
    elif algo == "dqn":
        common.update(
            {
                "agent_plugin": "dqn_agent",
                "position_size": 1.0 if "usdt" not in job["asset"] else 0.01,
                "learning_rate": 0.0001,
                "buffer_size": 200000,
                "learning_starts": min(5000, max(500, int(job["timesteps"]) // 10)),
                "batch_size": 128,
                "tau": 1.0,
                "gamma": 0.99,
                "train_freq": 4,
                "gradient_steps": 1,
                "target_update_interval": 1000,
                "exploration_fraction": 0.2,
                "exploration_initial_eps": 1.0,
                "exploration_final_eps": 0.05,
            }
        )
    else:
        raise ValueError(f"unknown algo: {algo}")
    return common


def write_report(machine: str, status: str, jobs: list[dict], active_job: dict | None = None, detail: str = "") -> None:
    payload = {
        "stage": "3.1",
        "status": status,
        "machine": machine,
        "hostname": socket.gethostname(),
        "generated_at": utc_now(),
        "financial_data_git_sha": git_sha(PROJECT_ROOT),
        "agent_multi_git_sha": git_sha(AGENT_MULTI_ROOT),
        "active_job": active_job,
        "jobs": jobs,
        "detail": detail,
    }
    write_json(PROJECT_ROOT / "_metadata" / f"stage31_worker_{machine}.json", payload)
    lines = [
        f"# Stage 3.1 Worker Status — {machine}",
        "",
        f"Generated: {payload['generated_at']}",
        f"Host: `{payload['hostname']}`",
        f"Status: `{status}`",
        f"Detail: {detail or '-'}",
        "",
        "| Run | Stage | Status | Deliverable |",
        "| --- | --- | --- | --- |",
    ]
    for job in jobs:
        lines.append(
            f"| {job.get('run_id', '-')} | {job.get('stage', '3.1')} | {job.get('status', '-')} | "
            f"`{job.get('run_dir', job.get('output_dir', '-'))}` |"
        )
    out = PROJECT_ROOT / "_logs" / "supervisor_reports" / f"stage31_worker_{machine}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_input(job: dict) -> str:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "_scripts" / "workers" / "stage31_prepare_inputs_worker.py"),
        "--asset",
        job["asset"],
        "--timeframe",
        job["timeframe"],
        "--preset",
        job["preset"],
        "--split",
        "train",
    ]
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)
    return str(
        PROJECT_ROOT
        / "experiments"
        / "stage_a_screening"
        / "inputs"
        / job["asset"]
        / job["timeframe"]
        / job["preset"]
        / "train.csv"
    )


def run_one(machine: str, job: dict, timeout_minutes: int) -> dict:
    job = dict(job)
    job["status"] = "preparing_input"
    write_report(machine, "running", [job], active_job=job, detail="exporting Project 3 feature CSV")
    input_csv = prepare_input(job)
    job["input_csv"] = input_csv

    run_root = PROJECT_ROOT / "experiments" / "stage_a_screening" / "runs" / machine
    config_root = PROJECT_ROOT / "experiments" / "stage_a_screening" / "configs" / machine
    config_root.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    job["output_dir"] = str(run_root)

    config = algo_defaults(job)
    config["save_model"] = str(run_root / f"{job['run_id']}_policy.zip")
    config["results_file"] = str(run_root / f"{job['run_id']}_summary.json")
    config["save_config"] = str(run_root / f"{job['run_id']}_config_out.json")
    config_path = config_root / f"{job['run_id']}.json"
    write_json(config_path, config)
    job["config"] = str(config_path)

    job["status"] = "training"
    write_report(machine, "running", [job], active_job=job, detail="agent-multi seed_sweep running")

    command_label = f"agent-multi {job['algo']} {job['asset']} {job['timeframe']} {job['preset']} seed={job['seed']}"
    locked = False
    if str(job.get("device", "cuda")).lower() != "cpu":
        acquire_gpu_lock(command=command_label, expected_duration_minutes=timeout_minutes, stage="3.1")
        locked = True
    try:
        cmd = [
            sys.executable,
            str(AGENT_MULTI_ROOT / "tools" / "seed_sweep.py"),
            "--config",
            str(config_path),
            "--seeds",
            str(job["seed"]),
            "--log_root",
            str(run_root),
            "--run_tag",
            "project3_stage31_firstwave",
        ]
        proc = subprocess.run(
            cmd,
            cwd=AGENT_MULTI_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_minutes * 60,
        )
    finally:
        if locked:
            release_gpu_lock()

    job["exit_code"] = proc.returncode
    job["stdout_tail"] = "\n".join(proc.stdout.splitlines()[-80:])
    job["status"] = "complete" if proc.returncode == 0 else "failed"
    return job


def main() -> int:
    parser = argparse.ArgumentParser(description="Run queued Project 3 Stage 3.1 agent-multi jobs.")
    parser.add_argument("--machine", required=True)
    parser.add_argument("--queue", default="")
    parser.add_argument("--max-jobs", type=int, default=1)
    parser.add_argument("--timeout-minutes", type=int, default=180)
    args = parser.parse_args()

    machine = args.machine
    worker_lock = acquire_worker_lock(machine)
    if worker_lock is None:
        return 0

    queue_path = Path(args.queue) if args.queue else PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"
    jobs = read_json(queue_path, [])
    completed = []
    try:
        if not jobs:
            write_report(machine, "idle", [], detail=f"no jobs in queue {queue_path}")
            return 0

        pending_indices = [
            idx
            for idx, job in enumerate(jobs)
            if is_runnable_status(job.get("status", "pending"))
        ]
        if not pending_indices:
            write_report(machine, "idle", jobs, detail=f"no pending jobs in queue {queue_path}")
            return 0

        for idx in pending_indices[: args.max_jobs]:
            result = run_one(machine, jobs[idx], timeout_minutes=args.timeout_minutes)
            jobs[idx] = result
            completed.append(result)
            jobs = merge_queue_and_write(queue_path, jobs)

        overall = "complete" if all(j.get("status") == "complete" for j in completed) else "needs_review"
        write_report(machine, overall, jobs, detail=f"ran {len(completed)} job(s)")
        return 0 if overall == "complete" else 1
    except Exception as exc:
        detail = str(exc)
        status = "skipped_busy" if "GPU lock already present" in detail else "failed"
        failed = completed + [{"status": status, "error": detail, "traceback": traceback.format_exc()}]
        write_report(machine, status, failed, detail=detail)
        return 0 if status == "skipped_busy" else 1
    finally:
        worker_lock.close()


if __name__ == "__main__":
    sys.exit(main())
