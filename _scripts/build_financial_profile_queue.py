#!/usr/bin/env python3
"""C127 (order 2026-09-12): the financial bank profile queue.

"No reprocese 14 GiB sin necesidad." The queue is derived from METADATA
ONLY: the incremental census, the producer binding manifest, feature
lineage, the feature DAG, the demand universes, the provenance.json
files the census names, data dictionaries the census names, and file
sizes the census already recorded. No parquet or CSV value is read,
and nothing here computes a target, a score or a model.

Per conceptual variable it derives producer, frequencies, feature
family, consumer, bytes presence, lineage verifiability, total bytes,
sealed periods and license state. Every attribute is taken from a
declared artifact or written UNRESOLVED / UNKNOWN; nothing is inferred
from a column or entity name.

The queue unit is one (variable, appearance) item, so the frequency of
a stratum is the frequency of the bytes that would be read. Strata are
producer x frequency x feature_family x consumer. Order: tier 1 (bytes
present and lineage verifiable), tier 2 (bytes present only), tier 3
(the rest); inside a tier a deterministic round robin across sorted
strata, variable_id then appearance_id sorted inside each stratum.

A first batch is taken from the head of the queue under a declared
budget of unique appearance bytes, and every appearance in it gets a
common dataset contract (predictor tools/df_contract.py) that must
pass `seal`.

License: every variable is INTERNAL_RESEARCH_ONLY_PENDING_EVIDENCE.
Nothing here is public and nothing is granted.

Outputs are write-once.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA = "financial_data.financial_profile_queue.v1"
CONTRACTS_SCHEMA = "financial_data.financial_first_batch_contracts.v1"
ORDER_ITEM = "C127"
UNKNOWN = "UNKNOWN"
UNAVAILABLE = "UNAVAILABLE"
UNRESOLVED = "UNRESOLVED"
NONE = "NONE"
LICENSE_STATE = "INTERNAL_RESEARCH_ONLY_PENDING_EVIDENCE"
HEX64 = re.compile(r"[0-9a-f]{64}")

DEFAULT_CENSUS = ("features/census/artifacts/census-"
                  "49a8813d782a0e11cfcfde3e02a946fa04883db9f4e9563dced2fa24a7a1b82d.json")
DEFAULT_OUT = "features/census/FINANCIAL_PROFILE_QUEUE.v1.json"
DEFAULT_CONTRACTS_OUT = "features/census/FINANCIAL_FIRST_BATCH_CONTRACTS.v1.json"
DEFAULT_DERIVED_AT = "2026-09-12T00:00:00Z"
#: 1.5 GiB of unique appearance bytes, about 11% of the 13.45 GiB lake
DEFAULT_BUDGET_BYTES = 3 * (1 << 29)
CONTRACT_MODULE_NAME = "predictor/tools/df_contract.py"

CENSUS_ARTIFACTS = {
    "binding_manifest": "features/census/PRODUCER_BINDING_MANIFEST.v2.json",
    "feature_lineage": "features/census/FEATURE_LINEAGE.v1.json",
    "feature_dag": "features/census/FEATURE_DAG.v4.json",
    "demand_universes": "features/census/DEMAND_UNIVERSES.v1.json",
}
DEMAND_KEYS = ("ACTIVE_EXECUTION_DEMAND", "CONFIRMATORY_RESERVED",
               "RESEARCH_BANK_CANDIDATES")
#: declared frequency labels of the census -> nominal seconds; any other
#: label stays UNKNOWN
FREQUENCY_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800,
                     "1h": 3600, "4h": 14400, "1d": 86400}
DIGESTED_STATES = ("PHYSICALLY_DIGESTED", "REUSED_FROM_PREVIOUS_VERIFIED_CENSUS")
METADATA_SUFFIXES = (".json", ".md")
SEALED_SEARCH = {
    "searched": ["census appearances and variables",
                 "features/census/DEMAND_UNIVERSES.v1.json",
                 "features/census/PRODUCER_BINDING_MANIFEST.v2.json",
                 "features/census/FEATURE_LINEAGE.v1.json",
                 "features/census/FEATURE_DAG.v4.json",
                 "provenance.json files named by census lineage"],
    "declaration_keys": ["sealed_periods", "sealed_2025"],
    "not_applied": "the ETH H4 successor temporal contracts declare test and embargo "
                   "windows for the successor model-ready dataset, not for any census "
                   "appearance, so they are not carried onto census bytes",
}


class QueueRefusal(RuntimeError):
    pass


# ------------------------------------------------------------------ digests
def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


def sha_obj(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def census_self_sha(doc: dict) -> str:
    """The census self digest exactly as `_scripts/lib/incremental_census.py`
    `_self_sha` defines it."""
    body = {k: doc[k] for k in sorted(doc) if k != "census_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def read_metadata(root: Path, rel: str) -> bytes | None:
    """The only file reader: metadata suffixes only, never data bytes."""
    if Path(rel).suffix not in METADATA_SUFFIXES:
        raise QueueRefusal(f"refusing to read non-metadata file {rel!r}")
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise QueueRefusal(f"refusing a path outside the repository: {rel!r}")
    p = root / rel
    return p.read_bytes() if p.is_file() else None


def load_contract_module(path: Path):
    spec = importlib.util.spec_from_file_location("df_contract_c127", path)
    if spec is None or spec.loader is None:
        raise QueueRefusal("the common contract module cannot be loaded")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------- provenance
class ProvenanceReader:
    """Reads and pins the provenance.json / data_dictionary.md files the
    census names. Every file it touched is recorded with its digest."""

    def __init__(self, root: Path):
        self.root = root
        self.pinned: dict[str, str] = {}
        self._docs: dict[str, dict | None] = {}

    def digest(self, rel: str) -> str:
        if rel not in self.pinned:
            b = read_metadata(self.root, rel)
            self.pinned[rel] = sha_bytes(b) if b is not None else UNAVAILABLE
            if rel.endswith(".json"):
                try:
                    self._docs[rel] = json.loads(b) if b is not None else None
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._docs[rel] = None
        return self.pinned[rel]

    def doc(self, rel: str) -> dict | None:
        self.digest(rel)
        d = self._docs.get(rel)
        return d if isinstance(d, dict) else None


def _declared_file_digests(doc: dict | None) -> list[str]:
    files = (doc or {}).get("files") or []
    return [f["sha256"] for f in files
            if isinstance(f, dict) and isinstance(f.get("sha256"), str)
            and HEX64.fullmatch(f["sha256"])]


def _declared_source(value) -> str | None:
    return value if isinstance(value, str) and value.strip() and value not in (UNKNOWN, UNAVAILABLE) else None


def _collection_of(dir_path: str) -> str | None:
    """The `<domain>/<collection>` prefix of a DECLARED directory path."""
    parts = [p for p in str(dir_path).split("/") if p]
    return "/".join(parts[:2]) if len(parts) >= 2 else None


# ------------------------------------------------------ per-variable facts
def derive_producer(v: dict, apps: list[dict], bindings: list[dict], prov: ProvenanceReader) -> dict:
    # 1. BOUND: a binding whose output IS this variable's bytes and column
    bound = sorted({(b.get("dataset_id"), b.get("commit"), b.get("file"), b.get("symbol"))
                    for b in bindings
                    for a in apps
                    if b.get("dataset_sha256") == a["physical_sha256"]
                    and b.get("output_column") == v["concept_name"]}, key=str)
    if len(bound) == 1:
        ds, commit, f, sym = bound[0]
        return {"state": "BOUND", "value": f"{f}:{sym}@{commit}",
                "evidence": [{"source": CENSUS_ARTIFACTS["binding_manifest"], "field": "bindings"}]}
    lin = v.get("lineage") or {}
    pfiles = list(lin.get("provenance_files") or [])
    # 2. DECLARED: one distinct declared source in census lineage
    decl = sorted({s for s in (lin.get("source_declarations") or []) if _declared_source(s)})
    if len(decl) == 1 and pfiles:
        return {"state": "DECLARED_IN_CENSUS_LINEAGE", "value": decl[0],
                "evidence": [{"source": "census.variables[].lineage.source_declarations"}]
                + [{"source": p, "sha256": prov.digest(p)} for p in sorted(pfiles)]}
    # 3. DECLARED through the provenance file's own declared source_dir
    if len(pfiles) == 1 and not decl:
        d = prov.doc(pfiles[0])
        sd = (d or {}).get("source_dir")
        if isinstance(sd, str) and sd.strip():
            up = f"{sd.strip('/')}/provenance.json"
            ud = prov.doc(up)
            src = _declared_source((ud or {}).get("source"))
            if src:
                return {"state": "DECLARED_VIA_PROVENANCE_SOURCE_DIR", "value": src,
                        "evidence": [{"source": pfiles[0], "sha256": prov.digest(pfiles[0]), "field": "source_dir"},
                                     {"source": up, "sha256": prov.digest(up), "field": "source"}]}
    reason = ("census declared ambiguous provenance candidates and chose none"
              if lin.get("ambiguous_provenance_candidates") else
              "no binding, no declared source, no declared source_dir")
    return {"state": UNRESOLVED, "value": UNRESOLVED, "evidence": [], "reason": reason}


def derive_family(v: dict, prov: ProvenanceReader) -> dict:
    lin = v.get("lineage") or {}
    dirs = [d for d in (lin.get("upstream_source_dirs") or []) if isinstance(d, str)]
    two = sorted({d.strip("/") for d in dirs if len([p for p in d.split("/") if p]) == 2})
    if len(two) == 1:
        return {"state": "DECLARED_IN_CENSUS_UPSTREAM_SOURCE_DIRS", "value": two[0],
                "evidence": [{"source": "census.variables[].lineage.upstream_source_dirs"}]}
    pfiles = list(lin.get("provenance_files") or [])
    if len(pfiles) == 1 and not dirs:
        d = prov.doc(pfiles[0])
        sd = (d or {}).get("source_dir")
        fam = _collection_of(sd) if isinstance(sd, str) else None
        if fam:
            return {"state": "DECLARED_VIA_PROVENANCE_SOURCE_DIR", "value": fam,
                    "evidence": [{"source": pfiles[0], "sha256": prov.digest(pfiles[0]), "field": "source_dir"}]}
    return {"state": UNRESOLVED, "value": UNRESOLVED, "evidence": []}


def derive_lineage_verifiable(producer: dict, v: dict, prov: ProvenanceReader) -> dict:
    """True only when the evidence to verify exists: a binding with digests,
    or every provenance file in the declared chain exists (and is pinned
    here) and the terminal one declares hex64 digests of its files. The
    declared upstream digests are NOT re-hashed by this tool."""
    if producer["state"] == "BOUND":
        return {"value": True, "basis": "BINDING_WITH_DIGESTS"}
    if producer["state"] == UNRESOLVED:
        return {"value": False, "basis": "PRODUCER_UNRESOLVED"}
    chain = [e["source"] for e in producer["evidence"] if e.get("sha256")]
    if not chain or any(prov.digest(p) == UNAVAILABLE for p in chain):
        return {"value": False, "basis": "PROVENANCE_FILE_ABSENT"}
    if not _declared_file_digests(prov.doc(chain[-1])):
        return {"value": False, "basis": "PROVENANCE_DECLARES_NO_FILE_DIGESTS"}
    return {"value": True,
            "basis": "DECLARED_PROVENANCE_WITH_FILE_DIGESTS_NOT_REHASHED",
            "provenance_chain": [{"source": p, "sha256": prov.digest(p)} for p in chain]}


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, x in node.items():
            yield str(k)
            yield from _strings(x)
    elif isinstance(node, list):
        for x in node:
            yield from _strings(x)


def consumer_index(appearances: list[dict], demand: dict, binding: dict) -> dict:
    """appearance_id -> sorted consumer labels. A consumer is recorded only
    when a demand universe or the binding manifest names the appearance's
    exact physical_sha256 or relative_path."""
    out: dict[str, set] = defaultdict(set)
    for key in DEMAND_KEYS:
        strings = set(_strings(demand.get(key, {})))
        for a in appearances:
            if a["physical_sha256"] in strings or a["relative_path"] in strings:
                out[a["appearance_id"]].add(f"DEMAND:{key}")
    succ = binding.get("successor") or {}
    rec = succ.get("input_recorded_as") or {}
    for a in appearances:
        if a["physical_sha256"] in (succ.get("input_sha256"), rec.get("sha256")) \
                and HEX64.fullmatch(a["physical_sha256"]):
            out[a["appearance_id"]].add("BOUND_PRODUCER_INPUT")
    return {k: sorted(x) for k, x in out.items()}


def cross_references(appearances: list[dict], doc) -> int:
    strings = set(_strings(doc))
    return sum(1 for a in appearances
               if a["physical_sha256"] in strings or a["relative_path"] in strings)


def sealed_periods_for(appearance: dict, docs: list) -> object:
    """Declared sealed periods for an appearance, or UNKNOWN."""
    found = []
    for d in [appearance] + docs:
        if isinstance(d, dict):
            for key in SEALED_SEARCH["declaration_keys"]:
                x = d.get(key)
                if isinstance(x, list):
                    found.extend(p for p in x if isinstance(p, dict)
                                 and p.get("relative_path") in (None, appearance["relative_path"]))
    return found if found else UNKNOWN


# ---------------------------------------------------------------- the queue
def derive(census: dict, binding: dict, lineage: dict, dag: dict, demand: dict,
           prov: ProvenanceReader) -> dict:
    apps = {a["appearance_id"]: a for a in census["appearances"]}
    consumers = consumer_index(census["appearances"], demand, binding)
    extra_docs = [demand, binding, lineage, dag]
    sealed = {aid: sealed_periods_for(a, extra_docs) for aid, a in apps.items()}
    variables, items = [], []
    for v in sorted(census["variables"], key=lambda x: x["variable_id"]):
        vapps = [apps[i] for i in sorted(v["appearances"]) if i in apps]
        if len(vapps) != len(v["appearances"]):
            raise QueueRefusal(f"variable {v['variable_id']} names an appearance the census lacks")
        producer = derive_producer(v, vapps, binding.get("bindings") or [], prov)
        family = derive_family(v, prov)
        lv = derive_lineage_verifiable(producer, v, prov)
        present = bool(vapps) and all(
            a["presence"] == "PRESENT" and a["digest_state"] in DIGESTED_STATES
            and isinstance(a["physical_sha256"], str) and HEX64.fullmatch(a["physical_sha256"])
            for a in vapps)
        tier = 1 if (present and lv["value"]) else 2 if present else 3
        vcons = sorted({c for a in vapps for c in consumers.get(a["appearance_id"], [])})
        variables.append({
            "variable_id": v["variable_id"],
            "tier": tier,
            "producer": producer,
            "feature_family": family,
            "frequencies": sorted({a["frequency"] for a in vapps}),
            "consumer": vcons or [NONE],
            "bytes_present": present,
            "lineage_verifiable": lv,
            "total_bytes": sum(a["size_bytes"] or 0 for a in vapps),
            "appearances": [a["appearance_id"] for a in vapps],
            "sealed_periods": {a["appearance_id"]: sealed[a["appearance_id"]] for a in vapps},
            "license_state": LICENSE_STATE,
        })
        for a in vapps:
            cons = "+".join(consumers.get(a["appearance_id"], [])) or NONE
            items.append({
                "variable_id": v["variable_id"],
                "appearance_id": a["appearance_id"],
                "tier": tier,
                "stratum": (producer["value"], a["frequency"], family["value"], cons),
            })
    return {"variables": variables, "items": items}


def order_queue(items: list[dict]) -> list[dict]:
    """Tier first; inside a tier a round robin across sorted strata, each
    stratum's items sorted by (variable_id, appearance_id). No score."""
    out = []
    for tier in sorted({i["tier"] for i in items}):
        by = defaultdict(list)
        for i in items:
            if i["tier"] == tier:
                by[i["stratum"]].append(i)
        lanes = [sorted(by[s], key=lambda x: (x["variable_id"], x["appearance_id"])) for s in sorted(by)]
        depth = max(len(l) for l in lanes)
        for k in range(depth):
            for lane in lanes:
                if k < len(lane):
                    out.append(lane[k])
    return out


