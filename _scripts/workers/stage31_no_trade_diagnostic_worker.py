#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
INDEX = ROOT / "experiments" / "stage_a_screening" / "index.csv"
OUT_DIR = ROOT / "experiments" / "stage_a_screening" / "hardening"
OUT_CSV = OUT_DIR / "no_trade_diagnostic_report.csv"
OUT_JSON = OUT_DIR / "no_trade_diagnostic_report.json"
OUT_MD = OUT_DIR / "no_trade_diagnostic_report.md"


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


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_config(run_dir: Path) -> dict[str, Any]:
    for name in ("config.json", "run_config.json"):
        path = run_dir / name
        if path.exists():
            return read_json(path)
    return {}


def load_rows() -> list[dict[str, str]]:
    with INDEX.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def continuous_threshold(config: dict[str, Any]) -> float:
    for key in ("continuous_action_threshold", "action_threshold", "entry_threshold"):
        value = safe_float(config.get(key), math.nan)
        if not math.isnan(value) and value > 0:
            return value
    return 0.1


def trace_action_stats(
    trace_path: Path,
    *,
    algo: str,
    threshold: float,
    max_rows: int = 0,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "trace_file": str(trace_path),
        "trace_exists": trace_path.exists(),
        "trace_rows_scanned": 0,
        "trace_rows_limited": False,
        "trace_hold_actions": 0,
        "trace_non_hold_actions": 0,
        "trace_deadband_actions": 0,
        "trace_action_abs_sum": 0.0,
        "trace_raw_min": math.nan,
        "trace_raw_max": math.nan,
        "trace_parse_errors": 0,
    }
    if not trace_path.exists():
        return stats

    algo = algo.lower()
    try:
        with trace_path.open("r", encoding="utf-8", newline="") as handle:
            header = handle.readline().rstrip("\n").split(",")
            if "action_raw" not in header:
                stats["trace_parse_errors"] = 1
                stats["trace_error"] = "missing_action_raw"
                return stats
            action_idx = header.index("action_raw")
            for line in handle:
                rows = int(stats["trace_rows_scanned"])
                if max_rows > 0 and rows >= max_rows:
                    stats["trace_rows_limited"] = True
                    break
                stats["trace_rows_scanned"] = rows + 1
                parts = line.rstrip("\n").split(",")
                if action_idx >= len(parts):
                    stats["trace_parse_errors"] = int(stats["trace_parse_errors"]) + 1
                    continue
                try:
                    raw = float(parts[action_idx] or 0.0)
                except (TypeError, ValueError):
                    stats["trace_parse_errors"] = int(stats["trace_parse_errors"]) + 1
                    continue
                abs_raw = abs(raw)
                stats["trace_action_abs_sum"] = float(stats["trace_action_abs_sum"]) + abs_raw
                raw_min = stats["trace_raw_min"]
                raw_max = stats["trace_raw_max"]
                stats["trace_raw_min"] = raw if math.isnan(raw_min) else min(float(raw_min), raw)
                stats["trace_raw_max"] = raw if math.isnan(raw_max) else max(float(raw_max), raw)
                if algo == "sac":
                    if abs_raw >= threshold:
                        stats["trace_non_hold_actions"] = int(stats["trace_non_hold_actions"]) + 1
                    else:
                        stats["trace_deadband_actions"] = int(stats["trace_deadband_actions"]) + 1
                elif algo in {"ppo", "dqn"}:
                    discrete = int(round(raw))
                    if discrete == 0:
                        stats["trace_hold_actions"] = int(stats["trace_hold_actions"]) + 1
                    else:
                        stats["trace_non_hold_actions"] = int(stats["trace_non_hold_actions"]) + 1
                else:
                    if abs_raw >= threshold:
                        stats["trace_non_hold_actions"] = int(stats["trace_non_hold_actions"]) + 1
                    else:
                        stats["trace_hold_actions"] = int(stats["trace_hold_actions"]) + 1
    except Exception as exc:
        stats["trace_parse_errors"] = int(stats["trace_parse_errors"]) + 1
        stats["trace_error"] = f"{type(exc).__name__}: {exc}"
        return stats

    rows = int(stats["trace_rows_scanned"])
    if rows > 0:
        stats["trace_non_hold_rate"] = int(stats["trace_non_hold_actions"]) / rows
        stats["trace_deadband_rate"] = int(stats["trace_deadband_actions"]) / rows
        stats["trace_hold_rate"] = int(stats["trace_hold_actions"]) / rows
        stats["trace_action_abs_mean"] = float(stats["trace_action_abs_sum"]) / rows
    else:
        stats["trace_non_hold_rate"] = math.nan
        stats["trace_deadband_rate"] = math.nan
        stats["trace_hold_rate"] = math.nan
        stats["trace_action_abs_mean"] = math.nan
    return stats


