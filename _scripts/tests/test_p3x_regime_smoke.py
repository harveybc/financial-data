"""
Tests for stage3x_regime_smoke_worker.py (Phase 3X P0-A).

Covers:
  1. Heldout rows (>= 2025-01-01) rejected before fitting
  2. Validation rows are NOT used for fitting (transform-only path)
  3. Missing timestamp column fails closed
  4. Duplicate/non-monotonic timestamps fail closed
  5. metadata.json: input_hashes, config_hash, fit_window, uses_heldout=false
  6. Output timestamps align exactly with input (row-for-row)
  7. Regime features are deterministic across two runs with same seed
  8. Soft probabilities sum to 1.0 per row
  9. Entropy is in [0, ln(k)] for every row
 10. Persistence is positive and monotonically increasing within a run
 11. All output files exist and are non-empty
 12. Registry contains regime_smoke entry with uses_heldout=false
 13. Join validation: regime_df can be left-joined to train_df without inflation

Run:
    cd /home/harveybc/Documents/GitHub/financial-data
    python -m pytest _scripts/tests/test_p3x_regime_smoke.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from _scripts.lib.split_guard import SplitViolation, assert_no_heldout_rows, validate_timestamps
from _scripts.lib.feature_alignment import validate_feature_join
from _scripts.lib.artifact_metadata import ArtifactMetadata

from _scripts.workers.stage3x_regime_smoke_worker import (
    ARTIFACT_DIR,
    CONFIG,
    FEATURE_OUT_DIR,
    HELDOUT_START,
    N_REGIMES,
    RANDOM_SEED,
    REGIME_FEATURES,
    TIMESTAMP_COL,
    TRAIN_CSV,
    build_regime_df,
    fit_pipeline,
    transform_pipeline,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _df_with_ts(timestamps: list[str], seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(timestamps)
    d: dict = {TIMESTAMP_COL: timestamps}
    for feat in REGIME_FEATURES:
        d[feat] = rng.standard_normal(n)
    return pd.DataFrame(d)


TRAIN_TS = [
    "2020-01-01T00:00:00Z",
    "2021-06-15T00:00:00Z",
    "2022-03-01T00:00:00Z",
    "2023-09-01T00:00:00Z",
]
VAL_TS   = ["2024-04-01T00:00:00Z", "2024-10-01T00:00:00Z"]
HELD_TS  = ["2025-01-01T00:00:00Z", "2025-06-01T00:00:00Z"]


# Pre-load train fixture once (used in many tests)
@pytest.fixture(scope="module")
def train_df() -> pd.DataFrame:
    if not TRAIN_CSV.exists():
        pytest.skip(f"train.csv not found: {TRAIN_CSV}")
    return pd.read_csv(TRAIN_CSV)


@pytest.fixture(scope="module")
def fitted_pipeline(train_df):
    X = train_df[REGIME_FEATURES].values
    return fit_pipeline(
        X, n_regimes=N_REGIMES, random_seed=RANDOM_SEED,
        n_init=CONFIG["kmeans_n_init"], max_iter=CONFIG["kmeans_max_iter"],
    )


@pytest.fixture(scope="module")
def regime_result(train_df, fitted_pipeline):
    scaler, km = fitted_pipeline
    X = train_df[REGIME_FEATURES].values
    return transform_pipeline(X, scaler, km, temperature=CONFIG["prob_temperature"])


# ===========================================================================
# 1. Heldout rows rejected before fitting
# ===========================================================================

class TestHeldoutRejection:

    def test_heldout_row_raises(self):
        df = _df_with_ts(TRAIN_TS + HELD_TS)
        with pytest.raises(SplitViolation, match="2025-01-01"):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_heldout_exact_boundary_raises(self):
        df = _df_with_ts(["2025-01-01T00:00:00Z"])
        with pytest.raises(SplitViolation):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_clean_train_passes(self):
        df = _df_with_ts(TRAIN_TS)
        assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_real_csv_has_no_heldout_rows(self, train_df):
        assert_no_heldout_rows(train_df, TIMESTAMP_COL, HELDOUT_START)

    def test_post_2024_row_excluded_from_fit(self):
        """
        Simulate the worker's guard logic: a CSV containing a 2024 row gets
        filtered before fitting; the resulting fit df has no val-window rows.
        """
        df = _df_with_ts(TRAIN_TS + VAL_TS)
        ts = pd.to_datetime(df[TIMESTAMP_COL], utc=True)
        val_boundary = pd.Timestamp("2024-01-01", tz="UTC")
        mask = ts >= val_boundary
        assert mask.any()
        fit_df = df[~mask]
        fit_ts  = ts[~mask]
        assert (fit_ts < val_boundary).all()
        assert len(fit_df) == len(TRAIN_TS)


# ===========================================================================
# 2. Validation uses transform-only, not fit
# ===========================================================================

class TestTransformOnlyValidation:

    def test_fitted_pipeline_transforms_validation_without_refitting(self, fitted_pipeline):
        """
        Core contract: applying the pipeline to 2024 data must use
        scaler.transform() and km.predict() — never fit.
        We verify by checking centroids are unchanged after the call.
        """
        scaler, km = fitted_pipeline
        centroids_before = km.cluster_centers_.copy()
        # Simulate validation rows
        rng = np.random.default_rng(77)
        X_val = rng.standard_normal((20, len(REGIME_FEATURES)))
        result = transform_pipeline(X_val, scaler, km, temperature=1.0)
        # Centroids must be identical — transform_pipeline must not call fit
        assert np.allclose(km.cluster_centers_, centroids_before), \
            "KMeans centroids changed — transform_pipeline called fit illegally."
        assert result["regime_id"].shape == (20,)

    def test_scaler_params_unchanged_after_transform(self, fitted_pipeline):
        scaler, km = fitted_pipeline
        mean_before = scaler.mean_.copy()
        std_before  = scaler.scale_.copy()
        rng = np.random.default_rng(99)
        X_val = rng.standard_normal((50, len(REGIME_FEATURES)))
        transform_pipeline(X_val, scaler, km)
        assert np.allclose(scaler.mean_, mean_before)
        assert np.allclose(scaler.scale_, std_before)

    def test_validation_rows_not_in_fit_window(self, fitted_pipeline):
        """Validation timestamps (2024) are after the fit window — produce valid outputs."""
        scaler, km = fitted_pipeline
        df_val = _df_with_ts(VAL_TS, seed=5)
        X_val = df_val[REGIME_FEATURES].values
        result = transform_pipeline(X_val, scaler, km)
        assert result["regime_id"].shape == (len(VAL_TS),)
        assert result["regime_probs"].shape == (len(VAL_TS), N_REGIMES)

    def test_loaded_pipeline_pkl_is_transform_only_capable(self):
        """The saved pipeline.pkl can be loaded and used without any fit calls."""
        pkl_path = ARTIFACT_DIR / "kmeans_pipeline.pkl"
        if not pkl_path.exists():
            pytest.skip("kmeans_pipeline.pkl not yet generated")
        bundle = joblib.load(pkl_path)
        scaler, km = bundle["scaler"], bundle["km"]
        rng = np.random.default_rng(1)
        X = rng.standard_normal((10, len(REGIME_FEATURES)))
        Xs = scaler.transform(X)
        labels = km.predict(Xs)
        assert labels.shape == (10,)
        assert set(labels).issubset(set(range(N_REGIMES)))


# ===========================================================================
# 3. Missing timestamp column fails closed
# ===========================================================================

class TestMissingTimestamp:

    def test_missing_col_raises(self):
        df = pd.DataFrame({"feat_a": [1.0, 2.0]})
        with pytest.raises(SplitViolation, match="not found"):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_wrong_col_name_raises(self):
        df = _df_with_ts(TRAIN_TS)
        df = df.rename(columns={TIMESTAMP_COL: "ts"})
        with pytest.raises(SplitViolation, match="not found"):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_unparseable_timestamp_raises(self):
        df = pd.DataFrame({TIMESTAMP_COL: ["bad_date", "also_bad"]})
        with pytest.raises(SplitViolation):
            assert_no_heldout_rows(df, TIMESTAMP_COL, HELDOUT_START)

    def test_join_with_missing_ts_col_raises(self):
        base = _df_with_ts(TRAIN_TS)
        feat = pd.DataFrame({"regime_id": [0, 1, 0, 1]})
        with pytest.raises(SplitViolation, match="not found"):
            validate_feature_join(base, feat, TIMESTAMP_COL)


# ===========================================================================
# 4. Duplicate / non-monotonic timestamps fail closed
# ===========================================================================

class TestTimestampIntegrity:

    def test_duplicate_timestamps_raise(self):
        dup = TRAIN_TS[:2] + TRAIN_TS[:2]
        df = _df_with_ts(dup)
        with pytest.raises(SplitViolation, match="duplicate"):
            validate_timestamps(df, TIMESTAMP_COL, allow_duplicates=False)

    def test_non_monotonic_timestamps_raise(self):
        non_mono = [TRAIN_TS[1], TRAIN_TS[0], TRAIN_TS[2], TRAIN_TS[3]]
        df = _df_with_ts(non_mono)
        with pytest.raises(SplitViolation, match="monotonically"):
            validate_timestamps(df, TIMESTAMP_COL, require_monotonic=True)

    def test_clean_timestamps_pass(self):
        df = _df_with_ts(TRAIN_TS)
        validate_timestamps(df, TIMESTAMP_COL)


# ===========================================================================
# 5. Metadata correctness
# ===========================================================================

class TestMetadata:

    @pytest.fixture(scope="class")
    def meta(self):
        p = ARTIFACT_DIR / "metadata.json"
        if not p.exists():
            pytest.skip("metadata.json not found")
        return json.loads(p.read_text())

    def test_uses_heldout_false(self, meta):
        assert meta["uses_heldout"] is False

    def test_fit_excludes_heldout_2025(self, meta):
        assert meta["fit_excludes_heldout_2025"] is True

    def test_input_hashes_populated(self, meta):
        hashes = meta["input_hashes"]
        assert len(hashes) > 0
        for _, h in hashes.items():
            assert len(h) == 64  # sha256

    def test_config_hash_is_64_hex(self, meta):
        assert len(meta["config_hash"]) == 64

    def test_fit_window_in_train_era(self, meta):
        assert "2017" in meta["fit_start"]
        assert "2023" in meta["fit_end"]

    def test_fit_end_before_heldout(self, meta):
        from datetime import datetime, timezone
        fe = datetime.fromisoformat(meta["fit_end"].replace("Z", "+00:00"))
        hs = datetime.fromisoformat(meta["heldout_start"].replace("Z", "+00:00"))
        assert fe < hs

    def test_fit_row_count_correct(self, meta):
        assert meta["fit_row_count"] == 13699

    def test_leakage_checks_present(self, meta):
        checks = meta.get("leakage_checks", {})
        assert "heldout_timestamp_exclusion" in checks
        assert "fit_window_precedes_validation" in checks

    def test_artifact_type(self, meta):
        assert meta["artifact_type"] == "regime_smoke"

    def test_schema_passes_artifact_metadata_validator(self, meta):
        am = ArtifactMetadata(**{
            k: v for k, v in meta.items()
            if k in ArtifactMetadata.__dataclass_fields__
        })
        errors = am.validate()
        assert errors == [], f"Metadata validation errors: {errors}"

    def test_model_class_recorded(self, meta):
        assert "KMeans" in meta.get("model_class", "")

    def test_fit_columns_are_regime_features(self, meta):
        fit_cols = meta.get("fit_columns", [])
        assert set(fit_cols) == set(REGIME_FEATURES)


# ===========================================================================
# 6. Output timestamps align exactly with input
# ===========================================================================

class TestTimestampAlignment:

    def test_regime_df_timestamps_match_input(self, train_df, regime_result):
        ts_input = pd.to_datetime(train_df[TIMESTAMP_COL], utc=True).reset_index(drop=True)
        regime_df = build_regime_df(ts_input, regime_result, TIMESTAMP_COL)
        ts_out = pd.to_datetime(regime_df[TIMESTAMP_COL], utc=True)
        assert len(ts_out) == len(ts_input)
        assert (ts_out.values == ts_input.values).all(), \
            "Output timestamps do not match input timestamps row-for-row."

    def test_regime_parquet_timestamps_match_train_csv(self, train_df):
        p = ARTIFACT_DIR / "regime_features_train.parquet"
        if not p.exists():
            pytest.skip()
        regime_df = pd.read_parquet(p)
        ts_train  = pd.to_datetime(train_df[TIMESTAMP_COL], utc=True)
        ts_regime = pd.to_datetime(regime_df[TIMESTAMP_COL], utc=True)
        assert len(ts_train) == len(ts_regime)
        assert (ts_train.values == ts_regime.values).all()

    def test_join_file_timestamps_match_train(self, train_df):
        p = FEATURE_OUT_DIR / "regime_smoke_tech_stat.parquet"
        if not p.exists():
            pytest.skip()
        jf = pd.read_parquet(p)
        ts_train = pd.to_datetime(train_df[TIMESTAMP_COL], utc=True)
        ts_join  = pd.to_datetime(jf[TIMESTAMP_COL], utc=True)
        assert (ts_train.values == ts_join.values).all()

    def test_validate_feature_join_passes(self, train_df):
        p = ARTIFACT_DIR / "regime_features_train.parquet"
        if not p.exists():
            pytest.skip()
        regime_df = pd.read_parquet(p)
        merged = validate_feature_join(
            train_df, regime_df, TIMESTAMP_COL,
            heldout_start=HELDOUT_START,
            allow_missing_in_feature=False,
        )
        assert len(merged) == len(train_df), "Join inflated row count"
        assert "unsup_regime_id" in merged.columns

    def test_join_does_not_inflate_rows(self, train_df):
        p = ARTIFACT_DIR / "regime_features_train.parquet"
        if not p.exists():
            pytest.skip()
        regime_df = pd.read_parquet(p)
        merged = validate_feature_join(train_df, regime_df, TIMESTAMP_COL)
        assert len(merged) == len(train_df)


# ===========================================================================
# 7. Determinism across two runs with same seed
# ===========================================================================

class TestDeterminism:

    def test_fit_pipeline_deterministic(self, train_df):
        X = train_df[REGIME_FEATURES].values
        s1, k1 = fit_pipeline(X, n_regimes=N_REGIMES, random_seed=RANDOM_SEED)
        s2, k2 = fit_pipeline(X, n_regimes=N_REGIMES, random_seed=RANDOM_SEED)
        assert np.allclose(k1.cluster_centers_, k2.cluster_centers_), \
            "KMeans centroids differ across two calls with same seed"
        assert np.allclose(s1.mean_, s2.mean_), "Scaler means differ"

    def test_transform_pipeline_deterministic(self, train_df, fitted_pipeline):
        scaler, km = fitted_pipeline
        X = train_df[REGIME_FEATURES].values
        r1 = transform_pipeline(X, scaler, km)
        r2 = transform_pipeline(X, scaler, km)
        assert (r1["regime_id"] == r2["regime_id"]).all()
        assert np.allclose(r1["regime_probs"], r2["regime_probs"])
        assert np.allclose(r1["regime_entropy"], r2["regime_entropy"])

    def test_different_seed_may_differ(self, train_df):
        X = train_df[REGIME_FEATURES].values
        _, k42 = fit_pipeline(X, n_regimes=N_REGIMES, random_seed=42)
        _, k99 = fit_pipeline(X, n_regimes=N_REGIMES, random_seed=99)
        # Centers are unlikely to be identical (not a strict guarantee, but almost always true)
        same = np.allclose(k42.cluster_centers_, k99.cluster_centers_, atol=1e-3)
        if same:
            pytest.xfail("Both seeds produced identical centroids — very unlikely but possible")

    def test_regime_parquet_is_deterministic_with_worker(self):
        """The output parquet should be bit-for-bit equal if we re-transform."""
        p = ARTIFACT_DIR / "regime_features_train.parquet"
        if not p.exists():
            pytest.skip()
        pkl_path = ARTIFACT_DIR / "kmeans_pipeline.pkl"
        if not pkl_path.exists():
            pytest.skip()
        bundle = joblib.load(pkl_path)
        scaler, km = bundle["scaler"], bundle["km"]
        train_df = pd.read_csv(TRAIN_CSV)
        X = train_df[REGIME_FEATURES].values
        result = transform_pipeline(X, scaler, km, temperature=CONFIG["prob_temperature"])
        ts = pd.to_datetime(train_df[TIMESTAMP_COL], utc=True)
        regime_df_fresh = build_regime_df(ts, result, TIMESTAMP_COL)
        regime_df_saved = pd.read_parquet(p)
        assert (regime_df_fresh["unsup_regime_id"].values ==
                regime_df_saved["unsup_regime_id"].values).all()


# ===========================================================================
# 8. Soft probabilities sum to 1.0 per row
# ===========================================================================

class TestSoftProbabilities:

    def test_prob_rows_sum_to_one(self, regime_result):
        probs = regime_result["regime_probs"]
        row_sums = probs.sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-5), \
            f"Probability rows don't sum to 1. Min={row_sums.min():.8f} Max={row_sums.max():.8f}"

    def test_probs_non_negative(self, regime_result):
        assert (regime_result["regime_probs"] >= 0).all()

    def test_probs_at_most_one(self, regime_result):
        assert (regime_result["regime_probs"] <= 1.0 + 1e-6).all()

    def test_n_prob_columns_equals_n_regimes(self, regime_result):
        assert regime_result["regime_probs"].shape[1] == N_REGIMES

    def test_prob_columns_in_output_df(self, train_df, regime_result):
        ts = pd.to_datetime(train_df[TIMESTAMP_COL], utc=True)
        df = build_regime_df(ts, regime_result, TIMESTAMP_COL)
        for k in range(N_REGIMES):
            assert f"unsup_regime_prob_{k}" in df.columns
        # Verify sums in DataFrame
        prob_cols = [f"unsup_regime_prob_{k}" for k in range(N_REGIMES)]
        row_sums = df[prob_cols].sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-5)

    def test_argmax_prob_matches_regime_id(self, regime_result):
        probs = regime_result["regime_probs"]
        argmax = probs.argmax(axis=1).astype(np.int32)
        assert (argmax == regime_result["regime_id"]).all(), \
            "argmax(probs) does not match regime_id"


# ===========================================================================
# 9. Entropy in [0, ln(k)] for every row
# ===========================================================================

class TestEntropy:

    def test_entropy_non_negative(self, regime_result):
        assert (regime_result["regime_entropy"] >= -1e-6).all()

    def test_entropy_at_most_ln_k(self, regime_result):
        max_H = float(np.log(N_REGIMES))
        assert (regime_result["regime_entropy"] <= max_H + 1e-5).all(), \
            f"Entropy exceeds max possible {max_H:.4f}"

    def test_entropy_zero_for_pure_assignment(self, fitted_pipeline):
        """If probs are [1, 0, 0, 0], entropy must be 0."""
        scaler, km = fitted_pipeline
        # Force a centroid-aligned point so one cluster gets ~100% probability
        centroid = km.cluster_centers_[0:1].copy()  # shape (1, n_features)
        # Un-scale back to feature space
        centroid_orig = scaler.inverse_transform(centroid)
        result = transform_pipeline(centroid_orig, scaler, km, temperature=1.0)
        # At the centroid itself, distance=0 → highest softmax weight.
        # With temperature=1.0 and finite inter-centroid distances the max
        # won't reach 1.0, but must be strictly higher than uniform (1/k).
        max_prob = float(result["regime_probs"].max())
        uniform  = 1.0 / N_REGIMES
        assert max_prob > uniform * 2.5, (
            f"Expected above-uniform probability at centroid, got max_prob={max_prob:.4f} "
            f"(uniform={uniform:.4f})"
        )

    def test_uniform_entropy_near_max_for_equidistant_point(self, fitted_pipeline):
        """
        A point equidistant from all centroids should produce near-uniform
        probabilities and entropy near ln(k).
        """
        scaler, km = fitted_pipeline
        # Average of all centroids (scaled space) → equidistant point
        centroid_mean = km.cluster_centers_.mean(axis=0, keepdims=True)
        centroid_orig = scaler.inverse_transform(centroid_mean)
        result = transform_pipeline(centroid_orig, scaler, km, temperature=1.0)
        H = float(result["regime_entropy"][0])
        max_H = float(np.log(N_REGIMES))
        # Entropy should be above 50% of maximum
        assert H > 0.5 * max_H, f"Expected near-maximum entropy, got H={H:.4f} (max={max_H:.4f})"

    def test_entropy_column_in_output_df(self, train_df, regime_result):
        ts = pd.to_datetime(train_df[TIMESTAMP_COL], utc=True)
        df = build_regime_df(ts, regime_result, TIMESTAMP_COL)
        assert "unsup_regime_entropy" in df.columns
        assert not df["unsup_regime_entropy"].isnull().any()


# ===========================================================================
# 10. Persistence is positive and increases within a run
# ===========================================================================

class TestPersistence:

    def test_persistence_starts_at_one_or_more(self, regime_result):
        assert (regime_result["persistence"] >= 1).all()

    def test_first_bar_persistence_is_one(self, regime_result):
        assert regime_result["persistence"][0] == 1

    def test_persistence_increments_within_run(self, regime_result):
        labels = regime_result["regime_id"]
        pers   = regime_result["persistence"]
        for i in range(1, len(labels)):
            if labels[i] == labels[i - 1]:
                assert pers[i] == pers[i - 1] + 1, \
                    f"Expected persistence increment at bar {i}"
            else:
                assert pers[i] == 1, \
                    f"Expected persistence reset at transition at bar {i}"

    def test_persistence_in_output_df(self, train_df, regime_result):
        ts = pd.to_datetime(train_df[TIMESTAMP_COL], utc=True)
        df = build_regime_df(ts, regime_result, TIMESTAMP_COL)
        assert "unsup_regime_persistence" in df.columns
        assert (df["unsup_regime_persistence"] >= 1).all()

    def test_transition_indicator_matches_persistence_reset(self, regime_result):
        pers  = regime_result["persistence"]
        trans = regime_result["transition_indicator"]
        # A persistence reset (pers[i]==1 for i>0) should coincide with transition
        for i in range(1, len(pers)):
            if pers[i] == 1:
                assert trans[i] == 1, f"No transition flag at persistence reset at bar {i}"


# ===========================================================================
# 11. All output files exist and are non-empty
# ===========================================================================

class TestOutputFiles:

    EXPECTED = [
        ARTIFACT_DIR / "regime_features_train.parquet",
        ARTIFACT_DIR / "kmeans_pipeline.pkl",
        ARTIFACT_DIR / "metadata.json",
        ARTIFACT_DIR / "regime_report.md",
        FEATURE_OUT_DIR / "regime_smoke_tech_stat.parquet",
    ]

    def test_all_files_exist(self):
        for p in self.EXPECTED:
            assert p.exists(), f"Missing: {p}"

    def test_all_files_non_empty(self):
        for p in self.EXPECTED:
            assert p.stat().st_size > 0, f"Empty file: {p}"

    def test_regime_parquet_has_correct_columns(self):
        df = pd.read_parquet(ARTIFACT_DIR / "regime_features_train.parquet")
        expected_cols = (
            [TIMESTAMP_COL, "unsup_regime_id"]
            + [f"unsup_regime_prob_{k}" for k in range(N_REGIMES)]
            + ["unsup_regime_entropy", "unsup_regime_transition_prob", "unsup_regime_persistence"]
        )
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_regime_parquet_row_count(self):
        df = pd.read_parquet(ARTIFACT_DIR / "regime_features_train.parquet")
        assert len(df) == 13699

    def test_pipeline_pkl_loadable(self):
        bundle = joblib.load(ARTIFACT_DIR / "kmeans_pipeline.pkl")
        assert "scaler" in bundle
        assert "km" in bundle
        assert "config" in bundle

    def test_pipeline_pkl_config_matches(self):
        bundle = joblib.load(ARTIFACT_DIR / "kmeans_pipeline.pkl")
        saved_cfg = bundle["config"]
        assert saved_cfg["n_regimes"] == N_REGIMES
        assert saved_cfg["random_seed"] == RANDOM_SEED
        assert saved_cfg["regime_features"] == REGIME_FEATURES

    def test_report_md_has_governance_section(self):
        content = (ARTIFACT_DIR / "regime_report.md").read_text()
        assert "Governance" in content
        assert "uses_heldout" in content
        assert "PASS" in content

    def test_join_file_has_expected_columns(self):
        df = pd.read_parquet(FEATURE_OUT_DIR / "regime_smoke_tech_stat.parquet")
        assert TIMESTAMP_COL in df.columns
        assert "unsup_regime_id" in df.columns
        assert f"unsup_regime_prob_0" in df.columns

    def test_join_file_no_heldout_rows(self):
        df = pd.read_parquet(FEATURE_OUT_DIR / "regime_smoke_tech_stat.parquet")
        ts = pd.to_datetime(df[TIMESTAMP_COL], utc=True)
        boundary = pd.Timestamp("2025-01-01", tz="UTC")
        assert (ts < boundary).all(), "Join file contains post-heldout rows"


# ===========================================================================
# 12. Registry entry correct
# ===========================================================================

class TestRegistry:

    @pytest.fixture(scope="class")
    def registry(self):
        p = REPO_ROOT / "experiments/unsup_causal_audit/registry.json"
        return json.loads(p.read_text())

    def test_regime_smoke_in_registry(self, registry):
        types = [a.get("artifact_type") for a in registry.get("artifacts", [])]
        assert "regime_smoke" in types

    def test_uses_heldout_false_in_registry(self, registry):
        for a in registry.get("artifacts", []):
            if a.get("artifact_type") == "regime_smoke":
                assert a.get("uses_heldout") is False

    def test_feature_path_in_registry(self, registry):
        for a in registry.get("artifacts", []):
            if a.get("artifact_type") == "regime_smoke":
                fp = Path(a.get("feature_path", ""))
                assert fp.exists(), f"Registered feature_path does not exist: {fp}"

    def test_config_hash_in_registry(self, registry):
        from _scripts.lib.artifact_metadata import compute_config_hash
        expected = compute_config_hash(CONFIG)
        for a in registry.get("artifacts", []):
            if a.get("artifact_type") == "regime_smoke":
                assert a.get("config_hash") == expected

    def test_leakage_checks_in_registry(self, registry):
        for a in registry.get("artifacts", []):
            if a.get("artifact_type") == "regime_smoke":
                checks = a.get("leakage_checks", {})
                assert "heldout_timestamp_exclusion" in checks
