#!/usr/bin/env python3
"""Redispatch idle Stage B GPU capacity to the remaining global backlog.

This worker is intentionally conservative:

* it only moves ``NOT_STARTED_LOCKED`` entries;
* it never launches on a machine with an active agent-multi process;
* it syncs the modified locked plan to every machine before launching;
* it launches one stolen variant per idle target, through the locked executor.

The locked executor has its own duplicate-run protection, so this worker is the
orchestrator layer and not the final safety boundary.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAN_DIR = ROOT / "experiments/stage_b_validation/run_plan"
PLAN_JSON = PLAN_DIR / "stage_b_locked_run_plan.json"
OUT_JSON = PLAN_DIR / "stage_b_idle_redispatcher_state.json"
OUT_MD = PLAN_DIR / "stage_b_idle_redispatcher_state.md"
LOCK_FILE = PLAN_DIR / "stage_b_idle_redispatcher.lock"
REMOTE_ROOT = "/home/harveybc/Documents/GitHub/financial-data"
PYTHON = "/home/harveybc/anaconda3/envs/trading-stack/bin/python"
EXECUTOR = "_scripts/workers/stage_b_locked_run_executor.py"
APPROVAL_TOKEN = "RUN_STAGE_B_VALIDATION"
MACHINES = ("dragon", "gamma", "omega")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_text(cmd: list[str], *, timeout: int = 20) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()


def shell_text(cmd: str, *, timeout: int = 20) -> str:
    return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()


def remote_cmd(machine: str, command: str) -> list[str]:
    if machine == "omega" or socket.gethostname() == machine:
        return ["bash", "-lc", command]
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", machine, command]


def machine_status(machine: str) -> dict[str, Any]:
    cmd = remote_cmd(machine, f"cd {REMOTE_ROOT} && {PYTHON} _scripts/workers/stage_b_machine_live_status_worker.py --machine {machine}")
    try:
        payload = json.loads(run_text(cmd, timeout=30))
        payload["query_ok"] = True
        return payload
    except Exception as exc:
        return {
            "machine": machine,
            "assigned": 0,
            "counts": {},
            "active": [],
            "query_ok": False,
            "query_error": str(exc),
        }


def progress_status(entry: dict[str, Any]) -> str:
    run_dir = Path(str(entry.get("run_dir", "")))
    progress_file = Path(str(entry.get("progress_file", "")))
    progress = load_json(progress_file, {})
    if progress.get("status") == "blocked_no_trade_early_abort":
        return "aborted_no_trade"
    if progress.get("status") in {"failed", "aborted"}:
        return "failed"
    if progress.get("status") in {"complete", "training_complete", "subprocess_complete"}:
        return "done"
    if (run_dir / "summary.json").exists() or Path(str(entry.get("expected_evidence_file", ""))).exists():
        return "done"
    if progress_file.exists():
        return "running"
    return "not_started"


def count_by_machine(entries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts = {
        machine: {"done": 0, "running": 0, "not_started": 0, "failed": 0, "aborted_no_trade": 0}
        for machine in MACHINES
    }
    for entry in entries:
        machine = str(entry.get("machine_hint", ""))
        if machine not in counts:
            continue
        counts[machine][progress_status(entry)] += 1
    return counts


def idle_targets(machine_payloads: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    for machine, payload in machine_payloads.items():
        counts = payload.get("counts") or {}
        active = payload.get("active") or []
        if payload.get("query_ok") and not active and int(counts.get("not_started") or 0) == 0:
            out.append(machine)
    return out


def source_backlog(counts: dict[str, dict[str, int]], *, exclude: set[str]) -> list[str]:
    machines = [m for m in MACHINES if m not in exclude]
    return sorted(machines, key=lambda m: counts[m]["not_started"], reverse=True)


def remote_counts(machine_payloads: dict[str, dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts = {
        machine: {"done": 0, "running": 0, "not_started": 0, "failed": 0, "aborted_no_trade": 0}
        for machine in MACHINES
    }
    for machine, payload in machine_payloads.items():
        raw = payload.get("counts") or {}
        for key in counts[machine]:
            try:
                counts[machine][key] = int(raw.get(key) or 0)
            except (TypeError, ValueError):
                counts[machine][key] = 0
    return counts


def choose_moves(
    entries: list[dict[str, Any]],
    machine_payloads: dict[str, dict[str, Any]],
    *,
    max_moves: int,
) -> list[dict[str, str]]:
    counts = remote_counts(machine_payloads)
    targets = idle_targets(machine_payloads)
    moves: list[dict[str, str]] = []
    used_sources: set[str] = set()
    for target in targets:
        for source in source_backlog(counts, exclude={target, *used_sources}):
            if counts[source]["not_started"] <= 0:
                continue
            candidate = next(
                (
                    entry for entry in entries
                    if entry.get("machine_hint") == source and progress_status(entry) == "not_started"
                ),
                None,
            )
            if candidate is None:
                continue
            moves.append({
                "variant_id": str(candidate["variant_id"]),
                "source": source,
                "target": target,
            })
            counts[source]["not_started"] -= 1
            counts[target]["not_started"] += 1
            used_sources.add(source)
            break
        if len(moves) >= max_moves:
            break
    return moves


def apply_moves(plan: dict[str, Any], moves: list[dict[str, str]]) -> None:
    by_id = {str(entry.get("variant_id")): entry for entry in plan.get("configs", [])}
    history = plan.setdefault("redispatch_history", [])
    for move in moves:
        entry = by_id[move["variant_id"]]
        entry.setdefault("original_machine_hint", entry.get("machine_hint", ""))
        entry["machine_hint"] = move["target"]
        entry["redispatched_from"] = move["source"]
        entry["redispatched_to"] = move["target"]
        entry["redispatched_at_utc"] = utc_now()
        history.append({
            "variant_id": move["variant_id"],
            "source": move["source"],
            "target": move["target"],
            "redispatched_at_utc": entry["redispatched_at_utc"],
        })
    if moves:
        plan["machine_assignment_rule"] = "stage_b_idle_redispatcher_dynamic"
        plan["last_redispatch_at_utc"] = utc_now()


def ensure_target_inputs(move: dict[str, str], entry: dict[str, Any]) -> list[str]:
    target = move["target"]
    copied: list[str] = []
    paths = [
        Path(str(entry.get("config_file", ""))),
        Path(str(entry.get("input_data_file", ""))),
    ]
    metadata = Path(str(entry.get("input_data_file", ""))).with_name("train_metadata.json")
    if metadata.exists():
        paths.append(metadata)
    if target == "omega" or socket.gethostname() == target:
        return copied
    for path in paths:
        if not path.exists():
            continue
        rel = path.relative_to(ROOT)
        remote_path = f"{REMOTE_ROOT}/{rel}"
        run_text(["ssh", target, f"mkdir -p {Path(remote_path).parent}"], timeout=20)
        run_text(["rsync", "-a", str(path), f"{target}:{remote_path}"], timeout=120)
        copied.append(str(rel))
    return copied


def sync_plan_to_machines() -> None:
    for machine in MACHINES:
        if machine == "omega" or socket.gethostname() == machine:
            continue
        run_text(["rsync", "-a", str(PLAN_JSON), f"{machine}:{REMOTE_ROOT}/experiments/stage_b_validation/run_plan/stage_b_locked_run_plan.json"], timeout=60)


def remote_variant_active(machine: str, variant_id: str) -> str:
    quoted = shlex.quote(variant_id)
    command = (
        "ps -eo pid,etimes,pcpu,args | "
        f"grep -F -- {quoted} | "
        "grep -E 'stage_b_locked_run_executor|agent-multi --load_config' | "
        "grep -v grep || true"
    )
    return run_text(remote_cmd(machine, command), timeout=10)


def launch_move(move: dict[str, str]) -> dict[str, Any]:
    target = move["target"]
    variant_id = move["variant_id"]
    log = f"{REMOTE_ROOT}/experiments/stage_b_validation/run_plan/redispatch_{target}_{variant_id}.nohup.log"
    command = (
        f"cd {REMOTE_ROOT} && "
        f"nohup {PYTHON} {EXECUTOR} --execute --approval-token {APPROVAL_TOKEN} "
        f"--variant-id {variant_id} "
        f"> {log} 2>&1 < /dev/null & echo $!"
    )
    try:
        pid = run_text(remote_cmd(target, command), timeout=20)
        return {"variant_id": variant_id, "target": target, "pid": pid, "log": log}
    except subprocess.TimeoutExpired as exc:
        active = remote_variant_active(target, variant_id)
        if active:
            return {
                "variant_id": variant_id,
                "target": target,
                "pid": "unknown_after_ssh_timeout",
                "log": log,
                "launch_warning": f"ssh launch timed out after {exc.timeout}s, but remote process is active",
                "active_process": active,
            }
        raise


def acquire_lock() -> None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"redispatcher already running or stale lock exists: {LOCK_FILE}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"pid": os.getpid(), "created_at_utc": utc_now()}) + "\n")


def release_lock() -> None:
    try:
        LOCK_FILE.unlink()
    except FileNotFoundError:
        pass


def build_once(*, execute: bool, max_moves: int) -> dict[str, Any]:
    plan = load_json(PLAN_JSON, {})
    if not isinstance(plan, dict) or not plan.get("configs"):
        raise RuntimeError(f"invalid run plan: {PLAN_JSON}")
    entries = list(plan["configs"])
    machine_payloads = {machine: machine_status(machine) for machine in MACHINES}
    moves = choose_moves(entries, machine_payloads, max_moves=max_moves)
    launch_results: list[dict[str, Any]] = []
    copied: dict[str, list[str]] = {}
    if execute and moves:
        apply_moves(plan, moves)
        write_json(PLAN_JSON, plan)
        by_id = {str(entry.get("variant_id")): entry for entry in plan.get("configs", [])}
        for move in moves:
            copied[move["variant_id"]] = ensure_target_inputs(move, by_id[move["variant_id"]])
        sync_plan_to_machines()
        for move in moves:
            launch_results.append(launch_move(move))
    payload = {
        "schema_version": "project3_stage_b_idle_redispatcher_v1",
        "generated_at_utc": utc_now(),
        "execute": execute,
        "machine_counts": remote_counts(machine_payloads),
        "machine_query_ok": {m: p.get("query_ok", False) for m, p in machine_payloads.items()},
        "machine_active": {m: [a.get("variant_id") for a in p.get("active", [])] for m, p in machine_payloads.items()},
        "moves": moves,
        "copied_inputs": copied,
        "launch_results": launch_results,
    }
    write_json(OUT_JSON, payload)
    write_markdown(payload)
    return payload


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Project 3 Stage B Idle Redispatcher",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        f"Execute: `{payload['execute']}`",
        "",
        "## Machine Counts",
        "",
        "| Machine | Done | Running | Not Started | Failed | Aborted No-Trade | Active |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for machine, counts in payload["machine_counts"].items():
        active = ",".join(payload["machine_active"].get(machine, []))
        lines.append(
            f"| {machine} | {counts['done']} | {counts['running']} | "
            f"{counts['not_started']} | {counts['failed']} | {counts['aborted_no_trade']} | {active} |"
        )
    lines += ["", "## Moves", ""]
    if payload["moves"]:
        for move in payload["moves"]:
            lines.append(f"- `{move['variant_id']}`: `{move['source']}` -> `{move['target']}`")
    else:
        lines.append("- None")
    if payload["launch_results"]:
        lines += ["", "## Launches", ""]
        for result in payload["launch_results"]:
            lines.append(f"- `{result['variant_id']}` on `{result['target']}` pid `{result['pid']}`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--max-moves", type=int, default=2)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    execute = bool(args.execute)
    if execute and args.approval_token != APPROVAL_TOKEN:
        raise RuntimeError(f"execution requires --approval-token {APPROVAL_TOKEN!r}")
    acquire_lock()
    try:
        while True:
            payload = build_once(execute=execute, max_moves=max(1, args.max_moves))
            print(json.dumps({
                "ok": True,
                "execute": execute,
                "moves": payload["moves"],
                "launch_results": payload["launch_results"],
                "state_file": str(OUT_JSON),
            }, indent=2, sort_keys=True))
            if not args.loop:
                return 0
            time.sleep(max(10.0, args.poll_seconds))
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
