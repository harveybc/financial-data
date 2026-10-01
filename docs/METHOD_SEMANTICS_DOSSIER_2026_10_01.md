# Method semantics dossier: what each signal-decomposition producer actually computes, in which units, and when

Lane C (method semantics and temporal tests) of the owner addendum
`SATOSHI_SOURCE_TRANSFORM_COVERAGE_ADDENDUM_2026_10_01.md` (predictor master `256c61a6`), findings 4, 5 and 6.
Written 2026-10-01 from the source code at the cited revisions; every claim cites `file:line`.

**Status: SOURCE-CODE OBSERVATIONS MADE EXECUTABLE. NO MEASURED LEAKAGE RATE.** Nothing here reads a lake artifact,
scores a retained model or quantifies how much any historical feature file leaked. The tests run on synthetic
series. Lane B owns the source/feature reconciliation ledger; this dossier supplies the method ids, units and timing
its rows cite, and nothing else. **Causality in this dossier means no use of unavailable future inputs. It does not
prove an economic causal effect; that ladder is PS3-C in causal-inference and stays separate.**

Tests: `tests/test_method_semantics_stage23.py` (this repository, branch `satoshi/c-method-semantics-20261001` off
`ef0ba661`) — 9 `test_observed_*` GREEN, 8 `test_required_*` RED with `MECHANISM_MISSING`;
`feature-eng/tests/test_regime_fold_boundary.py` (branch `satoshi/c-method-semantics-20261001` off `d081d0f`) —
2 observed GREEN, 3 required RED. A red test names the mechanism that turns it green; none is skipped.

## 1. Producer under inspection

`_scripts/workers/stage23_signal_decomposition_worker.py` at `ef0ba661` (470 lines). It writes, per asset and
timeframe (`5m`, `15m`, `1h`, `4h`; :23), five files: `wavelet.parquet`, `hilbert.parquet`, `multitaper.parquet`,
`emd.parquet`, `fracdiff.parquet` (:350-361). Its README (:323-339) calls them "causal multi-resolution signal
features" and cites Mallat, Ehlers, Percival-Walden, Huang and Lopez de Prado.

**Input: only `close`.** `read_asset` (:75-83) keeps `df[["timestamp", "close"]]`; open, high, low and volume never
reach a producer. The file-name census of 1,400 `*.parquet` paths (addendum finding 3) is therefore a census of
transforms of one channel per asset-timeframe, not of every input signal.

Note for lane B: line 22 hard-codes an absolute path under a user home directory as the default `PROJECT3_ROOT`; the
tests set the environment variable instead. Not a method issue; recorded for the ledger.

## 2. Method ids, units and timing per producer

