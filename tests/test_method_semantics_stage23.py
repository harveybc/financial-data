"""Method semantics and temporal tests for the Stage 2.3 signal-decomposition producer, written RED first.

Owner addendum `SATOSHI_SOURCE_TRANSFORM_COVERAGE_ADDENDUM_2026_10_01.md` (predictor master 256c61a6), findings 4 and
5, over `_scripts/workers/stage23_signal_decomposition_worker.py` at `ef0ba661`. The dossier that reads these tests is
`docs/METHOD_SEMANTICS_DOSSIER_2026_10_01.md`.

Two kinds of test live here and their names say which:

* `test_observed_*` are GREEN today. Each one measures, on a synthetic series, a property the source code has and the
  dossier states: the wavelet proxy differs from a PyWavelets db4 DWT; `ht_inst_freq` and `ht_phase_difference` are
  the same column; the multitaper frequency axis is cycles per bar; the producer reads only `close`; features update
  every `step` bars and are forward-filled between updates; the window recipe changes when a prefix is extended past
  1,000 rows. They are source-code observations made executable, not measured leakage rates on any lake artifact.
* `test_required_*` are RED today. Each one names the mechanism the producer lacks, and fails with a message that
  starts `MECHANISM_MISSING` -- never a skip -- until it exists: honest method ids in the metadata (`PROXY` versus
  `NATIVE`), a genuine wavelet producer, windows declared and frozen from TRAIN instead of derived from the input
  length, a sampling grid anchored to a declared instant so a restarted run emits the same values, and declared
  sampling interval, frequency units, update cadence and feature age.

Causality here means no use of unavailable future inputs. Nothing in this file is about an economic causal effect;
that ladder lives in causal-inference PS3-C.

CPU only, synthetic data, nothing read from the lake. numpy, pandas, scipy, pywt and the worker module itself.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import pywt

ROOT = Path(__file__).resolve().parents[1]
WORKER_PATH = ROOT / "_scripts" / "workers" / "stage23_signal_decomposition_worker.py"
os.environ.setdefault("PROJECT3_ROOT", str(ROOT))


def _load_worker():
    spec = importlib.util.spec_from_file_location("stage23_worker_under_test", WORKER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage23_worker_under_test"] = module
    spec.loader.exec_module(module)
    return module


worker = _load_worker()

BAR_SECONDS = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


def series(n, tf="1h", seed=7, period_bars=None):
    """A close series on a regular grid. With `period_bars`, a clean sinusoid rides on the random walk."""
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.002, n)))
    if period_bars:
        close = close + 2.0 * np.sin(2.0 * np.pi * np.arange(n) / period_bars)
    ts = pd.date_range("2024-01-01", periods=n, freq=f"{BAR_SECONDS[tf]}s", tz="UTC")
    return pd.DataFrame({"timestamp": ts, "open": close, "high": close, "low": close, "close": close,
                         "volume": np.ones(n)})


def _missing(what, how):
    pytest.fail(f"MECHANISM_MISSING: {what}. Turns green when {how}. See docs/METHOD_SEMANTICS_DOSSIER_2026_10_01.md.")


# ----------------------------------------------------------------------------------------------------- the wavelet proxy


def test_observed_wavelet_proxy_never_calls_wavedec():
    """Source observation: `pywt` is imported and never used; compute_wavelet is rolling means and their differences."""
    tree = ast.parse(WORKER_PATH.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    names = {getattr(call.func, "attr", getattr(call.func, "id", None)) for call in calls}
    assert "wavedec" not in names and "dwt" not in names and "swt" not in names
    assert "rolling" in names
    src = inspect.getsource(worker.compute_wavelet)
    assert "rolling(window, min_periods=window).mean()" in src
    assert "approx[level - 1] - approx[level]" in src


def test_observed_wavelet_proxy_differs_from_pywavelets_db4():
    """Measured on a synthetic series: the proxy's detail bands are not the db4 DWT details of the same signal."""
    df = series(2048)
    proxy, metadata = worker.compute_wavelet(df)
    close = df["close"].to_numpy(dtype=float)
    # the native object: a 4-level db4 DWT of the WHOLE series (non-causal by construction; used here only as the
    # oracle for "what a db4 detail is", never as a producer)
    coeffs = pywt.wavedec(close, "db4", level=4)
    native_d1 = pywt.upcoef("d", coeffs[-1], "db4", level=1, take=len(close))
    proxy_d1 = proxy["wavelet_detail_L1"].to_numpy(dtype=float)
    mask = np.isfinite(proxy_d1)
    assert mask.sum() > 1500
    correlation = np.corrcoef(proxy_d1[mask], native_d1[mask])[0, 1]
    assert abs(correlation) < 0.9, f"the proxy would be a db4 detail; correlation {correlation}"
    assert not np.allclose(proxy_d1[mask], native_d1[mask], atol=1e-6)
    assert "approximated" in metadata["wavelet_reference"], "the metadata itself says it is an approximation"


