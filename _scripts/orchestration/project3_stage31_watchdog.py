#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
LOG_DIR = ROOT / "_logs" / "supervisor_reports"
REPORT_PATH = LOG_DIR / "stage31_watchdog.md"
STATE_PATH = LOG_DIR / "stage31_watchdog.json"
EVENT_LOG = LOG_DIR / "stage31_watchdog_events.jsonl"
PYTHON = os.environ.get("PROJECT3_PYTHON", "/home/harveybc/anaconda3/envs/tensorflow/bin/python")
SSH_PORT = "22022"

os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={os.environ['XDG_RUNTIME_DIR']}/bus")


@dataclass(frozen=True)
class Machine:
    name: str
    host: str | None = None

    @property
    def is_local(self) -> bool:
        return self.host is None


MACHINES = (
    Machine("omega"),
    Machine("dragon", "192.0.2.13"),
    Machine("gamma", "192.0.2.15"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)


def shell(cmd: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return run(["bash", "-lc", cmd], timeout=timeout)


def machine_shell(machine: Machine, cmd: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    prefix = (
        "source ~/.bashrc >/dev/null 2>&1 || true; "
        "source /home/harveybc/anaconda3/etc/profile.d/conda.sh >/dev/null 2>&1 || true; "
        "conda activate tensorflow >/dev/null 2>&1 || true; "
        f"cd {shlex.quote(str(ROOT))} || exit 1; "
    )
    full = prefix + cmd
    if machine.is_local:
        return shell(full, timeout=timeout)
    return run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            "-p",
            SSH_PORT,
            f"harveybc@{machine.host}",
            f"bash -lc {shlex.quote(full)}",
        ],
        timeout=timeout,
    )


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_event(event: dict[str, Any]) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"generated_at": utc_now(), **event}, sort_keys=True) + "\n")


def notify(event: str, title: str, message: str, *, force: bool = False, min_interval: int = 5) -> None:
    script = ROOT / "_scripts" / "telegram_notify.py"
    if not script.exists():
        return
    cmd = [
        PYTHON,
        str(script),
        "--event",
        f"stage31-watchdog:{event}",
        "--title",
        title,
        "--message",
        message,
        "--min-interval-minutes",
        str(min_interval),
    ]
    if force:
        cmd.append("--force")
    try:
        run(cmd, timeout=30)
    except Exception:
        pass


def is_runnable_status(value: object) -> bool:
    status = str(value or "pending").lower()
    return status in {"", "pending", "queued", "retry", "needs_retry"}


def queue_counts(machine: Machine) -> tuple[dict[str, int], int, list[dict]]:
    path = ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine.name}.json"
    jobs = read_json(path, [])
    if not isinstance(jobs, list):
        return {"queue_error": 1}, 0, []
    counts = dict(Counter((job.get("status") or "pending") for job in jobs))
    pending = sum(1 for job in jobs if is_runnable_status(job.get("status")))
    active = [job for job in jobs if str(job.get("status") or "").lower() in {"training", "running", "registered", "preparing_input"}]
    return counts, pending, active


def rsync_from(machine: Machine, rel: str, dst_rel: str | None = None) -> None:
    if machine.is_local:
        return
    dst_rel = dst_rel or rel
    dst = ROOT / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    src = f"harveybc@{machine.host}:{ROOT / rel}"
    shell(f"rsync -az -e 'ssh -p {SSH_PORT}' {shlex.quote(src)} {shlex.quote(str(dst))} || true", timeout=30)


def sync_remote(machine: Machine) -> None:
    rsync_from(machine, f"experiments/stage_a_screening/queues/{machine.name}.json")
    rsync_from(machine, f"_logs/supervisor_reports/stage31_worker_{machine.name}.md")
    rsync_from(machine, f"_metadata/stage31_worker_{machine.name}.json")
    rsync_from(machine, f"artifacts/run_ledger_events/{machine.name}.jsonl", f"artifacts/run_ledger_events/{machine.name}.remote.jsonl")