| output file | function | what the code computes | honest `method_id` / `method_name` | `proxy_of` (native reference) | units of emitted values | window | sampling / cadence | past-only? |
|---|---|---|---|---|---|---|---|---|
| `wavelet.parquet` | `compute_wavelet` :124-152 | rolling means of `close` at 16/32/64/128 bars (:128-132); "details" are differences of consecutive approximations (:134-136); band "energy" = 128-bar rolling mean of squared detail (:142); relative energy and an entropy over the four bands (:143-147). `pywt` is imported (:12) and **never called**; metadata says "db4-style decomposition approximated with past-only dyadic windows" (:150-151) | **`PROXY` / `MULTISCALE_ROLLING_MEAN_PROXY`** | `DWT_DB4` — PyWavelets `pywt.wavedec(x, "db4", level=4)` (pywt 1.7.0 installed) | price units (approx, detail), price² (energy), fraction (relative energy), nats (entropy) | fixed 16/32/64/128 and 128 | every bar; no forward fill needed (min_periods = window) | yes (trailing windows) |
| `hilbert.parquet` | `compute_hilbert_features` :155-190 | detrend by a 50-bar rolling mean (:158); on sparse endpoints, `scipy.signal.hilbert` of the trailing `window` samples (:172-178); emits amplitude, unwrapped phase and **`phase[-1] - phase[-2]` twice** as `ht_inst_freq` and `ht_phase_difference` (:182-183); forward-filled between endpoints (:185-186); a 100-bar z-score of amplitude (:187-189) | **`NATIVE` (SciPy Hilbert on a trailing window)** — but with undeclared units and an input-length-dependent recipe | — | amplitude: price units; phase: radians; `ht_inst_freq` = `ht_phase_difference` = **radians per bar**, never divided by the physical sample interval (300/900/3600/14400 s) | `min(256, max(96, n//10)) if n < 1000 else 256` (:160) — **a function of the input length** | endpoints every `step = max(8, sample_step(tf)//4)` bars (:161; 128/64/24/8 for 5m/15m/1h/4h); value age grows to `step-1` bars between endpoints | window is trailing (yes); grid anchored at the first row of whatever input is given (:118-121), so a restart changes the endpoints |
| `multitaper.parquet` | `compute_multitaper` :202-236, `multitaper_psd` :193-199 | log returns (:204); on sparse endpoints, DPSS tapers (NW 3.5, K 5) over the trailing window, mean of |rfft|² (:194-197); PSD read at target frequencies 0.05..0.40 (:209, :225-227), spectral entropy, dominant frequency, centroid (:228-231); forward-filled (:233-235) | **`NATIVE` (SciPy DPSS multitaper)** — same two caveats as Hilbert | — | `freqs = rfftfreq(len(segment), d=1.0)` (:198): **cycles per bar**; `mt_psd_0.05` means 0.05 cycles/bar = a 20-bar period, which is 100 min at 5m and 80 h at 4h; PSD in (log return)²·bar | same formula as Hilbert (:207) | `step = sample_step(tf)` (:208): 512/256/96/32 bars for 5m/15m/1h/4h (:109-115); feature age up to `step-1` bars = 42.6 h at 5m, 95 h at 1h | same as Hilbert |
| `emd.parquet` (proxy path) | `compute_emd_proxy` :262-276 | nested rolling-mean band-pass: `close-ma8`, `ma8-ma32`, `ma32-ma128`, residue `ma128` | **`PROXY` / `NESTED_ROLLING_MEAN_BANDPASS_PROXY`** | `EMD` (Huang 1998; PyEMD `EMD().emd`) | price units | 8/32/128 | every bar | yes |
| `emd.parquet` (true path) | `compute_true_emd_sampled` :279-310 | PyEMD on trailing windows at sparse endpoints, last sample of up to 3 IMFs + residue, forward-filled; **falls back to the proxy silently when PyEMD is absent (:280-281) or when the series is longer than 80,000 rows in `auto` mode (:318-320)** | `NATIVE` / `EMD_PYEMD_SAMPLED` — but the file name does not say which path produced it | — | price units | Hilbert formula (:285) | `step = max(sample_step(tf), 128)` (:286) | trailing window yes; sifting is per window |
| `fracdiff.parquet` | `compute_fracdiff` :249-259 | fixed-width fractional differencing weights (:239-246), causal convolution (:256), d ∈ {0.4, 0.6, 0.8} | `NATIVE` / `FRACDIFF_FIXED_WIDTH` (Lopez de Prado) | — | price units × weights | weight count per d (threshold 1e-4, ≤256) | every bar | yes |
| regime (feature-eng) | `app/regime_detector.py` `classify_regime_v3` :284-312 at `d081d0f` | nearest-centroid assignment against **module-constant** scaler (:252-253) and nine centroids (:256-266) "fitted on 15yr EURUSD (24K 4h bars)" (:248-250); cluster→regime mapping (:272-282) "Based on forward-return analysis" (:269-271) | `LEARNED_REGIME_FIXED_CONSTANTS` — fit period and fold **unknown**, mapping informed by realized forward returns | — | label 1..6 | n/a | every bar | the classification of a bar uses only that bar's features (yes); **the constants were fitted on an unknown period that may include any fold's validation/test rows (no)** |

