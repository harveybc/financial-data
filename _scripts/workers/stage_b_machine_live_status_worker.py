#!/usr/bin/env python3
"""Live per-machine Stage B status.

Reports active executor/agent-multi processes, GPU utilization, current config,
progress percent, trades, returns, and assigned/done/running/not-started counts
for the requested machine. Intended to be safe to run locally or over SSH.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import socket
import subprocess
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN_JSON = ROOT / "experiments/stage_b_validation/run_plan/stage_b_locked_run_plan.json"


def load_json(path: pathlib.Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def run_text(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"ERROR: {exc}"


def shell_text(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"ERROR: {exc}"


def progress_payload(path: pathlib.Path) -> dict[str, Any]:
    payload = load_json(path, {})
    return payload if isinstance(payload, dict) else {}


def active_configs_from_ps(ps_text: str) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for match in re.finditer(r"--load_config\s+(\S+)", ps_text):
        out.append(pathlib.Path(match.group(1)))
    return out


def classify_entry(entry: dict[str, Any], active_config_paths: set[str] | None = None) -> str:
    if active_config_paths and str(entry.get("config_file", "")) in active_config_paths:
        return "running"
    run_dir = pathlib.Path(str(entry.get("run_dir", "")))
    progress_file = pathlib.Path(str(entry.get("progress_file", "")))
    progress = progress_payload(progress_file)
    status = progress.get("status")
    if status == "blocked_no_trade_early_abort":
        return "aborted_no_trade"
    if status in {"failed", "aborted"}:
        return "failed"
    if status in {"complete", "training_complete", "subprocess_complete"} or (run_dir / "summary.json").exists():
        return "done"
    if progress_file.exists():
        return "running"
    return "not_started"


def build_status(machine: str, plan_json: pathlib.Path = PLAN_JSON) -> dict[str, Any]:
    plan = load_json(plan_json, {})
    entries = [e for e in plan.get("configs", []) if e.get("machine_hint") == machine]
    ps_text = shell_text(
        "ps -eo pid,etimes,pcpu,args | "
        "grep -E 'stage_b_locked_run_executor|/bin/agent-multi --load_config' | "
        "grep -v grep || true"
    )
    active_config_paths = {str(path) for path in active_configs_from_ps(ps_text)}
    active: list[dict[str, Any]] = []
    for config_path in active_configs_from_ps(ps_text):
        config = load_json(config_path, {})
        progress_file = pathlib.Path(str(config.get("training_progress_file") or config.get("progress_file") or ""))
        progress = progress_payload(progress_file)
        active.append({
            "variant_id": config_path.stem,
            "config_file": str(config_path),
            "progress_file": str(progress_file),
            "progress_exists": progress_file.exists(),
            "status": progress.get("status"),
            "progress_pct": progress.get("progress_pct", progress.get("progress_percent")),
            "current_step": progress.get("current_step", progress.get("num_timesteps")),
            "total_timesteps": progress.get("total_timesteps"),
            "trades_total": progress.get("trades_total"),
            "trades_total_cumulative": progress.get("trades_total_cumulative"),
            "trades_total_current_episode": progress.get("trades_total_current_episode"),
            "trade_counter_reset_count": progress.get("trade_counter_reset_count"),
            "total_return": progress.get("total_return"),
            "profit_percent": progress.get("profit_percent"),
            "no_trade_anomaly": progress.get("no_trade_anomaly"),
            "no_trade_diagnosis": progress.get("no_trade_diagnosis"),
        })
    counts = {"done": 0, "running": 0, "not_started": 0, "aborted_no_trade": 0, "failed": 0}
    for entry in entries:
        counts[classify_entry(entry, active_config_paths)] += 1
    gpu = run_text([
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ])
    return {
        "machine": machine,
        "hostname": socket.gethostname(),
        "plan_json": str(plan_json),
        "gpu": gpu,
        "assigned": len(entries),
        "counts": counts,
        "active": active,
        "processes": ps_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", default=socket.gethostname())
    parser.add_argument("--plan-json", type=pathlib.Path, default=PLAN_JSON)
    args = parser.parse_args()
    print(json.dumps(build_status(args.machine, args.plan_json), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
