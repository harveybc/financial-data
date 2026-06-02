#!/usr/bin/env python3
"""Stage B statistical-governance evaluator.

This worker ingests agent-multi ``evidence.json`` return-trace indexes,
validates trace integrity, computes per-run statistical diagnostics, aggregates
candidate-level gates, and emits fail-closed evidence for the Stage B approval
worker.

It never reads Stage C data intentionally. Any trace row at or after
``2025-01-01`` without explicit Stage C authorization is a hard evidence error.
Even authorized Stage C traces do not clear Stage B gates.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any

from scipy import stats as _scipy_stats


ROOT = Path(__file__).resolve().parents[2]
STAGE_B_RUNS = ROOT / "experiments" / "stage_b_validation" / "runs"
PRAGMATIC_STAGE_B_PLANS = ROOT / "experiments" / "stage_b_validation" / "pragmatic_run_plan" / "plans"
SESSION_CALENDAR_STAGE_B_PLANS = (
    ROOT / "experiments" / "stage_b_validation" / "session_calendar_run_plan" / "plans"
)
FORCE_CLOSE_OBS_STAGE_B_PLANS = (
    ROOT / "experiments" / "stage_b_validation" / "force_close_obs_run_plan" / "plans"
)
FORCE_CLOSE_PENALTY_STAGE_B_PLANS = (
    ROOT / "experiments" / "stage_b_validation" / "force_close_penalty_run_plan" / "plans"
)
OUT_DIR = ROOT / "experiments" / "stage_b_validation" / "hardening"
OUT_JSON = OUT_DIR / "stageb_dsr_pbo_report.json"
OUT_MD = OUT_DIR / "stageb_dsr_pbo_report.md"
CONTRACT_MD = OUT_DIR / "RETURN_TRACE_CONTRACT.md"
LEDGER_SUMMARY = ROOT / "artifacts" / "run_ledger_summary.json"
PROMOTION_REPORT = ROOT / "experiments" / "stage_a_screening" / "hardening" / "promotion_hardening_report.json"
RUN_PLAN_STATUS_JSON = ROOT / "experiments" / "stage_b_validation" / "run_plan" / "stage_b_run_plan_status.json"

HELDOUT_START = "2025-01-01"
EVIDENCE_SCHEMA = "project3_return_trace_evidence_v1"
TRACE_SCHEMA = "stage_b_return_trace_v1"
MIN_DSR_RETURNS = 30
MIN_SEEDS = 5
PRAGMATIC_REQUIRED_COST_SCENARIOS = {"base", "plus_50pct", "plus_100pct"}
LEGACY_REQUIRED_COST_SCENARIOS = {"base", "pessimistic"}
REQUIRED_COST_SCENARIO_SETS = (
    PRAGMATIC_REQUIRED_COST_SCENARIOS,
    LEGACY_REQUIRED_COST_SCENARIOS,
)
KNOWN_COST_SUFFIXES = (
    "plus_100pct",
    "plus_50pct",
    "pessimistic",
    "optimistic",
    "base",
)
EXCESSIVE_TRADES_HARD_PER_YEAR = 730.0
ALWAYS_IN_MARKET_HARD = 0.95
PBO_EMBARGO_BARS = 24  # conservative purge between IS/OOS folds (~1 trading week @ 4h)
FAMILY_BOOTSTRAP_REPS = 499  # stationary-bootstrap reps for WRC/SPA-lite


class EvidenceError(ValueError):
    """Raised when trace evidence is missing, inconsistent, or unsafe."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def std(xs: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    mu = mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def percentile(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    ordered = sorted(xs)
    idx = min(max(int(round((len(ordered) - 1) * q)), 0), len(ordered) - 1)
    return ordered[idx]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace("T", " ")
    if text.endswith("Z"):
        text = text[:-1]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def before_heldout(value: Any) -> bool:
    ts = parse_time(value)
    boundary = datetime.fromisoformat(HELDOUT_START)
    return ts is not None and ts < boundary


_SEED_SUFFIX_RE = re.compile(r"_s\d+$")


def candidate_slug(run_id: str) -> str:
    """Return a seed-and-cost-stripped candidate identifier.

    Pragmatic run IDs encode ``_s<seed>_<cost>`` after the feature/preset
    tokens (for example ``ethusdt_4h_sac_tech_stat_s0_base``). Stripping both
    the cost suffix and the seed marker collapses the five seed copies into a
    single candidate slug, which is what the seed-uncertainty and PBO groupings
    expect. Without the seed strip every seed becomes its own candidate and
    every seed group degenerates to ``n_seeds=1``.
    """
    out = run_id
    if out.startswith("candidate_"):
        out = out[len("candidate_") :]
    elif out.startswith("rl_baseline_12_"):
        out = out[len("rl_baseline_12_") :]
    for suffix in tuple(f"_{value}" for value in KNOWN_COST_SUFFIXES):
        if out.endswith(suffix):
            out = out[: -len(suffix)]
            break
    out = _SEED_SUFFIX_RE.sub("", out)
    return out


def cost_scenario(run_id: str) -> str:
    for suffix in KNOWN_COST_SUFFIXES:
        if run_id.endswith(f"_{suffix}"):
            return suffix
    return "unknown"


