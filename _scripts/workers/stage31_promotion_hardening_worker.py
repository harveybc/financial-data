#!/usr/bin/env python3
"""
Stage 3.1 Promotion Hardening Worker

Evaluates every Stage A run against the governance gates defined in:
  - experiments/design/stage_b_promotion_gate.yaml
  - experiments/design/leakage_audit.md
  - experiments/design/cost_model.md
  - experiments/design/multiple_testing_correction.md
  - work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md §1.0

No run may advance to Stage B until this worker reports zero blockers for it.

Run:
  python _scripts/workers/stage31_promotion_hardening_worker.py

Outputs (all under experiments/stage_a_screening/hardening/):
  SPEC.md                           Evaluator scope and known gaps
  PLAN.md                           Data flow, checks, scoring, output schema
  TASKS.md                          Completed, skipped, and next tasks
  promotion_candidates.csv          Per-run classification table
  promotion_hardening_report.md     Human-readable governance report
  promotion_hardening_report.json   Machine-readable summary
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
STAGE_A_ROOT = ROOT / "experiments" / "stage_a_screening"
HARDENING_OUT = STAGE_A_ROOT / "hardening"
ARTIFACT_ROOT = ROOT / "artifacts"

INDEX_CSV = STAGE_A_ROOT / "index.csv"
LEDGER_JSONL = ARTIFACT_ROOT / "run_ledger.jsonl"
SIMPLE_BASELINE_CSV = HARDENING_OUT / "simple_baseline_results.csv"
FAMILY_ABLATION_JSON = HARDENING_OUT / "family_ablation_report.json"
LEAKAGE_HELDOUT_CSV = HARDENING_OUT / "leakage_heldout_audit.csv"

BEST_RUN_SLUG = (
    "ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave"
)

# ---------------------------------------------------------------------------
# Governance constants (sourced from configs/cost_scenarios.yaml and design docs)
# ---------------------------------------------------------------------------

# Cost scenarios in basis points per side.  Round-trip = 2x.
# Turnover penalty is a fraction of |gross_return| scaled by trade intensity.
# Source: configs/cost_scenarios.yaml v1 2026-05-02
COST_PARAMS: dict[str, dict[str, dict[str, float]]] = {
    "crypto_spot": {
        "optimistic": {"fee_bps": 2.0,  "spread_bps": 1.0, "slippage_bps": 1.0,  "turnover_penalty": 0.00},
        "base":       {"fee_bps": 5.0,  "spread_bps": 3.0, "slippage_bps": 3.0,  "turnover_penalty": 0.05},
        "pessimistic":{"fee_bps": 10.0, "spread_bps": 8.0, "slippage_bps": 8.0,  "turnover_penalty": 0.15},
    },
    "fx": {
        "optimistic": {"fee_bps": 0.2,  "spread_bps": 0.5, "slippage_bps": 0.2,  "turnover_penalty": 0.00},
        "base":       {"fee_bps": 0.5,  "spread_bps": 1.0, "slippage_bps": 0.5,  "turnover_penalty": 0.02},
        "pessimistic":{"fee_bps": 1.0,  "spread_bps": 3.0, "slippage_bps": 1.5,  "turnover_penalty": 0.08},
    },
}

# Simulation applied commission=0.0002 (2 bps) per side in the environment.
# Cost proxy deducts (scenario_cost - sim_cost) on top of reported total_return.
SIM_FEE_BPS = 2.0  # per side, as recorded in run configs

# Position fraction: configs use position_size=0.01 (1% of portfolio per trade).
POSITION_FRACTION = 0.01

VALID_ALGOS = {"ppo", "sac", "dqn"}
VALID_TIMEFRAMES = {"5m", "15m", "1h", "4h"}
VALID_PRESETS = {
    "baseline_12", "tech_full", "tech_stat", "tech_stat_decomp",
    "learned_lstm", "learned_cnn", "sota_low_cost",
    "crypto_full", "fx_full", "kitchen_sink_guarded",
}
VALID_MACHINES = {"omega", "dragon", "gamma"}

# Presets that use only the trading asset's own OHLCV-derived features.
# These do NOT require an availability/vintage contract for cross-source data.
OWN_ASSET_ONLY_PRESETS = {"baseline_12", "tech_full", "tech_stat", "tech_stat_decomp"}

# Promotion gate thresholds (from stage_b_promotion_gate.yaml)
MIN_SEEDS_FOR_PROMOTION = 2
CATASTROPHIC_PESSIMISTIC_THRESHOLD = -0.10  # net return below this = catastrophic collapse

# DSR: n_trials used for multiple-testing penalty is the total ledger trial count.
# This is a conservative estimate; the true N for DSR should be the number of
# independent strategy candidates tested, which we approximate as trial_count.
DSR_N_TRIALS_FALLBACK = 672  # from run_ledger_summary.json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def fmt(value: Any, digits: int = 4) -> str:
    v = safe_float(value)
    if v is None:
        return "—"
    return f"{v:.{digits}f}"


def get_asset_class(asset: str) -> str:
    a = asset.lower()
    if a.endswith("usdt") or "_perp" in a or a.endswith("perp"):
        return "crypto_spot"
    return "fx"


def _mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return statistics.fmean(values)


def _agg(values: list[float]) -> dict[str, float | None]:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"mean": None, "median": None, "std": None, "min": None, "max": None, "n": 0}
    return {
        "mean":   statistics.fmean(clean),
        "median": statistics.median(clean),
        "std":    statistics.stdev(clean) if len(clean) > 1 else 0.0,
        "min":    min(clean),
        "max":    max(clean),
        "n":      len(clean),
    }


# ---------------------------------------------------------------------------
# Step 1 – Load Stage A index
# ---------------------------------------------------------------------------

def load_stage_a_index() -> list[dict]:
    """Load experiments/stage_a_screening/index.csv."""
    if not INDEX_CSV.exists():
        print(f"[ERROR] Stage A index not found: {INDEX_CSV}", file=sys.stderr)
        sys.exit(1)
    rows: list[dict] = []
    with INDEX_CSV.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(dict(row))
    print(f"[INFO] Loaded {len(rows)} Stage A runs from {INDEX_CSV}")
    return rows


# ---------------------------------------------------------------------------
# Step 2 – Load run ledger
# ---------------------------------------------------------------------------

def load_run_ledger() -> list[dict]:
    """Load artifacts/run_ledger.jsonl (immutable append-only ledger)."""
    if not LEDGER_JSONL.exists():
        print(f"[WARN] Ledger not found: {LEDGER_JSONL}. All runs will be KILL_LEDGER_MISSING.", file=sys.stderr)
        return []
    events: list[dict] = []
    for line in LEDGER_JSONL.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    print(f"[INFO] Loaded {len(events)} ledger events from {LEDGER_JSONL}")
    return events


# ---------------------------------------------------------------------------
# Step 3 – Verify ledger membership
# ---------------------------------------------------------------------------

def _build_ledger_index(events: list[dict]) -> dict[str, Any]:
    """Index ledger by (asset, timeframe, algorithm, feature_preset, seed)."""
    by_config: dict[tuple, list[dict]] = defaultdict(list)
    for ev in events:
        asset   = str(ev.get("asset", "")).lower()
        tf      = str(ev.get("timeframe", ""))
        algo    = str(ev.get("algorithm", "")).lower()
        preset  = str(ev.get("feature_preset", ""))
        try:
            seed = int(ev.get("seed", 0))
        except (TypeError, ValueError):
            seed = 0
        by_config[(asset, tf, algo, preset, seed)].append(ev)
    return {
        "by_config": dict(by_config),
        "event_count": len(events),
        "trial_ids": {str(ev.get("trial_id", "")) for ev in events if ev.get("trial_id")},
    }


def verify_ledger_membership(row: dict, ledger_index: dict) -> tuple[bool, str]:
    """
    Return (is_member, detail_message).
    A run is a ledger member if at least one complete event exists for its
    (asset, timeframe, algo, preset, seed) combination.
    Missing evidence is treated as a blocker, not a pass.
    """
    asset  = str(row.get("asset", "")).lower()
    tf     = str(row.get("timeframe", ""))
    algo   = str(row.get("algo", "")).lower()
    preset = str(row.get("preset", ""))
    try:
        seed = int(row.get("seed", 0))
    except (TypeError, ValueError):
        seed = 0

    key    = (asset, tf, algo, preset, seed)
    events = ledger_index["by_config"].get(key, [])

    if not events:
        return False, f"No ledger events for ({asset},{tf},{algo},{preset},s{seed})"

    complete = [
        e for e in events
        if e.get("event_type") == "complete" or e.get("status") == "complete"
    ]
    if not complete:
        statuses = sorted({str(e.get("status", "?")) for e in events})
        return False, (
            f"Ledger events exist for ({asset},{tf},{algo},{preset},s{seed}) "
            f"but none are complete — statuses: {statuses}"
        )
    return True, f"{len(complete)} complete ledger event(s) for ({asset},{tf},{algo},{preset},s{seed})"


# ---------------------------------------------------------------------------
# Step 4 – Validate required metadata
# ---------------------------------------------------------------------------

def validate_required_metadata(row: dict) -> tuple[bool, list[str]]:
    """
    Check that asset, timeframe, algorithm, preset, seed, and machine are
    present and belong to the approved experiment matrix.
    Returns (is_valid, list_of_failures).
    """
    failures: list[str] = []

    asset   = str(row.get("asset", "")).lower()
    tf      = str(row.get("timeframe", ""))
    algo    = str(row.get("algo", "")).lower()
    preset  = str(row.get("preset", ""))
    machine = str(row.get("machine", "")).lower()
    seed    = row.get("seed", "")

    if not asset or asset in {"", "unknown"}:
        failures.append("asset: missing or unknown")
    if tf not in VALID_TIMEFRAMES:
        failures.append(f"timeframe '{tf}' not in approved set {sorted(VALID_TIMEFRAMES)}")
    if algo not in VALID_ALGOS:
        failures.append(f"algorithm '{algo}' not in approved set {sorted(VALID_ALGOS)}")
    if preset not in VALID_PRESETS:
        failures.append(f"preset '{preset}' not in approved preset list")
    if machine not in VALID_MACHINES:
        failures.append(f"machine '{machine}' not in approved machines {sorted(VALID_MACHINES)}")
    if seed == "" or seed is None:
        failures.append("seed: missing")

    return len(failures) == 0, failures


# ---------------------------------------------------------------------------
# Step 5 – Find matched baselines
# ---------------------------------------------------------------------------

def find_matched_baselines(row: dict, all_rows: list[dict]) -> list[dict]:
    """
    Find baseline_12 runs matching (asset, timeframe, algo, seed).
    Matching seed is required for paired uplift (same market conditions, same seed).
    """
    asset  = str(row.get("asset", "")).lower()
    tf     = str(row.get("timeframe", ""))
    algo   = str(row.get("algo", "")).lower()
    slug   = str(row.get("run_slug", ""))
    try:
        seed = int(row.get("seed", 0))
    except (TypeError, ValueError):
        seed = 0

    matches: list[dict] = []
    for other in all_rows:
        if str(other.get("run_slug", "")) == slug:
            continue
        if other.get("preset") != "baseline_12":
            continue
        if str(other.get("asset", "")).lower() != asset:
            continue
        if str(other.get("timeframe", "")) != tf:
            continue
        if str(other.get("algo", "")).lower() != algo:
            continue
        try:
            other_seed = int(other.get("seed", -99))
        except (TypeError, ValueError):
            other_seed = -99
        if other_seed == seed:
            matches.append(other)
    return matches


# ---------------------------------------------------------------------------
# Step 6 – Compute cost proxy
# ---------------------------------------------------------------------------

def compute_cost_proxy(row: dict) -> dict[str, float | None]:
    """
    Compute net-return proxies under optimistic, base, and pessimistic cost scenarios.

    Method:
        The simulation environment already applied commission = SIM_FEE_BPS per side.
        We compute the ADDITIONAL deduction required to reach each real-world scenario:

            extra_bps_per_side = scenario_fee + spread + slippage - SIM_FEE_BPS
            cost_per_roundtrip = max(0, extra_bps_per_side * 2) / 10000 * POSITION_FRACTION
            total_friction      = trades * cost_per_roundtrip
            turnover_contribution = |gross| * turnover_penalty * clamp(trades / 200, 0, 1)
            net = gross - total_friction - turnover_contribution

    Returns dict with scenario keys and float net-return values.
    Caveats (recorded in SPEC.md):
    - We assume POSITION_FRACTION = 0.01 uniformly; actual trade notional may differ.
    - Spread and slippage may be partially captured by the sim env; we conservatively
      treat them as additional deductions.
    - The turnover_penalty is an approximation; actual holding-period costs depend on
      leverage, carry, and financing details not present in summary.json.
    """
    gross  = safe_float(row.get("total_return"))
    trades = int(row.get("trades_total") or 0)
    asset  = str(row.get("asset", "")).lower()
    asset_class = get_asset_class(asset)
    params = COST_PARAMS.get(asset_class, COST_PARAMS["fx"])

    if gross is None:
        return {"optimistic": None, "base": None, "pessimistic": None, "asset_class": asset_class}

    results: dict[str, float | None] = {"asset_class": asset_class}
    for scenario, p in params.items():
        extra_per_side = p["fee_bps"] + p["spread_bps"] + p["slippage_bps"] - SIM_FEE_BPS
        per_roundtrip  = max(0.0, extra_per_side * 2.0) / 10000.0 * POSITION_FRACTION
        total_friction = trades * per_roundtrip

        # Turnover penalty scales with trade intensity relative to a 200-trade reference.
        trade_intensity = min(1.0, trades / 200.0) if trades > 0 else 0.0
        turnover_cost   = abs(gross) * p["turnover_penalty"] * trade_intensity

        net = gross - total_friction - turnover_cost
        results[scenario] = round(net, 8)
    return results


# ---------------------------------------------------------------------------
# Step 7 – Compute paired uplift
# ---------------------------------------------------------------------------

def compute_paired_uplift(row: dict, baselines: list[dict]) -> dict[str, Any]:
    """
    Compute Δ total_return, Δ Sharpe, Δ drawdown vs matched baseline_12.
    Missing baseline is treated as a blocker, not a pass.
    """
    if not baselines:
        return {
            "has_baseline": False,
            "uplift_total_return": None,
            "uplift_sharpe_ratio": None,
            "uplift_max_drawdown_pct": None,
            "baseline_slug": None,
            "baseline_return": None,
            "baseline_sharpe": None,
            "note": "BLOCKER: no matched baseline_12 run for (asset, timeframe, algo, seed)",
        }

    baseline = baselines[0]
    cand_ret  = safe_float(row.get("total_return"))
    base_ret  = safe_float(baseline.get("total_return"))
    cand_sr   = safe_float(row.get("sharpe_ratio"))
    base_sr   = safe_float(baseline.get("sharpe_ratio"))
    cand_dd   = safe_float(row.get("max_drawdown_pct"))
    base_dd   = safe_float(baseline.get("max_drawdown_pct"))

    return {
        "has_baseline": True,
        "uplift_total_return": (
            round(cand_ret - base_ret, 8) if cand_ret is not None and base_ret is not None else None
        ),
        "uplift_sharpe_ratio": (
            round(cand_sr - base_sr, 8) if cand_sr is not None and base_sr is not None else None
        ),
        "uplift_max_drawdown_pct": (
            round(cand_dd - base_dd, 8) if cand_dd is not None and base_dd is not None else None
        ),
        "baseline_slug":   str(baseline.get("run_slug", "")),
        "baseline_return": base_ret,
        "baseline_sharpe": base_sr,
        "note": "Matched baseline_12 found with same (asset, timeframe, algo, seed)",
    }


# ---------------------------------------------------------------------------
# Step 8 – Group statistics
# ---------------------------------------------------------------------------

def compute_group_statistics(rows: list[dict], group_key: str) -> list[dict]:
    """
    Mean, median, std, min, max for return, Sharpe, drawdown, and trades,
    grouped by group_key (e.g. "preset", "asset", "algo").
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_key, "unknown"))].append(row)

    result: list[dict] = []
    for name in sorted(buckets):
        items = buckets[name]

        def collect(field: str) -> list[float]:
            return [v for v in [safe_float(x.get(field)) for x in items] if v is not None]

        n_pos = sum(1 for x in items if (safe_float(x.get("total_return")) or -1) > 0)

        result.append({
            group_key:         name,
            "n_runs":          len(items),
            "n_positive_return": n_pos,
            "return":          _agg(collect("total_return")),
            "sharpe":          _agg(collect("sharpe_ratio")),
            "drawdown_pct":    _agg(collect("max_drawdown_pct")),
            "trades":          _agg(collect("trades_total")),
        })
    return result


