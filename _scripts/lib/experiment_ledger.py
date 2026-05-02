from __future__ import annotations

import fcntl
import hashlib
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts"
EVENT_ROOT = ARTIFACT_ROOT / "run_ledger_events"
COMBINED_JSONL = ARTIFACT_ROOT / "run_ledger.jsonl"
COMBINED_PARQUET = ARTIFACT_ROOT / "run_ledger.parquet"

PRESET_FAMILIES = {
    "baseline_12": ("base", "trading_ohlcv"),
    "tech_full": ("technical", "trading_ohlcv"),
    "tech_stat": ("technical_statistical", "trading_ohlcv"),
    "tech_stat_decomp": ("decomposition", "trading_ohlcv"),
    "learned_lstm": ("learned_embeddings", "trading_ohlcv"),
    "learned_cnn": ("learned_embeddings", "trading_ohlcv"),
    "learned_transformer": ("learned_embeddings", "trading_ohlcv"),
    "learned_cvae": ("learned_embeddings", "trading_ohlcv"),
    "crypto_full": ("crypto_structure", "free_crypto_stack"),
    "fx_full": ("fx_structure", "free_fx_macro_stack"),
    "sota_low_cost": ("sota_low_cost", "free_sota_stack"),
    "kitchen_sink_guarded": ("kitchen_sink_guarded", "all_validated_sources"),
}

REWARD_KEYS = [
    "reward_plugin",
    "strategy_plugin",
    "atr_period",
    "k_sl",
    "k_tp",
    "initial_cash",
]

ACTION_KEYS = [
    "action_space_mode",
    "continuous_action_threshold",
    "position_size",
    "rel_volume",
    "leverage",
    "size_mode",
    "min_order_volume",
    "max_order_volume",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(payload: Any, length: int = 16) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:length]


def git_sha(path: Path) -> str:
    try:
        import subprocess

        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    except Exception:
        return "unknown"


def infer_venue(asset: str) -> str:
    value = asset.lower()
    if value.endswith("_perp") or value.endswith("perp"):
        return "binance_usdm_perpetual"
    if value.endswith("usdt"):
        return "binance_spot"
    if len(value) == 6 and value.isalpha():
        return "histdata_fx"
    return "unknown"


def infer_cost_scenario(asset: str) -> str:
    value = asset.lower()
    if value.endswith("_perp") or value.endswith("perp"):
        return "base_crypto_perpetual"
    if value.endswith("usdt"):
        return "base_crypto_spot"
    if len(value) == 6 and value.isalpha():
        return "base_fx"
    return "base_unknown"


def config_hash(config: dict[str, Any] | None, keys: list[str]) -> str:
    if not config:
        return "pending_config"
    return stable_hash({key: config.get(key) for key in keys})


