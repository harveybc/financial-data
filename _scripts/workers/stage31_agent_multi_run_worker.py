#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
AGENT_MULTI_ROOT = Path(os.environ.get("AGENT_MULTI_ROOT", "/home/harveybc/Documents/GitHub/agent-multi"))
NO_TRADE_ABORT_PROGRESS_PERCENT = float(os.environ.get("PROJECT3_NO_TRADE_ABORT_PROGRESS_PERCENT", "20"))
NO_TRADE_POLL_SECONDS = float(os.environ.get("PROJECT3_NO_TRADE_POLL_SECONDS", "15"))

sys.path.insert(0, str(PROJECT_ROOT / "_scripts" / "lib"))
from gpu_lock import acquire_gpu_lock, release_gpu_lock  # noqa: E402
from experiment_ledger import record_stage31_event  # noqa: E402


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


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def write_training_progress(path: str | Path, job: dict, status: str, percent: float, detail: str = "") -> None:
    progress_path = Path(path)
    total_timesteps = int(job.get("timesteps") or 0)
    previous = read_json(progress_path, {})
    carried_keys = {
        "eval_step",
        "trades_total",
        "total_return",
        "profit_percent",
        "final_equity",
        "action_steps",
        "action_hold_count",
        "action_long_count",
        "action_short_count",
        "action_non_hold_count",
        "action_non_hold_rate",
        "action_abs_mean",
        "action_raw_min",
        "action_raw_max",
        "action_deadband_count",
        "action_deadband_rate",
        "execution_entry_actions_seen",
        "execution_entry_orders_submitted",
        "execution_blocked_atr_warmup",
        "execution_blocked_session_filter",
        "execution_blocked_non_positive_atr",
        "execution_blocked_non_positive_size",
        "execution_blocked_non_positive_price",
        "no_trade_diagnosis",
        "no_trade_preflight_file",
        "no_trade_preflight_passed",
        "no_trade_preflight_diagnosis",
    }
    payload = {
        "schema_version": "project3_training_progress_v1",
        "source": "stage31_worker",
        "status": status,
        "run_id": job.get("run_id"),
        "agent_plugin": f"{job.get('algo')}_agent" if job.get("algo") else None,
        "asset": job.get("asset"),
        "timeframe": job.get("timeframe"),
        "features_preset": job.get("preset") or job.get("feature_preset"),
        "seed": job.get("seed"),
        "pid": os.getpid(),
        "updated_at_utc": utc_now(),
        "num_timesteps": int(round(max(0.0, min(100.0, percent)) / 100.0 * total_timesteps)) if total_timesteps else 0,
        "total_timesteps": total_timesteps,
        "progress_percent": round(max(0.0, min(100.0, percent)), 4),
        "progress_detail": detail or status,
    }
    if isinstance(previous, dict):
        for key in carried_keys:
            if key in previous:
                payload[key] = previous[key]
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = progress_path.with_suffix(progress_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(progress_path)


def no_trade_abort_reason(progress_path: str | Path) -> str:
    progress = read_json(Path(progress_path), {})
    if not isinstance(progress, dict):
        return ""
    try:
        pct = float(progress.get("progress_percent") or 0.0)
    except (TypeError, ValueError):
        pct = 0.0
    if pct < NO_TRADE_ABORT_PROGRESS_PERCENT:
        return ""
    if "trades_total" not in progress or progress.get("trades_total") in (None, ""):
        return (
            f"progress {pct:.2f}% reached but trades_total is missing; "
            "telemetry contract violated"
        )
    try:
        trades = float(progress.get("trades_total") or 0.0)
    except (TypeError, ValueError):
        trades = 0.0
    if trades > 0:
        return ""
    diagnosis = progress.get("no_trade_diagnosis") or "no_trade_detected"
    return (
        f"progress {pct:.2f}% reached with trades_total=0 "
        f"(diagnosis={diagnosis}); aborting to avoid wasting compute"
    )


def terminate_process_group(proc: subprocess.Popen, *, kill: bool = False) -> None:
    sig = signal.SIGKILL if kill else signal.SIGTERM
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        return
    except Exception:
        if kill:
            proc.kill()
        else:
            proc.terminate()


def read_tail(path: Path, lines: int = 80) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(data[-lines:])
    except Exception:
        return ""


def notify_telegram(event: str, title: str, message: str) -> None:
    script = PROJECT_ROOT / "_scripts" / "telegram_notify.py"
    if not script.exists():
        return
    try:
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--event",
                event,
                "--title",
                title,
                "--message",
                message,
                "--min-interval-minutes",
                "0",
                "--force",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=25,
        )
    except Exception:
        pass


