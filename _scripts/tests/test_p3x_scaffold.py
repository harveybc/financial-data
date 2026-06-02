"""
Tests for Phase 3X unsupervised/causal audit scaffolding.

Covers:
  1. No rows >= 2025-01-01 can be passed to fit (split_guard)
  2. Validation data cannot be fitted — transform/score only
  3. ArtifactMetadata schema completeness and uses_heldout=false invariant
  4. Feature alignment: timestamp-safe join, no post-heldout rows
  5. Missing or ambiguous timestamp columns fail closed

Run:
    python -m pytest _scripts/tests/test_p3x_scaffold.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

# Make repo root importable
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from _scripts.lib.split_guard import (
    HELDOUT_START_DT,
    SplitBoundary,
    SplitViolation,
    assert_fit_precedes_eval,
    assert_no_fit_on_validation,
    assert_no_heldout_rows,
    assert_within_train,
    require_timestamp_column,
    slice_train,
    slice_validation,
    validate_timestamps,
)
from _scripts.lib.artifact_metadata import (
    ArtifactMetadata,
    build_metadata,
    compute_config_hash,
    compute_file_hash,
    compute_manifest_hash,
    write_metadata,
)
from _scripts.lib.feature_alignment import (
    assert_no_future_features,
    assert_timestamps_align,
    load_and_validate_feature_csv,
    validate_feature_join,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _df(timestamps: list[str], extra_cols: dict | None = None) -> pd.DataFrame:
    """Build a minimal DataFrame with DATE_TIME column."""
    d = {"DATE_TIME": timestamps}
    if extra_cols:
        d.update(extra_cols)
    return pd.DataFrame(d)


TRAIN_START = "2020-01-01T00:00:00Z"
TRAIN_END   = "2023-12-31T00:00:00Z"
VAL_START   = "2024-01-01T00:00:00Z"
VAL_END     = "2024-12-31T00:00:00Z"
HELDOUT_START = "2025-01-01T00:00:00Z"

BOUNDARY = SplitBoundary.from_strings(
    train_start=TRAIN_START,
    train_end=TRAIN_END,
    validation_start=VAL_START,
    validation_end=VAL_END,
    heldout_start=HELDOUT_START,
)

TRAIN_TIMESTAMPS = [
    "2020-06-01T00:00:00Z",
    "2021-01-01T00:00:00Z",
    "2022-06-01T00:00:00Z",
    "2023-06-01T00:00:00Z",
]
VAL_TIMESTAMPS = [
    "2024-03-01T00:00:00Z",
    "2024-09-01T00:00:00Z",
]
HELDOUT_TIMESTAMPS = [
    "2025-01-01T00:00:00Z",
    "2025-06-01T00:00:00Z",
]


# ===========================================================================
# 1. No rows >= 2025-01-01 can be passed to fit
# ===========================================================================

class TestNoHeldoutRowsForFit:

    def test_clean_train_data_passes(self):
        df = _df(TRAIN_TIMESTAMPS, {"feature_a": [1, 2, 3, 4]})
        assert_no_heldout_rows(df, "DATE_TIME")  # must not raise

    def test_heldout_row_exact_boundary_raises(self):
        df = _df(TRAIN_TIMESTAMPS + ["2025-01-01T00:00:00Z"])
        with pytest.raises(SplitViolation, match="2025-01-01"):
            assert_no_heldout_rows(df, "DATE_TIME")

    def test_heldout_row_after_boundary_raises(self):
        df = _df(["2025-06-15T00:00:00Z", "2026-01-01T00:00:00Z"])
        with pytest.raises(SplitViolation):
            assert_no_heldout_rows(df, "DATE_TIME")

    def test_validation_rows_alone_pass_heldout_check(self):
        """Validation rows < 2025 should not trigger the heldout guard."""
        df = _df(VAL_TIMESTAMPS)
        assert_no_heldout_rows(df, "DATE_TIME")  # must not raise

    def test_mixed_train_heldout_raises(self):
        df = _df(TRAIN_TIMESTAMPS + HELDOUT_TIMESTAMPS)
        with pytest.raises(SplitViolation, match=r"\b2\b"):  # "Found 2 rows"
            assert_no_heldout_rows(df, "DATE_TIME")

    def test_slice_train_removes_heldout(self):
        all_ts = TRAIN_TIMESTAMPS + VAL_TIMESTAMPS + HELDOUT_TIMESTAMPS
        df = _df(all_ts)
        train_df = slice_train(df, "DATE_TIME", BOUNDARY)
        ts = pd.to_datetime(train_df["DATE_TIME"], utc=True)
        assert (ts < HELDOUT_START_DT).all()
        assert (ts < _ts(VAL_START)).all()
        assert len(train_df) == len(TRAIN_TIMESTAMPS)

    def test_assert_within_train_blocks_heldout(self):
        df = _df(HELDOUT_TIMESTAMPS)
        with pytest.raises(SplitViolation):
            assert_within_train(df, "DATE_TIME", BOUNDARY)

    def test_assert_within_train_blocks_validation(self):
        df = _df(VAL_TIMESTAMPS)
        with pytest.raises(SplitViolation, match="validation_start"):
            assert_within_train(df, "DATE_TIME", BOUNDARY)

    def test_assert_within_train_passes_for_train_rows(self):
        df = _df(TRAIN_TIMESTAMPS)
        assert_within_train(df, "DATE_TIME", BOUNDARY)  # must not raise

    def test_custom_heldout_boundary(self):
        df = _df(["2024-07-01T00:00:00Z"])
        with pytest.raises(SplitViolation):
            assert_no_heldout_rows(df, "DATE_TIME", heldout_start="2024-06-01T00:00:00Z")

    def test_real_train_csv_has_no_heldout_rows(self):
        """Smoke test against the actual ETHUSDT 4h train.csv."""
        csv_path = (
            REPO_ROOT
            / "experiments/stage_a_screening/inputs/ethusdt/4h/tech_stat/train.csv"
        )
        if not csv_path.exists():
            pytest.skip(f"train.csv not found: {csv_path}")
        df = pd.read_csv(csv_path, usecols=["DATE_TIME"])
        assert_no_heldout_rows(df, "DATE_TIME")  # must not raise


# ===========================================================================
# 2. Validation data cannot be used for fitting (transform/score only)
# ===========================================================================

class TestValidationTransformOnly:

    def test_fit_on_validation_timestamps_raises(self):
        fit_ts = pd.to_datetime(VAL_TIMESTAMPS, utc=True)
        fit_series = pd.Series(fit_ts)
        with pytest.raises(SplitViolation, match="validation window"):
            assert_no_fit_on_validation(fit_series, BOUNDARY)

    def test_fit_on_heldout_timestamps_raises(self):
        fit_ts = pd.to_datetime(HELDOUT_TIMESTAMPS, utc=True)
        fit_series = pd.Series(fit_ts)
        with pytest.raises(SplitViolation, match="heldout"):
            assert_no_fit_on_validation(fit_series, BOUNDARY)

    def test_fit_on_train_timestamps_passes(self):
        fit_ts = pd.to_datetime(TRAIN_TIMESTAMPS, utc=True)
        assert_no_fit_on_validation(pd.Series(fit_ts), BOUNDARY)  # must not raise

    def test_fit_on_none_passes(self):
        assert_no_fit_on_validation(None, BOUNDARY)  # must not raise

    def test_slice_validation_excludes_heldout(self):
        all_ts = TRAIN_TIMESTAMPS + VAL_TIMESTAMPS + HELDOUT_TIMESTAMPS
        df = _df(all_ts)
        val_df = slice_validation(df, "DATE_TIME", BOUNDARY)
        ts = pd.to_datetime(val_df["DATE_TIME"], utc=True)
        assert (ts >= _ts(VAL_START)).all()
        assert (ts < HELDOUT_START_DT).all()
        assert len(val_df) == len(VAL_TIMESTAMPS)

    def test_assert_fit_precedes_eval_overlapping_raises(self):
        with pytest.raises(SplitViolation, match="eval_start"):
            assert_fit_precedes_eval(
                fit_end="2024-06-01T00:00:00Z",
                eval_start="2024-01-01T00:00:00Z",
            )

    def test_assert_fit_precedes_eval_equal_raises(self):
        with pytest.raises(SplitViolation):
            assert_fit_precedes_eval(
                fit_end="2024-01-01T00:00:00Z",
                eval_start="2024-01-01T00:00:00Z",
            )

    def test_assert_fit_precedes_eval_clean_passes(self):
        assert_fit_precedes_eval(
            fit_end="2023-12-31T23:00:00Z",
            eval_start="2024-01-01T00:00:00Z",
        )  # must not raise


# ===========================================================================
# 3. ArtifactMetadata: schema completeness and uses_heldout=false invariant
# ===========================================================================

class TestArtifactMetadata:

    def _minimal_valid(self) -> ArtifactMetadata:
        return ArtifactMetadata(
            artifact_type="test_artifact",
            asset="ethusdt",
            timeframe="4h",
            feature_family="tech_stat",
            fit_start="2020-01-01T00:00:00+00:00",
            fit_end="2023-12-31T00:00:00+00:00",
            heldout_start="2025-01-01T00:00:00Z",
            uses_heldout=False,
            fit_excludes_heldout_2025=True,
            fit_excludes_validation_if_required=True,
            input_hashes={"some_file.csv": "abc123"},
            config_hash="def456",
        )

    def test_valid_metadata_passes(self):
        meta = self._minimal_valid()
        errors = meta.validate()
        assert errors == [], f"Unexpected errors: {errors}"

    def test_uses_heldout_true_fails(self):
        meta = self._minimal_valid()
        meta.uses_heldout = True
        errors = meta.validate()
        assert any("uses_heldout" in e for e in errors)

    def test_fit_excludes_heldout_false_fails(self):
        meta = self._minimal_valid()
        meta.fit_excludes_heldout_2025 = False
        errors = meta.validate()
        assert any("fit_excludes_heldout_2025" in e for e in errors)

    def test_missing_input_hashes_fails(self):
        meta = self._minimal_valid()
        meta.input_hashes = {}
        errors = meta.validate()
        assert any("input_hashes" in e for e in errors)

    def test_missing_config_hash_fails(self):
        meta = self._minimal_valid()
        meta.config_hash = ""
        errors = meta.validate()
        assert any("config_hash" in e for e in errors)

    def test_fit_end_at_heldout_boundary_fails(self):
        meta = self._minimal_valid()
        meta.fit_end = "2025-01-01T00:00:00+00:00"
        errors = meta.validate()
        assert any("fit_end" in e for e in errors)

    def test_fit_end_after_heldout_boundary_fails(self):
        meta = self._minimal_valid()
        meta.fit_end = "2025-06-01T00:00:00+00:00"
        errors = meta.validate()
        assert any("fit_end" in e for e in errors)

    def test_assert_valid_raises_on_failure(self):
        meta = self._minimal_valid()
        meta.uses_heldout = True
        with pytest.raises(ValueError, match="uses_heldout"):
            meta.assert_valid()

    def test_to_json_contains_required_fields(self):
        meta = self._minimal_valid()
        payload = json.loads(meta.to_json())
        for field_name in [
            "artifact_type", "asset", "timeframe", "fit_start", "fit_end",
            "heldout_start", "uses_heldout", "input_hashes", "config_hash",
            "fit_excludes_heldout_2025", "fit_excludes_validation_if_required",
        ]:
            assert field_name in payload, f"Missing field: {field_name}"

    def test_write_metadata_creates_file(self):
        meta = self._minimal_valid()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "meta.json"
            write_metadata(meta, out)
            assert out.exists()
            loaded = json.loads(out.read_text())
            assert loaded["uses_heldout"] is False
            assert loaded["fit_excludes_heldout_2025"] is True

    def test_compute_config_hash_is_deterministic(self):
        cfg = {"n_components": 4, "algorithm": "hmm", "seed": 42}
        h1 = compute_config_hash(cfg)
        h2 = compute_config_hash(cfg)
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex

    def test_compute_config_hash_differs_on_change(self):
        cfg1 = {"n_components": 4}
        cfg2 = {"n_components": 5}
        assert compute_config_hash(cfg1) != compute_config_hash(cfg2)

    def test_compute_file_hash_missing_file(self):
        h = compute_file_hash("/nonexistent/path/to/file.parquet")
        assert h == "FILE_NOT_FOUND"

    def test_build_metadata_with_timestamps(self):
        fit_ts = pd.to_datetime(TRAIN_TIMESTAMPS, utc=True)
        meta = build_metadata(
            artifact_type="scaler",
            asset="ethusdt",
            timeframe="4h",
            config={"scaler": "standard", "seed": 0},
            input_paths=[],
            output_paths=[],
            fit_df_timestamps=pd.Series(fit_ts),
            feature_family="tech_stat",
        )
        assert meta.fit_start != ""
        assert meta.fit_end != ""
        assert meta.fit_row_count == 4
        assert meta.uses_heldout is False
        assert meta.fit_excludes_heldout_2025 is True

    def test_metadata_includes_input_hashes_and_config_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a small temp file to hash
            tmp_file = Path(tmpdir) / "input.csv"
            tmp_file.write_text("col1,col2\n1,2\n3,4\n")
            meta = build_metadata(
                artifact_type="hmm_regime",
                asset="ethusdt",
                timeframe="4h",
                config={"n_states": 3, "seed": 7},
                input_paths=[tmp_file],
                output_paths=[],
                fit_df_timestamps=pd.Series(
                    pd.to_datetime(TRAIN_TIMESTAMPS, utc=True)
                ),
            )
            assert str(tmp_file) in meta.input_hashes
            assert meta.input_hashes[str(tmp_file)] != "FILE_NOT_FOUND"
            assert meta.config_hash != ""

    def test_metadata_fit_window_is_recorded(self):
        fit_ts = pd.to_datetime(
            ["2020-01-01T00:00:00Z", "2023-12-31T00:00:00Z"], utc=True
        )
        meta = build_metadata(
            artifact_type="gmm_ood",
            asset="ethusdt",
            timeframe="4h",
            config={"n_components": 2},
            input_paths=[],
            output_paths=[],
            fit_df_timestamps=pd.Series(fit_ts),
        )
        assert "2020-01-01" in meta.fit_start
        assert "2023-12-31" in meta.fit_end

    def test_metadata_heldout_boundary_recorded(self):
        meta = self._minimal_valid()
        assert meta.heldout_start == "2025-01-01T00:00:00Z"


# ===========================================================================
# 4. Feature alignment: timestamp-safe join, no post-heldout rows in features
# ===========================================================================

class TestFeatureAlignment:

    def _base_df(self) -> pd.DataFrame:
        return _df(TRAIN_TIMESTAMPS, {"close": [100, 110, 105, 115]})

    def _feat_df(self, timestamps: list[str] | None = None) -> pd.DataFrame:
        ts = timestamps or TRAIN_TIMESTAMPS
        return _df(ts, {"regime_id": [0, 1, 0, 1][: len(ts)]})

    def test_clean_join_passes(self):
        base = self._base_df()
        feat = self._feat_df()
        merged = validate_feature_join(base, feat, "DATE_TIME")
        assert len(merged) == len(base)
        assert "regime_id" in merged.columns

    def test_post_heldout_feature_raises(self):
        base = self._base_df()
        feat = _df(TRAIN_TIMESTAMPS + HELDOUT_TIMESTAMPS, {"regime_id": [0, 1, 0, 1, 2, 2]})
        with pytest.raises(SplitViolation, match="heldout"):
            validate_feature_join(base, feat, "DATE_TIME")

    def test_feature_future_of_base_raises(self):
        base = self._base_df()  # max timestamp 2023-06-01
        future_ts = ["2024-01-01T00:00:00Z"]
        feat = _df(TRAIN_TIMESTAMPS + future_ts, {"regime_id": [0, 1, 0, 1, 2]})
        with pytest.raises(SplitViolation, match="after the last base timestamp"):
            validate_feature_join(base, feat, "DATE_TIME")

    def test_duplicated_feature_timestamps_raises(self):
        base = self._base_df()
        dup_ts = TRAIN_TIMESTAMPS[:2] + TRAIN_TIMESTAMPS[:2]  # duplicates
        feat = _df(dup_ts, {"regime_id": [0, 1, 0, 1]})
        with pytest.raises(SplitViolation):
            validate_feature_join(base, feat, "DATE_TIME")

    def test_no_row_count_inflation(self):
        base = self._base_df()
        feat = self._feat_df()
        merged = validate_feature_join(base, feat, "DATE_TIME")
        assert len(merged) == 4

    def test_assert_timestamps_align_equal_passes(self):
        df_a = _df(TRAIN_TIMESTAMPS)
        df_b = _df(TRAIN_TIMESTAMPS, {"regime_id": [0, 1, 0, 1]})
        assert_timestamps_align(df_a, df_b)  # must not raise

    def test_assert_timestamps_align_mismatch_raises(self):
        df_a = _df(TRAIN_TIMESTAMPS)
        different_ts = [
            "2020-06-01T00:00:00Z",
            "2021-01-01T00:00:00Z",
            "2022-06-01T00:00:00Z",
            "2023-07-01T00:00:00Z",  # differs
        ]
        df_b = _df(different_ts)
        with pytest.raises(SplitViolation, match="mismatch"):
            assert_timestamps_align(df_a, df_b)

    def test_assert_timestamps_align_different_lengths_raises(self):
        df_a = _df(TRAIN_TIMESTAMPS)
        df_b = _df(TRAIN_TIMESTAMPS[:2])
        with pytest.raises(SplitViolation, match="lengths"):
            assert_timestamps_align(df_a, df_b)

    def test_assert_no_future_features_clean_passes(self):
        obs = _df(TRAIN_TIMESTAMPS)
        feat = _df(TRAIN_TIMESTAMPS, {"regime_id": [0, 1, 0, 1]})
        assert_no_future_features(feat, obs)  # must not raise

    def test_assert_no_future_features_lookahead_raises(self):
        obs_ts = TRAIN_TIMESTAMPS  # max: 2023-06-01
        feat_ts = [
            "2020-06-01T00:00:00Z",
            "2021-01-01T00:00:00Z",
            "2022-06-01T00:00:00Z",
            "2024-01-01T00:00:00Z",  # future relative to obs[3]=2023-06-01
        ]
        obs = _df(obs_ts)
        feat = _df(feat_ts, {"regime_id": [0, 1, 0, 1]})
        with pytest.raises(SplitViolation, match="lookahead"):
            assert_no_future_features(feat, obs)

    def test_load_and_validate_feature_csv_real_data(self):
        """Smoke test: ETHUSDT 4h train.csv loads and passes all alignment checks."""
        csv_path = (
            REPO_ROOT
            / "experiments/stage_a_screening/inputs/ethusdt/4h/tech_stat/train.csv"
        )
        if not csv_path.exists():
            pytest.skip(f"train.csv not found: {csv_path}")
        df = load_and_validate_feature_csv(csv_path)
        assert len(df) > 0
        assert "DATE_TIME" in df.columns

    def test_load_csv_with_heldout_row_raises(self):
        """A feature CSV containing a 2025+ row must be rejected."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("DATE_TIME,feature_x\n")
            for ts in TRAIN_TIMESTAMPS:
                f.write(f"{ts},1.0\n")
            f.write("2025-03-01T00:00:00Z,2.0\n")  # heldout row
            fpath = f.name
        try:
            with pytest.raises(SplitViolation, match="heldout"):
                load_and_validate_feature_csv(fpath)
        finally:
            Path(fpath).unlink(missing_ok=True)