def select_first_batch(queue: list[dict], apps: dict, budget: int) -> dict:
    """Walk the queue in order. An item is taken when its appearance is
    already in the batch (zero extra bytes) or when its appearance's bytes
    fit in what is left of the budget and the appearance admits a 60/20/20
    chronological partition (declared_rows >= 3). Otherwise it is skipped
    and the walk continues (first fit). Bytes counted are unique."""
    chosen_apps: list[str] = []
    in_batch: set[str] = set()
    used = 0
    taken, skipped_budget, skipped_rows, skipped_absent = [], 0, set(), set()
    for pos, it in enumerate(queue):
        a = apps[it["appearance_id"]]
        if a["appearance_id"] not in in_batch:
            if not (a["presence"] == "PRESENT" and a["digest_state"] in DIGESTED_STATES
                    and isinstance(a["physical_sha256"], str) and HEX64.fullmatch(a["physical_sha256"])):
                skipped_absent.add(a["appearance_id"])
                continue
            rows = a.get("declared_rows")
            if type(rows) is not int or rows < 3:
                skipped_rows.add(a["appearance_id"])
                continue
            size = a["size_bytes"] or 0
            if used + size > budget:
                skipped_budget += 1
                continue
            used += size
            in_batch.add(a["appearance_id"])
            chosen_apps.append(a["appearance_id"])
        taken.append(pos)
    return {"positions": taken, "appearances": chosen_apps, "bytes": used,
            "items_skipped_for_budget": skipped_budget,
            "appearances_skipped_unpartitionable": sorted(skipped_rows),
            "appearances_skipped_bytes_not_present": sorted(skipped_absent)}


