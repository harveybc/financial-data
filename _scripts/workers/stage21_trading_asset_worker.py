from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
TARGET_TIMEFRAMES = ("5m", "15m", "1h", "4h")
TIMEFRAME_ALIASES = {
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
}
TIMESTAMP_COLUMNS = ("timestamp", "datetime", "date", "open_time", "time")
OHLC_COLUMNS = ("open", "high", "low", "close")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(machine: str, message: str) -> None:
    path = ROOT / "_logs" / machine / "stage21_trading_asset_worker.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def notify(event: str, title: str, message: str) -> None:
    script = ROOT / "_scripts" / "telegram_notify.py"
    if not script.exists():
        return
    import subprocess
    import sys

    try:
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--event",
                f"stage21:trading:{event}",
                "--title",
                title,
                "--message",
                message,
                "--min-interval-minutes",
                "20",
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
    except Exception:
        return


def discover_assets(roots: list[str]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for raw_root in roots:
        root = ROOT / raw_root
        if not root.exists():
            continue
        for asset_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            files = {tf: asset_dir / f"{tf}.parquet" for tf in TARGET_TIMEFRAMES}
            available = {tf: path for tf, path in files.items() if path.exists()}
            if not available:
                continue
            name = asset_dir.name.lower()
            if "perpetuals" in raw_root:
                name = f"{name}_perp"
            assets.append(
                {
                    "asset": name,
                    "source_root": raw_root,
                    "source_dir": rel(asset_dir),
                    "timeframes": {tf: rel(path) for tf, path in available.items()},
                }
            )
    return assets


def normalize_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    timestamp_col = next((col for col in TIMESTAMP_COLUMNS if col in out.columns), None)
    if timestamp_col is None:
        if isinstance(out.index, pd.DatetimeIndex):
            out = out.reset_index().rename(columns={out.index.name or "index": "timestamp"})
            timestamp_col = "timestamp"
        else:
            raise ValueError("no timestamp-like column found")
    out["timestamp"] = pd.to_datetime(out[timestamp_col], utc=True, errors="coerce")
    out = out.dropna(subset=["timestamp"]).sort_values("timestamp")
    out = out.drop_duplicates(subset=["timestamp"], keep="last")
    if timestamp_col != "timestamp" and timestamp_col in out.columns:
        out = out.drop(columns=[timestamp_col])
    cols = ["timestamp"] + [col for col in out.columns if col != "timestamp"]
    return out[cols]


def validate_ohlc(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    missing = [col for col in OHLC_COLUMNS if col not in df.columns]
    if missing:
        warnings.append(f"missing_ohlc_columns:{','.join(missing)}")
        return warnings
    for col in OHLC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    bad_high = (df["high"] < df[["open", "close"]].max(axis=1)).sum()
    bad_low = (df["low"] > df[["open", "close"]].min(axis=1)).sum()
    if int(bad_high):
        warnings.append(f"high_below_open_or_close:{int(bad_high)}")
    if int(bad_low):
        warnings.append(f"low_above_open_or_close:{int(bad_low)}")
    return warnings


def expected_step(tf: str) -> pd.Timedelta:
    return pd.Timedelta(TIMEFRAME_ALIASES[tf])


def validate_frequency(df: pd.DataFrame, tf: str) -> dict[str, Any]:
    if len(df) < 3:
        return {"status": "short", "unexpected_gaps": 0}
    deltas = df["timestamp"].diff().dropna()
    expected = expected_step(tf)
    unexpected = int((deltas > expected * 2).sum())
    return {
        "status": "ok",
        "expected_step_seconds": int(expected.total_seconds()),
        "unexpected_gaps": unexpected,
        "median_step_seconds": float(deltas.median().total_seconds()),
    }


def write_docs(out_dir: Path, asset: str, source_dir: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                f"# Stage 2.1 Trading Asset Data: {asset}",
                "",
                "Canonical multi-timeframe trading-asset OHLCV-aligned data generated for Phase 2 feature engineering.",
                "",
                f"Source: `{source_dir}`",
                "Timestamps are UTC and sorted. No interpolation is used.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "data_dictionary.md").write_text(
        "\n".join(
            [
                "# Data Dictionary",
                "",
                "- `timestamp`: UTC bar timestamp.",
                "- `open`, `high`, `low`, `close`: OHLC prices when available.",
                "- `volume`: traded base volume when available.",
                "- Additional exchange/vendor columns are preserved when present.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def process_asset(asset_info: dict[str, Any], machine: str) -> dict[str, Any]:
    asset = asset_info["asset"]
    out_dir = ROOT / "features" / "trading_asset_data" / asset
    write_docs(out_dir, asset, asset_info["source_dir"])
    tf_results: dict[str, Any] = {}
    for tf in TARGET_TIMEFRAMES:
        source_rel = asset_info["timeframes"].get(tf)
        if not source_rel:
            tf_results[tf] = {"status": "missing_source"}
            continue
        source = ROOT / source_rel
        try:
            df = normalize_timestamp(pd.read_parquet(source))
            warnings = validate_ohlc(df)
            freq = validate_frequency(df, tf)
            out_path = out_dir / f"{tf}.parquet"
            df.to_parquet(out_path, index=False)
            tf_results[tf] = {
                "status": "ok" if not warnings else "ok_with_warnings",
                "source": source_rel,
                "path": rel(out_path),
                "rows": int(len(df)),
                "start": df["timestamp"].min().isoformat() if len(df) else None,
                "end": df["timestamp"].max().isoformat() if len(df) else None,
                "warnings": warnings,
                "frequency": freq,
            }
        except Exception as exc:
            tf_results[tf] = {
                "status": "failed",
                "source": source_rel,
                "error": f"{type(exc).__name__}: {exc}",
            }
    provenance = {
        "generated_at": utc_now(),
        "stage": "Stage 2.1",
        "asset": asset,
        "source_dir": asset_info["source_dir"],
        "timeframes": tf_results,
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for item in tf_results.values() if str(item.get("status", "")).startswith("ok"))
    log(machine, f"asset={asset} ok_timeframes={ok}/{len(TARGET_TIMEFRAMES)}")
    return {"asset": asset, "source_dir": asset_info["source_dir"], "timeframes": tf_results}


def write_report(machine: str, universe: str, results: list[dict[str, Any]]) -> None:
    summary = {
        "generated_at": utc_now(),
        "stage": "Stage 2.1",
        "machine": machine,
        "universe": universe,
        "assets_total": len(results),
        "assets_complete": sum(
            all(str(tf.get("status", "")).startswith("ok") for tf in result["timeframes"].values())
            for result in results
        ),
        "timeframe_outputs": sum(
            1
            for result in results
            for tf in result["timeframes"].values()
            if str(tf.get("status", "")).startswith("ok")
        ),
        "results": results,
    }
    out_json = ROOT / "_metadata" / f"stage21_trading_assets_{machine}_{universe}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    out_md = ROOT / "_logs" / "supervisor_reports" / f"stage21_trading_assets_{machine}_{universe}.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Stage 2.1 Trading Asset Alignment - {machine} {universe}",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        f"- Assets total: {summary['assets_total']}",
        f"- Assets complete: {summary['assets_complete']}",
        f"- Timeframe outputs: {summary['timeframe_outputs']}",
        "",
        "| Asset | 5m | 15m | 1h | 4h |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        row = [result["asset"]]
        for tf in TARGET_TIMEFRAMES:
            row.append(result["timeframes"].get(tf, {}).get("status", "missing"))
        lines.append("| " + " | ".join(row) + " |")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--roots", nargs="+", required=True)
    args = parser.parse_args()

    log(args.machine, f"START stage21 trading universe={args.universe} roots={args.roots}")
    notify(
        f"{args.machine}:{args.universe}:start",
        f"Project 3 Stage 2.1 {args.machine} started",
        f"machine: {args.machine}\nstage: Stage 2.1\ncurrent_task: trading asset alignment\nexpected_deliverable: features/trading_asset_data; _metadata/stage21_trading_assets_{args.machine}_{args.universe}.json",
    )
    assets = discover_assets(args.roots)
    results = [process_asset(asset, args.machine) for asset in assets]
    write_report(args.machine, args.universe, results)
    log(args.machine, f"DONE stage21 trading universe={args.universe} assets={len(results)}")
    notify(
        f"{args.machine}:{args.universe}:finish",
        f"Project 3 Stage 2.1 {args.machine} finished",
        f"machine: {args.machine}\nstage: Stage 2.1\nstatus: finished\ndeliverable_path: _metadata/stage21_trading_assets_{args.machine}_{args.universe}.json\nassets: {len(results)}",
    )


if __name__ == "__main__":
    main()