# ---------------------------------------------------------------------------
# Step 9 – Seed dispersion
# ---------------------------------------------------------------------------

def compute_seed_dispersion(rows: list[dict]) -> list[dict]:
    """
    For each (asset, timeframe, algo, preset) group with ≥ 2 seeds,
    report return mean, std, min, max and Sharpe mean, std across seeds.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("asset", "")),
            str(row.get("timeframe", "")),
            str(row.get("algo", "")),
            str(row.get("preset", "")),
        )
        groups[key].append(row)

    result: list[dict] = []
    for (asset, tf, algo, preset), items in sorted(groups.items()):
        if len(items) < 2:
            continue
        returns = [v for v in [safe_float(r.get("total_return")) for r in items] if v is not None]
        sharpes = [v for v in [safe_float(r.get("sharpe_ratio")) for r in items] if v is not None]
        seeds   = [str(r.get("seed", "?")) for r in items]
        result.append({
            "asset":        asset,
            "timeframe":    tf,
            "algo":         algo,
            "preset":       preset,
            "n_seeds":      len(items),
            "seeds":        sorted(seeds),
            "return_mean":  statistics.fmean(returns) if returns else None,
            "return_std":   statistics.stdev(returns) if len(returns) > 1 else 0.0,
            "return_min":   min(returns) if returns else None,
            "return_max":   max(returns) if returns else None,
            "sharpe_mean":  statistics.fmean(sharpes) if sharpes else None,
            "sharpe_std":   statistics.stdev(sharpes) if len(sharpes) > 1 else 0.0,
        })
    return result


# ---------------------------------------------------------------------------
# Step 10 – Bootstrap CI
# ---------------------------------------------------------------------------

def compute_bootstrap_ci(
    rows: list[dict],
    group_key: str = "preset",
    n_boot: int = 2000,
    ci: float = 0.95,
    min_samples: int = 5,
) -> list[dict]:
    """
    Nonparametric bootstrap CI for total_return grouped by group_key.
    Uses a fixed seed (42) for reproducibility.
    Requires ≥ min_samples observations per group.
    """
    rng = random.Random(42)
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        key = str(row.get(group_key, "unknown"))
        v = safe_float(row.get("total_return"))
        if v is not None:
            buckets[key].append(v)

    alpha  = (1.0 - ci) / 2.0
    result: list[dict] = []
    for name in sorted(buckets):
        values = buckets[name]
        n      = len(values)
        if n < min_samples:
            result.append({
                group_key:  name,
                "n":        n,
                "mean":     statistics.fmean(values) if values else None,
                "ci_lo":    None,
                "ci_hi":    None,
                "ci_level": ci,
                "note":     f"Too few samples (n={n} < {min_samples}); CI not computed",
            })
            continue

        boot_means: list[float] = []
        for _ in range(n_boot):
            sample = [rng.choice(values) for _ in range(n)]
            boot_means.append(statistics.fmean(sample))
        boot_means.sort()
        lo_idx = max(0, int(alpha * n_boot))
        hi_idx = min(n_boot - 1, int((1.0 - alpha) * n_boot))
        result.append({
            group_key:  name,
            "n":        n,
            "mean":     statistics.fmean(values),
            "ci_lo":    boot_means[lo_idx],
            "ci_hi":    boot_means[hi_idx],
            "ci_level": ci,
            "n_boot":   n_boot,
            "note":     f"{int(ci*100)}% bootstrap CI for total_return ({n_boot} resamples, seed=42)",
        })
    return result


# ---------------------------------------------------------------------------
# Step 11 – DSR approximation
# ---------------------------------------------------------------------------

def compute_dsr_placeholder_or_approximation(row: dict, n_trials: int) -> dict[str, Any]:
    """
    Approximate Deflated Sharpe Ratio (Lopez de Prado 2018, Advances in FML ch.8).

    Full DSR formula:
        DSR = (SR_obs − E[max SR | N]) > 0
    where E[max SR | N] accounts for skewness, kurtosis, T, and trial count N.

    This implementation uses a Bonferroni-style correction for the expected
    maximum SR under N independent trials:
        E_max ≈ sqrt(2 * log(N))   [extreme-value approximation for large N]

    Caveats (documented in SPEC.md):
    1. The sharpe_ratio column is NOT annualized. It is an episode-level metric
       computed by the backtesting engine, not from a daily return series.
    2. We lack the return time-series, so skewness and kurtosis corrections
       (which typically reduce DSR by 10–40%) cannot be applied.
    3. The N=672 trial_count includes both complete and incomplete trials; the
       true independent strategy count is lower, making this conservative.
    4. Trials are NOT independent (same asset, same period, correlated returns),
       so E_max overestimates the true correction — this is conservative.
    5. Do NOT cite this as a rigorous DSR for promotion decisions.
    """
    sr_obs = safe_float(row.get("sharpe_ratio"))
    if sr_obs is None:
        return {
            "dsr_approx": None,
            "dsr_status": "not_computable",
            "dsr_note": "sharpe_ratio is missing or non-finite",
            "n_trials": n_trials,
        }

    # E[max SR | N independent Sharpe estimates] ≈ sqrt(2 * log(N)) for large N
    if n_trials <= 1:
        expected_max = 0.0
    else:
        expected_max = math.sqrt(2.0 * math.log(max(1, n_trials)))

    dsr_approx = sr_obs - expected_max

    return {
        "dsr_approx":             round(dsr_approx, 6),
        "sr_obs":                 sr_obs,
        "expected_max_sr":        round(expected_max, 6),
        "n_trials":               n_trials,
        "dsr_exceeds_threshold":  bool(dsr_approx > 0.0),
        "dsr_status":             "approximate_directional_only",
        "dsr_note": (
            "APPROXIMATION ONLY. Full DSR requires annualized return series with "
            "skewness/kurtosis corrections. This uses a Bonferroni extreme-value "
            "correction: E_max = sqrt(2*log(N)) for N independent trials. "
            "SR is episode-level, not annualized. Do not use for formal promotion claims."
        ),
    }


# ---------------------------------------------------------------------------
# Step 12 – PBO placeholder
# ---------------------------------------------------------------------------

def compute_pbo_placeholder() -> dict[str, Any]:
    """
    Probability of Backtest Overfitting / CSCV diagnostic.

    Stage A runs each use a single train/validation split.  CSCV requires
    multiple combinatorial folds of the SAME strategy evaluated on the SAME
    data with different IS/OOS partitions.  That structure does not exist here.

    Required at Stage B where longer runs and subperiod slicing become feasible.
    """
    return {
        "pbo_status":   "not_enough_structure",
        "cscv_status":  "not_enough_structure",
        "required_for_stage_b": True,
        "note": (
            "PBO/CSCV deferred. Stage A uses a single train split per run; "
            "no combinatorial fold structure exists. "
            "Implement at Stage B using purged k-fold or CSCV on 1M-step runs."
        ),
    }


# ---------------------------------------------------------------------------
# Step 13 – Classify candidate
# ---------------------------------------------------------------------------

def _count_seeds_for_config(row: dict, all_rows: list[dict]) -> int:
    """Count how many seeds have been run for (asset, timeframe, algo, preset)."""
    asset  = str(row.get("asset", "")).lower()
    tf     = str(row.get("timeframe", ""))
    algo   = str(row.get("algo", "")).lower()
    preset = str(row.get("preset", ""))
    seeds  = set()
    for other in all_rows:
        if (
            str(other.get("asset", "")).lower() == asset
            and str(other.get("timeframe", "")) == tf
            and str(other.get("algo", "")).lower() == algo
            and str(other.get("preset", "")) == preset
        ):
            seeds.add(str(other.get("seed", "?")))
    return len(seeds)


def load_b8_evidence() -> dict[str, str]:
    """
    Load B8 evidence from simple_baseline_results.csv if it exists.
    Returns a dict mapping run_slug → b8_evidence string.
    If the CSV does not exist, returns an empty dict (B8 remains NOT_COMPUTED).
    """
    if not SIMPLE_BASELINE_CSV.exists():
        return {}
    evidence: dict[str, str] = {}
    try:
        with open(SIMPLE_BASELINE_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # The CSV has one row per (run, strategy); we need the per-run verdict.
            # Re-derive it: if any strategy row for the run has status OK and
            # the run's rl return is positive, we trust the JSON report.
            # Simpler: read the JSON report if available.
            pass
    except Exception:
        pass

    # Prefer the JSON report which has the per-run b8_evidence field.
    json_path = HARDENING_OUT / "simple_baseline_report.json"
    if not json_path.exists():
        return {}
    try:
        with open(json_path, encoding="utf-8") as f:
            report = json.load(f)
        for cmp in report.get("all_run_comparisons", []):
            slug = cmp.get("run_slug", "")
            b8ev = cmp.get("b8_evidence", "INDETERMINATE")
            if slug:
                evidence[slug] = b8ev
    except Exception:
        pass
    return evidence


def load_b9_evidence() -> dict[str, str]:
    """
    Load B9 feature-family ablation evidence from family_ablation_report.json.

    If the report does not exist, returns an empty dict and B9 remains blocked.
    """
    evidence: dict[str, str] = {}
    if not FAMILY_ABLATION_JSON.exists():
        return evidence
    try:
        with FAMILY_ABLATION_JSON.open(encoding="utf-8") as fh:
            report = json.load(fh)
        for item in report.get("all_run_comparisons", []):
            slug = str(item.get("run_slug", ""))
            b9ev = str(item.get("b9_evidence", "INDETERMINATE"))
            if slug:
                evidence[slug] = b9ev
    except Exception:
        pass
    return evidence


def load_leakage_heldout_evidence() -> dict[str, dict[str, str]]:
    """
    Load B1/B10 evidence from leakage_heldout_audit.csv.

    Returns a map:
      run_slug -> {"b1": status, "b10": status, "detail": short detail}
    """
    evidence: dict[str, dict[str, str]] = {}
    if not LEAKAGE_HELDOUT_CSV.exists():
        return evidence
    try:
        with LEAKAGE_HELDOUT_CSV.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                slug = str(row.get("run_slug", ""))
                if not slug:
                    continue
                status = str(row.get("status", ""))
                heldout = str(row.get("b1_heldout_ts_check", ""))
                checks = [
                    str(row.get("b1_transform_check", "")),
                    str(row.get("b1_scaler_check", "")),
                    str(row.get("b1_autoencoder_check", "")),
                    str(row.get("b1_macro_check", "")),
                ]
                ok_values = {"PASS", "NOT_APPLICABLE"}
                if status == "FAIL_HELDOUT_LEAKAGE":
                    b10 = "FAIL"
                elif str(row.get("b10_firewall_cleared", "")).lower() == "true":
                    b10 = "PASS"
                elif status == "BLOCKED_INPUT_MISSING":
                    b10 = "BLOCKED_INPUT_MISSING"
                else:
                    b10 = "INDETERMINATE"

                if heldout == "PASS" and all(c in ok_values for c in checks):
                    b1 = "PASS"
                elif heldout == "PASS":
                    b1 = "PARTIAL_PASS"
                elif status == "FAIL_HELDOUT_LEAKAGE":
                    b1 = "FAIL"
                elif status == "BLOCKED_INPUT_MISSING":
                    b1 = "BLOCKED_INPUT_MISSING"
                else:
                    b1 = "INDETERMINATE"

                evidence[slug] = {
                    "b1": b1,
                    "b10": b10,
                    "detail": (
                        f"status={status}; min_ts={row.get('min_ts', '')}; "
                        f"max_ts={row.get('max_ts', '')}; b1_overall={row.get('b1_overall', '')}"
                    ),
                }
    except Exception:
        pass
    return evidence


def classify_candidate(
    row: dict,
    ledger_ok: bool,
    ledger_detail: str,
    metadata_ok: bool,
    metadata_failures: list[str],
    cost_proxy: dict,
    paired_uplift: dict,
    n_seeds: int,
    b8_evidence: str = "NOT_COMPUTED",
    b9_evidence: str = "NOT_COMPUTED",
    b1_evidence: str = "NOT_COMPUTED",
    b10_evidence: str = "NOT_COMPUTED",
    leakage_detail: str = "",
) -> tuple[str, list[str], list[str]]:
    """
    Assign a deterministic classification status and enumerate blockers.

    Status hierarchy (applied in order):
      KILL_LEDGER_MISSING       — not in immutable ledger
      KILL_INVALID_METRICS      — metadata validation failed
      KILL_NO_TRADES            — degenerate no-trade policy
      KILL_NON_POSITIVE_RETURN  — total_return ≤ 0 OR base-cost net ≤ 0
      KILL_NEGATIVE_SHARPE      — sharpe_ratio < 0
      PROMOTE_BLOCKED_HARDENING — survives KILLs but has unresolved governance blockers

    Secondary watch flags (additive, never replace primary status):
      WATCH_NEEDS_BASELINE
      WATCH_NEEDS_SEEDS
      WATCH_COST_FRAGILE

    Returns (status, blockers, watch_flags).
    """
    blockers:    list[str] = []
    watch_flags: list[str] = []

    # --- KILL: ledger ---
    if not ledger_ok:
        return "KILL_LEDGER_MISSING", [f"Ledger: {ledger_detail}"], []

    # --- KILL: metadata ---
    if not metadata_ok:
        return "KILL_INVALID_METRICS", [f"Metadata: {'; '.join(metadata_failures)}"], []

    total_return  = safe_float(row.get("total_return"))
    sharpe        = safe_float(row.get("sharpe_ratio"))
    max_dd        = safe_float(row.get("max_drawdown_pct"))
    trades        = int(row.get("trades_total") or 0)

    # --- KILL: no trades (checked before missing-metrics because no-trade runs have
    #     empty sharpe_ratio which parses as None — that is a consequence of no trades,
    #     not an independent data quality failure) ---
    if trades == 0:
        return "KILL_NO_TRADES", ["trades_total == 0; degenerate no-trade policy"], []

    # --- KILL: missing finite metrics (after no-trade check) ---
    if total_return is None or sharpe is None or max_dd is None:
        return "KILL_INVALID_METRICS", [
            "total_return, sharpe_ratio, or max_drawdown_pct is missing/non-finite"
        ], []

    # --- KILL: non-positive gross return ---
    if total_return <= 0:
        return "KILL_NON_POSITIVE_RETURN", [
            f"total_return={total_return:.6f} ≤ 0"
        ], []

    # --- KILL: negative Sharpe ---
    if sharpe < 0:
        return "KILL_NEGATIVE_SHARPE", [f"sharpe_ratio={sharpe:.6f} < 0"], []

    # --- KILL: non-positive under base cost ---
    base_net = cost_proxy.get("base")
    if base_net is not None and base_net <= 0:
        return "KILL_NON_POSITIVE_RETURN", [
            f"Positive gross ({total_return:.6f}) but base-cost proxy net ≤ 0 ({base_net:.6f}). "
            "Per cost_model.md: reject candidates non-positive under base cost."
        ], []

    # ---- All KILL criteria passed; enumerate governance blockers ----

    # B1: Leakage audit
    if b1_evidence == "PASS":
        pass
    elif b1_evidence == "PARTIAL_PASS":
        blockers.append(
            "B1_LEAKAGE_AUDIT: Heldout timestamp check passed, but some fitted-transform "
            f"or source-availability subchecks are deferred/incomplete. {leakage_detail}"
        )
    elif b1_evidence == "FAIL":
        return "KILL_LEAKAGE", [f"B1 leakage audit failed. {leakage_detail}"], []
    elif b1_evidence == "BLOCKED_INPUT_MISSING":
        blockers.append(
            "B1_LEAKAGE_AUDIT: Input CSV missing, so heldout and fitted-transform checks "
            f"cannot be verified. {leakage_detail}"
        )
    else:
        blockers.append(
            "B1_LEAKAGE_AUDIT: leakage_heldout_audit.csv evidence not found for this run. "
            "Run stage31_leakage_heldout_audit_worker.py."
        )

    # B2: Availability/vintage contract — required for cross-source presets
    preset = str(row.get("preset", ""))
    if preset not in OWN_ASSET_ONLY_PRESETS:
        blockers.append(
            f"B2_AVAILABILITY_CONTRACT: preset '{preset}' may include cross-source features. "
            "features/AVAILABILITY_CONTRACT.md must be verified per Rule P3.6."
        )

    # B3: DSR — always a blocker (approximation only, not rigorous)
    blockers.append(
        "B3_DSR: Deflated Sharpe Ratio not rigorously computed. "
        "Requires annualized return series with skewness/kurtosis. "
        "Current approximation is directional only and not sufficient for promotion."
    )

    # B4: PBO/CSCV — always a blocker at Stage A
    blockers.append(
        "B4_PBO: PBO/CSCV not feasible with Stage A single-split structure. "
        "Deferred to Stage B per multiple_testing_correction.md."
    )

    # B5: Baseline / paired uplift
    if not paired_uplift.get("has_baseline"):
        blockers.append(
            "B5_BASELINE: No matched baseline_12 run found for same "
            "(asset, timeframe, algo, seed). Paired uplift cannot be computed. "
            "Per stage_b_promotion_gate.yaml: matched_baseline is required."
        )
        watch_flags.append("WATCH_NEEDS_BASELINE")
    else:
        uplift_ret = paired_uplift.get("uplift_total_return")
        if uplift_ret is not None and uplift_ret <= 0:
            blockers.append(
                f"B5_BASELINE_UPLIFT: Paired uplift vs baseline_12 is non-positive "
                f"(Δreturn={uplift_ret:.6f}). Not promotable without positive paired evidence."
            )

    # B6: Seed dispersion — requires ≥ MIN_SEEDS_FOR_PROMOTION seeds
    if n_seeds < MIN_SEEDS_FOR_PROMOTION:
        blockers.append(
            f"B6_SEEDS: Only {n_seeds} seed(s) run; minimum {MIN_SEEDS_FOR_PROMOTION} required "
            "for seed dispersion report (stage_b_promotion_gate.yaml §uncertainty)."
        )
        watch_flags.append("WATCH_NEEDS_SEEDS")

    # B7: Pessimistic cost fragility (warn, not kill, but a blocker for Stage B)
    pessimistic_net = cost_proxy.get("pessimistic")
    if pessimistic_net is not None:
        if pessimistic_net <= CATASTROPHIC_PESSIMISTIC_THRESHOLD:
            blockers.append(
                f"B7_COST_FRAGILE: Catastrophic collapse under pessimistic cost proxy "
                f"(net={pessimistic_net:.6f} ≤ {CATASTROPHIC_PESSIMISTIC_THRESHOLD}). "
                "Stage B requires pessimistic cost not catastrophic per promotion gate."
            )
            watch_flags.append("WATCH_COST_FRAGILE")
        elif pessimistic_net < 0:
            blockers.append(
                f"B7_COST_FRAGILE: Negative under pessimistic cost proxy "
                f"(net={pessimistic_net:.6f}). Stage B must report pessimistic scenario."
            )
            watch_flags.append("WATCH_COST_FRAGILE")

    # B8: Baseline comparison — check if simple_baseline_worker has run
    if b8_evidence == "PASS":
        pass  # B8 cleared for this run
    elif b8_evidence == "PARTIAL_PASS":
        blockers.append(
            "B8_SIMPLE_BASELINES: Beats best simple baseline at base_cost but "
            "pessimistic_cost verdict incomplete. See simple_baseline_report.md."
        )
    elif b8_evidence == "INDETERMINATE":
        blockers.append(
            "B8_SIMPLE_BASELINES: Beats best baseline at base_cost but fails "
            "pessimistic_cost check. Review simple_baseline_report.md before promotion."
        )
    elif b8_evidence == "FAIL":
        blockers.append(
            "B8_SIMPLE_BASELINES: Does NOT beat the best simple baseline at base_cost. "
            "See simple_baseline_report.md for details."
        )
    elif b8_evidence == "BLOCKED_NO_BASELINES":
        blockers.append(
            "B8_SIMPLE_BASELINES: No input CSV available for baseline computation. "
            "Run stage31_simple_baseline_worker.py after generating train.csv inputs."
        )
    else:
        # NOT_COMPUTED or unknown
        blockers.append(
            "B8_SIMPLE_BASELINES: No comparison against no-trade, buy-and-hold, "
            "random/turnover-matched random, simple momentum, or simple reversal "
            "has been computed. Run stage31_simple_baseline_worker.py first."
        )

    # B9: Feature-family ablation
    if b9_evidence == "PASS":
        pass
    elif b9_evidence == "PARTIAL_PASS":
        blockers.append(
            "B9_FAMILY_ABLATION: Partial matched family-ablation evidence exists, "
            "but it is not complete enough to clear the gate. See family_ablation_report.md."
        )
    elif b9_evidence == "FAIL":
        blockers.append(
            "B9_FAMILY_ABLATION: Matched feature-family ablation is negative. "
            "Candidate does not show positive marginal family value."
        )
    elif b9_evidence == "BLOCKED_NO_MATCH":
        blockers.append(
            "B9_FAMILY_ABLATION: Required matched ablation run is missing for this "
            "asset/timeframe/algo/seed. See family_ablation_report.md."
        )
    elif b9_evidence == "NOT_APPLICABLE":
        blockers.append(
            "B9_FAMILY_ABLATION: Baseline-only preset has no narrower feature-family "
            "ablation. It cannot be promoted as a feature-family winner."
        )
    else:
        blockers.append(
            "B9_FAMILY_ABLATION: Feature-family marginal contribution not reported. "
            "Run stage31_family_ablation_worker.py before promotion."
        )

    # B10: Heldout firewall
    if b10_evidence == "PASS":
        pass
    elif b10_evidence == "FAIL":
        return "KILL_LEAKAGE", [f"B10 heldout firewall failed. {leakage_detail}"], []
    elif b10_evidence == "BLOCKED_INPUT_MISSING":
        blockers.append(
            "B10_HELDOUT_FIREWALL: Input CSV missing; cannot prove 2025 heldout exclusion. "
            f"{leakage_detail}"
        )
    else:
        blockers.append(
            "B10_HELDOUT_FIREWALL: Heldout exclusion evidence not found for this run. "
            "Run stage31_leakage_heldout_audit_worker.py."
        )

    return "PROMOTE_BLOCKED_HARDENING", blockers, watch_flags


# ---------------------------------------------------------------------------
# Step 14 – Write outputs
# ---------------------------------------------------------------------------

def _write_spec() -> None:
    """Write SPEC.md — evaluator scope and known limitations."""
    content = """\
