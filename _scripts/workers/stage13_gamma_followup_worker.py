from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, load_env, log_line, polite_sleep, write_docs, write_table


LOG = ROOT / "_logs" / "gamma" / "stage13_gamma_followup_worker.log"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
CM_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
SEC_HEADERS = {"User-Agent": "Project3 financial-data research harveybc@example.local"}

FRED_EXPANDED = {
    "inflation": [
        "CPIAUCSL", "CPILFESL", "PPIACO", "PCEPILFE", "PCECTPI", "GDPDEF",
        "CUSR0000SA0", "CUSR0000SA0L1E", "CPALTT01USM657N", "WPU0911",
        "WPSFD49207", "MEDCPIM158SFRBCLE", "TRMMEANCPIM159SFRBCLE",
        "FPCPITOTLZGUSA",
    ],
    "employment": [
        "UNRATE", "PAYEMS", "CIVPART", "U6RATE", "EMRATIO", "AHETPI",
        "ICSA", "CCSA", "NROU", "JTSJOL", "JTSQUR", "CE16OV",
        "LNS14000006", "MANEMP", "USPRIV", "AWHAETP",
    ],
    "gdp": [
        "GDP", "GDPC1", "A191RL1Q225SBEA", "GDPNOW", "GDPPOT", "GNP",
        "GNPC96", "GDI", "PCE", "GPDI", "NETEXP", "EXPGS", "IMPGS", "GCEC",
    ],
    "money": [
        "M1SL", "M2SL", "BOGMBASE", "WALCL", "WTREGEN", "M1V", "M2V",
        "TOTRESNS", "NONBORRES", "WRESBAL", "CURRCIR", "RRPONTSYD",
    ],
    "rates": [
        "DFF", "FEDFUNDS", "DPRIME", "DGS10", "DGS2", "DGS5", "DGS30",
        "DGS3MO", "TB3MS", "DTB3", "T10Y2Y", "T10Y3M", "DGS1", "DGS7",
        "DGS20", "DFII10", "DFII5", "T5YIE", "T10YIE", "T5YIFR",
    ],
    "credit": [
        "BAMLC0A0CM", "BAMLC0A0CMEY", "BAMLH0A0HYM2", "BAMLH0A0HYM2EY",
        "AAA", "BAA", "BAA10Y", "AAA10Y",
    ],
    "consumer": [
        "UMCSENT", "RSAFS", "PCEC", "PSAVERT", "DSPI", "RRSFS",
        "A229RX0", "HSN1F", "DPCERA3M086SBEA",
    ],
    "housing": [
        "HOUST", "EXHOSLUSM495S", "CSUSHPISA", "MORTGAGE30US", "PERMIT",
        "HOUST1F", "COMPU1USA", "MSPUS", "ASPUS", "HSN1F", "RHORUSQ156N",
    ],
    "industrial": [
        "INDPRO", "CAPUTLB50001SQ", "NAPM", "NAPMNOI", "BUSINV",
        "ISRATIO", "IPMAN", "TCU", "CUMFNS", "NEWORDER", "DGORDER",
    ],
    "trade": ["BOPGSTB", "IEAMTNQ", "EXPGS", "IMPGS", "NETEXP", "BOPTEXP", "BOPTIMP"],
    "fx_indices": ["DTWEXBGS", "DTWEXAFEGS", "DTWEXEMEGS", "DTWEXM", "DTWEXB"],
    "stress": ["STLFSI4", "NFCI", "ANFCI", "TEDRATE", "VIXCLS"],
    "recession": ["USREC", "USRECP", "USRECQ", "USRECDM"],
    "inflation_expectations": ["T5YIE", "T5YIFR", "T10YIE", "MICH", "EXPINF10YR"],
}

CM_ASSETS = ["btc", "eth", "ltc", "bch", "doge", "ada", "dot", "sol", "atom", "trx", "xlm", "link"]
CM_METRICS = ["AdrActCnt", "TxCnt", "HashRate", "DiffMean", "BlkCnt", "FeeMeanUSD", "TxTfrCnt", "TxTfrValAdjUSD"]
FALLBACK_SP500 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B", "LLY", "AVGO",
    "JPM", "TSLA", "UNH", "XOM", "V", "MA", "PG", "COST", "HD", "JNJ",
    "ABBV", "WMT", "BAC", "KO", "NFLX", "CRM", "MRK", "CVX", "AMD", "PEP",
    "ADBE", "TMO", "WFC", "LIN", "MCD", "CSCO", "ACN", "ABT", "ORCL", "DIS",
    "QCOM", "IBM", "INTU", "GE", "CAT", "AMAT", "VZ", "NOW", "TXN", "PM",
]


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


