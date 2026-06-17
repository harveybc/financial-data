#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import project3_event_context_source_coverage_worker as coverage


SCHEMA_VERSION = "project3_event_engineered_summary_v1"
HELDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")

EVENT_FEATURE_COLUMNS = [
    "event_upcoming_high_count_24h",
    "event_upcoming_high_count_72h",
    "event_upcoming_high_count_168h",
    "event_min_hours_to_high_impact",
    "event_sum_importance_weighted_relevance_24h",
    "event_sum_importance_weighted_relevance_168h",
    "event_cluster_count_6h",
    "event_cluster_count_12h",
    "event_cluster_count_24h",
    "event_cpi_week_flag",
    "event_nfp_week_flag",
    "event_fomc_week_flag",
    "event_central_bank_week_flag",
    "event_time_since_last_high_impact_hours",
    "event_recent_abs_surprise_z_max_24h",
    "event_recent_signed_surprise_z_sum_24h",
    "event_no_trade_window_active",
    "event_spread_stress_multiplier",
    "event_slippage_stress_multiplier",
]

HIGH_IMPACT_PATTERNS = (
    "nfp",
    "nonfarm",
    "payroll",
    "cpi",
    "pce",
    "fomc",
    "fed_funds",
    "policy_rate",
    "central_bank",
    "gdp",
    "unemployment",
    "retail_sales",
    "initial_claims",
)


def _repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported source extension: {path.suffix}")


def _sha256_file(path: Path) -> str:
    return coverage._sha256_file(path)


def _parse_timestamp(series: pd.Series) -> pd.Series:
    return coverage._parse_datetime_series(series)


def _find_time_column(df: pd.DataFrame) -> str:
    for candidate in ("DATE_TIME", "timestamp", "date_time", "datetime", "date"):
        if candidate in df.columns:
            return candidate
    raise ValueError("Input file has no DATE_TIME/timestamp column.")


def _derive_output_file(input_file: Path, output_file: str | None) -> Path:
    if output_file:
        return Path(output_file)
    parts = list(input_file.parts)
    if "inputs" in parts:
        preset_index = len(parts) - 2
        parts[preset_index] = f"{parts[preset_index]}_plus_event_engineered_v1"
        return Path(*parts)
    return input_file.with_name(f"{input_file.stem}_plus_event_engineered_v1{input_file.suffix}")


def _infer_target_currencies(target_asset: str | None) -> set[str]:
    if not target_asset:
        return {"USD"}
    asset = target_asset.lower().replace("/", "").replace("_", "")
    currencies: set[str] = set()
    if asset.endswith("usdt") or asset.endswith("usd") or "btc" in asset or "eth" in asset:
        currencies.add("USD")
    if "eur" in asset:
        currencies.add("EUR")
    if "aud" in asset:
        currencies.add("AUD")
    if "gbp" in asset:
        currencies.add("GBP")
    if "jpy" in asset:
        currencies.add("JPY")
    return currencies or {"USD"}


def _event_family(row: pd.Series, family_col: str | None, path: Path) -> str:
    if family_col and family_col in row.index and pd.notna(row[family_col]):
        return str(row[family_col]).lower()
    parent = path.parent.name.lower()
    return parent if parent else "event"


def _event_currency(row: pd.Series, currency_col: str | None) -> str:
    if currency_col and currency_col in row.index and pd.notna(row[currency_col]):
        return str(row[currency_col]).upper()
    return "USD"


def _importance_weight(row: pd.Series, importance_col: str | None, family: str) -> float:
    raw = ""
    if importance_col and importance_col in row.index and pd.notna(row[importance_col]):
        raw = str(row[importance_col]).lower()
    if raw in {"high", "3", "important", "red"}:
        return 1.0
    if raw in {"medium", "2", "orange"}:
        return 0.6
    if raw in {"low", "1", "yellow"}:
        return 0.25
    if any(pattern in family for pattern in HIGH_IMPACT_PATTERNS):
        return 1.0
    return 0.4


def _is_high_impact(family: str, weight: float) -> bool:
    return weight >= 0.9 or any(pattern in family for pattern in HIGH_IMPACT_PATTERNS)


def _event_relevance(currency: str, target_currencies: set[str]) -> float:
    if currency in target_currencies:
        return 1.0
    if currency == "USD" and not target_currencies:
        return 1.0
    return 0.25


