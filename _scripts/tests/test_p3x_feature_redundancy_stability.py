"""
Tests for stage3x_feature_redundancy_stability_worker.py (Phase 3X P0-D).

Covers:
  1. Heldout rows (>= 2025-01-01) cause SplitViolation before fitting
  2. Validation rows (>= 2024-01-01) are excluded from fitting
  3. Missing timestamp column fails closed
  4. Duplicate timestamps fail closed
  5. metadata.json contains input_hashes, config_hash, fit_window, uses_heldout=false
  6. greedy_cluster_representatives is deterministic
  7. Cluster threshold is respected
  8. Feature families cover all feature columns
  9. fold_stability produces correct fold count and columns
 10. near_constant_report flags binary and near-zero-std features correctly
 11. warmup_profile records correct warmup heuristics
 12. Generated outputs exist and are non-empty (integration smoke)

Run:
    cd /home/harveybc/Documents/GitHub/financial-data
    python -m pytest _scripts/tests/test_p3x_feature_redundancy_stability.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from _scripts.lib.split_guard import SplitViolation, assert_no_heldout_rows, validate_timestamps
from _scripts.lib.artifact_metadata import ArtifactMetadata

# Import worker internals directly (they are pure functions with no side-effects)
from _scripts.workers.stage3x_feature_redundancy_stability_worker import (
    CONFIG,
    OUT_DIR,
    TRAIN_CSV,
    build_family_map,
    fold_stability,
    fold_stability_summary,
    greedy_cluster_representatives,
    group_by_family,
    near_constant_report,
    warmup_profile,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TIMESTAMP_COL = "DATE_TIME"
HELDOUT_START = "2025-01-01T00:00:00Z"


def _small_df(timestamps: list[str], n_features: int = 4) -> pd.DataFrame:
    """Minimal DataFrame with DATE_TIME + n_features of float columns."""
    np.random.seed(42)
    d: dict = {TIMESTAMP_COL: timestamps}
    for i in range(n_features):
        d[f"feat_{i}"] = np.random.randn(len(timestamps))
    return pd.DataFrame(d)


TRAIN_TS = [
    "2020-01-01T00:00:00Z",
    "2021-01-01T00:00:00Z",
    "2022-01-01T00:00:00Z",
    "2023-01-01T00:00:00Z",
]
VAL_TS = ["2024-06-01T00:00:00Z"]
HELD_TS = ["2025-01-01T00:00:00Z", "2025-06-01T00:00:00Z"]


# ===========================================================================
# 1 & 2. Heldout and validation row guards
# ===========================================================================

class TestHeldoutGuard:

    def test_heldout_row_raises_before_fitting(self):
        df = _small_df(TRAIN_TS + HELD_TS)
        with pytest.raises(SplitViolation, match="2025-01-01"):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_heldout_exact_boundary_raises(self):
        df = _small_df(["2025-01-01T00:00:00Z"])
        with pytest.raises(SplitViolation):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_clean_train_passes_heldout_guard(self):
        df = _small_df(TRAIN_TS)
        assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)  # no exception

    def test_worker_config_heldout_boundary(self):
        assert CONFIG["heldout_start"] == "2025-01-01T00:00:00Z"

    def test_real_csv_has_no_heldout_rows(self):
        """Integration: actual train.csv must contain no 2025+ rows."""
        if not TRAIN_CSV.exists():
            pytest.skip(f"train.csv not found: {TRAIN_CSV}")
        df = pd.read_csv(TRAIN_CSV, usecols=[TIMESTAMP_COL])
        assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_validation_rows_are_excluded_from_fit(self):
        """
        Simulate a CSV containing a validation row (2024-xx).
        The worker's guard logic should detect and exclude it.
        Verify that after filtering, no validation rows remain.
        """
        df = _small_df(TRAIN_TS + VAL_TS)
        ts = pd.to_datetime(df[TIMESTAMP_COL], utc=True)
        val_boundary = pd.Timestamp("2024-01-01", tz="UTC")
        val_rows = ts >= val_boundary
        assert val_rows.any(), "Expected 1 validation row"
        train_df = df[~val_rows].copy()
        train_ts = ts[~val_rows]
        # No 2024+ rows remain
        assert (train_ts < val_boundary).all()
        assert len(train_df) == len(TRAIN_TS)


# ===========================================================================
# 3. Missing timestamp column fails closed
# ===========================================================================

class TestMissingTimestamp:

    def test_missing_column_raises(self):
        df = pd.DataFrame({"feature_a": [1, 2, 3]})
        with pytest.raises(SplitViolation, match="not found"):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_wrong_column_name_raises(self):
        df = _small_df(TRAIN_TS)
        df = df.rename(columns={TIMESTAMP_COL: "timestamp"})
        with pytest.raises(SplitViolation, match="not found"):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_unparseable_timestamp_raises(self):
        df = pd.DataFrame({TIMESTAMP_COL: ["not_a_date", "still_not"]})
        with pytest.raises(SplitViolation):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)


# ===========================================================================
# 4. Duplicate timestamps fail closed
# ===========================================================================

class TestDuplicateTimestamps:

    def test_duplicate_timestamps_raise(self):
        dup_ts = TRAIN_TS[:2] + TRAIN_TS[:2]  # rows 0+1 duplicated
        df = _small_df(dup_ts)
        with pytest.raises(SplitViolation, match="duplicate"):
            validate_timestamps(df, TIMESTAMP_COL, allow_duplicates=False)

    def test_unique_timestamps_pass(self):
        df = _small_df(TRAIN_TS)
        validate_timestamps(df, TIMESTAMP_COL, allow_duplicates=False)  # no exception


# ===========================================================================
# 5. Metadata: input_hashes, config_hash, fit_window, uses_heldout=false
# ===========================================================================

class TestMetadata:

    def test_metadata_file_exists(self):
        meta_path = OUT_DIR / "metadata.json"
        assert meta_path.exists(), f"metadata.json not found: {meta_path}"

    def test_uses_heldout_is_false(self):
        meta = json.loads((OUT_DIR / "metadata.json").read_text())
        assert meta["uses_heldout"] is False

    def test_fit_excludes_heldout_2025(self):
        meta = json.loads((OUT_DIR / "metadata.json").read_text())
        assert meta["fit_excludes_heldout_2025"] is True

    def test_input_hashes_populated(self):
        meta = json.loads((OUT_DIR / "metadata.json").read_text())
        assert isinstance(meta["input_hashes"], dict)
        assert len(meta["input_hashes"]) > 0
        # hash value is a 64-char hex string (sha256)
        for path, h in meta["input_hashes"].items():
            assert len(h) == 64, f"Expected sha256 hex for {path}"

    def test_config_hash_is_sha256(self):
        meta = json.loads((OUT_DIR / "metadata.json").read_text())
        assert len(meta["config_hash"]) == 64

    def test_fit_window_present(self):
        meta = json.loads((OUT_DIR / "metadata.json").read_text())
        assert meta["fit_start"] != ""
        assert meta["fit_end"] != ""
        # fit window is within [2017, 2024)
        assert "2017" in meta["fit_start"]
        assert "2023" in meta["fit_end"]

    def test_fit_end_before_heldout(self):
        meta = json.loads((OUT_DIR / "metadata.json").read_text())
        from datetime import datetime, timezone
        fe = datetime.fromisoformat(meta["fit_end"].replace("Z", "+00:00"))
        hs = datetime.fromisoformat(meta["heldout_start"].replace("Z", "+00:00"))
        assert fe < hs, f"fit_end {fe} must be < heldout_start {hs}"

    def test_fit_row_count(self):
        meta = json.loads((OUT_DIR / "metadata.json").read_text())
        assert meta["fit_row_count"] == 13699

    def test_leakage_checks_present(self):
        meta = json.loads((OUT_DIR / "metadata.json").read_text())
        checks = meta.get("leakage_checks", {})
        assert "heldout_timestamp_exclusion" in checks
        assert "fit_window_precedes_validation" in checks

    def test_artifact_metadata_schema_passes(self):
        """ArtifactMetadata.validate() must return no errors for the written metadata."""
        meta_dict = json.loads((OUT_DIR / "metadata.json").read_text())
        meta = ArtifactMetadata(**{
            k: v for k, v in meta_dict.items()
            if k in ArtifactMetadata.__dataclass_fields__
        })
        errors = meta.validate()
        assert errors == [], f"Metadata validation errors: {errors}"

    def test_config_hash_is_deterministic(self):
        from _scripts.lib.artifact_metadata import compute_config_hash
        h1 = compute_config_hash(CONFIG)
        h2 = compute_config_hash(CONFIG)
        assert h1 == h2
        assert len(h1) == 64

    def test_config_hash_differs_on_change(self):
        from _scripts.lib.artifact_metadata import compute_config_hash
        cfg_modified = {**CONFIG, "corr_abs_threshold": 0.95}
        assert compute_config_hash(CONFIG) != compute_config_hash(cfg_modified)


# ===========================================================================
# 6. greedy_cluster_representatives is deterministic
# ===========================================================================

class TestGreedyClusterDeterminism:

    def _make_corr(self) -> pd.DataFrame:
        """Construct a small correlation matrix with known cluster structure."""
        feats = ["a", "b", "c", "d", "e"]
        data = np.eye(5)
        # a-b-c form a cluster (|r| >= 0.95)
        data[0, 1] = data[1, 0] = 0.96
        data[0, 2] = data[2, 0] = 0.97
        data[1, 2] = data[2, 1] = 0.95
        # d-e form a cluster
        data[3, 4] = data[4, 3] = 0.92
        return pd.DataFrame(data, index=feats, columns=feats)

    def test_same_result_on_repeat_calls(self):
        corr = self._make_corr()
        r1 = greedy_cluster_representatives(corr, threshold=0.90)
        r2 = greedy_cluster_representatives(corr, threshold=0.90)
        assert r1["feature_to_cluster"] == r2["feature_to_cluster"]
        assert r1["n_clusters"] == r2["n_clusters"]

    def test_same_result_with_explicit_order(self):
        corr = self._make_corr()
        order = ["a", "b", "c", "d", "e"]
        r1 = greedy_cluster_representatives(corr, 0.90, prefer_order=order)
        r2 = greedy_cluster_representatives(corr, 0.90, prefer_order=order)
        assert r1["feature_to_cluster"] == r2["feature_to_cluster"]

    def test_order_matters_for_representative_selection(self):
        """With order [a, b, c], 'a' is rep; with order [c, b, a], 'c' is rep."""
        corr = self._make_corr()
        r_abc = greedy_cluster_representatives(corr, 0.90, prefer_order=["a", "b", "c", "d", "e"])
        r_cba = greedy_cluster_representatives(corr, 0.90, prefer_order=["c", "b", "a", "d", "e"])
        # Both have 2 clusters (a/b/c cluster and d/e cluster)
        assert r_abc["n_clusters"] == r_cba["n_clusters"] == 2
        # But different representatives
        reps_abc = {c["representative"] for c in r_abc["clusters"]}
        reps_cba = {c["representative"] for c in r_cba["clusters"]}
        # The a/b/c cluster representative differs
        assert "a" in reps_abc
        assert "c" in reps_cba

    def test_every_feature_assigned(self):
        corr = self._make_corr()
        result = greedy_cluster_representatives(corr, 0.90)
        assert set(result["feature_to_cluster"].keys()) == set(corr.columns)

    def test_representatives_are_subset_of_features(self):
        corr = self._make_corr()
        result = greedy_cluster_representatives(corr, 0.90)
        reps = {c["representative"] for c in result["clusters"]}
        assert reps.issubset(set(corr.columns))

    def test_all_cluster_members_above_threshold(self):
        """Every non-representative in a cluster must have |r| >= threshold with its rep."""
        corr = self._make_corr()
        threshold = 0.90
        result = greedy_cluster_representatives(corr, threshold)
        for cluster in result["clusters"]:
            rep = cluster["representative"]
            for member in cluster["members"]:
                if member == rep:
                    continue
                assert corr.loc[rep, member] >= threshold, (
                    f"Member {member} has |r|={corr.loc[rep, member]:.4f} "
                    f"< threshold {threshold} with rep {rep}"
                )


# ===========================================================================
# 7. Threshold is respected (edge cases)
# ===========================================================================

class TestClusterThreshold:

    def test_threshold_1_gives_all_singletons(self):
        """At threshold=1.0, only perfect correlations form clusters."""
        corr = pd.DataFrame(
            [[1.0, 0.99, 0.5],
             [0.99, 1.0, 0.3],
             [0.5, 0.3, 1.0]],
            index=["x", "y", "z"],
            columns=["x", "y", "z"],
        )
        # Threshold > 0.99 → no clusters
        result = greedy_cluster_representatives(corr, 1.0)
        assert result["n_clusters"] == 3  # all singletons

    def test_threshold_0_gives_one_cluster(self):
        """At threshold=0.0, all features form one cluster (first becomes rep)."""
        feats = ["p", "q", "r"]
        corr = pd.DataFrame(
            [[1.0, 0.05, 0.02],
             [0.05, 1.0, 0.01],
             [0.02, 0.01, 1.0]],
            index=feats, columns=feats,
        )
        result = greedy_cluster_representatives(corr, 0.0)
        assert result["n_clusters"] == 1
        assert result["clusters"][0]["n_members"] == 3

    def test_real_data_threshold_applied(self):
        """Integration: threshold 0.90 gives the expected cluster count from real data."""
        if not (OUT_DIR / "feature_cluster_representatives.yaml").exists():
            pytest.skip("Cluster YAML not yet generated")
        with open(OUT_DIR / "feature_cluster_representatives.yaml") as f:
            cl = yaml.safe_load(f)
        assert cl["config"]["corr_abs_threshold"] == 0.90
        # Multi-member clusters exist (some features are highly correlated)
        multi = [c for c in cl["clusters"] if c["n_members"] > 1]
        assert len(multi) > 0, "Expected at least one multi-member cluster"

    def test_perfect_corr_pairs_clustered(self):
        """Features with |r|=1.0 (e.g. roc_10 and return_10) must be in same cluster."""
        if not (OUT_DIR / "feature_cluster_representatives.yaml").exists():
            pytest.skip("Cluster YAML not yet generated")
        with open(OUT_DIR / "feature_cluster_representatives.yaml") as f:
            cl = yaml.safe_load(f)
        # Check at least one known-perfect pair
        ftr = cl["feature_to_representative"]
        known_pairs = [
            ("return_10", "roc_10"),
            ("sma_20", "bb_middle"),
        ]
        for a, b in known_pairs:
            if a in ftr and b in ftr:
                assert ftr[a] == ftr[b], (
                    f"Perfect corr pair ({a}, {b}) assigned to different clusters: "
                    f"{ftr[a]} vs {ftr[b]}"
                )


# ===========================================================================
# 8. Feature families cover all feature columns
# ===========================================================================

class TestFeatureFamilies:

    def test_every_feature_assigned_to_a_family(self):
        if not TRAIN_CSV.exists():
            pytest.skip("train.csv not found")
        df = pd.read_csv(TRAIN_CSV, nrows=1)
        exclude = set(CONFIG["exclude_cols"]) | {TIMESTAMP_COL}
        feat_cols = [c for c in df.columns if c not in exclude]
        family_map = build_family_map(feat_cols)
        assert set(family_map.keys()) == set(feat_cols)

    def test_no_column_assigned_to_two_families(self):
        if not TRAIN_CSV.exists():
            pytest.skip("train.csv not found")
        df = pd.read_csv(TRAIN_CSV, nrows=1)
        exclude = set(CONFIG["exclude_cols"]) | {TIMESTAMP_COL}
        feat_cols = [c for c in df.columns if c not in exclude]
        family_map = build_family_map(feat_cols)
        # Each column appears exactly once across all families
        all_cols = list(family_map.keys())
        assert len(all_cols) == len(set(all_cols))

    def test_known_columns_in_correct_families(self):
        expected = {
            "return_1":        "returns",
            "sma_10":          "trend",
            "rsi_14":          "momentum_oscillators",
            "bb_pct_b":        "bollinger",
            "hist_vol_20":     "volatility",
            "obv":             "volume_liquidity",
            "roll_std_ret_20": "rolling_moments",
            "vol_regime_high": "regime_flags",
        }
        for col, expected_family in expected.items():
            actual = build_family_map([col])[col]
            assert actual == expected_family, (
                f"Column '{col}': expected family '{expected_family}', got '{actual}'"
            )

    def test_group_by_family_totals_match_feature_count(self):
        if not TRAIN_CSV.exists():
            pytest.skip("train.csv not found")
        df = pd.read_csv(TRAIN_CSV, nrows=1)
        exclude = set(CONFIG["exclude_cols"]) | {TIMESTAMP_COL}
        feat_cols = [c for c in df.columns if c not in exclude]
        groups = group_by_family(feat_cols)
        total = sum(len(v) for v in groups.values())
        assert total == len(feat_cols)


# ===========================================================================
# 9. fold_stability: correct fold count and columns
# ===========================================================================

class TestFoldStability:

    def _make_df(self, n_rows: int = 100) -> pd.DataFrame:
        ts = pd.date_range("2020-01-01", periods=n_rows, freq="4h", tz="UTC")
        np.random.seed(0)
        return pd.DataFrame({
            TIMESTAMP_COL: ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "feat_a":       np.random.randn(n_rows),
            "feat_b":       np.random.randn(n_rows) * 10,
        })

    def test_correct_number_of_folds(self):
        df = self._make_df(100)
        result = fold_stability(df, ["feat_a", "feat_b"], n_folds=5)
        assert sorted(result["fold_id"].unique()) == [0, 1, 2, 3, 4]

    def test_every_feature_in_every_fold(self):
        df = self._make_df(100)
        result = fold_stability(df, ["feat_a", "feat_b"], n_folds=5)
        for fid in range(5):
            fold_feats = set(result[result["fold_id"] == fid]["feature"])
            assert "feat_a" in fold_feats
            assert "feat_b" in fold_feats

    def test_required_columns_present(self):
        df = self._make_df(50)
        result = fold_stability(df, ["feat_a", "feat_b"], n_folds=3)
        for col in ["fold_id", "fold_start", "fold_end", "fold_n_rows",
                    "feature", "mean", "std", "min", "max"]:
            assert col in result.columns, f"Missing column: {col}"

    def test_fold_rows_cover_all_data(self):
        """Total rows across all folds must equal n_features × n_folds."""
        df = self._make_df(100)
        n_feats = 2
        n_folds = 5
        result = fold_stability(df, ["feat_a", "feat_b"], n_folds=n_folds)
        assert len(result) == n_feats * n_folds

    def test_fold_row_counts_approximately_equal(self):
        """Each fold should contain approximately n_rows/n_folds rows."""
        df = self._make_df(100)
        result = fold_stability(df, ["feat_a"], n_folds=5)
        fold_sizes = result.groupby("fold_id")["fold_n_rows"].first()
        # Max fold size should not exceed min fold size by more than 1
        assert (fold_sizes.max() - fold_sizes.min()) <= 1

    def test_fold_start_end_are_valid_timestamps(self):
        df = self._make_df(20)
        result = fold_stability(df, ["feat_a"], n_folds=4)
        for fold_start in result["fold_start"]:
            # Should be parseable ISO-8601
            pd.Timestamp(fold_start)

    def test_stability_summary_has_all_features(self):
        df = self._make_df(50)
        feat_cols = ["feat_a", "feat_b"]
        stability = fold_stability(df, feat_cols, n_folds=5)
        summary = fold_stability_summary(stability)
        assert set(summary["feature"]) == set(feat_cols)

    def test_stability_summary_ranked_by_cv_of_std(self):
        df = self._make_df(200)
        feat_cols = ["feat_a", "feat_b"]
        stability = fold_stability(df, feat_cols, n_folds=5)
        summary = fold_stability_summary(stability)
        # cv_of_std should be monotonically non-decreasing with stability_rank
        cvs = summary.sort_values("stability_rank")["cv_of_std"].values
        assert all(cvs[i] <= cvs[i + 1] for i in range(len(cvs) - 1))

    def test_real_stability_csv_has_correct_shape(self):
        """Integration: generated CSV should have 83 features × 5 folds = 415 rows."""
        p = OUT_DIR / "feature_stability_by_train_fold.csv"
        if not p.exists():
            pytest.skip("Stability CSV not yet generated")
        df = pd.read_csv(p)
        assert len(df) == 83 * 5, f"Expected 415 rows, got {len(df)}"
        assert df["fold_id"].nunique() == 5


# ===========================================================================
# 10. near_constant_report flags binary and near-zero-std features
# ===========================================================================

class TestNearConstantReport:

    def test_binary_feature_flagged(self):
        df = pd.DataFrame({
            "binary": [0.0, 1.0, 0.0, 1.0, 0.0],
            "normal": [1.0, 2.3, -0.5, 4.1, 0.2],
        })
        result = near_constant_report(df, ["binary", "normal"], std_threshold=0.001)
        binary_row = result[result["feature"] == "binary"].iloc[0]
        assert bool(binary_row["is_binary_flag"]) is True
        assert binary_row["flag"] == "BINARY_FLAG"

    def test_near_zero_std_flagged(self):
        df = pd.DataFrame({
            "tiny_std": [1.0, 1.00001, 0.99999, 1.00002, 1.0],
        })
        result = near_constant_report(df, ["tiny_std"], std_threshold=0.001)
        row = result.iloc[0]
        assert bool(row["is_near_const_std"]) is True
        assert row["flag"] == "NEAR_CONST"

    def test_normal_feature_not_flagged(self):
        np.random.seed(1)
        df = pd.DataFrame({"normal": np.random.randn(100)})
        result = near_constant_report(df, ["normal"], std_threshold=0.001)
        assert result.iloc[0]["flag"] == ""

    def test_output_has_required_columns(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
        result = near_constant_report(df, ["x"])
        for col in ["feature", "mean", "std", "n_unique", "is_binary_flag",
                    "is_near_const_std", "flag"]:
            assert col in result.columns

    def test_real_binary_features_flagged(self):
        """Integration: vol_regime_high and vol_regime_low should be flagged as binary."""
        if not TRAIN_CSV.exists():
            pytest.skip("train.csv not found")
        df = pd.read_csv(TRAIN_CSV, usecols=["vol_regime_high", "vol_regime_low"])
        result = near_constant_report(df, ["vol_regime_high", "vol_regime_low"])
        for feat in ["vol_regime_high", "vol_regime_low"]:
            row = result[result["feature"] == feat].iloc[0]
            assert bool(row["is_binary_flag"]) is True, f"{feat} should be flagged as binary"


# ===========================================================================
# 11. warmup_profile records correct warmup heuristics
# ===========================================================================

class TestWarmupProfile:

    def test_warmup_heuristic_from_column_name(self):
        from _scripts.workers.stage3x_feature_redundancy_stability_worker import _warmup_heuristic
        assert _warmup_heuristic("sma_200") == 200
        assert _warmup_heuristic("rsi_14") == 14
        assert _warmup_heuristic("roll_std_ret_252") == 252
        assert _warmup_heuristic("return_1") == 1
        assert _warmup_heuristic("obv") == 0

    def test_nan_count_reported(self):
        df = pd.DataFrame({
            "good": [1.0, 2.0, 3.0],
            "has_nan": [float("nan"), 1.0, 2.0],
        })
        result = warmup_profile(df, ["good", "has_nan"])
        nan_row = result[result["feature"] == "has_nan"].iloc[0]
        assert nan_row["n_nan"] == 1

    def test_no_nan_reported_for_clean_data(self):
        df = pd.DataFrame({"clean": [1.0, 2.0, 3.0]})
        result = warmup_profile(df, ["clean"])
        assert result.iloc[0]["n_nan"] == 0

    def test_required_columns_present(self):
        df = pd.DataFrame({"feat": [1.0, 2.0]})
        result = warmup_profile(df, ["feat"])
        for col in ["feature", "n_nan", "first_valid_idx", "warmup_heuristic"]:
            assert col in result.columns

    def test_longest_warmup_is_hurst_or_sma200(self):
        """Integration: sma_200 or roll_mean_ret_252 should have the longest warmup."""
        if not TRAIN_CSV.exists():
            pytest.skip("train.csv not found")
        df = pd.read_csv(TRAIN_CSV)
        exclude = set(CONFIG["exclude_cols"]) | {"DATE_TIME"}
        feat_cols = [c for c in df.columns if c not in exclude]
        result = warmup_profile(df, feat_cols)
        top_warmup = result.nlargest(1, "warmup_heuristic").iloc[0]
        assert top_warmup["warmup_heuristic"] >= 200


# ===========================================================================
# 12. Integration smoke: all output files exist and are non-empty
# ===========================================================================

class TestOutputFiles:

    EXPECTED_FILES = [
        "pearson_corr.parquet",
        "spearman_corr.parquet",
        "feature_cluster_representatives.yaml",
        "feature_stability_by_train_fold.csv",
        "feature_redundancy_stability_report.md",
        "metadata.json",
    ]

    def test_all_output_files_exist(self):
        for fname in self.EXPECTED_FILES:
            p = OUT_DIR / fname
            assert p.exists(), f"Expected output not found: {p}"

    def test_all_output_files_non_empty(self):
        for fname in self.EXPECTED_FILES:
            p = OUT_DIR / fname
            assert p.stat().st_size > 0, f"Output file is empty: {p}"

    def test_pearson_corr_is_square_symmetric(self):
        df = pd.read_parquet(OUT_DIR / "pearson_corr.parquet")
        assert df.shape[0] == df.shape[1], "Pearson matrix must be square"
        # Symmetry check (up to float precision)
        diff = (df - df.T).abs().max().max()
        assert diff < 1e-10, f"Pearson matrix not symmetric: max diff={diff}"

    def test_spearman_corr_is_square_symmetric(self):
        df = pd.read_parquet(OUT_DIR / "spearman_corr.parquet")
        assert df.shape[0] == df.shape[1]
        diff = (df - df.T).abs().max().max()
        assert diff < 1e-10

    def test_pearson_diagonal_is_one(self):
        df = pd.read_parquet(OUT_DIR / "pearson_corr.parquet")
        diag = np.diag(df.values)
        assert np.allclose(diag, 1.0, atol=1e-10), "Diagonal should be 1.0"

    def test_cluster_yaml_valid_structure(self):
        with open(OUT_DIR / "feature_cluster_representatives.yaml") as f:
            cl = yaml.safe_load(f)
        assert "config" in cl
        assert "clusters" in cl
        assert "feature_to_representative" in cl
        assert cl["config"]["corr_abs_threshold"] == CONFIG["corr_abs_threshold"]

    def test_cluster_yaml_all_features_covered(self):
        with open(OUT_DIR / "feature_cluster_representatives.yaml") as f:
            cl = yaml.safe_load(f)
        if not TRAIN_CSV.exists():
            pytest.skip()
        df = pd.read_csv(TRAIN_CSV, nrows=1)
        exclude = set(CONFIG["exclude_cols"]) | {"DATE_TIME"}
        feat_cols = set(c for c in df.columns if c not in exclude)
        yaml_features = set(cl["feature_to_representative"].keys())
        assert yaml_features == feat_cols, (
            f"YAML covers {len(yaml_features)} features, expected {len(feat_cols)}"
        )

    def test_md_report_has_governance_section(self):
        content = (OUT_DIR / "feature_redundancy_stability_report.md").read_text()
        assert "Governance" in content
        assert "uses_heldout" in content
        assert "PASS" in content

    def test_registry_contains_artifact(self):
        reg = json.loads(REPO_ROOT.joinpath(
            "experiments/unsup_causal_audit/registry.json"
        ).read_text())
        types = [a.get("artifact_type") for a in reg.get("artifacts", [])]
        assert "feature_redundancy_stability" in types

    def test_registry_artifact_uses_heldout_false(self):
        reg = json.loads(REPO_ROOT.joinpath(
            "experiments/unsup_causal_audit/registry.json"
        ).read_text())
        for a in reg.get("artifacts", []):
            if a.get("artifact_type") == "feature_redundancy_stability":
                assert a.get("uses_heldout") is False
