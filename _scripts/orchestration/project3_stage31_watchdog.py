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
PYTHON = os.environ.get("PROJECT3_PYTHON", "/home/harveybc/anaconda3/envs/trading-stack/bin/python")
SSH_PORT = "22022"
WORKER_MAX_JOBS = int(os.environ.get("PROJECT3_STAGE31_WORKER_MAX_JOBS", "10"))

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
    Machine("gamma", "192.0.2.16"),
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
        "conda activate trading-stack >/dev/null 2>&1 || true; "
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


def active_ids_from_reconcile_detail(detail: str) -> list[str]:
    """Extract active run ids from the reconciler JSON when queue sync lags.

    Remote workers can update their human report before the queue file synced
    back to Omega reflects ``training``. In that short window the watchdog can
    correctly detect a busy process while still showing an empty active task.
    The reconciler already emits a compact JSON object with ``active``; use it
    as a display-only fallback without mutating queue state.
    """
    active: list[str] = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(detail):
        try:
            obj, end = decoder.raw_decode(detail[idx:])
        except json.JSONDecodeError:
            idx += 1
            continue
        idx += end
        if isinstance(obj, dict):
            values = obj.get("active")
            if isinstance(values, list):
                active.extend(str(v) for v in values if v)
    return active


def queue_counts(machine: Machine) -> tuple[dict[str, int], int, list[dict], dict | None]:
    path = ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine.name}.json"
    jobs = read_json(path, [])
    if not isinstance(jobs, list):
        return {"queue_error": 1}, 0, [], None
    counts = dict(Counter((job.get("status") or "pending") for job in jobs))
    pending = sum(1 for job in jobs if is_runnable_status(job.get("status")))
    active = [job for job in jobs if str(job.get("status") or "").lower() in {"training", "running", "registered", "preparing_input"}]
    next_job = next((job for job in jobs if is_runnable_status(job.get("status"))), None)
    return counts, pending, active, next_job


def rsync_from(machine: Machine, rel: str, dst_rel: str | None = None) -> None:
    if machine.is_local:
        return
    dst_rel = dst_rel or rel
    dst = ROOT / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    src = f"harveybc@{machine.host}:{ROOT / rel}"
    shell(f"rsync -az -e 'ssh -p {SSH_PORT}' {shlex.quote(src)} {shlex.quote(str(dst))} || true", timeout=30)


def rsync_to(machine: Machine, rel: str) -> None:
    if machine.is_local:
        return
    src = ROOT / rel
    dst = f"harveybc@{machine.host}:{ROOT / rel}"
    shell(f"rsync -az -e 'ssh -p {SSH_PORT}' {shlex.quote(str(src))} {shlex.quote(dst)} || true", timeout=30)


def rsync_return_traces(machine: Machine) -> None:
    if machine.is_local:
        return
    rel = f"experiments/stage_a_screening/runs/{machine.name}"
    dst = ROOT / "experiments" / "stage_a_screening" / "runs"
    dst.mkdir(parents=True, exist_ok=True)
    src = f"harveybc@{machine.host}:{ROOT / rel}"
    cmd = (
        "rsync -az "
        f"-e 'ssh -p {SSH_PORT}' "
        "--include='*/' "
        "--include='config.json' "
        "--include='summary.json' "
        "--include='config_out.json' "
        "--include='return_trace.csv' "
        "--include='*return_trace*.csv' "
        "--exclude='*' "
        f"{shlex.quote(src)} {shlex.quote(str(dst))} || true"
    )
    shell(cmd, timeout=60)


def sync_remote(machine: Machine) -> None:
    rsync_from(machine, f"experiments/stage_a_screening/queues/{machine.name}.json")
    rsync_from(machine, f"_logs/supervisor_reports/stage31_worker_{machine.name}.md")
    rsync_from(machine, f"_metadata/stage31_worker_{machine.name}.json")
    rsync_from(machine, f"artifacts/run_ledger_events/{machine.name}.jsonl", f"artifacts/run_ledger_events/{machine.name}.remote.jsonl")
    rsync_return_traces(machine)


def reconcile(machine: Machine) -> str:
    cp = machine_shell(machine, f"python _scripts/workers/stage31_reconcile_queue_worker.py --machine {machine.name}", timeout=60)
    return cp.stdout.strip()


def expand_queue(machine: Machine, target_pending: int = 24) -> str:
    if machine.name not in {"dragon", "gamma"}:
        return "queue_expansion_skipped:not_gpu_worker"
    worker = ROOT / "_scripts" / "workers" / "stage31_expand_matrix_queue_worker.py"
    if not worker.exists():
        return "queue_expansion_skipped:worker_missing"
    cp = shell(
        f"cd {shlex.quote(str(ROOT))} && {shlex.quote(PYTHON)} "
        f"_scripts/workers/stage31_expand_matrix_queue_worker.py "
        f"--machine {shlex.quote(machine.name)} --target-pending {int(target_pending)}",
        timeout=60,
    )
    if not machine.is_local:
        rsync_to(machine, f"experiments/stage_a_screening/queues/{machine.name}.json")
        rsync_to(machine, "_metadata/stage31_queue_expansion.json")
        rsync_to(machine, "_logs/supervisor_reports/stage31_queue_expansion.md")
    return cp.stdout.strip()


