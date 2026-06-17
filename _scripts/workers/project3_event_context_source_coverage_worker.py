#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


SCHEMA_VERSION = "project3_event_context_source_coverage_v1"
HELDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")

SOURCE_PATTERNS = (
    "economic_calendar/**/*.parquet",
    "economic_calendar/**/*.csv",
    "features/cross_source_features/*/economic_calendar*.parquet",
    "features/cross_source_features/*/economic_calendar*.csv",
    "features/cross_source_statistical/*/economic_calendar*.parquet",
    "features/cross_source_statistical/*/economic_calendar*.csv",
    "alternative_data/**/*calendar*.parquet",
    "alternative_data/**/*calendar*.csv",
    "alternative_data/**/*event*.parquet",
    "alternative_data/**/*event*.csv",
    "alternative_data/**/*news*.parquet",
    "alternative_data/**/*news*.csv",
)

SCHEDULED_TS_NAMES = (
    "scheduled_release_ts",
    "scheduled_release_time",
    "scheduled_datetime",
    "scheduled_date",
    "release_datetime_utc",
    "release_datetime",
    "release_time",
    "release_date",
    "announcement_datetime_utc",
    "announcement_datetime_local_utc",
    "announcement_datetime",
    "event_datetime_utc",
    "event_datetime",
    "timestamp",
    "date_time",
    "datetime",
    "date",
)
FIRST_AVAILABLE_NAMES = (
    "first_available_ts",
    "first_available_time",
    "available_ts",
    "availability_ts",
    "published_at",
    "publication_ts",
    "ingest_ts",
    "vendor_ingest_ts",
    "created_at",
    "asof_ts",
)
ACTUAL_NAMES = ("actual", "actual_value", "release_actual", "value", "val", "transformed_actual")
FORECAST_NAMES = (
    "forecast",
    "forecast_value",
    "consensus",
    "consensus_estimate",
    "expected",
    "estimate",
)
PREVIOUS_NAMES = ("previous", "previous_value", "prior", "prior_value")
REVISION_NAMES = ("revision", "revised", "revised_value")
SURPRISE_NAMES = ("surprise", "actual_minus_forecast", "forecast_error")
IMPORTANCE_NAMES = ("importance", "impact", "provider_importance", "rank", "priority")
COUNTRY_NAMES = ("country", "country_code", "region")
CURRENCY_NAMES = ("currency", "ccy", "base_currency", "quote_currency")
FAMILY_NAMES = ("event_family", "family", "indicator", "release", "event_name", "event_slug")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _infer_timeframe(path: Path) -> str | None:
    for part in path.parts:
        if part in {"5m", "15m", "1h", "4h"}:
            return part
    return None


def _classify_source(path: Path) -> str:
    text = str(path).lower()
    if "release_actuals" in text or "announcement" in text:
        return "release_actuals"
    if "scheduled_events" in text or "release_calendar" in text:
        return "scheduled_events"
    if "cross_source_features" in text:
        return "aligned_feature_snapshot"
    if "cross_source_statistical" in text:
        return "aligned_statistical_snapshot"
    if "news" in text:
        return "news_context"
    return "event_context"


def _find_matching_columns(columns: list[str], preferred_names: tuple[str, ...]) -> list[str]:
    normalized = {_normalize_name(c): c for c in columns}
    matches: list[str] = []
    for name in preferred_names:
        key = _normalize_name(name)
        if key in normalized and normalized[key] not in matches:
            matches.append(normalized[key])
    for column in columns:
        key = _normalize_name(column)
        for name in preferred_names:
            needle = _normalize_name(name)
            if needle and needle in key and column not in matches:
                matches.append(column)
                break
    return matches


def _first_matching_column(columns: list[str], preferred_names: tuple[str, ...]) -> str | None:
    matches = _find_matching_columns(columns, preferred_names)
    return matches[0] if matches else None


