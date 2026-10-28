"""Incremental canonical census of the financial-data lake.

Two grains are kept strictly separate, because conflating them is
the recurring error this census exists to prevent:

  * a **physical appearance** is one materialized slice — a file
    at a period, a source, a frequency, a declared schema, its
    bytes and (when policy allows) its digest;
  * a **conceptual variable** is one stable logical id with
    semantics, unit, role, availability and lineage, carrying the
    LIST of appearances in which it materializes.

Consequences enforced here, not merely documented:

  * an appearance is never counted as a variable;
  * a physical path is never a logical identity — ids derive from
    logical coordinates, and the path is an attribute;
  * equivalences and conflicts across names are DECLARED, never
    resolved by string similarity;
  * `event_time` and `available_time` are distinct fields and an
    undeclared availability is `UNAVAILABLE`, never inferred;
  * license, unit, provenance and availability gaps are listed
    exactly, per entity, never summarized away;
  * a delta against the previous census emits ADDED, UNCHANGED,
    CHANGED and MISSING;
  * the value sweep has two declared depths and a sampled profile
    is NEVER presented as a complete physical census.

The census joins what the repository already declares
(`features/MANIFEST.json`, 753 `provenance.json` files, 954
`data_dictionary.md` files, the availability contract schema) and
reads bytes only under the declared digest policy, so an
incremental run does not re-read the lake.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path

SCHEMA = "financial_data.incremental_census.v1"
_ID_SEPARATOR = "|"

ROOT = Path(__file__).resolve().parents[2]

# Values a source may declare for a field we refuse to invent.
UNKNOWN = "UNKNOWN"
UNAVAILABLE = "UNAVAILABLE"

DIGEST_POLICIES = ("selected", "all", "none")
PROFILE_FULL = "FULL_PROFILE_PHYSICALLY_VERIFIED"
PROFILE_SAMPLED = "SAMPLED_VALUE_PROFILE"
PROFILE_DECLARED = "DECLARED_SCHEMA_ONLY"


class CensusRefusal(SystemExit):
    def __init__(self, msg: str) -> None:
        super().__init__(f"REFUSED: {msg}")


# --------------------------------------------------------------
# identity
# --------------------------------------------------------------

def _sha(*parts: str) -> str:
    # explicit separator: identity must not depend on a
    # coordinate accidentally containing the joiner
    return hashlib.sha256(
        _ID_SEPARATOR.join(parts).encode()).hexdigest()


def appearance_id(source_class: str, entity: str, frequency: str,
                  period_start: str) -> str:
    """Logical identity of ONE materialized slice.

    Derived from logical coordinates only. The path is an
    attribute of the appearance, never its identity: moving a file
    must not create a new appearance, and two different files can
    never collapse into one because their paths happen to match.
    """
    return "app_" + _sha(source_class, entity, frequency,
                         period_start)[:24]


def variable_id(source_class: str, entity: str,
                concept: str) -> str:
    """Logical identity of ONE conceptual variable.

    Frequency and period are deliberately ABSENT: the same
    concept measured on the same entity at several resolutions or
    over several temporal slices is ONE variable with several
    appearances. Different entities keep different ids — an
    equivalence across entities is declared, never assumed.
    """
    return "var_" + _sha(source_class, entity, concept)[:24]


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------
# declared-metadata joins (no inference)
# --------------------------------------------------------------

def load_manifest(root: Path) -> dict:
    p = root / "features" / "MANIFEST.json"
    if not p.is_file():
        raise CensusRefusal(
            "features/MANIFEST.json is absent — the census joins "
            "declarations, it never guesses the lake")
    return json.loads(p.read_text())


def index_provenance(root: Path) -> dict:
    """path -> provenance facts, from the repository's own
    provenance.json files. Only what they declare is carried."""
    out: dict[str, dict] = {}
    for p in sorted(root.rglob("provenance.json")):
        if ".git" in p.parts or "_templates" in p.parts:
            continue
        try:
            doc = json.loads(p.read_text())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        rel_dir = str(p.parent.relative_to(root))
        facts = {
            "provenance_file": str(p.relative_to(root)),
            "source": doc.get("source", UNKNOWN),
            "description": doc.get("description", UNKNOWN),
            "acquired_at": doc.get("acquired_at", UNKNOWN),
            "license": doc.get("license", UNKNOWN),
            "url_or_doi": doc.get("url", doc.get("doi", UNKNOWN)),
        }
        out[rel_dir] = facts
        for f in doc.get("files", []) or []:
            fp = f.get("path")
            if fp:
                out[fp] = {**facts,
                           "declared_sha256": f.get("sha256",
                                                    UNKNOWN)}
    return out


_DICT_ROW = re.compile(r"^\s*\|\s*`?([A-Za-z0-9_.\- ]+?)`?\s*\|")
_DICT_BULLET = re.compile(
    r"^\s*[-*]\s+(`[^`]+`(?:\s*,\s*`[^`]+`)*)\s*:\s*(.+)$")
_DICT_NAME = re.compile(r"`([^`]+)`")
# Many dictionaries in this lake are autogenerated coverage stubs
# that SAY they are not a semantic schema. Counting them as
# documentation would be the exact lie this census prevents.
_STUB_MARKERS = (
    "not as a semantic schema guarantee",
    "columns follow source naming",
    "follow the upstream source",
)


def parse_dictionary(text: str) -> tuple[dict, str]:
    """Return ({column: declared semantics}, kind).

    Two real formats live in this repository: markdown tables in
    the curated trees and bullet lists in the derived feature
    trees. A unit is never parsed out of prose — an invented unit
    is the failure this census forbids.
    """
    rows: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("|"):
            m = _DICT_ROW.match(line)
            if not m:
                continue
            name = m.group(1).strip()
            if not name or name.lower() in (
                    "column", "field", "name", "variable", "---"):
                continue
            rows.setdefault(name, line.strip())
            continue
        m = _DICT_BULLET.match(line)
        if m:
            meaning = m.group(2).strip()
            for name in _DICT_NAME.findall(m.group(1)):
                rows.setdefault(name.strip(), meaning)
    low = text.lower()
    if rows:
        kind = "SEMANTIC_DICTIONARY"
    elif any(mk in low for mk in _STUB_MARKERS):
        kind = "COVERAGE_STUB_SELF_DECLARED_NON_SEMANTIC"
    else:
        kind = "PRESENT_BUT_NO_PARSEABLE_COLUMN_DECLARATIONS"
    return rows, kind


def index_dictionaries(root: Path) -> tuple[dict, dict]:
    """(directory -> {column -> semantics}, directory -> kind)."""
    out: dict[str, dict] = {}
    kinds: dict[str, str] = {}
    for p in sorted(root.rglob("data_dictionary.md")):
        if ".git" in p.parts or "_templates" in p.parts:
            continue
        rows, kind = parse_dictionary(
            p.read_text(encoding="utf-8", errors="replace"))
        key = str(p.parent.relative_to(root))
        kinds[key] = kind
        if rows:
            out[key] = rows
    return out, kinds


def load_availability_contract(root: Path) -> dict:
    """The contract SCHEMA is declared repo-side; per-family
    INSTANCES are what a census must find. Absence is reported as
    a gap, never filled in."""
    schema_p = root / "configs" / "availability_contract.schema.json"
    doc_p = root / "features" / "AVAILABILITY_CONTRACT.md"
    schema = (json.loads(schema_p.read_text())
              if schema_p.is_file() else None)
    instances: dict[str, dict] = {}
    if schema is not None:
        required = set(schema.get("required", []))
        for p in sorted(root.rglob("*.json")):
            if ".git" in p.parts or p == schema_p:
                continue
            if "availability" not in p.name.lower():
                continue
            try:
                doc = json.loads(p.read_text())
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            for cand in (doc if isinstance(doc, list) else [doc]):
                if isinstance(cand, dict) and required <= set(cand):
                    instances[cand["feature_family"]] = {
                        **cand,
                        "contract_file": str(p.relative_to(root)),
                    }
    return {
        "schema_present": schema is not None,
        "schema_file": (str(schema_p.relative_to(root))
                        if schema is not None else UNAVAILABLE),
        "schema_required_fields": sorted(
            schema.get("required", [])) if schema else [],
        "document_present": doc_p.is_file(),
        "instances": instances,
    }


def map_families_to_entities(instances: dict,
                             entities: list[tuple]) -> dict:
    """Explicit, executable join from contract families to lake
    entities.

    The previous census indexed availability instances by
    `feature_family` and then looked them up by `entity`. The two
    namespaces coincide only by accident, so the first real
    contract could land and still leave every variable
    UNAVAILABLE. The join is now declared and reported:

      * an entity matches a family when its name IS the family,
        or when the family is a path prefix of the entity's own
        `__`-encoded source path;
      * a family that matches nothing is reported as UNMATCHED
        rather than silently dropped;
      * an entity that matches TWO families is reported as
        AMBIGUOUS and receives no availability, because a census
        does not choose between contracts.
    """
    by_family, by_entity = {}, {}
    for family in sorted(instances):
        fam_path = family.replace("/", "__").strip("__")
        matched = []
        for source_class, entity in entities:
            if entity == family or entity == fam_path:
                matched.append(entity)
            elif entity.startswith(fam_path + "__"):
                matched.append(entity)
        by_family[family] = sorted(set(matched))
        for e in matched:
            by_entity.setdefault(e, []).append(family)
    ambiguous = {e: sorted(f) for e, f in by_entity.items()
                 if len(f) > 1}
    resolved = {e: f[0] for e, f in by_entity.items()
                if len(f) == 1}
    return {
        "by_family": by_family,
        "entity_to_family": resolved,
        "ambiguous_entities": ambiguous,
        "unmatched_families": sorted(
            f for f, e in by_family.items() if not e),
        "rule": "entity == family, or the family is a "
                "__-separated path prefix of the entity",
    }


# --------------------------------------------------------------
# grain 1: physical appearances
# --------------------------------------------------------------

def _slice_records(manifest: dict):
    """Yield (source_class, entity, frequency, slice_doc)."""
    for entity, doc in sorted(
            manifest.get("trading_assets", {}).items()):
        for freq, s in sorted(
                (doc.get("timeframes") or {}).items()):
            yield "trading_asset", entity, freq, s
    for freq, fams in sorted(
            manifest.get("cross_source_features", {}).items()):
        for entity, s in sorted(fams.items()):
            yield "cross_source", entity, freq, s


def build_appearances(root: Path, manifest: dict, provenance: dict,
                      digest_policy: str,
                      selected: set[str] | None,
                      previous: dict | None) -> list[dict]:
    if digest_policy not in DIGEST_POLICIES:
        raise CensusRefusal(
            f"unknown digest policy {digest_policy!r}")
    prev_by_id = {a["appearance_id"]: a
                  for a in (previous or {}).get("appearances", [])}
    selected = selected or set()
    out = []
    for source_class, entity, freq, s in _slice_records(manifest):
        rel = s.get("path")
        start = s.get("start") or UNKNOWN
        aid = appearance_id(source_class, entity, freq, str(start))
        abs_p = root / rel if rel else None
        present = bool(abs_p and abs_p.is_file())
        size = abs_p.stat().st_size if present else None
        mtime_ns = abs_p.stat().st_mtime_ns if present else None
        prev = prev_by_id.get(aid)
        ctime_ns = abs_p.stat().st_ctime_ns if present else None
        # C6: an appearance is NEW when the previous census does
        # not carry it, or carried it without a verified digest.
        # A first census therefore digests EVERYTHING present:
        # stat() is not a digest and was never allowed to stand
        # in for one.
        prev_digest = (prev or {}).get("physical_sha256")
        prev_verified = (
            prev is not None
            and isinstance(prev_digest, str)
            and prev_digest != UNAVAILABLE)
        is_new = not prev_verified
        # Physical identity: size alone missed an equal-length
        # mutation. mtime_ns and ctime_ns are compared too, and
        # any difference forces a re-hash.
        changed_physically = bool(
            prev_verified and (
                prev.get("size_bytes") != size
                or prev.get("mtime_ns") != mtime_ns
                or prev.get("ctime_ns") != ctime_ns))
        explicitly_selected = (aid in selected or rel in selected)
        want_digest = (
            digest_policy != "none"
            and (digest_policy == "all" or is_new
                 or changed_physically or explicitly_selected))
        digest = (sha256_file(abs_p)
                  if (present and want_digest) else None)
        if digest is None and present and prev_verified:
            # unchanged by every physical signal: the previously
            # VERIFIED digest is carried forward, and labelled as
            # carried rather than freshly computed
            digest = prev_digest
            digest_state = "REUSED_FROM_PREVIOUS_VERIFIED_CENSUS"
        elif digest is not None:
            digest_state = "PHYSICALLY_DIGESTED"
        else:
            digest_state = "DECLARED_ONLY_NOT_DIGESTED"
        prov = (provenance.get(rel)
                or provenance.get(str(Path(rel).parent))
                if rel else None)
        out.append({
            "appearance_id": aid,
            "source_class": source_class,
            "entity": entity,
            "frequency": freq,
            "relative_path": rel,
            "manifest_status": s.get("status", UNKNOWN),
            "presence": "PRESENT" if present else "MISSING",
            "period_start": start,
            "period_end": s.get("end") or UNKNOWN,
            "declared_rows": s.get("rows"),
            "declared_columns": list(s.get("columns") or []),
            "size_bytes": size,
            "mtime_ns": mtime_ns,
            "ctime_ns": ctime_ns,
            "physical_sha256": digest or UNAVAILABLE,
            "digest_state": digest_state,
            "bytes_read_for_digest": (
                size if digest_state == "PHYSICALLY_DIGESTED"
                and size else 0),
            "provenance": prov or UNAVAILABLE,
            "profile_depth": PROFILE_DECLARED,
        })
    return out


# --------------------------------------------------------------
# grain 2: conceptual variables
# --------------------------------------------------------------

def upstream_lineage_dirs(root: Path, source_class: str,
                          entity: str) -> list[str]:
    """Candidate SOURCE directories for a derived entity.

    Cross-source feature families encode their source path in the
    entity name with a `__` separator — the repository's own
    convention, used here as a declared join, never as a guess.
    Every candidate that physically exists is returned; the caller
    declares an ambiguity rather than picking one.
    """
    if source_class != "cross_source":
        return []
    parts = entity.split("__")
    out = []
    for depth in range(len(parts), 0, -1):
        cand = Path(*parts[:depth])
        if (root / cand).is_dir():
            out.append(str(cand))
    return out


def _dictionary_lookup(dicts: dict, rel_path: str, concept: str,
                       extra_dirs: list[str] | None = None
                       ) -> tuple[str, str]:
    """Return (semantics, dictionary_file) or (UNKNOWN, ...).

    The slice's own directory and its ancestors are consulted
    first — a dictionary governs its own subtree. Declared
    upstream lineage directories are consulted afterwards, and
    only when they carry an actual column declaration.
    """
    keys: list[str] = []
    if rel_path:
        parts = Path(rel_path).parent
        while True:
            keys.append(str(parts))
            if str(parts) in (".", ""):
                break
            parts = parts.parent
    keys.extend(extra_dirs or [])
    for key in keys:
        rows = dicts.get(key)
        if rows and concept in rows:
            return rows[concept], key + "/data_dictionary.md"
    return UNKNOWN, UNAVAILABLE


def build_variables(root: Path, appearances: list[dict],
                    dicts: dict, provenance: dict,
                    availability: dict,
                    family_join: dict | None = None) -> list[dict]:
    by_var: dict[str, dict] = {}
    entity_to_family = (family_join or {}).get(
        "entity_to_family", {})
    lineage_cache: dict[tuple, list[str]] = {}
    for a in appearances:
        key = (a["source_class"], a["entity"])
        if key not in lineage_cache:
            lineage_cache[key] = upstream_lineage_dirs(
                root, a["source_class"], a["entity"])
        upstream = lineage_cache[key]
        for concept in a["declared_columns"]:
            vid = variable_id(a["source_class"], a["entity"],
                              concept)
            v = by_var.get(vid)
            if v is None:
                sem, dict_file = _dictionary_lookup(
                    dicts, a["relative_path"], concept,
                    upstream)
                # C7: resolved through the EXPLICIT family join,
                # never by hoping two namespaces coincide
                fam = entity_to_family.get(a["entity"])
                inst = (availability["instances"].get(fam)
                        if fam else None)
                v = by_var[vid] = {
                    "variable_id": vid,
                    "source_class": a["source_class"],
                    "entity": a["entity"],
                    "concept_name": concept,
                    "semantics": sem,
                    "semantics_source": dict_file,
                    "unit": UNKNOWN,
                    "physical_type": UNKNOWN,
                    "role": UNKNOWN,
                    "event_time": (
                        inst.get("observation_ts_col") if inst
                        else UNAVAILABLE),
                    "available_time": (
                        inst.get("available_from_ts_col") if inst
                        else UNAVAILABLE),
                    "availability_contract": (
                        inst.get("contract_file") if inst
                        else UNAVAILABLE),
                    "license": UNKNOWN,
                    "lineage": {
                        "provenance_files": [],
                        "source_declarations": [],
                        "upstream_source_dirs": list(upstream),
                        "upstream_join_rule":
                            ("entity name encodes the source "
                             "path by repository convention"
                             if upstream else UNAVAILABLE),
                    },
                    "appearances": [],
                    "frequencies": [],
                    "profile_depth": PROFILE_DECLARED,
                }
            v["appearances"].append(a["appearance_id"])
            if a["frequency"] not in v["frequencies"]:
                v["frequencies"].append(a["frequency"])
            prov = a["provenance"]
            if isinstance(prov, dict):
                pf = prov.get("provenance_file")
                if pf and pf not in v["lineage"][
                        "provenance_files"]:
                    v["lineage"]["provenance_files"].append(pf)
                src = prov.get("source")
                if src and src not in v["lineage"][
                        "source_declarations"]:
                    v["lineage"]["source_declarations"].append(src)
                lic = prov.get("license")
                if lic and lic != UNKNOWN:
                    v["license"] = lic
    # upstream provenance, joined only when the declared lineage
    # names exactly ONE provenance-bearing directory; several
    # candidates are an ambiguity the census refuses to resolve
    for v in by_var.values():
        if not v["lineage"]["provenance_files"]:
            cands = [d for d in v["lineage"]["upstream_source_dirs"]
                     if d in provenance]
            if len(cands) == 1:
                p = provenance[cands[0]]
                v["lineage"]["provenance_files"].append(
                    p["provenance_file"])
                if p.get("source"):
                    v["lineage"]["source_declarations"].append(
                        p["source"])
                if p.get("license", UNKNOWN) != UNKNOWN:
                    v["license"] = p["license"]
            elif len(cands) > 1:
                v["lineage"]["ambiguous_provenance_candidates"] = \
                    cands
    for v in by_var.values():
        v["appearances"].sort()
        v["frequencies"].sort()
        v["appearance_count"] = len(v["appearances"])
    return [by_var[k] for k in sorted(by_var)]


# --------------------------------------------------------------
# value sweep, level 2: sampled profile of SELECTED slices
# --------------------------------------------------------------

def value_profile_slice(path: Path, row_cap: int) -> dict:
    """Per-column value facts for ONE slice, read once.

    Every number here describes the rows actually read. A capped
    read is labelled as capped; it is never presented as the
    complete physical content of the slice.
    """
    import pandas as pd

    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
        capped = len(df) > row_cap
        if capped:
            df = df.head(row_cap)
    else:
        df = pd.read_csv(path, nrows=row_cap)
        capped = len(df) == row_cap
    cols = {}
    for c in df.columns:
        col = df[c]
        d = {
            "physical_type": str(col.dtype),
            "rows_read": int(len(col)),
            "nulls": int(col.isna().sum()),
            "distinct": int(col.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(col):
            finite = col[col.notna()]
            import numpy as np
            arr = finite.to_numpy()
            d["non_finite"] = int(
                np.size(arr) - np.count_nonzero(np.isfinite(arr))
            ) if arr.size else 0
            if arr.size:
                d["min"] = float(np.nanmin(arr))
                d["max"] = float(np.nanmax(arr))
                d["q05"] = float(np.nanquantile(arr, 0.05))
                d["q50"] = float(np.nanquantile(arr, 0.50))
                d["q95"] = float(np.nanquantile(arr, 0.95))
                d["constant"] = bool(d["min"] == d["max"])
        cols[str(c)] = d
    return {
        "profile_depth": PROFILE_SAMPLED,
        "rows_read": int(len(df)),
        "row_cap": row_cap,
        "read_was_capped": bool(capped),
        "completeness":
            "SAMPLED_HEAD_NOT_A_COMPLETE_PHYSICAL_CENSUS"
        if capped else "COMPLETE_SLICE_READ",
        "columns": cols,
    }


def select_for_value_profile(appearances: list[dict],
                             per_class: int) -> list[str]:
    """Deterministic, declared selection: the first `per_class`
    appearance ids of each source class in id order.

    Deterministic so a census is reproducible, and DECLARED so no
    reader can mistake it for a full sweep.
    """
    chosen: dict[str, list[str]] = defaultdict(list)
    for a in sorted(appearances, key=lambda x: x["appearance_id"]):
        if a["presence"] != "PRESENT":
            continue
        bucket = chosen[a["source_class"]]
        if len(bucket) < per_class:
            bucket.append(a["appearance_id"])
    return sorted(i for v in chosen.values() for i in v)


# --------------------------------------------------------------
# declared equivalences and conflicts (never resolved)
# --------------------------------------------------------------

def _normalize_concept(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def declare_equivalences(variables: list[dict]) -> dict:
    """Group variables whose concept names normalize identically.

    This is a DECLARATION for review, not a merge: every member
    keeps its own id, and a group whose members disagree on a
    declared attribute is additionally reported as a conflict.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for v in variables:
        groups[_normalize_concept(v["concept_name"])].append(v)
    classes, conflicts = [], []
    for norm, members in sorted(groups.items()):
        spellings = sorted({m["concept_name"] for m in members})
        entities = sorted({m["entity"] for m in members})
        classes.append({
            "equivalence_class_id": "eqc_" + _sha(norm)[:16],
            "normalized_concept": norm,
            "distinct_spellings": spellings,
            "member_variable_count": len(members),
            "entity_count": len(entities),
            "status": "DECLARED_CANDIDATE_EQUIVALENCE_"
                      "NOT_RESOLVED",
            "resolution_authority": "external review — a census "
                                    "never merges concepts by "
                                    "name similarity",
        })
        if len(spellings) > 1:
            conflicts.append({
                "conflict_id": "cft_" + _sha(norm, "spelling")[:16],
                "kind": "SPELLING_VARIANTS_UNDER_ONE_NORMAL_FORM",
                "normalized_concept": norm,
                "spellings": spellings,
                "entity_count": len(entities),
                "consequence": "these may or may not be the same "
                               "concept; the census refuses to "
                               "decide",
            })
        sem = {m["semantics"] for m in members
               if m["semantics"] != UNKNOWN}
        if len(sem) > 1:
            conflicts.append({
                "conflict_id": "cft_" + _sha(norm, "semantics")[:16],
                "kind": "DIVERGENT_DECLARED_SEMANTICS",
                "normalized_concept": norm,
                "distinct_declarations": len(sem),
                "consequence": "two dictionaries describe the "
                               "same normal form differently",
            })
    return {"equivalence_classes": classes, "conflicts": conflicts}