def auto_rebalance_idle_dragon(machine_states: list[dict[str, Any]]) -> str:
    """Move GPU work from Gamma to Dragon when Dragon drains its queue.

    Dragon's matrix expansion is intentionally crypto-biased, while Gamma owns
    much of the FX backlog. Without this explicit cross-machine rebalance,
    Dragon can sit idle even though Gamma still has dozens of runnable jobs.
    The rebalancer also syncs pending asset data/features and refuses to write
    queues if it would create duplicate runnable run IDs.
    """
    by_name = {item["machine"]: item for item in machine_states}
    dragon = by_name.get("dragon", {})
    gamma = by_name.get("gamma", {})
    if dragon.get("busy") or int(dragon.get("pending") or 0) > 0:
        return ""
    if int(gamma.get("pending") or 0) <= 0:
        return ""
    worker = ROOT / "_scripts" / "orchestration" / "project3_stage31_gpu_rebalancer.py"
    if not worker.exists():
        return "auto_rebalance_skipped:worker_missing"
    cp = shell(
        f"cd {shlex.quote(str(ROOT))} && {shlex.quote(PYTHON)} "
        "_scripts/orchestration/project3_stage31_gpu_rebalancer.py "
        "--source gamma --target dragon --target-pending 24 --pull-remote --execute --launch",
        timeout=360,
    )
    detail = cp.stdout.strip()
    append_event({"type": "auto_rebalance_idle_dragon", "detail": detail[:2000]})
    notify(
        "auto_rebalance_idle_dragon",
        "Project 3 Stage 3.1 auto-rebalanced Dragon",
        f"reason: dragon_idle_gamma_pending\nstatus: executed\ndetail: {detail[:1200]}",
        min_interval=5,
    )
    return detail


def busy_detail(machine: Machine) -> str:
    machine_filter = f" --machine {machine.name}" if machine.name == "omega" else ""
    cmd = (
        "python3 - <<'PY'\n"
        "import os\n"
        "my_pid, my_ppid = os.getpid(), os.getppid()\n"
        f"machine_filter = {machine_filter!r}\n"
        "needles = ('stage31_agent_multi_run_worker.py', 'agent-multi/tools/seed_sweep.py')\n"
        "for pid in os.listdir('/proc'):\n"
        "    if not pid.isdigit() or pid in (str(my_pid), str(my_ppid)):\n"
        "        continue\n"
        "    try:\n"
        "        raw = open(f'/proc/{pid}/cmdline', 'rb').read()\n"
        "    except OSError:\n"
        "        continue\n"
        "    cmd = raw.replace(b'\\x00', b' ').decode('utf-8', 'ignore').strip()\n"
        "    if any(needle in cmd for needle in needles) and (not machine_filter or machine_filter in cmd or 'seed_sweep.py' in cmd):\n"
        "        print(f'{pid} {cmd}')\n"
        "PY"
    )
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
        + f"--max-jobs {WORKER_MAX_JOBS} --timeout-minutes {timeout} "
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
        "| Machine | Busy | Pending | Action | Active Task | Next Assignment Hint | Detail |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for item in state["machines"]:
        active = ", ".join(item.get("active_run_ids") or []) or "-"
        detail = str(item.get("detail", "")).replace("\n", " ")[:160]
        lines.append(
            f"| {item['machine']} | {item['busy']} | {item['pending']} | {item['action']} | "
            f"`{active}` | `{item.get('next_assignment_hint', '-')}` | `{detail}` |"
        )
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
        expansion_detail = expand_queue(machine)
        counts, pending, active_jobs, next_job = queue_counts(machine)
        busy = bool(busy_detail(machine))
        action = "busy" if busy else "idle_no_pending"
        detail = "\n".join(part for part in [reconcile_detail, expansion_detail] if part)
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
            counts, pending, active_jobs, next_job = queue_counts(machine)
        elif machine.name == "omega" and not busy and not pending:
            maintenance = maybe_start_omega_synthesis()
            detail = f"{detail}\nomega_maintenance: {maintenance}".strip()

        active_run_ids = [str(job.get("run_id")) for job in active_jobs if job.get("run_id")]
        if not active_run_ids:
            active_run_ids = active_ids_from_reconcile_detail(detail)

        machine_states.append(
            {
                "machine": machine.name,
                "busy": busy,
                "pending": pending,
                "counts": counts,
                "action": action,
                "active_run_ids": active_run_ids,
                "next_assignment_hint": job_label(next_job),
                "next_assignment_run_id": next_job.get("run_id") if next_job else None,
                "detail": detail,
            }
        )

    rebalance_detail = auto_rebalance_idle_dragon(machine_states)
    if rebalance_detail:
        # Refresh remote queue and process state after the rebalancer modifies
        # queues and potentially launches Dragon.
        refreshed: list[dict[str, Any]] = []
        for item in machine_states:
            machine = next(m for m in MACHINES if m.name == item["machine"])
            if machine.name in {"dragon", "gamma"}:
                sync_remote(machine)
                counts, pending, active_jobs, next_job = queue_counts(machine)
                busy = bool(busy_detail(machine))
                active_run_ids = [str(job.get("run_id")) for job in active_jobs if job.get("run_id")]
                detail = item.get("detail", "")
                if machine.name == "dragon":
                    detail = f"{detail}\nauto_rebalance: {rebalance_detail[:2000]}".strip()
                refreshed.append(
                    {
                        "machine": machine.name,
                        "busy": busy,
                        "pending": pending,
                        "counts": counts,
                        "action": "busy" if busy else ("idle_pending" if pending else "idle_no_pending"),
                        "active_run_ids": active_run_ids,
                        "next_assignment_hint": job_label(next_job),
                        "next_assignment_run_id": next_job.get("run_id") if next_job else None,
                        "detail": detail,
                    }
                )
            else:
                refreshed.append(item)
        machine_states = refreshed

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
