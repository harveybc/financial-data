#!/usr/bin/env python3
"""C95 (order 2026-09-12): the IDENTIFIED assembler of the ETH 4h
model-ready SUCCESSOR table.

The historical table `examples/data/project3/ethusdt_4h_tech_stat_full_
model_ready.csv` was assembled by code that is in no repository. This
module does not claim to be that code. It builds a NEW successor table
from exactly three row-aligned frames produced in one prospective rerun:

* `raw`          - the frame returned by the Stage 2.2 worker's
                   `read_asset` on the sealed raw OHLCV input;
* `technical`    - `compute_technical(raw)`;
* `statistical`  - `compute_statistical(raw)`.

Every operation is declared in `DECLARED_OPERATIONS`. There is no join,
no forward fill, no backfill, no tolerance join, no interpolation and no
sort in this module: the three frames must carry the identical timestamp
sequence (same length, same order) or assembly is refused. The only row
operation is a per-row filter that reads nothing but that row's own
values, so it cannot import information from other rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TECHNICAL_COLUMNS = (
    "return_1", "log_return_1", "return_5", "log_return_5", "return_10",
    "log_return_10", "return_20", "log_return_20", "return_60",
    "log_return_60", "sma_10", "ema_10", "close_sma_ratio_10", "sma_20",
    "ema_20", "close_sma_ratio_20", "sma_50", "ema_50", "close_sma_ratio_50",
    "sma_100", "ema_100", "close_sma_ratio_100", "sma_200", "ema_200",
    "close_sma_ratio_200", "macd", "macd_signal", "macd_hist", "rsi_7",
    "rsi_14", "rsi_21", "stoch_k", "stoch_d", "williams_r_14", "cci_14",
    "roc_10", "roc_20", "roc_60", "mom_10", "mom_20", "bb_upper",
    "bb_middle", "bb_lower", "bb_pct_b", "bb_width", "atr_14", "natr_14",
    "hist_vol_10", "hist_vol_20", "hist_vol_60", "ema_cross_10_50",
    "ema_cross_20_100", "trend_slope_50", "trend_strength_50", "obv",
    "obv_delta_20", "volume_sma_10", "volume_sma_20", "volume_ratio_20",
    "vwap_60", "mfi_14",
)
STATISTICAL_COLUMNS = (
    "log_return_1", "roll_mean_ret_20", "roll_std_ret_20",
    "roll_skew_ret_20", "roll_kurt_ret_20", "roll_mean_ret_60",
    "roll_std_ret_60", "roll_skew_ret_60", "roll_kurt_ret_60",
    "roll_mean_ret_252", "roll_std_ret_252", "roll_skew_ret_252",
    "roll_kurt_ret_252", "realized_var_12", "realized_var_48",
    "autocorr_lag1_100", "autocorr_lag5_100", "sqret_autocorr_lag1_100",
    "vol_regime_high", "vol_regime_low", "hurst_proxy_200",
    "zscore_close_100",
)
#: statistical columns whose name collides with a technical column are
#: renamed with the family stem, as the historical table names them.
COLLISION_PREFIX = "statistical__"
BAR_COLUMNS = ("typical_price", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME")
TIMESTAMP_COLUMN = "DATE_TIME"


def statistical_output_name(column: str) -> str:
    return COLLISION_PREFIX + column if column in TECHNICAL_COLUMNS \
        else column


OUTPUT_COLUMNS = ((TIMESTAMP_COLUMN,) + BAR_COLUMNS + TECHNICAL_COLUMNS
                  + tuple(statistical_output_name(c)
                          for c in STATISTICAL_COLUMNS))

#: output column -> (source frame, source column, producing symbol)
COLUMN_SOURCES = {
    **{c: ("bar", c, "derive_bar_columns") for c in BAR_COLUMNS},
    **{c: ("technical", c, "compute_technical") for c in TECHNICAL_COLUMNS},
    **{statistical_output_name(c): ("statistical", c, "compute_statistical")
       for c in STATISTICAL_COLUMNS},
}

DECLARED_OPERATIONS = (
    {"step": 1, "op": "UPSTREAM_READ",
     "performed_by": "stage22_trading_features_worker.read_asset",
     "detail": "parse timestamp as UTC; drop unparseable timestamps; sort "
               "by timestamp; drop duplicate timestamps keeping the last; "
               "coerce OHLCV to numeric. Performed by the producer, not "
               "here; recorded so the whole path is declared"},
    {"step": 2, "op": "EXACT_ROW_ALIGNMENT_CHECK",
     "detail": "raw, technical and statistical must hold the identical "
               "timestamp sequence (same length, same order, same values); "
               "otherwise assembly is REFUSED. No join of any kind is "
               "performed"},
    {"step": 3, "op": "DERIVE_BAR_COLUMNS", "symbol": "derive_bar_columns",
     "detail": "OPEN/HIGH/LOW/CLOSE/VOLUME are the same-row raw open/high/"
               "low/close/volume as float64; typical_price = (high + low + "
               "close) / 3 on the same row"},
    {"step": 4, "op": "COLUMN_SELECT_AND_RENAME",
     "detail": "technical columns kept by name; statistical columns kept "
               "by name except a name colliding with a technical column, "
               "which is prefixed 'statistical__'; producer column sets "
               "must equal the declared sets or assembly is REFUSED"},
    {"step": 5, "op": "ROW_FILTER_OWN_ROW_ONLY",
     "detail": "a row is kept iff every output value on that row is "
               "finite; the decision reads only that row"},
    {"step": 6, "op": "TIMESTAMP_RENAME",
     "detail": "timestamp -> DATE_TIME, kept as datetime64 UTC"},
)
FORWARD_FILL = "NONE"
BACKFILL = "NONE"
TOLERANCE_JOIN = "NONE"
JOIN = "NONE"
SORT = "NONE_IN_ASSEMBLER"
INTERPOLATION = "NONE"


class AssemblyRefused(ValueError):
    pass


def derive_bar_columns(raw):
    out = pd.DataFrame({"timestamp": raw["timestamp"]})
    out["OPEN"] = raw["open"].astype(float)
    out["HIGH"] = raw["high"].astype(float)
    out["LOW"] = raw["low"].astype(float)
    out["CLOSE"] = raw["close"].astype(float)
    out["VOLUME"] = raw["volume"].astype(float)
    out["typical_price"] = (raw["high"].astype(float)
                            + raw["low"].astype(float)
                            + raw["close"].astype(float)) / 3
    return out


def _same_timestamps(a: pd.Series, b: pd.Series) -> bool:
    return len(a) == len(b) and bool(
        (a.reset_index(drop=True) == b.reset_index(drop=True)).all())


def assemble(raw: pd.DataFrame, technical: pd.DataFrame,
             statistical: pd.DataFrame) -> pd.DataFrame:
    for name, frame, expected in (("technical", technical, TECHNICAL_COLUMNS),
                                  ("statistical", statistical,
                                   STATISTICAL_COLUMNS)):
        got = [c for c in frame.columns if c != "timestamp"]
        if set(got) != set(expected) or len(got) != len(expected):
            raise AssemblyRefused(
                f"{name} columns differ from the declared set: "
                f"missing={sorted(set(expected) - set(got))} "
                f"extra={sorted(set(got) - set(expected))}")
        if not _same_timestamps(raw["timestamp"], frame["timestamp"]):
            raise AssemblyRefused(f"{name} is not row-aligned with raw")
    ts = raw["timestamp"]
    if ts.isna().any() or not ts.is_monotonic_increasing or \
            ts.duplicated().any():
        raise AssemblyRefused("raw timestamps are not strictly increasing")
    bar = derive_bar_columns(raw).reset_index(drop=True)
    tech = technical.reset_index(drop=True)
    stat = statistical.reset_index(drop=True)
    cols = {TIMESTAMP_COLUMN: bar["timestamp"]}
    for c in BAR_COLUMNS:
        cols[c] = bar[c]
    for c in TECHNICAL_COLUMNS:
        cols[c] = tech[c]
    for c in STATISTICAL_COLUMNS:
        cols[statistical_output_name(c)] = stat[c]
    out = pd.DataFrame(cols, columns=list(OUTPUT_COLUMNS))
    values = out.drop(columns=[TIMESTAMP_COLUMN]).to_numpy(dtype="float64",
                                                           na_value=np.nan)
    keep = np.isfinite(values).all(axis=1)
    return out.loc[keep].reset_index(drop=True)


def to_csv_frame(successor: pd.DataFrame) -> pd.DataFrame:
    """The CSV rendering: DATE_TIME as naive 'YYYY-MM-DD HH:MM:SS' UTC."""
    out = successor.copy()
    out[TIMESTAMP_COLUMN] = out[TIMESTAMP_COLUMN].dt.strftime(
        "%Y-%m-%d %H:%M:%S")
    return out
