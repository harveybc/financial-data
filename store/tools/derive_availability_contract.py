#!/usr/bin/env python3
"""Derive a resource availability contract from the bytes of one financial resource.

A2 of `predictor/docs/handoffs/MUSASHI_TO_SATOSHI_CONTRACTS_AND_CONSUMER_ADOPTION_2026_09_14.md`:
follow one resource to its producer and demonstrate the properties instead of naming them.
Nothing here is installed; the output is a **candidate** contract plus the evidence a
reviewer needs to accept or reject it.

What counts as evidence here:

* the file's own digest against the digest its producer pinned (`provenance.json`);
* the physical schema — a tz-aware timestamp column is a producer statement about the time
  zone, a column *name* is not;
* the relation between the event column and the availability column, measured on every row;
* the grid, its gaps and its truncated bars, counted rather than assumed;
* what cannot be shown: provider delivery latency, revision policy and usage rights are
  reported as UNKNOWN with the reason. UNOBSERVED is not zero.

usage:
  derive_availability_contract.py --root ROOT --resource REL/PATH.parquet
      --event-column open_time --available-column close_time --frequency 4h
      --out DIR [--sample-rows N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def pinned_digests(root: Path, resource: str) -> dict:
    """What the producer's own `provenance.json` says about this file, if anything."""
    directory = (root / resource).parent
    found = {}
    for name in ("provenance.json",):
        path = directory / name
        if not path.is_file():
            continue
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            found[name] = {"error": "unparseable"}
            continue
        entries = {entry.get("path"): entry.get("sha256") for entry in body.get("files", [])
                   if isinstance(entry, dict)}
        found[name] = {"source": body.get("source"), "description": body.get("description"),
                       "acquired_at": body.get("acquired_at"),
                       "declared_sha256": entries.get(resource),
                       "declares_this_file": resource in entries,
                       "path": str(path.relative_to(root))}
    return found


def read_frame(path: Path, columns):
    import pandas as pd

    if path.suffix == ".parquet":
        return pd.read_parquet(path, columns=list(columns))
    return pd.read_csv(path, usecols=list(columns))


def describe_column(series) -> dict:
    import pandas as pd

    dtype = str(series.dtype)
    tz = getattr(getattr(series, "dt", None), "tz", None)
    return {"dtype": dtype, "timezone_in_schema": str(tz) if tz is not None else None,
            "is_datetime": bool(pd.api.types.is_datetime64_any_dtype(series)),
            "nulls": int(series.isna().sum()),
            "first": str(series.iloc[0]) if len(series) else None,
            "last": str(series.iloc[-1]) if len(series) else None}