def diagnose(row: dict[str, str], summary: dict[str, Any], trace_stats: dict[str, Any] | None = None) -> tuple[str, str]:
    algo = str(row.get("algo") or "").lower()
    trace_stats = trace_stats or {}
    trace_rows = safe_int(trace_stats.get("trace_rows_scanned"))
    trace_non_hold_rate = safe_float(trace_stats.get("trace_non_hold_rate"), math.nan)
    trace_deadband_rate = safe_float(trace_stats.get("trace_deadband_rate"), math.nan)
    trace_parse_errors = safe_int(trace_stats.get("trace_parse_errors"))
    if trace_rows > 0 and trace_parse_errors == 0:
        if not math.isnan(trace_non_hold_rate) and trace_non_hold_rate <= 0.001:
            if algo == "sac":
                return (
                    "policy_deadband_collapse",
                    "SAC raw actions stayed inside the continuous deadband. Treat as policy/action-scale collapse; do not promote. Diagnostic rerun must register threshold/action-scaling variants as new trials.",
                )
            return (
                "policy_hold_collapse",
                "Discrete policy selected hold almost always. Treat as policy/action-distribution collapse; inspect reward pressure and action masking before any rerun.",
            )
        if not math.isnan(trace_deadband_rate) and algo == "sac" and trace_deadband_rate >= 0.999:
            return (
                "policy_deadband_collapse",
                "SAC raw actions were effectively all below the trade threshold. Tightening the threshold is a new diagnostic trial, not a rescue.",
            )
        return (
            "non_hold_actions_but_no_trades",
            "Trace contains non-hold actions but the run still closed zero trades. Inspect strategy guards, sizing, ATR warmup, broker fills, and end-of-episode open positions.",
        )
    if trace_stats.get("trace_exists") and trace_parse_errors:
        return (
            "trace_unreadable",
            "A return trace exists but could not be parsed for action diagnostics; fix trace schema/reader before rerunning.",
        )
    action_non_hold_rate = safe_float(summary.get("action_non_hold_rate"), math.nan)
    entry_actions = safe_int(summary.get("execution_entry_actions_seen"), -1)
    orders = safe_int(summary.get("execution_entry_orders_submitted"), -1)
    blocked = {
        "atr_warmup": safe_int(summary.get("execution_blocked_atr_warmup")),
        "session_filter": safe_int(summary.get("execution_blocked_session_filter")),
        "non_positive_atr": safe_int(summary.get("execution_blocked_non_positive_atr")),
        "non_positive_size": safe_int(summary.get("execution_blocked_non_positive_size")),
        "non_positive_price": safe_int(summary.get("execution_blocked_non_positive_price")),
    }
    if not summary:
        return (
            "missing_summary",
            "Re-run with return_trace/progress diagnostics enabled; no summary.json was available.",
        )
    if not math.isnan(action_non_hold_rate):
        if action_non_hold_rate <= 0.001:
            return (
                "policy_hold_collapse",
                "Policy selected hold almost always; inspect reward/action scaling and add threshold/action diagnostics before rerun.",
            )
        if entry_actions == 0:
            return (
                "action_mapping_block",
                "Agent emitted non-hold raw actions but no entry action reached the strategy; inspect action mapping/deadband.",
            )
        if orders == 0:
            reason = max(blocked, key=lambda key: blocked[key])
            return (
                f"execution_guard_blocked:{reason}",
                "Strategy received entry actions but submitted no orders; inspect ATR warmup, sizing, session, and bracket guards.",
            )
        return (
            "orders_without_closed_trades",
            "Orders were submitted but no closed trades were recorded; inspect broker fills, brackets, and end-of-episode open positions.",
        )
    if algo in {"sac"}:
        return ("needs_continuous_action_trace", "No readable SAC action trace found; rerun with return_trace/action diagnostics enabled.")
    if algo in {"ppo", "dqn"}:
        return ("needs_discrete_action_trace", "No readable discrete action trace found; rerun with return_trace/action diagnostics enabled.")
    return ("needs_action_trace", "Unknown algo/action mode; rerun with action diagnostics enabled.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scan-traces",
        action="store_true",
        help="Read existing return_trace.csv files and classify no-trade action collapse directly.",
    )
    parser.add_argument(
        "--max-rows-per-trace",
        type=int,
        default=0,
        help="Limit rows scanned per trace. Default 0 scans full traces.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=50,
        help="When scanning traces, print progress every N no-trade rows. Default 50.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_rows()
    no_trade_rows = [row for row in rows if safe_int(row.get("trades_total")) <= 0]
    diagnostic_rows: list[dict[str, Any]] = []
    by_algo = Counter()
    by_diag = Counter()
    by_algo_tf = Counter()
    trace_scanned = 0
    trace_missing = 0
    for ordinal, row in enumerate(no_trade_rows, start=1):
        run_dir = Path(row.get("run_dir") or "")
        summary = read_json(run_dir / "summary.json") if run_dir else {}
        config = load_config(run_dir) if run_dir else {}
        threshold = continuous_threshold(config)
        trace_stats: dict[str, Any] = {}
        if args.scan_traces and run_dir:
            trace_stats = trace_action_stats(
                run_dir / "return_trace.csv",
                algo=str(row.get("algo") or ""),
                threshold=threshold,
                max_rows=max(0, int(args.max_rows_per_trace)),
            )
            if trace_stats.get("trace_exists"):
                trace_scanned += 1
            else:
                trace_missing += 1
            if args.progress_every > 0 and (ordinal == 1 or ordinal % int(args.progress_every) == 0):
                print(
                    f"[no-trade-scan] {ordinal}/{len(no_trade_rows)} "
                    f"trace_scanned={trace_scanned} trace_missing={trace_missing}",
                    file=sys.stderr,
                    flush=True,
                )
        diag, recommendation = diagnose(row, summary, trace_stats)
        by_algo[row.get("algo") or ""] += 1
        by_diag[diag] += 1
        by_algo_tf[(row.get("algo") or "", row.get("timeframe") or "")] += 1
        trace_rows = safe_int(trace_stats.get("trace_rows_scanned"))
        diagnostic_rows.append(
            {
                "run_slug": row.get("run_slug", ""),
                "machine": row.get("machine", ""),
                "asset": row.get("asset", ""),
                "timeframe": row.get("timeframe", ""),
                "algo": row.get("algo", ""),
                "preset": row.get("preset", ""),
                "seed": row.get("seed", ""),
                "total_return": row.get("total_return", ""),
                "sharpe_ratio": row.get("sharpe_ratio", ""),
                "trades_total": row.get("trades_total", ""),
                "action_non_hold_rate": summary.get("action_non_hold_rate", ""),
                "action_deadband_rate": summary.get("action_deadband_rate", ""),
                "action_abs_mean": summary.get("action_abs_mean", ""),
                "execution_entry_actions_seen": summary.get("execution_entry_actions_seen", ""),
                "execution_entry_orders_submitted": summary.get("execution_entry_orders_submitted", ""),
                "trace_scan_enabled": bool(args.scan_traces),
                "trace_file": trace_stats.get("trace_file", ""),
                "trace_rows_scanned": trace_rows if args.scan_traces else "",
                "trace_rows_limited": trace_stats.get("trace_rows_limited", ""),
                "trace_non_hold_rate": trace_stats.get("trace_non_hold_rate", ""),
                "trace_deadband_rate": trace_stats.get("trace_deadband_rate", ""),
                "trace_action_abs_mean": trace_stats.get("trace_action_abs_mean", ""),
                "trace_raw_min": trace_stats.get("trace_raw_min", ""),
                "trace_raw_max": trace_stats.get("trace_raw_max", ""),
                "continuous_action_threshold": threshold if str(row.get("algo") or "").lower() == "sac" else "",
                "no_trade_diagnosis": diag,
                "recommended_action": recommendation,
                "run_dir": row.get("run_dir", ""),
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_slug",
        "machine",
        "asset",
        "timeframe",
        "algo",
        "preset",
        "seed",
        "total_return",
        "sharpe_ratio",
        "trades_total",
        "action_non_hold_rate",
        "action_deadband_rate",
        "action_abs_mean",
        "execution_entry_actions_seen",
        "execution_entry_orders_submitted",
        "trace_scan_enabled",
        "trace_file",
        "trace_rows_scanned",
        "trace_rows_limited",
        "trace_non_hold_rate",
        "trace_deadband_rate",
        "trace_action_abs_mean",
        "trace_raw_min",
        "trace_raw_max",
        "continuous_action_threshold",
        "no_trade_diagnosis",
        "recommended_action",
        "run_dir",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in diagnostic_rows:
            writer.writerow({field: item.get(field, "") for field in fields})

    payload = {
        "schema_version": "project3_stage31_no_trade_diagnostic_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "index": str(INDEX),
        "total_runs": len(rows),
        "no_trade_runs": len(no_trade_rows),
        "trace_scan_enabled": bool(args.scan_traces),
        "max_rows_per_trace": int(args.max_rows_per_trace),
        "trace_files_scanned": trace_scanned,
        "trace_files_missing": trace_missing,
        "counts_by_algo": dict(sorted(by_algo.items())),
        "counts_by_diagnosis": dict(sorted(by_diag.items())),
        "counts_by_algo_timeframe": {
            f"{algo}:{tf}": count for (algo, tf), count in sorted(by_algo_tf.items())
        },
        "outputs": {"csv": str(OUT_CSV), "markdown": str(OUT_MD)},
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Stage 3.1 No-Trade Diagnostic Report",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Total Stage A runs: `{len(rows)}`",
        f"No-trade runs: `{len(no_trade_rows)}`",
        f"Trace scan enabled: `{bool(args.scan_traces)}`",
        f"Trace files scanned: `{trace_scanned}`",
        f"Trace files missing: `{trace_missing}`",
        f"Max rows per trace: `{int(args.max_rows_per_trace)}` (`0` means full trace)",
        "",
        "## Counts By Algorithm",
        "",
        "| Algorithm | No-trade runs |",
        "| --- | ---: |",
    ]
    for algo, count in sorted(by_algo.items()):
        lines.append(f"| {algo} | {count} |")
    lines += [
        "",
        "## Counts By Diagnosis",
        "",
        "| Diagnosis | Runs |",
        "| --- | ---: |",
    ]
    for diag, count in sorted(by_diag.items()):
        lines.append(f"| {diag} | {count} |")
    lines += [
        "",
        "## Top Required Actions",
        "",
        "- Future Stage 3/Stage B runs must emit action diagnostics, trade/profit progress telemetry, and return-trace evidence; no-trade summaries without action telemetry are insufficient.",
        "- Continuous SAC no-trade runs with `policy_deadband_collapse` require a registered threshold/action-scaling diagnostic lane. Any threshold change is a new trial, not a rescue of the original run.",
        "- Discrete PPO/DQN no-trade runs with `policy_hold_collapse` require reward/action-distribution diagnostics before rerun.",
        "- `non_hold_actions_but_no_trades` points to execution guards or broker/fill behavior, not just policy collapse.",
        "- A run with `trades_total == 0` remains a hard kill for promotion until a separately registered diagnostic experiment proves the issue is fixed.",
        "",
        "## Sample No-Trade Rows",
        "",
        "| Run | Algo | TF | Preset | Trace rows | Non-hold rate | Deadband rate | Diagnosis |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for item in diagnostic_rows[:40]:
        non_hold = item.get("trace_non_hold_rate", "")
        deadband = item.get("trace_deadband_rate", "")
        non_hold_s = "" if non_hold == "" else f"{safe_float(non_hold):.6f}"
        deadband_s = "" if deadband == "" else f"{safe_float(deadband):.6f}"
        lines.append(
            f"| `{item['run_slug']}` | {item['algo']} | {item['timeframe']} | {item['preset']} | "
            f"{item.get('trace_rows_scanned', '')} | {non_hold_s} | {deadband_s} | {item['no_trade_diagnosis']} |"
        )
    lines += [
        "",
        "## Output Files",
        "",
        f"- CSV: `{OUT_CSV}`",
        f"- JSON: `{OUT_JSON}`",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
