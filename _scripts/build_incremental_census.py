#!/usr/bin/env python3
"""Build the incremental canonical census of the financial-data
lake (two grains: physical appearance, conceptual variable).

The census is reproducible from a fixed `--censused-at`, joins the
repository's own declarations, and reads bytes only under the
declared digest policy. Large output is content-addressed and may
be written outside the repository; the small summary and the
receipt are what belongs in Git.

Examples
--------
  # first census: declarations + stat(), nothing re-read
  python _scripts/build_incremental_census.py \
      --censused-at 2026-09-10T00:00:00Z \
      --out-dir <state_root>/financial_data_census \
      --summary features/census/CENSUS_SUMMARY.v1.json \
      --receipt features/census/CENSUS_RECEIPT.v1.json

  # incremental: previous census drives ADDED/CHANGED/MISSING and
  # every physically changed slice is re-digested
  ... --previous <state_root>/financial_data_census/census-<sha>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_scripts" / "lib"))

import incremental_census as ic  # noqa: E402


def _load_external_full_profiles(paths: list[Path],
                                 roots: dict) -> list[dict]:
    """Bind FULL profiles produced by a consuming repository, and
    VERIFY them.

    The previous version copied an external inventory's own
    self-digest, row counts and dataset digests without checking
    one byte. A self-consistent summary is not a verified profile,
    so it is no longer labelled as one: this recomputes the
    inventory's self digest, requires the exact document schema,
    and re-hashes every dataset the inventory claims to have
    profiled. Anything it cannot verify is carried as
    DECLARED_ONLY_NOT_VERIFIED and says why.
    """
    out = []
    for p in paths:
        p = Path(p)
        doc = json.loads(p.read_text())
        required = {"datasets", "inventoried_at",
                    "inventory_sha256", "schema", "scope",
                    "summary"}
        if set(doc) != required:
            raise SystemExit(
                f"REFUSED: {p.name} is not the exact external "
                f"inventory schema (diff: "
                f"{sorted(set(doc) ^ required)})")
        declared = doc["inventory_sha256"]
        recomputed = ic._self_sha(doc, "inventory_sha256")
        inventory_verified = (declared == recomputed)
        for ds in doc["datasets"]:
            rel = ds.get("relative_path")
            root = roots.get(ds.get("root_id"))
            physical = ds.get("physical_sha256", ic.UNAVAILABLE)
            state, reason = "DECLARED_ONLY_NOT_VERIFIED", None
            recomputed_file = ic.UNAVAILABLE
            if not inventory_verified:
                reason = ("the external inventory's own self "
                          "digest does not re-derive")
            elif root is None:
                reason = (f"no local root was supplied for "
                          f"root_id={ds.get('root_id')!r}")
            else:
                target = Path(root) / rel
                if not target.is_file():
                    reason = (f"the profiled file is absent at "
                              f"{rel}")
                else:
                    recomputed_file = ic.sha256_file(target)
                    if recomputed_file == physical:
                        state = "FULL_PROFILE_PHYSICALLY_VERIFIED"
                    else:
                        reason = ("the profiled bytes do not "
                                  "match the declared digest")
            entry = {
                "external_profile_source": p.name,
                "external_inventory_sha256": declared,
                "external_inventory_self_digest_verified":
                    inventory_verified,
                "dataset_id": ds.get("dataset_id"),
                "relative_path": rel,
                "declared_physical_sha256": physical,
                "recomputed_physical_sha256": recomputed_file,
                "row_count": ds.get("row_count"),
                "variable_count": ds.get("variable_count"),
                "profile_status": ds.get("profile_status"),
                "binding_state": state,
                "binding_rule":
                    "a profile is FULL only when this census has "
                    "re-derived the inventory digest AND re-hashed "
                    "the bytes it claims to describe",
            }
            if reason:
                entry["not_verified_because"] = reason
            out.append(entry)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--censused-at", required=True,
                    help="RFC3339 timestamp fixed by the run "
                         "contract (reproducibility)")
    ap.add_argument("--digest-policy", default="selected",
                    choices=list(ic.DIGEST_POLICIES))
    ap.add_argument("--select", action="append", default=[],
                    help="relative path or appearance id to "
                         "digest physically; repeatable")
    ap.add_argument("--select-file", type=Path,
                    help="file with one selection per line")
    ap.add_argument("--previous", type=Path,
                    help="previous census document, for the "
                         "ADDED/UNCHANGED/CHANGED/MISSING delta")
    ap.add_argument("--external-full-profile", action="append",
                    type=Path, default=[],
                    help="inventory document from a consuming "
                         "repository whose FULL profiles are "
                         "bound by digest; repeatable")
    ap.add_argument("--out-dir", type=Path, required=True,
                    help="directory for the content-addressed "
                         "full census (may be outside the repo)")
    ap.add_argument("--summary", type=Path, required=True,
                    help="small Git-appropriate summary")
    ap.add_argument("--receipt", type=Path, required=True)
    ap.add_argument("--external-root", action="append",
                    default=[],
                    help="ROOT_ID=PATH for an external "
                         "inventory's datasets, so their bytes "
                         "can be re-hashed; repeatable")
    ap.add_argument("--value-profile-per-class", type=int,
                    default=0,
                    help="level-2 value sweep: profile this many "
                         "slices per source class, chosen "
                         "deterministically and declared as a "
                         "sample, never as a full census")
    ap.add_argument("--value-profile-row-cap", type=int,
                    default=50000)
    a = ap.parse_args(argv)

    selected = set(a.select)
    if a.select_file:
        selected |= {ln.strip() for ln
                     in a.select_file.read_text().splitlines()
                     if ln.strip()}
    previous = (json.loads(a.previous.read_text())
                if a.previous else None)
    ext_roots = {}
    for spec in a.external_root:
        rid, _, rpath = spec.partition("=")
        ext_roots[rid] = rpath
    ext = _load_external_full_profiles(a.external_full_profile,
                                       ext_roots)

    census = ic.build_census(
        a.root, a.censused_at, digest_policy=a.digest_policy,
        selected=selected, previous=previous,
        external_full_profiles=ext,
        value_profile_per_class=a.value_profile_per_class,
        value_profile_row_cap=a.value_profile_row_cap)

    a.out_dir.mkdir(parents=True, exist_ok=True)
    census_path = (a.out_dir /
                   f"census-{census['census_sha256']}.json")
    payload = json.dumps(census, indent=1, sort_keys=True)
    # C6: the name is content-addressed, so an existing file is
    # either the SAME artifact or a collision. Truncating it was
    # a defect; verify full byte equality instead.
    if census_path.exists():
        existing = census_path.read_bytes()
        if existing != payload.encode():
            raise SystemExit(
                "REFUSED: a different artifact already occupies "
                f"{census_path.name} — a content-addressed name "
                "is never overwritten")
        print(json.dumps({"census_file": census_path.name,
                          "write": "SKIPPED_IDENTICAL"}))
    else:
        fd = os.open(str(census_path),
                     os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, payload.encode())
            os.fsync(fd)
        finally:
            os.close(fd)

    a.summary.parent.mkdir(parents=True, exist_ok=True)
    a.summary.write_text(json.dumps(ic.summarize(census),
                                    indent=1, sort_keys=True))
    code = [ROOT / "_scripts/lib/incremental_census.py",
            ROOT / "_scripts/build_incremental_census.py"]
    # C42/C43: the receipt must be able to reproduce its own census.
    # Every argument that changes the artifact is recorded, and the
    # external profiles by digest — naming a path would let the same
    # receipt point at different bytes tomorrow.
    invocation = {
        "censused_at": a.censused_at,
        "digest_policy": a.digest_policy,
        "selected": sorted(selected),
        "value_profile_per_class": a.value_profile_per_class,
        "value_profile_row_cap": a.value_profile_row_cap,
        "previous_census_sha256": (previous or {}).get(
            "census_sha256", "NONE"),
        "external_full_profiles": [
            {"path": str(x.name),
             "sha256": ic.sha256_file(x)}
            for x in sorted(a.external_full_profile)],
        "external_roots": sorted(ext_roots),
    }
    rec = ic.receipt(census, census_path, a.summary, a.root, code,
                     invocation=invocation)
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(rec, indent=1,
                                    sort_keys=True))
    print(json.dumps({
        "census_sha256": census["census_sha256"],
        "census_file": census_path.name,
        "coverage": census["coverage"],
        "delta": {k: v for k, v in census["delta"].items()
                  if not k.endswith("_ids")},
        "conflicts": len(census["conflicts"]),
        "receipt_sha256": rec["receipt_sha256"],
    }, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