# ===========================================================================
# 5. Missing or ambiguous timestamp columns fail closed
# ===========================================================================

class TestTimestampFailClosed:

    def test_missing_timestamp_column_raises(self):
        df = pd.DataFrame({"feature_a": [1, 2, 3]})
        with pytest.raises(SplitViolation, match="not found"):
            require_timestamp_column(df, "DATE_TIME")

    def test_wrong_column_name_raises(self):
        df = _df(TRAIN_TIMESTAMPS)
        with pytest.raises(SplitViolation, match="not found"):
            require_timestamp_column(df, "timestamp")  # wrong name

    def test_unparseable_timestamp_values_raise(self):
        df = pd.DataFrame({"DATE_TIME": ["not_a_date", "also_not", "nope"]})
        with pytest.raises(SplitViolation):
            require_timestamp_column(df, "DATE_TIME")

    def test_nat_values_raise(self):
        df = pd.DataFrame({"DATE_TIME": [None, "2021-01-01T00:00:00Z"]})
        with pytest.raises(SplitViolation, match="NaT"):
            require_timestamp_column(df, "DATE_TIME")

    def test_duplicated_column_name_raises(self):
        df = pd.DataFrame(
            [[1, 2], [3, 4]],
            columns=["DATE_TIME", "DATE_TIME"],
        )
        with pytest.raises(SplitViolation, match="duplicated"):
            require_timestamp_column(df, "DATE_TIME")

    def test_non_monotonic_timestamps_raise(self):
        ts = ["2022-01-01T00:00:00Z", "2021-01-01T00:00:00Z", "2023-01-01T00:00:00Z"]
        df = _df(ts)
        with pytest.raises(SplitViolation, match="monotonically"):
            validate_timestamps(df, "DATE_TIME", require_monotonic=True)

    def test_duplicate_timestamps_raise(self):
        ts = ["2022-01-01T00:00:00Z", "2022-01-01T00:00:00Z", "2023-01-01T00:00:00Z"]
        df = _df(ts)
        with pytest.raises(SplitViolation, match="duplicate"):
            validate_timestamps(df, "DATE_TIME", allow_duplicates=False)

    def test_duplicate_timestamps_allowed_when_flag_set(self):
        ts = ["2022-01-01T00:00:00Z", "2022-01-01T00:00:00Z", "2023-01-01T00:00:00Z"]
        df = _df(ts)
        # should not raise when allow_duplicates=True (monotonic check still off for dupes)
        validate_timestamps(df, "DATE_TIME", require_monotonic=False, allow_duplicates=True)

    def test_missing_column_in_heldout_check_raises(self):
        df = pd.DataFrame({"price": [1.0, 2.0]})
        with pytest.raises(SplitViolation, match="not found"):
            assert_no_heldout_rows(df, "DATE_TIME")

    def test_split_boundary_train_after_validation_raises(self):
        with pytest.raises(SplitViolation, match="train_end.*must be <="):
            SplitBoundary.from_strings(
                train_start="2020-01-01T00:00:00Z",
                train_end="2024-06-01T00:00:00Z",   # overlaps validation
                validation_start="2024-01-01T00:00:00Z",
                validation_end="2024-12-31T00:00:00Z",
            )

    def test_split_boundary_validation_after_heldout_raises(self):
        with pytest.raises(SplitViolation, match="validation_end.*must be <="):
            SplitBoundary.from_strings(
                train_start="2020-01-01T00:00:00Z",
                train_end="2023-12-31T00:00:00Z",
                validation_start="2024-01-01T00:00:00Z",
                validation_end="2025-06-01T00:00:00Z",  # past heldout
            )

    def test_feature_join_missing_timestamp_col_raises(self):
        base = pd.DataFrame({"price": [100, 110]})
        feat = _df(TRAIN_TIMESTAMPS[:2], {"regime_id": [0, 1]})
        with pytest.raises(SplitViolation, match="not found"):
            validate_feature_join(base, feat, "DATE_TIME")

    def test_feature_join_feature_missing_timestamp_col_raises(self):
        base = _df(TRAIN_TIMESTAMPS[:2])
        feat = pd.DataFrame({"regime_id": [0, 1]})
        with pytest.raises(SplitViolation, match="not found"):
            validate_feature_join(base, feat, "DATE_TIME")

    def test_empty_timestamp_string_raises(self):
        """Empty string timestamp column name fails closed."""
        df = _df(TRAIN_TIMESTAMPS)
        with pytest.raises(SplitViolation, match="not found"):
            require_timestamp_column(df, "")


