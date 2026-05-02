#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
LOG_DIR = ROOT / "_logs" / "supervisor_reports"
STATE_PATH = LOG_DIR / "project3_event_daemon_state.json"
REPORT_PATH = LOG_DIR / "project3_event_daemon_status.md"
EVENT_LOG = LOG_DIR / "project3_event_daemon_events.jsonl"
PYTHON = os.environ.get("PROJECT3_PYTHON", "/home/harveybc/anaconda3/envs/tensorflow/bin/python")
SSH_PORT = 22022
SSH_USER = "harveybc"


@dataclass(frozen=True)
class Machine:
    name: str
    host: str | None = None
    user: str = SSH_USER

    @property
    def is_local(self) -> bool:
        return self.host is None


MACHINES = (
    Machine("omega"),
    Machine("dragon", "192.0.2.13"),
    Machine("gamma", "192.0.2.15"),
)

ASSETS = ("btcusdt", "ethusdt", "btcusdt_perp", "eurusd", "usdjpy")
TIMEFRAMES = ("15m", "5m", "4h", "1h")
METHODS = ("lstm", "cnn")
WORKERS = {
    "lstm": "_scripts/workers/stage24_lstm_autoencoder_worker.py",
    "cnn": "_scripts/workers/stage24_cnn_autoencoder_worker.py",
}
CPU_PREP_JOBS = (
    {
        "machine": "omega",
        "universe": "crypto_stage_a_5m",
        "assets": ("btcusdt", "ethusdt", "btcusdt_perp"),
        "timeframes": ("5m",),
        "log": "_logs/omega/stage24_input_prep_crypto_5m.out",
    },
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str], timeout: int = 120, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=check)