# Promotion Hardening Evaluator — SPEC

Generated: {ts}

## Purpose

This evaluator enforces the Stage A → Stage B promotion gate defined in:
- experiments/design/stage_b_promotion_gate.yaml
- experiments/design/leakage_audit.md
- experiments/design/cost_model.md
- experiments/design/multiple_testing_correction.md
- work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md §1.0 (SOTA Hardening Gate)

No run may advance to Stage B until all blockers are cleared.

## Checks Implemented

| Check | Status |
| --- | --- |
| Ledger membership (immutable record) | IMPLEMENTED |
| Required metadata validation (asset, tf, algo, preset, seed, machine) | IMPLEMENTED |
| total_return present and finite | IMPLEMENTED |
| sharpe_ratio present and finite | IMPLEMENTED |
| max_drawdown_pct present and finite | IMPLEMENTED |
| trades_total > 0 (no-trade detection) | IMPLEMENTED |
| Base-cost proxy positive | IMPLEMENTED |
| Pessimistic-cost proxy catastrophic collapse detection | IMPLEMENTED |
| Matched baseline_12 lookup | IMPLEMENTED |
| Paired uplift vs baseline_12 | IMPLEMENTED |
| Seed dispersion (≥ 2 seeds check) | IMPLEMENTED |
| Preset-level group statistics | IMPLEMENTED |
| Bootstrap CI for total_return by preset | IMPLEMENTED |
| DSR approximation (directional, not rigorous) | IMPLEMENTED (caveat-flagged) |
| PBO/CSCV placeholder | IMPLEMENTED (not_enough_structure) |