def test_required_wavelet_metadata_carries_an_honest_method_id():
    df = series(600)
    _, metadata = worker.compute_wavelet(df)
    if "method_id" not in metadata:
        _missing("compute_wavelet metadata has no `method_id`; it says 'db4-style decomposition approximated'",
                 "metadata carries method_id='PROXY', method_name='MULTISCALE_ROLLING_MEAN_PROXY', "
                 "proxy_of='DWT_DB4', and native_coverage_claimed=False")
    assert metadata["method_id"] == "PROXY"
    assert metadata["method_name"] == "MULTISCALE_ROLLING_MEAN_PROXY"
    assert metadata["proxy_of"] == "DWT_DB4"
    assert metadata["native_coverage_claimed"] is False


def test_required_native_wavelet_producer_exists_and_is_past_only():
    """A genuine wavelet family: PyWavelets db4 applied per past-only window, declared NATIVE, separate from the proxy."""
    native = getattr(worker, "compute_wavelet_native", None)
    if native is None:
        _missing("no `compute_wavelet_native` producer exists (pywt is imported, wavedec never called)",
                 "compute_wavelet_native(df, window=W, wavelet='db4', level=4) exists, computes pywt.wavedec on each "
                 "past-only window [t-W, t], emits the last coefficient per level at t, and its metadata carries "
                 "method_id='NATIVE', library='pywt', version=pywt.__version__, window=W")
    df = series(1200)
    out, metadata = native(df, window=256, wavelet="db4", level=4)
    assert metadata["method_id"] == "NATIVE" and metadata["library"] == "pywt"
    # past-only: perturbing the future never changes an emitted value
    disturbed = df.copy()
    disturbed.loc[disturbed.index >= 900, "close"] += 10.0
    out2, _ = native(disturbed, window=256, wavelet="db4", level=4)
    cols = [c for c in out.columns if c != "timestamp"]
    pd.testing.assert_frame_equal(out.loc[:899, cols], out2.loc[:899, cols])


# ------------------------------------------------------------------------------------- Hilbert and multitaper: semantics


def test_observed_hilbert_inst_freq_is_the_phase_difference_column():
    """Source and measurement: `ht_inst_freq` and `ht_phase_difference` are assigned the same expression (:182-183)."""
    df = series(1500, tf="1h")
    out, _ = worker.compute_hilbert_features(df, "1h")
    a, b = out["ht_inst_freq"].to_numpy(), out["ht_phase_difference"].to_numpy()
    mask = np.isfinite(a) | np.isfinite(b)
    assert mask.sum() > 0
    np.testing.assert_array_equal(a[mask], b[mask])
    src = inspect.getsource(worker.compute_hilbert_features)
    assert src.count("phase[-1] - phase[-2]") == 2, "both columns are the same radians-per-bar difference"


