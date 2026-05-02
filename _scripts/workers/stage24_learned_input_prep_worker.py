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
FEATURE_FILES = (
    "technical",
    "statistical",
    "wavelet",
    "hilbert",
    "multitaper",
    "emd",
    "fracdiff",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(machine: str, message: str) -> None:
    path = ROOT / "_logs" / machine / "stage24_learned_input_prep_worker.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def read_base(asset: str, tf: str) -> pd.DataFrame:
    path = ROOT / "features" / "trading_asset_data" / asset / f"{tf}.parquet"
    if not path.exists():
        raise FileNotFoundError(rel(path))
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"{rel(path)} missing timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    keep = ["timestamp"] + [col for col in ("open", "high", "low", "close", "volume") if col in df.columns]
    out = df[keep].dropna(subset=["timestamp"]).sort_values("timestamp")
    for col in out.columns:
        if col != "timestamp":
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def read_feature(asset: str, tf: str, name: str) -> pd.DataFrame | None:
    path = ROOT / "features" / "trading_asset_features" / asset / tf / f"{name}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        return None
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    rename = {col: f"{name}__{col}" for col in df.columns if col != "timestamp"}
    df = df.rename(columns=rename).dropna(subset=["timestamp"]).sort_values("timestamp")
    for col in df.columns:
        if col != "timestamp":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def combine_features(asset: str, tf: str) -> pd.DataFrame:
    out = read_base(asset, tf)
    for name in FEATURE_FILES:
        df = read_feature(asset, tf, name)
        if df is None:
            continue
        out = out.merge(df, on="timestamp", how="left", validate="one_to_one")
    numeric_cols = [col for col in out.columns if col != "timestamp"]
    out[numeric_cols] = out[numeric_cols].replace([np.inf, -np.inf], np.nan)
    out[numeric_cols] = out[numeric_cols].ffill().bfill()
    usable_cols = [col for col in numeric_cols if out[col].notna().sum() >= 100 and out[col].std(skipna=True) > 0]
    if len(usable_cols) < 8:
        raise ValueError(f"too few usable columns after merge: {len(usable_cols)}")
    return out[["timestamp", *usable_cols]]


def split_and_normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    train_mask = df["timestamp"] < pd.Timestamp("2024-01-01", tz="UTC")
    val_mask = (df["timestamp"] >= pd.Timestamp("2024-01-01", tz="UTC")) & (
        df["timestamp"] < pd.Timestamp("2025-01-01", tz="UTC")
    )
    test_mask = df["timestamp"] >= pd.Timestamp("2025-01-01", tz="UTC")
    train = df.loc[train_mask].copy()
    val = df.loc[val_mask].copy()
    test = df.loc[test_mask].copy()
    if len(train) < 500 or len(val) < 100 or len(test) < 100:
        raise ValueError(f"insufficient split rows train={len(train)} val={len(val)} test={len(test)}")

    cols = [col for col in df.columns if col != "timestamp"]
    means = train[cols].mean()
    stds = train[cols].std().replace(0, np.nan)
    stds = stds.fillna(1.0)

    def normalize(part: pd.DataFrame) -> pd.DataFrame:
        out = part.copy()
        out[cols] = ((out[cols] - means) / stds).clip(-10, 10)
        return out

    full = normalize(df)
    metadata = {
        "feature_columns": cols,
        "column_count": len(cols),
        "split_rows": {"train": len(train), "validation": len(val), "test": len(test), "full": len(df)},
        "normalization": "StandardScaler equivalent fit on training split only; values clipped to [-10, 10]",
        "train_start": str(train["timestamp"].min()),
        "train_end": str(train["timestamp"].max()),
        "validation_start": str(val["timestamp"].min()),
        "validation_end": str(val["timestamp"].max()),
        "test_start": str(test["timestamp"].min()),
        "test_end": str(test["timestamp"].max()),
    }
    return normalize(train), normalize(val), normalize(test), full, metadata


def write_feature_extractor_config(asset: str, tf: str, out_dir: Path, metadata: dict[str, Any]) -> Path:
    config = {
        "asset": asset,
        "timeframe": tf,
        "stage": "2.4",
        "feature_extractor_repo": "/home/harveybc/Documents/GitHub/feature-extractor",
        "required_pythonpath": "/home/harveybc/Documents/GitHub/feature-extractor:/home/harveybc/Documents/GitHub/feature-extractor/app",
        "x_train_file": rel(out_dir / "train.csv"),
        "y_train_file": rel(out_dir / "train.csv"),
        "x_validation_file": rel(out_dir / "validation.csv"),
        "y_validation_file": rel(out_dir / "validation.csv"),
        "x_test_file": rel(out_dir / "test.csv"),
        "y_test_file": rel(out_dir / "test.csv"),
        "headers": True,
        "force_date": True,
        "window_size": 64 if tf in {"5m", "15m", "1h"} else 32,
        "batch_size": 128,
        "epochs": 200,
        "early_patience": 20,
        "latent_dim": 32,
        "encoder_plugin_candidates": ["lstm", "cnn", "transformer"],
        "decoder_plugin_candidates": ["lstm", "cnn", "transformer"],
        "output_dir": rel(out_dir),
        "feature_columns": metadata["feature_columns"],
    }
    path = out_dir / "feature_extractor_config_template.json"
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def process(asset: str, tf: str, machine: str) -> dict[str, Any]:
    out_dir = ROOT / "features" / "learned_inputs" / asset / tf
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        merged = combine_features(asset, tf)
        train, val, test, full, metadata = split_and_normalize(merged)
        train.to_csv(out_dir / "train.csv", index=False)
        val.to_csv(out_dir / "validation.csv", index=False)
        test.to_csv(out_dir / "test.csv", index=False)
        full.to_parquet(out_dir / "full_normalized.parquet", index=False)
        (out_dir / "feature_columns.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        config_path = write_feature_extractor_config(asset, tf, out_dir, metadata)
        result = {
            "asset": asset,
            "timeframe": tf,
            "status": "ok",
            "output_dir": rel(out_dir),
            "config_template": rel(config_path),
            **metadata,
        }
    except Exception as exc:
        result = {"asset": asset, "timeframe": tf, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    log(machine, f"asset={asset} tf={tf} status={result['status']}")
    return result


def write_report(machine: str, universe: str, results: list[dict[str, Any]]) -> None:
    summary = {
        "generated_at": utc_now(),
        "stage": "Stage 2.4 input preparation",
        "machine": machine,
        "universe": universe,
        "jobs_total": len(results),
        "jobs_ok": sum(item["status"] == "ok" for item in results),
        "jobs_failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
    out_json = ROOT / "_metadata" / f"stage24_learned_input_prep_{machine}_{universe}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    out_md = ROOT / "_logs" / "supervisor_reports" / f"stage24_learned_input_prep_{machine}_{universe}.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Stage 2.4 Learned Input Prep - {machine} {universe}",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        f"- Jobs total: {summary['jobs_total']}",
        f"- Jobs ok: {summary['jobs_ok']}",
        f"- Jobs failed: {summary['jobs_failed']}",
        "",
        "| Asset | TF | Status | Columns | Train | Validation | Test |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for item in results:
        rows = item.get("split_rows", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    item["asset"],
                    item["timeframe"],
                    item["status"],
                    str(item.get("column_count", "")),
                    str(rows.get("train", "")),
                    str(rows.get("validation", "")),
                    str(rows.get("test", "")),
                ]
            )
            + " |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--assets", nargs="+", required=True)
    parser.add_argument("--timeframes", nargs="+", default=["1h", "4h"])
    args = parser.parse_args()
    jobs = [(asset, tf) for asset in args.assets for tf in args.timeframes]
    log(args.machine, f"START stage24 learned input prep universe={args.universe} jobs={len(jobs)}")
    results = [process(asset, tf, args.machine) for asset, tf in jobs]
    write_report(args.machine, args.universe, results)
    log(args.machine, f"DONE stage24 learned input prep universe={args.universe} jobs={len(jobs)}")


if __name__ == "__main__":
    main()
