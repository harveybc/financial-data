#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
LOCK_PATH = PROJECT_ROOT / "_metadata" / "stage31_supervisor_tick.lock"
TARGET_PENDING = int(os.environ.get("PROJECT3_STAGE31_TARGET_PENDING", "48"))
SSH = {
    "dragon": "ssh -p 22022 harveybc@192.0.2.13",
    "gamma": "ssh -p 22022 harveybc@192.0.2.15",
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


def pending_count(machine: str) -> int:
    queue = read_json(PROJECT_ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json", [])
    return sum(1 for job in queue if is_runnable_status(job.get("status", "pending")))


def refill_queues() -> str:
    script = PROJECT_ROOT / "_scripts" / "workers" / "stage31_expand_matrix_queue_worker.py"
    if not script.exists():
        return "refill_script_missing"
    proc = run(
        f"cd {PROJECT_ROOT} && python {script} --target-pending {TARGET_PENDING}",
        timeout=60,
    )
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


def launch_local() -> str:
    cmd = (
        f"bash -lc '{PREFIX}cd {PROJECT_ROOT}; "
        "setsid -f python _scripts/workers/stage31_agent_multi_run_worker.py "
        "--machine omega --max-jobs 1 --timeout-minutes 120 "
        "> _logs/supervisor_reports/stage31_worker_omega.nohup.log 2>&1 < /dev/null'"
    )
    return run(cmd).stdout.strip()


def launch_remote(machine: str) -> str:
    cmd = (
        f"{SSH[machine]} \"bash -lc '{PREFIX}cd {PROJECT_ROOT}; "
        f"setsid -f python _scripts/workers/stage31_agent_multi_run_worker.py --machine {machine} --max-jobs 1 --timeout-minutes 180 "
        f"> _logs/supervisor_reports/stage31_worker_{machine}.nohup.log 2>&1 < /dev/null'\""
    )
    return run(cmd, timeout=30).stdout.strip()


def sync_remote(machine: str) -> None:
    for rel in [
        f"_logs/supervisor_reports/stage31_worker_{machine}.md",
        f"_metadata/stage31_worker_{machine}.json",
        f"experiments/stage_a_screening/queues/{machine}.json",
        f"artifacts/run_ledger_events/{machine}.jsonl",
        f"artifacts/run_ledger_events/{machine}.parquet",
    ]:
        src = f"harveybc@{'192.0.2.13' if machine == 'dragon' else '192.0.2.15'}:{PROJECT_ROOT / rel}"
        dst = PROJECT_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        run(f"rsync -az -e 'ssh -p 22022' {src} {dst} || true", timeout=30)


def push_remote_queue(machine: str) -> None:
    rel = f"experiments/stage_a_screening/queues/{machine}.json"
    dst = f"harveybc@{'192.0.2.13' if machine == 'dragon' else '192.0.2.15'}:{PROJECT_ROOT / rel}"
    run(f"rsync -az -e 'ssh -p 22022' {PROJECT_ROOT / rel} {dst} || true", timeout=30)


def combine_ledger() -> str:
    proc = run(
        f"cd {PROJECT_ROOT} && python _scripts/workers/stage31_combine_ledger_worker.py",
        timeout=30,
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
        "| Machine | Busy | Pending | Action | Detail |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for event in events:
        detail = str(event.get("detail", "")).replace("\n", " ")[:180]
        lines.append(
            f"| {event['machine']} | {event['busy']} | {event['pending']} | {event['action']} | `{detail}` |"
        )
    out = PROJECT_ROOT / "_logs" / "supervisor_reports" / "stage31_supervisor_tick.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tick() -> list[dict]:
    events = []
    for machine in ("dragon", "gamma"):
        sync_remote(machine)
    ledger_detail = combine_ledger()
    refill_detail = refill_queues()
    for machine in ("dragon", "gamma"):
        push_remote_queue(machine)

    busy, detail = local_busy()
    pending = pending_count("omega")
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
            "detail": detail,
            "refill": refill_detail,
            "ledger": ledger_detail,
        }
    )

    for machine in ("dragon", "gamma"):
        busy, detail = remote_busy(machine)
        pending = pending_count(machine)
        action = "busy"
        if not busy and pending:
            detail = launch_remote(machine) or f"launched {machine}"
            action = "launched"
            busy = True
        elif not busy:
            action = "idle_no_pending"
        events.append({"machine": machine, "busy": busy, "pending": pending, "action": action, "detail": detail})
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