def measure(path: Path, event_column: str, available_column: str, frequency: str) -> dict:
    import numpy as np
    import pandas as pd

    frame = read_frame(path, (event_column, available_column))
    event, available = frame[event_column], frame[available_column]
    step = pd.Timedelta(frequency)
    facts = {
        "rows": int(len(frame)),
        "event_column": describe_column(event),
        "available_column": describe_column(available),
        "event_monotonic_increasing": bool(event.is_monotonic_increasing),
        "event_duplicates": int(event.duplicated().sum()),
    }
    if not (pd.api.types.is_datetime64_any_dtype(event)
            and pd.api.types.is_datetime64_any_dtype(available)):
        facts["measured"] = False
        facts["why"] = "the two columns are not both timestamps in the physical schema"
        return facts

    delta = (available - event)
    spacing = event.diff().dropna()
    span = (delta.dt.total_seconds() * 1000).round().astype("int64")
    epoch_ms = (event.astype("int64") // 10**6) if str(event.dtype).startswith("datetime64[ns") \
        else event.astype("int64")
    on_grid = (epoch_ms % int(step.total_seconds() * 1000) == 0)
    facts.update({
        "measured": True,
        "available_minus_event_ms": {"min": int(span.min()), "max": int(span.max()),
                                     "distinct": int(span.nunique()),
                                     "modal": int(span.mode().iloc[0])},
        "available_at_or_after_event_always": bool((delta >= pd.Timedelta(0)).all()),
        "available_strictly_after_event": int((delta > pd.Timedelta(0)).sum()),
        "available_equal_to_event": int((delta == pd.Timedelta(0)).sum()),
        "available_within_one_step_always": bool((delta <= step).all()),
        "spacing_seconds": {"min": float(spacing.dt.total_seconds().min()),
                            "max": float(spacing.dt.total_seconds().max()),
                            "modal": float(spacing.dt.total_seconds().mode().iloc[0]),
                            "distinct": int(spacing.nunique())},
        "nominal_step_seconds": float(step.total_seconds()),
        "gaps": int((spacing > step).sum()),
        "rows_on_nominal_grid": int(np.count_nonzero(on_grid)),
        "rows_off_nominal_grid": int(len(event) - np.count_nonzero(on_grid)),
        "truncated_bars": int((delta < step - pd.Timedelta("1ms")).sum()),
        "first_event": str(event.iloc[0]), "last_event": str(event.iloc[-1]),
        "first_available": str(available.iloc[0]), "last_available": str(available.iloc[-1]),
    })
    return facts


def candidate_contract(event_column, available_column, frequency, facts) -> dict:
    """The contract the measurements support — and only that."""
    tz_in_schema = facts["event_column"]["timezone_in_schema"]
    timezone = "UTC" if tz_in_schema in ("UTC", "utc") else "NAIVE_WALL_CLOCK"
    evidence = "PRODUCER_STATEMENT" if tz_in_schema else "UNKNOWN"
    return {
        "event_time_column": event_column,
        "available_time_column": available_column,
        "timezone": timezone,
        "time_unit": None if facts["event_column"]["is_datetime"] else "ms",
        "frequency": frequency,
        "availability": {
            # the availability column is the bar's own completion time, so no further lag is
            # claimed *against that column*; provider delivery latency is a separate, and
            # here unobserved, quantity — which is exactly why this is not LIVE_EQUIVALENT
            "label": "WINDOW_END",
            "completion_lag_max": "0s",
            "timezone_evidence": evidence,
            "use_class": "OFFLINE_DAY_GRANULAR",
        },
    }


def unknowns(provenance: dict) -> list:
    """What this derivation does not establish, each with the reason."""
    return [
        {"property": "provider_delivery_latency",
         "status": "UNOBSERVED",
         "why": "no artifact records when the provider published any bar; the acquisition "
                "timestamp bounds the whole file, not a bar. UNOBSERVED is not zero, which "
                "is why the use class is OFFLINE_DAY_GRANULAR and not LIVE_EQUIVALENT"},
        {"property": "revision_policy",
         "status": "UNKNOWN",
         "why": "the producer documents one acquisition with a pinned digest and no "
                "statement about restatements; a second acquisition would be needed to "
                "observe whether past bars change"},
        {"property": "usage_rights",
         "status": "UNKNOWN",
         "why": "the provenance names the source but no licence or terms of use are "
                "recorded in this repository; a scientific publication needs that answered"},
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--resource", required=True)
    parser.add_argument("--event-column", required=True)
    parser.add_argument("--available-column", required=True)
    parser.add_argument("--frequency", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    path = (args.root / args.resource).resolve()
    if not path.is_file():
        raise SystemExit(f"REFUSED: no such resource: {args.resource}")
    args.out.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(path)
    provenance = pinned_digests(args.root, args.resource)
    facts = measure(path, args.event_column, args.available_column, args.frequency)
    contract = candidate_contract(args.event_column, args.available_column, args.frequency, facts)
    declared = next((v.get("declared_sha256") for v in provenance.values()
                     if isinstance(v, dict) and v.get("declares_this_file")), None)
    receipt = {
        "schema": "financial_resource_contract_candidate.v1",
        "resource": args.resource,
        "bytes": path.stat().st_size,
        "sha256": digest,
        "producer_declaration": provenance,
        "digest_matches_producer_declaration": (declared == digest) if declared else None,
        "measured": facts,
        "candidate_contract": contract,
        "contract_sha256": hashlib.sha256(
            json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "unknowns": unknowns(provenance),
        "status": "CANDIDATE_NOT_INSTALLED",
        "note": "installing this contract makes the resource deliverable under governance; "
                "that is a scientific eligibility change and belongs to review",
    }
    out = args.out / "CONTRACT_CANDIDATE.json"
    out.write_text(json.dumps(receipt, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"resource": args.resource, "sha256": digest,
                      "digest_matches_producer_declaration": receipt["digest_matches_producer_declaration"],
                      "contract_sha256": receipt["contract_sha256"],
                      "rows": facts.get("rows"),
                      "available_minus_event_ms": facts.get("available_minus_event_ms"),
                      "timezone_in_schema": facts["event_column"]["timezone_in_schema"],
                      "unknowns": [u["property"] for u in receipt["unknowns"]]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
