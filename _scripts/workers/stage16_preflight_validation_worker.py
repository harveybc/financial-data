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
DATA_SUFFIXES = {".parquet", ".csv", ".json", ".jsonl"}
DOC_NAMES = ("README.md", "data_dictionary.md", "provenance.json")
MAX_SAMPLE_ROWS = 1000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(machine: str, message: str) -> None:
    path = ROOT / "_logs" / machine / "stage16_preflight_validation_worker.log"
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
                f"stage16:{machine}:{event}",
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


def doc_state(folder: Path) -> dict[str, Any]:
    missing = [name for name in DOC_NAMES if not (folder / name).exists()]
    return {"complete": not missing, "missing": missing}


def parquet_profile(path: Path) -> dict[str, Any]:
    import pyarrow.parquet as pq

    parquet_file = pq.ParquetFile(path)
    schema = parquet_file.schema_arrow
    columns = schema.names
    row_count = parquet_file.metadata.num_rows if parquet_file.metadata else None
    row_groups = parquet_file.metadata.num_row_groups if parquet_file.metadata else None
    warnings: list[str] = []
    if row_count == 0:
        warnings.append("zero_rows")

    timestamp_columns = [
        name
        for name in columns
        if any(token in name.lower() for token in ("date", "time", "timestamp", "period"))
    ][:4]
    sample_info: dict[str, Any] = {}
    if row_count and timestamp_columns:
        try:
            table = parquet_file.read_row_group(0, columns=timestamp_columns)
            sample = table.to_pandas()
            for column in sample.columns:
                values = sample[column].dropna()
                sample_info[column] = {
                    "sample_non_null": int(values.shape[0]),
                    "sample_min": str(values.min()) if not values.empty else None,
                    "sample_max": str(values.max()) if not values.empty else None,
                }
        except Exception as exc:
            warnings.append(f"timestamp_sample_failed:{type(exc).__name__}")

    return {
        "kind": "parquet",
        "rows": row_count,
        "row_groups": row_groups,
        "columns": columns,
        "timestamp_sample": sample_info,
        "warnings": warnings,
    }


def csv_profile(path: Path) -> dict[str, Any]:
    import pandas as pd

    warnings: list[str] = []
    try:
        sample = pd.read_csv(path, nrows=MAX_SAMPLE_ROWS)
    except Exception as exc:
        return {
            "kind": "csv",
            "rows": None,
            "columns": [],
            "sample_rows": 0,
            "warnings": [f"read_failed:{type(exc).__name__}"],
        }

    if sample.empty:
        warnings.append("zero_sample_rows")
    timestamp_info: dict[str, Any] = {}
    for column in sample.columns:
        if not any(token in column.lower() for token in ("date", "time", "timestamp", "period")):
            continue
        values = sample[column].dropna()
        timestamp_info[column] = {
            "sample_non_null": int(values.shape[0]),
            "sample_min": str(values.min()) if not values.empty else None,
            "sample_max": str(values.max()) if not values.empty else None,
        }

    return {
        "kind": "csv",
        "rows": None,
        "columns": list(sample.columns),
        "sample_rows": int(sample.shape[0]),
        "timestamp_sample": timestamp_info,
        "warnings": warnings,
    }


def json_profile(path: Path) -> dict[str, Any]:
    warnings: list[str] = []
    first = ""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            first = f.readline().strip()
    except Exception as exc:
        warnings.append(f"read_failed:{type(exc).__name__}")
    if not first and path.stat().st_size == 0:
        warnings.append("zero_bytes")
    return {
        "kind": "json",
        "rows": None,
        "columns": [],
        "sample_rows": 1 if first else 0,
        "warnings": warnings,
    }


def profile_file(path: Path) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
        warnings.append("stat_failed")
    if size == 0:
        warnings.append("zero_bytes")

    suffix = path.suffix.lower()
    try:
        if suffix == ".parquet":
            profile = parquet_profile(path)
        elif suffix == ".csv":
            profile = csv_profile(path)
        elif suffix in {".json", ".jsonl"}:
            profile = json_profile(path)
        else:
            profile = {"kind": suffix.lstrip(".") or "unknown", "rows": None, "columns": [], "warnings": []}
    except Exception as exc:
        profile = {
            "kind": suffix.lstrip(".") or "unknown",
            "rows": None,
            "columns": [],
            "warnings": [f"profile_failed:{type(exc).__name__}"],
        }

    profile_warnings = list(profile.get("warnings", []))
    return {
        "path": rel(path),
        "size_bytes": size,
        "folder_docs": doc_state(path.parent),
        **{k: v for k, v in profile.items() if k != "warnings"},
        "warnings": warnings + profile_warnings,
    }


