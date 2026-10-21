#!/usr/bin/env python3
"""FXMacroData HISTORY pull with consensus vintages (2020-2024), bounded and governed (Satoshi, 2026-10-21).

Answers the open item of work_plan/ECONOMIC_CALENDAR_ACQUISITION_REQUEST_2026_10_19.md: the stage-15 worker has no
--from/--to, no `predictions` (consensus) endpoint and no dry run. This is a NEW worker; stage 15 is unchanged.

Rules enforced in code:
  * The API key is read ONLY from the process environment variable FXMACRODATA_API_KEY, i.e. what an existing systemd
    EnvironmentFile= provides. This worker never opens a .env file, never prints, logs or stores the key, and redacts
    it from any error text. Without the variable it refuses (except --dry-run, which needs no key and no network).
  * At most 1 request per second (provider fair use), bounded total requests (--max-requests), no retry storms (one
    retry after 30 s on 429/5xx, then the item is recorded FAILED and skipped).
  * TEST boundary: --to may not exceed 2025-01-01 (the period this lane is allowed to read).
  * Every response is stored as received (raw JSON lines) with request_sha256 (URL WITHOUT the key), response_sha256,
    HTTP status and the receipt clock; nothing is overwritten (append-only run directory).
  * Normalisation keeps the provider timestamps and labels each consensus row: PRE_RELEASE (vintage strictly before
    the announcement instant), CONSENSUS_VINTAGE_AFTER_RELEASE (unusable as a pre-release snapshot) or
    CONSENSUS_VINTAGE_UNKNOWN (no vintage field).

Usage (dry run first; the real run is executed by the governed data path, not by hand):
    python _scripts/workers/stage16_fxmacrodata_history_worker.py --out <run_dir> --dry-run
    python _scripts/workers/stage16_fxmacrodata_history_worker.py --out <run_dir> --probe        # 1 bounded probe / currency
    python _scripts/workers/stage16_fxmacrodata_history_worker.py --out <run_dir>                  # full bounded pull
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

BASE_URL = "https://fxmacrodata.com/api/v1"
TEST_START = "2025-01-01"
FAMILIES = {
    "usd": ["policy_rate", "non_farm_payrolls", "unemployment", "average_hourly_earnings", "initial_jobless_claims",
            "inflation", "inflation_mom", "core_inflation", "core_inflation_mom", "pce", "core_pce", "ppi", "gdp",
            "retail_sales", "durable_goods_orders", "industrial_production", "pmi", "nmi", "consumer_sentiment",
            "business_sentiment", "job_openings"],
    "eur": ["policy_rate", "unemployment", "inflation", "inflation_mom", "core_inflation", "ppi", "gdp", "retail_sales"],
}
ENDPOINTS = ("announcements", "predictions")


class Refusal(RuntimeError):
    pass


def redact(text: str, key: str | None) -> str:
    text = re.sub(r"([?&]api_key=)[^&\s]+", r"\1<redacted>", text)
    return text.replace(key, "<redacted>") if key else text


def plan(currencies, date_from: str, date_to: str, include_predictions: bool, date_params=("start_date", "end_date")):
    if date_to > TEST_START:
        raise Refusal(f"TEST_BOUNDARY: --to {date_to} exceeds {TEST_START}")
    if date_from >= date_to:
        raise Refusal("EMPTY_WINDOW")
    out = [{"endpoint": f"calendar/{c}", "params": {date_params[0]: date_from, date_params[1]: date_to}} for c in currencies]
    for c in currencies:
        for ind in FAMILIES[c]:
            for ep in ENDPOINTS if include_predictions else ENDPOINTS[:1]:
                out.append({"endpoint": f"{ep}/{c}/{ind}", "params": {date_params[0]: date_from, date_params[1]: date_to}})
    return out


def request_sha(endpoint: str, params: dict) -> str:
    """Hash of the request WITHOUT the key (stable identity of what was asked)."""
    return hashlib.sha256(f"{BASE_URL}/{endpoint}?{urlencode(sorted(params.items()))}".encode()).hexdigest()


class Throttle:
    def __init__(self, min_interval: float = 1.05, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.min_interval, self.clock, self.sleep, self.last = min_interval, clock, sleep, None

    def wait(self):
        if self.last is not None:
            dt = self.clock() - self.last
            if dt < self.min_interval:
                self.sleep(self.min_interval - dt)
        self.last = self.clock()


def label_consensus(row: dict) -> str:
    """PRE_RELEASE / CONSENSUS_VINTAGE_AFTER_RELEASE / CONSENSUS_VINTAGE_UNKNOWN from the provider's own fields."""
    rel = row.get("announcement_datetime")
    vin = next((row.get(k) for k in ("prediction_datetime", "forecast_datetime", "published_at", "vintage_datetime",
                                      "updated_at") if row.get(k) is not None), None)
    if rel is None or vin is None:
        return "CONSENSUS_VINTAGE_UNKNOWN"
    try:
        r, v = float(rel), float(vin)
    except (TypeError, ValueError):
        try:
            r = datetime.fromisoformat(str(rel).replace("Z", "+00:00")).timestamp()
            v = datetime.fromisoformat(str(vin).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return "CONSENSUS_VINTAGE_UNKNOWN"
    return "PRE_RELEASE" if v < r else "CONSENSUS_VINTAGE_AFTER_RELEASE"


def run(args, fetch: Callable[[str, dict, str], tuple[int, bytes]] | None = None, throttle: Throttle | None = None) -> dict:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    reqs = plan(args.currencies, args.date_from, args.date_to, not args.no_predictions,
                tuple(args.date_params.split(",")))
    if args.probe:
        reqs = [r for r in reqs if r["endpoint"].startswith(("announcements/", "predictions/")) and
                r["endpoint"].split("/")[-1] in ("non_farm_payrolls", "inflation")]
    reqs = reqs[: args.max_requests]
    summary = {"worker": "stage16_fxmacrodata_history_worker", "planned_requests": len(reqs), "from": args.date_from,
               "to": args.date_to, "dry_run": bool(args.dry_run), "probe": bool(args.probe), "started_utc": datetime.now(timezone.utc).isoformat()}
    if args.dry_run:
        (out / "PLAN.json").write_text(json.dumps({"summary": summary, "requests": reqs}, indent=1))
        return summary
    key = os.environ.get("FXMACRODATA_API_KEY", "").strip()
    if not key:
        raise Refusal("NO_KEY_IN_ENVIRONMENT: run under the governed systemd unit (EnvironmentFile=); this worker never reads .env files")
    if fetch is None:
        import requests

        def fetch(endpoint, params, k):
            r = requests.get(f"{BASE_URL}/{endpoint}", params={**params, "api_key": k}, timeout=45)
            return r.status_code, r.content
    th = throttle or Throttle()
    raw = open(out / "RAW.jsonl", "a")
    stats = {"ok": 0, "failed": 0, "rows": 0, "consensus_labels": {}}
    for rq in reqs:
        status, body = None, b""
        for attempt in (1, 2):
            th.wait()
            try:
                status, body = fetch(rq["endpoint"], rq["params"], key)
            except Exception as exc:                      # network error: one retry, then recorded
                status, body = -1, redact(f"{type(exc).__name__}: {exc}", key).encode()
            if status in (429,) or (isinstance(status, int) and status >= 500) or status == -1:
                if attempt == 1:
                    th.sleep(30)
                    continue
            break
        rec = {"endpoint": rq["endpoint"], "params": rq["params"], "request_sha256": request_sha(rq["endpoint"], rq["params"]),
               "status": status, "receipt_utc": datetime.now(timezone.utc).isoformat(),
               "response_sha256": hashlib.sha256(body).hexdigest(), "body": redact(body.decode("utf-8", "replace"), key)}
        raw.write(json.dumps(rec) + "\n")
        raw.flush()
        if status == 200:
            stats["ok"] += 1
            try:
                rows = json.loads(body).get("data", [])
            except (ValueError, AttributeError):
                rows = []
            stats["rows"] += len(rows) if isinstance(rows, list) else 0
            if rq["endpoint"].startswith("predictions/") and isinstance(rows, list):
                for r_ in rows:
                    lab = label_consensus(r_) if isinstance(r_, dict) else "CONSENSUS_VINTAGE_UNKNOWN"
                    stats["consensus_labels"][lab] = stats["consensus_labels"].get(lab, 0) + 1
        else:
            stats["failed"] += 1
    raw.close()
    summary.update(stats, finished_utc=datetime.now(timezone.utc).isoformat())
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=1))
    return summary


def parser():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="append-only run directory OUTSIDE Git")
    ap.add_argument("--currencies", nargs="*", default=["usd", "eur"])
    ap.add_argument("--from", dest="date_from", default="2019-12-01")
    ap.add_argument("--to", dest="date_to", default=TEST_START)
    ap.add_argument("--no-predictions", action="store_true")
    ap.add_argument("--date-params", default="start_date,end_date", help="provider query names for the window")
    ap.add_argument("--max-requests", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probe", action="store_true", help="only NFP and CPI (announcements + predictions) per currency")
    return ap


def main(argv=None) -> int:
    try:
        s = run(parser().parse_args(argv))
    except Refusal as exc:
        print(json.dumps({"refused": str(exc)}))
        return 2
    print(json.dumps({k: v for k, v in s.items() if k != "requests"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
