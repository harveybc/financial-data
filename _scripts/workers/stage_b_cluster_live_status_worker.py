#!/usr/bin/env python3
"""Cluster-wide live status for Project 3 Stage B validation.

This worker queries every known worker machine and aggregates their local
``stage_b_machine_live_status_worker.py`` output. It is the authoritative status
entrypoint while Stage B jobs are distributed across dragon, gamma, and omega.
It also compares the fresh snapshot with the previous cluster snapshot so a
status query can say whether each active task has actually moved.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import socket
import subprocess
import argparse
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN_DIR = ROOT / "experiments/stage_b_validation/run_plan"
OUT_JSON = PLAN_DIR / "stage_b_cluster_live_status.json"
OUT_CSV = PLAN_DIR / "stage_b_cluster_live_status.csv"
OUT_MD = PLAN_DIR / "stage_b_cluster_live_status.md"
MACHINES = ("dragon", "gamma", "omega")
REMOTE_PYTHON = "/home/harveybc/anaconda3/envs/trading-stack/bin/python"
WORKER = "_scripts/workers/stage_b_machine_live_status_worker.py"
POLL_INTERVAL_SECONDS = 60


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: pathlib.Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def query_machine(machine: str, plan_json: pathlib.Path | None = None) -> dict[str, Any]:
    plan_arg = []
    if plan_json is not None:
        plan_arg = ["--plan-json", str(plan_json)]
    if machine == "omega" or socket.gethostname() == machine:
        cmd = [REMOTE_PYTHON, WORKER, "--machine", machine, *plan_arg]
    else:
        remote_plan = ""
        if plan_json is not None:
            remote_plan = f" --plan-json {plan_json}"
        remote = (
            "cd /home/harveybc/Documents/GitHub/financial-data && "
            f"{REMOTE_PYTHON} {WORKER} --machine {machine}{remote_plan}"
        )
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", machine, remote]
    try:
        raw = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=20)
        payload = json.loads(raw)
        payload["query_ok"] = True
        return payload
    except Exception as exc:
        return {
            "machine": machine,
            "hostname": "",
            "gpu": "",
            "assigned": 0,
            "counts": {"done": 0, "running": 0, "not_started": 0, "aborted_no_trade": 0, "failed": 0},
            "active": [],
            "processes": "",
            "query_ok": False,
            "query_error": str(exc),
        }


def previous_active_index(previous: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in previous.get("active_rows", []):
        key = (str(row.get("machine", "")), str(row.get("variant_id", "")))
        out[key] = row
    return out


def flatten_active(
    machine_payloads: list[dict[str, Any]],
    previous: dict[str, Any],
) -> list[dict[str, Any]]:
    prior = previous_active_index(previous)
    rows: list[dict[str, Any]] = []
    for payload in machine_payloads:
        machine = str(payload.get("machine", ""))
        for active in payload.get("active", []):
            variant_id = str(active.get("variant_id", ""))
            key = (machine, variant_id)
            prev = prior.get(key, {})
            pct = safe_float(active.get("progress_pct"))
            trades_raw = safe_int(active.get("trades_total"))
            trades_cumulative = active.get("trades_total_cumulative")
            trades = safe_int(trades_cumulative, trades_raw) if trades_cumulative not in (None, "") else trades_raw
            prev_pct = safe_float(prev.get("progress_pct"), pct)
            prev_trades = safe_int(prev.get("trades_total"), trades)
            delta_pct = pct - prev_pct
            delta_trades = trades - prev_trades
            comparison_reset = bool(prev and (delta_pct < 0.0 or delta_trades < 0))
            if comparison_reset:
                prev_pct_out = None
                prev_trades_out = None
                delta_pct_out = None
                delta_trades_out = None
                progress_advancing: bool | None = None
                nonmonotonic = False
                reset_reason = "active_task_restarted_or_progress_counter_reset"
            else:
                prev_pct_out = prev_pct if prev else None
                prev_trades_out = prev_trades if prev else None
                delta_pct_out = round(delta_pct, 4) if prev else None
                delta_trades_out = delta_trades if prev else None
                progress_advancing = (delta_pct > 0.0) if prev else None
                nonmonotonic = False
                reset_reason = ""
            row = {
                "machine": machine,
                "variant_id": variant_id,
                "status": active.get("status"),
                "progress_pct": pct,
                "previous_progress_pct": prev_pct_out,
                "delta_progress_pct": delta_pct_out,
                "current_step": active.get("current_step"),
                "total_timesteps": active.get("total_timesteps"),
                "trades_total": trades,
                "trades_total_raw": trades_raw,
                "trades_total_current_episode": active.get("trades_total_current_episode"),
                "trade_counter_reset_count": active.get("trade_counter_reset_count"),
                "previous_trades_total": prev_trades_out,
                "delta_trades_total": delta_trades_out,
                "comparison_reset": comparison_reset,
                "comparison_reset_reason": reset_reason,
                "live_trades_nonmonotonic": nonmonotonic,
                "profit_percent": safe_float(active.get("profit_percent")),
                "total_return": safe_float(active.get("total_return")),
                "no_trade_anomaly": bool(active.get("no_trade_anomaly")),
                "no_trade_diagnosis": active.get("no_trade_diagnosis"),
                "config_file": active.get("config_file"),
                "progress_file": active.get("progress_file"),
                "progress_advancing": progress_advancing,
            }
            rows.append(row)
    return rows


def build_status(plan_json: pathlib.Path | None = None) -> dict[str, Any]:
    previous = load_json(OUT_JSON, {})
    machines = [query_machine(machine, plan_json) for machine in MACHINES]
    counts = {"done": 0, "running": 0, "not_started": 0, "aborted_no_trade": 0, "failed": 0}
    assigned = 0
    for payload in machines:
        assigned += safe_int(payload.get("assigned"))
        for key in counts:
            counts[key] += safe_int((payload.get("counts") or {}).get(key))
    active_rows = flatten_active(machines, previous if isinstance(previous, dict) else {})
    query_errors = {
        p.get("machine"): p.get("query_error")
        for p in machines
        if not p.get("query_ok")
    }
    generated_at = dt.datetime.now(dt.timezone.utc)
    return {
        "schema_version": "project3_stage_b_cluster_live_status_v1",
        "generated_at_utc": generated_at.isoformat(),
        "poll_interval_seconds": POLL_INTERVAL_SECONDS,
        "plan_json": str(plan_json) if plan_json is not None else "",
        "next_expected_poll_utc": (
            generated_at + dt.timedelta(seconds=POLL_INTERVAL_SECONDS)
        ).isoformat(),
        "machines": machines,
        "assigned": assigned,
        "counts": counts,
        "active_rows": active_rows,
        "query_errors": query_errors,
        "all_queries_ok": not query_errors,
    }


def write_outputs(payload: dict[str, Any]) -> None:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    fields = [
        "machine", "variant_id", "status", "progress_pct", "previous_progress_pct",
        "delta_progress_pct", "current_step", "total_timesteps", "trades_total",
        "trades_total_raw", "trades_total_current_episode", "trade_counter_reset_count",
        "previous_trades_total", "delta_trades_total", "live_trades_nonmonotonic",
        "comparison_reset", "comparison_reset_reason",
        "profit_percent", "total_return",
        "no_trade_anomaly", "no_trade_diagnosis", "progress_advancing",
        "config_file", "progress_file",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload["active_rows"])

    lines = [
        "# Project 3 Stage B Cluster Live Status",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        f"Next expected poll UTC: `{payload['next_expected_poll_utc']}`",
        f"Poll interval seconds: `{payload['poll_interval_seconds']}`",
        f"All machine queries OK: `{payload['all_queries_ok']}`",
        f"Assigned tasks: `{payload['assigned']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- `{key}`: {value}")
    if payload["query_errors"]:
        lines += ["", "## Query Errors", ""]
        for machine, error in payload["query_errors"].items():
            lines.append(f"- `{machine}`: {error}")
    lines += [
        "",
        "## Active Tasks",
        "",
        "| Machine | Variant | Progress % | Delta % | Trades | Delta Trades | Profit % | Advancing | Comparison Reset | No-Trade Anomaly |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    if payload["active_rows"]:
        for row in payload["active_rows"]:
            lines.append(
                f"| {row['machine']} | {row['variant_id']} | {row['progress_pct']} | "
                f"{row['delta_progress_pct']} | {row['trades_total']} | "
                f"{row['delta_trades_total']} | {row['profit_percent']} | "
                f"{row['progress_advancing']} | {row['comparison_reset']} | "
                f"{row['no_trade_anomaly']} |"
            )
    else:
        lines.append("| None | - | - | - | - | - | - | - | - | - |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-json", type=pathlib.Path, default=None)
    args = parser.parse_args()
    payload = build_status(args.plan_json)
    write_outputs(payload)
    print(json.dumps({
        "ok": payload["all_queries_ok"],
        "counts": payload["counts"],
        "active": [
            {
                "machine": r["machine"],
                "variant_id": r["variant_id"],
                "progress_pct": r["progress_pct"],
                "delta_progress_pct": r["delta_progress_pct"],
                "trades_total": r["trades_total"],
                "live_trades_nonmonotonic": r["live_trades_nonmonotonic"],
                "comparison_reset": r["comparison_reset"],
                "comparison_reset_reason": r["comparison_reset_reason"],
                "delta_trades_total": r["delta_trades_total"],
                "profit_percent": r["profit_percent"],
                "progress_advancing": r["progress_advancing"],
                "no_trade_anomaly": r["no_trade_anomaly"],
            }
            for r in payload["active_rows"]
        ],
        "query_errors": payload["query_errors"],
        "next_expected_poll_utc": payload["next_expected_poll_utc"],
        "poll_interval_seconds": payload["poll_interval_seconds"],
        "json": str(OUT_JSON),
        "csv": str(OUT_CSV),
        "markdown": str(OUT_MD),
    }, indent=2, sort_keys=True))
    return 0 if payload["all_queries_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
