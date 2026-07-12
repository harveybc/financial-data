#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
LOCK_PATH = PROJECT_ROOT / "_metadata" / "stage31_supervisor_tick.lock"
# This is a queue buffer, not the remaining-work counter. Keep it modest so
# pending counts reflect reality and cross-machine rebalancing can drain.
TARGET_PENDING = int(os.environ.get("PROJECT3_STAGE31_TARGET_PENDING", "24"))
OMEGA_TARGET_PENDING = int(os.environ.get("PROJECT3_STAGE31_OMEGA_TARGET_PENDING", "12"))
WORKER_MAX_JOBS = int(os.environ.get("PROJECT3_STAGE31_WORKER_MAX_JOBS", "10"))
PYTHON = os.environ.get("PROJECT3_PYTHON", sys.executable)
PYTHON_Q = shlex.quote(PYTHON)
SSH = {
    "dragon": "ssh -p 22022 harveybc@192.0.2.13",
    "gamma": "ssh -p 22022 harveybc@192.0.2.16",
}
STRIP_MACHINE_FIELDS = {
    "completed_at",
    "config",
    "exit_code",
    "failure_reason",
    "host",
    "input_csv",
    "machine_run_id",
    "output_dir",
    "pid",
    "run_dir",
    "started_at",
    "stdout_tail",
    "summary_path",
    "trial_id",
    "worker_pid",
}
PREFIX = (
    "source ~/.bashrc >/dev/null 2>&1; "
    "source /home/harveybc/anaconda3/etc/profile.d/conda.sh >/dev/null 2>&1 && conda activate tensorflow; "
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def is_runnable_status(status: object) -> bool:
    value = str(status or "pending").lower()
    if value in {"", "pending", "queued", "retry", "needs_retry"}:
        return True
    if value in {"complete", "training", "running", "preparing_input", "skipped_busy"}:
        return False
    if value.startswith("blocked") or value.startswith("failed") or value.startswith("skipped"):
        return False
    return True


def is_active_status(status: object) -> bool:
    return str(status or "").lower() in {"training", "running", "registered", "preparing_input"}


def job_label(job: dict | None) -> str:
    if not job:
        return "-"
    return (
        f"{job.get('run_id', 'unknown')} "
        f"({job.get('asset', 'unknown')} {job.get('timeframe', 'unknown')} "
        f"{job.get('algo') or job.get('algorithm') or 'unknown'} "
        f"{job.get('preset') or job.get('feature_preset') or 'unknown'} "
        f"seed={job.get('seed', 'unknown')})"
    )


def next_pending_job(machine: str) -> dict | None:
    queue = read_json(PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json", [])
    if not isinstance(queue, list):
        return None
    for job in queue:
        if is_runnable_status(job.get("status", "pending")):
            return job
    return None


def pending_count(machine: str) -> int:
    queue = read_json(PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json", [])
    return sum(1 for job in queue if is_runnable_status(job.get("status", "pending")))


def refill_queues() -> str:
    script = PROJECT_ROOT / "_scripts" / "workers" / "stage31_expand_matrix_queue_worker.py"
    if not script.exists():
        return "refill_script_missing"
    proc = run(
        f"cd {shlex.quote(str(PROJECT_ROOT))} && {PYTHON_Q} {shlex.quote(str(script))} --target-pending {TARGET_PENDING}",
        timeout=60,
    )
    return proc.stdout.strip()


def reconcile_local(machine: str) -> str:
    script = PROJECT_ROOT / "_scripts" / "workers" / "stage31_reconcile_queue_worker.py"
    if not script.exists():
        return "reconcile_script_missing"
    proc = run(
        f"cd {shlex.quote(str(PROJECT_ROOT))} && {PYTHON_Q} {shlex.quote(str(script))} --machine {shlex.quote(machine)}",
        timeout=30,
    )
    return proc.stdout.strip()


def reconcile_remote(machine: str) -> str:
    cmd = (
        f"{SSH[machine]} \"bash -lc '{PREFIX}cd {PROJECT_ROOT}; "
        f"{PYTHON_Q} _scripts/workers/stage31_reconcile_queue_worker.py --machine {machine}'\""
    )
    proc = run(cmd, timeout=30)
    return proc.stdout.strip()


def local_busy() -> tuple[bool, str]:
    proc = run(
        "ps -eo pid=,args= | "
        "awk '(/stage31_agent_multi_run_worker.py --machine omega/ || /agent-multi\\/tools\\/seed_sweep.py/) "
        "&& !/awk/ && !/bash -lc/ && !/stage31_supervisor_tick_worker.py/ {print}' || true"
    )
    detail = proc.stdout.strip()
    return bool(detail), detail


def remote_busy(machine: str) -> tuple[bool, str]:
    cmd = (
        f"{SSH[machine]} \"bash -lc 'ps -eo pid=,args= | "
        "awk '\\''(/stage31_agent_multi_run_worker.py/ || /agent-multi\\/tools\\/seed_sweep.py/) "
        "&& !/awk/ && !/bash -lc/ {print}'\\'' || true; "
        "test -e /tmp/gpu_busy.lock && cat /tmp/gpu_busy.lock || true'\""
    )
    proc = run(cmd, timeout=20)
    detail = proc.stdout.strip()
    return bool(detail), detail


def remote_active_run_ids(machine: str) -> set[str]:
    cmd = (
        f"{SSH[machine]} \"bash -lc 'ps -eo args= | "
        "awk '\\''(/agent-multi\\/tools\\/seed_sweep.py/) && !/awk/ {print}'\\'' || true'\""
    )
    proc = run(cmd, timeout=20)
    active: set[str] = set()
    marker = f"configs/{machine}/"
    for line in proc.stdout.splitlines():
        if marker not in line:
            continue
        tail = line.split(marker, 1)[1].split()[0]
        if tail.endswith(".json"):
            active.add(tail[:-5])
    return active


def annotate_live_active(queues: dict[str, list[dict]]) -> dict[str, list[str]]:
    active_by_machine: dict[str, list[str]] = {}
    for machine in ("dragon", "gamma"):
        active = remote_active_run_ids(machine)
        active_by_machine[machine] = sorted(active)
        for job in queues.get(machine, []):
            if str(job.get("run_id") or "") in active:
                job["status"] = "training"
                job.setdefault("live_process_confirmed_at", utc_now())
    return active_by_machine


def launch_local() -> str:
    cmd = (
        f"bash -lc '{PREFIX}cd {PROJECT_ROOT}; "
        f"setsid -f {PYTHON_Q} _scripts/workers/stage31_agent_multi_run_worker.py "
        f"--machine omega --max-jobs {WORKER_MAX_JOBS} --timeout-minutes 120 "
        "> _logs/supervisor_reports/stage31_worker_omega.nohup.log 2>&1 < /dev/null'"
    )
    return run(cmd).stdout.strip()


def launch_remote(machine: str) -> str:
    cmd = (
        f"{SSH[machine]} \"bash -lc '{PREFIX}cd {PROJECT_ROOT}; "
        f"setsid -f {PYTHON_Q} _scripts/workers/stage31_agent_multi_run_worker.py --machine {machine} --max-jobs {WORKER_MAX_JOBS} --timeout-minutes 180 "
        f"> _logs/supervisor_reports/stage31_worker_{machine}.nohup.log 2>&1 < /dev/null'\""
    )
    return run(cmd, timeout=30).stdout.strip()


def sync_remote(machine: str) -> None:
    for rel in [
        f"_logs/supervisor_reports/stage31_worker_{machine}.md",
        f"_metadata/stage31_worker_{machine}.json",
        f"experiments/stage_a_screening/queues/{machine}.json",
    ]:
        src = f"harveybc@{'192.0.2.13' if machine == 'dragon' else '192.0.2.16'}:{PROJECT_ROOT / rel}"
        dst = PROJECT_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        run(f"rsync -az -e 'ssh -p 22022' {src} {dst} || true", timeout=30)

    src = (
        f"harveybc@{'192.0.2.13' if machine == 'dragon' else '192.0.2.16'}:"
        f"{PROJECT_ROOT / 'artifacts' / 'run_ledger_events' / f'{machine}.jsonl'}"
    )
    dst = PROJECT_ROOT / "artifacts" / "run_ledger_events" / f"{machine}.remote.jsonl"
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(f"rsync -az -e 'ssh -p 22022' {src} {dst} || true", timeout=30)

    src_progress = (
        f"harveybc@{'192.0.2.13' if machine == 'dragon' else '192.0.2.16'}:"
        f"{PROJECT_ROOT / 'experiments' / 'stage_a_screening' / 'runs' / machine}/*_training_progress.json"
    )
    dst_progress = PROJECT_ROOT / "experiments" / "stage_a_screening" / "runs" / machine / ""
    dst_progress.mkdir(parents=True, exist_ok=True)
    run(f"rsync -az -e 'ssh -p 22022' {src_progress} {dst_progress} 2>/dev/null || true", timeout=30)


def push_remote_queue(machine: str) -> None:
    rel = f"experiments/stage_a_screening/queues/{machine}.json"
    dst = f"harveybc@{'192.0.2.13' if machine == 'dragon' else '192.0.2.16'}:{PROJECT_ROOT / rel}"
    run(f"rsync -az -e 'ssh -p 22022' {PROJECT_ROOT / rel} {dst} || true", timeout=30)


def kill_remote_run(machine: str, run_id: str) -> str:
    pattern_config = shlex.quote(f"configs/{machine}/{run_id}.json")
    pattern_worker = shlex.quote(f"stage31_agent_multi_run_worker.py --machine {machine}")
    cmd = (
        f"{SSH[machine]} \"bash -lc '"
        f"pkill -f {pattern_config} || true; "
        f"pkill -f {pattern_worker} || true; "
        "sleep 2; "
        "rm -f /tmp/gpu_busy.lock; "
        "ps -eo pid=,args= | "
        "awk '\\''(/stage31_agent_multi_run_worker.py/ || /agent-multi\\/tools\\/seed_sweep.py/) "
        "&& !/awk/ && !/bash -lc/ {print}'\\'' || true"
        "'\""
    )
    return run(cmd, timeout=30).stdout.strip()


def load_queues() -> dict[str, list[dict]]:
    queues: dict[str, list[dict]] = {}
    for machine in ("omega", "dragon", "gamma"):
        path = PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"
        queue = read_json(path, [])
        queues[machine] = queue if isinstance(queue, list) else []
    return queues


def save_queue(machine: str, queue: list[dict]) -> None:
    path = PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"
    write_json(path, queue)


def global_dedupe_queues() -> str:
    """Fail closed on duplicate runnable run_ids across machines.

    This is the guard the old supervisor was missing. A run_id may appear in
    several queue files historically, but only one copy is allowed to be
    runnable or active. If two machines are already active on the same run, keep
    the earliest-started row and kill the other process before the next launch.
    """
    queues = load_queues()
    live_active = annotate_live_active(queues)
    by_run: dict[str, list[tuple[str, int, dict]]] = {}
    for machine, queue in queues.items():
        for idx, job in enumerate(queue):
            run_id = job.get("run_id")
            if not run_id:
                continue
            if is_runnable_status(job.get("status")) or is_active_status(job.get("status")):
                by_run.setdefault(str(run_id), []).append((machine, idx, job))

    changed: list[str] = []
    killed: dict[str, str] = {}
    machine_order = {"dragon": 0, "gamma": 1, "omega": 2}
    for run_id, rows in by_run.items():
        if len(rows) <= 1:
            continue

        def keep_key(item: tuple[str, int, dict]) -> tuple[int, str, int]:
            machine, idx, job = item
            active_rank = 0 if is_active_status(job.get("status")) else 1
            # ISO timestamps sort lexicographically. Missing timestamps lose to
            # active rows with real starts but remain deterministic.
            started = str(job.get("started_at") or "9999")
            return (active_rank, started, machine_order.get(machine, 99), idx)

        keep_machine, _, keep_job = min(rows, key=keep_key)
        for machine, idx, job in rows:
            if machine == keep_machine and job is keep_job:
                continue
            status = str(job.get("status") or "pending").lower()
            if is_active_status(status) and machine in SSH:
                killed[f"{machine}:{run_id}"] = kill_remote_run(machine, run_id)
            job["status"] = f"blocked_duplicate_kept_on_{keep_machine}"
            job["duplicate_cancelled_on"] = machine
            job["kept_on"] = keep_machine
            job["duplicate_guarded_at"] = utc_now()
            for key in ("pid", "started_at", "completed_at", "error"):
                job.pop(key, None)
            changed.append(f"{run_id}:{machine}->{keep_machine}")

    if changed:
        for machine, queue in queues.items():
            save_queue(machine, queue)
            if machine in SSH:
                push_remote_queue(machine)

    return json.dumps(
        {"changed": changed, "changed_count": len(changed), "killed": killed, "live_active": live_active},
        indent=2,
        sort_keys=True,
    )


def combine_ledger() -> str:
    proc = run(
        f"cd {shlex.quote(str(PROJECT_ROOT))} && {PYTHON_Q} _scripts/workers/stage31_combine_ledger_worker.py",
        timeout=30,
    )
    return proc.stdout.strip()


def rebalance_gpu_queues() -> str:
    script = PROJECT_ROOT / "_scripts" / "orchestration" / "project3_stage31_gpu_rebalancer.py"
    if not script.exists():
        return "rebalance_script_missing"
    proc = run(
        f"cd {shlex.quote(str(PROJECT_ROOT))} && {PYTHON_Q} {shlex.quote(str(script))} "
        f"--source gamma --target dragon --target-pending {TARGET_PENDING} --pull-remote --execute",
        timeout=360,
    )
    return proc.stdout.strip()


def strip_machine_fields(job: dict) -> None:
    for key in STRIP_MACHINE_FIELDS:
        job.pop(key, None)


def open_queue_count(queue: list[dict]) -> int:
    return sum(1 for job in queue if is_runnable_status(job.get("status")) or is_active_status(job.get("status")))


def rebalance_omega_queue() -> str:
    """Keep Omega fed with GPU work instead of leaving it as an empty queue.

    The remote rebalancer is intentionally remote-to-remote. Omega is the local
    machine, so this local move is the missing path: copy pending jobs from the
    largest remote backlog into omega's local queue, mark the source copy as
    rerouted, then push the source queue back to its worker.
    """
    if OMEGA_TARGET_PENDING <= 0:
        return json.dumps({"skipped": "omega_target_pending_disabled", "target_pending": OMEGA_TARGET_PENDING})

    queues = load_queues()
    omega = queues["omega"]
    omega_existing = {str(job.get("run_id") or "") for job in omega if job.get("run_id")}
    omega_open = open_queue_count(omega)
    needed = max(0, OMEGA_TARGET_PENDING - omega_open)
    if needed <= 0:
        return json.dumps(
            {
                "moved_count": 0,
                "reason": "omega_queue_already_has_capacity_buffer",
                "omega_open": omega_open,
                "target_pending": OMEGA_TARGET_PENDING,
            },
            indent=2,
            sort_keys=True,
        )

    source_order = sorted(
        ("dragon", "gamma"),
        key=lambda machine: sum(1 for job in queues[machine] if is_runnable_status(job.get("status"))),
        reverse=True,
    )
    moved: list[str] = []
    changed_sources: set[str] = set()
    reason = f"auto_rebalance_{utc_now()}_to_omega"
    for source in source_order:
        if needed <= 0:
            break
        source_queue = queues[source]
        for idx, job in enumerate(source_queue):
            if needed <= 0:
                break
            if not is_runnable_status(job.get("status")):
                continue
            run_id = str(job.get("run_id") or "")
            if not run_id:
                continue
            if run_id in omega_existing:
                job["status"] = "blocked_duplicate_kept_on_omega"
                job["duplicate_cancelled_on"] = source
                job["kept_on"] = "omega"
                job["duplicate_guarded_at"] = utc_now()
                strip_machine_fields(job)
                changed_sources.add(source)
                continue

            copied = dict(job)
            copied["status"] = "pending"
            copied["stage"] = "3.1_stage_a_broad_matrix_omega"
            copied["rerouted_from"] = source
            copied["rerouted_to"] = "omega"
            copied["reroute_reason"] = reason
            strip_machine_fields(copied)
            omega.append(copied)
            omega_existing.add(run_id)

            source_queue[idx]["status"] = "blocked_resolved_rerouted_to_omega"
            source_queue[idx]["rerouted_to"] = "omega"
            source_queue[idx]["reroute_reason"] = reason
            strip_machine_fields(source_queue[idx])
            changed_sources.add(source)
            moved.append(run_id)
            needed -= 1

    if moved or changed_sources:
        save_queue("omega", omega)
        for source in sorted(changed_sources):
            save_queue(source, queues[source])
            push_remote_queue(source)

    return json.dumps(
        {
            "moved_count": len(moved),
            "moved_run_ids": moved,
            "changed_sources": sorted(changed_sources),
            "omega_open_before": omega_open,
            "omega_open_after": open_queue_count(omega),
            "target_pending": OMEGA_TARGET_PENDING,
            "source_order": source_order,
        },
        indent=2,
        sort_keys=True,
    )


def refresh_eta_report() -> str:
    script = PROJECT_ROOT / "_scripts" / "orchestration" / "project3_stage31_pending_eta_report.py"
    if not script.exists():
        return "eta_report_script_missing"
    proc = run(
        f"cd {shlex.quote(str(PROJECT_ROOT))} && {PYTHON_Q} {shlex.quote(str(script))}",
        timeout=120,
    )
    return proc.stdout.strip()


def write_report(events: list[dict]) -> None:
    payload = {"generated_at": utc_now(), "stage": "3.1", "events": events}
    write_json(PROJECT_ROOT / "_metadata" / "stage31_supervisor_tick.json", payload)
    lines = [
        "# Stage 3.1 Supervisor Tick",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "| Machine | Busy | Pending | Action | Next Assignment Hint | Detail |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for event in events:
        detail = str(event.get("detail", "")).replace("\n", " ")[:180]
        lines.append(
            f"| {event['machine']} | {event['busy']} | {event['pending']} | {event['action']} | "
            f"`{event.get('next_assignment_hint', '-')}` | `{detail}` |"
        )
    out = PROJECT_ROOT / "_logs" / "supervisor_reports" / "stage31_supervisor_tick.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tick() -> list[dict]:
    events = []
    for machine in ("dragon", "gamma"):
        reconcile_remote(machine)
        sync_remote(machine)
    reconcile_local("omega")
    ledger_detail = combine_ledger()
    refill_detail = refill_queues()
    dedupe_detail = global_dedupe_queues()
    for machine in ("dragon", "gamma"):
        push_remote_queue(machine)
    rebalance_detail = rebalance_gpu_queues()
    omega_rebalance_detail = rebalance_omega_queue()
    eta_detail = refresh_eta_report()

    busy, detail = local_busy()
    pending = pending_count("omega")
    next_job = next_pending_job("omega")
    action = "busy"
    if not busy and pending:
        detail = launch_local() or "launched omega"
        action = "launched"
        busy = True
    elif not busy:
        action = "idle_no_pending"
    events.append(
        {
            "machine": "omega",
            "busy": busy,
            "pending": pending,
            "action": action,
            "next_assignment_hint": job_label(next_job),
            "next_assignment_run_id": next_job.get("run_id") if next_job else None,
            "detail": detail,
            "refill": refill_detail,
            "dedupe": dedupe_detail,
            "rebalance": rebalance_detail,
            "omega_rebalance": omega_rebalance_detail,
            "eta_report": eta_detail,
            "ledger": ledger_detail,
        }
    )

    for machine in ("dragon", "gamma"):
        busy, detail = remote_busy(machine)
        pending = pending_count(machine)
        next_job = next_pending_job(machine)
        action = "busy"
        if not busy and pending:
            detail = launch_remote(machine) or f"launched {machine}"
            action = "launched"
            busy = True
        elif not busy:
            action = "idle_no_pending"
        events.append(
            {
                "machine": machine,
                "busy": busy,
                "pending": pending,
                "action": action,
                "next_assignment_hint": job_label(next_job),
                "next_assignment_run_id": next_job.get("run_id") if next_job else None,
                "detail": detail,
            }
        )
    write_report(events)
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep Stage 3.1 queues moving when machines become idle.")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--sleep-seconds", type=int, default=60)
    parser.add_argument("--iterations", type=int, default=1)
    args = parser.parse_args()

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"skipped": "supervisor_tick_already_running"}, indent=2))
            return 0

        lock_file.write(f"pid={os.getpid()}\nstarted_at={utc_now()}\n")
        lock_file.flush()

        count = max(1, args.iterations)
        for idx in range(count):
            events = tick()
            print(json.dumps({"iteration": idx + 1, "events": events}, indent=2, default=str))
            if not args.loop or idx == count - 1:
                break
            time.sleep(args.sleep_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
