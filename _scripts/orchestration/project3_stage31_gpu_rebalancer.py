#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import os
import shlex
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
PYTHON = os.environ.get("PROJECT3_PYTHON", "/home/harveybc/anaconda3/envs/tensorflow/bin/python")
SSH_PORT = "22022"
WORKER_MAX_JOBS = int(os.environ.get("PROJECT3_STAGE31_WORKER_MAX_JOBS", "10"))
HOSTS = {
    "dragon": "192.0.2.13",
    "gamma": "192.0.2.15",
}
RUNNABLE_STATUSES = {"", "pending", "queued", "retry", "needs_retry"}
ACTIVE_STATUSES = {"preparing_input", "training", "running", "registered"}
STRIP_MACHINE_FIELDS = {
    "completed_at",
    "config",
    "exit_code",
    "failure_reason",
    "host",
    "input_csv",
    "machine_run_id",
    "output_dir",
    "run_dir",
    "started_at",
    "stdout_tail",
    "summary_path",
    "trial_id",
    "worker_pid",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str] | str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    if isinstance(cmd, str):
        return subprocess.run(
            ["bash", "-lc", cmd],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)


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


def queue_path(machine: str) -> Path:
    return ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"


def machine_host(machine: str) -> str:
    if machine not in HOSTS:
        raise ValueError(f"unsupported remote GPU machine: {machine}")
    return HOSTS[machine]


def rsync_from(machine: str, rel: str, dst: Path | None = None, timeout: int = 60) -> None:
    dst = dst or (ROOT / rel)
    dst.parent.mkdir(parents=True, exist_ok=True)
    src = f"harveybc@{machine_host(machine)}:{ROOT / rel}"
    run(f"rsync -az -e 'ssh -p {SSH_PORT}' {shlex.quote(src)} {shlex.quote(str(dst))}", timeout=timeout)


def rsync_to(machine: str, rel: str, timeout: int = 60) -> None:
    src = ROOT / rel
    dst = f"harveybc@{machine_host(machine)}:{ROOT / rel}"
    run(f"rsync -az -e 'ssh -p {SSH_PORT}' {shlex.quote(str(src))} {shlex.quote(dst)}", timeout=timeout)


def rsync_dir_to(machine: str, rel_dir: str, timeout: int = 180) -> None:
    src = ROOT / rel_dir
    if not src.exists():
        raise FileNotFoundError(f"local sync source missing: {src}")
    dst = f"harveybc@{machine_host(machine)}:{ROOT / rel_dir}"
    suffix = "/" if src.is_dir() else ""
    run(f"rsync -az -e 'ssh -p {SSH_PORT}' {shlex.quote(str(src))}{suffix} {shlex.quote(dst)}{suffix}", timeout=timeout)


def remote_busy(machine: str) -> bool:
    probe = r"""
import os
needles = ("stage31_agent_multi_run_worker.py", "agent-multi/tools/seed_sweep.py")
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        raw = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    cmd = raw.replace(b"\x00", b" ").decode("utf-8", "ignore").strip()
    if any(needle in cmd for needle in needles):
        print(cmd)
"""
    cp = run(
        [
            "ssh",
            "-o",
            "ConnectTimeout=5",
            "-p",
            SSH_PORT,
            f"harveybc@{machine_host(machine)}",
            f"python3 - <<'PY'\n{probe}PY",
        ],
        timeout=15,
    )
    return bool(cp.stdout.strip())


def remote_active_run_ids(machine: str) -> set[str]:
    host = machine_host(machine)
    cp = run(
        [
            "ssh",
            "-o",
            "ConnectTimeout=5",
            "-p",
            SSH_PORT,
            f"harveybc@{host}",
            (
                "ps -eo args= | "
                "awk '(/agent-multi\\/tools\\/seed_sweep.py/) && !/awk/ {print}'"
            ),
        ],
        timeout=15,
    )
    active: set[str] = set()
    marker = f"configs/{machine}/"
    for line in cp.stdout.splitlines():
        if marker not in line:
            continue
        tail = line.split(marker, 1)[1].split()[0]
        if tail.endswith(".json"):
            active.add(tail[:-5])
    return active


