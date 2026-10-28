"""C114 materializer: ETH H4 SUCCESSOR temporal quality contract v3 + mask.

Governs the Stage 2.2 rerun SUCCESSOR dataset
``financial_data.project3.ethusdt_4h_tech_stat.model_ready.successor_stage22_rerun.v1``
(parquet sha256 427a754b...), NOT the historical ``...model_ready.v1`` CSV
that ETH_H4_TEMPORAL_CONTRACT.v1/v2 govern. The historical dataset id and the
historical contract digests are never used as this contract's identity; the
availability PARAMETERS (nominal bar seconds, close-time convention, grid
anchor, timestamp semantics) are carried from v2 and declared as parameter
provenance only.

Byte discipline (same as v2): every source is opened exactly once, read into
memory, hashed, compared with its pinned digest, and parsed from that same
buffer. All digests are verified before anything is parsed.

Writes (write-once, refuses if either output exists):
  features/census/ETH_H4_SUCCESSOR_TEMPORAL_CONTRACT.v3.json
  features/census/ETH_H4_SUCCESSOR_SAMPLE_ELIGIBILITY_MASK.v1.parquet

Usage:
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 \
    python _scripts/materialize_eth_h4_successor_temporal_quality.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import temporal_availability as ta  # noqa: E402
import temporal_quality as tq  # noqa: E402

FD_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUCCESSORS_ROOT = Path.home() / ".local/state/crispdm-successors"

SUCCESSOR_DATASET_ID = ("financial_data.project3.ethusdt_4h_tech_stat.model_ready."
                        "successor_stage22_rerun.v1")
SUCCESSOR_DATASET_SHA256 = "427a754ba3774e381e4f1353690b997d4e0ca89bf4ce6439ff2f8d651fd16d7c"
SUCCESSOR_ROOT_ID = "crispdm-successors/eth_h4_stage22_rerun_v1"
HISTORICAL_DATASET_ID = "financial_data.project3.ethusdt_4h_tech_stat.model_ready.v1"
HISTORICAL_DATASET_SHA256 = "1b447c66e68495e826c53e2ab2b08ecd3922c8fdc735747628f8d0435ebe440f"
HISTORICAL_CONTRACT_IDS = ("financial_data.eth_h4_temporal_contract.v1",
                           "financial_data.eth_h4_temporal_contract.v2")
V2_CONTRACT_ID = "financial_data.eth_h4_temporal_contract.v2"

CONTRACT_ID = "financial_data.eth_h4_successor_temporal_contract.v3"
CONTRACT_ARTIFACT = "ETH_H4_SUCCESSOR_TEMPORAL_CONTRACT.v3"
CONTRACT_NAME = CONTRACT_ARTIFACT + ".json"
MASK_NAME = "ETH_H4_SUCCESSOR_SAMPLE_ELIGIBILITY_MASK.v1.parquet"

EXPECTED = {"rows": 18085, "truncated_inside": 20, "truncated_outside": 1, "gaps_inside": 8}
OHLCV = (("OPEN", "open"), ("HIGH", "high"), ("LOW", "low"),
         ("CLOSE", "close"), ("VOLUME", "volume"))


@dataclass(frozen=True)
class Source:
    name: str
    root_id: str
    relative_path: str
    expected_sha256: str


SOURCES = (
    Source("successor_parquet", SUCCESSOR_ROOT_ID,
           "successor/ethusdt_4h_tech_stat_model_ready_successor.parquet",
           SUCCESSOR_DATASET_SHA256),
    Source("raw_ohlcv_parquet", SUCCESSOR_ROOT_ID, "inputs/raw_ohlcv.parquet",
           "37321161d3e0d372abd0c3a0cc867ed4b2faf1fdf1e4569d55da6f6a1a1df099"),
    Source("pre_run_manifest", SUCCESSOR_ROOT_ID, "PRE_RUN_MANIFEST.json",
           "18b4e8fd1565df322de2f5594bbdbdb88f571955fa7f4e142e93a129faac069a"),
    Source("post_run_manifest", SUCCESSOR_ROOT_ID, "POST_RUN_MANIFEST.json",
           "300b9610811cdc6ef9b19db0e655c2a4c1b6b716d8bad8ea04750bc75c4c6aa9"),
    Source("feature_dag_v4", "financial-data", "features/census/FEATURE_DAG.v4.json",
           "4fa4d1341e51fc4ff0576834fb0455297f177ec319ecd05b3429fa74c8249204"),
    Source("binding_manifest_v2", "financial-data",
           "features/census/PRODUCER_BINDING_MANIFEST.v2.json",
           "7d2b7d38c2e3be3e99f3aa06606cbc36825cd653974f8d4068f215de618f34bc"),
    Source("historical_contract_v2", "financial-data",
           "features/census/ETH_H4_TEMPORAL_CONTRACT.v2.json",
           "43b9f2b6650205ec30c4cd000b174ad5db9b321c6efcd356aaf1398904f4d6f1"),
    Source("historical_mask_v1", "financial-data",
           "features/census/ETH_H4_SAMPLE_ELIGIBILITY_MASK.v1.parquet",
           "b5c2e3b5811c11c4bdf32c7736037ecc68bff50f0edf59e40a0bfdc185939e85"),
)
PRE_MANIFEST_SHA = "9820d32d8747309d5e6c667df19966d44e042391d42f2b9fa6750c4a47f9222c"
POST_MANIFEST_SHA = "7971157d03d420d1bc32a0c4fe7cd40b8641c1c3c5ab8bd4533e469f61700624"
HOME_RE = re.compile(r"(/home|/Users|/root)/")


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
    """Identical canonicalization to ETH_H4_TEMPORAL_CONTRACT.v2."""
    body = {k: v for k, v in doc.items() if k != "self_digest"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
    return {"algorithm": "sha256",
            "canonicalization": "json.dumps(document_without_self_digest, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')",
            "value": hashlib.sha256(canon).hexdigest()}


def sha_obj(o: Any) -> str:
    """The digest rule of FEATURE_DAG.v4 / PRODUCER_BINDING_MANIFEST.v2."""
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def content_digest(table: pa.Table) -> str:
    """Library-version-independent digest of the mask CONTENT (v2 rule)."""
    canon = json.dumps({"columns": table.column_names, "rows": table.to_pydict()},
                       sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def _ms_column(table: pa.Table, name: str) -> np.ndarray:
    col = table.column(name)
    t = col.type
    if not (pa.types.is_timestamp(t) and t.unit == "ms" and t.tz == "UTC"):
        raise Refusal(f"{name}: expected timestamp[ms, tz=UTC], got {t}")
    if col.null_count:
        raise Refusal(f"{name}: {col.null_count} nulls")
    return col.cast(pa.int64()).to_numpy()


def availability_contract(dataset_id: str, dataset_sha256: str, params_source: dict) -> dict:
    """Availability contract of THIS dataset. Parameters from v2, identity own."""
    return {
        "contract_id": CONTRACT_ID,
        "dataset_id": dataset_id,
        "dataset_sha256": dataset_sha256,
        "timestamp_semantics": params_source["timestamp_semantics"],
        "information_complete_not_before": params_source["information_complete_not_before"],
        "nominal_bar_seconds": params_source["nominal_bar_seconds"],
        "bar_close_time_convention": params_source["bar_close_time_convention"],
        "provider_delivery_latency": {
            "status": "UNOBSERVED", "seconds": None,
            "evidence": "No artifact records when the provider delivered any bar of the raw input; no latency was observed or declared. UNOBSERVED is not zero."},
        "provenance": {
            "status": "EVIDENCED_BY_EXACT_MATCH_WITH_DECLARED_UPSTREAM",
            "basis": ("PRE_RUN_MANIFEST (manifest_sha256 9820d32d...) declares inputs.raw_ohlcv "
                      "sha256 37321161... as the rerun input and POST_RUN_MANIFEST (7971157d...) "
                      "records successor_dataset_sha256 427a754b... produced from input_sha256 "
                      "37321161...; every successor row's DATE_TIME equals a raw `timestamp` "
                      "exactly and OPEN/HIGH/LOW/CLOSE/VOLUME equal raw open/high/low/close/volume "
                      "exactly (float64 array equality). Per-bar close times are the raw "
                      "`close_time` of the matched bar.")},
    }


def identity_defects(doc: dict) -> list[str]:
    """A successor contract must not carry historical identity anywhere it names itself."""
    d = []
    ac = doc.get("availability_contract", {})
    ds = doc.get("dataset", {})
    if doc.get("contract_id") in HISTORICAL_CONTRACT_IDS or ac.get("contract_id") in HISTORICAL_CONTRACT_IDS:
        d.append("HISTORICAL_CONTRACT_ID_AS_IDENTITY")
    for where, rec in (("availability_contract", ac), ("dataset", ds)):
        if rec.get("dataset_id") == HISTORICAL_DATASET_ID:
            d.append(f"HISTORICAL_DATASET_ID_TRANSPLANTED:{where}")
        if rec.get("dataset_sha256") == HISTORICAL_DATASET_SHA256:
            d.append(f"HISTORICAL_DATASET_SHA256_TRANSPLANTED:{where}")
        if rec.get("dataset_id") != SUCCESSOR_DATASET_ID:
            d.append(f"DATASET_ID_NOT_SUCCESSOR:{where}")
        if rec.get("dataset_sha256") != SUCCESSOR_DATASET_SHA256:
            d.append(f"DATASET_SHA256_NOT_SUCCESSOR:{where}")
    ma = doc.get("mask_artifact", {})
    if ma and (ma.get("dataset_id") != SUCCESSOR_DATASET_ID or ma.get("dataset_sha256") != SUCCESSOR_DATASET_SHA256):
        d.append("MASK_IDENTITY_NOT_SUCCESSOR")
    return d


def join_successor_to_raw(succ: pa.Table, raw: pa.Table) -> dict[str, Any]:
    """Exact join DATE_TIME == raw timestamp. Refuses on a missing raw bar or any
    OHLCV difference. Never fills, never substitutes a neighbouring bar."""
    s_ms = _ms_column(succ, "DATE_TIME")
    open_all = _ms_column(raw, "timestamp")
    close_all = _ms_column(raw, "close_time")
    if len(np.unique(open_all)) != len(open_all):
        raise Refusal("raw timestamps are not unique")
    idx = pd_index_get(open_all, s_ms)
    if (idx < 0).any():
        raise Refusal(f"{int((idx < 0).sum())} successor rows have no raw bar")
    for c_s, c_r in OHLCV:
        a = succ.column(c_s).to_numpy()
        b = raw.column(c_r).to_numpy()[idx]
        if a.dtype != np.float64 or not np.array_equal(a, b.astype(np.float64)):
            raise Refusal(f"successor {c_s} differs from raw {c_r}")
    return {"idx": idx, "open_ms": open_all[idx], "close_ms": close_all[idx],
            "raw_open_ms": open_all, "raw_close_ms": close_all}


def pd_index_get(haystack: np.ndarray, needles: np.ndarray) -> np.ndarray:
    order = np.argsort(haystack, kind="stable")
    sh = haystack[order]
    pos = np.searchsorted(sh, needles)
    pos_c = np.minimum(pos, len(sh) - 1)
    hit = (pos < len(sh)) & (sh[pos_c] == needles)
    return np.where(hit, order[pos_c], -1).astype(np.int64)


def mask_table(bars: tq.BarLayers, mask: tq.SampleMask, roles: list[np.ndarray],
               identity: dict[str, str]) -> pa.Table:
    """Same columns as mask v1; the dataset identity lives in the schema metadata."""
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
    t = pa.table(cols)
    return t.replace_schema_metadata({k: v for k, v in identity.items()})


def _origin_boundaries(origins: list[dict]) -> list[dict]:
    keep = []
    for o in origins:
        keep.append({"origin": o["origin"], "status": o["status"],
                     "development_region": o.get("development_region"),
                     "embargo": o.get("embargo"), "test_block": o.get("test_block")})
    return keep


def _verify_bindings(dag: dict, man: dict, bound: dict) -> dict:
    if dag.get("schema") != "financial_data.feature_dag.v4":
        raise Refusal("FEATURE_DAG.v4 schema id mismatch")
    if sha_obj({k: v for k, v in dag.items() if k != "dag_sha256"}) != dag.get("dag_sha256"):
        raise Refusal("FEATURE_DAG.v4 dag_sha256 does not verify")
    if man.get("schema") != "financial_data.producer_binding_manifest.v2":
        raise Refusal("PRODUCER_BINDING_MANIFEST.v2 schema id mismatch")
    if sha_obj({k: v for k, v in man.items() if k not in ("derived_at", "manifest_sha256")}) != man.get("manifest_sha256"):
        raise Refusal("PRODUCER_BINDING_MANIFEST.v2 manifest_sha256 does not verify")
    if dag.get("binding_manifest_sha256") != man["manifest_sha256"]:
        raise Refusal("DAG binding_manifest_sha256 != manifest_sha256")
    if dag.get("successor_dataset_id") != SUCCESSOR_DATASET_ID:
        raise Refusal("DAG successor_dataset_id is not the successor")
    if dag.get("successor_root_id") != SUCCESSOR_ROOT_ID:
        raise Refusal("DAG successor_root_id mismatch")
    if man.get("successor", {}).get("dataset_id") != SUCCESSOR_DATASET_ID or \
            man["successor"].get("dataset_sha256") != SUCCESSOR_DATASET_SHA256:
        raise Refusal("binding manifest successor identity mismatch")
    for b in man["bindings"]:
        if b.get("dataset_id") != SUCCESSOR_DATASET_ID or b.get("dataset_sha256") != SUCCESSOR_DATASET_SHA256:
            raise Refusal(f"binding {b.get('output_column')} does not bind the successor bytes")
    for n in dag["nodes"]:
        if n.get("dataset_id") != SUCCESSOR_DATASET_ID:
            raise Refusal(f"DAG node {n.get('column')} is not a successor node")
    active = [n["column"] for n in dag["nodes"] if n["class"] == "CAUSAL_ACTIVE"]
    bound_cols = [b["output_column"] for b in man["bindings"]]
    if len(set(active)) != len(active) or set(active) != set(bound_cols) or len(bound_cols) != len(set(bound_cols)):
        raise Refusal("DAG CAUSAL_ACTIVE columns and manifest bindings disagree or repeat")
    return {"feature_dag_v4": {"file_sha256": bound["feature_dag_v4"]["sha256"],
                               "dag_sha256": dag["dag_sha256"], "dag_sha256_verified": True,
                               "binding_manifest_sha256": dag["binding_manifest_sha256"],
                               "successor_dataset_id": dag["successor_dataset_id"],
                               "causal_active_columns": len(active)},
            "binding_manifest_v2": {"file_sha256": bound["binding_manifest_v2"]["sha256"],
                                    "manifest_sha256": man["manifest_sha256"],
                                    "manifest_sha256_verified": True,
                                    "bindings": len(man["bindings"]),
                                    "every_binding_dataset_id_and_sha256_equal_successor": True},
            "rule": "dag_sha256 = sha256(json.dumps(dag_without_dag_sha256, sort_keys=True, default=str)); manifest_sha256 = sha256(json.dumps(manifest_without_derived_at_and_manifest_sha256, sort_keys=True, default=str))",
            "active_columns": active}


def materialize(fd_root: Path = FD_ROOT, successors_root: Path = DEFAULT_SUCCESSORS_ROOT,
                params: tq.EligibilityParams | None = None,
                dataset_id: str = SUCCESSOR_DATASET_ID,
                expected: dict | None = None) -> tuple[dict, bytes]:
    params = params or tq.EligibilityParams()
    expected = EXPECTED if expected is None else expected
    if params.defects():
        raise tq.ParameterRefusal(params.defects())
    roots = {"financial-data": Path(fd_root),
             SUCCESSOR_ROOT_ID: Path(successors_root) / "eth_h4_stage22_rerun_v1"}

    # 1. read + verify EVERY source before parsing any
    raw_bytes: dict[str, bytes] = {}
    bound: dict[str, dict[str, Any]] = {}
    for s in SOURCES:
        data, digest = read_once(roots[s.root_id] / s.relative_path, s.expected_sha256)
        raw_bytes[s.name] = data
        bound[s.name] = {"root_id": s.root_id, "relative_path": s.relative_path,
                         "sha256": digest, "bytes": len(data),
                         "digest_check": "VERIFIED_AGAINST_PINNED_DIGEST"}

    # 2. parse verified bytes
    succ = pq.read_table(pa.BufferReader(raw_bytes["successor_parquet"]))
    raw = pq.read_table(pa.BufferReader(raw_bytes["raw_ohlcv_parquet"]))
    pre = json.loads(raw_bytes["pre_run_manifest"].decode("utf-8"))
    post = json.loads(raw_bytes["post_run_manifest"].decode("utf-8"))
    dag = json.loads(raw_bytes["feature_dag_v4"].decode("utf-8"))
    man = json.loads(raw_bytes["binding_manifest_v2"].decode("utf-8"))
    v2 = json.loads(raw_bytes["historical_contract_v2"].decode("utf-8"))
    v2_mask = pq.read_table(pa.BufferReader(raw_bytes["historical_mask_v1"]))

    # 3. identity + binding checks
    if dataset_id != SUCCESSOR_DATASET_ID:
        raise Refusal(f"dataset id {dataset_id!r} is not the successor dataset id")
    if pre.get("manifest_sha256") != PRE_MANIFEST_SHA or post.get("manifest_sha256") != POST_MANIFEST_SHA:
        raise Refusal("successor run manifest digests do not match")
    if post.get("pre_run_manifest_sha256") != PRE_MANIFEST_SHA:
        raise Refusal("POST manifest does not chain to PRE")
    if pre.get("successor_dataset_id") != SUCCESSOR_DATASET_ID or post.get("successor_dataset_id") != SUCCESSOR_DATASET_ID:
        raise Refusal("run manifests name another successor dataset")
    if post.get("successor_dataset_sha256") != bound["successor_parquet"]["sha256"]:
        raise Refusal("POST manifest successor sha256 != successor bytes")
    if pre["inputs"]["raw_ohlcv"]["sha256"] != bound["raw_ohlcv_parquet"]["sha256"] or \
            post.get("input_sha256") != bound["raw_ohlcv_parquet"]["sha256"]:
        raise Refusal("run manifests do not declare these raw bytes as input")
    bindings = _verify_bindings(dag, man, bound)
    v2_ac = v2["availability_contract"]
    if v2.get("contract_id") != V2_CONTRACT_ID or v2["self_digest"]["value"] != self_digest(v2)["value"]:
        raise Refusal("historical v2 contract id or self digest does not verify")
    if v2["mask_artifact"]["sha256"] != bound["historical_mask_v1"]["sha256"]:
        raise Refusal("historical mask bytes are not the mask v2 binds")
    if v2_ac["dataset_id"] != HISTORICAL_DATASET_ID:
        raise Refusal("v2 no longer names the historical dataset")

    # 4. schema of the successor
    names = succ.column_names
    if names[0] != "DATE_TIME" or len(names) != 90 or len(set(names)) != 90:
        raise Refusal("successor columns are not DATE_TIME + 89 unique features")
    if set(names[1:]) != set(bindings["active_columns"]):
        raise Refusal("successor feature columns != DAG CAUSAL_ACTIVE columns")
    if succ.num_rows != expected["rows"]:
        raise Refusal(f"successor rows {succ.num_rows} != {expected['rows']}")

    # 5. exact join to raw; close times from raw close_time
    j = join_successor_to_raw(succ, raw)
    ac = availability_contract(dataset_id, bound["successor_parquet"]["sha256"], v2_ac)
    if ta.validate_contract(ac):
        raise Refusal(f"availability contract invalid: {ta.validate_contract(ac)}")

    # 6. layers + mask + origins on the successor timeline (rows only)
    bars = tq.evaluate_bars(ac, j["open_ms"].tolist(), j["close_ms"].tolist(),
                            observed_sha256=bound["successor_parquet"]["sha256"],
                            grid_anchor_ms=int(v2["dataset"]["grid_anchor_ms"]))
    mask = tq.sample_eligibility(bars, params)
    roles, origins = tq.rolling_origins(bars, mask, params)
    summary = tq.summarize(bars, mask)
    propagation = tq.event_propagation(bars, mask, params)

    # 7. raw bars outside the successor timeline
    full = ac["nominal_bar_seconds"] * 1000 - (1 if ac["bar_close_time_convention"] == "INCLUSIVE_LAST_MILLISECOND" else 0)
    raw_o, raw_c = j["raw_open_ms"], j["raw_close_ms"]
    in_succ = np.zeros(len(raw_o), dtype=bool)
    in_succ[j["idx"]] = True
    raw_trunc = (raw_c - raw_o) < full
    first_o, last_o = int(bars.open_ms[0]), int(bars.open_ms[-1])
    outside = []
    for i in np.flatnonzero(raw_trunc & ~in_succ):
        o = int(raw_o[i])
        where = "BEFORE_FIRST_SUCCESSOR_ROW" if o < first_o else ("AFTER_LAST_SUCCESSOR_ROW" if o > last_o else "BETWEEN_SUCCESSOR_ROWS")
        outside.append({"raw_row_index": int(i), "open_time_ms": o, "open_time_utc": tq._iso(o),
                        "span_ms": int(raw_c[i] - raw_o[i]), "position": where,
                        "effect": "NONE: not a row of the successor; the sample timeline is the successor rows only"
                        if where != "BETWEEN_SUCCESSOR_ROWS" else "ABSENT_ROW_INSIDE_TIMELINE"})
    raw_steps = np.diff(raw_o)
    raw_gaps = int((raw_steps > ac["nominal_bar_seconds"] * 1000).sum())
    trunc_inside = int(bars.truncated.sum())
    gaps_inside = int((bars.next_step_state == 1).sum())
    counts = {"rows": bars.n, "truncated_inside": trunc_inside,
              "truncated_outside": len(outside), "gaps_inside": gaps_inside}
    if counts != expected:
        raise Refusal(f"measured bar structure {counts} != expected {expected}")
    if any(o["position"] != "BEFORE_FIRST_SUCCESSOR_ROW" for o in outside):
        raise Refusal("a truncated raw bar outside the successor lies inside its span")

    # 8. mask bytes with successor identity in the schema metadata
    identity = {"dataset_id": dataset_id, "dataset_sha256": bound["successor_parquet"]["sha256"],
                "contract_id": CONTRACT_ID}
    table = mask_table(bars, mask, roles, identity)
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="snappy")
    mask_bytes = sink.getvalue().to_pybytes()

    # 9. GEOMETRY comparison with v2 (reported, never forced)
    v2p, v2m = v2["propagation"], v2_mask.to_pydict()
    t_now = table.to_pydict()
    trunc_now = sorted(e["open_time_utc"] for e in propagation["truncated_bar_events"])
    trunc_v2 = sorted(e["open_time_utc"] for e in v2p["truncated_bar_events"])
    gaps_now = sorted((e["previous_open_time_utc"], e["next_open_time_utc"]) for e in propagation["gap_events"])
    gaps_v2 = sorted((e["previous_open_time_utc"], e["next_open_time_utc"]) for e in v2p["gap_events"])
    same_rows = t_now["open_time_ms"] == v2m["open_time_ms"]
    geometry = {
        "row_open_times_equal": same_rows,
        "row_close_times_equal": t_now["close_time_ms"] == v2m["close_time_ms"],
        "truncated_open_times_equal": trunc_now == trunc_v2,
        "gap_positions_equal": gaps_now == gaps_v2,
        "per_row_eligibility_vector_equal": same_rows and t_now["sample_eligible"] == v2m["sample_eligible"],
        "per_row_reasons_equal": same_rows and t_now["ineligibility_reasons"] == v2m["ineligibility_reasons"],
        "origin_boundaries_equal": _origin_boundaries(origins) == _origin_boundaries(v2["rolling_origins"]["origins"]),
        "origin_role_vectors_equal": same_rows and all(
            t_now[f"origin_{k}_role"] == v2m.get(f"origin_{k}_role") for k in range(1, len(roles) + 1)),
        "sample_summary_equal": summary["samples"] == v2["sample_summary"],
        "bar_layer_summary_equal": summary["bars"] == v2["bar_layer_summary"],
        "propagation_equal": propagation == v2p,
        "rolling_origin_reports_equal": origins == v2["rolling_origins"]["origins"],
        "parameters_equal": params.to_dict() == v2["parameters"],
        "mask_content_sha256_equal": content_digest(table) == v2["mask_artifact"]["content_sha256"],
    }
    comparison = {
        "kind": "GEOMETRY_EQUALITY_NOT_IDENTITY_EQUALITY",
        "against": {"artifact": "ETH_H4_TEMPORAL_CONTRACT.v2", "contract_id": V2_CONTRACT_ID,
                    "root_id": "financial-data",
                    "relative_path": "features/census/ETH_H4_TEMPORAL_CONTRACT.v2.json",
                    "sha256": bound["historical_contract_v2"]["sha256"],
                    "self_digest": v2["self_digest"]["value"],
                    "mask_sha256": bound["historical_mask_v1"]["sha256"]},
        "geometry": geometry,
        "geometry_all_equal": all(geometry.values()),
        "geometry_differences": sorted(k for k, v in geometry.items() if not v),
        "identity_equal": False,
        "identity": {
            "this_contract": {"contract_id": CONTRACT_ID, "dataset_id": dataset_id,
                              "dataset_sha256": bound["successor_parquet"]["sha256"]},
            "v2": {"contract_id": V2_CONTRACT_ID, "dataset_id": v2_ac["dataset_id"],
                   "dataset_sha256": v2_ac["dataset_sha256"]}},
        "statement": "Equal geometry means the successor rows carry the same bar timeline, truncations, gaps and eligibility as the historical rows. It does not make the datasets the same dataset: ids and byte digests differ, and nothing proven for one is transferred to the other.",
    }
    if comparison["identity"]["this_contract"]["dataset_id"] == comparison["identity"]["v2"]["dataset_id"] or \
            comparison["identity"]["this_contract"]["dataset_sha256"] == comparison["identity"]["v2"]["dataset_sha256"]:
        raise Refusal("successor identity equals historical identity")

    doc = {
        "artifact": CONTRACT_ARTIFACT,
        "contract_id": CONTRACT_ID,
        "order_items": ["C114"],
        "identity": {"dataset_id": dataset_id, "dataset_sha256": bound["successor_parquet"]["sha256"],
                     "contract_id": CONTRACT_ID,
                     "statement": "This contract's identity is the successor dataset. No historical dataset id or historical contract digest is part of it."},
        "producer": {"root_id": "financial-data",
                     "relative_path": "_scripts/materialize_eth_h4_successor_temporal_quality.py",
                     "library": "_scripts/temporal_quality.py",
                     "availability_library": "_scripts/temporal_availability.py",
                     "byte_discipline": "Each source opened once, read into memory, hashed, compared with its pinned digest, parsed from that same buffer. All digests verified before any parse.",
                     "write_policy": "write-once (O_CREAT|O_EXCL); refuses if either output exists"},
        "schema": {"id": tq.SCHEMA_ID, "root_id": "financial-data",
                   "relative_path": "features/census/TEMPORAL_QUALITY_SCHEMA.v1.json",
                   "note": "Same layer semantics and mask columns as v2; this contract names the successor in identity, supersedes nothing."},
        "bound_files": bound,
        "bindings": {k: v for k, v in bindings.items() if k != "active_columns"},
        "availability_contract": ac,
        "availability_parameter_provenance": {
            "parameters": ["timestamp_semantics", "information_complete_not_before",
                           "nominal_bar_seconds", "bar_close_time_convention", "grid_anchor_ms"],
            "carried_from": {"artifact": "ETH_H4_TEMPORAL_CONTRACT.v2",
                             "relative_path": "features/census/ETH_H4_TEMPORAL_CONTRACT.v2.json",
                             "sha256": bound["historical_contract_v2"]["sha256"],
                             "role": "PROVENANCE_OF_PARAMETERS_NOT_IDENTITY"},
            "values": {"timestamp_semantics": ac["timestamp_semantics"],
                       "information_complete_not_before": ac["information_complete_not_before"],
                       "nominal_bar_seconds": ac["nominal_bar_seconds"],
                       "bar_close_time_convention": ac["bar_close_time_convention"],
                       "grid_anchor_ms": int(v2["dataset"]["grid_anchor_ms"])},
            "applicability": "The successor's DATE_TIME and OHLCV equal the raw input bars exactly and close times are the raw close_time, i.e. the same bar convention v1/v2 established for these raw bytes."},
        "dataset": {"dataset_id": dataset_id,
                    "dataset_sha256": bound["successor_parquet"]["sha256"],
                    "root_id": SUCCESSOR_ROOT_ID,
                    "relative_path": SOURCES[0].relative_path,
                    "sample_timeline": f"The {bars.n}-row successor parquet only; the {int((~in_succ).sum())} raw bars not in it are not part of any window.",
                    "rows": bars.n,
                    "raw_input_rows": int(len(raw_o)),
                    "raw_rows_before_first_successor_row": int((raw_o < first_o).sum()),
                    "raw_rows_after_last_successor_row": int((raw_o > last_o).sum()),
                    "first_open_time_utc": tq._iso(first_o),
                    "last_open_time_utc": tq._iso(last_o),
                    "grid_anchor_ms": int(v2["dataset"]["grid_anchor_ms"]),
                    "nominal_bar_seconds": ac["nominal_bar_seconds"],
                    "bar_close_time_convention": ac["bar_close_time_convention"],
                    "join": "DATE_TIME == raw timestamp exactly; OHLCV float64 array-equal; close_time from raw"},
        "parameters": params.to_dict(),
        "parameter_provenance": {"eligibility_parameters_equal_v2": params.to_dict() == v2["parameters"],
                                 "source": "temporal_quality.EligibilityParams defaults (design draft values, as v2)"},
        "layers": tq.schema_document()["x-layers"],
        "definitions": v2["definitions"],
        "bar_structure": {
            "truncated_bars_inside_dataset": trunc_inside,
            "truncated_bars_outside_dataset": outside,
            "truncated_bars_outside_dataset_count": len(outside),
            "truncated_bars_in_raw_input_total": int(raw_trunc.sum()),
            "gaps_inside_dataset": gaps_inside,
            "gaps_in_raw_input_total": raw_gaps,
            "expected_counts_verified": expected,
            "gap_filling": "NONE: absent nominal intervals stay absent; no row is inserted, interpolated, or substituted by the next observed row"},
        "bar_layer_summary": summary["bars"],
        "sample_summary": summary["samples"],
        "propagation": propagation,
        "rolling_origins": {"rule": tq.schema_document()["x-rolling-origin-rule"], "origins": origins},
        "comparison_with_v2": comparison,
        "mask_artifact": {
            "root_id": "financial-data", "relative_path": f"features/census/{MASK_NAME}",
            "dataset_id": dataset_id, "dataset_sha256": bound["successor_parquet"]["sha256"],
            "format": "parquet (snappy)", "sha256": hashlib.sha256(mask_bytes).hexdigest(),
            "bytes": len(mask_bytes), "rows": table.num_rows, "columns": table.column_names,
            "schema_metadata": identity,
            "content_sha256": content_digest(table),
            "content_digest_rule": "sha256 of json.dumps({'columns': names, 'rows': table.to_pydict()}, sort_keys=True, separators=(',', ':'))"},
        "gates": {"E5a": {"status": "OPEN" if summary["bars"]["availability_status_counts"] == {"RESOLVED": bars.n} else "CLOSED",
                          "basis": "every successor row's causal information bound RESOLVED under this contract"},
                  "E5b": {"status": "CLOSED", "basis": "provider delivery latency UNOBSERVED"},
                  "note": "Eligibility is a sample-level screen constraint, not an availability verdict."},
    }
    defects = identity_defects(doc)
    if defects:
        raise Refusal(f"identity defects: {defects}")
    doc["self_digest"] = self_digest(doc)
    text = json.dumps(doc)
    if HOME_RE.search(text) or str(Path.home()) in text:
        raise Refusal("absolute home-directory path in published document")
    return doc, mask_bytes


def write_once(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def publish(doc: dict, mask_bytes: bytes, out_dir: Path) -> None:
    targets = [out_dir / MASK_NAME, out_dir / CONTRACT_NAME]
    existing = [p.name for p in targets if p.exists()]
    if existing:
        raise Refusal(f"write-once: outputs already exist: {existing}")
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if HOME_RE.search(text):
        raise Refusal("absolute home-directory path in published document")
    write_once(out_dir / MASK_NAME, mask_bytes)
    write_once(out_dir / CONTRACT_NAME, text.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--financial-data-root", type=Path, default=FD_ROOT)
    ap.add_argument("--successors-root", type=Path, default=DEFAULT_SUCCESSORS_ROOT)
    ap.add_argument("--out-dir", type=Path, default=FD_ROOT / "features/census")
    a = ap.parse_args(argv)
    doc, mask_bytes = materialize(a.financial_data_root, a.successors_root)
    publish(doc, mask_bytes, a.out_dir)
    s, c = doc["sample_summary"], doc["comparison_with_v2"]
    print(json.dumps({"rows": doc["dataset"]["rows"],
                      "truncated_inside": doc["bar_structure"]["truncated_bars_inside_dataset"],
                      "truncated_outside": doc["bar_structure"]["truncated_bars_outside_dataset_count"],
                      "gaps_inside": doc["bar_structure"]["gaps_inside_dataset"],
                      "eligible": s["eligible"], "ineligible": s["ineligible"],
                      "geometry": c["geometry"], "identity_equal": c["identity_equal"],
                      "mask_sha256": doc["mask_artifact"]["sha256"],
                      "self_digest": doc["self_digest"]["value"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
