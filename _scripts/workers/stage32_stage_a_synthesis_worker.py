#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path


ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
RUN_ROOT = ROOT / "experiments" / "stage_a_screening" / "runs"
OUT_ROOT = ROOT / "experiments" / "stage_a_screening"

PRESET_FAMILIES = {
    "baseline_12": ["baseline"],
    "tech_full": ["technical"],
    "tech_stat": ["technical", "statistical"],
    "tech_stat_decomp": ["technical", "statistical", "wavelet", "emd", "fracdiff"],
    "learned_lstm": ["learned_lstm"],
    "learned_cnn": ["learned_cnn"],
    "sota_low_cost": [
        "technical",
        "statistical",
        "sota_intrabar_realized",
        "sota_hmm_regime",
        "sota_pair_spreads",
        "sota_funding_term_structure",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def split_asset(asset_field: str) -> tuple[str, str]:
    if "_" not in asset_field:
        return asset_field, ""
    asset, timeframe = asset_field.rsplit("_", 1)
    return asset, timeframe


def algo_from_config(config: dict) -> str:
    plugin = str(config.get("agent_plugin", "")).replace("_agent", "")
    return plugin or "unknown"


@lru_cache(maxsize=None)
def buy_hold_return(input_csv: str) -> float | None:
    path = Path(input_csv)
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            header = handle.readline().decode("utf-8", "ignore").strip()
            first_line = handle.readline().decode("utf-8", "ignore").strip()
            if not header or not first_line:
                return None
            columns = next(csv.reader([header]))
            try:
                close_idx = columns.index("CLOSE")
            except ValueError:
                return None
            handle.seek(0, os.SEEK_END)
            pos = handle.tell()
            tail = b""
            while pos > 0:
                step = min(8192, pos)
                pos -= step
                handle.seek(pos)
                tail = handle.read(step) + tail
                lines = [line for line in tail.splitlines() if line.strip()]
                if len(lines) >= 2:
                    break
            last_line = lines[-1].decode("utf-8", "ignore").strip() if lines else ""
        first_row = next(csv.reader([first_line]))
        last_row = next(csv.reader([last_line]))
        first = safe_float(first_row[close_idx] if close_idx < len(first_row) else None)
        last = safe_float(last_row[close_idx] if close_idx < len(last_row) else None)
    except Exception:
        return None
    if first is None or last is None or first == 0:
        return None
    return (last / first) - 1.0


def collect_rows() -> list[dict]:
    rows = []
    for summary_path in sorted(RUN_ROOT.glob("*/*/summary.json")):
        run_dir = summary_path.parent
        machine = run_dir.parent.name
        config = read_json(run_dir / "config.json")
        summary = read_json(summary_path)
        asset, timeframe = split_asset(str(config.get("asset", "")))
        algo = algo_from_config(config)
        preset = str(config.get("features_preset", "unknown"))
        seed = config.get("eval_seed", config.get("train_seed", ""))
        total_return = safe_float(summary.get("total_return"))
        max_drawdown = safe_float(summary.get("max_drawdown_pct"))
        sharpe = safe_float(summary.get("sharpe_ratio"))
        sqn = safe_float(summary.get("sqn"))
        trades = int(summary.get("trades_total") or 0)
        bh = buy_hold_return(str(config.get("input_data_file", "")))
        no_trade_delta = total_return if total_return is not None else None
        buy_hold_delta = total_return - bh if total_return is not None and bh is not None else None
        pessimistic_cost_return = None
        if total_return is not None:
            notional_round_trip_cost = 0.0002 if asset.endswith("usdt") else 0.00005
            pessimistic_cost_return = total_return - min(0.50, trades * notional_round_trip_cost / 1000.0)
        rows.append(
            {
                "machine": machine,
                "run_dir": str(run_dir),
                "run_slug": run_dir.name,
                "asset": asset,
                "timeframe": timeframe,
                "algo": algo,
                "preset": preset,
                "feature_families": ",".join(PRESET_FAMILIES.get(preset, [preset])),
                "seed": seed,
                "device": config.get("device", ""),
                "timesteps": config.get("total_timesteps", ""),
                "commission": config.get("commission", ""),
                "slippage": config.get("slippage", ""),
                "total_return": total_return,
                "pessimistic_cost_return": pessimistic_cost_return,
                "buy_hold_return": bh,
                "delta_vs_no_trade": no_trade_delta,
                "delta_vs_buy_hold": buy_hold_delta,
                "max_drawdown_pct": max_drawdown,
                "sharpe_ratio": sharpe,
                "sqn": sqn,
                "trades_total": trades,
                "trades_won": summary.get("trades_won", ""),
                "trades_lost": summary.get("trades_lost", ""),
                "avg_trade_pnl": summary.get("avg_trade_pnl", ""),
                "episode_length": summary.get("episode_length", ""),
                "promotion_blocked_by_hardening": True,
                "promotion_blocker_reason": "Requires leakage audit, availability audit, DSR/PBO diagnostics, and explicit cost-sensitivity rerun before Stage B promotion.",
            }
        )
    return rows


def write_index(rows: list[dict]) -> Path:
    out = OUT_ROOT / "index.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "machine",
        "run_slug",
        "asset",
        "timeframe",
        "algo",
        "preset",
        "feature_families",
        "seed",
        "device",
        "timesteps",
        "commission",
        "slippage",
        "total_return",
        "pessimistic_cost_return",
        "buy_hold_return",
        "delta_vs_no_trade",
        "delta_vs_buy_hold",
        "max_drawdown_pct",
        "sharpe_ratio",
        "sqn",
        "trades_total",
        "trades_won",
        "trades_lost",
        "avg_trade_pnl",
        "episode_length",
        "promotion_blocked_by_hardening",
        "promotion_blocker_reason",
        "run_dir",
    ]
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return out


def mean(values: list[float]) -> float | None:
    values = [x for x in values if x is not None]
    if not values:
        return None
    return statistics.fmean(values)


def fmt(value, digits: int = 4) -> str:
    num = safe_float(value)
    if num is None:
        return "-"
    return f"{num:.{digits}f}"


def grouped(rows: list[dict], key: str) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key, ""))].append(row)
    out = []
    for name, items in buckets.items():
        out.append(
            {
                key: name,
                "runs": len(items),
                "mean_return": mean([safe_float(x.get("total_return")) for x in items]),
                "mean_sharpe": mean([safe_float(x.get("sharpe_ratio")) for x in items]),
                "mean_drawdown": mean([safe_float(x.get("max_drawdown_pct")) for x in items]),
                "mean_trades": mean([safe_float(x.get("trades_total")) for x in items]),
                "positive_return_runs": sum(1 for x in items if (safe_float(x.get("total_return")) or 0) > 0),
            }
        )
    return sorted(out, key=lambda x: (x["mean_return"] is None, -(x["mean_return"] or -999)))