def save(df: pd.DataFrame, folder: Path, filename: str, source: str, description: str) -> None:
    out = folder / filename
    write_table(df, out)
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


def fetch_fred_expansion() -> dict[str, int]:
    key = __import__("os").environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY missing")
    summary = {"fetched": 0, "skipped": 0, "failed": 0}
    for category, series_ids in FRED_EXPANDED.items():
        for sid in dict.fromkeys(series_ids):
            folder = ROOT / "macro_economic" / "fred" / category / sid.lower()
            out = folder / "observations.parquet"
            if out.exists() or out.with_suffix(".csv").exists():
                summary["skipped"] += 1
                continue
            log_line(LOG, f"fetch FRED expanded {sid}")
            try:
                r = requests.get(
                    FRED_URL,
                    params={
                        "series_id": sid,
                        "api_key": key,
                        "file_type": "json",
                        "observation_start": "1900-01-01",
                        "observation_end": "2025-12-31",
                    },
                    timeout=60,
                )
                r.raise_for_status()
                df = pd.DataFrame(r.json().get("observations", []))
                if df.empty:
                    summary["failed"] += 1
                    log_line(LOG, f"empty FRED expanded {sid}")
                else:
                    save(df, folder, "observations.parquet", "FRED", f"Expanded FRED series {sid}")
                    summary["fetched"] += 1
            except Exception as exc:
                summary["failed"] += 1
                log_line(LOG, f"FRED expanded failed series={sid} error={exc}")
            polite_sleep(0.15)
    return summary


def fetch_coinmetrics_per_metric() -> dict[str, int]:
    summary = {"fetched": 0, "failed": 0, "skipped": 0}
    failures: list[dict[str, str]] = []
    for asset in CM_ASSETS:
        root = ROOT / "alternative_data" / ("onchain_btc" if asset == "btc" else "onchain_eth" if asset == "eth" else "onchain_other") / "coinmetrics_community" / asset
        for metric in CM_METRICS:
            out = root / f"{metric}.parquet"
            if out.exists() or out.with_suffix(".csv").exists():
                summary["skipped"] += 1
                continue
            log_line(LOG, f"fetch CoinMetrics per-metric asset={asset} metric={metric}")
            rows: list[dict] = []
            token = None
            try:
                while True:
                    params = {
                        "assets": asset,
                        "metrics": metric,
                        "frequency": "1d",
                        "start_time": "2009-01-01",
                        "end_time": "2025-12-31",
                        "page_size": "10000",
                    }
                    if token:
                        params["next_page_token"] = token
                    r = requests.get(CM_URL, params=params, timeout=60)
                    if r.status_code in {400, 403, 404}:
                        raise RuntimeError(f"{r.status_code}: {r.text[:180]}")
                    r.raise_for_status()
                    payload = r.json()
                    rows.extend(payload.get("data", []))
                    token = payload.get("next_page_token")
                    if not token:
                        break
                    polite_sleep(0.15)
                if rows:
                    save(pd.DataFrame(rows), root, f"{metric}.parquet", "CoinMetrics Community", f"{asset} {metric} daily community metric")
                    summary["fetched"] += 1
                else:
                    summary["failed"] += 1
                    failures.append({"asset": asset, "metric": metric, "error": "empty"})
            except Exception as exc:
                summary["failed"] += 1
                failures.append({"asset": asset, "metric": metric, "error": str(exc)[:220]})
                log_line(LOG, f"CoinMetrics per-metric failed asset={asset} metric={metric} error={exc}")
            polite_sleep(0.25)
    gap = ROOT / "_logs" / "gamma" / "stage13_coinmetrics_followup_failures.json"
    gap.write_text(json.dumps({"generated_at": utc_now(), "failures": failures}, indent=2) + "\n", encoding="utf-8")
    return summary


def sp500_tickers() -> list[str]:
    try:
        r = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers=SEC_HEADERS,
            timeout=60,
        )
        r.raise_for_status()
        tables = pd.read_html(StringIO(r.text))
        symbols = [str(v).replace(".", "-").strip().upper() for v in tables[0]["Symbol"].dropna().tolist()]
        return symbols[:505]
    except Exception as exc:
        log_line(LOG, f"S&P 500 wiki list failed; using fallback: {exc}")
        return FALLBACK_SP500


