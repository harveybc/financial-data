#!/usr/bin/env python3
"""Summarize the Project 3 Stage 3X SAC smoke run.

This worker consumes the agent-multi direct-dispatch state and per-run
results/evidence files. It does not launch training and it refuses any Stage C
evidence.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import statistics
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
AGENT_MULTI_ROOT = ROOT.parent / "agent-multi"
STATE_FILE = (
    AGENT_MULTI_ROOT
    / "experiments"
    / "stage3x_sac_smoke_plan"
    / "stage3x_sac_smoke_dispatch_state.json"
)
OUT_ROOT = ROOT / "experiments" / "stage3x_sac_smoke_results"
OUT_JSON = OUT_ROOT / "stage3x_sac_smoke_result_synthesis.json"
OUT_MD = OUT_ROOT / "stage3x_sac_smoke_result_synthesis.md"
OUT_CSV = OUT_ROOT / "stage3x_sac_smoke_result_rows.csv"
SELECTED_CONTRACTS = ROOT / "experiments" / "stage3x_target_relation_screen" / "selected_feature_contracts.json"
SCHEMA_VERSION = "project3_stage3x_sac_smoke_result_synthesis_v2_finra_oanda"
HELDOUT_START = "2025-01-01"
FORCE_CLOSE_FIELDS = {
    "bars_to_force_close",
    "hours_to_force_close",
    "is_force_close_zone",
    "is_monday_entry_window",
}
DEFAULT_COMMISSION = 0.0002
DEFAULT_SLIPPAGE = 0.0
COST_TO_GROSS_EDGE_WARN_ABOVE = 0.75
MIN_MICRO_NSGA_DONE_SEEDS = 2
TARGET_LEAK_NAMES = {"target", "label", "y"}
TARGET_LEAK_PREFIXES = ("target_", "label_", "y_", "future_", "next_", "fwd_return_")

# --- Broker / regulatory policy layer (PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO) ---
BROKER_OANDA_FX = "oanda_us_fx"
BROKER_OANDA_SPOT_CRYPTO = "oanda_us_spot_crypto"
BROKER_CRYPTO_SPOT = "crypto_exchange_spot"
BROKER_CRYPTO_PERP = "crypto_exchange_perp"
BROKER_UNCONFIRMED = "spot_crypto_unconfirmed"

FX_ASSET_TOKENS = frozenset({
    "audusd", "eurusd", "gbpusd", "usdjpy", "usdcad", "usdchf", "nzdusd",
    "eurgbp", "eurjpy", "audjpy", "gbpjpy", "eurchf", "euraud", "gbpaud",
    "audcad", "audnzd", "cadjpy", "nzdjpy", "xauusd",
})

# trades/week bands from the FINRA/OANDA memo section 5.2.
# ``hard_max`` is fail-closed; exceeding it emits TRADE_FREQUENCY_HARD_MAX_EXCEEDED.
# Above ``warning_above`` emits TRADE_FREQUENCY_WARNING_BAND_EXCEEDED.
TRADE_FREQUENCY_POLICY: dict[tuple[str, str], dict[str, float]] = {
    (BROKER_OANDA_FX, "4h"): {"target_min": 3, "target_max": 3, "warning_above": 6, "hard_max": 12},
    (BROKER_OANDA_FX, "1h"): {"target_min": 6, "target_max": 6, "warning_above": 12, "hard_max": 24},
    (BROKER_OANDA_SPOT_CRYPTO, "4h"): {"target_min": 1, "target_max": 3, "warning_above": 3, "hard_max": 12},
    (BROKER_OANDA_SPOT_CRYPTO, "1h"): {"target_min": 3, "target_max": 6, "warning_above": 12, "hard_max": 24},
    (BROKER_CRYPTO_SPOT, "4h"): {"target_min": 3, "target_max": 6, "warning_above": 12, "hard_max": 24},
    (BROKER_CRYPTO_SPOT, "1h"): {"target_min": 6, "target_max": 12, "warning_above": 24, "hard_max": 36},
    (BROKER_CRYPTO_PERP, "4h"): {"target_min": 3, "target_max": 6, "warning_above": 12, "hard_max": 24},
    (BROKER_CRYPTO_PERP, "1h"): {"target_min": 6, "target_max": 12, "warning_above": 24, "hard_max": 36},
    # An unconfirmed-venue spot crypto is policy-flagged as fail-closed, but we
    # still report a conservative band derived from the non-OANDA crypto rows so
    # the report carries a usable number alongside the blocker.
    (BROKER_UNCONFIRMED, "4h"): {"target_min": 3, "target_max": 6, "warning_above": 12, "hard_max": 24},
    (BROKER_UNCONFIRMED, "1h"): {"target_min": 6, "target_max": 12, "warning_above": 24, "hard_max": 36},
}

NEW_YORK_TZ = ZoneInfo("America/New_York")
OANDA_FX_DAILY_BREAK_START = dt.time(16, 59)
OANDA_FX_DAILY_BREAK_END = dt.time(17, 5)
OANDA_FX_FRIDAY_FORCE_FLAT_TIME = dt.time(15, 45)
FRIDAY_WEEKDAY = 4  # Monday=0 .. Sunday=6


class SmokeSynthesisError(RuntimeError):
    pass


def configure_paths(
    *,
    state_file: Path | None = None,
    out_root: Path | None = None,
    selected_contracts: Path | None = None,
) -> None:
    global STATE_FILE, OUT_ROOT, OUT_JSON, OUT_MD, OUT_CSV, SELECTED_CONTRACTS
    if state_file is not None:
        STATE_FILE = state_file
    if out_root is not None:
        OUT_ROOT = out_root
        OUT_JSON = OUT_ROOT / "stage3x_sac_smoke_result_synthesis.json"
        OUT_MD = OUT_ROOT / "stage3x_sac_smoke_result_synthesis.md"
        OUT_CSV = OUT_ROOT / "stage3x_sac_smoke_result_rows.csv"
    if selected_contracts is not None:
        SELECTED_CONTRACTS = selected_contracts


def is_target_leak_feature(name: Any) -> bool:
    feature = str(name or "").strip().lower()
    return feature in TARGET_LEAK_NAMES or any(feature.startswith(prefix) for prefix in TARGET_LEAK_PREFIXES)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def split_metric(results: dict[str, Any], split: str, key: str) -> Any:
    return ((results.get("splits") or {}).get(split) or {}).get(key)


def _contract_asset_token(contract_id: str) -> str:
    """Return the leading asset token of a contract id, e.g. ``audusd`` or ``btcusdt_perp``."""
    return contract_id.split("__", 1)[0].lower()


def _contract_timeframe(contract_id: str) -> str:
    """Return the timeframe token (e.g. ``1h`` / ``4h``) from a contract id."""
    parts = contract_id.split("__")
    return parts[1].lower() if len(parts) >= 2 else ""


def _broker_blockers_for_profile(profile: str) -> list[str]:
    if profile in {BROKER_UNCONFIRMED, "broker_profile_unconfirmed", ""}:
        return ["BROKER_PROFILE_MISSING_OR_UNCONFIRMED"]
    return []


def selected_contract_metadata() -> dict[str, dict[str, Any]]:
    if not SELECTED_CONTRACTS.exists():
        return {}
    try:
        doc = load_json(SELECTED_CONTRACTS)
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in doc.get("contracts") or []:
        cid = str(row.get("contract_id") or "")
        if cid:
            out[cid] = row
    return out


def infer_broker_profile(contract_id: str, contract_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Infer ``(broker_profile, regulatory_profile, asset, timeframe)`` from a contract id.

    Rules from PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO:

    - ``*_perp`` asset → ``crypto_exchange_perp``;
    - FX cross in :data:`FX_ASSET_TOKENS` → ``oanda_us_fx``;
    - spot crypto without an explicit venue → ``spot_crypto_unconfirmed`` and a
      :data:`BROKER_PROFILE_MISSING_OR_UNCONFIRMED` hard blocker.
    """
    asset = _contract_asset_token(contract_id)
    timeframe = _contract_timeframe(contract_id)
    contract_metadata = contract_metadata or {}
    if contract_metadata.get("broker_profile"):
        profile = str(contract_metadata.get("broker_profile") or "")
        return {
            "broker_profile": profile,
            "regulatory_profile": str(contract_metadata.get("regulatory_profile") or "none_or_external"),
            "asset_token": str(contract_metadata.get("asset") or asset).lower(),
            "timeframe": str(contract_metadata.get("timeframe") or timeframe).lower(),
            "broker_profile_blockers": _broker_blockers_for_profile(profile),
            "broker_profile_warnings": [],
        }
    blockers: list[str] = []
    warnings: list[str] = []
    if asset.endswith("_perp"):
        profile = BROKER_CRYPTO_PERP
        regulatory = "none_or_external"
    elif asset in FX_ASSET_TOKENS:
        profile = BROKER_OANDA_FX
        regulatory = "cftc_nfa_retail_forex"
    else:
        # Spot crypto: cannot distinguish OANDA vs. exchange without venue evidence.
        profile = BROKER_UNCONFIRMED
        regulatory = "none_or_external"
        blockers.append("BROKER_PROFILE_MISSING_OR_UNCONFIRMED")
    return {
        "broker_profile": profile,
        "regulatory_profile": regulatory,
        "asset_token": asset,
        "timeframe": timeframe,
        "broker_profile_blockers": blockers,
        "broker_profile_warnings": warnings,
    }


