#!/usr/bin/env python3
"""C43-C44 (order 2026-09-11): lineage of the consumed columns.

The bridge established WHERE the chain breaks. This derives the other
half: for each consumed column, the entity it belongs to and the
earliest time it could honestly be known.

Two different problems, and they are not solved the same way.

  * THE OHLCV HALF. The bridge refused these because the concept
    `CLOSE` appears on 128 lake entities and a bridge never picks one
    by name. It does not have to: the model-ready VIEW carries its own
    provenance — domain, provider, and a dataset id that names symbol
    and timeframe. The entity is DERIVED from that provenance, never
    chosen from a candidate list.

  * THE DERIVED-FEATURE HALF. A feature the lake does not carry needs
    its producer to publish the binding. Where the producer publishes
    an availability policy, the causal latency is read from it and the
    earliest available time follows: max(inputs) + latency. Where it
    does not, this tool emits a DEFICIT naming the exact producer and
    the exact missing field. It never copies `event_time` into
    `available_time`, and it never invents a latency.

    python _scripts/derive_feature_lineage.py \\
        --bridge features/census/AVAILABILITY_BRIDGE.v2.json \\
        --predictor-root ... --output ... --derived-at ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: a policy token that says features are computed causally and the
#: decision is taken at the bar close. The earliest a value can be
#: known is therefore the close of the bar it describes.
CAUSAL_THROUGH_CLOSE = "FEATURES_COMPUTED_CAUSALLY_THROUGH_BAR_CLOSE"

RESOLVED = "RESOLVED_FROM_VIEW_PROVENANCE"
DEFICIT = "PRODUCER_DEFICIT"

#: how a dataset id names its subject. `...ethusdt_4h_tech_stat...`
_SYMBOL_TF = re.compile(r"\.([a-z0-9]+)_(\d+[mhdw])_", re.I)

#: OHLCV concepts, the ones the bridge could not place on one entity.
OHLCV = {"OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"}

TIMEFRAME_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}


def sha_obj(o) -> str:
    return hashlib.sha256(
        json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def parse_symbol_timeframe(dataset_id: str) -> dict:
    m = _SYMBOL_TF.search(dataset_id)
    if not m:
        return {"symbol": "UNDERIVABLE", "timeframe": "UNDERIVABLE",
                "reason": "the dataset id does not name a symbol and a "
                          "timeframe; the view must publish them"}
    return {"symbol": m.group(1).upper(), "timeframe": m.group(2)}


def timeframe_seconds(tf: str):
    m = re.fullmatch(r"(\d+)([mhdw])", tf or "")
    return int(m.group(1)) * TIMEFRAME_SECONDS[m.group(2)] if m else None


def entity_binding(ds: dict) -> dict:
    """Symbol, timeframe and provider DERIVED from the view itself."""
    st = parse_symbol_timeframe(ds["dataset_id"])
    provider = str(ds.get("provider") or "").strip()
    domain = str(ds.get("domain") or "").strip()
    missing = []
    if st["symbol"] == "UNDERIVABLE":
        missing.append("symbol/timeframe in the dataset id")
    if not provider or "not recorded" in provider.lower():
        missing.append("provider")
    if not domain:
        missing.append("domain")
    return {
        "dataset_id": ds["dataset_id"],
        "symbol": st["symbol"], "timeframe": st["timeframe"],
        "provider": provider or "UNDECLARED",
        "domain": domain or "UNDECLARED",
        "state": DEFICIT if missing else RESOLVED,
        "missing": missing,
        "derivation": "from the model-ready view's own provenance; no "
                      "candidate entity was chosen by name",
    }


def availability_contract(ds: dict, binding: dict) -> dict:
    """The causal latency, read from the producer's declared policy."""
    policy = str(ds.get("availability_policy") or "UNDECLARED")
    seconds = timeframe_seconds(binding.get("timeframe", ""))
    if CAUSAL_THROUGH_CLOSE in policy and seconds:
        return {
            "policy": policy,
            "state": RESOLVED,
            "causal_latency_seconds": seconds,
            "earliest_available_time": (
                "event_time + one bar; the producer declares features "
                "are computed causally through the bar close, so the "
                "earliest a value is knowable is that close"),
            "derivation": "max(input event times) + the declared "
                          "causal latency of the transformation",
        }
    missing = []
    if CAUSAL_THROUGH_CLOSE not in policy:
        missing.append("availability_policy declaring causal latency")
    if not seconds:
        missing.append("a parseable timeframe")
    return {
        "policy": policy, "state": DEFICIT, "missing": missing,
        "earliest_available_time": "UNAVAILABLE",
        "refusal": "event_time is NOT copied into available_time and "
                   "no latency is invented; the producer must publish "
                   "the policy",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bridge", required=True, type=Path)
    ap.add_argument("--predictor-root", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--derived-at", required=True)
    ap.add_argument("--candidate", type=Path, default=None,
                    help="emit a NON-AUTHORIZING candidate submission "
                         "for external review when the resolved set is "
                         "non-empty")
    a = ap.parse_args(argv)

    bridge = json.loads(a.bridge.read_text())
    inv_path = (a.predictor_root /
                "examples/research/crispdm_dataset_inventory.v1.json")
    inventory = json.loads(inv_path.read_text())
    datasets = {d["dataset_id"]: d for d in inventory["datasets"]}

    demand = bridge["demand"]
    by_dataset: dict[str, list[str]] = {}
    for source in demand["supervised_sources"]:
        excluded = {e["column"] for e in source["columns_excluded"]}
        path = a.predictor_root / source["relative_path"]
        header = path.read_text(encoding="utf-8",
                                errors="replace").split("\n", 1)[0]
        by_dataset[source["dataset_id"]] = [
            c.strip() for c in header.split(",")
            if c.strip() and c.strip() not in excluded]

    lineage, deficits = [], []
    for dataset_id, columns in sorted(by_dataset.items()):
        ds = datasets[dataset_id]
        binding = entity_binding(ds)
        contract = availability_contract(ds, binding)
        for column in columns:
            kind = "OHLCV_RAW" if column.upper() in OHLCV \
                else "DERIVED_FEATURE"
            node = {
                "column": column,
                "dataset_id": dataset_id,
                "kind": kind,
                "entity": {k: binding[k] for k in
                           ("symbol", "timeframe", "provider",
                            "domain", "state")},
                "event_time": "the bar this row describes",
                "earliest_available_time":
                    contract["earliest_available_time"],
                "availability_state": contract["state"],
            }
            if kind == "DERIVED_FEATURE":
                node["upstream"] = (
                    "computed inside this view's producer from the "
                    "OHLCV of the same bar; the lake census does not "
                    "carry it as a conceptual variable")
            lineage.append(node)
        if binding["state"] == DEFICIT or contract["state"] == DEFICIT:
            deficits.append({
                "dataset_id": dataset_id,
                "producer": ds.get("provider", "UNDECLARED"),
                "relative_path": ds.get("relative_path"),
                "missing_entity_fields": binding["missing"],
                "missing_availability_fields": contract.get("missing",
                                                            []),
                "consequence": "every column of this view stays "
                               "UNAVAILABLE until the producer "
                               "publishes these fields; a new view "
                               "identity follows, it is not patched "
                               "in place",
                "holder": "the producer of this view",
                "requires_owner_decision": False,
            })

    resolved = [n for n in lineage
                if n["availability_state"] == RESOLVED
                and n["entity"]["state"] == RESOLVED]
    doc = {
        "schema": "financial_data.feature_lineage.v1",
        "derived_at": a.derived_at,
        "bridge_sha256": bridge.get("bridge_sha256", "UNAVAILABLE"),
        "inventory_sha256": inventory.get("inventory_sha256",
                                          "UNAVAILABLE"),
        "columns_examined": len(lineage),
        "columns_resolved": len(resolved),
        "columns_unresolved": len(lineage) - len(resolved),
        "by_kind": {
            k: sum(1 for n in lineage if n["kind"] == k)
            for k in ("OHLCV_RAW", "DERIVED_FEATURE")},
        "resolved_by_kind": {
            k: sum(1 for n in resolved if n["kind"] == k)
            for k in ("OHLCV_RAW", "DERIVED_FEATURE")},
        "lineage": lineage,
        "producer_deficits": deficits,
        "rules": {
            "entity": "derived from the model-ready view's own "
                      "provenance; never chosen from candidates",
            "available_time": "max(input event times) + the declared "
                              "causal latency; event_time is never "
                              "copied and latency is never invented",
        },
        # C44
        "disposition": ("FINANCIAL_AVAILABILITY_CANDIDATE_READY"
                        if resolved else
                        "FINANCIAL_AVAILABILITY_EVIDENCE_REQUIRED"),
        "candidate_submission": (
            "a candidate submission for EXTERNAL review may be built "
            "from the resolved columns; this tool emits no "
            "authorization and grants no eligibility"
            if resolved else
            "no submission is emitted: it would bind an empty set"),
    }
    doc["lineage_sha256"] = sha_obj(doc)

    # C44: a NON-EMPTY resolved set produces a CANDIDATE SUBMISSION for
    # external review. It is not an authorization, it does not make a
    # column eligible, and nothing downstream may read it as a
    # decision — a submission states what was derived and asks.
    if resolved and a.candidate:
        candidate = {
            "schema": "financial_data.availability_candidate.v1",
            "derived_at": a.derived_at,
            "lineage_sha256": doc["lineage_sha256"],
            "bridge_sha256": doc["bridge_sha256"],
            "inventory_sha256": doc["inventory_sha256"],
            "columns": [
                {"column": n["column"], "dataset_id": n["dataset_id"],
                 "kind": n["kind"], "symbol": n["entity"]["symbol"],
                 "timeframe": n["entity"]["timeframe"],
                 "provider": n["entity"]["provider"],
                 "earliest_available_time":
                     n["earliest_available_time"]}
                for n in sorted(resolved, key=lambda x: x["column"])],
            "columns_total": len(resolved),
            "excluded_with_named_deficit": deficits,
            "grants_nothing":
                "this is a SUBMISSION. It states which consumed "
                "columns now have a derived entity and a derived "
                "earliest-available time, and asks for a decision. It "
                "confers no eligibility, opens no selection, and is "
                "not self-authorizing",
            "requires": "EXTERNAL_REVIEW",
        }
        candidate["candidate_sha256"] = sha_obj(candidate)
        a.candidate.parent.mkdir(parents=True, exist_ok=True)
        a.candidate.write_text(
            json.dumps(candidate, indent=1, sort_keys=True) + "\n")
        doc["candidate_submission_file"] = str(a.candidate.name)
        doc["candidate_sha256"] = candidate["candidate_sha256"]
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(doc, indent=1, sort_keys=True)
                        + "\n")
    print(json.dumps({k: doc[k] for k in
                      ("columns_examined", "columns_resolved",
                       "columns_unresolved", "by_kind",
                       "resolved_by_kind", "disposition",
                       "lineage_sha256")}, indent=1, sort_keys=True))
    for d in deficits:
        print(f"  DEFICIT {d['dataset_id']}: entity={d['missing_entity_fields']} "
              f"availability={d['missing_availability_fields']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
