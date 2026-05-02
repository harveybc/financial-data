from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
TARGET_ASSETS = ("btcusdt", "ethusdt", "btcusdt_perp", "eurusd", "usdjpy")
TARGET_TIMEFRAMES = ("1h", "4h")
PAIR_GROUPS = (
    ("btcusdt", "ethusdt"),
    ("btcusdt", "btcusdt_perp"),
    ("eurusd", "usdjpy"),
)
FUNDING_SYMBOLS = {
    "btcusdt": "btcusdt",
    "btcusdt_perp": "btcusdt",
    "ethusdt": "ethusdt",
    "ethusdt_perp": "ethusdt",
}
RESAMPLE_RULES = {"1h": "1h", "4h": "4h"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def clean_name(value: str) -> str:
    return value.lower().replace("/", "_").replace("-", "_")


def read_asset(asset: str, timeframe: str) -> pd.DataFrame:
    path = ROOT / "features" / "trading_asset_data" / asset / f"{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(rel(path))
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"{rel(path)} missing timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp")
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "close" not in df.columns:
        raise ValueError(f"{rel(path)} missing close")
    return df


def output_dir(asset: str, timeframe: str) -> Path:
    path = ROOT / "features" / "trading_asset_features" / asset / timeframe
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_parquet(df: pd.DataFrame, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.replace([np.inf, -np.inf], np.nan)
    out.to_parquet(path, index=False)
    return {
        "path": rel(path),
        "rows": int(len(out)),
        "columns": int(len(out.columns)),
        "start": str(out["timestamp"].min()) if "timestamp" in out.columns and len(out) else None,
        "end": str(out["timestamp"].max()) if "timestamp" in out.columns and len(out) else None,
    }


def realized_moments(asset: str, timeframe: str) -> dict[str, Any]:
    if timeframe not in RESAMPLE_RULES:
        raise ValueError(f"unsupported timeframe {timeframe}")
    low = read_asset(asset, "5m")
    if len(low) < 100:
        raise ValueError("insufficient 5m rows")
    low = low.set_index("timestamp")
    close = low["close"].replace(0, np.nan).astype(float)
    low["log_return_5m"] = np.log(close).diff()
    rule = RESAMPLE_RULES[timeframe]
    grouped = low.resample(rule, label="left", closed="left")
    records = grouped["log_return_5m"].agg(
        intrabar_count="count",
        sota_realized_var=lambda x: float(np.nansum(np.square(x))),
        sota_intrabar_mean="mean",
        sota_intrabar_std="std",
        sota_intrabar_skew=lambda x: float(pd.Series(x).skew(skipna=True)),
        sota_intrabar_kurt=lambda x: float(pd.Series(x).kurt(skipna=True)),
        sota_intrabar_min="min",
        sota_intrabar_max="max",
    )
    abs_ret = low["log_return_5m"].abs()
    records["sota_bipower_var"] = grouped["log_return_5m"].apply(
        lambda x: float((np.pi / 2.0) * np.nansum(np.abs(x).shift(1) * np.abs(x)))
    )
    records["sota_tripower_quarticity"] = abs_ret.resample(rule, label="left", closed="left").apply(
        lambda x: float(np.nansum((pd.Series(x).shift(2) * pd.Series(x).shift(1) * pd.Series(x)) ** (4.0 / 3.0)))
    )
    if "volume" in low.columns:
        records["sota_intrabar_volume_sum"] = grouped["volume"].sum(min_count=1)
    records["sota_realized_vol"] = np.sqrt(records["sota_realized_var"].clip(lower=0))
    records["sota_jump_var_bpv"] = (records["sota_realized_var"] - records["sota_bipower_var"]).clip(lower=0)
    records = records.reset_index().rename(columns={"timestamp": "timestamp"})
    records = records.loc[records["intrabar_count"] >= (8 if timeframe == "1h" else 24)].reset_index(drop=True)
    return write_parquet(records, output_dir(asset, timeframe) / "sota_intrabar_realized.parquet")


def regime_labels(asset: str, timeframe: str) -> dict[str, Any]:
    from hmmlearn.hmm import GaussianHMM

    df = read_asset(asset, timeframe)
    close = df["close"].replace(0, np.nan).astype(float)
    ret = np.log(close).diff()
    vol_window = 48 if timeframe == "1h" else 30
    xdf = pd.DataFrame(
        {
            "timestamp": df["timestamp"],
            "ret": ret,
            "abs_ret": ret.abs(),
            "rolling_vol": ret.rolling(vol_window, min_periods=max(10, vol_window // 3)).std(),
        }
    ).dropna()
    if len(xdf) < 1000:
        raise ValueError(f"insufficient rows for HMM: {len(xdf)}")
    values = xdf[["ret", "abs_ret", "rolling_vol"]].to_numpy(dtype=float)
    sample_step = max(1, len(values) // 50000)
    train_values = values[::sample_step]
    means = train_values.mean(axis=0)
    stds = train_values.std(axis=0)
    stds[stds == 0] = 1.0
    train_scaled = (train_values - means) / stds
    full_scaled = (values - means) / stds
    model = GaussianHMM(n_components=3, covariance_type="diag", n_iter=100, random_state=7)
    model.fit(train_scaled)
    states = model.predict(full_scaled)
    probs = model.predict_proba(full_scaled)
    state_vol = {state: float(xdf.loc[states == state, "rolling_vol"].mean()) for state in range(model.n_components)}
    order = {state: rank for rank, state in enumerate(sorted(state_vol, key=state_vol.get))}
    out = pd.DataFrame({"timestamp": xdf["timestamp"].to_numpy(), "sota_hmm_state": states})
    out["sota_hmm_vol_regime"] = out["sota_hmm_state"].map(order).astype("int16")
    for state in range(model.n_components):
        out[f"sota_hmm_prob_state_{state}"] = probs[:, state]
    return write_parquet(out, output_dir(asset, timeframe) / "sota_hmm_regime.parquet")


def pair_spreads(pair: tuple[str, str], timeframe: str, sink: dict[tuple[str, str], list[pd.DataFrame]]) -> dict[str, Any]:
    a, b = pair
    left = read_asset(a, timeframe)[["timestamp", "close"]].rename(columns={"close": f"{a}_close"})
    right = read_asset(b, timeframe)[["timestamp", "close"]].rename(columns={"close": f"{b}_close"})
    merged = left.merge(right, on="timestamp", how="inner").dropna()
    if len(merged) < 1000:
        raise ValueError(f"insufficient overlap for {a}/{b} {timeframe}: {len(merged)}")
    y = np.log(merged[f"{a}_close"].replace(0, np.nan).astype(float))
    x = np.log(merged[f"{b}_close"].replace(0, np.nan).astype(float))
    valid = y.notna() & x.notna()
    merged = merged.loc[valid].copy()
    y = y.loc[valid]
    x = x.loc[valid]
    train = merged["timestamp"] < pd.Timestamp("2024-01-01", tz="UTC")
    if train.sum() < 500:
        train = pd.Series(True, index=merged.index)
    x_train = x.loc[train]
    y_train = y.loc[train]
    beta = float(np.cov(x_train, y_train)[0, 1] / np.var(x_train)) if np.var(x_train) > 0 else 1.0
    alpha = float(y_train.mean() - beta * x_train.mean())
    spread = y - alpha - beta * x
    window = 120 if timeframe == "1h" else 90
    name = f"{clean_name(a)}_{clean_name(b)}"
    out = pd.DataFrame(
        {
            "timestamp": merged["timestamp"].to_numpy(),
            f"sota_pair_{name}_spread": spread.to_numpy(),
            f"sota_pair_{name}_zscore": ((spread - spread.rolling(window, min_periods=20).mean()) / spread.rolling(window, min_periods=20).std()).to_numpy(),
            f"sota_pair_{name}_corr": y.rolling(window, min_periods=20).corr(x).to_numpy(),
            f"sota_pair_{name}_hedge_beta": beta,
        }
    )
    for asset in pair:
        sink.setdefault((asset, timeframe), []).append(out)
    return {
        "pair": list(pair),
        "timeframe": timeframe,
        "rows": int(len(out)),
        "hedge_beta": beta,
        "start": str(out["timestamp"].min()),
        "end": str(out["timestamp"].max()),
    }


def write_pair_outputs(sink: dict[tuple[str, str], list[pd.DataFrame]]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for (asset, timeframe), frames in sorted(sink.items()):
        merged = frames[0]
        for frame in frames[1:]:
            merged = merged.merge(frame, on="timestamp", how="outer")
        merged = merged.sort_values("timestamp").reset_index(drop=True)
        outputs.append(write_parquet(merged, output_dir(asset, timeframe) / "sota_pair_spreads.parquet"))
    return outputs


def funding_term_structure(asset: str, timeframe: str) -> dict[str, Any]:
    symbol = FUNDING_SYMBOLS.get(asset)
    if not symbol:
        raise ValueError(f"no funding symbol mapped for {asset}")
    fpath = ROOT / "market_data" / "crypto" / "funding_rates" / symbol / "funding_rates.parquet"
    if not fpath.exists():
        raise FileNotFoundError(rel(fpath))
    base = read_asset(asset, timeframe)[["timestamp"]]
    funding = pd.read_parquet(fpath)
    if "fundingTime" not in funding.columns or "fundingRate" not in funding.columns:
        raise ValueError(f"{rel(fpath)} missing fundingTime/fundingRate")
    funding = funding.rename(columns={"fundingTime": "timestamp", "fundingRate": "funding_rate"})
    funding["timestamp"] = pd.to_datetime(funding["timestamp"], utc=True, errors="coerce")
    funding["funding_rate"] = pd.to_numeric(funding["funding_rate"], errors="coerce")
    funding = funding.dropna(subset=["timestamp", "funding_rate"]).sort_values("timestamp")
    funding["sota_funding_rate"] = funding["funding_rate"]
    funding["sota_funding_3_event_mean"] = funding["funding_rate"].rolling(3, min_periods=1).mean()
    funding["sota_funding_9_event_mean"] = funding["funding_rate"].rolling(9, min_periods=1).mean()
    funding["sota_funding_30_event_mean"] = funding["funding_rate"].rolling(30, min_periods=1).mean()
    funding["sota_funding_30_event_std"] = funding["funding_rate"].rolling(30, min_periods=2).std()
    funding["sota_funding_term_slope_3_30"] = funding["sota_funding_3_event_mean"] - funding["sota_funding_30_event_mean"]
    funding["sota_funding_annualized"] = funding["funding_rate"] * 3 * 365
    keep = [
        "timestamp",
        "sota_funding_rate",
        "sota_funding_3_event_mean",
        "sota_funding_9_event_mean",
        "sota_funding_30_event_mean",
        "sota_funding_30_event_std",
        "sota_funding_term_slope_3_30",
        "sota_funding_annualized",
    ]
    aligned = pd.merge_asof(base.sort_values("timestamp"), funding[keep], on="timestamp", direction="backward")
    return write_parquet(aligned, output_dir(asset, timeframe) / "sota_funding_term_structure.parquet")


def run(args: argparse.Namespace) -> dict[str, Any]:
    results: dict[str, Any] = {
        "generated_at": utc_now(),
        "stage": "Stage 2 SOTA feature enrichment",
        "machine": args.machine,
        "assets": list(args.assets),
        "timeframes": list(args.timeframes),
        "outputs": [],
        "errors": [],
        "decisions": {
            "applied_now": [
                "jump-robust intrabar realized moments using existing 5m bars",
                "HMM market-regime labels using existing OHLC closes",
                "cointegration-style pair spread and z-score features",
                "crypto funding-rate term-structure features from existing Binance funding data",
            ],
            "deferred": [
                "VRP and DVOL until options/implied-volatility feeds are acquired",
                "FX carry until a full currency policy-rate mapping is validated",
                "PCMCI+ causal selection until Phase 3 experiment framework can validate feature selection leakage",
                "Decision Transformer, DreamerV3, hierarchical RL, and CQL/IQL until Phase 3 baselines are reproducible",
            ],
        },
    }

    for asset in args.assets:
        for timeframe in args.timeframes:
            for label, func in (("intrabar_realized", realized_moments), ("hmm_regime", regime_labels)):
                try:
                    item = func(asset, timeframe)
                    item.update({"asset": asset, "timeframe": timeframe, "feature_set": label, "status": "ok"})
                    results["outputs"].append(item)
                except Exception as exc:
                    results["errors"].append(
                        {
                            "asset": asset,
                            "timeframe": timeframe,
                            "feature_set": label,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
            if asset in FUNDING_SYMBOLS:
                try:
                    item = funding_term_structure(asset, timeframe)
                    item.update({"asset": asset, "timeframe": timeframe, "feature_set": "funding_term_structure", "status": "ok"})
                    results["outputs"].append(item)
                except Exception as exc:
                    results["errors"].append(
                        {
                            "asset": asset,
                            "timeframe": timeframe,
                            "feature_set": "funding_term_structure",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )

    pair_sink: dict[tuple[str, str], list[pd.DataFrame]] = {}
    for timeframe in args.timeframes:
        for pair in PAIR_GROUPS:
            if pair[0] in args.assets and pair[1] in args.assets:
                try:
                    results["outputs"].append({**pair_spreads(pair, timeframe, pair_sink), "feature_set": "pair_spread", "status": "ok"})
                except Exception as exc:
                    results["errors"].append(
                        {
                            "pair": list(pair),
                            "timeframe": timeframe,
                            "feature_set": "pair_spread",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
    for item in write_pair_outputs(pair_sink):
        item.update({"feature_set": "pair_spread_output", "status": "ok"})
        results["outputs"].append(item)

    results["jobs_ok"] = sum(1 for item in results["outputs"] if item.get("status") == "ok")
    results["jobs_failed"] = len(results["errors"])
    return results


def write_reports(summary: dict[str, Any]) -> None:
    metadata_path = ROOT / "_metadata" / "stage25_sota_feature_enrichment_omega.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    report_path = ROOT / "_logs" / "supervisor_reports" / "stage25_sota_feature_enrichment_omega.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage 2 SOTA Feature Enrichment - Omega",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        f"- Jobs ok: {summary['jobs_ok']}",
        f"- Jobs failed: {summary['jobs_failed']}",
        "",
        "## Applied Now",
        "",
        *[f"- {item}" for item in summary["decisions"]["applied_now"]],
        "",
        "## Deferred",
        "",
        *[f"- {item}" for item in summary["decisions"]["deferred"]],
        "",
        "## Outputs",
        "",
        "| Feature Set | Asset/Pair | TF | Rows | Columns | Path |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in summary["outputs"]:
        asset = item.get("asset") or "/".join(item.get("pair", [])) or ""
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("feature_set", "")),
                    str(asset),
                    str(item.get("timeframe", "")),
                    str(item.get("rows", "")),
                    str(item.get("columns", "")),
                    f"`{item.get('path', '')}`" if item.get("path") else "",
                ]
            )
            + " |"
        )
    if summary["errors"]:
        lines.extend(["", "## Errors", ""])
        for item in summary["errors"]:
            subject = item.get("asset") or "/".join(item.get("pair", []))
            lines.append(f"- {item['feature_set']} {subject} {item.get('timeframe', '')}: {item['error']}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    decision_path = ROOT / "work_plan" / "SOTA_INTEGRATION_DECISIONS.md"
    decision_lines = [
        "# SOTA Integration Decisions",
        "",
        f"Updated: {summary['generated_at']}",
        "",
        "## Immediate Additions",
        "",
        *[f"- {item}" for item in summary["decisions"]["applied_now"]],
        "",
        "These additions are CPU-safe, use already acquired data, and produce auditable parquet deliverables under `features/trading_asset_features/<asset>/<tf>/`.",
        "",
        "## Deferred Items",
        "",
        *[f"- {item}" for item in summary["decisions"]["deferred"]],
        "",
        "## Validation Rule",
        "",
        "Every new SOTA feature family must provide a metadata/report artifact and must be validated against the relevant work-plan deliverable before Phase 3 experiments consume it.",
    ]
    decision_path.write_text("\n".join(decision_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", default="omega")
    parser.add_argument("--assets", nargs="+", default=list(TARGET_ASSETS))
    parser.add_argument("--timeframes", nargs="+", default=list(TARGET_TIMEFRAMES))
    args = parser.parse_args()
    summary = run(args)
    write_reports(summary)
    print(json.dumps({"jobs_ok": summary["jobs_ok"], "jobs_failed": summary["jobs_failed"]}, indent=2))


if __name__ == "__main__":
    main()
