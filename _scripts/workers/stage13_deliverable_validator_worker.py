from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
LOG = ROOT / "_logs" / "omega" / "stage13_deliverable_validator_worker.log"
WORK_PLAN = ROOT / "work_plan" / "13_STAGE_1_3_FREE_DATA_ACQUISITION.md"
MASTER_PLAN = ROOT / "work_plan" / "00_PROJECT_3_MASTER_PLAN.md"
STAGE16_PLAN = ROOT / "work_plan" / "16_STAGE_1_6_VALIDATION_AND_DOCUMENTATION.md"
JSON_OUT = ROOT / "_metadata" / "STAGE_1_3_DELIVERABLE_VALIDATION.json"
MD_OUT = ROOT / "_logs" / "supervisor_reports" / "stage13_deliverable_validation.md"
QUEUE = ROOT / "_logs" / "supervisor_reports" / "escalation_queue.json"

DOC_FILES = {"README.md", "data_dictionary.md", "provenance.json"}
DATA_SUFFIXES = {".parquet", ".csv", ".json", ".jsonl", ".zip"}
STATUS_ORDER = {"validated": 0, "in_progress": 1, "partial": 2, "needs_codex": 3, "failed": 4}


@dataclass
class TaskResult:
    task_id: str
    title: str
    machine: str
    workplan_doc: str
    workplan_summary: str
    expected_deliverable: list[str]
    evidence: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    status: str = "needs_codex"
    confidence: float = 0.0
    next_action: str = ""
    escalation_question: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def run(cmd: list[str], timeout: int = 45) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)


def remote(host: str, command: str, timeout: int = 45) -> subprocess.CompletedProcess[str]:
    wrapped = (
        "source ~/.bashrc >/dev/null 2>&1; "
        "source /home/harveybc/anaconda3/etc/profile.d/conda.sh >/dev/null 2>&1; "
        "conda activate tensorflow >/dev/null 2>&1; "
        f"cd {shlex.quote(str(ROOT))}; {command}"
    )
    return run(["ssh", host, "bash", "-lc", wrapped], timeout=timeout)


def local_count(path: str, suffixes: tuple[str, ...] = (".parquet", ".csv", ".json", ".zip")) -> int:
    root = ROOT / path
    if not root.exists():
        return 0
    return sum(1 for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes)


def local_dirs_with_file(path: str, filename: str) -> int:
    root = ROOT / path
    if not root.exists():
        return 0
    return sum(1 for p in root.rglob(filename) if p.is_file())


def remote_count(host: str, path: str, name_pattern: str = "*") -> int:
    result = remote(
        host,
        f"find {shlex.quote(path)} -type f -name {shlex.quote(name_pattern)} 2>/dev/null | wc -l",
        timeout=60,
    )
    try:
        return int(result.stdout.strip().splitlines()[-1])
    except Exception:
        return 0


def remote_dir_count(host: str, path: str) -> int:
    result = remote(
        host,
        f"find {shlex.quote(path)} -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l",
        timeout=60,
    )
    try:
        return int(result.stdout.strip().splitlines()[-1])
    except Exception:
        return 0


def remote_latest_binance_tradable(host: str, log_path: str) -> int:
    result = remote(
        host,
        f"grep -E 'top50_candidates=[0-9]+ binance_tradable=[0-9]+' {shlex.quote(log_path)} 2>/dev/null | tail -1",
        timeout=30,
    )
    match = re.search(r"binance_tradable=(\d+)", result.stdout)
    return int(match.group(1)) if match else 0


def local_json(path: str) -> Any:
    try:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def parquet_stats(path: str, unique_col: str | None = None) -> dict[str, int]:
    file = ROOT / path
    if not file.exists():
        return {"rows": 0, "unique": 0}
    try:
        columns = [unique_col] if unique_col else None
        df = pd.read_parquet(file, columns=columns)
    except Exception:
        return {"rows": 0, "unique": 0}
    stats = {"rows": int(len(df)), "unique": 0}
    if unique_col and unique_col in df.columns:
        stats["unique"] = int(df[unique_col].nunique())
    return stats


