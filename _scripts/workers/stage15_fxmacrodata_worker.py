from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, load_env, log_line, write_docs, write_table


BASE_URL = "https://fxmacrodata.com/api/v1"
LOG = ROOT / "_logs" / "omega" / "stage15_fxmacrodata_worker.log"
SUMMARY_PATH = ROOT / "_metadata" / "stage15_fxmacrodata_acquisition.json"
SUMMARY_MD = ROOT / "_logs" / "supervisor_reports" / "stage15_fxmacrodata_acquisition.md"

DEFAULT_CURRENCIES = [
    "usd",
    "eur",
    "gbp",
    "jpy",
    "aud",
    "cad",
    "chf",
    "nzd",
    "cny",
    "sgd",
    "sek",
    "dkk",
    "pln",
    "brl",
    "hkd",
    "nok",
    "krw",
    "mxn",
]


def safe_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {str(exc)[:260]}"
    return re.sub(r"([?&]api_key=)[^&\s]+", r"\1<redacted>", text)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_json(path: str, api_key: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query = dict(params or {})
    if api_key:
        query["api_key"] = api_key
    url = f"{BASE_URL}/{path.lstrip('/')}"
    response = requests.get(url, params=query, timeout=45)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Unexpected payload type for {path}: {type(payload).__name__}")
    return payload


def normalize_epoch_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in ["announcement_datetime", "announcement_datetime_local"]:
        if column in out.columns:
            numeric = pd.to_numeric(out[column], errors="coerce")
            out[f"{column}_utc"] = pd.to_datetime(numeric, unit="s", utc=True, errors="coerce")
    return out


def catalogue_indicators(payload: dict[str, Any]) -> list[str]:
    data = payload.get("data")
    if isinstance(data, list):
        values = []
        for row in data:
            if isinstance(row, dict):
                candidate = row.get("indicator") or row.get("release") or row.get("slug")
                if candidate:
                    values.append(str(candidate))
        return sorted(set(values))
    return sorted(k for k, v in payload.items() if isinstance(v, (dict, list, str, int, float, bool, type(None))))


def fetch_currency(currency: str, api_key: str, max_indicators: int | None = None) -> dict[str, Any]:
    log_line(LOG, f"fetch FXMacroData currency={currency}")
    catalogue_payload = request_json(f"data_catalogue/{currency}", api_key)
    indicators = catalogue_indicators(catalogue_payload)
    if max_indicators is not None:
        indicators = indicators[:max_indicators]

    calendar_payload = request_json(f"calendar/{currency}", api_key)
    calendar_rows = calendar_payload.get("data", [])
    if not isinstance(calendar_rows, list):
        calendar_rows = []
    calendar_df = normalize_epoch_columns(pd.DataFrame(calendar_rows))
    if not calendar_df.empty:
        calendar_df.insert(0, "currency", currency.upper())

    announcement_frames: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    for indicator in indicators:
        try:
            payload = request_json(f"announcements/{currency}/{indicator}", api_key)
            rows = payload.get("data", [])
            if not isinstance(rows, list) or not rows:
                continue
            df = normalize_epoch_columns(pd.DataFrame(rows))
            df.insert(0, "indicator", indicator)
            df.insert(0, "currency", currency.upper())
            announcement_frames.append(df)
            time.sleep(0.05)
        except Exception as exc:
            error = safe_error(exc)
            failures.append({"indicator": indicator, "error": error})
            log_line(LOG, f"FXMacroData indicator failed currency={currency} indicator={indicator} error={error}")

    announcements_df = pd.concat(announcement_frames, ignore_index=True, sort=False) if announcement_frames else pd.DataFrame()
    if not announcements_df.empty:
        sort_cols = [col for col in ["currency", "indicator", "date", "announcement_datetime"] if col in announcements_df.columns]
        announcements_df = announcements_df.drop_duplicates()
        if sort_cols:
            announcements_df = announcements_df.sort_values(sort_cols).reset_index(drop=True)
    return {
        "currency": currency,
        "indicator_count": len(indicators),
        "calendar": calendar_df,
        "announcements": announcements_df,
        "failures": failures,
    }


def write_outputs(results: list[dict[str, Any]]) -> dict[str, Any]:
    calendar_frames = [r["calendar"] for r in results if isinstance(r.get("calendar"), pd.DataFrame) and not r["calendar"].empty]
    announcement_frames = [r["announcements"] for r in results if isinstance(r.get("announcements"), pd.DataFrame) and not r["announcements"].empty]

    calendar_df = pd.concat(calendar_frames, ignore_index=True, sort=False) if calendar_frames else pd.DataFrame()
    announcements_df = pd.concat(announcement_frames, ignore_index=True, sort=False) if announcement_frames else pd.DataFrame()
    if not calendar_df.empty:
        sort_cols = [col for col in ["currency", "announcement_datetime", "release"] if col in calendar_df.columns]
        calendar_df = calendar_df.drop_duplicates()
        if sort_cols:
            calendar_df = calendar_df.sort_values(sort_cols).reset_index(drop=True)
    if not announcements_df.empty:
        sort_cols = [col for col in ["currency", "indicator", "date", "announcement_datetime"] if col in announcements_df.columns]
        announcements_df = announcements_df.drop_duplicates()
        if sort_cols:
            announcements_df = announcements_df.sort_values(sort_cols).reset_index(drop=True)

    calendar_folder = ROOT / "economic_calendar" / "scheduled_events" / "fxmacrodata"
    announcements_folder = ROOT / "economic_calendar" / "release_actuals" / "fxmacrodata"
    calendar_path = calendar_folder / "release_calendar.parquet"
    announcements_path = announcements_folder / "announcements.parquet"

    written: list[Path] = []
    if not calendar_df.empty:
        write_table(calendar_df, calendar_path)
        written.append(calendar_path if calendar_path.exists() else calendar_path.with_suffix(".csv"))
        write_docs(
            calendar_folder,
            "FXMacroData",
            "Upcoming macro release calendar with announcement timestamps for supported currencies.",
            written[-1:],
        )
        append_acquisition_log({
            "timestamp": utc_now(),
            "source": "FXMacroData",
            "dataset": "scheduled_events_fxmacrodata",
            "status": "ok",
            "path": str(written[-1].relative_to(ROOT)),
            "notes": f"rows={len(calendar_df)} currencies={calendar_df['currency'].nunique() if 'currency' in calendar_df else 0}",
        })

    if not announcements_df.empty:
        write_table(announcements_df, announcements_path)
        written.append(announcements_path if announcements_path.exists() else announcements_path.with_suffix(".csv"))
        write_docs(
            announcements_folder,
            "FXMacroData",
            "Historical macro announcement values with no-lookahead announcement timestamps. Consensus/forecast fields are not present unless supplied by the provider payload.",
            written[-1:],
        )
        append_acquisition_log({
            "timestamp": utc_now(),
            "source": "FXMacroData",
            "dataset": "release_actuals_fxmacrodata",
            "status": "ok",
            "path": str(written[-1].relative_to(ROOT)),
            "notes": f"rows={len(announcements_df)} currencies={announcements_df['currency'].nunique() if 'currency' in announcements_df else 0}",
        })

    all_failures = [
        {"currency": r["currency"], **failure}
        for r in results
        for failure in r.get("failures", [])
    ]
    summary = {
        "generated_at": utc_now(),
        "stage": "Stage 1.5 paid/credentialed macro data acquisition",
        "provider": "FXMacroData",
        "status": "ok" if written else "failed",
        "calendar_rows": int(len(calendar_df)),
        "announcement_rows": int(len(announcements_df)),
        "currencies_requested": [r["currency"].upper() for r in results],
        "currencies_with_calendar": sorted(calendar_df["currency"].dropna().unique().tolist()) if "currency" in calendar_df else [],
        "currencies_with_announcements": sorted(announcements_df["currency"].dropna().unique().tolist()) if "currency" in announcements_df else [],
        "columns": {
            "calendar": list(calendar_df.columns),
            "announcements": list(announcements_df.columns),
        },
        "consensus_or_forecast_columns_present": [
            col for col in announcements_df.columns if str(col).lower() in {"consensus", "forecast", "estimate", "surprise"}
        ],
        "failures": all_failures[:200],
        "failure_count": len(all_failures),
        "outputs": [str(path.relative_to(ROOT)) for path in written],
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_summary_markdown(summary)
    return summary


def write_summary_markdown(summary: dict[str, Any]) -> None:
    lines = [
        "# Stage 1.5 FXMacroData Acquisition",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Provider: {summary['provider']}",
        f"- Status: {summary['status']}",
        f"- Calendar rows: {summary['calendar_rows']}",
        f"- Announcement rows: {summary['announcement_rows']}",
        f"- Currencies with calendar: {', '.join(summary['currencies_with_calendar'])}",
        f"- Currencies with announcements: {', '.join(summary['currencies_with_announcements'])}",
        f"- Consensus/forecast columns present: {', '.join(summary['consensus_or_forecast_columns_present']) if summary['consensus_or_forecast_columns_present'] else 'none'}",
        f"- Provider endpoint failures: {summary['failure_count']}",
        "",
        "## Outputs",
        "",
    ]
    for output in summary["outputs"]:
        lines.append(f"- `{output}`")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- FXMacroData improves no-lookahead macro timing because rows include announcement timestamps.",
            "- It does not currently provide consensus/forecast/surprise fields in the acquired payload, so it does not fully replace Trading Economics or FXStreet Calendar API consensus-surprise data.",
            "- Provider 503/404 endpoint failures are recorded in the JSON summary for supervisor review; successful rows are preserved.",
        ]
    )
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch FXMacroData paid macro calendar/announcement data.")
    parser.add_argument("--currencies", nargs="*", default=DEFAULT_CURRENCIES)
    parser.add_argument("--max-indicators", type=int, default=None)
    args = parser.parse_args()

    load_env()
    api_key = os.environ.get("FXMACRODATA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("FXMACRODATA_API_KEY is not available in _metadata/.env")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_line(LOG, f"START FXMacroData acquisition currencies={','.join(args.currencies)}")
    results = []
    for currency in args.currencies:
        try:
            results.append(fetch_currency(currency.lower(), api_key, args.max_indicators))
        except Exception as exc:
            error = safe_error(exc)
            log_line(LOG, f"FXMacroData currency failed currency={currency} error={error}")
            results.append({"currency": currency.lower(), "calendar": pd.DataFrame(), "announcements": pd.DataFrame(), "failures": [{"indicator": "*currency*", "error": error}]})
    summary = write_outputs(results)
    log_line(LOG, f"DONE FXMacroData acquisition status={summary['status']} calendar_rows={summary['calendar_rows']} announcement_rows={summary['announcement_rows']} failures={summary['failure_count']}")


if __name__ == "__main__":
    main()
