"""
Split guard utilities for Phase 3X unsupervised/causal audit scaffolding.

Enforces temporal boundaries:
  - Training fit window: strictly before validation_start
  - Validation: transform/score only, never used to fit
  - Heldout (Stage C): rows at or after 2025-01-01T00:00:00Z are forbidden before
    the final locked Stage C evaluation

All checks fail closed (raise SplitViolation on ambiguity or missing data).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd


HELDOUT_START_DEFAULT = "2025-01-01T00:00:00Z"
HELDOUT_START_DT = datetime(2025, 1, 1, tzinfo=timezone.utc)


class SplitViolation(Exception):
    """Raised whenever a temporal or split-integrity check fails."""


# ---------------------------------------------------------------------------
# Split boundary declaration
# ---------------------------------------------------------------------------

@dataclass
class SplitBoundary:
    """Declared temporal boundaries for one experiment run or artifact."""

    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    heldout_start: datetime = field(default_factory=lambda: HELDOUT_START_DT)

    def __post_init__(self) -> None:
        if self.train_end > self.validation_start:
            raise SplitViolation(
                f"train_end ({self.train_end}) must be <= validation_start "
                f"({self.validation_start})"
            )
        if self.validation_end > self.heldout_start:
            raise SplitViolation(
                f"validation_end ({self.validation_end}) must be <= heldout_start "
                f"({self.heldout_start})"
            )
        if self.train_end >= self.heldout_start:
            raise SplitViolation(
                f"train_end ({self.train_end}) must be < heldout_start "
                f"({self.heldout_start})"
            )

    @classmethod
    def from_strings(
        cls,
        train_start: str,
        train_end: str,
        validation_start: str,
        validation_end: str,
        heldout_start: str = HELDOUT_START_DEFAULT,
    ) -> "SplitBoundary":
        return cls(
            train_start=_parse_ts(train_start),
            train_end=_parse_ts(train_end),
            validation_start=_parse_ts(validation_start),
            validation_end=_parse_ts(validation_end),
            heldout_start=_parse_ts(heldout_start),
        )


# ---------------------------------------------------------------------------
# Timestamp parsing helpers
# ---------------------------------------------------------------------------

def _parse_ts(value: str | datetime) -> datetime:
    """Parse an ISO-8601 string or pass-through datetime. Always returns UTC-aware."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.strip():
        raise SplitViolation(f"Cannot parse timestamp: {value!r}")
    s = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise SplitViolation(f"Cannot parse timestamp string: {value!r}") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _coerce_series_to_utc(series: pd.Series, col_name: str) -> pd.Series:
    """Convert a Series to UTC-aware datetime64, fail closed on error."""
    try:
        parsed = pd.to_datetime(series, utc=True, errors="raise")
    except Exception as exc:
        raise SplitViolation(
            f"Column '{col_name}' cannot be parsed as timestamps: {exc}"
        ) from exc
    if parsed.isnull().any():
        n_null = int(parsed.isnull().sum())
        raise SplitViolation(
            f"Column '{col_name}' has {n_null} unparseable/NaT values."
        )
    return parsed


# ---------------------------------------------------------------------------
# Public guards — all raise SplitViolation on failure
# ---------------------------------------------------------------------------