def remote_pid_running(host: str, pid_file: str) -> bool:
    result = remote(
        host,
        f"pid=$(cat {shlex.quote(pid_file)} 2>/dev/null || true); "
        "test -n \"$pid\" && ps -p \"$pid\" >/dev/null 2>&1 && echo running || echo idle",
        timeout=30,
    )
    return "running" in result.stdout


def task_snippet(task_id: str) -> str:
    text = WORK_PLAN.read_text(encoding="utf-8")
    pattern = rf"### Task {re.escape(task_id)}:[\s\S]*?(?=\n### Task 1\.3\.|\n## \d+\.|\Z)"
    match = re.search(pattern, text)
    if not match:
        return ""
    lines = [line.strip() for line in match.group(0).splitlines() if line.strip()]
    return " ".join(lines[:12])[:900]


def has_standard_docs(folder: Path) -> bool:
    return all((folder / name).exists() for name in DOC_FILES)


def docs_missing_under(path: str) -> int:
    root = ROOT / path
    if not root.exists():
        return 0
    data_dirs: set[Path] = set()
    for file in root.rglob("*"):
        if file.is_file() and file.name not in DOC_FILES and file.suffix.lower() in DATA_SUFFIXES:
            data_dirs.add(file.parent)
    return sum(1 for folder in data_dirs if not has_standard_docs(folder))


def status_from(required: bool, partial: bool = False, in_progress: bool = False) -> tuple[str, float]:
    if in_progress:
        return "in_progress", 0.95
    if required and not partial:
        return "validated", 0.9
    if required and partial:
        return "partial", 0.78
    return "needs_codex", 0.55


def result(task_id: str, title: str, machine: str, expected: list[str]) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        title=title,
        machine=machine,
        workplan_doc=rel(WORK_PLAN),
        workplan_summary=task_snippet(task_id),
        expected_deliverable=expected,
    )