# ------------------------------------------------------------- contracts
def build_contract(dfc, census_sha: str, app: dict, cvars: list[dict], qvars: dict,
                   prov: ProvenanceReader) -> dict:
    ds = f"financial_data.census_appearance.{app['appearance_id']}"
    freq = FREQUENCY_SECONDS.get(app["frequency"], UNKNOWN)
    producers = sorted({qvars[v["variable_id"]]["producer"]["value"] for v in cvars})
    provider = producers[0] if len(producers) == 1 and producers[0] != UNRESOLVED else UNKNOWN
    by_name = {v["concept_name"]: v for v in cvars}
    variables = []
    for name in app["declared_columns"]:
        cv = by_name[name]
        q = qvars[cv["variable_id"]]
        sem_src = cv.get("semantics_source")
        declared_sem = cv.get("semantics") not in (None, UNKNOWN, UNAVAILABLE) and \
            isinstance(sem_src, str) and sem_src.endswith(".md")
        sem = {"type": UNKNOWN,
               "description": cv["semantics"] if declared_sem else UNKNOWN,
               "evidence": [{"source": sem_src, "sha256": prov.digest(sem_src)}] if declared_sem else []}
        prod = q["producer"]
        variables.append(dfc.variable(
            ds, name, semantics=sem,
            producer={"kind": UNKNOWN,
                      "reference": UNKNOWN if prod["state"] == UNRESOLVED else f"{prod['state']}:{prod['value']}"},
            frequency_nominal_seconds=freq, license_state=LICENSE_STATE,
            original_fields={"census_variable_id": cv["variable_id"]}))
    sealed = qvars[cvars[0]["variable_id"]]["sealed_periods"][app["appearance_id"]] if cvars else UNKNOWN
    doc = {
        "schema": dfc.DATASET_SCHEMA, "dataset_id": ds, "version": f"census_sha256:{census_sha}",
        "bank": "FINANCIAL",
        "files": [{"name": app["relative_path"], "bytes": app["size_bytes"],
                   "sha256": app["physical_sha256"], "role": "DATA"}],
        "content_sha256": "",
        "source": {"provider": provider, "official_url": UNKNOWN, "citation": UNKNOWN,
                   "doi": UNKNOWN, "upstream_owner": UNKNOWN},
        "license": {"state": LICENSE_STATE, "id": UNKNOWN, "url": UNKNOWN, "text_sha256": UNKNOWN,
                    "attribution_required": UNKNOWN, "redistribution": UNKNOWN,
                    "derivatives": UNKNOWN, "evidence": []},
        "time": {"frequency_nominal_seconds": freq, "timezone": UNKNOWN,
                 "timestamp_meaning": UNKNOWN, "range_start": str(app["period_start"]),
                 "range_end": str(app["period_end"]), "availability_rule": UNKNOWN,
                 "availability_delay_seconds": UNKNOWN},
        "panel": {"aligned_common_grid": False, "n_series": 1, "alignment_rule": UNKNOWN},
        "partitions": {"scheme": "chronological_contiguous_row_blocks_on_census_declared_rows",
                       "fractions": {"train": 0.6, "calibration": 0.2, "confirmation": 0.2},
                       "boundaries": dfc.chronological_partitions(app["declared_rows"]),
                       "sealed_periods_excluded": sealed if isinstance(sealed, list) else [],
                       "frozen_before_profile": True},
        "dependence": [],
        "variables": variables,
        "original_fields": {"census_appearance": app, "census_variables": cvars},
        "contract_sha256": "",
    }
    return dfc.seal(doc)


