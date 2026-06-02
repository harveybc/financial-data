#!/usr/bin/env python3
"""Materialize the pragmatic ETHUSDT 4h Stage B diagnostic feature variants.

The worker reads only existing Stage A pre-heldout input CSVs and writes
diagnostic Stage B input CSVs. It refuses any source row with
``DATE_TIME >= 2025-01-01``. It does not launch training.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "experiments" / "stage_a_screening" / "inputs" / "ethusdt" / "4h"
OUT_ROOT = ROOT / "experiments" / "stage_b_validation" / "diagnostic_inputs" / "ethusdt" / "4h"
SUMMARY_JSON = OUT_ROOT / "feature_variant_materialization_summary.json"
SUMMARY_MD = OUT_ROOT / "feature_variant_materialization_summary.md"

HELDOUT_START = pd.Timestamp("2025-01-01")
CORE_COLUMNS = ["DATE_TIME", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]
FORCE_CLOSE_DOW = 4
FORCE_CLOSE_HOUR = 20
HOURS_PER_WEEK = 7 * 24

SESSION_CALENDAR_COLUMNS = [
    "calendar_weekday",
    "calendar_hour",
    "calendar_hour_of_week",
    "calendar_weekday_sin",
    "calendar_weekday_cos",
    "calendar_hour_of_day_sin",
    "calendar_hour_of_day_cos",
    "calendar_hour_of_week_sin",
    "calendar_hour_of_week_cos",
    "calendar_is_trading_session",
    "calendar_is_force_close_zone",
    "calendar_is_friday_close_day",
    "calendar_is_friday_force_close_bar",
    "calendar_is_monday_entry_window",
    "calendar_hours_to_friday_close",
    "calendar_bars_to_friday_close",
    "calendar_hours_to_next_friday_close",
    "calendar_bars_to_next_friday_close",
    "calendar_hours_to_next_entry_window",
]

VARIANT_ORDER = [
    "baseline_12",
    "baseline_12_plus_session_calendar",
    "tech_stat_full",
    "tech_stat_full_plus_session_calendar",
    "tech_stat_reduced_corr_v1",
    "tech_stat_reduced_corr_v1_plus_session_calendar",
    "tech_stat_volatility_only",
    "tech_stat_trend_only",
    "tech_stat_momentum_only",
    "tech_stat_volume_liquidity_only",
    "tech_stat_full_plus_train_only_regime_probs",
    "tech_stat_reduced_corr_v1_plus_train_only_regime_probs",
    "tech_stat_full_plus_train_only_ood_score",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_source_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"source CSV not found: {path}")
    df = pd.read_csv(path)
    if "DATE_TIME" not in df.columns:
        raise ValueError(f"source CSV missing DATE_TIME: {path}")
    ts = pd.to_datetime(df["DATE_TIME"], errors="raise")
    if (ts >= HELDOUT_START).any():
        offending = df.loc[ts >= HELDOUT_START, "DATE_TIME"].iloc[0]
        raise ValueError(f"source CSV contains Stage C row {offending!r}: {path}")
    if ts.duplicated().any():
        raise ValueError(f"source CSV contains duplicate DATE_TIME rows: {path}")
    if not ts.is_monotonic_increasing:
        raise ValueError(f"source CSV DATE_TIME is not monotonic: {path}")
    return df


def existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [col for col in columns if col in df.columns]


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in df.columns if col not in CORE_COLUMNS]


def select_family_columns(df: pd.DataFrame, family: str) -> list[str]:
    cols = feature_columns(df)
    if family == "volatility":
        keys = ("bb_", "atr", "natr", "hist_vol", "realized_var", "vol_regime", "zscore")
    elif family == "trend":
        keys = ("sma_", "ema_", "close_sma_ratio", "macd", "trend_", "ema_cross")
    elif family == "momentum":
        keys = ("rsi_", "stoch_", "williams", "cci", "roc_", "mom_")
    elif family == "volume_liquidity":
        keys = ("obv", "volume_", "volume_ratio", "vwap", "mfi")
    else:
        raise ValueError(f"unknown family: {family}")
    return [col for col in cols if any(key in col for key in keys)]


def reduced_corr_columns(df: pd.DataFrame, *, threshold: float = 0.95) -> list[str]:
    candidates = [
        col for col in feature_columns(df)
        if pd.api.types.is_numeric_dtype(df[col]) and df[col].notna().any()
    ]
    if not candidates:
        return []
    frame = df[candidates].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    corr = frame.corr(method="spearman").abs().fillna(0.0)
    keep: list[str] = []
    dropped: set[str] = set()
    for col in candidates:
        if col in dropped:
            continue
        keep.append(col)
        high = corr.index[(corr[col] >= threshold) & (corr.index != col)].tolist()
        dropped.update(high)
    return keep


def infer_bar_hours(ts: pd.Series) -> float:
    deltas = ts.sort_values().diff().dropna()
    if deltas.empty:
        return 4.0
    hours = deltas.dt.total_seconds() / 3600.0
    median = float(hours.median())
    if not np.isfinite(median) or median <= 0:
        return 4.0
    return median


def add_session_calendar_columns(
    df: pd.DataFrame,
    *,
    force_close_dow: int = FORCE_CLOSE_DOW,
    force_close_hour: int = FORCE_CLOSE_HOUR,
) -> pd.DataFrame:
    """Add deterministic calendar context known at decision time.

    The trading strategy already enforces a Friday force-close window. These
    columns make that rule visible to the policy without using future market
    values. They are safe for train/validation/test construction because they
    are deterministic functions of each row timestamp.
    """
    out = df.copy()
    ts = pd.to_datetime(out["DATE_TIME"], errors="raise")
    bar_hours = infer_bar_hours(ts)

    weekday = ts.dt.weekday.astype(float)
    hour = ts.dt.hour.astype(float) + ts.dt.minute.astype(float) / 60.0
    hour_of_week = weekday * 24.0 + hour
    close_hour_of_week = float(force_close_dow * 24 + force_close_hour)

    hours_to_current_close = np.maximum(close_hour_of_week - hour_of_week, 0.0)
    hours_to_next_close = (close_hour_of_week - hour_of_week) % HOURS_PER_WEEK
    is_trading_session = (hour_of_week < close_hour_of_week).astype(float)
    is_force_close_zone = (hour_of_week >= close_hour_of_week).astype(float)
    next_entry = np.where(is_trading_session > 0.0, 0.0, (HOURS_PER_WEEK - hour_of_week) % HOURS_PER_WEEK)

    # A bar is force-close-sensitive if the configured close falls inside the
    # current bar interval, or if the row itself is already in the close zone.
    is_force_close_bar = (
        ((hour_of_week < close_hour_of_week) & ((hour_of_week + bar_hours) >= close_hour_of_week))
        | (hour_of_week >= close_hour_of_week)
    ).astype(float)

    out["calendar_weekday"] = weekday
    out["calendar_hour"] = hour
    out["calendar_hour_of_week"] = hour_of_week
    out["calendar_weekday_sin"] = np.sin(2.0 * np.pi * weekday / 7.0)
    out["calendar_weekday_cos"] = np.cos(2.0 * np.pi * weekday / 7.0)
    out["calendar_hour_of_day_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
    out["calendar_hour_of_day_cos"] = np.cos(2.0 * np.pi * hour / 24.0)
    out["calendar_hour_of_week_sin"] = np.sin(2.0 * np.pi * hour_of_week / HOURS_PER_WEEK)
    out["calendar_hour_of_week_cos"] = np.cos(2.0 * np.pi * hour_of_week / HOURS_PER_WEEK)
    out["calendar_is_trading_session"] = is_trading_session
    out["calendar_is_force_close_zone"] = is_force_close_zone
    out["calendar_is_friday_close_day"] = (weekday == float(force_close_dow)).astype(float)
    out["calendar_is_friday_force_close_bar"] = is_force_close_bar
    out["calendar_is_monday_entry_window"] = ((weekday == 0.0) & (is_trading_session > 0.0)).astype(float)
    out["calendar_hours_to_friday_close"] = hours_to_current_close
    out["calendar_bars_to_friday_close"] = np.ceil(hours_to_current_close / bar_hours).astype(float)
    out["calendar_hours_to_next_friday_close"] = hours_to_next_close
    out["calendar_bars_to_next_friday_close"] = np.ceil(hours_to_next_close / bar_hours).astype(float)
    out["calendar_hours_to_next_entry_window"] = next_entry
    return out


def add_regime_prob_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "roll_std_ret_20" in out.columns:
        signal = pd.to_numeric(out["roll_std_ret_20"], errors="coerce")
    elif "hist_vol_20" in out.columns:
        signal = pd.to_numeric(out["hist_vol_20"], errors="coerce")
    else:
        signal = pd.to_numeric(out.get("log_return_1", 0.0), errors="coerce").abs()
    signal = signal.replace([np.inf, -np.inf], np.nan).fillna(signal.median())
    q_low = float(signal.quantile(0.33))
    q_high = float(signal.quantile(0.66))
    low = (signal <= q_low).astype(float)
    high = (signal >= q_high).astype(float)
    mid = ((signal > q_low) & (signal < q_high)).astype(float)
    out["train_only_regime_prob_low"] = low
    out["train_only_regime_prob_mid"] = mid
    out["train_only_regime_prob_high"] = high
    probs = np.vstack([low.to_numpy(), mid.to_numpy(), high.to_numpy()]).T
    entropy = -(probs * np.log(np.clip(probs, 1e-12, 1.0))).sum(axis=1)
    out["train_only_regime_entropy"] = entropy
    return out


def add_ood_score_column(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cols = [
        col for col in feature_columns(out)
        if pd.api.types.is_numeric_dtype(out[col]) and not col.startswith("train_only_")
    ]
    if not cols:
        out["train_only_ood_score"] = 0.0
        return out
    frame = out[cols].replace([np.inf, -np.inf], np.nan)
    med = frame.median(axis=0)
    mad = (frame - med).abs().median(axis=0).replace(0.0, np.nan).fillna(1.0)
    robust_z = ((frame.fillna(med) - med) / mad).clip(-20.0, 20.0)
    out["train_only_ood_score"] = np.sqrt((robust_z ** 2).mean(axis=1))
    return out


def write_variant(name: str, df: pd.DataFrame, selected_features: list[str], source: Path) -> dict[str, Any]:
    columns = existing_columns(df, CORE_COLUMNS) + existing_columns(df, selected_features)
    out_df = df[columns].copy()
    out_dir = OUT_ROOT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "train.csv"
    out_meta = out_dir / "train_metadata.json"
    out_df.to_csv(out_csv, index=False)
    ts = pd.to_datetime(out_df["DATE_TIME"], errors="raise")
    metadata = {
        "schema_version": "project3_stage_b_feature_variant_v1",
        "generated_at": utc_now(),
        "variant": name,
        "asset": "ethusdt",
        "timeframe": "4h",
        "source_csv": str(source),
        "output_csv": str(out_csv),
        "heldout_start": "2025-01-01",
        "fit_uses_stage_c": False,
        "fit_uses_validation": False,
        "rows": int(len(out_df)),
        "columns": int(len(out_df.columns)),
        "feature_columns": existing_columns(out_df, selected_features),
        "first_timestamp": str(out_df["DATE_TIME"].iloc[0]),
        "last_timestamp": str(out_df["DATE_TIME"].iloc[-1]),
        "max_timestamp_lt_heldout": bool((ts < HELDOUT_START).all()),
        "config_hash": sha256_text("\n".join(columns)),
    }
    out_meta.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def build_variants() -> list[dict[str, Any]]:
    baseline = load_source_csv(SOURCE_ROOT / "baseline_12" / "train.csv")
    tech = load_source_csv(SOURCE_ROOT / "tech_stat" / "train.csv")
    reduced = reduced_corr_columns(tech)
    calendar_baseline = add_session_calendar_columns(baseline)
    calendar_tech = add_session_calendar_columns(tech)

    specs: dict[str, tuple[pd.DataFrame, list[str], Path]] = {
        "baseline_12": (baseline, feature_columns(baseline), SOURCE_ROOT / "baseline_12" / "train.csv"),
        "baseline_12_plus_session_calendar": (
            calendar_baseline,
            feature_columns(baseline) + SESSION_CALENDAR_COLUMNS,
            SOURCE_ROOT / "baseline_12" / "train.csv",
        ),
        "tech_stat_full": (tech, feature_columns(tech), SOURCE_ROOT / "tech_stat" / "train.csv"),
        "tech_stat_full_plus_session_calendar": (
            calendar_tech,
            feature_columns(tech) + SESSION_CALENDAR_COLUMNS,
            SOURCE_ROOT / "tech_stat" / "train.csv",
        ),
        "tech_stat_reduced_corr_v1": (tech, reduced, SOURCE_ROOT / "tech_stat" / "train.csv"),
        "tech_stat_reduced_corr_v1_plus_session_calendar": (
            calendar_tech,
            reduced + SESSION_CALENDAR_COLUMNS,
            SOURCE_ROOT / "tech_stat" / "train.csv",
        ),
        "tech_stat_volatility_only": (tech, select_family_columns(tech, "volatility"), SOURCE_ROOT / "tech_stat" / "train.csv"),
        "tech_stat_trend_only": (tech, select_family_columns(tech, "trend"), SOURCE_ROOT / "tech_stat" / "train.csv"),
        "tech_stat_momentum_only": (tech, select_family_columns(tech, "momentum"), SOURCE_ROOT / "tech_stat" / "train.csv"),
        "tech_stat_volume_liquidity_only": (tech, select_family_columns(tech, "volume_liquidity"), SOURCE_ROOT / "tech_stat" / "train.csv"),
    }

    regime_full = add_regime_prob_columns(tech)
    regime_cols = feature_columns(tech) + [
        "train_only_regime_prob_low",
        "train_only_regime_prob_mid",
        "train_only_regime_prob_high",
        "train_only_regime_entropy",
    ]
    specs["tech_stat_full_plus_train_only_regime_probs"] = (
        regime_full, regime_cols, SOURCE_ROOT / "tech_stat" / "train.csv",
    )
    specs["tech_stat_reduced_corr_v1_plus_train_only_regime_probs"] = (
        regime_full,
        reduced + [
            "train_only_regime_prob_low",
            "train_only_regime_prob_mid",
            "train_only_regime_prob_high",
            "train_only_regime_entropy",
        ],
        SOURCE_ROOT / "tech_stat" / "train.csv",
    )

    ood_full = add_ood_score_column(tech)
    specs["tech_stat_full_plus_train_only_ood_score"] = (
        ood_full,
        feature_columns(tech) + ["train_only_ood_score"],
        SOURCE_ROOT / "tech_stat" / "train.csv",
    )

    outputs = [write_variant(name, *specs[name]) for name in VARIANT_ORDER]
    return outputs


def write_summary(outputs: list[dict[str, Any]]) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "project3_stage_b_feature_variant_materialization_summary_v1",
        "generated_at": utc_now(),
        "heldout_start": "2025-01-01",
        "stage_c_touched": False,
        "session_calendar_context": {
            "force_close_dow": FORCE_CLOSE_DOW,
            "force_close_hour": FORCE_CLOSE_HOUR,
            "columns": SESSION_CALENDAR_COLUMNS,
        },
        "variant_count": len(outputs),
        "variants": outputs,
    }
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage B Feature Variant Materialization Summary",
        "",
        f"Generated UTC: `{payload['generated_at']}`",
        "",
        f"- Stage C touched: `{payload['stage_c_touched']}`",
        f"- Heldout boundary: `{payload['heldout_start']}`",
        f"- Variants: `{payload['variant_count']}`",
        f"- Session force close: `dow={FORCE_CLOSE_DOW}`, `hour={FORCE_CLOSE_HOUR}`",
        f"- Session/calendar columns added where variant name ends with `plus_session_calendar`: `{len(SESSION_CALENDAR_COLUMNS)}`",
        "",
        "| variant | rows | cols | first | last |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for item in outputs:
        lines.append(
            f"| `{item['variant']}` | {item['rows']} | {item['columns']} | "
            f"`{item['first_timestamp']}` | `{item['last_timestamp']}` |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    outputs = build_variants()
    write_summary(outputs)
    print(json.dumps({
        "ok": True,
        "variant_count": len(outputs),
        "summary_json": str(SUMMARY_JSON),
        "summary_md": str(SUMMARY_MD),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
