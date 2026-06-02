#!/usr/bin/env python3
"""
Stage 3X P0-A Regime Smoke Worker — KMeans train-only regime baseline.

Governance:
  - All fitting uses train rows only (2017-09-28 to 2023-12-31).
  - Heldout rows (>= 2025-01-01) are firewalled via split_guard.assert_no_heldout_rows.
  - Validation data (2024-xx) must only be TRANSFORMED by the fitted pipeline, never fitted.
  - Model reproducibility: random_seed=42, n_init=10, fixed feature set.

Produced regime features (one row per bar, timestamped):
  unsup_regime_id              — 0-indexed cluster label (int)
  unsup_regime_prob_0 .. _k-1  — soft cluster probabilities (softmax of neg centroid distances)
  unsup_regime_entropy         — Shannon entropy (nats) of the probability row
  unsup_regime_transition_prob — 1 if regime label changed vs previous bar, 0 otherwise
  unsup_regime_persistence     — number of consecutive bars in current regime

Outputs:
  experiments/unsup_causal_audit/artifacts/regime_smoke/ethusdt_4h_tech_stat/
    regime_features_train.parquet  — regime features for every train row
    kmeans_pipeline.pkl            — fitted (StandardScaler, KMeans) for transform-only use
    regime_report.md               — human-readable report
    metadata.json                  — ArtifactMetadata provenance record

  experiments/unsup_causal_audit/features/trading_asset_features/ethusdt/4h/
    regime_smoke_tech_stat.parquet — joinable feature file (DATE_TIME + regime cols)

Registry: experiments/unsup_causal_audit/registry.json — updated with artifact entry.

Run:
    cd /home/harveybc/Documents/GitHub/financial-data
    python _scripts/workers/stage3x_regime_smoke_worker.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Repo root + lib imports
# ---------------------------------------------------------------------------

ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(ROOT))

from _scripts.lib.split_guard import (
    SplitViolation,
    assert_no_heldout_rows,
    validate_timestamps,
)
from _scripts.lib.artifact_metadata import (
    build_metadata,
    compute_config_hash,
    compute_manifest_hash,
    write_metadata,
)
from _scripts.lib.feature_alignment import validate_feature_join

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TRAIN_CSV = ROOT / "experiments/stage_a_screening/inputs/ethusdt/4h/tech_stat/train.csv"

ARTIFACT_DIR = (
    ROOT / "experiments/unsup_causal_audit/artifacts/regime_smoke/ethusdt_4h_tech_stat"
)
FEATURE_OUT_DIR = (
    ROOT / "experiments/unsup_causal_audit/features/trading_asset_features/ethusdt/4h"
)
REGISTRY_JSON = ROOT / "experiments/unsup_causal_audit/registry.json"

# ---------------------------------------------------------------------------
# Config — its sha256 goes into metadata; changing any value changes the hash
# ---------------------------------------------------------------------------

CONFIG: dict[str, Any] = {
    "artifact_type":   "regime_smoke",
    "asset":           "ethusdt",
    "timeframe":       "4h",
    "feature_family":  "tech_stat",
    "timestamp_col":   "DATE_TIME",
    "heldout_start":   "2025-01-01T00:00:00Z",
    "n_regimes":       4,
    "random_seed":     42,
    "kmeans_n_init":   10,
    "kmeans_max_iter": 300,
    "prob_temperature": 1.0,   # softmax temperature over negative centroid distances
    # Compact feature set: scale-invariant volatility + momentum + mean-reversion
    "regime_features": [
        "natr_14",           # normalised ATR — scale-invariant volatility
        "hist_vol_20",       # 20-bar realised volatility
        "roll_std_ret_20",   # rolling return std (short-horizon vol)
        "rsi_14",            # momentum / overbought-oversold
        "bb_width",          # Bollinger band width (volatility regime)
        "zscore_close_100",  # trend-strength / mean-reversion signal
        "vol_regime_high",   # existing binary high-vol flag
        "vol_regime_low",    # existing binary low-vol flag
    ],
}

TIMESTAMP_COL  = CONFIG["timestamp_col"]
HELDOUT_START  = CONFIG["heldout_start"]
REGIME_FEATURES = CONFIG["regime_features"]
N_REGIMES       = CONFIG["n_regimes"]
RANDOM_SEED     = CONFIG["random_seed"]


# ---------------------------------------------------------------------------
# Core computations (pure functions — no I/O, all testable)
# ---------------------------------------------------------------------------

def fit_pipeline(
    X: np.ndarray,
    *,
    n_regimes: int = 4,
    random_seed: int = 42,
    n_init: int = 10,
    max_iter: int = 300,
) -> tuple[StandardScaler, KMeans]:
    """
    Fit StandardScaler + KMeans on the training feature matrix.

    Returns:
        scaler  — fitted StandardScaler
        km      — fitted KMeans
    """
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    km = KMeans(
        n_clusters=n_regimes,
        random_state=random_seed,
        n_init=n_init,
        max_iter=max_iter,
    )
    km.fit(Xs)
    return scaler, km


def transform_pipeline(
    X: np.ndarray,
    scaler: StandardScaler,
    km: KMeans,
    *,
    temperature: float = 1.0,
) -> dict[str, np.ndarray]:
    """
    Apply a fitted pipeline to raw feature matrix X.

    This function MUST be used for both train and validation data.
    It calls scaler.transform() and km.predict() / km.transform() — never fit.

    Returns a dict:
        regime_id              — (n,)  int32
        regime_probs           — (n, k) float32  soft probabilities
        regime_entropy         — (n,)  float32  Shannon entropy (nats)
        transition_indicator   — (n,)  int8     1 if regime changed vs prev bar
        persistence            — (n,)  int32    bars in current regime
    """
    Xs = scaler.transform(X)                  # transform-only; never fit
    labels = km.predict(Xs).astype(np.int32)  # predict-only; never fit

    # Soft probabilities via softmax over negative squared distances
    dists = km.transform(Xs)                  # (n, k) distances to centroids
    neg = -dists / max(temperature, 1e-6)
    neg -= neg.max(axis=1, keepdims=True)     # numerical stability
    exp_neg = np.exp(neg)
    probs = (exp_neg / exp_neg.sum(axis=1, keepdims=True)).astype(np.float32)

    # Shannon entropy (nats)
    entropy = (-np.sum(probs * np.log(probs.clip(min=1e-12)), axis=1)).astype(np.float32)

    # Transition indicator: 1 if regime changed vs previous bar
    transitions = np.zeros(len(labels), dtype=np.int8)
    transitions[1:] = (labels[1:] != labels[:-1]).astype(np.int8)

    # Persistence: consecutive bars in current regime (1-indexed)
    persistence = np.ones(len(labels), dtype=np.int32)
    for i in range(1, len(labels)):
        if labels[i] == labels[i - 1]:
            persistence[i] = persistence[i - 1] + 1

    return {
        "regime_id":           labels,
        "regime_probs":        probs,
        "regime_entropy":      entropy,
        "transition_indicator": transitions,
        "persistence":         persistence,
    }


def build_regime_df(
    timestamps: pd.Series,
    result: dict[str, np.ndarray],
    timestamp_col: str = "DATE_TIME",
) -> pd.DataFrame:
    """
    Assemble a regime feature DataFrame from transform_pipeline output.

    Columns:
        DATE_TIME
        unsup_regime_id
        unsup_regime_prob_0 .. unsup_regime_prob_{k-1}
        unsup_regime_entropy
        unsup_regime_transition_prob
        unsup_regime_persistence
    """
    n_regimes = result["regime_probs"].shape[1]
    data: dict[str, Any] = {timestamp_col: timestamps.values}
    data["unsup_regime_id"] = result["regime_id"]
    for k in range(n_regimes):
        data[f"unsup_regime_prob_{k}"] = result["regime_probs"][:, k]
    data["unsup_regime_entropy"]         = result["regime_entropy"]
    data["unsup_regime_transition_prob"] = result["transition_indicator"]
    data["unsup_regime_persistence"]     = result["persistence"]
    return pd.DataFrame(data)


def regime_summary(
    regime_df: pd.DataFrame,
    timestamps: pd.Series,
    n_regimes: int,
) -> dict[str, Any]:
    """Compute summary statistics for the MD report."""
    labels = regime_df["unsup_regime_id"].values
    counts = {int(k): int((labels == k).sum()) for k in range(n_regimes)}
    ts = pd.to_datetime(timestamps, utc=True)
    return {
        "n_rows":          len(regime_df),
        "n_regimes":       n_regimes,
        "label_counts":    counts,
        "mean_entropy":    float(regime_df["unsup_regime_entropy"].mean()),
        "max_entropy":     float(np.log(n_regimes)),
        "n_transitions":   int(regime_df["unsup_regime_transition_prob"].sum()),
        "mean_persistence": float(regime_df["unsup_regime_persistence"].mean()),
        "fit_start":       ts.min().isoformat(),
        "fit_end":         ts.max().isoformat(),
    }


# ---------------------------------------------------------------------------
# Registry update
# ---------------------------------------------------------------------------

def update_registry(registry_path: Path, entry: dict[str, Any]) -> None:
    reg = json.loads(registry_path.read_text(encoding="utf-8"))
    key = (entry.get("artifact_type"), entry.get("asset"),
           entry.get("timeframe"), entry.get("feature_family"))
    arts = reg.setdefault("artifacts", [])
    for i, a in enumerate(arts):
        if (a.get("artifact_type"), a.get("asset"),
                a.get("timeframe"), a.get("feature_family")) == key:
            arts[i] = entry
            break
    else:
        arts.append(entry)
    registry_path.write_text(
        json.dumps(reg, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def write_report(
    out_dir: Path,
    summary: dict[str, Any],
    config: dict[str, Any],
    output_paths: list[Path],
) -> Path:
    n_r = summary["n_regimes"]
    max_H = summary["max_entropy"]
    lines = [
        "# Regime Smoke Artifact Report (P0-A)",
        "",
        f"**Asset:** {config['asset']}  "
        f"**Timeframe:** {config['timeframe']}  "
        f"**Feature family:** {config['feature_family']}",
        f"**Method:** KMeans (k={n_r}, seed={config['random_seed']})",
        f"**Fit window:** {summary['fit_start']} → {summary['fit_end']} ({summary['n_rows']} rows)",
        f"**Heldout boundary:** {config['heldout_start']} (Stage C firewall)",
        "",
        "---",
        "",
        "## 1. Governance",
        "",
        "| Check | Result |",
        "| --- | --- |",
        "| Heldout rows (>= 2025-01-01) in fit data | NONE — PASS |",
        "| Validation data used for fitting | NONE — transform-only |",
        "| Timestamp column present and valid | PASS |",
        "| Timestamps monotonic, no duplicates | PASS |",
        "| uses_heldout | false |",
        "| fit_excludes_heldout_2025 | true |",
        "| Model type | KMeans (no HMM) — train-only smoke baseline |",
        "",
        "---",
        "",
        "## 2. Regime Features",
        "",
        f"Input features for clustering ({len(config['regime_features'])}):",
        "",
    ]
    for f in config["regime_features"]:
        lines.append(f"  - `{f}`")
    lines += [
        "",
        "Output columns per bar:",
        "  - `unsup_regime_id` — integer cluster label 0…{k-1}",
        "  - `unsup_regime_prob_0` … `unsup_regime_prob_{k-1}` — softmax probabilities",
        "  - `unsup_regime_entropy` — Shannon entropy (nats); max = ln(k) = "
        f"{max_H:.4f}",
        "  - `unsup_regime_transition_prob` — 1 if label changed vs previous bar",
        "  - `unsup_regime_persistence` — consecutive bars in current regime",
        "",
        "---",
        "",
        "## 3. Regime Distribution",
        "",
        "| Regime | Count | Fraction |",
        "| --- | --- | --- |",
    ]
    total = summary["n_rows"]
    for k, cnt in sorted(summary["label_counts"].items()):
        lines.append(f"| {k} | {cnt} | {cnt/total:.3f} |")
    lines += [
        "",
        f"Mean entropy: **{summary['mean_entropy']:.4f}** nats "
        f"(max possible: {max_H:.4f} nats)",
        f"Total regime transitions: **{summary['n_transitions']}** "
        f"({summary['n_transitions']/total:.3f} per bar)",
        f"Mean persistence: **{summary['mean_persistence']:.1f}** bars per regime run",
        "",
        "---",
        "",
        "## 4. Split Compliance",
        "",
        "This artifact was produced by `stage3x_regime_smoke_worker.py`.  "
        "The fitted pipeline (StandardScaler + KMeans) is saved to "
        "`kmeans_pipeline.pkl` and must only be applied via `.transform()` / "
        "`.predict()` to any future validation or heldout data — never via "
        "`.fit()` or `.fit_transform()`.  "
        "The `metadata.json` records `uses_heldout=false` and "
        "`fit_excludes_heldout_2025=true`.",
        "",
        "To apply to validation rows:",
        "```python",
        "scaler, km = joblib.load('kmeans_pipeline.pkl')",
        "X_val = validation_df[config['regime_features']].values",
        "Xs_val = scaler.transform(X_val)   # transform-only",
        "labels_val = km.predict(Xs_val)     # predict-only",
        "```",
        "",
        "---",
        "",
        "## 5. Outputs",
        "",
    ]
    for p in output_paths:
        lines.append(f"  - `{p.relative_to(ROOT)}`")
    lines += [
        "",
        f"*Generated by stage3x_regime_smoke_worker.py at "
        f"{datetime.now(timezone.utc).isoformat()}*",
    ]
    out = out_dir / "regime_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    FEATURE_OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Artifact dir : {ARTIFACT_DIR}")
    print(f"[INFO] Feature dir  : {FEATURE_OUT_DIR}")

    # ---- Load data ----
    if not TRAIN_CSV.exists():
        print(f"[ERROR] train.csv not found: {TRAIN_CSV}", file=sys.stderr)
        sys.exit(1)
    df_raw = pd.read_csv(TRAIN_CSV)
    print(f"[INFO] Loaded {len(df_raw)} rows, {len(df_raw.columns)} columns")

    # ---- Split guard: validate timestamps, assert no heldout rows ----
    try:
        ts_series = validate_timestamps(
            df_raw, TIMESTAMP_COL,
            require_monotonic=True,
            allow_duplicates=False,
        )
        assert_no_heldout_rows(
            df_raw, TIMESTAMP_COL, HELDOUT_START,
            context="regime_smoke_worker",
        )
    except SplitViolation as exc:
        print(f"[ERROR] Split guard violation: {exc}", file=sys.stderr)
        sys.exit(2)

    # Exclude any rows >= 2024-01-01 from the fit (belt-and-suspenders;
    # the train.csv already ends at 2023-12-31, but guard explicitly)
    val_boundary = pd.Timestamp("2024-01-01", tz="UTC")
    val_mask = ts_series >= val_boundary
    if val_mask.any():
        n_val = int(val_mask.sum())
        print(f"[WARN] Excluding {n_val} rows >= 2024-01-01 from fit (validation window).")
    train_df = df_raw[~val_mask].copy()
    train_ts  = ts_series[~val_mask]

    print(f"[INFO] Train rows   : {len(train_df)}")
    print(f"[INFO] Fit window   : {train_ts.min().isoformat()} → {train_ts.max().isoformat()}")

    # ---- Verify all required regime feature columns are present ----
    missing = [c for c in REGIME_FEATURES if c not in train_df.columns]
    if missing:
        print(f"[ERROR] Missing regime feature columns: {missing}", file=sys.stderr)
        sys.exit(3)

    # ---- Fit pipeline ----
    print(f"[INFO] Fitting StandardScaler + KMeans (k={N_REGIMES}, seed={RANDOM_SEED})...")
    X_train = train_df[REGIME_FEATURES].values
    scaler, km = fit_pipeline(
        X_train,
        n_regimes=N_REGIMES,
        random_seed=RANDOM_SEED,
        n_init=CONFIG["kmeans_n_init"],
        max_iter=CONFIG["kmeans_max_iter"],
    )
    print(f"[INFO] KMeans fitted. Inertia={km.inertia_:.2f}")

    # ---- Transform train data ----
    print("[INFO] Transforming train data...")
    result = transform_pipeline(
        X_train, scaler, km,
        temperature=CONFIG["prob_temperature"],
    )
    regime_df = build_regime_df(train_ts, result, TIMESTAMP_COL)

    # ---- Summary ----
    summary = regime_summary(regime_df, train_ts, N_REGIMES)
    print(f"[INFO] Regime distribution: {summary['label_counts']}")
    print(f"[INFO] Mean entropy: {summary['mean_entropy']:.4f} nats "
          f"(max={summary['max_entropy']:.4f})")

    # ---- Write artifacts ----
    regime_train_path = ARTIFACT_DIR / "regime_features_train.parquet"
    pipeline_path     = ARTIFACT_DIR / "kmeans_pipeline.pkl"
    feature_join_path = FEATURE_OUT_DIR / "regime_smoke_tech_stat.parquet"
    meta_path         = ARTIFACT_DIR / "metadata.json"

    print("[INFO] Writing regime_features_train.parquet...")
    regime_df.to_parquet(regime_train_path, index=False)

    print("[INFO] Writing kmeans_pipeline.pkl...")
    joblib.dump({"scaler": scaler, "km": km, "config": CONFIG}, pipeline_path)

    print("[INFO] Writing regime_smoke_tech_stat.parquet (joinable feature file)...")
    # The joinable file is a copy of regime_features_train — same content,
    # stored under the canonical feature path for RL consumption.
    regime_df.to_parquet(feature_join_path, index=False)

    # ---- Metadata ----
    output_paths_so_far = [regime_train_path, pipeline_path, feature_join_path]
    meta = build_metadata(
        artifact_type="regime_smoke",
        asset=CONFIG["asset"],
        timeframe=CONFIG["timeframe"],
        config=CONFIG,
        input_paths=[TRAIN_CSV],
        output_paths=output_paths_so_far,
        fit_df_timestamps=train_ts,
        feature_family=CONFIG["feature_family"],
        model_class="sklearn.cluster.KMeans + sklearn.preprocessing.StandardScaler",
        random_seed=RANDOM_SEED,
        fit_columns=REGIME_FEATURES,
        notes=(
            f"Train-only KMeans regime smoke artifact. k={N_REGIMES}, seed={RANDOM_SEED}. "
            "Soft probabilities via softmax of negative centroid distances. "
            "Pipeline saved to kmeans_pipeline.pkl for transform-only validation use."
        ),
        repo_root=ROOT,
    )
    write_metadata(meta, meta_path)
    print(f"[INFO] Wrote metadata.json")

    # ---- Markdown report ----
    report_path = write_report(
        ARTIFACT_DIR, summary, CONFIG, output_paths_so_far + [meta_path]
    )
    print(f"[INFO] Wrote regime_report.md")

    # ---- Validate join alignment ----
    print("[INFO] Validating timestamp join alignment...")
    validate_feature_join(
        train_df,
        regime_df,
        TIMESTAMP_COL,
        heldout_start=HELDOUT_START,
        allow_missing_in_feature=False,
        context="regime_smoke_train_join",
    )
    print("[INFO] Join validation: PASS")

    # ---- Update output manifest with report ----
    all_outputs = output_paths_so_far + [meta_path, report_path]
    meta.output_paths.append(str(report_path))
    meta.output_manifest_hash = compute_manifest_hash(all_outputs)
    write_metadata(meta, meta_path)

    # ---- Update registry ----
    print("[INFO] Updating registry.json...")
    artifact_entry = {
        "artifact_type":  "regime_smoke",
        "asset":          CONFIG["asset"],
        "timeframe":      CONFIG["timeframe"],
        "feature_family": CONFIG["feature_family"],
        "method":         "KMeans",
        "n_regimes":      N_REGIMES,
        "fit_start":      summary["fit_start"],
        "fit_end":        summary["fit_end"],
        "uses_heldout":   False,
        "metadata_path":  str(meta_path),
        "output_dir":     str(ARTIFACT_DIR),
        "feature_path":   str(feature_join_path),
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "config_hash":    compute_config_hash(CONFIG),
        "leakage_checks": {
            "heldout_timestamp_exclusion": "CHECKED",
            "fit_window_precedes_validation": "CHECKED",
        },
    }
    update_registry(REGISTRY_JSON, artifact_entry)

    # ---- Final summary ----
    print()
    print("=" * 62)
    print("REGIME SMOKE ARTIFACT COMPLETE")
    print("=" * 62)
    print(f"  Asset / Timeframe  : {CONFIG['asset']} / {CONFIG['timeframe']}")
    print(f"  Feature family     : {CONFIG['feature_family']}")
    print(f"  Method             : KMeans (k={N_REGIMES})")
    print(f"  Fit rows           : {len(train_df)}")
    print(f"  Fit window         : {summary['fit_start']} → {summary['fit_end']}")
    print(f"  Regime distribution: {summary['label_counts']}")
    print(f"  Mean entropy       : {summary['mean_entropy']:.4f} nats")
    print(f"  Transitions        : {summary['n_transitions']}")
    print(f"  uses_heldout       : false")
    print(f"  Join alignment     : PASS")
    print("=" * 62)
    print(f"[INFO] Outputs: {ARTIFACT_DIR}")
    print(f"[INFO] Feature : {feature_join_path}")


if __name__ == "__main__":
    main()
