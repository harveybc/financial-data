#!/usr/bin/env python3
"""Finalize Project 3 Stage B pragmatic validation after the run queue ends.

This worker is intentionally conservative:

- it does not launch training;
- it does not inspect or unlock Stage C;
- it refuses to run promotion analysis until the locked Stage B queue is
  complete, unless ``--force-analysis`` is explicitly passed for diagnostics;
- it records every command it runs and writes a finalization packet.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN_PLAN_DIR = ROOT / "experiments" / "stage_b_validation" / "run_plan"
HARDENING_DIR = ROOT / "experiments" / "stage_b_validation" / "hardening"
OUT_JSON = HARDENING_DIR / "stage_b_post_pragmatic_finalization.json"
OUT_MD = HARDENING_DIR / "stage_b_post_pragmatic_finalization.md"

RUN_PLAN_STATUS = RUN_PLAN_DIR / "stage_b_run_plan_status.json"
CLUSTER_STATUS = RUN_PLAN_DIR / "stage_b_cluster_live_status.json"
STAT_REPORT = HARDENING_DIR / "stageb_dsr_pbo_report.json"
APPROVAL_PACKET = ROOT / "experiments" / "stage_a_screening" / "stage_b_approval" / "stage_b_approval_packet.json"
DECISION_READINESS = HARDENING_DIR / "stage_b_decision_readiness.json"
ROOT_CAUSE_REPORT = HARDENING_DIR / "stageb_no_pass_root_cause.md"

PYTHON = Path(sys.executable)
WORKERS = ROOT / "_scripts" / "workers"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def refresh_worker(worker_name: str, dry_run: bool) -> dict[str, Any]:
    cmd = [str(PYTHON), str(WORKERS / worker_name)]
    record: dict[str, Any] = {
        "worker": worker_name,
        "cmd": cmd,
        "dry_run": dry_run,
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if dry_run:
        record["returncode"] = 0
        return record
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    record["returncode"] = proc.returncode
    record["stdout_tail"] = proc.stdout[-4000:]
    record["stderr_tail"] = proc.stderr[-4000:]
    return record


def current_counts() -> dict[str, Any]:
    cluster = load_json(CLUSTER_STATUS, {})
    run_plan = load_json(RUN_PLAN_STATUS, {})
    counts = cluster.get("counts") or run_plan.get("summary", {}).get("counts") or {}
    assigned = safe_int(cluster.get("assigned") or run_plan.get("summary", {}).get("total_rows"))
    return {
        "assigned": assigned,
        "done": safe_int(counts.get("done")),
        "running": safe_int(counts.get("running")),
        "not_started": safe_int(counts.get("not_started")),
        "failed": safe_int(counts.get("failed")),
        "aborted_no_trade": safe_int(counts.get("aborted_no_trade")),
        "cluster_generated_at_utc": cluster.get("generated_at_utc"),
        "next_expected_poll_utc": cluster.get("next_expected_poll_utc"),
        "all_machine_queries_ok": cluster.get("all_queries_ok"),
    }


def queue_complete(counts: dict[str, Any]) -> bool:
    assigned = safe_int(counts.get("assigned"))
    done = safe_int(counts.get("done"))
    return (
        assigned > 0
        and done >= assigned
        and safe_int(counts.get("running")) == 0
        and safe_int(counts.get("not_started")) == 0
        and safe_int(counts.get("failed")) == 0
        and safe_int(counts.get("aborted_no_trade")) == 0
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    pre_counts = current_counts()
    complete = queue_complete(pre_counts)
    commands: list[dict[str, Any]] = []
    analysis_allowed = complete or args.force_analysis
    blocked_reason = "" if complete else "STAGE_B_PRAGMATIC_QUEUE_NOT_COMPLETE"

    if analysis_allowed:
        for worker in (
            "stage_b_run_plan_status_worker.py",
            "stageb_dsr_pbo_evaluator.py",
            "stage_b_approval_gate_worker.py",
            "stage_b_decision_readiness_worker.py",
            "stage_b_pragmatic_root_cause_worker.py",
        ):
            result = refresh_worker(worker, args.dry_run)
            commands.append(result)
            if result["returncode"] != 0:
                blocked_reason = f"POST_RUN_WORKER_FAILED:{worker}"
                break

    post_counts = current_counts()
    stat = load_json(STAT_REPORT, {})
    approval = load_json(APPROVAL_PACKET, {})
    readiness = load_json(DECISION_READINESS, {})

    return {
        "schema_version": "project3_stage_b_post_pragmatic_finalization_v1",
        "generated_at_utc": utc_now(),
        "dry_run": args.dry_run,
        "force_analysis": args.force_analysis,
        "stage_c_touched": False,
        "training_launched": False,
        "queue_complete": complete,
        "analysis_allowed": analysis_allowed,
        "blocked_reason": blocked_reason,
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "commands": commands,
        "stageb_stat_summary": stat.get("summary", {}),
        "approval_summary": approval.get("summary", {}),
        "decision_readiness": {
            "stage_c_decision": readiness.get("stage_c_decision"),
            "stage_c_locked": readiness.get("stage_c_locked"),
            "hard_stop_reasons": readiness.get("hard_stop_reasons", []),
        },
        "artifacts": {
            "cluster_status": str(CLUSTER_STATUS),
            "run_plan_status": str(RUN_PLAN_STATUS),
            "stageb_stat_report": str(STAT_REPORT),
            "approval_packet": str(APPROVAL_PACKET),
            "decision_readiness": str(DECISION_READINESS),
            "root_cause_report": str(ROOT_CAUSE_REPORT),
        },
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Stage B Pragmatic Post-Run Finalization",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        f"Queue complete: `{payload['queue_complete']}`",
        f"Analysis allowed: `{payload['analysis_allowed']}`",
        f"Blocked reason: `{payload['blocked_reason']}`",
        f"Training launched by this worker: `{payload['training_launched']}`",
        f"Stage C touched by this worker: `{payload['stage_c_touched']}`",
        "",
        "## Queue Counts",
        "",
        f"- Before: `{payload['pre_counts']}`",
        f"- After: `{payload['post_counts']}`",
        "",
        "## Commands",
        "",
    ]
    if payload["commands"]:
        lines += [
            "| Worker | Return Code |",
            "| --- | ---: |",
        ]
        for row in payload["commands"]:
            lines.append(f"| `{row['worker']}` | `{row['returncode']}` |")
    else:
        lines.append("- No analysis commands were run because the queue is not complete.")

    lines += [
        "",
        "## Stage B Decision",
        "",
        f"- Stage C decision: `{payload['decision_readiness'].get('stage_c_decision')}`",
        f"- Stage C locked: `{payload['decision_readiness'].get('stage_c_locked')}`",
        f"- Approval summary: `{payload['approval_summary']}`",
        f"- Statistical summary: `{payload['stageb_stat_summary']}`",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-analysis", action="store_true", help="Run analysis even when the queue is incomplete.")
    parser.add_argument("--dry-run", action="store_true", help="Record intended commands without running them.")
    args = parser.parse_args()

    HARDENING_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    write_markdown(payload)
    print(json.dumps({
        "ok": not payload["blocked_reason"] or payload["blocked_reason"] == "STAGE_B_PRAGMATIC_QUEUE_NOT_COMPLETE",
        "queue_complete": payload["queue_complete"],
        "analysis_allowed": payload["analysis_allowed"],
        "blocked_reason": payload["blocked_reason"],
        "pre_counts": payload["pre_counts"],
        "post_counts": payload["post_counts"],
        "json": str(OUT_JSON),
        "markdown": str(OUT_MD),
    }, indent=2, sort_keys=True))
    return 0 if not str(payload["blocked_reason"]).startswith("POST_RUN_WORKER_FAILED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
