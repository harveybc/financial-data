from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, load_env, log_line, write_docs, write_table


LOG = ROOT / "_logs" / "omega" / "stage13_economic_calendar_worker.log"
FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"

EVENTS = [
    {"name": "CPI YoY", "slug": "cpi_yoy", "fred_series": "CPIAUCSL", "transform": "yoy_pct_change"},
    {"name": "Core CPI YoY", "slug": "core_cpi_yoy", "fred_series": "CPILFESL", "transform": "yoy_pct_change"},
    {"name": "PCE Core YoY", "slug": "core_pce_yoy", "fred_series": "PCEPILFE", "transform": "yoy_pct_change"},
    {"name": "Nonfarm Payrolls MoM", "slug": "nonfarm_payrolls_mom", "fred_series": "PAYEMS", "transform": "month_over_month_diff"},
    {"name": "Unemployment Rate", "slug": "unemployment_rate", "fred_series": "UNRATE", "transform": "level"},
    {"name": "GDP QoQ Annualized", "slug": "gdp_qoq_annualized", "fred_series": "A191RL1Q225SBEA", "transform": "level"},
    {"name": "Fed Funds", "slug": "fed_funds", "fred_series": "FEDFUNDS", "transform": "level"},
    {"name": "10Y Treasury", "slug": "treasury_10y", "fred_series": "DGS10", "transform": "level"},
    {"name": "Initial Claims", "slug": "initial_claims", "fred_series": "ICSA", "transform": "level"},
    {"name": "Retail Sales", "slug": "retail_sales_mom", "fred_series": "RSAFS", "transform": "pct_change"},
]


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


def fred_observations(series_id: str) -> pd.DataFrame:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY is not available")
    r = requests.get(
        FRED_OBS_URL,
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "observation_start": "1990-01-01",
            "observation_end": "2025-12-31",
        },
        timeout=60,
    )
    r.raise_for_status()
    rows = r.json().get("observations", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["actual"] = pd.to_numeric(df["value"].replace(".", pd.NA), errors="coerce")
    return df[["date", "actual"]].dropna(subset=["date"])


def transform_actuals(df: pd.DataFrame, transform: str) -> pd.Series:
    values = df["actual"]
    if transform == "yoy_pct_change":
        return values.pct_change(12) * 100.0
    if transform == "pct_change":
        return values.pct_change() * 100.0
    if transform == "month_over_month_diff":
        return values.diff()
    return values


def fetch_release_actuals() -> None:
    for event in EVENTS:
        try:
            folder = ROOT / "economic_calendar" / "release_actuals" / event["slug"]
            out = folder / "actuals.parquet"
            if out.exists() or out.with_suffix(".csv").exists():
                log_line(LOG, f"skip existing economic calendar {event['slug']}")
                continue
            log_line(LOG, f"fetch FRED release actual {event['fred_series']} {event['slug']}")
            df = fred_observations(event["fred_series"])
            if df.empty:
                log_line(LOG, f"empty FRED release actual {event['fred_series']}")
                continue
            df["event_name"] = event["name"]
            df["fred_series"] = event["fred_series"]
            df["transform"] = event["transform"]
            df["transformed_actual"] = transform_actuals(df, event["transform"])
            df["consensus_estimate"] = pd.NA
            df["surprise"] = pd.NA
            df["source_note"] = "FRED actuals acquired; consensus/scheduled estimates require a supported free calendar source."
            save(
                df,
                folder,
                "actuals.parquet",
                "FRED",
                f"Economic release actuals for {event['name']} from FRED; consensus fields are intentionally blank until a free scheduled-events source is validated.",
            )
        except Exception as exc:
            log_line(LOG, f"economic calendar event failed {event['slug']} {event['fred_series']}: {exc}")
            continue


def write_calendar_gap_note() -> None:
    folder = ROOT / "economic_calendar" / "scheduled_events"
    folder.mkdir(parents=True, exist_ok=True)
    note = folder / "stage13_scheduled_events_gap.md"
    note.write_text(
        """# Stage 1.3 Scheduled Economic Events Gap

Stage: 1.3 Free Data Acquisition
Agent: Omega economic-calendar worker

FRED release actuals were acquired for high-impact events. Consensus estimates and forward scheduled-event calendars remain blank because the currently planned free sources require either a stable free endpoint validation or manual subscription/source decision.

Autonomous next action: keep actuals as valid Stage 1.3 deliverables, and route consensus/scheduled-event source choice to Stage 1.4/validation if no stable free endpoint is confirmed.
""",
        encoding="utf-8",
    )


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    load_env()
    log_line(LOG, "START omega economic calendar worker")
    for fn in [fetch_release_actuals, write_calendar_gap_note]:
        try:
            fn()
        except Exception as exc:
            log_line(LOG, f"ERROR {fn.__name__}: {exc}")
    log_line(LOG, "DONE omega economic calendar worker all events attempted")


if __name__ == "__main__":
    main()