def job_label(job: dict | None) -> str:
    if not job:
        return "none"
    return (
        f"{job.get('run_id', 'unknown')} "
        f"({job.get('asset', 'unknown')} {job.get('timeframe', 'unknown')} "
        f"{job.get('algo') or job.get('algorithm') or 'unknown'} "
        f"{job.get('preset') or job.get('feature_preset') or 'unknown'} "
        f"seed={job.get('seed', 'unknown')})"
    )


def stage31_message(machine: str, job: dict, status: str, detail: str = "", next_job: dict | None = None) -> str:
    return "\n".join(
        [
            "work_plan_stage: Stage 3.1 Stage A screening",
            f"machine: {machine}",
            f"task: {job.get('run_id', 'unknown')}",
            f"asset: {job.get('asset', 'unknown')}",
            f"timeframe: {job.get('timeframe', 'unknown')}",
            f"algorithm: {job.get('algo') or job.get('algorithm') or 'unknown'}",
            f"feature_preset: {job.get('preset') or job.get('feature_preset') or 'unknown'}",
            f"seed: {job.get('seed', 'unknown')}",
            f"status: {status}",
            f"deliverable_path: {PROJECT_ROOT / 'experiments' / 'stage_a_screening' / 'runs' / machine}",
            f"next_assignment_hint: {job_label(next_job)}",
            "next_action: finish current run, write deliverables, then pull the hinted job unless supervisor overrides it",
            f"detail: {detail}" if detail else "detail: none",
        ]
    )


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


def next_runnable_job(jobs: list[dict], current_run_id: str | None = None) -> dict | None:
    for job in jobs:
        if current_run_id and job.get("run_id") == current_run_id:
            continue
        if is_runnable_status(job.get("status", "pending")):
            return job
    return None


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
        "no_trade_min_trades": 1,
        "no_trade_policy": "hard_kill_with_action_execution_diagnostics",
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
    overrides = job.get("config_overrides") or {}
    if overrides:
        allowed = {
            "continuous_action_threshold",
            "diagnostic_only",
            "ent_coef",
            "exploration_final_eps",
            "exploration_fraction",
            "no_trade_fix_id",
            "no_trade_preflight_required",
            "repeat_training_params",
        }
        unknown = sorted(set(overrides) - allowed)
        if unknown:
            raise ValueError(f"unsupported config_overrides for {job.get('run_id')}: {unknown}")
        common.update(overrides)
    return common


