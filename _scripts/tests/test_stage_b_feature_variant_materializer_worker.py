from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage_b_feature_variant_materializer_worker as W


def _fixture_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "DATE_TIME": pd.date_range("2020-01-01", periods=8, freq="4h").astype(str),
        "OPEN": range(8),
        "HIGH": range(1, 9),
        "LOW": range(8),
        "CLOSE": range(2, 10),
        "VOLUME": range(100, 108),
        "return_1": [0.0, 0.1, -0.1, 0.2, 0.0, 0.1, -0.2, 0.1],
        "log_return_1": [0.0, 0.09, -0.11, 0.18, 0.0, 0.09, -0.22, 0.09],
        "sma_10": range(8),
        "ema_10": range(8),
        "macd": range(8),
        "rsi_14": range(40, 48),
        "roc_10": range(8),
        "bb_width": [1, 2, 3, 4, 5, 6, 7, 8],
        "atr_14": [1, 1, 2, 2, 3, 3, 4, 4],
        "roll_std_ret_20": [0.1, 0.1, 0.2, 0.2, 0.3, 0.3, 0.4, 0.4],
        "obv": range(8),
        "volume_ratio_20": range(8),
    })


class TestStageBFeatureVariantMaterializer(unittest.TestCase):

    def test_stage_c_rows_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            df = _fixture_frame()
            df.loc[0, "DATE_TIME"] = "2025-01-01 00:00:00"
            df.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Stage C"):
                W.load_source_csv(path)

    def test_family_column_selection(self):
        df = _fixture_frame()
        self.assertIn("atr_14", W.select_family_columns(df, "volatility"))
        self.assertIn("macd", W.select_family_columns(df, "trend"))
        self.assertIn("rsi_14", W.select_family_columns(df, "momentum"))
        self.assertIn("volume_ratio_20", W.select_family_columns(df, "volume_liquidity"))

    def test_regime_and_ood_columns_are_added(self):
        df = _fixture_frame()
        regime = W.add_regime_prob_columns(df)
        self.assertIn("train_only_regime_prob_high", regime.columns)
        ood = W.add_ood_score_column(df)
        self.assertIn("train_only_ood_score", ood.columns)
        self.assertFalse(ood["train_only_ood_score"].isna().any())

    def test_write_variant_outputs_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_out = W.OUT_ROOT
            try:
                W.OUT_ROOT = Path(tmp)
                meta = W.write_variant(
                    "x",
                    _fixture_frame(),
                    ["return_1", "atr_14"],
                    Path("source.csv"),
                )
                self.assertEqual(meta["variant"], "x")
                self.assertTrue(meta["max_timestamp_lt_heldout"])
                self.assertTrue(Path(meta["output_csv"]).exists())
                self.assertEqual(meta["feature_columns"], ["return_1", "atr_14"])
            finally:
                W.OUT_ROOT = old_out


if __name__ == "__main__":
    unittest.main()
