from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
ASSETS = ("btcusdt", "ethusdt", "btcusdt_perp", "eurusd", "usdjpy")
TIMEFRAMES = ("5m", "15m", "1h", "4h")
METHODS = ("lstm", "cnn")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def metadata_paths(method: str, asset: str, timeframe: str) -> list[Path]:
    return sorted((ROOT / "_metadata").glob(f"stage24_{method}_autoencoder_*_{asset}_{timeframe}.json"))


def inspect_job(method: str, asset: str, timeframe: str) -> dict[str, Any]:
    paths = metadata_paths(method, asset, timeframe)
    feature_path = ROOT / "features" / "trading_asset_features" / asset / timeframe / f"learned_{method}.parquet"
    return {
        "job_id": f"{method}:{asset}:{timeframe}",
        "status": "complete" if paths else "pending",
        "metadata_paths": [str(path.relative_to(ROOT)) for path in paths],
        "metadata_count": len(paths),
        "duplicate_metadata": len(paths) > 1,
        "feature_path": str(feature_path.relative_to(ROOT)),
        "feature_exists": feature_path.exists(),
        "feature_size_bytes": feature_path.stat().st_size if feature_path.exists() else 0,
    }


def write_outputs(machine: str, payload: dict[str, Any]) -> None:
    metadata = ROOT / "_metadata" / f"stage24_progress_audit_{machine}.json"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = ROOT / "_logs" / "supervisor_reports" / f"stage24_progress_audit_{machine}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage 2.4 Progress Audit",
        "",
        f"Generated: {payload['generated_at']}",
        f"Machine: {machine}",
        "",
        "## Summary",
        "",
        f"- Total jobs: {payload['jobs_total']}",
        f"- Complete jobs: {payload['jobs_complete']}",
        f"- Pending jobs: {payload['jobs_pending']}",
        f"- Duplicate metadata groups: {payload['duplicate_metadata_groups']}",
        "",
        "## Pending Jobs",
        "",
    ]
    if payload["pending_jobs"]:
        lines.extend(f"- `{job}`" for job in payload["pending_jobs"])
    else:
        lines.append("- none")
    lines.extend(["", "## Duplicate Metadata", ""])
    if payload["duplicate_metadata"]:
        for item in payload["duplicate_metadata"]:
            lines.append(f"- `{item['job_id']}`: {', '.join(item['metadata_paths'])}")
    else:
        lines.append("- none")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", default="omega")
    args = parser.parse_args()

    jobs = [inspect_job(method, asset, timeframe) for timeframe in TIMEFRAMES for method in METHODS for asset in ASSETS]
    pending = [job["job_id"] for job in jobs if job["status"] == "pending"]
    duplicates = [job for job in jobs if job["duplicate_metadata"]]
    payload: dict[str, Any] = {
        "generated_at": utc_now(),
        "stage": "Stage 2.4",
        "machine": args.machine,
        "jobs_total": len(jobs),
        "jobs_complete": len(jobs) - len(pending),
        "jobs_pending": len(pending),
        "pending_jobs": pending,
        "duplicate_metadata_groups": len(duplicates),
        "duplicate_metadata": duplicates,
        "jobs": jobs,
    }
    write_outputs(args.machine, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
