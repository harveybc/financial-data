from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pywt
from scipy.signal import hilbert
from scipy.signal.windows import dpss

try:
    from PyEMD import EMD
except Exception:  # pragma: no cover - optional dependency
    EMD = None  # type: ignore[assignment]


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
TARGET_TIMEFRAMES = ("5m", "15m", "1h", "4h")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(machine: str, message: str) -> None:
    path = ROOT / "_logs" / machine / "stage23_signal_decomposition_worker.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def notify(event: str, title: str, message: str) -> None:
    script = ROOT / "_scripts" / "telegram_notify.py"
    if not script.exists():
        return
    import subprocess
    import sys

    try:
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--event",
                f"stage23:signal:{event}",
                "--title",
                title,
                "--message",
                message,
                "--min-interval-minutes",
                "20",
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
    except Exception:
        return


def read_asset(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns or "close" not in df.columns:
        raise ValueError("missing timestamp or close column")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["timestamp", "close"]).sort_values("timestamp")
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    return df[["timestamp", "close"]].reset_index(drop=True)


def sanitize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.replace([np.inf, -np.inf], np.nan)
    for col in out.columns:
        if col == "timestamp":
            continue
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("float32")
    return out


def validate_features(df: pd.DataFrame, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    values = df.drop(columns=["timestamp"], errors="ignore")
    all_nan_cols = [col for col in values.columns if values[col].isna().all()]
    validation = {
        "rows": int(len(df)),
        "columns": int(len(values.columns)),
        "all_nan_column_count": len(all_nan_cols),
        "all_nan_columns": all_nan_cols[:50],
    }
    if extra:
        validation.update(extra)
    return validation


def sample_step(tf: str) -> int:
    return {
        "5m": 512,
        "15m": 256,
        "1h": 96,
        "4h": 32,
    }.get(tf, 128)


def sampled_positions(n: int, window: int, step: int) -> range:
    if n <= window:
        return range(0, 0)
    return range(window, n, step)


def compute_wavelet(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    close = df["close"].astype(float)
    out = pd.DataFrame({"timestamp": df["timestamp"]})

    windows = {1: 16, 2: 32, 3: 64, 4: 128}
    approx: dict[int, pd.Series] = {}
    for level, window in windows.items():
        approx[level] = close.rolling(window, min_periods=window).mean()
        out[f"wavelet_approx_L{level}"] = approx[level]

    out["wavelet_detail_L1"] = close - approx[1]
    for level in (2, 3, 4):
        out[f"wavelet_detail_L{level}"] = approx[level - 1] - approx[level]

    energy_cols = []
    for level in (1, 2, 3, 4):
        col = f"wavelet_energy_L{level}"
        energy_cols.append(col)
        out[col] = out[f"wavelet_detail_L{level}"].pow(2).rolling(128, min_periods=32).mean()
    total_energy = sum(out[col] for col in energy_cols)
    for level, col in enumerate(energy_cols, start=1):
        out[f"wavelet_relative_energy_L{level}"] = out[col] / total_energy
    rel_energy = out[[f"wavelet_relative_energy_L{level}" for level in (1, 2, 3, 4)]].clip(lower=0)
    out["wavelet_entropy"] = -(rel_energy * np.log(rel_energy + 1e-12)).sum(axis=1)

    return sanitize(out), {
        "backend": "causal rolling multiresolution filters",
        "wavelet_reference": "db4-style decomposition approximated with past-only dyadic windows",
    }


def compute_hilbert_features(df: pd.DataFrame, tf: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    close = df["close"].astype(float).reset_index(drop=True)
    timestamps = df["timestamp"].reset_index(drop=True)
    detrended = close - close.rolling(50, min_periods=20).mean()
    n = len(close)
    window = min(256, max(96, n // 10)) if n < 1000 else 256
    step = max(8, sample_step(tf) // 4)
    out = pd.DataFrame(
        {
            "timestamp": timestamps,
            "ht_amplitude": np.nan,
            "ht_phase": np.nan,
            "ht_inst_freq": np.nan,
            "ht_phase_difference": np.nan,
        }
    )

    for end in sampled_positions(n, window, step):
        segment = detrended.iloc[end - window : end].interpolate(limit_direction="both").to_numpy(dtype=float)
        if np.isnan(segment).any():
            continue
        analytic = hilbert(segment)
        amplitude = np.abs(analytic)
        phase = np.unwrap(np.angle(analytic))
        idx = end - 1
        out.at[idx, "ht_amplitude"] = amplitude[-1]
        out.at[idx, "ht_phase"] = phase[-1]
        out.at[idx, "ht_inst_freq"] = phase[-1] - phase[-2] if len(phase) > 1 else np.nan
        out.at[idx, "ht_phase_difference"] = phase[-1] - phase[-2] if len(phase) > 1 else np.nan

    for col in ["ht_amplitude", "ht_phase", "ht_inst_freq", "ht_phase_difference"]:
        out[col] = out[col].ffill()
    out["ht_amplitude_zscore_100"] = (
        (out["ht_amplitude"] - out["ht_amplitude"].rolling(100).mean()) / out["ht_amplitude"].rolling(100).std()
    )
    return sanitize(out), {"backend": "causal rolling SciPy Hilbert", "window": window, "step": step}


def multitaper_psd(segment: np.ndarray, nw: float = 3.5, k: int = 5) -> tuple[np.ndarray, np.ndarray]:
    tapers = dpss(len(segment), NW=nw, Kmax=k, sym=False)
    tapered = tapers * (segment - np.nanmean(segment))
    fft_values = np.fft.rfft(tapered, axis=1)
    psd = np.mean(np.abs(fft_values) ** 2, axis=0)
    freqs = np.fft.rfftfreq(len(segment), d=1.0)
    return freqs, psd


def compute_multitaper(df: pd.DataFrame, tf: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    close = df["close"].astype(float).reset_index(drop=True)
    returns = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan)
    timestamps = df["timestamp"].reset_index(drop=True)
    n = len(close)
    window = min(256, max(96, n // 10)) if n < 1000 else 256
    step = sample_step(tf)
    targets = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
    out = pd.DataFrame({"timestamp": timestamps})
    for target in targets:
        out[f"mt_psd_{target:.2f}"] = np.nan
    out["mt_spec_entropy"] = np.nan
    out["mt_dominant_freq"] = np.nan
    out["mt_spectral_centroid"] = np.nan

    for end in sampled_positions(n, window, step):
        segment = returns.iloc[end - window : end].interpolate(limit_direction="both").to_numpy(dtype=float)
        if np.isnan(segment).any():
            continue
        freqs, psd = multitaper_psd(segment)
        if not np.isfinite(psd).any() or psd.sum() <= 0:
            continue
        idx = end - 1
        for target in targets:
            freq_idx = int(np.argmin(np.abs(freqs - target)))
            out.at[idx, f"mt_psd_{target:.2f}"] = psd[freq_idx]
        psd_norm = psd / psd.sum()
        out.at[idx, "mt_spec_entropy"] = float(-(psd_norm * np.log(psd_norm + 1e-12)).sum())
        out.at[idx, "mt_dominant_freq"] = float(freqs[int(np.argmax(psd))])
        out.at[idx, "mt_spectral_centroid"] = float((freqs * psd).sum() / psd.sum())

    for col in out.columns:
        if col != "timestamp":
            out[col] = out[col].ffill()
    return sanitize(out), {"backend": "scipy DPSS multitaper", "window": window, "step": step}


def fracdiff_weights(d: float, threshold: float = 1e-4, max_size: int = 256) -> np.ndarray:
    weights = [1.0]
    for k in range(1, max_size):
        weight = -weights[-1] * (d - k + 1) / k
        if abs(weight) < threshold:
            break
        weights.append(weight)
    return np.asarray(weights, dtype=float)


def compute_fracdiff(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    close = df["close"].astype(float).interpolate(limit_direction="both").to_numpy(dtype=float)
    out = pd.DataFrame({"timestamp": df["timestamp"]})
    sizes: dict[str, int] = {}
    for d in (0.4, 0.6, 0.8):
        weights = fracdiff_weights(d)
        sizes[f"fracdiff_d_{d:.1f}"] = int(len(weights))
        values = np.convolve(close, weights, mode="full")[: len(close)]
        values[: len(weights) - 1] = np.nan
        out[f"fracdiff_d_{d:.1f}"] = values
    return sanitize(out), {"backend": "fixed-width Lopez de Prado fractional differentiation", "weight_counts": sizes}


def compute_emd_proxy(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    close = df["close"].astype(float)
    ma8 = close.rolling(8, min_periods=8).mean()
    ma32 = close.rolling(32, min_periods=32).mean()
    ma128 = close.rolling(128, min_periods=128).mean()
    out = pd.DataFrame(
        {
            "timestamp": df["timestamp"],
            "emd_imf_1": close - ma8,
            "emd_imf_2": ma8 - ma32,
            "emd_imf_3": ma32 - ma128,
            "emd_residue": ma128,
        }
    )
    return sanitize(out), {"backend": "causal EMD proxy from nested rolling band-pass filters"}


def compute_true_emd_sampled(df: pd.DataFrame, tf: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if EMD is None:
        return compute_emd_proxy(df)
    close = df["close"].astype(float).reset_index(drop=True)
    timestamps = df["timestamp"].reset_index(drop=True)
    n = len(close)
    window = min(256, max(96, n // 10)) if n < 1000 else 256
    step = max(sample_step(tf), 128)
    out = pd.DataFrame(
        {
            "timestamp": timestamps,
            "emd_imf_1": np.nan,
            "emd_imf_2": np.nan,
            "emd_imf_3": np.nan,
            "emd_residue": np.nan,
        }
    )
    emd = EMD()
    for end in sampled_positions(n, window, step):
        segment = close.iloc[end - window : end].interpolate(limit_direction="both").to_numpy(dtype=float)
        if np.isnan(segment).any():
            continue
        imfs = emd.emd(segment, max_imf=3)
        idx = end - 1
        for imf_idx in range(min(3, len(imfs))):
            out.at[idx, f"emd_imf_{imf_idx + 1}"] = imfs[imf_idx, -1]
        residue = segment[-1] - imfs[:, -1].sum() if len(imfs) else np.nan
        out.at[idx, "emd_residue"] = residue
    for col in out.columns:
        if col != "timestamp":
            out[col] = out[col].ffill()
    return sanitize(out), {"backend": "sampled causal PyEMD", "window": window, "step": step}


def compute_emd(df: pd.DataFrame, tf: str, backend: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if backend == "proxy":
        return compute_emd_proxy(df)
    if backend == "true":
        return compute_true_emd_sampled(df, tf)
    if len(df) <= 80_000:
        return compute_true_emd_sampled(df, tf)
    return compute_emd_proxy(df)


def write_docs(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signal_decomposition_README.md").write_text(
        "\n".join(
            [
                "# Stage 2.3 Signal Decomposition Features",
                "",
                "Causal multi-resolution signal features derived from Stage 2.1 OHLCV close series.",
                "",
                "Files produced here: `wavelet.parquet`, `hilbert.parquet`, `multitaper.parquet`, `emd.parquet`, and `fracdiff.parquet`.",
                "",
                "Citations: Mallat, A Wavelet Tour of Signal Processing; Ehlers, Cybernetic Analysis for Stocks and Futures; Percival and Walden, Spectral Analysis for Physical Applications; Huang et al. 1998; Lopez de Prado, Advances in Financial Machine Learning.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def process_asset_tf(asset: str, tf: str, machine: str, emd_backend: str) -> dict[str, Any]:
    source = ROOT / "features" / "trading_asset_data" / asset / f"{tf}.parquet"
    if not source.exists():
        return {"asset": asset, "timeframe": tf, "status": "missing_source", "source": rel(source)}
    out_dir = ROOT / "features" / "trading_asset_features" / asset / tf
    write_docs(out_dir)
    try:
        df = read_asset(source)
        tasks = {
            "wavelet": compute_wavelet(df),
            "hilbert": compute_hilbert_features(df, tf),
            "multitaper": compute_multitaper(df, tf),
            "fracdiff": compute_fracdiff(df),
            "emd": compute_emd(df, tf, emd_backend),
        }
        validations: dict[str, Any] = {}
        paths: dict[str, str] = {}
        for name, (features, metadata) in tasks.items():
            path = out_dir / f"{name}.parquet"
            features.to_parquet(path, index=False)
            validations[name] = validate_features(features, metadata)
            paths[f"{name}_path"] = rel(path)
        result = {
            "asset": asset,
            "timeframe": tf,
            "status": "ok",
            "source": rel(source),
            **paths,
            "validations": validations,
        }
    except Exception as exc:
        result = {
            "asset": asset,
            "timeframe": tf,
            "status": "failed",
            "source": rel(source),
            "error": f"{type(exc).__name__}: {exc}",
        }
    log(machine, f"asset={asset} tf={tf} status={result['status']}")
    return result


def discover_assets(args_assets: list[str] | None) -> list[str]:
    if args_assets:
        return sorted(args_assets)
    root = ROOT / "features" / "trading_asset_data"
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def write_report(machine: str, universe: str, results: list[dict[str, Any]]) -> None:
    summary = {
        "generated_at": utc_now(),
        "stage": "Stage 2.3",
        "machine": machine,
        "universe": universe,
        "jobs_total": len(results),
        "jobs_ok": sum(item["status"] == "ok" for item in results),
        "jobs_failed": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
    out_json = ROOT / "_metadata" / f"stage23_signal_decomposition_{machine}_{universe}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    out_md = ROOT / "_logs" / "supervisor_reports" / f"stage23_signal_decomposition_{machine}_{universe}.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Stage 2.3 Signal Decomposition - {machine} {universe}",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        f"- Jobs total: {summary['jobs_total']}",
        f"- Jobs ok: {summary['jobs_ok']}",
        f"- Jobs failed: {summary['jobs_failed']}",
        "",
        "| Asset | TF | Status | Wavelet | Hilbert | Multitaper | EMD | Fracdiff |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in results:
        vals = item.get("validations", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    item["asset"],
                    item["timeframe"],
                    item["status"],
                    str(vals.get("wavelet", {}).get("columns", "")),
                    str(vals.get("hilbert", {}).get("columns", "")),
                    str(vals.get("multitaper", {}).get("columns", "")),
                    str(vals.get("emd", {}).get("columns", "")),
                    str(vals.get("fracdiff", {}).get("columns", "")),
                ]
            )
            + " |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--assets", nargs="*")
    parser.add_argument("--timeframes", nargs="*", default=list(TARGET_TIMEFRAMES))
    parser.add_argument("--emd-backend", choices=["auto", "proxy", "true"], default="auto")
    args = parser.parse_args()

    assets = discover_assets(args.assets)
    jobs = [(asset, tf) for asset in assets for tf in args.timeframes]
    log(args.machine, f"START stage23 signal universe={args.universe} jobs={len(jobs)} emd_backend={args.emd_backend}")
    notify(
        f"{args.machine}:{args.universe}:start",
        f"Project 3 Stage 2.3 {args.machine} started",
        f"machine: {args.machine}\nstage: Stage 2.3\ncurrent_task: signal decomposition features\njobs: {len(jobs)}",
    )
    results = [process_asset_tf(asset, tf, args.machine, args.emd_backend) for asset, tf in jobs]
    write_report(args.machine, args.universe, results)
    log(args.machine, f"DONE stage23 signal universe={args.universe} jobs={len(jobs)}")
    notify(
        f"{args.machine}:{args.universe}:finish",
        f"Project 3 Stage 2.3 {args.machine} finished",
        f"machine: {args.machine}\nstage: Stage 2.3\nstatus: finished\ndeliverable_path: _metadata/stage23_signal_decomposition_{args.machine}_{args.universe}.json\njobs: {len(jobs)}",
    )


if __name__ == "__main__":
    main()