def lookup_trade_frequency_policy(broker_profile: str, timeframe: str) -> dict[str, Any]:
    """Return the trade-frequency band for ``(broker_profile, timeframe)`` or an empty record."""
    policy = TRADE_FREQUENCY_POLICY.get((broker_profile, timeframe.lower()))
    if not policy:
        return {
            "broker_profile": broker_profile,
            "timeframe": timeframe,
            "target_min": None,
            "target_max": None,
            "warning_above": None,
            "hard_max": None,
            "policy_known": False,
        }
    return {
        "broker_profile": broker_profile,
        "timeframe": timeframe,
        "target_min": policy["target_min"],
        "target_max": policy["target_max"],
        "warning_above": policy["warning_above"],
        "hard_max": policy["hard_max"],
        "policy_known": True,
    }


def _parse_split_timestamp(text: Any) -> dt.datetime | None:
    if text in (None, "", False):
        return None
    candidate = str(text).strip().replace("T", " ")
    if candidate.endswith("Z"):
        candidate = candidate[:-1]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(candidate[: len(fmt)], fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    try:
        parsed = dt.datetime.fromisoformat(candidate)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def split_duration_weeks(first_ts: Any, last_ts: Any) -> float:
    """Return the inclusive split duration in weeks from first/last timestamps.

    A small floor (1/7 of a week) is applied so a single-day fixture does not
    explode trades/week into infinity.
    """
    first = _parse_split_timestamp(first_ts)
    last = _parse_split_timestamp(last_ts)
    if first is None or last is None or last <= first:
        return 0.0
    seconds = (last - first).total_seconds()
    weeks = seconds / (7 * 24 * 3600)
    return max(weeks, 1.0 / 7.0)


def trades_per_week(trades: float, weeks: float) -> float | None:
    if weeks <= 0 or trades is None:
        return None
    return float(trades) / weeks


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def cost_edge_estimate(
    *,
    net_return: Any,
    trades: Any,
    commission: Any,
    slippage: Any,
) -> dict[str, float | None]:
    """Return a conservative per-contract gross-edge-vs-cost estimate.

    The backtest outputs net returns after costs, but the synthesis layer needs
    a cheap fail-fast estimate of whether costs dominate the gross edge. For
    one closed trade, approximate a round-trip cost as ``2 *
    (commission + slippage)`` of notional. This is not a broker statement; it is
    a research guardrail that stops "positive before costs, useless after
    costs" contracts from silently advancing.
    """
    net = _safe_float(net_return)
    n_trades = _safe_float(trades)
    commission_f = _safe_float(commission)
    slippage_f = _safe_float(slippage)
    if net is None or n_trades is None or commission_f is None or slippage_f is None:
        return {
            "cost_drag_estimate": None,
            "gross_edge_estimate": None,
            "cost_to_gross_edge_ratio": None,
        }
    cost_drag = max(0.0, n_trades) * 2.0 * max(0.0, commission_f + slippage_f)
    gross_edge = net + cost_drag
    ratio = cost_drag / abs(gross_edge) if abs(gross_edge) > 1e-12 else None
    return {
        "cost_drag_estimate": cost_drag,
        "gross_edge_estimate": gross_edge,
        "cost_to_gross_edge_ratio": ratio,
    }


def _bar_is_friday_force_flat(ts_utc: dt.datetime) -> bool:
    """Return True if ``ts_utc`` falls at or after Friday 15:45 America/New_York."""
    local = ts_utc.astimezone(NEW_YORK_TZ)
    if local.weekday() != FRIDAY_WEEKDAY:
        return False
    return (local.hour, local.minute) >= (
        OANDA_FX_FRIDAY_FORCE_FLAT_TIME.hour,
        OANDA_FX_FRIDAY_FORCE_FLAT_TIME.minute,
    )


def _bar_in_daily_break(ts_utc: dt.datetime) -> bool:
    """Return True if ``ts_utc`` falls inside the OANDA daily 16:59–17:05 NY break."""
    local = ts_utc.astimezone(NEW_YORK_TZ)
    # Sunday is the weekly open day; restrict break to weekdays Mon-Fri.
    if local.weekday() >= 5:
        return False
    local_time = local.time()
    return OANDA_FX_DAILY_BREAK_START <= local_time < OANDA_FX_DAILY_BREAK_END


def audit_oanda_fx_calendar_violations(trace_path: Path) -> dict[str, int]:
    """Scan an OANDA FX trace CSV for Friday-force-flat and daily-break violations.

    A Friday-force-flat violation is a row at/after Friday 15:45 NY with a
    nonzero position. A daily-break trade attempt is a row inside the 16:59–17:05
    NY window where ``position`` differs from the prior row (i.e. an effective
    fill happened across the break).
    """
    result = {
        "friday_force_flat_violations": 0,
        "daily_break_trade_attempts": 0,
        "scanned_rows": 0,
    }
    if not trace_path.exists():
        return result
    prev_position: float | None = None
    with trace_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            ts = _parse_split_timestamp(row.get("timestamp"))
            if ts is None:
                continue
            try:
                position = float(row.get("position") or 0.0)
            except (TypeError, ValueError):
                position = 0.0
            result["scanned_rows"] += 1
            if _bar_is_friday_force_flat(ts) and abs(position) > 1e-12:
                result["friday_force_flat_violations"] += 1
            if (
                _bar_in_daily_break(ts)
                and prev_position is not None
                and abs(position - prev_position) > 1e-12
            ):
                result["daily_break_trade_attempts"] += 1
            prev_position = position
    return result


def validate_evidence(evidence: dict[str, Any], evidence_file: Path) -> None:
    if evidence.get("schema_version") != "project3_return_trace_evidence_v1":
        raise SmokeSynthesisError(f"Bad evidence schema in {evidence_file}")
    if evidence.get("trace_schema_version") != "stage_b_return_trace_v1":
        raise SmokeSynthesisError(f"Bad trace schema in {evidence_file}")
    if evidence.get("heldout_boundary") != HELDOUT_START:
        raise SmokeSynthesisError(f"Bad heldout boundary in {evidence_file}")
    if evidence.get("stage_c_authorized") is True or evidence.get("contains_heldout_rows") is True:
        raise SmokeSynthesisError(f"Stage C contamination/authorization in {evidence_file}")
    for trace in evidence.get("traces") or []:
        if trace.get("stage_c_authorized") is True or trace.get("contains_heldout_rows") is True:
            raise SmokeSynthesisError(f"Stage C trace contamination/authorization in {evidence_file}")


def _trace_lookup_by_split(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for trace in evidence.get("traces") or []:
        split = str(trace.get("split", "")).lower()
        if split:
            out[split] = trace
    return out


def row_from_task(task: dict[str, Any], contract_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    broker = infer_broker_profile(
        task["contract_id"],
        contract_metadata,
    )
    row: dict[str, Any] = {
        "task_id": task["id"],
        "contract_id": task["contract_id"],
        "seed": task["seed"],
        "cost_scenario": task.get("cost_scenario", "base"),
        "host": task.get("assigned_host"),
        "status": task["status"],
        "notes": task.get("notes", ""),
        "broker_profile": broker["broker_profile"],
        "regulatory_profile": broker["regulatory_profile"],
        "asset_token": broker["asset_token"],
        "timeframe": broker["timeframe"],
        "feature_list_hash": "",
        "feature_column_count": "",
        "observation_state_hash": "",
        "expected_market_state_profile_id": "",
        "market_state_profile_id": "",
        "market_state_profile_hash": "",
        "market_state_profile_family": "",
        "market_state_profile_name": "",
        "market_state_selected_columns": "",
        "force_close_obs_present": False,
        "validation_return": "",
        "validation_sharpe": "",
        "validation_trades": "",
        "validation_weeks": "",
        "validation_trades_per_week": "",
        "test_return": "",
        "test_sharpe": "",
        "test_trades": "",
        "test_weeks": "",
        "test_trades_per_week": "",
        "commission": "",
        "slippage": "",
        "validation_cost_drag_estimate": "",
        "validation_gross_edge_estimate": "",
        "validation_cost_to_gross_edge_ratio": "",
        "test_cost_drag_estimate": "",
        "test_gross_edge_estimate": "",
        "test_cost_to_gross_edge_ratio": "",
        "test_no_trades": "",
        "friday_force_flat_violations": "",
        "daily_break_trade_attempts": "",
    }
    if task["status"] != "done":
        return row
    config = load_json(Path(task.get("config_file") or "")) if task.get("config_file") else {}
    row["expected_market_state_profile_id"] = config.get("market_state_profile_id") or ""
    results_file = Path(task["run_dir"]) / "results.json"
    if not results_file.exists():
        row["status"] = "missing_results"
        row["notes"] = (row["notes"] + "; " if row["notes"] else "") + "missing results.json"
        return row
    results = load_json(results_file)
    evidence_file = Path(results.get("return_trace_evidence_file") or task["expected_evidence_file"])
    if not evidence_file.exists():
        row["status"] = "missing_evidence"
        row["notes"] = (row["notes"] + "; " if row["notes"] else "") + "missing evidence.json"
        return row
    evidence = load_json(evidence_file)
    validate_evidence(evidence, evidence_file)
    obs_fields = set(evidence.get("observation_state_fields") or [])
    traces_by_split = _trace_lookup_by_split(evidence)
    val_trace = traces_by_split.get("validation") or {}
    test_trace = traces_by_split.get("test") or {}
    val_weeks = split_duration_weeks(val_trace.get("first_timestamp"), val_trace.get("last_timestamp"))
    test_weeks = split_duration_weeks(test_trace.get("first_timestamp"), test_trace.get("last_timestamp"))
    val_trades = split_metric(results, "validation", "trades_total")
    test_trades = split_metric(results, "test", "trades_total")
    commission = config.get("commission", DEFAULT_COMMISSION)
    slippage = config.get("slippage", DEFAULT_SLIPPAGE)
    val_cost_edge = cost_edge_estimate(
        net_return=split_metric(results, "validation", "total_return"),
        trades=val_trades,
        commission=commission,
        slippage=slippage,
    )
    test_cost_edge = cost_edge_estimate(
        net_return=split_metric(results, "test", "total_return"),
        trades=test_trades,
        commission=commission,
        slippage=slippage,
    )
    row.update(
        {
            "feature_list_hash": evidence.get("feature_list_hash") or "",
            "feature_column_count": evidence.get("feature_column_count") or "",
            "observation_state_hash": evidence.get("observation_state_hash") or "",
            "market_state_profile_id": evidence.get("market_state_profile_id") or "",
            "market_state_profile_hash": evidence.get("market_state_profile_hash") or "",
            "market_state_profile_family": evidence.get("market_state_profile_family") or "",
            "market_state_profile_name": evidence.get("market_state_profile_name") or "",
            "market_state_selected_columns": evidence.get("market_state_selected_columns") or "",
            "force_close_obs_present": FORCE_CLOSE_FIELDS.issubset(obs_fields),
            "validation_return": split_metric(results, "validation", "total_return"),
            "validation_sharpe": split_metric(results, "validation", "sharpe_ratio"),
            "validation_trades": val_trades,
            "validation_weeks": val_weeks,
            "validation_trades_per_week": trades_per_week(val_trades, val_weeks) if val_trades is not None else "",
            "test_return": split_metric(results, "test", "total_return"),
            "test_sharpe": split_metric(results, "test", "sharpe_ratio"),
            "test_trades": test_trades,
            "test_weeks": test_weeks,
            "test_trades_per_week": trades_per_week(test_trades, test_weeks) if test_trades is not None else "",
            "commission": commission,
            "slippage": slippage,
            "validation_cost_drag_estimate": val_cost_edge["cost_drag_estimate"],
            "validation_gross_edge_estimate": val_cost_edge["gross_edge_estimate"],
            "validation_cost_to_gross_edge_ratio": val_cost_edge["cost_to_gross_edge_ratio"],
            "test_cost_drag_estimate": test_cost_edge["cost_drag_estimate"],
            "test_gross_edge_estimate": test_cost_edge["gross_edge_estimate"],
            "test_cost_to_gross_edge_ratio": test_cost_edge["cost_to_gross_edge_ratio"],
        }
    )
    row["test_no_trades"] = row["test_trades"] == 0
    # OANDA FX calendar audit: scan validation+test trace bars for Friday
    # force-flat violations and trades attempted during the daily 16:59–17:05
    # NY break. Non-FX rows skip the scan to keep the audit cheap.
    if broker["broker_profile"] == BROKER_OANDA_FX:
        violations = {"friday_force_flat_violations": 0, "daily_break_trade_attempts": 0}
        for trace in (val_trace, test_trace):
            trace_file = trace.get("trace_file") or trace.get("path") or ""
            if not trace_file:
                continue
            counts = audit_oanda_fx_calendar_violations(Path(str(trace_file)))
            violations["friday_force_flat_violations"] += counts["friday_force_flat_violations"]
            violations["daily_break_trade_attempts"] += counts["daily_break_trade_attempts"]
        row["friday_force_flat_violations"] = violations["friday_force_flat_violations"]
        row["daily_break_trade_attempts"] = violations["daily_break_trade_attempts"]
    return row


def _floats(rows: list[dict[str, Any]], key: str) -> list[float]:
    out: list[float] = []
    for row in rows:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            continue
    return out


def stage3x_micro_nsga_entry_blockers(
    *,
    done_rows: list[dict[str, Any]],
    force_close_all: bool,
    broker: dict[str, Any],
    policy_band: dict[str, Any],
    max_val_tpw: float | None,
    max_test_tpw: float | None,
    oanda_calendar: dict[str, int],
    contract_metadata: dict[str, Any] | None = None,
) -> list[str]:
    """Return fail-closed blockers for the existing micro-NSGA pass label."""
    contract_metadata = contract_metadata or {}
    blockers: list[str] = []
    selected_features = contract_metadata.get("selected_features")
    selected_features = [] if selected_features is None else list(selected_features)
    leak_features = [str(f) for f in selected_features if is_target_leak_feature(f)]
    hard_max = policy_band.get("hard_max")

    if len(done_rows) < MIN_MICRO_NSGA_DONE_SEEDS:
        blockers.append("INSUFFICIENT_COMPLETED_SMOKE_SEEDS")
    if contract_metadata and not selected_features:
        blockers.append("MISSING_SELECTED_FEATURE_LIST")
    if leak_features:
        blockers.append("SELECTED_FEATURES_CONTAIN_TARGET_LEAK")
    if any(not r.get("feature_list_hash") for r in done_rows):
        blockers.append("MISSING_FEATURE_LIST_HASH")
    if any(not r.get("observation_state_hash") for r in done_rows):
        blockers.append("MISSING_OBSERVATION_STATE_HASH")
    if any(
        r.get("expected_market_state_profile_id")
        and (
            not r.get("market_state_profile_id")
            or not r.get("market_state_profile_hash")
            or not r.get("market_state_selected_columns")
        )
        for r in done_rows
    ):
        blockers.append("MISSING_MARKET_STATE_PROFILE_EVIDENCE")
    if done_rows and not force_close_all:
        blockers.append("MISSING_FORCE_CLOSE_OBSERVATION_FIELDS")
    if not done_rows or all(int(r.get("test_trades") or 0) <= 0 for r in done_rows):
        blockers.append("TEST_NO_TRADES")
    if broker["broker_profile_blockers"]:
        blockers.extend(broker["broker_profile_blockers"])
    if policy_band.get("policy_known") and hard_max is not None:
        if (
            (max_val_tpw is not None and max_val_tpw > hard_max)
            or (max_test_tpw is not None and max_test_tpw > hard_max)
        ):
            blockers.append("TRADE_FREQUENCY_HARD_MAX_EXCEEDED")
    else:
        blockers.append("TRADE_FREQUENCY_POLICY_UNKNOWN")
    if oanda_calendar.get("friday_force_flat_violations", 0) > 0:
        blockers.append("OANDA_FX_FRIDAY_FORCE_FLAT_VIOLATION")
    if oanda_calendar.get("daily_break_trade_attempts", 0) > 0:
        blockers.append("OANDA_FX_DAILY_BREAK_TRADE_ATTEMPT")
    return sorted(set(blockers))


def summarize_contract(
    contract_id: str,
    rows: list[dict[str, Any]],
    contract_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    done_rows = [r for r in rows if r["status"] == "done"]
    test_returns = [float(r["test_return"]) for r in done_rows if r["test_return"] != ""]
    val_returns = [float(r["validation_return"]) for r in done_rows if r["validation_return"] != ""]
    test_trades = [int(r["test_trades"]) for r in done_rows if r["test_trades"] != ""]
    force_close_all = bool(done_rows) and all(bool(r["force_close_obs_present"]) for r in done_rows)
    failed_rows = [r for r in rows if r["status"] != "done"]
    costs_done = sorted({str(r.get("cost_scenario") or "base") for r in done_rows})
    done_by_cost = {
        cost: sum(1 for r in done_rows if str(r.get("cost_scenario") or "base") == cost)
        for cost in costs_done
    }
    returns_by_cost = {
        cost: [
            float(r["test_return"])
            for r in done_rows
            if str(r.get("cost_scenario") or "base") == cost and r["test_return"] != ""
        ]
        for cost in costs_done
    }
    validation_returns_by_cost = {
        cost: [
            float(r["validation_return"])
            for r in done_rows
            if str(r.get("cost_scenario") or "base") == cost and r["validation_return"] != ""
        ]
        for cost in costs_done
    }
    median_test_return_by_cost = {
        cost: statistics.median(values)
        for cost, values in returns_by_cost.items()
        if values
    }
    median_validation_return_by_cost = {
        cost: statistics.median(values)
        for cost, values in validation_returns_by_cost.items()
        if values
    }
    warnings: list[str] = []
    economic_warnings: list[str] = []
    if failed_rows:
        economic_warnings.append("FAILED_OR_ABORTED_SEEDS")
    if done_rows and any(r["test_no_trades"] is True for r in done_rows):
        economic_warnings.append("TEST_NO_TRADES")
    if val_returns and statistics.median(val_returns) <= 0:
        economic_warnings.append("NON_POSITIVE_MEDIAN_VALIDATION_RETURN")
    if test_returns and statistics.median(test_returns) <= 0:
        economic_warnings.append("NON_POSITIVE_MEDIAN_TEST_RETURN")
    required_costs = {"base", "plus_50pct", "plus_100pct"}
    has_full_cost_coverage = set(costs_done) == required_costs
    if any(cost != "base" for cost in costs_done):
        if not has_full_cost_coverage:
            economic_warnings.append("INCOMPLETE_COST_SCENARIO_COVERAGE")
        if any(value <= 0 for value in median_test_return_by_cost.values()):
            economic_warnings.append("COST_FRAGILITY_NON_POSITIVE_MEDIAN_TEST_RETURN")
        if any(value <= 0 for value in median_validation_return_by_cost.values()):
            economic_warnings.append("COST_FRAGILITY_NON_POSITIVE_MEDIAN_VALIDATION_RETURN")

    # --- FINRA/OANDA trade-frequency + broker-profile policy layer ---
    broker = infer_broker_profile(contract_id, contract_metadata)
    policy_band = lookup_trade_frequency_policy(broker["broker_profile"], broker["timeframe"])
    val_tpw = _floats(done_rows, "validation_trades_per_week")
    test_tpw = _floats(done_rows, "test_trades_per_week")
    val_cost_ratios = _floats(done_rows, "validation_cost_to_gross_edge_ratio")
    test_cost_ratios = _floats(done_rows, "test_cost_to_gross_edge_ratio")
    median_val_tpw = statistics.median(val_tpw) if val_tpw else None
    median_test_tpw = statistics.median(test_tpw) if test_tpw else None
    max_val_tpw = max(val_tpw) if val_tpw else None
    max_test_tpw = max(test_tpw) if test_tpw else None
    median_val_cost_ratio = statistics.median(val_cost_ratios) if val_cost_ratios else None
    median_test_cost_ratio = statistics.median(test_cost_ratios) if test_cost_ratios else None
    hard_max = policy_band.get("hard_max")
    warning_above = policy_band.get("warning_above")
    if policy_band.get("policy_known") and hard_max is not None:
        if not (
            (max_val_tpw is not None and max_val_tpw > hard_max)
            or (max_test_tpw is not None and max_test_tpw > hard_max)
        ) and (
            warning_above is not None
            and (
                (median_val_tpw is not None and median_val_tpw > warning_above)
                or (median_test_tpw is not None and median_test_tpw > warning_above)
            )
        ):
            warnings.append("TRADE_FREQUENCY_WARNING_BAND_EXCEEDED")
    # OANDA FX-specific calendar gates: detected from the per-bar trace.
    if broker["broker_profile"] == BROKER_OANDA_FX:
        ff_total = sum(int(r["friday_force_flat_violations"] or 0) for r in done_rows if r["friday_force_flat_violations"] != "")
        db_total = sum(int(r["daily_break_trade_attempts"] or 0) for r in done_rows if r["daily_break_trade_attempts"] != "")
        oanda_calendar = {
            "friday_force_flat_violations": ff_total,
            "daily_break_trade_attempts": db_total,
        }
    else:
        oanda_calendar = {}
    # Warnings the spec calls out as informational rather than fail-closed.
    if broker["broker_profile"] == BROKER_OANDA_FX and not oanda_calendar:
        warnings.append("OANDA_POLICY_FIELDS_MISSING")
    elif broker["broker_profile"] == BROKER_UNCONFIRMED:
        # The hard blocker is already in place; mirror as a warning so reports
        # display the unfilled OANDA-specific fields.
        warnings.append("OANDA_POLICY_FIELDS_MISSING")
    if done_rows and (median_val_cost_ratio is None or median_test_cost_ratio is None):
        warnings.append("COST_TO_GROSS_EDGE_UNAVAILABLE")
    elif (
        (median_val_cost_ratio is not None and median_val_cost_ratio > COST_TO_GROSS_EDGE_WARN_ABOVE)
        or (median_test_cost_ratio is not None and median_test_cost_ratio > COST_TO_GROSS_EDGE_WARN_ABOVE)
    ):
        warnings.append("COST_TO_GROSS_EDGE_HIGH")
    if not policy_band.get("policy_known"):
        warnings.append("TRADE_FREQUENCY_POLICY_UNKNOWN_FOR_TIMEFRAME")
    for warning in economic_warnings:
        if warning not in warnings:
            warnings.append(warning)

    micro_nsga_blockers = stage3x_micro_nsga_entry_blockers(
        done_rows=done_rows,
        force_close_all=force_close_all,
        broker=broker,
        policy_band=policy_band,
        max_val_tpw=max_val_tpw,
        max_test_tpw=max_test_tpw,
        oanda_calendar=oanda_calendar,
        contract_metadata=contract_metadata,
    )
    blockers = micro_nsga_blockers
    if val_returns and statistics.median(val_returns) <= 0:
        warnings.append("MICRO_NSGA_WILL_OPTIMIZE_NON_POSITIVE_VALIDATION_RETURN")
    if test_returns and statistics.median(test_returns) <= 0:
        warnings.append("MICRO_NSGA_WILL_OPTIMIZE_NON_POSITIVE_TEST_RETURN")
    if failed_rows:
        warnings.append("MICRO_NSGA_SEED_FAILURES_REMAIN_IN_LEDGER")
    if done_rows and any(r["test_no_trades"] is True for r in done_rows):
        warnings.append("MICRO_NSGA_WILL_OPTIMIZE_TEST_NO_TRADES")
    if costs_done == ["base"]:
        warnings.append("MICRO_NSGA_BASE_COST_ONLY")
    action = "defer_blocked_by_smoke_evidence"
    if not micro_nsga_blockers:
        action = "eligible_for_stage3x_micro_nsga"
    return {
        "contract_id": contract_id,
        "broker_profile": broker["broker_profile"],
        "regulatory_profile": broker["regulatory_profile"],
        "asset_token": broker["asset_token"],
        "timeframe": broker["timeframe"],
        "trade_frequency_policy": policy_band,
        "median_validation_trades_per_week": median_val_tpw,
        "median_test_trades_per_week": median_test_tpw,
        "max_validation_trades_per_week": max_val_tpw,
        "max_test_trades_per_week": max_test_tpw,
        "median_validation_cost_to_gross_edge_ratio": median_val_cost_ratio,
        "median_test_cost_to_gross_edge_ratio": median_test_cost_ratio,
        "oanda_calendar_audit": oanda_calendar,
        "done": len(done_rows),
        "failed": len(failed_rows),
        "cost_scenarios_done": costs_done,
        "done_by_cost": done_by_cost,
        "median_validation_return": statistics.median(val_returns) if val_returns else None,
        "median_test_return": statistics.median(test_returns) if test_returns else None,
        "median_test_return_by_cost": median_test_return_by_cost,
        "median_validation_return_by_cost": median_validation_return_by_cost,
        "median_test_trades": statistics.median(test_trades) if test_trades else None,
        "force_close_obs_present_all_done": force_close_all,
        "blockers": blockers,
        "warnings": warnings,
        "recommended_action": action,
    }


def render_md(payload: dict[str, Any]) -> str:
    all_force_close = all(
        item["force_close_obs_present_all_done"]
        for item in payload["contract_summary"]
        if item["done"] > 0
    )
    eligible = [
        item["contract_id"]
        for item in payload["contract_summary"]
        if item["recommended_action"] == "eligible_for_targeted_cost_seed_followup"
    ]
    micro_nsga_eligible = [
        item["contract_id"]
        for item in payload["contract_summary"]
        if item["recommended_action"] == "eligible_for_stage3x_micro_nsga"
    ]
    missing_broker_profile = any(
        "BROKER_PROFILE_MISSING_OR_UNCONFIRMED" in item.get("blockers", [])
        for item in payload["contract_summary"]
    )
    lines = [
        "# Stage 3X SAC Smoke Result Synthesis",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Stage C access: `{payload['stage_c_access']}`",
        f"- Task count: `{payload['task_count']}`",
        f"- Done / failed / running / pending: `{payload['counts'].get('done', 0)}` / `{payload['counts'].get('failed', 0)}` / `{payload['counts'].get('running', 0)}` / `{payload['counts'].get('pending', 0)}`",
        f"- Evidence files validated: `{payload['evidence_validated']}`",
        "",
        "## Contract Summary",
        "",
        "| contract | broker profile | policy band (target/warn/hard) | median val tpw | median test tpw | test cost/gross | costs | done | failed | median val return | median test return | force-close obs | action | blockers | warnings |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for item in payload["contract_summary"]:
        policy = item.get("trade_frequency_policy") or {}
        target_min = policy.get("target_min")
        target_max = policy.get("target_max")
        target_str = (
            f"{target_min}" if target_min == target_max else f"{target_min}-{target_max}"
        ) if policy.get("policy_known") else "?"
        band_str = (
            f"{target_str} / >{policy.get('warning_above')} / {policy.get('hard_max')}"
            if policy.get("policy_known")
            else "(no policy)"
        )
        val_tpw = item.get("median_validation_trades_per_week")
        test_tpw = item.get("median_test_trades_per_week")
        test_cost_ratio = item.get("median_test_cost_to_gross_edge_ratio")
        lines.append(
            f"| `{item['contract_id']}` | `{item.get('broker_profile')}` | `{band_str}` | "
            f"{val_tpw if val_tpw is None else f'{val_tpw:.2f}'} | "
            f"{test_tpw if test_tpw is None else f'{test_tpw:.2f}'} | "
            f"{test_cost_ratio if test_cost_ratio is None else f'{test_cost_ratio:.2f}'} | "
            f"`{', '.join(item['cost_scenarios_done'])}` | "
            f"{item['done']} | {item['failed']} | "
            f"{item['median_validation_return']} | {item['median_test_return']} | "
            f"`{item['force_close_obs_present_all_done']}` | "
            f"`{item['recommended_action']}` | `{', '.join(item['blockers'])}` | `{', '.join(item.get('warnings') or [])}` |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Broad GPU launch allowed: `{payload['broad_gpu_launch_allowed']}`",
            f"- Stage C allowed: `{payload['stage_c_allowed']}`",
            f"- Next action: `{payload['next_action']}`",
            "",
            "## Trade-Frequency Policy (FINRA/OANDA memo §5.2)",
            "",
            "- FX 4h: target 3/week, warn >6/week, hard max 12/week.",
            "- FX 1h: target 6/week, warn >12/week, hard max 24/week.",
            "- OANDA crypto 4h: target 1-3/week, warn >3/week, hard max 12/week.",
            "- OANDA crypto 1h: target 3-6/week, warn >12/week, hard max 24/week.",
            "- Non-OANDA crypto/perp 4h: target 3-6/week, warn >12/week, hard max 24/week.",
            "- Non-OANDA crypto/perp 1h: target 6-12/week, warn >24/week, hard max 36/week.",
            "",
            "## Notes",
            "",
            "- This smoke run validated that feature hashes and evidence files are now emitted for completed cells.",
            f"- Force-close/calendar observation fields present in all completed evidence: `{all_force_close}`.",
            f"- Eligible targeted follow-up contracts: `{', '.join(eligible)}`.",
            f"- Eligible Stage 3X micro-NSGA contracts: `{', '.join(micro_nsga_eligible)}`.",
            (
                "- Spot-crypto contracts whose venue cannot be confirmed remain blocked by `BROKER_PROFILE_MISSING_OR_UNCONFIRMED`."
                if missing_broker_profile
                else "- Broker profiles are explicitly resolved for every summarized smoke contract."
            ),
            f"- Cost-to-gross-edge warning threshold: `{COST_TO_GROSS_EDGE_WARN_ABOVE}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=STATE_FILE)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    parser.add_argument("--selected-contracts", type=Path, default=SELECTED_CONTRACTS)
    args = parser.parse_args(argv)
    configure_paths(
        state_file=args.state_file,
        out_root=args.out_root,
        selected_contracts=args.selected_contracts,
    )
    state = load_json(STATE_FILE)
    if state.get("stage_c_access") != "DENIED":
        raise SmokeSynthesisError("Dispatch state does not deny Stage C")
    contract_meta = selected_contract_metadata()
    rows = [
        row_from_task(task, contract_meta.get(str(task["contract_id"])))
        for task in state["tasks"]
    ]
    by_contract: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_contract.setdefault(row["contract_id"], []).append(row)
    contract_summary = [
        summarize_contract(contract_id, contract_rows, contract_meta.get(contract_id))
        for contract_id, contract_rows in sorted(by_contract.items())
    ]
    counts: dict[str, int] = {}
    for task in state["tasks"]:
        counts[task["status"]] = counts.get(task["status"], 0) + 1
    evidence_validated = sum(1 for row in rows if row["status"] == "done" and row["feature_list_hash"])
    repair_needed = any(
        "MISSING_FORCE_CLOSE_OBSERVATION_FIELDS" in item["blockers"]
        for item in contract_summary
    )
    targeted_followup_ready = any(
        item["recommended_action"] == "eligible_for_targeted_cost_seed_followup"
        for item in contract_summary
    )
    micro_nsga_ready = any(
        item["recommended_action"] == "eligible_for_stage3x_micro_nsga"
        for item in contract_summary
    )
    if repair_needed:
        next_action = "repair_force_close_observation_contract_and_repeat_small_smoke"
    elif targeted_followup_ready:
        next_action = "select_targeted_cost_seed_followup"
    elif micro_nsga_ready:
        next_action = "prepare_stage3x_micro_nsga_plan"
    else:
        next_action = "return_to_cpu_feature_screen_or_next_smoke_subset"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "state_file": str(STATE_FILE),
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "task_count": len(state["tasks"]),
        "counts": counts,
        "evidence_validated": evidence_validated,
        "broad_gpu_launch_allowed": False,
        "next_action": next_action,
        "contract_summary": contract_summary,
        "rows": rows,
    }
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(payload), encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: payload[k] for k in ("task_count", "counts", "evidence_validated", "next_action")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
