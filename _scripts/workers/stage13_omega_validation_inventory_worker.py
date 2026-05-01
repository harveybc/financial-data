from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
LOG = ROOT / "_logs" / "omega" / "stage13_validation_inventory_worker.log"
JSON_OUT = ROOT / "_metadata" / "stage13_inventory.json"
JSON_OUT_CANONICAL = ROOT / "_metadata" / "STAGE_1_3_INVENTORY.json"
MD_OUT = ROOT / "_logs" / "supervisor_reports" / "stage13_validation_inventory.md"

SCAN_ROOTS = [
    "market_data",
    "macro_economic",
    "alternative_data",
    "reference_data",
    "economic_calendar",
]
DATA_SUFFIXES = {".parquet", ".csv", ".json", ".jsonl", ".zip"}
DOC_NAMES = {"README.md", "data_dictionary.md", "provenance.json"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def file_inventory() -> dict[str, Any]:
    by_root: dict[str, dict[str, Any]] = {}
    data_dirs: set[Path] = set()
    total_files = 0
    total_bytes = 0

    for name in SCAN_ROOTS:
        root = ROOT / name
        suffixes: Counter[str] = Counter()
        files = 0
        bytes_ = 0
        if root.exists():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                files += 1
                total_files += 1
                suffixes[path.suffix.lower() or "<none>"] += 1
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                bytes_ += size
                total_bytes += size
                if path.suffix.lower() in DATA_SUFFIXES and path.name not in DOC_NAMES:
                    data_dirs.add(path.parent)
        by_root[name] = {
            "exists": root.exists(),
            "files": files,
            "bytes": bytes_,
            "suffix_counts": dict(sorted(suffixes.items())),
        }

    missing_docs = []
    for folder in sorted(data_dirs):
        missing = sorted(name for name in DOC_NAMES if not (folder / name).exists())
        if missing:
            missing_docs.append({"path": rel(folder), "missing": missing})

    return {
        "roots": by_root,
        "totals": {"files": total_files, "bytes": total_bytes, "data_directories": len(data_dirs)},
        "documentation": {
            "data_directories_checked": len(data_dirs),
            "directories_missing_docs": len(missing_docs),
            "missing_doc_examples": missing_docs[:80],
        },
    }


def acquisition_summary() -> dict[str, Any]:
    path = ROOT / "_metadata" / "acquisition_log.csv"
    if not path.exists():
        return {"exists": False, "rows": 0}

    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    def normalized_status(row: dict[str, str]) -> str:
        value = (row.get("status") or "").strip()
        lower = value.lower()
        if lower in {"ok", "success", "done", "failed", "error", "skipped", "partial"}:
            return lower
        if "/" in value or value.endswith((".parquet", ".csv", ".json", ".zip")):
            return "schema_shifted_or_malformed"
        return value or "<missing>"

    by_status = Counter(normalized_status(row) for row in rows)
    by_source = Counter(row.get("source", "<missing>") for row in rows)
    failed_or_gap = [
        row for row in rows if normalized_status(row) not in {"ok", "success", "done"}
    ]
    return {
        "exists": True,
        "rows": len(rows),
        "latest_timestamp": rows[-1].get("timestamp") if rows else "",
        "status_counts": dict(by_status.most_common()),
        "top_sources": dict(by_source.most_common(30)),
        "non_ok_rows": failed_or_gap[-40:],
        "recent_rows": rows[-20:],
    }


def gap_notes() -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    patterns = ("gap", "gaps", "escalation", "handoff")
    ignored_parts = {".git", "__pycache__"}
    for path in sorted(ROOT.rglob("*.md")):
        if ignored_parts.intersection(path.parts):
            continue
        lower_name = path.name.lower()
        if not any(pattern in lower_name for pattern in patterns):
            continue
        try:
            lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
        except OSError:
            lines = []
        summary = next((line for line in lines if line and not line.startswith("#")), "")
        notes.append({"path": rel(path), "summary": summary[:240]})
    return notes[:100]


def dispatch_snapshot() -> dict[str, Any]:
    path = ROOT / "_logs" / "supervisor_reports" / "autonomous_dispatch_report.json"
    if not path.exists():
        return {"exists": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"exists": True, "error": str(exc)}
    return {
        "exists": True,
        "generated_at": payload.get("generated_at", ""),
        "decisions": payload.get("decisions", []),
        "anomalies": payload.get("anomalies", []),
    }


def improvement_suggestions(inventory: dict[str, Any], acquisition: dict[str, Any], dispatch: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    missing_docs = inventory["documentation"]["directories_missing_docs"]
    if missing_docs:
        suggestions.append(
            f"Backfill README/data_dictionary/provenance for {missing_docs} data directories after acquisition stabilizes."
        )
    if acquisition.get("non_ok_rows"):
        suggestions.append("Review non-ok acquisition_log rows and convert true provider limitations into Tier 4 handoffs.")
    if any(row.get("state") == "completed_idle" for row in dispatch.get("decisions", [])):
        suggestions.append("Treat completed_idle as available capacity and dispatch non-overlapping validation, sync, or acquisition slices.")
    if any(row.get("state") == "deferred_busy" for row in dispatch.get("decisions", [])):
        suggestions.append("Keep sync jobs deferred while workers are active, then sync immediately on the next idle tick.")
    suggestions.append("Every agent handoff should pass current stage, task, deliverable, evidence, anomalies, confidence, and context_to_pass_forward.")
    return suggestions


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Stage 1.3 Validation Inventory",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## File Counts",
        "",
        "| Root | Exists | Files | Size MB | Top suffixes |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for name, info in payload["inventory"]["roots"].items():
        suffixes = ", ".join(f"{k}:{v}" for k, v in list(info["suffix_counts"].items())[:8])
        lines.append(
            f"| {name} | {info['exists']} | {info['files']} | {info['bytes'] / 1024 / 1024:.1f} | {suffixes} |"
        )

    docs = payload["inventory"]["documentation"]
    lines.extend([
        "",
        "## Documentation Coverage",
        "",
        f"- Data directories checked: {docs['data_directories_checked']}",
        f"- Directories missing docs: {docs['directories_missing_docs']}",
    ])
    for item in docs["missing_doc_examples"][:20]:
        lines.append(f"- Missing {', '.join(item['missing'])}: {item['path']}")

    acq = payload["acquisition_log"]
    lines.extend([
        "",
        "## Acquisition Log",
        "",
        f"- Rows: {acq.get('rows', 0)}",
        f"- Latest timestamp: {acq.get('latest_timestamp', '')}",
        f"- Status counts: {json.dumps(acq.get('status_counts', {}), sort_keys=True)}",
    ])

    lines.extend(["", "## Known Gaps And Handoffs", ""])
    if payload["gap_notes"]:
        for note in payload["gap_notes"]:
            suffix = f" - {note['summary']}" if note["summary"] else ""
            lines.append(f"- {note['path']}{suffix}")
    else:
        lines.append("- No local gap notes found.")

    lines.extend(["", "## Active Dispatch Context", ""])
    dispatch = payload["dispatch"]
    for row in dispatch.get("decisions", []):
        lines.append(
            f"- {row.get('machine')}: {row.get('stage')} | {row.get('state')} | {row.get('deliverable')}"
        )
    if dispatch.get("anomalies"):
        lines.extend(["", "## Dispatch Anomalies", ""])
        for anomaly in dispatch["anomalies"]:
            lines.append(
                f"- {anomaly.get('severity')} {anomaly.get('category')} on {anomaly.get('machine')}: {anomaly.get('evidence')}"
            )

    lines.extend(["", "## Improvement Suggestions", ""])
    for suggestion in payload["improvement_suggestions"]:
        lines.append(f"- {suggestion}")

    MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    log("START omega validation/inventory worker")
    inventory = file_inventory()
    acquisition = acquisition_summary()
    gaps = gap_notes()
    dispatch = dispatch_snapshot()
    payload = {
        "generated_at": utc_now(),
        "stage": "Stage 1.3 Free Data Acquisition validation/inventory",
        "inventory": inventory,
        "acquisition_log": acquisition,
        "gap_notes": gaps,
        "dispatch": dispatch,
        "improvement_suggestions": improvement_suggestions(inventory, acquisition, dispatch),
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    JSON_OUT_CANONICAL.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload)
    log(
        "DONE omega validation/inventory worker "
        f"files={inventory['totals']['files']} data_dirs={inventory['totals']['data_directories']} "
        f"missing_doc_dirs={inventory['documentation']['directories_missing_docs']}"
    )


if __name__ == "__main__":
    main()