def shell(cmd: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return run(["bash", "-lc", cmd], timeout=timeout)


def machine_shell(machine: Machine, cmd: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
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
            str(SSH_PORT),
            f"{machine.user}@{machine.host}",
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
    event = {"generated_at": utc_now(), **event}
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def notify(event: str, title: str, message: str, *, force: bool = True, min_interval_minutes: int = 0) -> None:
    cmd = [
        PYTHON,
        str(ROOT / "_scripts" / "telegram_notify.py"),
        "--event",
        f"event-daemon:{event}",
        "--title",
        title,
        "--message",
        message,
        "--min-interval-minutes",
        str(min_interval_minutes),
    ]
    if force:
        cmd.append("--force")
    try:
        run(cmd, timeout=30)
    except Exception:
        pass


def job_id(method: str, asset: str, timeframe: str) -> str:
    return f"{method}:{asset}:{timeframe}"


def metadata_pattern(method: str, asset: str, timeframe: str) -> str:
    return str(ROOT / "_metadata" / f"stage24_{method}_autoencoder_*_{asset}_{timeframe}.json")


def completed_job_ids() -> set[str]:
    completed: set[str] = set()
    for method in METHODS:
        for asset in ASSETS:
            for timeframe in TIMEFRAMES:
                if glob.glob(metadata_pattern(method, asset, timeframe)):
                    completed.add(job_id(method, asset, timeframe))
    return completed


def input_ready(asset: str, timeframe: str) -> bool:
    base = ROOT / "features" / "learned_inputs" / asset / timeframe
    return all((base / name).exists() for name in ("train.csv", "validation.csv", "full_normalized.parquet"))


def job_priority() -> list[tuple[str, str, str]]:
    jobs: list[tuple[str, str, str]] = []
    for timeframe in TIMEFRAMES:
        for method in METHODS:
            for asset in ASSETS:
                jobs.append((method, asset, timeframe))
    return jobs


def parse_lock(machine: Machine) -> dict[str, Any]:
    script = r'''
python - <<'PY'
import json, os
from pathlib import Path
p = Path("/tmp/gpu_busy.lock")
out = {"lock_present": p.exists(), "pid": None, "pid_alive": False, "command": "", "removed_stale": False}
if p.exists():
    try:
        payload = json.loads(p.read_text())
    except Exception:
        payload = {"command": p.read_text(errors="ignore")}
    pid = payload.get("pid") or payload.get("owner_pid")
    out.update({"pid": pid, "command": payload.get("command") or payload.get("owner_command") or "", "stage": payload.get("stage")})
    if pid:
        out["pid_alive"] = os.path.exists(f"/proc/{pid}")
    if pid and not out["pid_alive"]:
        p.unlink(missing_ok=True)
        out["lock_present"] = False
        out["removed_stale"] = True
print(json.dumps(out))
PY
'''
    cp = machine_shell(machine, script, timeout=30)
    try:
        return json.loads(cp.stdout.strip().splitlines()[-1])
    except Exception:
        return {"lock_present": True, "pid_alive": True, "error": cp.stdout[-500:]}


def rsync_from(machine: Machine, remote_rel: str, local_rel: str | None = None, directory: bool = False) -> bool:
    if machine.is_local:
        return True
    local_rel = local_rel or remote_rel
    src_rel = remote_rel.rstrip("/") + ("/" if directory else "")
    dst = ROOT / local_rel
    if directory:
        dst.mkdir(parents=True, exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
    src_path = str(ROOT / src_rel.rstrip("/"))
    src = f"{machine.user}@{machine.host}:{src_path}{'/' if directory else ''}"
    cp = run(["rsync", "-az", "-e", f"ssh -p {SSH_PORT}", src, str(dst) + ("/" if directory else "")], timeout=300)
    return cp.returncode == 0


def rsync_to(machine: Machine, local_rel: str, remote_rel: str | None = None, directory: bool = False) -> bool:
    if machine.is_local:
        return True
    remote_rel = remote_rel or local_rel
    src = ROOT / local_rel
    if not src.exists():
        return False
    machine_shell(machine, f"mkdir -p {shlex.quote(str((ROOT / remote_rel).parent if not directory else ROOT / remote_rel))}", timeout=30)
    src_arg = str(src).rstrip("/") + ("/" if directory else "")
    dst = f"{machine.user}@{machine.host}:{ROOT / remote_rel}"
    if directory:
        dst = dst.rstrip("/") + "/"
    cp = run(["rsync", "-az", "-e", f"ssh -p {SSH_PORT}", src_arg, dst], timeout=600)
    return cp.returncode == 0


def sync_remote_metadata(machine: Machine) -> list[Path]:
    if machine.is_local:
        return []
    before = set((ROOT / "_metadata").glob(f"stage24_*_autoencoder_{machine.name}_*.json"))
    run(
        [
            "bash",
            "-lc",
            " ".join(
                [
                    "rsync -az",
                    f"-e {shlex.quote(f'ssh -p {SSH_PORT}')}",
                    shlex.quote(f"{machine.user}@{machine.host}:{ROOT}/_metadata/stage24_*_autoencoder_{machine.name}_*.json"),
                    shlex.quote(str(ROOT / "_metadata" / "")),
                    "2>/dev/null || true",
                ]
            ),
        ],
        timeout=120,
    )
    after = set((ROOT / "_metadata").glob(f"stage24_*_autoencoder_{machine.name}_*.json"))
    return sorted(after - before)


def sync_remote_prep(machine: Machine) -> list[Path]:
    if machine.is_local:
        return []
    before = set((ROOT / "_metadata").glob(f"stage24_learned_input_prep_{machine.name}_*.json"))
    run(
        [
            "bash",
            "-lc",
            " ".join(
                [
                    "rsync -az",
                    f"-e {shlex.quote(f'ssh -p {SSH_PORT}')}",
                    shlex.quote(f"{machine.user}@{machine.host}:{ROOT}/_metadata/stage24_learned_input_prep_{machine.name}_*.json"),
                    shlex.quote(str(ROOT / "_metadata" / "")),
                    "2>/dev/null || true",
                ]
            ),
        ],
        timeout=120,
    )
    changed = sorted(set((ROOT / "_metadata").glob(f"stage24_learned_input_prep_{machine.name}_*.json")) - before)
    for path in changed:
        payload = read_json(path, {})
        for result in payload.get("results", []):
            if result.get("status") == "ok" and result.get("output_dir"):
                rsync_from(machine, result["output_dir"], directory=True)
    return changed


def sync_outputs_for_metadata(machine: Machine, metadata_path: Path) -> None:
    payload = read_json(metadata_path, {})
    feature_path = payload.get("features_path")
    if feature_path:
        rsync_from(machine, feature_path)
    for key in ("encoder_path", "autoencoder_path"):
        model_path = payload.get(key)
        if model_path:
            rsync_from(machine, str(Path(model_path).parent), directory=True)


def sync_all_completed() -> list[str]:
    synced: list[str] = []
    for machine in MACHINES:
        if machine.is_local:
            continue
        for path in sync_remote_metadata(machine):
            sync_outputs_for_metadata(machine, path)
            synced.append(path.name)
        for path in sync_remote_prep(machine):
            synced.append(path.name)
    return synced


def start_job(machine: Machine, method: str, asset: str, timeframe: str) -> str:
    jid = job_id(method, asset, timeframe)
    input_rel = f"features/learned_inputs/{asset}/{timeframe}"
    if not machine.is_local:
        rsync_to(machine, input_rel, directory=True)
        rsync_to(machine, WORKERS[method])
        rsync_to(machine, "_scripts/lib/gpu_lock.py")
    log_path = f"_logs/{machine.name}/stage24_{method}_{asset}_{timeframe}.out"
    epochs = "20"
    max_windows = "24000" if timeframe in {"5m", "15m"} else "12000"
    command = (
        f"mkdir -p _logs/{shlex.quote(machine.name)}; "
        "if [ -f /tmp/gpu_busy.lock ]; then echo busy; cat /tmp/gpu_busy.lock; exit 2; fi; "
        f"nohup env PYTHONUNBUFFERED=1 python {shlex.quote(WORKERS[method])} "
        f"--machine {shlex.quote(machine.name)} --asset {shlex.quote(asset)} --timeframe {shlex.quote(timeframe)} "
        f"--epochs {epochs} --max-train-windows {max_windows} --batch-size 128 "
        f"> {shlex.quote(log_path)} 2>&1 < /dev/null & echo $!"
    )
    cp = machine_shell(machine, command, timeout=60)
    pid = cp.stdout.strip().splitlines()[-1] if cp.returncode == 0 and cp.stdout.strip() else ""
    if not pid.isdigit():
        raise RuntimeError(f"failed to start {jid} on {machine.name}: {cp.stdout[-1000:]}")
    append_event({"type": "task_started", "machine": machine.name, "job_id": jid, "pid": pid})
    notify(
        f"start:{machine.name}:{jid}",
        f"Project 3 {machine.name} task started",
        f"machine: {machine.name}\nwork_plan_stage: Stage 2.4\ntask: {jid}\nstatus: started\npid: {pid}\ndeliverable_path: features/trading_asset_features/{asset}/{timeframe}/learned_{method}.parquet",
    )
    return pid


def process_running(pattern: str) -> bool:
    current = os.getpid()
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            pid = int(proc.name)
            if pid == current:
                continue
            cmdline = (proc / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="ignore")
        except Exception:
            continue
        if pattern in cmdline:
            return True
    return False


def start_cpu_prep_jobs() -> list[dict[str, str]]:
    assignments: list[dict[str, str]] = []
    for job in CPU_PREP_JOBS:
        machine = str(job["machine"])
        universe = str(job["universe"])
        metadata = ROOT / "_metadata" / f"stage24_learned_input_prep_{machine}_{universe}.json"
        pattern = f"stage24_learned_input_prep_worker.py --machine {machine} --universe {universe}"
        if metadata.exists() or process_running(pattern):
            continue
        assets = " ".join(shlex.quote(asset) for asset in job["assets"])
        timeframes = " ".join(shlex.quote(tf) for tf in job["timeframes"])
        log_path = shlex.quote(str(job["log"]))
        command = (
            f"mkdir -p {shlex.quote(str(Path(str(job['log'])).parent))}; "
            "nohup env PYTHONUNBUFFERED=1 python _scripts/workers/stage24_learned_input_prep_worker.py "
            f"--machine {shlex.quote(machine)} --universe {shlex.quote(universe)} "
            f"--assets {assets} --timeframes {timeframes} "
            f"> {log_path} 2>&1 < /dev/null & echo $!"
        )
        cp = machine_shell(Machine(machine), command, timeout=30)
        pid = cp.stdout.strip().splitlines()[-1] if cp.returncode == 0 and cp.stdout.strip() else ""
        if pid.isdigit():
            item = {"machine": machine, "job_id": f"input_prep:{universe}", "pid": pid}
            assignments.append(item)
            append_event({"type": "cpu_prep_started", **item})
            notify(
                f"cpu_prep_start:{machine}:{universe}",
                f"Project 3 {machine} CPU prep started",
                f"machine: {machine}\nwork_plan_stage: Stage 2.4\ntask: input_prep:{universe}\nstatus: started\npid: {pid}\ndeliverable_path: _metadata/stage24_learned_input_prep_{machine}_{universe}.json",
            )
        else:
            append_event({"type": "cpu_prep_failed", "machine": machine, "job_id": f"input_prep:{universe}", "error": cp.stdout[-1000:]})
    return assignments


def running_cpu_prep_jobs() -> dict[str, list[str]]:
    running: dict[str, list[str]] = {}
    for job in CPU_PREP_JOBS:
        machine = str(job["machine"])
        universe = str(job["universe"])
        pattern = f"stage24_learned_input_prep_worker.py --machine {machine} --universe {universe}"
        if process_running(pattern):
            running.setdefault(machine, []).append(f"input_prep:{universe}")
    return running


def choose_job(machine: Machine, completed: set[str], running: set[str]) -> tuple[str, str, str] | None:
    for method, asset, timeframe in job_priority():
        jid = job_id(method, asset, timeframe)
        if jid in completed or jid in running:
            continue
        if machine.name == "omega" and timeframe == "5m":
            continue
        if not input_ready(asset, timeframe):
            continue
        return method, asset, timeframe
    return None


def tick() -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    first_run = not STATE_PATH.exists()
    state = read_json(STATE_PATH, {"running": {}, "completed_notified": []})
    synced = sync_all_completed()
    cpu_assignments = start_cpu_prep_jobs()
    cpu_running = running_cpu_prep_jobs()
    completed = completed_job_ids()
    completed_notified = set(state.get("completed_notified", []))
    if first_run and not completed_notified:
        # The daemon may be enabled after many Stage 2.4 jobs already finished.
        # Seed historical completions silently so Telegram only receives new events.
        completed_notified = set(completed)
    for jid in sorted(completed - completed_notified):
        append_event({"type": "task_completed", "job_id": jid})
        notify(
            f"done:{jid}",
            "Project 3 task completed",
            f"work_plan_stage: Stage 2.4\ntask: {jid}\nstatus: finished\ndeliverable_path: see _metadata/stage24_*_{jid.split(':')[1]}_{jid.split(':')[2]}.json\nrecommended_next_action: supervisor dispatches the next validated job",
        )
    completed_notified |= completed

    running_jobs = set()
    machine_reports = []
    assignments = []
    for machine in MACHINES:
        lock = parse_lock(machine)
        busy = bool(lock.get("lock_present") and lock.get("pid_alive", True))
        if busy:
            command = str(lock.get("command") or "")
            for method in METHODS:
                if f"stage24_{method}_autoencoder_worker.py" in command:
                    parts = command.split()
                    try:
                        asset = parts[parts.index("--asset") + 1]
                        timeframe = parts[parts.index("--timeframe") + 1]
                        running_jobs.add(job_id(method, asset, timeframe))
                    except Exception:
                        pass
            machine_reports.append({"machine": machine.name, "state": "busy", "lock": lock})
            continue
        job = choose_job(machine, completed, running_jobs)
        if job is None:
            if machine.name in cpu_running:
                machine_reports.append({"machine": machine.name, "state": "cpu_busy", "reason": ",".join(cpu_running[machine.name])})
                continue
            machine_reports.append({"machine": machine.name, "state": "idle", "reason": "no validated ready Stage 2.4 job found"})
            notify(
                f"idle:{machine.name}",
                f"Project 3 {machine.name} idle",
                f"machine: {machine.name}\nwork_plan_stage: Stage 2.4\nstatus: idle\nreason: no validated ready Stage 2.4 job found\nrecommended_next_action: prepare more learned inputs or assign Phase 3.1 validation/design work",
                force=False,
                min_interval_minutes=20,
            )
            continue
        method, asset, timeframe = job
        try:
            pid = start_job(machine, method, asset, timeframe)
            jid = job_id(method, asset, timeframe)
            running_jobs.add(jid)
            assignments.append({"machine": machine.name, "job_id": jid, "pid": pid})
            machine_reports.append({"machine": machine.name, "state": "started", "job_id": jid, "pid": pid})
        except Exception as exc:
            machine_reports.append({"machine": machine.name, "state": "dispatch_failed", "error": str(exc)})
            append_event({"type": "dispatch_failed", "machine": machine.name, "error": str(exc)})
            notify(
                f"dispatch_failed:{machine.name}",
                f"Project 3 {machine.name} dispatch failed",
                f"machine: {machine.name}\nwork_plan_stage: Stage 2.4\nstatus: dispatch_failed\nerror: {exc}\nneeds_codex: true",
            )

    new_state = {
        "updated_at": utc_now(),
        "completed_notified": sorted(completed_notified),
        "last_synced": synced,
        "last_assignments": [*cpu_assignments, *assignments],
        "machines": machine_reports,
    }
    write_json(STATE_PATH, new_state)
    write_report(new_state, completed)
    return new_state


def write_report(state: dict[str, Any], completed: set[str]) -> None:
    lines = [
        "# Project 3 Event Daemon Status",
        "",
        f"Generated: {state['updated_at']}",
        "",
        "## Purpose",
        "",
        "Low-latency supervisor loop for Stage 2.4. It syncs remote outputs, detects idle machines, assigns the next validated learned-representation job, and emits concise Telegram events.",
        "",
        f"- Completed Stage 2.4 learned-representation jobs detected: {len(completed)}",
        f"- Last synced artifacts: {len(state.get('last_synced', []))}",
        f"- Last assignments: {len(state.get('last_assignments', []))}",
        "",
        "## Machines",
        "",
        "| Machine | State | Detail |",
        "| --- | --- | --- |",
    ]
    for item in state.get("machines", []):
        detail = item.get("job_id") or item.get("reason") or item.get("error") or item.get("lock", {}).get("command", "")
        lines.append(f"| {item.get('machine')} | {item.get('state')} | `{str(detail)[:180]}` |")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=float, default=45.0)
    args = parser.parse_args()

    if args.loop:
        while True:
            try:
                tick()
            except Exception as exc:
                append_event({"type": "daemon_error", "error": str(exc)})
                notify("daemon_error", "Project 3 event daemon error", f"status: daemon_error\nerror: {exc}\nneeds_codex: true")
            time.sleep(args.interval)
    else:
        tick()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
