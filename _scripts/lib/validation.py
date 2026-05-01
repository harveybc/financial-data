from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ValidationResult:
    status: str
    checks: dict[str, Any]
    notes: list[str]


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table suffix: {path}")


def validate_non_empty_table(path: Path) -> ValidationResult:
    if not path.exists():
        return ValidationResult("failed", {"exists": False}, [f"missing: {path}"])
    df = read_table(path)
    return ValidationResult(
        "validated" if len(df) > 0 else "failed",
        {"exists": True, "rows": int(len(df)), "columns": list(df.columns)},
        [],
    )


def validate_ohlcv_shape(path: Path) -> ValidationResult:
    base = validate_non_empty_table(path)
    if base.status != "validated":
        return base
    cols = {str(col).lower() for col in base.checks["columns"]}
    required = {"open", "high", "low", "close"}
    missing = sorted(required - cols)
    status = "validated" if not missing else "failed"
    notes = [f"missing OHLC columns: {', '.join(missing)}"] if missing else []
    return ValidationResult(status, {**base.checks, "missing_ohlc_columns": missing}, notes)
