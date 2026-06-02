#!/usr/bin/env python3
"""
Stage B Approval Gate Validator.

Reads Stage A hardening artifacts and emits a machine-readable and
human-readable Stage B approval packet. Does NOT launch training and
does NOT use Stage C / 2025-01-01+ data.

Outputs
-------
experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.json
experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.md
experiments/stage_a_screening/stage_b_approval/stage_b_approval_candidates.csv
experiments/stage_a_screening/stage_b_approval/TASKS.md
"""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
HARDENING_DIR = ROOT / "experiments" / "stage_a_screening" / "hardening"
OUT_DIR = ROOT / "experiments" / "stage_a_screening" / "stage_b_approval"

PROMOTION_CANDIDATES_CSV = HARDENING_DIR / "promotion_candidates.csv"
HARDENING_REPORT_JSON = HARDENING_DIR / "promotion_hardening_report.json"
LEAKAGE_REPORT_JSON = HARDENING_DIR / "leakage_heldout_audit_report.json"
BASELINE_REPORT_JSON = HARDENING_DIR / "simple_baseline_report.json"
ABLATION_REPORT_JSON = HARDENING_DIR / "family_ablation_report.json"
STAGEB_STAT_REPORT_JSON = ROOT / "experiments" / "stage_b_validation" / "hardening" / "stageb_dsr_pbo_report.json"
LEDGER_PARQUET = ROOT / "artifacts" / "run_ledger.parquet"
LEDGER_JSONL = ROOT / "artifacts" / "run_ledger.jsonl"
GATE_YAML = ROOT / "experiments" / "design" / "stage_b_promotion_gate.yaml"

SCHEMA_VERSION = 1
PROJECT3_HELDOUT_START = "2025-01-01"

# gate statuses — exactly this set, no others allowed
VALID_STATUSES = {
    "PASS_STAGE_B_READY",
    "FAIL_ECONOMIC_OR_STATISTICAL",
    "BLOCKED_MISSING_EVIDENCE",
    "BLOCKED_LEDGER_ABSENT",
    "BLOCKED_LEAKAGE_AUDIT",
    "BLOCKED_HELDOUT_FIREWALL",
    "BLOCKED_BASELINE_COMPARISON",
    "BLOCKED_FAMILY_ABLATION",
    "BLOCKED_DSR_DEFERRED",
    "BLOCKED_PBO_DEFERRED",
    "KILL_NO_TRADES",
    "KILL_NEGATIVE_SHARPE",
    "KILL_NON_POSITIVE_RETURN",
}


# ---------------------------------------------------------------------------
# Safe helpers
# ---------------------------------------------------------------------------
def _safe_float(v: Any) -> float | None:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _safe_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    if isinstance(v, (int, float)):
        return bool(v)
    return None


def _load_json(path: Path) -> tuple[dict | list | None, str]:
    """Return (data, error). error='' on success."""
    if not path.exists():
        return None, f"file not found: {path}"
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), ""
    except Exception as exc:
        return None, f"JSON parse error in {path}: {exc}"


def _load_csv_df(path: Path) -> tuple[pd.DataFrame | None, str]:
    if not path.exists():
        return None, f"file not found: {path}"
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False), ""
    except Exception as exc:
        return None, f"CSV parse error in {path}: {exc}"


