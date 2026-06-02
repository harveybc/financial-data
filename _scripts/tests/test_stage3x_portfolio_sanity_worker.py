from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_portfolio_sanity_worker as W


class TestStage3xPortfolioSanityWorker(unittest.TestCase):

    def test_fixture_passes_mechanical_sanity(self):
        report = W.validate_evidence(W.build_fixture())
        self.assertTrue(report["ok"])
        self.assertEqual(report["stage_c_access"], "DENIED")
        self.assertFalse(report["training_launched"])
        self.assertEqual(report["blocker_count"], 0)
        self.assertEqual(report["asset_count"], 2)

    def test_stage_c_timestamp_blocks(self):
        evidence = W.build_fixture()
        evidence["assets"][0]["last_timestamp"] = "2025-01-01 00:00:00"
        report = W.validate_evidence(evidence)
        self.assertFalse(report["ok"])
        self.assertIn("ASSET_STAGE_C_TIMESTAMP", {row["code"] for row in report["blockers"]})

    def test_return_aggregation_mismatch_blocks(self):
        evidence = W.build_fixture()
        evidence["portfolio_return"] = 0.50
        report = W.validate_evidence(evidence)
        self.assertFalse(report["ok"])
        self.assertIn("PORTFOLIO_RETURN_AGGREGATION_MISMATCH", {row["code"] for row in report["blockers"]})

    def test_trade_count_mismatch_blocks(self):
        evidence = W.build_fixture()
        evidence["portfolio_trades"] = 99
        report = W.validate_evidence(evidence)
        self.assertFalse(report["ok"])
        self.assertIn("PORTFOLIO_TRADE_COUNT_MISMATCH", {row["code"] for row in report["blockers"]})

    def test_missing_force_close_fields_block(self):
        evidence = W.build_fixture()
        del evidence["assets"][0]["force_close_exposed_bars"]
        report = W.validate_evidence(evidence)
        self.assertFalse(report["ok"])
        self.assertIn("ASSET_FORCE_CLOSE_FIELDS_MISSING", {row["code"] for row in report["blockers"]})

    def test_asset_trade_frequency_hard_max_blocks(self):
        evidence = W.build_fixture()
        evidence["assets"][0]["trades"] = 100
        evidence["portfolio_trades"] = 103
        report = W.validate_evidence(evidence)
        self.assertFalse(report["ok"])
        self.assertIn("ASSET_TRADE_FREQUENCY_HARD_MAX_EXCEEDED", {row["code"] for row in report["blockers"]})

    def test_no_negative_return_blocker(self):
        evidence = copy.deepcopy(W.build_fixture())
        evidence["assets"][0]["net_return"] = -0.01
        evidence["assets"][1]["net_return"] = -0.02
        evidence["portfolio_return"] = -0.014
        report = W.validate_evidence(evidence)
        self.assertTrue(report["ok"], report["blockers"])


if __name__ == "__main__":
    unittest.main()

