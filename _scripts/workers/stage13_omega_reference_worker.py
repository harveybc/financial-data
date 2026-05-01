from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, log_line, polite_sleep, write_docs, write_table


LOG = ROOT / "_logs" / "omega" / "stage13_reference_worker.log"


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


def fetch_cftc_disaggregated() -> None:
    raw_dir = ROOT / "alternative_data" / "cot_reports" / "cftc_disaggregated" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for year in range(2006, 2026):
        out = raw_dir / f"fut_disagg_txt_{year}.zip"
        if out.exists():
            downloaded.append(out)
            continue
        url = f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
        try:
            log_line(LOG, f"fetch CFTC disaggregated {year}")
            r = requests.get(url, timeout=60)
            if r.status_code == 404:
                log_line(LOG, f"CFTC missing {year}")
                continue
            r.raise_for_status()
            out.write_bytes(r.content)
            downloaded.append(out)
            polite_sleep(0.2)
        except Exception as exc:
            log_line(LOG, f"CFTC failed {year}: {exc}")
    folder = raw_dir.parent
    extracted_dir = folder / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    for zp in downloaded:
        try:
            with zipfile.ZipFile(zp) as zf:
                zf.extractall(extracted_dir / zp.stem)
        except Exception as exc:
            log_line(LOG, f"CFTC unzip failed {zp.name}: {exc}")
    write_docs(folder, "CFTC", "CFTC historical disaggregated Commitments of Traders reports.", downloaded)


def generate_exchange_calendars() -> None:
    folder = ROOT / "reference_data" / "trading_calendars"
    try:
        import exchange_calendars as xcals
    except Exception as exc:
        log_line(LOG, f"exchange_calendars unavailable: {exc}")
        generate_fallback_trading_calendars(folder)
        return
    for cal_name in ["XNYS", "XNAS", "CME", "XETR", "XTKS", "XLON"]:
        try:
            cal = xcals.get_calendar(cal_name)
            sched = cal.schedule.loc["2000-01-01":"2025-12-31"].reset_index()
            save(sched, folder / cal_name.lower(), "schedule.parquet", "exchange_calendars", f"{cal_name} trading schedule")
        except Exception as exc:
            log_line(LOG, f"calendar failed {cal_name}: {exc}")


def generate_fallback_trading_calendars(folder: Path) -> None:
    try:
        import holidays
    except Exception as exc:
        log_line(LOG, f"fallback calendars unavailable: {exc}")
        return
    country_map = {
        "xnys": "US",
        "xnas": "US",
        "cme": "US",
        "xetr": "DE",
        "xtks": "JP",
        "xlon": "GB",
    }
    dates = pd.date_range("2000-01-01", "2025-12-31", freq="B")
    for cal_name, country in country_map.items():
        country_holidays = holidays.country_holidays(country, years=range(2000, 2026))
        rows = []
        for date in dates:
            day = date.date()
            if day in country_holidays:
                continue
            rows.append({
                "session": day.isoformat(),
                "market_open": f"{day.isoformat()} 09:30:00",
                "market_close": f"{day.isoformat()} 16:00:00",
                "calendar": cal_name.upper(),
                "source_note": "fallback weekday calendar excluding country public holidays",
            })
        save(
            pd.DataFrame(rows),
            folder / cal_name,
            "schedule.parquet",
            "fallback calendar generator",
            f"{cal_name.upper()} fallback trading schedule generated from weekdays and public holidays",
        )


def generate_holidays() -> None:
    folder = ROOT / "reference_data" / "holidays"
    try:
        import holidays
    except Exception as exc:
        log_line(LOG, f"holidays unavailable: {exc}")
        return
    rows = []
    for country in ["US", "GB", "JP", "DE", "CA", "AU"]:
        for date, name in holidays.country_holidays(country, years=range(2000, 2026)).items():
            rows.append({"country": country, "date": date.isoformat(), "name": name})
    save(pd.DataFrame(rows), folder, "holidays.parquet", "python-holidays", "Public holiday calendar for market-aligned countries")


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_line(LOG, "START omega reference/CFTC worker")
    for fn in [fetch_cftc_disaggregated, generate_exchange_calendars, generate_holidays]:
        try:
            fn()
        except Exception as exc:
            log_line(LOG, f"ERROR {fn.__name__}: {exc}")
    log_line(LOG, "DONE omega reference/CFTC worker")


if __name__ == "__main__":
    main()