def verdict(row: dict) -> str:
    ret = safe_float(row.get("total_return")) or 0.0
    trades = int(row.get("trades_total") or 0)
    sharpe = safe_float(row.get("sharpe_ratio"))
    if trades == 0:
        return "KILL_no_trades"
    if ret <= 0:
        return "KILL_non_positive_return"
    if sharpe is not None and sharpe < 0:
        return "KILL_negative_sharpe"
    return "WATCH_preliminary_blocked_until_hardening"


def write_summary(rows: list[dict]) -> Path:
    out = OUT_ROOT / "stage_a_summary.md"
    top = sorted(rows, key=lambda r: (safe_float(r.get("total_return")) or -999), reverse=True)[:20]
    top_sharpe = sorted(rows, key=lambda r: (safe_float(r.get("sharpe_ratio")) or -999), reverse=True)[:20]
    verdict_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        verdict_counts[verdict(row)] += 1

    lines = [
        "# Stage A Screening Summary",
        "",
        f"Generated: {utc_now()}",
        "",
        "This is a preliminary Stage A synthesis. Per the adopted SOTA hardening gates, no configuration is promoted to Stage B until leakage, availability, DSR/PBO, baseline, and cost-sensitivity checks pass.",
        "",
        "## Run Counts",
        "",
        f"- Total summary files: {len(rows)}",
        f"- Machines: {', '.join(sorted({r['machine'] for r in rows}))}",
        f"- Assets: {', '.join(sorted({r['asset'] for r in rows}))}",
        f"- Feature presets: {', '.join(sorted({r['preset'] for r in rows}))}",
        "",
        "## Verdict Counts",
        "",
        "| Verdict | Runs |",
        "| --- | ---: |",
    ]
    for name, count in sorted(verdict_counts.items()):
        lines.append(f"| {name} | {count} |")

    lines += [
        "",
        "## Top 20 By Total Return",
        "",
        "| Rank | Run | Asset | TF | Algo | Preset | Return | Sharpe | Drawdown % | Trades | Verdict |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for idx, row in enumerate(top, start=1):
        lines.append(
            f"| {idx} | `{row['run_slug']}` | {row['asset']} | {row['timeframe']} | {row['algo']} | {row['preset']} | "
            f"{fmt(row['total_return'])} | {fmt(row['sharpe_ratio'])} | {fmt(row['max_drawdown_pct'], 2)} | {row['trades_total']} | {verdict(row)} |"
        )

    lines += [
        "",
        "## Top 20 By Sharpe",
        "",
        "| Rank | Run | Asset | TF | Algo | Preset | Return | Sharpe | Drawdown % | Trades | Verdict |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for idx, row in enumerate(top_sharpe, start=1):
        lines.append(
            f"| {idx} | `{row['run_slug']}` | {row['asset']} | {row['timeframe']} | {row['algo']} | {row['preset']} | "
            f"{fmt(row['total_return'])} | {fmt(row['sharpe_ratio'])} | {fmt(row['max_drawdown_pct'], 2)} | {row['trades_total']} | {verdict(row)} |"
        )

    for key, title in [
        ("preset", "Feature Preset Ranking"),
        ("algo", "Algorithm Ranking"),
        ("asset", "Asset Ranking"),
        ("machine", "Machine Contribution"),
    ]:
        lines += [
            "",
            f"## {title}",
            "",
            f"| {key.title()} | Runs | Mean Return | Mean Sharpe | Mean Drawdown % | Positive Runs |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for item in grouped(rows, key):
            lines.append(
                f"| {item[key]} | {item['runs']} | {fmt(item['mean_return'])} | {fmt(item['mean_sharpe'])} | "
                f"{fmt(item['mean_drawdown'], 2)} | {item['positive_return_runs']} |"
            )

    lines += [
        "",
        "## Promotion Blockers",
        "",
        "- All candidates are currently blocked from Stage B promotion by the hardening gate.",
        "- Required before promotion: leakage audit, availability/vintage audit, DSR/PBO-style overfit diagnostics, net-cost sensitivity, and baseline/null comparisons.",
        "- Several high-return runs still show negative Sharpe or low trade counts; those must not be treated as validated edge.",
        "",
        "## Deliverables",
        "",
        "- `experiments/stage_a_screening/index.csv`",
        "- `experiments/stage_a_screening/stage_a_summary.md`",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_metadata(rows: list[dict]) -> None:
    payload = {
        "generated_at": utc_now(),
        "stage": "3.2",
        "source_stage": "3.1_stage_a",
        "runs": len(rows),
        "outputs": [
            str(OUT_ROOT / "index.csv"),
            str(OUT_ROOT / "stage_a_summary.md"),
        ],
        "status": "preliminary_blocked_until_hardening",
    }
    path = ROOT / "_metadata" / "stage32_stage_a_synthesis.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    rows = collect_rows()
    write_index(rows)
    write_summary(rows)
    write_metadata(rows)
    print(json.dumps({"ok": True, "runs": len(rows), "outputs": [str(OUT_ROOT / "index.csv"), str(OUT_ROOT / "stage_a_summary.md")]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
