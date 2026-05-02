from __future__ import annotations

import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
CQ_ROOT = ROOT / "alternative_data" / "cryptoquant"
OUT_JSON = ROOT / "_metadata" / "stage15_cryptoquant_value_probe.json"
OUT_MD = ROOT / "_logs" / "supervisor_reports" / "stage15_cryptoquant_value_probe.md"
BINANCE_URL = "https://api.binance.com/api/v3/klines"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def fetch_binance_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    end_ms = int(pd.Timestamp(end, tz="UTC").timestamp() * 1000)
    params = {
        "symbol": symbol.upper(),
        "interval": "1d",
        "startTime": str(start_ms),
        "endTime": str(end_ms),
        "limit": "1000",
    }
    url = BINANCE_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "project3-cryptoquant-value-probe/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        rows = json.loads(response.read().decode("utf-8", errors="replace"))
    cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
        "ignore",
    ]
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.floor("D")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    for horizon in (1, 3, 7):
        df[f"return_fwd_{horizon}d"] = np.log(df["close"].shift(-horizon) / df["close"])
    return df[["date", "close", "return_fwd_1d", "return_fwd_3d", "return_fwd_7d"]]


def numeric_metric_columns(df: pd.DataFrame) -> list[str]:
    ignored = {
        "provider",
        "endpoint",
        "metric_slug",
        "date",
        "param_exchange",
        "param_window",
        "param_miner",
        "param_token",
    }
    cols: list[str] = []
    for col in df.columns:
        if col in ignored or col.startswith("param_"):
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() >= 30 and series.nunique(dropna=True) > 5:
            cols.append(col)
    return cols


