#!/usr/bin/env python3
"""Characterise a financial resource and decide, separately, what it is eligible to promise.

Successor of the first version, after Musashi's review of 2026-09-14. Three of its findings
are structural and are answered here:

* **a window's close is not availability.** `close_time` says when the window ended, not when
  the data could be known. Publication and reception were never observed for this file, so no
  availability column is asserted and the resource is characterised as a retrospective
  archive. `UNOBSERVED` never becomes `0s`;
* **a short bar is not a final bar.** Bars whose span is not the nominal one are classified
  from the bytes — empty placeholder, shorter nominal interval, partial aggregate — and none
  of them is claimed to be final;
* **measurements that invalidate a contract must stop it.** Eligibility is computed, with
  typed reasons; a failed measurement, a non-monotonic clock, duplicates or availability
  before the event produce refusals, not a zero-lag contract.

The tool emits a **characterisation** always, and an installable contract only when the
evidence supports one. Neither is installed by running it.

usage:
  derive_availability_contract.py --root ROOT --resource REL/PATH --event-column open_time
      --window-end-column close_time --frequency 4h --out DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

#: The clocks a resource can have. They are separate questions, and confusing them is how a
#: file's geometry gets presented as a guarantee about knowledge.
CLOCKS = ("window_start", "window_end", "finalization", "publication", "reception", "revision")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def producer_declaration(root: Path, resource: str) -> dict:
    """What the producer's own `provenance.json` states about this file, if anything."""
    path = (root / resource).parent / "provenance.json"
    if not path.is_file():
        return {"present": False}
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {"present": True, "error": "unparseable"}
    entries = {e.get("path"): e.get("sha256") for e in body.get("files", []) if isinstance(e, dict)}
    return {"present": True, "source": body.get("source"), "description": body.get("description"),
            "acquired_at": body.get("acquired_at"), "declared_sha256": entries.get(resource),
            "declares_this_file": resource in entries,
            "states_publication_time": False, "states_reception_time": False,
            "states_revision_policy": False, "states_usage_rights": False}


def read_frame(path: Path, columns=None):
    import pandas as pd

    if path.suffix == ".parquet":
        return pd.read_parquet(path, columns=list(columns) if columns else None)
    return pd.read_csv(path, usecols=list(columns) if columns else None)


def describe_column(series) -> dict:
    import pandas as pd

    tz = getattr(getattr(series, "dt", None), "tz", None)
    return {"dtype": str(series.dtype), "timezone_in_schema": str(tz) if tz is not None else None,
            "is_datetime": bool(pd.api.types.is_datetime64_any_dtype(series)),
            "nulls": int(series.isna().sum()),
            "first": str(series.iloc[0]) if len(series) else None,
            "last": str(series.iloc[-1]) if len(series) else None}


def classify_bars(frame, event_column, end_column, step, extra_columns) -> dict:
    """Classify every bar whose span is not the nominal one. None is called final."""
    import pandas as pd

    span = frame[end_column] - frame[event_column]
    nominal = step - pd.Timedelta("1ms")
    odd = frame.index[span != nominal]
    spacing = frame[event_column].diff()
    precedes_gap = set(frame.index[(spacing.shift(-1) > step).fillna(False)])
    volume = frame[extra_columns[0]] if extra_columns and extra_columns[0] in frame else None
    trades = frame[extra_columns[1]] if len(extra_columns) > 1 and extra_columns[1] in frame else None
    classified = []
    for i in odd:
        ms = int(round(span.loc[i].total_seconds() * 1000))
        empty = bool((volume is not None and volume.loc[i] == 0)
                     and (trades is not None and trades.loc[i] == 0))
        if ms == 0 and empty:
            kind = "EMPTY_PLACEHOLDER"
        elif ms == 0:
            kind = "ZERO_SPAN"
        elif (ms + 1) % 3_600_000 == 0:
            kind = "SHORTER_NOMINAL_INTERVAL"
        else:
            kind = "PARTIAL_AGGREGATE"
        classified.append({"index": int(i), "open_time": str(frame[event_column].loc[i]),
                           "span_ms": ms, "kind": kind,
                           "precedes_gap": bool(i in precedes_gap),
                           "volume": float(volume.loc[i]) if volume is not None else None,
                           "trade_count": int(trades.loc[i]) if trades is not None else None})
    kinds = {}
    for row in classified:
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    return {"count": len(classified), "by_kind": kinds,
            "precedes_gap": sum(1 for r in classified if r["precedes_gap"]),
            "finality_demonstrated": False,
            "why": "the file carries no field stating whether a bar is final; a span shorter "
                   "than the nominal window is consistent with a partial aggregate, a "
                   "different interval or a collection boundary, and none of those is a "
                   "demonstrated final bar",
            "rows": classified[:50]}