# ---------------------------------------------------------------------------
# Ledger loading and composite-key resolution
# ---------------------------------------------------------------------------
def load_ledger_data() -> tuple[pd.DataFrame | None, str]:
    """
    Load the immutable run ledger as a DataFrame.

    Tries run_ledger.parquet first, then run_ledger.jsonl as fallback.
    Returns (df, "") on success or (None, error_message) on failure.
    """
    if LEDGER_PARQUET.exists():
        try:
            return pd.read_parquet(LEDGER_PARQUET), ""
        except Exception:
            pass
    if LEDGER_JSONL.exists():
        try:
            records = []
            with open(LEDGER_JSONL, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            if records:
                return pd.DataFrame(records), ""
        except Exception as exc:
            return None, f"Cannot read ledger: {exc}"
    return None, "Ledger not found (neither run_ledger.parquet nor run_ledger.jsonl)"


def build_ledger_indexes(
    df: pd.DataFrame,
) -> tuple[set[str], dict[tuple, list[dict]]]:
    """
    Build two lookup structures from the ledger DataFrame.

    Returns
    -------
    raw_ids : set[str]
        All values appearing in the `run_id` and `trial_id` columns — used for
        exact match before composite-key resolution.
    composite_index : dict
        Maps ``(asset, timeframe, algo, preset, seed_int)`` (all lowercase
        strings except seed_int which is int) to a list of ledger row dicts.
        Used when a direct run_id/trial_id match is absent.
    """
    raw_ids: set[str] = set()
    composite_index: dict[tuple, list[dict]] = {}

    for _, row in df.iterrows():
        if "run_id" in df.columns and pd.notna(row.get("run_id")):
            raw_ids.add(str(row["run_id"]))
        if "trial_id" in df.columns and pd.notna(row.get("trial_id")):
            raw_ids.add(str(row["trial_id"]))

        # Build composite key using the structured identity fields
        algo_field = "algorithm" if "algorithm" in df.columns else "algo"
        preset_field = "feature_preset" if "feature_preset" in df.columns else "preset"
        asset = str(row.get("asset", "")).lower().strip()
        timeframe = str(row.get("timeframe", "")).lower().strip()
        algo = str(row.get(algo_field, "")).lower().strip()
        preset = str(row.get(preset_field, "")).lower().strip()
        try:
            seed_int = int(float(row.get("seed", -1)))
        except (TypeError, ValueError):
            seed_int = -1

        if asset and timeframe and algo and preset and seed_int >= 0:
            key = (asset, timeframe, algo, preset, seed_int)
            composite_index.setdefault(key, []).append(dict(row))

    return raw_ids, composite_index


# Match field labels for the evidence dict
_MATCH_NONE = "NO_MATCH"
_MATCH_RUN_ID = "run_id_exact"
_MATCH_TRIAL_ID = "trial_id_exact"
_MATCH_COMPOSITE = "composite_asset_timeframe_algo_preset_seed"


def resolve_ledger_membership(
    run_slug: str,
    asset: str,
    timeframe: str,
    algo: str,
    preset: str,
    seed: str | int,
    raw_ids: set[str],
    composite_index: dict[tuple, list[dict]],
) -> dict:
    """
    Resolve whether a promotion candidate appears in the immutable run ledger.

    Resolution strategy (conservative, no fuzzy matching):
    1. Exact match: run_slug appears as a run_id value in the ledger.
    2. Exact match: run_slug appears as a trial_id value in the ledger.
    3. Composite key match: (asset, timeframe, algo, preset, seed_int) all
       match exactly using the structured ledger fields.  Only valid if all
       five fields are non-empty and seed_int >= 0.

    Returns a dict with:
        matched           : bool
        ledger_match_status : "MATCHED" | "NOT_MATCHED" | "LEDGER_UNAVAILABLE"
        ledger_match_field  : which field/strategy matched (or empty string)
        ledger_match_value  : the matched value in the ledger (or empty string)
        ledger_run_id       : run_id from the matched ledger row
        ledger_trial_id     : trial_id from the matched ledger row
    """
    # 1. Exact run_id match
    if run_slug in raw_ids:
        return {
            "matched": True,
            "ledger_match_status": "MATCHED",
            "ledger_match_field": _MATCH_RUN_ID,
            "ledger_match_value": run_slug,
            "ledger_run_id": run_slug,
            "ledger_trial_id": "",
        }

    # 2. Exact trial_id match (slug may equal a trial_id hex)
    if run_slug in raw_ids:  # already checked; kept for clarity — trial_ids also in raw_ids
        pass

    # 3. Composite key match
    try:
        seed_int = int(float(seed)) if str(seed).strip() not in ("", "nan") else -1
    except (TypeError, ValueError):
        seed_int = -1

    key = (
        str(asset).lower().strip(),
        str(timeframe).lower().strip(),
        str(algo).lower().strip(),
        str(preset).lower().strip(),
        seed_int,
    )

    if all(k for k in key[:-1]) and seed_int >= 0:  # all string fields non-empty, seed valid
        rows = composite_index.get(key, [])
        if rows:
            # Prefer rows with event_type == 'complete'; fallback to last row
            complete_rows = [r for r in rows if str(r.get("event_type", "")).lower() == "complete"]
            best = complete_rows[-1] if complete_rows else rows[-1]
            return {
                "matched": True,
                "ledger_match_status": "MATCHED",
                "ledger_match_field": _MATCH_COMPOSITE,
                "ledger_match_value": str(best.get("run_id", "")),
                "ledger_run_id": str(best.get("run_id", "")),
                "ledger_trial_id": str(best.get("trial_id", "")),
            }

    return {
        "matched": False,
        "ledger_match_status": "NOT_MATCHED",
        "ledger_match_field": _MATCH_NONE,
        "ledger_match_value": "",
        "ledger_run_id": "",
        "ledger_trial_id": "",
    }


def _no_ledger_evidence() -> dict:
    return {
        "matched": False,
        "ledger_match_status": "LEDGER_UNAVAILABLE",
        "ledger_match_field": "",
        "ledger_match_value": "",
        "ledger_run_id": "",
        "ledger_trial_id": "",
    }


# ---------------------------------------------------------------------------
# Evidence loaders (return structured index maps)
# ---------------------------------------------------------------------------
def load_leakage_index(report: dict) -> dict[str, dict]:
    """slug → per_run_result dict."""
    runs = report.get("per_run_results", [])
    return {r["run_slug"]: r for r in runs if isinstance(r, dict) and "run_slug" in r}


def load_baseline_index(report: dict) -> dict[str, dict]:
    """slug → all_run_comparison entry."""
    comps = report.get("all_run_comparisons", [])
    return {c["run_slug"]: c for c in comps if isinstance(c, dict) and "run_slug" in c}


def load_ablation_index(report: dict) -> dict[str, dict]:
    """slug → run entry from all_run_comparisons."""
    comps = report.get("all_run_comparisons", [])
    return {c["run_slug"]: c for c in comps if isinstance(c, dict) and "run_slug" in c}


def load_stageb_stat_index(report: dict) -> dict[str, dict]:
    """slug → Stage B statistical candidate gate."""
    gates = report.get("candidate_gates", {}) if isinstance(report, dict) else {}
    return gates if isinstance(gates, dict) else {}


# ---------------------------------------------------------------------------
# Per-candidate classification
# ---------------------------------------------------------------------------
def _make_blocker(code: str, message: str, evidence_file: str, candidate_id: str,
                  next_action: str) -> dict:
    return {
        "blocker_code": code,
        "blocker_message": message,
        "evidence_file": evidence_file,
        "candidate_id": candidate_id,
        "next_required_artifact_or_action": next_action,
    }


def classify_candidate(
    row: pd.Series,
    ledger_raw_ids: set[str],
    ledger_composite_index: dict[tuple, list[dict]],
    ledger_error: str,
    leakage_index: dict[str, dict],
    leakage_available: bool,
    baseline_index: dict[str, dict],
    baseline_available: bool,
    ablation_index: dict[str, dict],
    ablation_available: bool,
    stageb_stat_index: dict[str, dict] | None = None,
    stageb_stat_available: bool = False,
) -> dict:
    slug = str(row.get("run_slug", "")).strip()
    blockers: list[dict] = []
    watch: list[str] = []
    dsr_status = "missing"
    pbo_status = "missing"

    # ---- 1. Ledger membership ----
    if ledger_error:
        ledger_ev = _no_ledger_evidence()
        ledger_ev["ledger_match_status"] = "LEDGER_UNAVAILABLE"
        return {
            "run_slug": slug,
            "stage_b_status": "BLOCKED_LEDGER_ABSENT",
            "blockers": [_make_blocker(
                "LEDGER_LOAD_ERROR",
                f"Cannot load ledger: {ledger_error}",
                str(LEDGER_PARQUET),
                slug,
                "Restore run_ledger.parquet or run_ledger.jsonl",
            )],
            "watch_flags": [],
            "dsr_status": dsr_status,
            "pbo_status": pbo_status,
            "hardening_classification": str(row.get("classification", "")),
            "asset": str(row.get("asset", "")),
            "timeframe": str(row.get("timeframe", "")),
            "algo": str(row.get("algo", "")),
            "preset": str(row.get("preset", "")),
            "seed": str(row.get("seed", "")),
            "total_return": _safe_float(row.get("total_return")),
            "sharpe_ratio": _safe_float(row.get("sharpe_ratio")),
            **ledger_ev,
            "stageb_stat_available": bool(stageb_stat_available),
            "stageb_stat_promotion_allowed": None,
            "stageb_stat_status": "",
            "stageb_stat_blocking_reasons": [],
        }

    ledger_ev = resolve_ledger_membership(
        run_slug=slug,
        asset=str(row.get("asset", "")),
        timeframe=str(row.get("timeframe", "")),
        algo=str(row.get("algo", "")),
        preset=str(row.get("preset", "")),
        seed=str(row.get("seed", "")),
        raw_ids=ledger_raw_ids,
        composite_index=ledger_composite_index,
    )

    if not ledger_ev["matched"]:
        blockers.append(_make_blocker(
            "LEDGER_MISSING_ENTRY",
            f"run_slug '{slug}' not found in immutable run ledger by any "
            f"deterministic resolution strategy (run_id exact, trial_id exact, "
            f"or composite key asset/timeframe/algo/preset/seed).",
            str(LEDGER_PARQUET),
            slug,
            "Verify run was registered in run_ledger before promotion; "
            "check asset/timeframe/algo/preset/seed fields match ledger entries",
        ))

    # ---- 2. Hardening kill checks — not overridable ----
    # Trust the hardening CSV classification directly. Do not re-derive kill status
    # from metrics, as overlapping conditions (e.g. negative sharpe on a non-positive
    # return run) would misclassify kills.
    hardening_cls = str(row.get("classification", "")).strip()
    hardening_blockers_raw = str(row.get("blockers", "")).strip()
    n_blockers = int(row.get("n_blockers", 0) or 0)
    trades = _safe_float(row.get("trades_total"))
    sharpe = _safe_float(row.get("sharpe_ratio"))
    total_return = _safe_float(row.get("total_return"))

    if hardening_cls == "KILL_NO_TRADES":
        return _final(slug, "KILL_NO_TRADES", row, [_make_blocker(
            "NO_TRADES",
            f"Zero trades — strategy never traded. trades_total={trades}",
            str(PROMOTION_CANDIDATES_CSV),
            slug,
            "Investigate reward shaping; do not promote zero-trade runs",
        )], [], dsr_status, pbo_status, hardening_cls, ledger_ev)

    if hardening_cls == "KILL_NEGATIVE_SHARPE":
        return _final(slug, "KILL_NEGATIVE_SHARPE", row, [_make_blocker(
            "NEGATIVE_SHARPE",
            f"Sharpe ratio {sharpe} < 0",
            str(PROMOTION_CANDIDATES_CSV),
            slug,
            "Run is killed by hardening. No promotion path.",
        )], [], dsr_status, pbo_status, hardening_cls, ledger_ev)

    if hardening_cls == "KILL_NON_POSITIVE_RETURN":
        return _final(slug, "KILL_NON_POSITIVE_RETURN", row, [_make_blocker(
            "NON_POSITIVE_RETURN",
            f"Total return {total_return} <= 0",
            str(PROMOTION_CANDIDATES_CSV),
            slug,
            "Run is killed by hardening. No promotion path.",
        )], [], dsr_status, pbo_status, hardening_cls, ledger_ev)

    # Metric-based kills for runs that lack an explicit hardening kill label
    # (e.g. new runs not yet classified by the hardening worker)
    if trades is not None and trades == 0:
        return _final(slug, "KILL_NO_TRADES", row, [_make_blocker(
            "NO_TRADES",
            f"Zero trades — strategy never traded. trades_total={trades}",
            str(PROMOTION_CANDIDATES_CSV),
            slug,
            "Investigate reward shaping; do not promote zero-trade runs",
        )], [], dsr_status, pbo_status, hardening_cls, ledger_ev)

    if total_return is not None and total_return <= 0:
        return _final(slug, "KILL_NON_POSITIVE_RETURN", row, [_make_blocker(
            "NON_POSITIVE_RETURN",
            f"Total return {total_return} <= 0",
            str(PROMOTION_CANDIDATES_CSV),
            slug,
            "Run killed by non-positive return.",
        )], [], dsr_status, pbo_status, hardening_cls, ledger_ev)

    if sharpe is not None and sharpe < 0:
        return _final(slug, "KILL_NEGATIVE_SHARPE", row, [_make_blocker(
            "NEGATIVE_SHARPE",
            f"Sharpe ratio {sharpe} < 0",
            str(PROMOTION_CANDIDATES_CSV),
            slug,
            "Run killed by negative sharpe.",
        )], [], dsr_status, pbo_status, hardening_cls, ledger_ev)

    # ---- 3. Economic checks ----
    cost_base = _safe_float(row.get("cost_base"))
    cost_pess = _safe_float(row.get("cost_pessimistic"))

    if cost_base is not None and cost_base <= 0:
        blockers.append(_make_blocker(
            "NON_POSITIVE_BASE_RETURN",
            f"Net return under base cost = {cost_base} <= 0",
            str(PROMOTION_CANDIDATES_CSV),
            slug,
            "Compute cost-adjusted return; must be positive under base cost",
        ))

    if cost_pess is not None and total_return is not None and cost_pess < -0.5 * abs(total_return):
        watch.append(f"Pessimistic-cost return {cost_pess} is catastrophic relative to gross {total_return}")

    # Seed dispersion (warning only if n_seeds == 1)
    n_seeds = _safe_float(row.get("n_seeds"))
    if n_seeds is not None and n_seeds < 2:
        watch.append("Only 1 seed available; seed dispersion report cannot be computed")

    # ---- 4. Leakage / heldout firewall ----
    if not leakage_available:
        blockers.append(_make_blocker(
            "LEAKAGE_REPORT_MISSING",
            "leakage_heldout_audit_report.json not found or unreadable",
            str(LEAKAGE_REPORT_JSON),
            slug,
            "Run stage31_leakage_heldout_audit_worker.py to produce audit report",
        ))
    else:
        audit = leakage_index.get(slug)
        if audit is None:
            blockers.append(_make_blocker(
                "LEAKAGE_ENTRY_MISSING",
                f"No leakage audit entry for run_slug '{slug}'",
                str(LEAKAGE_REPORT_JSON),
                slug,
                "Re-run leakage audit worker to include this candidate",
            ))
        else:
            status = str(audit.get("status", "")).upper()
            b1 = str(audit.get("b1_overall", "")).upper()
            b10 = _safe_bool(audit.get("b10_firewall_cleared"))
            error_field = str(audit.get("error", "")).strip()

            # Fatal: any heldout data in training inputs
            if not _safe_bool(audit.get("max_ts_before_boundary")):
                blockers.append(_make_blocker(
                    "HELDOUT_DATA_IN_TRAIN",
                    f"max_ts={audit.get('max_ts')} >= 2025-01-01 in training input",
                    str(LEAKAGE_REPORT_JSON),
                    slug,
                    "FATAL — strip all rows >= 2025-01-01 from train.csv and re-run",
                ))

            if status == "BLOCKED_INPUT_MISSING" or status == "BLOCKED_MISSING":
                blockers.append(_make_blocker(
                    "LEAKAGE_INPUT_MISSING",
                    f"Leakage audit blocked: {error_field or 'input CSV not found'}",
                    str(LEAKAGE_REPORT_JSON),
                    slug,
                    "Provide train.csv input artifact for leakage audit",
                ))
            elif b10 is False:
                blockers.append(_make_blocker(
                    "HELDOUT_FIREWALL_FAIL",
                    "b10_firewall_cleared=False in leakage audit",
                    str(LEAKAGE_REPORT_JSON),
                    slug,
                    "Investigate and fix heldout data contamination before promotion",
                ))
            # B1_PARTIAL_PASS is acceptable (own-asset OHLCV runs not applicable)

    # ---- 5. Simple baselines ----
    if not baseline_available:
        blockers.append(_make_blocker(
            "BASELINE_REPORT_MISSING",
            "simple_baseline_report.json not found or unreadable",
            str(BASELINE_REPORT_JSON),
            slug,
            "Run stage31_simple_baseline_worker.py",
        ))
    else:
        b_entry = baseline_index.get(slug)
        if b_entry is None:
            blockers.append(_make_blocker(
                "BASELINE_ENTRY_MISSING",
                f"No simple baseline entry for run_slug '{slug}'",
                str(BASELINE_REPORT_JSON),
                slug,
                "Re-run stage31_simple_baseline_worker.py to include this run",
            ))
        else:
            b8 = str(b_entry.get("b8_evidence", "")).upper()
            baselines_avail = _safe_bool(b_entry.get("baselines_available"))
            if not baselines_avail:
                blockers.append(_make_blocker(
                    "BASELINE_INPUT_MISSING",
                    "baselines_available=False; no input CSV for baseline computation",
                    str(BASELINE_REPORT_JSON),
                    slug,
                    "Provide train.csv; re-run simple_baseline_worker",
                ))
            elif b8 == "FAIL":
                beats_base = _safe_bool(b_entry.get("rl_beats_best_baseline_at_base_cost"))
                beats_pess = _safe_bool(b_entry.get("rl_beats_best_baseline_at_pessimistic_cost"))
                blockers.append(_make_blocker(
                    "BASELINE_FAIL",
                    f"RL does not beat best simple baseline. "
                    f"beats_base={beats_base}, beats_pess={beats_pess}",
                    str(BASELINE_REPORT_JSON),
                    slug,
                    "Candidate must outperform all simple baselines under base AND pessimistic cost",
                ))
            elif b8 not in ("PASS", "NOT_APPLICABLE"):
                blockers.append(_make_blocker(
                    "BASELINE_UNCLEAR",
                    f"b8_evidence='{b8}' — unclear status",
                    str(BASELINE_REPORT_JSON),
                    slug,
                    "Re-run simple_baseline_worker; require explicit PASS or NOT_APPLICABLE",
                ))

    # ---- 6. Family ablation ----
    if not ablation_available:
        blockers.append(_make_blocker(
            "ABLATION_REPORT_MISSING",
            "family_ablation_report.json not found or unreadable",
            str(ABLATION_REPORT_JSON),
            slug,
            "Run stage31_family_ablation_worker.py",
        ))
    else:
        abl = ablation_index.get(slug)
        if abl is None:
            blockers.append(_make_blocker(
                "ABLATION_ENTRY_MISSING",
                f"No family ablation entry for run_slug '{slug}'",
                str(ABLATION_REPORT_JSON),
                slug,
                "Re-run stage31_family_ablation_worker.py to include this run",
            ))
        else:
            b9 = str(abl.get("b9_evidence", "")).upper()
            if b9 == "FAIL":
                blockers.append(_make_blocker(
                    "ABLATION_FAIL",
                    f"Family ablation FAIL: {abl.get('reason','')}",
                    str(ABLATION_REPORT_JSON),
                    slug,
                    "Feature family does not provide marginal value vs ablation; "
                    "investigate or drop feature family",
                ))
            elif b9 == "BLOCKED_NO_MATCH":
                blockers.append(_make_blocker(
                    "ABLATION_NO_MATCH",
                    "No matched ablation variant found for this run",
                    str(ABLATION_REPORT_JSON),
                    slug,
                    "Run matched ablation variant (same asset/timeframe/algo/seed)",
                ))
            # NOT_APPLICABLE (baseline preset), PASS, PARTIAL_PASS all accepted

    # ---- 7. Stage B statistical checks (B3 DSR, B4 PBO, family/seed/cost/trade gates) ----
    stageb_stat_ev: dict[str, Any] = {
        "stageb_stat_available": bool(stageb_stat_available),
        "stageb_stat_promotion_allowed": None,
        "stageb_stat_status": "MISSING_REPORT" if not stageb_stat_available else "MISSING_CANDIDATE_GATE",
        "stageb_stat_blocking_reasons": [],
    }
    if stageb_stat_available:
        gate = (stageb_stat_index or {}).get(slug)
        if not isinstance(gate, dict):
            dsr_status = "Stage_B_missing"
            pbo_status = "Stage_B_missing"
            blockers.append(_make_blocker(
                "STAGEB_STAT_EVIDENCE_MISSING",
                "No Stage B statistical candidate gate exists for this run_slug.",
                str(STAGEB_STAT_REPORT_JSON),
                slug,
                "Produce return-trace evidence and re-run stageb_dsr_pbo_evaluator.py",
            ))
        else:
            reasons = [str(x) for x in gate.get("blocking_reasons", [])]
            allowed = bool(gate.get("promotion_allowed"))
            stageb_stat_ev.update({
                "stageb_stat_promotion_allowed": allowed,
                "stageb_stat_status": str(gate.get("status", "")),
                "stageb_stat_blocking_reasons": reasons,
            })
            if allowed:
                dsr_status = "Stage_B_rigorous_PASS"
                pbo_status = "Stage_B_PBO_PASS"
            else:
                dsr_status = "Stage_B_rigorous_FAIL_OR_BLOCKED"
                pbo_status = "Stage_B_PBO_FAIL_OR_BLOCKED"
                reason_messages = {
                    "EVIDENCE_INVALID_OR_MISSING": "Trace evidence is invalid or missing.",
                    "MISSING_COST_SCENARIO": "Both base and pessimistic cost scenarios are required.",
                    "DSR_RIGOROUS_FAIL": "Rigorous DSR failed or could not be computed from per-bar traces.",
                    "PBO_DEFERRED_OR_FAIL": "PBO/CSCV gate failed or remains structurally blocked.",
                    "FAMILY_REALITY_CHECK_FAIL": "Family-level Reality Check / SPA gate failed.",
                    "SEED_UNCERTAINTY_BLOCKED": "Paired seed uncertainty gate is blocked or failed.",
                    "FINAL_NO_TRADES": "Stage B trace has no trades.",
                    "FINAL_EXCESSIVE_TRADES_HARD": "Stage B trace exceeds hard trade-rate limit.",
                    "FINAL_ALWAYS_IN_MARKET_LOSING": "Stage B trace is always-in-market while losing.",
                }
                for reason in reasons or ["STAGEB_STAT_GATE_FAIL"]:
                    blockers.append(_make_blocker(
                        reason,
                        reason_messages.get(reason, f"Stage B statistical gate blocker: {reason}"),
                        str(STAGEB_STAT_REPORT_JSON),
                        slug,
                        "Inspect stageb_dsr_pbo_report.json, correct missing evidence/configuration, "
                        "and re-run Stage B evaluator before any Stage C access",
                    ))
    else:
        dsr_approx = str(row.get("dsr_status", "")).strip()
        dsr_status = _classify_dsr(dsr_approx)
        pbo_status = "Stage_B_required"  # Stage A single-split never supports CSCV/PBO

        if dsr_status == "missing":
            blockers.append(_make_blocker(
                "DSR_MISSING",
                "DSR not computed for this candidate",
                str(PROMOTION_CANDIDATES_CSV),
                slug,
                "Run DSR computation; requires per-step return trace from agent-multi",
            ))
        elif dsr_status == "Stage_A_approximate":
            # per gate.yaml, rigorous DSR is required; approximate is not sufficient for full PASS
            blockers.append(_make_blocker(
                "DSR_APPROXIMATE_INSUFFICIENT",
                "DSR is Stage A approximation only. Gate policy requires rigorous DSR for PASS_STAGE_B_READY.",
                str(HARDENING_REPORT_JSON),
                slug,
                "Stage B must produce per-step return trace via return_trace_file; "
                "then run stageb_dsr_pbo_evaluator.py",
            ))

        # PBO always deferred at Stage A
        blockers.append(_make_blocker(
            "PBO_DEFERRED",
            "PBO/CSCV not feasible with Stage A single-split structure; deferred to Stage B.",
            str(HARDENING_REPORT_JSON),
            slug,
            "Stage B must implement purged k-fold or CSCV on 1M-step runs; "
            "run stageb_dsr_pbo_evaluator.py",
        ))

    # ---- Final classification ----
    if not blockers:
        status = "PASS_STAGE_B_READY"
    else:
        # Priority ordering of first blocker code → gate status
        blocker_codes = [b["blocker_code"] for b in blockers]
        if "HELDOUT_DATA_IN_TRAIN" in blocker_codes or "HELDOUT_FIREWALL_FAIL" in blocker_codes:
            status = "BLOCKED_HELDOUT_FIREWALL"
        elif "LEAKAGE_REPORT_MISSING" in blocker_codes or "LEAKAGE_ENTRY_MISSING" in blocker_codes \
                or "LEAKAGE_INPUT_MISSING" in blocker_codes:
            status = "BLOCKED_LEAKAGE_AUDIT"
        elif "BASELINE_REPORT_MISSING" in blocker_codes or "BASELINE_ENTRY_MISSING" in blocker_codes \
                or "BASELINE_INPUT_MISSING" in blocker_codes or "BASELINE_UNCLEAR" in blocker_codes:
            status = "BLOCKED_BASELINE_COMPARISON"
        elif "BASELINE_FAIL" in blocker_codes:
            status = "BLOCKED_BASELINE_COMPARISON"
        elif "ABLATION_REPORT_MISSING" in blocker_codes or "ABLATION_ENTRY_MISSING" in blocker_codes \
                or "ABLATION_NO_MATCH" in blocker_codes:
            status = "BLOCKED_FAMILY_ABLATION"
        elif "ABLATION_FAIL" in blocker_codes:
            status = "BLOCKED_FAMILY_ABLATION"
        elif "FINAL_NO_TRADES" in blocker_codes:
            status = "KILL_NO_TRADES"
        elif "STAGEB_STAT_EVIDENCE_MISSING" in blocker_codes \
                or "EVIDENCE_INVALID_OR_MISSING" in blocker_codes \
                or "MISSING_COST_SCENARIO" in blocker_codes:
            status = "BLOCKED_MISSING_EVIDENCE"
        elif "DSR_RIGOROUS_FAIL" in blocker_codes:
            status = "BLOCKED_DSR_DEFERRED"
        elif "PBO_DEFERRED_OR_FAIL" in blocker_codes:
            status = "BLOCKED_PBO_DEFERRED"
        elif "DSR_MISSING" in blocker_codes:
            status = "BLOCKED_DSR_DEFERRED"
        elif "DSR_APPROXIMATE_INSUFFICIENT" in blocker_codes:
            status = "BLOCKED_DSR_DEFERRED"
        elif "PBO_DEFERRED" in blocker_codes:
            status = "BLOCKED_PBO_DEFERRED"
        elif "LEDGER_MISSING_ENTRY" in blocker_codes:
            status = "BLOCKED_LEDGER_ABSENT"
        elif "LEDGER_LOAD_ERROR" in blocker_codes:
            status = "BLOCKED_LEDGER_ABSENT"
        elif any(c in blocker_codes for c in (
            "NON_POSITIVE_BASE_RETURN",
            "FAMILY_REALITY_CHECK_FAIL",
            "SEED_UNCERTAINTY_BLOCKED",
            "FINAL_EXCESSIVE_TRADES_HARD",
            "FINAL_ALWAYS_IN_MARKET_LOSING",
            "STAGEB_STAT_GATE_FAIL",
        )):
            status = "FAIL_ECONOMIC_OR_STATISTICAL"
        else:
            status = "BLOCKED_MISSING_EVIDENCE"

    return _final(slug, status, row, blockers, watch, dsr_status, pbo_status, hardening_cls,
                  ledger_ev, stageb_stat_ev)


def _classify_dsr(dsr_status_raw: str) -> str:
    if not dsr_status_raw or dsr_status_raw in ("", "not_run", "nan"):
        return "missing"
    if "approx" in dsr_status_raw.lower() or "approximat" in dsr_status_raw.lower():
        return "Stage_A_approximate"
    if "rigorous" in dsr_status_raw.lower() or "pass" in dsr_status_raw.lower():
        return "Stage_B_required"
    return "Stage_A_approximate"


def _final(slug, status, row, blockers, watch, dsr_status, pbo_status,
           hardening_cls, ledger_ev: dict | None = None,
           stageb_stat_ev: dict | None = None) -> dict:
    assert status in VALID_STATUSES, f"Invalid status: {status}"
    if ledger_ev is None:
        ledger_ev = _no_ledger_evidence()
    if stageb_stat_ev is None:
        stageb_stat_ev = {
            "stageb_stat_available": False,
            "stageb_stat_promotion_allowed": None,
            "stageb_stat_status": "",
            "stageb_stat_blocking_reasons": [],
        }
    return {
        "run_slug": slug,
        "stage_b_status": status,
        "hardening_classification": hardening_cls,
        "asset": str(row.get("asset", "")),
        "timeframe": str(row.get("timeframe", "")),
        "algo": str(row.get("algo", "")),
        "preset": str(row.get("preset", "")),
        "seed": str(row.get("seed", "")),
        "machine": str(row.get("machine", "")),
        "total_return": _safe_float(row.get("total_return")),
        "sharpe_ratio": _safe_float(row.get("sharpe_ratio")),
        "max_drawdown_pct": _safe_float(row.get("max_drawdown_pct")),
        "trades_total": _safe_float(row.get("trades_total")),
        "cost_base": _safe_float(row.get("cost_base")),
        "cost_pessimistic": _safe_float(row.get("cost_pessimistic")),
        "dsr_status": dsr_status,
        "pbo_status": pbo_status,
        "blockers": blockers,
        "watch_flags": watch,
        "n_blockers": len(blockers),
        # Ledger resolution evidence
        "ledger_match_status": ledger_ev.get("ledger_match_status", ""),
        "ledger_match_field": ledger_ev.get("ledger_match_field", ""),
        "ledger_match_value": ledger_ev.get("ledger_match_value", ""),
        "ledger_run_id": ledger_ev.get("ledger_run_id", ""),
        "ledger_trial_id": ledger_ev.get("ledger_trial_id", ""),
        "stageb_stat_available": stageb_stat_ev.get("stageb_stat_available", False),
        "stageb_stat_promotion_allowed": stageb_stat_ev.get("stageb_stat_promotion_allowed"),
        "stageb_stat_status": stageb_stat_ev.get("stageb_stat_status", ""),
        "stageb_stat_blocking_reasons": stageb_stat_ev.get("stageb_stat_blocking_reasons", []),
    }


# ---------------------------------------------------------------------------
# Status counts
# ---------------------------------------------------------------------------
def count_by_status(results: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        s = r["stage_b_status"]
        counts[s] = counts.get(s, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------
def write_json_packet(results: list[dict], status_counts: dict, out_path: Path) -> None:
    ready = [r for r in results if r["stage_b_status"] == "PASS_STAGE_B_READY"]
    ready.sort(key=lambda r: -(r["total_return"] or -9999))

    top_blocked = [r for r in results if r["stage_b_status"].startswith("BLOCKED")
                   and r.get("total_return") is not None]
    top_blocked.sort(key=lambda r: -(r["total_return"] or -9999))

    packet = {
        "schema_version": SCHEMA_VERSION,
        "project3_heldout_start": PROJECT3_HELDOUT_START,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stageb_stat_report": str(STAGEB_STAT_REPORT_JSON),
        "stageb_stat_report_exists": STAGEB_STAT_REPORT_JSON.exists(),
        "summary": {
            "total_candidates": len(results),
            "status_counts": dict(sorted(status_counts.items())),
            "any_stage_b_ready": len(ready) > 0,
            "n_stage_b_ready": len(ready),
            "n_with_stageb_stat_gate": sum(1 for r in results if r.get("stageb_stat_promotion_allowed") is not None),
        },
        "stage_b_ready": ready,
        "top_blocked_by_return": top_blocked[:10],
        "all_candidates": sorted(results, key=lambda r: r["run_slug"]),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(packet, fh, indent=2, default=str)
    print(f"[OK] Wrote {out_path}")


def write_csv(results: list[dict], out_path: Path) -> None:
    fields = [
        "run_slug", "stage_b_status", "hardening_classification",
        "asset", "timeframe", "algo", "preset", "seed", "machine",
        "total_return", "sharpe_ratio", "max_drawdown_pct", "trades_total",
        "cost_base", "cost_pessimistic",
        "dsr_status", "pbo_status", "n_blockers",
        "stageb_stat_available", "stageb_stat_promotion_allowed",
        "stageb_stat_status", "stageb_stat_blocking_reasons",
        "blocker_codes", "watch_flags",
        # Ledger resolution evidence columns
        "ledger_match_status", "ledger_match_field", "ledger_match_value",
        "ledger_run_id", "ledger_trial_id",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(results, key=lambda x: x["run_slug"]):
            row = dict(r)
            row["blocker_codes"] = ";".join(b["blocker_code"] for b in r.get("blockers", []))
            row["watch_flags"] = ";".join(r.get("watch_flags", []))
            row["stageb_stat_blocking_reasons"] = ";".join(r.get("stageb_stat_blocking_reasons", []))
            writer.writerow(row)
    print(f"[OK] Wrote {out_path}")


def write_markdown(results: list[dict], status_counts: dict, out_path: Path) -> None:
    ready = [r for r in results if r["stage_b_status"] == "PASS_STAGE_B_READY"]
    ready.sort(key=lambda r: -(r["total_return"] or -9999))

    lines = [
        "# Stage B Approval Packet",
        "",
        f"**Generated at:** {datetime.now(timezone.utc).isoformat()}  ",
        f"**Heldout firewall:** `{PROJECT3_HELDOUT_START}`  ",
        f"**Total candidates:** {len(results)}  ",
        f"**Stage B ready:** {len(ready)}  ",
        "",
        "## Status Summary",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for s, n in sorted(status_counts.items()):
        lines.append(f"| {s} | {n} |")

    lines += [
        "",
        "## Stage B Ready Candidates",
        "",
    ]
    if ready:
        lines += [
            "| run_slug | total_return | sharpe | cost_base | cost_pess | dsr | pbo |",
            "|----------|-------------|--------|-----------|-----------|-----|-----|",
        ]
        for r in ready[:20]:
            lines.append(
                f"| {r['run_slug']} | {r['total_return']:.4f} | {r['sharpe_ratio']:.4f}"
                f" | {r['cost_base']} | {r['cost_pessimistic']}"
                f" | {r['dsr_status']} | {r['pbo_status']} |"
            )
    else:
        lines.append("_No candidates are currently Stage B ready._")

    lines += [
        "",
        "## Blocker Summary (top 20 by return, non-killed)",
        "",
        "| run_slug | status | total_return | blocker_codes |",
        "|----------|--------|-------------|---------------|",
    ]
    top = [r for r in results
           if r["stage_b_status"].startswith("BLOCKED") and r.get("total_return") is not None]
    top.sort(key=lambda r: -(r["total_return"] or -9999))
    for r in top[:20]:
        codes = ";".join(b["blocker_code"] for b in r.get("blockers", []))
        lines.append(f"| {r['run_slug']} | {r['stage_b_status']} | {r['total_return']:.4f} | {codes} |")

    lines += [
        "",
        "## Governance Gate Policy",
        "",
        f"Gate configuration: `{GATE_YAML}`  ",
        "",
        "Key requirements for `PASS_STAGE_B_READY`:",
        "- Immutable ledger membership",
        "- No heldout data (DATE_TIME >= 2025-01-01) in training inputs",
        "- Beat all simple baselines at base AND pessimistic cost",
        "- Family ablation evidence (PASS or NOT_APPLICABLE)",
        "- Rigorous DSR (Stage A approximation is insufficient)",
        "- PBO/CSCV (always deferred to Stage B with per-step return traces)",
        "",
        "> Note: `BLOCKED_DSR_DEFERRED` and `BLOCKED_PBO_DEFERRED` are the "
        "expected terminal states for all Stage A candidates. "
        "These require Stage B 1M-step runs with `return_trace_file` enabled.",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {out_path}")


def write_tasks_md(results: list[dict], status_counts: dict, out_path: Path) -> None:
    lines = [
        "# Stage B Approval — Required Next Actions",
        "",
        f"_Generated: {datetime.now(timezone.utc).isoformat()}_",
        "",
        "## Blocking Issues (must resolve before any PASS_STAGE_B_READY)",
        "",
    ]

    # Collect unique next actions
    next_actions: dict[str, list[str]] = {}
    for r in results:
        for b in r.get("blockers", []):
            code = b["blocker_code"]
            action = b.get("next_required_artifact_or_action", "")
            if code not in next_actions:
                next_actions[code] = []
            if action and action not in next_actions[code]:
                next_actions[code].append(action)

    for code in sorted(next_actions.keys()):
        lines.append(f"### {code}")
        for a in next_actions[code]:
            lines.append(f"- {a}")
        lines.append("")

    lines += [
        "## Summary",
        "",
        f"- Total candidates: {len(results)}",
    ]
    for s, n in sorted(status_counts.items()):
        lines.append(f"- {s}: {n}")

    lines += [
        "",
        "## Required Stage B Artifacts",
        "",
        "1. **Return trace files** — agent-multi must emit `return_trace_file` for each 1M-step run",
        "2. **stageb_dsr_pbo_evaluator.py** — run after Stage B training to compute rigorous DSR and PBO",
        "3. **Purged k-fold splits** — required for CSCV/PBO; implement in Stage B training config",
        "",
        "## Do NOT",
        "",
        "- Do not mark any candidate `PASS_STAGE_B_READY` until B3/B4 clear via the above artifacts",
        "- Do not treat Stage B diagnostic/statistical runs as promotion evidence until rigorous DSR/PBO reports exist",
        "- Do not inspect or use any data from 2025-01-01 onwards (heldout firewall)",
        "- Do not modify existing Stage A hardening artifacts",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"[INFO] Stage B Approval Gate Validator")
    print(f"[INFO] Heldout start: {PROJECT3_HELDOUT_START}")

    # Load promotion candidates
    candidates_df, err = _load_csv_df(PROMOTION_CANDIDATES_CSV)
    if err:
        print(f"[FATAL] Cannot load promotion_candidates.csv: {err}", file=sys.stderr)
        sys.exit(1)
    print(f"[INFO] Loaded {len(candidates_df)} promotion candidates")

    # Load run ledger
    ledger_df, ledger_error = load_ledger_data()
    if ledger_error:
        print(f"[WARN] Ledger error: {ledger_error}")
        ledger_raw_ids: set[str] = set()
        ledger_composite_index: dict = {}
    else:
        ledger_raw_ids, ledger_composite_index = build_ledger_indexes(ledger_df)
        print(f"[INFO] Ledger loaded: {len(ledger_df)} rows, "
              f"{len(ledger_raw_ids)} unique IDs, "
              f"{len(ledger_composite_index)} composite keys")

    # Load leakage report
    leakage_report, lerr = _load_json(LEAKAGE_REPORT_JSON)
    leakage_available = leakage_report is not None
    leakage_index = load_leakage_index(leakage_report) if leakage_available else {}
    if lerr:
        print(f"[WARN] Leakage report: {lerr}")
    else:
        print(f"[INFO] Leakage audit: {len(leakage_index)} entries")

    # Load simple baseline report
    baseline_report, berr = _load_json(BASELINE_REPORT_JSON)
    baseline_available = baseline_report is not None
    baseline_index = load_baseline_index(baseline_report) if baseline_available else {}
    if berr:
        print(f"[WARN] Baseline report: {berr}")
    else:
        print(f"[INFO] Baseline report: {len(baseline_index)} entries")

    # Load family ablation report
    ablation_report, aerr = _load_json(ABLATION_REPORT_JSON)
    ablation_available = ablation_report is not None
    ablation_index = load_ablation_index(ablation_report) if ablation_available else {}
    if aerr:
        print(f"[WARN] Ablation report: {aerr}")
    else:
        print(f"[INFO] Ablation report: {len(ablation_index)} entries")

    # Load rigorous Stage B statistical report, if present.
    stageb_stat_report, serr = _load_json(STAGEB_STAT_REPORT_JSON)
    stageb_stat_available = stageb_stat_report is not None
    stageb_stat_index = load_stageb_stat_index(stageb_stat_report) if stageb_stat_available else {}
    if serr:
        print(f"[WARN] Stage B statistical report: {serr}")
    else:
        print(f"[INFO] Stage B statistical gates: {len(stageb_stat_index)} entries")

    # Classify each candidate
    results: list[dict] = []
    for _, row in candidates_df.iterrows():
        result = classify_candidate(
            row=row,
            ledger_raw_ids=ledger_raw_ids,
            ledger_composite_index=ledger_composite_index,
            ledger_error=ledger_error,
            leakage_index=leakage_index,
            leakage_available=leakage_available,
            baseline_index=baseline_index,
            baseline_available=baseline_available,
            ablation_index=ablation_index,
            ablation_available=ablation_available,
            stageb_stat_index=stageb_stat_index,
            stageb_stat_available=stageb_stat_available,
        )
        results.append(result)

    status_counts = count_by_status(results)

    # Write outputs
    write_json_packet(results, status_counts, OUT_DIR / "stage_b_approval_packet.json")
    write_csv(results, OUT_DIR / "stage_b_approval_candidates.csv")
    write_markdown(results, status_counts, OUT_DIR / "stage_b_approval_packet.md")
    write_tasks_md(results, status_counts, OUT_DIR / "TASKS.md")

    # Print summary
    print("\n=== Stage B Approval Gate Summary ===")
    for s, n in sorted(status_counts.items()):
        print(f"  {s}: {n}")

    ready = sum(1 for r in results if r["stage_b_status"] == "PASS_STAGE_B_READY")
    print(f"\n  ANY STAGE B READY: {'YES' if ready > 0 else 'NO'} ({ready} candidates)")

    if ready == 0:
        best_blocked = [r for r in results if r["stage_b_status"].startswith("BLOCKED")]
        best_blocked.sort(key=lambda r: -(r["total_return"] or -9999))
        if best_blocked:
            top = best_blocked[0]
            print(f"\n  Best blocked: {top['run_slug']}")
            print(f"    status: {top['stage_b_status']}")
            print(f"    total_return: {top['total_return']}")
            codes = [b["blocker_code"] for b in top["blockers"]]
            print(f"    blocker codes: {codes}")


if __name__ == "__main__":
    main()
