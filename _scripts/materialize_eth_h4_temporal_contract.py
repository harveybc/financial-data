"""C81 materializer: ETH H4 temporal availability contract (order 2026-09-12).

Binds the model-ready CSV and its candidate source parquet by sha256 and
consumes EXACTLY the bytes it verifies: each file is opened once, read
into memory, hashed, compared with the expected digest, and parsed from
that same buffer. A digest mismatch refuses before anything is parsed or
written.

Writes (only when every digest verifies):
  features/census/TEMPORAL_AVAILABILITY_SCHEMA.v1.json
  features/census/ETH_H4_TEMPORAL_CONTRACT.v1.json

Usage:
  PYTHONDONTWRITEBYTECODE=1 python _scripts/materialize_eth_h4_temporal_contract.py
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import temporal_availability as ta  # noqa: E402

FD_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTOR_ROOT = FD_ROOT.parent / "predictor"

ETH_DATASET_ID = "financial_data.project3.ethusdt_4h_tech_stat.model_ready.v1"
CONTRACT_ID = "financial_data.eth_h4_temporal_contract.v1"
NOMINAL_BAR_SECONDS = 14400
OHLCV = (("OPEN", "open"), ("HIGH", "high"), ("LOW", "low"),
         ("CLOSE", "close"), ("VOLUME", "volume"))


@dataclass(frozen=True)
class Source:
    name: str
    root_id: str
    relative_path: str
    expected_sha256: str | None


SOURCES = (
    Source("model_ready_csv", "predictor",
           "examples/data/project3/ethusdt_4h_tech_stat_full_model_ready.csv",
           "1b447c66e68495e826c53e2ab2b08ecd3922c8fdc735747628f8d0435ebe440f"),
    Source("candidate_source_parquet", "financial-data",
           "features/trading_asset_data/ethusdt/4h.parquet",
           "37321161d3e0d372abd0c3a0cc867ed4b2faf1fdf1e4569d55da6f6a1a1df099"),
    Source("declared_upstream_parquet", "financial-data",
           "market_data/crypto/spot_top50/ethusdt/4h.parquet",
           "7a6b79833355d7c22a3db30e6494ced078d628338d76e671af320a06b35fc9e5"),
    # declarations: hashed and recorded, content-checked, no pinned digest
    Source("export_metadata", "predictor",
           "examples/data/project3/ethusdt_4h_tech_stat_export_metadata.json", None),
    Source("candidate_provenance", "financial-data",
           "features/trading_asset_data/ethusdt/provenance.json", None),
    Source("upstream_provenance", "financial-data",
           "market_data/crypto/spot_top50/ethusdt/provenance.json", None),
    Source("dataset_inventory", "predictor",
           "examples/research/crispdm_dataset_inventory.v1.json", None),
    Source("dataset_registry", "predictor",
           "examples/research/crispdm_dataset_registry.v1.json", None),
)


class DigestMismatch(RuntimeError):
    pass


class Refusal(RuntimeError):
    pass


def read_once(path: Path, expected_sha256: str | None) -> tuple[bytes, str]:
    """The ONLY place a source file is opened."""
    with open(path, "rb") as fh:
        data = fh.read()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise DigestMismatch(f"{path.name}: sha256 {digest} != expected {expected_sha256}")
    return data, digest


def _iso(ms: int) -> str:
    t = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(ms))
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _ms_column(table: pa.Table, name: str) -> np.ndarray:
    col = table.column(name)
    t = col.type
    if not (pa.types.is_timestamp(t) and t.unit == "ms" and t.tz == "UTC"):
        raise Refusal(f"{name}: expected timestamp[ms, tz=UTC], got {t}")
    if col.null_count:
        raise Refusal(f"{name}: {col.null_count} nulls")
    return col.cast(pa.int64()).to_numpy()


def self_digest(doc: dict[str, Any]) -> dict[str, str]:
    body = {k: v for k, v in doc.items() if k != "self_digest"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
    return {"algorithm": "sha256",
            "canonicalization": "json.dumps(document_without_self_digest, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')",
            "value": hashlib.sha256(canon).hexdigest()}


def _rel_tail(declared: str, tail: str) -> bool:
    return isinstance(declared, str) and declared.replace("\\", "/").endswith("/" + tail)


def materialize(fd_root: Path = FD_ROOT,
                predictor_root: Path = DEFAULT_PREDICTOR_ROOT) -> tuple[dict, dict]:
    roots = {"financial-data": Path(fd_root), "predictor": Path(predictor_root)}

    # 1. read + verify EVERY byte source before parsing any of them
    raw: dict[str, bytes] = {}
    bound: dict[str, dict[str, Any]] = {}
    for s in SOURCES:
        data, digest = read_once(roots[s.root_id] / s.relative_path, s.expected_sha256)
        raw[s.name] = data
        bound[s.name] = {"root_id": s.root_id, "relative_path": s.relative_path,
                         "sha256": digest, "bytes": len(data),
                         "digest_check": "VERIFIED_AGAINST_PINNED_DIGEST"
                         if s.expected_sha256 else "RECORDED_NOT_PINNED"}
    csv_sha = bound["model_ready_csv"]["sha256"]

    # 2. parse the verified bytes (never the paths)
    csv = pd.read_csv(io.BytesIO(raw["model_ready_csv"]),
                      usecols=["DATE_TIME"] + [c for c, _ in OHLCV],
                      dtype={"DATE_TIME": str}, float_precision="round_trip")
    par = pq.read_table(pa.BufferReader(raw["candidate_source_parquet"]))
    up = pq.read_table(pa.BufferReader(raw["declared_upstream_parquet"]))
    decl = {k: json.loads(raw[k].decode("utf-8")) for k in (
        "export_metadata", "candidate_provenance", "upstream_provenance",
        "dataset_inventory", "dataset_registry")}

    # 3. CSV timestamps: offset-free strings, UTC per the registry
    pat = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
    bad = int((~csv["DATE_TIME"].map(lambda s: bool(pat.match(s)))).sum())
    if bad:
        raise Refusal(f"{bad} DATE_TIME values not in 'YYYY-MM-DD HH:MM:SS' form")
    dt = pd.to_datetime(csv["DATE_TIME"], format="%Y-%m-%d %H:%M:%S", utc=True)
    csv_ms = ((dt - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)).to_numpy(np.int64)

    open_ms = _ms_column(par, "timestamp")
    close_ms = _ms_column(par, "close_time")
    n_par = len(open_ms)
    nominal_ms = NOMINAL_BAR_SECONDS * 1000
    full_span = nominal_ms - 1  # Binance close_time: inclusive last millisecond

    # 4. join DATE_TIME == open time
    idx = pd.Index(open_ms).get_indexer(csv_ms)
    matched = idx >= 0
    n_matched = int(matched.sum())
    max_err, exact_rows = {}, {}
    for c_csv, c_par in OHLCV:
        a = csv[c_csv].to_numpy(np.float64)[matched]
        b = par.column(c_par).to_numpy()[idx[matched]]
        diff = np.abs(a - b)
        max_err[c_csv] = float(np.nanmax(diff)) if len(diff) else None
        exact_rows[c_csv] = int((a == b).sum())
    in_csv = np.zeros(n_par, dtype=bool)
    in_csv[idx[matched]] = True
    mi = idx[matched]

    # 5. per-bar close_time structure of the source
    span = close_ms - open_ms
    step = np.diff(open_ms)
    nxt = np.append(open_ms[1:], -1)
    followed_by_gap = np.append(step > nominal_ms, False)
    truncated = []
    for i in np.flatnonzero(span < full_span):
        truncated.append({
            "open_time_utc": _iso(open_ms[i]), "close_time_utc": _iso(close_ms[i]),
            "open_time_ms": int(open_ms[i]), "close_time_ms": int(close_ms[i]),
            "span_seconds": round(int(span[i]) / 1000.0, 3),
            "nominal_span_seconds": round(full_span / 1000.0, 3),
            "in_model_ready_csv": bool(in_csv[i]),
            "followed_by_gap": bool(followed_by_gap[i])})
    gaps = []
    for j in np.flatnonzero(step > nominal_ms):
        gaps.append({
            "previous_open_time_utc": _iso(open_ms[j]), "next_open_time_utc": _iso(open_ms[j + 1]),
            "delta_seconds": int(step[j]) // 1000,
            "missing_nominal_bars": int(step[j] // nominal_ms) - 1
            if step[j] % nominal_ms == 0 else None,
            "exceeds_twice_nominal": bool(step[j] > 2 * nominal_ms),
            "previous_bar_truncated": bool(span[j] < full_span),
            "previous_bar_in_model_ready_csv": bool(in_csv[j]),
            "next_bar_in_model_ready_csv": bool(in_csv[j + 1])})
    structure = {
        "source_rows": n_par,
        "open_times_strictly_increasing": bool((step > 0).all()),
        "open_times_off_nominal_grid": int((open_ms % nominal_ms != 0).sum()),
        "close_time_before_open_time": int((close_ms < open_ms).sum()),
        "close_time_exceeds_nominal_bar": int((span > full_span).sum()),
        "close_time_at_or_after_next_open": int((close_ms[:-1] >= open_ms[1:]).sum()),
        "full_nominal_span_bars": int((span == full_span).sum()),
        "truncated_bars_total": len(truncated),
        "truncated_bars_in_model_ready_csv": sum(t["in_model_ready_csv"] for t in truncated),
        "truncated_bars": truncated,
        "gaps_greater_than_nominal_total": len(gaps),
        "gaps_greater_than_twice_nominal_total": sum(g["exceeds_twice_nominal"] for g in gaps),
        "gaps": gaps,
    }

    # 6. provenance: exact match + declarations
    up_ren = up.rename_columns(["timestamp" if n == "open_time" else n for n in up.column_names])
    upstream_identical = (up.column_names[0] == "open_time"
                          and up_ren.column_names == par.column_names
                          and up_ren.equals(par, check_metadata=False))
    em, cp, upv = decl["export_metadata"], decl["candidate_provenance"], decl["upstream_provenance"]
    declarations = {
        "export_metadata_sources.raw_ohlcv_names_declared_upstream": _rel_tail(
            em.get("sources", {}).get("raw_ohlcv"), SOURCES[2].relative_path),
        "export_metadata_names_candidate_parquet": any(
            _rel_tail(v, SOURCES[1].relative_path) for v in em.get("sources", {}).values()),
        "export_metadata_model_ready_csv_names_this_csv": _rel_tail(
            em.get("model_ready_csv"), SOURCES[0].relative_path),
        "export_metadata_model_ready_rows": em.get("model_ready_rows"),
        "export_metadata_declares_digests": False,
        "candidate_provenance_4h_source": cp.get("timeframes", {}).get("4h", {}).get("source"),
        "candidate_provenance_4h_unexpected_gaps": cp.get("timeframes", {}).get("4h", {}).get("frequency", {}).get("unexpected_gaps"),
        "upstream_provenance_declared_sha256": next(
            (f.get("sha256") for f in upv.get("files", [])
             if f.get("path") == SOURCES[2].relative_path), None),
    }
    declarations["upstream_provenance_digest_equals_bytes"] = (
        declarations["upstream_provenance_declared_sha256"] == bound["declared_upstream_parquet"]["sha256"])
    all_match = (n_matched == len(csv) and all(v == 0.0 for v in max_err.values()))
    if not all_match:
        raise Refusal(f"CSV does not match candidate parquet exactly: {n_matched}/{len(csv)}, {max_err}")
    declared_chain = (declarations["export_metadata_sources.raw_ohlcv_names_declared_upstream"]
                      and declarations["candidate_provenance_4h_source"] == SOURCES[2].relative_path
                      and declarations["upstream_provenance_digest_equals_bytes"]
                      and upstream_identical)
    prov_status = ("EVIDENCED_BY_EXACT_MATCH_WITH_DECLARED_UPSTREAM" if declared_chain
                   else "EVIDENCED_BY_EXACT_MATCH_NOT_BY_DECLARATION")
    basis = (
        f"Exact OHLCV match of all {n_matched}/{len(csv)} CSV rows to the candidate parquet on DATE_TIME == open time (max abs error 0.0 per column). "
        "No artifact declares the candidate parquet as the CSV's source: the CSV's export metadata declares raw_ohlcv = market_data/crypto/spot_top50/ethusdt/4h.parquet by absolute PATH ONLY (no digest). "
        + ("The candidate's own provenance.json declares that same upstream as its 4h source, the upstream's provenance.json declares a sha256 equal to the upstream bytes read here, and the candidate is value-identical to the upstream on every column after renaming open_time -> timestamp (bytes differ). "
           if declared_chain else "The declared upstream chain could NOT be confirmed. ")
        + "The CSV -> candidate binding is therefore evidenced by exact match; the declaration reaches the candidate only through the upstream, by path.")

    # 7. contract + row-level evaluation with the pure functions
    contract = {
        "contract_id": CONTRACT_ID,
        "dataset_id": ETH_DATASET_ID,
        "dataset_sha256": csv_sha,
        "timestamp_semantics": "BAR_OPEN",
        "information_complete_not_before": "PER_BAR_CLOSE_TIME",
        "nominal_bar_seconds": NOMINAL_BAR_SECONDS,
        "bar_close_time_convention": "INCLUSIVE_LAST_MILLISECOND",
        "provider_delivery_latency": {
            "status": "UNOBSERVED", "seconds": None,
            "evidence": "No artifact records when Binance delivered any bar; no latency was observed or declared. UNOBSERVED is not zero."},
        "provenance": {"status": prov_status, "basis": basis},
    }
    defects = ta.validate_contract(contract)
    if defects:
        raise Refusal(f"contract invalid: {defects}")
    rows = ({"timestamp_ms": int(open_ms[i]), "close_time_ms": int(close_ms[i]),
             "next_timestamp_ms": int(nxt[i]) if nxt[i] >= 0 else None} for i in mi)
    evaluation = ta.evaluate_rows(contract, rows, observed_sha256=csv_sha)

    # 8. EURUSD: UNDECLARED, not generalized
    registry_by_id = {d["dataset_id"]: d for d in decl["dataset_registry"].get("datasets", [])}
    undeclared = []
    for d in decl["dataset_inventory"].get("datasets", []):
        if "eurusd" not in d.get("dataset_id", "").lower():
            continue
        ucontract = {
            "contract_id": f"{d['dataset_id']}.temporal_contract.undeclared",
            "dataset_id": d["dataset_id"], "dataset_sha256": d["physical_sha256"],
            "timestamp_semantics": "UNDECLARED", "information_complete_not_before": "UNDECLARED",
            "nominal_bar_seconds": None,
            "provider_delivery_latency": {"status": "UNOBSERVED", "seconds": None,
                                          "evidence": "No provider recorded."},
            "provenance": {"status": "UNDECLARED",
                           "basis": f"Inventory provider '{d.get('provider')}', availability_policy '{d.get('availability_policy')}', registry timestamp_semantics '{registry_by_id.get(d['dataset_id'], {}).get('timestamp_semantics')}'. The ETH decision is not generalized to this dataset."}}
        cb = ta.causal_information_bound(ucontract, {}, observed_sha256=d["physical_sha256"])
        ob = ta.operational_delivery_bound(ucontract, cb)
        undeclared.append({
            "dataset_id": d["dataset_id"], "root_id": d.get("root_id"),
            "relative_path": d.get("relative_path"),
            "inventory_physical_sha256": d["physical_sha256"],
            "digest_note": "Taken from the inventory; the dataset bytes were NOT re-read by this tool.",
            "contract": ucontract,
            "causal_information_bound": cb.to_dict(),
            "operational_delivery_bound": ob.to_dict(),
            "E5a": ta.gate_e5a(ucontract, cb).to_dict(),
            "E5b": ta.gate_e5b(ucontract, cb, ob).to_dict()})
    if not undeclared:
        raise Refusal("no EURUSD dataset found in the inventory")

    schema = ta.schema_document()
    schema["self_digest"] = self_digest(schema)

    doc = {
        "artifact": "ETH_H4_TEMPORAL_CONTRACT.v1",
        "order_items": ["C81", "C82", "C83"],
        "schema": {"id": ta.SCHEMA_ID, "root_id": "financial-data",
                   "relative_path": "features/census/TEMPORAL_AVAILABILITY_SCHEMA.v1.json",
                   "self_digest": schema["self_digest"]["value"]},
        "producer": {"root_id": "financial-data",
                     "relative_path": "_scripts/materialize_eth_h4_temporal_contract.py",
                     "library": "_scripts/temporal_availability.py",
                     "byte_discipline": "Each source opened once, read into memory, hashed, compared with its pinned digest, and parsed from that same buffer (pandas.read_csv(io.BytesIO), pyarrow.parquet.read_table(pyarrow.BufferReader))."},
        "bound_files": bound,
        "contract": contract,
        "measurements": {
            "csv_rows": int(len(csv)),
            "csv_timestamp_column": "DATE_TIME",
            "csv_timestamp_format": "YYYY-MM-DD HH:MM:SS without offset; interpreted as UTC per registry timestamp_semantics BAR_OPEN_TIME_UTC",
            "csv_float_parser": "pandas round_trip",
            "join": "CSV DATE_TIME == parquet timestamp (open time, ms UTC)",
            "rows_matched": n_matched,
            "rows_unmatched": int(len(csv) - n_matched),
            "matched_source_index_range": [int(mi.min()), int(mi.max())],
            "matched_rows_contiguous_in_source": bool(mi.max() - mi.min() + 1 == n_matched and (np.diff(mi) == 1).all()),
            "ohlcv_max_abs_error": max_err,
            "ohlcv_exactly_equal_rows": exact_rows,
            "csv_first_open_time_utc": _iso(csv_ms[0]), "csv_last_open_time_utc": _iso(csv_ms[-1]),
        },
        "source_bar_structure": structure,
        "stage_2_1_gap_count_reconciliation": (
            "candidate provenance.json reports unexpected_gaps = "
            f"{declarations['candidate_provenance_4h_unexpected_gaps']} using the rule delta > 2 x step "
            "(_scripts/workers/stage21_trading_asset_worker.py validate_frequency); this artifact counts "
            f"delta > 1 x step = {structure['gaps_greater_than_nominal_total']}, of which "
            f"{structure['gaps_greater_than_twice_nominal_total']} exceed 2 x step."),
        "information_complete_not_before_rule": "Per bar: the bar's own close_time as recorded in the candidate parquet. Never open_time + nominal_bar_seconds; truncated bars complete at their actual (earlier) close_time.",
        "provider_delivery_latency": "UNOBSERVED",
        "provenance": {"status": prov_status, "basis": basis,
                       "declared_upstream_value_identical_after_rename": bool(upstream_identical),
                       "declarations": declarations},
        "row_evaluation": evaluation,
        "gates": {
            "E5a": {"status": evaluation["E5a"]["status"],
                    "scope": "Timestamp availability of the raw OHLCV bars of this exact CSV (sha256 above). Derived feature columns' causal lookback is NOT adjudicated here.",
                    "closed_reason_counts": evaluation["E5a"]["closed_reason_counts"]},
            "E5b": {"status": evaluation["E5b"]["status"],
                    "closed_reason_counts": evaluation["E5b"]["closed_reason_counts"],
                    "note": "This order grants no live viability."},
        },
        "undeclared_datasets": undeclared,
    }
    doc["self_digest"] = self_digest(doc)
    for d in (schema, doc):
        text = json.dumps(d)
        if "/home/" in text or str(Path.home()) in text:
            raise Refusal("absolute home-directory path in published document")
    return schema, doc


def write(doc: dict, path: Path) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--financial-data-root", type=Path, default=FD_ROOT)
    ap.add_argument("--predictor-root", type=Path, default=DEFAULT_PREDICTOR_ROOT)
    ap.add_argument("--out-dir", type=Path, default=FD_ROOT / "features/census")
    a = ap.parse_args(argv)
    schema, doc = materialize(a.financial_data_root, a.predictor_root)
    write(schema, a.out_dir / "TEMPORAL_AVAILABILITY_SCHEMA.v1.json")
    write(doc, a.out_dir / "ETH_H4_TEMPORAL_CONTRACT.v1.json")
    print(json.dumps({"E5a": doc["gates"]["E5a"]["status"], "E5b": doc["gates"]["E5b"]["status"],
                      "rows_matched": doc["measurements"]["rows_matched"],
                      "truncated": doc["source_bar_structure"]["truncated_bars_total"],
                      "gaps": doc["source_bar_structure"]["gaps_greater_than_nominal_total"],
                      "self_digest": doc["self_digest"]["value"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