def measure(path: Path, event_column: str, end_column: str, frequency: str,
            publication_column: str | None = None) -> dict:
    import numpy as np
    import pandas as pd

    frame = read_frame(path)
    missing = [c for c in (event_column, end_column) if c not in frame.columns]
    if missing:
        return {"measured": False, "why": f"columns absent from the file: {missing}",
                "columns": list(frame.columns)}
    event, window_end = frame[event_column], frame[end_column]
    step = pd.Timedelta(frequency)
    facts = {"rows": int(len(frame)), "columns": list(frame.columns),
             "event_column": describe_column(event), "window_end_column": describe_column(window_end),
             "event_monotonic_increasing": bool(event.is_monotonic_increasing),
             "event_duplicates": int(event.duplicated().sum())}
    if not (pd.api.types.is_datetime64_any_dtype(event)
            and pd.api.types.is_datetime64_any_dtype(window_end)):
        facts.update({"measured": False,
                      "why": "the two columns are not both timestamps in the physical schema"})
        return facts
    delta = window_end - event
    spacing = event.diff().dropna()
    span_ms = (delta.dt.total_seconds() * 1000).round().astype("int64")
    epoch_ms = event.astype("int64")
    on_grid = (epoch_ms % int(step.total_seconds() * 1000) == 0)
    facts.update({
        "measured": True,
        "window_end_minus_start_ms": {"min": int(span_ms.min()), "max": int(span_ms.max()),
                                      "distinct": int(span_ms.nunique()),
                                      "modal": int(span_ms.mode().iloc[0])},
        "window_end_at_or_after_start_always": bool((delta >= pd.Timedelta(0)).all()),
        "window_end_within_one_step_always": bool((delta <= step).all()),
        "spacing_seconds": {"min": float(spacing.dt.total_seconds().min()),
                            "max": float(spacing.dt.total_seconds().max()),
                            "modal": float(spacing.dt.total_seconds().mode().iloc[0]),
                            "distinct": int(spacing.nunique())} if len(spacing) else None,
        "nominal_step_seconds": float(step.total_seconds()),
        "gaps": int((spacing > step).sum()),
        "rows_on_nominal_grid": int(np.count_nonzero(on_grid)),
        "rows_off_nominal_grid": int(len(event) - np.count_nonzero(on_grid)),
        "first_event": str(event.iloc[0]), "last_event": str(event.iloc[-1]),
        "anomalous_bars": classify_bars(frame, event_column, end_column, step,
                                        ["volume", "trade_count"]),
    })
    if publication_column and publication_column in frame.columns:
        published = frame[publication_column]
        described = describe_column(published)
        if pd.api.types.is_datetime64_any_dtype(published):
            described["at_or_after_window_end_always"] = bool((published >= window_end).all())
            described["publication_minus_window_end_seconds"] = {
                "min": float((published - window_end).dt.total_seconds().min()),
                "max": float((published - window_end).dt.total_seconds().max())}
        else:
            described["at_or_after_window_end_always"] = False
        facts["publication_column"] = described
    return facts