# --------------------------------------------------------------
# exact gaps
# --------------------------------------------------------------

def name_gaps(variables: list[dict],
              appearances: list[dict]) -> dict:
    def _gap(pred):
        hit = [v for v in variables if pred(v)]
        return {
            # BOTH grains are reported: an entity-level count
            # hides how much of the lake is actually undeclared,
            # and a variable-level count alone hides how many
            # owners must be asked.
            "variable_count": len(hit),
            "variable_fraction": (round(len(hit) / len(variables), 6)
                                  if variables else 0.0),
            "entity_count": len({v["entity"] for v in hit}),
            "entities": sorted({v["entity"] for v in hit}),
        }

    missing_slices = [a["appearance_id"] for a in appearances
                      if a["presence"] == "MISSING"]
    return {
        "license_gap": _gap(lambda v: v["license"] == UNKNOWN),
        "unit_gap": _gap(lambda v: v["unit"] == UNKNOWN),
        "provenance_gap": _gap(
            lambda v: not v["lineage"]["provenance_files"]),
        "availability_gap": _gap(
            lambda v: v["available_time"] == UNAVAILABLE),
        "role_gap": _gap(lambda v: v["role"] == UNKNOWN),
        "semantics_gap": _gap(
            lambda v: v["semantics"] == UNKNOWN),
        "ambiguous_provenance": _gap(
            lambda v: "ambiguous_provenance_candidates"
            in v["lineage"]),
        "physically_missing_appearances": missing_slices,
    }


