from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_weekly_walk_forward_contract_worker as W


class TestStage3xWeeklyWalkForwardContractWorker(unittest.TestCase):

    def test_tiny_weekly_anchors_are_ordered_and_pre_stage_c(self):
        anchors = W.build_anchor_dates(
            anchor_start=dt.date(2024, 6, 3),
            anchor_end=dt.date(2024, 6, 24),
            train_days=14,
            validation_days=7,
            test_days=7,
            max_anchors=4,
        )
        self.assertEqual(len(anchors), 4)
        for anchor in anchors:
            train_end = dt.date.fromisoformat(anchor["train_end"])
            validation_start = dt.date.fromisoformat(anchor["validation_start"])
            validation_end = dt.date.fromisoformat(anchor["validation_end"])
            test_start = dt.date.fromisoformat(anchor["test_start"])
            test_end = dt.date.fromisoformat(anchor["test_end"])
            self.assertLess(train_end, validation_start)
            self.assertLess(validation_end, test_start)
            self.assertEqual(test_start.weekday(), 0)
            self.assertLess(test_end, W.HELDOUT_START)

    def test_stage_c_boundary_stops_anchor_generation(self):
        anchors = W.build_anchor_dates(
            anchor_start=dt.date(2024, 12, 23),
            anchor_end=dt.date(2025, 1, 31),
            train_days=14,
            validation_days=7,
            test_days=7,
            max_anchors=10,
        )
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["test_start"], "2024-12-23")
        self.assertEqual(anchors[0]["test_end"], "2024-12-29")

    def test_contract_separates_target_asset_and_input_asset_mask(self):
        payload = W.build_contract(
            mode="tiny",
            anchor_start=dt.date(2024, 6, 3),
            anchor_end=dt.date(2024, 6, 3),
            train_days=14,
            validation_days=7,
            test_days=7,
            max_anchors=1,
            target_assets=["eurusd"],
            input_assets=["eurusd", "audusd", "btcusdt_perp"],
        )
        self.assertEqual(payload["stage_c_access"], "DENIED")
        self.assertFalse(payload["training_launched"])
        self.assertEqual(payload["contract_count"], 1)
        contract = payload["contracts"][0]
        self.assertEqual(contract["target_asset"], "eurusd")
        self.assertNotIn("eurusd", contract["input_asset_mask"])
        self.assertIn("audusd", contract["input_asset_mask"])
        self.assertTrue(contract["own_asset_inputs"])

    def test_write_outputs(self):
        payload = W.build_contract(
            mode="tiny",
            anchor_start=dt.date(2024, 6, 3),
            anchor_end=dt.date(2024, 6, 3),
            train_days=14,
            validation_days=7,
            test_days=7,
            max_anchors=1,
            target_assets=["btcusdt_perp"],
            input_assets=["btcusdt_perp", "ethusdt_perp"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_json, out_md = W.write_outputs(payload, Path(tmp))
            doc = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(doc["schema_version"], W.SCHEMA_VERSION)
            self.assertIn("Weekly Walk-Forward", out_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