## Checks NOT Yet Implemented (Require External Evidence)

| Check | Reason | Blocking? |
| --- | --- | --- |
| Leakage audit (train timestamp exclusion, transform fit windows) | Requires inspecting input CSV timestamps and fitted-transform metadata | YES — all runs blocked |
| Availability/vintage contract for cross-source presets | Requires features/AVAILABILITY_CONTRACT.md per preset | YES — cross-source presets blocked |
| Rigorous DSR (annualized, with skewness/kurtosis) | Requires full per-bar return series, not available in summary.json | YES — approximation only |
| PBO/CSCV combinatorial cross-validation | Stage A has single-split; fold structure not available | YES — deferred to Stage B |
| Simple baseline comparisons (B&H, random, momentum) | Requires running baseline strategies on same data/period | YES — all runs blocked |
| Feature-family ablation (marginal contribution) | Requires matched runs with one family removed | YES — all runs blocked |
| 2025 heldout firewall verification | Requires timestamp audit of train.csv files | YES — all runs blocked |
| Regime-sliced performance | Requires regime labels or HMM regime assignments | Deferred to Stage B |
| Reality Check / SPA family tests | Requires family-level block bootstrap | Deferred to Stage B |

## Cost Proxy Model

Simulation environment applied commission=2 bps per side, slippage=0.
Cost proxy adds the delta from simulation to each real-world scenario:

    extra_bps = scenario_fee + spread + slippage - 2 bps (sim)
    cost = trades × max(0, extra_bps × 2) / 10000 × position_fraction (0.01)
    turnover_contribution = |gross| × turnover_penalty × min(1, trades/200)

