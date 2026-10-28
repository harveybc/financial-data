"""Shared fixture for the C94-C97 tests: a throwaway committed checkout
holding copies of the harness, producer and assembler, a synthetic raw
OHLCV input with the real input's physical schema, synthetic "old"
artifacts, and a committed config pinning their digests."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HARNESS = "_scripts/prospective_producer_rerun.py"
WORKER = "_scripts/workers/stage22_trading_features_worker.py"
ASSEMBLER = "_scripts/assemble_eth_h4_model_ready_successor.py"
CONFIG = "_scripts/prospective_rerun_configs/fixture.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def synthetic_raw(n: int = 700, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    open_ = close * np.exp(rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, 0.003, n)))
    vol = rng.lognormal(10, 0.5, n)
    ts = pd.date_range("2020-01-01", periods=n, freq="4h", tz="UTC",
                       unit="ms")
    return pd.DataFrame({
        "timestamp": ts, "open": open_, "high": high, "low": low,
        "close": close, "volume": vol,
        "close_time": ts + pd.Timedelta(hours=4) - pd.Timedelta(
            milliseconds=1),
        "quote_volume": vol * close,
        "trade_count": rng.integers(100, 1000, n).astype("int64"),
        "taker_buy_base_volume": vol * 0.5,
        "taker_buy_quote_volume": vol * close * 0.5})


def git(repo: Path, *args) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=fixture",
         "-c", "user.email=fixture@example.invalid", *args],
        check=True, capture_output=True, text=True).stdout.strip()


def build_world(tmp: Path, *, worker_patch=None, assembler_patch=None,
                config_patch=None, n: int = 700) -> dict:
    """Returns paths and the commit of a clean fixture checkout."""
    repo, data = tmp / "checkout", tmp / "data"
    for rel in (HARNESS, WORKER, ASSEMBLER):
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = (ROOT / rel).read_text(encoding="utf-8")
        if rel == WORKER and worker_patch:
            text = worker_patch(text)
        if rel == ASSEMBLER and assembler_patch:
            text = assembler_patch(text)
        dst.write_text(text, encoding="utf-8")
    raw_rel = "features/trading_asset_data/ethusdt/4h.parquet"
    raw_path = data / raw_rel
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw = synthetic_raw(n)
    raw.to_parquet(raw_path, index=False)
    # "old" artifacts: made with the REAL producer and assembler, then one
    # technical column is nudged so the comparison has something to report
    worker = load("_fixture_worker", ROOT / WORKER)
    asm = load("_fixture_asm", ROOT / ASSEMBLER)
    r = worker.read_asset(raw_path)
    tech, stat = worker.compute_technical(r), worker.compute_statistical(r)
    old_tech = tech.copy()
    old_tech["sma_10"] = (old_tech["sma_10"] + np.float32(1.0)).astype(
        "float32")
    old_dir = data / "old"
    old_dir.mkdir(parents=True, exist_ok=True)
    old_tech.to_parquet(old_dir / "technical.parquet", index=False)
    stat.to_parquet(old_dir / "statistical.parquet", index=False)
    asm.to_csv_frame(asm.assemble(r, tech, stat)).to_csv(
        old_dir / "model_ready.csv", index=False)
    import pyarrow.parquet as pq
    schema = {f.name: str(f.type) for f in pq.read_schema(raw_path)}
    cfg = json.loads((ROOT / "_scripts/prospective_rerun_configs/"
                      "eth_h4_stage22_rerun.v1.json").read_text())
    cfg.update({
        "run_id": "fixture_run",
        "inputs": {"raw_ohlcv": {"root_id": "financial-data",
                                 "path": raw_rel, "sha256": sha(raw_path),
                                 "established_by": ["FIXTURE"]}},
        "comparisons": {
            "technical": {"root_id": "financial-data",
                          "path": "old/technical.parquet",
                          "sha256": sha(old_dir / "technical.parquet"),
                          "kind": "parquet_table", "key": "timestamp",
                          "successor_output": "technical"},
            "statistical": {"root_id": "financial-data",
                            "path": "old/statistical.parquet",
                            "sha256": sha(old_dir / "statistical.parquet"),
                            "kind": "parquet_table", "key": "timestamp",
                            "successor_output": "statistical"},
            "historical_model_ready_csv": {
                "root_id": "financial-data", "path": "old/model_ready.csv",
                "sha256": sha(old_dir / "model_ready.csv"),
                "kind": "csv_table", "key": "DATE_TIME"}},
        "expected_raw_schema": schema,
        "e2e_probe": {"cut_fractions": [0.5, 0.9],
                      "modes": ["truncate", "scale_noise", "nan_inject",
                                "zeros_and_spikes"], "seed": 5},
        "budget": {"wall_seconds": 300}})
    if config_patch:
        config_patch(cfg)
    (repo / CONFIG).parent.mkdir(parents=True, exist_ok=True)
    (repo / CONFIG).write_text(json.dumps(cfg, indent=1, sort_keys=True))
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "fixture")
    return {"repo": repo, "data": data, "commit": git(repo, "rev-parse",
                                                      "HEAD"),
            "out": tmp / "successors" / "fixture_run", "raw": raw,
            "raw_path": raw_path, "old_dir": old_dir}


def harness_of(world: dict, name: str = "_fixture_harness"):
    return load(name, world["repo"] / HARNESS)


def run_world(world: dict, harness=None, **kw):
    h = harness or harness_of(world)
    args = dict(config=CONFIG, out_root=world["out"],
                expect_commit=world["commit"],
                data_roots={"financial-data": world["data"]},
                sealed_at="2026-09-12T00:00:00Z")
    args.update(kw)
    return h.run(**args)


def snapshot(*roots: Path, exclude: Path | None = None) -> dict:
    out = {}
    for root in roots:
        for p in sorted(Path(root).rglob("*")):
            if exclude is not None and (p == exclude or
                                        exclude in p.parents):
                continue
            if ".git" in p.parts:
                continue
            st = p.lstat()
            out[str(p)] = (st.st_mtime_ns, st.st_size,
                           sha(p) if p.is_file() else None)
    return out


def rmtree(p: Path) -> None:
    def onerror(func, path, exc):
        import os
        os.chmod(Path(path).parent, 0o755)
        os.chmod(path, 0o755)
        func(path)
    shutil.rmtree(p, onerror=onerror)
