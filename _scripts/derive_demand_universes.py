#!/usr/bin/env python3
"""C45-C46 (order 2026-09-12): three universes, six grains, no mixing.

The bridge called every header of the two datasets in the CRISP-DM
research registry "ACTIVE consumer demand". They are a registry: one of
them (`base_d6.csv`) is referenced by no configuration at all, and the
other is referenced only by configurations that declare
`feature_columns` without binding an `observation_contract`. A registry
entry is a candidate, not a consumption.

So demand is derived from CONFIGURATIONS a running entry point can
actually execute:

  * ACTIVE_EXECUTION_DEMAND — a config whose data files all exist, read
    through the same (dataset, side, contract_role, column) derivation
    the eligibility gate uses. Supervised configs name x/y partitions;
    an RL config counts only when it binds an observation contract;
  * RESEARCH_BANK_CANDIDATES — registered development datasets with no
    executable consumer. Real, useful, and not demand;
  * CONFIRMATORY_RESERVED — data whose examination would spend
    confirmation, named so nothing wanders into it.

C46: the six grains are materialised separately, because 93 unique
column NAMES and 97 (dataset, column) SUBJECTS are different numbers
and reporting one as the other is how a count stops meaning anything.
An empty set yields NOT_APPLICABLE — never `true` on a subset or
coverage test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCHEMA = "financial_data.demand_universes.v1"

#: the partition keys a supervised run declares, by side.
X_KEYS = ("x_train_file", "x_validation_file", "x_test_file")
Y_KEYS = ("y_train_file", "y_validation_file", "y_test_file")

TEMPORAL = {"date_time", "datetime", "date", "timestamp", "time",
            "index", "period"}

NOT_APPLICABLE = "NOT_APPLICABLE"


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha_obj(o) -> str:
    return hashlib.sha256(
        json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def is_temporal(column: str) -> bool:
    return column.strip().lower() in TEMPORAL


def header_of(path: Path) -> list[str]:
    with path.open(encoding="utf-8", errors="replace") as fh:
        return [c.strip() for c in fh.readline().split(",") if c.strip()]


def resolve(base: Path, value) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    p = Path(value)
    return p if p.is_absolute() else (base / p)


# ------------------------------------------------- active supervised
def supervised_demand(predictor_root: Path) -> dict:
    """Every config the predictor entry point could execute today."""
    configs, unreachable = [], []
    for cfg_path in sorted((predictor_root / "examples/config")
                           .rglob("*.json")):
        try:
            cfg = json.loads(cfg_path.read_text())
        except (UnicodeDecodeError, ValueError):
            continue
        if not isinstance(cfg, dict):
            continue
        declared = {k: cfg.get(k) for k in X_KEYS + Y_KEYS
                    if cfg.get(k)}
        if not declared:
            continue
        rel = str(cfg_path.relative_to(predictor_root))
        files = {k: resolve(predictor_root, v)
                 for k, v in declared.items()}
        absent = sorted(k for k, p in files.items()
                        if p is None or not p.is_file())
        if absent:
            unreachable.append({"config": rel, "missing_inputs": absent,
                                "reason": "the entry point cannot run "
                                          "this config: its declared "
                                          "inputs are not present"})
            continue
        configs.append({"config": rel, "sha256": sha_file(cfg_path),
                        "files": files, "target": cfg.get("target_column"),
                        "target_side": cfg.get("target_side")})

    subjects: dict[tuple, dict] = {}
    targets: dict[str, list] = {}
    per_config = []
    for entry in configs:
        seen_here = set()
        for key, path in sorted(entry["files"].items()):
            side = "x" if key in X_KEYS else "y"
            dataset = str(path.relative_to(predictor_root)) \
                if path.is_relative_to(predictor_root) else path.name
            for column in header_of(path):
                if is_temporal(column):
                    continue
                if column == entry["target"]:
                    role = "target"
                    targets.setdefault(column, []).append(entry["config"])
                else:
                    role = "input" if side == "x" else "label"
                sid = (dataset, side, role, column)
                seen_here.add(sid)
                node = subjects.setdefault(sid, {
                    "subject_id": f"{dataset}::{side}::{role}::{column}",
                    "dataset": dataset, "side": side,
                    "contract_role": role, "column": column,
                    "configs": []})
                if entry["config"] not in node["configs"]:
                    node["configs"].append(entry["config"])
        per_config.append({"config": entry["config"],
                           "sha256": entry["sha256"],
                           "subjects": len(seen_here)})
    return {
        "executable_configs": per_config,
        "unreachable_configs": unreachable,
        "subjects": [subjects[k] for k in sorted(subjects)],
        "targets": {k: sorted(set(v)) for k, v in targets.items()},
    }


# -------------------------------------------------------- active RL
def rl_demand(agent_multi_root: Path) -> dict:
    active, rejected = [], []
    columns: dict[str, list] = {}
    for cfg_path in sorted((agent_multi_root / "examples/config")
                           .rglob("*.json")):
        try:
            cfg = json.loads(cfg_path.read_text())
        except (UnicodeDecodeError, ValueError):
            continue
        if not isinstance(cfg, dict):
            continue
        cols = [str(c) for c in (cfg.get("feature_columns") or [])]
        if not cols:
            continue
        rel = str(cfg_path.relative_to(agent_multi_root))
        if "observation_contract" not in cfg:
            rejected.append({"config": rel, "feature_columns": len(cols),
                             "reason": "declares feature_columns but "
                                       "binds no observation_contract, "
                                       "so it is a draft, not an active "
                                       "consumer"})
            continue
        data = resolve(agent_multi_root, cfg.get("input_data_file"))
        if data is None or not data.is_file():
            rejected.append({"config": rel, "feature_columns": len(cols),
                             "reason": "binds a contract but its "
                                       "input_data_file is not present"})
            continue
        digest = sha_file(cfg_path)
        active.append({"config": rel, "sha256": digest,
                       "feature_columns": len(cols)})
        for c in cols:
            if not is_temporal(c):
                columns.setdefault(c, []).append(rel)
    return {"active_configs": active, "rejected_configs": rejected,
            "columns": columns}


# ------------------------------------------------- research / reserved
def research_candidates(predictor_root: Path,
                        active_datasets: set[str]) -> dict:
    inv_p = (predictor_root /
             "examples/research/crispdm_dataset_inventory.v1.json")
    if not inv_p.is_file():
        return {"state": "UNAVAILABLE", "datasets": []}
    inv = json.loads(inv_p.read_text())
    out = []
    for ds in inv.get("datasets", []):
        rel = ds.get("relative_path")
        path = predictor_root / rel if rel else None
        columns = header_of(path) if (path and path.is_file()) else []
        out.append({
            "dataset_id": ds["dataset_id"],
            "relative_path": rel,
            "sha256": sha_file(path) if path and path.is_file()
            else "UNAVAILABLE",
            "columns_in_file": len(columns),
            "non_temporal_columns": len([c for c in columns
                                         if not is_temporal(c)]),
            "has_executable_consumer": rel in active_datasets,
            "exposure_status": ds.get("exposure_status", "UNDECLARED"),
        })
    return {"state": "REGISTERED_FOR_DEVELOPMENT",
            "inventory_sha256": inv.get("inventory_sha256",
                                        "UNAVAILABLE"),
            "datasets": out,
            "note": "registered development datasets. A registry entry "
                    "is a CANDIDATE; it becomes demand only when an "
                    "executable consumer reads it"}


def confirmatory_reserved(manifest_path: Path) -> dict:
    if not manifest_path.is_file():
        return {"state": "UNAVAILABLE",
                "reason": "no public manifest on this host",
                "datasets": []}
    doc = json.loads(manifest_path.read_text())
    reserved = [{"dataset": k, "admission": v.get("admission"),
                 "family": v.get("family"), "sha256": v.get("sha256")}
                for k, v in sorted(doc.get("datasets", {}).items())
                if v.get("admission") == "ADMISSIBLE"]
    return {"state": "RESERVED_FOR_CONFIRMATION",
            "datasets": reserved,
            "note": "examining these would spend confirmation; no "
                    "development measurement may touch them"}


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictor-root", required=True, type=Path)
    ap.add_argument("--agent-multi-root", required=True, type=Path)
    ap.add_argument("--public-manifest", type=Path, default=(
        Path.home() / ".local/share/agent-multi"
        / "t2_public_data_manifest_20260906.json"))
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--derived-at", required=True)
    a = ap.parse_args(argv)

    sup = supervised_demand(a.predictor_root)
    rl = rl_demand(a.agent_multi_root)
    active_datasets = {s["dataset"] for s in sup["subjects"]}
    research = research_candidates(a.predictor_root, active_datasets)
    reserved = confirmatory_reserved(a.public_manifest)

    # ---- C46: six grains, kept apart -------------------------------
    x_subjects = [s for s in sup["subjects"] if s["side"] == "x"]
    y_subjects = [s for s in sup["subjects"] if s["side"] == "y"]
    unique_names = sorted({s["column"] for s in sup["subjects"]})
    dataset_column = sorted({(s["dataset"], s["column"])
                             for s in sup["subjects"]})
    research_cols = sum(d["non_temporal_columns"]
                        for d in research.get("datasets", []))

    def subset_claim(small: set, large: set):
        """C46: an empty set proves nothing about containment."""
        if not small:
            return NOT_APPLICABLE
        return sorted(small) == sorted(small & large)

    grains = {
        "unique_column_names": len(unique_names),
        "dataset_column_subjects": len(dataset_column),
        "active_x_subjects": len(x_subjects),
        "active_y_subjects": len(y_subjects),
        "targets": len(sup["targets"]),
        "research_bank_candidates": research_cols,
        "rl_active_columns": len(rl["columns"]),
        "definition": {
            "unique_column_names": "distinct column NAMES across every "
                                   "active subject",
            "dataset_column_subjects": "distinct (dataset, column) "
                                       "pairs — a different population",
            "active_x_subjects": "(dataset, x, role, column)",
            "active_y_subjects": "(dataset, y, role, column)",
            "targets": "columns a config declares as its target",
            "research_bank_candidates": "non-temporal columns of "
                                        "registered datasets with no "
                                        "executable consumer",
        },
    }

    doc = {
        "schema": SCHEMA,
        "derived_at": a.derived_at,
        "ACTIVE_EXECUTION_DEMAND": {
            "supervised": {
                "executable_configs": len(sup["executable_configs"]),
                "unreachable_configs": len(sup["unreachable_configs"]),
                "subjects": sup["subjects"],
                "targets": sup["targets"],
                "configs": sup["executable_configs"],
                "unreachable": sup["unreachable_configs"][:20],
            },
            "rl": {
                "active_configs": rl["active_configs"],
                "rejected_configs": rl["rejected_configs"],
                "columns": sorted(rl["columns"]),
            },
            "derivation": "from configurations the entry point can "
                          "execute — every declared input present — "
                          "read through the (dataset, side, role, "
                          "column) subject identity",
        },
        "RESEARCH_BANK_CANDIDATES": research,
        "CONFIRMATORY_RESERVED": reserved,
        "grains": grains,
        "relations": {
            "rl_is_subset_of_supervised": subset_claim(
                set(rl["columns"]), {s["column"] for s in sup["subjects"]}),
            # A containment test against an empty side answers a
            # question nobody asked. The useful fact is the count.
            "research_datasets_with_executable_consumer": sum(
                1 for d in research.get("datasets", [])
                if d["has_executable_consumer"]),
            "research_datasets_total": len(research.get("datasets", [])),
            "rule": "an empty set yields NOT_APPLICABLE; it never "
                    "yields a positive subset, sufficiency or coverage "
                    "claim",
        },
        "grants_nothing": "this derivation describes what is consumed "
                          "and what is merely registered. It confers no "
                          "eligibility on anything",
    }
    doc["universes_sha256"] = sha_obj(doc)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({
        "grains": {k: v for k, v in grains.items() if k != "definition"},
        "supervised_configs": len(sup["executable_configs"]),
        "supervised_unreachable": len(sup["unreachable_configs"]),
        "rl_active": len(rl["active_configs"]),
        "rl_rejected": len(rl["rejected_configs"]),
        "research_datasets": len(research.get("datasets", [])),
        "confirmatory_reserved": len(reserved.get("datasets", [])),
        "relations": {k: v for k, v in doc["relations"].items()
                      if k != "rule"},
        "universes_sha256": doc["universes_sha256"],
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