This is a simplified proxy. Actual costs depend on execution quality, market
impact, holding period, and leverage. Do not treat as exact net performance.

## DSR Approximation Limitations

The DSR approximation uses:
    E[max SR | N] ≈ sqrt(2 × log(N))

Limitations:
1. SR is episode-level (backtesting engine), NOT annualized.
2. Skewness and kurtosis corrections are absent (no return series).
3. N = 672 trials (all ledger trials, not only competing strategies).
4. Trials are correlated (same asset/period), making E_max conservative.
5. Result is directional only — negative DSR_approx is a warning, not proof of overfit.

## PBO Limitation

Stage A uses a single train split. CSCV requires multiple combinatorial folds
of the same strategy on the same data. Implement at Stage B with purged k-fold.
""".format(ts=utc_now())
    (HARDENING_OUT / "SPEC.md").write_text(content, encoding="utf-8")
    print(f"[INFO] Wrote SPEC.md")


def _write_plan() -> None:
    """Write PLAN.md — data flow, checks, scoring logic."""
    content = """\
# Promotion Hardening Evaluator — PLAN

Generated: {ts}

## Data Flow

```
artifacts/run_ledger.jsonl          →  build_ledger_index()
experiments/stage_a_screening/      →  load_stage_a_index()
  index.csv
         │
         ├── verify_ledger_membership()      per run
         ├── validate_required_metadata()    per run
         ├── compute_cost_proxy()            per run × 3 scenarios
         ├── find_matched_baselines()        per run
         ├── compute_paired_uplift()         per run
         ├── classify_candidate()            per run → status + blockers
         │
         ├── compute_group_statistics()      by preset, asset, algo
         ├── compute_seed_dispersion()       by (asset, tf, algo, preset)
         ├── compute_bootstrap_ci()          by preset
         ├── compute_dsr_placeholder_or_approximation()  per surviving run
         └── compute_pbo_placeholder()       global placeholder
                   │
                   ▼
hardening/
  SPEC.md
  PLAN.md
  TASKS.md
  promotion_candidates.csv
  promotion_hardening_report.md
  promotion_hardening_report.json
```

## Validation Checks (in order)

### KILL Checks (immediate disqualifiers)

| Order | Check | Status assigned |
| --- | --- | --- |
| 1 | Run not in immutable ledger | KILL_LEDGER_MISSING |
| 2 | asset/tf/algo/preset/seed/machine invalid | KILL_INVALID_METRICS |
| 3 | total_return / sharpe / drawdown missing or non-finite | KILL_INVALID_METRICS |
| 4 | trades_total == 0 | KILL_NO_TRADES |
| 5 | total_return ≤ 0 | KILL_NON_POSITIVE_RETURN |
| 6 | sharpe_ratio < 0 | KILL_NEGATIVE_SHARPE |
| 7 | base-cost proxy net ≤ 0 | KILL_NON_POSITIVE_RETURN |

### Governance Blockers (after all KILLs pass)

| Blocker id | Check | Source |
| --- | --- | --- |
| B1 | Leakage audit not completed | leakage_audit.md |
| B2 | Availability contract not verified (cross-source presets) | Rule P3.6 |
| B3 | DSR not rigorous (no annualized return series) | multiple_testing_correction.md |
| B4 | PBO/CSCV not feasible at Stage A | multiple_testing_correction.md |
| B5 | No matched baseline_12 OR uplift ≤ 0 | stage_b_promotion_gate.yaml |
| B6 | Fewer than 2 seeds | stage_b_promotion_gate.yaml §uncertainty |
| B7 | Pessimistic cost: catastrophic or negative | cost_model.md |
| B8 | Simple baselines not compared | §1.3 Stage A deliverable |
| B9 | Feature-family ablation not reported | feature_family_ablation_plan.md |
| B10 | Heldout firewall not audited | leakage_audit.md §heldout_timestamp_exclusion |

### Secondary Watch Flags (additive)

| Flag | Trigger |
| --- | --- |
| WATCH_NEEDS_BASELINE | has_baseline = False |
| WATCH_NEEDS_SEEDS | n_seeds < 2 |
| WATCH_COST_FRAGILE | pessimistic_net < 0 |

## Scoring Logic

No numeric promotion score is computed. Classification is deterministic:
1. Apply KILL checks in order. First KILL terminates evaluation.
2. If no KILL: accumulate all governance blockers.
3. Assign PROMOTE_BLOCKED_HARDENING if any blocker exists.
4. Assign secondary watch flags independently.

## Output Schema

### promotion_candidates.csv

