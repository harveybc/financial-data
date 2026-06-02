#!/usr/bin/env python3
"""
Execute Project 3 Stage B locked run-plan configs with live anomaly monitoring.

Default mode is a dry run. Real execution requires both ``--execute`` and the
exact approval token ``RUN_STAGE_B_VALIDATION``. The executor runs the emitted
agent-multi config directly so the locked manifest paths for progress, traces,
and evidence remain valid. It does not use seed_sweep.py because seed_sweep
rewrites output directories.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT_MULTI_ROOT = Path(os.environ.get("AGENT_MULTI_ROOT", "/home/harveybc/Documents/GitHub/agent-multi"))
PLAN_JSON = ROOT / "experiments/stage_b_validation/run_plan/stage_b_locked_run_plan.json"
OUT_JSON = ROOT / "experiments/stage_b_validation/run_plan/stage_b_executor_state.json"
OUT_MD = ROOT / "experiments/stage_b_validation/run_plan/stage_b_executor_state.md"
APPROVAL_TOKEN = "RUN_STAGE_B_VALIDATION"
NO_TRADE_ABORT_PROGRESS_PERCENT = float(os.environ.get("PROJECT3_NO_TRADE_ABORT_PROGRESS_PERCENT", "20"))
POLL_SECONDS = float(os.environ.get("PROJECT3_STAGE_B_EXECUTOR_POLL_SECONDS", "15"))
IDLE_POLL_SECONDS = float(os.environ.get("PROJECT3_STAGE_B_IDLE_POLL_SECONDS", "30"))
TERMINAL_PROGRESS_STATUSES = {
    "complete",
    "training_complete",
    "subprocess_complete",
    "failed",
    "aborted",
    "blocked_no_trade_early_abort",
}


class StageBExecutionError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def progress_percent(progress: dict[str, Any]) -> float:
    raw = progress.get(
        "progress_pct",
        progress.get("progress_percent", progress.get("percent_complete", progress.get("progress", 0.0))),
    )
    pct = safe_float(raw)
    if pct <= 1.0 and progress.get("progress") not in (None, ""):
        pct *= 100.0
    if pct <= 0.0 and progress.get("num_timesteps") not in (None, ""):
        total = safe_float(progress.get("total_timesteps"))
        if total > 0:
            pct = safe_float(progress.get("num_timesteps")) / total * 100.0
    return max(0.0, min(100.0, pct))


def is_expected_no_trade_baseline(entry: dict[str, Any]) -> bool:
    return (
        str(entry.get("role", "")).lower() == "baseline"
        and str(entry.get("baseline_name", "")).lower() == "no_trade"
    )


def no_trade_abort_reason(entry: dict[str, Any], progress_file: Path) -> str:
    if is_expected_no_trade_baseline(entry):
        return ""
    progress = load_json(progress_file, {})
    if not isinstance(progress, dict) or not progress:
        return ""
    pct = progress_percent(progress)
    if pct < NO_TRADE_ABORT_PROGRESS_PERCENT:
        return ""
    trade_value = progress.get("trades_total_cumulative", progress.get("trades_total"))
    if trade_value in (None, ""):
        return f"progress {pct:.2f}% reached but trades_total is missing"
    trades = safe_float(trade_value)
    if trades > 0:
        return ""
    diagnosis = progress.get("no_trade_diagnosis") or "no_trade_detected"
    return f"progress {pct:.2f}% reached with trades_total=0 (diagnosis={diagnosis})"


def active_agent_multi_processes() -> list[str]:
    """Return running agent-multi training/eval process lines.

    The executor may be restarted while an earlier child process is still
    finishing. In that case the safe behavior is to wait; launching another
    config on the same GPU would corrupt throughput and make status misleading.
    """
    try:
        raw = subprocess.check_output(
            "ps -eo pid,etimes,pcpu,args | "
            "grep -E '/bin/agent-multi --load_config' | grep -v grep || true",
            shell=True,
            text=True,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        return []
    return [line for line in raw.splitlines() if line.strip()]


def wait_for_machine_idle() -> None:
    while True:
        active = active_agent_multi_processes()
        if not active:
            return
        time.sleep(IDLE_POLL_SECONDS)


def existing_run_skip_reason(entry: dict[str, Any], *, force_rerun: bool = False) -> str:
    if force_rerun:
        return ""
    run_dir = Path(str(entry.get("run_dir", "")))
    progress_file = Path(str(entry.get("progress_file", "")))
    summary_file = run_dir / "summary.json"
    evidence_file = Path(str(entry.get("expected_evidence_file", "")))
    if summary_file.exists():
        return "summary_exists"
    if evidence_file.exists():
        return "evidence_exists"
    progress = load_json(progress_file, {})
    if isinstance(progress, dict) and progress:
        status = str(progress.get("status", ""))
        if status in TERMINAL_PROGRESS_STATUSES:
            return f"terminal_progress_status:{status}"
        stdout_log = run_dir / "agent_multi_stdout.log"
        if stdout_log.exists():
            try:
                text = stdout_log.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            if "Traceback (most recent call last)" in text:
                if "Expected parameter scale" in text and "[nan]" in text:
                    return "stale_failed_stdout:SAC_NAN_SCALE"
                if "FileNotFoundError" in text or "No such file or directory" in text:
                    return "stale_failed_stdout:MISSING_INPUT"
                if "return_trace split='stage_b_validation'" in text:
                    return "stale_failed_stdout:OLD_TRACE_SPLIT_REJECT"
                return "stale_failed_stdout:TRACEBACK"
    return ""


def terminate_process_group(proc: subprocess.Popen[str], *, kill: bool = False) -> None:
    sig = signal.SIGKILL if kill else signal.SIGTERM
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        return
    except Exception:
        if kill:
            proc.kill()
        else:
            proc.terminate()


def agent_multi_binary() -> str:
    configured = os.environ.get("AGENT_MULTI_BIN")
    if configured:
        return configured
    sibling = Path(sys.executable).with_name("agent-multi")
    if sibling.exists():
        return str(sibling)
    return "agent-multi"


def validate_entry(entry: dict[str, Any], config: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if config.get("_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED") is not True:
        issues.append("LOCK_FLAG_MISSING")
    if config.get("stage_c_access") != "DENIED":
        issues.append("STAGE_C_ACCESS_NOT_DENIED")
    if config.get("final_stage_c_evaluation") or config.get("stage_c_acknowledged"):
        issues.append("STAGE_C_AUTH_FLAG_SET")
    expected_progress = str(entry.get("progress_file", ""))
    if not expected_progress:
        issues.append("MANIFEST_PROGRESS_FILE_MISSING")
    if config.get("progress_file") != expected_progress:
        issues.append("CONFIG_PROGRESS_FILE_MISMATCH")
    if config.get("training_progress_file") != expected_progress:
        issues.append("CONFIG_TRAINING_PROGRESS_FILE_MISMATCH")
    if not config.get("return_trace_dir"):
        issues.append("RETURN_TRACE_DIR_MISSING")
    if str(config.get("return_trace_dir", "")) != str(entry.get("return_trace_dir", "")):
        issues.append("RETURN_TRACE_DIR_MISMATCH")
    if config.get("pipeline_plugin") == "rl_pipeline":
        expected_trace_file = str(entry.get("return_trace_file", ""))
        if not config.get("return_trace_file"):
            issues.append("RETURN_TRACE_FILE_MISSING_FOR_RL_PIPELINE")
        elif expected_trace_file and str(config.get("return_trace_file")) != expected_trace_file:
            issues.append("RETURN_TRACE_FILE_MISMATCH")
    is_zero_step_baseline = (
        str(entry.get("role", "")).lower() == "baseline"
        and safe_int(config.get("total_timesteps")) == 0
    )
    if safe_int(config.get("total_timesteps")) <= 0 and not is_zero_step_baseline:
        issues.append("TOTAL_TIMESTEPS_INVALID")
    return issues


def selected_entries(
    plan: dict[str, Any],
    *,
    variant_id: str = "",
    machine: str = "",
    limit: int = 0,
) -> list[dict[str, Any]]:
    entries = list(plan.get("configs", []))
    if variant_id:
        entries = [e for e in entries if e.get("variant_id") == variant_id]
    if machine:
        entries = [e for e in entries if str(e.get("machine_hint", "")).lower() == machine.lower()]
    if limit:
        entries = entries[:limit]
    return entries


def build_dry_run_state(entries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for entry in entries:
        config_path = Path(str(entry.get("config_file", "")))
        config = load_json(config_path, {}) if config_path.exists() else {}
        issues = validate_entry(entry, config) if isinstance(config, dict) else ["CONFIG_INVALID_JSON"]
        rows.append({
            "variant_id": entry.get("variant_id", ""),
            "machine_hint": entry.get("machine_hint", ""),
            "role": entry.get("role", ""),
            "asset": entry.get("asset", ""),
            "timeframe": entry.get("timeframe", ""),
            "algo": entry.get("algo", ""),
            "preset": entry.get("preset", ""),
            "seed": entry.get("seed", ""),
            "cost_scenario": entry.get("cost_scenario", ""),
            "config_file": str(config_path),
            "progress_file": entry.get("progress_file", ""),
            "return_trace_dir": entry.get("return_trace_dir", ""),
            "return_trace_file": entry.get("return_trace_file", ""),
            "expected_evidence_file": entry.get("expected_evidence_file", ""),
            "total_timesteps": config.get("total_timesteps") if isinstance(config, dict) else "",
            "validation_issues": issues,
            "ready_to_execute": not issues,
        })
    return {
        "schema_version": "project3_stage_b_executor_state_v1",
        "generated_at_utc": utc_now(),
        "mode": "dry_run",
        "training_launched": False,
        "selected_count": len(rows),
        "ready_count": sum(1 for r in rows if r["ready_to_execute"]),
        "blocked_count": sum(1 for r in rows if not r["ready_to_execute"]),
        "rows": rows,
    }


def write_markdown(payload: dict[str, Any]) -> None:
    lines = [
        "# Project 3 Stage B Executor State",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        f"Mode: `{payload['mode']}`",
        f"Training launched: `{payload['training_launched']}`",
        f"Selected configs: `{payload.get('selected_count', 0)}`",
        f"Ready configs: `{payload.get('ready_count', 0)}`",
        f"Blocked configs: `{payload.get('blocked_count', 0)}`",
        "",
        "| Variant | Machine | Role | Seed | Cost | Ready | Issues |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload.get("rows", [])[:200]:
        issues = ";".join(row.get("validation_issues", []))
        lines.append(
            f"| {row.get('variant_id','')} | {row.get('machine_hint','')} | "
            f"{row.get('role','')} | {row.get('seed','')} | {row.get('cost_scenario','')} | "
            f"{row.get('ready_to_execute')} | {issues} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_entry(entry: dict[str, Any], *, timeout_minutes: float, force_rerun: bool = False) -> dict[str, Any]:
    config_path = Path(str(entry.get("config_file", "")))
    config = load_json(config_path, {})
    if not isinstance(config, dict):
        raise StageBExecutionError(f"invalid config JSON: {config_path}")
    issues = validate_entry(entry, config)
    if issues:
        raise StageBExecutionError(f"config contract invalid for {entry.get('variant_id')}: {issues}")

    skip_reason = existing_run_skip_reason(entry, force_rerun=force_rerun)
    if skip_reason:
        if skip_reason.startswith("stale_failed_stdout:"):
            progress_file = Path(str(entry.get("progress_file", "")))
            progress = load_json(progress_file, {})
            if not isinstance(progress, dict):
                progress = {}
            progress.update({
                "source": "stage_b_executor",
                "status": "failed",
                "updated_at_utc": utc_now(),
                "failure_reason": skip_reason,
                "stdout_log": str(Path(str(entry.get("run_dir", ""))) / "agent_multi_stdout.log"),
            })
            write_json(progress_file, progress)
        return {
            "variant_id": entry.get("variant_id", ""),
            "status": "skipped_existing",
            "exit_code": 0,
            "failure_reason": "",
            "skip_reason": skip_reason,
            "progress_file": str(entry.get("progress_file", "")),
            "stdout_log": str(Path(str(entry.get("run_dir", ""))) / "agent_multi_stdout.log"),
        }

    run_dir = Path(str(entry.get("run_dir", "")))
    progress_file = Path(str(entry.get("progress_file", "")))
    stdout_log = run_dir / "agent_multi_stdout.log"
    run_dir.mkdir(parents=True, exist_ok=True)
    progress_file.parent.mkdir(parents=True, exist_ok=True)

    write_json(progress_file, {
        "schema_version": "project3_training_progress_v1",
        "source": "stage_b_executor",
        "status": "subprocess_starting",
        "run_id": entry.get("variant_id", ""),
        "updated_at_utc": utc_now(),
        "current_step": 0,
        "num_timesteps": 0,
        "total_timesteps": safe_int(config.get("total_timesteps")),
        "progress_pct": 0.0,
        "progress_percent": 0.0,
        "trades_total": 0,
        "total_return": 0.0,
        "profit_percent": 0.0,
        "no_trade_anomaly": False,
    })

    cmd = [agent_multi_binary(), "--load_config", str(config_path), "--quiet_mode"]
    started = utc_now()
    deadline = time.time() + timeout_minutes * 60
    aborted_reason = ""
    with stdout_log.open("w", encoding="utf-8") as stdout_handle:
        proc = subprocess.Popen(
            cmd,
            cwd=AGENT_MULTI_ROOT,
            text=True,
            stdout=stdout_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        while proc.poll() is None:
            if time.time() >= deadline:
                aborted_reason = f"timeout_after_{timeout_minutes}_minutes"
                terminate_process_group(proc)
                break
            reason = no_trade_abort_reason(entry, progress_file)
            if reason:
                aborted_reason = reason
                terminate_process_group(proc)
                break
            try:
                proc.wait(timeout=POLL_SECONDS)
            except subprocess.TimeoutExpired:
                continue
        if proc.poll() is None:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                terminate_process_group(proc, kill=True)
                proc.wait(timeout=30)

    progress = load_json(progress_file, {})
    status = "complete" if proc.returncode == 0 and not aborted_reason else "failed"
    if aborted_reason:
        status = "blocked_no_trade_early_abort" if "trades_total=0" in aborted_reason else "aborted"
    progress.update({
        "source": "stage_b_executor",
        "status": status,
        "updated_at_utc": utc_now(),
        "executor_started_at_utc": started,
        "executor_finished_at_utc": utc_now(),
        "exit_code": proc.returncode,
        "failure_reason": aborted_reason,
        "stdout_log": str(stdout_log),
    })
    write_json(progress_file, progress)
    return {
        "variant_id": entry.get("variant_id", ""),
        "status": status,
        "exit_code": proc.returncode,
        "failure_reason": aborted_reason,
        "progress_file": str(progress_file),
        "stdout_log": str(stdout_log),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-json", type=Path, default=PLAN_JSON)
    parser.add_argument("--variant-id", default="")
    parser.add_argument("--machine", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--timeout-minutes", type=float, default=720.0)
    parser.add_argument("--force-rerun", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = load_json(args.plan_json, {})
    if not isinstance(plan, dict) or not plan.get("configs"):
        raise StageBExecutionError(f"missing or invalid plan: {args.plan_json}")
    entries = selected_entries(
        plan,
        variant_id=args.variant_id,
        machine=args.machine,
        limit=args.limit,
    )
    state = build_dry_run_state(entries)
    if not args.execute:
        write_json(OUT_JSON, state)
        write_markdown(state)
        print(json.dumps({
            "ok": True,
            "mode": "dry_run",
            "selected_count": state["selected_count"],
            "ready_count": state["ready_count"],
            "blocked_count": state["blocked_count"],
            "state_file": str(OUT_JSON),
        }, indent=2, sort_keys=True))
        return 0 if state["blocked_count"] == 0 else 2

    if args.approval_token != APPROVAL_TOKEN:
        raise StageBExecutionError(
            f"execution requires --approval-token {APPROVAL_TOKEN!r}; dry-run state written to {OUT_JSON}"
        )
    if state["blocked_count"]:
        write_json(OUT_JSON, state)
        write_markdown(state)
        raise StageBExecutionError("refusing execution because selected configs have validation issues")
    results = []
    for entry in entries:
        wait_for_machine_idle()
        results.append(
            run_entry(
                entry,
                timeout_minutes=args.timeout_minutes,
                force_rerun=args.force_rerun,
            )
        )
    payload = {
        **state,
        "mode": "execute",
        "training_launched": bool(results),
        "results": results,
    }
    write_json(OUT_JSON, payload)
    write_markdown(payload)
    ok = all(r["status"] in {"complete", "skipped_existing"} for r in results)
    print(json.dumps({"ok": ok, "results": results, "state_file": str(OUT_JSON)}, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