def write_report(
    machine: str,
    status: str,
    jobs: list[dict],
    active_job: dict | None = None,
    detail: str = "",
    next_job: dict | None = None,
) -> None:
    if next_job is None:
        next_job = next_runnable_job(jobs, active_job.get("run_id") if active_job else None)
    payload = {
        "stage": "3.1",
        "status": status,
        "machine": machine,
        "hostname": socket.gethostname(),
        "generated_at": utc_now(),
        "financial_data_git_sha": git_sha(PROJECT_ROOT),
        "agent_multi_git_sha": git_sha(AGENT_MULTI_ROOT),
        "active_job": active_job,
        "next_job_hint": next_job,
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
        f"Next assignment hint: `{job_label(next_job)}`",
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


def run_no_trade_preflight(config_path: Path, output_path: Path, config: dict) -> dict:
    cmd = [
        sys.executable,
        str(AGENT_MULTI_ROOT / "tools" / "project3_no_trade_preflight.py"),
        "--config",
        str(config_path),
        "--output",
        str(output_path),
        "--max-steps",
        str(int(config.get("no_trade_preflight_max_steps") or 5000)),
        "--hold-bars",
        str(int(config.get("no_trade_preflight_hold_bars") or 16)),
        "--min-trades",
        str(int(config.get("no_trade_preflight_min_trades") or 1)),
    ]
    proc = subprocess.run(
        cmd,
        cwd=AGENT_MULTI_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=int(config.get("no_trade_preflight_timeout_seconds") or 300),
    )
    payload = read_json(output_path, {})
    if not isinstance(payload, dict):
        payload = {}
    payload["_exit_code"] = proc.returncode
    payload["_stdout_tail"] = "\n".join(proc.stdout.splitlines()[-40:])
    return payload


def run_one(
    machine: str,
    job: dict,
    timeout_minutes: int,
    queue_path: Path | None = None,
    jobs: list[dict] | None = None,
    job_idx: int | None = None,
) -> dict:
    job = dict(job)
    next_job = next_runnable_job(jobs or [], job.get("run_id"))

    def persist_active_state() -> None:
        if queue_path is None or jobs is None or job_idx is None:
            return
        jobs[job_idx] = dict(job)
        merge_queue_and_write(queue_path, jobs)

    job["status"] = "preparing_input"
    job["trial_id"] = record_stage31_event(
        machine,
        job,
        event_type="preparing_input",
        status="preparing_input",
        detail="Stage 3.1 worker selected run and is exporting input features.",
    )
    persist_active_state()
    write_report(
        machine,
        "running",
        jobs or [job],
        active_job=job,
        detail="exporting Project 3 feature CSV",
        next_job=next_job,
    )
    try:
        input_csv = prepare_input(job)
    except Exception as exc:
        job["status"] = "failed"
        job["failure_reason"] = f"input_preparation_failed: {exc}"
        record_stage31_event(
            machine,
            job,
            event_type="failed",
            status="failed",
            detail="Stage 3.1 input export failed before training.",
            failure_reason=job["failure_reason"],
        )
        notify_telegram(
            f"stage31:{machine}:{job.get('run_id', 'unknown')}:failed_input",
            "Project 3 Stage 3.1 input failed",
            stage31_message(machine, job, "failed", job["failure_reason"], next_job=next_job),
        )
        raise
    job["input_csv"] = input_csv

    run_root = PROJECT_ROOT / "experiments" / "stage_a_screening" / "runs" / machine
    config_root = PROJECT_ROOT / "experiments" / "stage_a_screening" / "configs" / machine
    no_trade_state_root = PROJECT_ROOT / "experiments" / "stage_a_screening" / "no_trade_state" / machine
    config_root.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    no_trade_state_root.mkdir(parents=True, exist_ok=True)
    job["output_dir"] = str(run_root)

    config = algo_defaults(job)
    config["run_id"] = job["run_id"]
    config["timeframe"] = job["timeframe"]
    config["save_model"] = str(run_root / f"{job['run_id']}_policy.zip")
    config["results_file"] = str(run_root / f"{job['run_id']}_summary.json")
    config["save_config"] = str(run_root / f"{job['run_id']}_config_out.json")
    config["return_trace_file"] = str(run_root / f"{job['run_id']}_return_trace.csv")
    config["training_progress_file"] = str(run_root / f"{job['run_id']}_training_progress.json")
    config["progress_update_interval_steps"] = max(250, min(2000, int(job["timesteps"]) // 100))
    config["no_trade_preflight_file"] = str(no_trade_state_root / f"{job['run_id']}.json")
    config["no_trade_preflight_max_steps"] = int(job.get("no_trade_preflight_max_steps") or 5000)
    config["no_trade_preflight_hold_bars"] = int(job.get("no_trade_preflight_hold_bars") or 16)
    config["no_trade_preflight_min_trades"] = int(job.get("no_trade_preflight_min_trades") or 1)
    job["training_progress_file"] = config["training_progress_file"]
    job["no_trade_preflight_file"] = config["no_trade_preflight_file"]
    write_training_progress(config["training_progress_file"], job, "registered", 0.0, "config written; training not started")
    config_path = config_root / f"{job['run_id']}.json"
    write_json(config_path, config)
    job["config"] = str(config_path)

    preflight = run_no_trade_preflight(config_path, Path(config["no_trade_preflight_file"]), config)
    job["no_trade_preflight"] = preflight
    job["no_trade_preflight_passed"] = bool(preflight.get("preflight_passed"))
    job["no_trade_preflight_diagnosis"] = preflight.get("diagnosis")
    write_training_progress(
        config["training_progress_file"],
        job,
        "no_trade_preflight_passed" if job["no_trade_preflight_passed"] else "blocked_no_trade_preflight",
        0.0,
        (
            f"no-trade preflight diagnosis={preflight.get('diagnosis')} "
            f"closed_trades={preflight.get('closed_trades')} "
            f"orders={preflight.get('entry_orders_submitted')}"
        ),
    )
    if not job["no_trade_preflight_passed"]:
        job["status"] = "blocked_no_trade_preflight"
        job["failure_reason"] = (
            f"no_trade_preflight_failed: {preflight.get('diagnosis')} "
            f"closed_trades={preflight.get('closed_trades')} "
            f"orders={preflight.get('entry_orders_submitted')}"
        )
        record_stage31_event(
            machine,
            job,
            event_type="blocked_no_trade_preflight",
            status=job["status"],
            config=config,
            detail="Forced-action no-trade preflight failed before training.",
            failure_reason=job["failure_reason"],
        )
        notify_telegram(
            f"stage31:{machine}:{job.get('run_id', 'unknown')}:blocked_no_trade_preflight",
            "Project 3 Stage 3.1 no-trade preflight blocked run",
            stage31_message(machine, job, job["status"], job["failure_reason"], next_job=next_job),
        )
        persist_active_state()
        write_report(
            machine,
            "blocked_no_trade_preflight",
            jobs or [job],
            active_job=job,
            detail=job["failure_reason"],
            next_job=next_job,
        )
        return job

    job["trial_id"] = record_stage31_event(
        machine,
        job,
        event_type="registered",
        status="registered",
        config=config,
        detail="Stage 3.1 trial registered before training start.",
    )

    job["status"] = "training"
    write_training_progress(config["training_progress_file"], job, "subprocess_starting", 0.0, "agent-multi seed_sweep subprocess starting")
    record_stage31_event(
        machine,
        job,
        event_type="training",
        status="training",
        config=config,
        detail="Stage 3.1 training process is starting.",
    )
    persist_active_state()
    write_report(
        machine,
        "running",
        jobs or [job],
        active_job=job,
        detail="agent-multi seed_sweep running",
        next_job=next_job,
    )
    notify_telegram(
        f"stage31:{machine}:{job.get('run_id', 'unknown')}:start",
        "Project 3 Stage 3.1 run started",
        stage31_message(machine, job, "training", next_job=next_job),
    )

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
        stdout_log = run_root / f"{job['run_id']}_subprocess_stdout.log"
        aborted_reason = ""
        with stdout_log.open("w", encoding="utf-8") as stdout_handle:
            proc = subprocess.Popen(
                cmd,
                cwd=AGENT_MULTI_ROOT,
                text=True,
                stdout=stdout_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            deadline = datetime.now(timezone.utc).timestamp() + timeout_minutes * 60
            while proc.poll() is None:
                if datetime.now(timezone.utc).timestamp() >= deadline:
                    aborted_reason = f"training_timeout_after_{timeout_minutes}_minutes"
                    terminate_process_group(proc)
                    break
                reason = no_trade_abort_reason(config["training_progress_file"])
                if reason:
                    aborted_reason = reason
                    terminate_process_group(proc)
                    break
                try:
                    proc.wait(timeout=NO_TRADE_POLL_SECONDS)
                except subprocess.TimeoutExpired:
                    continue
            if proc.poll() is None:
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    terminate_process_group(proc, kill=True)
                    proc.wait(timeout=30)
        stdout_text = read_tail(stdout_log)
        if aborted_reason and proc.returncode == 0:
            proc.returncode = 124
        job["no_trade_abort_reason"] = aborted_reason
    except Exception as exc:
        job["status"] = "failed"
        job["failure_reason"] = f"training_failed: {exc}"
        record_stage31_event(
            machine,
            job,
            event_type="failed",
            status="failed",
            config=config,
            detail="Stage 3.1 training subprocess failed.",
            failure_reason=job["failure_reason"],
        )
        notify_telegram(
            f"stage31:{machine}:{job.get('run_id', 'unknown')}:failed_exception",
            "Project 3 Stage 3.1 run failed",
            stage31_message(machine, job, "failed", job["failure_reason"], next_job=next_job),
        )
        raise
    finally:
        if locked:
            release_gpu_lock()

    job["exit_code"] = proc.returncode
    job["stdout_tail"] = "\n".join(str(locals().get("stdout_text", "") or "").splitlines()[-80:])
    if job.get("no_trade_abort_reason"):
        job["status"] = "blocked_no_trade_early_abort"
        job["failure_reason"] = job["no_trade_abort_reason"]
    else:
        job["status"] = "complete" if proc.returncode == 0 else "failed"
    write_training_progress(
        config["training_progress_file"],
        job,
        "subprocess_complete" if proc.returncode == 0 else job["status"],
        100.0 if proc.returncode == 0 else max(
            0.0,
            safe_float(read_json(Path(config["training_progress_file"]), {}).get("progress_percent")),
        ),
        job.get("failure_reason") or "agent-multi seed_sweep subprocess finished",
    )
    record_stage31_event(
        machine,
        job,
        event_type=job["status"],
        status=job["status"],
        config=config,
        detail="Stage 3.1 training subprocess finished.",
        failure_reason=None if proc.returncode == 0 else job.get("failure_reason") or "nonzero_exit_code",
    )
    notify_telegram(
        f"stage31:{machine}:{job.get('run_id', 'unknown')}:{job['status']}",
        f"Project 3 Stage 3.1 run {job['status']}",
        stage31_message(
            machine,
            job,
            job["status"],
            "summary/model artifacts written" if proc.returncode == 0 else f"nonzero_exit_code={proc.returncode}",
            next_job=next_job,
        ),
    )
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
            result = run_one(
                machine,
                jobs[idx],
                timeout_minutes=args.timeout_minutes,
                queue_path=queue_path,
                jobs=jobs,
                job_idx=idx,
            )
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
