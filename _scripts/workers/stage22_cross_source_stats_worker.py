from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
TARGET_TIMEFRAMES = ("5m", "15m", "1h", "4h")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(machine: str, message: str) -> None:
    path = ROOT / "_logs" / machine / "stage22_cross_source_stats_worker.log"
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
                f"stage22:cross_stats:{event}",
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


def sanitize_name(name: str) -> str:
    return name.lower().replace(" ", "_").replace("/", "_")


def compute_stats(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        raise ValueError("missing timestamp")
    out = pd.DataFrame({"timestamp": pd.to_datetime(df["timestamp"], utc=True, errors="coerce")})
    numeric_cols = []
    for col in df.columns:
        if col == "timestamp":
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        if values.notna().sum() < 3:
            continue
        numeric_cols.append(col)
        name = sanitize_name(col)
        out[f"{name}_value"] = values.astype("float32")
        out[f"{name}_diff_1"] = values.diff().astype("float32")
        if (values > 0).sum() >= 3:
            out[f"{name}_pct_change_1"] = values.pct_change().replace([np.inf, -np.inf], np.nan).astype("float32")
        for window in (20, 60):
            mean = values.rolling(window).mean()
            std = values.rolling(window).std()
            out[f"{name}_zscore_{window}"] = ((values - mean) / std).replace([np.inf, -np.inf], np.nan).astype("float32")
            out[f"{name}_roll_mean_{window}"] = mean.astype("float32")
            out[f"{name}_roll_std_{window}"] = std.astype("float32")
    if not numeric_cols:
        raise ValueError("no numeric columns")
    validation = {
        "rows": int(len(out)),
        "source_numeric_columns": numeric_cols,
        "feature_columns": int(len(out.columns) - 1),
        "all_nan_columns": [col for col in out.columns if col != "timestamp" and out[col].isna().all()][:50],
    }
    return out, validation


def process_file(path: Path, tf: str, machine: str) -> dict[str, Any]:
    slug = path.stem
    out_dir = ROOT / "features" / "cross_source_statistical" / tf
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.parquet"
    try:
        features, validation = compute_stats(path)
        features.to_parquet(out_path, index=False)
        result = {
            "status": "ok",
            "timeframe": tf,
            "source": rel(path),
            "path": rel(out_path),
            "validation": validation,
        }
    except Exception as exc:
        result = {
            "status": "failed",
            "timeframe": tf,
            "source": rel(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    log(machine, f"tf={tf} source={rel(path)} status={result['status']}")
    return result


def write_docs() -> None:
    root = ROOT / "features" / "cross_source_statistical"
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Stage 2.2 Cross-Source Statistical Features",
                "",
                "Point-in-time statistical transforms over Stage 2.1 cross-source aligned inputs.",
                "",
                "Features include current value, first difference, optional percent change, rolling z-scores, rolling means, and rolling standard deviations.",
                "These are observation-space state descriptors, not predictive labels.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "data_dictionary.md").write_text(
        "\n".join(
            [
                "# Data Dictionary",
                "",
                "- `*_value`: forward-filled current source value.",
                "- `*_diff_1`: one-bar first difference.",
                "- `*_pct_change_1`: one-bar percent change where source values are positive.",
                "- `*_zscore_20`, `*_zscore_60`: rolling z-scores.",
                "- `*_roll_mean_*`, `*_roll_std_*`: rolling location and scale.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_report(machine: str, results: list[dict[str, Any]]) -> None:
    summary = {
        "generated_at": utc_now(),
        "stage": "Stage 2.2",
        "machine": machine,
        "jobs_total": len(results),
        "jobs_ok": sum(item["status"] == "ok" for item in results),
        "jobs_failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
    out_json = ROOT / "_metadata" / f"stage22_cross_source_stats_{machine}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    out_md = ROOT / "_logs" / "supervisor_reports" / f"stage22_cross_source_stats_{machine}.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                f"# Stage 2.2 Cross-Source Statistical Features - {machine}",
                "",
                f"Generated: {summary['generated_at']}",
                "",
                f"- Jobs total: {summary['jobs_total']}",
                f"- Jobs ok: {summary['jobs_ok']}",
                f"- Jobs failed: {summary['jobs_failed']}",
                "- Output root: `features/cross_source_statistical/`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", default="gamma")
    parser.add_argument("--timeframes", nargs="*", default=list(TARGET_TIMEFRAMES))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    write_docs()
    jobs: list[tuple[Path, str]] = []
    for tf in args.timeframes:
        tf_dir = ROOT / "features" / "cross_source_features" / tf
        if tf_dir.exists():
            jobs.extend((path, tf) for path in sorted(tf_dir.glob("*.parquet")))
    if args.limit:
        jobs = jobs[: args.limit]
    log(args.machine, f"START stage22 cross-source stats jobs={len(jobs)}")
    notify(
        f"{args.machine}:start",
        f"Project 3 Stage 2.2 {args.machine} cross-source stats started",
        f"machine: {args.machine}\nstage: Stage 2.2\ncurrent_task: cross-source statistical features\njobs: {len(jobs)}",
    )
    results = [process_file(path, tf, args.machine) for path, tf in jobs]
    write_report(args.machine, results)
    log(args.machine, f"DONE stage22 cross-source stats jobs={len(jobs)}")
    notify(
        f"{args.machine}:finish",
        f"Project 3 Stage 2.2 {args.machine} cross-source stats finished",
        f"machine: {args.machine}\nstage: Stage 2.2\nstatus: finished\ndeliverable_path: _metadata/stage22_cross_source_stats_{args.machine}.json\njobs: {len(jobs)}",
    )


if __name__ == "__main__":
    main()