def missing_required_cost_scenarios(scenarios: set[str]) -> list[str]:
    """Return missing scenarios for the best matching accepted cost contract.

    Stage B has two accepted evidence contracts during the migration:

    - legacy: ``base`` + ``pessimistic``;
    - pragmatic: ``base`` + ``plus_50pct`` + ``plus_100pct``.

    A candidate may pass the cost-coverage gate if either full set is present.
    The returned list is for the accepted set with the smallest gap, so reports
    remain useful while old and pragmatic artifacts coexist.
    """
    if any(required.issubset(scenarios) for required in REQUIRED_COST_SCENARIO_SETS):
        return []
    if scenarios & (PRAGMATIC_REQUIRED_COST_SCENARIOS - {"base"}):
        return sorted(PRAGMATIC_REQUIRED_COST_SCENARIOS - scenarios)
    if scenarios & (LEGACY_REQUIRED_COST_SCENARIOS - {"base"}):
        return sorted(LEGACY_REQUIRED_COST_SCENARIOS - scenarios)
    best = min(
        REQUIRED_COST_SCENARIO_SETS,
        key=lambda required: (len(required - scenarios), sorted(required)),
    )
    return sorted(best - scenarios)


PRAGMATIC_BASELINE_NAMES = (
    "no_trade",
    "buy_and_hold",
    "random",
    "momentum",
    "reversal",
)


def is_baseline_run(run_id: str, preset: str) -> bool:
    """Return True iff this run is a deterministic baseline, not a candidate.

    Three patterns count as a baseline:

    - legacy ``rl_baseline_12_*`` run IDs;
    - the canonical ``preset == 'baseline_12'`` marker used by Stage A
      hardening artifacts;
    - pragmatic Stage B baselines, whose run IDs contain a
      ``_baseline_<name>_`` substring drawn from
      :data:`PRAGMATIC_BASELINE_NAMES` (``buy_and_hold``, ``no_trade``,
      ``random``, ``momentum``, ``reversal``).

    Without this last branch all pragmatic baselines are mis-classified as
    promotion candidates, which makes :func:`family_tests` emit
    ``BLOCKED_MISSING_MATCHED_BASELINE`` for every (asset, timeframe, algo,
    cost) group that only has pragmatic baselines.
    """
    if run_id.startswith("rl_baseline_12_"):
        return True
    if preset == "baseline_12":
        return True
    return any(f"_baseline_{name}_" in run_id for name in PRAGMATIC_BASELINE_NAMES)


def parse_run_identity(run_id: str, evidence: dict[str, Any]) -> dict[str, str]:
    slug = candidate_slug(run_id)
    parts = slug.split("_")
    # Handles assets that contain one suffix component such as btcusdt_perp.
    tf_idx = next((i for i, part in enumerate(parts) if part in {"5m", "15m", "30m", "1h", "4h", "1d"}), -1)
    asset = "_".join(parts[:tf_idx]) if tf_idx > 0 else str(evidence.get("asset") or "")
    timeframe = parts[tf_idx] if tf_idx >= 0 else str(evidence.get("timeframe") or "")
    algo_idx = next((i for i, part in enumerate(parts) if part in {"ppo", "sac", "dqn"}), -1)
    algo = parts[algo_idx] if algo_idx >= 0 else ""
    preset = "_".join(parts[tf_idx + 1 : algo_idx]) if tf_idx >= 0 and algo_idx > tf_idx else ""
    return {
        "candidate_slug": slug,
        "asset": asset,
        "timeframe": timeframe,
        "algo": algo,
        "preset": preset,
        "cost_scenario": cost_scenario(run_id),
        "is_baseline": is_baseline_run(run_id, preset),
    }


def trial_count() -> int:
    for path, keys in (
        (LEDGER_SUMMARY, ("trial_count", "distinct_trial_ids")),
        (PROMOTION_REPORT, ("ledger_trial_ids",)),
    ):
        data = load_json(path, {}) or {}
        for key in keys:
            value = data.get(key)
            if isinstance(value, int) and value > 0:
                return value
    return 1


def effective_trial_count(records: list[dict[str, Any]], n_raw: int) -> int:
    identities = {
        (r.get("asset"), r.get("timeframe"), r.get("algo"), r.get("preset"), r.get("seed"))
        for r in records
        if r.get("evidence_status") == "PASS"
    }
    return max(1, min(int(n_raw), len(identities) or 1))


def effective_n_newey_west(returns: list[float], max_lag: int | None = None) -> int:
    """Newey-West / Bartlett-window effective sample size.

    ``T_eff = T / (1 + 2 * sum_{k=1..L} w_k * rho_k)`` with the Bartlett window
    ``w_k = 1 - k/(L+1)``. The default lag follows Newey & West's
    ``L = floor(4*(T/100)^(2/9))``. Positive autocorrelation shrinks T_eff, so
    DSR cannot be inflated by overlap.
    """
    t = len(returns)
    if t < 4:
        return max(1, t)
    mu = mean(returns)
    centered = [x - mu for x in returns]
    var0 = sum(x * x for x in centered) / t
    if var0 <= 0 or not math.isfinite(var0):
        return t
    if max_lag is None:
        max_lag = max(1, min(int(math.floor(4.0 * (t / 100.0) ** (2.0 / 9.0))), t - 1))
    rho_sum = 0.0
    for k in range(1, max_lag + 1):
        cov_k = sum(centered[i] * centered[i + k] for i in range(t - k)) / t
        weight = 1.0 - k / (max_lag + 1)
        rho_sum += weight * (cov_k / var0)
    denom = 1.0 + 2.0 * rho_sum
    if denom <= 0 or not math.isfinite(denom):
        return 1
    t_eff = t / denom
    return max(1, min(t, int(round(t_eff))))