def _parse_datetime_series(series: pd.Series) -> pd.Series:
    non_null = series.dropna()
    if non_null.empty:
        return pd.to_datetime(series, errors="coerce", utc=True)

    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce", utc=True)

    if pd.api.types.is_numeric_dtype(series):
        median_abs = float(non_null.abs().median())
        if not math.isfinite(median_abs):
            return pd.to_datetime(series, errors="coerce", utc=True)
        if median_abs > 1e17:
            return pd.to_datetime(series, errors="coerce", utc=True, unit="ns")
        if median_abs > 1e14:
            return pd.to_datetime(series, errors="coerce", utc=True, unit="us")
        if median_abs > 1e11:
            return pd.to_datetime(series, errors="coerce", utc=True, unit="ms")
        if median_abs > 1e8:
            return pd.to_datetime(series, errors="coerce", utc=True, unit="s")

    return pd.to_datetime(series, errors="coerce", utc=True)


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported source extension: {path.suffix}")


def discover_sources(source_root: Path) -> list[Path]:
    files: set[Path] = set()
    for pattern in SOURCE_PATTERNS:
        files.update(p for p in source_root.glob(pattern) if p.is_file())
    return sorted(files)


def _sample_values(df: pd.DataFrame, column: str | None, limit: int = 10) -> list[str]:
    if not column or column not in df.columns:
        return []
    values = df[column].dropna().astype(str).head(limit).tolist()
    return values


def audit_source(path: Path, source_root: Path) -> dict[str, Any]:
    relative = path.relative_to(source_root)
    source: dict[str, Any] = {
        "path": str(relative),
        "source_class": _classify_source(relative),
        "timeframe": _infer_timeframe(relative),
        "file_size_bytes": path.stat().st_size,
        "source_hash": _sha256_file(path),
        "read_error": None,
        "row_count": 0,
        "column_count": 0,
        "columns": [],
        "scheduled_timestamp_column": None,
        "first_available_timestamp_column": None,
        "country_column": None,
        "currency_column": None,
        "event_family_column": None,
        "actual_columns": [],
        "forecast_columns": [],
        "previous_columns": [],
        "revision_columns": [],
        "surprise_columns": [],
        "importance_columns": [],
        "has_scheduled_release_ts": False,
        "has_first_available_ts": False,
        "has_actual": False,
        "has_forecast": False,
        "has_previous": False,
        "has_revision": False,
        "has_surprise": False,
        "has_provider_importance": False,
        "coverage_start": None,
        "coverage_end": None,
        "pre_heldout_rows": 0,
        "heldout_or_later_rows": 0,
        "uses_heldout": False,
        "sample_currencies": [],
        "sample_countries": [],
        "sample_event_families": [],
        "blocking_issues": [],
        "warnings": [],
    }
    try:
        df = _read_table(path)
    except Exception as exc:  # pragma: no cover - error text depends on engine.
        source["read_error"] = f"{type(exc).__name__}: {exc}"
        source["blocking_issues"].append("SOURCE_READ_FAILED")
        return source

    columns = [str(c) for c in df.columns]
    source["row_count"] = int(len(df))
    source["column_count"] = int(len(columns))
    source["columns"] = columns

    scheduled_col = _first_matching_column(columns, SCHEDULED_TS_NAMES)
    first_available_col = _first_matching_column(columns, FIRST_AVAILABLE_NAMES)
    country_col = _first_matching_column(columns, COUNTRY_NAMES)
    currency_col = _first_matching_column(columns, CURRENCY_NAMES)
    family_col = _first_matching_column(columns, FAMILY_NAMES)
    actual_cols = _find_matching_columns(columns, ACTUAL_NAMES)
    forecast_cols = _find_matching_columns(columns, FORECAST_NAMES)
    previous_cols = _find_matching_columns(columns, PREVIOUS_NAMES)
    revision_cols = _find_matching_columns(columns, REVISION_NAMES)
    surprise_cols = _find_matching_columns(columns, SURPRISE_NAMES)
    importance_cols = _find_matching_columns(columns, IMPORTANCE_NAMES)

    source.update(
        {
            "scheduled_timestamp_column": scheduled_col,
            "first_available_timestamp_column": first_available_col,
            "country_column": country_col,
            "currency_column": currency_col,
            "event_family_column": family_col,
            "actual_columns": actual_cols,
            "forecast_columns": forecast_cols,
            "previous_columns": previous_cols,
            "revision_columns": revision_cols,
            "surprise_columns": surprise_cols,
            "importance_columns": importance_cols,
            "has_scheduled_release_ts": scheduled_col is not None,
            "has_first_available_ts": first_available_col is not None,
            "has_actual": bool(actual_cols),
            "has_forecast": bool(forecast_cols),
            "has_previous": bool(previous_cols),
            "has_revision": bool(revision_cols),
            "has_surprise": bool(surprise_cols),
            "has_provider_importance": bool(importance_cols),
            "sample_currencies": _sample_values(df, currency_col),
            "sample_countries": _sample_values(df, country_col),
            "sample_event_families": _sample_values(df, family_col),
        }
    )

    if scheduled_col:
        parsed = _parse_datetime_series(df[scheduled_col])
        valid = parsed.dropna()
        if not valid.empty:
            source["coverage_start"] = valid.min().isoformat()
            source["coverage_end"] = valid.max().isoformat()
            source["pre_heldout_rows"] = int((valid < HELDOUT_START).sum())
            source["heldout_or_later_rows"] = int((valid >= HELDOUT_START).sum())
            source["uses_heldout"] = bool(source["heldout_or_later_rows"])
        else:
            source["warnings"].append("SCHEDULED_TIMESTAMP_UNPARSEABLE")
    else:
        source["warnings"].append("SCHEDULED_TIMESTAMP_MISSING")

    point_in_time_fields = actual_cols + forecast_cols + previous_cols + revision_cols + surprise_cols
    if point_in_time_fields and not first_available_col:
        source["blocking_issues"].append("POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS")
    if source["has_actual"] and not first_available_col:
        source["blocking_issues"].append("ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS")
    if source["has_surprise"] and not first_available_col:
        source["blocking_issues"].append("SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS")
    if scheduled_col and first_available_col:
        source["warnings"].append("VERIFY_FIRST_AVAILABLE_SEMANTICS_BEFORE_FEATURE_BUILD")

    return source