def reconcile(machine: Machine) -> str:
    cp = machine_shell(machine, f"python _scripts/workers/stage31_reconcile_queue_worker.py --machine {machine.name}", timeout=60)
    return cp.stdout.strip()


def busy_detail(machine: Machine) -> str:
    if machine.name == "omega":
        pattern = "stage31_agent_multi_run_worker.py --machine omega|agent-multi/tools/seed_sweep.py"
    else:
        pattern = "stage31_agent_multi_run_worker.py|agent-multi/tools/seed_sweep.py"
    cmd = f"ps -eo pid=,args= | grep -E {shlex.quote(pattern)} | grep -v grep || true"
    cp = machine_shell(machine, cmd, timeout=30)
    return cp.stdout.strip()


def launch_worker(machine: Machine) -> str:
    timeout = "120" if machine.name == "omega" else "180"
    stale_lock_cleanup = ""
    if not machine.is_local:
        stale_lock_cleanup = (
            "if [ -f /tmp/gpu_busy.lock ]; then "
            "python - <<'PY'\n"
            "import json, os\n"
            "from pathlib import Path\n"
            "p=Path('/tmp/gpu_busy.lock')\n"
            "try:\n"
            "    d=json.loads(p.read_text())\n"
            "except Exception:\n"
            "    d={}\n"
            "pid=d.get('pid') or d.get('owner_pid')\n"
            "if pid and not os.path.exists(f'/proc/{pid}'):\n"
            "    p.unlink(missing_ok=True)\n"
            "PY\n"
            "fi; "
        )
    cmd = (
        stale_lock_cleanup
        + f"setsid -f python _scripts/workers/stage31_agent_multi_run_worker.py --machine {machine.name} "
        + f"--max-jobs 1 --timeout-minutes {timeout} "
        + f"> _logs/supervisor_reports/stage31_worker_{machine.name}.nohup.log 2>&1 < /dev/null; "
        + "sleep 2; "
        + "ps -eo pid=,args= | grep -E 'stage31_agent_multi_run_worker.py|agent-multi/tools/seed_sweep.py' | grep -v grep || true"
    )
    cp = machine_shell(machine, cmd, timeout=45)
    return cp.stdout.strip()


def ensure_supervisor_service() -> dict[str, str]:
    service = "project3-stage31-supervisor.service"
    active = shell(f"systemctl --user is-active {service} 2>/dev/null || true", timeout=20).stdout.strip()
    if active == "active":
        return {"service": service, "action": "already_active"}
    shell(f"systemctl --user start {service} 2>/dev/null || true", timeout=30)
    active_after = shell(f"systemctl --user is-active {service} 2>/dev/null || true", timeout=20).stdout.strip()
    action = "started" if active_after == "active" else f"start_failed:{active_after or active}"
    if action == "started":
        append_event({"type": "supervisor_service_started"})
        notify("supervisor_service_started", "Project 3 Stage 3.1 supervisor restarted", "status: restarted\nmechanism: stage31 watchdog\nservice: project3-stage31-supervisor.service", force=True)
    return {"service": service, "action": action}


def combine_ledger() -> None:
    shell(
        f"cd {shlex.quote(str(ROOT))} && {shlex.quote(PYTHON)} _scripts/workers/stage31_combine_ledger_worker.py >/dev/null 2>&1 || true",
        timeout=60,
    )