def test_observed_producer_reads_only_close():
    """Source (:75-83): read_asset keeps exactly timestamp and close; open/high/low/volume never reach a producer."""
    src = inspect.getsource(worker.read_asset)
    assert 'df[["timestamp", "close"]]' in src
    df = series(300)
    out, _ = worker.compute_wavelet(df)
    assert not any(c.startswith(("open", "high", "low", "volume")) for c in out.columns)


def test_observed_multitaper_frequency_axis_is_cycles_per_bar():
    """A clean 32-bar sinusoid: the dominant frequency comes out at 1/32 cycles per BAR, whatever the bar length."""
    for tf in ("5m", "1h"):
        df = series(2000, tf=tf, period_bars=32)
        out, metadata = worker.compute_multitaper(df, tf)
        dominant = out["mt_dominant_freq"].dropna().to_numpy()
        assert dominant.size > 0
        assert np.allclose(np.median(dominant), 1.0 / 32.0, atol=0.01), f"{tf}: {np.median(dominant)}"
    src = inspect.getsource(worker.multitaper_psd)
    assert "rfftfreq(len(segment), d=1.0)" in src


def test_required_frequency_units_and_sampling_interval_are_declared():
    df = series(1500, tf="5m")
    _, hilbert_meta = worker.compute_hilbert_features(df, "5m")
    _, multitaper_meta = worker.compute_multitaper(df, "5m")
    for name, meta in (("hilbert", hilbert_meta), ("multitaper", multitaper_meta)):
        if "sample_interval_seconds" not in meta or "units" not in meta:
            _missing(f"compute_{name} metadata declares neither `sample_interval_seconds` nor `units` "
                     f"(keys today: {sorted(meta)})",
                     "metadata carries sample_interval_seconds (300 for 5m) and a units map naming "
                     "ht_inst_freq='radians_per_bar', mt_*_freq='cycles_per_bar', and the cycles_per_second conversion")
    assert hilbert_meta["sample_interval_seconds"] == 300
    assert hilbert_meta["units"]["ht_inst_freq"] == "radians_per_bar"
    assert multitaper_meta["units"]["mt_dominant_freq"] == "cycles_per_bar"


def test_required_inputs_transformed_are_declared():
    df = series(600)
    _, metadata = worker.compute_wavelet(df)
    if "inputs_transformed" not in metadata:
        _missing("no producer declares which input signals it transforms (all read only `close`)",
                 "every compute_* metadata carries inputs_transformed=['close']")
    assert metadata["inputs_transformed"] == ["close"]


# ---------------------------------------------------------------------------------------------- timing: cadence and age


@pytest.mark.parametrize("tf", ["5m", "1h"])
def test_observed_features_update_every_step_bars_and_forward_fill(tf):
    n = 4000
    df = series(n, tf=tf)
    out, metadata = worker.compute_multitaper(df, tf)
    step = metadata["step"]
    assert step == worker.sample_step(tf)
    values = out["mt_spec_entropy"].to_numpy()
    finite = values[np.isfinite(values)]
    plateaus = 1 + int(np.sum(finite[1:] != finite[:-1]))
    expected_updates = len(range(metadata["window"], n, step))
    assert abs(plateaus - expected_updates) <= 1, (plateaus, expected_updates)
    # between two updates the value is the previous endpoint's: a feature age that grows to step - 1 bars
    first, second = metadata["window"] - 1, metadata["window"] - 1 + step
    assert np.isfinite(values[first]) and np.all(values[first:second] == values[first])


def test_required_update_cadence_and_feature_age_are_declared():
    df = series(1500, tf="5m")
    _, metadata = worker.compute_hilbert_features(df, "5m")
    if "update_cadence_bars" not in metadata or "max_feature_age_bars" not in metadata:
        _missing("metadata has `step` but declares neither `update_cadence_bars` nor `max_feature_age_bars`",
                 "metadata carries update_cadence_bars=step, max_feature_age_bars=step-1 and max_feature_age_seconds")
    assert metadata["update_cadence_bars"] == metadata["step"]
    assert metadata["max_feature_age_bars"] == metadata["step"] - 1
    assert metadata["max_feature_age_seconds"] == (metadata["step"] - 1) * 300


