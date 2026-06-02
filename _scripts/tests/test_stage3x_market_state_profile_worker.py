from __future__ import annotations

import copy
import datetime as dt
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_market_state_causal_contract_worker as C
import stage3x_market_state_profile_worker as W
import stage3x_weekly_walk_forward_contract_worker as WW


def _causal_contract() -> dict:
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
    return C.build_contract(
        weekly_contract=weekly,
        pretrade_gap_hours=12,
        lookback_hours=168,
        state_encoding_mode="window_summary",
    )


class TestStage3xMarketStateProfileWorker(unittest.TestCase):

    def test_builds_profiles_for_1h_and_4h(self):
        payload = W.build_profiles(
            _causal_contract(),
            timeframes=["4h", "1h"],
            profile_names=["engineered_summary", "engineered_pca", "engineered_regime"],
            state_lookback_weeks_1h=1,
            state_lookback_weeks_4h=2,
        )
        self.assertEqual(payload["stage_c_access"], "DENIED")
        self.assertFalse(payload["training_launched"])
        self.assertEqual(payload["profile_count"], 2 * 2 * 2 * 3)
        self.assertEqual(payload["implemented_profile_count"], payload["profile_count"])
        self.assertEqual({row["timeframe"] for row in payload["profiles"]}, {"1h", "4h"})

    def test_hashes_are_deterministic(self):
        kwargs = dict(
            timeframes=["4h"],
            profile_names=["engineered_summary", "engineered_pca"],
            state_lookback_weeks_1h=1,
            state_lookback_weeks_4h=2,
        )
        first = W.build_profiles(_causal_contract(), **kwargs)
        second = W.build_profiles(_causal_contract(), **kwargs)
        first_hashes = [row["market_state_profile_hash"] for row in first["profiles"]]
        second_hashes = [row["market_state_profile_hash"] for row in second["profiles"]]
        self.assertEqual(first_hashes, second_hashes)

    def test_pca_dimensions_follow_timeframe(self):
        payload = W.build_profiles(
            _causal_contract(),
            timeframes=["4h", "1h"],
            profile_names=["engineered_pca"],
            state_lookback_weeks_1h=1,
            state_lookback_weeks_4h=2,
        )
        dims = {(row["timeframe"], row["output_column_count"]) for row in payload["profiles"]}
        self.assertIn(("4h", 8), dims)
        self.assertIn(("1h", 16), dims)

    def test_learned_encoder_profiles_are_explicit_stubs(self):
        payload = W.build_profiles(
            _causal_contract(),
            timeframes=["1h"],
            profile_names=["engineered_autoencoder", "engineered_ts2vec", "engineered_patch"],
            state_lookback_weeks_1h=1,
            state_lookback_weeks_4h=2,
        )
        self.assertEqual(payload["implemented_profile_count"], 0)
        self.assertEqual(payload["stub_profile_count"], payload["profile_count"])
        self.assertTrue(
            all(row["implementation_status"] == "stub_dependency_pending" for row in payload["profiles"])
        )

    def test_stage_c_access_not_denied_is_rejected(self):
        contract = _causal_contract()
        contract["stage_c_access"] = "ALLOWED"
        contract["stage_c_allowed"] = True
        with self.assertRaises(W.MarketStateProfileError):
            W.build_profiles(
                contract,
                timeframes=["4h"],
                profile_names=["engineered_summary"],
                state_lookback_weeks_1h=1,
                state_lookback_weeks_4h=2,
            )

    def test_observation_after_cutoff_is_rejected(self):
        contract = _causal_contract()
        broken = copy.deepcopy(contract)
        row = broken["rows"][0]
        row["observation_window_end"] = row["outcome_window_start"]
        with self.assertRaises(W.MarketStateProfileError):
            W.build_profiles(
                broken,
                timeframes=["4h"],
                profile_names=["engineered_summary"],
                state_lookback_weeks_1h=1,
                state_lookback_weeks_4h=2,
            )

    def test_post_heldout_outcome_row_is_rejected(self):
        # Spec A requires fail-closed rejection of rows whose outcome window
        # reaches the Stage C boundary. Mutate a causal row so its outcome
        # crosses 2025-01-01 and confirm validation refuses it.
        contract = _causal_contract()
        broken = copy.deepcopy(contract)
        broken["rows"][0]["outcome_window_end"] = "2025-01-05 00:00:00"
        with self.assertRaises(W.MarketStateProfileError):
            W.build_profiles(
                broken,
                timeframes=["4h"],
                profile_names=["engineered_summary"],
                state_lookback_weeks_1h=1,
                state_lookback_weeks_4h=2,
            )

    def test_pca_and_regime_fit_metadata_is_train_only(self):
        payload = W.build_profiles(
            _causal_contract(),
            timeframes=["4h", "1h"],
            profile_names=["engineered_pca", "engineered_regime"],
            state_lookback_weeks_1h=1,
            state_lookback_weeks_4h=2,
        )
        for row in payload["profiles"]:
            self.assertTrue(row["train_only_fit"])
            self.assertEqual(
                row["encoder_config"]["fit_scope"],
                "train_only_before_decision_cutoff",
            )
            # Fit window must close at or before the decision cutoff so the
            # encoder never sees post-cutoff or outcome-window rows.
            self.assertLessEqual(
                W.parse_dt(row["fit_window_end"]),
                W.parse_dt(row["decision_cutoff"]),
            )
            self.assertLess(
                W.parse_dt(row["fit_window_end"]),
                W.parse_dt(row["outcome_window_start"]),
            )

    def test_negative_control_evidence_and_sentinel_recorded(self):
        payload = W.build_profiles(
            _causal_contract(),
            timeframes=["4h"],
            profile_names=["engineered_summary"],
            state_lookback_weeks_1h=1,
            state_lookback_weeks_4h=2,
        )
        for row in payload["profiles"]:
            self.assertIn("future_leak_sentinel_detected", row)
            self.assertIn("negative_control_evidence", row)
            self.assertTrue(row["future_leak_sentinel_detected"])
            self.assertEqual(
                row["negative_control_evidence"]["source_temporal_issues"],
                [],
            )

    def test_row_with_temporal_issue_clears_sentinel(self):
        # A causal row with temporal issues is rejected by the validator; the
        # validator runs before any profile is built. Confirm the validator
        # fires and the profile worker never produces a sentinel-True row for
        # such a contract.
        contract = _causal_contract()
        contract["rows"][0]["temporal_issues"] = ["OBSERVATION_AFTER_DECISION_CUTOFF"]
        with self.assertRaises(W.MarketStateProfileError):
            W.build_profiles(
                contract,
                timeframes=["4h"],
                profile_names=["engineered_summary"],
                state_lookback_weeks_1h=1,
                state_lookback_weeks_4h=2,
            )


if __name__ == "__main__":
    unittest.main()
