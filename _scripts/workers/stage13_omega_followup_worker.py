from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from stage13_common import ROOT, append_acquisition_log, load_env, log_line, write_docs, write_table


LOG = ROOT / "_logs" / "omega" / "stage13_omega_followup_worker.log"
YF_BACKFILL = {
    "market_data/equities/global_indices": [
        "^FTSE", "^GDAXI", "^FCHI", "^N225", "^HSI", "000001.SS", "^STOXX50E",
        "^AXJO", "^GSPTSE", "^BVSP", "^MXX", "^KS11", "^TWII", "^BSESN",
    ],
    "market_data/equities/etfs": [
        "EEM", "EFA", "VEA", "VWO", "AGG", "BND", "LQD", "HYG", "TIP", "SHY",
        "IYR", "VNQ", "DIA", "VOO", "IVV", "VTI",
    ],
    "market_data/forex/emerging_markets": ["USDCOP=X", "USDCLP=X", "USDKRW=X", "USDTWD=X", "USDIDR=X"],
    "market_data/commodities/agriculture": ["ZC=F", "ZS=F", "ZW=F", "KC=F", "SB=F", "CT=F"],
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


def slug(symbol: str) -> str:
    return symbol.replace("^", "").replace("=", "_").replace("-", "_").replace(".", "_").lower()


def save(df: pd.DataFrame, folder: Path, filename: str, source: str, description: str) -> None:
    out = folder / filename
    write_table(df.reset_index(), out)
    actual = out if out.exists() else out.with_suffix(".csv")
    write_docs(folder, source, description, [actual])
    append_acquisition_log({
        "timestamp": utc_now(),
        "source": source,
        "dataset": folder.name,
        "status": "ok",
        "path": str(actual.relative_to(ROOT)),
        "notes": f"rows={len(df)}",
    })


def backfill_yfinance() -> dict[str, int]:
    import yfinance as yf

    summary = {"fetched": 0, "skipped": 0, "empty": 0, "failed": 0}
    for rel, symbols in YF_BACKFILL.items():
        for symbol in symbols:
            folder = ROOT / rel / slug(symbol)
            out = folder / "daily.parquet"
            if out.exists() or out.with_suffix(".csv").exists():
                summary["skipped"] += 1
                continue
            log_line(LOG, f"fetch yfinance follow-up {symbol}")
            try:
                df = yf.Ticker(symbol).history(period="max", interval="1d", end="2025-12-31", auto_adjust=False)
                if df.empty:
                    summary["empty"] += 1
                    log_line(LOG, f"empty yfinance follow-up {symbol}")
                    continue
                save(df, folder, "daily.parquet", "Yahoo Finance", f"{symbol} daily OHLCV follow-up backfill")
                summary["fetched"] += 1
            except Exception as exc:
                summary["failed"] += 1
                log_line(LOG, f"yfinance follow-up failed {symbol}: {exc}")
    return summary


def build_scheduled_event_proxy() -> dict[str, int]:
    rows: list[dict] = []
    actual_root = ROOT / "economic_calendar" / "release_actuals"
    for actuals in actual_root.glob("*/actuals.parquet"):
        try:
            df = pd.read_parquet(actuals)
        except Exception:
            continue
        event_slug = actuals.parent.name
        for _, row in df.tail(120).iterrows():
            rows.append({
                "event_slug": event_slug,
                "event_name": row.get("event_name", event_slug),
                "scheduled_date_proxy": str(row.get("date", ""))[:10],
                "fred_series": row.get("fred_series"),
                "actual": row.get("actual"),
                "transformed_actual": row.get("transformed_actual"),
                "consensus_estimate": pd.NA,
                "surprise": pd.NA,
                "source_note": "Historical release-date proxy generated from FRED actual observation dates; consensus estimates remain a Stage 1.4/source-selection gap.",
            })
    folder = ROOT / "economic_calendar" / "scheduled_events" / "fred_release_date_proxy"
    if rows:
        save(pd.DataFrame(rows), folder, "scheduled_events.parquet", "FRED-derived release-date proxy", "Historical scheduled-event proxy from acquired release actuals")
    gap = ROOT / "economic_calendar" / "release_surprises" / "stage13_consensus_gap.md"
    gap.parent.mkdir(parents=True, exist_ok=True)
    gap.write_text(
        "# Stage 1.3 Consensus/Surprise Gap\n\n"
        "FRED release actuals and a historical release-date proxy are present. Consensus estimates are not available from the validated free sources yet; route paid/free source choice to Stage 1.4 if required.\n",
        encoding="utf-8",
    )
    return {"rows": len(rows)}


def write_followup_summary(summary: dict) -> None:
    out = ROOT / "_logs" / "omega" / "stage13_omega_followup_summary.json"
    out.write_text(json.dumps({"generated_at": utc_now(), "summary": summary}, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    load_env()
    log_line(LOG, "START omega follow-up worker")
    notify(
        "omega-followup-started",
        "Project 3 Omega follow-up started",
        "Stage 1.3 follow-up: yfinance catalog backfill and FRED-derived scheduled-event proxy. Deliverables: market_data/equities/global_indices, additional ETFs/EM FX/agriculture, economic_calendar/scheduled_events/fred_release_date_proxy.",
    )
    summary = {}
    for name, fn in [("yfinance_backfill", backfill_yfinance), ("scheduled_event_proxy", build_scheduled_event_proxy)]:
        try:
            summary[name] = fn()
        except Exception as exc:
            summary[name] = {"error": str(exc)}
            log_line(LOG, f"ERROR {name}: {exc}")
    write_followup_summary(summary)
    log_line(LOG, f"DONE omega follow-up worker {json.dumps(summary, sort_keys=True)[:500]}")
    notify(
        "omega-followup-done",
        "Project 3 Omega follow-up complete",
        "Stage 1.3 follow-up finished. Deliverables: yfinance backfill and economic_calendar/scheduled_events/fred_release_date_proxy. Evidence: _logs/omega/stage13_omega_followup_summary.json and stage13_omega_followup_worker.log.",
    )


if __name__ == "__main__":
    main()
