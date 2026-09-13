"""C115: semantic census of the 89 CAUSAL_ACTIVE columns of the ETH H4 successor.

One row per column of FEATURE_DAG.v4 (successor dataset
``financial_data.project3.ethusdt_4h_tech_stat.model_ready.successor_stage22_rerun.v1``).
Every declared field carries evidence ``{"source", "sha256"}`` pointing at a
file whose bytes were hashed here. A field without evidence is ``UNKNOWN``
with evidence ``{"source": "NONE", "sha256": null}``; ``UNKNOWN`` EXCLUDES
the variable downstream.

Rules enforced by ``validate_census``:
* unit ``1`` only with a FORMULA PROOF: code expressions that appear
  verbatim in the named producer symbol of the verified producer file and
  show the value is a ratio / log-ratio / normalized statistic. A unit is
  never inferred from a column name. Price/volume-denominated columns stay
  ``UNKNOWN`` because no document read here states their currency or unit.
* license only from a license document for these bytes. None exists in the
  repository (see ``license_search``), so every license is ``UNKNOWN``.
* missing / sentinel policy only from producer or assembler code, with the
  observed non-finite counts of the bound bytes published alongside.

variable_id rule: ``sha256((dataset_id + "\\0" + column).encode("utf-8")).hexdigest()``.

Usage:
  CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 \
    python _scripts/build_eth_h4_successor_semantic_census.py
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

FD_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUCCESSORS_ROOT = Path.home() / ".local/state/crispdm-successors"

SCHEMA_ID = "financial_data.eth_h4_successor_semantic_census.v1"
CENSUS_NAME = "ETH_H4_SUCCESSOR_SEMANTIC_CENSUS.v1.json"
DATASET_ID = "financial_data.project3.ethusdt_4h_tech_stat.model_ready.successor_stage22_rerun.v1"
DATASET_SHA256 = "427a754ba3774e381e4f1353690b997d4e0ca89bf4ce6439ff2f8d651fd16d7c"
SUCC_ROOT_ID = "crispdm-successors/eth_h4_stage22_rerun_v1"
UNKNOWN = "UNKNOWN"
NONE_EVIDENCE = {"source": "NONE", "sha256": None}

ROW_KEYS = ("variable_id", "dataset_id", "dataset_sha256", "column", "physical_type",
            "semantic_type", "semantics", "role", "unit", "license", "license_source",
            "missing_policy", "sentinel_policy", "producer", "symbol", "lookback_bars",
            "evidence")
EVIDENCE_FIELDS = ("semantic_type", "role", "unit", "license", "missing_policy",
                   "sentinel_policy", "producer", "symbol", "lookback_bars", "physical_type")
ROLES = ("input_feature", "identifier", "excluded")

# logical key -> (root_id, relative_path, pinned sha256)
PINNED = {
    "successor_parquet": (SUCC_ROOT_ID, "successor/ethusdt_4h_tech_stat_model_ready_successor.parquet", DATASET_SHA256),
    "feature_dag_v4": ("financial-data", "features/census/FEATURE_DAG.v4.json",
                       "4fa4d1341e51fc4ff0576834fb0455297f177ec319ecd05b3429fa74c8249204"),
    "binding_manifest_v2": ("financial-data", "features/census/PRODUCER_BINDING_MANIFEST.v2.json",
                            "7d2b7d38c2e3be3e99f3aa06606cbc36825cd653974f8d4068f215de618f34bc"),
    "assembler": ("financial-data", "_scripts/assemble_eth_h4_model_ready_successor.py",
                  "864449b74968af06326baf1f39b62c23b7e0e72aaf1fc448769783ab70d5ff73"),
    "worker": ("financial-data", "_scripts/workers/stage22_trading_features_worker.py",
               "7495a0d974a7eb086eef0c11927b1c536946746ee3544ad82f6c256d1c6ee050"),
    "raw_data_dictionary": ("financial-data", "features/trading_asset_data/ethusdt/data_dictionary.md",
                            "04d3d4c0a8b8f1593d4d012786abacf72e539df43295d97ba7adb3992c24b4a6"),
    "raw_parquet_in_repo": ("financial-data", "features/trading_asset_data/ethusdt/4h.parquet",
                            "37321161d3e0d372abd0c3a0cc867ed4b2faf1fdf1e4569d55da6f6a1a1df099"),
}
# Files searched for a license of these bytes (hashed, not pinned: evidence of absence).
LICENSE_SEARCH = (
    ("financial-data", "features/trading_asset_data/ethusdt/provenance.json"),
    ("financial-data", "features/trading_asset_data/ethusdt/README.md"),
    ("financial-data", "features/trading_asset_data/ethusdt/data_dictionary.md"),
    ("financial-data", "market_data/crypto/spot_top50/ethusdt/provenance.json"),
    ("financial-data", "market_data/crypto/spot_top50/ethusdt/README.md"),
    ("financial-data", "market_data/crypto/spot_top50/ethusdt/data_dictionary.md"),
    ("financial-data", "features/trading_asset_features/ethusdt/4h/README.md"),
    ("financial-data", "features/trading_asset_features/ethusdt/4h/data_dictionary.md"),
    ("financial-data", "README.md"),
    (SUCC_ROOT_ID, "PRE_RUN_MANIFEST.json"),
    (SUCC_ROOT_ID, "POST_RUN_MANIFEST.json"),
)
LICENSE_FILE_GLOBS = ("LICENSE*", "LICENCE*", "NOTICE*", "COPYING*")
HOME_RE = re.compile(r"(/home|/Users|/root)/")


class DigestMismatch(RuntimeError):
    pass


class CensusRefusal(RuntimeError):
    pass


def variable_id(dataset_id: str, column: str) -> str:
    return hashlib.sha256((dataset_id + "\0" + column).encode("utf-8")).hexdigest()


def self_digest(doc: dict[str, Any]) -> dict[str, str]:
    body = {k: v for k, v in doc.items() if k != "self_digest"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {"algorithm": "sha256",
            "canonicalization": "json.dumps(document_without_self_digest, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')",
            "value": hashlib.sha256(canon).hexdigest()}


def sha_obj(o: Any) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def read_once(path: Path, expected: str | None) -> tuple[bytes, str]:
    with open(path, "rb") as fh:
        data = fh.read()
    d = hashlib.sha256(data).hexdigest()
    if expected is not None and d != expected:
        raise DigestMismatch(f"{path.name}: sha256 {d} != expected {expected}")
    return data, d


def symbol_source(py_bytes: bytes, symbol: str) -> str:
    text = py_bytes.decode("utf-8")
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == symbol:
            return ast.get_source_segment(text, node)
    raise CensusRefusal(f"symbol {symbol} not found")


# ----------------------------------------------------------- declarations
W, A, D = "worker", "assembler", "raw_data_dictionary"
SANITIZE = (W, "sanitize", ["out = df.replace([np.inf, -np.inf], np.nan)",
                            'out[col] = pd.to_numeric(out[col], errors="coerce").astype("float32")'])
NO_SENTINEL_WORKER = "NO_SENTINEL: non-finite values become NaN (sanitize), never a substitute value"


def _t(sem, expr, unit=UNKNOWN, extra=(), sentinel=None, symbol="compute_technical", helper=()):
    """semantic declaration for a worker column."""
    return {"semantic_type": sem, "symbol": symbol, "expressions": [expr, *extra],
            "helpers": list(helper), "unit": unit, "sentinel": sentinel}


def declarations() -> dict[str, dict]:
    d: dict[str, dict] = {}
    for c, raw_col in (("OPEN", "open"), ("HIGH", "high"), ("LOW", "low"), ("CLOSE", "close")):
        d[c] = {"semantic_type": f"bar_{raw_col}_price", "producer_key": A, "symbol": "derive_bar_columns",
                "expressions": [f'out["{c}"] = raw["{raw_col}"].astype(float)'], "helpers": [],
                "semantic_evidence": (D, "- `open`, `high`, `low`, `close`: OHLC prices when available."),
                "unit": UNKNOWN, "sentinel": None}
    d["VOLUME"] = {"semantic_type": "bar_traded_base_volume", "producer_key": A, "symbol": "derive_bar_columns",
                   "expressions": ['out["VOLUME"] = raw["volume"].astype(float)'], "helpers": [],
                   "semantic_evidence": (D, "- `volume`: traded base volume when available."),
                   "unit": UNKNOWN, "sentinel": None}
    d["typical_price"] = {"semantic_type": "typical_price_mean_of_high_low_close", "producer_key": A,
                          "symbol": "derive_bar_columns",
                          "expressions": ['out["typical_price"] = (raw["high"].astype(float)'],
                          "helpers": [], "unit": UNKNOWN, "sentinel": None}
    for h in (1, 5, 10, 20, 60):
        loop = "for horizon in [1, 5, 10, 20, 60]:"
        d[f"return_{h}"] = _t("simple_return", 'out[f"return_{horizon}"] = close.pct_change(horizon)', "1", [loop])
        d[f"log_return_{h}"] = _t("log_return", 'out[f"log_return_{horizon}"] = np.log(close / close.shift(horizon))', "1", [loop])
    for p in (10, 20, 50, 100, 200):
        loop = "for period in [10, 20, 50, 100, 200]:"
        d[f"sma_{p}"] = _t("simple_moving_average_of_close", 'out[f"sma_{period}"] = close.rolling(period).mean()', extra=[loop])
        d[f"ema_{p}"] = _t("exponential_moving_average_of_close", 'out[f"ema_{period}"] = ema(close, period)', extra=[loop])
        d[f"close_sma_ratio_{p}"] = _t("relative_deviation_of_close_from_sma",
                                       'out[f"close_sma_ratio_{period}"] = close / out[f"sma_{period}"] - 1', "1", [loop])
    d["macd"] = _t("ema_difference_macd", 'out["macd"] = ema12 - ema26')
    d["macd_signal"] = _t("ema_of_macd", 'out["macd_signal"] = ema(out["macd"], 9)')
    d["macd_hist"] = _t("macd_minus_signal", 'out["macd_hist"] = out["macd"] - out["macd_signal"]')
    rsi_helper = [("rsi", ["rs = up.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / down.ewm(",
                           "return 100 - (100 / (1 + rs))"])]
    for p in (7, 14, 21):
        d[f"rsi_{p}"] = _t("relative_strength_index_0_100", 'out[f"rsi_{period}"] = rsi(close, period)', "1",
                           ["for period in [7, 14, 21]:"], helper=rsi_helper,
                           sentinel="NO_SENTINEL: non-finite values become NaN (sanitize); a zero down-move average gives the formula's bound 100, not a substitute")
    d["stoch_k"] = _t("stochastic_oscillator_k_0_100", 'out["stoch_k"] = 100 * (close - low14) / (high14 - low14)', "1")
    d["stoch_d"] = _t("stochastic_oscillator_d_0_100", 'out["stoch_d"] = out["stoch_k"].rolling(3).mean()', "1",
                      ['out["stoch_k"] = 100 * (close - low14) / (high14 - low14)'])
    d["williams_r_14"] = _t("williams_percent_r_minus100_0", 'out["williams_r_14"] = -100 * (high14 - close) / (high14 - low14)', "1")
    d["cci_14"] = _t("commodity_channel_index", 'out["cci_14"] = (typical - mean_typical_14) / (0.015 * mean_abs_dev_14)', "1")
    for p in (10, 20, 60):
        d[f"roc_{p}"] = _t("rate_of_change_simple_return", 'out[f"roc_{period}"] = close.pct_change(period)', "1",
                           ["for period in [10, 20, 60]:"])
        d[f"hist_vol_{p}"] = _t("scaled_rolling_std_of_log_return",
                                'out[f"hist_vol_{period}"] = out["log_return_1"].rolling(period).std() * np.sqrt(period)', "1",
                                ["for period in [10, 20, 60]:",
                                 'out[f"log_return_{horizon}"] = np.log(close / close.shift(horizon))'])
    d["mom_10"] = _t("close_price_difference_momentum", 'out["mom_10"] = close.diff(10)')
    d["mom_20"] = _t("close_price_difference_momentum", 'out["mom_20"] = close.diff(20)')
    d["bb_upper"] = _t("bollinger_upper_band", 'out["bb_upper"] = bb_mid + 2 * bb_std')
    d["bb_middle"] = _t("bollinger_middle_band_sma_20", 'out["bb_middle"] = bb_mid')
    d["bb_lower"] = _t("bollinger_lower_band", 'out["bb_lower"] = bb_mid - 2 * bb_std')
    d["bb_pct_b"] = _t("bollinger_percent_b", 'out["bb_pct_b"] = (close - out["bb_lower"]) / (out["bb_upper"] - out["bb_lower"])', "1")
    d["bb_width"] = _t("bollinger_relative_width", 'out["bb_width"] = (out["bb_upper"] - out["bb_lower"]) / out["bb_middle"]', "1")
    d["atr_14"] = _t("average_true_range", 'out["atr_14"] = tr.rolling(14).mean()')
    d["natr_14"] = _t("normalized_average_true_range", 'out["natr_14"] = out["atr_14"] / close', "1")
    d["ema_cross_10_50"] = _t("normalized_ema_difference", 'out["ema_cross_10_50"] = (out["ema_10"] - out["ema_50"]) / close', "1")
    d["ema_cross_20_100"] = _t("normalized_ema_difference", 'out["ema_cross_20_100"] = (out["ema_20"] - out["ema_100"]) / close', "1")
    zero_close = "ZERO_CLOSE_TREATED_AS_NAN (close.replace(0, np.nan)); non-finite values become NaN (sanitize); no substitute value"
    d["trend_slope_50"] = _t("mean_log_price_change_per_bar_over_50", 'out["trend_slope_50"] = np.log(close.replace(0, np.nan)).diff(50) / 50', "1", sentinel=zero_close)
    d["trend_strength_50"] = _t("absolute_mean_log_price_change_per_bar_over_50", 'out["trend_strength_50"] = out["trend_slope_50"].abs()', "1",
                                ['out["trend_slope_50"] = np.log(close.replace(0, np.nan)).diff(50) / 50'], sentinel=zero_close)
    obv_s = "NAN_PRICE_CHANGE_SIGN_AND_NAN_VOLUME_ENCODED_AS_0 before the cumulative sum (fillna(0)); other non-finite values become NaN (sanitize)"
    d["obv"] = _t("on_balance_volume_cumulative", 'out["obv"] = (signed * volume.fillna(0)).cumsum()',
                  extra=["signed = np.sign(close.diff()).fillna(0)"], sentinel=obv_s)
    d["obv_delta_20"] = _t("on_balance_volume_20_bar_change", 'out["obv_delta_20"] = out["obv"].diff(20)',
                           extra=["signed = np.sign(close.diff()).fillna(0)"], sentinel=obv_s)
    for p in (10, 20):
        d[f"volume_sma_{p}"] = _t("simple_moving_average_of_volume", 'out[f"volume_sma_{period}"] = volume.rolling(period).mean()',
                                  extra=["for period in [10, 20]:"])
    d["volume_ratio_20"] = _t("volume_to_its_20_bar_mean_ratio", 'out["volume_ratio_20"] = volume / out["volume_sma_20"]', "1")
    d["vwap_60"] = _t("volume_weighted_typical_price_60", 'out["vwap_60"] = (typical * volume).rolling(60).sum() / volume.rolling(60).sum()')
    d["mfi_14"] = _t("money_flow_index_0_100", 'out["mfi_14"] = 100 - (100 / (1 + positive / negative))', "1",
                     ["positive = mf_raw.where(typical.diff() > 0, 0).rolling(14).sum()",
                      "negative = mf_raw.where(typical.diff() < 0, 0).rolling(14).sum().abs()"],
                     sentinel="NO_SENTINEL: non-finite values become NaN (sanitize); a zero negative money flow gives the formula's bound 100, not a substitute")
    S = "compute_statistical"
    ret = "returns = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan)"
    d["statistical__log_return_1"] = _t("log_return", 'out["log_return_1"] = returns', "1", [ret], symbol=S)
    for w in (20, 60, 252):
        loop = "for window in [20, 60, 252]:"
        d[f"roll_mean_ret_{w}"] = _t("rolling_mean_of_log_return", 'out[f"roll_mean_ret_{window}"] = returns.rolling(window).mean()', "1", [loop, ret], symbol=S)
        d[f"roll_std_ret_{w}"] = _t("rolling_std_of_log_return", 'out[f"roll_std_ret_{window}"] = returns.rolling(window).std()', "1", [loop, ret], symbol=S)
        d[f"roll_skew_ret_{w}"] = _t("rolling_skewness_of_log_return", 'out[f"roll_skew_ret_{window}"] = returns.rolling(window).skew()', "1", [loop, ret], symbol=S)
        d[f"roll_kurt_ret_{w}"] = _t("rolling_excess_kurtosis_of_log_return", 'out[f"roll_kurt_ret_{window}"] = returns.rolling(window).kurt()', "1", [loop, ret], symbol=S)
    for w in (12, 48):
        d[f"realized_var_{w}"] = _t("rolling_sum_of_squared_log_return", f'out["realized_var_{w}"] = returns.pow(2).rolling({w}).sum()', "1", [ret], symbol=S)
    ac_helper = [("rolling_autocorr", ["return series.rolling(window).corr(series.shift(lag))"])]
    d["autocorr_lag1_100"] = _t("rolling_autocorrelation_of_log_return", 'out["autocorr_lag1_100"] = rolling_autocorr(returns, 100, 1)', "1", [ret], symbol=S, helper=ac_helper)
    d["autocorr_lag5_100"] = _t("rolling_autocorrelation_of_log_return", 'out["autocorr_lag5_100"] = rolling_autocorr(returns, 100, 5)', "1", [ret], symbol=S, helper=ac_helper)
    d["sqret_autocorr_lag1_100"] = _t("rolling_autocorrelation_of_squared_log_return", 'out["sqret_autocorr_lag1_100"] = rolling_autocorr(returns.pow(2), 100, 1)', "1", [ret], symbol=S, helper=ac_helper)
    regime = "UNDEFINED_THRESHOLD_COMPARISON_ENCODED_AS_0.0: where vol20 or the 252-bar quantile of vol252 is NaN the comparison is False and the flag is 0.0, indistinguishable from a real 0.0"
    d["vol_regime_high"] = _t("binary_indicator_short_vol_above_long_vol_q75", 'out["vol_regime_high"] = (vol20 > vol252.rolling(252).quantile(0.75)).astype("float")', "1",
                              ["vol20 = returns.rolling(20).std()", "vol252 = returns.rolling(252).std()"], sentinel=regime, symbol=S)
    d["vol_regime_low"] = _t("binary_indicator_short_vol_below_long_vol_q25", 'out["vol_regime_low"] = (vol20 < vol252.rolling(252).quantile(0.25)).astype("float")', "1",
                             ["vol20 = returns.rolling(20).std()", "vol252 = returns.rolling(252).std()"], sentinel=regime, symbol=S)
    d["hurst_proxy_200"] = _t("autocorrelation_based_persistence_proxy_0_1", 'out["hurst_proxy_200"] = hurst_proxy(returns, 200)', "1", [ret], symbol=S,
                              helper=[("hurst_proxy", ["return (0.5 + 0.5 * rolling_autocorr(series, window, 1)).clip(0, 1)"])] + ac_helper,
                              sentinel="CLIPPED_TO_[0,1] (clip, a bound not a substitute); non-finite values become NaN (sanitize)")
    d["zscore_close_100"] = _t("rolling_zscore_of_close", 'out["zscore_close_100"] = (close - close.rolling(100).mean()) / close.rolling(100).std()', "1", symbol=S)
    for v in d.values():
        v.setdefault("producer_key", W)
    return d


MISSING_POLICY = ("ROW_DROPPED_AT_ASSEMBLY_IF_ANY_OUTPUT_VALUE_NON_FINITE; NO_FILL_NO_INTERPOLATION "
                  "(assemble keeps a row iff every output value on it is finite)")
MISSING_EXPRESSIONS = ["keep = np.isfinite(values).all(axis=1)", "return out.loc[keep].reset_index(drop=True)"]


# ------------------------------------------------------------------ build
def _src(key: str, suffix: str = "") -> str:
    root_id, rel, _ = PINNED[key]
    return f"{root_id}:{rel}{suffix}"


def build(fd_root: Path = FD_ROOT, successors_root: Path = DEFAULT_SUCCESSORS_ROOT) -> dict:
    roots = {"financial-data": Path(fd_root), SUCC_ROOT_ID: Path(successors_root) / "eth_h4_stage22_rerun_v1"}
    blobs: dict[str, bytes] = {}
    shas: dict[str, str] = {}
    for key, (rid, rel, pin) in PINNED.items():
        blobs[key], shas[key] = read_once(roots[rid] / rel, pin)

    dag = json.loads(blobs["feature_dag_v4"])
    man = json.loads(blobs["binding_manifest_v2"])
    if sha_obj({k: v for k, v in dag.items() if k != "dag_sha256"}) != dag["dag_sha256"]:
        raise CensusRefusal("dag_sha256 does not verify")
    if sha_obj({k: v for k, v in man.items() if k not in ("derived_at", "manifest_sha256")}) != man["manifest_sha256"]:
        raise CensusRefusal("manifest_sha256 does not verify")
    if dag["binding_manifest_sha256"] != man["manifest_sha256"] or dag["successor_dataset_id"] != DATASET_ID:
        raise CensusRefusal("DAG does not bind this manifest / successor")
    file_key = {PINNED["assembler"][1]: "assembler", PINNED["worker"][1]: "worker"}
    bindings = {}
    for b in man["bindings"]:
        if b["dataset_id"] != DATASET_ID or b["dataset_sha256"] != DATASET_SHA256:
            raise CensusRefusal(f"binding {b['output_column']} is not the successor")
        if b["output_column"] in bindings:
            raise CensusRefusal(f"duplicate binding {b['output_column']}")
        if b["file"] not in file_key or b["file_sha256"] != shas[file_key[b["file"]]]:
            raise CensusRefusal(f"binding {b['output_column']} producer file bytes differ from the bound file_sha256")
        bindings[b["output_column"]] = b
    nodes = {}
    for n in dag["nodes"]:
        if n["column"] in nodes:
            raise CensusRefusal(f"duplicate DAG column {n['column']}")
        nodes[n["column"]] = n

    table = pq.read_table(pa.BufferReader(blobs["successor_parquet"]))
    schema = {f.name: str(f.type) for f in table.schema}
    active = [c for c, n in nodes.items() if n["class"] == "CAUSAL_ACTIVE"]
    if set(active) != set(bindings) or set(active) != set(table.column_names) - {"DATE_TIME"}:
        raise CensusRefusal("DAG / manifest / parquet column sets disagree")

    decl = declarations()
    if set(decl) != set(active):
        raise CensusRefusal(f"declarations do not cover exactly the active columns: {sorted(set(decl) ^ set(active))}")

    # observations of the bound bytes
    observed = {}
    arrays = {}
    for c in active:
        col = table.column(c)
        v = col.to_numpy(zero_copy_only=False).astype(np.float64)
        arrays[c] = v
        observed[c] = {"rows": int(len(v)), "nulls": int(col.null_count),
                       "nan": int(np.isnan(v).sum()), "infinite": int(np.isinf(v).sum())}
    ident = []
    cols = list(active)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            if np.array_equal(arrays[a], arrays[b]):
                ident.append([a, b])
    first_nonzero = {c: int(np.argmax(arrays[c] != 0)) if (arrays[c] != 0).any() else None
                     for c in ("vol_regime_high", "vol_regime_low")}

    rows, unit_derivations, semantic_derivations, sentinel_derivations = [], {}, {}, {}
    for c in [n["column"] for n in dag["nodes"] if n["class"] == "CAUSAL_ACTIVE"]:
        b, n, dc = bindings[c], nodes[c], decl[c]
        pkey = dc["producer_key"]
        if PINNED[pkey][1] != b["file"] or dc["symbol"] != b["symbol"]:
            raise CensusRefusal(f"{c}: declaration producer/symbol differ from the binding")
        code_src = _src(pkey, f"::{dc['symbol']}")
        proof = {"source": code_src, "sha256": shas[pkey], "expressions": dc["expressions"],
                 "helpers": [{"source": _src(pkey, f"::{h}"), "sha256": shas[pkey], "expressions": ex}
                             for h, ex in dc["helpers"]]}
        if "semantic_evidence" in dc:
            skey, quote = dc["semantic_evidence"]
            sem_ev = {"source": _src(skey, "#" + quote), "sha256": shas[skey]}
            semantic_derivations[c] = {"document": {"source": _src(skey), "sha256": shas[skey], "quote": quote},
                                       "mapping": proof,
                                       "applicability": {"source": _src("raw_parquet_in_repo"), "sha256": shas["raw_parquet_in_repo"],
                                                         "statement": "the dictionary describes features/trading_asset_data/ethusdt, whose 4h.parquet bytes equal the rerun's raw input (sha256 37321161...)"}}
        else:
            sem_ev = {"source": code_src, "sha256": shas[pkey]}
            semantic_derivations[c] = {"mapping": proof}
        unit = dc["unit"]
        if unit != UNKNOWN:
            unit_derivations[c] = dict(proof, rule="value is a ratio, log-ratio, normalized statistic or indicator of same-unit quantities in the quoted code")
        unit_ev = {"source": code_src, "sha256": shas[pkey]} if unit != UNKNOWN else dict(NONE_EVIDENCE)
        if dc["sentinel"] is None:
            if pkey == "assembler":
                sentinel = "NONE_IN_PRODUCER_CODE: same-row copy/arithmetic of raw values, no substitution"
                sent_ev = {"source": code_src, "sha256": shas[pkey]}
                sentinel_derivations[c] = proof
            else:
                sentinel = NO_SENTINEL_WORKER
                sent_ev = {"source": _src(W, "::sanitize"), "sha256": shas[W]}
                sentinel_derivations[c] = {"source": _src(W, "::sanitize"), "sha256": shas[W], "expressions": SANITIZE[2]}
        else:
            sentinel = dc["sentinel"]
            sent_ev = {"source": code_src, "sha256": shas[pkey]}
            sentinel_derivations[c] = dict(proof, sanitize={"source": _src(W, "::sanitize"), "expressions": SANITIZE[2]})
        row = {
            "variable_id": variable_id(DATASET_ID, c),
            "dataset_id": DATASET_ID,
            "dataset_sha256": DATASET_SHA256,
            "column": c,
            "physical_type": schema[c],
            "semantic_type": dc["semantic_type"],
            "semantics": dc["semantic_type"],
            "role": "input_feature",
            "unit": unit,
            "license": UNKNOWN,
            "license_source": "NONE",
            "missing_policy": MISSING_POLICY,
            "sentinel_policy": sentinel,
            "producer": b["file"],
            "symbol": b["symbol"],
            "lookback_bars": n["static"]["lookback_bars"],
            "evidence": {
                "semantic_type": sem_ev,
                "role": {"source": _src("feature_dag_v4", f"#nodes[column={c}].class=CAUSAL_ACTIVE"), "sha256": shas["feature_dag_v4"]},
                "unit": unit_ev,
                "license": dict(NONE_EVIDENCE),
                "missing_policy": {"source": _src("assembler", "::assemble"), "sha256": shas["assembler"]},
                "sentinel_policy": sent_ev,
                "producer": {"source": _src("binding_manifest_v2", f"#bindings[output_column={c}].file"), "sha256": shas["binding_manifest_v2"]},
                "symbol": {"source": _src("binding_manifest_v2", f"#bindings[output_column={c}].symbol"), "sha256": shas["binding_manifest_v2"]},
                "lookback_bars": {"source": _src("feature_dag_v4", f"#nodes[column={c}].static.lookback_bars"), "sha256": shas["feature_dag_v4"]},
                "physical_type": {"source": _src("successor_parquet", f"#schema.{c}"), "sha256": shas["successor_parquet"]},
            },
        }
        if n["class"] != "CAUSAL_ACTIVE":
            raise CensusRefusal(f"{c}: not CAUSAL_ACTIVE")
        rows.append(row)

    # license search: evidence of absence
    search = []
    for rid, rel in LICENSE_SEARCH:
        p = roots[rid] / rel
        if not p.is_file():
            search.append({"source": f"{rid}:{rel}", "present": False})
            continue
        data, d = read_once(p, None)
        text = data.decode("utf-8", errors="replace")
        hits = [ln.strip() for ln in text.splitlines() if re.search(r"licen[cs]", ln, re.I)]
        search.append({"source": f"{rid}:{rel}", "present": True, "sha256": d, "license_lines": hits})
    license_files = sorted(str(p.relative_to(roots["financial-data"])) for g in LICENSE_FILE_GLOBS
                           for p in roots["financial-data"].glob(g))
    license_search = {
        "files_examined": search,
        "repository_root_license_files": license_files,
        "finding": "NO_LICENSE_DOCUMENT_FOR_THESE_BYTES",
        "detail": ("No provenance, README or data dictionary for the ETH 4h raw source or its Stage 2.1/2.2 derivatives "
                   "declares a license. The repository README's License section states that no license file is present and "
                   "grants no permission beyond rights supplied by the original data sources; it names no license for the source. "
                   "The provider being a known exchange is not evidence of a license."),
        "result": "license = UNKNOWN for every variable",
    }
    for s in search:
        if s.get("present") and s["license_lines"] and s["source"] != "financial-data:README.md":
            raise CensusRefusal(f"unreviewed license statement in {s['source']}: {s['license_lines']}")

    def counts(field):
        return dict(sorted(Counter(r[field] for r in rows).items(), key=lambda kv: str(kv[0])))

    def state(field):
        return dict(sorted(Counter("UNKNOWN" if r[field] == UNKNOWN else "DECLARED" for r in rows).items()))

    doc = {
        "schema": SCHEMA_ID,
        "artifact": "ETH_H4_SUCCESSOR_SEMANTIC_CENSUS.v1",
        "order_items": ["C115"],
        "dataset_id": DATASET_ID,
        "dataset_sha256": DATASET_SHA256,
        "dataset_root_id": SUCC_ROOT_ID,
        "dataset_relative_path": PINNED["successor_parquet"][1],
        "feature_dag": {"source": _src("feature_dag_v4"), "file_sha256": shas["feature_dag_v4"], "dag_sha256": dag["dag_sha256"]},
        "binding_manifest": {"source": _src("binding_manifest_v2"), "file_sha256": shas["binding_manifest_v2"],
                             "manifest_sha256": man["manifest_sha256"]},
        "producer": {"root_id": "financial-data", "relative_path": "_scripts/build_eth_h4_successor_semantic_census.py"},
        "variable_id_rule": 'sha256((dataset_id + "\\0" + column).encode("utf-8")).hexdigest()',
        "row_keys": list(ROW_KEYS),
        "evidence_fields": list(EVIDENCE_FIELDS),
        "evidence_rule": "evidence[field] = {source: '<root_id>:<relative_path>[::symbol | #document key]', sha256: sha256 of that file's bytes}; a field without evidence is UNKNOWN with {source: NONE, sha256: null}",
        "evidence_files": {_src(k): shas[k] for k in PINNED},
        "unknown_excludes": "UNKNOWN in any declared field EXCLUDES the variable from every downstream use that needs that field. No rule was relaxed to make a variable eligible; a unit is never inferred from a column name and a license never from provider reputation.",
        "rows": rows,
        "counts": {"rows": len(rows), "by_role": counts("role"), "by_unit": counts("unit"), "unit_state": state("unit"),
                   "by_license": counts("license"), "license_state": state("license"),
                   "missing_policy_state": state("missing_policy"), "by_missing_policy": counts("missing_policy"),
                   "sentinel_policy_state": state("sentinel_policy"), "by_sentinel_policy": counts("sentinel_policy"),
                   "semantic_type_state": state("semantic_type"), "by_physical_type": counts("physical_type")},
        "unit_derivations": unit_derivations,
        "unit_unknown_reason": "Price-, volume- or price-difference-denominated columns: no document read here states the currency or the base-asset unit of the raw open/high/low/close/volume, so the unit is UNKNOWN rather than guessed from the pair name.",
        "semantic_derivations": semantic_derivations,
        "missing_policy_derivation": {"source": _src("assembler", "::assemble"), "sha256": shas["assembler"], "expressions": MISSING_EXPRESSIONS},
        "sentinel_derivations": sentinel_derivations,
        "license_search": license_search,
        "observations": {
            "non_finite_by_column": observed,
            "non_finite_total": int(sum(o["nan"] + o["infinite"] + o["nulls"] for o in observed.values())),
            "first_nonzero_row": first_nonzero,
            "identical_column_pairs": ident,
            "note": "Observed on the bound bytes; informational. Identical pairs are equal arrays, not a role decision.",
        },
    }
    defects = validate_census(doc, {_src(k): blobs[k] for k in PINNED})
    if defects:
        raise CensusRefusal(f"census invalid: {defects}")
    doc["self_digest"] = self_digest(doc)
    if HOME_RE.search(json.dumps(doc)):
        raise CensusRefusal("absolute home-directory path in census")
    return doc


# --------------------------------------------------------------- validator
def _file_key(source: str) -> str:
    return source.split("::")[0].split("#")[0]


def validate_census(doc: dict, files: dict[str, bytes]) -> list[str]:
    """Every defect. ``files`` maps '<root_id>:<relative_path>' -> bytes."""
    d: list[str] = []
    rows = doc.get("rows", [])
    shas = {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
    cols, vids = Counter(r.get("column") for r in rows), Counter(r.get("variable_id") for r in rows)
    d += [f"DUPLICATE_COLUMN:{c}" for c, k in cols.items() if k > 1]
    d += [f"DUPLICATE_VARIABLE_ID:{v}" for v, k in vids.items() if k > 1]
    for r in rows:
        c = r.get("column")
        if tuple(sorted(r)) != tuple(sorted(ROW_KEYS)):
            d.append(f"ROW_KEYS:{c}")
            continue
        if r["variable_id"] != variable_id(r["dataset_id"], c):
            d.append(f"VARIABLE_ID_RULE:{c}")
        if r["dataset_id"] != doc.get("dataset_id") or r["dataset_sha256"] != doc.get("dataset_sha256"):
            d.append(f"DATASET_IDENTITY:{c}")
        if r["semantics"] != r["semantic_type"]:
            d.append(f"SEMANTICS_NE_SEMANTIC_TYPE:{c}")
        if r["role"] not in ROLES and not str(r["role"]).startswith("excluded"):
            d.append(f"ROLE:{c}")
        ev = r["evidence"]
        if set(ev) != set(EVIDENCE_FIELDS):
            d.append(f"EVIDENCE_FIELDS:{c}")
            continue
        for f in EVIDENCE_FIELDS:
            e = ev[f]
            if not isinstance(e, dict) or set(e) != {"source", "sha256"}:
                d.append(f"EVIDENCE_SHAPE:{c}.{f}")
                continue
            unknown = r[f] == UNKNOWN
            if unknown:
                if e != NONE_EVIDENCE:
                    d.append(f"UNKNOWN_WITH_EVIDENCE:{c}.{f}")
                continue
            if e["source"] == "NONE" or e["sha256"] is None:
                d.append(f"DECLARED_WITHOUT_EVIDENCE:{c}.{f}")
                continue
            key = _file_key(e["source"])
            if key not in shas:
                d.append(f"EVIDENCE_FILE_NOT_PRESENTED:{c}.{f}")
            elif shas[key] != e["sha256"]:
                d.append(f"EVIDENCE_SHA256_MISMATCH:{c}.{f}")
        if r["license"] != UNKNOWN and r["license_source"] in ("NONE", None, ""):
            d.append(f"LICENSE_WITHOUT_SOURCE:{c}")
        if r["license"] == UNKNOWN and r["license_source"] != "NONE":
            d.append(f"LICENSE_SOURCE_WITHOUT_LICENSE:{c}")
        if r["unit"] != UNKNOWN:
            src = ev["unit"]["source"]
            if not src.endswith(".py::" + r["symbol"]) or _file_key(src).split(":", 1)[-1] != r["producer"]:
                d.append(f"UNIT_EVIDENCE_NOT_PRODUCER_CODE:{c}")
            proof = doc.get("unit_derivations", {}).get(c)
            if not proof:
                d.append(f"UNIT_WITHOUT_FORMULA_PROOF:{c}")
            else:
                d += _check_proof(proof, files, c, "UNIT")
    for c, proof in doc.get("semantic_derivations", {}).items():
        d += _check_proof(proof["mapping"], files, c, "SEMANTIC")
        if "document" in proof:
            k = _file_key(proof["document"]["source"])
            if k not in files or proof["document"]["quote"] not in files[k].decode("utf-8"):
                d.append(f"SEMANTIC_QUOTE_NOT_IN_DOCUMENT:{c}")
    mp = doc.get("missing_policy_derivation")
    if mp:
        d += _check_proof(mp, files, "*", "MISSING")
    return d


def _check_proof(proof: dict, files: dict[str, bytes], c: str, tag: str) -> list[str]:
    out = []
    for part in [proof, *proof.get("helpers", [])]:
        key = _file_key(part["source"])
        if key not in files:
            out.append(f"{tag}_PROOF_FILE_NOT_PRESENTED:{c}")
            continue
        if hashlib.sha256(files[key]).hexdigest() != part["sha256"]:
            out.append(f"{tag}_PROOF_SHA256_MISMATCH:{c}")
            continue
        if "::" not in part["source"]:
            out.append(f"{tag}_PROOF_WITHOUT_SYMBOL:{c}")
            continue
        try:
            body = symbol_source(files[key], part["source"].split("::", 1)[1])
        except CensusRefusal:
            out.append(f"{tag}_PROOF_SYMBOL_ABSENT:{c}")
            continue
        if not part.get("expressions"):
            out.append(f"{tag}_PROOF_EMPTY:{c}")
        for ex in part.get("expressions", []):
            if ex not in body:
                out.append(f"{tag}_PROOF_EXPRESSION_NOT_IN_SYMBOL:{c}:{ex}")
    return out


def publish(doc: dict, out: Path) -> None:
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if HOME_RE.search(text):
        raise CensusRefusal("absolute home-directory path in census")
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--financial-data-root", type=Path, default=FD_ROOT)
    ap.add_argument("--successors-root", type=Path, default=DEFAULT_SUCCESSORS_ROOT)
    ap.add_argument("--output", type=Path, default=FD_ROOT / "features/census" / CENSUS_NAME)
    a = ap.parse_args(argv)
    if a.output.exists():
        raise CensusRefusal(f"write-once: {a.output.name} already exists")
    doc = build(a.financial_data_root, a.successors_root)
    publish(doc, a.output)
    print(json.dumps({"rows": doc["counts"]["rows"], "self_digest": doc["self_digest"]["value"],
                      **{k: doc["counts"][k] for k in ("by_role", "unit_state", "license_state",
                                                       "missing_policy_state", "sentinel_policy_state")}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