def scan_roots(root_names: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files: list[Path] = []
    for name in root_names:
        root = ROOT / name
        if not root.exists():
            continue
        files.extend(path for path in sorted(root.rglob("*")) if path.is_file() and path.suffix.lower() in DATA_SUFFIXES)

    profiles = [profile_file(path) for path in files]
    warning_counts: dict[str, int] = {}
    for item in profiles:
        if not item["folder_docs"]["complete"]:
            warning_counts["missing_folder_docs"] = warning_counts.get("missing_folder_docs", 0) + 1
        for warning in item.get("warnings", []):
            key = warning.split(":", 1)[0]
            warning_counts[key] = warning_counts.get(key, 0) + 1

    summary = {
        "roots": root_names,
        "files_profiled": len(profiles),
        "total_bytes": sum(int(item.get("size_bytes") or 0) for item in profiles),
        "warning_counts": dict(sorted(warning_counts.items())),
        "files_with_warnings": sum(
            1 for item in profiles if item.get("warnings") or not item["folder_docs"]["complete"]
        ),
    }
    return profiles, summary


def write_markdown(machine: str, payload: dict[str, Any]) -> None:
    path = ROOT / "_logs" / "supervisor_reports" / f"stage16_preflight_validation_{machine}.md"
    lines = [
        f"# Stage 1.6 Preflight Validation - {machine}",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Roots: {', '.join(payload['summary']['roots'])}",
        f"- Files profiled: {payload['summary']['files_profiled']}",
        f"- Files with warnings: {payload['summary']['files_with_warnings']}",
        f"- Warning counts: {json.dumps(payload['summary']['warning_counts'], sort_keys=True)}",
        "",
        "## Warning Examples",
        "",
    ]
    examples = [
        item
        for item in payload["profiles"]
        if item.get("warnings") or not item["folder_docs"]["complete"]
    ][:40]
    if not examples:
        lines.append("- No warnings detected in this preflight scan.")
    for item in examples:
        doc_warning = ""
        if not item["folder_docs"]["complete"]:
            doc_warning = f"; missing docs={','.join(item['folder_docs']['missing'])}"
        warnings = ",".join(item.get("warnings", [])) or "none"
        lines.append(f"- {item['path']}: warnings={warnings}{doc_warning}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Project 3 Stage 1.6 preflight validation worker")
    parser.add_argument("--machine", required=True)
    parser.add_argument("--roots", required=True, help="Comma-separated root folders to scan")
    args = parser.parse_args()

    roots = [item.strip() for item in args.roots.split(",") if item.strip()]
    log(args.machine, f"START stage16 preflight validation roots={','.join(roots)}")
    notify(
        args.machine,
        "start",
        f"Project 3 {args.machine} Stage 1.6 preflight started",
        "\n".join(
            [
                f"machine: {args.machine}",
                "work_plan_stage: Stage 1.6 preflight validation",
                f"task: validate roots {', '.join(roots)}",
                "status: started",
                "expected_deliverable: _metadata/stage16_preflight_validation_<machine>.json",
            ]
        ),
    )

    profiles, summary = scan_roots(roots)
    payload = {
        "generated_at": utc_now(),
        "machine": args.machine,
        "stage": "Stage 1.6 preflight validation",
        "formal_stage_status": "preflight_only_waiting_for_stage_1_4_and_1_5",
        "summary": summary,
        "profiles": profiles,
    }
    out = ROOT / "_metadata" / f"stage16_preflight_validation_{args.machine}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.machine, payload)

    notify(
        args.machine,
        "finish",
        f"Project 3 {args.machine} Stage 1.6 preflight finished",
        "\n".join(
            [
                f"machine: {args.machine}",
                "work_plan_stage: Stage 1.6 preflight validation",
                "status: finished",
                f"deliverable_path: {rel(out)}",
                f"validation_evidence: files_profiled={summary['files_profiled']} warnings={summary['files_with_warnings']}",
                "recommended_next_action: supervisor aggregates preflight report and dispatches remaining checks",
                "needs_codex: false unless warnings are high-severity or ambiguous",
            ]
        ),
    )
    log(
        args.machine,
        f"DONE stage16 preflight validation files={summary['files_profiled']} warnings={summary['files_with_warnings']}",
    )


if __name__ == "__main__":
    main()
