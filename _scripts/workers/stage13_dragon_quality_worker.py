from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from stage13_common import ROOT, log_line


LOG = ROOT / "_logs" / "dragon" / "stage13_dragon_quality_worker.log"
REPORT = ROOT / "_logs" / "dragon" / "stage13_crypto_quality_report.md"
SUMMARY = ROOT / "_logs" / "dragon" / "stage13_crypto_quality_summary.json"
EXCLUSIONS = ROOT / "_logs" / "dragon" / "stage13_crypto_exclusions.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def notify(event: str, title: str, message: str) -> None:
    script = ROOT / "_scripts" / "telegram_notify.py"
    if not script.exists():
        return
    subprocess.run(
        ["python", str(script), "--event", event, "--title", title, "--message", message, "--min-interval-minutes", "10"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
    )


def table_summary(path: Path) -> dict:
    try:
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
        elif path.suffix == ".csv":
            df = pd.read_csv(path)
        else:
            return {"path": str(path.relative_to(ROOT)), "status": "skipped_suffix"}
    except Exception as exc:
        return {"path": str(path.relative_to(ROOT)), "status": "read_error", "error": str(exc)[:180]}
    checks = {
        "path": str(path.relative_to(ROOT)),
        "status": "ok",
        "rows": int(len(df)),
        "columns": list(map(str, df.columns)),
    }
    lower = {str(c).lower(): c for c in df.columns}
    if {"open", "high", "low", "close"}.issubset(lower):
        o = pd.to_numeric(df[lower["open"]], errors="coerce")
        h = pd.to_numeric(df[lower["high"]], errors="coerce")
        l = pd.to_numeric(df[lower["low"]], errors="coerce")
        c = pd.to_numeric(df[lower["close"]], errors="coerce")
        checks["ohlc_null_rows"] = int((o.isna() | h.isna() | l.isna() | c.isna()).sum())
        checks["ohlc_order_violations"] = int(((h < l) | (h < o) | (h < c) | (l > o) | (l > c)).sum())
    for time_col in ["datetime", "timestamp", "open_time", "fundingTime"]:
        if time_col in df.columns:
            checks["duplicate_time_rows"] = int(df[time_col].duplicated().sum())
            break
    return checks


def read_exclusions() -> list[dict]:
    try:
        payload = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    except Exception:
        return []
    exclusions = payload.get("exclusions", [])
    return exclusions if isinstance(exclusions, list) else []


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_line(LOG, "START dragon crypto quality worker")
    notify(
        "dragon-quality-started",
        "Project 3 Dragon quality audit started",
        "Stage 1.3 validation follow-up: checking crypto OHLC/funding files for read errors, empty files, duplicate timestamps, null OHLC, and OHLC order violations.",
    )
    crypto = ROOT / "market_data" / "crypto"
    paths = sorted([*crypto.rglob("*.parquet"), *crypto.rglob("*.csv")])
    results = [table_summary(path) for path in paths]
    bad = [
        row for row in results
        if row.get("status") != "ok"
        or row.get("rows", 1) == 0
        or row.get("ohlc_null_rows", 0) > 0
        or row.get("ohlc_order_violations", 0) > 0
        or row.get("duplicate_time_rows", 0) > 0
    ]
    payload = {
        "generated_at": utc_now(),
        "files_checked": len(results),
        "anomaly_count": len(bad),
        "anomalies": bad[:200],
        "documented_exclusion_count": len(read_exclusions()),
        "exclusion_report": str(EXCLUSIONS.relative_to(ROOT)) if EXCLUSIONS.exists() else "",
    }
    SUMMARY.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Stage 1.3 Dragon Crypto Quality Report\n\n"
        f"Generated: {payload['generated_at']}\n\n"
        f"- Files checked: {payload['files_checked']}\n"
        f"- Anomaly count: {payload['anomaly_count']}\n\n"
        f"- Documented no-data exclusions: {payload['documented_exclusion_count']}\n\n"
        "Anomalies are listed in `stage13_crypto_quality_summary.json`. Documented Binance no-data exclusions are listed in `stage13_crypto_exclusions.json`.\n",
        encoding="utf-8",
    )
    log_line(LOG, f"DONE dragon crypto quality worker files={len(results)} anomalies={len(bad)}")
    notify(
        "dragon-quality-done",
        "Project 3 Dragon quality audit complete",
        f"Stage 1.3 crypto quality audit finished. Files checked: {payload['files_checked']}. Anomalies: {payload['anomaly_count']}. Deliverables: _logs/dragon/stage13_crypto_quality_report.md and stage13_crypto_quality_summary.json.",
    )


if __name__ == "__main__":
    main()