def load_trace_rows(trace_path: Path, max_rows: int = 20_000) -> list[dict[str, str]]:
    """Validate all timestamps while retaining a bounded deterministic sample.

    Some Stage B traces are tens of megabytes. The evaluator only needs a
    stable return sample for fail-closed diagnostics; it still scans every row
    for monotonic timestamps and heldout contamination.
    """
    with trace_path.open(encoding="utf-8") as handle:
        total_rows = max(sum(1 for _ in handle) - 1, 0)
    stride = max(1, math.ceil(total_rows / max_rows)) if total_rows else 1
    rows: list[dict[str, str]] = []
    last_ts: datetime | None = None
    with trace_path.open(newline="", encoding="utf-8") as handle:
        for idx, row in enumerate(csv.DictReader(handle)):
            ts = parse_time(row.get("timestamp"))
            if ts is None:
                raise EvidenceError(f"unparseable trace timestamp in {trace_path}")
            if last_ts is not None and ts <= last_ts:
                raise EvidenceError(f"non-monotonic trace timestamps in {trace_path}")
            last_ts = ts
            if ts >= datetime.fromisoformat(HELDOUT_START):
                raise EvidenceError(f"trace contains Stage C timestamp: {ts.isoformat()}")
            if idx % stride == 0 or idx == total_rows - 1:
                rows.append(row)
    return rows


def returns_from_rows(rows: list[dict[str, str]], column: str) -> list[float]:
    values: list[float] = []
    if rows and column in rows[0]:
        for row in rows:
            value = safe_float(row.get(column))
            if value is not None:
                values.append(value)
    if values:
        return values
    equities = [safe_float(row.get("equity")) for row in rows]
    equities = [x for x in equities if x is not None]
    return [(cur - prev) / prev for prev, cur in zip(equities, equities[1:]) if prev]


def _count_trade_segment(values: list[float]) -> int:
    if not values:
        return 0
    nondecreasing = all(values[i] >= values[i - 1] for i in range(1, len(values)))
    if nondecreasing:
        return max(0, int(round(values[-1])))
    return max(0, int(round(sum(values))))


def infer_trade_count(rows: list[dict[str, str]]) -> int:
    """Infer total trades from trace rows.

    Agent-multi traces report ``trades`` as a cumulative counter within each
    split/episode. Stage B evidence concatenates train, validation, and test
    traces, so the counter legitimately resets between split episodes. Treating
    that reset as "not cumulative" and summing all rows inflates buy-and-hold
    style traces into millions of trades/year. We therefore count each
    contiguous split/episode segment independently and sum segment terminal
    counts.
    """
    segments: list[list[float]] = []
    current: list[float] = []
    current_key: tuple[str, str] | None = None
    previous_value: float | None = None
    for idx, row in enumerate(rows):
        value = safe_float(row.get("trades")) if row.get("trades") not in (None, "") else None
        if value is None:
            continue
        key = (str(row.get("split", "")), str(row.get("episode_id", "")))
        reset = (
            current_key is not None
            and (
                key != current_key
                or (previous_value is not None and value < previous_value)
            )
        )
        if reset and current:
            segments.append(current)
            current = []
        current_key = key or ("", f"row_{idx}")
        current.append(value)
        previous_value = value
    if current:
        segments.append(current)
    if segments:
        return sum(_count_trade_segment(segment) for segment in segments)
    positions = [safe_float(row.get("position")) or 0.0 for row in rows]
    return sum(1 for a, b in zip(positions, positions[1:]) if abs(a - b) > 1e-12)


def trace_years(rows: list[dict[str, str]]) -> float:
    times = [parse_time(row.get("timestamp")) for row in rows]
    times = [ts for ts in times if ts is not None]
    if len(times) < 2:
        return 0.0
    return max((times[-1] - times[0]).total_seconds() / (365.25 * 86400.0), 1.0 / 365.25)


def exposure_fraction(rows: list[dict[str, str]]) -> float:
    positions = [safe_float(row.get("position")) or 0.0 for row in rows]
    return sum(1 for p in positions if abs(p) > 1e-12) / len(positions) if positions else 0.0