def fetch_sec_sp500_metadata() -> dict[str, int]:
    tickers = sp500_tickers()
    r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS, timeout=60)
    r.raise_for_status()
    company = pd.DataFrame(r.json().values())
    company["ticker_norm"] = company["ticker"].astype(str).str.replace(".", "-", regex=False).str.upper()
    cik_by_ticker = {row["ticker_norm"]: int(row["cik_str"]) for _, row in company.iterrows()}
    rows: list[dict] = []
    missing: list[str] = []
    forms = {"10-K", "10-Q", "8-K", "4"}
    for i, ticker in enumerate(tickers, start=1):
        cik = cik_by_ticker.get(ticker)
        if cik is None:
            missing.append(ticker)
            continue
        url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
        try:
            payload = requests.get(url, headers=SEC_HEADERS, timeout=60).json()
            recent = payload.get("filings", {}).get("recent", {})
            form_list = recent.get("form", [])
            accession = recent.get("accessionNumber", [])
            filing_date = recent.get("filingDate", [])
            report_date = recent.get("reportDate", [])
            primary_doc = recent.get("primaryDocument", [])
            for idx, form in enumerate(form_list):
                if form not in forms:
                    continue
                rows.append({
                    "ticker": ticker,
                    "cik": cik,
                    "company_name": payload.get("name"),
                    "form": form,
                    "filing_date": filing_date[idx] if idx < len(filing_date) else None,
                    "report_date": report_date[idx] if idx < len(report_date) else None,
                    "accession_number": accession[idx] if idx < len(accession) else None,
                    "primary_document": primary_doc[idx] if idx < len(primary_doc) else None,
                })
        except Exception as exc:
            missing.append(f"{ticker}:{exc}")
        if i % 25 == 0:
            log_line(LOG, f"SEC metadata progress tickers={i} rows={len(rows)}")
        polite_sleep(0.12)
    folder = ROOT / "alternative_data" / "sec_filings" / "edgar_sp500_metadata"
    if rows:
        save(pd.DataFrame(rows), folder, "filing_metadata.parquet", "SEC EDGAR submissions API", "S&P 500 recent 10-K, 10-Q, 8-K, and Form 4 metadata")
    (folder / "missing_tickers.json").write_text(json.dumps({"generated_at": utc_now(), "missing": missing}, indent=2) + "\n", encoding="utf-8")
    return {"tickers": len(tickers), "rows": len(rows), "missing": len(missing)}


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    load_env()
    log_line(LOG, "START gamma follow-up worker")
    notify(
        "gamma-followup-started",
        "Project 3 Gamma follow-up started",
        "Stage 1.3 follow-up: FRED expansion, CoinMetrics per-metric repair, and SEC S&P 500 metadata. Deliverables: macro_economic/fred, alternative_data/onchain_*/coinmetrics_community, alternative_data/sec_filings/edgar_sp500_metadata.",
    )
    summary = {}
    for name, fn in [
        ("fred_expansion", fetch_fred_expansion),
        ("coinmetrics_per_metric", fetch_coinmetrics_per_metric),
        ("sec_sp500_metadata", fetch_sec_sp500_metadata),
    ]:
        try:
            summary[name] = fn()
        except Exception as exc:
            summary[name] = {"error": str(exc)}
            log_line(LOG, f"ERROR {name}: {exc}")
    out = ROOT / "_logs" / "gamma" / "stage13_gamma_followup_summary.json"
    out.write_text(json.dumps({"generated_at": utc_now(), "summary": summary}, indent=2) + "\n", encoding="utf-8")
    log_line(LOG, f"DONE gamma follow-up worker {json.dumps(summary, sort_keys=True)[:500]}")
    notify(
        "gamma-followup-done",
        "Project 3 Gamma follow-up complete",
        "Stage 1.3 follow-up finished. Deliverables: macro_economic/fred expanded series, alternative_data/onchain_* CoinMetrics per-metric files, alternative_data/sec_filings/edgar_sp500_metadata. Evidence: _logs/gamma/stage13_gamma_followup_summary.json and stage13_gamma_followup_worker.log.",
    )


if __name__ == "__main__":
    main()