Column index check for lane B: the Hilbert file emits `ht_amplitude`, `ht_phase`, `ht_inst_freq`,
`ht_phase_difference`, `ht_amplitude_zscore_100`; the multitaper file emits `mt_psd_0.05 … mt_psd_0.40`,
`mt_spec_entropy`, `mt_dominant_freq`, `mt_spectral_centroid`; the wavelet file emits `wavelet_approx_L1..4`,
`wavelet_detail_L1..4`, `wavelet_energy_L1..4`, `wavelet_relative_energy_L1..4`, `wavelet_entropy`. Lane B's index
holding no `wavelet_*`, `ht_*` or `mt_psd_*` columns means these files were never selected into a profiled view;
`MT_001..MT_370` are electricity channel names (addendum finding 3), not multitaper outputs.

## 3. What the observed tests pin (GREEN today, 9 of 9 in financial-data, 2 of 2 in feature-eng)

| test | observation it makes executable |
|---|---|
| `test_observed_wavelet_proxy_never_calls_wavedec` | no `wavedec`/`dwt`/`swt` call in the module; the proxy is rolling means and differences |
| `test_observed_wavelet_proxy_differs_from_pywavelets_db4` | on a 2,048-row synthetic series the proxy's `wavelet_detail_L1` and the db4 level-1 detail of the same signal have |corr| < 0.9 and are not allclose: **a proxy cannot certify native-wavelet coverage** |
| `test_observed_hilbert_inst_freq_is_the_phase_difference_column` | the two columns are bitwise equal on every emitted row; the source assigns the same expression twice |
| `test_observed_producer_reads_only_close` | `read_asset` keeps exactly timestamp and close |
| `test_observed_multitaper_frequency_axis_is_cycles_per_bar` | a 32-bar sinusoid yields `mt_dominant_freq ≈ 1/32` at 5m AND at 1h: the unit is cycles per bar, not per second |
| `test_observed_features_update_every_step_bars_and_forward_fill[5m,1h]` | number of value plateaus = number of sampled endpoints ± 1; the value is constant for `step` bars after each endpoint |
| `test_observed_window_recipe_changes_when_the_prefix_crosses_1000_rows` | window 96 at n=600, 99 at n=990, 256 at n=1000 and n=5000 |
| `test_observed_prefix_invariance_holds_at_or_above_1000_rows` | with both inputs ≥ 1,000 rows, the 1,200-row prefix of a 2,400-row run equals the 1,200-row run |
| feature-eng `test_observed_v3_constants_are_literals_with_no_fit_provenance` | the four `_GMM_*` names are literals; no `fit_period`, `train_end` or `fold_id` in the file; the comments cite 15 years of EURUSD and forward returns |
| feature-eng `test_observed_classify_v3_uses_the_same_centroids_for_any_input` | two unrelated histories are classified against identical constants; `classify_regime_v3` takes one argument |

## 4. What the required tests demand (RED today, 8 of 8 in financial-data, 3 of 3 in feature-eng)

