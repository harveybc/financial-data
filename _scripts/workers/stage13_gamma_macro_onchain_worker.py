from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, load_env, log_line, polite_sleep, write_docs, write_table


LOG = ROOT / "_logs" / "gamma" / "stage13_macro_onchain_worker.log"
FRED_SERIES = {
    "inflation": ["CPIAUCSL", "CPILFESL", "PPIACO", "PCEPILFE", "PCECTPI", "MEDCPIM158SFRBCLE", "TRMMEANCPIM159SFRBCLE", "FPCPITOTLZGUSA"],
    "employment": ["UNRATE", "PAYEMS", "CIVPART", "U6RATE", "EMRATIO", "AHETPI", "ICSA", "CCSA"],
    "gdp": ["GDP", "GDPC1", "A191RL1Q225SBEA", "GDPNOW", "GDPPOT"],
    "money": ["M1SL", "M2SL", "BOGMBASE", "WALCL", "WTREGEN"],
    "rates": ["DFF", "FEDFUNDS", "DPRIME", "DGS10", "DGS2", "DGS5", "DGS30", "DGS3MO", "TB3MS", "DTB3", "T10Y2Y", "T10Y3M"],
    "consumer": ["UMCSENT", "RSAFS", "PCEC", "PSAVERT", "DSPI"],
    "housing": ["HOUST", "EXHOSLUSM495S", "CSUSHPISA", "MORTGAGE30US", "PERMIT"],
    "industrial": ["INDPRO", "CAPUTLB50001SQ", "NAPM", "NAPMNOI", "BUSINV"],
    "fx_indices": ["DTWEXBGS", "DTWEXAFEGS", "DTWEXEMEGS"],
    "stress": ["STLFSI4", "NFCI", "ANFCI", "TEDRATE"],
    "recession": ["USREC", "USRECP", "USRECQ", "USRECDM"],
    "inflation_expectations": ["T5YIE", "T5YIFR", "T10YIE", "MICH"],
}
COINMETRICS_ASSETS = ["btc", "eth", "ltc", "bch", "xmr", "doge", "ada", "dot", "sol", "atom", "near", "matic", "avax", "trx", "xlm", "fil", "icp", "uni", "link", "etc"]
COINMETRICS_METRICS = ["AdrActCnt", "TxCnt", "HashRate", "DiffMean", "BlkCnt", "FeeMeanUSD", "TxTfrCnt", "TxTfrValAdjUSD"]


def get_json(url: str, params: dict | None = None) -> object:
    for attempt in range(6):
        r = requests.get(url, params=params, timeout=45)
        if r.status_code in {429, 500, 502, 503, 504}:
            polite_sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"failed after retries: {url}")


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


def fetch_fred() -> None:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY missing")
    for category, series_list in FRED_SERIES.items():
        for sid in series_list:
            folder = ROOT / "macro_economic" / "fred" / category / sid.lower()
            out = folder / "observations.parquet"
            if out.exists() or out.with_suffix(".csv").exists():
                log_line(LOG, f"skip existing FRED {sid}")
                continue
            log_line(LOG, f"fetch FRED {sid}")
            try:
                payload = get_json(
                    "https://api.stlouisfed.org/fred/series/observations",
                    {"series_id": sid, "api_key": key, "file_type": "json", "observation_start": "1900-01-01", "observation_end": "2025-12-31"},
                )
                df = pd.DataFrame(payload.get("observations", []))
                save(df, folder, "observations.parquet", "FRED", f"FRED series {sid}")
            except Exception as exc:
                log_line(LOG, f"FRED failed series={sid} error={exc}")
            polite_sleep(0.25)


def fetch_coinmetrics() -> None:
    metrics = ",".join(COINMETRICS_METRICS)
    for asset in COINMETRICS_ASSETS:
        folder = ROOT / "alternative_data" / ("onchain_btc" if asset == "btc" else "onchain_eth" if asset == "eth" else "onchain_other") / "coinmetrics" / asset
        out = folder / "community_metrics.parquet"
        if out.exists() or out.with_suffix(".csv").exists():
            log_line(LOG, f"skip existing CoinMetrics {asset}")
            continue
        log_line(LOG, f"fetch CoinMetrics {asset}")
        try:
            payload = get_json(
                "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics",
                {"assets": asset, "metrics": metrics, "frequency": "1d", "start_time": "2009-01-01", "end_time": "2025-12-31", "page_size": 10000},
            )
            df = pd.DataFrame(payload.get("data", []))
            save(df, folder, "community_metrics.parquet", "CoinMetrics Community", f"{asset} community on-chain metrics")
        except Exception as exc:
            log_line(LOG, f"CoinMetrics failed asset={asset} error={exc}")
        polite_sleep(0.25)


