from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_target_relation_screen_worker as W


def _write_fixture(path: Path, *, stage_c: bool = False, signal: bool = True) -> None:
    n = 240
    dates = pd.date_range("2023-01-01", periods=n, freq="4h", tz="UTC")
    if stage_c:
        dates = pd.date_range("2024-12-20", periods=n, freq="4h", tz="UTC")
    rng = np.random.default_rng(7)
    signal_feature = np.sin(np.arange(n) / 8.0)
    noise = rng.normal(0.0, 0.01, size=n)
    future_component = 0.002 * signal_feature if signal else rng.normal(0.0, 0.002, size=n)
    returns = np.roll(future_component, 1) + noise
    close = 100.0 * np.cumprod(1.0 + returns)
    df = pd.DataFrame(
        {
            "DATE_TIME": dates.astype(str),
            "OPEN": close,
            "HIGH": close * 1.001,
            "LOW": close * 0.999,
            "CLOSE": close,
            "VOLUME": 1000.0,
            "signal_feature": signal_feature,
            "noise_feature": rng.normal(size=n),
            "constant_feature": 1.0,
        }
    )
    df.to_csv(path, index=False)


class TestStage3xTargetRelationScreenWorker(unittest.TestCase):

    def test_stage_c_rows_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.csv"
            _write_fixture(path, stage_c=True)
            with self.assertRaises(W.TargetRelationError):
                W.load_dataset(path)

    def test_known_signal_ranks_above_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.csv"
            _write_fixture(path)
            genome = {
                "genome_id": "fixture",
                "asset": "ethusdt",
                "timeframe": "4h",
                "feature_preset": "fixture",
                "source_family": "test",
                "feature_selection_method": "rank_ic_topk",
                "feature_budget": "2",
                "preprocessing_profile": "p00",
                "input_data_file": str(path),
            }
            row = W.screen_genome(genome)
            self.assertIn(row["status"], {"PASS_CPU_SCREEN", "WATCH_CPU_SCREEN"})
            self.assertIn("signal_feature", row["selected_features"])
            self.assertGreater(row["best_abs_validation_ic"], 0.01)
            self.assertFalse(row["training_launched"])
            self.assertEqual(row["stage_c_access"], "DENIED")

    def test_constant_feature_is_penalized_and_not_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.csv"
            _write_fixture(path)
            genome = {
                "genome_id": "fixture",
                "asset": "ethusdt",
                "timeframe": "4h",
                "feature_preset": "fixture",
                "source_family": "test",
                "feature_selection_method": "corr_stability_topk",
                "feature_budget": "2",
                "preprocessing_profile": "p00",
                "input_data_file": str(path),
            }
            row = W.screen_genome(genome)
            self.assertGreaterEqual(row["constant_feature_count"], 1)
            self.assertNotIn("constant_feature", row["selected_features"])

    def test_write_outputs_emits_selected_contracts_and_denies_stage_c(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_root = W.OUT_ROOT
            old_json = W.OUT_JSON
            old_csv = W.OUT_CSV
            old_md = W.OUT_MD
            old_selected = W.SELECTED_JSON
            try:
                root = Path(tmp)
                W.OUT_ROOT = root
                W.OUT_JSON = root / "screen.json"
                W.OUT_CSV = root / "screen.csv"
                W.OUT_MD = root / "screen.md"
                W.SELECTED_JSON = root / "selected.json"
                rows = [
                    {
                        "genome_id": "g0",
                        "asset": "ethusdt",
                        "timeframe": "4h",
                        "feature_preset": "fixture",
                        "source_family": "test",
                        "feature_selection_method": "rank_ic_topk",
                        "preprocessing_profile": "p00",
                        "n_rows": 200,
                        "feature_count_available": 3,
                        "constant_feature_count": 1,
                        "selected_feature_count": 2,
                        "best_abs_validation_ic": 0.1,
                        "stable_selected_feature_count": 2,
                        "proxy_net_return": 0.02,
                        "proxy_trades": 5,
                        "proxy_exposure": 0.5,
                        "screen_score": 0.2,
                        "status": "PASS_CPU_SCREEN",
                        "blockers": [],
                    }
                ]
                payload = W.write_outputs(rows, [])
                self.assertEqual(payload["stage_c_access"], "DENIED")
                self.assertFalse(payload["training_launched"])
                selected = json.loads(W.SELECTED_JSON.read_text(encoding="utf-8"))
                self.assertEqual(selected["stage_c_access"], "DENIED")
                self.assertTrue(W.OUT_CSV.exists())
            finally:
                W.OUT_ROOT = old_root
                W.OUT_JSON = old_json
                W.OUT_CSV = old_csv
                W.OUT_MD = old_md
                W.SELECTED_JSON = old_selected


class TestTargetLeakExclusion(unittest.TestCase):

    def test_obvious_target_columns_are_not_treated_as_features(self):
        # Sanity: any of these names already in a CSV would trivially "beat"
        # the IC + proxy check by being a perfect future signal. The screen
        # must refuse to treat them as features.
        leak_columns = [
            "target", "label", "y",
            "future_return", "next_return", "next_close",
            "fwd_return_1", "future_return_3", "next_close_5",
            "target_1", "label_3", "y_5",
        ]
        for col in leak_columns:
            self.assertTrue(W.is_target_leak_column(col), msg=f"{col!r} should be classified as a target/label")
        # Reasonable feature names must not be flagged.
        for col in ("close_ema_50", "rsi_14", "log_return_1", "momentum_24"):
            self.assertFalse(W.is_target_leak_column(col), msg=f"{col!r} must remain a feature")

    def test_target_column_is_filtered_out_before_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.csv"
            _write_fixture(path)
            # Inject a perfect-leak column that, if used, would dominate IC.
            df = pd.read_csv(path)
            close = pd.to_numeric(df["CLOSE"], errors="coerce")
            df["target"] = (close.shift(-1) / close - 1.0).fillna(0.0)
            df["next_return"] = df["target"]
            df.to_csv(path, index=False)
            genome = {
                "genome_id": "fixture",
                "asset": "ethusdt",
                "timeframe": "4h",
                "feature_preset": "fixture",
                "source_family": "test",
                "feature_selection_method": "rank_ic_topk",
                "feature_budget": "2",
                "preprocessing_profile": "p00",
                "input_data_file": str(path),
            }
            row = W.screen_genome(genome)
            self.assertNotIn("target", row["selected_features"])
            self.assertNotIn("next_return", row["selected_features"])


class TestCostAwareSanity(unittest.TestCase):

    def _genome(self, path: Path, method: str = "rank_ic_topk") -> dict:
        return {
            "genome_id": "neg_proxy",
            "asset": "ethusdt",
            "timeframe": "4h",
            "feature_preset": "fixture",
            "source_family": "test",
            "feature_selection_method": method,
            "feature_budget": "2",
            "preprocessing_profile": "p00",
            "input_data_file": str(path),
        }

    def test_high_ic_alone_with_negative_proxy_does_not_pass(self):
        # Build a fixture where the top feature has positive |IC| but the
        # cost-aware threshold strategy loses money once the per-trade cost is
        # applied. The screen must not award PASS_CPU_SCREEN on IC alone.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.csv"
            n = 360
            dates = pd.date_range("2023-01-01", periods=n, freq="4h", tz="UTC")
            rng = np.random.default_rng(2026)
            # A feature with tiny anticipatory effect on the next return, but
            # whose value flips sign on nearly every bar so the cost-aware
            # proxy churns enough to drown the gross edge in costs.
            churny = ((np.arange(n) % 2) * 2 - 1).astype(float) + rng.normal(0.0, 0.01, size=n)
            returns = 0.0003 * np.roll(churny, 1) + rng.normal(0.0, 0.003, size=n)
            close = 100.0 * np.cumprod(1.0 + returns)
            df = pd.DataFrame(
                {
                    "DATE_TIME": dates.astype(str),
                    "OPEN": close,
                    "HIGH": close * 1.001,
                    "LOW": close * 0.999,
                    "CLOSE": close,
                    "VOLUME": 1000.0,
                    "churny_signal": churny,
                    "feat_b": rng.normal(size=n),
                    "feat_c": rng.normal(size=n),
                    "feat_d": rng.normal(size=n),
                    "feat_e": rng.normal(size=n),
                    "feat_f": rng.normal(size=n),
                }
            )
            df.to_csv(path, index=False)
            row = W.screen_genome(self._genome(path, method="rank_ic_topk"))
            # Either of these proves the cost-aware lockout: the proxy is
            # negative, or there are no threshold trades. Both keep the screen
            # off PASS_CPU_SCREEN — which is the property the spec demands.
            self.assertNotEqual(row["status"], "PASS_CPU_SCREEN")
            self.assertTrue(
                "NEGATIVE_COST_AWARE_PROXY_RETURN" in row["blockers"]
                or "NO_THRESHOLD_TRADES" in row["blockers"],
                msg=f"expected proxy-driven blocker, got {row['blockers']}",
            )


class TestOutputContractFields(unittest.TestCase):

    def test_data_file_sha256_is_emitted_per_row_and_per_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.csv"
            _write_fixture(path)
            genome = {
                "genome_id": "fixture",
                "asset": "ethusdt",
                "timeframe": "4h",
                "feature_preset": "fixture",
                "source_family": "test",
                "feature_selection_method": "corr_stability_topk",
                "feature_budget": "2",
                "preprocessing_profile": "p02_rolling_short_64",
                "scaling_mode": "rolling_zscore",
                "feature_scaling_window": 64,
                "feature_clip": 10,
                "window_size": 32,
                "stage_b_force_close_obs": True,
                "input_data_file": str(path),
            }
            row = W.screen_genome(genome)
            # 64 hex chars from SHA-256 of the actual CSV bytes.
            self.assertEqual(len(row["data_file_sha256"]), 64)
            self.assertEqual(row["data_file_sha256"], W.sha256_file(path))
            self.assertEqual(row["preprocessing_profile"], "p02_rolling_short_64")
            self.assertEqual(row["scaling_mode"], "rolling_zscore")
            self.assertEqual(row["feature_scaling_window"], 64)
            self.assertTrue(row["stage_b_force_close_obs"])

    def test_broker_metadata_for_asset_is_explicit(self):
        fx = W.broker_metadata_for_asset("audusd", "1h")
        self.assertEqual(fx["broker_profile"], "oanda_us_fx")
        self.assertEqual(fx["market_type"], "fx")
        self.assertEqual(fx["regulatory_profile"], "cftc_nfa_retail_forex")
        self.assertEqual(fx["trade_rate_band_id"], "oanda_us_fx_1h")

        spot = W.broker_metadata_for_asset("btcusdt", "4h")
        self.assertEqual(spot["broker_profile"], "crypto_exchange_spot")
        self.assertEqual(spot["market_type"], "crypto_spot")
        self.assertEqual(spot["trade_rate_band_id"], "crypto_exchange_spot_4h")

        perp = W.broker_metadata_for_asset("btcusdt_perp", "4h")
        self.assertEqual(perp["broker_profile"], "crypto_exchange_perp")
        self.assertEqual(perp["market_type"], "crypto_perp")


class TestRegimeCacheReuse(unittest.TestCase):

    def test_regime_conditioned_score_is_cached_per_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.csv"
            _write_fixture(path)
            prepared = W.prepare_dataset(path)
            self.assertIn("regime_cache", prepared)
            self.assertEqual(prepared["regime_cache"], {})
            # Two genomes pointing at the same dataset and the same selection
            # method must populate the cache once and reuse it.
            base_genome = {
                "genome_id": "g0",
                "asset": "ethusdt",
                "timeframe": "4h",
                "feature_preset": "fixture",
                "source_family": "test",
                "feature_selection_method": "regime_conditioned_topk",
                "feature_budget": "2",
                "preprocessing_profile": "p00",
                "input_data_file": str(path),
            }
            W.screen_prepared_genome(base_genome, prepared)
            self.assertGreater(len(prepared["regime_cache"]), 0)
            cached = dict(prepared["regime_cache"])
            # Count regime_conditioned_score calls during the second pass —
            # they should all hit the cache and never re-enter the function.
            from unittest.mock import patch
            second_genome = dict(base_genome, genome_id="g1")
            with patch.object(W, "regime_conditioned_score", side_effect=AssertionError("should not be called")):
                W.screen_prepared_genome(second_genome, prepared)
            self.assertEqual(prepared["regime_cache"], cached)


if __name__ == "__main__":
    unittest.main()