def clocks(facts: dict, declaration: dict, publication_column: str | None = None) -> dict:
    """Which clocks the evidence establishes, and which stay unobserved.

    A publication clock exists only when the producer carries one in the bytes: a column
    that records when each row became available, verified to sit at or after the window it
    describes. Nothing else promotes `UNOBSERVED` to `MEASURED`.
    """
    measured = facts.get("measured")
    publication = {"status": "UNOBSERVED",
                   "evidence": "no artefact records when the provider published any row; "
                               "the producer declaration states no publication time"}
    if publication_column and facts.get("publication_column"):
        column = facts["publication_column"]
        if column.get("is_datetime") and column.get("at_or_after_window_end_always"):
            publication = {"status": "MEASURED", "column": publication_column,
                           "evidence": "every row carries a publication timestamp at or "
                                       "after the end of the window it describes"}
        else:
            publication = {"status": "REFUSED", "column": publication_column,
                           "evidence": "the declared publication column is not a timestamp "
                                       "at or after every window it describes"}
    tz = (facts.get("event_column") or {}).get("timezone_in_schema")
    return {
        "window_start": {"status": "MEASURED" if measured else "UNKNOWN",
                         "evidence": "the event column of every row, tz-aware "
                                     f"{tz} in the physical schema" if measured else None},
        "window_end": {"status": "MEASURED" if measured else "UNKNOWN",
                       "evidence": "the window-end column; modal span equals the nominal "
                                   "window minus one millisecond" if measured else None},
        "finalization": {"status": "NOT_DEMONSTRATED",
                         "evidence": (facts.get("anomalous_bars") or {}).get("why")},
        "publication": publication,
        "reception": {"status": "UNOBSERVED",
                      "evidence": f"one file-level acquisition timestamp "
                                  f"({declaration.get('acquired_at')}) bounds the whole file, "
                                  f"not a row"},
        "revision": {"status": "UNKNOWN",
                     "evidence": "a single acquisition cannot show whether past rows are "
                                 "restated; the producer declaration states no policy"},
    }


def eligibility(facts: dict, clock_states: dict, declaration: dict) -> dict:
    """What this evidence supports. Refusals are typed, and each names its measurement."""
    refusals = []
    if not facts.get("measured"):
        refusals.append({"reason": "MEASUREMENT_FAILED", "detail": facts.get("why")})
        return {"installable_availability_contract": False, "kind": "UNUSABLE",
                "refusals": refusals, "point_in_time_claim": "REFUSED",
                "live_claim": "REFUSED",
                "what_would_change_it": ["a readable file whose two time columns are "
                                         "timestamps in the physical schema"]}
    if not facts["event_monotonic_increasing"]:
        refusals.append({"reason": "EVENT_CLOCK_NOT_MONOTONIC",
                         "detail": "the event column does not increase row after row"})
    if facts["event_duplicates"]:
        refusals.append({"reason": "DUPLICATE_EVENT_TIMES",
                         "detail": f"{facts['event_duplicates']} duplicated event timestamps"})
    if not facts["window_end_at_or_after_start_always"]:
        refusals.append({"reason": "WINDOW_END_BEFORE_START",
                         "detail": "at least one row ends before it starts"})
    if declaration.get("declared_sha256") and not declaration.get("digest_matches"):
        refusals.append({"reason": "DIGEST_DOES_NOT_MATCH_PRODUCER",
                         "detail": "the bytes are not the ones the producer pinned"})
    if clock_states["publication"]["status"] != "MEASURED":
        refusals.append({"reason": "PUBLICATION_TIME_UNOBSERVED",
                         "detail": "no availability column can be asserted: a window's close "
                                   "is geometry, not knowledge"})
    if clock_states["finalization"]["status"] != "MEASURED":
        refusals.append({"reason": "FINALITY_NOT_DEMONSTRATED",
                         "detail": f"{(facts.get('anomalous_bars') or {}).get('count', 0)} bars "
                                   "have a span other than the nominal one and none is shown "
                                   "to be final"})
    blocking = {"MEASUREMENT_FAILED", "EVENT_CLOCK_NOT_MONOTONIC", "DUPLICATE_EVENT_TIMES",
                "WINDOW_END_BEFORE_START", "DIGEST_DOES_NOT_MATCH_PRODUCER"}
    unusable = [r for r in refusals if r["reason"] in blocking]
    point_in_time = (not unusable
                     and clock_states["publication"]["status"] == "MEASURED"
                     and clock_states["finalization"]["status"] != "NOT_DEMONSTRATED")
    if point_in_time:
        return {"installable_availability_contract": True, "kind": "POINT_IN_TIME",
                "refusals": refusals, "point_in_time_claim": "SUPPORTED",
                "live_claim": "REFUSED",
                "what_would_change_it": ["a producer statement bounding delivery latency to "
                                         "zero would be needed for a live claim"]}
    return {
        "installable_availability_contract": False,
        "kind": "UNUSABLE" if unusable else "ARCHIVE_RETROSPECTIVE",
        "refusals": refusals,
        "point_in_time_claim": "REFUSED",
        "live_claim": "REFUSED",
        "what_would_change_it": [
            "a producer statement or observation of publication time per row, or a bound on it",
            "a field or producer statement distinguishing final rows from partial aggregates",
        ],
    }


