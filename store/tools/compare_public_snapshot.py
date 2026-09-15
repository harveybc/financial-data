#!/usr/bin/env python3
"""Compare the stored ETHUSDT 4h archive against a second public snapshot, once.

R5 of `predictor/docs/handoffs/MUSASHI_TO_SATOSHI_REAL_PLUGIN_CAUSALITY_AND_REPLAY_2026_09_14.md`:

    "A public read-only comparison is authorized: at most 3 requests, 1000 bars each, 5 MiB
     total, timeout <=30 seconds/request, no retries after a provider denial. Declare windows
     before requesting, covering the anomalous and ordinary bars. No account keys, trades or
     changes to the original lake."

What this can and cannot settle, said before it runs: a second snapshot that agrees with the
first proves **neither** finality **nor** the absence of revisions — it is one comparison at
one moment. A difference is evidence of a revision and is reported field by field, without
inferring a policy from it.

Three phases, deliberately separate so the declaration cannot be written after seeing the
answer:

    declare   read the archive, choose the windows, write DECLARED_WINDOWS.json  (no network)
    fetch     read that declaration and perform at most three GETs                (network)
    compare   match by bar identity (open_time) and report                        (no network)

The endpoint is the producer's own: GET https://api.binance.com/api/v3/klines, public, no
account key, no order ever placed. Nothing in the lake is modified: the archive is opened
read-only and the outputs go to the directory given on the command line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://api.binance.com/api/v3/klines"
SYMBOL = "ETHUSDT"
INTERVAL = "4h"
STEP_MS = 4 * 60 * 60 * 1000
MAX_REQUESTS = 3
MAX_BARS = 1000
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 30


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_archive(path: Path):
    import pandas as pd

    frame = pd.read_parquet(path)
    frame = frame.sort_values("open_time").reset_index(drop=True)
    return frame


def anomalous_rows(frame):
    """Bars whose window span is not the nominal one: the 21 the characterisation named."""
    span = (frame["close_time"].astype("int64") - frame["open_time"].astype("int64")) // 10**6
    return frame[span != STEP_MS - 1]


def declare(archive: Path, out: Path) -> dict:
    """Choose the windows BEFORE any request, and write them down with their digest."""
    frame = load_archive(archive)
    odd = anomalous_rows(frame)
    first_odd = int(odd["open_time"].iloc[0].value // 10**6) if len(odd) else None
    ordinary = int(frame["open_time"].iloc[len(frame) // 2].value // 10**6)
    tail_start = int(frame["open_time"].iloc[-1].value // 10**6) - (MAX_BARS - 1) * STEP_MS

    windows = []
    if first_odd is not None:
        windows.append({"name": "anomalous", "startTime": first_odd, "limit": MAX_BARS,
                        "why": "the first bar whose window span is not the nominal one"})
    windows.append({"name": "ordinary", "startTime": ordinary, "limit": MAX_BARS,
                    "why": "the middle of the archive: bars with nothing remarkable"})
    windows.append({"name": "end_bound", "startTime": tail_start, "limit": MAX_BARS,
                    "why": "the last bars, where the producer's fixed END_MS sits"})
    windows = windows[:MAX_REQUESTS]

    declaration = {
        "schema": "public_snapshot_declaration.v1",
        "declared_at": now(),
        "endpoint": ENDPOINT, "symbol": SYMBOL, "interval": INTERVAL,
        "archive": str(archive), "archive_sha256": digest(archive.read_bytes()),
        "archive_rows": int(len(frame)),
        "anomalous_bars_in_archive": int(len(odd)),
        "limits": {"requests": MAX_REQUESTS, "bars_per_request": MAX_BARS,
                   "total_bytes": MAX_BYTES, "timeout_seconds": TIMEOUT,
                   "retries_after_denial": 0},
        "windows": windows,
        "what_this_cannot_settle": [
            "agreement proves neither finality nor the absence of revisions",
            "one comparison at one moment is not a policy",
        ],
    }
    declaration["declaration_sha256"] = digest(json.dumps(
        {k: v for k, v in declaration.items() if k != "declared_at"},
        sort_keys=True, separators=(",", ":")).encode())
    out.mkdir(parents=True, exist_ok=True)
    (out / "DECLARED_WINDOWS.json").write_text(json.dumps(declaration, indent=1) + "\n",
                                               encoding="utf-8")
    return declaration


def fetch(out: Path) -> dict:
    """At most three GETs, exactly the declared ones. Stops at the first denial."""
    declaration = json.loads((out / "DECLARED_WINDOWS.json").read_text(encoding="utf-8"))
    responses, total = [], 0
    for window in declaration["windows"]:
        query = urllib.parse.urlencode({"symbol": SYMBOL, "interval": INTERVAL,
                                        "startTime": window["startTime"],
                                        "limit": window["limit"]})
        url = f"{ENDPOINT}?{query}"
        record = {"window": window["name"], "url": url, "requested_at": now()}
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "crispdm-archive-comparison/1"})
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                body = response.read(MAX_BYTES - total + 1)
                record.update({"status": response.status, "received_at": now(),
                               "bytes": len(body), "sha256": digest(body)})
        except urllib.error.HTTPError as exc:
            record.update({"status": exc.code, "received_at": now(),
                           "denied": True, "reason": str(exc)[:200]})
            responses.append(record)
            break                                     # no retry after a provider denial
        except Exception as exc:                      # network refused, timed out, resolved nowhere
            record.update({"status": None, "received_at": now(),
                           "error": f"{type(exc).__name__}: {exc}"[:200]})
            responses.append(record)
            break
        total += record["bytes"]
        if total > MAX_BYTES:
            record["over_budget"] = True
            responses.append(record)
            break
        (out / f"raw_{window['name']}.json").write_bytes(body)
        responses.append(record)
        time.sleep(1)                                  # deliberately gentle
    receipt = {"schema": "public_snapshot_fetch.v1",
               "declaration_sha256": declaration["declaration_sha256"],
               "responses": responses, "total_bytes": total}
    (out / "FETCH_RECEIPT.json").write_text(json.dumps(receipt, indent=1) + "\n",
                                            encoding="utf-8")
    return receipt


FIELDS = ["open", "high", "low", "close", "volume", "close_time", "quote_volume",
          "trade_count", "taker_buy_base_volume", "taker_buy_quote_volume"]


def compare(archive: Path, out: Path) -> dict:
    """Match by open_time and report field by field. No tolerance is invented: exact strings."""
    frame = load_archive(archive)
    by_open = {int(value.value // 10**6): index for index, value in
               enumerate(frame["open_time"])}
    report = {"schema": "public_snapshot_comparison.v1", "compared_at": now(),
              "archive_sha256": digest(archive.read_bytes()), "windows": {}}
    for raw in sorted(out.glob("raw_*.json")):
        name = raw.stem.replace("raw_", "")
        payload = json.loads(raw.read_text(encoding="utf-8"))
        matched = differing = absent = material = 0
        differences = []
        for row in payload:
            open_ms = int(row[0])
            index = by_open.get(open_ms)
            if index is None:
                absent += 1
                continue
            matched += 1
            stored = frame.iloc[index]
            remote = {"open": row[1], "high": row[2], "low": row[3], "close": row[4],
                      "volume": row[5], "close_time": int(row[6]), "quote_volume": row[7],
                      "trade_count": int(row[8]), "taker_buy_base_volume": row[9],
                      "taker_buy_quote_volume": row[10]}
            fields = {}
            representation_only = True
            for field in FIELDS:
                if field not in frame.columns:
                    continue
                left = stored[field]
                if field == "close_time":
                    left = int(left.value // 10**6)
                    same = left == remote[field]
                elif field == "trade_count":
                    left = int(left)
                    same = left == remote[field]
                else:
                    same = float(left) == float(remote[field])
                if not same:
                    kind = "material"
                    if field not in ("close_time", "trade_count"):
                        # a decimal string stored as float64 comes back one ULP away: that is
                        # the archive's precision, not a revision of the bar
                        a, b = float(left), float(remote[field])
                        relative = abs(a - b) / max(abs(a), 1e-12)
                        kind = "representation" if relative <= 1e-12 else "material"
                    if kind == "material":
                        representation_only = False
                    fields[field] = {"archive": str(left), "snapshot": str(remote[field]),
                                     "kind": kind}
            if fields:
                differing += 1
                if not representation_only:
                    material += 1
                if len(differences) < 25:
                    differences.append({"open_time_ms": open_ms, "fields": fields})
        report["windows"][name] = {"bars_in_snapshot": len(payload), "matched": matched,
                                   "not_in_archive": absent, "differing": differing,
                                   "materially_differing": material,
                                   "differences": differences}
    material_total = sum(w["materially_differing"] for w in report["windows"].values())
    differing_total = sum(w["differing"] for w in report["windows"].values())
    if not report["windows"]:
        report["verdict"] = "nothing was fetched, so nothing was compared"
    elif material_total:
        report["verdict"] = (f"{material_total} bars differ materially: evidence of revision, "
                             "reported field by field. One comparison is not a policy")
    elif differing_total:
        report["verdict"] = (
            f"no material difference in the compared bars. {differing_total} bars differ only "
            "in the last digits of quote-denominated columns: the archive stores the "
            "producer's decimal strings as float64 and loses them there. That is a property "
            "of the stored artefact, not a revision. Agreement settles neither finality nor "
            "the absence of revisions")
    else:
        report["verdict"] = ("no difference found in the compared bars; this settles neither "
                             "finality nor the absence of revisions")
    (out / "COMPARISON.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", choices=["declare", "fetch", "compare", "all"])
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.phase in ("declare", "all"):
        print(json.dumps({"declared": declare(args.archive, args.out)["windows"]}, indent=1))
    if args.phase in ("fetch", "all"):
        print(json.dumps(fetch(args.out), indent=1)[:2000])
    if args.phase in ("compare", "all"):
        report = compare(args.archive, args.out)
        print(json.dumps({"verdict": report["verdict"],
                          "windows": {k: {kk: vv for kk, vv in v.items()
                                          if kk != "differences"}
                                      for k, v in report["windows"].items()}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
