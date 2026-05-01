from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from stage13_common import ROOT, append_acquisition_log, load_env, log_line, polite_sleep, write_docs, write_table


LOG = ROOT / "_logs" / "gamma" / "stage13_remaining_free_worker.log"


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


def append_gap(name: str, detail: str) -> None:
    path = ROOT / "_logs" / "gamma" / "stage13_remaining_free_gaps.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- {datetime.now(timezone.utc).isoformat()} {name}: {detail}\n")


def etherscan_request(action: str, extra: dict[str, str] | None = None) -> dict:
    key = os.environ.get("ETHERSCAN_API_KEY")
    if not key:
        raise RuntimeError("ETHERSCAN_API_KEY is not available")
    params = {"chainid": "1", "module": "stats", "action": action, "apikey": key}
    if extra:
        params.update(extra)
    r = requests.get("https://api.etherscan.io/v2/api", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_etherscan_free_snapshots() -> None:
    folder = ROOT / "alternative_data" / "onchain_eth" / "etherscan_free_snapshots"
    out = folder / "snapshots.parquet"
    if out.exists() or out.with_suffix(".csv").exists():
        log_line(LOG, "skip existing Etherscan free snapshots")
        return
    rows = []
    actions = ["ethprice", "ethsupply"]
    for action in actions:
        log_line(LOG, f"fetch Etherscan {action}")
        payload = etherscan_request(action)
        rows.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": payload.get("status"),
            "message": payload.get("message"),
            "result_json": json.dumps(payload.get("result"), sort_keys=True),
        })
        polite_sleep(0.25)
    gas = requests.get(
        "https://api.etherscan.io/v2/api",
        params={"chainid": "1", "module": "gastracker", "action": "gasoracle", "apikey": os.environ.get("ETHERSCAN_API_KEY", "")},
        timeout=60,
    )
    gas.raise_for_status()
    payload = gas.json()
    rows.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "gasoracle",
        "status": payload.get("status"),
        "message": payload.get("message"),
        "result_json": json.dumps(payload.get("result"), sort_keys=True),
    })
    save(pd.DataFrame(rows), folder, "snapshots.parquet", "Etherscan API V2", "Free Etherscan ETH price, supply, and gas oracle snapshots.")

    pro_gaps = []
    for action in ["dailytx", "dailyavgblocksize", "dailyavggasprice", "dailynewaddress"]:
        payload = etherscan_request(action, {"startdate": "2025-01-01", "enddate": "2025-01-05", "sort": "asc"})
        if payload.get("status") != "1":
            pro_gaps.append(f"{action}: {payload.get('result') or payload.get('message')}")
        polite_sleep(0.25)
    if pro_gaps:
        append_gap("Etherscan historical endpoints", "; ".join(pro_gaps))


def parse_oecd_generic_xml(text: str) -> pd.DataFrame:
    root = ET.fromstring(text)
    rows: list[dict[str, str]] = []
    for series in root.iter():
        if not series.tag.endswith("Series"):
            continue
        series_keys: dict[str, str] = {}
        for child in series:
            if child.tag.endswith("SeriesKey"):
                for value in child:
                    if value.tag.endswith("Value"):
                        series_keys[value.attrib.get("id", "key")] = value.attrib.get("value", "")
        for obs in series:
            if not obs.tag.endswith("Obs"):
                continue
            row = dict(series_keys)
            for item in obs:
                if item.tag.endswith("ObsDimension"):
                    row["period"] = item.attrib.get("value", "")
                elif item.tag.endswith("ObsValue"):
                    row["value"] = item.attrib.get("value", "")
            if row:
                rows.append(row)
    return pd.DataFrame(rows)


def fetch_oecd_cli() -> None:
    folder = ROOT / "macro_economic" / "oecd" / "cli"
    out = folder / "monthly.parquet"
    if out.exists() or out.with_suffix(".csv").exists():
        log_line(LOG, "skip existing OECD CLI")
        return
    url = "https://sdmx.oecd.org/public/rest/v1/data/OECD.SDD.STES,DSD_STES@DF_CLI/.M.LI...AA...H"
    log_line(LOG, "fetch OECD CLI selected indicators")
    r = requests.get(url, params={"startPeriod": "2000-01", "endPeriod": "2025-12"}, timeout=120)
    r.raise_for_status()
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / "raw_response.xml"
    raw.write_text(r.text, encoding="utf-8")
    df = parse_oecd_generic_xml(r.text)
    if df.empty:
        append_gap("OECD CLI", "endpoint returned no parsed observations")
        return
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    save(df, folder, "monthly.parquet", "OECD SDMX", "OECD Composite Leading Indicator selected free SDMX data.")


def fetch_finra_regsho_daily() -> None:
    folder = ROOT / "alternative_data" / "short_interest" / "finra_regsho_daily"
    done = folder / "stage13_finra_regsho_done.json"
    if done.exists():
        log_line(LOG, "skip existing FINRA Reg SHO daily")
        return
    venues = ["CNMS", "FNSQ", "FNYX"]
    dates = pd.bdate_range("2025-01-01", "2025-12-31")
    summary = {}
    for venue in venues:
        rows = []
        for date in dates:
            ymd = date.strftime("%Y%m%d")
            url = f"https://cdn.finra.org/equity/regsho/daily/{venue}shvol{ymd}.txt"
            try:
                r = requests.get(url, timeout=30)
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                batch = pd.read_csv(StringIO(r.text), sep="|")
                batch["venue_file"] = venue
                rows.append(batch)
                polite_sleep(0.03)
            except Exception as exc:
                log_line(LOG, f"FINRA {venue} {ymd} failed: {exc}")
        if rows:
            df = pd.concat(rows, ignore_index=True)
            save(
                df,
                folder / venue.lower(),
                "2025_daily_short_volume.parquet",
                "FINRA Reg SHO Daily Short Sale Volume",
                f"FINRA Reg SHO daily short sale volume for {venue}, 2025. This is related free short-volume data; bi-weekly short-interest mapping remains a validation follow-up.",
            )
            summary[venue] = len(df)
    done.parent.mkdir(parents=True, exist_ok=True)
    done.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "rows_by_venue": summary}, indent=2) + "\n", encoding="utf-8")
    append_gap("FINRA bi-weekly short interest", "FINRA Reg SHO daily short volume acquired for 2025; true bi-weekly short-interest bulk mapping still needs source-specific validation.")


def write_bea_gap_note() -> None:
    folder = ROOT / "macro_economic" / "bea"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "stage13_bea_gap.md"
    if path.exists():
        return
    path.write_text(
        """# Stage 1.3 BEA Gap

Stage: 1.3 Free Data Acquisition
Agent: Gamma remaining-free worker

No `BEA_API_KEY` was available in `_metadata/.env`. BEA series already covered by FRED remain available in `macro_economic/fred/`. Direct BEA API acquisition is held for Stage 1.4/validation unless a key is added or a keyless endpoint is approved.
""",
        encoding="utf-8",
    )


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    load_env()
    log_line(LOG, "START gamma remaining free-source worker")
    for fn in [fetch_etherscan_free_snapshots, fetch_oecd_cli, fetch_finra_regsho_daily, write_bea_gap_note]:
        try:
            fn()
        except Exception as exc:
            log_line(LOG, f"ERROR {fn.__name__}: {exc}")
    log_line(LOG, "DONE gamma remaining free-source worker")


if __name__ == "__main__":
    main()