def fetch_blockchain_charts() -> None:
    charts = ["n-transactions", "hash-rate", "difficulty", "miners-revenue", "transaction-fees-usd", "mempool-size"]
    for chart in charts:
        folder = ROOT / "alternative_data" / "onchain_btc" / "blockchain_com" / chart
        out = folder / "daily.parquet"
        if out.exists() or out.with_suffix(".csv").exists():
            continue
        log_line(LOG, f"fetch Blockchain.com {chart}")
        payload = get_json(f"https://api.blockchain.info/charts/{chart}", {"timespan": "all", "format": "json"})
        df = pd.DataFrame(payload.get("values", []))
        save(df, folder, "daily.parquet", "Blockchain.com", f"BTC {chart}")
        polite_sleep(0.25)


def fetch_defillama() -> None:
    folder = ROOT / "alternative_data" / "defi_metrics" / "defillama"
    out = folder / "protocols.parquet"
    if out.exists() or out.with_suffix(".csv").exists():
        return
    log_line(LOG, "fetch DeFiLlama protocols")
    payload = get_json("https://api.llama.fi/protocols")
    save(pd.DataFrame(payload), folder, "protocols.parquet", "DeFiLlama", "Protocol TVL metadata snapshot")


def fetch_mempool_current() -> None:
    endpoints = {
        "fees_recommended": "https://mempool.space/api/v1/fees/recommended",
        "mempool": "https://mempool.space/api/mempool",
        "difficulty_adjustment": "https://mempool.space/api/v1/difficulty-adjustment",
    }
    for name, url in endpoints.items():
        folder = ROOT / "alternative_data" / "onchain_btc" / "mempool_space" / name
        out = folder / "snapshot.parquet"
        if out.exists() or out.with_suffix(".csv").exists():
            continue
        log_line(LOG, f"fetch mempool.space {name}")
        payload = get_json(url)
        df = pd.DataFrame([payload]) if isinstance(payload, dict) else pd.DataFrame(payload)
        save(df, folder, "snapshot.parquet", "mempool.space", f"BTC mempool.space {name} snapshot")


def fetch_sec_company_tickers() -> None:
    folder = ROOT / "alternative_data" / "sec_filings" / "edgar_company_tickers"
    out = folder / "company_tickers.parquet"
    if out.exists() or out.with_suffix(".csv").exists():
        return
    log_line(LOG, "fetch SEC company tickers")
    headers = {"User-Agent": "Project3 financial-data research harveybc@example.local"}
    r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=45)
    r.raise_for_status()
    payload = r.json()
    df = pd.DataFrame(payload.values())
    save(df, folder, "company_tickers.parquet", "SEC EDGAR", "SEC company tickers metadata")


def write_gamma_escalations() -> None:
    esc = ROOT / "_logs" / "gamma" / "stage13_macro_onchain_escalation.md"
    text = """# Gamma Stage 1.3 Data Anomalies

- Stage: 1.3 Free Data Acquisition
- Agent: Gamma Hermes/Gemma + Python worker
- CoinMetrics Community API returned 403/400 for the metric bundle requested by the work plan. This is a data-source/API access anomaly, not a user-action blocker.
- FRED invalid/deprecated series are logged individually and skipped; valid series continue.
- Next agent action: use available free alternatives now; revisit CoinMetrics endpoint/metric availability during Stage 1.3 validation or Stage 1.4 subscription gap analysis.
"""
    esc.write_text(text, encoding="utf-8")


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    load_env()
    log_line(LOG, "START gamma macro/on-chain acquisition")
    for fn in [fetch_fred, fetch_coinmetrics, fetch_blockchain_charts, fetch_defillama, fetch_mempool_current, fetch_sec_company_tickers]:
        try:
            fn()
        except Exception as exc:
            log_line(LOG, f"ERROR {fn.__name__}: {exc}")
    write_gamma_escalations()
    log_line(LOG, "DONE gamma macro/on-chain acquisition")


if __name__ == "__main__":
    main()