# ------------------------------------------------------------------------------ timing: prefix and restart invariance


def test_observed_window_recipe_changes_when_the_prefix_crosses_1000_rows():
    """Source (:160, :207): window = min(256, max(96, n//10)) if n < 1000 else 256."""
    for n, expected in ((600, 96), (990, 99), (1000, 256), (5000, 256)):
        _, meta = worker.compute_hilbert_features(series(n), "1h")
        assert meta["window"] == expected, (n, meta["window"])


def test_required_prefix_invariance_below_1000_rows():
    """Extending the input must not change values already emitted. Today the window AND the sampling grid move."""
    short, long = series(990, tf="1h"), series(1500, tf="1h")
    a, meta_a = worker.compute_hilbert_features(short, "1h")
    b, meta_b = worker.compute_hilbert_features(long, "1h")
    common = len(short)
    cols = ["ht_amplitude", "ht_phase", "ht_inst_freq"]
    same = all(np.array_equal(a[c].to_numpy()[:common], b[c].to_numpy()[:common], equal_nan=True) for c in cols)
    if not same:
        _missing(f"values emitted on a 990-row prefix (window {meta_a['window']}) change when the input grows to "
                 f"1,500 rows (window {meta_b['window']}): the recipe depends on the input length",
                 "the window is a declared parameter frozen from TRAIN (compute_hilbert_features(df, tf, window=W)) "
                 "and the sampling grid is anchored to a declared instant, so emitted values are a function of the "
                 "past only")
    assert same


def test_observed_prefix_invariance_holds_at_or_above_1000_rows():
    """With both inputs past 1,000 rows the window is fixed at 256 and the grid starts at 256: values agree."""
    a, _ = worker.compute_hilbert_features(series(1200, tf="1h"), "1h")
    b, _ = worker.compute_hilbert_features(series(2400, tf="1h"), "1h")
    for c in ("ht_amplitude", "ht_phase", "ht_inst_freq"):
        assert np.array_equal(a[c].to_numpy(), b[c].to_numpy()[:1200], equal_nan=True), c


def test_required_restart_and_chunked_replay_emit_the_same_values():
    """A run restarted at row k must emit, for every later timestamp, what the uninterrupted run emitted."""
    df = series(3000, tf="1h")
    full, meta = worker.compute_multitaper(df, "1h")
    k = 1000
    restarted, _ = worker.compute_multitaper(df.iloc[k:].reset_index(drop=True), "1h")
    col = "mt_spec_entropy"
    whole = full[col].to_numpy()[k + meta["window"] + meta["step"]:]
    again = restarted[col].to_numpy()[meta["window"] + meta["step"]:]
    if not np.array_equal(whole, again, equal_nan=True):
        _missing("a run restarted at row 1,000 emits different values than the uninterrupted run at the same "
                 "timestamps: sampled_positions(n, window, step) anchors the grid at the first row of whatever "
                 "input it is given",
                 "the sampling grid is anchored to a declared calendar instant (e.g. epoch-aligned multiples of "
                 "step bars) so a restart, a chunked replay and a prefix all evaluate the same endpoints")
    assert np.array_equal(whole, again, equal_nan=True)


def test_required_windows_are_declared_parameters_frozen_from_train():
    try:
        worker.compute_hilbert_features(series(1200, tf="1h"), "1h", window=128)
    except TypeError as trouble:
        _missing(f"compute_hilbert_features accepts no `window` argument ({trouble}); the window is derived from "
                 f"the input length",
                 "window and step are explicit parameters, recorded in the metadata with the TRAIN fold they were "
                 "frozen from (fold id, train_end), and never derived from len(df)")