| Column | Description |
| --- | --- |
| run_slug | Unique run identifier |
| asset, timeframe, algo, preset, seed, machine | Experiment metadata |
| total_return | Gross return from summary.json |
| sharpe_ratio | Episode Sharpe from backtesting engine |
| max_drawdown_pct | Maximum drawdown |
| trades_total | Number of trades executed |
| ledger_ok | bool: found in immutable ledger |
| metadata_ok | bool: all required metadata present |
| cost_optimistic | Net return under optimistic cost proxy |
| cost_base | Net return under base cost proxy |
| cost_pessimistic | Net return under pessimistic cost proxy |
| asset_class | crypto_spot or fx |
| has_baseline | bool: matched baseline_12 found |
| baseline_slug | Matching baseline_12 run slug |
| baseline_return | baseline_12 total_return |
| baseline_sharpe | baseline_12 sharpe_ratio |
| uplift_total_return | Δ total_return vs baseline |
| uplift_sharpe_ratio | Δ sharpe vs baseline |
| n_seeds | Seeds run for this (asset,tf,algo,preset) |
| dsr_approx | Approximate DSR value |
| dsr_status | Status string for DSR |
| classification | Primary status |
| watch_flags | Semicolon-separated secondary flags |
| n_blockers | Count of governance blockers |
| blockers | Pipe-separated blocker list |
""".format(ts=utc_now())
    (HARDENING_OUT / "PLAN.md").write_text(content, encoding="utf-8")
    print(f"[INFO] Wrote PLAN.md")


def write_reports(
    rows: list[dict],
    ledger_events: list[dict],
    results: list[dict],
    group_stats_preset: list[dict],
    group_stats_asset: list[dict],
    group_stats_algo: list[dict],
    seed_dispersion: list[dict],
    boot_ci: list[dict],
    n_trials: int,
    b8_map: dict | None = None,
    b9_map: dict | None = None,
    leakage_map: dict | None = None,
) -> None:
    """Write promotion_candidates.csv, promotion_hardening_report.md, and .json."""

    HARDENING_OUT.mkdir(parents=True, exist_ok=True)

    # ---- Count summary ----
    total_runs    = len(results)
    killed        = sum(1 for r in results if r["classification"].startswith("KILL_"))
    blocked       = sum(1 for r in results if r["classification"] == "PROMOTE_BLOCKED_HARDENING")
    watchlisted   = sum(1 for r in results if r["watch_flags"])
    promotable    = sum(1 for r in results if r["classification"] == "PROMOTE")  # always 0 for now

    kill_breakdown: dict[str, int] = defaultdict(int)
    for r in results:
        if r["classification"].startswith("KILL_"):
            kill_breakdown[r["classification"]] += 1

    # ---- Derive B8 governance gate status from b8_map ----
    b8_map = b8_map or {}
    if not b8_map:
        b8_gate_md  = "✗ NOT COMPUTED"
        b8_gate_json = "NOT_COMPUTED"
    else:
        n_b8_pass    = sum(1 for v in b8_map.values() if v == "PASS")
        n_b8_fail    = sum(1 for v in b8_map.values() if v == "FAIL")
        n_b8_blocked = sum(1 for v in b8_map.values() if v == "BLOCKED_NO_BASELINES")
        b8_gate_md   = (
            f"~ PARTIALLY_CLEARED — {n_b8_pass} run(s) PASS, "
            f"{n_b8_fail} FAIL (mostly killed), {n_b8_blocked} BLOCKED_NO_INPUT"
        )
        b8_gate_json = (
            f"PARTIALLY_CLEARED ({n_b8_pass} PASS / {n_b8_fail} FAIL / "
            f"{n_b8_blocked} BLOCKED_NO_INPUT out of {len(b8_map)} audited)"
        )

    # ---- Derive B9 governance gate status from b9_map ----
    b9_map = b9_map or {}
    if not b9_map:
        b9_gate_md = "✗ NOT COMPUTED"
        b9_gate_json = "NOT_COMPUTED"
    else:
        n_b9_pass = sum(1 for v in b9_map.values() if v == "PASS")
        n_b9_partial = sum(1 for v in b9_map.values() if v == "PARTIAL_PASS")
        n_b9_fail = sum(1 for v in b9_map.values() if v == "FAIL")
        n_b9_blocked = sum(1 for v in b9_map.values() if v == "BLOCKED_NO_MATCH")
        n_b9_na = sum(1 for v in b9_map.values() if v == "NOT_APPLICABLE")
        b9_gate_md = (
            f"~ PARTIALLY_CLEARED — {n_b9_pass} run(s) PASS, "
            f"{n_b9_partial} PARTIAL, {n_b9_fail} FAIL, "
            f"{n_b9_blocked} BLOCKED_NO_MATCH, {n_b9_na} N/A"
        )
        b9_gate_json = (
            f"PARTIALLY_CLEARED ({n_b9_pass} PASS / {n_b9_partial} PARTIAL / "
            f"{n_b9_fail} FAIL / {n_b9_blocked} BLOCKED_NO_MATCH / "
            f"{n_b9_na} N/A out of {len(b9_map)} audited)"
        )

    # ---- Derive B1/B10 governance gate status from leakage_map ----
    leakage_map = leakage_map or {}
    if not leakage_map:
        b1_gate_md = "✗ NOT COMPUTED"
        b10_gate_md = "✗ NOT COMPUTED"
        b1_gate_json = "NOT_COMPUTED"
        b10_gate_json = "NOT_COMPUTED"
    else:
        b1_counts = defaultdict(int)
        b10_counts = defaultdict(int)
        for item in leakage_map.values():
            b1_counts[item.get("b1", "INDETERMINATE")] += 1
            b10_counts[item.get("b10", "INDETERMINATE")] += 1
        b1_gate_md = (
            f"~ PARTIALLY_CLEARED — {b1_counts.get('PASS', 0)} PASS, "
            f"{b1_counts.get('PARTIAL_PASS', 0)} PARTIAL, "
            f"{b1_counts.get('BLOCKED_INPUT_MISSING', 0)} BLOCKED_INPUT_MISSING"
        )
        b10_gate_md = (
            f"~ PARTIALLY_CLEARED — {b10_counts.get('PASS', 0)} PASS, "
            f"{b10_counts.get('FAIL', 0)} FAIL, "
            f"{b10_counts.get('BLOCKED_INPUT_MISSING', 0)} BLOCKED_INPUT_MISSING"
        )
        b1_gate_json = dict(b1_counts)
        b10_gate_json = dict(b10_counts)

    # ---- promotion_candidates.csv ----
    csv_path = HARDENING_OUT / "promotion_candidates.csv"
    csv_fields = [
        "run_slug", "asset", "timeframe", "algo", "preset", "seed", "machine",
        "total_return", "sharpe_ratio", "max_drawdown_pct", "trades_total",
        "ledger_ok", "metadata_ok",
        "cost_optimistic", "cost_base", "cost_pessimistic", "asset_class",
        "has_baseline", "baseline_slug", "baseline_return", "baseline_sharpe",
        "uplift_total_return", "uplift_sharpe_ratio",
        "n_seeds", "dsr_approx", "dsr_status",
        "classification", "watch_flags", "n_blockers", "blockers",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for r in results:
            writer.writerow({
                "run_slug":           r["run_slug"],
                "asset":              r["asset"],
                "timeframe":          r["timeframe"],
                "algo":               r["algo"],
                "preset":             r["preset"],
                "seed":               r["seed"],
                "machine":            r["machine"],
                "total_return":       r["total_return"],
                "sharpe_ratio":       r["sharpe_ratio"],
                "max_drawdown_pct":   r["max_drawdown_pct"],
                "trades_total":       r["trades_total"],
                "ledger_ok":          r["ledger_ok"],
                "metadata_ok":        r["metadata_ok"],
                "cost_optimistic":    r.get("cost_proxy", {}).get("optimistic"),
                "cost_base":          r.get("cost_proxy", {}).get("base"),
                "cost_pessimistic":   r.get("cost_proxy", {}).get("pessimistic"),
                "asset_class":        r.get("cost_proxy", {}).get("asset_class", ""),
                "has_baseline":       r.get("paired_uplift", {}).get("has_baseline", False),
                "baseline_slug":      r.get("paired_uplift", {}).get("baseline_slug", ""),
                "baseline_return":    r.get("paired_uplift", {}).get("baseline_return"),
                "baseline_sharpe":    r.get("paired_uplift", {}).get("baseline_sharpe"),
                "uplift_total_return":r.get("paired_uplift", {}).get("uplift_total_return"),
                "uplift_sharpe_ratio":r.get("paired_uplift", {}).get("uplift_sharpe_ratio"),
                "n_seeds":            r["n_seeds"],
                "dsr_approx":         r.get("dsr", {}).get("dsr_approx"),
                "dsr_status":         r.get("dsr", {}).get("dsr_status", "not_run"),
                "classification":     r["classification"],
                "watch_flags":        ";".join(r.get("watch_flags", [])),
                "n_blockers":         len(r.get("blockers", [])),
                "blockers":           " | ".join(r.get("blockers", [])),
            })
    print(f"[INFO] Wrote {csv_path}")

    # ---- Find best run details ----
    best_result = next((r for r in results if r["run_slug"] == BEST_RUN_SLUG), None)

    # ---- promotion_hardening_report.md ----
    lines = [
        "# Promotion Hardening Report — Stage A → Stage B Gate",
        "",
        f"Generated: {utc_now()}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"- **Total Stage A runs evaluated:** {total_runs}",
        f"- **Total ledger events/trials:** {len(ledger_events)} events, {n_trials} distinct trial IDs",
        f"- **Killed:** {killed}",
        f"  " + "  \n  ".join(f"- {k}: {v}" for k, v in sorted(kill_breakdown.items())),
        f"- **Watchlisted (secondary flags):** {watchlisted}",
        f"- **Blocked from Stage B (governance):** {blocked}",
        f"- **Promotable to Stage B now:** {promotable}",
        "",
        "> **VERDICT: No candidate can advance to Stage B.** "
        "All surviving runs carry unresolved P0 governance blockers (B1–B10). "
        "See §7 for the exact blocker list for the current best run.",
        "",
        "---",
        "",
        "## 2. Classification Breakdown",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    status_counts: dict[str, int] = defaultdict(int)
    for r in results:
        status_counts[r["classification"]] += 1
    for s, c in sorted(status_counts.items()):
        lines.append(f"| {s} | {c} |")

    lines += [
        "",
        "### Watch Flags (secondary, additive)",
        "",
        "| Flag | Count |",
        "| --- | ---: |",
    ]
    flag_counts: dict[str, int] = defaultdict(int)
    for r in results:
        for f in r.get("watch_flags", []):
            flag_counts[f] += 1
    for f, c in sorted(flag_counts.items()):
        lines.append(f"| {f} | {c} |")

    # ---- Best run spotlight ----
    lines += [
        "",
        "---",
        "",
        "## 3. Current Best Run — Exact Governance Report",
        "",
        f"**Run:** `{BEST_RUN_SLUG}`",
        "",
    ]
    if best_result:
        br = best_result
        pu = br.get("paired_uplift", {})
        cp = br.get("cost_proxy", {})
        dsr = br.get("dsr", {})

        lines += [
            "### 3.1 Performance Metrics",
            "",
            f"| Metric | Value |",
            f"| --- | --- |",
            f"| total_return | {fmt(br['total_return'])} |",
            f"| sharpe_ratio | {fmt(br['sharpe_ratio'])} |",
            f"| max_drawdown_pct | {fmt(br['max_drawdown_pct'], 2)}% |",
            f"| trades_total | {br['trades_total']} |",
            f"| ledger_ok | {br['ledger_ok']} |",
            f"| metadata_ok | {br['metadata_ok']} |",
            f"| n_seeds_run | {br['n_seeds']} |",
            "",
            "### 3.2 Cost Proxy (net return estimates)",
            "",
            "| Scenario | Net Return | Positive? |",
            "| --- | ---: | --- |",
            f"| optimistic | {fmt(cp.get('optimistic'))} | {(cp.get('optimistic') or 0) > 0} |",
            f"| base       | {fmt(cp.get('base'))}       | {(cp.get('base') or 0) > 0} |",
            f"| pessimistic| {fmt(cp.get('pessimistic'))} | {(cp.get('pessimistic') or 0) > 0} |",
            "",
            "> Cost proxy assumptions: position_fraction=0.01, sim_fee=2bps/side. "
            "Crypto spot base: fee=5, spread=3, slippage=3 bps/side + turnover penalty.",
            "",
            "### 3.3 Paired Uplift vs Matched Baseline",
            "",
        ]
        if pu.get("has_baseline"):
            lines += [
                f"| Metric | Baseline | Candidate | Uplift |",
                f"| --- | ---: | ---: | ---: |",
                f"| total_return | {fmt(pu.get('baseline_return'))} | {fmt(br['total_return'])} | **{fmt(pu.get('uplift_total_return'))}** |",
                f"| sharpe_ratio | {fmt(pu.get('baseline_sharpe'))} | {fmt(br['sharpe_ratio'])} | **{fmt(pu.get('uplift_sharpe_ratio'))}** |",
                "",
                f"Matched baseline: `{pu.get('baseline_slug', 'N/A')}`",
            ]
        else:
            lines.append(f"> **BLOCKER:** {pu.get('note', 'No baseline found')}")

        lines += [
            "",
            "### 3.4 DSR Approximation",
            "",
            f"| Field | Value |",
            f"| --- | --- |",
            f"| SR observed | {fmt(dsr.get('sr_obs'))} |",
            f"| E[max SR | N={dsr.get('n_trials')} trials] | {fmt(dsr.get('expected_max_sr'))} |",
            f"| DSR approx | {fmt(dsr.get('dsr_approx'))} |",
            f"| DSR > 0? | {dsr.get('dsr_exceeds_threshold', False)} |",
            f"| Status | {dsr.get('dsr_status', 'N/A')} |",
            "",
            f"> {dsr.get('dsr_note', '')}",
            "",
            "### 3.5 PBO/CSCV",
            "",
            "> PBO/CSCV: not_enough_structure. Stage A uses single-split per run. "
            "Deferred to Stage B.",
            "",
            "### 3.6 Exact Blockers for Best Run",
            "",
            f"**Classification:** `{br['classification']}`  ",
            f"**Watch flags:** `{';'.join(br.get('watch_flags', ['none']))}`  ",
            f"**Blocker count:** {len(br.get('blockers', []))}",
            "",
        ]
        for i, b in enumerate(br.get("blockers", []), start=1):
            lines.append(f"{i}. {b}")
    else:
        lines.append(f"> Run `{BEST_RUN_SLUG}` not found in index.csv.")

    # ---- Seed dispersion for best config ----
    best_disp = next(
        (d for d in seed_dispersion
         if d["asset"] == "ethusdt" and d["timeframe"] == "4h"
         and d["algo"] == "sac" and d["preset"] == "tech_stat"),
        None,
    )
    lines += [
        "",
        "---",
        "",
        "## 4. Seed Dispersion — Best Config (ETH/USDT 4h SAC tech_stat)",
        "",
    ]
    if best_disp:
        lines += [
            f"- Seeds run: {best_disp['seeds']}",
            f"- Return mean: {fmt(best_disp['return_mean'])}  std: {fmt(best_disp['return_std'])}  "
            f"min: {fmt(best_disp['return_min'])}  max: {fmt(best_disp['return_max'])}",
            f"- Sharpe mean: {fmt(best_disp['sharpe_mean'])}  std: {fmt(best_disp['sharpe_std'])}",
            "",
            "> High std across seeds indicates policy instability. "
            "Only seed 0 shows positive return; other seeds must be examined before promotion.",
        ]
    else:
        lines.append("> Seed dispersion data not available for this config.")

    # ---- Group statistics ----
    lines += [
        "",
        "---",
        "",
        "## 5. Group Statistics by Preset",
        "",
        "| Preset | Runs | Pos. Return | Return Mean | Return Median | Return Std | Sharpe Mean | DD Mean |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for g in group_stats_preset:
        ret  = g["return"]
        sr   = g["sharpe"]
        dd   = g["drawdown_pct"]
        lines.append(
            f"| {g['preset']} | {g['n_runs']} | {g['n_positive_return']} "
            f"| {fmt(ret['mean'])} | {fmt(ret['median'])} | {fmt(ret['std'])} "
            f"| {fmt(sr['mean'])} | {fmt(dd['mean'], 2)} |"
        )

    lines += [
        "",
        "## 6. Bootstrap CI for total_return by Preset",
        "",
        "| Preset | N | Mean | 95% CI Lo | 95% CI Hi | Note |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for b in boot_ci:
        lines.append(
            f"| {b['preset']} | {b['n']} | {fmt(b.get('mean'))} "
            f"| {fmt(b.get('ci_lo'))} | {fmt(b.get('ci_hi'))} | {b.get('note', '')} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 7. Governance Gate Status",
        "",
        "| Gate | Status |",
        "| --- | --- |",
        "| Immutable ledger | ✓ Checked |",
        f"| Leakage audit (B1) | {b1_gate_md} |",
        "| Availability contract (B2) | ✗ NOT VERIFIED for cross-source presets |",
        "| DSR rigorous (B3) | ✗ APPROXIMATION ONLY |",
        "| PBO/CSCV (B4) | ✗ DEFERRED to Stage B |",
        "| Paired uplift (B5) | ✓ Computed where baseline exists |",
        "| Seed dispersion (B6) | ✓ Reported |",
        "| Cost sensitivity (B7) | ✓ Proxy computed; exact rerun needed |",
        f"| Simple baselines (B8) | {b8_gate_md} |",
        f"| Family ablation (B9) | {b9_gate_md} |",
        f"| Heldout firewall (B10) | {b10_gate_md} |",
        "",
        "**All surviving candidates remain BLOCKED from Stage B promotion until B3/B4 are resolved through Stage B infrastructure.**",
        "",
        "---",
        "",
        f"*End of report. Generated by stage31_promotion_hardening_worker.py at {utc_now()}*",
    ]

    md_path = HARDENING_OUT / "promotion_hardening_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[INFO] Wrote {md_path}")

    # ---- promotion_hardening_report.json ----
    report_json = {
        "generated_at":        utc_now(),
        "worker":              "stage31_promotion_hardening_worker.py",
        "total_stage_a_runs":  total_runs,
        "ledger_events":       len(ledger_events),
        "ledger_trial_ids":    n_trials,
        "n_killed":            killed,
        "kill_breakdown":      dict(sorted(kill_breakdown.items())),
        "n_watchlisted":       watchlisted,
        "n_blocked_hardening": blocked,
        "n_promotable":        promotable,
        "any_promotable_now":  promotable > 0,
        "best_run_slug":       BEST_RUN_SLUG,
        "best_run": {
            "classification": best_result["classification"] if best_result else "NOT_FOUND",
            "n_blockers":     len(best_result.get("blockers", [])) if best_result else None,
            "watch_flags":    best_result.get("watch_flags", []) if best_result else [],
            "blockers":       best_result.get("blockers", []) if best_result else [],
            "total_return":   best_result["total_return"] if best_result else None,
            "sharpe_ratio":   best_result["sharpe_ratio"] if best_result else None,
            "cost_proxy":     best_result.get("cost_proxy") if best_result else None,
            "paired_uplift":  best_result.get("paired_uplift") if best_result else None,
            "dsr":            best_result.get("dsr") if best_result else None,
            "pbo":            compute_pbo_placeholder(),
        },
        "group_stats_by_preset": group_stats_preset,
        "group_stats_by_asset":  group_stats_asset,
        "group_stats_by_algo":   group_stats_algo,
        "seed_dispersion":       seed_dispersion,
        "bootstrap_ci_by_preset":boot_ci,
        "governance_gate": {
            "B1_leakage_audit":      b1_gate_json,
            "B2_availability":       "NOT_VERIFIED",
            "B3_dsr_rigorous":       "APPROXIMATION_ONLY",
            "B4_pbo_cscv":           "DEFERRED_TO_STAGE_B",
            "B5_paired_uplift":      "COMPUTED",
            "B6_seed_dispersion":    "REPORTED",
            "B7_cost_sensitivity":   "PROXY_COMPUTED",
            "B8_simple_baselines":   b8_gate_json,
            "B9_family_ablation":    b9_gate_json,
            "B10_heldout_firewall":  b10_gate_json,
        },
    }
    json_path = HARDENING_OUT / "promotion_hardening_report.json"
    json_path.write_text(json.dumps(report_json, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"[INFO] Wrote {json_path}")


def _write_tasks(results: list[dict]) -> None:
    """Write TASKS.md — completed, skipped, and next implementation tasks."""
    blocked_run = next(
        (r for r in results if r["classification"] == "PROMOTE_BLOCKED_HARDENING"), None
    )
    n_killed  = sum(1 for r in results if r["classification"].startswith("KILL_"))
    n_blocked = sum(1 for r in results if r["classification"] == "PROMOTE_BLOCKED_HARDENING")
    exact_blockers = blocked_run.get("blockers", []) if blocked_run else []
    exact_blocker_lines = "\n".join(
        f"{idx}. {blocker}" for idx, blocker in enumerate(exact_blockers, start=1)
    ) or "No surviving run found."

    content = f"""\
