from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_market_state_causal_contract_worker as C
import stage3x_market_state_profile_screen_worker as S
import stage3x_market_state_profile_worker as P
import stage3x_weekly_walk_forward_contract_worker as WW


def _profile_contract() -> dict:
    weekly = WW.build_contract(
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
    causal = C.build_contract(
        weekly_contract=weekly,
        pretrade_gap_hours=12,
        lookback_hours=168,
        state_encoding_mode="window_summary",
    )
    return P.build_profiles(
        causal,
        timeframes=["4h", "1h"],
        profile_names=[
            "engineered_summary",
            "engineered_pca",
            "engineered_regime",
            "engineered_autoencoder",
        ],
        state_lookback_weeks_1h=1,
        state_lookback_weeks_4h=2,
    )


class TestStage3xMarketStateProfileScreenWorker(unittest.TestCase):

    def test_screen_selects_implemented_profiles_only(self):
        screen = S.build_screen(_profile_contract(), max_selected=12)
        self.assertEqual(screen["stage_c_access"], "DENIED")
        self.assertFalse(screen["training_launched"])
        self.assertGreater(screen["eligible_profile_count"], 0)
        self.assertEqual(screen["selected_profile_count"], 12)
        self.assertTrue(
            all(row["implementation_status"] == "implemented_cpu_contract" for row in screen["selected_profiles"])
        )
        self.assertTrue(all(row["eligible_for_gpu_smoke"] for row in screen["selected_profiles"]))

    def test_negative_controls_are_recorded_and_pass_for_selected(self):
        screen = S.build_screen(_profile_contract(), max_selected=8)
        for row in screen["selected_profiles"]:
            self.assertTrue(row["negative_controls_pass"])
            self.assertTrue(row["future_leak_sentinel_detected"])
            self.assertLessEqual(row["shuffled_outcome_score"], 0.01)
            self.assertLessEqual(row["irrelevant_feature_score"], 0.008)

    def test_learned_stub_is_blocked(self):
        screen = S.build_screen(_profile_contract(), max_selected=100)
        stub_rows = [row for row in screen["rows"] if row["profile_name"] == "engineered_autoencoder"]
        self.assertTrue(stub_rows)
        self.assertTrue(all("ENCODER_NOT_IMPLEMENTED" in row["blockers"] for row in stub_rows))
        selected_names = {row["profile_name"] for row in screen["selected_profiles"]}
        self.assertNotIn("engineered_autoencoder", selected_names)

    def test_selected_packet_preserves_hashes_and_stage_c_denial(self):
        screen = S.build_screen(_profile_contract(), max_selected=6)
        packet = S.build_selected_packet(screen)
        self.assertEqual(packet["schema_version"], S.SELECTED_SCHEMA_VERSION)
        self.assertEqual(packet["stage_c_access"], "DENIED")
        self.assertFalse(packet["training_launched"])
        self.assertEqual(packet["contract_count"], 6)
        for row in packet["contracts"]:
            self.assertRegex(row["market_state_profile_hash"], r"^[0-9a-f]{64}$")
            self.assertRegex(row["encoder_config_hash"], r"^[0-9a-f]{64}$")
            self.assertTrue(row["selected_columns"])

    def test_profile_contract_stage_c_allowed_is_rejected(self):
        profile = _profile_contract()
        profile["stage_c_access"] = "ALLOWED"
        profile["stage_c_allowed"] = True
        with self.assertRaises(S.MarketStateProfileScreenError):
            S.build_screen(profile, max_selected=4)

    def test_selection_is_nonredundant_per_anchor_signature(self):
        screen = S.build_screen(_profile_contract(), max_selected=12)
        keys = [
            (
                row["target_asset"],
                row["timeframe"],
                row["weekly_anchor_id"],
                row["redundancy_signature"],
            )
            for row in screen["selected_profiles"]
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_selection_diversifies_timeframe_and_profile_family(self):
        screen = S.build_screen(_profile_contract(), max_selected=12)
        timeframes = {row["timeframe"] for row in screen["selected_profiles"]}
        profile_names = {row["profile_name"] for row in screen["selected_profiles"]}
        self.assertEqual(timeframes, {"1h", "4h"})
        self.assertIn("engineered_summary", profile_names)
        self.assertIn("engineered_pca", profile_names)
        self.assertIn("engineered_regime", profile_names)

    def test_future_leak_sentinel_false_blocks_row_and_keeps_it_out_of_shortlist(self):
        profile = _profile_contract()
        # Clear the sentinel on every implemented row; the screen must reject
        # the entire universe rather than promote anything to the shortlist.
        for row in profile["profiles"]:
            if row["implementation_status"] == "implemented_cpu_contract":
                row["future_leak_sentinel_detected"] = False
                evidence = dict(row.get("negative_control_evidence") or {})
                evidence["future_leak_sentinel_detected"] = False
                row["negative_control_evidence"] = evidence
        screen = S.build_screen(profile, max_selected=12)
        self.assertEqual(screen["selected_profile_count"], 0)
        # Every implemented row picks up BOTH the sentinel-missing blocker and
        # the umbrella negative-control failure marker.
        for row in screen["rows"]:
            if row["implementation_status"] == "implemented_cpu_contract":
                self.assertIn("FUTURE_LEAK_SENTINEL_MISSING", row["blockers"])
                self.assertIn("NEGATIVE_CONTROL_FAILED", row["blockers"])
                self.assertFalse(row["negative_controls_pass"])

    def test_negative_control_scores_above_threshold_block_row(self):
        profile = _profile_contract()
        impl_rows = [
            row
            for row in profile["profiles"]
            if row["implementation_status"] == "implemented_cpu_contract"
        ]
        self.assertTrue(impl_rows)
        target = impl_rows[0]
        # Inject a real "shuffled outcome looks predictable" signal that
        # exceeds the screen threshold — the row must lose eligibility.
        evidence = dict(target.get("negative_control_evidence") or {})
        evidence["shuffled_outcome_score"] = 0.5
        evidence["future_leak_sentinel_detected"] = True
        target["negative_control_evidence"] = evidence
        target["future_leak_sentinel_detected"] = True
        screen = S.build_screen(profile, max_selected=100)
        match = next(
            row
            for row in screen["rows"]
            if row["market_state_profile_id"] == target["market_state_profile_id"]
        )
        self.assertFalse(match["negative_controls_pass"])
        self.assertIn("NEGATIVE_CONTROL_FAILED", match["blockers"])
        self.assertNotIn(
            target["market_state_profile_id"],
            {row["market_state_profile_id"] for row in screen["selected_profiles"]},
        )


if __name__ == "__main__":
    unittest.main()
