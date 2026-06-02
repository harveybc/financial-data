#!/usr/bin/env python3
"""Validate the agent-multi Stage 3X SAC smoke-plan manifest.

The acceptance worker is fail-closed: it can approve a locked smoke-plan
manifest for later human/supervisor dispatch, but it does not launch training.
If the manifest is missing because Copilot is still working, it reports a
waiting state rather than inventing progress.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT_MULTI_ROOT = ROOT.parent / "agent-multi"
REQUEST_JSON = (
    ROOT
    / "experiments"
    / "stage3x_sac_smoke_request"
    / "stage3x_sac_smoke_request.json"
)
MANIFEST_JSON = (
    AGENT_MULTI_ROOT
    / "experiments"
    / "stage3x_sac_smoke_plan"
    / "stage3x_sac_smoke_plan_manifest.json"
)
OUT_ROOT = ROOT / "experiments" / "stage3x_sac_smoke_request"
OUT_JSON = OUT_ROOT / "stage3x_sac_smoke_plan_acceptance.json"
OUT_MD = OUT_ROOT / "stage3x_sac_smoke_plan_acceptance.md"

SCHEMA_VERSION = "project3_stage3x_sac_smoke_plan_acceptance_v1"
MANIFEST_SCHEMA_VERSION = "project3_stage3x_sac_smoke_plan_v1"
HELDOUT_START = "2025-01-01"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_issue(
    issues: list[dict[str, Any]],
    code: str,
    message: str,
    severity: str = "block",
    evidence: Any = None,
) -> None:
    issues.append(
        {
            "code": code,
            "severity": severity,
            "message": message,
            "evidence": evidence,
        }
    )


def _is_true(value: Any) -> bool:
    return value is True


def _is_false(value: Any) -> bool:
    return value is False


def validate_config(
    *,
    config_path: Path,
    entry: dict[str, Any],
    selected_contract_ids: set[str],
    allowed_cost_scenarios: set[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not config_path.exists():
        add_issue(issues, "CONFIG_FILE_MISSING", f"Config file missing: {config_path}")
        return issues

    try:
        cfg = load_json(config_path)
    except Exception as exc:
        add_issue(issues, "CONFIG_FILE_UNREADABLE", f"Config file unreadable: {config_path}", evidence=str(exc))
        return issues

    if cfg.get("stage_c_access") != "DENIED":
        add_issue(issues, "CONFIG_STAGE_C_NOT_DENIED", "Config does not set stage_c_access=DENIED.", evidence=str(config_path))
    if not _is_false(cfg.get("final_stage_c_evaluation")):
        add_issue(issues, "CONFIG_FINAL_STAGE_C_FLAG_NOT_FALSE", "Config final_stage_c_evaluation must be false.", evidence=str(config_path))
    if not _is_false(cfg.get("stage_c_acknowledged")):
        add_issue(issues, "CONFIG_STAGE_C_ACK_NOT_FALSE", "Config stage_c_acknowledged must be false.", evidence=str(config_path))
    if not _is_true(cfg.get("_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED")):
        add_issue(issues, "CONFIG_MISSING_STAGE_B_LOCK", "Config missing _NOT_TO_RUN_UNTIL_STAGE_B_APPROVED=true.", evidence=str(config_path))
    if not _is_true(cfg.get("_project3_stage3x_sac_smoke")):
        add_issue(issues, "CONFIG_MISSING_STAGE3X_SMOKE_FLAG", "Config missing _project3_stage3x_sac_smoke=true.", evidence=str(config_path))
    if "sac" not in str(cfg.get("agent_plugin", "")).lower():
        add_issue(issues, "CONFIG_NOT_SAC", "Config agent_plugin is not SAC-scoped.", evidence=cfg.get("agent_plugin"))
    if any(name in str(cfg.get("agent_plugin", "")).lower() for name in ("ppo", "dqn")):
        add_issue(issues, "CONFIG_FORBIDDEN_ALGO", "Config agent_plugin mentions PPO or DQN.", evidence=cfg.get("agent_plugin"))

    feature_list = cfg.get("feature_list")
    feature_columns = cfg.get("feature_columns")
    if not isinstance(feature_list, list) or not feature_list:
        add_issue(issues, "CONFIG_EMPTY_FEATURE_LIST", "Config feature_list must be a non-empty list.", evidence=str(config_path))
    if not isinstance(feature_columns, list) or not feature_columns:
        add_issue(issues, "CONFIG_EMPTY_FEATURE_COLUMNS", "Config feature_columns must be a non-empty list.", evidence=str(config_path))
    if isinstance(feature_list, list) and isinstance(feature_columns, list) and feature_list != feature_columns:
        add_issue(issues, "CONFIG_FEATURE_LIST_COLUMNS_MISMATCH", "feature_list and feature_columns differ.", evidence=str(config_path))

    contract_id = str(cfg.get("_stage3x_contract_id") or entry.get("contract_id") or "")
    if contract_id not in selected_contract_ids:
        add_issue(issues, "CONFIG_CONTRACT_NOT_REQUESTED", "Config contract_id was not requested.", evidence=contract_id)

    input_data_file = Path(str(cfg.get("input_data_file") or ""))
    if not input_data_file.exists():
        add_issue(issues, "CONFIG_INPUT_DATA_FILE_MISSING", "Config input_data_file does not exist.", evidence=str(input_data_file))

    for key in ("return_trace_dir", "return_trace_file", "progress_file"):
        if not cfg.get(key):
            add_issue(issues, f"CONFIG_MISSING_{key.upper()}", f"Config missing {key}.", evidence=str(config_path))

    cost = cfg.get("_cost_scenario") or entry.get("cost_scenario")
    if cost not in allowed_cost_scenarios:
        add_issue(
            issues,
            "CONFIG_COST_NOT_REQUESTED",
            "Config cost scenario was not requested by financial-data.",
            evidence=cost,
        )
    try:
        commission = float(cfg.get("commission"))
    except (TypeError, ValueError):
        commission = -1.0
    if commission <= 0:
        add_issue(
            issues,
            "CONFIG_NON_POSITIVE_COMMISSION",
            "Config commission must be a positive explicit value for cost-aware Stage 3X runs.",
            evidence={"cost_scenario": cost, "commission": cfg.get("commission")},
        )
    multiplier = cfg.get("_cost_multiplier")
    expected_multiplier = {"base": 1.0, "plus_50pct": 1.5, "plus_100pct": 2.0}.get(str(cost))
    if expected_multiplier is not None and float(multiplier or -1.0) != expected_multiplier:
        add_issue(
            issues,
            "CONFIG_COST_MULTIPLIER_MISMATCH",
            "Config _cost_multiplier does not match the requested cost scenario.",
            evidence={"cost_scenario": cost, "_cost_multiplier": multiplier},
        )

    return issues


def build_acceptance() -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    request: dict[str, Any] = {}

    if not REQUEST_JSON.exists():
        add_issue(
            issues,
            "REQUEST_PACKET_MISSING",
            f"Smoke request packet missing: {REQUEST_JSON}",
            severity="wait",
        )
    else:
        request = load_json(REQUEST_JSON)

    if not MANIFEST_JSON.exists():
        add_issue(
            issues,
            "WAITING_FOR_COPILOT_MANIFEST",
            f"agent-multi manifest is not present yet: {MANIFEST_JSON}",
            severity="wait",
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "stage_c_access": "DENIED",
            "training_launched": False,
            "accepted": False,
            "status": "WAITING_FOR_COPILOT_MANIFEST",
            "issue_count": len(issues),
            "issues": issues,
            "request_file": str(REQUEST_JSON),
            "manifest_file": str(MANIFEST_JSON),
            "config_count": 0,
        }

    manifest = load_json(MANIFEST_JSON)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        add_issue(
            issues,
            "MANIFEST_SCHEMA_MISMATCH",
            "Unexpected smoke-plan manifest schema.",
            evidence=manifest.get("schema_version"),
        )
    if manifest.get("stage_c_access") != "DENIED":
        add_issue(issues, "MANIFEST_STAGE_C_NOT_DENIED", "Manifest does not deny Stage C.")
    if not _is_false(manifest.get("final_stage_c_evaluation")):
        add_issue(issues, "MANIFEST_FINAL_STAGE_C_FLAG_NOT_FALSE", "Manifest final_stage_c_evaluation must be false.")
    if not _is_false(manifest.get("stage_c_acknowledged")):
        add_issue(issues, "MANIFEST_STAGE_C_ACK_NOT_FALSE", "Manifest stage_c_acknowledged must be false.")
    if not _is_false(manifest.get("training_launched")):
        add_issue(issues, "MANIFEST_TRAINING_LAUNCHED", "Manifest says training_launched is not false.")
    if not _is_true(manifest.get("_project3_stage3x_sac_smoke")):
        add_issue(issues, "MANIFEST_MISSING_SMOKE_FLAG", "Manifest missing _project3_stage3x_sac_smoke=true.")
    if manifest.get("heldout_start") != HELDOUT_START:
        add_issue(issues, "MANIFEST_HELDOUT_START_MISMATCH", "Manifest heldout_start mismatch.", evidence=manifest.get("heldout_start"))

    rules = manifest.get("rules", {})
    if rules.get("broad_gpu_launch_allowed") is not False:
        add_issue(issues, "MANIFEST_BROAD_GPU_NOT_BLOCKED", "Manifest must keep broad_gpu_launch_allowed=false.")
    if rules.get("sac_only") is not True:
        add_issue(issues, "MANIFEST_NOT_SAC_ONLY", "Manifest rules.sac_only must be true.")

    requested_cost_scenarios = set(
        str(x)
        for x in (
            request.get("requested_cost_scenarios")
            or [request.get("requested_cost_scenario") or "base"]
        )
    )
    manifest_cost_scenarios = set(
        str(x)
        for x in (
            manifest.get("cost_scenarios")
            or [manifest.get("cost_scenario") or "base"]
        )
    )
    if requested_cost_scenarios and manifest_cost_scenarios != requested_cost_scenarios:
        add_issue(
            issues,
            "MANIFEST_COST_SCENARIOS_MISMATCH",
            "Manifest cost scenarios do not match financial-data request.",
            evidence={
                "manifest": sorted(manifest_cost_scenarios),
                "request": sorted(requested_cost_scenarios),
            },
        )

    configs = manifest.get("configs")
    if not isinstance(configs, list) or not configs:
        add_issue(issues, "MANIFEST_EMPTY_CONFIGS", "Manifest has no configs.")
        configs = []

    expected_config_count = int(request.get("expected_config_count") or 0) if request else 0
    if expected_config_count and int(manifest.get("config_count") or 0) != expected_config_count:
        add_issue(
            issues,
            "MANIFEST_CONFIG_COUNT_MISMATCH",
            "Manifest config_count does not match financial-data request.",
            evidence={
                "manifest": manifest.get("config_count"),
                "request": expected_config_count,
            },
        )
    if int(manifest.get("config_count") or 0) != len(configs):
        add_issue(
            issues,
            "MANIFEST_CONFIG_COUNT_FIELD_MISMATCH",
            "Manifest config_count does not match configs length.",
            evidence={"field": manifest.get("config_count"), "len": len(configs)},
        )

    request_sha = request.get("selected_contracts_sha256") if request else ""
    if request_sha and manifest.get("selected_contracts_sha256") != request_sha:
        add_issue(
            issues,
            "SELECTED_CONTRACTS_SHA_MISMATCH",
            "Manifest selected_contracts_sha256 does not match request.",
            evidence={
                "manifest": manifest.get("selected_contracts_sha256"),
                "request": request_sha,
            },
        )
    selected_path = Path(str(manifest.get("selected_contracts_file") or ""))
    if selected_path.exists():
        actual_sha = sha256_file(selected_path)
        if manifest.get("selected_contracts_sha256") != actual_sha:
            add_issue(
                issues,
                "SELECTED_CONTRACTS_SHA_DOES_NOT_MATCH_BYTES",
                "Manifest selected_contracts_sha256 does not match file bytes.",
                evidence={"manifest": manifest.get("selected_contracts_sha256"), "actual": actual_sha},
            )
    else:
        add_issue(issues, "SELECTED_CONTRACTS_FILE_MISSING", "Manifest selected_contracts_file is missing.", evidence=str(selected_path))

    selected_contract_ids = set(str(x) for x in request.get("selected_contract_ids", [])) if request else set()
    if not selected_contract_ids:
        selected_contract_ids = set(str(x) for x in manifest.get("selected_contract_ids", []))

    config_issue_count = 0
    manifest_config_files = {
        str(Path(str(entry.get("config_file") or "")).resolve())
        for entry in configs
        if entry.get("config_file")
    }
    manifest_dir = MANIFEST_JSON.parent
    config_dir = manifest_dir / "configs"
    if config_dir.exists():
        extra_config_files = [
            str(path.resolve())
            for path in sorted(config_dir.glob("*.json"))
            if str(path.resolve()) not in manifest_config_files
        ]
        if extra_config_files:
            add_issue(
                issues,
                "UNMANIFESTED_CONFIG_FILES_PRESENT",
                "Config directory contains JSON files not listed in the accepted manifest.",
                evidence=extra_config_files,
            )

    for entry in configs:
        entry_issues = validate_config(
            config_path=Path(str(entry.get("config_file") or "")),
            entry=dict(entry),
            selected_contract_ids=selected_contract_ids,
            allowed_cost_scenarios=requested_cost_scenarios or {"base"},
        )
        config_issue_count += len(entry_issues)
        issues.extend(entry_issues)

    accepted = not any(issue["severity"] != "info" for issue in issues)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "stage_c_access": "DENIED",
        "training_launched": False,
        "accepted": accepted,
        "status": "ACCEPTED_LOCKED_SMOKE_PLAN" if accepted else "REJECTED_LOCKED_SMOKE_PLAN",
        "issue_count": len(issues),
        "config_issue_count": config_issue_count,
        "issues": issues,
        "request_file": str(REQUEST_JSON),
        "manifest_file": str(MANIFEST_JSON),
        "manifest_sha256": sha256_file(MANIFEST_JSON),
        "config_count": len(configs),
        "selected_contract_ids": list(manifest.get("selected_contract_ids", [])),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Stage 3X SAC Smoke Plan Acceptance",
        "",
        f"Generated UTC: `{payload['generated_at']}`",
        "",
        f"- Status: `{payload['status']}`",
        f"- Accepted: `{payload['accepted']}`",
        f"- Stage C access: `{payload['stage_c_access']}`",
        f"- Training launched by this worker: `{payload['training_launched']}`",
        f"- Config count: `{payload['config_count']}`",
        f"- Issues: `{payload['issue_count']}`",
        f"- Manifest: `{payload['manifest_file']}`",
        "",
        "## Issues",
        "",
        "| severity | code | message |",
        "| --- | --- | --- |",
    ]
    for issue in payload["issues"]:
        lines.append(f"| `{issue['severity']}` | `{issue['code']}` | {issue['message']} |")
    if not payload["issues"]:
        lines.append("| `none` | `NONE` | Locked smoke plan accepted. |")
    return "\n".join(lines) + "\n"


def write_acceptance(payload: dict[str, Any]) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")


def main() -> None:
    global REQUEST_JSON, MANIFEST_JSON, OUT_ROOT, OUT_JSON, OUT_MD
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-json", type=Path, default=REQUEST_JSON)
    parser.add_argument("--manifest-json", type=Path, default=MANIFEST_JSON)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    args = parser.parse_args()
    REQUEST_JSON = args.request_json
    MANIFEST_JSON = args.manifest_json
    OUT_ROOT = args.out_root
    OUT_JSON = OUT_ROOT / "stage3x_sac_smoke_plan_acceptance.json"
    OUT_MD = OUT_ROOT / "stage3x_sac_smoke_plan_acceptance.md"
    payload = build_acceptance()
    write_acceptance(payload)
    print(
        json.dumps(
            {
                "ok": True,
                "accepted": payload["accepted"],
                "status": payload["status"],
                "issue_count": payload["issue_count"],
                "config_count": payload["config_count"],
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