| test | missing mechanism | what turns it green |
|---|---|---|
| `test_required_wavelet_metadata_carries_an_honest_method_id` | metadata has no `method_id` | `method_id='PROXY'`, `method_name='MULTISCALE_ROLLING_MEAN_PROXY'`, `proxy_of='DWT_DB4'`, `native_coverage_claimed=False` |
| `test_required_native_wavelet_producer_exists_and_is_past_only` | no genuine wavelet producer | `compute_wavelet_native(df, window, wavelet='db4', level)`: `pywt.wavedec` on each trailing window, last coefficient per level emitted at `t`, metadata `method_id='NATIVE'`, `library='pywt'`, version; perturbing the future never changes an emitted value |
| `test_required_frequency_units_and_sampling_interval_are_declared` | no `sample_interval_seconds`, no `units` | per-timeframe sample interval and a units map (`ht_inst_freq: radians_per_bar`, `mt_*_freq: cycles_per_bar`) with the cycles-per-second conversion |
| `test_required_inputs_transformed_are_declared` | no producer says what it transforms | `inputs_transformed=['close']` in every metadata |
| `test_required_update_cadence_and_feature_age_are_declared` | `step` present, cadence/age not | `update_cadence_bars=step`, `max_feature_age_bars=step-1`, `max_feature_age_seconds` |
| `test_required_prefix_invariance_below_1000_rows` | window derived from `len(df)` | window and step are declared parameters frozen from TRAIN; emitted values are a function of the past only |
| `test_required_restart_and_chunked_replay_emit_the_same_values` | grid anchored at row 0 of the given input | grid anchored to a declared calendar instant (e.g. epoch-aligned multiples of `step` bars) so restart, chunked replay and prefix evaluate the same endpoints |
| `test_required_windows_are_declared_parameters_frozen_from_train` | no `window` argument | explicit `window`/`step` parameters recorded with the TRAIN fold they were frozen from |
| feature-eng `test_required_fit_is_bound_to_a_fold_and_refuses_rows_past_train_end` | no `fit_regime_v3` | fit on rows ≤ `train_end` only; `RegimeFit` with fold id, train_end, n_rows, data digest; refuses `REGIME_FIT_CROSSES_FOLD` |
| feature-eng `test_required_label_mapping_carries_its_own_fold_provenance` | mapping is a literal from forward returns | `label_mapping_for(fitted, outcomes_train)` from TRAIN-only forward returns of the same fold, with fold id, train_end, horizon |
| feature-eng `test_required_admission_links_fit_period_and_mapping_to_the_fold` | nothing links detector to fold | `admit_regime_feature(fitted, mapping, fold)`: ADMITTED only with matching fold id and train_end ≤ fold; the `d081d0f` constants are refused `REGIME_FIT_PERIOD_UNKNOWN` |

## 5. Ledger states these findings imply (for lane B's transform-family rows; not decided here)

| family | state today | reason |
|---|---|---|
| wavelet (native db4) | **NOT_IMPLEMENTED** | only the proxy exists; a native producer is specified by the red test |
| wavelet (multiscale rolling-mean proxy) | IMPLEMENTED, MATERIALIZED (file census), **NOT temporally verified** (no declared cadence/units; past-only by construction), NOT profiled, NOT evaluated | honest id required before any claim |
| Hilbert amplitude/phase/frequency | IMPLEMENTED, MATERIALIZED, **temporal verification VIOLATED for n<1000 and for restarts** (red tests), units undeclared | `ht_inst_freq` duplicates `ht_phase_difference` |
| multitaper spectral measures | same as Hilbert; frequency unit cycles/bar undeclared | |
| EMD (true / proxy) | file does not record which path produced it; silent fallback at >80,000 rows or missing PyEMD | PyEMD is not installed in the coordinator's Python 3.12 environment (checked 2026-10-01), so `auto` mode produces the proxy here |
| fractional differencing | IMPLEMENTED, past-only, fixed width | no timing issue found in source |
| learned regime v3 | IMPLEMENTED; **admission into any temporal fold refused until fit period and label mapping are bound to the fold or refitted on its TRAIN** | provenance/leakage risk, not proof that any retained model used it |

## 6. Contract field

`representation_candidate_card.v1` (predictor branch `satoshi/c-contracts-20261001`) gains a required `method`
block: `method_id ∈ {PROXY, NATIVE, LEARNED, NOT_APPLICABLE}`, `method_name`, `proxy_of`, `native_reference`,
`inputs_transformed`, `units`, `sample_interval_seconds`, `update_cadence_bars`, `max_feature_age_bars`, and
`timing_invariance ∈ {VERIFIED, VIOLATED, NOT_EVALUATED}` with the test ids that decided it. A `PROXY` card cannot
claim native coverage; a `VIOLATED` timing cannot be `ADMISSIBLE`.

## 7. Not done

- No producer was changed; the native wavelet producer, the honest metadata, the declared windows and the anchored
  grid are specified by the red tests only.
- No lake artifact was read; no leakage rate was measured; nothing says which retained models consumed these files.
- The regime detector's actual fit period and data digest are unknown; only their absence is tested.
- Lane B's ledger rows are not written here.
