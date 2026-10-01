"""Native wavelet SUCCESSOR producer: PyWavelets db4 on past-only trailing windows (lane B, addendum 256c61a6).

Written red first. It mirrors the required specs frozen by lane C in tests/test_method_semantics_stage23.py
(satoshi/c-method-semantics-20261001 @ 99766205): NATIVE method id, past-only, frozen declared window,
prefix and restart/chunked-replay invariance, declared units, cadence and feature age. The Stage 2.3 worker
and its proxy are NOT edited; this is a separate successor module. Synthetic data, CPU, nothing read from the lake.
"""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import pywt

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_wavelet", ROOT / "_scripts" / "lib" / "native_wavelet.py")
NW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NW)

FROZEN = {"fold_id": "inner_1", "train_end": "2023-12-31T20:00:00Z"}


def series(n, seed=7, period=None, step_s=3600):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.002, n)))
    if period:
        close = close + 2.0 * np.sin(2.0 * np.pi * np.arange(n) / period)
    ts = pd.date_range("2024-01-01", periods=n, freq=f"{step_s}s", tz="UTC")
    return pd.DataFrame({"timestamp": ts, "close": close})


def run(df, **kw):
    args = dict(window=128, wavelet="db4", level=3, frozen_from=FROZEN, sample_interval_seconds=3600)
    args.update(kw)
    return NW.compute_wavelet_native(df, **args)


def cols(out):
    return [c for c in out.columns if c != "timestamp"]


def test_metadata_is_native_and_declares_units_cadence_age():
    out, meta = run(series(400))
    assert meta["method_id"] == "NATIVE" and meta["method_name"] == "DWT_DB4_TRAILING_WINDOW"
    assert meta["library"] == "pywt" and meta["version"] == pywt.__version__
    assert meta["native_coverage_claimed"] is True and meta["proxy_of"] is None
    assert meta["window"] == 128 and meta["level"] == 3 and meta["mode"]
    assert meta["inputs_transformed"] == ["close"]
    assert meta["sample_interval_seconds"] == 3600
    assert meta["update_cadence_bars"] == 1 and meta["max_feature_age_bars"] == 0
    assert meta["units"]["detail"] and meta["units"]["energy"]
    assert meta["window_frozen_from"] == FROZEN


def test_window_is_a_required_frozen_parameter_never_derived_from_length():
    df = series(300)
    with pytest.raises(TypeError):
        NW.compute_wavelet_native(df, wavelet="db4", level=3, frozen_from=FROZEN, sample_interval_seconds=3600)
    with pytest.raises(ValueError):
        run(df, frozen_from=None)
    assert "len(df)" not in inspect.getsource(NW.compute_wavelet_native).split('"""')[-1]


def test_values_are_pywt_wavedec_of_the_trailing_window():
    df = series(600, period=24)
    out, meta = run(df)
    t = 450
    win = np.array(df["close"].to_numpy()[t - 127:t + 1], dtype=float, copy=True)   # writable for PyWavelets under pandas 3
    coeffs = pywt.wavedec(win, "db4", level=3, mode=meta["mode"])
    assert out.loc[t, "wavelet_native_A3"] == pytest.approx(coeffs[0][-1])
    for k, lev in enumerate(range(3, 0, -1), start=1):
        assert out.loc[t, f"wavelet_native_D{lev}"] == pytest.approx(coeffs[k][-1])
        assert out.loc[t, f"wavelet_native_energy_D{lev}"] == pytest.approx(float(np.mean(coeffs[k] ** 2)))


def test_past_only_future_perturbation_changes_nothing_before_it():
    df = series(900)
    out, _ = run(df)
    d2 = df.copy()
    d2.loc[d2.index >= 700, "close"] += 25.0
    out2, _ = run(d2)
    pd.testing.assert_frame_equal(out.loc[:699, cols(out)], out2.loc[:699, cols(out)])


def test_prefix_invariance_below_1000_rows():
    df = series(1500)
    a, _ = run(df.iloc[:990].reset_index(drop=True))
    b, _ = run(df)
    pd.testing.assert_frame_equal(a[cols(a)], b.loc[:989, cols(b)].reset_index(drop=True))


def test_restart_and_chunked_replay_emit_the_same_values():
    df = series(1500)
    full, meta = run(df)
    k = 1000
    restarted, _ = run(df.iloc[k - meta["window"] + 1:].reset_index(drop=True))
    tail = restarted.iloc[meta["window"] - 1:].reset_index(drop=True)
    pd.testing.assert_frame_equal(tail[cols(tail)], full.loc[k:, cols(full)].reset_index(drop=True))
    chunks = [run(df.iloc[max(0, s - meta["window"] + 1):s + 300].reset_index(drop=True))[0].iloc[(s - max(0, s - meta["window"] + 1)):]
              for s in range(0, 1500, 300)]
    replay = pd.concat(chunks, ignore_index=True)
    pd.testing.assert_frame_equal(replay[cols(replay)], full[cols(full)])


def test_warmup_and_missing_values_are_nan_never_interpolated():
    df = series(400)
    df.loc[200, "close"] = np.nan
    out, meta = run(df)
    assert out.loc[: meta["window"] - 2, cols(out)].isna().all().all()
    assert out.loc[200:200 + meta["window"] - 1, cols(out)].isna().all().all()
    assert out.loc[200 + meta["window"], cols(out)].notna().all()


def test_no_hard_coded_user_home_default():
    src = (ROOT / "_scripts" / "lib" / "native_wavelet.py").read_text()
    assert "/home/" not in src and "expanduser" not in src


def test_read_only_input_is_accepted():
    """pandas >= 3 may expose read-only arrays; the producer must copy rather than fail in PyWavelets."""
    df = series(300)
    arr = df["close"].to_numpy(copy=True)
    arr.setflags(write=False)
    ro = pd.DataFrame({"timestamp": df["timestamp"], "close": arr})
    a, _ = run(ro)
    b, _ = run(df)
    pd.testing.assert_frame_equal(a[cols(a)], b[cols(b)])