def validate_evidence(evidence_path: Path) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    evidence = load_json(evidence_path)
    if not isinstance(evidence, dict):
        raise EvidenceError(f"evidence is not valid JSON object: {evidence_path}")
    if evidence.get("schema_version") != EVIDENCE_SCHEMA:
        raise EvidenceError(f"unsupported evidence schema: {evidence.get('schema_version')}")
    if evidence.get("trace_schema_version") != TRACE_SCHEMA:
        raise EvidenceError(f"unsupported trace schema: {evidence.get('trace_schema_version')}")
    if evidence.get("heldout_boundary") != HELDOUT_START:
        raise EvidenceError(f"unexpected heldout boundary: {evidence.get('heldout_boundary')}")
    if evidence.get("contains_heldout_rows") and not evidence.get("stage_c_authorized"):
        raise EvidenceError("evidence reports unauthorized heldout rows")
    traces = evidence.get("traces")
    if not isinstance(traces, list) or not traces:
        raise EvidenceError("evidence has no traces")

    seen_splits: set[str] = set()
    all_rows: list[dict[str, str]] = []
    trace_entries: list[dict[str, str]] = []
    for item in traces:
        if not isinstance(item, dict):
            raise EvidenceError("trace entry is not an object")
        split = str(item.get("split") or "")
        if split in seen_splits:
            raise EvidenceError(f"duplicate trace split: {split}")
        seen_splits.add(split)
        if item.get("contains_heldout_rows") and not item.get("stage_c_authorized"):
            raise EvidenceError(f"trace split {split} reports unauthorized heldout rows")
        if item.get("stage_c_authorized"):
            raise EvidenceError(f"trace split {split} is Stage C-authorized; Stage B evaluator refuses it")
        if item.get("first_timestamp") and not before_heldout(item.get("first_timestamp")):
            raise EvidenceError(f"trace split {split} starts at/after heldout boundary")
        if item.get("last_timestamp") and not before_heldout(item.get("last_timestamp")):
            raise EvidenceError(f"trace split {split} ends at/after heldout boundary")

        trace_path = Path(str(item.get("trace_file") or ""))
        meta_path = Path(str(item.get("metadata_file") or ""))
        if not trace_path.exists():
            raise EvidenceError(f"missing trace file: {trace_path}")
        if meta_path and not meta_path.exists():
            raise EvidenceError(f"missing trace metadata file: {meta_path}")
        expected_hash = str(item.get("trace_file_sha256") or "")
        actual_hash = sha256_file(trace_path)
        if expected_hash and actual_hash != expected_hash:
            raise EvidenceError(f"trace SHA mismatch for {trace_path}")
        rows = load_trace_rows(trace_path)
        if not rows:
            raise EvidenceError(f"empty trace file: {trace_path}")
        all_rows.extend(rows)
        trace_entries.append({"split": split, "trace_file": str(trace_path), "metadata_file": str(meta_path)})
    return evidence, trace_entries, all_rows


def moments(xs: list[float]) -> dict[str, float]:
    """Sample mean, std (unbiased), skew (unbiased), kurtosis (non-excess, unbiased).

    Returns Gaussian kurtosis = 3 by using ``fisher=False``. Bailey & López de
    Prado's PSR/DSR formulation expects non-excess kurtosis.
    """
    n = len(xs)
    mu = mean(xs)
    sd = std(xs)
    if n < 4 or not sd or not math.isfinite(sd):
        return {"mean": mu, "std": sd, "skew": float("nan"), "kurtosis": float("nan")}
    try:
        skew = float(_scipy_stats.skew(xs, bias=False))
    except Exception:
        skew = float("nan")
    try:
        kurt = float(_scipy_stats.kurtosis(xs, fisher=False, bias=False))
    except Exception:
        kurt = float("nan")
    return {"mean": mu, "std": sd, "skew": skew, "kurtosis": kurt}


def sharpe(xs: list[float]) -> float:
    sd = std(xs)
    return mean(xs) / sd if sd and math.isfinite(sd) else float("nan")


def expected_max_sr(observed_srs: list[float], n_trials: int, n_obs: int) -> float:
    clean = [x for x in observed_srs if math.isfinite(x)]
    if len(clean) >= 2:
        mu = mean(clean)
        sigma = std(clean)
    else:
        mu = 0.0
        sigma = 1.0 / math.sqrt(max(2, n_obs))
    nd = NormalDist()
    gamma = 0.5772156649015329
    n = max(2, int(n_trials))
    return mu + sigma * (
        (1 - gamma) * nd.inv_cdf(1 - 1 / n)
        + gamma * nd.inv_cdf(1 - 1 / (n * math.e))
    )


def dsr(returns: list[float], sr_benchmark: float) -> dict[str, Any]:
    """Probabilistic / Deflated Sharpe Ratio (Bailey & López de Prado).

    Uses unbiased skew, non-excess kurtosis, and a Newey-West autocorrelation
    correction on the effective sample size. ``status='PASS'`` requires p-value
    below 0.01 against the supplied benchmark Sharpe.
    """
    n = len(returns)
    mom = moments(returns)
    sr = sharpe(returns)
    if n < MIN_DSR_RETURNS or not math.isfinite(sr):
        return {"status": "BLOCKED_INSUFFICIENT_RETURNS", "n": n, "sr_period": sr, **mom}
    skew = mom["skew"] if math.isfinite(mom["skew"]) else 0.0
    kurt = mom["kurtosis"] if math.isfinite(mom["kurtosis"]) else 3.0
    denom = 1 - skew * sr + ((kurt - 1) / 4.0) * sr * sr
    if denom <= 0 or not math.isfinite(denom):
        return {"status": "BLOCKED_NUMERIC_DSR", "n": n, "sr_period": sr, "sr_benchmark": sr_benchmark, **mom}
    t_eff = effective_n_newey_west(returns)
    eff_t = max(2, min(n, t_eff))
    z = (sr - sr_benchmark) * math.sqrt(eff_t - 1) / math.sqrt(denom)
    probability = NormalDist().cdf(z)
    p_value = 1 - probability
    return {
        "status": "PASS" if p_value < 0.01 else "FAIL",
        "n": n,
        "n_effective_newey_west": eff_t,
        "sr_period": sr,
        "sr_benchmark": sr_benchmark,
        "dsr_probability": probability,
        "dsr_p_value": p_value,
        "z": z,
        **mom,
    }


def fold_sharpes(returns: list[float], folds: int = 8) -> list[float]:
    if len(returns) < folds * 10:
        return []
    out: list[float] = []
    n = len(returns)
    for idx in range(folds):
        lo = math.floor(idx * n / folds)
        hi = math.floor((idx + 1) * n / folds)
        out.append(sharpe(returns[lo:hi]))
    return out


