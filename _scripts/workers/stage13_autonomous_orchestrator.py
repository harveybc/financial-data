from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
REPORT_DIR = ROOT / "_logs" / "supervisor_reports"
REPORT = REPORT_DIR / "autonomous_dispatch_report.json"
MD_REPORT = REPORT_DIR / "autonomous_dispatch_report.md"


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
    try:
        pid = pid_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return False, ""
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


def local_log_done(log_file: Path, done_phrase: str) -> bool:
    if not log_file.exists():
        return False
    return done_phrase in log_file.read_text(encoding="utf-8", errors="ignore")[-4000:]


def remote_log_done(host: str, log_file: str, done_phrase: str) -> bool:
    result = remote(
        host,
        f"tail -c 4000 {shlex.quote(log_file)} 2>/dev/null | grep -F {shlex.quote(done_phrase)} >/dev/null && echo done || echo pending",
        timeout=20,
    )
    return "done" in result.stdout


def local_gpu_lock() -> bool:
    return Path("/tmp/gpu_busy.lock").exists()


def remote_gpu_lock(host: str) -> bool:
    result = remote(host, "test -f /tmp/gpu_busy.lock && echo locked || echo free", timeout=20)
    return "locked" in result.stdout


def start_local_worker(
    script: str,
    pid_file: Path,
    out_file: Path,
    log_file: Path,
    done_phrase: str,
) -> dict[str, str]:
    running, pid = local_pid_running(pid_file)
    if running:
        return {"state": "busy", "pid": pid, "action": "kept_running"}
    if local_log_done(log_file, done_phrase):
        return {"state": "completed_idle", "pid": pid, "action": "no_dispatch_needed"}
    out_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = (
        f"PYTHONDONTWRITEBYTECODE=1 nohup python {shlex.quote(script)} "
        f"> {shlex.quote(str(out_file))} 2>&1 & echo $! > {shlex.quote(str(pid_file))}"
    )
    result = run(["bash", "-lc", cmd], timeout=20)
    pid = pid_file.read_text(encoding="utf-8").strip() if pid_file.exists() else ""
    return {
        "state": "started" if result.returncode == 0 else "start_failed",
        "pid": pid,
        "action": script,
        "stderr": result.stderr[-500:],
    }


def start_remote_worker(
    host: str,
    script: str,
    pid_file: str,
    out_file: str,
    log_file: str,
    done_phrase: str,
) -> dict[str, str]:
    running, pid = remote_pid_running(host, pid_file)
    if running:
        return {"state": "busy", "pid": pid, "action": "kept_running"}
    if remote_log_done(host, log_file, done_phrase):
        return {"state": "completed_idle", "pid": pid, "action": "no_dispatch_needed"}
    if remote_gpu_lock(host):
        return {"state": "skipped_gpu_lock", "pid": pid, "action": script}
    cmd = (
        f"mkdir -p {shlex.quote(str(Path(pid_file).parent))} {shlex.quote(str(Path(out_file).parent))}; "
        f"PYTHONDONTWRITEBYTECODE=1 nohup python {shlex.quote(script)} "
        f"> {shlex.quote(out_file)} 2>&1 & echo $! > {shlex.quote(pid_file)}"
    )
    result = remote(host, cmd, timeout=20)
    running, pid = remote_pid_running(host, pid_file)
    return {
        "state": "started" if result.returncode == 0 and pid else "start_failed",
        "pid": pid,
        "action": script,
        "stderr": result.stderr[-500:],
    }


