from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_market_state_causal_contract_worker as W
import stage3x_weekly_walk_forward_contract_worker as WW


def _weekly_contract() -> dict:
    return WW.build_contract(
        mode="tiny",
        anchor_start=dt.date(2024, 6, 3),
        anchor_end=dt.date(2024, 6, 10),
        train_days=14,
        validation_days=7,
        test_days=7,
        max_anchors=2,
        target_assets=["eurusd", "btcusdt_perp"],
        input_assets=["eurusd", "audusd", "btcusdt_perp", "ethusdt_perp"],
    )


class TestStage3xMarketStateCausalContractWorker(unittest.TestCase):

    def test_builds_patient_medicine_outcome_contract(self):
        payload = W.build_contract(
            weekly_contract=_weekly_contract(),
            pretrade_gap_hours=12,
            lookback_hours=168,
            state_encoding_mode="window_summary",
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["stage_c_access"], "DENIED")
        self.assertFalse(payload["training_launched"])
        self.assertEqual(payload["causal_role_mapping"]["patient"], "target_asset_at_weekly_anchor")
        self.assertIn("observed_input_or_supervisor_exposure", payload["causal_role_mapping"]["medicine"])
        self.assertGreater(payload["row_count"], 0)

    def test_temporal_gap_prevents_weekend_border_leakage(self):
        payload = W.build_contract(
            weekly_contract=_weekly_contract(),
            pretrade_gap_hours=12,
            lookback_hours=168,
            state_encoding_mode="window_summary",
        )
        for row in payload["rows"]:
            cutoff = W.parse_dt(row["decision_cutoff"])
            outcome_start = W.parse_dt(row["outcome_window_start"])
            self.assertLessEqual(cutoff + dt.timedelta(hours=12), outcome_start)
            self.assertFalse(row["temporal_issues"])

    def test_snapshot_mode_uses_single_cutoff_state(self):
        payload = W.build_contract(
            weekly_contract=_weekly_contract(),
            pretrade_gap_hours=6,
            lookback_hours=168,
            state_encoding_mode="snapshot",
        )
        self.assertTrue(payload["ok"])
        for row in payload["rows"]:
            self.assertEqual(row["observation_window_start"], row["observation_window_end"])

    def test_rejects_gap_under_six_hours(self):
        with self.assertRaises(ValueError):
            W.build_contract(
                weekly_contract=_weekly_contract(),
                pretrade_gap_hours=5,
                lookback_hours=168,
                state_encoding_mode="window_summary",
            )

    def test_stage_c_outcomes_are_skipped(self):
        weekly = WW.build_contract(
            mode="tiny",
            anchor_start=dt.date(2024, 12, 30),
            anchor_end=dt.date(2025, 1, 6),
            train_days=14,
            validation_days=7,
            test_days=7,
            max_anchors=2,
            target_assets=["eurusd"],
            input_assets=["eurusd", "audusd"],
        )
        payload = W.build_contract(
            weekly_contract=weekly,
            pretrade_gap_hours=12,
            lookback_hours=168,
            state_encoding_mode="window_summary",
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["row_count"], 0)

    def test_treatments_are_marked_observed_not_randomized(self):
        payload = W.build_contract(
            weekly_contract=_weekly_contract(),
            pretrade_gap_hours=12,
            lookback_hours=168,
            state_encoding_mode="window_summary",
        )
        notes = " ".join(payload["assumption_notes"]).lower()
        self.assertIn("not randomized", notes)
        self.assertIn("diagnostic", notes)
        for row in payload["rows"]:
            self.assertIn("portfolio_no_trade_flag", row["exposure_treatment_families"])
            self.assertIn("next_week_net_return", row["outcome_components"])


if __name__ == "__main__":
    unittest.main()

