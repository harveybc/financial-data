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


def _load_external_full_profiles(paths: list[Path]) -> list[dict]:
    """Bind FULL profiles produced by a consuming repository
    (predictor's CRISP-DM inventory) by digest.

    The census does not re-profile those bytes; it records who
    profiled them, the digest that was profiled, and the counts
    claimed — so a later disagreement is visible instead of
    silently averaged away.
    """
    out = []
    for p in paths:
        doc = json.loads(Path(p).read_text())
        for ds in doc.get("datasets", []):
            out.append({
                "external_profile_source": str(Path(p).name),
                "external_inventory_sha256":
                    doc.get("inventory_sha256", ic.UNKNOWN),
                "dataset_id": ds.get("dataset_id"),
                "relative_path": ds.get("relative_path"),
                "physical_sha256": ds.get("physical_sha256",
                                          ic.UNKNOWN),
                "row_count": ds.get("row_count"),
                "variable_count": ds.get("variable_count"),
                "profile_status": ds.get("profile_status"),
                "profile_depth": ic.PROFILE_FULL,
                "binding_rule": "bound by digest; this census "
                                "never re-profiles externally "
                                "profiled bytes",
            })
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
    ext = _load_external_full_profiles(a.external_full_profile)

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
    fd = os.open(str(census_path),
                 os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
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
    rec = ic.receipt(census, census_path, a.summary, a.root, code)
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