def load_scheduled_events(event_source_file: Path, target_asset: str | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = _read_table(event_source_file)
    columns = [str(c) for c in df.columns]
    scheduled_col = coverage._first_matching_column(columns, coverage.SCHEDULED_TS_NAMES)
    if not scheduled_col:
        raise ValueError(f"Event source has no scheduled timestamp column: {event_source_file}")
    family_col = coverage._first_matching_column(columns, coverage.FAMILY_NAMES)
    currency_col = coverage._first_matching_column(columns, coverage.CURRENCY_NAMES)
    importance_col = coverage._first_matching_column(columns, coverage.IMPORTANCE_NAMES)
    first_available_col = coverage._first_matching_column(columns, coverage.FIRST_AVAILABLE_NAMES)
    actual_cols = coverage._find_matching_columns(columns, coverage.ACTUAL_NAMES)
    forecast_cols = coverage._find_matching_columns(columns, coverage.FORECAST_NAMES)
    revision_cols = coverage._find_matching_columns(columns, coverage.REVISION_NAMES)
    surprise_cols = coverage._find_matching_columns(columns, coverage.SURPRISE_NAMES)

    target_currencies = _infer_target_currencies(target_asset)
    scheduled_ts = _parse_timestamp(df[scheduled_col])
    records: list[dict[str, Any]] = []
    for idx, row in df.assign(_scheduled_ts=scheduled_ts).dropna(subset=["_scheduled_ts"]).iterrows():
        ts = row["_scheduled_ts"]
        if ts >= HELDOUT_START:
            continue
        family = _event_family(row, family_col, event_source_file)
        currency = _event_currency(row, currency_col)
        weight = _importance_weight(row, importance_col, family)
        relevance = _event_relevance(currency, target_currencies)
        records.append(
            {
                "scheduled_ts": ts,
                "family": family,
                "currency": currency,
                "importance_weight": weight,
                "relevance_weight": relevance,
                "weighted_relevance": weight * relevance,
                "is_high_impact": _is_high_impact(family, weight),
            }
        )

    events = pd.DataFrame.from_records(records)
    if not events.empty:
        events = events.sort_values("scheduled_ts").reset_index(drop=True)

    audit = {
        "event_source_file": str(event_source_file),
        "event_source_hash": _sha256_file(event_source_file),
        "scheduled_timestamp_column": scheduled_col,
        "first_available_timestamp_column": first_available_col,
        "family_column": family_col,
        "currency_column": currency_col,
        "importance_column": importance_col,
        "raw_event_rows": int(len(df)),
        "scheduled_pre_heldout_event_rows": int(len(events)),
        "target_currencies": sorted(target_currencies),
        "actual_columns_detected": actual_cols,
        "forecast_columns_detected": forecast_cols,
        "revision_columns_detected": revision_cols,
        "surprise_columns_detected": surprise_cols,
        "actual_fields_used": False,
        "forecast_fields_used": False,
        "revision_fields_used": False,
        "surprise_fields_used": False,
        "disabled_point_in_time_fields_reason": None,
    }
    if (actual_cols or forecast_cols or revision_cols or surprise_cols) and not first_available_col:
        audit[
            "disabled_point_in_time_fields_reason"
        ] = "actual/forecast/revision/surprise fields lack first_available_ts"
    return events, audit


def _family_flag(families: pd.Series, *patterns: str) -> int:
    if families.empty:
        return 0
    text = " ".join(families.astype(str).str.lower().tolist())
    return int(any(pattern in text for pattern in patterns))


def build_event_features(
    input_file: Path,
    event_source_file: Path,
    output_file: Path,
    target_asset: str | None,
    no_trade_hours: float,
) -> dict[str, Any]:
    base = pd.read_csv(input_file)
    time_col = _find_time_column(base)
    base_ts = _parse_timestamp(base[time_col])
    pre_heldout_mask = base_ts < HELDOUT_START
    if not bool(pre_heldout_mask.all()):
        base = base.loc[pre_heldout_mask].reset_index(drop=True)
        base_ts = base_ts.loc[pre_heldout_mask].reset_index(drop=True)

    events, event_audit = load_scheduled_events(event_source_file, target_asset)
    event_ts = pd.Series(dtype="datetime64[ns, UTC]")
    if not events.empty:
        event_ts = pd.to_datetime(events["scheduled_ts"], utc=True)

    feature_rows: list[dict[str, float]] = []
    for ts in base_ts:
        row: dict[str, float] = {}
        if events.empty:
            for column in EVENT_FEATURE_COLUMNS:
                row[column] = 0.0
            row["event_min_hours_to_high_impact"] = 9999.0
            row["event_time_since_last_high_impact_hours"] = 9999.0
            row["event_spread_stress_multiplier"] = 1.0
            row["event_slippage_stress_multiplier"] = 1.0
            feature_rows.append(row)
            continue

        future = events[(event_ts >= ts) & (event_ts < ts + pd.Timedelta(hours=168))]
        high_future = future[future["is_high_impact"]]
        past_high = events[(event_ts < ts) & (events["is_high_impact"])]

        for hours in (6, 12, 24, 72, 168):
            window = future[future["scheduled_ts"] < ts + pd.Timedelta(hours=hours)]
            high_window = window[window["is_high_impact"]]
            if hours in (6, 12):
                row[f"event_cluster_count_{hours}h"] = float(len(high_window))
            elif hours == 24:
                row["event_upcoming_high_count_24h"] = float(len(high_window))
                row["event_cluster_count_24h"] = float(len(high_window))
                row["event_sum_importance_weighted_relevance_24h"] = float(
                    high_window["weighted_relevance"].sum()
                )
            elif hours == 72:
                row["event_upcoming_high_count_72h"] = float(len(high_window))
            elif hours == 168:
                row["event_upcoming_high_count_168h"] = float(len(high_window))
                row["event_sum_importance_weighted_relevance_168h"] = float(
                    high_window["weighted_relevance"].sum()
                )

        if high_future.empty:
            min_hours = 9999.0
        else:
            min_hours = float(((high_future["scheduled_ts"].min() - ts) / pd.Timedelta(hours=1)))
        row["event_min_hours_to_high_impact"] = min_hours

        if past_high.empty:
            row["event_time_since_last_high_impact_hours"] = 9999.0
        else:
            row["event_time_since_last_high_impact_hours"] = float(
                (ts - past_high["scheduled_ts"].max()) / pd.Timedelta(hours=1)
            )

        weekly_families = high_future["family"] if not high_future.empty else pd.Series(dtype=str)
        row["event_cpi_week_flag"] = float(_family_flag(weekly_families, "cpi", "pce"))
        row["event_nfp_week_flag"] = float(_family_flag(weekly_families, "nfp", "nonfarm", "payroll"))
        row["event_fomc_week_flag"] = float(_family_flag(weekly_families, "fomc", "fed_funds"))
        row["event_central_bank_week_flag"] = float(
            _family_flag(weekly_families, "central_bank", "policy_rate", "fed_funds")
        )

        row["event_recent_abs_surprise_z_max_24h"] = 0.0
        row["event_recent_signed_surprise_z_sum_24h"] = 0.0
        no_trade = 0.0 <= min_hours <= no_trade_hours
        row["event_no_trade_window_active"] = float(no_trade)
        row["event_spread_stress_multiplier"] = float(
            min(2.0, 1.0 + 0.20 * row["event_no_trade_window_active"] + 0.05 * row["event_upcoming_high_count_24h"])
        )
        row["event_slippage_stress_multiplier"] = float(
            min(2.5, 1.0 + 0.25 * row["event_no_trade_window_active"] + 0.07 * row["event_upcoming_high_count_24h"])
        )
        feature_rows.append(row)

    features = pd.DataFrame(feature_rows, columns=EVENT_FEATURE_COLUMNS)
    output = pd.concat([base.reset_index(drop=True), features], axis=1)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "input_data_file": str(input_file),
        "input_data_hash": _sha256_file(input_file),
        "output_file": str(output_file),
        "output_hash": _sha256_file(output_file),
        "target_asset": target_asset,
        "time_column": time_col,
        "input_rows_before_filter": int(len(pre_heldout_mask)),
        "output_rows": int(len(output)),
        "dropped_heldout_or_later_input_rows": int((~pre_heldout_mask).sum()),
        "event_feature_columns": EVENT_FEATURE_COLUMNS,
        "no_trade_hours": no_trade_hours,
        "event_audit": event_audit,
    }
    metadata_path = output_file.with_name(f"{output_file.stem}_metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metadata["metadata_file"] = str(metadata_path)
    return metadata


def build_arg_parser() -> argparse.ArgumentParser:
    repo_root = _repo_root_from_file()
    parser = argparse.ArgumentParser(
        description="Build Project 3 point-in-time engineered event context features."
    )
    parser.add_argument(
        "--input-data-file",
        default=str(
            repo_root
            / "experiments"
            / "stage_a_screening"
            / "inputs"
            / "ethusdt"
            / "4h"
            / "sota_low_cost"
            / "train.csv"
        ),
    )
    parser.add_argument(
        "--event-source-file",
        default=str(
            repo_root
            / "economic_calendar"
            / "scheduled_events"
            / "fred_release_date_proxy"
            / "scheduled_events.parquet"
        ),
    )
    parser.add_argument("--output-file", default=None)
    parser.add_argument("--target-asset", default="ethusdt")
    parser.add_argument("--no-trade-hours", type=float, default=6.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    input_file = Path(args.input_data_file)
    output_file = _derive_output_file(input_file, args.output_file)
    metadata = build_event_features(
        input_file=input_file,
        event_source_file=Path(args.event_source_file),
        output_file=output_file,
        target_asset=args.target_asset,
        no_trade_hours=args.no_trade_hours,
    )
    print(
        json.dumps(
            {
                "schema_version": metadata["schema_version"],
                "output_file": metadata["output_file"],
                "output_rows": metadata["output_rows"],
                "event_columns": len(metadata["event_feature_columns"]),
                "actual_fields_used": metadata["event_audit"]["actual_fields_used"],
                "surprise_fields_used": metadata["event_audit"]["surprise_fields_used"],
                "training_launched": metadata["training_launched"],
                "stage_c_access": metadata["stage_c_access"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