def maybe_start_omega_synthesis() -> str:
    running = shell("ps -eo pid=,args= | grep -E 'stage32_stage_a_synthesis_worker.py' | grep -v grep || true", timeout=20).stdout.strip()
    if running:
        return f"stage32_synthesis_running:{running.splitlines()[0][:120]}"
    summary = ROOT / "experiments" / "stage_a_screening" / "stage_a_summary.md"
    if summary.exists() and time.time() - summary.stat().st_mtime < 600:
        return "stage32_synthesis_recent"
    worker = ROOT / "_scripts" / "workers" / "stage32_stage_a_synthesis_worker.py"
    if not worker.exists():
        return "stage32_synthesis_worker_missing"
    cmd = (
        f"cd {shlex.quote(str(ROOT))}; "
        f"setsid -f {shlex.quote(PYTHON)} _scripts/workers/stage32_stage_a_synthesis_worker.py "
        "> _logs/supervisor_reports/stage32_stage_a_synthesis.nohup.log 2>&1 < /dev/null; "
        "sleep 1; "
        "ps -eo pid=,args= | grep -E 'stage32_stage_a_synthesis_worker.py' | grep -v grep || true"
    )
    detail = shell(cmd, timeout=10).stdout.strip()
    append_event({"type": "omega_cpu_maintenance_started", "task": "stage32_stage_a_synthesis", "detail": detail})
    return f"stage32_synthesis_started:{detail[:160] or 'launched'}"


def write_context_packet() -> None:
    shell(
        f"cd {shlex.quote(str(ROOT))} && python _scripts/orchestration/project3_stage31_context_packet.py >/dev/null 2>&1 || true",
        timeout=60,
    )


def write_report(state: dict[str, Any]) -> None:
    lines = [
        "# Stage 3.1 Watchdog",
        "",
        f"Generated: {state['generated_at']}",
        "",
        f"Supervisor service: `{state['supervisor']['action']}`",
        "",
        "| Machine | Busy | Pending | Action | Active Task | Detail |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for item in state["machines"]:
        active = ", ".join(item.get("active_run_ids") or []) or "-"
        detail = str(item.get("detail", "")).replace("\n", " ")[:160]
        lines.append(f"| {item['machine']} | {item['busy']} | {item['pending']} | {item['action']} | `{active}` | `{detail}` |")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tick() -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    supervisor = ensure_supervisor_service()
    machine_states: list[dict[str, Any]] = []

    for machine in MACHINES:
        try:
            reconcile_detail = reconcile(machine)
        except Exception as exc:
            reconcile_detail = f"reconcile_failed:{exc}"
        if not machine.is_local:
            sync_remote(machine)
        counts, pending, active_jobs = queue_counts(machine)
        busy = bool(busy_detail(machine))
        action = "busy" if busy else "idle_no_pending"
        detail = reconcile_detail
        if not busy and pending:
            detail = launch_worker(machine)
            busy = bool(busy_detail(machine))
            action = "launched" if busy else "launch_failed"
            append_event({"type": action, "machine": machine.name, "pending": pending})
            notify(
                f"{action}:{machine.name}",
                f"Project 3 Stage 3.1 {machine.name} {action}",
                f"machine: {machine.name}\nwork_plan_stage: Stage 3.1 Stage A\nstatus: {action}\npending_before: {pending}\ndetail: {detail[:800]}",
                force=(action == "launch_failed"),
                min_interval=2,
            )
            if not machine.is_local:
                sync_remote(machine)
            counts, pending, active_jobs = queue_counts(machine)
        elif machine.name == "omega" and not busy and not pending:
            maintenance = maybe_start_omega_synthesis()
            detail = f"{detail}\nomega_maintenance: {maintenance}".strip()

        machine_states.append(
            {
                "machine": machine.name,
                "busy": busy,
                "pending": pending,
                "counts": counts,
                "action": action,
                "active_run_ids": [str(job.get("run_id")) for job in active_jobs if job.get("run_id")],
                "detail": detail,
            }
        )

    combine_ledger()
    state = {"generated_at": utc_now(), "supervisor": supervisor, "machines": machine_states}
    write_json(STATE_PATH, state)
    write_report(state)
    write_context_packet()
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Project 3 Stage 3.1 supervisor watchdog.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    state = tick()
    if args.json:
        print(json.dumps(state, indent=2, sort_keys=True))
    else:
        print(REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
