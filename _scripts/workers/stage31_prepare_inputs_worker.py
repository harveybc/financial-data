#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))

BASELINE_MAP = {
    "return_1": "returns",
    "log_return_1": "log_returns",
    "rsi_14": "rsi_14",
    "macd_hist": "macd_hist",
    "bb_pct_b": "bb_pos",
    "volume_ratio_20": "volume_ratio",
    "ema_cross_10_50": "ema_cross",
    "natr_14": "atr_norm",
    "obv_delta_20": "obv_delta",
    "return_5": "momentum_5",
    "return_20": "momentum_20",
    "hist_vol_20": "vol_20",
}

PRESET_FAMILIES = {
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
    "crypto_full": [
        "technical",
        "statistical",
        "wavelet",
        "emd",
        "fracdiff",
        "learned_lstm",
        "learned_cnn",
        "sota_intrabar_realized",
        "sota_hmm_regime",
        "sota_pair_spreads",
        "sota_funding_term_structure",
    ],
    "fx_full": [
        "technical",
        "statistical",
        "wavelet",
        "emd",
        "fracdiff",
        "learned_lstm",
        "learned_cnn",
        "sota_intrabar_realized",
        "sota_hmm_regime",
        "sota_pair_spreads",
    ],
    "kitchen_sink_guarded": [
        "technical",
        "statistical",
        "wavelet",
        "hilbert",
        "multitaper",
        "emd",
        "fracdiff",
        "learned_lstm",
        "learned_cnn",
        "sota_intrabar_realized",
        "sota_hmm_regime",
        "sota_pair_spreads",
        "sota_funding_term_structure",
    ],
}

