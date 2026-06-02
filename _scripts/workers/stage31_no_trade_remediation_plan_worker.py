#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
DIAGNOSTIC_CSV = ROOT / "experiments" / "stage_a_screening" / "hardening" / "no_trade_diagnostic_report.csv"
OUT_DIR = ROOT / "experiments" / "stage_a_screening" / "hardening"
OUT_CSV = OUT_DIR / "no_trade_remediation_plan.csv"
OUT_JSON = OUT_DIR / "no_trade_remediation_plan.json"
OUT_MD = OUT_DIR / "no_trade_remediation_plan.md"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_rows() -> list[dict[str, str]]:
    with DIAGNOSTIC_CSV.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def existing_signatures() -> set[str]:
    signatures: set[str] = set()
    for config_path in (ROOT / "experiments" / "stage_a_screening" / "configs").glob("**/*.json"):
        cfg = read_json(config_path)
        if cfg:
            signatures.add(signature_from_config(cfg))
    for config_path in (ROOT / "experiments" / "stage_a_screening" / "runs").glob("**/config.json"):
        cfg = read_json(config_path)
        if cfg:
            signatures.add(signature_from_config(cfg))
    return signatures


def signature_from_config(cfg: dict[str, Any]) -> str:
    keys = [
        "asset",
        "timeframe",
        "agent_plugin",
        "features_preset",
        "train_seed",
        "total_timesteps",
        "continuous_action_threshold",
        "ent_coef",
        "exploration_fraction",
        "exploration_final_eps",
        "no_trade_fix_id",
    ]
    return "|".join(f"{key}={cfg.get(key, '')}" for key in keys)


def base_config_from_row(row: dict[str, str]) -> dict[str, Any]:
    run_dir = Path(row.get("run_dir") or "")
    cfg = read_json(run_dir / "config.json")
    if cfg:
        return cfg
    algo = row.get("algo", "")
    return {
        "asset": f"{row.get('asset', '')}_{row.get('timeframe', '')}",
        "timeframe": row.get("timeframe", ""),
        "agent_plugin": f"{algo}_agent" if algo else "",
        "features_preset": row.get("preset", ""),
        "train_seed": row.get("seed", ""),
        "total_timesteps": "",
    }


def proposal_for(row: dict[str, str]) -> tuple[str, dict[str, Any], str]:
    diagnosis = row.get("no_trade_diagnosis", "")
    algo = row.get("algo", "")
    if diagnosis == "policy_deadband_collapse" and algo == "sac":
        return (
            "diagnostic_sac_threshold_005",
            {
                "no_trade_fix_id": "sac_threshold_005",
                "continuous_action_threshold": 0.05,
                "no_trade_preflight_required": True,
                "diagnostic_only": True,
            },
            "SAC raw actions were inside the 0.10 deadband; test a lower threshold as a new diagnostic trial.",
        )
    if diagnosis == "policy_hold_collapse" and algo == "ppo":
        return (
            "diagnostic_ppo_entropy_003",
            {
                "no_trade_fix_id": "ppo_entropy_003",
                "ent_coef": 0.03,
                "no_trade_preflight_required": True,
                "diagnostic_only": True,
            },
            "PPO selected hold almost always; test stronger entropy pressure as a new diagnostic trial.",
        )
    if diagnosis == "policy_hold_collapse" and algo == "dqn":
        return (
            "diagnostic_dqn_exploration_015",
            {
                "no_trade_fix_id": "dqn_exploration_015",
                "exploration_final_eps": 0.15,
                "exploration_fraction": 0.35,
                "no_trade_preflight_required": True,
                "diagnostic_only": True,
            },
            "DQN selected hold almost always; test higher sustained exploration as a new diagnostic trial.",
        )
    if diagnosis.startswith("needs_"):
        return (
            "skip_or_telemetry_rerun_only",
            {
                "no_trade_fix_id": "telemetry_only_no_trade_classification",
                "no_trade_preflight_required": True,
                "diagnostic_only": True,
                "repeat_training_params": True,
            },
            "Old run lacks readable action trace. Rerun only if classification is required; it is not promotion evidence.",
        )
    return (
        "manual_review",
        {
            "no_trade_fix_id": "manual_review_required",
            "no_trade_preflight_required": True,
            "diagnostic_only": True,
        },
        "No automatic parameter remediation selected; inspect execution diagnostics manually.",
    )


def main() -> int:
    rows = load_rows()
    existing = existing_signatures()
    out_rows: list[dict[str, Any]] = []
    by_action = Counter()
    duplicate_count = 0
    for row in rows:
        base = base_config_from_row(row)
        action, patch, reason = proposal_for(row)
        proposed = dict(base)
        proposed.update(patch)
        sig = signature_from_config(proposed)
        duplicate = sig in existing
        duplicate_count += int(duplicate)
        by_action[action] += 1
        out_rows.append(
            {
                "run_slug": row.get("run_slug", ""),
                "asset": row.get("asset", ""),
                "timeframe": row.get("timeframe", ""),
                "algo": row.get("algo", ""),
                "preset": row.get("preset", ""),
                "seed": row.get("seed", ""),
                "diagnosis": row.get("no_trade_diagnosis", ""),
                "recommended_action": action,
                "parameter_patch_json": json.dumps(patch, sort_keys=True),
                "duplicate_existing_exact_signature": duplicate,
                "promotion_eligible": False,
                "requires_preflight": True,
                "reason": reason,
                "run_dir": row.get("run_dir", ""),
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_slug",
        "asset",
        "timeframe",
        "algo",
        "preset",
        "seed",
        "diagnosis",
        "recommended_action",
        "parameter_patch_json",
        "duplicate_existing_exact_signature",
        "promotion_eligible",
        "requires_preflight",
        "reason",
        "run_dir",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in out_rows:
            writer.writerow({field: item.get(field, "") for field in fields})

    payload = {
        "schema_version": "project3_no_trade_remediation_plan_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "diagnostic_csv": str(DIAGNOSTIC_CSV),
        "rows": len(out_rows),
        "counts_by_recommended_action": dict(sorted(by_action.items())),
        "duplicate_existing_exact_signature_count": duplicate_count,
        "outputs": {"csv": str(OUT_CSV), "markdown": str(OUT_MD)},
        "policy": {
            "no_trade_runs_are_promotion_eligible": False,
            "diagnostic_variants_are_new_trials": True,
            "preflight_required_before_training": True,
            "do_not_repeat_exact_failed_parameters": True,
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Stage 3.1 No-Trade Remediation Plan",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Rows: `{len(out_rows)}`",
        f"Duplicate proposed exact signatures: `{duplicate_count}`",
        "",
        "## Policy",
        "",
        "- No-trade runs remain hard kills and are not promotion evidence.",
        "- Diagnostic variants are new trials and must pass forced-action no-trade preflight before training.",
        "- Exact failed parameters must not be repeated as normal jobs.",
        "",
        "## Counts By Action",
        "",
        "| Action | Rows |",
        "| --- | ---: |",
    ]
    for action, count in sorted(by_action.items()):
        lines.append(f"| {action} | {count} |")
    lines += [
        "",
        "## Output Files",
        "",
        f"- CSV: `{OUT_CSV}`",
        f"- JSON: `{OUT_JSON}`",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
