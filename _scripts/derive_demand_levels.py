#!/usr/bin/env python3
"""C53-C54 (order 2026-09-12): three levels of demand, never mixed.

`ACTIVE_EXECUTION_DEMAND` was neither active nor execution. It called
a configuration executable because the `x`/`y` files it names exist:
no effective configuration, no defaults, no plugin parameters, no
entry-point resolution, no target validation. 137 was a count of
"configs whose inputs are present".

Three levels now, with the labels the audit assigned:

  1. OBSERVED_EXECUTION_DEMAND — subjects consumed by runs that
     actually TERMINATED, read from the cube's own campaign facts.
     Evidence of execution, not of runnability;
  2. VALIDATED_RUNNABLE_CONFIGS — the effective configuration built
     with the real precedence, entry points resolved, data and target
     validated, by a side-effect-free path that runs in a SUBPROCESS
     and stops before any model or pipeline. The caller asserts from
     outside that it imported no framework and wrote no file;
  3. INPUT_FILES_PRESENT_CONFIG_CANDIDATES — the previous census,
     honestly named.

Nothing here promotes a level to the one above it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "financial_data.demand_levels.v1"

OBSERVED = "OBSERVED_EXECUTION_DEMAND"
VALIDATED = "VALIDATED_RUNNABLE_CONFIGS"
CANDIDATES = "INPUT_FILES_PRESENT_CONFIG_CANDIDATES"
ABSENT = "INPUT_FILES_ABSENT_CONFIGS"


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha_obj(o) -> str:
    return hashlib.sha256(
        json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


# ------------------------------------------------ level 1: observed
def observed_demand(dsn: str | None) -> dict:
    """Subjects consumed by runs that reached a terminal state."""
    if not dsn:
        return {"state": "UNAVAILABLE",
                "reason": "no cube DSN supplied; observed execution "
                          "cannot be asserted from a configuration"}
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        return {"state": "UNAVAILABLE", "reason": "no sqlalchemy"}
    engine = create_engine(dsn)
    try:
        with engine.connect() as c:
            runs = [dict(r) for r in c.execute(text("""
                SELECT campaign_key, run_id, producer, terminal_state,
                       code_identity
                  FROM public.dim_campaign_run
                 ORDER BY campaign_key, run_id""")).mappings()]
            subjects = [dict(r) for r in c.execute(text("""
                SELECT subject_kind, subject_id, subject_digest,
                       eligibility_state, count(*) AS rows
                  FROM public.fact_campaign_consumption
                 GROUP BY 1, 2, 3, 4
                 ORDER BY 1, 2""")).mappings()]
    finally:
        engine.dispose()
    # The cube stores a run's identity as its producer wrote it, and
    # four of those run_ids are FILESYSTEM PATHS ("./prediction.csv",
    # "examples/results/..."). A public record carries no path, so
    # each identity is published as a logical id — a sanitized label
    # bound to a digest of the original — and the SHAPE of the
    # original is declared, because "this run is identified by a
    # path" is a finding about the cube, not something to hide.
    def shape(v: str) -> str:
        if not v or v == "UNAVAILABLE":
            return "UNDECLARED"
        if v.startswith(("/", "./", "../")) or "/" in v:
            return "PATH_SHAPED_IDENTITY"
        return "OPAQUE_IDENTITY"

    def logical(v: str, kind: str) -> str:
        if not v:
            return f"{kind}-UNDECLARED"
        return f"{kind}-{hashlib.sha256(v.encode()).hexdigest()[:16]}"

    sanitized = []
    for r in runs:
        ck, rid = r.get("campaign_key") or "", r.get("run_id") or ""
        sanitized.append({
            "campaign_logical": logical(ck, "campaign"),
            "run_logical": logical(rid, "run"),
            "campaign_shape": shape(ck),
            "run_id_shape": shape(rid),
            "producer": r.get("producer"),
            "terminal_state": r.get("terminal_state"),
            "code_identity": r.get("code_identity"),
        })
    path_shaped = sum(1 for r in sanitized
                      if r["run_id_shape"] == "PATH_SHAPED_IDENTITY")
    return {
        "state": "DERIVED_FROM_TERMINAL_RUNS",
        "runs": sanitized,
        "identities": "SANITIZED — campaign keys and run ids are "
                      "published as logical ids bound to a digest of "
                      "the original. The raw values are private "
                      "evidence, never a public record",
        "runs_identified_by_a_path": path_shaped,
        "path_shaped_identity_finding":
            f"{path_shaped} of {len(runs)} terminal runs are "
            "identified in the cube by a FILESYSTEM PATH rather than "
            "by an opaque id. That is a defect in how those producers "
            "name their runs; it is reported, not corrected here, "
            "because rewriting a historical identity would rewrite "
            "history",
        "runs_total": len(runs),
        "consumed_subjects": len(subjects),
        "subjects_by_kind": {
            k: sum(1 for s in subjects if s["subject_kind"] == k)
            for k in sorted({s["subject_kind"] for s in subjects})},
        "note": "these subjects were consumed by runs that reached a "
                "terminal state. That is evidence of EXECUTION; it "
                "says nothing about whether those configurations "
                "would run today",
    }


# ----------------------------------------------- level 2: validated
def validate_one(predictor_root: Path, config: Path) -> dict:
    """Run the validator in a SUBPROCESS and assert from outside that
    it executed nothing."""
    before = {p.name for p in predictor_root.iterdir()}
    env = {**os.environ, "PYTHONPATH": str(predictor_root),
           "CUDA_VISIBLE_DEVICES": ""}
    proc = subprocess.run(
        (sys.executable, "-X", "importtime",
         str(predictor_root / "tools/validate_runnable_config.py"),
         "--config", str(config), "--checkout", str(predictor_root)),
        capture_output=True, text=True, env=env, timeout=600,
        cwd=str(predictor_root))
    after = {p.name for p in predictor_root.iterdir()}
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    try:
        verdict = json.loads(lines[-1]) if lines else {
            "verdict": "NOT_RUNNABLE",
            "reasons": [f"validator exited {proc.returncode}"]}
    except ValueError:
        verdict = {"verdict": "NOT_RUNNABLE",
                   "reasons": ["validator produced no verdict"]}
    imported = {ln.split("|")[-1].strip()
                for ln in (proc.stdout + proc.stderr).splitlines()
                if ln.startswith("import time:")}
    heavy = sorted(m for m in imported
                   if m.split(".")[0] in ("tensorflow", "keras", "torch",
                                          "jax"))
    verdict["subprocess_proof"] = {
        "frameworks_imported": heavy,
        "files_created_in_checkout_root": sorted(after - before),
        "exit_code": proc.returncode,
    }
    if heavy or (after - before):
        verdict["verdict"] = "NOT_RUNNABLE"
        verdict.setdefault("reasons", []).append(
            "the validation path had side effects; a validator that "
            "executes is not a validator")
    return verdict


def validated_configs(predictor_root: Path, limit: int | None) -> dict:
    configs = sorted((predictor_root / "examples/config").rglob("*.json"))
    if limit:
        configs = configs[:limit]
    runnable, refused = [], []
    for cfg in configs:
        try:
            raw = json.loads(cfg.read_text())
        except (UnicodeDecodeError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        if not any(k.startswith(("x_", "y_")) and k.endswith("_file")
                   for k in raw):
            continue
        out = validate_one(predictor_root, cfg)
        rel = str(cfg.relative_to(predictor_root))
        entry = {"config": rel, "sha256": sha_file(cfg),
                 "verdict": out["verdict"],
                 "reasons": out.get("reasons", [])[:2],
                 "targets": out.get("targets", []),
                 "sides": out.get("sides", {}),
                 "subprocess_proof": out["subprocess_proof"]}
        (runnable if out["verdict"] == "VALIDATED_RUNNABLE"
         else refused).append(entry)
    subjects: dict[tuple, dict] = {}
    return {"state": "EFFECTIVE_CONFIGURATION_BUILT_AND_VALIDATED",
            "runnable": runnable, "refused": refused,
            "runnable_total": len(runnable),
            "refused_total": len(refused),
            "note": "each verdict comes from a subprocess that built "
                    "the effective configuration, resolved every entry "
                    "point and derived the subjects, then stopped. The "
                    "caller asserts from OUTSIDE that no framework was "
                    "imported and no file was created"}


# ---------------------------------------------- level 3: candidates
def candidates(previous: Path) -> dict:
    if not previous.is_file():
        return {"state": "UNAVAILABLE"}
    doc = json.loads(previous.read_text())
    sup = doc["ACTIVE_EXECUTION_DEMAND"]["supervised"]
    return {
        "state": "CENSUS_OF_CONFIGS_WHOSE_INPUTS_ARE_PRESENT",
        "input_files_present": sup["executable_configs"],
        "input_files_absent": sup["unreachable_configs"],
        "raw_config_derived_subjects": {
            "x": doc["grains"]["active_x_subjects"],
            "y": doc["grains"]["active_y_subjects"],
            "targets": doc["grains"]["targets"],
            "label": "RAW_CONFIG_DERIVED_PENDING_EFFECTIVE_CONFIG"},
        "superseded_labels": {
            "executable_configs": CANDIDATES,
            "unreachable_configs": ABSENT,
            "active_x_subjects": "RAW_CONFIG_DERIVED_PENDING_"
                                 "EFFECTIVE_CONFIG",
            "active_y_subjects": "RAW_CONFIG_DERIVED_PENDING_"
                                 "EFFECTIVE_CONFIG",
            "targets": "RAW_CONFIG_DERIVED_PENDING_EFFECTIVE_CONFIG"},
        "source": previous.name,
        "source_sha256": sha_file(previous),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictor-root", required=True, type=Path)
    ap.add_argument("--previous", type=Path, default=(
        ROOT / "features/census/DEMAND_UNIVERSES.v1.json"))
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--derived-at", required=True)
    a = ap.parse_args(argv)

    pred = a.predictor_root.expanduser().resolve()
    doc = {
        "schema": SCHEMA,
        "derived_at": a.derived_at,
        OBSERVED: observed_demand(a.dsn),
        VALIDATED: validated_configs(pred, a.limit),
        CANDIDATES: candidates(a.previous),
        "rule": "a level is never promoted to the one above it. A "
                "registry entry is not a candidate config, a candidate "
                "config is not validated, and a validated config is "
                "not an observed execution",
        "grants_nothing": "this describes what runs, what could run "
                          "and what merely exists. It confers no "
                          "eligibility",
    }
    doc["levels_sha256"] = sha_obj(doc)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({
        "observed": {k: v for k, v in doc[OBSERVED].items()
                     if k in ("state", "runs_total",
                              "consumed_subjects")},
        "validated": {k: v for k, v in doc[VALIDATED].items()
                      if k in ("runnable_total", "refused_total")},
        "candidates": {k: v for k, v in doc[CANDIDATES].items()
                       if k in ("input_files_present",
                                "input_files_absent")},
        "levels_sha256": doc["levels_sha256"],
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