OHLCV = ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def normalize_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def load_base(asset: str, timeframe: str) -> pd.DataFrame:
    path = PROJECT_ROOT / "features" / "trading_asset_data" / asset / f"{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"missing trading asset parquet: {path}")
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"{path} is missing timestamp column")
    rename = {
        "timestamp": "DATE_TIME",
        "open": "OPEN",
        "high": "HIGH",
        "low": "LOW",
        "close": "CLOSE",
        "volume": "VOLUME",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df["DATE_TIME"] = normalize_timestamp(df["DATE_TIME"])
    if "CLOSE" not in df.columns:
        raise ValueError(f"{path} is missing close/CLOSE column")
    for col in ("OPEN", "HIGH", "LOW"):
        if col not in df.columns:
            df[col] = df["CLOSE"]
    if "VOLUME" not in df.columns:
        df["VOLUME"] = 0.0
    keep = ["DATE_TIME", *OHLCV]
    return df[keep].dropna(subset=["DATE_TIME", "CLOSE"]).sort_values("DATE_TIME")


def load_feature_family(asset: str, timeframe: str, family: str) -> tuple[pd.DataFrame | None, str | None]:
    path = PROJECT_ROOT / "features" / "trading_asset_features" / asset / timeframe / f"{family}.parquet"
    if not path.exists():
        return None, None
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        return None, str(path)
    df = df.copy()
    df["timestamp"] = normalize_timestamp(df["timestamp"])
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    return df, str(path)


def merge_family(base: pd.DataFrame, feature_df: pd.DataFrame, family: str) -> tuple[pd.DataFrame, list[str]]:
    used = {c.lower() for c in base.columns}
    rename = {"timestamp": "DATE_TIME"}
    selected = []
    for col in feature_df.columns:
        if col == "timestamp":
            continue
        out_col = col
        if out_col.lower() in used:
            out_col = f"{family}__{col}"
        rename[col] = out_col
        selected.append(out_col)
        used.add(out_col.lower())
    feature_df = feature_df.rename(columns=rename)
    merged = base.merge(feature_df[["DATE_TIME", *selected]], on="DATE_TIME", how="left")
    return merged, selected


def select_baseline_features(asset: str, timeframe: str, base: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    technical, source = load_feature_family(asset, timeframe, "technical")
    sources = [source] if source else []
    if technical is None:
        for out_col in BASELINE_MAP.values():
            base[out_col] = 0.0
        return base, list(BASELINE_MAP.values()), sources, list(BASELINE_MAP)

    technical = technical.rename(columns={"timestamp": "DATE_TIME"})
    technical["DATE_TIME"] = normalize_timestamp(technical["DATE_TIME"])
    keep_existing = [col for col in BASELINE_MAP if col in technical.columns]
    merged = base.merge(technical[["DATE_TIME", *keep_existing]], on="DATE_TIME", how="left")
    missing = []
    for raw_col, out_col in BASELINE_MAP.items():
        if raw_col in merged.columns:
            merged[out_col] = merged[raw_col]
        else:
            merged[out_col] = 0.0
            missing.append(raw_col)
    return merged, list(BASELINE_MAP.values()), sources, missing


def families_for_preset(asset: str, preset: str) -> list[str]:
    if preset == "baseline_12":
        return []
    if preset == "fx_full" and asset.endswith("usdt"):
        return PRESET_FAMILIES["crypto_full"]
    if preset == "crypto_full" and not asset.endswith("usdt") and "usdt" not in asset:
        return PRESET_FAMILIES["fx_full"]
    if preset in PRESET_FAMILIES:
        return PRESET_FAMILIES[preset]
    raise ValueError(f"unknown feature preset: {preset}")


def prune_feature_columns(df: pd.DataFrame, feature_cols: Iterable[str], max_features: int) -> list[str]:
    cols = []
    for col in feature_cols:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        non_null = float(s.notna().mean()) if len(s) else 0.0
        if non_null < 0.5:
            continue
        std = float(s.std(skipna=True)) if len(s) else 0.0
        if not math.isfinite(std) or std == 0.0:
            continue
        cols.append(col)
    if len(cols) <= max_features:
        return cols
    ranked = []
    for col in cols:
        s = pd.to_numeric(df[col], errors="coerce")
        ranked.append((float(s.notna().mean()), float(s.std(skipna=True)), col))
    ranked.sort(reverse=True)
    return [col for _, _, col in ranked[:max_features]]


def apply_split(df: pd.DataFrame, split: str) -> pd.DataFrame:
    dt = df["DATE_TIME"]
    if split == "train":
        return df[dt < pd.Timestamp("2024-01-01", tz="UTC")]
    if split == "validation":
        return df[(dt >= pd.Timestamp("2024-01-01", tz="UTC")) & (dt < pd.Timestamp("2025-01-01", tz="UTC"))]
    if split == "preheldout":
        return df[dt < pd.Timestamp("2025-01-01", tz="UTC")]
    if split == "heldout":
        return df[(dt >= pd.Timestamp("2025-01-01", tz="UTC")) & (dt < pd.Timestamp("2026-01-01", tz="UTC"))]
    if split == "all":
        return df
    raise ValueError(f"unknown split: {split}")


def export_input(asset: str, timeframe: str, preset: str, split: str, max_features: int) -> dict:
    base = load_base(asset, timeframe)
    sources = [str(PROJECT_ROOT / "features" / "trading_asset_data" / asset / f"{timeframe}.parquet")]
    missing_families = []
    missing_baseline = []

    if preset == "baseline_12":
        df, feature_cols, family_sources, missing_baseline = select_baseline_features(asset, timeframe, base)
        sources.extend(family_sources)
    else:
        df = base
        feature_cols = []
        for family in families_for_preset(asset, preset):
            feature_df, source = load_feature_family(asset, timeframe, family)
            if feature_df is None:
                missing_families.append(family)
                continue
            df, new_cols = merge_family(df, feature_df, family)
            feature_cols.extend(new_cols)
            if source:
                sources.append(source)
        feature_cols = prune_feature_columns(df, feature_cols, max_features=max_features)

    required_cols = ["DATE_TIME", *OHLCV, *feature_cols]
    df = apply_split(df[required_cols], split)
    numeric_cols = [c for c in required_cols if c != "DATE_TIME"]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)
    df[numeric_cols] = df[numeric_cols].ffill()
    df = df.dropna(subset=["DATE_TIME", "OPEN", "HIGH", "LOW", "CLOSE", *feature_cols]).copy()
    df = df.sort_values("DATE_TIME")
    df["DATE_TIME"] = df["DATE_TIME"].dt.strftime("%Y-%m-%d %H:%M:%S")

    out_dir = PROJECT_ROOT / "experiments" / "stage_a_screening" / "inputs" / asset / timeframe / preset
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{split}.csv"
    df.to_csv(out_path, index=False)

    meta = {
        "asset": asset,
        "timeframe": timeframe,
        "preset": preset,
        "split": split,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "feature_columns": feature_cols,
        "missing_feature_families": missing_families,
        "missing_baseline_features_filled_zero": missing_baseline,
        "sources": sources,
        "output_csv": str(out_path),
        "generated_at": utc_now(),
        "machine": socket.gethostname(),
    }
    write_json(out_dir / f"{split}_metadata.json", meta)
    return meta


def write_report(results: list[dict], status: str) -> None:
    report_path = PROJECT_ROOT / "_logs" / "supervisor_reports" / "stage31_input_exports.md"
    meta_path = PROJECT_ROOT / "_metadata" / "stage31_input_exports.json"
    payload = {
        "status": status,
        "machine": socket.gethostname(),
        "generated_at": utc_now(),
        "exports": results,
    }
    write_json(meta_path, payload)
    lines = [
        "# Stage 3.1 Input Export Report",
        "",
        f"Generated: {payload['generated_at']}",
        f"Machine: `{payload['machine']}`",
        f"Status: `{status}`",
        "",
        "| Asset | TF | Preset | Split | Rows | Columns | Missing families | CSV |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for item in results:
        lines.append(
            f"| {item['asset']} | {item['timeframe']} | {item['preset']} | {item['split']} | "
            f"{item['rows']} | {item['columns']} | {', '.join(item['missing_feature_families']) or '-'} | "
            f"`{item['output_csv']}` |"
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Project 3 parquet feature presets to agent-multi CSV inputs.")
    parser.add_argument("--asset", action="append", dest="assets", required=True)
    parser.add_argument("--timeframe", action="append", dest="timeframes", required=True)
    parser.add_argument("--preset", action="append", dest="presets", required=True)
    parser.add_argument("--split", action="append", dest="splits")
    parser.add_argument("--max-features", type=int, default=180)
    args = parser.parse_args()

    results = []
    splits = args.splits or ["train"]
    for asset in args.assets:
        for timeframe in args.timeframes:
            for preset in args.presets:
                for split in splits:
                    results.append(export_input(asset, timeframe, preset, split, args.max_features))
    write_report(results, "complete")
    print(json.dumps({"ok": True, "exports": results}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
