#!/usr/bin/env python3
"""C93, C96-C97 (order 2026-09-12): the FEATURE_DAG.v3 disposition, the
PRODUCER_BINDING_MANIFEST.v2 and FEATURE_DAG.v4 for the SUCCESSOR
dataset produced by a prospective rerun (prospective_producer_rerun.py).

Nothing here rewrites v1, v2 or v3. The historical dataset keeps the
class v3 gave every one of its columns, and zero CAUSAL_ACTIVE.

A successor column is CAUSAL_ACTIVE only when ALL of these hold:

1. a COMPLETE binding: dataset_id + dataset_sha256 + input_sha256 ->
   repository + commit + tree + file + symbol + config_sha256 +
   output_column, every field present and well formed, and every digest
   re-verified against the successor root and against git (the commit
   exists, its tree is the recorded tree, and the executed files at that
   commit hash to the recorded sha256);
2. the end-to-end prefix-invariance probe of that run gives the column
   PASS (non-vacuous and perturbation-sensitive);
3. v3's static analyzer, run on the producer source AT THE RECORDED
   COMMIT with the bound symbol selected, gives STATIC_CAUSAL (this is
   stricter than the order: the dynamic probe never replaces the static
   proof).

A FAIL of (2) or a forward read in (3) makes the column NON_CAUSAL; any
other gap leaves it UNRESOLVED or UNRESOLVED_PRODUCER_BINDING. No column
is dropped. No availability time and no license are granted.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "features" / "census"


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


d3 = _load("derive_feature_dag_v3", Path(__file__).resolve().parent
           / "derive_feature_dag_v3.py")
rr = _load("prospective_producer_rerun", Path(__file__).resolve().parent
           / "prospective_producer_rerun.py")

CAUSAL, CANDIDATE, NON_CAUSAL = d3.CAUSAL, d3.CANDIDATE, d3.NON_CAUSAL
UNRESOLVED, UNBOUND = d3.UNRESOLVED, d3.UNBOUND

BINDING_FIELDS = ("dataset_id", "dataset_sha256", "input_sha256",
                  "repository", "commit", "tree", "file", "file_sha256",
                  "symbol", "config_sha256", "output_column")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX40 = re.compile(r"[0-9a-f]{40}")
PROTECTED = ("FEATURE_DAG.v1.json", "FEATURE_DAG.v2.json",
             "FEATURE_DAG.v3.json", "PRODUCER_BINDING_MANIFEST.v1.json",
             "ETH_H4_TEMPORAL_CONTRACT.v1.json")
HISTORICAL_DATASET = "financial_data.project3.ethusdt_4h_tech_stat.model_ready.v1"


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def binding_complete(b: dict | None) -> tuple[bool, list[str]]:
    """Every minimum field present and well formed."""
    if not isinstance(b, dict):
        return False, ["BINDING_ABSENT"]
    missing = []
    for f in BINDING_FIELDS:
        v = b.get(f)
        if not isinstance(v, str) or not v.strip():
            missing.append(f"FIELD_MISSING:{f}")
        elif f in ("dataset_sha256", "input_sha256", "file_sha256",
                   "config_sha256") and not _HEX64.fullmatch(v):
            missing.append(f"FIELD_MALFORMED:{f}")
        elif f in ("commit", "tree") and not _HEX40.fullmatch(v):
            missing.append(f"FIELD_MALFORMED:{f}")
    return not missing, missing


def classify_successor(binding_ok: bool, static_klass: str,
                       probe_verdict: str | None) -> dict:
    if static_klass == NON_CAUSAL:
        return {"class": NON_CAUSAL, "codes": ["STATIC_FORWARD_READ"]}
    if probe_verdict == "FAIL":
        return {"class": NON_CAUSAL, "codes": ["E2E_PREFIX_INVARIANCE_FAILED"]}
    if not binding_ok:
        return {"class": UNBOUND, "codes": ["BINDING_INCOMPLETE"]}
    codes = []
    if static_klass != d3.STATIC_CAUSAL:
        codes.append(f"STATIC_{static_klass}")
    if probe_verdict != "PASS":
        codes.append(f"E2E_{probe_verdict or 'NOT_RUN'}")
    if codes:
        return {"class": UNRESOLVED, "codes": codes}
    return {"class": CAUSAL, "codes": []}


# ---------------------------------------------------------- C93
def build_v3_disposition(census: Path = CENSUS,
                         decided_at: str = "2026-09-12T00:00:00Z") -> dict:
    v3p = census / "FEATURE_DAG.v3.json"
    b1p = census / "PRODUCER_BINDING_MANIFEST.v1.json"
    v3 = json.loads(v3p.read_text())
    b1 = json.loads(b1p.read_text())
    active = sum(n["class"] == CAUSAL for n in v3["nodes"])
    per_ds = {}
    for n in v3["nodes"]:
        per_ds.setdefault(n["dataset_id"], {}).setdefault(n["class"], 0)
        per_ds[n["dataset_id"]][n["class"]] += 1
    gaps = {d["dataset_id"]: sorted(d.get("gaps", []))
            for d in b1["datasets"]}
    codes = {}
    for d in b1["datasets"]:
        for col, rec in d.get("columns", {}).items():
            for c in rec.get("codes", []):
                codes[c] = codes.get(c, 0) + 1
    return {
        "schema": "financial_data.feature_dag_disposition.v1",
        "order_item": "C93",
        "decided_at": decided_at,
        "subject": {
            "file": "features/census/FEATURE_DAG.v3.json",
            "file_sha256": sha_file(v3p),
            "dag_sha256": v3["dag_sha256"],
            "binding_manifest": {
                "file": "features/census/PRODUCER_BINDING_MANIFEST.v1.json",
                "file_sha256": sha_file(b1p),
                "manifest_sha256": b1["manifest_sha256"]}},
        "disposition": "STATIC_CANDIDATE_INVENTORY_UNBOUND",
        "accepted_as": "a static inventory of candidate lineages only",
        "rewritten": False,
        "columns_examined": v3["columns_examined"],
        "by_class": v3["by_class"],
        "by_dataset_and_class": dict(sorted(per_ds.items())),
        "causal_active_columns": active,
        "bindings_established": b1["bindings_established"],
        "licenses_granted": 0,
        "license": "NONE: this disposition licenses no column for any use",
        "availability_granted": "NONE: every column stays UNAVAILABLE",
        "declared_limitations": {
            "binding_gaps_by_dataset": gaps,
            "binding_codes_by_column_count": dict(sorted(codes.items())),
            "static_analysis": [
                "an abstract interpreter over one producer symbol; unknown "
                "calls, dynamic dispatch, positional indices, cycles and "
                "budget exhaustion are UNRESOLVED",
                "static STATIC_CAUSAL describes the code as read in the "
                "scanned checkout, not the code that produced the "
                "historical bytes",
            ],
            "provenance": [
                "the Stage 2.2 run receipt records no commit and no code "
                "digest",
                "the Stage 2.2 run predates the first commit of the "
                "producer file",
                "the code that assembled the historical model-ready CSV is "
                "in no repository (EXPORT_STEP_CODE_ABSENT)",
                "typical_price has no source artifact",
                "OHLCV values are not value-equal to any named source "
                "artifact",
                "statistical__log_return_1 was renamed by an unrecorded "
                "export",
            ],
            "dynamic_probe": [
                "the v3 prefix-invariance probe ran on synthetic OHLCV only, "
                "per producer symbol, not end to end through an assembler",
                "its write guard patches Python entry points; a C extension "
                "could bypass it",
            ],
            "temporal": [
                "timestamp semantics are UNDECLARED in v3; no availability "
                "time is derived",
            ],
        },
        "historical_dataset": {
            "dataset_id": HISTORICAL_DATASET,
            "causal_active_columns": per_ds.get(
                HISTORICAL_DATASET, {}).get(CAUSAL, 0),
            "statement": "stays at zero CAUSAL_ACTIVE; a later successor "
                         "rerun never binds the historical run"},
        "authorized_next_path": "C94-C97: a prospective rerun of the "
                                "current committed producer on the recorded "
                                "physical inputs creates a NEW successor "
                                "dataset with its own bindings "
                                "(PRODUCER_BINDING_MANIFEST.v2, "
                                "FEATURE_DAG.v4)",
    }


# ---------------------------------------------------- successor root
def _git(repo: Path, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                       check=False)
    return r.returncode, r.stdout


def verify_successor_root(root: Path, repo: Path | None) -> dict:
    """Re-verify every digest a binding will cite. Returns facts + codes."""
    root = Path(root)
    codes, facts = [], {}

    def jload(name):
        p = root / name
        if not p.is_file():
            codes.append(f"ROOT_FILE_ABSENT:{name}")
            return None
        return json.loads(p.read_text())

    if (root / rr.STOP_NAME).exists():
        codes.append("RUN_STOPPED")
    pre, post = jload(rr.PRE_NAME), jload(rr.POST_NAME)
    e2e, cmp_doc = jload(rr.E2E_NAME), jload(rr.CMP_NAME)
    if not (pre and post and e2e):
        return {"ok": False, "codes": codes, "facts": facts, "pre": pre,
                "post": post, "e2e": e2e, "comparison": cmp_doc}
    for doc, field in ((pre, "manifest_sha256"), (post, "manifest_sha256")):
        want = rr.sha_obj({k: v for k, v in doc.items() if k != field})
        if doc.get(field) != want:
            codes.append(f"MANIFEST_SELF_DIGEST_MISMATCH:{doc['schema']}")
    if post.get("pre_run_manifest_sha256") != pre.get("manifest_sha256"):
        codes.append("POST_DOES_NOT_CITE_PRE")
    if e2e.get("pre_run_manifest_sha256") != pre.get("manifest_sha256"):
        codes.append("E2E_DOES_NOT_CITE_PRE")
    for rec in post.get("outputs", []):
        p = root / rec["path"]
        if not p.is_file() or sha_file(p) != rec["sha256"]:
            codes.append(f"OUTPUT_DIGEST_MISMATCH:{rec['path']}")
    succ = root / rr.SUCC_PARQUET
    facts["dataset_sha256"] = sha_file(succ) if succ.is_file() else None
    if facts["dataset_sha256"] != post.get("successor_dataset_sha256"):
        codes.append("SUCCESSOR_DIGEST_MISMATCH")
    if e2e.get("successor_parquet_sha256") != facts["dataset_sha256"]:
        codes.append("E2E_PROBED_A_DIFFERENT_SUCCESSOR")
    inp = root / rr.INPUT_COPY
    facts["input_sha256"] = sha_file(inp) if inp.is_file() else None
    if facts["input_sha256"] != pre["inputs"]["raw_ohlcv"]["sha256"] or \
            facts["input_sha256"] != post.get("input_sha256"):
        codes.append("INPUT_DIGEST_MISMATCH")
    rep = pre["repository"]
    facts.update(commit=rep.get("commit"), tree=rep.get("tree"),
                 repository=rep.get("name"),
                 config_sha256=pre.get("config_sha256"),
                 clean=rep.get("clean"))
    if rep.get("clean") is not True:
        codes.append("CHECKOUT_NOT_RECORDED_CLEAN")
    facts["git_verified"] = False
    if repo is None:
        codes.append("GIT_REPOSITORY_NOT_PROVIDED")
    else:
        rc, _ = _git(repo, "cat-file", "-e", f"{rep['commit']}^{{commit}}")
        if rc != 0:
            codes.append("COMMIT_ABSENT_FROM_REPOSITORY")
        else:
            rc, tree = _git(repo, "rev-parse", f"{rep['commit']}^{{tree}}")
            if tree.decode().strip() != rep.get("tree"):
                codes.append("TREE_MISMATCH")
            bad = False
            for key, rec in pre["executed_files"].items():
                rc, blob = _git(repo, "show", f"{rep['commit']}:{rec['path']}")
                if rc != 0 or hashlib.sha256(blob).hexdigest() != \
                        rec["sha256"]:
                    codes.append(f"EXECUTED_FILE_NOT_AT_COMMIT:{key}")
                    bad = True
            facts["git_verified"] = not bad and "TREE_MISMATCH" not in codes
    return {"ok": not codes, "codes": codes, "facts": facts, "pre": pre,
            "post": post, "e2e": e2e, "comparison": cmp_doc}


def _module_from_source(name: str, source: str, filename: str):
    import types
    mod = types.ModuleType(name)
    mod.__file__ = filename
    sys.modules[name] = mod
    exec(compile(source, filename, "exec"), mod.__dict__)
    return mod


def _source_at_commit(repo: Path | None, commit: str, rel: str,
                      expect_sha: str):
    if repo is None:
        return None
    rc, blob = _git(repo, "show", f"{commit}:{rel}")
    if rc != 0 or hashlib.sha256(blob).hexdigest() != expect_sha:
        return None
    return blob.decode("utf-8")


def derive(successor_root: Path, repo: Path | None, derived_at: str,
           census: Path = CENSUS, asm=None) -> tuple[dict, dict]:
    ver = verify_successor_root(successor_root, repo)
    pre, post, e2e = ver["pre"], ver["post"], ver["e2e"]
    facts = ver["facts"]
    if pre is None:
        raise SystemExit("successor root lacks a pre-run manifest")
    files = pre["executed_files"]
    prod_rel, asm_rel = files["producer"]["path"], files["assembler"]["path"]
    commit = facts.get("commit") or ""
    sources = {
        "producer": _source_at_commit(repo, commit, prod_rel,
                                      files["producer"]["sha256"]),
        "assembler": _source_at_commit(repo, commit, asm_rel,
                                       files["assembler"]["sha256"])}
    if asm is None:
        # the column map comes from the assembler AS EXECUTED (the blob at
        # the recorded commit); the working copy is only a fallback
        asm = (_module_from_source("_assembler_at_commit",
                                   sources["assembler"], asm_rel)
               if sources["assembler"] is not None else
               _load("assemble_eth_h4_model_ready_successor",
                     Path(__file__).resolve().parent /
                     "assemble_eth_h4_model_ready_successor.py"))
    idx = {k: d3.index_source(v, file=(prod_rel if k == "producer"
                                       else asm_rel),
                              repo=facts.get("repository") or "unknown")
           for k, v in sources.items() if v is not None}
    succ_id = pre["successor_dataset_id"]
    expected = [c for c in pre["expected_output_columns"] if c != "DATE_TIME"]
    produced = set(post.get("successor_columns", [])) if post else set()
    probe_cols = (e2e or {}).get("columns", {})
    bindings, nodes, by_class = [], [], {}
    for col in expected:
        src_frame, src_col, symbol = asm.COLUMN_SOURCES.get(
            col, (None, None, None))
        hop = "assembler" if src_frame == "bar" else "producer"
        rel = asm_rel if hop == "assembler" else prod_rel
        b = {"dataset_id": succ_id,
             "dataset_sha256": facts.get("dataset_sha256"),
             "input_sha256": facts.get("input_sha256"),
             "repository": facts.get("repository"),
             "commit": facts.get("commit"), "tree": facts.get("tree"),
             "file": rel if symbol else None,
             "file_sha256": files[hop]["sha256"] if symbol else None,
             "symbol": symbol, "config_sha256": facts.get("config_sha256"),
             "output_column": col,
             "producer_output_column": src_col,
             "assembly": {"file": asm_rel,
                          "file_sha256": files["assembler"]["sha256"],
                          "symbol": pre["assembler"]["symbol"]},
             "pre_run_manifest_sha256": pre.get("manifest_sha256"),
             "post_run_manifest_sha256": (post or {}).get("manifest_sha256")}
        ok, bcodes = binding_complete(b)
        if not ver["ok"]:
            ok = False
            bcodes = bcodes + ver["codes"]
        if col not in produced:
            ok = False
            bcodes.append("COLUMN_NOT_IN_SUCCESSOR_OUTPUT")
        if hop not in idx:
            static = {"klass": UNRESOLVED, "lookback": None, "why":
                      "producer source at the recorded commit unavailable",
                      "unresolved": ["SOURCE_AT_COMMIT_UNAVAILABLE"],
                      "forward": [], "leaves": []}
        elif symbol is None:
            static = {"klass": UNRESOLVED, "lookback": None,
                      "why": "no declared source", "forward": [],
                      "unresolved": ["NO_DECLARED_SOURCE"], "leaves": []}
        else:
            static = d3.classify(src_col if hop == "producer" else col,
                                 idx[hop], selected=(
                                     facts.get("repository"), rel, symbol))
        pv = probe_cols.get(col, {}).get("verdict")
        final = classify_successor(ok, static["klass"], pv)
        by_class[final["class"]] = by_class.get(final["class"], 0) + 1
        if ok:
            bindings.append(b)
        nodes.append({
            "dataset_id": succ_id, "column": col, "class": final["class"],
            "reason_codes": sorted(set(final["codes"] + bcodes)),
            "binding": {"complete": ok, "codes": sorted(set(bcodes)),
                        "file": rel, "symbol": symbol,
                        "producer_output_column": src_col},
            "static": {"class": static["klass"],
                       "lookback_bars": static.get("lookback"),
                       "leaves": static.get("leaves", []),
                       "forward_reads": static.get("forward", []),
                       "unresolved_because": sorted(set(
                           static.get("unresolved", [])))},
            "e2e_prefix_invariance": {
                "verdict": pv or "NOT_RUN",
                **{k: probe_cols.get(col, {}).get(k) for k in (
                    "runs_pass", "runs_fail", "runs_vacuous",
                    "sensitive_runs", "compared_values")}},
            "availability": {
                "earliest_available_time": "UNAVAILABLE",
                "reason": "timestamp semantics are owned by the temporal "
                          "availability work; this DAG derives no time"},
        })
    # historical datasets: v3 classes carried verbatim, never upgraded
    v3 = json.loads((census / "FEATURE_DAG.v3.json").read_text())
    hist_nodes = [{"dataset_id": n["dataset_id"], "column": n["column"],
                   "class": n["class"], "source": "FEATURE_DAG.v3.json"}
                  for n in v3["nodes"]]
    hist_active = sum(n["class"] == CAUSAL for n in hist_nodes)
    if hist_active:
        raise AssertionError("a historical column is CAUSAL_ACTIVE")
    root_id = f"crispdm-successors/{pre['run_id']}"
    manifest = {
        "schema": "financial_data.producer_binding_manifest.v2",
        "derived_at": derived_at,
        "additive": "PRODUCER_BINDING_MANIFEST.v1.json is left "
                    "byte-identical; v2 binds only the successor dataset",
        "required_fields": list(BINDING_FIELDS),
        "successor": {
            "dataset_id": succ_id, "root_id": root_id,
            "dataset_path": rr.SUCC_PARQUET,
            "dataset_sha256": facts.get("dataset_sha256"),
            "csv_sha256": (post or {}).get("successor_csv_sha256"),
            "input_sha256": facts.get("input_sha256"),
            "input_recorded_as": {k: pre["inputs"]["raw_ohlcv"][k]
                                  for k in ("root_id", "path", "sha256")},
            "pre_run_manifest_sha256": pre.get("manifest_sha256"),
            "post_run_manifest_sha256": (post or {}).get("manifest_sha256"),
            "verification_codes": ver["codes"],
            "git_verified": facts.get("git_verified", False)},
        "historical": {
            "dataset_id": HISTORICAL_DATASET,
            "bindings_established": 0,
            "source": "PRODUCER_BINDING_MANIFEST.v1.json",
            "source_sha256": sha_file(census /
                                      "PRODUCER_BINDING_MANIFEST.v1.json"),
            "statement": "the successor rerun does not bind the historical "
                         "run"},
        "bindings": bindings,
        "bindings_established": len(bindings),
        "rules": {
            "bound": "a binding is complete when every required field is "
                     "present and well formed, the successor root's "
                     "manifests and output digests re-verify, and git "
                     "confirms commit, tree and executed file digests",
            "zero_is_reportable": "no binding is manufactured"},
    }
    manifest["manifest_sha256"] = d3.sha_obj(
        {k: v for k, v in manifest.items() if k != "derived_at"})
    doc = {
        "schema": "financial_data.feature_dag.v4",
        "derived_at": derived_at,
        "additive": "v1, v2 and v3 are left byte-identical",
        "successor_dataset_id": succ_id,
        "successor_root_id": root_id,
        "columns_examined": len(nodes),
        "by_class": dict(sorted(by_class.items())),
        "causal_active_columns": by_class.get(CAUSAL, 0),
        "bindings_established": len(bindings),
        "binding_manifest_sha256": manifest["manifest_sha256"],
        "e2e_verdict": (e2e or {}).get("verdict"),
        "historical_causal_active_columns": hist_active,
        "historical_nodes_carried_from_v3": len(hist_nodes),
        "classes": [CAUSAL, NON_CAUSAL, UNRESOLVED, UNBOUND],
        "nodes": nodes,
        "historical_nodes": hist_nodes,
        "rules": {
            "causal_active": "complete binding AND end-to-end prefix "
                             "invariance PASS for the column AND static "
                             "STATIC_CAUSAL of the bound symbol at the "
                             "recorded commit",
            "non_causal": "a static forward read or an end-to-end FAIL",
            "no_drop": "every expected successor column is listed; one "
                       "whose producer or assembly did not run stays "
                       "UNRESOLVED_PRODUCER_BINDING",
            "historical": "historical classes are v3's, verbatim; zero "
                          "CAUSAL_ACTIVE",
            "availability": "no availability time and no license are "
                            "granted"},
    }
    doc["dag_sha256"] = d3.sha_obj(doc)
    return doc, manifest


def write_new(path: Path, obj: dict) -> None:
    data = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    if re.search(r"(/home|/Users|/root)/", data):
        raise SystemExit(f"refusing to publish an absolute path in {path.name}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(data)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("disposition")
    d.add_argument("--output", type=Path,
                   default=CENSUS / "FEATURE_DAG_V3_DISPOSITION.v1.json")
    d.add_argument("--decided-at", default="2026-09-12T00:00:00Z")
    v = sub.add_parser("derive")
    v.add_argument("--successor-root", required=True, type=Path)
    v.add_argument("--repository", type=Path, default=ROOT)
    v.add_argument("--derived-at", required=True)
    v.add_argument("--output", type=Path,
                   default=CENSUS / "FEATURE_DAG.v4.json")
    v.add_argument("--binding-output", type=Path,
                   default=CENSUS / "PRODUCER_BINDING_MANIFEST.v2.json")
    a = ap.parse_args(argv)
    if a.cmd == "disposition":
        write_new(a.output, build_v3_disposition())
        return 0
    before = {f: sha_file(CENSUS / f) for f in PROTECTED
              if (CENSUS / f).is_file()}
    doc, manifest = derive(a.successor_root.expanduser(), a.repository,
                           a.derived_at)
    write_new(a.binding_output, manifest)
    write_new(a.output, doc)
    after = {f: sha_file(CENSUS / f) for f in before}
    if before != after:
        raise SystemExit("a protected census artifact changed")
    print(json.dumps({k: doc[k] for k in (
        "columns_examined", "by_class", "causal_active_columns",
        "bindings_established", "e2e_verdict",
        "historical_causal_active_columns", "dag_sha256")},
        indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