def pbo_group(records: list[dict[str, Any]], folds: int = 8, embargo_bars: int = 0) -> dict[str, Any]:
    """Contiguous-fold PBO-lite (CSCV-style) with optional bar-level embargo.

    When ``embargo_bars > 0``, the IS Sharpe is recomputed on the merged IS bars
    after dropping ``embargo_bars`` adjacent to the OOS fold on both sides.
    Without an embargo we fall back to the cheap fold-SR mean, which is the
    existing PBO-lite behavior.
    """
    candidates = [r for r in records if len(r.get("net_returns", [])) >= folds * 10]
    if len(candidates) < 2:
        return {"status": "BLOCKED_TOO_FEW_CANDIDATES", "candidate_count": len(candidates)}
    for record in candidates:
        record["fold_srs"] = fold_sharpes(record["net_returns"], folds)
    candidates = [r for r in candidates if len(r["fold_srs"]) == folds and all(math.isfinite(x) for x in r["fold_srs"])]
    if len(candidates) < 2:
        return {"status": "BLOCKED_INSUFFICIENT_FOLD_RETURNS", "candidate_count": len(candidates)}

    logits: list[float] = []
    selections: list[dict[str, Any]] = []
    embargo = max(0, int(embargo_bars))
    for oos_fold in range(folds):
        scored = []
        for record in candidates:
            ret = record["net_returns"]
            t = len(ret)
            oos_lo = math.floor(oos_fold * t / folds)
            oos_hi = math.floor((oos_fold + 1) * t / folds)
            if embargo > 0:
                drop_lo = max(0, oos_lo - embargo)
                drop_hi = min(t, oos_hi + embargo)
                is_returns = ret[:drop_lo] + ret[drop_hi:]
                is_sharpe = sharpe(is_returns) if len(is_returns) >= 2 else float("nan")
            else:
                is_scores = [sr for idx, sr in enumerate(record["fold_srs"]) if idx != oos_fold]
                is_sharpe = mean(is_scores)
            oos_sharpe = record["fold_srs"][oos_fold]
            scored.append((record, is_sharpe, oos_sharpe))
        scored = [item for item in scored if math.isfinite(item[1])]
        if len(scored) < 2:
            continue
        selected = max(scored, key=lambda item: item[1])
        ranked = sorted(scored, key=lambda item: item[2], reverse=True)
        rank = next(idx for idx, item in enumerate(ranked, start=1) if item[0]["run_id"] == selected[0]["run_id"])
        percentile_rank = 1 - ((rank - 1) / (len(ranked) - 1)) if len(ranked) > 1 else 1.0
        percentile_rank = min(max(percentile_rank, 1e-6), 1 - 1e-6)
        logit = math.log(percentile_rank / (1 - percentile_rank))
        logits.append(logit)
        selections.append({
            "oos_fold": oos_fold,
            "selected_run_id": selected[0]["run_id"],
            "is_sharpe": selected[1],
            "oos_sharpe": selected[2],
            "oos_rank": rank,
            "candidate_count": len(ranked),
            "logit": logit,
        })
    if not logits:
        return {"status": "BLOCKED_INSUFFICIENT_FOLD_RETURNS", "candidate_count": len(candidates)}
    pbo = sum(1 for x in logits if x < 0) / len(logits)
    return {
        "status": "PASS" if pbo <= 0.20 else ("WATCH" if pbo <= 0.50 else "FAIL"),
        "folds": folds,
        "embargo_bars": embargo,
        "candidate_count": len(candidates),
        "pbo": pbo,
        "selections": selections,
    }


def bounded_series(values: list[float], max_points: int = 2_000) -> list[float]:
    """Return a deterministic length-bounded view for bootstrap cost control."""
    if len(values) <= max_points:
        return values
    step = len(values) / max_points
    return [values[int(i * step)] for i in range(max_points)]


def stationary_bootstrap_means(values: list[float], reps: int = 499, block_length: int | None = None) -> list[float]:
    if not values:
        return []
    values = bounded_series(values)
    rng = random.Random(1337)
    n = len(values)
    block = block_length or max(2, int(round(math.sqrt(n))))
    p_new = 1.0 / block
    out: list[float] = []
    for _ in range(reps):
        idx = rng.randrange(n)
        sample_sum = 0.0
        for _j in range(n):
            sample_sum += values[idx]
            idx = rng.randrange(n) if rng.random() < p_new else (idx + 1) % n
        out.append(sample_sum / n)
    return out


