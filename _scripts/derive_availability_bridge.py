#!/usr/bin/env python3
"""C27-C28: the availability bridge, derived from evidence.

The previous scope report ended on an honest gap: no configuration
declares both `observation_contract` and `feature_columns`, so the
families the ratified contract consumes could not be derived from
configurations. C27 asks for a BRIDGE instead — a derivation that
crosses the gap using physical evidence rather than by editing a
configuration to fake a match.

The bridge follows one chain and reports where it breaks:

    column -> conceptual variable -> physical appearance
           -> family -> temporal contract

Each link is resolved from artifacts that already exist: the
headers of the active views, the census the lake published, and
the manifests and producer code of each family. A link that cannot
be resolved is marked `UNRESOLVED` with the reason, never guessed.

C28 then derives the eight availability fields for every family
the bridge actually reaches, from local evidence only. Event time
is NEVER used as available time: that substitution is the single
assumption this whole contract exists to forbid.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_scripts" / "lib"))

import incremental_census as ic  # noqa: E402

REQUIRED_FIELDS = ("feature_family", "provider",
                   "observation_ts_col", "available_from_ts_col",
                   "revision_policy", "timezone",
                   "min_latency_minutes", "license_scope")


def _header(path: Path) -> list[str]:
    with open(path, newline="", encoding="utf-8",
              errors="replace") as fh:
        return [c.strip() for c in next(csv.reader(fh))]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def demand_columns(predictor_root: Path,
                   agent_multi_root: Path) -> dict:
    """Every column an ACTIVE consumer declares it will read."""
    supervised, sources = {}, []
    inv = (predictor_root /
           "examples/research/crispdm_dataset_inventory.v1.json")
    if inv.is_file():
        doc = json.loads(inv.read_text())
        for ds in doc.get("datasets", []):
            rel = ds.get("relative_path")
            p = predictor_root / rel if rel else None
            if p and p.is_file():
                cols = _header(p)
                sources.append({"dataset_id": ds["dataset_id"],
                                "relative_path": rel,
                                "columns": len(cols)})
                for c in cols:
                    supervised.setdefault(c, []).append(
                        ds["dataset_id"])
    rl, rl_configs, contract_configs = {}, [], []
    for cfg in sorted((agent_multi_root /
                       "examples/config").rglob("*.json")):
        try:
            c = json.loads(cfg.read_text())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(c, dict):
            continue
        rel = str(cfg.relative_to(agent_multi_root))
        if "observation_contract" in c:
            contract_configs.append(rel)
        for col in (c.get("feature_columns") or []):
            rl.setdefault(str(col), []).append(rel)
        if c.get("feature_columns"):
            rl_configs.append(rel)
    return {"supervised_columns": supervised,
            "supervised_sources": sources,
            "rl_columns": rl,
            "rl_configs": rl_configs,
            "observation_contract_configs": contract_configs}


def build_bridge(root: Path, census_doc: dict,
                 demand: dict) -> dict:
    """column -> variable -> appearance -> family -> contract."""
    by_concept = {}
    for v in census_doc.get("variables", []):
        by_concept.setdefault(_norm(v["concept_name"]),
                              []).append(v)
    appearances = {a["appearance_id"]: a
                   for a in census_doc.get("appearances", [])}

    links, unresolved = [], []
    all_columns = sorted(set(demand["supervised_columns"])
                         | set(demand["rl_columns"]))
    for column in all_columns:
        consumers = []
        if column in demand["supervised_columns"]:
            consumers.append("supervised")
        if column in demand["rl_columns"]:
            consumers.append("rl")
        candidates = by_concept.get(_norm(column), [])
        if not candidates:
            unresolved.append({
                "column": column, "consumers": consumers,
                "stage": "column_to_variable",
                "reason": "no conceptual variable in the census "
                          "carries this concept — the column is "
                          "derived downstream of the lake, or "
                          "the lake does not contain it"})
            continue
        entities = sorted({v["entity"] for v in candidates})
        if len(entities) > 1:
            unresolved.append({
                "column": column, "consumers": consumers,
                "stage": "variable_to_entity",
                "candidate_entities": entities[:12],
                "candidate_entity_count": len(entities),
                "reason": "the concept appears on several "
                          "entities; a bridge never chooses "
                          "between them"})
            continue
        v = candidates[0]
        apps = [appearances[a] for a in v.get("appearances", [])
                if a in appearances]
        links.append({
            "column": column, "consumers": consumers,
            "variable_id": v["variable_id"],
            "entity": v["entity"],
            "appearance_count": len(apps),
            "appearance_ids": [a["appearance_id"]
                               for a in apps][:8],
            "family_path": "/".join(v["entity"].split("__")),
            "event_time": v["event_time"],
            "available_time": v["available_time"],
            "state": ("RESOLVED_TO_FAMILY"
                      if apps else "UNRESOLVED_NO_APPEARANCE"),
        })
    return {"links": links, "unresolved": unresolved,
            "columns_examined": len(all_columns)}


def derive_contracts(root: Path, families: list[str],
                     provenance: dict) -> dict:
    complete, blocked = [], []
    for family in sorted(set(families)):
        prov = provenance.get(family)
        have, missing = {}, []
        if prov is None:
            missing = list(REQUIRED_FIELDS)
        else:
            have["feature_family"] = family
            have["provider"] = prov.get("source", ic.UNKNOWN)
            if have["provider"] == ic.UNKNOWN:
                missing.append("provider")
            for f in ("observation_ts_col",
                      "available_from_ts_col",
                      "revision_policy", "timezone",
                      "min_latency_minutes", "license_scope"):
                val = prov.get(f)
                if val in (None, "", ic.UNKNOWN):
                    missing.append(f)
                else:
                    have[f] = val
        record = {"family": family,
                  "provenance_file": (prov or {}).get(
                      "provenance_file", ic.UNAVAILABLE),
                  "missing_required_fields": sorted(set(missing))}
        if missing:
            blocked.append(record)
        else:
            complete.append({**have, "_derived_from":
                             record["provenance_file"]})
    return {"complete": complete, "blocked": blocked}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--census", required=True, type=Path)
    ap.add_argument("--predictor-root", required=True, type=Path)
    ap.add_argument("--agent-multi-root", required=True,
                    type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--derived-at", required=True)
    a = ap.parse_args(argv)

    census_doc = json.loads(a.census.read_text())
    demand = demand_columns(a.predictor_root,
                            a.agent_multi_root)
    bridge = build_bridge(a.root, census_doc, demand)
    provenance = ic.index_provenance(a.root)
    families = [ln["family_path"] for ln in bridge["links"]]
    contracts = derive_contracts(a.root, families, provenance)

    by_field: dict[str, int] = {}
    for b in contracts["blocked"]:
        for f in b["missing_required_fields"]:
            by_field[f] = by_field.get(f, 0) + 1

    doc = {
        "schema": "financial_data.availability_bridge.v1",
        "derived_at": a.derived_at,
        "census_sha256": census_doc.get("census_sha256",
                                        ic.UNKNOWN),
        "demand": {
            "supervised_columns":
                len(demand["supervised_columns"]),
            "supervised_sources": demand["supervised_sources"],
            "rl_columns": len(demand["rl_columns"]),
            "rl_configs": demand["rl_configs"],
            "observation_contract_configs":
                demand["observation_contract_configs"],
            "configs_declaring_both": sorted(
                set(demand["rl_configs"])
                & set(demand["observation_contract_configs"])),
        },
        "bridge": {
            "columns_examined": bridge["columns_examined"],
            "resolved": len(bridge["links"]),
            "unresolved": len(bridge["unresolved"]),
            "links": bridge["links"],
            "unresolved_detail": bridge["unresolved"],
            "chain": "column -> conceptual variable -> physical "
                     "appearance -> family -> temporal contract",
            "no_config_was_edited":
                "the gap between observation_contract and "
                "feature_columns is crossed with physical "
                "evidence; no configuration was changed to "
                "manufacture a match",
        },
        "contracts": {
            "families_reached": len(set(families)),
            "complete": contracts["complete"],
            "blocked": contracts["blocked"],
            "blocked_by_missing_field": dict(
                sorted(by_field.items())),
        },
        "rules": {
            "event_time_is_never_available_time":
                "an available time is derived from a publication "
                "policy, a worker or a provider statement — "
                "never copied from the event time",
            "zero_is_a_valid_answer":
                "the goal is not a positive count; a family "
                "whose evidence does not exist stays blocked",
        },
        "required_fields": list(REQUIRED_FIELDS),
    }
    doc["bridge_sha256"] = ic._self_sha(doc, "bridge_sha256")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(doc, indent=1,
                                   sort_keys=True) + "\n")
    print(json.dumps({
        "columns_examined": doc["bridge"]["columns_examined"],
        "resolved": doc["bridge"]["resolved"],
        "unresolved": doc["bridge"]["unresolved"],
        "families_reached": doc["contracts"]["families_reached"],
        "contracts_complete": len(contracts["complete"]),
        "contracts_blocked": len(contracts["blocked"]),
        "blocked_by_missing_field":
            doc["contracts"]["blocked_by_missing_field"],
        "configs_declaring_both":
            doc["demand"]["configs_declaring_both"],
        "bridge_sha256": doc["bridge_sha256"],
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
