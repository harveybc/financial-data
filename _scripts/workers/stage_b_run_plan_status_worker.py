#!/usr/bin/env python3
"""
Status reader for Project 3 locked Stage B run-plan templates.

This worker does not launch training. It reads the locked run-plan manifest and
reports, for each planned config, whether the run is not started, running, done,
or anomalous. It is intentionally strict about no-trade progress: if a run has
reached 20% progress and still has zero trades, it is flagged immediately.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN_DIR = ROOT / "experiments/stage_b_validation/run_plan"
PLAN_JSON = PLAN_DIR / "stage_b_locked_run_plan.json"
OUT_JSON = PLAN_DIR / "stage_b_run_plan_status.json"
OUT_CSV = PLAN_DIR / "stage_b_run_plan_status.csv"
OUT_MD = PLAN_DIR / "stage_b_run_plan_status.md"
CLUSTER_LIVE_JSON = PLAN_DIR / "stage_b_cluster_live_status.json"
NO_TRADE_PROGRESS_THRESHOLD = 20.0
FINAL_TRADES_PER_YEAR_WARN = 312.0
FINAL_TRADES_PER_YEAR_HARD = 730.0
FINAL_ALWAYS_IN_MARKET_HARD = 0.95


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_timestamp(value: Any) -> dt.datetime | None:
    if value in (None, "", b""):
        return None
    text = str(value).strip().replace("T", " ")
    if text.endswith("Z"):
        text = text[:-1]
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ):
        try:
            return dt.datetime.strptime(text[: len(fmt)], fmt)
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def infer_trade_count(values: list[float], positions: list[float]) -> int:
    if values:
        nondecreasing = all(values[i] >= values[i - 1] for i in range(1, len(values)))
        # agent-multi normally reports a cumulative trade count in the trace.
        # If a plugin ever reports per-step trade counts instead, summing is
        # the safer interpretation.
        if nondecreasing and (values[-1] > 1.0 or sum(values) > values[-1] * 2.0):
            return max(0, int(round(values[-1])))
        return max(0, int(round(sum(values))))
    if positions:
        return sum(
            1 for i in range(1, len(positions))
            if abs(positions[i] - positions[i - 1]) > 1e-12
        )
    return 0


def analyze_return_trace(trace_file: pathlib.Path) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "final_trace_exists": trace_file.exists(),
        "final_trace_rows": 0,
        "final_trace_first_ts": "",
        "final_trace_last_ts": "",
        "final_trace_years": 0.0,
        "final_trades_total": 0,
        "final_trades_per_year": 0.0,
        "final_exposure_fraction": 0.0,
        "final_total_return": 0.0,
        "final_trace_warnings": [],
        "final_trace_anomalies": [],
    }
    if not trace_file.exists():
        return metrics

    trade_values: list[float] = []
    positions: list[float] = []
    timestamps: list[dt.datetime] = []
    first_equity: float | None = None
    last_equity: float | None = None
    row_count = 0
    with trace_file.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_count += 1
            parsed = parse_timestamp(row.get("timestamp"))
            if parsed is not None:
                timestamps.append(parsed)
            trade_raw = row.get("trades")
            if trade_raw not in (None, ""):
                trade_values.append(safe_float(trade_raw))
            pos = safe_float(row.get("position"), 0.0)
            positions.append(pos)
            equity_raw = row.get("equity")
            if equity_raw not in (None, ""):
                equity = safe_float(equity_raw)
                if first_equity is None:
                    first_equity = equity
                last_equity = equity

    metrics["final_trace_rows"] = row_count
    if timestamps:
        first_ts = timestamps[0]
        last_ts = timestamps[-1]
        metrics["final_trace_first_ts"] = first_ts.isoformat(sep=" ")
        metrics["final_trace_last_ts"] = last_ts.isoformat(sep=" ")
        years = max((last_ts - first_ts).total_seconds() / (86400.0 * 365.25), 1.0 / 365.25)
        metrics["final_trace_years"] = years
    else:
        years = 0.0
        metrics["final_trace_anomalies"].append("FINAL_TRACE_TIMESTAMP_MISSING")

    trades_total = infer_trade_count(trade_values, positions)
    metrics["final_trades_total"] = trades_total
    if years > 0:
        metrics["final_trades_per_year"] = trades_total / years
    if positions:
        metrics["final_exposure_fraction"] = (
            sum(1 for p in positions if abs(p) > 1e-12) / len(positions)
        )
    if first_equity not in (None, 0.0) and last_equity is not None:
        metrics["final_total_return"] = (last_equity - first_equity) / first_equity

    if row_count > 0 and trades_total <= 0:
        metrics["final_trace_anomalies"].append("FINAL_NO_TRADES")
    if metrics["final_trades_per_year"] > FINAL_TRADES_PER_YEAR_HARD:
        metrics["final_trace_anomalies"].append("FINAL_EXCESSIVE_TRADES_HARD")
    elif metrics["final_trades_per_year"] > FINAL_TRADES_PER_YEAR_WARN:
        metrics["final_trace_warnings"].append("FINAL_EXCESSIVE_TRADES_WARN")
    if (
        metrics["final_exposure_fraction"] >= FINAL_ALWAYS_IN_MARKET_HARD
        and metrics["final_total_return"] <= 0.0
    ):
        metrics["final_trace_anomalies"].append("FINAL_ALWAYS_IN_MARKET_LOSING")
    elif metrics["final_exposure_fraction"] >= FINAL_ALWAYS_IN_MARKET_HARD:
        metrics["final_trace_warnings"].append("FINAL_ALWAYS_IN_MARKET_WARN")
    return metrics


def is_expected_no_trade_baseline(entry: dict[str, Any]) -> bool:
    return (
        str(entry.get("role", "")).lower() == "baseline"
        and str(entry.get("baseline_name", "")).lower() == "no_trade"
    )


def progress_percent(progress: dict[str, Any], summary: dict[str, Any]) -> float:
    raw = progress.get(
        "progress_pct",
        progress.get(
            "progress_percent",
            progress.get("percent_complete", progress.get("progress", 0.0)),
        ),
    )
    pct = safe_float(raw)
    if pct <= 1.0 and progress.get("progress") not in (None, ""):
        pct *= 100.0
    if pct <= 0.0 and progress.get("num_timesteps") not in (None, ""):
        total = safe_float(progress.get("total_timesteps"))
        if total > 0:
            pct = (safe_float(progress.get("num_timesteps")) / total) * 100.0
    if summary:
        pct = max(pct, 100.0)
    return max(0.0, min(100.0, pct))


def load_active_variant_ids() -> set[str] | None:
    """
    Return active variant ids from the cluster live-status worker.

    None means the live-status file is unavailable, so callers should fall back
    to progress-file-only classification. An empty set is meaningful: the
    cluster was queried and reports no active work.
    """
    payload = load_json(CLUSTER_LIVE_JSON)
    if not payload:
        return None
    active = payload.get("active")
    if active is None:
        active = payload.get("active_rows")
    if not isinstance(active, list):
        return None
    out: set[str] = set()
    for item in active:
        if isinstance(item, dict):
            variant = item.get("variant_id") or item.get("variant") or item.get("run_id")
            if variant:
                out.add(str(variant))
    return out


def status_for_entry(entry: dict[str, Any], active_variant_ids: set[str] | None = None) -> dict[str, Any]:
    config_file = pathlib.Path(str(entry.get("config_file", "")))
    run_dir = pathlib.Path(str(entry.get("run_dir", "")))
    progress_file = pathlib.Path(str(entry.get("progress_file", "")))
    summary_file = run_dir / "summary.json"
    evidence_file = pathlib.Path(str(entry.get("expected_evidence_file", "")))
    trace_dir = pathlib.Path(str(entry.get("return_trace_dir", "")))
    trace_file = pathlib.Path(str(entry.get("return_trace_file", "")))

    config = load_json(config_file) if config_file.exists() else {}
    progress = load_json(progress_file) if progress_file.exists() else {}
    summary = load_json(summary_file) if summary_file.exists() else {}

    lock_ok = (
        bool(config)
        and config.get("_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED") is True
        and config.get("stage_c_access") == "DENIED"
        and bool(config.get("return_trace_dir"))
        and (
            config.get("pipeline_plugin") != "rl_pipeline"
            or bool(config.get("return_trace_file"))
        )
    )

    progress_pct = progress_percent(progress, summary)

    trades_total = safe_int(
        progress.get(
            "trades_total_cumulative",
            progress.get("trades_total", progress.get("trades", summary.get("trades_total", 0))),
        )
    )
    total_return = safe_float(
        progress.get("total_return", progress.get("profit", summary.get("total_return", 0.0)))
    )

    progress_status = str(progress.get("status", "")).strip().lower()
    if summary or evidence_file.exists():
        run_status = "DONE"
    elif progress_file.exists():
        if progress_status == "blocked_no_trade_early_abort":
            run_status = "ABORTED_NO_TRADE"
        elif progress_status in {"failed", "aborted", "subprocess_failed", "error"}:
            run_status = "FAILED"
        elif progress_status in {"complete", "training_complete", "subprocess_complete"}:
            run_status = "DONE"
        elif (
            active_variant_ids is not None
            and str(entry.get("variant_id", "")) not in active_variant_ids
            and progress_status in {"training", "running", "learning"}
        ):
            # A stale progress file should not keep the plan artificially active.
            # The cluster live-status worker is authoritative about currently
            # active remote/local executors.
            run_status = "FAILED_STALE_NOT_ACTIVE"
        else:
            run_status = "RUNNING"
    else:
        run_status = "NOT_STARTED_LOCKED"

    anomalies: list[str] = []
    warnings: list[str] = []
    if not config_file.exists():
        anomalies.append("CONFIG_MISSING")
    elif not lock_ok:
        anomalies.append("LOCK_OR_TRACE_CONTRACT_INVALID")
    if config.get("pipeline_plugin") == "rl_pipeline" and not config.get("return_trace_file"):
        anomalies.append("RL_PIPELINE_RETURN_TRACE_FILE_MISSING")
    expected_no_trade = is_expected_no_trade_baseline(entry)
    if (
        progress_pct >= NO_TRADE_PROGRESS_THRESHOLD
        and trades_total <= 0
        and run_status != "NOT_STARTED_LOCKED"
        and not expected_no_trade
    ):
        anomalies.append("NO_TRADES_AFTER_20_PERCENT")
    if evidence_file.exists() and not trace_dir.exists():
        anomalies.append("EVIDENCE_WITHOUT_TRACE_DIR")
    trace_metrics = analyze_return_trace(trace_file)
    if expected_no_trade and "FINAL_NO_TRADES" in trace_metrics["final_trace_anomalies"]:
        trace_metrics["final_trace_anomalies"] = [
            item for item in trace_metrics["final_trace_anomalies"]
            if item != "FINAL_NO_TRADES"
        ]
        trace_metrics["final_trace_warnings"].append("EXPECTED_NO_TRADE_BASELINE")
    anomalies.extend(trace_metrics["final_trace_anomalies"])
    warnings.extend(trace_metrics["final_trace_warnings"])

    return {
        "variant_id": entry.get("variant_id", ""),
        "role": entry.get("role", ""),
        "candidate_run_slug": entry.get("candidate_run_slug", ""),
        "source_run_slug": entry.get("source_run_slug", ""),
        "asset": entry.get("asset", ""),
        "timeframe": entry.get("timeframe", ""),
        "algo": entry.get("algo", ""),
        "preset": entry.get("preset", ""),
        "seed": entry.get("seed", ""),
        "cost_scenario": entry.get("cost_scenario", ""),
        "machine_hint": entry.get("machine_hint", ""),
        "run_status": run_status,
        "progress_pct": round(progress_pct, 4),
        "trades_total": trades_total,
        "total_return": total_return,
        "final_trace_exists": trace_metrics["final_trace_exists"],
        "final_trace_rows": trace_metrics["final_trace_rows"],
        "final_trace_first_ts": trace_metrics["final_trace_first_ts"],
        "final_trace_last_ts": trace_metrics["final_trace_last_ts"],
        "final_trace_years": trace_metrics["final_trace_years"],
        "final_trades_total": trace_metrics["final_trades_total"],
        "final_trades_per_year": trace_metrics["final_trades_per_year"],
        "final_exposure_fraction": trace_metrics["final_exposure_fraction"],
        "final_total_return": trace_metrics["final_total_return"],
        "config_file": str(config_file),
        "progress_file": str(progress_file),
        "summary_file": str(summary_file),
        "return_trace_file": str(trace_file),
        "return_trace_dir": str(trace_dir),
        "expected_evidence_file": str(evidence_file),
        "lock_ok": lock_ok,
        "anomalies": ";".join(anomalies),
        "warnings": ";".join(warnings),
    }


def build_status(plan_json: pathlib.Path = PLAN_JSON) -> dict[str, Any]:
    plan = load_json(plan_json)
    if not plan:
        raise RuntimeError(f"Missing or invalid Stage B run plan: {plan_json}")
    active_variant_ids = load_active_variant_ids()
    rows = [status_for_entry(entry, active_variant_ids) for entry in plan.get("configs", [])]
    status_counts: dict[str, int] = {}
    anomaly_counts: dict[str, int] = {}
    warning_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["run_status"]] = status_counts.get(row["run_status"], 0) + 1
        for anomaly in filter(None, str(row.get("anomalies", "")).split(";")):
            anomaly_counts[anomaly] = anomaly_counts.get(anomaly, 0) + 1
        for warning in filter(None, str(row.get("warnings", "")).split(";")):
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
    return {
        "schema_version": "project3_stage_b_run_plan_status_v1",
        "generated_at_utc": utc_now(),
        "plan_json": str(plan_json),
        "plan_id": plan.get("plan_id", ""),
        "total_configs": len(rows),
        "status_counts": status_counts,
        "anomaly_counts": anomaly_counts,
        "warning_counts": warning_counts,
        "no_trade_progress_threshold": NO_TRADE_PROGRESS_THRESHOLD,
        "final_trades_per_year_warn": FINAL_TRADES_PER_YEAR_WARN,
        "final_trades_per_year_hard": FINAL_TRADES_PER_YEAR_HARD,
        "final_always_in_market_hard": FINAL_ALWAYS_IN_MARKET_HARD,
        "cluster_live_status_json": str(CLUSTER_LIVE_JSON),
        "cluster_active_count": None if active_variant_ids is None else len(active_variant_ids),
        "rows": rows,
    }


def write_outputs(payload: dict[str, Any], out_dir: pathlib.Path = PLAN_DIR) -> dict[str, pathlib.Path]:
    out_json = out_dir / "stage_b_run_plan_status.json"
    out_csv = out_dir / "stage_b_run_plan_status.csv"
    out_md = out_dir / "stage_b_run_plan_status.md"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fields = [
        "variant_id", "role", "candidate_run_slug", "source_run_slug", "asset",
        "timeframe", "algo", "preset", "seed", "cost_scenario", "machine_hint",
        "run_status", "progress_pct", "trades_total", "total_return", "lock_ok",
        "anomalies", "warnings", "final_trace_exists", "final_trace_rows",
        "final_trades_total", "final_trades_per_year", "final_exposure_fraction",
        "final_total_return", "final_trace_first_ts", "final_trace_last_ts",
        "config_file", "progress_file", "summary_file", "return_trace_file",
        "return_trace_dir", "expected_evidence_file",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(payload["rows"])
    lines = [
        "# Project 3 Stage B Run Plan Status",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        f"Plan ID: `{payload['plan_id']}`",
        f"Total configs: `{payload['total_configs']}`",
        f"No-trade anomaly threshold: `{payload['no_trade_progress_threshold']}%`",
        "",
        "## Status Counts",
        "",
    ]
    for key, value in sorted(payload["status_counts"].items()):
        lines.append(f"- `{key}`: {value}")
    lines += ["", "## Anomaly Counts", ""]
    if payload["anomaly_counts"]:
        for key, value in sorted(payload["anomaly_counts"].items()):
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- None")
    lines += ["", "## Warning Counts", ""]
    if payload["warning_counts"]:
        for key, value in sorted(payload["warning_counts"].items()):
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- None")
    lines += [
        "",
        "## Final Trace Gates",
        "",
        f"- No-trade hard fail: `final_trades_total <= 0` when trace exists.",
        f"- Excessive-trade warning: `>{payload['final_trades_per_year_warn']}` trades/year.",
        f"- Excessive-trade hard fail: `>{payload['final_trades_per_year_hard']}` trades/year.",
        f"- Always-in-market hard fail when losing: exposure `>={payload['final_always_in_market_hard']}` and final return `<= 0`.",
    ]
    lines += [
        "",
        "## Running Or Anomalous Rows",
        "",
        "| Variant | Status | Progress % | Live Trades | Return | Final Trades/Yr | Exposure | Anomalies | Warnings |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    interesting = [
        row for row in payload["rows"]
        if row["run_status"] != "NOT_STARTED_LOCKED" or row["anomalies"]
    ]
    if interesting:
        for row in interesting[:100]:
            lines.append(
                f"| {row['variant_id']} | {row['run_status']} | {row['progress_pct']} | "
                f"{row['trades_total']} | {row['total_return']} | "
                f"{round(row['final_trades_per_year'], 4)} | "
                f"{round(row['final_exposure_fraction'], 4)} | "
                f"{row['anomalies']} | {row['warnings']} |"
            )
    else:
        lines.append("| None | - | - | - | - | - |")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": out_json, "csv": out_csv, "markdown": out_md}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-json", type=pathlib.Path, default=PLAN_JSON)
    parser.add_argument("--output-dir", type=pathlib.Path, default=None)
    args = parser.parse_args()
    payload = build_status(args.plan_json)
    paths = write_outputs(payload, args.output_dir or args.plan_json.parent)
    print(json.dumps({
        "ok": True,
        "total_configs": payload["total_configs"],
        "status_counts": payload["status_counts"],
        "anomaly_counts": payload["anomaly_counts"],
        "warning_counts": payload["warning_counts"],
        "csv": str(paths["csv"]),
        "markdown": str(paths["markdown"]),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