def trial_fields(machine: str, job: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    preset = str(job.get("preset") or job.get("feature_preset") or "unknown")
    feature_family, source_family = PRESET_FAMILIES.get(preset, (preset, "unknown"))
    asset = str(job.get("asset") or "unknown").lower()
    fields = {
        "stage": str(job.get("stage") or "3.1_stage_a"),
        "machine": machine,
        "algorithm": str(job.get("algo") or job.get("algorithm") or "unknown").lower(),
        "asset": asset,
        "venue": str(job.get("venue") or infer_venue(asset)),
        "timeframe": str(job.get("timeframe") or "unknown"),
        "feature_preset": preset,
        "feature_family": str(job.get("feature_family") or feature_family),
        "source_family": str(job.get("source_family") or source_family),
        "seed": int(job.get("seed") or 0),
        "split_version": str(job.get("split_version") or "train_pre_2025_holdout_v1"),
        "data_version": str(job.get("data_version") or git_sha(PROJECT_ROOT)),
        "reward_config_hash": str(job.get("reward_config_hash") or config_hash(config, REWARD_KEYS)),
        "action_space_hash": str(job.get("action_space_hash") or config_hash(config, ACTION_KEYS)),
        "cost_scenario": str(job.get("cost_scenario") or infer_cost_scenario(asset)),
        "timesteps": int(job.get("timesteps") or config.get("total_timesteps") if config else job.get("timesteps") or 0),
        "device": str(job.get("device") or (config or {}).get("device") or "unknown"),
    }
    return fields


def trial_id(machine: str, job: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    fields = trial_fields(machine, job, config)
    stable = {
        key: fields[key]
        for key in [
            "algorithm",
            "asset",
            "venue",
            "timeframe",
            "feature_preset",
            "feature_family",
            "source_family",
            "seed",
            "split_version",
            "data_version",
            "reward_config_hash",
            "action_space_hash",
            "cost_scenario",
        ]
    }
    return stable_hash(stable, length=24)


def make_event(
    machine: str,
    job: dict[str, Any],
    event_type: str,
    status: str,
    config: dict[str, Any] | None = None,
    detail: str = "",
    failure_reason: str | None = None,
) -> dict[str, Any]:
    fields = trial_fields(machine, job, config)
    tid = str(job.get("trial_id") or trial_id(machine, job, config))
    event_ts = utc_now()
    record = {
        **fields,
        "trial_id": tid,
        "event_id": stable_hash(
            {
                "trial_id": tid,
                "event_type": event_type,
                "event_ts": event_ts,
                "machine": machine,
                "status": status,
            },
            length=24,
        ),
        "event_type": event_type,
        "status": status,
        "event_ts": event_ts,
        "worker": f"{machine}:{socket.gethostname()}:{os.getpid()}",
        "start_ts": job.get("started_at") or job.get("start_ts"),
        "end_ts": job.get("end_ts"),
        "failure_reason": failure_reason,
        "detail": detail,
        "run_id": job.get("run_id"),
        "run_dir": job.get("run_dir") or job.get("output_dir"),
        "config_path": job.get("config"),
        "input_csv": job.get("input_csv"),
        "exit_code": job.get("exit_code"),
        "financial_data_git_sha": git_sha(PROJECT_ROOT),
    }
    return record


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    try:
        import pandas as pd

        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(path, index=False)
    except Exception:
        # JSONL is the authoritative append-only ledger. Parquet is a convenience export.
        return


def append_event(record: dict[str, Any], machine: str) -> None:
    EVENT_ROOT.mkdir(parents=True, exist_ok=True)
    jsonl_path = EVENT_ROOT / f"{machine}.jsonl"
    lock_path = EVENT_ROOT / f"{machine}.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        with jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(stable_json(record) + "\n")
        rows = _read_jsonl(jsonl_path)
        _write_parquet(EVENT_ROOT / f"{machine}.parquet", rows)


def record_stage31_event(
    machine: str,
    job: dict[str, Any],
    event_type: str,
    status: str,
    config: dict[str, Any] | None = None,
    detail: str = "",
    failure_reason: str | None = None,
) -> str:
    record = make_event(
        machine=machine,
        job=job,
        event_type=event_type,
        status=status,
        config=config,
        detail=detail,
        failure_reason=failure_reason,
    )
    append_event(record, machine)
    return record["trial_id"]


def combine_ledgers() -> dict[str, Any]:
    EVENT_ROOT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for path in sorted(EVENT_ROOT.glob("*.jsonl")):
        rows.extend(_read_jsonl(path))
    rows.sort(key=lambda row: (str(row.get("event_ts", "")), str(row.get("machine", "")), str(row.get("event_id", ""))))
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    COMBINED_JSONL.write_text("".join(stable_json(row) + "\n" for row in rows), encoding="utf-8")
    _write_parquet(COMBINED_PARQUET, rows)
    summary = {
        "generated_at": utc_now(),
        "event_count": len(rows),
        "trial_count": len({row.get("trial_id") for row in rows if row.get("trial_id")}),
        "machines": sorted({str(row.get("machine")) for row in rows if row.get("machine")}),
        "jsonl": str(COMBINED_JSONL),
        "parquet": str(COMBINED_PARQUET),
    }
    (ARTIFACT_ROOT / "run_ledger_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