def corr_or_none(left: pd.Series, right: pd.Series, method: str) -> float | None:
    frame = pd.DataFrame({"x": left, "y": right}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 30 or frame["x"].nunique() < 5 or frame["y"].nunique() < 5:
        return None
    value = frame["x"].corr(frame["y"], method=method)
    if value is None or math.isnan(float(value)):
        return None
    return float(value)


def analyze_metric_file(path: Path, prices: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    df = pd.read_parquet(path)
    if "date" not in df.columns:
        return []
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.floor("D")
    df = df.dropna(subset=["date"]).sort_values("date").drop_duplicates(["date", "metric_slug"], keep="last")
    if df.empty:
        return []
    slug = str(df["metric_slug"].iloc[0]) if "metric_slug" in df.columns else path.stem
    asset_targets: list[str] = []
    if slug.startswith("btc_"):
        asset_targets.append("btcusdt")
    if slug.startswith("eth_"):
        asset_targets.append("ethusdt")
    if slug.startswith("stablecoin_"):
        asset_targets.extend(["btcusdt", "ethusdt"])
    if not asset_targets:
        return []

    metrics = numeric_metric_columns(df)
    results: list[dict[str, Any]] = []
    for asset in asset_targets:
        px = prices.get(asset)
        if px is None or px.empty:
            continue
        merged = df.merge(px, on="date", how="inner")
        if len(merged) < 30:
            continue
        for col in metrics:
            level = pd.to_numeric(merged[col], errors="coerce")
            diff = level.diff()
            zscore = (level - level.rolling(30, min_periods=10).mean()) / level.rolling(30, min_periods=10).std()
            transforms = {"level": level, "diff": diff, "zscore": zscore}
            for transform_name, series in transforms.items():
                for horizon in (1, 3, 7):
                    target = merged[f"return_fwd_{horizon}d"]
                    spearman = corr_or_none(series, target, "spearman")
                    pearson = corr_or_none(series, target, "pearson")
                    if spearman is None and pearson is None:
                        continue
                    results.append(
                        {
                            "asset": asset,
                            "metric_slug": slug,
                            "metric_column": col,
                            "transform": transform_name,
                            "horizon_days": horizon,
                            "overlap_days": int(pd.DataFrame({"x": series, "y": target}).dropna().shape[0]),
                            "spearman_ic": spearman,
                            "pearson_ic": pearson,
                            "path": rel(path),
                        }
                    )
    return results


def summarize_coverage() -> dict[str, Any]:
    files = sorted(CQ_ROOT.rglob("*.parquet"))
    ranges = []
    for path in files:
        df = pd.read_parquet(path, columns=None)
        row: dict[str, Any] = {"path": rel(path), "rows": int(len(df)), "columns": int(len(df.columns))}
        if "date" in df.columns and len(df):
            dates = pd.to_datetime(df["date"], utc=True, errors="coerce").dropna()
            if len(dates):
                row["start"] = str(dates.min())
                row["end"] = str(dates.max())
        ranges.append(row)
    starts = [row["start"] for row in ranges if row.get("start")]
    ends = [row["end"] for row in ranges if row.get("end")]
    return {
        "files": len(files),
        "rows_total": sum(row["rows"] for row in ranges),
        "global_start": min(starts) if starts else None,
        "global_end": max(ends) if ends else None,
        "ranges": ranges,
    }


def recommendation(coverage: dict[str, Any], best_rows: list[dict[str, Any]]) -> dict[str, Any]:
    days = 0
    if coverage.get("global_start") and coverage.get("global_end"):
        days = int((pd.Timestamp(coverage["global_end"]) - pd.Timestamp(coverage["global_start"])).days) + 1
    best_abs_ic = max((abs(item.get("spearman_ic") or 0.0) for item in best_rows), default=0.0)
    if days < 365:
        decision = "cancel_unless_historical_export_is_enabled"
        reason = "API coverage is recent-window only, so it cannot support Project 3 historical RL backtests."
    elif best_abs_ic < 0.05:
        decision = "cancel_if_no_stage_a_lift"
        reason = "Historical coverage would be usable, but the quick lead-lag probe found weak signal."
    else:
        decision = "keep_for_stage_a_ablation"
        reason = "Coverage and exploratory signal are sufficient to justify a formal Stage A ablation."
    return {
        "decision": decision,
        "reason": reason,
        "coverage_days": days,
        "best_abs_spearman_ic": best_abs_ic,
    }


def main() -> int:
    coverage = summarize_coverage()
    start = str(pd.Timestamp(coverage["global_start"]).date()) if coverage.get("global_start") else "2026-01-01"
    end = str((pd.Timestamp(coverage["global_end"]) + pd.Timedelta(days=8)).date()) if coverage.get("global_end") else "2026-05-10"
    time.sleep(0.2)
    prices = {
        "btcusdt": fetch_binance_daily("BTCUSDT", start, end),
        "ethusdt": fetch_binance_daily("ETHUSDT", start, end),
    }
    results: list[dict[str, Any]] = []
    for path in sorted(CQ_ROOT.rglob("*.parquet")):
        results.extend(analyze_metric_file(path, prices))
    ranked = sorted(results, key=lambda item: abs(item.get("spearman_ic") or 0.0), reverse=True)
    best = ranked[:30]
    rec = recommendation(coverage, best)
    payload = {
        "generated_at": utc_now(),
        "stage": "Stage 1.5 subscription value triage",
        "provider": "CryptoQuant",
        "coverage": {key: value for key, value in coverage.items() if key != "ranges"},
        "price_sources": {
            asset: {
                "rows": int(len(df)),
                "start": str(df["date"].min()) if len(df) else None,
                "end": str(df["date"].max()) if len(df) else None,
            }
            for asset, df in prices.items()
        },
        "correlations_tested": len(results),
        "top_lead_lag_results": best,
        "recommendation": rec,
        "limitations": [
            "This is a subscription-value triage, not a Phase 3 model-selection result.",
            "CryptoQuant data currently overlaps 2026 only, while the Project 3 historical corpus ends at 2025-12-31.",
            "Small samples can overstate correlations; use only to decide whether historical access is worth pursuing.",
        ],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# CryptoQuant Subscription Value Probe",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Decision",
        "",
        f"- Recommendation: `{rec['decision']}`",
        f"- Reason: {rec['reason']}",
        f"- Coverage days: {rec['coverage_days']}",
        f"- Best absolute Spearman IC in quick probe: {rec['best_abs_spearman_ic']:.4f}",
        "",
        "## Coverage",
        "",
        f"- Files: {coverage['files']}",
        f"- Rows: {coverage['rows_total']}",
        f"- Global start: {coverage['global_start']}",
        f"- Global end: {coverage['global_end']}",
        "",
        "## Top Exploratory Lead/Lag Results",
        "",
        "| Asset | Metric | Column | Transform | Horizon | Days | Spearman IC | Path |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for item in best[:12]:
        lines.append(
            "| "
            + " | ".join(
                [
                    item["asset"],
                    item["metric_slug"],
                    item["metric_column"],
                    item["transform"],
                    str(item["horizon_days"]),
                    str(item["overlap_days"]),
                    f"{(item.get('spearman_ic') or 0.0):.4f}",
                    f"`{item['path']}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The current Professional API data is useful as recent/live context, but not enough for Project 3 historical RL experiments.",
            "- Keep only if CryptoQuant can provide historical export/API coverage back through the training and validation windows.",
            "- Otherwise cancel after preserving the acquired parquet files and documentation.",
        ]
    )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"recommendation": rec, "correlations_tested": len(results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
