from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, log_line, polite_sleep, write_docs, write_table


LOG = ROOT / "_logs" / "dragon" / "stage13_crypto_worker.log"
EXCLUSIONS = ROOT / "_logs" / "dragon" / "stage13_crypto_exclusions.json"
BINANCE = "https://api.binance.com"
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


def binance_symbols() -> set[str]:
    data = get_json(f"{BINANCE}/api/v3/exchangeInfo")
    return {
        s["symbol"]
        for s in data["symbols"]
        if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING"
    }


def top50_symbols() -> list[str]:
    cg = get_json(
        "https://api.coingecko.com/api/v3/coins/markets",
        {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 50, "page": 1},
    )
    candidates = [coin["symbol"].upper() + "USDT" for coin in cg]
    tradable = binance_symbols()
    symbols = [s for s in candidates if s in tradable]
    log_line(LOG, f"top50_candidates={len(candidates)} binance_tradable={len(symbols)}")
    return symbols


def klines(base: str, path: str, symbol: str, interval: str) -> pd.DataFrame:
    rows = []
    start = 0
    while start < END_MS:
        payload = get_json(
            f"{base}{path}",
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
            log_line(LOG, f"{symbol} {interval} rows={len(rows)}")
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


def record_exclusion(dataset_type: str, symbol: str, timeframe: str, source: str, reason: str, folder: Path | None = None) -> None:
    EXCLUSIONS.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    except Exception:
        payload = {"exclusions": []}
    exclusions = payload.setdefault("exclusions", [])
    key = f"{dataset_type}:{symbol}:{timeframe}"
    if not any(item.get("key") == key for item in exclusions):
        exclusions.append({
            "key": key,
            "dataset_type": dataset_type,
            "symbol": symbol,
            "timeframe": timeframe,
            "source": source,
            "reason": reason,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    EXCLUSIONS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if folder is not None:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "README.md").write_text(
            f"# {folder.name}\n\n"
            f"No data file is saved for {symbol} {dataset_type} {timeframe} because {reason}.\n\n"
            f"Source: {source}\nAcquired: {datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8",
        )
        (folder / "data_dictionary.md").write_text(
            "# Data Dictionary\n\nNo tabular data file was written for this symbol because the source returned no rows.\n",
            encoding="utf-8",
        )
        (folder / "provenance.json").write_text(
            json.dumps(
                {
                    "source": source,
                    "description": f"{symbol} {dataset_type} {timeframe}",
                    "acquired_at": datetime.now(timezone.utc).isoformat(),
                    "status": "no_data",
                    "reason": reason,
                    "files": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    append_acquisition_log({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "dataset": symbol.lower(),
        "status": "no_data",
        "path": "",
        "notes": f"{dataset_type} {timeframe}: {reason}",
    })


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
    log_line(LOG, "START dragon crypto acquisition")
    symbols = top50_symbols()
    for symbol in symbols:
        slug = symbol.lower()
        for tf in TIMEFRAMES:
            folder = ROOT / "market_data" / "crypto" / "spot_top50" / slug
            out = folder / f"{tf}.parquet"
            if out.exists() or out.with_suffix(".csv").exists():
                log_line(LOG, f"skip existing spot {symbol} {tf}")
                continue
            log_line(LOG, f"fetch spot {symbol} {tf}")
            df = klines(BINANCE, "/api/v3/klines", symbol, tf)
            if df.empty:
                reason = "Binance spot kline endpoint returned HTTP 200 with an empty payload through 2025-12-31"
                log_line(LOG, f"no_data spot {symbol} {tf}: {reason}")
                record_exclusion("spot_top50", symbol, tf, "Binance Spot", reason, folder)
                continue
            save_dataset(df, folder, f"{tf}.parquet", "Binance Spot", f"{symbol} spot OHLCV {tf}")
    for symbol in PERP_SYMBOLS:
        slug = symbol.lower()
        for tf in TIMEFRAMES:
            folder = ROOT / "market_data" / "crypto" / "perpetuals" / slug
            out = folder / f"{tf}.parquet"
            if out.exists() or out.with_suffix(".csv").exists():
                log_line(LOG, f"skip existing perp {symbol} {tf}")
                continue
            log_line(LOG, f"fetch perp {symbol} {tf}")
            df = klines(FUTURES, "/fapi/v1/klines", symbol, tf)
            if df.empty:
                reason = "Binance futures kline endpoint returned HTTP 200 with an empty payload through 2025-12-31"
                log_line(LOG, f"no_data perp {symbol} {tf}: {reason}")
                record_exclusion("perpetuals", symbol, tf, "Binance Futures", reason, folder)
                continue
            save_dataset(df, folder, f"{tf}.parquet", "Binance Futures", f"{symbol} perpetual OHLCV {tf}")
        folder = ROOT / "market_data" / "crypto" / "funding_rates" / slug
        out = folder / "funding_rates.parquet"
        if not out.exists() and not out.with_suffix(".csv").exists():
            log_line(LOG, f"fetch funding {symbol}")
            df = funding_rates(symbol)
            if df.empty:
                reason = "Binance funding-rate endpoint returned HTTP 200 with an empty payload through 2025-12-31"
                log_line(LOG, f"no_data funding {symbol}: {reason}")
                record_exclusion("funding_rates", symbol, "8h_native", "Binance Futures", reason, folder)
                continue
            save_dataset(df, folder, "funding_rates.parquet", "Binance Futures", f"{symbol} funding rates")
    log_line(LOG, "DONE dragon crypto acquisition")


if __name__ == "__main__":
    main()