# --------------------------------------------------------------
# delta against the previous census
# --------------------------------------------------------------

_APPEARANCE_IDENTITY_FIELDS = (
    "relative_path", "period_start", "period_end",
    "declared_rows", "declared_columns", "size_bytes",
    "physical_sha256", "presence",
)


def compute_delta(previous: dict | None, appearances: list[dict],
                  variables: list[dict]) -> dict:
    if previous is None:
        return {
            "previous_census": UNAVAILABLE,
            "basis": "FIRST_CENSUS_NO_PREDECESSOR",
            "appearances": {"ADDED": len(appearances),
                            "UNCHANGED": 0, "CHANGED": 0,
                            "MISSING": 0},
            "variables": {"ADDED": len(variables),
                          "UNCHANGED": 0, "CHANGED": 0,
                          "MISSING": 0},
            "changed_appearance_ids": [],
            "missing_appearance_ids": [],
            "changed_variable_ids": [],
            "missing_variable_ids": [],
        }
    prev_a = {a["appearance_id"]: a
              for a in previous.get("appearances", [])}
    prev_v = {v["variable_id"]: v
              for v in previous.get("variables", [])}
    now_a = {a["appearance_id"]: a for a in appearances}
    now_v = {v["variable_id"]: v for v in variables}

    def _cmp(now, prev, fields):
        added = sorted(set(now) - set(prev))
        gone = sorted(set(prev) - set(now))
        changed, unchanged = [], []
        for k in sorted(set(now) & set(prev)):
            if any(now[k].get(f) != prev[k].get(f)
                   for f in fields):
                changed.append(k)
            else:
                unchanged.append(k)
        return added, unchanged, changed, gone

    a_add, a_un, a_ch, a_gone = _cmp(
        now_a, prev_a, _APPEARANCE_IDENTITY_FIELDS)
    v_add, v_un, v_ch, v_gone = _cmp(
        now_v, prev_v, ("appearances", "semantics", "unit",
                        "role", "event_time", "available_time",
                        "license"))
    return {
        "previous_census": previous.get("census_sha256",
                                        UNKNOWN),
        "basis": "COMPARED_BY_LOGICAL_IDENTITY",
        "appearances": {"ADDED": len(a_add),
                        "UNCHANGED": len(a_un),
                        "CHANGED": len(a_ch),
                        "MISSING": len(a_gone)},
        "variables": {"ADDED": len(v_add),
                      "UNCHANGED": len(v_un),
                      "CHANGED": len(v_ch),
                      "MISSING": len(v_gone)},
        "changed_appearance_ids": a_ch,
        "missing_appearance_ids": a_gone,
        "changed_variable_ids": v_ch,
        "missing_variable_ids": v_gone,
    }


