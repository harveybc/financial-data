from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, log_line, polite_sleep, write_docs, write_table


LOG = ROOT / "_logs" / "gamma" / "stage13_crypto_perp_accelerator_worker.log"
FUTURES = "https://fapi.binance.com"
TIMEFRAMES = ["5m", "15m", "1h", "4h"]
END_MS = int(datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc).timestamp() * 1000)
PERP_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT"]


def get_json(url: str, params: dict | None = None) -> object:
    for attempt in range(8):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code in {418, 429}:
            wait = 2 ** min(attempt, 6)
            log_line(LOG, f"rate_limited url={url} wait={wait}s")
            polite_sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"rate limited too long: {url}")


def klines(symbol: str, interval: str) -> pd.DataFrame:
    rows = []
    start = 0
    while start < END_MS:
        payload = get_json(
            f"{FUTURES}/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "startTime": start, "endTime": END_MS, "limit": 1000},
        )
        if not payload:
            break
        rows.extend(payload)
        next_start = int(payload[-1][0]) + 1
        if next_start <= start:
            break
        start = next_start
        if len(rows) % 5000 == 0:
            log_line(LOG, f"{symbol} perp {interval} rows={len(rows)}")
        polite_sleep(0.08)
    cols = [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trade_count", "taker_buy_base_volume", "taker_buy_quote_volume", "ignore",
    ]
    df = pd.DataFrame(rows, columns=cols)
    if not df.empty:
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
        for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_base_volume", "taker_buy_quote_volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["trade_count"] = pd.to_numeric(df["trade_count"], errors="coerce")
        df = df.drop(columns=["ignore"])
    return df


def funding_rates(symbol: str) -> pd.DataFrame:
    rows = []
    start = 0
    while start < END_MS:
        payload = get_json(
            f"{FUTURES}/fapi/v1/fundingRate",
            {"symbol": symbol, "startTime": start, "endTime": END_MS, "limit": 1000},
        )
        if not payload:
            break
        rows.extend(payload)
        next_start = int(payload[-1]["fundingTime"]) + 1
        if next_start <= start:
            break
        start = next_start
        polite_sleep(0.08)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
        df["fundingRate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
    return df


def save_dataset(df: pd.DataFrame, folder: Path, filename: str, source: str, description: str) -> None:
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


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_line(LOG, "START gamma crypto perpetual/funding accelerator")
    for symbol in PERP_SYMBOLS:
        slug = symbol.lower()
        for tf in TIMEFRAMES:
            folder = ROOT / "market_data" / "crypto" / "perpetuals" / slug
            out = folder / f"{tf}.parquet"
            if out.exists() or out.with_suffix(".csv").exists():
                log_line(LOG, f"skip existing perp {symbol} {tf}")
                continue
            log_line(LOG, f"fetch perp {symbol} {tf}")
            save_dataset(klines(symbol, tf), folder, f"{tf}.parquet", "Binance Futures", f"{symbol} perpetual OHLCV {tf}")
        folder = ROOT / "market_data" / "crypto" / "funding_rates" / slug
        out = folder / "funding_rates.parquet"
        if out.exists() or out.with_suffix(".csv").exists():
            log_line(LOG, f"skip existing funding {symbol}")
            continue
        log_line(LOG, f"fetch funding {symbol}")
        save_dataset(funding_rates(symbol), folder, "funding_rates.parquet", "Binance Futures", f"{symbol} funding rates")
    log_line(LOG, "DONE gamma crypto perpetual/funding accelerator")


if __name__ == "__main__":
    main()
