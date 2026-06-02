#!/usr/bin/env python3
"""
Build a locked Stage B run plan from the current Project 3 approval packet.

This worker does not launch training. It emits locked config templates and a
machine-readable manifest so Stage B execution can be reviewed before any GPU
worker is allowed to run the 1M-step validation jobs.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import pathlib
import re
from collections import defaultdict
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
APPROVAL_CSV = ROOT / "experiments/stage_a_screening/stage_b_approval/stage_b_approval_candidates.csv"
INDEX_CSV = ROOT / "experiments/stage_a_screening/index.csv"
LEAKAGE_CSV = ROOT / "experiments/stage_a_screening/hardening/leakage_heldout_audit.csv"
DEFAULT_OUT = ROOT / "experiments/stage_b_validation/run_plan"
HELDOUT_START = "2025-01-01"
TRACE_SCHEMA_VERSION = "stage_b_return_trace_v1"
EVIDENCE_SCHEMA_VERSION = "project3_return_trace_evidence_v1"
PLAN_SCHEMA_VERSION = "project3_stage_b_locked_run_plan_v1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: pathlib.Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    clean = re.sub(r"_+", "_", clean).strip("._")
    return clean or "unknown"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def row_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("asset", ""),
        row.get("timeframe", ""),
        row.get("algo", ""),
        row.get("preset", ""),
        str(row.get("seed", "")),
    )


def comparison_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("asset", ""),
        row.get("timeframe", ""),
        row.get("algo", ""),
        str(row.get("seed", "")),
    )


def load_source_config(run_dir_raw: str) -> tuple[pathlib.Path, dict[str, Any]]:
    run_dir = pathlib.Path(run_dir_raw)
    config_path = run_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing source config: {config_path}")
    return config_path, load_json(config_path)


def validate_source_config(config: dict[str, Any]) -> list[str]:
    missing = []
    for key in ("agent_plugin", "pipeline_plugin", "input_data_file", "asset", "features_preset"):
        if not config.get(key):
            missing.append(key)
    return missing


def build_locked_config(
    *,
    source_config: dict[str, Any],
    source_config_sha256: str,
    source_run_slug: str,
    plan_id: str,
    role: str,
    cost_scenario: str,
    heldout_start: str,
    stage_b_timesteps: int,
    run_dir: pathlib.Path,
    candidate_slug: str,
    baseline_name: str | None,
) -> dict[str, Any]:
    locked = dict(source_config)
    progress_file = str(run_dir / "training_progress.json")
    locked["total_timesteps"] = stage_b_timesteps
    locked["results_file"] = str(run_dir / "summary.json")
    locked["save_model"] = str(run_dir / "policy.zip")
    locked["save_config"] = str(run_dir / "config_out.json")
    trace_dir = run_dir / "traces"
    locked["return_trace_dir"] = str(trace_dir)
    locked["return_trace_file"] = str(trace_dir / "evaluation_return_trace.csv")
    # Source Stage A configs often carry machine-local progress paths. Do not
    # inherit them into Stage B, or the runner and status reader will disagree.
    locked["progress_file"] = progress_file
    locked["training_progress_file"] = progress_file
    locked["progress_update_interval_steps"] = int(
        locked.get("progress_update_interval_steps") or 1000
    )
    locked["no_trade_min_trades"] = max(1, safe_int(locked.get("no_trade_min_trades"), 0))
    locked["stage_c_access"] = "DENIED"
    locked["heldout_start"] = heldout_start
    locked["final_stage_c_evaluation"] = False
    locked["stage_c_acknowledged"] = False
    locked["cost_scenario"] = cost_scenario
    locked["eval_split"] = "stage_b_validation"
    locked["mode"] = "train"
    locked["_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED"] = True
    locked["_project3_stage_b_lock"] = {
        "schema_version": "project3_stage_b_lock_v1",
        "locked": True,
        "reason": "Stage B plan template only; requires operator approval and Stage B runner support.",
        "plan_id": plan_id,
        "role": role,
        "candidate_run_slug": candidate_slug,
        "source_run_slug": source_run_slug,
        "source_config_sha256": source_config_sha256,
        "cost_scenario": cost_scenario,
        "baseline_name": baseline_name,
        "heldout_start": heldout_start,
        "stage_c_access": "DENIED",
        "return_trace_schema_version": TRACE_SCHEMA_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "training_launched": False,
    }
    locked["_project3_progress_contract"] = {
        "progress_file": progress_file,
        "training_progress_file": progress_file,
        "progress_update_interval_steps": locked["progress_update_interval_steps"],
        "required_live_fields": [
            "progress_pct",
            "progress_percent",
            "elapsed_seconds",
            "current_step",
            "num_timesteps",
            "total_timesteps",
            "trades_total",
            "total_return",
            "equity",
        ],
        "no_trade_anomaly_rule": "flag if progress_pct >= 20 and trades_total <= 0",
    }
    return locked


def select_candidates(rows: list[dict[str, str]], limit: int | None = None) -> list[dict[str, str]]:
    selected = [row for row in rows if row.get("stage_b_status") == "BLOCKED_DSR_DEFERRED"]
    selected.sort(key=lambda r: safe_float(r.get("total_return")) or float("-inf"), reverse=True)
    return selected[:limit] if limit else selected


def choose_baseline(
    candidate: dict[str, str],
    by_pair: dict[tuple[str, str, str, str], list[dict[str, str]]],
) -> dict[str, str] | None:
    if candidate.get("preset") == "baseline_12":
        return None
    candidates = [
        row for row in by_pair.get(comparison_key(candidate), [])
        if row.get("preset") == "baseline_12"
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda r: safe_float(r.get("total_return")) or float("-inf"), reverse=True)
    return candidates[0]


def build_plan(
    *,
    approval_csv: pathlib.Path = APPROVAL_CSV,
    index_csv: pathlib.Path = INDEX_CSV,
    leakage_csv: pathlib.Path = LEAKAGE_CSV,
    output_dir: pathlib.Path = DEFAULT_OUT,
    heldout_start: str = HELDOUT_START,
    cost_scenarios: list[str] | None = None,
    stage_b_timesteps: int = 1_000_000,
    limit: int | None = None,
) -> dict[str, Any]:
    cost_scenarios = cost_scenarios or ["base", "pessimistic"]
    output_dir.mkdir(parents=True, exist_ok=True)
    config_dir = output_dir / "configs"
    run_root = ROOT / "experiments/stage_b_validation/runs/locked_plan"
    config_dir.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    for old_config in config_dir.glob("*.json"):
        old_config.unlink()

    approval_rows = read_csv(approval_csv)
    index_rows = read_csv(index_csv)
    leakage_rows = read_csv(leakage_csv) if leakage_csv.exists() else []

    index_by_slug = {row.get("run_slug", ""): row for row in index_rows}
    leakage_by_slug = {row.get("run_slug", ""): row for row in leakage_rows}
    by_pair: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in approval_rows:
        by_pair[comparison_key(row)].append(row)

    selected = select_candidates(approval_rows, limit)
    if not selected:
        raise RuntimeError("No BLOCKED_DSR_DEFERRED candidates found.")

    plan_id = f"project3_stage_b_locked_{utc_now().replace(':', '').replace('+', 'Z')}"
    config_entries: list[dict[str, Any]] = []
    comparison_entries: list[dict[str, Any]] = []
    unique_sources: dict[tuple[str, str, str, str], dict[str, str]] = {}
    missing_baselines: list[str] = []
    blocked_matched_baselines: list[dict[str, str]] = []
    blocked_sources: list[dict[str, str]] = []

    for candidate in selected:
        candidate_slug = candidate["run_slug"]
        baseline = choose_baseline(candidate, by_pair)
        comparison = {
            "candidate_run_slug": candidate_slug,
            "candidate_asset": candidate.get("asset", ""),
            "candidate_timeframe": candidate.get("timeframe", ""),
            "candidate_algo": candidate.get("algo", ""),
            "candidate_preset": candidate.get("preset", ""),
            "candidate_seed": candidate.get("seed", ""),
            "candidate_stage_a_return": candidate.get("total_return", ""),
            "candidate_stage_a_sharpe": candidate.get("sharpe_ratio", ""),
            "candidate_stage_a_trades": candidate.get("trades_total", ""),
            "matched_baseline_run_slug": baseline.get("run_slug") if baseline else "",
            "matched_baseline_status": baseline.get("stage_b_status") if baseline else "MISSING_OR_SELF_BASELINE_12",
            "matched_baseline_return": baseline.get("total_return") if baseline else "",
            "matched_baseline_sharpe": baseline.get("sharpe_ratio") if baseline else "",
            "matched_baseline_trades": baseline.get("trades_total") if baseline else "",
        }
        comparison_entries.append(comparison)
        unique_sources[(candidate_slug, "candidate", "", "")] = candidate
        if baseline:
            unique_sources[(baseline["run_slug"], "rl_baseline_12", "", "baseline_12")] = baseline
        elif candidate.get("preset") != "baseline_12":
            missing_baselines.append(candidate_slug)

    for (source_slug, role, candidate_slug_for_baseline, baseline_name), row in sorted(unique_sources.items()):
        index_row = index_by_slug.get(source_slug)
        leakage_row = leakage_by_slug.get(source_slug)
        if not index_row:
            issue = {"run_slug": source_slug, "reason": "missing_index_row", "role": role}
            if role == "candidate":
                blocked_sources.append(issue)
            else:
                blocked_matched_baselines.append(issue)
            continue
        if not leakage_row or leakage_row.get("status") != "PASS_HELDOUT_FIREWALL":
            issue = {
                "run_slug": source_slug,
                "reason": "heldout_firewall_not_passed",
                "leakage_status": leakage_row.get("status", "MISSING") if leakage_row else "MISSING",
                "role": role,
            }
            if role == "candidate":
                blocked_sources.append(issue)
            else:
                blocked_matched_baselines.append(issue)
            continue

        source_config_path, source_config = load_source_config(index_row.get("run_dir", ""))
        missing_fields = validate_source_config(source_config)
        if missing_fields:
            issue = {
                "run_slug": source_slug,
                "reason": "source_config_missing_required_fields",
                "missing_fields": ",".join(missing_fields),
                "role": role,
            }
            if role == "candidate":
                blocked_sources.append(issue)
            else:
                blocked_matched_baselines.append(issue)
            continue

        source_config_hash = sha256_file(source_config_path)
        for cost_scenario in cost_scenarios:
            variant_id = slugify(f"{role}__{source_slug}__{cost_scenario}")
            config_path = config_dir / f"{variant_id}.json"
            run_dir = run_root / variant_id
            locked_config = build_locked_config(
                source_config=source_config,
                source_config_sha256=source_config_hash,
                source_run_slug=source_slug,
                plan_id=plan_id,
                role=role,
                cost_scenario=cost_scenario,
                heldout_start=heldout_start,
                stage_b_timesteps=stage_b_timesteps,
                run_dir=run_dir,
                candidate_slug=candidate_slug_for_baseline or source_slug,
                baseline_name=baseline_name or None,
            )
            config_path.write_text(json.dumps(locked_config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            config_entries.append({
                "variant_id": variant_id,
                "role": role,
                "baseline_name": baseline_name or "",
                "candidate_run_slug": candidate_slug_for_baseline or source_slug,
                "source_run_slug": source_slug,
                "source_stage_a_status": row.get("stage_b_status", ""),
                "asset": row.get("asset", ""),
                "timeframe": row.get("timeframe", ""),
                "algo": row.get("algo", ""),
                "preset": row.get("preset", ""),
                "seed": row.get("seed", ""),
                "cost_scenario": cost_scenario,
                "stage_b_timesteps": stage_b_timesteps,
                "machine_hint": index_row.get("machine", ""),
                "config_file": str(config_path),
                "source_config_file": str(source_config_path),
                "source_config_sha256": source_config_hash,
                "input_data_file": str(source_config.get("input_data_file", "")),
                "input_firewall_status": leakage_row.get("status", ""),
                "input_max_ts": leakage_row.get("max_ts", ""),
                "run_dir": str(run_dir),
                "return_trace_dir": str(run_dir / "traces"),
                "return_trace_file": str(run_dir / "traces" / "evaluation_return_trace.csv"),
                "expected_evidence_file": str(run_dir / "traces" / "evidence.json"),
                "progress_file": str(run_dir / "training_progress.json"),
                "locked": True,
                "training_launched": False,
                "stage_c_access": "DENIED",
                "execution_status": "LOCKED_TEMPLATE_NOT_RUNNABLE_UNTIL_STAGE_B_APPROVED",
            })

    if blocked_sources:
        raise RuntimeError(f"Blocked source rows prevent a complete Stage B run plan: {blocked_sources[:5]}")

    manifest = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "plan_id": plan_id,
        "approval_csv": str(approval_csv),
        "index_csv": str(index_csv),
        "leakage_csv": str(leakage_csv),
        "heldout_start": heldout_start,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "stage_b_timesteps": stage_b_timesteps,
        "selection_rule": "all candidates with stage_b_status == BLOCKED_DSR_DEFERRED",
        "selected_candidate_count": len(selected),
        "unique_config_count": len(config_entries),
        "cost_scenarios": cost_scenarios,
        "return_trace_schema_version": TRACE_SCHEMA_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "minimum_required_live_progress_fields": [
            "progress_pct",
            "current_step",
            "total_timesteps",
            "trades_total",
            "total_return",
        ],
        "no_trade_anomaly_rule": "flag and stop/remediate if progress_pct >= 20 and trades_total <= 0",
        "missing_matched_baselines": missing_baselines,
        "blocked_matched_baselines": blocked_matched_baselines,
        "promotion_rules": {
            "minimum_paired_seeds": 5,
            "candidate_must_beat_matched_baseline_under_base_cost": True,
            "pessimistic_cost_must_not_be_catastrophic": True,
            "rigorous_dsr_required": True,
            "pbo_cscv_required": True,
            "stage_c_forbidden": True,
        },
        "configs": config_entries,
        "comparisons": comparison_entries,
    }
    (output_dir / "stage_b_locked_run_plan.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_csv(
        output_dir / "stage_b_locked_run_plan.csv",
        config_entries,
        [
            "variant_id", "role", "baseline_name", "candidate_run_slug", "source_run_slug",
            "source_stage_a_status", "asset", "timeframe", "algo", "preset", "seed",
            "cost_scenario", "stage_b_timesteps", "machine_hint", "config_file",
            "source_config_file", "source_config_sha256", "input_data_file",
            "input_firewall_status", "input_max_ts", "run_dir", "return_trace_dir",
            "return_trace_file", "expected_evidence_file", "progress_file", "locked",
            "training_launched", "stage_c_access", "execution_status",
        ],
    )
    write_markdown(output_dir / "stage_b_locked_run_plan.md", manifest)
    return manifest


def write_markdown(path: pathlib.Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Project 3 Stage B Locked Run Plan",
        "",
        f"Generated UTC: `{manifest['generated_at_utc']}`",
        f"Plan ID: `{manifest['plan_id']}`",
        f"Selected candidates: `{manifest['selected_candidate_count']}`",
        f"Locked config templates: `{manifest['unique_config_count']}`",
        f"Stage B timesteps per config: `{manifest['stage_b_timesteps']}`",
        f"Stage C access: `{manifest['stage_c_access']}`",
        f"Training launched: `{manifest['training_launched']}`",
        "",
        "## Required Live Progress Fields",
        "",
        ", ".join(f"`{field}`" for field in manifest["minimum_required_live_progress_fields"]),
        "",
        f"No-trade anomaly rule: `{manifest['no_trade_anomaly_rule']}`",
        "",
        "## Top Candidate Comparisons",
        "",
        "| Candidate | Preset | Seed | Return | Trades | Matched baseline | Baseline return |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for item in manifest["comparisons"][:25]:
        lines.append(
            "| {candidate_run_slug} | {candidate_preset} | {candidate_seed} | "
            "{candidate_stage_a_return} | {candidate_stage_a_trades} | "
            "{matched_baseline_run_slug} | {matched_baseline_return} |".format(**item)
        )
    if manifest["missing_matched_baselines"]:
        lines += [
            "",
            "## Missing Matched Baselines",
            "",
        ]
        lines.extend(f"- `{slug}`" for slug in manifest["missing_matched_baselines"])
    if manifest["blocked_matched_baselines"]:
        lines += [
            "",
            "## Blocked Matched Baselines",
            "",
        ]
        for item in manifest["blocked_matched_baselines"]:
            lines.append(
                f"- `{item.get('run_slug', '')}`: {item.get('reason', '')} "
                f"({item.get('leakage_status', '')})"
            )
    lines += [
        "",
        "## Safety",
        "",
        "- All generated configs contain `_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED: true`.",
        "- All generated configs set `stage_c_access: DENIED`.",
        "- This worker does not launch training.",
        "- DSR/PBO remain blocked until Stage B traces and fold evidence exist.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-csv", type=pathlib.Path, default=APPROVAL_CSV)
    parser.add_argument("--index-csv", type=pathlib.Path, default=INDEX_CSV)
    parser.add_argument("--leakage-csv", type=pathlib.Path, default=LEAKAGE_CSV)
    parser.add_argument("--output-dir", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--heldout-start", default=HELDOUT_START)
    parser.add_argument("--cost-scenarios", default="base,pessimistic")
    parser.add_argument("--stage-b-timesteps", type=int, default=1_000_000)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cost_scenarios = [item.strip() for item in args.cost_scenarios.split(",") if item.strip()]
    manifest = build_plan(
        approval_csv=args.approval_csv,
        index_csv=args.index_csv,
        leakage_csv=args.leakage_csv,
        output_dir=args.output_dir,
        heldout_start=args.heldout_start,
        cost_scenarios=cost_scenarios,
        stage_b_timesteps=args.stage_b_timesteps,
        limit=args.limit or None,
    )
    summary = {
        "ok": True,
        "output_dir": str(args.output_dir),
        "selected_candidate_count": manifest["selected_candidate_count"],
        "locked_config_templates": manifest["unique_config_count"],
        "training_launched": manifest["training_launched"],
        "stage_c_access": manifest["stage_c_access"],
        "missing_matched_baselines": len(manifest["missing_matched_baselines"]),
        "blocked_matched_baselines": len(manifest["blocked_matched_baselines"]),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