# ------------------------------------------------------------------ build
def _count(xs) -> dict:
    return dict(sorted(Counter(xs).items()))


def build(root: Path, census_rel: str, dfc, contract_module_sha: str,
          derived_at: str = DEFAULT_DERIVED_AT, budget: int = DEFAULT_BUDGET_BYTES,
          contracts_rel: str = DEFAULT_CONTRACTS_OUT) -> tuple[dict, dict]:
    raw = (root / census_rel).read_bytes()
    census = json.loads(raw)
    if census_self_sha(census) != census.get("census_sha256"):
        raise QueueRefusal("the census self digest does not re-derive")
    if census["census_sha256"] not in Path(census_rel).name:
        raise QueueRefusal("the census file name does not carry its content digest")
    docs, inputs = {}, {"census": {"relative_path": census_rel, "file_sha256": sha_bytes(raw),
                                   "census_sha256": census["census_sha256"],
                                   "census_self_digest_rederived": True,
                                   "variables": len(census["variables"]),
                                   "appearances": len(census["appearances"])}}
    for key, rel in CENSUS_ARTIFACTS.items():
        b = read_metadata(root, rel)
        if b is None:
            raise QueueRefusal(f"declared input {rel} is absent")
        docs[key] = json.loads(b)
        inputs[key] = {"relative_path": rel, "file_sha256": sha_bytes(b)}
    inputs["contract_module"] = {"name": CONTRACT_MODULE_NAME, "file_sha256": contract_module_sha}

    prov = ProvenanceReader(root)
    d = derive(census, docs["binding_manifest"], docs["feature_lineage"], docs["feature_dag"],
               docs["demand_universes"], prov)
    variables, items = d["variables"], d["items"]
    apps = {a["appearance_id"]: a for a in census["appearances"]}
    queue = order_queue(items)
    qvars = {v["variable_id"]: v for v in variables}

    strata = sorted({i["stratum"] for i in items})
    s_index = {s: n for n, s in enumerate(strata)}
    s_vars, s_items, s_apps = defaultdict(set), Counter(), defaultdict(set)
    for i in items:
        s_vars[i["stratum"]].add(i["variable_id"])
        s_items[i["stratum"]] += 1
        s_apps[i["stratum"]].add(i["appearance_id"])

    batch = select_first_batch(queue, apps, budget)
    b_items = [queue[p] for p in batch["positions"]]
    b_strata = {i["stratum"] for i in b_items}
    b_vars = {i["variable_id"] for i in b_items}
    taken = set(batch["positions"])
    sealed_declared = {aid for v in variables for aid, s in v["sealed_periods"].items()
                       if isinstance(s, list)}

    vars_of_app = defaultdict(list)
    for v in census["variables"]:
        for aid in v["appearances"]:
            vars_of_app[aid].append(v)
    contracts = []
    for aid in sorted(batch["appearances"]):
        cvars = sorted(vars_of_app[aid], key=lambda x: x["variable_id"])
        contracts.append(build_contract(dfc, census["census_sha256"], apps[aid], cvars, qvars, prov))
    contracts_doc = {
        "schema": CONTRACTS_SCHEMA, "order_item": ORDER_ITEM, "derived_at": derived_at,
        "census_sha256": census["census_sha256"],
        "contract_module": inputs["contract_module"],
        "bank": "FINANCIAL", "license_state": LICENSE_STATE,
        "contracts_count": len(contracts),
        "contracts": contracts,
    }
    contracts_doc["contracts_file_sha256"] = sha_obj(contracts_doc)

    inputs["provenance_and_dictionary_files"] = dict(sorted(prov.pinned.items()))
    inputs["cross_references_to_census_appearances"] = {
        k: cross_references(census["appearances"], docs[k])
        for k in CENSUS_ARTIFACTS}

    doc = {
        "schema": SCHEMA,
        "order_item": ORDER_ITEM,
        "derived_at": derived_at,
        "grants_nothing": "this queue orders what to profile next; it grants no eligibility, "
                          "no availability and no license to any variable",
        "inputs": inputs,
        "rules": {
            "metadata_only": "derived from the census, manifests, lineage, demand universes, "
                             "provenance and dictionary files and census-recorded file sizes; "
                             "no parquet or csv value is read; no target, score or model",
            "queue_unit": "one (variable, appearance) item; a variable at one frequency",
            "producer": "BOUND when a binding's dataset_sha256 equals the appearance digest and its "
                        "output_column equals the variable; else DECLARED_IN_CENSUS_LINEAGE when census "
                        "lineage carries exactly one declared source and a provenance file; else "
                        "DECLARED_VIA_PROVENANCE_SOURCE_DIR when the variable's single provenance file "
                        "declares source_dir and that directory's provenance.json declares a source; "
                        "else UNRESOLVED. Never from a column or entity name.",
            "feature_family": "the single two-component directory (<domain>/<collection>) in census "
                              "lineage.upstream_source_dirs; else, for a variable without upstream dirs, "
                              "the first two components of the source_dir its single provenance file "
                              "declares; else UNRESOLVED",
            "consumer": "a demand universe (ACTIVE_EXECUTION_DEMAND, CONFIRMATORY_RESERVED, "
                        "RESEARCH_BANK_CANDIDATES) or the binding manifest's recorded producer input "
                        "that names the appearance's exact physical_sha256 or relative_path; else NONE",
            "bytes_present": "every appearance PRESENT with a hex64 digest in a digested state",
            "lineage_verifiable": "BOUND with digests, or every provenance file of the declared chain "
                                  "exists (pinned here) and the terminal one declares hex64 file "
                                  "digests; declared upstream digests are not re-hashed by this tool",
            "tiers": {"1": "bytes present AND lineage verifiable", "2": "bytes present, lineage not "
                      "verifiable", "3": "the rest"},
            "order": "tier ascending; inside a tier round robin across strata sorted by "
                     "(producer, frequency, feature_family, consumer), items inside a stratum sorted "
                     "by (variable_id, appearance_id)",
            "stratum": "producer x frequency x feature_family x consumer",
            "first_batch": "walk the queue in order, first fit: take an item when its appearance is "
                           "already in the batch, or when the appearance is PRESENT with a hex64 "
                           "digest, admits a 60/20/20 "
                           "chronological partition (declared_rows >= 3) and its size_bytes fit in "
                           "the remaining budget of unique appearance bytes; otherwise skip it",
            "sealed_periods": SEALED_SEARCH,
            "license": f"every variable is {LICENSE_STATE}: no license document with a sha256 is known "
                       "for these bytes and the repository README grants no reuse; not public, "
                       "not eligible",
        },
        "license": {"state": LICENSE_STATE, "evidence": []},
        "counts": {
            "variables": len(variables),
            "items": len(items),
            "variables_by_tier": _count(str(v["tier"]) for v in variables),
            "items_by_tier": _count(str(i["tier"]) for i in items),
            "strata": len(strata),
            "producer_state": _count(v["producer"]["state"] for v in variables),
            "producer_value": _count(v["producer"]["value"] for v in variables),
            "producer_resolved": sum(v["producer"]["state"] != UNRESOLVED for v in variables),
            "producer_unresolved": sum(v["producer"]["state"] == UNRESOLVED for v in variables),
            "feature_family_state": _count(v["feature_family"]["state"] for v in variables),
            "feature_family_value": _count(v["feature_family"]["value"] for v in variables),
            "feature_family_resolved": sum(v["feature_family"]["state"] != UNRESOLVED for v in variables),
            "feature_family_unresolved": sum(v["feature_family"]["state"] == UNRESOLVED for v in variables),
            "lineage_verifiable_basis": _count(v["lineage_verifiable"]["basis"] for v in variables),
            "consumer_variables": _count("+".join(v["consumer"]) for v in variables),
            "consumer_items": _count(i["stratum"][3] for i in items),
            "bytes_present_variables": sum(v["bytes_present"] for v in variables),
            "sealed_periods_declared_appearances": len(sealed_declared),
            "lake_bytes_unique_appearances": sum(a["size_bytes"] or 0 for a in apps.values()),
            "license_state": _count(v["license_state"] for v in variables),
        },
        "strata": [{"index": s_index[s], "producer": s[0], "frequency": s[1], "feature_family": s[2],
                    "consumer": s[3], "variables": len(s_vars[s]), "items": s_items[s],
                    "unique_appearance_bytes": sum(apps[a]["size_bytes"] or 0 for a in s_apps[s])}
                   for s in strata],
        "first_batch": {
            "budget_bytes": budget,
            "budget_statement": f"at most {budget} bytes ({budget / (1 << 30):.2f} GiB) of unique "
                                "appearance bytes, against a lake of "
                                f"{sum(a['size_bytes'] or 0 for a in apps.values())} bytes",
            "bytes": batch["bytes"],
            "items": len(b_items),
            "variables": len(b_vars),
            "variables_with_every_appearance_in_batch": sum(
                1 for v in b_vars if set(qvars[v]["appearances"]) <= set(batch["appearances"])),
            "appearances": len(batch["appearances"]),
            "appearance_ids": sorted(batch["appearances"]),
            "items_by_tier": _count(str(i["tier"]) for i in b_items),
            "items_skipped_for_budget": batch["items_skipped_for_budget"],
            "appearances_skipped_unpartitionable": batch["appearances_skipped_unpartitionable"],
            "appearances_skipped_bytes_not_present": batch["appearances_skipped_bytes_not_present"],
            "strata_covered": len(b_strata),
            "strata_uncovered": len(strata) - len(b_strata),
            "strata_uncovered_list": [{"index": s_index[s], "producer": s[0], "frequency": s[1],
                                       "feature_family": s[2], "consumer": s[3]}
                                      for s in strata if s not in b_strata],
            "last_queue_position_taken": batch["positions"][-1] if batch["positions"] else None,
        },
        "first_batch_contracts": {
            "relative_path": contracts_rel,
            "contracts_file_sha256": contracts_doc["contracts_file_sha256"],
            "contracts_sealed": len(contracts),
            "contract_rule": "one common dataset contract per first-batch appearance, built with "
                             f"{CONTRACT_MODULE_NAME} and passed through its seal",
        },
        "variables": variables,
        "queue_columns": ["position", "variable_id", "appearance_id", "tier", "stratum_index",
                          "in_first_batch"],
        "queue": [[p, i["variable_id"], i["appearance_id"], i["tier"], s_index[i["stratum"]],
                   p in taken] for p, i in enumerate(queue)],
    }
    doc["queue_sha256"] = sha_obj(doc)
    return doc, contracts_doc


