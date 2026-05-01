from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from stage13_common import ROOT, append_acquisition_log, load_env, log_line, write_docs, write_table


LOG = ROOT / "_logs" / "omega" / "stage13_light_sources_worker.log"
HISTDATA = Path("/home/harveybc/Downloads/histdata")
YF_TICKERS = {
    "market_data/equities/us_indices": ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX"],
    "market_data/equities/etfs": ["SPY", "QQQ", "IWM", "XLF", "XLK", "XLE", "XLV", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC", "TLT", "IEF", "GLD", "SLV", "USO"],
    "market_data/commodities/precious_metals": ["GC=F", "SI=F", "PL=F", "PA=F"],
    "market_data/commodities/energy": ["CL=F", "BZ=F", "NG=F", "RB=F"],
    "market_data/forex/emerging_markets": ["USDMXN=X", "USDZAR=X", "USDTRY=X", "USDBRL=X", "USDINR=X"],
}


def safe_slug(symbol: str) -> str:
    return symbol.replace("^", "").replace("=", "_").replace("-", "_").lower()


def save(df: pd.DataFrame, folder: Path, filename: str, source: str, description: str) -> None:
    out = folder / filename
    write_table(df.reset_index(), out)
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


def fetch_yfinance() -> None:
    import yfinance as yf

    for rel, tickers in YF_TICKERS.items():
        for ticker in tickers:
            folder = ROOT / rel / safe_slug(ticker)
            out = folder / "daily.parquet"
            if out.exists() or out.with_suffix(".csv").exists():
                log_line(LOG, f"skip existing yfinance {ticker}")
                continue
            log_line(LOG, f"fetch yfinance {ticker}")
            df = yf.Ticker(ticker).history(period="max", interval="1d", end="2025-12-31", auto_adjust=False)
            if df.empty:
                log_line(LOG, f"empty yfinance {ticker}")
                continue
            save(df, folder, "daily.parquet", "Yahoo Finance", f"{ticker} daily OHLCV")


def parse_histdata_zip(path: Path) -> pd.DataFrame:
    frames = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            with zf.open(name) as f:
                df = pd.read_csv(f, header=None)
                if df.shape[1] >= 6:
                    df = df.iloc[:, :6]
                    df.columns = ["date", "time", "open", "high", "low", "close"]
                    dt = pd.to_datetime(df["date"].astype(str) + df["time"].astype(str).str.zfill(6), format="%Y%m%d%H%M%S", errors="coerce", utc=True)
                elif df.shape[1] >= 5:
                    df = df.iloc[:, :5]
                    df.columns = ["datetime", "open", "high", "low", "close"]
                    dt = pd.to_datetime(df["datetime"], errors="coerce", utc=True)
                else:
                    continue
                df["datetime"] = dt
                frames.append(df[["datetime", "open", "high", "low", "close"]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def process_histdata() -> None:
    if not HISTDATA.exists():
        log_line(LOG, f"HistData input missing: {HISTDATA}")
        return
    for pair_dir in sorted(p for p in HISTDATA.iterdir() if p.is_dir()):
        pair = pair_dir.name.lower()
        folder = ROOT / "market_data" / "forex" / "g10" / pair
        if (folder / "5m.parquet").exists() or (folder / "5m.csv").exists():
            log_line(LOG, f"skip existing HistData {pair}")
            continue
        zip_paths = sorted(pair_dir.glob("*.zip"))
        if not zip_paths:
            continue
        log_line(LOG, f"process HistData {pair} zips={len(zip_paths)}")
        parts = []
        for zp in zip_paths:
            try:
                part = parse_histdata_zip(zp)
                if not part.empty:
                    parts.append(part)
            except Exception as exc:
                log_line(LOG, f"HistData zip failed {zp}: {exc}")
        if not parts:
            continue
        df = pd.concat(parts, ignore_index=True).dropna(subset=["datetime"]).drop_duplicates("datetime").sort_values("datetime")
        df = df.set_index("datetime")
        for tf, rule in {"5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h"}.items():
            ohlc = df.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
            write_table(ohlc, folder / f"{tf}.parquet")
        files = [p for p in folder.glob("*.parquet")] + [p for p in folder.glob("*.csv")]
        write_docs(folder, "HistData", f"{pair.upper()} FX bars resampled from 1-minute source zips in {HISTDATA}", files)
        append_acquisition_log({"timestamp": datetime.now(timezone.utc).isoformat(), "source": "HistData", "dataset": pair, "status": "ok", "path": str(folder.relative_to(ROOT)), "notes": f"zips={len(zip_paths)}"})


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    load_env()
    log_line(LOG, "START omega light-source acquisition")
    for fn in [fetch_yfinance, process_histdata]:
        try:
            fn()
        except Exception as exc:
            log_line(LOG, f"ERROR {fn.__name__}: {exc}")
    log_line(LOG, "DONE omega light-source acquisition")


if __name__ == "__main__":
    main()