def validate_tasks() -> list[TaskResult]:
    tasks: list[TaskResult] = []

    t = result("1.3.A", "Setup shared utilities", "Omega", ["_scripts/lib/*.py"])
    required = ["validation.py", "provenance.py", "documentation.py", "acquisition_log.py"]
    existing = [name for name in required if (ROOT / "_scripts" / "lib" / name).exists()]
    t.evidence = ["work_plan/13_STAGE_1_3_FREE_DATA_ACQUISITION.md § Task 1.3.A", "_scripts/lib"]
    t.checks = {"required_modules": required, "existing_modules": existing}
    t.status, t.confidence = status_from(len(existing) == len(required))
    t.next_action = "Keep wrappers aligned with worker common utilities."
    tasks.append(t)

    t = result("1.3.B", "FRED comprehensive macro pull", "Gamma", ["macro_economic/fred/**/observations.parquet"])
    fred_count = local_count("macro_economic/fred", (".parquet",))
    t.evidence = ["macro_economic/fred", "_metadata/acquisition_log.csv", "_logs/gamma/stage13_macro_onchain_worker.log"]
    t.checks = {"fred_observation_files": fred_count, "catalog_expected_series_count": 150, "minimum_for_current_task_list": 80, "missing_doc_dirs": docs_missing_under("macro_economic/fred")}
    if fred_count >= 80 and t.checks["missing_doc_dirs"] == 0:
        t.status, t.confidence = "validated", 0.86
        t.next_action = "Stage 1.6 coverage audit should compare against the full catalog series list."
    else:
        t.status, t.confidence = "needs_codex", 0.62
        t.next_action = "Codex should decide whether current FRED bundle is acceptable or dispatch additional catalog series."
        t.escalation_question = "FRED task expects roughly 150 catalog series; local observations count is below that threshold. Should Tier 2 expand FRED acquisition now?"
    tasks.append(t)

    t = result("1.3.C", "Yahoo Finance equity indices", "Omega", ["market_data/equities/**/daily.parquet"])
    equity_files = local_count("market_data/equities", (".parquet",))
    t.evidence = ["market_data/equities", "_logs/omega/stage13_light_sources_worker.log"]
    t.checks = {"daily_parquet_files": equity_files, "missing_doc_dirs": docs_missing_under("market_data/equities")}
    t.status, t.confidence = status_from(equity_files >= 25 and t.checks["missing_doc_dirs"] == 0)
    t.next_action = "If below catalog count in Stage 1.6, backfill the missing equity/ETF symbols."
    tasks.append(t)

    t = result("1.3.D", "Yahoo Finance commodities, ETFs, EM FX, bonds", "Omega", ["market_data/commodities/**/daily.parquet", "market_data/forex/emerging_markets/**/daily.parquet", "market_data/equities/etfs/**/daily.parquet"])
    commodity = local_count("market_data/commodities", (".parquet",))
    emfx = local_count("market_data/forex/emerging_markets", (".parquet",))
    etfs = local_count("market_data/equities/etfs", (".parquet",))
    t.evidence = ["market_data/commodities", "market_data/forex/emerging_markets", "market_data/equities/etfs"]
    t.checks = {"commodity_files": commodity, "em_fx_files": emfx, "etf_files": etfs, "missing_doc_dirs": docs_missing_under("market_data/commodities") + docs_missing_under("market_data/forex/emerging_markets") + docs_missing_under("market_data/equities/etfs")}
    t.status, t.confidence = status_from(commodity >= 8 and emfx >= 5 and etfs >= 20 and t.checks["missing_doc_dirs"] == 0)
    t.next_action = "No action unless catalog coverage audit finds missing symbols."
    tasks.append(t)

    t = result("1.3.E", "HistData FX processing", "Omega", ["market_data/forex/g10/<pair>/{5m,15m,1h,4h}.parquet"])
    pairs = ["eurusd", "usdjpy", "gbpusd", "usdchf", "audusd", "usdcad", "nzdusd", "eurgbp", "eurjpy", "gbpjpy"]
    tfs = ["5m", "15m", "1h", "4h"]
    missing = [f"{pair}/{tf}.parquet" for pair in pairs for tf in tfs if not (ROOT / "market_data" / "forex" / "g10" / pair / f"{tf}.parquet").exists()]
    t.evidence = ["market_data/forex/g10", "/home/harveybc/Downloads/histdata", "_logs/omega/stage13_light_sources_worker.log"]
    t.checks = {"expected_files": len(pairs) * len(tfs), "missing_files": missing[:80], "actual_files": len(pairs) * len(tfs) - len(missing), "missing_doc_dirs": docs_missing_under("market_data/forex/g10")}
    t.status, t.confidence = status_from(not missing and t.checks["missing_doc_dirs"] == 0)
    t.next_action = "If missing remains, inspect HistData downloads under /home/harveybc/Downloads/histdata."
    tasks.append(t)

    dragon_busy = remote_pid_running("dragon", f"{ROOT}/_logs/dragon/stage13_crypto_python.pid")
    gamma_crypto_busy = remote_pid_running("gamma", f"{ROOT}/_logs/gamma/stage13_crypto_perp_accelerator_python.pid")
    t = result("1.3.F", "Binance crypto comprehensive", "Dragon/Gamma", ["market_data/crypto/spot_top50/**/{5m,15m,1h,4h}.parquet", "market_data/crypto/perpetuals/**/{5m,15m,1h,4h}.parquet", "market_data/crypto/funding_rates/**/*.parquet"])
    dragon_spot = remote_count("dragon", f"{ROOT}/market_data/crypto/spot_top50", "*.parquet")
    dragon_perp = remote_count("dragon", f"{ROOT}/market_data/crypto/perpetuals", "*.parquet")
    dragon_funding = remote_count("dragon", f"{ROOT}/market_data/crypto/funding_rates", "*.parquet")
    gamma_perp = remote_count("gamma", f"{ROOT}/market_data/crypto/perpetuals", "*.parquet")
    gamma_funding = remote_count("gamma", f"{ROOT}/market_data/crypto/funding_rates", "*.parquet")
    local_spot = local_count("market_data/crypto/spot_top50", (".parquet",))
    local_perp = local_count("market_data/crypto/perpetuals", (".parquet",))
    local_funding = local_count("market_data/crypto/funding_rates", (".parquet",))
    dragon_spot_symbols = remote_dir_count("dragon", f"{ROOT}/market_data/crypto/spot_top50")
    binance_tradable = remote_latest_binance_tradable("dragon", f"{ROOT}/_logs/dragon/stage13_crypto_worker.log")
    exclusions_payload = local_json("_logs/dragon/stage13_crypto_exclusions.json")
    exclusions = exclusions_payload.get("exclusions", []) if isinstance(exclusions_payload, dict) else []
    spot_no_data_exclusions = len([
        item for item in exclusions
        if isinstance(item, dict) and item.get("dataset_type") == "spot_top50"
    ])
    expected_spot_files = max((binance_tradable * 4) - spot_no_data_exclusions, 0)
    t.evidence = ["dragon:market_data/crypto", "gamma:market_data/crypto", "_logs/dragon/stage13_crypto_worker.log", "_logs/gamma/stage13_crypto_perp_accelerator_worker.log"]
    t.checks = {
        "dragon_spot_parquet": dragon_spot,
        "omega_spot_parquet": local_spot,
        "dragon_spot_symbols": dragon_spot_symbols,
        "binance_tradable_top50_symbols": binance_tradable,
        "documented_spot_no_data_exclusions": spot_no_data_exclusions,
        "dragon_perp_parquet": dragon_perp,
        "omega_perp_parquet": local_perp,
        "dragon_funding_parquet": dragon_funding,
        "omega_funding_parquet": local_funding,
        "gamma_perp_parquet": gamma_perp,
        "gamma_funding_parquet": gamma_funding,
        "dragon_busy": dragon_busy,
        "gamma_crypto_busy": gamma_crypto_busy,
        "expected_spot_files_after_binance_filter": expected_spot_files,
        "expected_perp_files": 40,
        "expected_funding_files": 10,
    }
    if dragon_busy or gamma_crypto_busy:
        t.status, t.confidence = "in_progress", 0.96
        t.next_action = "Keep workers running; validate after Gamma crypto sync and Dragon completion."
    elif expected_spot_files and max(dragon_spot, local_spot) >= expected_spot_files and max(dragon_perp, gamma_perp, local_perp) >= 40 and max(dragon_funding, gamma_funding, local_funding) >= 10:
        t.status, t.confidence = "validated", 0.88
        t.next_action = "Run Stage 1.6 quality validation; documented Binance no-data exclusions remain in _logs/dragon/stage13_crypto_exclusions.json."
    else:
        t.status, t.confidence = "failed", 0.75
        t.next_action = "Restart or repair missing crypto acquisition slices."
        t.escalation_question = "Binance workers are not running and expected crypto output counts are incomplete. Should Codex inspect worker completion markers and restart missing slices?"
    tasks.append(t)

    t = result("1.3.G", "CoinMetrics Community on-chain", "Gamma", ["alternative_data/onchain_*/coinmetrics_community/*"])
    cm_files = len(list((ROOT / "alternative_data").glob("onchain_*/coinmetrics_community/*"))) if (ROOT / "alternative_data").exists() else 0
    has_gap = (ROOT / "_logs" / "gamma" / "stage13_macro_onchain_escalation.md").exists()
    t.evidence = ["alternative_data/onchain_*/coinmetrics_community", "_logs/gamma/stage13_macro_onchain_escalation.md"]
    t.checks = {"coinmetrics_files": cm_files, "has_escalation_note": has_gap}
    if cm_files:
        t.status, t.confidence = "partial" if has_gap else "validated", 0.78 if has_gap else 0.88
        t.next_action = "Review metric coverage against advanced on-chain subscription gaps."
    else:
        t.status, t.confidence = "needs_codex", 0.7
        t.next_action = "Codex should decide whether CoinMetrics Community is blocked/free-tier unavailable or needs endpoint repair."
        t.escalation_question = "CoinMetrics Community deliverable appears absent and an escalation note exists. Is this a provider limitation, endpoint bug, or subscription decision input?"
    tasks.append(t)

    t = result("1.3.H", "Blockchain.com BTC supplementary", "Gamma", ["alternative_data/onchain_btc/blockchain_com/*"])
    count = local_count("alternative_data/onchain_btc/blockchain_com")
    t.evidence = ["alternative_data/onchain_btc/blockchain_com", "_logs/gamma/stage13_macro_onchain_worker.log"]
    t.checks = {"data_files": count, "missing_doc_dirs": docs_missing_under("alternative_data/onchain_btc/blockchain_com")}
    t.status, t.confidence = status_from(count >= 1 and t.checks["missing_doc_dirs"] == 0)
    t.next_action = "Stage 1.6 should check individual metrics against catalog."
    tasks.append(t)

    t = result("1.3.I", "Etherscan ETH supplementary", "Gamma", ["alternative_data/onchain_eth/etherscan/*"])
    eth_count = local_count("alternative_data/onchain_eth")
    gap_text = ROOT / "_logs" / "gamma" / "stage13_remaining_free_gaps.md"
    t.evidence = ["alternative_data/onchain_eth", "_logs/gamma/stage13_remaining_free_gaps.md"]
    t.checks = {"onchain_eth_files": eth_count, "gap_note_exists": gap_text.exists()}
    if eth_count and gap_text.exists():
        t.status, t.confidence = "partial", 0.76
        t.next_action = "Treat historical Pro endpoints as Stage 1.4 subscription evidence; no more free-source retry unless a replacement source is approved."
    else:
        t.status, t.confidence = status_from(eth_count >= 1)
        t.next_action = "If absent, inspect key/env and endpoint errors."
    tasks.append(t)

    t = result("1.3.J", "Mempool.space", "Gamma", ["alternative_data/onchain_btc/mempool_space/*"])
    mempool_count = local_count("alternative_data/onchain_btc/mempool_space")
    t.evidence = ["alternative_data/onchain_btc/mempool_space", "_logs/gamma/stage13_macro_onchain_worker.log"]
    t.checks = {"data_files": mempool_count, "missing_doc_dirs": docs_missing_under("alternative_data/onchain_btc/mempool_space")}
    t.status, t.confidence = status_from(mempool_count >= 1 and t.checks["missing_doc_dirs"] == 0)
    t.next_action = "No action unless Stage 1.6 metric coverage finds missing required metrics."
    tasks.append(t)

    t = result("1.3.K", "SEC EDGAR metadata", "Gamma", ["alternative_data/sec_filings/edgar or metadata"])
    sec_count = local_count("alternative_data/sec_filings")
    sec_stats = parquet_stats("alternative_data/sec_filings/edgar_sp500_metadata/filing_metadata.parquet", "ticker")
    t.evidence = ["alternative_data/sec_filings", "_logs/gamma/stage13_macro_onchain_worker.log"]
    t.checks = {"sec_files": sec_count, "plan_requested_sp500_form_metadata": True, "sp500_metadata_rows": sec_stats["rows"], "sp500_metadata_tickers": sec_stats["unique"]}
    if sec_stats["rows"] >= 100000 and sec_stats["unique"] >= 400:
        t.status, t.confidence = "validated", 0.9
        t.next_action = "Stage 1.6 should validate filing-date completeness by form and ticker."
    elif sec_count >= 1:
        t.status, t.confidence = "partial", 0.72
        t.next_action = "Codex should decide whether current SEC ticker metadata is enough or S&P 500 filing metadata must be fetched."
        t.escalation_question = "Stage 1.3.K asks for S&P 500 10-K/10-Q/8-K/Form 4 metadata. Current SEC output appears limited; should Gamma run a broader EDGAR metadata job?"
    else:
        t.status, t.confidence = "failed", 0.8
        t.next_action = "Dispatch SEC metadata acquisition."
    tasks.append(t)

    t = result("1.3.L", "CFTC COT reports", "Omega", ["alternative_data/cot_reports/cftc*"])
    cot_count = local_count("alternative_data/cot_reports", (".zip", ".parquet", ".csv", ".txt"))
    t.evidence = ["alternative_data/cot_reports", "_logs/omega/stage13_reference_worker.log"]
    t.checks = {"cot_data_files": cot_count, "missing_doc_dirs": docs_missing_under("alternative_data/cot_reports")}
    t.status, t.confidence = status_from(cot_count >= 10 and t.checks["missing_doc_dirs"] == 0)
    t.next_action = "CFTC missing years should remain documented as provider gaps."
    tasks.append(t)

    t = result("1.3.M", "FINRA short interest", "Gamma", ["alternative_data/short_interest/*"])
    finra_count = local_count("alternative_data/short_interest")
    finra_running = remote_pid_running("dragon", f"{ROOT}/_logs/dragon/stage13_finra_short_interest_python.pid")
    finra_stats = parquet_stats("alternative_data/short_interest/finra_consolidated_short_interest/2025.parquet", "settlementDate")
    t.evidence = ["alternative_data/short_interest", "_logs/gamma/stage13_remaining_free_gaps.md"]
    t.checks = {
        "finra_files": finra_count,
        "plan_requested_biweekly_short_interest": True,
        "current_regsho_daily": (ROOT / "alternative_data" / "short_interest" / "finra_regsho_daily").exists(),
        "finra_consolidated_2025_rows": finra_stats["rows"],
        "finra_consolidated_settlement_dates": finra_stats["unique"],
        "dragon_finra_worker_running": finra_running,
    }
    if finra_running:
        t.status, t.confidence = "in_progress", 0.95
        t.next_action = "Keep Dragon FINRA consolidated short-interest worker running, then sync and revalidate."
    elif finra_stats["rows"] > 0 and finra_stats["unique"] >= 20:
        t.status, t.confidence = "validated", 0.9
        t.next_action = "Stage 1.6 should compare consolidated short-interest coverage to selected equity universe."
    elif finra_count:
        t.status, t.confidence = "needs_codex", 0.68
        t.next_action = "Codex should decide whether Reg SHO daily volume is acceptable or true bi-weekly short interest is still required."
        t.escalation_question = "FINRA deliverable currently appears to be daily Reg SHO short volume, while the work plan requested bi-weekly short interest. Should we fetch another FINRA dataset?"
    else:
        t.status, t.confidence = "failed", 0.8
        t.next_action = "Dispatch FINRA short-interest acquisition."
    tasks.append(t)

    t = result("1.3.N", "DeFiLlama", "Gamma", ["alternative_data/defi_metrics/*"])
    defi_count = local_count("alternative_data/defi_metrics")
    t.evidence = ["alternative_data/defi_metrics", "_logs/gamma/stage13_macro_onchain_worker.log"]
    t.checks = {"defillama_files": defi_count, "missing_doc_dirs": docs_missing_under("alternative_data/defi_metrics")}
    t.status, t.confidence = status_from(defi_count >= 1 and t.checks["missing_doc_dirs"] == 0)
    t.next_action = "No action unless Stage 1.6 coverage audit finds missing chains/protocols."
    tasks.append(t)

    t = result("1.3.O", "Trading calendars and holidays", "Omega", ["reference_data/trading_calendars/*/schedule.parquet", "reference_data/holidays/holidays.parquet"])
    calendars = local_count("reference_data/trading_calendars", (".parquet",))
    holidays = (ROOT / "reference_data" / "holidays" / "holidays.parquet").exists()
    t.evidence = ["reference_data/trading_calendars", "reference_data/holidays", "_logs/omega/stage13_reference_worker.log"]
    t.checks = {"calendar_files": calendars, "holidays_exists": holidays, "missing_doc_dirs": docs_missing_under("reference_data")}
    t.status, t.confidence = status_from(calendars >= 6 and holidays and t.checks["missing_doc_dirs"] == 0)
    t.next_action = "Install exchange_calendars later if exact exchange calendars need replacement for fallback schedules."
    tasks.append(t)

    t = result("1.3.P", "Economic calendar scheduled events and actuals", "Omega", ["economic_calendar/release_actuals/*/actuals.parquet", "economic_calendar/scheduled_events/*"])
    actuals = local_count("economic_calendar/release_actuals", (".parquet",))
    scheduled_files = local_count("economic_calendar/scheduled_events")
    scheduled_gap = (ROOT / "economic_calendar" / "scheduled_events" / "stage13_scheduled_events_gap.md").exists()
    t.evidence = ["economic_calendar/release_actuals", "economic_calendar/scheduled_events", "_logs/omega/stage13_economic_calendar_worker.log"]
    t.checks = {"release_actual_files": actuals, "scheduled_event_files": scheduled_files, "scheduled_gap_note": scheduled_gap}
    if actuals >= 8 and scheduled_gap:
        t.status, t.confidence = "partial", 0.78
        t.next_action = "FRED actuals and release-date proxy are present; Trading Economics guest access is discontinued and FXStreet requires OAuth, so consensus/surprise is a Stage 1.4 credential/subscription decision."
    else:
        t.status, t.confidence = status_from(actuals >= 8 and scheduled_files >= 1)
        t.next_action = "Validate scheduled-event source and surprise calculation."
    tasks.append(t)

    t = result("1.3.Q", "BLS, BEA, Treasury supplementary", "Gamma", ["macro_economic/bls/*", "macro_economic/bea/*", "macro_economic/yield_curves/treasury_average_interest_rates/*"])
    bls = local_count("macro_economic/bls")
    treasury = local_count("macro_economic/yield_curves/treasury_average_interest_rates")
    bea_data = local_count("macro_economic/bea", (".parquet", ".csv"))
    bea_gap = (ROOT / "macro_economic" / "bea" / "stage13_bea_gap.md").exists()
    t.evidence = ["macro_economic/bls", "macro_economic/bea", "macro_economic/yield_curves/treasury_average_interest_rates"]
    t.checks = {"bls_files": bls, "treasury_files": treasury, "bea_data_files": bea_data, "bea_gap_note": bea_gap}
    if bls >= 1 and treasury >= 1 and bea_data >= 1:
        t.status, t.confidence = "validated", 0.9
        t.next_action = "Stage 1.6 should compare direct BEA tables against overlapping FRED macro series."
    elif bls and treasury and bea_gap:
        t.status, t.confidence = "partial", 0.78
        t.next_action = "Treat BEA key/direct API gap as subscription/key decision evidence; FRED covers many BEA series."
        t.escalation_question = "BLS and Treasury are present, BEA direct API has a documented key gap. Is FRED BEA coverage sufficient or should the user obtain BEA_API_KEY?"
    else:
        t.status, t.confidence = status_from(bls >= 1 and treasury >= 1 and not bea_gap)
        t.next_action = "Complete missing BLS/Treasury/BEA slice."
    tasks.append(t)

    t = result("1.3.R", "OECD selected indicators", "Gamma", ["macro_economic/oecd/cli/monthly.parquet"])
    oecd = local_count("macro_economic/oecd", (".parquet", ".csv", ".json"))
    t.evidence = ["macro_economic/oecd", "_logs/gamma/stage13_remaining_free_worker.log"]
    t.checks = {"oecd_files": oecd, "missing_doc_dirs": docs_missing_under("macro_economic/oecd")}
    t.status, t.confidence = status_from(oecd >= 1 and t.checks["missing_doc_dirs"] == 0)
    t.next_action = "No action unless coverage audit identifies additional OECD non-FRED indicators."
    tasks.append(t)

    t = result("Stage 1.3 Deliverables", "Final Stage 1.3 reports", "Omega", ["STAGE_1.3_DELIVERABLE.md", "STAGE_1.3_INVENTORY.md"])
    deliverable = (ROOT / "STAGE_1.3_DELIVERABLE.md").exists()
    inventory = (ROOT / "STAGE_1.3_INVENTORY.md").exists()
    active = any(item.status == "in_progress" for item in tasks)
    t.evidence = ["work_plan/13_STAGE_1_3_FREE_DATA_ACQUISITION.md § 7", "STAGE_1.3_DELIVERABLE.md", "STAGE_1.3_INVENTORY.md"]
    t.checks = {"deliverable_report_exists": deliverable, "inventory_report_exists": inventory, "active_acquisition_still_running": active}
    if active:
        t.status, t.confidence = "in_progress", 0.95
        t.next_action = "Generate final reports after active acquisition and remote sync complete."
    elif deliverable and inventory:
        t.status, t.confidence = "validated", 0.9
        t.next_action = "User can review Stage 1.4 subscription decision matrix."
    else:
        t.status, t.confidence = "needs_codex", 0.8
        t.next_action = "Codex should generate final Stage 1.3 deliverable and inventory reports after resolving validation escalations."
        t.escalation_question = "Stage 1.3 acquisition appears inactive but final deliverable documents are missing. Should Codex synthesize them now?"
    tasks.append(t)

    return tasks


