from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
BASE = ROOT / "alternative_data" / "short_interest" / "finra_regsho_daily"
LOG = ROOT / "_logs" / "gamma" / "stage16_finra_regsho_dedup_worker.log"
REPORT = ROOT / "_logs" / "supervisor_reports" / "stage16_finra_regsho_dedup.md"
SUMMARY = ROOT / "_metadata" / "stage16_finra_regsho_dedup.json"


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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def update_provenance(folder: Path, data_file: Path, duplicate_rows_removed: int) -> None:
    path = folder / "provenance.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {
            "source": "FINRA Reg SHO Daily Short Sale Volume",
            "description": f"FINRA Reg SHO daily short sale volume for {folder.name.upper()}, 2025.",
            "files": [],
        }
    payload["stage16_quality_cleanup"] = {
        "cleaned_at": utc_now(),
        "operation": "drop exact duplicate rows",
        "duplicate_rows_removed": duplicate_rows_removed,
        "reason": "Stage 1.6 quality validation detected exact duplicate rows across all columns.",
    }
    payload["files"] = [{"path": rel(data_file), "sha256": sha256_file(data_file)}]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    log("START stage16 FINRA Reg SHO dedup worker")
    results = []
    for venue in ("cnms", "fnsq", "fnyx"):
        folder = BASE / venue
        path = folder / "2025_daily_short_volume.parquet"
        if not path.exists():
            results.append({"venue": venue, "status": "missing", "path": rel(path)})
            continue
        df = pd.read_parquet(path)
        before = int(df.shape[0])
        cleaned = df.drop_duplicates().reset_index(drop=True)
        removed = before - int(cleaned.shape[0])
        if removed:
            cleaned.to_parquet(path, index=False)
            update_provenance(folder, path, removed)
        results.append(
            {
                "venue": venue,
                "status": "cleaned" if removed else "no_duplicates",
                "path": rel(path),
                "rows_before": before,
                "rows_after": int(cleaned.shape[0]),
                "duplicate_rows_removed": removed,
            }
        )
        log(f"{venue} duplicate_rows_removed={removed}")

    payload = {
        "generated_at": utc_now(),
        "stage": "Stage 1.6 quality validation follow-up",
        "status": "complete",
        "results": results,
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage 1.6 FINRA Reg SHO Deduplication",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "Exact duplicate rows were removed from FINRA Reg SHO daily short-volume files. This does not collapse panel rows that legitimately share a date.",
        "",
        "| Venue | Status | Rows Before | Rows After | Removed |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in results:
        lines.append(
            f"| {row['venue']} | {row['status']} | {row.get('rows_before', 0)} | {row.get('rows_after', 0)} | {row.get('duplicate_rows_removed', 0)} |"
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log("DONE stage16 FINRA Reg SHO dedup worker")


if __name__ == "__main__":
    main()