def sync_gamma_outputs() -> dict[str, str]:
    macro_running, _ = remote_pid_running("gamma", f"{ROOT}/_logs/gamma/stage13_macro_onchain_python.pid")
    supp_running, _ = remote_pid_running("gamma", f"{ROOT}/_logs/gamma/stage13_supplemental_python.pid")
    remaining_running, _ = remote_pid_running("gamma", f"{ROOT}/_logs/gamma/stage13_remaining_free_python.pid")
    crypto_accel_running, _ = remote_pid_running("gamma", f"{ROOT}/_logs/gamma/stage13_crypto_perp_accelerator_python.pid")
    if macro_running or supp_running or remaining_running or crypto_accel_running:
        return {"state": "deferred_busy", "action": "gamma_sync"}
    commands = [
        ["scp", "-r", f"gamma:{ROOT}/macro_economic/fred", f"gamma:{ROOT}/macro_economic/bls", str(ROOT / "macro_economic/")],
        ["scp", "-r", f"gamma:{ROOT}/macro_economic/yield_curves/treasury_average_interest_rates", str(ROOT / "macro_economic/yield_curves/")],
        ["scp", "-r", f"gamma:{ROOT}/macro_economic/oecd", f"gamma:{ROOT}/macro_economic/bea", str(ROOT / "macro_economic/")],
        ["scp", "-r", f"gamma:{ROOT}/alternative_data/onchain_btc", f"gamma:{ROOT}/alternative_data/defi_metrics", f"gamma:{ROOT}/alternative_data/sec_filings", str(ROOT / "alternative_data/")],
        ["scp", "-r", f"gamma:{ROOT}/alternative_data/onchain_eth", f"gamma:{ROOT}/alternative_data/short_interest", str(ROOT / "alternative_data/")],
        ["scp", "-r", f"gamma:{ROOT}/market_data/crypto/perpetuals", f"gamma:{ROOT}/market_data/crypto/funding_rates", str(ROOT / "market_data/crypto/")],
        ["scp", "-r", f"gamma:{ROOT}/_logs/gamma", str(ROOT / "_logs/")],
    ]
    errors = []
    for cmd in commands:
        result = run(cmd, timeout=240)
        if result.returncode != 0:
            errors.append(result.stderr[-500:])
    return {"state": "ok" if not errors else "partial", "action": "gamma_sync", "errors": "\n".join(errors)}


def sync_gamma_crypto_to_dragon() -> dict[str, str]:
    running, _ = remote_pid_running("gamma", f"{ROOT}/_logs/gamma/stage13_crypto_perp_accelerator_python.pid")
    if running:
        return {"state": "deferred_busy", "action": "gamma_crypto_to_dragon_sync"}
    done = remote_log_done("gamma", f"{ROOT}/_logs/gamma/stage13_crypto_perp_accelerator_worker.log", "DONE gamma crypto perpetual/funding accelerator")
    if not done:
        return {"state": "not_ready", "action": "gamma_crypto_to_dragon_sync"}
    commands = [
        ["scp", "-r", f"gamma:{ROOT}/market_data/crypto/perpetuals", f"dragon:{ROOT}/market_data/crypto/"],
        ["scp", "-r", f"gamma:{ROOT}/market_data/crypto/funding_rates", f"dragon:{ROOT}/market_data/crypto/"],
    ]
    errors = []
    for cmd in commands:
        result = run(cmd, timeout=600)
        if result.returncode != 0:
            errors.append(result.stderr[-500:])
    return {"state": "ok" if not errors else "partial", "action": "gamma_crypto_to_dragon_sync", "errors": "\n".join(errors)}


def sync_dragon_outputs() -> dict[str, str]:
    running, _ = remote_pid_running("dragon", f"{ROOT}/_logs/dragon/stage13_crypto_python.pid")
    if running:
        return {"state": "deferred_busy", "action": "dragon_sync"}
    result = run(["scp", "-r", f"dragon:{ROOT}/market_data/crypto", str(ROOT / "market_data/")], timeout=600)
    logs = run(["scp", "-r", f"dragon:{ROOT}/_logs/dragon", str(ROOT / "_logs/")], timeout=120)
    state = "ok" if result.returncode == 0 and logs.returncode == 0 else "partial"
    return {"state": state, "action": "dragon_sync", "stderr": (result.stderr + logs.stderr)[-800:]}