# Promotion Hardening — Task Ledger

Generated: {utc_now()}

## COMPLETED checks (this worker)

- [x] load_stage_a_index() — loaded {len(results)} runs from index.csv
- [x] load_run_ledger() — loaded events from artifacts/run_ledger.jsonl
- [x] verify_ledger_membership() — per run, by (asset, tf, algo, preset, seed)
- [x] validate_required_metadata() — asset, timeframe, algo, preset, seed, machine
- [x] compute_cost_proxy() — optimistic, base, pessimistic scenarios
- [x] find_matched_baselines() — same (asset, tf, algo, seed), preset=baseline_12
- [x] compute_paired_uplift() — Δ return, Δ Sharpe, Δ drawdown vs baseline_12
- [x] compute_group_statistics() — by preset, asset, algo (mean/median/std/min/max)
- [x] compute_seed_dispersion() — for all (asset, tf, algo, preset) with ≥2 seeds
- [x] compute_bootstrap_ci() — 95% bootstrap CI for total_return by preset (n_boot=2000)
- [x] compute_dsr_placeholder_or_approximation() — directional approximation, caveat-flagged
- [x] compute_pbo_placeholder() — not_enough_structure documented
- [x] consume B1/B10 leakage-heldout evidence — loaded leakage_heldout_audit.csv when present
- [x] consume B8 simple-baseline evidence — loaded simple_baseline_report.json when present
- [x] consume B9 family-ablation evidence — loaded family_ablation_report.json when present
- [x] classify_candidate() — deterministic KILL_* / PROMOTE_BLOCKED_HARDENING
- [x] write_reports() — SPEC.md, PLAN.md, TASKS.md, .csv, .md, .json

