#!/usr/bin/env python3
"""
Stage 3X P0-D Feature Redundancy and Stability Worker

Computes train-only feature redundancy and stability reports for ETHUSDT 4h tech_stat.

Governance:
  - All fitting uses train rows only (2017-09-28 to 2023-12-31).
  - Heldout rows (>= 2025-01-01) are firewalled via split_guard.assert_no_heldout_rows.
  - Outputs metadata.json with input_hashes, config_hash, fit_window, uses_heldout=false.

Outputs (experiments/unsup_causal_audit/artifacts/feature_redundancy_stability/ethusdt_4h_tech_stat/):
  pearson_corr.parquet               - 83 x 83 Pearson correlation matrix
  spearman_corr.parquet              - 83 x 83 Spearman rank-correlation matrix
  feature_cluster_representatives.yaml - greedy cluster assignments
  feature_stability_by_train_fold.csv - per-feature stats across 5 temporal folds
  feature_redundancy_stability_report.md - human-readable report
  metadata.json                      - ArtifactMetadata provenance record

Run:
    cd /home/harveybc/Documents/GitHub/financial-data
    python _scripts/workers/stage3x_feature_redundancy_stability_worker.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Repo paths
# ---------------------------------------------------------------------------

ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(ROOT))

from _scripts.lib.split_guard import (
    SplitViolation,
    assert_no_heldout_rows,
    assert_no_fit_on_validation,
    validate_timestamps,
)
from _scripts.lib.artifact_metadata import (
    ArtifactMetadata,
    build_metadata,
    compute_config_hash,
    compute_file_hash,
    write_metadata,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TRAIN_CSV = (
    ROOT / "experiments/stage_a_screening/inputs/ethusdt/4h/tech_stat/train.csv"
)
OUT_DIR = (
    ROOT
    / "experiments/unsup_causal_audit/artifacts"
    / "feature_redundancy_stability"
    / "ethusdt_4h_tech_stat"
)
REGISTRY_JSON = ROOT / "experiments/unsup_causal_audit/registry.json"

# ---------------------------------------------------------------------------
# Config (canonical — its hash goes into metadata)
# ---------------------------------------------------------------------------

CONFIG: dict[str, Any] = {
    "artifact_type":              "feature_redundancy_stability",
    "asset":                      "ethusdt",
    "timeframe":                  "4h",
    "feature_family":             "tech_stat",
    "timestamp_col":              "DATE_TIME",
    "heldout_start":              "2025-01-01T00:00:00Z",
    "corr_abs_threshold":         0.90,
    "corr_method_for_clustering": "pearson",
    "near_constant_std_threshold": 0.001,
    "near_constant_cv_threshold": 0.05,   # CV < this → near-constant in mean
    "n_train_folds":              5,
    "random_seed":                42,
    # Columns excluded from feature analysis (price/volume raw)
    "exclude_cols": ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"],
}

TIMESTAMP_COL = CONFIG["timestamp_col"]
HELDOUT_START = CONFIG["heldout_start"]

# ---------------------------------------------------------------------------
# Feature family definitions (by name prefix / substring pattern)
# Each feature belongs to exactly one family.  Order of matching matters.
# ---------------------------------------------------------------------------

FEATURE_FAMILIES: dict[str, list[str]] = {
    "returns":            [],
    "trend":              [],
    "momentum_oscillators": [],
    "bollinger":          [],
    "volatility":         [],
    "volume_liquidity":   [],
    "rolling_moments":    [],
    "regime_flags":       [],
    "other":              [],
}

_FAMILY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    # (family, tuple of substrings to match against column name)
    ("returns",            ("return_", "log_return_")),
    ("trend",              ("sma_", "ema_", "close_sma_ratio_", "macd",
                            "ema_cross_", "trend_slope_", "trend_strength_")),
    ("bollinger",          ("bb_",)),
    ("momentum_oscillators", ("rsi_", "stoch_", "williams_", "cci_",
                              "roc_", "mom_")),
    ("volatility",         ("atr_", "natr_", "hist_vol_", "realized_var_")),
    ("volume_liquidity",   ("obv", "volume_sma_", "volume_ratio_", "vwap_", "mfi_")),
    ("rolling_moments",    ("statistical__", "roll_", "autocorr_", "sqret_")),
    ("regime_flags",       ("vol_regime_", "hurst_", "zscore_")),
]


def _assign_family(col: str) -> str:
    for family, patterns in _FAMILY_PATTERNS:
        for p in patterns:
            if p in col:
                return family
    return "other"


def build_family_map(feat_cols: list[str]) -> dict[str, str]:
    """Return {col: family} for every feature column."""
    return {c: _assign_family(c) for c in feat_cols}


def group_by_family(feat_cols: list[str]) -> dict[str, list[str]]:
    """Return {family: [col, ...]} for every feature column."""
    groups: dict[str, list[str]] = {k: [] for k in FEATURE_FAMILIES}
    for c in feat_cols:
        groups[_assign_family(c)].append(c)
    return {k: v for k, v in groups.items() if v}  # drop empty families


# ---------------------------------------------------------------------------
# Correlation helpers
# ---------------------------------------------------------------------------

def compute_pearson(df: pd.DataFrame, feat_cols: list[str]) -> pd.DataFrame:
    return df[feat_cols].corr(method="pearson")


def compute_spearman(df: pd.DataFrame, feat_cols: list[str]) -> pd.DataFrame:
    return df[feat_cols].corr(method="spearman")


# ---------------------------------------------------------------------------
# Near-constant feature detection
# ---------------------------------------------------------------------------

def near_constant_report(
    df: pd.DataFrame,
    feat_cols: list[str],
    *,
    std_threshold: float = 0.001,
    cv_threshold: float = 0.05,
) -> pd.DataFrame:
    """
    Report features that are:
      - near-zero absolute std (std < std_threshold)
      - near-zero coefficient of variation (|mean| >> std: CV < cv_threshold)
      - binary flags (only 2 unique values)

    Returns a DataFrame with one row per feature.
    """
    records = []
    for col in feat_cols:
        s = df[col]
        n_unique = int(s.nunique())
        std = float(s.std())
        mean = float(s.mean())
        cv = abs(std / mean) if abs(mean) > 1e-12 else float("inf")
        is_binary = n_unique <= 2
        is_near_const_std = std < std_threshold
        is_near_const_cv = cv < cv_threshold and not math.isinf(cv)
        records.append({
            "feature":           col,
            "mean":              round(mean, 8),
            "std":               round(std, 8),
            "cv":                round(cv, 6) if not math.isinf(cv) else None,
            "n_unique":          n_unique,
            "is_binary_flag":    is_binary,
            "is_near_const_std": is_near_const_std,
            "is_near_const_cv":  is_near_const_cv,
            "flag":              (
                "BINARY_FLAG"      if is_binary and not is_near_const_std
                else "NEAR_CONST"  if is_near_const_std or is_near_const_cv
                else ""
            ),
        })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Missingness / warmup profile
# ---------------------------------------------------------------------------

def warmup_profile(df: pd.DataFrame, feat_cols: list[str]) -> pd.DataFrame:
    """
    For each feature: count NaN rows, first non-NaN index, warmup rows.
    Even if the CSV has been pre-filled (no NaN), report the first row where
    the rolling window would be fully initialised (heuristic from column name).
    """
    records = []
    for col in feat_cols:
        n_nan = int(df[col].isnull().sum())
        first_valid = int(df[col].first_valid_index() or 0)
        # Heuristic warmup from column name (e.g. sma_200 → 200)
        warmup_heuristic = _warmup_heuristic(col)
        records.append({
            "feature":           col,
            "n_nan":             n_nan,
            "first_valid_idx":   first_valid,
            "warmup_heuristic":  warmup_heuristic,
            "note": (
                f"Pre-filled (NaN→0) if n_nan=0 but warmup_heuristic>0"
                if n_nan == 0 and warmup_heuristic > 0
                else ("NaN rows present" if n_nan > 0 else "")
            ),
        })
    return pd.DataFrame(records)


def _warmup_heuristic(col: str) -> int:
    """Parse the largest integer suffix from a column name as its warmup period."""
    import re
    nums = re.findall(r"\d+", col)
    if not nums:
        return 0
    return max(int(n) for n in nums)


# ---------------------------------------------------------------------------
# Greedy cluster representatives
# ---------------------------------------------------------------------------

def greedy_cluster_representatives(
    corr_abs: pd.DataFrame,
    threshold: float,
    *,
    prefer_order: list[str] | None = None,
) -> dict[str, Any]:
    """
    Greedy algorithm for finding cluster representatives.

    Selection order:
      1. If prefer_order is given, iterate features in that order.
         (Use original column order for determinism.)
      2. For the next unassigned feature: designate it as representative.
      3. Assign all currently unassigned features with |corr| >= threshold
         to this representative's cluster.
      4. Continue until every feature has been assigned.

    Returns a dict with:
      "clusters": list of {representative, members, n_members, cluster_id}
      "feature_to_cluster": {feature: representative}
      "n_clusters": int
      "threshold": float
      "method": "greedy_column_order"
    """
    cols = list(prefer_order) if prefer_order else list(corr_abs.columns)
    assert set(cols) == set(corr_abs.columns), "prefer_order must match corr matrix cols"

    assigned: dict[str, str] = {}   # feature → representative
    clusters: list[dict[str, Any]] = []
    cluster_id = 0

    for col in cols:
        if col in assigned:
            continue
        # This feature becomes a representative
        assigned[col] = col
        members = [col]
        # Find all other unassigned features correlated >= threshold with this rep
        for other in cols:
            if other == col or other in assigned:
                continue
            if corr_abs.loc[col, other] >= threshold:
                assigned[other] = col
                members.append(other)
        clusters.append({
            "cluster_id":    cluster_id,
            "representative": col,
            "members":        members,
            "n_members":      len(members),
        })
        cluster_id += 1

    return {
        "clusters":          clusters,
        "feature_to_cluster": assigned,
        "n_clusters":         len(clusters),
        "threshold":          threshold,
        "method":             "greedy_column_order",
        "n_features_total":   len(cols),
        "n_standalone":       sum(1 for c in clusters if c["n_members"] == 1),
    }


# ---------------------------------------------------------------------------
# Chronological fold stability
# ---------------------------------------------------------------------------

def fold_stability(
    df: pd.DataFrame,
    feat_cols: list[str],
    n_folds: int,
    timestamp_col: str = "DATE_TIME",
) -> pd.DataFrame:
    """
    Divide df chronologically into n_folds of approximately equal size.
    For each fold, compute per-feature: mean, std, min, max, CV.

    Returns a tidy DataFrame with columns:
      fold_id, fold_start, fold_end, fold_n_rows, feature, mean, std, min, max, cv
    """
    n = len(df)
    fold_size = n // n_folds
    ts = pd.to_datetime(df[timestamp_col], utc=True)

    records = []
    for i in range(n_folds):
        start_idx = i * fold_size
        end_idx = (i + 1) * fold_size if i < n_folds - 1 else n
        fold_df = df.iloc[start_idx:end_idx]
        fold_ts = ts.iloc[start_idx:end_idx]
        fold_start = fold_ts.iloc[0].isoformat()
        fold_end = fold_ts.iloc[-1].isoformat()
        fold_n = len(fold_df)

        for col in feat_cols:
            s = fold_df[col]
            mean_v = float(s.mean())
            std_v = float(s.std())
            min_v = float(s.min())
            max_v = float(s.max())
            cv = abs(std_v / mean_v) if abs(mean_v) > 1e-12 else None
            records.append({
                "fold_id":      i,
                "fold_start":   fold_start,
                "fold_end":     fold_end,
                "fold_n_rows":  fold_n,
                "feature":      col,
                "mean":         round(mean_v, 8),
                "std":          round(std_v, 8),
                "min":          round(min_v, 8),
                "max":          round(max_v, 8),
                "cv":           round(cv, 6) if cv is not None else None,
            })
    return pd.DataFrame(records)


def fold_stability_summary(stability_df: pd.DataFrame) -> pd.DataFrame:
    """
    From fold_stability output, compute per-feature:
      - mean_std_across_folds: average of per-fold stds
      - std_of_std_across_folds: std of per-fold stds
      - cv_of_std: coefficient of variation of std across folds (lower = more stable)
      - stability_rank: rank by cv_of_std (1 = most stable)
    """
    grp = stability_df.groupby("feature")["std"]
    summary = pd.DataFrame({
        "mean_std":    grp.mean(),
        "std_of_std":  grp.std(),
    })
    summary["cv_of_std"] = summary["std_of_std"] / summary["mean_std"].clip(lower=1e-12)
    summary = summary.sort_values("cv_of_std")
    summary["stability_rank"] = range(1, len(summary) + 1)
    return summary.reset_index().rename(columns={"index": "feature"})


# ---------------------------------------------------------------------------
# Registry update
# ---------------------------------------------------------------------------

def update_registry(
    registry_path: Path,
    artifact_entry: dict[str, Any],
) -> None:
    """Add or replace an artifact entry in registry.json (keyed by artifact_type+asset+timeframe)."""
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    key = (
        artifact_entry.get("artifact_type", ""),
        artifact_entry.get("asset", ""),
        artifact_entry.get("timeframe", ""),
        artifact_entry.get("feature_family", ""),
    )
    existing = registry.setdefault("artifacts", [])
    for i, e in enumerate(existing):
        if (e.get("artifact_type"), e.get("asset"),
                e.get("timeframe"), e.get("feature_family")) == key:
            existing[i] = artifact_entry
            break
    else:
        existing.append(artifact_entry)
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_md_report(
    out_dir: Path,
    feat_cols: list[str],
    family_groups: dict[str, list[str]],
    near_const_df: pd.DataFrame,
    warmup_df: pd.DataFrame,
    cluster_result: dict[str, Any],
    stability_summary: pd.DataFrame,
    pearson_corr: pd.DataFrame,
    config: dict[str, Any],
    fit_start: str,
    fit_end: str,
    fit_n_rows: int,
) -> Path:
    lines: list[str] = [
        "# Feature Redundancy and Stability Report",
        "",
        f"**Asset:** {config['asset']}  **Timeframe:** {config['timeframe']}  "
        f"**Feature family:** {config['feature_family']}",
        f"**Fit window:** {fit_start} → {fit_end} ({fit_n_rows} rows)",
        f"**Heldout boundary:** {config['heldout_start']} (Stage C firewall)",
        f"**Correlation clustering threshold:** |r| ≥ {config['corr_abs_threshold']}",
        f"**Chronological folds:** {config['n_train_folds']}",
        "",
        "---",
        "",
        "## 1. Feature Count and Family Grouping",
        "",
        f"Total feature columns analysed: **{len(feat_cols)}**",
        "",
        "| Family | Count | Features (truncated) |",
        "| --- | --- | --- |",
    ]
    for family, cols in sorted(family_groups.items()):
        preview = ", ".join(cols[:5]) + (f", … (+{len(cols)-5})" if len(cols) > 5 else "")
        lines.append(f"| {family} | {len(cols)} | {preview} |")

    lines += [
        "",
        "---",
        "",
        "## 2. Near-Constant and Binary Features",
        "",
    ]
    flagged = near_const_df[near_const_df["flag"] != ""]
    if flagged.empty:
        lines.append(f"No near-constant features found (threshold: std < {config['near_constant_std_threshold']}).")
    else:
        lines += [
            f"| Feature | Flag | std | mean | n_unique |",
            "| --- | --- | --- | --- | --- |",
        ]
        for _, r in flagged.iterrows():
            lines.append(
                f"| {r['feature']} | {r['flag']} | {r['std']:.6f} | {r['mean']:.6f} | {r['n_unique']} |"
            )

    lines += [
        "",
        "---",
        "",
        "## 3. Missingness and Warmup Profile",
        "",
    ]
    has_nan = warmup_df[warmup_df["n_nan"] > 0]
    if has_nan.empty:
        lines.append(
            "All features have zero NaN rows in the train CSV.  "
            "Warmup rows may have been pre-filled to 0 by the feature-engineering pipeline."
        )
    else:
        lines += [
            "| Feature | n_nan | first_valid_idx | warmup_heuristic |",
            "| --- | --- | --- | --- |",
        ]
        for _, r in has_nan.iterrows():
            lines.append(
                f"| {r['feature']} | {r['n_nan']} | {r['first_valid_idx']} | {r['warmup_heuristic']} |"
            )

    lines += [
        "",
        "Features with longest heuristic warmup period (top 10):",
        "",
        "| Feature | warmup_heuristic |",
        "| --- | --- |",
    ]
    for _, r in warmup_df.nlargest(10, "warmup_heuristic").iterrows():
        lines.append(f"| {r['feature']} | {r['warmup_heuristic']} |")

    lines += [
        "",
        "---",
        "",
        "## 4. Perfect and Near-Perfect Correlations (|r| ≥ 0.99)",
        "",
    ]
    # Find top correlated pairs
    corr_vals = pearson_corr.copy()
    corr_array = corr_vals.to_numpy(copy=True)
    np.fill_diagonal(corr_array, np.nan)
    corr_vals = pd.DataFrame(corr_array, index=corr_vals.index, columns=corr_vals.columns)
    stack = corr_vals.abs().stack().dropna().sort_values(ascending=False)
    seen: set[frozenset] = set()
    perfect_pairs = []
    for (a, b), v in stack.items():
        if frozenset({a, b}) in seen or v < 0.99:
            break
        seen.add(frozenset({a, b}))
        perfect_pairs.append((a, b, float(v)))

    if perfect_pairs:
        lines += [
            "| Feature A | Feature B | |r| |",
            "| --- | --- | --- |",
        ]
        for a, b, v in perfect_pairs[:20]:
            lines.append(f"| {a} | {b} | {v:.6f} |")
        lines.append("")
        lines.append(
            f"> **{len(perfect_pairs)} feature pair(s)** with |r| ≥ 0.99.  "
            "These are functionally redundant and one of each pair can be dropped."
        )
    else:
        lines.append("No feature pairs with |r| ≥ 0.99.")

    lines += [
        "",
        "---",
        "",
        "## 5. Greedy Cluster Representatives",
        "",
        f"Clustering method: **{cluster_result['method']}**  "
        f"  Threshold: |r| ≥ {cluster_result['threshold']}",
        f"Total features: {cluster_result['n_features_total']}  "
        f"  Clusters: {cluster_result['n_clusters']}  "
        f"  Standalone: {cluster_result['n_standalone']}",
        "",
        "Clusters with more than 1 member (showing representative → members):",
        "",
    ]
    multi = [c for c in cluster_result["clusters"] if c["n_members"] > 1]
    if multi:
        lines += ["| Cluster ID | Representative | n_members | Members |", "| --- | --- | --- | --- |"]
        for c in multi:
            members_str = ", ".join(c["members"])
            lines.append(f"| {c['cluster_id']} | {c['representative']} | {c['n_members']} | {members_str} |")
    else:
        lines.append("No clusters with more than 1 member at this threshold.")

    lines += [
        "",
        "---",
        "",
        "## 6. Feature Stability Across Chronological Train Folds",
        "",
        f"({config['n_train_folds']} equal-size chronological folds over the train window.)",
        "",
        "**Most stable features** (lowest CV of std across folds):",
        "",
        "| Rank | Feature | mean_std | std_of_std | cv_of_std |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, r in stability_summary.head(10).iterrows():
        lines.append(
            f"| {int(r['stability_rank'])} | {r['feature']} | "
            f"{r['mean_std']:.6f} | {r['std_of_std']:.6f} | {r['cv_of_std']:.4f} |"
        )

    lines += [
        "",
        "**Least stable features** (highest CV of std across folds):",
        "",
        "| Rank | Feature | mean_std | std_of_std | cv_of_std |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, r in stability_summary.tail(10).sort_values("cv_of_std", ascending=False).iterrows():
        lines.append(
            f"| {int(r['stability_rank'])} | {r['feature']} | "
            f"{r['mean_std']:.6f} | {r['std_of_std']:.6f} | {r['cv_of_std']:.4f} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 7. Governance",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| Heldout rows (>= 2025-01-01) in fit data | NONE — PASS |",
        f"| Validation rows used for fitting | NONE — PASS |",
        f"| Timestamp column present and valid | PASS |",
        f"| Timestamps monotonic, no duplicates | PASS |",
        f"| uses_heldout | false |",
        f"| fit_excludes_heldout_2025 | true |",
        "",
        "---",
        "",
        f"*Generated by stage3x_feature_redundancy_stability_worker.py  "
        f"at {datetime.now(timezone.utc).isoformat()}*",
    ]

    out_path = out_dir / "feature_redundancy_stability_report.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Output directory: {OUT_DIR}")
    print(f"[INFO] Input: {TRAIN_CSV}")

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
            context="feature_redundancy_stability_worker",
        )
        # Also confirm no validation-window timestamps (>= 2024-01-01) are present.
        # The train.csv ends at 2023-12-31, so this is belt-and-suspenders.
        val_boundary = pd.Timestamp("2024-01-01", tz="UTC")
        val_rows = (ts_series >= val_boundary)
        if val_rows.any():
            n = int(val_rows.sum())
            print(
                f"[WARN] {n} rows in train.csv fall in the validation window "
                f"(>= 2024-01-01). They will NOT be used for fitting."
            )
        # Keep only rows strictly before the validation window for fitting
        train_df = df_raw[~val_rows].copy() if val_rows.any() else df_raw.copy()
        train_ts = ts_series[~val_rows] if val_rows.any() else ts_series
    except SplitViolation as exc:
        print(f"[ERROR] Split guard violation: {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"[INFO] Train rows after split guard: {len(train_df)}")
    fit_start = train_ts.min().isoformat()
    fit_end = train_ts.max().isoformat()
    print(f"[INFO] Fit window: {fit_start} → {fit_end}")

    # ---- Feature columns ----
    exclude = set(CONFIG["exclude_cols"]) | {TIMESTAMP_COL}
    feat_cols = [c for c in train_df.columns if c not in exclude]
    print(f"[INFO] Feature columns: {len(feat_cols)}")

    # ---- Feature family grouping ----
    family_groups = group_by_family(feat_cols)
    print(f"[INFO] Feature families: {list(family_groups.keys())}")

    # ---- Correlation matrices ----
    print("[INFO] Computing Pearson correlation...")
    pearson_corr = compute_pearson(train_df, feat_cols)

    print("[INFO] Computing Spearman correlation...")
    spearman_corr = compute_spearman(train_df, feat_cols)

    # ---- Near-constant detection ----
    near_const_df = near_constant_report(
        train_df, feat_cols,
        std_threshold=CONFIG["near_constant_std_threshold"],
        cv_threshold=CONFIG["near_constant_cv_threshold"],
    )

    # ---- Warmup / missingness ----
    warmup_df = warmup_profile(train_df, feat_cols)

    # ---- Greedy cluster representatives ----
    print("[INFO] Computing greedy cluster representatives...")
    corr_abs = pearson_corr.abs() if CONFIG["corr_method_for_clustering"] == "pearson" \
        else spearman_corr.abs()
    cluster_result = greedy_cluster_representatives(
        corr_abs,
        threshold=CONFIG["corr_abs_threshold"],
        prefer_order=feat_cols,
    )
    print(
        f"[INFO] Clusters: {cluster_result['n_clusters']} "
        f"(standalone: {cluster_result['n_standalone']}, "
        f"multi-member: {cluster_result['n_clusters'] - cluster_result['n_standalone']})"
    )

    # ---- Chronological fold stability ----
    print(f"[INFO] Computing fold stability ({CONFIG['n_train_folds']} folds)...")
    stability_df = fold_stability(
        train_df, feat_cols,
        n_folds=CONFIG["n_train_folds"],
        timestamp_col=TIMESTAMP_COL,
    )
    stability_summary_df = fold_stability_summary(stability_df)

    # ---- Write outputs ----
    pearson_path = OUT_DIR / "pearson_corr.parquet"
    spearman_path = OUT_DIR / "spearman_corr.parquet"
    cluster_path = OUT_DIR / "feature_cluster_representatives.yaml"
    stability_path = OUT_DIR / "feature_stability_by_train_fold.csv"
    meta_path = OUT_DIR / "metadata.json"

    print("[INFO] Writing pearson_corr.parquet...")
    pearson_corr.to_parquet(pearson_path)

    print("[INFO] Writing spearman_corr.parquet...")
    spearman_corr.to_parquet(spearman_path)

    print("[INFO] Writing feature_cluster_representatives.yaml...")
    cluster_yaml: dict[str, Any] = {
        "config": {
            "corr_abs_threshold":         cluster_result["threshold"],
            "method":                     cluster_result["method"],
            "corr_method_for_clustering": CONFIG["corr_method_for_clustering"],
            "n_features_total":           cluster_result["n_features_total"],
            "n_clusters":                 cluster_result["n_clusters"],
            "n_standalone":               cluster_result["n_standalone"],
            "asset":                      CONFIG["asset"],
            "timeframe":                  CONFIG["timeframe"],
            "feature_family":             CONFIG["feature_family"],
        },
        "clusters": [
            {
                "cluster_id":    int(c["cluster_id"]),
                "representative": c["representative"],
                "n_members":      int(c["n_members"]),
                "members":        c["members"],
            }
            for c in cluster_result["clusters"]
        ],
        "feature_to_representative": cluster_result["feature_to_cluster"],
        "standalone_features": [
            c["representative"]
            for c in cluster_result["clusters"]
            if c["n_members"] == 1
        ],
    }
    with cluster_path.open("w", encoding="utf-8") as f:
        yaml.dump(cluster_yaml, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print("[INFO] Writing feature_stability_by_train_fold.csv...")
    stability_df.to_csv(stability_path, index=False)

    # ---- Metadata ----
    output_paths = [pearson_path, spearman_path, cluster_path, stability_path]
    meta = build_metadata(
        artifact_type="feature_redundancy_stability",
        asset=CONFIG["asset"],
        timeframe=CONFIG["timeframe"],
        config=CONFIG,
        input_paths=[TRAIN_CSV],
        output_paths=output_paths,
        fit_df_timestamps=train_ts,
        feature_family=CONFIG["feature_family"],
        model_class="pandas.DataFrame.corr + greedy_clustering",
        random_seed=CONFIG["random_seed"],
        fit_columns=feat_cols,
        notes=(
            f"Train-only feature redundancy/stability analysis. "
            f"Pearson/Spearman correlation matrices, near-constant detection, "
            f"greedy cluster representatives (|r|>={CONFIG['corr_abs_threshold']}), "
            f"and {CONFIG['n_train_folds']}-fold chronological stability."
        ),
        repo_root=ROOT,
    )
    # Update output_manifest_hash after writing outputs
    from _scripts.lib.artifact_metadata import compute_manifest_hash
    meta.output_manifest_hash = compute_manifest_hash(output_paths)
    write_metadata(meta, meta_path)
    print(f"[INFO] Wrote metadata.json")

    # ---- Markdown report ----
    print("[INFO] Writing feature_redundancy_stability_report.md...")
    report_path = write_md_report(
        out_dir=OUT_DIR,
        feat_cols=feat_cols,
        family_groups=family_groups,
        near_const_df=near_const_df,
        warmup_df=warmup_df,
        cluster_result=cluster_result,
        stability_summary=stability_summary_df,
        pearson_corr=pearson_corr,
        config=CONFIG,
        fit_start=fit_start,
        fit_end=fit_end,
        fit_n_rows=len(train_df),
    )

    # ---- Update metadata output_paths to include report ----
    output_paths.append(report_path)
    meta.output_paths.append(str(report_path))
    meta.output_manifest_hash = compute_manifest_hash(output_paths)
    write_metadata(meta, meta_path)

    # ---- Update registry ----
    print("[INFO] Updating registry.json...")
    artifact_entry = {
        "artifact_type":   "feature_redundancy_stability",
        "asset":           CONFIG["asset"],
        "timeframe":       CONFIG["timeframe"],
        "feature_family":  CONFIG["feature_family"],
        "fit_start":       fit_start,
        "fit_end":         fit_end,
        "uses_heldout":    False,
        "metadata_path":   str(meta_path),
        "output_dir":      str(OUT_DIR),
        "n_features":      len(feat_cols),
        "n_clusters":      cluster_result["n_clusters"],
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "config_hash":     compute_config_hash(CONFIG),
        "leakage_checks": {
            "heldout_timestamp_exclusion": "CHECKED",
            "fit_window_precedes_validation": "CHECKED",
        },
    }
    update_registry(REGISTRY_JSON, artifact_entry)
    print(f"[INFO] Registry updated: {REGISTRY_JSON}")

    # ---- Summary ----
    print()
    print("=" * 62)
    print("FEATURE REDUNDANCY AND STABILITY COMPLETE")
    print("=" * 62)
    print(f"  Asset / Timeframe:  {CONFIG['asset']} / {CONFIG['timeframe']}")
    print(f"  Feature family:     {CONFIG['feature_family']}")
    print(f"  Fit rows:           {len(train_df)}")
    print(f"  Fit window:         {fit_start} → {fit_end}")
    print(f"  Feature columns:    {len(feat_cols)}")
    print(f"  Near-constant:      {(near_const_df['flag'] != '').sum()}")
    print(f"  Binary flags:       {near_const_df['is_binary_flag'].sum()}")
    print(f"  Clusters (|r|≥{CONFIG['corr_abs_threshold']}): {cluster_result['n_clusters']}")
    print(f"  Standalone feats:   {cluster_result['n_standalone']}")
    print(f"  uses_heldout:       false")
    print("=" * 62)
    print(f"[INFO] Outputs written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
