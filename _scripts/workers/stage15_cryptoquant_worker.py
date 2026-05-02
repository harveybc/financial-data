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

from stage13_common import ROOT, append_acquisition_log, load_env, log_line, sha256_file, write_table


BASE_URL = "https://api.cryptoquant.com"
USER_AGENT = "project3-financial-data-research/1.0"
LOG = ROOT / "_logs" / "dragon" / "stage15_cryptoquant_worker.log"
OUT_DIR = ROOT / "alternative_data" / "cryptoquant"
SUMMARY_JSON = ROOT / "_metadata" / "stage15_cryptoquant_acquisition.json"
SUMMARY_MD = ROOT / "_logs" / "supervisor_reports" / "stage15_cryptoquant_acquisition.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {str(exc)[:260]}"
    text = re.sub(r"([?&]api_key=)[^&\s]+", r"\1<redacted>", text)
    text = re.sub(r"(Bearer\s+)[A-Za-z0-9._-]+", r"\1<redacted>", text)
    return text


def headers() -> dict[str, str]:
    key = os.environ.get("CRYPTOQUANT_API_KEY", "").strip()
    if not key:
        raise RuntimeError("CRYPTOQUANT_API_KEY is not available")
    return {"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT}


def request_json(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, 7):
        try:
            response = requests.get(
                f"{BASE_URL}{path}",
                params=params or {},
                headers=headers(),
                timeout=45,
            )
            if response.status_code == 429 or 500 <= response.status_code < 600:
                wait = min(90.0, 2.0 * attempt * attempt)
                log_line(LOG, f"CryptoQuant retryable status={response.status_code} path={path} attempt={attempt} wait={wait:.1f}s")
                time.sleep(wait)
                continue
            response.raise_for_status()
            break
        except Exception as exc:
            last_exc = exc
            if attempt >= 6:
                raise
            wait = min(90.0, 2.0 * attempt * attempt)
            log_line(LOG, f"CryptoQuant request exception path={path} attempt={attempt} wait={wait:.1f}s error={safe_error(exc)}")
            time.sleep(wait)
    else:
        if last_exc:
            raise last_exc
        raise RuntimeError(f"CryptoQuant request failed for {path}")
    payload = response.json()
    status = payload.get("status", {}) if isinstance(payload, dict) else {}
    if status.get("code") not in {200, "200", None}:
        raise RuntimeError(f"CryptoQuant status={status}")
    return payload


def discover_endpoints() -> set[str]:
    payload = request_json("/v1/discovery/endpoints", {"format": "json"})
    rows = payload.get("result", {}).get("data", [])
    return {row.get("path") for row in rows if isinstance(row, dict) and row.get("path")}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def selected_requests() -> list[dict[str, Any]]:
    requests_: list[dict[str, Any]] = []

    exchanges = ["all_exchange", "binance", "coinbase_advanced", "okx", "bybit", "kraken"]
    exchange_metrics = ["reserve", "inflow", "outflow", "netflow"]
    for asset in ["btc", "eth"]:
        for metric in exchange_metrics:
            for exchange in exchanges:
                requests_.append(
                    {
                        "group": f"{asset}_exchange_flows",
                        "path": f"/v1/{asset}/exchange-flows/{metric}",
                        "params": {"exchange": exchange, "window": "day"},
                        "slug": f"{asset}_exchange_{metric}_{exchange}",
                    }
                )

    for metric in ["reserve", "inflow", "outflow", "netflow"]:
        requests_.append(
            {
                "group": "btc_miner_flows",
                "path": f"/v1/btc/miner-flows/{metric}",
                "params": {"miner": "all_miner", "window": "day"},
                "slug": f"btc_miner_{metric}_all_miner",
            }
        )

    btc_indicator_specs = [
        ("/v1/btc/flow-indicator/mpi", {}, "btc_mpi"),
        ("/v1/btc/flow-indicator/exchange-whale-ratio", {"exchange": "all_exchange"}, "btc_exchange_whale_ratio_all_exchange"),
        ("/v1/btc/flow-indicator/exchange-whale-ratio", {"exchange": "binance"}, "btc_exchange_whale_ratio_binance"),
        ("/v1/btc/flow-indicator/fund-flow-ratio", {"exchange": "all_exchange"}, "btc_fund_flow_ratio_all_exchange"),
        ("/v1/btc/flow-indicator/stablecoins-ratio", {"exchange": "all_exchange"}, "btc_stablecoins_ratio_all_exchange"),
        ("/v1/btc/flow-indicator/exchange-supply-ratio", {"exchange": "all_exchange"}, "btc_exchange_supply_ratio_all_exchange"),
        ("/v1/btc/market-indicator/stablecoin-supply-ratio", {}, "btc_stablecoin_supply_ratio"),
        ("/v1/btc/market-indicator/estimated-leverage-ratio", {"exchange": "all_exchange"}, "btc_estimated_leverage_ratio_all_exchange"),
        ("/v1/btc/market-indicator/estimated-leverage-ratio", {"exchange": "binance"}, "btc_estimated_leverage_ratio_binance"),
        ("/v1/btc/market-indicator/mvrv", {}, "btc_mvrv"),
        ("/v1/btc/market-indicator/sopr", {}, "btc_sopr"),
        ("/v1/btc/market-indicator/sopr-ratio", {}, "btc_sopr_ratio"),
        ("/v1/btc/market-indicator/realized-price", {}, "btc_realized_price"),
    ]
    for path, params, slug in btc_indicator_specs:
        merged = {"window": "day", **params}
        requests_.append({"group": "btc_indicators", "path": path, "params": merged, "slug": slug})

    eth_indicator_specs = [
        ("/v1/eth/flow-indicator/exchange-supply-ratio", {"exchange": "all_exchange"}, "eth_exchange_supply_ratio_all_exchange"),
        ("/v1/eth/market-indicator/estimated-leverage-ratio", {"exchange": "all_exchange"}, "eth_estimated_leverage_ratio_all_exchange"),
        ("/v1/eth/market-indicator/estimated-leverage-ratio", {"exchange": "binance"}, "eth_estimated_leverage_ratio_binance"),
    ]
    for path, params, slug in eth_indicator_specs:
        merged = {"window": "day", **params}
        requests_.append({"group": "eth_indicators", "path": path, "params": merged, "slug": slug})

    for token in ["all_token", "usdt_eth", "usdc"]:
        requests_.append(
            {
                "group": "stablecoin_network",
                "path": "/v1/stablecoin/network-data/supply",
                "params": {"token": token, "window": "day"},
                "slug": f"stablecoin_supply_{token}",
            }
        )
        if token != "all_token":
            requests_.append(
                {
                    "group": "stablecoin_market",
                    "path": "/v1/stablecoin/market-data/capitalization",
                    "params": {"token": token, "window": "day"},
                    "slug": f"stablecoin_capitalization_{token}",
                }
            )
        for metric in ["reserve", "inflow", "outflow", "netflow"]:
            for exchange in ["all_exchange", "binance"]:
                requests_.append(
                    {
                        "group": "stablecoin_exchange_flows",
                        "path": f"/v1/stablecoin/exchange-flows/{metric}",
                        "params": {"token": token, "exchange": exchange, "window": "day"},
                        "slug": f"stablecoin_{metric}_{token}_{exchange}",
                    }
                )

    return requests_


def rows_to_frame(rows: list[dict[str, Any]], spec: dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df.insert(0, "provider", "CryptoQuant")
    df.insert(1, "endpoint", spec["path"])
    df.insert(2, "metric_slug", spec["slug"])
    for key, value in spec["params"].items():
        df[f"param_{key}"] = value
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    sort_cols = [col for col in ["date", "metric_slug", "param_exchange", "param_token", "param_miner"] if col in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)
    return df.drop_duplicates().reset_index(drop=True)


def fetch_spec(spec: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = request_json(spec["path"], spec["params"])
        rows = payload.get("result", {}).get("data", [])
        if not isinstance(rows, list):
            rows = []
        df = rows_to_frame(rows, spec)
        output = OUT_DIR / spec["group"] / f"{slugify(spec['slug'])}.parquet"
        if not df.empty:
            write_table(df, output)
        return {
            "slug": spec["slug"],
            "group": spec["group"],
            "path": spec["path"],
            "params": spec["params"],
            "status": "ok" if not df.empty else "empty",
            "rows": int(len(df)),
            "output": str(output.relative_to(ROOT)) if not df.empty else "",
            "columns": list(df.columns),
        }
    except Exception as exc:
        return {
            "slug": spec["slug"],
            "group": spec["group"],
            "path": spec["path"],
            "params": spec["params"],
            "status": "failed",
            "rows": 0,
            "error": safe_error(exc),
        }


def write_docs_and_summary(results: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    data_files = sorted(OUT_DIR.rglob("*.parquet"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ok = [item for item in results if item["status"] == "ok"]
    empty = [item for item in results if item["status"] == "empty"]
    failed = [item for item in results if item["status"] == "failed"]
    rows_total = sum(item.get("rows", 0) for item in ok)
    groups = sorted({item["group"] for item in ok})

    readme = [
        "# CryptoQuant",
        "",
        "Stage 1.5 paid CryptoQuant acquisition for Project 3.",
        "",
        "The worker fetches high-value Professional-tier endpoints that validated at runtime: BTC/ETH exchange flows, BTC miner flows, selected BTC/ETH market and flow indicators, and stablecoin supply/exchange-flow metrics.",
        "",
        "Observed API behavior on 2026-05-01: the Professional plan accepts current/recent daily pulls, while older explicit ranges such as 2024 and 2017 return `Out of allowed request range` for tested metrics. Treat this acquisition as recent-window paid data unless CryptoQuant support confirms a historical export path.",
        "",
        f"Generated: {utc_now()}",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    (OUT_DIR / "data_dictionary.md").write_text(
        "\n".join(
            [
                "# Data Dictionary",
                "",
                "- `provider`: source provider name.",
                "- `endpoint`: CryptoQuant API path.",
                "- `metric_slug`: local normalized metric identifier.",
                "- `param_*`: endpoint request parameters used for the pull.",
                "- `date`: UTC timestamp/date supplied by CryptoQuant, when present.",
                "- Remaining columns preserve CryptoQuant metric names as supplied by the API.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    provenance = {
        "source": "CryptoQuant",
        "acquired_at": utc_now(),
        "description": "Stage 1.5 paid CryptoQuant Professional acquisition; recent-window on-chain/exchange-flow metrics.",
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)} for path in data_files],
        "endpoint_summary": {
            "requested": len(results) + len(skipped),
            "ok": len(ok),
            "empty": len(empty),
            "failed": len(failed),
            "skipped_not_discovered": len(skipped),
        },
    }
    (OUT_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    append_acquisition_log(
        {
            "timestamp": utc_now(),
            "source": "CryptoQuant",
            "dataset": "stage15_cryptoquant_professional",
            "status": "ok" if ok else "failed",
            "path": str(OUT_DIR.relative_to(ROOT)),
            "notes": f"files={len(data_files)} rows={rows_total} ok={len(ok)} empty={len(empty)} failed={len(failed)} skipped={len(skipped)}",
        }
    )

    summary = {
        "generated_at": utc_now(),
        "stage": "Stage 1.5 paid data acquisition",
        "provider": "CryptoQuant",
        "status": "ok" if ok else "failed",
        "plan_observed": "Professional API accepted with User-Agent; recent/default daily window returns up to 100 rows per endpoint.",
        "historical_range_note": "Explicit older date ranges tested before acquisition returned Out of allowed request range; treat as recent-window coverage unless vendor support confirms historical access/export.",
        "requested": len(results) + len(skipped),
        "ok": len(ok),
        "empty": len(empty),
        "failed": len(failed),
        "skipped_not_discovered": len(skipped),
        "rows_total": rows_total,
        "groups": groups,
        "files": [str(path.relative_to(ROOT)) for path in data_files],
        "failures": failed[:120],
        "empty_results": empty[:120],
        "skipped": skipped[:120],
    }
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Stage 1.5 CryptoQuant Acquisition",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Status: {summary['status']}",
        f"- Requested endpoints: {summary['requested']}",
        f"- Successful endpoints: {summary['ok']}",
        f"- Empty endpoints: {summary['empty']}",
        f"- Failed endpoints: {summary['failed']}",
        f"- Rows acquired: {summary['rows_total']}",
        f"- Files: {len(summary['files'])}",
        f"- Groups: {', '.join(summary['groups'])}",
        "",
        "## Coverage Note",
        "",
        f"- {summary['plan_observed']}",
        f"- {summary['historical_range_note']}",
        "",
        "## Deliverable",
        "",
        f"- `{OUT_DIR.relative_to(ROOT)}`",
    ]
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Stage 1.5 CryptoQuant Professional data.")
    parser.add_argument("--limit", type=int, default=0, help="Limit request count for smoke tests; 0 means all selected requests.")
    args = parser.parse_args()

    load_env()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log_line(LOG, "START CryptoQuant Stage 1.5 acquisition")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in OUT_DIR.rglob("*.parquet"):
        old_file.unlink()

    available = discover_endpoints()
    specs = selected_requests()
    if args.limit:
        specs = specs[: args.limit]

    skipped = [
        {"slug": spec["slug"], "path": spec["path"], "params": spec["params"], "status": "skipped_not_discovered"}
        for spec in specs
        if spec["path"] not in available
    ]
    specs = [spec for spec in specs if spec["path"] in available]

    results = []
    for index, spec in enumerate(specs, start=1):
        result = fetch_spec(spec)
        results.append(result)
        log_line(LOG, f"CryptoQuant {index}/{len(specs)} slug={spec['slug']} status={result['status']} rows={result.get('rows', 0)}")
        time.sleep(0.75)

    summary = write_docs_and_summary(results, skipped)
    log_line(LOG, f"DONE CryptoQuant status={summary['status']} ok={summary['ok']} rows={summary['rows_total']} failed={summary['failed']}")


if __name__ == "__main__":
    main()