def local_file_count(*parts: str) -> int:
    path = ROOT.joinpath(*parts)
    if not path.exists():
        return 0
    return sum(1 for p in path.rglob("*") if p.is_file())


def remote_file_count(host: str, path: str) -> int:
    result = remote(host, f"find {shlex.quote(path)} -type f 2>/dev/null | wc -l", timeout=30)
    try:
        return int(result.stdout.strip().splitlines()[-1])
    except Exception:
        return 0


def remote_log_age_seconds(host: str, path: str) -> int | None:
    result = remote(
        host,
        f"python - <<'PY'\nfrom pathlib import Path\nimport time\np=Path({path!r})\nprint(int(time.time() - p.stat().st_mtime) if p.exists() else -1)\nPY",
        timeout=30,
    )
    try:
        value = int(result.stdout.strip().splitlines()[-1])
    except Exception:
        return None
    return None if value < 0 else value


def build_anomalies(decisions: list[dict[str, str]]) -> list[dict[str, str]]:
    anomalies: list[dict[str, str]] = []
    by_machine = {row["machine"]: row for row in decisions}
    dragon_age = remote_log_age_seconds("dragon", f"{ROOT}/_logs/dragon/stage13_crypto_worker.log")
    dragon_files = remote_file_count("dragon", f"{ROOT}/market_data/crypto")
    gamma_files = remote_file_count("gamma", f"{ROOT}/macro_economic") + remote_file_count("gamma", f"{ROOT}/alternative_data")
    omega_macro = local_file_count("macro_economic")
    omega_alt = local_file_count("alternative_data")

    if by_machine.get("dragon", {}).get("state") == "busy" and dragon_age is not None and dragon_age > 900:
        anomalies.append({
            "severity": "high",
            "category": "stalled_worker",
            "machine": "dragon",
            "evidence": f"Dragon worker busy but crypto log age is {dragon_age}s",
            "suggestion": "Tier 2 should inspect PID, network/API errors, and latest Binance output before restarting.",
        })
    if by_machine.get("dragon", {}).get("state") == "busy" and dragon_files == 0:
        anomalies.append({
            "severity": "medium",
            "category": "missing_output",
            "machine": "dragon",
            "evidence": "Dragon Binance worker is busy but market_data/crypto has 0 files",
            "suggestion": "Check write permissions and output path.",
        })
    if by_machine.get("gamma->omega", {}).get("state") in {"ok", "partial"} and gamma_files and (omega_macro + omega_alt) == 0:
        anomalies.append({
            "severity": "high",
            "category": "sync_gap",
            "machine": "gamma->omega",
            "evidence": f"Gamma has {gamma_files} macro/alternative files but Omega has no synced macro/alternative files",
            "suggestion": "Retry gamma sync and inspect scp stderr.",
        })
    if by_machine.get("gamma->omega", {}).get("state") == "partial":
        anomalies.append({
            "severity": "medium",
            "category": "partial_sync",
            "machine": "gamma->omega",
            "evidence": "Gamma sync reported partial",
            "suggestion": "Inspect autonomous_dispatch_report.json errors and retry missing source folders.",
        })
    if by_machine.get("dragon->omega", {}).get("state") == "partial":
        anomalies.append({
            "severity": "medium",
            "category": "partial_sync",
            "machine": "dragon->omega",
            "evidence": "Dragon sync reported partial",
            "suggestion": "Inspect autonomous_dispatch_report.json errors and retry crypto/log sync.",
        })
    return anomalies