def write_escalation_queue(tasks: list[TaskResult]) -> None:
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    if QUEUE.exists():
        try:
            payload = json.loads(QUEUE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"queue": []}
    else:
        payload = {"queue": []}
    queue = payload.setdefault("queue", [])
    by_id = {
        item.get("id"): item
        for item in queue
        if isinstance(item, dict) and not str(item.get("id", "")).startswith("stage13-deliverable-")
    }

    for task in tasks:
        if task.status not in {"needs_codex", "failed"} and not task.escalation_question:
            continue
        if task.status == "in_progress":
            continue
        escalation_id = f"stage13-deliverable-{re.sub(r'[^a-zA-Z0-9]+', '-', task.task_id).strip('-').lower()}"
        item = {
            "id": escalation_id,
            "created_or_updated_at": utc_now(),
            "stage": "Stage 1.3 Free Data Acquisition",
            "task_id": task.task_id,
            "title": task.title,
            "category": "deliverable_validation",
            "severity": "high" if task.status == "failed" else "medium",
            "status": "pending_codex",
            "confidence": task.confidence,
            "workplan_doc": task.workplan_doc,
            "required_context": [rel(MASTER_PLAN), task.workplan_doc, rel(STAGE16_PLAN)],
            "deliverables": task.expected_deliverable,
            "evidence": task.evidence,
            "checks": task.checks,
            "question_for_codex": task.escalation_question or task.next_action,
            "context_to_pass_forward": "Read the work-plan task spec and produced deliverable before deciding. Do not guess or mark complete from status text alone.",
        }
        by_id[escalation_id] = item

    payload["queue"] = sorted(by_id.values(), key=lambda row: row.get("id", ""))
    QUEUE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_reports(tasks: list[TaskResult]) -> None:
    status_counts: dict[str, int] = {}
    for task in tasks:
        status_counts[task.status] = status_counts.get(task.status, 0) + 1
    payload = {
        "generated_at": utc_now(),
        "stage": "Stage 1.3 Free Data Acquisition",
        "validation_rule": "Validate each task against the work-plan spec plus produced artifacts; uncertainty routes to Tier 4/Codex.",
        "status_counts": status_counts,
        "tasks": [task.__dict__ for task in tasks],
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Stage 1.3 Deliverable Validation",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "Rule: a deliverable is complete only when the exact work-plan task spec and produced artifact evidence agree. Uncertainty is escalated to Tier 4/Codex.",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    for status, count in sorted(status_counts.items(), key=lambda item: STATUS_ORDER.get(item[0], 99)):
        lines.append(f"| {status} | {count} |")

    lines.extend([
        "",
        "## Task Results",
        "",
        "| Task | Machine | Status | Confidence | Evidence | Next action |",
        "| --- | --- | --- | ---: | --- | --- |",
    ])
    for task in tasks:
        evidence = "<br>".join(task.evidence[:4])
        lines.append(
            f"| {task.task_id} {task.title} | {task.machine} | {task.status} | {task.confidence:.2f} | {evidence} | {task.next_action} |"
        )
    lines.extend(["", "## Escalations For Codex", ""])
    escalated = [task for task in tasks if task.escalation_question or task.status in {"needs_codex", "failed"}]
    if not escalated:
        lines.append("- None.")
    for task in escalated:
        lines.append(f"- {task.task_id} {task.title}: {task.escalation_question or task.next_action}")
    lines.extend(["", "## Context To Pass Forward", ""])
    lines.append("Any agent validating these outputs must read the task's work-plan section, inspect deliverable files and provenance, then report confidence. If confidence is below 0.8, escalate to Codex.")
    MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    log("START Stage 1.3 deliverable validator")
    tasks = validate_tasks()
    write_reports(tasks)
    write_escalation_queue(tasks)
    counts: dict[str, int] = {}
    for task in tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
    log(f"DONE Stage 1.3 deliverable validator status_counts={json.dumps(counts, sort_keys=True)}")


if __name__ == "__main__":
    main()
