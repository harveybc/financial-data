from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
DATA_SUFFIXES = {".parquet", ".csv"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(machine: str, message: str) -> None:
    path = ROOT / "_logs" / machine / "stage16_quality_worker.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def notify(machine: str, event: str, title: str, message: str) -> None:
    script = ROOT / "_scripts" / "telegram_notify.py"
    if not script.exists():
        return
    try:
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--event",
                f"stage16-quality:{machine}:{event}",
                "--title",
                title,
                "--message",
                message,
                "--min-interval-minutes",
                "30",
            ],
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except Exception as exc:
        log(machine, f"telegram notify skipped event={event} error={type(exc).__name__}")


def candidate_time_column(columns: list[str]) -> str | None:
    priority = ("timestamp", "datetime", "date", "time", "open_time", "period", "filing_date", "release_date")
    lower = {column.lower(): column for column in columns}
    for exact in priority:
        if exact in lower:
            return lower[exact]
    for column in columns:
        name = column.lower()
        if any(token in name for token in ("date", "time", "timestamp", "period")):
            return column
    return None


def natural_key_columns(columns: list[str], time_column: str | None) -> list[str]:
    available = {column.lower(): column for column in columns}

    def present(*names: str) -> list[str]:
        return [available[name] for name in names if name in available and available[name] != time_column]

    rules = [
        ("filing_date", "ticker", "accession_number"),
        ("ticker", "accession_number"),
        ("accession_number",),
        ("timeperiod", "seriescode", "linenumber"),
        ("date", "symbol", "market", "venue_file"),
        ("year", "period", "series_id"),
        (
            "period",
            "ref_area",
            "freq",
            "measure",
            "unit_measure",
            "activity",
            "adjustment",
            "transformation",
            "time_horiz",
            "methodology",
        ),
        ("record_date", "security_type_desc", "security_desc"),
    ]
    for rule in rules:
        if all(name in available for name in rule):
            return present(*rule)

    generic = present("symbol", "ticker", "series_id", "metric", "cik", "form", "market", "venue_file")
    return generic


def read_frame(path: Path):
    import pandas as pd

    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def numeric_series(df, column: str):
    import pandas as pd

    return pd.to_numeric(df[column], errors="coerce")


def quality_check(path: Path) -> dict[str, Any]:
    import pandas as pd

    warnings: list[str] = []
    try:
        df = read_frame(path)
    except Exception as exc:
        return {
            "path": rel(path),
            "rows": None,
            "columns": [],
            "time_column": None,
            "warnings": [f"read_failed:{type(exc).__name__}"],
        }

    rows = int(df.shape[0])
    columns = [str(column) for column in df.columns]
    if rows == 0:
        warnings.append("zero_rows")

    time_column = candidate_time_column(columns)
    natural_keys = natural_key_columns(columns, time_column)
    time_stats: dict[str, Any] = {}
    if time_column:
        parsed = pd.to_datetime(df[time_column], errors="coerce", utc=True)
        nulls = int(parsed.isna().sum())
        key_columns = [time_column] + natural_keys if natural_keys else [time_column]
        duplicates = int(df.duplicated(key_columns).sum()) if rows else 0
        if natural_keys:
            monotonic = True
        else:
            monotonic = bool(parsed.dropna().is_monotonic_increasing)
        if nulls:
            warnings.append("time_parse_nulls")
        if duplicates:
            warnings.append("duplicate_time_natural_key")
        if rows and not monotonic:
            warnings.append("non_monotonic_time")
        valid = parsed.dropna()
        time_stats = {
            "nulls": nulls,
            "duplicates": duplicates,
            "duplicate_key_columns": key_columns,
            "natural_key_columns": natural_keys,
            "monotonic_increasing": monotonic,
            "min": str(valid.min()) if not valid.empty else None,
            "max": str(valid.max()) if not valid.empty else None,
        }

    try:
        all_duplicate_rows = int(df.duplicated().sum()) if rows else 0
    except TypeError:
        all_duplicate_rows = 0
        if rows > 1:
            warnings.append("exact_duplicate_check_skipped_unhashable_columns")
    if all_duplicate_rows:
        warnings.append("exact_duplicate_rows")

    lower_map = {str(column).lower(): str(column) for column in df.columns}
    ohlc = {key: lower_map[key] for key in ("open", "high", "low", "close") if key in lower_map}
    ohlc_stats: dict[str, int] = {}
    if set(ohlc) == {"open", "high", "low", "close"}:
        open_ = numeric_series(df, ohlc["open"])
        high = numeric_series(df, ohlc["high"])
        low = numeric_series(df, ohlc["low"])
        close = numeric_series(df, ohlc["close"])
        bad_high = int((high < pd.concat([open_, low, close], axis=1).max(axis=1)).sum())
        bad_low = int((low > pd.concat([open_, high, close], axis=1).min(axis=1)).sum())
        negative_prices = int(((open_ < 0) | (high < 0) | (low < 0) | (close < 0)).sum())
        if bad_high:
            warnings.append("bad_ohlc_high")
        if bad_low:
            warnings.append("bad_ohlc_low")
        if negative_prices:
            warnings.append("negative_prices")
        ohlc_stats = {
            "bad_high_rows": bad_high,
            "bad_low_rows": bad_low,
            "negative_price_rows": negative_prices,
        }

    volume_stats: dict[str, int] = {}
    for name in columns:
        if "volume" not in name.lower():
            continue
        values = numeric_series(df, name)
        negative = int((values < 0).sum())
        if negative:
            warnings.append(f"negative_{name}")
        volume_stats[name] = negative

    return {
        "path": rel(path),
        "rows": rows,
        "columns": columns,
        "time_column": time_column,
        "time_stats": time_stats,
        "exact_duplicate_rows": all_duplicate_rows,
        "ohlc_stats": ohlc_stats,
        "negative_volume_rows": volume_stats,
        "warnings": sorted(set(warnings)),
    }


