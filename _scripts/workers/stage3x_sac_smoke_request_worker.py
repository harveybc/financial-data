#!/usr/bin/env python3
"""Emit the financial-data request packet for the Stage 3X SAC smoke plan.

This worker is the orchestration bridge from the CPU target-relation screen to
agent-multi's locked SAC smoke-plan generator. It never launches training and
never authorizes Stage C. Its output is deliberately explicit so another agent
or a human can run exactly the listed agent-multi command without guessing.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT_MULTI_ROOT = ROOT.parent / "agent-multi"

SELECTED_CONTRACTS = (
    ROOT
    / "experiments"
    / "stage3x_target_relation_screen"
    / "selected_feature_contracts.json"
)
ABSURDITY_GUARD = (
    ROOT
    / "experiments"
    / "stage3x_absurdity_guard"
    / "stage3x_absurdity_guard_report.json"
)
SMOKE_SYNTHESIS = (
    ROOT
    / "experiments"
    / "stage3x_sac_smoke_results"
    / "stage3x_sac_smoke_result_synthesis.json"
)
OUT_ROOT = ROOT / "experiments" / "stage3x_sac_smoke_request"
OUT_JSON = OUT_ROOT / "stage3x_sac_smoke_request.json"
OUT_MD = OUT_ROOT / "stage3x_sac_smoke_request.md"
SMOKE_SHORTLIST_JSON = OUT_ROOT / "selected_feature_contracts_smoke_shortlist.json"

AGENT_MULTI_TOOL = AGENT_MULTI_ROOT / "tools" / "project3_stage3x_sac_smoke_plan.py"
AGENT_MULTI_OUTPUT_DIR = AGENT_MULTI_ROOT / "experiments" / "stage3x_sac_smoke_plan"
PYTHON_BIN = Path("/home/harveybc/anaconda3/envs/trading-stack/bin/python")

SCHEMA_VERSION = "project3_stage3x_sac_smoke_request_v1"
HELDOUT_START = "2025-01-01"
DEFAULT_TOP_N = 4
DEFAULT_SEEDS = (0, 1, 2)
DEFAULT_COST_SCENARIO = "base"
FOLLOWUP_SEEDS = (0, 1, 2, 3, 4)
FOLLOWUP_COST_SCENARIOS = ("base", "plus_50pct", "plus_100pct")
PREFERRED_SMOKE_CONTRACT_IDS = (
    "btcusdt_perp__4h__crypto_full__regime_conditioned_topk__p00__selected",
    "btcusdt__1h__learned_cnn__rank_ic_topk__p00__selected",
    "btcusdt__4h__learned_cnn__rank_ic_topk__p00__selected",
    "btcusdt__1h__learned_lstm__regime_conditioned_topk__p00__selected",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ranked_contracts(contracts: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    def score(row: dict[str, Any]) -> tuple[float, float, float]:
        return (
            float(row.get("screen_score") or 0.0),
            float(row.get("proxy_net_return") or 0.0),
            float(row.get("best_abs_validation_ic") or 0.0),
        )

    return sorted(contracts, key=score, reverse=True)[:top_n]


def smoke_shortlist_contracts(contracts: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    """Return the diverse smoke subset recommended by the research review.

    The raw score ordering puts two BTC-perp contracts with identical CPU
    scores at ranks 1 and 2. For the first smoke we want diversity across
    source/representation/asset families, so we prefer the research-reviewed
    shortlist and only fall back to raw ranking when one of those contracts is
    missing.
    """
    by_id = {str(row.get("contract_id")): row for row in contracts}
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cid in PREFERRED_SMOKE_CONTRACT_IDS:
        row = by_id.get(cid)
        if row is None:
            continue
        selected.append(row)
        seen.add(cid)
        if len(selected) >= top_n:
            return selected

    for row in ranked_contracts(contracts, len(contracts)):
        cid = str(row.get("contract_id"))
        if cid in seen:
            continue
        selected.append(row)
        seen.add(cid)
        if len(selected) >= top_n:
            break
    return selected


def build_shortlist_doc(
    *,
    selected_doc: dict[str, Any],
    top_contracts: list[dict[str, Any]],
    source_sha: str,
    generated_at: str,
    selection_policy: str,
) -> dict[str, Any]:
    return {
        "schema_version": selected_doc.get("schema_version", "project3_stage3x_selected_feature_contracts_v1"),
        "generated_at": generated_at,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "source_selected_contracts_file": str(SELECTED_CONTRACTS),
        "source_selected_contracts_sha256": source_sha,
        "selection_policy": selection_policy,
        "contracts": top_contracts,
    }


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_command(
    *,
    validate_only: bool = False,
    top_n: int = DEFAULT_TOP_N,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    cost_scenarios: tuple[str, ...] = (DEFAULT_COST_SCENARIO,),
) -> list[str]:
    cmd = [
        str(PYTHON_BIN),
        str(AGENT_MULTI_TOOL),
        "--selected-contracts",
        str(SMOKE_SHORTLIST_JSON),
        "--output-dir",
        str(AGENT_MULTI_OUTPUT_DIR),
        "--top-n",
        str(top_n),
        "--seeds",
        ",".join(str(seed) for seed in seeds),
    ]
    if len(cost_scenarios) == 1:
        cmd.extend(["--cost-scenario", cost_scenarios[0]])
    else:
        cmd.extend(["--cost-scenarios", ",".join(cost_scenarios)])
    if validate_only:
        cmd.append("--validate-only")
    return cmd


def eligible_followup_contract_ids() -> list[str]:
    if not SMOKE_SYNTHESIS.exists():
        return []
    synthesis = load_json(SMOKE_SYNTHESIS)
    if synthesis.get("stage_c_access") != "DENIED":
        return []
    if synthesis.get("next_action") != "select_targeted_cost_seed_followup":
        return []
    ids: list[str] = []
    for row in synthesis.get("contract_summary") or []:
        if row.get("recommended_action") == "eligible_for_targeted_cost_seed_followup":
            cid = str(row.get("contract_id") or "")
            if cid:
                ids.append(cid)
    return ids


def historical_smoke_contract_ids() -> set[str]:
    """Contracts already covered by valid Stage 3X smoke dispatch states.

    The current synthesis file is a single-batch view. The dispatcher archives
    completed batches before writing the next manifest, so use those archives
    to avoid retesting already-covered contracts. Deliberately ignore
    ``archive_invalid_*`` directories because those runs were rejected as bad
    evidence and must not count as coverage.
    """
    state_files = [AGENT_MULTI_OUTPUT_DIR / "stage3x_sac_smoke_dispatch_state.json"]
    state_files.extend(
        sorted(AGENT_MULTI_OUTPUT_DIR.glob("archive_completed*/stage3x_sac_smoke_dispatch_state.json"))
    )
    ids: set[str] = set()
    for state_file in state_files:
        if not state_file.exists():
            continue
        try:
            state = load_json(state_file)
        except Exception:
            continue
        if state.get("stage_c_access") != "DENIED":
            continue
        for task in state.get("tasks") or []:
            if task.get("status") not in {"done", "failed"}:
                continue
            cid = str(task.get("contract_id") or "")
            if cid:
                ids.add(cid)
    return ids


def completed_smoke_contract_ids_for_secondary_subset() -> set[str]:
    """Return contracts already covered by a completed smoke/follow-up synthesis."""
    if not SMOKE_SYNTHESIS.exists():
        return set()
    synthesis = load_json(SMOKE_SYNTHESIS)
    if synthesis.get("stage_c_access") != "DENIED":
        return set()
    if synthesis.get("next_action") != "return_to_cpu_feature_screen_or_next_smoke_subset":
        return set()
    return historical_smoke_contract_ids() | {
        str(row.get("contract_id"))
        for row in synthesis.get("contract_summary") or []
        if row.get("contract_id")
    }


def followup_contracts(
    contracts: list[dict[str, Any]],
    eligible_ids: list[str],
) -> list[dict[str, Any]]:
    by_id = {str(row.get("contract_id")): row for row in contracts}
    return [by_id[cid] for cid in eligible_ids if cid in by_id]


def secondary_smoke_contracts(
    contracts: list[dict[str, Any]],
    excluded_ids: set[str],
    top_n: int,
) -> list[dict[str, Any]]:
    remaining = [row for row in contracts if str(row.get("contract_id")) not in excluded_ids]
    return ranked_contracts(remaining, top_n)


def build_request() -> dict[str, Any]:
    generated_at = utc_now()
    blockers: list[dict[str, str]] = []
    selected_doc: dict[str, Any] = {}
    guard_doc: dict[str, Any] = {}

    if not SELECTED_CONTRACTS.exists():
        blockers.append(
            {
                "code": "MISSING_SELECTED_CONTRACTS",
                "message": f"Selected feature contracts file not found: {SELECTED_CONTRACTS}",
            }
        )
    else:
        selected_doc = load_json(SELECTED_CONTRACTS)

    if not ABSURDITY_GUARD.exists():
        blockers.append(
            {
                "code": "MISSING_ABSURDITY_GUARD",
                "message": f"Absurdity guard report not found: {ABSURDITY_GUARD}",
            }
        )
    else:
        guard_doc = load_json(ABSURDITY_GUARD)

    if selected_doc and str(selected_doc.get("stage_c_access", "DENIED")).upper() != "DENIED":
        blockers.append(
            {
                "code": "SELECTED_CONTRACTS_STAGE_C_NOT_DENIED",
                "message": "selected_feature_contracts.json does not deny Stage C.",
            }
        )
    if selected_doc and bool(selected_doc.get("training_launched")):
        blockers.append(
            {
                "code": "SELECTED_CONTRACTS_MARKED_TRAINING_LAUNCHED",
                "message": "selected_feature_contracts.json says training_launched=true.",
            }
        )

    contracts = selected_doc.get("contracts", []) if selected_doc else []
    if selected_doc and not contracts:
        blockers.append(
            {
                "code": "NO_SELECTED_CONTRACTS",
                "message": "selected_feature_contracts.json has no contracts.",
            }
        )

    if guard_doc and str(guard_doc.get("stage_c_access", "DENIED")).upper() != "DENIED":
        blockers.append(
            {
                "code": "GUARD_STAGE_C_NOT_DENIED",
                "message": "absurdity guard does not deny Stage C.",
            }
        )
    if guard_doc and not bool(guard_doc.get("small_sac_smoke_allowed")):
        blockers.append(
            {
                "code": "SMALL_SAC_SMOKE_BLOCKED_BY_GUARD",
                "message": "absurdity guard blocks the small SAC smoke plan.",
            }
        )

    eligible_ids = eligible_followup_contract_ids()
    secondary_excluded_ids = completed_smoke_contract_ids_for_secondary_subset()
    if eligible_ids:
        mode = "targeted_cost_seed_followup"
    elif secondary_excluded_ids:
        mode = "secondary_sac_smoke"
    else:
        mode = "small_sac_smoke"
    seeds = FOLLOWUP_SEEDS if mode == "targeted_cost_seed_followup" else DEFAULT_SEEDS
    cost_scenarios = (
        FOLLOWUP_COST_SCENARIOS
        if mode == "targeted_cost_seed_followup"
        else (DEFAULT_COST_SCENARIO,)
    )
    if mode == "targeted_cost_seed_followup":
        top_contracts = followup_contracts(list(contracts), eligible_ids)
        missing = [cid for cid in eligible_ids if cid not in {str(row.get("contract_id")) for row in top_contracts}]
        if missing:
            blockers.append(
                {
                    "code": "FOLLOWUP_CONTRACTS_NOT_IN_SELECTED_SOURCE",
                    "message": f"Eligible follow-up contract(s) missing from selected source: {missing}",
                }
            )
    elif mode == "secondary_sac_smoke":
        top_contracts = secondary_smoke_contracts(list(contracts), secondary_excluded_ids, DEFAULT_TOP_N) if contracts else []
        if contracts and not top_contracts:
            blockers.append(
                {
                    "code": "NO_UNTESTED_CONTRACTS_FOR_SECONDARY_SMOKE",
                    "message": "Smoke synthesis asked for another subset, but every selected contract is already covered.",
                }
            )
    else:
        top_contracts = smoke_shortlist_contracts(list(contracts), DEFAULT_TOP_N) if contracts else []
    requested_top_n = len(top_contracts) if mode == "targeted_cost_seed_followup" else DEFAULT_TOP_N
    expected_config_count = len(top_contracts) * len(seeds) * len(cost_scenarios)
    request_allowed = not blockers and expected_config_count > 0
    source_selected_sha = sha256_file(SELECTED_CONTRACTS) if SELECTED_CONTRACTS.exists() else ""
    shortlist_doc = (
        build_shortlist_doc(
            selected_doc=selected_doc,
            top_contracts=top_contracts,
            source_sha=source_selected_sha,
            generated_at=generated_at,
            selection_policy=(
                "stage3x_targeted_cost_seed_followup_v1"
                if mode == "targeted_cost_seed_followup"
                else "stage3x_secondary_smoke_subset_after_blocked_followup_v1"
                if mode == "secondary_sac_smoke"
                else "research_review_diverse_smoke_subset_v1"
            ),
        )
        if selected_doc and top_contracts
        else {}
    )
    shortlist_sha = hashlib.sha256(canonical_json_bytes(shortlist_doc)).hexdigest() if shortlist_doc else ""

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "stage_c_access": "DENIED",
        "heldout_start": HELDOUT_START,
        "training_launched": False,
        "request_mode": mode,
        "request_allowed": request_allowed,
        "blockers": blockers,
        "source_selected_contracts_file": str(SELECTED_CONTRACTS),
        "source_selected_contracts_sha256": source_selected_sha,
        "selected_contracts_file": str(SMOKE_SHORTLIST_JSON),
        "selected_contracts_sha256": shortlist_sha,
        "smoke_shortlist_file": str(SMOKE_SHORTLIST_JSON),
        "selected_contract_count": len(contracts),
        "requested_top_n": requested_top_n,
        "requested_seed_count": len(seeds),
        "requested_seeds": list(seeds),
        "requested_cost_scenario": cost_scenarios[0] if len(cost_scenarios) == 1 else "multiple",
        "requested_cost_scenarios": list(cost_scenarios),
        "expected_config_count": expected_config_count,
        "selected_contract_ids": [str(row.get("contract_id")) for row in top_contracts],
        "excluded_contract_ids": sorted(secondary_excluded_ids) if mode == "secondary_sac_smoke" else [],
        "agent_multi_root": str(AGENT_MULTI_ROOT),
        "agent_multi_tool": str(AGENT_MULTI_TOOL),
        "agent_multi_output_dir": str(AGENT_MULTI_OUTPUT_DIR),
        "expected_manifest": str(AGENT_MULTI_OUTPUT_DIR / "stage3x_sac_smoke_plan_manifest.json"),
        "commands": {
            "validate_only": build_command(
                validate_only=True,
                top_n=requested_top_n,
                seeds=seeds,
                cost_scenarios=cost_scenarios,
            ),
            "write_locked_plan": build_command(
                validate_only=False,
                top_n=requested_top_n,
                seeds=seeds,
                cost_scenarios=cost_scenarios,
            ),
        },
        "guard_summary": {
            "broad_gpu_launch_allowed": bool(guard_doc.get("broad_gpu_launch_allowed", False)),
            "small_sac_smoke_allowed": bool(guard_doc.get("small_sac_smoke_allowed", False)),
            "issue_count": int(guard_doc.get("issue_count") or 0) if guard_doc else None,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Stage 3X SAC Smoke Request",
        "",
        f"Generated UTC: `{payload['generated_at']}`",
        "",
        f"- Stage C access: `{payload['stage_c_access']}`",
        f"- Training launched by this worker: `{payload['training_launched']}`",
        f"- Request mode: `{payload['request_mode']}`",
        f"- Request allowed: `{payload['request_allowed']}`",
        f"- Selected contracts available: `{payload['selected_contract_count']}`",
        f"- Top contracts requested: `{payload['requested_top_n']}`",
        f"- Seeds: `{payload['requested_seeds']}`",
        f"- Cost scenarios: `{payload['requested_cost_scenarios']}`",
        f"- Expected configs: `{payload['expected_config_count']}`",
        f"- Expected manifest: `{payload['expected_manifest']}`",
        f"- Smoke shortlist: `{payload['smoke_shortlist_file']}`",
        "",
        "## Selected Contracts",
        "",
    ]
    for cid in payload["selected_contract_ids"]:
        lines.append(f"- `{cid}`")
    lines.extend(["", "## Commands", ""])
    lines.append("Validate only:")
    lines.append("")
    lines.append("```bash")
    lines.append(" ".join(payload["commands"]["validate_only"]))
    lines.append("```")
    lines.append("")
    lines.append("Write locked plan files, still no training:")
    lines.append("")
    lines.append("```bash")
    lines.append(" ".join(payload["commands"]["write_locked_plan"]))
    lines.append("```")
    if payload["blockers"]:
        lines.extend(["", "## Blockers", ""])
        for blocker in payload["blockers"]:
            lines.append(f"- `{blocker['code']}`: {blocker['message']}")
    return "\n".join(lines) + "\n"


def write_request(payload: dict[str, Any]) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")
    selected_doc = load_json(SELECTED_CONTRACTS)
    selected_ids = set(payload["selected_contract_ids"])
    shortlist = build_shortlist_doc(
        selected_doc=selected_doc,
        top_contracts=[
            row
            for row in selected_doc.get("contracts", [])
            if str(row.get("contract_id")) in selected_ids
        ],
        source_sha=payload["source_selected_contracts_sha256"],
        generated_at=payload["generated_at"],
        selection_policy=(
            "stage3x_targeted_cost_seed_followup_v1"
            if payload["request_mode"] == "targeted_cost_seed_followup"
            else "stage3x_secondary_smoke_subset_after_blocked_followup_v1"
            if payload["request_mode"] == "secondary_sac_smoke"
            else "research_review_diverse_smoke_subset_v1"
        ),
    )
    # Preserve the exact requested order rather than source-file order.
    by_id = {str(row.get("contract_id")): row for row in shortlist["contracts"]}
    shortlist["contracts"] = [by_id[cid] for cid in payload["selected_contract_ids"] if cid in by_id]
    SMOKE_SHORTLIST_JSON.write_text(
        canonical_json_bytes(shortlist).decode("utf-8"),
        encoding="utf-8",
    )


def main() -> None:
    payload = build_request()
    write_request(payload)
    print(
        json.dumps(
            {
                "ok": True,
                "request_allowed": payload["request_allowed"],
                "expected_config_count": payload["expected_config_count"],
                "report_json": str(OUT_JSON),
                "report_md": str(OUT_MD),
                "training_launched": False,
                "stage_c_access": "DENIED",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
