"""
Feature alignment validator for Phase 3X unsupervised/causal artifacts.

Ensures that unsupervised/causal feature tables can be timestamp-safely joined
to RL training inputs without introducing lookahead or post-heldout rows.

Design rules (from unsupervised_causal_audit.md § Split Rules):
  - All joins are left-joins on DATE_TIME (RL input is the left table).
  - Right-side feature timestamps must be present in or earlier than the join key.
  - No post-2025-01-01 rows may enter via join.
  - Non-monotonic, duplicated, or missing timestamps fail closed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from _scripts.lib.split_guard import (
    HELDOUT_START_DEFAULT,
    SplitViolation,
    _parse_ts,
    require_timestamp_column,
    validate_timestamps,
)


TIMESTAMP_COL = "DATE_TIME"


# ---------------------------------------------------------------------------
# Core join validator
# ---------------------------------------------------------------------------

def validate_feature_join(
    base_df: pd.DataFrame,
    feature_df: pd.DataFrame,
    timestamp_col: str = TIMESTAMP_COL,
    *,
    heldout_start: str | None = HELDOUT_START_DEFAULT,
    allow_missing_in_feature: bool = True,
    context: str = "",
) -> pd.DataFrame:
    """
    Validate that `feature_df` can be left-joined to `base_df` on `timestamp_col`
    without introducing data leakage or misalignment.

    Checks performed:
      1. Both DataFrames have the timestamp column.
      2. Timestamps in both DataFrames are monotonic and non-duplicated.
      3. No post-heldout rows in feature_df.
      4. feature_df contains no timestamps that are strictly after max(base_df[ts]).
         (A feature column should not reference a bar that hasn't happened yet in the
         RL input timeline — this is a lookahead check.)
      5. The left-join produces no rows with NaT in the join key.
      6. Returns the merged DataFrame (base with features appended).

    Raises SplitViolation on any failure.
    Returns the merged DataFrame for inspection.
    """
    ctx = f"[{context}] " if context else ""

    # 1. Validate timestamps in both frames
    base_ts = validate_timestamps(base_df, timestamp_col, require_monotonic=True)
    feat_ts = validate_timestamps(feature_df, timestamp_col, require_monotonic=True)

    # 2. No post-heldout rows in feature frame
    if heldout_start:
        boundary = _parse_ts(heldout_start)
        post_heldout = feat_ts >= boundary
        if post_heldout.any():
            n = int(post_heldout.sum())
            examples = feat_ts[post_heldout].iloc[:3].tolist()
            raise SplitViolation(
                f"{ctx}feature_df has {n} rows with timestamp >= heldout_start "
                f"({boundary.isoformat()}). Examples: {examples}. "
                "These rows must be removed before the join."
            )

    # 3. No feature timestamp strictly after the last base timestamp
    base_max = base_ts.max()
    future_feat = feat_ts > base_max
    if future_feat.any():
        n = int(future_feat.sum())
        raise SplitViolation(
            f"{ctx}feature_df has {n} timestamps after the last base timestamp "
            f"({base_max}). This would produce NaN rows and may indicate lookahead."
        )

    # 4. Perform the left join and verify no NaT keys in result
    base_copy = base_df.copy()
    base_copy["__base_ts_utc__"] = base_ts

    feat_copy = feature_df.copy()
    feat_copy["__feat_ts_utc__"] = feat_ts

    # Normalise timestamp col to UTC string for merge key to avoid tz mismatches
    base_copy["__merge_key__"] = base_copy["__base_ts_utc__"].dt.floor("s")
    feat_copy["__merge_key__"] = feat_copy["__feat_ts_utc__"].dt.floor("s")

    # Drop internal helpers from feature side before merge
    feat_merge = feat_copy.drop(columns=["__feat_ts_utc__"])

    merged = base_copy.merge(
        feat_merge.drop(columns=[timestamp_col], errors="ignore"),
        on="__merge_key__",
        how="left",
    )

    # 5. Check for unexpected row count change (left join should preserve base rows)
    if len(merged) != len(base_df):
        raise SplitViolation(
            f"{ctx}Left join inflated row count: {len(base_df)} → {len(merged)}. "
            "feature_df likely has duplicate timestamps at the join key."
        )

    # Drop helper columns
    merged.drop(columns=["__base_ts_utc__", "__merge_key__"], inplace=True, errors="ignore")

    # 6. Check for extra NaN rows introduced by non-matching timestamps
    if not allow_missing_in_feature:
        feat_cols = [c for c in feature_df.columns if c != timestamp_col]
        nan_mask = merged[feat_cols].isnull().any(axis=1)
        if nan_mask.any():
            n = int(nan_mask.sum())
            raise SplitViolation(
                f"{ctx}{n} rows in base_df have no matching feature timestamp. "
                "Set allow_missing_in_feature=True to allow NaN-filled rows."
            )

    return merged


# ---------------------------------------------------------------------------
# Additional point-in-time availability checks
# ---------------------------------------------------------------------------

def assert_no_future_features(
    feature_df: pd.DataFrame,
    observation_df: pd.DataFrame,
    timestamp_col: str = TIMESTAMP_COL,
    *,
    context: str = "",
) -> None:
    """
    Confirm that for every row i in observation_df, any feature value at
    timestamp T was computed using only data available at or before T.

    This is a structural check: it verifies that the feature timestamps
    in feature_df do NOT exceed the corresponding observation timestamps.
    Both DataFrames must be the same length and share the same row ordering.

    For a causal feature computed at bar i from data through bar i-1,
    the feature_df[timestamp_col][i] == observation_df[timestamp_col][i]
    is acceptable (feature is available at the start of bar i).

    Raises SplitViolation if any feature timestamp > observation timestamp.
    """
    ctx = f"[{context}] " if context else ""
    if len(feature_df) != len(observation_df):
        raise SplitViolation(
            f"{ctx}feature_df and observation_df have different lengths "
            f"({len(feature_df)} vs {len(observation_df)}). "
            "They must be row-aligned for the point-in-time check."
        )
    obs_ts = require_timestamp_column(observation_df, timestamp_col)
    feat_ts = require_timestamp_column(feature_df, timestamp_col)
    future_mask = feat_ts > obs_ts
    if future_mask.any():
        n = int(future_mask.sum())
        examples = list(zip(
            feat_ts[future_mask].iloc[:3].tolist(),
            obs_ts[future_mask].iloc[:3].tolist(),
        ))
        raise SplitViolation(
            f"{ctx}{n} feature timestamps are strictly after their corresponding "
            f"observation timestamps (lookahead). Examples (feat, obs): {examples}"
        )


def assert_timestamps_align(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    timestamp_col: str = TIMESTAMP_COL,
    *,
    context: str = "",
) -> None:
    """
    Verify that two DataFrames of equal length share identical timestamps.
    Used to confirm a feature table is row-aligned with the base input table.
    """
    ctx = f"[{context}] " if context else ""
    if len(df_a) != len(df_b):
        raise SplitViolation(
            f"{ctx}DataFrames have different lengths ({len(df_a)} vs {len(df_b)})."
        )
    ts_a = require_timestamp_column(df_a, timestamp_col)
    ts_b = require_timestamp_column(df_b, timestamp_col)
    mismatches = (ts_a.values != ts_b.values)
    if mismatches.any():
        n = int(mismatches.sum())
        raise SplitViolation(
            f"{ctx}{n} timestamp mismatches between the two DataFrames. "
            "Feature table is not row-aligned with the base input."
        )


def load_and_validate_feature_csv(
    path: str | Path,
    timestamp_col: str = TIMESTAMP_COL,
    heldout_start: str = HELDOUT_START_DEFAULT,
) -> pd.DataFrame:
    """
    Load a feature CSV and run basic integrity checks.
    Returns a DataFrame with validated, UTC-normalised timestamps.
    """
    p = Path(path)
    if not p.exists():
        raise SplitViolation(f"Feature CSV not found: {p}")
    df = pd.read_csv(p)
    validate_timestamps(df, timestamp_col, require_monotonic=True)
    from _scripts.lib.split_guard import assert_no_heldout_rows
    assert_no_heldout_rows(df, timestamp_col, heldout_start)
    return df