def availability_contract(event_column, frequency, facts, verdict, publication_column) -> dict | None:
    """The contract an *evidenced* publication clock supports: availability, with zero lag
    against the column that records it."""
    if verdict["kind"] != "POINT_IN_TIME" or not publication_column:
        return None
    tz = facts["event_column"]["timezone_in_schema"]
    return {
        "event_time_column": event_column,
        "available_time_column": publication_column,
        "timezone": "UTC" if tz in ("UTC", "utc") else "NAIVE_WALL_CLOCK",
        "time_unit": None if facts["event_column"]["is_datetime"] else "ms",
        "frequency": frequency,
        "availability": {"label": "EVENT_INSTANT", "completion_lag_max": "0s",
                         "timezone_evidence": "PRODUCER_STATEMENT" if tz else "UNKNOWN",
                         "use_class": "OFFLINE_DAY_GRANULAR"},
    }


def archive_contract(event_column, end_column, frequency, facts, verdict) -> dict | None:
    """The contract a retrospective archive can carry: geometry, and no promise of knowledge."""
    if verdict["kind"] != "ARCHIVE_RETROSPECTIVE":
        return None
    tz = facts["event_column"]["timezone_in_schema"]
    return {
        "event_time_column": event_column,
        # the archive class is delivered whole; the column is named for description only and
        # the lake refuses a ranged delivery under this use class
        "available_time_column": end_column,
        "timezone": "UTC" if tz in ("UTC", "utc") else "NAIVE_WALL_CLOCK",
        "time_unit": None if facts["event_column"]["is_datetime"] else "ms",
        "frequency": frequency,
        "availability": {"label": "WINDOW_END",
                         "completion_lag_max": "UNKNOWN",
                         "timezone_evidence": "PRODUCER_STATEMENT" if tz else "UNKNOWN",
                         "use_class": "ARCHIVE_RETROSPECTIVE"},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--resource", required=True)
    parser.add_argument("--event-column", required=True)
    parser.add_argument("--window-end-column", required=True)
    parser.add_argument("--frequency", required=True)
    parser.add_argument("--publication-column",
                        help="a column recording when each row became available, when the "
                             "producer carries one; absent means unobserved, not zero")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    path = (args.root / args.resource).resolve()
    if not path.is_file():
        raise SystemExit(f"REFUSED: no such resource: {args.resource}")
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(path)
    declaration = producer_declaration(args.root, args.resource)
    declaration["digest_matches"] = (declaration.get("declared_sha256") == digest
                                     if declaration.get("declared_sha256") else None)
    facts = measure(path, args.event_column, args.window_end_column, args.frequency,
                    args.publication_column)
    clock_states = clocks(facts, declaration, args.publication_column)
    verdict = eligibility(facts, clock_states, declaration)
    contract = None
    if facts.get("measured"):
        contract = (availability_contract(args.event_column, args.frequency, facts, verdict,
                                          args.publication_column)
                    or archive_contract(args.event_column, args.window_end_column,
                                        args.frequency, facts, verdict))
    receipt = {
        "schema": "financial_resource_characterisation.v2",
        "supersedes": "financial_resource_contract_candidate.v1 (its zero-lag availability "
                      "claim is withdrawn: window close is not publication)",
        "resource": args.resource, "bytes": path.stat().st_size, "sha256": digest,
        "producer_declaration": declaration, "clocks": clock_states, "measured": facts,
        "eligibility": verdict, "contract": contract,
        "contract_sha256": hashlib.sha256(
            json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if contract else None,
        "status": "CHARACTERISATION_ONLY_NOT_INSTALLED",
    }
    (args.out / "CHARACTERISATION.json").write_text(
        json.dumps(receipt, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"resource": args.resource, "sha256": digest[:16],
                      "digest_matches_producer": declaration.get("digest_matches"),
                      "clocks": {k: v["status"] for k, v in clock_states.items()},
                      "eligibility": {"kind": verdict["kind"],
                                      "installable": verdict["installable_availability_contract"],
                                      "refusals": [r["reason"] for r in verdict["refusals"]]},
                      "anomalous_bars": (facts.get("anomalous_bars") or {}).get("by_kind"),
                      "contract_sha256": receipt["contract_sha256"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