def require_timestamp_column(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Verify that `col` exists in df and is parseable as timestamps.
    Returns the UTC-normalised datetime Series.
    Fails closed if column is missing, has duplicate name, or contains NaT.
    """
    if col not in df.columns:
        present = list(df.columns[:10])
        raise SplitViolation(
            f"Required timestamp column '{col}' not found in DataFrame. "
            f"First 10 columns: {present}"
        )
    # Guard against accidental duplicate columns (returns DataFrame, not Series)
    col_data = df[col]
    if isinstance(col_data, pd.DataFrame):
        raise SplitViolation(
            f"Timestamp column '{col}' is duplicated in the DataFrame "
            f"(found {col_data.shape[1]} copies). Deduplicate first."
        )
    return _coerce_series_to_utc(col_data, col)


def validate_timestamps(
    df: pd.DataFrame,
    col: str,
    *,
    require_monotonic: bool = True,
    allow_duplicates: bool = False,
) -> pd.Series:
    """
    Full timestamp integrity check.
    Returns UTC-normalised timestamp Series.
    """
    ts = require_timestamp_column(df, col)
    if not allow_duplicates:
        dupes = ts.duplicated()
        if dupes.any():
            n = int(dupes.sum())
            examples = ts[dupes].iloc[:3].tolist()
            raise SplitViolation(
                f"Column '{col}' has {n} duplicate timestamps. "
                f"Examples: {examples}"
            )
    if require_monotonic:
        if not ts.is_monotonic_increasing:
            first_bad_idx = int((ts.diff() < pd.Timedelta(0)).idxmax())
            raise SplitViolation(
                f"Column '{col}' is not monotonically increasing. "
                f"First violation at index {first_bad_idx}: {ts.iloc[first_bad_idx]}"
            )
    return ts


def assert_no_heldout_rows(
    df: pd.DataFrame,
    timestamp_col: str,
    heldout_start: str | datetime = HELDOUT_START_DEFAULT,
    *,
    context: str = "",
) -> None:
    """
    Raise SplitViolation if any row has timestamp >= heldout_start.
    This is the primary firewall preventing Stage C data leakage.
    """
    boundary = _parse_ts(heldout_start)
    ts = require_timestamp_column(df, timestamp_col)
    violating = ts >= boundary
    if violating.any():
        n = int(violating.sum())
        examples = ts[violating].iloc[:3].tolist()
        ctx = f" [{context}]" if context else ""
        raise SplitViolation(
            f"{ctx}Found {n} rows with timestamp >= heldout_start "
            f"({boundary.isoformat()}). "
            f"Examples: {examples}. "
            "These rows must not be used for fitting. "
            "Apply df = df[df[col] < heldout_start] before calling fit()."
        )


def assert_fit_precedes_eval(
    fit_end: str | datetime,
    eval_start: str | datetime,
    *,
    context: str = "",
) -> None:
    """
    Raise SplitViolation if fit_end >= eval_start.
    Enforces that a fitted transform was not trained on data it is evaluated on.
    """
    fe = _parse_ts(fit_end)
    es = _parse_ts(eval_start)
    if fe >= es:
        ctx = f" [{context}]" if context else ""
        raise SplitViolation(
            f"{ctx}fit_end ({fe.isoformat()}) >= eval_start ({es.isoformat()}). "
            "The fitted transform overlaps the evaluation window — data leakage."
        )


def assert_within_train(
    df: pd.DataFrame,
    timestamp_col: str,
    boundary: SplitBoundary,
    *,
    context: str = "",
) -> None:
    """
    Raise SplitViolation if any row falls outside [train_start, train_end).
    Used to verify that data being fitted is strictly within the declared train window.
    """
    ts = require_timestamp_column(df, timestamp_col)
    too_early = ts < boundary.train_start
    too_late = ts >= boundary.validation_start
    ctx = f" [{context}]" if context else ""
    if too_early.any():
        n = int(too_early.sum())
        raise SplitViolation(
            f"{ctx}{n} rows predate train_start ({boundary.train_start.isoformat()})."
        )
    if too_late.any():
        n = int(too_late.sum())
        examples = ts[too_late].iloc[:3].tolist()
        raise SplitViolation(
            f"{ctx}{n} rows are at or after validation_start "
            f"({boundary.validation_start.isoformat()}). "
            f"Examples: {examples}. "
            "Only training rows may be passed to fit()."
        )


def assert_no_fit_on_validation(
    fit_timestamps: pd.Series | None,
    boundary: SplitBoundary,
    *,
    context: str = "",
) -> None:
    """
    If fit_timestamps is provided, verify none are in the validation window.
    Calling this with the timestamps that were actually passed to .fit() proves
    the model was not trained on validation data.
    """
    if fit_timestamps is None:
        return
    ctx = f" [{context}]" if context else ""
    val_rows = (fit_timestamps >= boundary.validation_start) & (
        fit_timestamps < boundary.heldout_start
    )
    if val_rows.any():
        n = int(val_rows.sum())
        raise SplitViolation(
            f"{ctx}{n} timestamps passed to fit() fall in the validation window "
            f"[{boundary.validation_start.isoformat()}, "
            f"{boundary.heldout_start.isoformat()}). "
            "Validation data must not be used for fitting."
        )
    heldout_rows = fit_timestamps >= boundary.heldout_start
    if heldout_rows.any():
        n = int(heldout_rows.sum())
        raise SplitViolation(
            f"{ctx}{n} timestamps passed to fit() are at or after heldout_start "
            f"({boundary.heldout_start.isoformat()}). Heldout data must never be fitted."
        )


def slice_train(
    df: pd.DataFrame,
    timestamp_col: str,
    boundary: SplitBoundary,
) -> pd.DataFrame:
    """Return only rows in [train_start, validation_start) — safe for fitting."""
    ts = require_timestamp_column(df, timestamp_col)
    mask = (ts >= boundary.train_start) & (ts < boundary.validation_start)
    return df[mask].copy()


def slice_validation(
    df: pd.DataFrame,
    timestamp_col: str,
    boundary: SplitBoundary,
) -> pd.DataFrame:
    """Return only rows in [validation_start, heldout_start) — safe for transform/score only."""
    ts = require_timestamp_column(df, timestamp_col)
    mask = (ts >= boundary.validation_start) & (ts < boundary.heldout_start)
    return df[mask].copy()
