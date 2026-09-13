"""C116: CPU characterization of the 89 ETH H4 successor columns (own descriptors).

Descriptors are RECOMPUTED here from the bound successor parquet bytes (sha256
verified before parsing). No lake terminal of any version is read or copied.

Order of writes, all write-once:
  1. NEW root  <successors_root>/eth_h4_stage22_rerun_v1_characterization_v1/
     (refuses if it exists; never inside the read-only successor root)
  2. PRE_LEDGER.json  (the plan: bound bytes, census, columns, descriptor rules)
  3. terminals/<column>.json  (one per column, exactly TERMINAL_KEYS)
  4. features/census/ETH_H4_SUCCESSOR_CHARACTERIZATION.v1.json  (committed
     summary; logical root id only, no home paths)
Files are chmod 0444 and directories 0555 at the end.

Semantic state (from the C115 census row, never from a column name):
  NON_NUMERIC               physical type not integer/float, OR semantic_type
                            temporal (a date/time stored as an integer is never
                            measurable)
  SEMANTIC_TYPE_UNRESOLVED  semantic_type UNKNOWN
  MISSING_POLICY_UNRESOLVED missing_policy UNKNOWN
  NUMERIC_MEASURABLE        otherwise
Layer: NUMERIC_MEASURABLE -> INDEPENDENTLY_RECOMPUTED; SEMANTIC_TYPE_UNRESOLVED
-> SEMANTICALLY_UNRESOLVED; NON_NUMERIC / MISSING_POLICY_UNRESOLVED ->
PHYSICALLY_TYPED. Unit and license are NOT decided here: a census UNKNOWN in
them still excludes the variable downstream via the census join.

Usage:
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 \
    python _scripts/characterize_eth_h4_successor.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

FD_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUCCESSORS_ROOT = Path.home() / ".local/state/crispdm-successors"
DATASET_ID = "financial_data.project3.ethusdt_4h_tech_stat.model_ready.successor_stage22_rerun.v1"
DATASET_SHA256 = "427a754ba3774e381e4f1353690b997d4e0ca89bf4ce6439ff2f8d651fd16d7c"
SUCCESSOR_REL = "eth_h4_stage22_rerun_v1/successor/ethusdt_4h_tech_stat_model_ready_successor.parquet"
SUCCESSOR_DIR = "eth_h4_stage22_rerun_v1"
OUT_DIR_NAME = "eth_h4_stage22_rerun_v1_characterization_v1"
CENSUS_REL = "features/census/ETH_H4_SUCCESSOR_SEMANTIC_CENSUS.v1.json"
SUMMARY_REL = "features/census/ETH_H4_SUCCESSOR_CHARACTERIZATION.v1.json"
SCHEMA_ID = "financial_data.eth_h4_successor_characterization.v1"

TERMINAL_KEYS = ("dataset_id", "dataset_sha256", "column", "variable_id", "layer",
                 "semantic_state", "physical_type", "observations", "missing_fraction",
                 "descriptors", "source_sha256")
QUANTILES = (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)
TEMPORAL_SEMANTIC_TYPES = frozenset({"timestamp", "date", "datetime", "time", "calendar_date",
                                     "epoch_seconds", "epoch_milliseconds", "epoch_ms", "epoch_s",
                                     "date_yyyymmdd", "date_integer", "bar_open_time", "bar_close_time"})
TEMPORAL_PREFIXES = ("temporal_", "date_", "datetime_", "timestamp_", "epoch_", "calendar_")
HOME_RE = re.compile(r"(/home|/Users|/root)/")


class DigestMismatch(RuntimeError):
    pass


class Refusal(RuntimeError):
    pass


def self_digest(doc: dict[str, Any]) -> dict[str, str]:
    body = {k: v for k, v in doc.items() if k != "self_digest"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {"algorithm": "sha256",
            "canonicalization": "json.dumps(document_without_self_digest, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')",
            "value": hashlib.sha256(canon).hexdigest()}


def read_once(path: Path, expected: str | None) -> tuple[bytes, str]:
    with open(path, "rb") as fh:
        data = fh.read()
    d = hashlib.sha256(data).hexdigest()
    if expected is not None and d != expected:
        raise DigestMismatch(f"{path.name}: sha256 {d} != expected {expected}")
    return data, d


def is_temporal_semantic(sem: str) -> bool:
    s = str(sem).lower()
    return s in TEMPORAL_SEMANTIC_TYPES or s.startswith(TEMPORAL_PREFIXES)


def semantic_state(arrow_type: pa.DataType, row: dict) -> str:
    numeric = (pa.types.is_integer(arrow_type) or pa.types.is_floating(arrow_type))
    if not numeric:
        return "NON_NUMERIC"
    sem = row.get("semantic_type", "UNKNOWN")
    if sem == "UNKNOWN":
        return "SEMANTIC_TYPE_UNRESOLVED"
    if is_temporal_semantic(sem):
        return "NON_NUMERIC"
    if row.get("missing_policy", "UNKNOWN") == "UNKNOWN":
        return "MISSING_POLICY_UNRESOLVED"
    return "NUMERIC_MEASURABLE"


LAYER = {"NUMERIC_MEASURABLE": "INDEPENDENTLY_RECOMPUTED",
         "SEMANTIC_TYPE_UNRESOLVED": "SEMANTICALLY_UNRESOLVED",
         "NON_NUMERIC": "PHYSICALLY_TYPED",
         "MISSING_POLICY_UNRESOLVED": "PHYSICALLY_TYPED"}


def descriptors(col: pa.ChunkedArray, measurable: bool) -> dict[str, Any]:
    n = len(col)
    nulls = int(col.null_count)
    out: dict[str, Any] = {"count": n, "null_count": nulls}
    t = col.type
    if pa.types.is_integer(t) or pa.types.is_floating(t):
        v = col.to_numpy(zero_copy_only=False).astype(np.float64)  # nulls -> NaN
        nan = int(np.isnan(v).sum())
        inf = int(np.isinf(v).sum())
        fin = v[np.isfinite(v)]
        out.update({"missing_count": nan, "nan_count_excluding_nulls": nan - nulls,
                    "infinite_count": inf, "finite_count": int(fin.size)})
    else:
        out.update({"missing_count": nulls, "nan_count_excluding_nulls": 0,
                    "infinite_count": 0, "finite_count": None})
        fin = None
    stats = dict.fromkeys(("mean", "std", "min", "max"))
    q = {f"q{p:g}": None for p in QUANTILES}
    if measurable and fin is not None and fin.size:
        stats = {"mean": float(np.mean(fin)), "std": float(np.std(fin, ddof=0)),
                 "min": float(np.min(fin)), "max": float(np.max(fin))}
        qs = np.quantile(fin, QUANTILES, method="linear")
        q = {f"q{p:g}": float(x) for p, x in zip(QUANTILES, qs)}
    out.update(stats)
    out["quantiles"] = q
    return out


def terminal(table: pa.Table, column: str, row: dict, dataset_id: str, sha: str) -> dict:
    col = table.column(column)
    state = semantic_state(col.type, row)
    desc = descriptors(col, state == "NUMERIC_MEASURABLE")
    obs = desc["finite_count"] if desc["finite_count"] is not None else desc["count"] - desc["null_count"]
    t = {"dataset_id": dataset_id, "dataset_sha256": sha, "column": column,
         "variable_id": row["variable_id"], "layer": LAYER[state], "semantic_state": state,
         "physical_type": str(col.type), "observations": int(obs),
         "missing_fraction": (desc["missing_count"] / desc["count"]) if desc["count"] else None,
         "descriptors": desc, "source_sha256": sha}
    assert tuple(t) == TERMINAL_KEYS
    return t


def _write_once(path: Path, obj: dict, mode: int = 0o444) -> str:
    text = json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if HOME_RE.search(text):
        raise Refusal(f"absolute home-directory path in {path.name}")
    data = text.encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.chmod(path, mode)
    return hashlib.sha256(data).hexdigest()


def run(*, dataset_path: Path, dataset_sha256: str, dataset_id: str, census_path: Path,
        out_root: Path, summary_path: Path, root_logical_id: str,
        protected_roots: tuple[Path, ...] = ()) -> dict:
    out_root = Path(out_root)
    for p in protected_roots:
        if out_root.resolve() == Path(p).resolve() or Path(p).resolve() in out_root.resolve().parents:
            raise Refusal("output root lies inside a protected read-only root")
    if out_root.exists():
        raise Refusal(f"write-once: output root {out_root.name} already exists")
    if summary_path.exists():
        raise Refusal(f"write-once: {summary_path.name} already exists")

    # verify + parse inputs before creating anything
    data, sha = read_once(dataset_path, dataset_sha256)
    cbytes, csha = read_once(census_path, None)
    census = json.loads(cbytes)
    if census.get("self_digest", {}).get("value") != self_digest(census)["value"]:
        raise Refusal("census self digest does not verify")
    if census.get("dataset_id") != dataset_id or census.get("dataset_sha256") != sha:
        raise Refusal("census does not describe these bytes")
    rows = {}
    for r in census["rows"]:
        if r["column"] in rows:
            raise Refusal(f"duplicate census column {r['column']}")
        if r["dataset_id"] != dataset_id or r["dataset_sha256"] != sha:
            raise Refusal(f"census row {r['column']} is for other bytes")
        rows[r["column"]] = r
    if len({r["variable_id"] for r in rows.values()}) != len(rows):
        raise Refusal("duplicate census variable_id")
    table = pq.read_table(pa.BufferReader(data))
    columns = [c for c in table.column_names if c in rows]
    if set(columns) != set(rows):
        raise Refusal(f"census columns absent from the parquet: {sorted(set(rows) - set(columns))}")
    for c in columns:
        if str(table.column(c).type) != rows[c]["physical_type"]:
            raise Refusal(f"{c}: parquet type {table.column(c).type} != census physical_type {rows[c]['physical_type']}")
    own_bytes, own_sha = read_once(Path(__file__), None)

    out_root.mkdir(parents=False, exist_ok=False)
    (out_root / "terminals").mkdir()
    ledger = {
        "schema": SCHEMA_ID + ".pre_ledger",
        "sealed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root_logical_id": root_logical_id,
        "dataset": {"dataset_id": dataset_id, "dataset_sha256": sha, "rows": table.num_rows},
        "census": {"relative_path": CENSUS_REL, "sha256": csha, "self_digest": census["self_digest"]["value"]},
        "producer": {"root_id": "financial-data", "relative_path": "_scripts/characterize_eth_h4_successor.py", "sha256": own_sha},
        "runtime": {"python": sys.version.split()[0], "numpy": np.__version__, "pyarrow": pa.__version__,
                    "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES")},
        "descriptor_rules": {
            "missing": "null or NaN (pyarrow nulls read as NaN); infinite values counted separately and excluded from statistics",
            "statistics_over": "finite values only, as float64",
            "std": "population std, numpy ddof=0",
            "quantiles": list(QUANTILES), "quantile_method": "numpy.quantile method='linear'",
            "observations": "finite_count for numeric physical types, non-null count otherwise",
            "missing_fraction": "missing_count / count",
            "not_read": "no lake terminal of any version is read; every value is recomputed from the bound bytes"},
        "semantic_state_rules": {"NON_NUMERIC": "physical type not integer/float, or temporal semantic_type (integer dates never measurable)",
                                 "SEMANTIC_TYPE_UNRESOLVED": "census semantic_type UNKNOWN",
                                 "MISSING_POLICY_UNRESOLVED": "census missing_policy UNKNOWN",
                                 "NUMERIC_MEASURABLE": "otherwise"},
        "layer_rules": LAYER,
        "planned_terminals": [{"column": c, "variable_id": rows[c]["variable_id"],
                               "relative_path": f"terminals/{c}.json"} for c in columns],
    }
    ledger_sha = _write_once(out_root / "PRE_LEDGER.json", ledger)

    terminals = []
    for c in columns:
        t = terminal(table, c, rows[c], dataset_id, sha)
        tsha = _write_once(out_root / "terminals" / f"{c}.json", t)
        terminals.append({"column": c, "variable_id": t["variable_id"], "layer": t["layer"],
                          "semantic_state": t["semantic_state"], "physical_type": t["physical_type"],
                          "observations": t["observations"], "missing_fraction": t["missing_fraction"],
                          "terminal_relative_path": f"terminals/{c}.json", "terminal_sha256": tsha})
    os.chmod(out_root / "terminals", 0o555)
    os.chmod(out_root, 0o555)

    def count(k):
        out: dict[str, int] = {}
        for t in terminals:
            out[t[k]] = out.get(t[k], 0) + 1
        return dict(sorted(out.items()))

    summary = {
        "schema": SCHEMA_ID,
        "artifact": "ETH_H4_SUCCESSOR_CHARACTERIZATION.v1",
        "order_items": ["C116"],
        "dataset_id": dataset_id, "dataset_sha256": sha,
        "census": ledger["census"],
        "root_logical_id": root_logical_id,
        "pre_ledger": {"relative_path": "PRE_LEDGER.json", "sha256": ledger_sha},
        "producer": ledger["producer"],
        "descriptor_rules": ledger["descriptor_rules"],
        "columns": len(terminals),
        "counts_by_layer": count("layer"),
        "counts_by_semantic_state": count("semantic_state"),
        "terminals": terminals,
        "statement": "Descriptors are recomputed from the bound successor bytes; unit and license UNKNOWN in the census still exclude a variable downstream.",
    }
    summary["self_digest"] = self_digest(summary)
    _write_once(summary_path, summary, mode=0o644)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--financial-data-root", type=Path, default=FD_ROOT)
    ap.add_argument("--successors-root", type=Path, default=DEFAULT_SUCCESSORS_ROOT)
    a = ap.parse_args(argv)
    sroot = a.successors_root
    s = run(dataset_path=sroot / SUCCESSOR_REL, dataset_sha256=DATASET_SHA256, dataset_id=DATASET_ID,
            census_path=a.financial_data_root / CENSUS_REL, out_root=sroot / OUT_DIR_NAME,
            summary_path=a.financial_data_root / SUMMARY_REL,
            root_logical_id=f"crispdm-successors/{OUT_DIR_NAME}",
            protected_roots=(sroot / SUCCESSOR_DIR,))
    print(json.dumps({k: s[k] for k in ("columns", "counts_by_layer", "counts_by_semantic_state", "pre_ledger")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
