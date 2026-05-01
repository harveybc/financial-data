from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, log_line, polite_sleep, write_docs, write_table


LOG = ROOT / "_logs" / "gamma" / "stage13_supplemental_worker.log"


def save(df: pd.DataFrame, folder: Path, filename: str, source: str, description: str) -> None:
    out = folder / filename
    write_table(df, out)
    actual = out if out.exists() else out.with_suffix(".csv")
    write_docs(folder, source, description, [actual])
    append_acquisition_log({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "dataset": folder.name,
        "status": "ok",
        "path": str(actual.relative_to(ROOT)),
        "notes": f"rows={len(df)}",
    })


def fetch_treasury_average_rates() -> None:
    folder = ROOT / "macro_economic" / "yield_curves" / "treasury_average_interest_rates"
    out = folder / "average_interest_rates.parquet"
    if out.exists() or out.with_suffix(".csv").exists():
        return
    log_line(LOG, "fetch Treasury average interest rates")
    rows = []
    page = 1
    while True:
        r = requests.get(
            "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates",
            params={"page[number]": page, "page[size]": 10000, "sort": "record_date"},
            timeout=60,
        )
        r.raise_for_status()
        payload = r.json()
        batch = payload.get("data", [])
        rows.extend(batch)
        if page >= int(payload.get("meta", {}).get("total-pages", page)):
            break
        page += 1
        polite_sleep(0.1)
    save(pd.DataFrame(rows), folder, "average_interest_rates.parquet", "US Treasury FiscalData", "Average interest rates on U.S. Treasury securities")


def fetch_bls_public_series() -> None:
    series = ["CUUR0000SA0", "LNS14000000", "CES0000000001", "CES0500000003"]
    folder = ROOT / "macro_economic" / "bls"
    log_line(LOG, "fetch BLS public series")
    r = requests.post(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        json={"seriesid": series, "startyear": "2000", "endyear": "2025"},
        timeout=60,
    )
    r.raise_for_status()
    payload = r.json()
    rows = []
    for item in payload.get("Results", {}).get("series", []):
        sid = item.get("seriesID")
        for obs in item.get("data", []):
            row = {"series_id": sid, **obs}
            rows.append(row)
    save(pd.DataFrame(rows), folder, "public_series.parquet", "BLS Public API", "Selected BLS public macro series")


def write_supplemental_gap_note() -> None:
    path = ROOT / "_logs" / "gamma" / "stage13_supplemental_gaps.md"
    path.write_text(
        """# Gamma Stage 1.3 Supplemental Gaps

- Stage: 1.3 Free Data Acquisition
- Agent: Gamma Hermes/Gemma + supplemental Python worker
- CoinMetrics Community: API returned 403/400 for requested metric bundle. Logged as data-source anomaly.
- FINRA short interest: requires more source-specific implementation/validation than this quick supplemental slice; keep for Stage 1.3 validation follow-up.
- OECD: public API shape needs catalog-specific indicator mapping; keep for Stage 1.3 validation follow-up.
- Current action: use successfully acquired FRED, Blockchain.com, mempool.space, DeFiLlama, SEC, Treasury, and BLS outputs.
""",
        encoding="utf-8",
    )


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_line(LOG, "START gamma supplemental worker")
    for fn in [fetch_treasury_average_rates, fetch_bls_public_series, write_supplemental_gap_note]:
        try:
            fn()
        except Exception as exc:
            log_line(LOG, f"ERROR {fn.__name__}: {exc}")
    log_line(LOG, "DONE gamma supplemental worker")


if __name__ == "__main__":
    main()