def collect_files(root_names: list[str]) -> list[Path]:
    files: list[Path] = []
    for name in root_names:
        root = ROOT / name
        if root.exists():
            files.extend(path for path in sorted(root.rglob("*")) if path.is_file() and path.suffix.lower() in DATA_SUFFIXES)
    return files


def write_markdown(machine: str, payload: dict[str, Any]) -> None:
    path = ROOT / "_logs" / "supervisor_reports" / f"stage16_quality_validation_{machine}.md"
    lines = [
        f"# Stage 1.6 Quality Validation - {machine}",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Roots: {', '.join(payload['summary']['roots'])}",
        f"- Files checked: {payload['summary']['files_checked']}",
        f"- Files with warnings: {payload['summary']['files_with_warnings']}",
        f"- Warning counts: {json.dumps(payload['summary']['warning_counts'], sort_keys=True)}",
        "",
        "## Warning Examples",
        "",
    ]
    examples = [item for item in payload["checks"] if item.get("warnings")][:60]
    if not examples:
        lines.append("- No quality warnings detected.")
    for item in examples:
        lines.append(f"- {item['path']}: {', '.join(item['warnings'])}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Project 3 Stage 1.6 quality validation worker")
    parser.add_argument("--machine", required=True)
    parser.add_argument("--roots", required=True)
    args = parser.parse_args()

    roots = [item.strip() for item in args.roots.split(",") if item.strip()]
    log(args.machine, f"START stage16 quality validation roots={','.join(roots)}")
    notify(
        args.machine,
        "start",
        f"Project 3 {args.machine} Stage 1.6 quality validation started",
        f"machine: {args.machine}\nwork_plan_stage: Stage 1.6 quality validation\ntask: quality-check {', '.join(roots)}\nstatus: started",
    )

    checks = [quality_check(path) for path in collect_files(roots)]
    warning_counts: dict[str, int] = {}
    for item in checks:
        for warning in item.get("warnings", []):
            warning_counts[warning] = warning_counts.get(warning, 0) + 1
    summary = {
        "roots": roots,
        "files_checked": len(checks),
        "files_with_warnings": sum(1 for item in checks if item.get("warnings")),
        "warning_counts": dict(sorted(warning_counts.items())),
    }
    payload = {
        "generated_at": utc_now(),
        "machine": args.machine,
        "stage": "Stage 1.6 quality validation",
        "formal_stage_status": "preflight_only_waiting_for_stage_1_4_and_1_5",
        "summary": summary,
        "checks": checks,
    }
    out = ROOT / "_metadata" / f"stage16_quality_validation_{args.machine}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.machine, payload)
    notify(
        args.machine,
        "finish",
        f"Project 3 {args.machine} Stage 1.6 quality validation finished",
        "\n".join(
            [
                f"machine: {args.machine}",
                "work_plan_stage: Stage 1.6 quality validation",
                "status: finished",
                f"deliverable_path: {rel(out)}",
                f"validation_evidence: files_checked={summary['files_checked']} warnings={summary['files_with_warnings']}",
                "recommended_next_action: supervisor aggregates quality results and escalates only supported anomalies",
            ]
        ),
    )
    log(
        args.machine,
        f"DONE stage16 quality validation files={summary['files_checked']} warnings={summary['files_with_warnings']}",
    )


if __name__ == "__main__":
    main()