def annotate_live_active(machine: str, jobs: list[dict[str, Any]]) -> set[str]:
    active = remote_active_run_ids(machine)
    if not active:
        return active
    for job in jobs:
        run_id = str(job.get("run_id") or "")
        if run_id in active:
            job["status"] = "training"
            job.setdefault("live_process_confirmed_at", utc_now())
    return active


def launch_worker(machine: str) -> str:
    host = machine_host(machine)
    cmd = (
        "source ~/.bashrc >/dev/null 2>&1 || true; "
        "source /home/harveybc/anaconda3/etc/profile.d/conda.sh >/dev/null 2>&1 || true; "
        "conda activate tensorflow >/dev/null 2>&1 || true; "
        f"cd {shlex.quote(str(ROOT))} || exit 1; "
        f"setsid -f python _scripts/workers/stage31_agent_multi_run_worker.py --machine {shlex.quote(machine)} "
        f"--max-jobs {WORKER_MAX_JOBS} --timeout-minutes 180 "
        f"> _logs/supervisor_reports/stage31_worker_{shlex.quote(machine)}.nohup.log 2>&1 < /dev/null; "
        "sleep 2; "
        "ps -eo pid=,args= | grep -E 'stage31_agent_multi_run_worker.py|agent-multi/tools/seed_sweep.py' | grep -v grep || true"
    )
    cp = run(["ssh", "-o", "ConnectTimeout=5", "-p", SSH_PORT, f"harveybc@{host}", f"bash -lc {shlex.quote(cmd)}"], timeout=45)
    return cp.stdout.strip()


def kill_target_run(machine: str, run_id: str) -> str:
    host = machine_host(machine)
    # Match the seed_sweep config path first, then stop the worker so it cannot
    # continue from an already-cancelled queue snapshot.
    cmd = (
        f"pkill -f {shlex.quote('configs/' + machine + '/' + run_id + '.json')} || true; "
        f"pkill -f {shlex.quote('stage31_agent_multi_run_worker.py --machine ' + machine)} || true; "
        "sleep 2; "
        "if ! ps -eo args= | grep -E 'stage31_agent_multi_run_worker.py|agent-multi/tools/seed_sweep.py' | grep -v grep >/dev/null; "
        "then rm -f /tmp/gpu_busy.lock; fi; "
        "ps -eo pid=,args= | grep -E 'stage31_agent_multi_run_worker.py|agent-multi/tools/seed_sweep.py' | grep -v grep || true"
    )
    cp = run(["ssh", "-o", "ConnectTimeout=5", "-p", SSH_PORT, f"harveybc@{host}", f"bash -lc {shlex.quote(cmd)}"], timeout=30)
    return cp.stdout.strip()


def status_value(job: dict[str, Any]) -> str:
    return str(job.get("status") or "pending").lower()


def is_pending(job: dict[str, Any]) -> bool:
    return status_value(job) in RUNNABLE_STATUSES


def is_active(job: dict[str, Any]) -> bool:
    return status_value(job) in ACTIVE_STATUSES


def strip_machine_fields(job: dict[str, Any]) -> None:
    for key in STRIP_MACHINE_FIELDS:
        job.pop(key, None)


def pending_assets(jobs: list[dict[str, Any]]) -> set[str]:
    assets: set[str] = set()
    for job in jobs:
        if is_pending(job) and job.get("asset"):
            assets.add(str(job["asset"]))
    return assets


def sync_assets(assets: set[str], machines: list[str]) -> dict[str, list[str]]:
    synced: dict[str, list[str]] = {machine: [] for machine in machines}
    for asset in sorted(assets):
        data_rel = f"features/trading_asset_data/{asset}"
        features_rel = f"features/trading_asset_features/{asset}"
        if not (ROOT / data_rel).exists() or not (ROOT / features_rel).exists():
            raise FileNotFoundError(f"missing local data/features for pending asset {asset}")
        for machine in machines:
            rsync_dir_to(machine, data_rel)
            rsync_dir_to(machine, features_rel)
            synced[machine].append(asset)
    return synced