def _counter_from_samples(sources: list[dict[str, Any]], field: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for source in sources:
        values = source.get(field) or []
        counter.update(str(v) for v in values if str(v).strip())
    return dict(counter.most_common())


def build_report(source_root: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    sources = [audit_source(path, source_root) for path in discover_sources(source_root)]
    issue_counter: Counter[str] = Counter()
    warning_counter: Counter[str] = Counter()
    class_counter: Counter[str] = Counter()
    timeframe_counter: Counter[str] = Counter()
    safe_scheduled_sources = 0
    point_in_time_candidate_sources = 0

    for source in sources:
        issue_counter.update(source.get("blocking_issues", []))
        warning_counter.update(source.get("warnings", []))
        class_counter.update([source["source_class"]])
        if source.get("timeframe"):
            timeframe_counter.update([source["timeframe"]])
        if source.get("has_scheduled_release_ts"):
            safe_scheduled_sources += 1
        if source.get("has_first_available_ts"):
            point_in_time_candidate_sources += 1

    coverage_by_timeframe = defaultdict(lambda: {"source_count": 0, "row_count": 0})
    for source in sources:
        timeframe = source.get("timeframe") or "native"
        coverage_by_timeframe[timeframe]["source_count"] += 1
        coverage_by_timeframe[timeframe]["row_count"] += int(source.get("row_count") or 0)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "source_root": str(source_root),
        "heldout_start": HELDOUT_START.isoformat(),
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "worker": "project3_event_context_source_coverage_worker",
        "source_count": len(sources),
        "safe_scheduled_source_count": safe_scheduled_sources,
        "point_in_time_candidate_source_count": point_in_time_candidate_sources,
        "source_classes": dict(class_counter.most_common()),
        "timeframes": dict(timeframe_counter.most_common()),
        "coverage_by_timeframe": dict(coverage_by_timeframe),
        "coverage_by_currency_sample": _counter_from_samples(sources, "sample_currencies"),
        "coverage_by_country_sample": _counter_from_samples(sources, "sample_countries"),
        "coverage_by_event_family_sample": _counter_from_samples(sources, "sample_event_families"),
        "blocking_issues": dict(issue_counter.most_common()),
        "warnings": dict(warning_counter.most_common()),
        "sources": sources,
    }


def write_json(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        "# Project 3 Event-Context Source Coverage Report",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        "",
        "## Summary",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Source root: `{report['source_root']}`",
        f"- Source count: `{report['source_count']}`",
        f"- Sources with scheduled timestamps: `{report['safe_scheduled_source_count']}`",
        f"- Sources with first-available timestamps: `{report['point_in_time_candidate_source_count']}`",
        f"- Stage C access: `{report['stage_c_access']}`",
        f"- Training launched: `{str(report['training_launched']).lower()}`",
        "",
        "## Blocking Issues",
        "",
    ]
    if report["blocking_issues"]:
        rows.extend(f"- `{issue}`: {count}" for issue, count in report["blocking_issues"].items())
    else:
        rows.append("- None")

    rows.extend(["", "## Warnings", ""])
    if report["warnings"]:
        rows.extend(f"- `{warning}`: {count}" for warning, count in report["warnings"].items())
    else:
        rows.append("- None")

    rows.extend(["", "## Sources", ""])
    rows.append(
        "| Path | Class | Timeframe | Rows | Coverage | Scheduled TS | First Available | Actual | Forecast | Issues |"
    )
    rows.append("| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |")
    for source in report["sources"]:
        coverage = "n/a"
        if source.get("coverage_start") or source.get("coverage_end"):
            coverage = f"{source.get('coverage_start') or '?'} -> {source.get('coverage_end') or '?'}"
        issues = ", ".join(source.get("blocking_issues") or []) or "none"
        rows.append(
            "| "
            + " | ".join(
                [
                    f"`{source['path']}`",
                    f"`{source['source_class']}`",
                    f"`{source.get('timeframe') or 'native'}`",
                    str(source.get("row_count", 0)),
                    coverage,
                    f"`{source.get('scheduled_timestamp_column') or ''}`",
                    f"`{source.get('first_available_timestamp_column') or ''}`",
                    str(bool(source.get("has_actual"))).lower(),
                    str(bool(source.get("has_forecast"))).lower(),
                    issues,
                ]
            )
            + " |"
        )
    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = _repo_root_from_file()
    return argparse.ArgumentParser(description=__doc__).parse_args(argv)


def build_arg_parser() -> argparse.ArgumentParser:
    repo_root = _repo_root_from_file()
    parser = argparse.ArgumentParser(
        description="Audit Project 3 event/calendar context sources before feature engineering."
    )
    parser.add_argument("--source-root", default=str(repo_root), help="financial-data repository root.")
    parser.add_argument(
        "--output-dir",
        default=str(repo_root / "experiments" / "stage3x_event_context"),
        help="Directory for JSON and Markdown reports.",
    )
    parser.add_argument(
        "--stem",
        default="event_source_coverage_report",
        help="Output filename stem.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    source_root = Path(args.source_root)
    output_dir = Path(args.output_dir)
    report = build_report(source_root)
    write_json(report, output_dir / f"{args.stem}.json")
    write_markdown(report, output_dir / f"{args.stem}.md")
    print(
        json.dumps(
            {
                "schema_version": report["schema_version"],
                "source_count": report["source_count"],
                "safe_scheduled_source_count": report["safe_scheduled_source_count"],
                "point_in_time_candidate_source_count": report[
                    "point_in_time_candidate_source_count"
                ],
                "blocking_issues": report["blocking_issues"],
                "warnings": report["warnings"],
                "training_launched": report["training_launched"],
                "stage_c_access": report["stage_c_access"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