# --------------------------------------------------------------
# assembly
# --------------------------------------------------------------

def _self_sha(doc: dict, key: str = "census_sha256") -> str:
    body = {k: doc[k] for k in sorted(doc) if k != key}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True).encode()).hexdigest()


def build_census(root: Path, censused_at: str,
                 digest_policy: str = "selected",
                 selected: set[str] | None = None,
                 previous: dict | None = None,
                 external_full_profiles: list[dict] | None = None,
                 value_profile_per_class: int = 0,
                 value_profile_row_cap: int = 50000) -> dict:
    manifest = load_manifest(root)
    provenance = index_provenance(root)
    dicts, dict_kinds = index_dictionaries(root)
    availability = load_availability_contract(root)
    appearances = build_appearances(root, manifest, provenance,
                                    digest_policy, selected,
                                    previous)
    entities = sorted({(a["source_class"], a["entity"])
                       for a in appearances})
    family_join = map_families_to_entities(
        availability["instances"], entities)
    variables = build_variables(root, appearances, dicts,
                                provenance, availability,
                                family_join)
    # value sweep level 2: a declared, deterministic selection
    profiled = []
    if value_profile_per_class > 0:
        by_id = {a["appearance_id"]: a for a in appearances}
        for aid in select_for_value_profile(
                appearances, value_profile_per_class):
            a = by_id[aid]
            try:
                prof = value_profile_slice(
                    root / a["relative_path"],
                    value_profile_row_cap)
            except Exception as exc:            # noqa: BLE001
                prof = {"profile_depth": PROFILE_SAMPLED,
                        "error": f"{exc.__class__.__name__}",
                        "completeness": "PROFILE_FAILED"}
            a["profile_depth"] = PROFILE_SAMPLED
            profiled.append({"appearance_id": aid,
                             "relative_path": a["relative_path"],
                             "source_class": a["source_class"],
                             **prof})
    eq = declare_equivalences(variables)
    gaps = name_gaps(variables, appearances)
    delta = compute_delta(previous, appearances, variables)

    digested = sum(1 for a in appearances
                   if a["digest_state"] == "PHYSICALLY_DIGESTED")
    reused = sum(1 for a in appearances
                 if a["digest_state"] ==
                 "REUSED_FROM_PREVIOUS_VERIFIED_CENSUS")
    undigested = sum(1 for a in appearances
                     if a["digest_state"] ==
                     "DECLARED_ONLY_NOT_DIGESTED")
    bytes_read = sum(a.get("bytes_read_for_digest") or 0
                     for a in appearances)
    present = sum(1 for a in appearances
                  if a["presence"] == "PRESENT")
    declared_bytes = sum(a["size_bytes"] or 0 for a in appearances)
    occurrences = sum(len(a["declared_columns"])
                      for a in appearances)
    ext = external_full_profiles or []
    doc = {
        "schema": SCHEMA,
        "censused_at": censused_at,
        "manifest_generated_at": manifest.get("generated_at",
                                              UNKNOWN),
        "manifest_stage": manifest.get("stage", UNKNOWN),
        "policy": {
            "digest_policy": digest_policy,
            "selection_size": len(selected or ()),
            "value_sweep": {
                "level_1": "FULL profile of the ACTIVE "
                           "model-ready views, bound by digest "
                           "from the consuming repository",
                "level_2": "declared schema for every other "
                           "slice; a value profile is produced "
                           "only for explicitly selected slices",
                "honesty_rule": "no sampled profile is ever "
                                "presented as a complete "
                                "physical census",
            },
            "identity_rule": "ids derive from logical "
                             "coordinates; the physical path is "
                             "an attribute, never an identity",
        },
        "coverage": {
            "appearances_total": len(appearances),
            "appearances_present": present,
            "appearances_missing": len(appearances) - present,
            "appearances_physically_digested": digested,
            "appearances_digest_reused": reused,
            "appearances_not_digested": undigested,
            "bytes_read_for_digest": bytes_read,
            "digest_coverage_fraction": (
                round((digested + reused) / len(appearances), 6)
                if appearances else 0.0),
            "digest_coverage_note":
                "coverage counts appearances whose bytes have "
                "been hashed at least once and verified "
                "unchanged since; stat() is never counted as a "
                "digest",
            "declared_column_occurrences": occurrences,
            "conceptual_variables": len(variables),
            "entities": len(
                {(a["source_class"], a["entity"])
                 for a in appearances}),
            "declared_bytes_from_stat": declared_bytes,
            "externally_bound_full_profiles": len(ext),
            "sampled_value_profiles": len(profiled),
            "sampled_value_profile_fraction": (
                round(len(profiled) / len(appearances), 6)
                if appearances else 0.0),
        },
        "dictionary_coverage": {
            "files_indexed": len(dict_kinds),
            "by_kind": {k: sum(1 for v in dict_kinds.values()
                               if v == k)
                        for k in sorted(set(dict_kinds.values()))},
            "honesty_note":
                "a data dictionary that self-declares it is not "
                "a semantic schema is counted as a coverage "
                "stub, never as documented semantics",
        },
        "availability_contract": {
            "schema_present": availability["schema_present"],
            "schema_file": availability["schema_file"],
            "schema_required_fields":
                availability["schema_required_fields"],
            "document_present": availability["document_present"],
            "instances_found": len(availability["instances"]),
            "family_join": family_join,
            "consequence": (
                "every variable's available_time is UNAVAILABLE "
                "until a per-family contract instance exists"
                if not availability["instances"] else
                "contract instances joined by feature family"),
        },
        "value_profiles_sampled": profiled,
        "external_full_profiles": ext,
        "appearances": appearances,
        "variables": variables,
        "equivalence_classes": eq["equivalence_classes"],
        "conflicts": eq["conflicts"],
        "gaps": gaps,
        "delta": delta,
    }
    doc["census_sha256"] = _self_sha(doc)
    return doc