def duplicate_report(queues: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    runnable: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    all_ids: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for machine, jobs in queues.items():
        for idx, job in enumerate(jobs):
            run_id = job.get("run_id")
            if not run_id:
                continue
            status = status_value(job)
            all_ids[str(run_id)].append((machine, idx, status))
            if is_pending(job) or is_active(job):
                runnable[str(run_id)].append((machine, idx, status))
    runnable_dups = {run_id: rows for run_id, rows in runnable.items() if len(rows) > 1}
    suspicious = {}
    for run_id, rows in all_ids.items():
        runnable_count = sum(status in RUNNABLE_STATUSES or status in ACTIVE_STATUSES for _, _, status in rows)
        if runnable_count > 1:
            suspicious[run_id] = rows
    return {
        "runnable_duplicate_count": len(runnable_dups),
        "runnable_duplicates": runnable_dups,
        "suspicious_duplicate_count": len(suspicious),
        "suspicious_duplicates": suspicious,
    }


def rebalance(source: str, target: str, target_pending: int, *, pull_remote: bool, execute: bool, launch: bool) -> dict[str, Any]:
    if source == target:
        raise ValueError("source and target must differ")
    if source not in HOSTS or target not in HOSTS:
        raise ValueError("source and target must be remote GPU machine names")

    if pull_remote:
        rsync_from(source, f"experiments/stage_a_screening/queues/{source}.json", queue_path(source))
        rsync_from(target, f"experiments/stage_a_screening/queues/{target}.json", queue_path(target))

    source_jobs = read_json(queue_path(source), [])
    target_jobs = read_json(queue_path(target), [])
    if not isinstance(source_jobs, list) or not isinstance(target_jobs, list):
        raise ValueError("queue file is not a JSON list")

    source_live_active = annotate_live_active(source, source_jobs)
    target_live_active = annotate_live_active(target, target_jobs)

    # Heal any previous partial reroute before calculating capacity. This is
    # the critical duplicate-prevention rule: once a run_id exists on the
    # target as a reroute from the source, the source copy must not remain
    # pending. If the source is already active or complete, keep the source and
    # make the target copy non-runnable instead.
    target_existing = {
        job.get("run_id"): job
        for job in target_jobs
        if job.get("run_id")
    }
    healed_source_rows: list[str] = []
    healed_target_rows: list[str] = []
    target_rows_to_kill: list[str] = []
    for source_job in source_jobs:
        run_id = source_job.get("run_id")
        if run_id not in target_existing:
            continue
        target_job = target_existing[run_id]
        if is_active(source_job) or status_value(source_job) == "complete":
            if is_pending(target_job) or is_active(target_job):
                # Kill the target process only when the kept source row is
                # genuinely active. A completed source row should block future
                # duplicate work, but it must not kill an unrelated target
                # process if stale queue metadata briefly overlaps.
                if is_active(source_job) and is_active(target_job):
                    target_rows_to_kill.append(str(run_id))
                target_job["status"] = f"blocked_duplicate_cancelled_kept_on_{source}"
                target_job["duplicate_cancelled_on"] = target
                target_job["kept_on"] = source
                healed_target_rows.append(str(run_id))
            continue
        if is_pending(source_job):
            source_job["status"] = f"blocked_resolved_rerouted_to_{target}"
            source_job["rerouted_to"] = target
            source_job.setdefault("reroute_reason", f"auto_heal_existing_reroute_{utc_now()}")
            strip_machine_fields(source_job)
            healed_source_rows.append(str(run_id))

    target_open = sum(1 for job in target_jobs if is_pending(job) or is_active(job))
    desired_move = max(0, target_pending - target_open)
    source_pending = [(idx, job) for idx, job in enumerate(source_jobs) if is_pending(job)]
    # Leave at least one runnable source job behind when the source is not already active.
    source_has_active = any(is_active(job) for job in source_jobs) or bool(source_live_active)
    reserve = 0 if source_has_active else 1
    movable_count = max(0, len(source_pending) - reserve)
    move = [
        (idx, job)
        for idx, job in source_pending
        if str(job.get("run_id") or "") not in source_live_active
    ][: min(desired_move, movable_count)]

    moved_assets = {str(job.get("asset")) for _, job in move if job.get("asset")}
    synced_assets: dict[str, list[str]] = {}
    if moved_assets and execute:
        # Sync to both machines: target needs the rerouted work, source needs its remaining backlog.
        synced_assets = sync_assets(moved_assets | pending_assets(source_jobs), [source, target])

    reason = f"auto_rebalance_{utc_now()}_{source}_to_{target}"
    existing_target_ids = {job.get("run_id") for job in target_jobs}
    moved_run_ids: list[str] = []
    for idx, original in move:
        run_id = original.get("run_id")
        if run_id not in existing_target_ids:
            copied = copy.deepcopy(original)
            copied["status"] = "pending"
            copied["stage"] = f"3.1_stage_a_broad_matrix_{target}"
            copied["rerouted_from"] = source
            copied["rerouted_to"] = target
            copied["reroute_reason"] = reason
            strip_machine_fields(copied)
            target_jobs.append(copied)
            existing_target_ids.add(run_id)
            moved_run_ids.append(str(run_id))
        source_jobs[idx]["status"] = f"blocked_resolved_rerouted_to_{target}"
        source_jobs[idx]["rerouted_to"] = target
        source_jobs[idx]["reroute_reason"] = reason
        strip_machine_fields(source_jobs[idx])

    dupes = duplicate_report({source: source_jobs, target: target_jobs})
    if dupes["runnable_duplicate_count"] or dupes["suspicious_duplicate_count"]:
        raise RuntimeError(f"refusing to write duplicate runnable queues: {dupes}")

    launched = ""
    killed_target_duplicates: dict[str, str] = {}
    if execute:
        write_json(queue_path(source), source_jobs)
        write_json(queue_path(target), target_jobs)
        rsync_to(source, f"experiments/stage_a_screening/queues/{source}.json")
        rsync_to(target, f"experiments/stage_a_screening/queues/{target}.json")
        for run_id in target_rows_to_kill:
            killed_target_duplicates[run_id] = kill_target_run(target, run_id)
        if launch and moved_run_ids and not remote_busy(target):
            launched = launch_worker(target)

    return {
        "generated_at": utc_now(),
        "execute": execute,
        "source": source,
        "target": target,
        "target_pending": target_pending,
        "target_open_before": target_open,
        "source_pending_before": len(source_pending),
        "source_has_active": source_has_active,
        "source_live_active": sorted(source_live_active),
        "target_live_active": sorted(target_live_active),
        "moved_count": len(moved_run_ids),
        "moved_run_ids": moved_run_ids,
        "healed_source_rows": healed_source_rows,
        "healed_target_rows": healed_target_rows,
        "killed_target_duplicates": killed_target_duplicates,
        "synced_assets": synced_assets,
        "duplicate_report": dupes,
        "source_counts_after": dict(Counter(status_value(job) for job in source_jobs)),
        "target_counts_after": dict(Counter(status_value(job) for job in target_jobs)),
        "target_launch_detail": launched,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely rebalance Project 3 Stage 3.1 GPU queues.")
    parser.add_argument("--source", default="gamma")
    parser.add_argument("--target", default="dragon")
    parser.add_argument("--target-pending", type=int, default=24)
    parser.add_argument("--pull-remote", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args()
    payload = rebalance(
        args.source,
        args.target,
        args.target_pending,
        pull_remote=args.pull_remote,
        execute=args.execute,
        launch=args.launch,
    )
    out = ROOT / "_logs" / "supervisor_reports" / "stage31_gpu_rebalancer.json"
    write_json(out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
