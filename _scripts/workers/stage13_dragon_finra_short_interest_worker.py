from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, log_line, polite_sleep, write_docs, write_table


LOG = ROOT / "_logs" / "dragon" / "stage13_finra_short_interest_worker.log"
SUMMARY = ROOT / "_logs" / "dragon" / "stage13_finra_short_interest_summary.json"
FINRA_URL = "https://api.finra.org/data/group/otcmarket/name/consolidatedShortInterest"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Project3 financial-data research",
}


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


def fetch_consolidated_short_interest() -> pd.DataFrame:
    rows: list[dict] = []
    limit = 5000
    offset = 0
    while True:
        payload = {
            "limit": limit,
            "offset": offset,
            "dateRangeFilters": [
                {"fieldName": "settlementDate", "startDate": "2025-01-01", "endDate": "2025-12-31"}
            ],
        }
        r = requests.post(FINRA_URL, headers=HEADERS, json=payload, timeout=60)
        if r.status_code == 204:
            break
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        log_line(LOG, f"FINRA consolidated short interest offset={offset} rows_total={len(rows)}")
        if len(batch) < limit:
            break
        offset += limit
        polite_sleep(0.2)
    return pd.DataFrame(rows)


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_line(LOG, "START dragon FINRA consolidated short-interest worker")
    notify(
        "dragon-finra-short-interest-started",
        "Project 3 Dragon FINRA worker started",
        "Stage 1.3 Task 1.3.M: fetching FINRA consolidated biweekly short-interest rows for 2025 via the public Query API.",
    )
    folder = ROOT / "alternative_data" / "short_interest" / "finra_consolidated_short_interest"
    out = folder / "2025.parquet"
    if out.exists() or out.with_suffix(".csv").exists():
        log_line(LOG, "skip existing FINRA consolidated short-interest 2025")
        summary = {"rows": -1, "skipped_existing": True}
    else:
        df = fetch_consolidated_short_interest()
        if df.empty:
            summary = {"rows": 0, "status": "empty"}
            (folder / "stage13_finra_consolidated_gap.md").parent.mkdir(parents=True, exist_ok=True)
            (folder / "stage13_finra_consolidated_gap.md").write_text(
                "# Stage 1.3 FINRA Consolidated Short-Interest Gap\n\n"
                "The public FINRA consolidatedShortInterest Query API returned no rows for the 2025 date range.\n",
                encoding="utf-8",
            )
        else:
            if "settlementDate" in df.columns:
                df["settlementDate"] = pd.to_datetime(df["settlementDate"], errors="coerce")
            for col in [
                "currentShortPositionQuantity",
                "previousShortPositionQuantity",
                "averageDailyVolumeQuantity",
                "daysToCoverQuantity",
                "changePercent",
                "changePreviousNumber",
            ]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            write_table(df, out)
            actual = out if out.exists() else out.with_suffix(".csv")
            write_docs(
                folder,
                "FINRA Query API consolidatedShortInterest",
                "FINRA consolidated biweekly short-interest data for 2025. This directly addresses Stage 1.3.M more closely than Reg SHO daily short-sale volume.",
                [actual],
            )
            append_acquisition_log({
                "timestamp": utc_now(),
                "source": "FINRA Query API consolidatedShortInterest",
                "dataset": "finra_consolidated_short_interest",
                "status": "ok",
                "path": str(actual.relative_to(ROOT)),
                "notes": f"rows={len(df)}",
            })
            summary = {
                "rows": int(len(df)),
                "settlement_dates": int(df["settlementDate"].nunique()) if "settlementDate" in df.columns else 0,
                "symbols": int(df["symbolCode"].nunique()) if "symbolCode" in df.columns else 0,
            }
    SUMMARY.write_text(json.dumps({"generated_at": utc_now(), "summary": summary}, indent=2) + "\n", encoding="utf-8")
    log_line(LOG, f"DONE dragon FINRA consolidated short-interest worker {json.dumps(summary, sort_keys=True)}")
    notify(
        "dragon-finra-short-interest-done",
        "Project 3 Dragon FINRA worker complete",
        f"Stage 1.3 Task 1.3.M finished. Deliverable: alternative_data/short_interest/finra_consolidated_short_interest/2025.parquet. Summary: {json.dumps(summary, sort_keys=True)}.",
    )


if __name__ == "__main__":
    main()
