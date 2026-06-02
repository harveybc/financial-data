#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))


@dataclass(frozen=True)
class MachinePlan:
    assets: tuple[str, ...]
    timeframes: tuple[str, ...]
    presets: tuple[str, ...]
    algos: tuple[str, ...]
    seeds: tuple[int, ...]
    timesteps: int
    device: str
    max_new_per_tick: int


MACHINE_PLANS = {
    "dragon": MachinePlan(
        assets=(
            "btcusdt",
            "ethusdt",
            "btcusdt_perp",
            "ethusdt_perp",
            "solusdt",
            "bnbusdt",
            "xrpusdt",
            "adausdt",
            "dogeusdt",
            "linkusdt",
        ),
        timeframes=("15m", "1h", "4h"),
        presets=(
            "baseline_12",
            "tech_full",
            "tech_stat",
            "tech_stat_decomp",
            "learned_lstm",
            "learned_cnn",
            "sota_low_cost",
            "crypto_full",
            "kitchen_sink_guarded",
        ),
        algos=("sac", "ppo", "dqn"),
        seeds=(0, 1),
        timesteps=50_000,
        device="cuda",
        max_new_per_tick=48,
    ),
    "gamma": MachinePlan(
        assets=(
            "eurusd",
            "usdjpy",
            "audusd",
            "gbpusd",
            "usdcad",
            "usdchf",
            "nzdusd",
            "eurgbp",
            "eurjpy",
            "gbpjpy",
            "btcusdt",
            "ethusdt",
            "btcusdt_perp",
            "ethusdt_perp",
            "solusdt",
            "bnbusdt",
            "xrpusdt",
            "adausdt",
            "dogeusdt",
            "linkusdt",
        ),
        timeframes=("15m", "1h", "4h"),
        presets=(
            "baseline_12",
            "tech_full",
            "tech_stat",
            "tech_stat_decomp",
            "learned_lstm",
            "learned_cnn",
            "fx_full",
            "crypto_full",
            "sota_low_cost",
            "kitchen_sink_guarded",
        ),
        algos=("sac", "ppo", "dqn"),
        seeds=(0, 1, 2),
        timesteps=50_000,
        device="cuda",
        max_new_per_tick=48,
    ),
    "omega": MachinePlan(
        assets=(
            "eurusd",
            "usdjpy",
            "audusd",
            "gbpusd",
            "usdcad",
            "usdchf",
            "nzdusd",
            "eurgbp",
        ),
        timeframes=("1h", "4h"),
        presets=("baseline_12", "tech_full", "tech_stat", "tech_stat_decomp"),
        algos=("dqn", "ppo"),
        seeds=(0,),
        timesteps=12_500,
        device="cpu",
        max_new_per_tick=24,
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def is_runnable_status(status: object) -> bool:
    value = str(status or "pending").lower()
    if value in {"", "pending", "queued", "retry", "needs_retry"}:
        return True
    if value in {"complete", "training", "running", "preparing_input", "skipped_busy"}:
        return False
    if value.startswith("blocked") or value.startswith("failed") or value.startswith("skipped"):
        return False
    return True


def asset_available(asset: str, timeframe: str) -> bool:
    return (ROOT / "features" / "trading_asset_data" / asset / f"{timeframe}.parquet").exists()


def is_fx_asset(asset: str) -> bool:
    return asset in {
        "eurusd",
        "usdjpy",
        "audusd",
        "gbpusd",
        "usdcad",
        "usdchf",
        "nzdusd",
        "eurgbp",
        "eurjpy",
        "gbpjpy",
    }


def is_crypto_asset(asset: str) -> bool:
    return asset.endswith("usdt") or asset.endswith("_perp")


def preset_compatible(asset: str, preset: str) -> bool:
    if preset == "fx_full":
        return is_fx_asset(asset)
    if preset in {"crypto_full", "sota_low_cost"}:
        return is_crypto_asset(asset)
    return True


def run_id(asset: str, timeframe: str, preset: str, algo: str, seed: int, timesteps: int) -> str:
    return f"{asset}_{timeframe}_{preset}_{algo}_s{seed}_{timesteps}"


def all_known_run_ids() -> set[str]:
    queues_dir = ROOT / "experiments" / "stage_a_screening" / "queues"
    known: set[str] = set()
    for path in queues_dir.glob("*.json"):
        if path.name.endswith(".remote.json"):
            continue
        queue = read_json(path, [])
        if not isinstance(queue, list):
            continue
        known.update(str(job.get("run_id")) for job in queue if job.get("run_id"))
    return known


def candidate_jobs(machine: str, plan: MachinePlan) -> list[dict]:
    jobs = []
    for asset in plan.assets:
        for timeframe in plan.timeframes:
            if not asset_available(asset, timeframe):
                continue
            for preset in plan.presets:
                if not preset_compatible(asset, preset):
                    continue
                for algo in plan.algos:
                    for seed in plan.seeds:
                        jobs.append(
                            {
                                "algo": algo,
                                "asset": asset,
                                "device": plan.device,
                                "preset": preset,
                                "run_id": run_id(asset, timeframe, preset, algo, seed, plan.timesteps),
                                "seed": seed,
                                "stage": f"3.1_stage_a_broad_matrix_{machine}",
                                "status": "pending",
                                "timeframe": timeframe,
                                "timesteps": plan.timesteps,
                            }
                        )
    return jobs


def expand_machine(machine: str, target_pending: int) -> dict:
    plan = MACHINE_PLANS[machine]
    queue_path = ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"
    queue = read_json(queue_path, [])
    existing = all_known_run_ids()
    pending = sum(1 for job in queue if is_runnable_status(job.get("status", "pending")))
    appended = []
    if pending < target_pending:
        for job in candidate_jobs(machine, plan):
            if job["run_id"] in existing:
                continue
            queue.append(job)
            existing.add(job["run_id"])
            appended.append(job["run_id"])
            pending += 1
            if pending >= target_pending or len(appended) >= plan.max_new_per_tick:
                break
    write_json(queue_path, queue)
    return {
        "machine": machine,
        "target_pending": target_pending,
        "pending_after": pending,
        "appended": len(appended),
        "appended_run_ids": appended,
        "queue": str(queue_path),
    }


def write_report(results: list[dict]) -> None:
    payload = {"generated_at": utc_now(), "stage": "3.1", "results": results}
    write_json(ROOT / "_metadata" / "stage31_queue_expansion.json", payload)
    lines = [
        "# Stage 3.1 Queue Expansion",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "| Machine | Target pending | Pending after | Appended |",
        "| --- | ---: | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            f"| {result['machine']} | {result['target_pending']} | {result['pending_after']} | {result['appended']} |"
        )
    lines += ["", "## Appended Jobs", ""]
    for result in results:
        lines.append(f"### {result['machine']}")
        if result["appended_run_ids"]:
            lines.extend(f"- `{run_id}`" for run_id in result["appended_run_ids"])
        else:
            lines.append("- No new jobs needed.")
        lines.append("")
    out = ROOT / "_logs" / "supervisor_reports" / "stage31_queue_expansion.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refill Project 3 Stage 3.1 queues from the broad experiment matrix.")
    parser.add_argument("--machine", action="append", choices=sorted(MACHINE_PLANS), default=[])
    parser.add_argument("--target-pending", type=int, default=24)
    args = parser.parse_args()
    machines = args.machine or sorted(MACHINE_PLANS)
    results = [expand_machine(machine, args.target_pending) for machine in machines]
    write_report(results)
    print(json.dumps({"ok": True, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