# ===========================================================================
# 6. SplitBoundary helpers
# ===========================================================================

class TestSplitBoundary:

    def test_from_strings_roundtrip(self):
        b = SplitBoundary.from_strings(
            train_start=TRAIN_START,
            train_end=TRAIN_END,
            validation_start=VAL_START,
            validation_end=VAL_END,
            heldout_start=HELDOUT_START,
        )
        assert b.heldout_start == HELDOUT_START_DT

    def test_train_end_after_validation_start_raises(self):
        with pytest.raises(SplitViolation):
            SplitBoundary.from_strings(
                train_start="2020-01-01T00:00:00Z",
                train_end="2024-06-01T00:00:00Z",
                validation_start="2024-01-01T00:00:00Z",
                validation_end="2024-12-31T00:00:00Z",
            )

    def test_default_heldout_is_2025(self):
        b = SplitBoundary.from_strings(
            train_start="2020-01-01T00:00:00Z",
            train_end="2023-12-31T00:00:00Z",
            validation_start="2024-01-01T00:00:00Z",
            validation_end="2024-12-31T00:00:00Z",
        )
        assert b.heldout_start.year == 2025
        assert b.heldout_start.month == 1
        assert b.heldout_start.day == 1


# ===========================================================================
# 7. Registry file exists and is valid JSON
# ===========================================================================

class TestRegistry:

    def test_registry_file_exists(self):
        registry = REPO_ROOT / "experiments/unsup_causal_audit/registry.json"
        assert registry.exists(), f"Registry not found: {registry}"

    def test_registry_is_valid_json(self):
        registry = REPO_ROOT / "experiments/unsup_causal_audit/registry.json"
        data = json.loads(registry.read_text())
        assert "schema_version" in data
        assert "heldout_start" in data
        assert data["heldout_start"] == "2025-01-01T00:00:00Z"

    def test_registry_heldout_boundary(self):
        registry = REPO_ROOT / "experiments/unsup_causal_audit/registry.json"
        data = json.loads(registry.read_text())
        assert data["heldout_start"] == "2025-01-01T00:00:00Z"