def family_tests(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("evidence_status") == "PASS":
            key = "|".join([
                str(record.get("asset", "")),
                str(record.get("timeframe", "")),
                str(record.get("algo", "")),
                str(record.get("cost_scenario", "")),
            ])
            groups[key].append(record)

    out: dict[str, dict[str, Any]] = {}
    for key, group in groups.items():
        baseline = next((r for r in group if r.get("is_baseline")), None)
        candidates = [r for r in group if not r.get("is_baseline")]
        if baseline is None or not candidates:
            out[key] = {"status": "BLOCKED_MISSING_MATCHED_BASELINE", "candidate_count": len(candidates)}
            continue
        diffs_by_run: dict[str, list[float]] = {}
        for candidate in candidates:
            n = min(len(candidate["net_returns"]), len(baseline["net_returns"]))
            diffs_by_run[candidate["run_id"]] = [
                candidate["net_returns"][i] - baseline["net_returns"][i]
                for i in range(n)
            ]
        observed = {run_id: mean(diffs) for run_id, diffs in diffs_by_run.items() if diffs}
        if not observed:
            out[key] = {"status": "BLOCKED_EMPTY_DIFFS", "candidate_count": len(candidates)}
            continue
        best_run = max(observed, key=observed.get)
        best_mean = observed[best_run]
        # White Reality Check style max statistic under centered diffs.
        centered = {
            run_id: [x - mean(diffs) for x in diffs]
            for run_id, diffs in diffs_by_run.items()
            if diffs
        }
        boot_by_run = {
            run_id: stationary_bootstrap_means(diffs, reps=FAMILY_BOOTSTRAP_REPS)
            for run_id, diffs in centered.items()
        }
        reps = min((len(v) for v in boot_by_run.values()), default=0)
        boot_max: list[float] = [
            max(values[i] for values in boot_by_run.values())
            for i in range(reps)
        ]
        p_value = sum(1 for x in boot_max if x >= best_mean) / len(boot_max) if boot_max else 1.0
        # SPA-lite: test only positive observed alternatives.
        positive = {k: v for k, v in observed.items() if v > 0}
        spa_p = p_value if positive else 1.0
        out[key] = {
            "status": "PASS" if p_value < 0.05 and spa_p < 0.05 else "FAIL",
            "best_run_id": best_run,
            "best_mean_return_diff": best_mean,
            "white_reality_check_p": p_value,
            "spa_lite_p": spa_p,
            "candidate_count": len(candidates),
            "baseline_run_id": baseline["run_id"],
        }
    return out


def seed_uncertainty(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for record in records:
        if record.get("evidence_status") == "PASS" and not record.get("is_baseline"):
            key = "|".join([
                str(record.get("candidate_slug")),
                str(record.get("cost_scenario")),
            ])
            groups[key].append(sum(record.get("net_returns", [])))
    out: dict[str, dict[str, Any]] = {}
    for key, values in groups.items():
        clean = sorted(values)
        n = len(clean)
        trim = clean[int(0.25 * n) : max(int(0.75 * n), int(0.25 * n) + 1)] if n else []
        boot = []
        if clean:
            rng = random.Random(2026)
            for _ in range(499):
                sample = [clean[rng.randrange(n)] for _ in range(n)]
                boot.append(mean(sample))
        out[key] = {
            "status": "PASS" if n >= MIN_SEEDS else "BLOCKED_UNPAIRED_SEEDS",
            "n_seeds": n,
            "median": percentile(clean, 0.5),
            "iqm": mean(trim),
            "mean": mean(clean),
            "ci_low": percentile(boot, 0.025),
            "ci_high": percentile(boot, 0.975),
            "probability_positive": sum(1 for x in clean if x > 0) / n if n else 0.0,
        }
    return out


def trade_gate(rows: list[dict[str, str]], returns: list[float]) -> dict[str, Any]:
    trades = infer_trade_count(rows)
    years = trace_years(rows)
    trades_per_year = trades / years if years > 0 else float("inf")
    exposure = exposure_fraction(rows)
    total_return = sum(returns)
    blockers: list[str] = []
    warnings: list[str] = []
    if trades <= 0:
        blockers.append("FINAL_NO_TRADES")
    if trades_per_year > EXCESSIVE_TRADES_HARD_PER_YEAR:
        blockers.append("FINAL_EXCESSIVE_TRADES_HARD")
    if exposure >= ALWAYS_IN_MARKET_HARD and total_return <= 0:
        blockers.append("FINAL_ALWAYS_IN_MARKET_LOSING")
    elif exposure >= ALWAYS_IN_MARKET_HARD:
        warnings.append("FINAL_ALWAYS_IN_MARKET_WARN")
    return {
        "status": "PASS" if not blockers else "FAIL",
        "trades_total": trades,
        "years": years,
        "trades_per_year": trades_per_year,
        "exposure_fraction": exposure,
        "total_return_from_trace": total_return,
        "blockers": blockers,
        "warnings": warnings,
    }


def discover_evidence(root: Path | None = None) -> list[Path]:
    roots = [root] if root is not None else [
        STAGE_B_RUNS,
        PRAGMATIC_STAGE_B_PLANS,
        SESSION_CALENDAR_STAGE_B_PLANS,
        FORCE_CLOSE_OBS_STAGE_B_PLANS,
        FORCE_CLOSE_PENALTY_STAGE_B_PLANS,
    ]
    found: dict[str, Path] = {}
    for search_root in roots:
        if search_root and search_root.exists():
            for path in search_root.glob("**/evidence.json"):
                found[str(path.resolve())] = path
    return sorted(found.values())


def build_records(evidence_paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for evidence_path in evidence_paths:
        run_id = evidence_path.parent.parent.name
        base = {
            "run_id": run_id,
            "run_dir": str(evidence_path.parent.parent),
            "evidence_file": str(evidence_path),
            "evidence_status": "PASS",
            "evidence_errors": [],
        }
        try:
            evidence, trace_entries, rows = validate_evidence(evidence_path)
            identity = parse_run_identity(str(evidence.get("run_id") or run_id), evidence)
            # Drop training-split rows for statistical and trade-gate evaluation:
            # pragmatic agent-multi traces emit train+validation+test, but Stage B
            # gates are an out-of-sample test by construction. Legacy single-split
            # traces label rows ``stage_b_validation`` / ``evaluation`` and are
            # unaffected by this denylist.
            oos_rows = [r for r in rows if str(r.get("split", "")).strip().lower() != "train"]
            net = returns_from_rows(oos_rows, "net_return")
            gross = returns_from_rows(oos_rows, "gross_return")
            tgate = trade_gate(oos_rows, net)
            base.update(identity)
            base.update({
                "run_id": str(evidence.get("run_id") or run_id),
                "seed": evidence.get("seed"),
                "config_hash": evidence.get("config_hash"),
                "data_file": evidence.get("data_file"),
                "data_file_hash": evidence.get("data_file_hash"),
                "feature_list_hash": evidence.get("feature_list_hash"),
                "trace_schema_version": evidence.get("trace_schema_version"),
                "trace_entries": trace_entries,
                "net_returns": net,
                "gross_returns": gross,
                "n_returns": len(net),
                "sr_period": sharpe(net),
                "trade_gate": tgate,
            })
        except EvidenceError as exc:
            base.update({
                "candidate_slug": candidate_slug(run_id),
                "cost_scenario": cost_scenario(run_id),
                "evidence_status": "FAIL",
                "evidence_errors": [str(exc)],
                "net_returns": [],
                "gross_returns": [],
                "n_returns": 0,
                "sr_period": float("nan"),
                "trade_gate": {"status": "FAIL", "blockers": ["EVIDENCE_INVALID"], "warnings": []},
            })
        records.append(base)
    return records


def candidate_gates(records: list[dict[str, Any]], pbo_groups: dict[str, dict[str, Any]], family: dict[str, dict[str, Any]], seed: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("candidate_slug"))].append(record)
    out: dict[str, dict[str, Any]] = {}
    for slug, rows in grouped.items():
        blockers: list[str] = []
        if any(r.get("evidence_status") != "PASS" for r in rows):
            blockers.append("EVIDENCE_INVALID_OR_MISSING")
        scenarios = {str(r.get("cost_scenario")) for r in rows if r.get("evidence_status") == "PASS"}
        missing_costs = missing_required_cost_scenarios(scenarios)
        if missing_costs:
            blockers.append("MISSING_COST_SCENARIO")
        if any(r.get("trade_gate", {}).get("status") != "PASS" for r in rows):
            blockers.extend(sorted({b for r in rows for b in r.get("trade_gate", {}).get("blockers", [])}))

        dsr_statuses = [str(r.get("dsr_n_raw", {}).get("status")) for r in rows if r.get("evidence_status") == "PASS"]
        if not dsr_statuses or any(status != "PASS" for status in dsr_statuses):
            blockers.append("DSR_RIGOROUS_FAIL")

        for record in rows:
            group_key = "|".join([str(record.get("asset", "")), str(record.get("timeframe", "")), str(record.get("algo", ""))])
            pbo = pbo_groups.get(group_key, {})
            if pbo.get("status") != "PASS":
                blockers.append("PBO_DEFERRED_OR_FAIL")
            fam_key = "|".join([str(record.get("asset", "")), str(record.get("timeframe", "")), str(record.get("algo", "")), str(record.get("cost_scenario", ""))])
            fam = family.get(fam_key, {})
            if fam.get("status") != "PASS":
                blockers.append("FAMILY_REALITY_CHECK_FAIL")
            seed_key = "|".join([slug, str(record.get("cost_scenario", ""))])
            sgate = seed.get(seed_key, {})
            if sgate.get("status") != "PASS":
                blockers.append("SEED_UNCERTAINTY_BLOCKED")

        blockers = sorted(set(blockers))
        out[slug] = {
            "candidate_slug": slug,
            "promotion_allowed": not blockers,
            "status": "PASS" if not blockers else "FAIL",
            "blocking_reasons": blockers,
            "cost_scenarios_present": sorted(scenarios),
            "missing_required_cost_scenarios": missing_costs,
            "record_count": len(rows),
            "records": [r["run_id"] for r in rows],
        }
    return out


def write_contract() -> None:
    CONTRACT_MD.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_MD.write_text(
        "\n".join([
            "# Stage B Return-Trace Evidence Contract",
            "",
            f"- Accepted evidence schema: `{EVIDENCE_SCHEMA}`",
            f"- Accepted trace schema: `{TRACE_SCHEMA}`",
            f"- Heldout boundary: `{HELDOUT_START}`",
            f"- Accepted cost contracts: legacy `{sorted(LEGACY_REQUIRED_COST_SCENARIOS)}` or pragmatic `{sorted(PRAGMATIC_REQUIRED_COST_SCENARIOS)}`.",
            f"- Evidence roots include `{STAGE_B_RUNS}`, `{PRAGMATIC_STAGE_B_PLANS}`, `{SESSION_CALENDAR_STAGE_B_PLANS}`, `{FORCE_CLOSE_OBS_STAGE_B_PLANS}`, and `{FORCE_CLOSE_PENALTY_STAGE_B_PLANS}`.",
            "- Each run must write `traces/evidence.json` and one or more trace CSV files.",
            "- Trace SHA-256 in evidence must match the trace file bytes.",
            "- Stage B evaluator refuses any Stage C-authorized trace.",
            "- Candidate promotion requires a complete accepted cost contract, rigorous DSR, PBO-lite, family bootstrap tests, paired seed evidence, and trade-behavior gates.",
        ])
        + "\n",
        encoding="utf-8",
    )


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in {"net_returns", "gross_returns"}}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_contract()
    evidence_paths = discover_evidence()
    records = build_records(evidence_paths)
    n_raw = trial_count()
    n_eff = effective_trial_count(records, n_raw)
    observed_srs = [r["sr_period"] for r in records if r.get("evidence_status") == "PASS" and math.isfinite(r.get("sr_period", float("nan")))]
    for record in records:
        if record.get("evidence_status") != "PASS":
            record["dsr_n_raw"] = {"status": "BLOCKED_EVIDENCE_INVALID"}
            record["dsr_n_eff"] = {"status": "BLOCKED_EVIDENCE_INVALID"}
            continue
        record["dsr_n_raw"] = dsr(record["net_returns"], expected_max_sr(observed_srs, n_raw, record["n_returns"]))
        record["dsr_n_eff"] = dsr(record["net_returns"], expected_max_sr(observed_srs, n_eff, record["n_returns"]))

    pbo_input: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("evidence_status") == "PASS":
            key = "|".join([str(record.get("asset", "")), str(record.get("timeframe", "")), str(record.get("algo", ""))])
            pbo_input[key].append(record)
    pbo_groups = {key: pbo_group(group, embargo_bars=PBO_EMBARGO_BARS) for key, group in sorted(pbo_input.items())}
    family = family_tests(records)
    seeds = seed_uncertainty(records)
    gates = candidate_gates(records, pbo_groups, family, seeds)

    summary = {
        "schema_version": "project3_stageb_statistical_evaluator_v2",
        "generated_at_utc": utc_now(),
        "stage": "stage_b",
        "evidence_files": len(evidence_paths),
        "run_count": len(records),
        "evidence_pass": sum(1 for r in records if r.get("evidence_status") == "PASS"),
        "evidence_fail": sum(1 for r in records if r.get("evidence_status") != "PASS"),
        "dsr_pass_n_raw": sum(1 for r in records if r.get("dsr_n_raw", {}).get("status") == "PASS"),
        "dsr_fail_n_raw": sum(1 for r in records if r.get("dsr_n_raw", {}).get("status") == "FAIL"),
        "candidate_gate_pass": sum(1 for g in gates.values() if g["promotion_allowed"]),
        "candidate_gate_fail": sum(1 for g in gates.values() if not g["promotion_allowed"]),
        "trial_count_n_raw": n_raw,
        "trial_count_n_eff": n_eff,
        "pbo_group_count": len(pbo_groups),
        "family_test_group_count": len(family),
        "seed_group_count": len(seeds),
        "promotion_allowed": any(g["promotion_allowed"] for g in gates.values()),
        "stage_c_allowed": any(g["promotion_allowed"] for g in gates.values()),
        "stage_c_blocked_reason": "" if any(g["promotion_allowed"] for g in gates.values()) else "NO_STAGE_B_CANDIDATE_PASSED_ALL_STATISTICAL_GATES",
    }
    # Backward-compatible aliases for older synthesis/report workers.
    summary.update({
        "trace_found": summary["evidence_pass"],
        "trace_missing": summary["evidence_fail"],
        "dsr_pass": summary["dsr_pass_n_raw"],
        "dsr_fail": summary["dsr_fail_n_raw"],
        "trial_count_for_deflation": n_raw,
        "statistical_governance_status": "PASS" if summary["promotion_allowed"] else "BLOCKED",
    })

    report = {
        "summary": summary,
        "candidate_gates": gates,
        "pbo_groups": pbo_groups,
        "family_tests": family,
        "seed_uncertainty": seeds,
        "records": [public_record(record) for record in records],
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    blocker_counts = Counter(reason for gate in gates.values() for reason in gate["blocking_reasons"])
    lines = [
        "# Stage B Statistical Governance Evaluation",
        "",
        f"Generated UTC: `{summary['generated_at_utc']}`",
        f"Evidence files: `{summary['evidence_files']}`",
        f"Evidence pass/fail: `{summary['evidence_pass']}` / `{summary['evidence_fail']}`",
        f"DSR pass/fail using N_raw: `{summary['dsr_pass_n_raw']}` / `{summary['dsr_fail_n_raw']}`",
        f"Candidate gates pass/fail: `{summary['candidate_gate_pass']}` / `{summary['candidate_gate_fail']}`",
        f"Stage C allowed: `{summary['stage_c_allowed']}`",
        "",
        "## Candidate Gate Blockers",
        "",
        "| Blocker | Count |",
        "| --- | ---: |",
    ]
    for reason, count in sorted(blocker_counts.items()):
        lines.append(f"| {reason} | {count} |")
    lines.extend([
        "",
        "## Method Notes",
        "",
        "- DSR uses per-bar net returns, skewness, non-excess kurtosis, and both raw/effective trial counts.",
        f"- Evidence discovery includes `{STAGE_B_RUNS}`, pragmatic outputs under `{PRAGMATIC_STAGE_B_PLANS}`, session-calendar outputs under `{SESSION_CALENDAR_STAGE_B_PLANS}`, force-close observation outputs under `{FORCE_CLOSE_OBS_STAGE_B_PLANS}`, and force-close penalty outputs under `{FORCE_CLOSE_PENALTY_STAGE_B_PLANS}`.",
        f"- Cost coverage accepts either legacy `{sorted(LEGACY_REQUIRED_COST_SCENARIOS)}` or pragmatic `{sorted(PRAGMATIC_REQUIRED_COST_SCENARIOS)}` contracts.",
        "- PBO is contiguous-fold PBO-lite over available traces; full purged retraining CSCV still requires a dedicated Stage B runner.",
        "- White Reality Check / SPA are implemented as deterministic stationary-bootstrap family tests against matched `baseline_12` traces where available.",
        "- Seed uncertainty is fail-closed until at least five paired seeds exist for each candidate/cost scenario.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
