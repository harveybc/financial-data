from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
REPORT_DIR = ROOT / "_logs" / "supervisor_reports"
REPORT_JSON = REPORT_DIR / "stage16_preflight_dispatch.json"
REPORT_MD = REPORT_DIR / "stage16_preflight_dispatch.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str], timeout: int = 60, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd or ROOT, text=True, capture_output=True, timeout=timeout)


def remote(host: str, command: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    wrapped = (
        "source ~/.bashrc >/dev/null 2>&1; "
        "source /home/harveybc/anaconda3/etc/profile.d/conda.sh >/dev/null 2>&1; "
        "conda activate tensorflow >/dev/null 2>&1; "
        f"cd {shlex.quote(str(ROOT))}; {command}"
    )
    return run(["ssh", host, "bash", "-lc", wrapped], timeout=timeout)


def local_pid_running(pid_file: Path) -> tuple[bool, str]:
    pid = pid_file.read_text(encoding="utf-8").strip() if pid_file.exists() else ""
    if not pid:
        return False, ""
    result = run(["ps", "-p", pid, "-o", "pid="], timeout=10)
    return result.returncode == 0 and bool(result.stdout.strip()), pid


def remote_pid_running(host: str, pid_file: str) -> tuple[bool, str]:
    result = remote(
        host,
        f"pid=$(cat {shlex.quote(pid_file)} 2>/dev/null || true); "
        "if [ -n \"$pid\" ] && ps -p \"$pid\" >/dev/null 2>&1; then echo running:$pid; else echo idle:${pid:-}; fi",
        timeout=20,
    )
    output = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if output.startswith("running:"):
        return True, output.split(":", 1)[1]
    if output.startswith("idle:"):
        return False, output.split(":", 1)[1]
    return False, ""


def local_done(log_file: Path, marker: str) -> bool:
    return log_file.exists() and marker in log_file.read_text(encoding="utf-8", errors="ignore")[-4000:]


def remote_done(host: str, log_file: str, marker: str) -> bool:
    result = remote(
        host,
        f"tail -c 4000 {shlex.quote(log_file)} 2>/dev/null | grep -F {shlex.quote(marker)} >/dev/null && echo done || echo pending",
        timeout=20,
    )
    return "done" in result.stdout


def ensure_remote_worker(host: str, script_name: str) -> dict[str, str]:
    script = ROOT / "_scripts" / "workers" / script_name
    result = run(["scp", str(script), f"{host}:{ROOT}/_scripts/workers/"], timeout=60)
    return {"state": "ok" if result.returncode == 0 else "failed", "stderr": result.stderr[-500:]}


def start_local_omega() -> dict[str, str]:
    pid_file = ROOT / "_logs" / "omega" / "stage16_preflight_omega_python.pid"
    out_file = ROOT / "_logs" / "omega" / "stage16_preflight_omega_python.out"
    log_file = ROOT / "_logs" / "omega" / "stage16_preflight_omega_worker.log"
    running, pid = local_pid_running(pid_file)
    if running:
        return {"state": "busy", "pid": pid, "action": "kept_running"}
    out_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = (
        f"PYTHONDONTWRITEBYTECODE=1 nohup python _scripts/workers/stage16_preflight_omega_worker.py "
        f"> {shlex.quote(str(out_file))} 2>&1 & echo $! > {shlex.quote(str(pid_file))}"
    )
    result = run(["bash", "-lc", cmd], timeout=20)
    pid = pid_file.read_text(encoding="utf-8").strip() if pid_file.exists() else ""
    state = "started" if result.returncode == 0 else "start_failed"
    if result.returncode == 0 and local_done(log_file, "DONE stage16 omega preflight worker"):
        state = "completed_idle"
    return {"state": state, "pid": pid, "action": "stage16_preflight_omega_worker", "stderr": result.stderr[-500:]}


def start_remote_validation(host: str, machine: str, roots: str) -> dict[str, str]:
    pid_file = f"{ROOT}/_logs/{machine}/stage16_preflight_validation_python.pid"
    out_file = f"{ROOT}/_logs/{machine}/stage16_preflight_validation_python.out"
    log_file = f"{ROOT}/_logs/{machine}/stage16_preflight_validation_worker.log"
    running, pid = remote_pid_running(host, pid_file)
    if running:
        return {"state": "busy", "pid": pid, "action": "kept_running"}
    if remote_done(host, log_file, "DONE stage16 preflight validation"):
        return {"state": "completed_idle", "pid": pid, "action": "no_dispatch_needed"}
    copied = ensure_remote_worker(host, "stage16_preflight_validation_worker.py")
    if copied["state"] != "ok":
        return {"state": "sync_failed", "pid": pid, "action": "copy_stage16_worker", "stderr": copied["stderr"]}
    cmd = (
        f"mkdir -p {shlex.quote(str(Path(pid_file).parent))} {shlex.quote(str(Path(out_file).parent))}; "
        f"PYTHONDONTWRITEBYTECODE=1 nohup python _scripts/workers/stage16_preflight_validation_worker.py "
        f"--machine {shlex.quote(machine)} --roots {shlex.quote(roots)} "
        f"> {shlex.quote(out_file)} 2>&1 & echo $! > {shlex.quote(pid_file)}"
    )
    result = remote(host, cmd, timeout=20)
    running, pid = remote_pid_running(host, pid_file)
    return {
        "state": "started" if result.returncode == 0 and pid else "start_failed",
        "pid": pid,
        "action": "stage16_preflight_validation_worker",
        "stderr": result.stderr[-500:],
    }


def start_remote_quality(host: str, machine: str, roots: str) -> dict[str, str]:
    pid_file = f"{ROOT}/_logs/{machine}/stage16_quality_python.pid"
    out_file = f"{ROOT}/_logs/{machine}/stage16_quality_python.out"
    log_file = f"{ROOT}/_logs/{machine}/stage16_quality_worker.log"
    running, pid = remote_pid_running(host, pid_file)
    if running:
        return {"state": "busy", "pid": pid, "action": "kept_running"}
    if remote_done(host, log_file, "DONE stage16 quality validation"):
        return {"state": "completed_idle", "pid": pid, "action": "no_dispatch_needed"}
    if not remote_done(host, f"{ROOT}/_logs/{machine}/stage16_preflight_validation_worker.log", "DONE stage16 preflight validation"):
        return {"state": "waiting_preflight", "pid": pid, "action": "stage16_quality_validation"}
    copied = ensure_remote_worker(host, "stage16_quality_worker.py")
    if copied["state"] != "ok":
        return {"state": "sync_failed", "pid": pid, "action": "copy_stage16_quality_worker", "stderr": copied["stderr"]}
    cmd = (
        f"mkdir -p {shlex.quote(str(Path(pid_file).parent))} {shlex.quote(str(Path(out_file).parent))}; "
        f"PYTHONDONTWRITEBYTECODE=1 nohup python _scripts/workers/stage16_quality_worker.py "
        f"--machine {shlex.quote(machine)} --roots {shlex.quote(roots)} "
        f"> {shlex.quote(out_file)} 2>&1 & echo $! > {shlex.quote(pid_file)}"
    )
    result = remote(host, cmd, timeout=20)
    running, pid = remote_pid_running(host, pid_file)
    return {
        "state": "started" if result.returncode == 0 and pid else "start_failed",
        "pid": pid,
        "action": "stage16_quality_worker",
        "stderr": result.stderr[-500:],
    }


def sync_remote_preflight(host: str, machine: str) -> dict[str, str]:
    running, _ = remote_pid_running(host, f"{ROOT}/_logs/{machine}/stage16_preflight_validation_python.pid")
    if running:
        return {"state": "deferred_busy", "action": f"{machine}_stage16_sync"}
    if not remote_done(host, f"{ROOT}/_logs/{machine}/stage16_preflight_validation_worker.log", "DONE stage16 preflight validation"):
        return {"state": "not_ready", "action": f"{machine}_stage16_sync"}
    commands = [
        ["scp", f"{host}:{ROOT}/_metadata/stage16_preflight_validation_{machine}.json", str(ROOT / "_metadata/")],
        ["scp", f"{host}:{ROOT}/_logs/supervisor_reports/stage16_preflight_validation_{machine}.md", str(REPORT_DIR / "")],
        ["scp", "-r", f"{host}:{ROOT}/_logs/{machine}", str(ROOT / "_logs/")],
    ]
    errors = []
    for cmd in commands:
        result = run(cmd, timeout=180)
        if result.returncode != 0:
            errors.append(result.stderr[-500:])
    return {"state": "ok" if not errors else "partial", "action": f"{machine}_stage16_sync", "stderr": "\n".join(errors)}


def sync_remote_quality(host: str, machine: str) -> dict[str, str]:
    running, _ = remote_pid_running(host, f"{ROOT}/_logs/{machine}/stage16_quality_python.pid")
    if running:
        return {"state": "deferred_busy", "action": f"{machine}_stage16_quality_sync"}
    if not remote_done(host, f"{ROOT}/_logs/{machine}/stage16_quality_worker.log", "DONE stage16 quality validation"):
        return {"state": "not_ready", "action": f"{machine}_stage16_quality_sync"}
    commands = [
        ["scp", f"{host}:{ROOT}/_metadata/stage16_quality_validation_{machine}.json", str(ROOT / "_metadata/")],
        ["scp", f"{host}:{ROOT}/_logs/supervisor_reports/stage16_quality_validation_{machine}.md", str(REPORT_DIR / "")],
        ["scp", "-r", f"{host}:{ROOT}/_logs/{machine}", str(ROOT / "_logs/")],
    ]
    errors = []
    for cmd in commands:
        result = run(cmd, timeout=180)
        if result.returncode != 0:
            errors.append(result.stderr[-500:])
    return {"state": "ok" if not errors else "partial", "action": f"{machine}_stage16_quality_sync", "stderr": "\n".join(errors)}


def write_reports(payload: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Stage 1.6 Preflight Dispatch",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "| Machine | Stage | State | Action | Deliverable |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["decisions"]:
        lines.append(f"| {row['machine']} | {row['stage']} | {row['state']} | {row['action']} | {row['deliverable']} |")
    lines.extend(["", "## Policy", "", payload["policy"]])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    decisions: list[dict[str, str]] = []
    dragon = start_remote_validation("dragon", "dragon", "market_data")
    decisions.append(
        {
            "machine": "dragon",
            "stage": "Stage 1.6 preflight validation",
            "state": dragon["state"],
            "action": dragon["action"],
            "deliverable": "_metadata/stage16_preflight_validation_dragon.json for market_data",
        }
    )
    gamma = start_remote_validation("gamma", "gamma", "macro_economic,alternative_data,reference_data,economic_calendar")
    decisions.append(
        {
            "machine": "gamma",
            "stage": "Stage 1.6 preflight validation",
            "state": gamma["state"],
            "action": gamma["action"],
            "deliverable": "_metadata/stage16_preflight_validation_gamma.json for macro/alternative/reference/calendar",
        }
    )
    dragon_sync = sync_remote_preflight("dragon", "dragon")
    decisions.append(
        {
            "machine": "dragon->omega",
            "stage": "Stage 1.6 preflight sync",
            "state": dragon_sync["state"],
            "action": dragon_sync["action"],
            "deliverable": "Dragon preflight validation report copied to Omega",
        }
    )
    gamma_sync = sync_remote_preflight("gamma", "gamma")
    decisions.append(
        {
            "machine": "gamma->omega",
            "stage": "Stage 1.6 preflight sync",
            "state": gamma_sync["state"],
            "action": gamma_sync["action"],
            "deliverable": "Gamma preflight validation report copied to Omega",
        }
    )
    dragon_quality = start_remote_quality("dragon", "dragon", "market_data")
    decisions.append(
        {
            "machine": "dragon",
            "stage": "Stage 1.6 quality validation",
            "state": dragon_quality["state"],
            "action": dragon_quality["action"],
            "deliverable": "_metadata/stage16_quality_validation_dragon.json for market_data time/price/volume checks",
        }
    )
    gamma_quality = start_remote_quality("gamma", "gamma", "macro_economic,alternative_data,reference_data,economic_calendar")
    decisions.append(
        {
            "machine": "gamma",
            "stage": "Stage 1.6 quality validation",
            "state": gamma_quality["state"],
            "action": gamma_quality["action"],
            "deliverable": "_metadata/stage16_quality_validation_gamma.json for macro/alternative/reference/calendar checks",
        }
    )
    dragon_quality_sync = sync_remote_quality("dragon", "dragon")
    decisions.append(
        {
            "machine": "dragon->omega",
            "stage": "Stage 1.6 quality sync",
            "state": dragon_quality_sync["state"],
            "action": dragon_quality_sync["action"],
            "deliverable": "Dragon quality validation report copied to Omega",
        }
    )
    gamma_quality_sync = sync_remote_quality("gamma", "gamma")
    decisions.append(
        {
            "machine": "gamma->omega",
            "stage": "Stage 1.6 quality sync",
            "state": gamma_quality_sync["state"],
            "action": gamma_quality_sync["action"],
            "deliverable": "Gamma quality validation report copied to Omega",
        }
    )
    omega = start_local_omega()
    decisions.append(
        {
            "machine": "omega",
            "stage": "Stage 1.6 preflight documentation/inventory",
            "state": omega["state"],
            "action": omega["action"],
            "deliverable": "STAGE_1.6_PREFLIGHT.md, INVENTORY.md, audit_documentation_preflight.json",
        }
    )
    payload = {
        "generated_at": utc_now(),
        "policy": "Use completion-idle capacity after Stage 1.3 for bounded Stage 1.6 preflight audits. Formal Stage 1.6 remains gated on Stage 1.4/1.5 decisions.",
        "decisions": decisions,
    }
    write_reports(payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
