#!/usr/bin/env python3
"""Build the initial Project 3 weekly walk-forward pool plan."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "experiments/stage_a_screening/inputs/btcusdt_perp/4h/sota_low_cost/train.csv"
OUTPUT_DIR = ROOT / "experiments/weekly_walkforward_pool"
HELDOUT_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
SCHEMA_VERSION = "project3_weekly_pool_seed_plan_v2"

DEFAULT_FEATURES = [
    "return_1",
    "log_return_1",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
    "atr_14",
    "natr_14",
    "hist_vol_20",
    "roll_std_ret_20",
    "sota_intrabar_std",
    "sota_realized_vol",
    "sota_jump_var_bpv",
    "sota_hmm_state",
    "sota_hmm_prob_state_0",
    "sota_hmm_prob_state_1",
    "sota_hmm_prob_state_2",
    "sota_funding_rate",
    "sota_funding_30_event_mean",
    "sota_funding_30_event_std",
    "sota_funding_annualized",
]

OPTIONAL_FEATURE_PREFIXES = ("event_",)
BASE_NON_FEATURE_COLUMNS = {
    "DATE_TIME",
    "OPEN",
    "HIGH",
    "LOW",
    "CLOSE",
    "VOLUME",
}
LEAKAGE_FEATURE_NAME_PARTS = (
    "future",
    "forward",
    "lookahead",
    "leak",
    "target",
    "label",
    "outcome",
)


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def infer_input_metadata(
    input_path: Path,
    *,
    asset: str | None = None,
    timeframe: str | None = None,
    feature_preset: str | None = None,
) -> tuple[str, str, str]:
    """Infer asset/timeframe/preset from stage_a_screening input paths.

    Expected canonical path:
    experiments/stage_a_screening/inputs/<asset>/<timeframe>/<preset>/train.csv
    """
    parts = input_path.parts
    inferred_asset = asset
    inferred_timeframe = timeframe
    inferred_preset = feature_preset
    if "inputs" in parts:
        idx = parts.index("inputs")
        tail = parts[idx + 1 :]
        if len(tail) >= 4 and tail[-1] == "train.csv":
            inferred_asset = inferred_asset or tail[0]
            inferred_timeframe = inferred_timeframe or tail[1]
            inferred_preset = inferred_preset or tail[2]
    return (
        inferred_asset or "btcusdt_perp",
        inferred_timeframe or "4h",
        inferred_preset or "sota_low_cost",
    )


def subtract_years(dt: datetime, years: int) -> datetime:
    try:
        return dt.replace(year=dt.year - years)
    except ValueError:
        return dt.replace(month=2, day=28, year=dt.year - years)


def subtract_months(dt: datetime, months: int) -> datetime:
    month_index = dt.year * 12 + (dt.month - 1) - months
    year = month_index // 12
    month = month_index % 12 + 1
    day = dt.day
    while True:
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
            if day < 1:
                raise


def load_dates(path: Path) -> tuple[list[str], list[datetime]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        dates = [parse_dt(row["DATE_TIME"]) for row in reader if row.get("DATE_TIME")]
    dates.sort()
    return header, dates


def _looks_like_leakage_column(column: str) -> bool:
    lowered = column.lower()
    return any(part in lowered for part in LEAKAGE_FEATURE_NAME_PARTS)


def build_feature_columns(header: list[str], mode: str = "seed_default") -> list[str]:
    if mode == "all_available":
        features = [
            column
            for column in header
            if column not in BASE_NON_FEATURE_COLUMNS
            and not _looks_like_leakage_column(column)
        ]
        if not features:
            raise RuntimeError("all_available mode found no safe feature columns")
        return features
    if mode != "seed_default":
        raise ValueError("feature_column_mode must be seed_default or all_available")
    missing = [f for f in DEFAULT_FEATURES if f not in header]
    if missing:
        raise RuntimeError(f"input CSV is missing required seed features: {missing}")
    optional = [
        column
        for column in header
        if column not in DEFAULT_FEATURES
        and any(column.startswith(prefix) for prefix in OPTIONAL_FEATURE_PREFIXES)
    ]
    return [*DEFAULT_FEATURES, *optional]


def count_rows(dates: list[datetime], start: datetime, end: datetime) -> int:
    return sum(1 for dt in dates if start <= dt < end)


def candidate_anchors(dates: list[datetime], max_anchors: int, horizon_days: int = 14) -> list[datetime]:
    last = dates[-1]
    latest_anchor = min(last + timedelta(hours=4), HELDOUT_START) - timedelta(days=horizon_days)
    anchors = [
        dt
        for dt in dates
        if dt.weekday() == 0 and dt.hour == 0 and dt <= latest_anchor
    ]
    return list(reversed(anchors))[:max_anchors]


def monday_starts_for_year(year: int) -> list[datetime]:
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    first_monday = start + timedelta(days=(7 - start.weekday()) % 7)
    out: list[datetime] = []
    cur = first_monday
    while cur.year == year:
        out.append(cur)
        cur += timedelta(days=7)
    return out


def annual_block_windows(
    *,
    block: str,
    validation_year: int,
    test_year: int,
    validation_days: int,
    test_days: int,
) -> list[dict[str, datetime]]:
    if block == "validation_year":
        validation_starts = monday_starts_for_year(validation_year)
        return [
            {
                "label_start": validation_start,
                "train_end": validation_start,
                "validation_start": validation_start,
                "validation_end": validation_start + timedelta(days=validation_days),
                "test_start": validation_start + timedelta(days=validation_days),
                "test_end": validation_start + timedelta(days=validation_days + test_days),
            }
            for validation_start in validation_starts
        ]
    if block == "test_year":
        test_starts = monday_starts_for_year(test_year)
        return [
            {
                "label_start": test_start,
                "train_end": test_start - timedelta(days=validation_days),
                "validation_start": test_start - timedelta(days=validation_days),
                "validation_end": test_start,
                "test_start": test_start,
                "test_end": test_start + timedelta(days=test_days),
            }
            for test_start in test_starts
        ]
    raise ValueError(f"unsupported annual evaluation block: {block}")


def build_full_year_plan(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input_data_file).resolve()
    asset, timeframe, feature_preset = infer_input_metadata(
        input_path,
        asset=getattr(args, "asset", None),
        timeframe=getattr(args, "timeframe", None),
        feature_preset=getattr(args, "feature_preset", None),
    )
    validation_year = int(args.annual_validation_year)
    test_year = int(args.annual_test_year)
    annual_min_weeks = int(args.annual_min_weeks)
    execution_profile = (getattr(args, "execution_profile", None) or "").strip()
    execution_slug = execution_profile.lower().replace("-", "_").replace(" ", "_")
    execution_suffix = f"_exec_{execution_slug}" if execution_slug else ""
    contract_prefix = f"{asset}_{timeframe}_{feature_preset}{execution_suffix}_sac"
    header, dates = load_dates(input_path)
    feature_column_mode = getattr(args, "feature_column_mode", "seed_default")
    feature_columns = build_feature_columns(header, feature_column_mode)
    train_years = [int(x) for x in str(args.train_years).split(",") if x.strip()]
    policies = [x.strip() for x in str(args.policies).split(",") if x.strip()]
    fine_tune_months = [int(x) for x in str(args.fine_tune_months).split(",") if x.strip()]
    validation_days = int(args.validation_days)
    test_days = int(args.test_days)
    early_stop_train_tail_days = int(args.early_stop_train_tail_days)
    if min(validation_days, test_days, early_stop_train_tail_days, annual_min_weeks) <= 0:
        raise ValueError("annual/full-year windows and metric days must be positive")
    metric_suffix = (
        ""
        if (early_stop_train_tail_days, validation_days, test_days) == (7, 7, 7)
        else f"_etd{early_stop_train_tail_days}_vd{validation_days}_td{test_days}"
    )
    allowed_policies = {
        "scratch",
        "warm_start_chain",
        "scratch_recent_window",
        "fine_tune_recent_window",
    }
    bad_policies = sorted(set(policies) - allowed_policies)
    if bad_policies:
        raise ValueError(f"unsupported policies: {bad_policies}; allowed={sorted(allowed_policies)}")

    jobs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    data_hash = sha256_file(input_path)
    first = dates[0]
    last = dates[-1]
    block_names = ["validation_year", "test_year"]

    for block in block_names:
        windows = annual_block_windows(
            block=block,
            validation_year=validation_year,
            test_year=test_year,
            validation_days=validation_days,
            test_days=test_days,
        )
        for years in train_years:
            for policy in policies:
                recent_windows = (
                    fine_tune_months
                    if policy in {"scratch_recent_window", "fine_tune_recent_window"}
                    else [None]
                )
                for recent_months in recent_windows:
                    subjobs = []
                    chain_windows = (
                        windows
                        if policy in {"warm_start_chain", "fine_tune_recent_window"}
                        else list(reversed(windows))
                    )
                    previous_subjob_id: str | None = None
                    for ordinal, window in enumerate(chain_windows):
                        label_start = window["label_start"]
                        train_end = window["train_end"]
                        if policy in {"scratch_recent_window", "fine_tune_recent_window"}:
                            assert recent_months is not None
                            train_start = subtract_months(train_end, recent_months)
                        else:
                            train_start = subtract_years(train_end, years)
                        validation_start = window["validation_start"]
                        validation_end = window["validation_end"]
                        test_start = window["test_start"]
                        test_end = window["test_end"]
                        train_rows = count_rows(dates, train_start, train_end)
                        validation_rows = count_rows(dates, validation_start, validation_end)
                        test_rows = count_rows(dates, test_start, test_end)
                        skip_context = {
                            "evaluation_block": block,
                            "configured_validation_year": validation_year,
                            "configured_test_year": test_year,
                            "train_years": years,
                            "fine_tune_months": recent_months,
                            "policy": policy,
                            "weekly_anchor_id": label_start.strftime("%Y-%m-%d"),
                        }
                        if train_start < first:
                            skipped.append(
                                {
                                    **skip_context,
                                    "reason": "INSUFFICIENT_HISTORY",
                                    "train_start": fmt_dt(train_start),
                                    "first_row": fmt_dt(first),
                                }
                            )
                            continue
                        if test_end > HELDOUT_START:
                            skipped.append(
                                {
                                    **skip_context,
                                    "reason": "WOULD_REACH_STAGE_C",
                                    "test_end": fmt_dt(test_end),
                                }
                            )
                            continue
                        if train_rows < int(args.min_train_rows) or validation_rows < 10 or test_rows < 10:
                            skipped.append(
                                {
                                    **skip_context,
                                    "reason": "INSUFFICIENT_ROWS",
                                    "train_rows": train_rows,
                                    "validation_rows": validation_rows,
                                    "test_rows": test_rows,
                                }
                            )
                            continue
                        block_slug = "valyear" if block == "validation_year" else "testyear"
                        date_token = label_start.strftime("%Y%m%d")
                        base_token = (
                            f"{contract_prefix}_annual_fyv{validation_year}_fyt{test_year}"
                            f"_{block_slug}"
                        )
                        if policy == "warm_start_chain":
                            subjob_id = f"{base_token}_warm_ty{years}{metric_suffix}_{date_token}"
                        elif policy == "scratch_recent_window":
                            subjob_id = (
                                f"{base_token}_scratch_recent_m{recent_months}"
                                f"_ty{years}{metric_suffix}_{date_token}"
                            )
                        elif policy == "fine_tune_recent_window":
                            subjob_id = (
                                f"{base_token}_ft_m{recent_months}"
                                f"_ty{years}{metric_suffix}_{date_token}"
                            )
                        else:
                            subjob_id = f"{base_token}_scratch_ty{years}{metric_suffix}_{date_token}"
                        if policy == "scratch":
                            priority = 10_000 + (0 if block == "validation_year" else 50_000) + years * 100 + ordinal
                        elif policy == "warm_start_chain":
                            priority = 10_000 + (0 if block == "validation_year" else 50_000) + years * 100 + 50 + ordinal
                        elif policy == "scratch_recent_window":
                            priority = 10_000 + (0 if block == "validation_year" else 50_000) + 1000 + int(recent_months or 0) * 100 + ordinal
                        else:
                            priority = 10_000 + (0 if block == "validation_year" else 50_000) + 2000 + int(recent_months or 0) * 100 + ordinal
                        subjob = {
                            "subjob_id": subjob_id,
                            "weekly_anchor_id": label_start.strftime("%Y-%m-%d"),
                            "train_start": fmt_dt(train_start),
                            "train_end": fmt_dt(train_end),
                            "validation_start": fmt_dt(validation_start),
                            "validation_end": fmt_dt(validation_end),
                            "test_start": fmt_dt(test_start),
                            "test_end": fmt_dt(test_end),
                            "train_rows": train_rows,
                            "validation_rows": validation_rows,
                            "test_rows": test_rows,
                            "priority": priority,
                            "evaluation_block": block,
                        }
                        if policy == "warm_start_chain" and previous_subjob_id:
                            subjob["depends_on_subjob_id"] = previous_subjob_id
                            subjob["warm_start_parent_subjob_id"] = previous_subjob_id
                        if policy == "fine_tune_recent_window":
                            scratch_parent = f"{base_token}_scratch_ty{years}{metric_suffix}_{date_token}"
                            parent = previous_subjob_id or scratch_parent
                            subjob["depends_on_subjob_id"] = parent
                            subjob["warm_start_parent_subjob_id"] = parent
                        subjobs.append(subjob)
                        previous_subjob_id = subjob_id
                    if len(subjobs) < annual_min_weeks:
                        skipped.append(
                            {
                                "evaluation_block": block,
                                "configured_validation_year": validation_year,
                                "configured_test_year": test_year,
                                "train_years": years,
                                "fine_tune_months": recent_months,
                                "policy": policy,
                                "reason": "INSUFFICIENT_ANNUAL_COVERAGE",
                                "valid_weeks": len(subjobs),
                                "required_weeks": annual_min_weeks,
                            }
                        )
                        continue
                    if policy == "warm_start_chain":
                        training_policy = "warm_start_chain_n_years"
                    elif policy == "scratch_recent_window":
                        training_policy = "scratch_recent_window"
                    elif policy == "fine_tune_recent_window":
                        training_policy = "fine_tune_recent_window_chain"
                    else:
                        training_policy = "scratch_n_years"
                    block_slug = "valyear" if block == "validation_year" else "testyear"
                    if recent_months is None:
                        policy_suffix = f"{policy}_{years}y{metric_suffix}"
                    else:
                        policy_suffix = f"{policy}_m{recent_months}_base{years}y{metric_suffix}"
                    base_candidate_id = (
                        f"{asset}_{timeframe}_{feature_preset}{execution_suffix}_sac"
                        f"_annual_fyv{validation_year}_fyt{test_year}_{policy_suffix}"
                    )
                    job_id = f"{base_candidate_id}_{block_slug}"
                    jobs.append(
                        {
                            "job_id": job_id,
                            "candidate_id": base_candidate_id,
                            "asset": asset,
                            "timeframe": timeframe,
                            "input_data_file": str(input_path),
                            "input_data_sha256": data_hash,
                            "feature_preset": feature_preset,
                            "execution_profile": execution_profile or None,
                            "preprocessing_profile": "raw_plus_sota_indicators",
                            "feature_column_mode": feature_column_mode,
                            "feature_columns": list(feature_columns),
                            "model_family": "sac",
                            "agent_plugin": "project3_sac_actor_critic_agent",
                            "env_plugin": "gym_fx_env",
                            "pipeline_plugin": "rl_pipeline_with_validation",
                            "training_policy": training_policy,
                            "train_years": years,
                            "fine_tune_months": recent_months,
                            "validation_days": validation_days,
                            "test_days": test_days,
                            "evaluation_protocol": "full_year_validation_test_v1",
                            "evaluation_block": block,
                            "configured_validation_year": validation_year,
                            "configured_test_year": test_year,
                            "annual_eval_min_weeks": annual_min_weeks,
                            "experiment_phase": "full_year_validation_test_phase_v1",
                            "experiment_rationale": (
                                "Full annual protocol: aggregate at least "
                                f"{annual_min_weeks} weekly retrained evaluations "
                                "for validation-year selection and test-year reporting. "
                                "Weekly test remains report-only inside each subjob."
                            ),
                            "hyperparameters": {
                                "learning_rate": 0.0001,
                                "batch_size": 256,
                                "buffer_size": 200000,
                                "learning_starts": 1000,
                                "gamma": 0.99,
                                "tau": 0.005,
                                "ent_coef": "auto",
                                "train_freq": 1,
                                "gradient_steps": 1,
                                "use_sde": False,
                                "window_size": 32,
                                "epoch_timesteps": 2000,
                                "max_epochs": 500,
                                "l1_patience": 20,
                                "l1_min_delta": 0.0001,
                                "early_stop_train_tail_days": early_stop_train_tail_days,
                                "early_stop_min_trades": 1,
                                "early_stop_no_trade_penalty": 1000000.0,
                                "total_timesteps": 1000000,
                                "selection_metric": "risk_adjusted_return",
                            },
                            "subjobs": subjobs,
                        }
                    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage_c_access": "DENIED",
        "training_launched": False,
        "heldout_start": fmt_dt(HELDOUT_START),
        "evaluation_protocol": "full_year_validation_test_v1",
        "configured_validation_year": validation_year,
        "configured_test_year": test_year,
        "annual_eval_min_weeks": annual_min_weeks,
        "metric_windows": {
            "early_stop_train_tail_days": early_stop_train_tail_days,
            "validation_days": validation_days,
            "test_days": test_days,
        },
        "execution_profile": execution_profile or None,
        "feature_column_mode": feature_column_mode,
        "source": {
            "input_data_file": str(input_path),
            "input_data_sha256": data_hash,
            "first_row": fmt_dt(first),
            "last_row": fmt_dt(last),
            "row_count": len(dates),
        },
        "jobs": jobs,
        "skipped": skipped,
    }


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    annual_validation_year = getattr(args, "annual_validation_year", None)
    annual_test_year = getattr(args, "annual_test_year", None)
    if annual_validation_year or annual_test_year:
        if not (annual_validation_year and annual_test_year):
            raise ValueError("--annual-validation-year and --annual-test-year must be provided together")
        return build_full_year_plan(args)
    input_path = Path(args.input_data_file).resolve()
    asset, timeframe, feature_preset = infer_input_metadata(
        input_path,
        asset=getattr(args, "asset", None),
        timeframe=getattr(args, "timeframe", None),
        feature_preset=getattr(args, "feature_preset", None),
    )
    execution_profile = (getattr(args, "execution_profile", None) or "").strip()
    execution_slug = execution_profile.lower().replace("-", "_").replace(" ", "_")
    execution_suffix = f"_exec_{execution_slug}" if execution_slug else ""
    contract_prefix = f"{asset}_{timeframe}_{feature_preset}{execution_suffix}_sac"
    header, dates = load_dates(input_path)
    feature_column_mode = getattr(args, "feature_column_mode", "seed_default")
    feature_columns = build_feature_columns(header, feature_column_mode)
    train_years = [int(x) for x in str(args.train_years).split(",") if x.strip()]
    policies = [x.strip() for x in str(args.policies).split(",") if x.strip()]
    fine_tune_months = [int(x) for x in str(args.fine_tune_months).split(",") if x.strip()]
    validation_days = int(args.validation_days)
    test_days = int(args.test_days)
    early_stop_train_tail_days = int(args.early_stop_train_tail_days)
    if min(validation_days, test_days, early_stop_train_tail_days) <= 0:
        raise ValueError("validation_days, test_days, and early_stop_train_tail_days must be positive")
    metric_suffix = (
        ""
        if (early_stop_train_tail_days, validation_days, test_days) == (7, 7, 7)
        else f"_etd{early_stop_train_tail_days}_vd{validation_days}_td{test_days}"
    )
    allowed_policies = {
        "scratch",
        "warm_start_chain",
        "scratch_recent_window",
        "fine_tune_recent_window",
    }
    bad_policies = sorted(set(policies) - allowed_policies)
    if bad_policies:
        raise ValueError(f"unsupported policies: {bad_policies}; allowed={sorted(allowed_policies)}")
    anchors = candidate_anchors(dates, args.max_anchors, horizon_days=validation_days + test_days)
    jobs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    data_hash = sha256_file(input_path)
    first = dates[0]
    last = dates[-1]

    for years in train_years:
        for policy in policies:
            recent_windows = fine_tune_months if policy in {"scratch_recent_window", "fine_tune_recent_window"} else [None]
            for recent_months in recent_windows:
                subjobs = []
                chain_anchors = (
                    sorted(anchors)
                    if policy in {"warm_start_chain", "fine_tune_recent_window"}
                    else anchors
                )
                previous_subjob_id: str | None = None
                for ordinal, anchor in enumerate(chain_anchors):
                    if policy in {"scratch_recent_window", "fine_tune_recent_window"}:
                        assert recent_months is not None
                        train_start = subtract_months(anchor, recent_months)
                    else:
                        train_start = subtract_years(anchor, years)
                    train_end = anchor
                    validation_start = anchor
                    validation_end = validation_start + timedelta(days=validation_days)
                    test_start = validation_end
                    test_end = test_start + timedelta(days=test_days)
                    train_rows = count_rows(dates, train_start, train_end)
                    validation_rows = count_rows(dates, validation_start, validation_end)
                    test_rows = count_rows(dates, test_start, test_end)
                    if train_start < first:
                        skipped.append(
                            {
                                "train_years": years,
                                "fine_tune_months": recent_months,
                                "policy": policy,
                                "weekly_anchor_id": anchor.strftime("%Y-%m-%d"),
                                "reason": "INSUFFICIENT_HISTORY",
                                "train_start": fmt_dt(train_start),
                                "first_row": fmt_dt(first),
                            }
                        )
                        continue
                    if test_end > HELDOUT_START:
                        skipped.append(
                            {
                                "train_years": years,
                                "fine_tune_months": recent_months,
                                "policy": policy,
                                "weekly_anchor_id": anchor.strftime("%Y-%m-%d"),
                                "reason": "WOULD_REACH_STAGE_C",
                                "test_end": fmt_dt(test_end),
                            }
                        )
                        continue
                    if train_rows < int(args.min_train_rows) or validation_rows < 10 or test_rows < 10:
                        skipped.append(
                            {
                                "train_years": years,
                                "fine_tune_months": recent_months,
                                "policy": policy,
                                "weekly_anchor_id": anchor.strftime("%Y-%m-%d"),
                                "reason": "INSUFFICIENT_ROWS",
                                "train_rows": train_rows,
                                "validation_rows": validation_rows,
                                "test_rows": test_rows,
                            }
                        )
                        continue
                    if policy == "warm_start_chain":
                        subjob_id = f"{contract_prefix}_warm_ty{years}{metric_suffix}_{anchor.strftime('%Y%m%d')}"
                    elif policy == "scratch_recent_window":
                        subjob_id = (
                            f"{contract_prefix}_scratch_recent_m{recent_months}"
                            f"_ty{years}{metric_suffix}_{anchor.strftime('%Y%m%d')}"
                        )
                    elif policy == "fine_tune_recent_window":
                        subjob_id = (
                            f"{contract_prefix}_ft_m{recent_months}"
                            f"_ty{years}{metric_suffix}_{anchor.strftime('%Y%m%d')}"
                        )
                    else:
                        subjob_id = f"{contract_prefix}_scratch_ty{years}{metric_suffix}_{anchor.strftime('%Y%m%d')}"
                    if policy == "scratch":
                        priority = years * 100 + ordinal
                    elif policy == "warm_start_chain":
                        priority = years * 100 + 50 + ordinal
                    elif policy == "scratch_recent_window":
                        priority = 1000 + int(recent_months or 0) * 100 + ordinal
                    else:
                        priority = 2000 + int(recent_months or 0) * 100 + ordinal
                    subjob = {
                        "subjob_id": subjob_id,
                        "weekly_anchor_id": anchor.strftime("%Y-%m-%d"),
                        "train_start": fmt_dt(train_start),
                        "train_end": fmt_dt(train_end),
                        "validation_start": fmt_dt(validation_start),
                        "validation_end": fmt_dt(validation_end),
                        "test_start": fmt_dt(test_start),
                        "test_end": fmt_dt(test_end),
                        "train_rows": train_rows,
                        "validation_rows": validation_rows,
                        "test_rows": test_rows,
                        "priority": priority,
                    }
                    if policy == "warm_start_chain" and previous_subjob_id:
                        subjob["depends_on_subjob_id"] = previous_subjob_id
                        subjob["warm_start_parent_subjob_id"] = previous_subjob_id
                    if policy == "fine_tune_recent_window":
                        parent = (
                            previous_subjob_id
                            or f"{contract_prefix}_scratch_ty{years}{metric_suffix}_{anchor.strftime('%Y%m%d')}"
                        )
                        subjob["depends_on_subjob_id"] = parent
                        subjob["warm_start_parent_subjob_id"] = parent
                    subjobs.append(subjob)
                    previous_subjob_id = subjob_id
                if subjobs:
                    if policy == "warm_start_chain":
                        training_policy = "warm_start_chain_n_years"
                    elif policy == "scratch_recent_window":
                        training_policy = "scratch_recent_window"
                    elif policy == "fine_tune_recent_window":
                        training_policy = "fine_tune_recent_window_chain"
                    else:
                        training_policy = "scratch_n_years"
                    if recent_months is None:
                        job_id = (
                            f"{asset}_{timeframe}_{feature_preset}{execution_suffix}"
                            f"_sac_{policy}_{years}y{metric_suffix}"
                        )
                    else:
                        job_id = (
                            f"{asset}_{timeframe}_{feature_preset}{execution_suffix}_sac_{policy}"
                            f"_m{recent_months}_base{years}y{metric_suffix}"
                        )
                    jobs.append(
                        {
                            "job_id": job_id,
                            "candidate_id": job_id,
                            "asset": asset,
                            "timeframe": timeframe,
                            "input_data_file": str(input_path),
                            "input_data_sha256": data_hash,
                            "feature_preset": feature_preset,
                            "execution_profile": execution_profile or None,
                            "preprocessing_profile": "raw_plus_sota_indicators",
                            "feature_column_mode": feature_column_mode,
                            "feature_columns": list(feature_columns),
                            "model_family": "sac",
                            "agent_plugin": "project3_sac_actor_critic_agent",
                            "env_plugin": "gym_fx_env",
                            "pipeline_plugin": "rl_pipeline_with_validation",
                            "training_policy": training_policy,
                            "train_years": years,
                            "fine_tune_months": recent_months,
                            "validation_days": validation_days,
                            "test_days": test_days,
                            "hyperparameters": {
                                "learning_rate": 0.0001,
                                "batch_size": 256,
                                "buffer_size": 200000,
                                "learning_starts": 1000,
                                "gamma": 0.99,
                                "tau": 0.005,
                                "ent_coef": "auto",
                                "train_freq": 1,
                                "gradient_steps": 1,
                                "use_sde": False,
                                "window_size": 32,
                                "epoch_timesteps": 2000,
                                "max_epochs": 500,
                                "l1_patience": 20,
                                "l1_min_delta": 0.0001,
                                "early_stop_train_tail_days": early_stop_train_tail_days,
                                "early_stop_min_trades": 1,
                                "early_stop_no_trade_penalty": 1000000.0,
                                "total_timesteps": 1000000,
                            },
                            "subjobs": subjobs,
                        }
                    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage_c_access": "DENIED",
        "training_launched": False,
        "heldout_start": fmt_dt(HELDOUT_START),
        "metric_windows": {
            "early_stop_train_tail_days": early_stop_train_tail_days,
            "validation_days": validation_days,
            "test_days": test_days,
        },
        "execution_profile": execution_profile or None,
        "feature_column_mode": feature_column_mode,
        "source": {
            "input_data_file": str(input_path),
            "input_data_sha256": data_hash,
            "first_row": fmt_dt(first),
            "last_row": fmt_dt(last),
            "row_count": len(dates),
        },
        "jobs": jobs,
        "skipped": skipped,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Project 3 Weekly Pool Seed Plan",
        "",
        f"- Schema: `{plan['schema_version']}`",
        f"- Stage C access: `{plan['stage_c_access']}`",
        f"- Training launched: `{str(plan['training_launched']).lower()}`",
        f"- Input: `{plan['source']['input_data_file']}`",
        f"- Rows: `{plan['source']['row_count']}` from `{plan['source']['first_row']}` to `{plan['source']['last_row']}`",
        f"- Early-stop train-tail days: `{plan.get('metric_windows', {}).get('early_stop_train_tail_days', 7)}`",
        f"- Validation days: `{plan.get('metric_windows', {}).get('validation_days', 7)}`",
        f"- Test days: `{plan.get('metric_windows', {}).get('test_days', 7)}`",
        f"- Execution profile: `{plan.get('execution_profile') or ''}`",
        f"- Jobs: `{len(plan['jobs'])}`",
        f"- Subjobs: `{sum(len(j['subjobs']) for j in plan['jobs'])}`",
        f"- Skipped windows: `{len(plan['skipped'])}`",
        "",
        "## Enqueued Jobs",
        "",
        "| job | policy | train years | recent months | subjobs | features |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for job in plan["jobs"]:
        lines.append(
            f"| `{job['job_id']}` | `{job['training_policy']}` | {job['train_years']} | "
            f"{job.get('fine_tune_months') or ''} | "
            f"{len(job['subjobs'])} | {len(job['feature_columns'])} |"
        )
    lines.extend([
        "",
        "## Subjobs",
        "",
        "| subjob | depends on | train | validation | test | rows |",
        "|---|---|---|---|---|---|",
    ])
    for job in plan["jobs"]:
        for subjob in job["subjobs"]:
            lines.append(
                f"| `{subjob['subjob_id']}` | `{subjob.get('depends_on_subjob_id', '')}` | "
                f"`{subjob['train_start']} -> {subjob['train_end']}` | "
                f"`{subjob['validation_start']} -> {subjob['validation_end']}` | "
                f"`{subjob['test_start']} -> {subjob['test_end']}` | "
                f"{subjob['train_rows']}/{subjob['validation_rows']}/{subjob['test_rows']} |"
            )
    if plan["skipped"]:
        lines.extend(["", "## Skipped", "", "| train years | anchor | reason |", "|---:|---|---|"])
        for item in plan["skipped"][:80]:
            lines.append(
                f"| {item.get('train_years')} | `{item.get('weekly_anchor_id')}` | `{item.get('reason')}` |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input-data-file", default=str(DEFAULT_INPUT))
    ap.add_argument("--asset")
    ap.add_argument("--timeframe")
    ap.add_argument("--feature-preset")
    ap.add_argument("--execution-profile")
    ap.add_argument(
        "--feature-column-mode",
        choices=("seed_default", "all_available"),
        default="seed_default",
        help=(
            "seed_default keeps the historic Project 3 feature contract; "
            "all_available uses all non-OHLCV, non-leakage columns in the input CSV."
        ),
    )
    ap.add_argument("--train-years", default="1,4")
    ap.add_argument("--policies", default="scratch,warm_start_chain")
    ap.add_argument("--fine-tune-months", default="12,6,3,1")
    ap.add_argument("--max-anchors", type=int, default=2)
    ap.add_argument("--min-train-rows", type=int, default=500)
    ap.add_argument("--early-stop-train-tail-days", type=int, default=7)
    ap.add_argument("--validation-days", type=int, default=7)
    ap.add_argument("--test-days", type=int, default=7)
    ap.add_argument(
        "--annual-validation-year",
        type=int,
        help=(
            "Build the full-year validation block for this calendar year. "
            "Must be used with --annual-test-year."
        ),
    )
    ap.add_argument(
        "--annual-test-year",
        type=int,
        help=(
            "Build the full-year test block for this calendar year. "
            "Must be used with --annual-validation-year."
        ),
    )
    ap.add_argument(
        "--annual-min-weeks",
        type=int,
        default=48,
        help="Minimum distinct weekly windows required for each annual block.",
    )
    ap.add_argument("--output-dir", default=str(OUTPUT_DIR))
    ap.add_argument("--plan-stem", default="weekly_pool_seed_plan")
    args = ap.parse_args()

    plan = build_plan(args)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{args.plan_stem}.json"
    md_path = out_dir / f"{args.plan_stem}.md"
    json_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(plan), encoding="utf-8")
    print(json.dumps({"plan": str(json_path), "markdown": str(md_path), "jobs": len(plan["jobs"]), "subjobs": sum(len(j["subjobs"]) for j in plan["jobs"])}, indent=2))


if __name__ == "__main__":
    main()
