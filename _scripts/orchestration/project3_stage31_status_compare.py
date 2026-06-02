#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import shlex
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
PROGRESS_SCRIPT = ROOT / "_scripts" / "orchestration" / "project3_stage31_pending_eta_report.py"
PROGRESS_CSV = ROOT / "experiments" / "stage_a_screening" / "job_timing" / "stage31_task_progress.csv"
SNAPSHOT = ROOT / "_metadata" / "stage31_status_compare_snapshot.json"
OUT_JSON = ROOT / "_logs" / "supervisor_reports" / "stage31_status_compare.json"
OUT_MD = ROOT / "_logs" / "supervisor_reports" / "stage31_status_compare.md"
SUPERVISOR_META = ROOT / "_metadata" / "stage31_supervisor_tick.json"
SUPERVISOR_SLEEP_SECONDS = int(os.environ.get("PROJECT3_STAGE31_SUPERVISOR_SLEEP_SECONDS", "60"))
LOCAL_TZ = ZoneInfo(os.environ.get("PROJECT3_LOCAL_TZ", "America/Bogota"))

REMOTE = {
    "dragon": ("harveybc@192.0.2.13", "22022"),
    "gamma": ("harveybc@192.0.2.15", "22022"),
}
ACTIVE = {"training", "running", "registered", "preparing_input"}
RUNNABLE = {"", "pending", "queued", "retry", "needs_retry"}
ANOMALY_SECONDS = int(os.environ.get("PROJECT3_STATUS_ANOMALY_SECONDS", "180"))
MIN_PROGRESS_DELTA = float(os.environ.get("PROJECT3_STATUS_MIN_PROGRESS_DELTA", "0.05"))
NO_TRADE_ANOMALY_PROGRESS_PERCENT = float(os.environ.get("PROJECT3_NO_TRADE_ANOMALY_PROGRESS_PERCENT", "20"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_cmd(cmd: str, timeout: int = 25) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)


def run_remote(machine: str, script: str, timeout: int = 25) -> subprocess.CompletedProcess:
    host, port = REMOTE[machine]
    return subprocess.run(
        ["ssh", "-p", port, host, f"bash -lc {shlex.quote(script)}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )


def remote_host(machine: str) -> str:
    return REMOTE[machine][0]


def remote_port(machine: str) -> str:
    return REMOTE[machine][1]


def sync_remote_state() -> None:
    """Pull the queue/progress files before status reporting.

    The supervisor also syncs these files, but a manual status request can land
    between ticks. Pulling them here prevents stale local queue rows from being
    mistaken for idle workers.
    """
    for machine in ("dragon", "gamma"):
        host = remote_host(machine)
        port = remote_port(machine)
        rels = [
            f"_logs/supervisor_reports/stage31_worker_{machine}.md",
            f"_metadata/stage31_worker_{machine}.json",
            f"experiments/stage_a_screening/queues/{machine}.json",
            f"artifacts/run_ledger_events/{machine}.jsonl",
        ]
        for rel in rels:
            src = f"{host}:{ROOT / rel}"
            dst = ROOT / rel
            if rel.endswith(f"{machine}.jsonl"):
                dst = ROOT / "artifacts" / "run_ledger_events" / f"{machine}.remote.jsonl"
            dst.parent.mkdir(parents=True, exist_ok=True)
            run_cmd(f"rsync -az -e 'ssh -p {shlex.quote(port)}' {shlex.quote(src)} {shlex.quote(str(dst))} 2>/dev/null || true", timeout=25)
        progress_dst = ROOT / "experiments" / "stage_a_screening" / "runs" / machine
        progress_dst.mkdir(parents=True, exist_ok=True)
        progress_src = f"{host}:{ROOT / 'experiments' / 'stage_a_screening' / 'runs' / machine}/*_training_progress.json"
        run_cmd(
            f"rsync -az -e 'ssh -p {shlex.quote(port)}' {progress_src} {shlex.quote(str(progress_dst))}/ 2>/dev/null || true",
            timeout=25,
        )


def parse_ts(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def load_progress_rows() -> list[dict[str, str]]:
    proc = run_cmd(f"{shlex.quote(sys.executable)} {shlex.quote(str(PROGRESS_SCRIPT))}", timeout=90)
    if proc.returncode != 0:
        raise RuntimeError(f"progress report failed with {proc.returncode}:\n{proc.stdout}")
    if not PROGRESS_CSV.exists():
        raise FileNotFoundError(PROGRESS_CSV)
    with PROGRESS_CSV.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def machine_rows(rows: list[dict[str, str]], machine: str) -> list[dict[str, str]]:
    return [row for row in rows if row.get("machine") == machine]


def queue_status_map(machine: str) -> dict[str, str]:
    queue = read_json(ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json", [])
    statuses: dict[str, str] = {}
    if isinstance(queue, list):
        for job in queue:
            run_id = str(job.get("run_id") or "")
            if run_id:
                statuses[run_id] = str(job.get("status") or "pending").lower()
    return statuses


def row_effective_status(row: dict[str, str], queue_statuses: dict[str, str] | None = None) -> str:
    run_id = str(row.get("run_id") or "")
    if queue_statuses and run_id in queue_statuses:
        return queue_statuses[run_id]
    return str(row.get("status") or "").lower()


def active_queue_rows(
    rows: list[dict[str, str]],
    machine: str,
    queue_statuses: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    return [row for row in machine_rows(rows, machine) if row_effective_status(row, queue_statuses) in ACTIVE]


def live_run_ids_from_worker_processes(machine: str, worker: dict[str, Any]) -> list[str]:
    """Extract the actually running run ids from seed_sweep config paths.

    Queue rows can be stale for one or more supervisor ticks when a subprocess
    finished but the queue has not been reconciled yet. The process table is the
    source of truth for "what is currently burning compute" on a worker.
    """
    marker = f"experiments/stage_a_screening/configs/{machine}/"
    live: list[str] = []
    for line in worker.get("processes") or []:
        if marker not in line:
            continue
        tail = line.split(marker, 1)[1].split()[0]
        if tail.endswith(".json"):
            run_id = Path(tail).name[:-5]
            if run_id and run_id not in live:
                live.append(run_id)
    return live


def active_row(
    rows: list[dict[str, str]],
    machine: str,
    live_run_ids: list[str] | None = None,
    queue_statuses: dict[str, str] | None = None,
) -> dict[str, str] | None:
    active_rows = active_queue_rows(rows, machine, queue_statuses)
    live_run_ids = live_run_ids or []
    for run_id in live_run_ids:
        for row in active_rows:
            if row.get("run_id") == run_id:
                return row
        for row in machine_rows(rows, machine):
            if row.get("run_id") == run_id:
                return row
    for row in active_rows:
        if row_effective_status(row, queue_statuses) in ACTIVE:
            return row
    return None


def queue_counts(machine: str) -> dict[str, int]:
    queue = read_json(ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json", [])
    counts: Counter[str] = Counter()
    if isinstance(queue, list):
        for job in queue:
            counts[str(job.get("status") or "pending").lower()] += 1
    return dict(counts)


def gpu_probe(machine: str) -> dict[str, Any]:
    gpu_cmd = (
        "if command -v nvidia-smi >/dev/null 2>&1; then "
        "nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total "
        "--format=csv,noheader,nounits; "
        "echo __PROCESSES__; "
        "nvidia-smi --query-compute-apps=pid,process_name,used_memory "
        "--format=csv,noheader,nounits 2>/dev/null || true; "
        "else echo NO_NVIDIA_SMI; fi"
    )
    try:
        if machine in REMOTE:
            proc = run_remote(machine, gpu_cmd, timeout=25)
        else:
            cmd = f"bash -lc {shlex.quote(gpu_cmd)}"
            proc = run_cmd(cmd, timeout=25)
    except Exception as exc:
        return {"available": False, "error": str(exc), "raw": ""}
    text = proc.stdout.strip()
    if "NO_NVIDIA_SMI" in text:
        return {"available": False, "raw": text, "gpus": [], "processes": []}
    gpu_part, _, proc_part = text.partition("__PROCESSES__")
    gpus = []
    for line in gpu_part.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 4:
            gpus.append(
                {
                    "index": parts[0],
                    "utilization_gpu_percent": parts[1],
                    "memory_used_mb": parts[2],
                    "memory_total_mb": parts[3],
                }
            )
    processes = []
    for line in proc_part.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 3:
            processes.append({"pid": parts[0], "name": parts[1], "used_memory_mb": parts[2]})
    return {"available": True, "raw": text, "gpus": gpus, "processes": processes}


def worker_probe(machine: str) -> dict[str, Any]:
    ps_cmd = (
        "ps -eo pid=,etimes=,args= | "
        "awk '(/stage31_agent_multi_run_worker.py/ || /agent-multi\\/tools\\/seed_sweep.py/) "
        "&& !/awk/ && !/bash -lc/ {print}' || true"
    )
    try:
        if machine in REMOTE:
            proc = run_remote(machine, ps_cmd, timeout=20)
        else:
            cmd = f"bash -lc {shlex.quote(ps_cmd)}"
            proc = run_cmd(cmd, timeout=20)
    except Exception as exc:
        return {"process_count": 0, "error": str(exc), "processes": []}
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return {"process_count": len(lines), "processes": lines}


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def display_metric(active: dict[str, Any], key: str, default: str = "metric_pending") -> object:
    value = active.get(key)
    if value in (None, ""):
        return default
    return value


def compare_machine(current: dict[str, Any], previous: dict[str, Any] | None, generated_at: datetime) -> dict[str, Any]:
    active = current.get("active_task") or {}
    prev_active = (previous or {}).get("active_task") or {}
    prev_at = parse_ts((previous or {}).get("generated_at_utc"))
    elapsed_since_previous = (generated_at - prev_at).total_seconds() if prev_at else None

    current_run = active.get("run_id") or ""
    previous_run = prev_active.get("run_id") or ""
    current_pct = safe_float(active.get("progress_percent"))
    previous_pct = safe_float(prev_active.get("progress_percent"))
    trades_raw = active.get("trades_total")
    trades_metric_present = trades_raw not in (None, "")
    trades_total = safe_float(trades_raw)
    no_trade_issue = (
        bool(current_run)
        and current_pct >= NO_TRADE_ANOMALY_PROGRESS_PERCENT
        and trades_metric_present
        and trades_total <= 0
    )
    missing_trade_metric_issue = (
        bool(current_run)
        and current_pct >= NO_TRADE_ANOMALY_PROGRESS_PERCENT
        and not trades_metric_present
    )

    if not current_run:
        status = "idle_or_no_active_task"
        progressed = False
        anomaly = False
        detail = "No active task on this machine."
    elif not previous:
        status = "baseline_recorded"
        progressed = True
        anomaly = False
        detail = "No previous snapshot existed."
    elif current_run != previous_run:
        status = "new_task_running"
        progressed = True
        anomaly = False
        detail = f"Previous task `{previous_run or '-'}` changed to `{current_run}`."
    else:
        delta = current_pct - previous_pct
        progressed = delta >= MIN_PROGRESS_DELTA
        if progressed:
            status = "progressed"
            anomaly = False
            detail = f"Same task advanced by {delta:.2f} percentage points."
        elif elapsed_since_previous is not None and elapsed_since_previous >= ANOMALY_SECONDS:
            status = "anomaly_no_progress"
            anomaly = True
            detail = (
                f"Same task showed {delta:.2f} percentage-point progress over "
                f"{elapsed_since_previous:.0f}s; investigate worker/GPU/logs."
            )
        else:
            status = "waiting_for_next_sample"
            anomaly = False
        detail = (
            f"Same task has not moved yet, but only "
            f"{elapsed_since_previous:.0f}s elapsed since the last snapshot."
            if elapsed_since_previous is not None
            else "Same task, no previous timestamp available."
        )

    if no_trade_issue:
        status = "anomaly_no_trades_at_progress_threshold"
        anomaly = True
        detail = (
            f"Task is {current_pct:.2f}% complete with trades_total={trades_total:g}; "
            f"threshold is {NO_TRADE_ANOMALY_PROGRESS_PERCENT:.2f}%. "
            "Investigate policy action collapse, SAC deadband, or execution guards immediately."
        )
    elif missing_trade_metric_issue:
        status = "anomaly_missing_trade_progress_metric"
        anomaly = True
        detail = (
            f"Task is {current_pct:.2f}% complete but progress heartbeat has no trades_total field; "
            "worker/agent telemetry is incomplete."
        )

    return {
        "comparison_status": status,
        "progressed_or_new_task": progressed,
        "anomaly": anomaly,
        "detail": detail,
        "previous_run_id": previous_run,
        "previous_progress_percent": previous_pct if previous_run else "",
        "seconds_since_previous_status": elapsed_since_previous,
    }


def runtime_issues(machine: str, payload: dict[str, Any]) -> list[str]:
    active = payload.get("active_task") or {}
    status = str(active.get("status") or "").lower()
    source = str(active.get("progress_source") or "")
    pct = safe_float(active.get("progress_percent"))
    detail = str(active.get("progress_detail") or "")
    completed_waiting_for_reconcile = (
        status in ACTIVE
        and pct >= 100.0
        and source == "exact_sb3_callback"
        and (
            detail.startswith("subprocess_complete:")
            or detail.startswith("training_complete:")
        )
    )
    issues: list[str] = []
    worker_count = int(payload.get("worker_processes", {}).get("process_count") or 0)
    live_run_ids = payload.get("live_active_run_ids") or []
    counts = payload.get("queue_counts") or {}
    pending_count = sum(int(counts.get(status, 0) or 0) for status in RUNNABLE)
    if machine in REMOTE and live_run_ids and not active:
        issues.append("live_process_without_matching_queue_or_progress_row")
    gpu = payload.get("gpu") or {}
    gpu_processes = gpu.get("processes") or []
    project_gpu_processes = [
        proc for proc in gpu_processes
        if "python" in str(proc.get("name") or "").lower()
        or "agent-multi" in str(proc.get("name") or "").lower()
    ]
    if not active and project_gpu_processes:
        issues.append("project_gpu_process_without_tracked_active_task")
    if not active and pending_count > 0 and not live_run_ids:
        if worker_count <= 0:
            issues.append("idle_with_pending_work_no_worker")
        else:
            issues.append("worker_alive_without_registered_active_task")
    if not active:
        return issues
    if machine in REMOTE and status in ACTIVE and worker_count == 0 and not completed_waiting_for_reconcile:
        issues.append("active_queue_row_without_worker_process")
    gpu_process_count = len(gpu_processes)
    if machine in REMOTE and status == "training" and gpu.get("available") and gpu_process_count == 0 and pct < 100.0:
        issues.append("training_row_without_gpu_compute_process")
    if (
        status in ACTIVE
        and pct >= 100.0
        and source == "exact_sb3_callback"
        and worker_count == 0
        and not completed_waiting_for_reconcile
    ):
        issues.append("completed_progress_file_but_queue_still_active_and_no_worker")
    if machine in REMOTE and status in ACTIVE and live_run_ids and active.get("run_id") not in live_run_ids:
        issues.append("selected_active_row_does_not_match_live_process")
    return issues


def summarize_gpu(gpu: dict[str, Any]) -> str:
    if not gpu.get("available"):
        return "nvidia-smi unavailable"
    gpus = gpu.get("gpus") or []
    procs = gpu.get("processes") or []
    if not gpus:
        return "nvidia-smi available, no GPU rows"
    util = "; ".join(
        f"gpu{item['index']} {item['utilization_gpu_percent']}% mem {item['memory_used_mb']}/{item['memory_total_mb']}MB"
        for item in gpus
    )
    return f"{util}; compute_procs={len(procs)}"


def supervisor_cycle_info(now: datetime) -> dict[str, Any]:
    meta = read_json(SUPERVISOR_META, {})
    last_tick = parse_ts(meta.get("generated_at")) if isinstance(meta, dict) else None
    if last_tick is None:
        return {
            "last_tick_utc": "",
            "last_tick_local": "",
            "next_scheduled_tick_utc": "",
            "next_scheduled_tick_local": "",
            "seconds_until_next_tick": "",
            "seconds_overdue": "",
            "sleep_seconds": SUPERVISOR_SLEEP_SECONDS,
            "status": "unknown",
        }
    next_tick = last_tick + timedelta(seconds=SUPERVISOR_SLEEP_SECONDS)
    delta = (next_tick - now).total_seconds()
    return {
        "last_tick_utc": last_tick.isoformat(),
        "last_tick_local": last_tick.astimezone(LOCAL_TZ).isoformat(),
        "next_scheduled_tick_utc": next_tick.isoformat(),
        "next_scheduled_tick_local": next_tick.astimezone(LOCAL_TZ).isoformat(),
        "seconds_until_next_tick": round(max(0.0, delta), 3),
        "seconds_overdue": round(max(0.0, -delta), 3),
        "sleep_seconds": SUPERVISOR_SLEEP_SECONDS,
        "status": "scheduled" if delta >= 0 else "due_or_running",
    }


def main() -> int:
    generated_at = utc_now()
    sync_remote_state()
    rows = load_progress_rows()
    previous = read_json(SNAPSHOT, {})
    prev_machines = previous.get("machines", {}) if isinstance(previous, dict) else {}
    supervisor_cycle = supervisor_cycle_info(generated_at)

    machines: dict[str, Any] = {}
    for machine in ("dragon", "gamma", "omega"):
        worker = worker_probe(machine)
        live_run_ids = live_run_ids_from_worker_processes(machine, worker)
        queue_statuses = queue_status_map(machine)
        queue_active = active_queue_rows(rows, machine, queue_statuses)
        active = active_row(rows, machine, live_run_ids, queue_statuses)
        active_payload = dict(active) if active else None
        if active_payload and active_payload.get("run_id") in live_run_ids:
            status = str(active_payload.get("status") or "").lower()
            if status not in ACTIVE:
                active_payload["status"] = "live_process_pending_queue_sync"
                if str(active_payload.get("progress_source") or "") == "queued":
                    active_payload["progress_source"] = "live_process_no_progress_yet"
                    active_payload["progress_detail"] = (
                        "live seed_sweep process detected; waiting for first training_progress update"
                    )
        if not active_payload and live_run_ids:
            active_payload = {
                "machine": machine,
                "run_id": live_run_ids[0],
                "status": "live_process_unregistered",
                "progress_percent": "",
                "progress_source": "live_process_no_queue_row",
                "progress_detail": (
                    "live seed_sweep process detected, but the queue/progress table "
                    "has not registered it yet"
                ),
            }
        machine_payload = {
            "machine": machine,
            "generated_at_utc": generated_at.isoformat(),
            "tasks_left": sum(1 for row in machine_rows(rows, machine) if str(row.get("status") or "").lower() in ACTIVE | RUNNABLE),
            "queue_counts": queue_counts(machine),
            "active_queue_run_ids": [row.get("run_id", "") for row in queue_active],
            "live_active_run_ids": live_run_ids,
            "active_task": active_payload,
            "gpu": gpu_probe(machine),
            "worker_processes": worker,
        }
        machine_payload["comparison"] = compare_machine(machine_payload, prev_machines.get(machine), generated_at)
        issues = runtime_issues(machine, machine_payload)
        machine_payload["runtime_issues"] = issues
        if issues:
            machine_payload["comparison"]["comparison_status"] = "runtime_anomaly"
            machine_payload["comparison"]["anomaly"] = True
            machine_payload["comparison"]["progressed_or_new_task"] = False
            machine_payload["comparison"]["detail"] = "; ".join(issues)
        machines[machine] = machine_payload

    anomalies = [
        machine
        for machine, payload in machines.items()
        if payload["comparison"].get("anomaly")
    ]
    payload = {
        "schema_version": "project3_stage31_status_compare_v1",
        "generated_at_utc": generated_at.isoformat(),
        "progress_csv": str(PROGRESS_CSV),
        "supervisor_cycle": supervisor_cycle,
        "machines": machines,
        "anomalies": anomalies,
        "overall_ok": not anomalies,
    }
    write_json(OUT_JSON, payload)
    write_json(SNAPSHOT, payload)

    lines = [
        "# Stage 3.1 Status Compare",
        "",
        f"Generated local ({LOCAL_TZ.key}): {generated_at.astimezone(LOCAL_TZ).isoformat()}",
        f"Generated UTC: {generated_at.isoformat()}",
        f"Previous snapshot: `{previous.get('generated_at_utc', 'none') if isinstance(previous, dict) else 'none'}`",
        f"Supervisor interval: `{supervisor_cycle['sleep_seconds']}s`",
        f"Supervisor last tick local: `{supervisor_cycle['last_tick_local'] or '-'}` "
        f"(UTC `{supervisor_cycle['last_tick_utc'] or '-'}`)",
        f"Supervisor next scheduled tick local: `{supervisor_cycle['next_scheduled_tick_local'] or '-'}` "
        f"(UTC `{supervisor_cycle['next_scheduled_tick_utc'] or '-'}`) "
        f"(status={supervisor_cycle['status']}, "
        f"in={supervisor_cycle['seconds_until_next_tick']}s, overdue={supervisor_cycle['seconds_overdue']}s)",
        f"Overall OK: `{payload['overall_ok']}`",
        "",
        "| Machine | Current Task | Progress | Trades | Profit % | Action non-hold | Deadband | Diagnosis | Source | Tasks Left | GPU | Comparison |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | --- | --- |",
    ]
    for machine, item in machines.items():
        active = item.get("active_task") or {}
        comparison = item["comparison"]
        if active:
            task_s = active.get("run_id", "UNKNOWN_ACTIVE")
            progress_s = f"{display_metric(active, 'progress_percent', 'UNKNOWN')}%"
            trades_s = display_metric(active, "trades_total")
            profit_s = display_metric(active, "profit_percent")
            non_hold_s = display_metric(active, "action_non_hold_rate")
            deadband_s = display_metric(active, "action_deadband_rate")
            diagnosis_s = display_metric(active, "no_trade_diagnosis", "metric_pending")
            source_s = active.get("progress_source", "unknown")
        else:
            task_s = "NO_ACTIVE_TASK"
            progress_s = "NOT_EXECUTING"
            trades_s = "NOT_EXECUTING"
            profit_s = "NOT_EXECUTING"
            non_hold_s = "NOT_EXECUTING"
            deadband_s = "NOT_EXECUTING"
            diagnosis_s = "idle_or_sync_gap"
            source_s = "no_active_row"
        lines.append(
            f"| {machine} | `{task_s}` | "
            f"{progress_s} | {trades_s} | "
            f"{profit_s} | {non_hold_s} | "
            f"{deadband_s} | {diagnosis_s} | "
            f"{source_s} | "
            f"{item['tasks_left']} | {summarize_gpu(item['gpu'])} | "
            f"{comparison['comparison_status']}: {comparison['detail']} |"
        )
    lines += [
        "",
        "## Active Task Details",
        "",
    ]
    for machine, item in machines.items():
        active = item.get("active_task") or {}
        if active:
            current_task_s = active.get("run_id", "UNKNOWN_ACTIVE")
            status_s = active.get("status", "unknown")
            progress_s = f"{display_metric(active, 'progress_percent', 'UNKNOWN')}%"
            progress_source_s = active.get("progress_source", "unknown")
            trades_s = display_metric(active, "trades_total")
            profit_s = display_metric(active, "profit_percent")
            total_return_s = display_metric(active, "total_return")
            final_equity_s = display_metric(active, "final_equity")
            non_hold_s = display_metric(active, "action_non_hold_rate")
            deadband_s = display_metric(active, "action_deadband_rate")
            abs_mean_s = display_metric(active, "action_abs_mean")
            diagnosis_s = display_metric(active, "no_trade_diagnosis", "metric_pending")
            entry_actions_s = display_metric(active, "execution_entry_actions_seen")
            orders_s = display_metric(active, "execution_entry_orders_submitted")
            detail_s = active.get("progress_detail", "")
            eta_s = active.get("estimated_remaining_minutes", "metric_pending")
        else:
            current_task_s = "NO_ACTIVE_TASK"
            status_s = "NOT_EXECUTING"
            progress_s = "NOT_EXECUTING"
            progress_source_s = "no_active_row"
            trades_s = "NOT_EXECUTING"
            profit_s = "NOT_EXECUTING"
            total_return_s = "NOT_EXECUTING"
            final_equity_s = "NOT_EXECUTING"
            non_hold_s = "NOT_EXECUTING"
            deadband_s = "NOT_EXECUTING"
            abs_mean_s = "NOT_EXECUTING"
            diagnosis_s = "idle_or_sync_gap"
            entry_actions_s = "NOT_EXECUTING"
            orders_s = "NOT_EXECUTING"
            detail_s = "No active queue/progress row. If tasks_left > 0, this is idle or a sync/startup gap."
            eta_s = "NOT_EXECUTING"
        lines += [
            f"### {machine}",
            f"- Current task: `{current_task_s}`",
            f"- Status: `{status_s}`",
            f"- Progress: `{progress_s}` via `{progress_source_s}`",
            f"- Trades/profit: trades=`{trades_s}`, profit_percent=`{profit_s}`, total_return=`{total_return_s}`, final_equity=`{final_equity_s}`",
            f"- Action diagnostics: non_hold_rate=`{non_hold_s}`, deadband_rate=`{deadband_s}`, abs_mean=`{abs_mean_s}`, diagnosis=`{diagnosis_s}`",
            f"- Execution diagnostics: entry_actions=`{entry_actions_s}`, orders_submitted=`{orders_s}`",
            f"- Detail: {detail_s}",
            f"- Estimated remaining minutes: `{eta_s}`",
            f"- Tasks left on machine: `{item['tasks_left']}`",
            f"- Queue counts: `{item['queue_counts']}`",
            f"- Queue active run ids: `{item.get('active_queue_run_ids', [])}`",
            f"- Live process run ids: `{item.get('live_active_run_ids', [])}`",
            f"- GPU: {summarize_gpu(item['gpu'])}",
            f"- Worker process count: `{item['worker_processes'].get('process_count', 0)}`",
            f"- Compare: {item['comparison']['detail']}",
            "",
        ]
    if anomalies:
        lines += [
            "## Required Intervention",
            "",
            "Anomaly detected on: " + ", ".join(f"`{machine}`" for machine in anomalies),
            "Do not explain this away; inspect the worker process, GPU process, queue row, and log before assigning more work.",
            "",
        ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"generated_at": generated_at.isoformat(), "overall_ok": payload["overall_ok"], "anomalies": anomalies, "markdown": str(OUT_MD), "json": str(OUT_JSON)}, indent=2))
    return 2 if anomalies else 0


if __name__ == "__main__":
    raise SystemExit(main())