## KILLED runs

- {n_killed} runs killed at KILL gate (no_trades, non_positive_return, negative_sharpe, ledger_missing, invalid_metrics)
- {n_blocked} run(s) survive KILLs but blocked by governance

## Evidence now wired into this gate

- [x] B1: Leakage/heldout evidence consumed from `leakage_heldout_audit.csv`
- [x] B8: Simple baseline evidence consumed from `simple_baseline_report.json`
- [x] B9: Feature-family ablation evidence consumed from `family_ablation_report.json`
- [x] B10: Heldout firewall evidence consumed from `leakage_heldout_audit.csv`
- [ ] B2: Availability/vintage contract — requires features/AVAILABILITY_CONTRACT.md per preset
- [ ] B3: Rigorous DSR — requires per-bar annualized return series with skewness/kurtosis
- [ ] B4: PBO/CSCV — requires multi-fold split structure (deferred to Stage B)

## BLOCKERS for current best surviving run

{exact_blocker_lines}

## NEXT implementation tasks (priority order)

1. **At Stage B**: implement B3 rigorous DSR with per-bar annualized return series, skewness, kurtosis, and multiple-testing correction.
2. **At Stage B**: implement B4 PBO/CSCV with purged k-fold or CSCV-compatible split artifacts.
3. **Before any cross-source candidate promotes**: implement B2 availability/vintage contract validation.
4. Keep B1/B8/B9/B10 evidence refreshed as new Stage A/Stage B runs complete.
"""
    (HARDENING_OUT / "TASKS.md").write_text(content, encoding="utf-8")
    print(f"[INFO] Wrote TASKS.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    HARDENING_OUT.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Output directory: {HARDENING_OUT}")

    # Write spec and plan first (they don't depend on data)
    _write_spec()
    _write_plan()

    # Load data
    index_rows    = load_stage_a_index()
    ledger_events = load_run_ledger()

    # Build ledger index
    ledger_index = _build_ledger_index(ledger_events)
    n_trials     = len(ledger_index["trial_ids"])
    print(f"[INFO] Ledger index: {len(ledger_index['by_config'])} config keys, {n_trials} distinct trial IDs")

    # Load B8 evidence (from simple_baseline_worker output, if available)
    b8_map = load_b8_evidence()
    print(f"[INFO] Loaded B8 evidence for {len(b8_map)} runs from simple_baseline_report.json")

    # Load B9 evidence (from family_ablation_worker output, if available)
    b9_map = load_b9_evidence()
    print(f"[INFO] Loaded B9 evidence for {len(b9_map)} runs from family_ablation_report.json")

    # Load B1/B10 evidence
    leakage_map = load_leakage_heldout_evidence()
    print(f"[INFO] Loaded B1/B10 evidence for {len(leakage_map)} runs from leakage_heldout_audit.csv")

    # Per-run evaluation
    results: list[dict] = []
    for row in index_rows:
        ledger_ok, ledger_detail = verify_ledger_membership(row, ledger_index)
        metadata_ok, meta_failures = validate_required_metadata(row)
        cost_proxy    = compute_cost_proxy(row)
        baselines     = find_matched_baselines(row, index_rows)
        paired_uplift = compute_paired_uplift(row, baselines)
        n_seeds       = _count_seeds_for_config(row, index_rows)

        leak = leakage_map.get(str(row.get("run_slug", "")), {})
        classification, blockers, watch_flags = classify_candidate(
            row          = row,
            ledger_ok    = ledger_ok,
            ledger_detail= ledger_detail,
            metadata_ok  = metadata_ok,
            metadata_failures = meta_failures,
            cost_proxy   = cost_proxy,
            paired_uplift= paired_uplift,
            n_seeds      = n_seeds,
            b8_evidence  = b8_map.get(str(row.get("run_slug", "")), "NOT_COMPUTED"),
            b9_evidence  = b9_map.get(str(row.get("run_slug", "")), "NOT_COMPUTED"),
            b1_evidence  = leak.get("b1", "NOT_COMPUTED"),
            b10_evidence = leak.get("b10", "NOT_COMPUTED"),
            leakage_detail = leak.get("detail", ""),
        )

        # DSR only for non-killed runs
        dsr = {}
        if not classification.startswith("KILL_"):
            dsr = compute_dsr_placeholder_or_approximation(row, n_trials)

        results.append({
            "run_slug":      str(row.get("run_slug", "")),
            "asset":         str(row.get("asset", "")),
            "timeframe":     str(row.get("timeframe", "")),
            "algo":          str(row.get("algo", "")),
            "preset":        str(row.get("preset", "")),
            "seed":          row.get("seed", ""),
            "machine":       str(row.get("machine", "")),
            "total_return":  safe_float(row.get("total_return")),
            "sharpe_ratio":  safe_float(row.get("sharpe_ratio")),
            "max_drawdown_pct": safe_float(row.get("max_drawdown_pct")),
            "trades_total":  int(row.get("trades_total") or 0),
            "ledger_ok":     ledger_ok,
            "ledger_detail": ledger_detail,
            "metadata_ok":   metadata_ok,
            "metadata_failures": meta_failures,
            "cost_proxy":    cost_proxy,
            "paired_uplift": paired_uplift,
            "n_seeds":       n_seeds,
            "dsr":           dsr,
            "classification":classification,
            "blockers":      blockers,
            "watch_flags":   watch_flags,
        })

    # Group statistics
    group_stats_preset = compute_group_statistics(index_rows, "preset")
    group_stats_asset  = compute_group_statistics(index_rows, "asset")
    group_stats_algo   = compute_group_statistics(index_rows, "algo")

    # Seed dispersion
    seed_dispersion = compute_seed_dispersion(index_rows)
    print(f"[INFO] Seed dispersion computed for {len(seed_dispersion)} config groups")

    # Bootstrap CI
    boot_ci = compute_bootstrap_ci(index_rows, group_key="preset", n_boot=2000, ci=0.95, min_samples=5)

    # Write reports
    write_reports(
        rows              = index_rows,
        ledger_events     = ledger_events,
        results           = results,
        group_stats_preset= group_stats_preset,
        group_stats_asset = group_stats_asset,
        group_stats_algo  = group_stats_algo,
        seed_dispersion   = seed_dispersion,
        boot_ci           = boot_ci,
        n_trials          = n_trials,
        b8_map            = b8_map,
        b9_map            = b9_map,
        leakage_map       = leakage_map,
    )

    # Write tasks
    _write_tasks(results)

    # Summary
    n_killed   = sum(1 for r in results if r["classification"].startswith("KILL_"))
    n_blocked  = sum(1 for r in results if r["classification"] == "PROMOTE_BLOCKED_HARDENING")
    n_promote  = sum(1 for r in results if r["classification"] == "PROMOTE")

    print("\n" + "=" * 60)
    print("PROMOTION HARDENING SUMMARY")
    print("=" * 60)
    print(f"  Total Stage A runs:  {len(results)}")
    print(f"  Ledger events:       {len(ledger_events)}")
    print(f"  Ledger trial IDs:    {n_trials}")
    print(f"  Killed:              {n_killed}")
    print(f"  Blocked (hardening): {n_blocked}")
    print(f"  Promotable now:      {n_promote}")
    print(f"  Any promotable:      {'YES' if n_promote > 0 else 'NO — all runs are blocked'}")
    print("=" * 60)

    best = next((r for r in results if r["run_slug"] == BEST_RUN_SLUG), None)
    if best:
        print(f"\nBest run ({BEST_RUN_SLUG}):")
        print(f"  Classification: {best['classification']}")
        print(f"  Blocker count:  {len(best['blockers'])}")
        print(f"  Watch flags:    {best['watch_flags']}")
        print(f"  Cost base net:  {best['cost_proxy'].get('base')}")
        print(f"  Cost pess net:  {best['cost_proxy'].get('pessimistic')}")
        if best["paired_uplift"].get("has_baseline"):
            print(f"  Paired uplift:  {best['paired_uplift'].get('uplift_total_return')} (return)")
        else:
            print("  Paired uplift:  NO BASELINE FOUND")

    print("\n[INFO] Outputs written to:", HARDENING_OUT)
    print("[INFO] Run stage31_combine_ledger_worker.py and stage32_stage_a_synthesis_worker.py to refresh ledger and index.")


if __name__ == "__main__":
    main()
