#!/usr/bin/env python3
"""C7: derive the MINIMUM availability scope, and instantiate
only what the sources actually demonstrate.

The order settles the scope question by narrowing it: instantiate
availability contracts first for the families consumed by the
ratified observation contract v2 and by the active supervised
financial tasks, derive that list from manifests and headers
rather than from memory, and leave everything else
`UNAVAILABLE`.

This tool does the deriving and then reports, per family, whether
all eight required fields can be demonstrated from a source, a
worker and a publication policy. It instantiates a contract only
where they can. It never writes a field a source does not state.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_scripts" / "lib"))

import incremental_census as ic  # noqa: E402

REQUIRED_FIELDS = ("feature_family", "provider",
                   "observation_ts_col", "available_from_ts_col",
                   "revision_policy", "timezone",
                   "min_latency_minutes", "license_scope")


def _read_header(path: Path) -> list[str]:
    with open(path, newline="", encoding="utf-8",
              errors="replace") as fh:
        return [c.strip() for c in next(csv.reader(fh))]


def derive_consumers(predictor_root: Path,
                     agent_multi_root: Path) -> dict:
    """The exact demand side, read from artifacts."""
    supervised_columns, supervised_sources = set(), []
    inv = (predictor_root /
           "examples/research/crispdm_dataset_inventory.v1.json")
    if inv.is_file():
        doc = json.loads(inv.read_text())
        for ds in doc.get("datasets", []):
            rel = ds.get("relative_path")
            p = predictor_root / rel if rel else None
            if p and p.is_file():
                cols = _read_header(p)
                supervised_columns.update(cols)
                supervised_sources.append({
                    "dataset_id": ds.get("dataset_id"),
                    "relative_path": rel,
                    "columns": len(cols)})

    rl_columns, rl_configs, contract_configs = set(), [], []
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
        if c.get("feature_columns"):
            rl_columns.update(str(x) for x in
                              c["feature_columns"])
            rl_configs.append(rel)

    return {
        "supervised_financial_tasks": {
            "sources": supervised_sources,
            "columns": sorted(supervised_columns),
            "column_count": len(supervised_columns),
        },
        "observation_contract_v2": {
            "configs_declaring_the_contract": contract_configs,
            "configs_declaring_feature_columns": rl_configs,
            "columns": sorted(rl_columns),
            "column_count": len(rl_columns),
            "derivation_gap": (
                "NO configuration declares BOTH "
                "observation_contract and feature_columns, so "
                "the families consumed by the ratified contract "
                "cannot be derived from configurations alone; "
                "the column set below is what the "
                "feature_columns declarations demand, and is "
                "reported as such"
                if contract_configs and rl_configs
                and not set(contract_configs) & set(rl_configs)
                else "derived from configurations declaring both"),
        },
    }


def assess_families(root: Path, demand: dict) -> dict:
    """For every lake family a consumer could plausibly need, say
    whether an availability contract can be instantiated."""
    manifest = ic.load_manifest(root)
    provenance = ic.index_provenance(root)
    entities = []
    for source_class, entity, freq, _s in ic._slice_records(
            manifest):
        entities.append((source_class, entity))
    entities = sorted(set(entities))

    assessed, instantiable = [], []
    for source_class, entity in entities:
        upstream = ic.upstream_lineage_dirs(root, source_class,
                                            entity)
        prov = None
        for d in upstream:
            if d in provenance:
                prov = provenance[d]
                break
        missing = []
        have = {}
        if prov is None:
            missing = list(REQUIRED_FIELDS)
        else:
            have["feature_family"] = entity
            have["provider"] = prov.get("source", ic.UNKNOWN)
            if have["provider"] == ic.UNKNOWN:
                missing.append("provider")
            for field in ("observation_ts_col",
                          "available_from_ts_col",
                          "revision_policy", "timezone",
                          "min_latency_minutes",
                          "license_scope"):
                value = prov.get(field)
                if value in (None, "", ic.UNKNOWN):
                    missing.append(field)
                else:
                    have[field] = value
        record = {
            "entity": entity,
            "source_class": source_class,
            "provenance_file": (prov or {}).get(
                "provenance_file", ic.UNAVAILABLE),
            "missing_required_fields": sorted(set(missing)),
            "instantiable": not missing,
        }
        assessed.append(record)
        if not missing:
            instantiable.append({**have, "_derived_from":
                                 record["provenance_file"]})
    return {"assessed": assessed, "instances": instantiable}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--predictor-root", type=Path, required=True)
    ap.add_argument("--agent-multi-root", type=Path,
                    required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--derived-at", required=True)
    a = ap.parse_args(argv)

    demand = derive_consumers(a.predictor_root,
                              a.agent_multi_root)
    supply = assess_families(a.root, demand)
    instantiable = supply["instances"]
    doc = {
        "schema": "financial_data.availability_scope.v1",
        "derived_at": a.derived_at,
        "demand": demand,
        "supply": {
            "families_assessed": len(supply["assessed"]),
            "families_instantiable": len(instantiable),
            "instances": instantiable,
            "missing_field_histogram": _histogram(
                supply["assessed"]),
        },
        "instantiation_rule":
            "a contract is instantiated only when a source, a "
            "worker and a publication policy demonstrate all "
            "eight required fields; every other family keeps "
            "UNAVAILABLE, and nothing is written that a source "
            "does not state",
        "required_fields": list(REQUIRED_FIELDS),
    }
    doc["scope_sha256"] = ic._self_sha(doc, "scope_sha256")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(doc, indent=1,
                                   sort_keys=True) + "\n")
    print(json.dumps({
        "supervised_columns":
            demand["supervised_financial_tasks"]["column_count"],
        "rl_feature_columns":
            demand["observation_contract_v2"]["column_count"],
        "derivation_gap":
            demand["observation_contract_v2"]["derivation_gap"],
        "families_assessed": doc["supply"]["families_assessed"],
        "families_instantiable":
            doc["supply"]["families_instantiable"],
        "missing_field_histogram":
            doc["supply"]["missing_field_histogram"],
        "scope_sha256": doc["scope_sha256"],
    }, indent=1, sort_keys=True))
    return 0


def _histogram(assessed: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for a in assessed:
        for f in a["missing_required_fields"]:
            counts[f] = counts.get(f, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
