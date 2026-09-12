"""C98 materializer: ETH H4 temporal quality contract v2 + sample eligibility mask.

Successor to ETH_H4_TEMPORAL_CONTRACT.v1.json, which is READ (never written)
and bound by its pinned sha256. Same byte discipline as v1: each source is
opened exactly once, read into memory, hashed, compared with its pinned
digest and parsed from that same buffer. Every digest is verified before
anything is parsed; a mismatch refuses before anything is written.

Writes (only when every digest verifies):
  features/census/TEMPORAL_QUALITY_SCHEMA.v1.json
  features/census/ETH_H4_SAMPLE_ELIGIBILITY_MASK.v1.parquet
  features/census/ETH_H4_TEMPORAL_CONTRACT.v2.json

Usage:
  PYTHONDONTWRITEBYTECODE=1 python _scripts/materialize_eth_h4_temporal_quality.py
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import temporal_availability as ta  # noqa: E402
import temporal_quality as tq  # noqa: E402

FD_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTOR_ROOT = FD_ROOT.parent / "predictor"

CONTRACT_ID = "financial_data.eth_h4_temporal_contract.v2"
V1_CONTRACT_ID = "financial_data.eth_h4_temporal_contract.v1"
MASK_NAME = "ETH_H4_SAMPLE_ELIGIBILITY_MASK.v1.parquet"
SCHEMA_NAME = "TEMPORAL_QUALITY_SCHEMA.v1.json"
CONTRACT_NAME = "ETH_H4_TEMPORAL_CONTRACT.v2.json"
OHLCV = (("OPEN", "open"), ("HIGH", "high"), ("LOW", "low"),
         ("CLOSE", "close"), ("VOLUME", "volume"))


@dataclass(frozen=True)
class Source:
    name: str
    root_id: str
    relative_path: str
    expected_sha256: str


SOURCES = (
    Source("model_ready_csv", "predictor",
           "examples/data/project3/ethusdt_4h_tech_stat_full_model_ready.csv",
           "1b447c66e68495e826c53e2ab2b08ecd3922c8fdc735747628f8d0435ebe440f"),
    Source("candidate_source_parquet", "financial-data",
           "features/trading_asset_data/ethusdt/4h.parquet",
           "37321161d3e0d372abd0c3a0cc867ed4b2faf1fdf1e4569d55da6f6a1a1df099"),
    Source("v1_contract", "financial-data",
           "features/census/ETH_H4_TEMPORAL_CONTRACT.v1.json",
           "6e3a0c8d67dd2ec64dcad8bd7bb7ca0154dd514b43e9e2990de83578cc794254"),
)


class DigestMismatch(RuntimeError):
    pass


class Refusal(RuntimeError):
    pass


def read_once(path: Path, expected_sha256: str) -> tuple[bytes, str]:
    """The ONLY place a source file is opened."""
    with open(path, "rb") as fh:
        data = fh.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise DigestMismatch(f"{path.name}: sha256 {digest} != expected {expected_sha256}")
    return data, digest


def self_digest(doc: dict[str, Any]) -> dict[str, str]:
    body = {k: v for k, v in doc.items() if k != "self_digest"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
    return {"algorithm": "sha256",
            "canonicalization": "json.dumps(document_without_self_digest, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')",
            "value": hashlib.sha256(canon).hexdigest()}


def _ms_column(table: pa.Table, name: str) -> np.ndarray:
    col = table.column(name)
    t = col.type
    if not (pa.types.is_timestamp(t) and t.unit == "ms" and t.tz == "UTC"):
        raise Refusal(f"{name}: expected timestamp[ms, tz=UTC], got {t}")
    if col.null_count:
        raise Refusal(f"{name}: {col.null_count} nulls")
    return col.cast(pa.int64()).to_numpy()


def mask_table(bars: tq.BarLayers, mask: tq.SampleMask, roles: list[np.ndarray]) -> pa.Table:
    n = bars.n
    cols = {
        "row_index": pa.array(np.arange(n, dtype=np.int32)),
        "open_time_ms": pa.array(bars.open_ms, type=pa.int64()),
        "close_time_ms": pa.array([int(c) if p else None for c, p in zip(bars.close_ms, bars.close_present)], type=pa.int64()),
        "bar_available": pa.array(bars.available),
        "bar_interval_complete": pa.array(bars.interval_complete),
        "bar_truncated": pa.array(bars.truncated),
        "next_step_state": pa.array([tq.STEP_STATES[s] for s in bars.next_step_state], type=pa.string()),
        "missing_nominal_intervals_after": pa.array([int(m) if m >= 0 else None for m in bars.missing_nominal_bars_after], type=pa.int32()),
        "sample_eligible": pa.array(mask.eligible),
        "ineligibility_reasons": pa.array([list(mask.reasons(i)) for i in range(n)], type=pa.list_(pa.string())),
        "eligible_support_through": pa.array(mask.support_through.astype(np.int32)),
    }
    for j, r in enumerate(roles, start=1):
        cols[f"origin_{j}_role"] = pa.array([str(x) for x in r], type=pa.string())
    return pa.table(cols)


def content_digest(table: pa.Table) -> str:
    """Library-version-independent digest of the mask CONTENT."""
    canon = json.dumps({"columns": table.column_names, "rows": table.to_pydict()},
                       sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def materialize(fd_root: Path = FD_ROOT, predictor_root: Path = DEFAULT_PREDICTOR_ROOT,
                params: tq.EligibilityParams | None = None) -> tuple[dict, bytes, dict]:
    params = params or tq.EligibilityParams()
    if params.defects():
        raise tq.ParameterRefusal(params.defects())
    roots = {"financial-data": Path(fd_root), "predictor": Path(predictor_root)}

    # 1. read + verify EVERY source before parsing any
    raw: dict[str, bytes] = {}
    bound: dict[str, dict[str, Any]] = {}
    for s in SOURCES:
        data, digest = read_once(roots[s.root_id] / s.relative_path, s.expected_sha256)
        raw[s.name] = data
        bound[s.name] = {"root_id": s.root_id, "relative_path": s.relative_path,
                         "sha256": digest, "bytes": len(data),
                         "digest_check": "VERIFIED_AGAINST_PINNED_DIGEST"}

    # 2. parse the verified bytes
    v1 = json.loads(raw["v1_contract"].decode("utf-8"))
    csv = pd.read_csv(io.BytesIO(raw["model_ready_csv"]),
                      usecols=["DATE_TIME"] + [c for c, _ in OHLCV],
                      dtype={"DATE_TIME": str}, float_precision="round_trip")
    par = pq.read_table(pa.BufferReader(raw["candidate_source_parquet"]))

    # 3. v1 binding checks
    contract = v1["contract"]
    if contract.get("contract_id") != V1_CONTRACT_ID:
        raise Refusal("v1 contract id mismatch")
    if contract.get("dataset_sha256") != bound["model_ready_csv"]["sha256"]:
        raise Refusal("v1 contract does not govern these CSV bytes")
    if ta.validate_contract(contract):
        raise Refusal(f"v1 contract invalid: {ta.validate_contract(contract)}")
    if v1["self_digest"]["value"] != self_digest(v1)["value"]:
        raise Refusal("v1 self digest does not verify")

    # 4. CSV rows -> source bars (DATE_TIME == open time), exact match
    pat = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
    if not csv["DATE_TIME"].map(lambda s: bool(pat.match(s))).all():
        raise Refusal("DATE_TIME values not in 'YYYY-MM-DD HH:MM:SS' form")
    dt = pd.to_datetime(csv["DATE_TIME"], format="%Y-%m-%d %H:%M:%S", utc=True)
    csv_ms = ((dt - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)).to_numpy(np.int64)
    open_all = _ms_column(par, "timestamp")
    close_all = _ms_column(par, "close_time")
    idx = pd.Index(open_all).get_indexer(csv_ms)
    if (idx < 0).any():
        raise Refusal(f"{int((idx < 0).sum())} CSV rows have no source bar")
    for c_csv, c_par in OHLCV:
        if not np.array_equal(csv[c_csv].to_numpy(np.float64), par.column(c_par).to_numpy()[idx]):
            raise Refusal(f"CSV {c_csv} differs from source parquet")
    open_ms, close_ms = open_all[idx], close_all[idx]

    # 5. layers + mask + origins (the dataset timeline is the CSV rows only)
    bars = tq.evaluate_bars(contract, open_ms.tolist(), close_ms.tolist(),
                            observed_sha256=bound["model_ready_csv"]["sha256"], grid_anchor_ms=0)
    mask = tq.sample_eligibility(bars, params)
    roles, origins = tq.rolling_origins(bars, mask, params)
    summary = tq.summarize(bars, mask)
    propagation = tq.event_propagation(bars, mask, params)

    # 6. cross-check against v1's published structure
    s1 = v1["source_bar_structure"]
    csv_trunc_v1 = sorted(t["open_time_ms"] for t in s1["truncated_bars"] if t["in_model_ready_csv"])
    csv_gaps_v1 = sorted(g["previous_open_time_utc"] for g in s1["gaps"]
                         if g["previous_bar_in_model_ready_csv"] and g["next_bar_in_model_ready_csv"])
    trunc_here = sorted(int(x) for x in bars.open_ms[bars.truncated])
    gaps_here = sorted(e["previous_open_time_utc"] for e in propagation["gap_events"])
    cross = {
        "v1_truncated_bars_total": s1["truncated_bars_total"],
        "v1_truncated_bars_in_model_ready_csv": s1["truncated_bars_in_model_ready_csv"],
        "truncated_bars_in_dataset_recomputed": len(trunc_here),
        "truncated_open_times_equal_v1": trunc_here == csv_trunc_v1,
        "v1_gaps_greater_than_nominal_total": s1["gaps_greater_than_nominal_total"],
        "gaps_inside_dataset_recomputed": len(gaps_here),
        "gap_positions_equal_v1": gaps_here == csv_gaps_v1,
        "truncated_bars_outside_dataset": [
            {"open_time_utc": t["open_time_utc"], "effect": "NONE: before the first CSV row; the sample timeline is the CSV rows"}
            for t in s1["truncated_bars"] if not t["in_model_ready_csv"]],
    }
    if not (cross["truncated_open_times_equal_v1"] and cross["gap_positions_equal_v1"]):
        raise Refusal(f"recomputed bar structure disagrees with v1: {cross}")

    # 7. mask bytes
    table = mask_table(bars, mask, roles)
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="snappy")
    mask_bytes = sink.getvalue().to_pybytes()

    schema = tq.schema_document()
    schema["self_digest"] = self_digest(schema)

    doc = {
        "artifact": "ETH_H4_TEMPORAL_CONTRACT.v2",
        "contract_id": CONTRACT_ID,
        "order_items": ["C98", "C99"],
        "supersedes": {
            "artifact": "ETH_H4_TEMPORAL_CONTRACT.v1", "contract_id": V1_CONTRACT_ID,
            "root_id": "financial-data", "relative_path": SOURCES[2].relative_path,
            "sha256": bound["v1_contract"]["sha256"],
            "self_digest": v1["self_digest"]["value"],
            "disposition": "PRESERVED_BYTE_FOR_BYTE; read, never written. v1 remains the governing AVAILABILITY contract; v2 adds completeness, regularity and eligibility.",
            "auditor_acceptance_scope": "AVAILABILITY only. Truncated bars and gaps do not contradict per-row availability but forbid treating every pair of rows as a regular H4 horizon."},
        "schema": {"id": tq.SCHEMA_ID, "root_id": "financial-data",
                   "relative_path": f"features/census/{SCHEMA_NAME}",
                   "self_digest": schema["self_digest"]["value"]},
        "producer": {"root_id": "financial-data",
                     "relative_path": "_scripts/materialize_eth_h4_temporal_quality.py",
                     "library": "_scripts/temporal_quality.py",
                     "availability_library": "_scripts/temporal_availability.py",
                     "byte_discipline": "Each source opened once, read into memory, hashed, compared with its pinned digest, parsed from that same buffer. All digests verified before any parse."},
        "bound_files": bound,
        "availability_contract": contract,
        "dataset": {"dataset_id": contract["dataset_id"],
                    "sample_timeline": "The 18,085-row CSV only; the 252 source bars before its first row are not part of any window.",
                    "rows": bars.n,
                    "first_open_time_utc": tq._iso(bars.open_ms[0]),
                    "last_open_time_utc": tq._iso(bars.open_ms[-1]),
                    "grid_anchor_ms": 0, "nominal_bar_seconds": contract["nominal_bar_seconds"],
                    "bar_close_time_convention": contract["bar_close_time_convention"]},
        "parameters": params.to_dict(),
        "parameter_provenance": {
            "from_design_draft": ["model_lookback_bars", "max_operator_warmup_bars",
                                  "target_horizon_nominal_bars", "n_rolling_origins",
                                  "test_block_bars", "embargo_bars", "development_window",
                                  "inner_validation_fraction"],
            "not_in_design_draft": {"inner_validation_embargo_bars": "Default 0 (purge only). The draft states no embargo between inner train and validation."}},
        "layers": schema["x-layers"],
        "definitions": {
            "truncated_bar": "close_time - open_time < nominal_ms - 1 (INCLUSIVE_LAST_MILLISECOND).",
            "gap": "next observed open - open > nominal_ms; the intervals in between are ABSENT, never filled.",
            "next_bar": "The next NOMINAL interval open_t + nominal_ms. If no row has that open time the target is absent (TARGET_NOMINAL_BAR_ABSENT); the next observed row is never substituted.",
            "sample_ineligible_if": "its lookback, operator window or target contains a truncated bar, an unavailable bar, an absent nominal interval (gap), or reaches before the first row / after the last row.",
            "prefix_invariance": schema["x-prefix-invariance"],
        },
        "bar_layer_summary": summary["bars"],
        "sample_summary": summary["samples"],
        "propagation": propagation,
        "v1_cross_check": cross,
        "rolling_origins": {"rule": schema["x-rolling-origin-rule"], "origins": origins},
        "mask_artifact": {
            "root_id": "financial-data", "relative_path": f"features/census/{MASK_NAME}",
            "format": "parquet (snappy)", "sha256": hashlib.sha256(mask_bytes).hexdigest(),
            "bytes": len(mask_bytes), "rows": table.num_rows, "columns": table.column_names,
            "content_sha256": content_digest(table),
            "content_digest_rule": "sha256 of json.dumps({'columns': names, 'rows': table.to_pydict()}, sort_keys=True, separators=(',', ':'))",
            "format_justification": "18,085 rows x per-row reason lists and per-origin roles; parquet keeps typed nulls and list<string> reasons; the JSON binds it by sha256 and by a library-independent content digest."},
        "gates": {
            "E5a": {"status": v1["gates"]["E5a"]["status"], "source": "v1, unchanged"},
            "E5b": {"status": v1["gates"]["E5b"]["status"], "source": "v1, unchanged"},
            "note": "v2 changes no gate. Eligibility is a sample-level screen constraint, not an availability verdict."},
    }
    doc["self_digest"] = self_digest(doc)
    for d in (schema, doc):
        text = json.dumps(d)
        if "/home/" in text or str(Path.home()) in text:
            raise Refusal("absolute home-directory path in published document")
    return doc, mask_bytes, schema


def write_json(doc: dict, path: Path) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--financial-data-root", type=Path, default=FD_ROOT)
    ap.add_argument("--predictor-root", type=Path, default=DEFAULT_PREDICTOR_ROOT)
    ap.add_argument("--out-dir", type=Path, default=FD_ROOT / "features/census")
    dflt = tq.EligibilityParams()
    for k, v in dflt.to_dict().items():
        ap.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)
    a = ap.parse_args(argv)
    params = tq.EligibilityParams(**{k: getattr(a, k) for k in dflt.to_dict()})
    doc, mask_bytes, schema = materialize(a.financial_data_root, a.predictor_root, params)
    for name in (SCHEMA_NAME, MASK_NAME, CONTRACT_NAME):
        if (a.out_dir / name) == (FD_ROOT / SOURCES[2].relative_path):
            raise Refusal("refusing to write over v1")
    write_json(schema, a.out_dir / SCHEMA_NAME)
    with open(a.out_dir / MASK_NAME, "wb") as fh:
        fh.write(mask_bytes)
    write_json(doc, a.out_dir / CONTRACT_NAME)
    s = doc["sample_summary"]
    print(json.dumps({"samples": s["total"], "eligible": s["eligible"], "ineligible": s["ineligible"],
                      "origins": [(o["origin"], o["status"], o.get("eligible_sample_counts")) for o in doc["rolling_origins"]["origins"]],
                      "mask_sha256": doc["mask_artifact"]["sha256"],
                      "self_digest": doc["self_digest"]["value"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