def write_reports(payload: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Autonomous Dispatch Report",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "| Machine | Stage | State | Action | Deliverable |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["decisions"]:
        lines.append(
            f"| {row['machine']} | {row['stage']} | {row['state']} | {row['action']} | {row['deliverable']} |"
        )
    lines.extend(["", "## Deterministic Anomaly Scan", ""])
    if payload["anomalies"]:
        for anomaly in payload["anomalies"]:
            lines.append(
                f"- {anomaly['severity']} {anomaly['category']} on {anomaly['machine']}: {anomaly['evidence']} Suggestion: {anomaly['suggestion']}"
            )
    else:
        lines.append("- No deterministic anomalies detected in this tick.")
    lines.extend([
        "",
        "## Context To Pass Forward",
        "",
        "Preserve active_stage, machine role, current task, expected deliverable, relevant docs/logs, constraints, evidence, anomalies, confidence, and improvement suggestion in the next agent communication.",
    ])
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    decisions: list[dict[str, str]] = []

    omega_light = start_local_worker(
        "_scripts/workers/stage13_omega_light_worker.py",
        ROOT / "_logs/omega/stage13_light_sources_python.pid",
        ROOT / "_logs/omega/stage13_light_sources_python.out",
        ROOT / "_logs/omega/stage13_light_sources_worker.log",
        "DONE omega light-source acquisition",
    )
    decisions.append({
        "machine": "omega",
        "stage": "Stage 1.3 Free Data Acquisition",
        "state": omega_light["state"],
        "action": omega_light["action"],
        "deliverable": "market_data/equities, commodities, forex, HistData-derived parquet/csv",
    })

    omega_reference = start_local_worker(
        "_scripts/workers/stage13_omega_reference_worker.py",
        ROOT / "_logs/omega/stage13_reference_python.pid",
        ROOT / "_logs/omega/stage13_reference_python.out",
        ROOT / "_logs/omega/stage13_reference_worker.log",
        "DONE omega reference/CFTC worker",
    )
    decisions.append({
        "machine": "omega",
        "stage": "Stage 1.3 Free Data Acquisition",
        "state": omega_reference["state"],
        "action": omega_reference["action"],
        "deliverable": "CFTC, holidays, trading calendars, reference provenance",
    })

    omega_calendar = start_local_worker(
        "_scripts/workers/stage13_omega_economic_calendar_worker.py",
        ROOT / "_logs/omega/stage13_economic_calendar_python.pid",
        ROOT / "_logs/omega/stage13_economic_calendar_python.out",
        ROOT / "_logs/omega/stage13_economic_calendar_worker.log",
        "DONE omega economic calendar worker all events attempted",
    )
    decisions.append({
        "machine": "omega",
        "stage": "Stage 1.3 Task 1.3.P Economic calendar",
        "state": omega_calendar["state"],
        "action": omega_calendar["action"],
        "deliverable": "economic_calendar/release_actuals with FRED actuals and scheduled-events gap note",
    })

    dragon = start_remote_worker(
        "dragon",
        "_scripts/workers/stage13_dragon_crypto_worker.py",
        f"{ROOT}/_logs/dragon/stage13_crypto_python.pid",
        f"{ROOT}/_logs/dragon/stage13_crypto_python.out",
        f"{ROOT}/_logs/dragon/stage13_crypto_worker.log",
        "DONE dragon Binance acquisition",
    )
    decisions.append({
        "machine": "dragon",
        "stage": "Stage 1.3 Task 1.3.F Binance crypto comprehensive",
        "state": dragon["state"],
        "action": dragon["action"],
        "deliverable": "market_data/crypto spot/perpetual/funding outputs",
    })

    gamma_macro = start_remote_worker(
        "gamma",
        "_scripts/workers/stage13_gamma_macro_onchain_worker.py",
        f"{ROOT}/_logs/gamma/stage13_macro_onchain_python.pid",
        f"{ROOT}/_logs/gamma/stage13_macro_onchain_python.out",
        f"{ROOT}/_logs/gamma/stage13_macro_onchain_worker.log",
        "DONE gamma macro/on-chain acquisition",
    )
    decisions.append({
        "machine": "gamma",
        "stage": "Stage 1.3 macro/on-chain public acquisition",
        "state": gamma_macro["state"],
        "action": gamma_macro["action"],
        "deliverable": "FRED, CoinMetrics attempts, Blockchain.com, mempool, SEC, DeFiLlama",
    })

    gamma_supplemental = start_remote_worker(
        "gamma",
        "_scripts/workers/stage13_gamma_supplemental_worker.py",
        f"{ROOT}/_logs/gamma/stage13_supplemental_python.pid",
        f"{ROOT}/_logs/gamma/stage13_supplemental_python.out",
        f"{ROOT}/_logs/gamma/stage13_supplemental_worker.log",
        "DONE gamma supplemental worker",
    )
    decisions.append({
        "machine": "gamma",
        "stage": "Stage 1.3 supplemental public macro",
        "state": gamma_supplemental["state"],
        "action": gamma_supplemental["action"],
        "deliverable": "Treasury FiscalData, BLS public series, gap notes",
    })

    gamma_remaining = start_remote_worker(
        "gamma",
        "_scripts/workers/stage13_gamma_remaining_free_worker.py",
        f"{ROOT}/_logs/gamma/stage13_remaining_free_python.pid",
        f"{ROOT}/_logs/gamma/stage13_remaining_free_python.out",
        f"{ROOT}/_logs/gamma/stage13_remaining_free_worker.log",
        "DONE gamma remaining free-source worker",
    )
    decisions.append({
        "machine": "gamma",
        "stage": "Stage 1.3 Tasks 1.3.I/1.3.M/1.3.Q/1.3.R remaining free-source follow-up",
        "state": gamma_remaining["state"],
        "action": gamma_remaining["action"],
        "deliverable": "Etherscan free snapshots, FINRA Reg SHO daily short-volume, OECD CLI, BEA gap note",
    })

    gamma_crypto_accel = start_remote_worker(
        "gamma",
        "_scripts/workers/stage13_gamma_crypto_perp_accelerator_worker.py",
        f"{ROOT}/_logs/gamma/stage13_crypto_perp_accelerator_python.pid",
        f"{ROOT}/_logs/gamma/stage13_crypto_perp_accelerator_python.out",
        f"{ROOT}/_logs/gamma/stage13_crypto_perp_accelerator_worker.log",
        "DONE gamma crypto perpetual/funding accelerator",
    )
    decisions.append({
        "machine": "gamma",
        "stage": "Stage 1.3 Task 1.3.F Binance crypto acceleration",
        "state": gamma_crypto_accel["state"],
        "action": gamma_crypto_accel["action"],
        "deliverable": "market_data/crypto/perpetuals and funding_rates fetched on Gamma, then synced to Dragon/Omega",
    })

    gamma_sync = sync_gamma_outputs()
    decisions.append({
        "machine": "gamma->omega",
        "stage": "Stage 1.3 canonical sync",
        "state": gamma_sync["state"],
        "action": gamma_sync["action"],
        "deliverable": "Gamma completed macro/on-chain outputs copied to Omega",
    })

    gamma_crypto_dragon_sync = sync_gamma_crypto_to_dragon()
    decisions.append({
        "machine": "gamma->dragon",
        "stage": "Stage 1.3 crypto acceleration sync",
        "state": gamma_crypto_dragon_sync["state"],
        "action": gamma_crypto_dragon_sync["action"],
        "deliverable": "Gamma perpetual/funding outputs copied to Dragon so Dragon skips duplicated work",
    })

    dragon_sync = sync_dragon_outputs()
    decisions.append({
        "machine": "dragon->omega",
        "stage": "Stage 1.3 canonical sync",
        "state": dragon_sync["state"],
        "action": dragon_sync["action"],
        "deliverable": "Dragon crypto outputs copied to Omega after worker completion",
    })

    payload = {
        "generated_at": utc_now(),
        "policy": "Detect idle machines each Tier 2 cron tick; keep busy workers running; start safe pending Stage 1.3 workers; sync completed remote outputs to Omega.",
        "decisions": decisions,
        "anomalies": build_anomalies(decisions),
    }
    write_reports(payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