def summarize(census: dict) -> dict:
    """The small, Git-appropriate summary. The full census is
    content-addressed and may live outside the repository."""
    return {
        "schema": "financial_data.incremental_census_summary.v1",
        "censused_at": census["censused_at"],
        "census_sha256": census["census_sha256"],
        "coverage": census["coverage"],
        "availability_contract": census["availability_contract"],
        "delta": {k: v for k, v in census["delta"].items()
                  if not k.endswith("_ids")},
        "dictionary_coverage": census["dictionary_coverage"],
        "gap_counts": {
            k: ({"variables": v["variable_count"],
                 "entities": v["entity_count"]}
                if isinstance(v, dict) and "variable_count" in v
                else len(v))
            for k, v in census["gaps"].items()},
        "equivalence_class_count": len(
            census["equivalence_classes"]),
        "conflict_count": len(census["conflicts"]),
        "conflicts": census["conflicts"][:50],
    }


def receipt(census: dict, census_path: Path,
            summary_path: Path, root: Path,
            code_files: list[Path],
            invocation: dict | None = None) -> dict:
    """The receipt of ONE census, including how to produce it again.

    C42/C43 (order 2026-09-11): the receipt recorded the census digest
    and the manifest, and nothing about the ARGUMENTS. Rebuilding from
    the same lake at the same `censused_at` therefore produced a
    different content address, and the committed receipt named an
    artifact nobody could reproduce. A content-addressed name is only
    useful if the address can be arrived at twice.

    `invocation` carries the digest policy, the selections and the
    external profiles that were bound, each by digest. It is recorded
    as UNDECLARED when a caller does not supply it, so the absence is
    visible rather than assumed empty.
    """
    doc = {
        "schema": "financial_data.incremental_census_receipt.v1",
        "censused_at": census["censused_at"],
        "census_sha256": census["census_sha256"],
        "census_file_sha256": sha256_file(census_path),
        "census_file_bytes": census_path.stat().st_size,
        "census_logical_location": str(
            census_path.name if census_path.is_absolute()
            else census_path),
        "summary_file_sha256": sha256_file(summary_path),
        # keyed by repo-relative path when the code lives inside
        # the censused root, by bare name otherwise — the census
        # tool may legitimately run from a different checkout
        "code_identity": {
            (str(p.relative_to(root))
             if p.is_relative_to(root) else p.name):
            sha256_file(p) for p in sorted(code_files)},
        "inputs": {
            "manifest_sha256": sha256_file(
                root / "features" / "MANIFEST.json"),
            "manifest_generated_at":
                census["manifest_generated_at"],
        },
        "invocation": (invocation if invocation is not None
                       else "UNDECLARED — this receipt cannot "
                            "reproduce its own census"),
        "grants_nothing": "a census records what exists; it "
                          "confers no eligibility on any "
                          "variable or operator",
    }
    doc["receipt_sha256"] = _self_sha(doc, "receipt_sha256")
    return doc