def write_once(path: Path, doc: dict) -> None:
    if path.exists():
        raise QueueRefusal(f"{path.name} already exists; the artifact is write-once")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False) + "\n")


def main(argv=None) -> int:
    here = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(here))
    ap.add_argument("--census", default=DEFAULT_CENSUS)
    ap.add_argument("--contract-module", default=str(here.parent / CONTRACT_MODULE_NAME))
    ap.add_argument("--derived-at", default=DEFAULT_DERIVED_AT)
    ap.add_argument("--budget-bytes", type=int, default=DEFAULT_BUDGET_BYTES)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--contracts-out", default=DEFAULT_CONTRACTS_OUT)
    a = ap.parse_args(argv)
    root = Path(a.root)
    for rel in (a.out, a.contracts_out):
        if (root / rel).exists():
            print(f"REFUSED: {rel} already exists; write-once", file=sys.stderr)
            return 2
    mpath = Path(a.contract_module)
    dfc = load_contract_module(mpath)
    doc, contracts = build(root, a.census, dfc, sha_bytes(mpath.read_bytes()),
                           a.derived_at, a.budget_bytes, a.contracts_out)
    write_once(root / a.contracts_out, contracts)
    write_once(root / a.out, doc)
    c, fb = doc["counts"], doc["first_batch"]
    print(json.dumps({"queue_sha256": doc["queue_sha256"], "variables_by_tier": c["variables_by_tier"],
                      "strata": c["strata"], "producer_resolved": c["producer_resolved"],
                      "producer_unresolved": c["producer_unresolved"],
                      "feature_family_resolved": c["feature_family_resolved"],
                      "feature_family_unresolved": c["feature_family_unresolved"],
                      "consumer_variables": c["consumer_variables"],
                      "first_batch": {k: fb[k] for k in ("variables", "items", "appearances", "bytes",
                                                         "strata_covered", "strata_uncovered")},
                      "contracts_sealed": doc["first_batch_contracts"]["contracts_sealed"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
