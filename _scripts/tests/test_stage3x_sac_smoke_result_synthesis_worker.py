from __future__ import annotations

import csv
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage3x_sac_smoke_result_synthesis_worker as W


def _row(
    *,
    cost: str = "base",
    validation_return: float = 0.04,
    test_return: float = 0.05,
    test_trades: int = 20,
    validation_trades: int = 20,
    validation_weeks: float = 52.0,
    test_weeks: float = 52.0,
    validation_trades_per_week: float | str | None = None,
    test_trades_per_week: float | str | None = None,
    force_close: bool = True,
    status: str = "done",
    friday_force_flat_violations: int | str = "",
    daily_break_trade_attempts: int | str = "",
    validation_cost_to_gross_edge_ratio: float | str = 0.25,
    test_cost_to_gross_edge_ratio: float | str = 0.25,
    feature_list_hash: str = "f" * 64,
    observation_state_hash: str = "o" * 64,
    expected_market_state_profile_id: str = "",
    market_state_profile_id: str = "",
    market_state_profile_hash: str = "",
    market_state_selected_columns: list[str] | str = "",
) -> dict:
    if validation_trades_per_week is None:
        validation_trades_per_week = (
            validation_trades / validation_weeks if validation_weeks else 0.0
        )
    if test_trades_per_week is None:
        test_trades_per_week = test_trades / test_weeks if test_weeks else 0.0
    return {
        "status": status,
        "cost_scenario": cost,
        "validation_return": validation_return,
        "test_return": test_return,
        "validation_trades": validation_trades,
        "test_trades": test_trades,
        "validation_weeks": validation_weeks,
        "test_weeks": test_weeks,
        "validation_trades_per_week": validation_trades_per_week,
        "test_trades_per_week": test_trades_per_week,
        "test_no_trades": test_trades == 0,
        "force_close_obs_present": force_close,
        "validation_cost_to_gross_edge_ratio": validation_cost_to_gross_edge_ratio,
        "test_cost_to_gross_edge_ratio": test_cost_to_gross_edge_ratio,
        "friday_force_flat_violations": friday_force_flat_violations,
        "daily_break_trade_attempts": daily_break_trade_attempts,
        "feature_list_hash": feature_list_hash,
        "observation_state_hash": observation_state_hash,
        "expected_market_state_profile_id": expected_market_state_profile_id,
        "market_state_profile_id": market_state_profile_id,
        "market_state_profile_hash": market_state_profile_hash,
        "market_state_selected_columns": market_state_selected_columns,
    }


def _full_cost_rows(
    *,
    validation_by_cost: dict[str, list[float]] | None = None,
    test_by_cost: dict[str, list[float]] | None = None,
) -> list[dict]:
    validation_by_cost = validation_by_cost or {
        "base": [0.04, 0.05, 0.06],
        "plus_50pct": [0.03, 0.04, 0.05],
        "plus_100pct": [0.02, 0.03, 0.04],
    }
    test_by_cost = test_by_cost or {
        "base": [0.05, 0.06, 0.07],
        "plus_50pct": [0.04, 0.05, 0.06],
        "plus_100pct": [0.03, 0.04, 0.05],
    }
    rows: list[dict] = []
    for cost in ("base", "plus_50pct", "plus_100pct"):
        for val, test in zip(validation_by_cost[cost], test_by_cost[cost]):
            rows.append(_row(cost=cost, validation_return=val, test_return=test))
    return rows


FX_FIXTURE_CONTRACT = "eurusd__1h__fx_full__corr_stability_topk__p00__selected"


class TestStage3xSacSmokeResultSynthesisWorker(unittest.TestCase):

    def test_full_cost_positive_contract_can_enter_micro_nsga(self):
        # Use a confirmed-broker (OANDA FX) slug so the broker-profile blocker
        # does not preempt the economic-eligibility path.
        summary = W.summarize_contract(FX_FIXTURE_CONTRACT, _full_cost_rows())

        self.assertEqual(summary["blockers"], [])
        self.assertEqual(summary["recommended_action"], "eligible_for_stage3x_micro_nsga")

    def test_cost_fragility_warns_but_keeps_micro_nsga_open(self):
        summary = W.summarize_contract(
            FX_FIXTURE_CONTRACT,
            _full_cost_rows(
                test_by_cost={
                    "base": [0.08, 0.09, 0.10],
                    "plus_50pct": [-0.02, -0.01, -0.03],
                    "plus_100pct": [0.05, 0.06, 0.07],
                }
            ),
        )

        self.assertEqual(summary["blockers"], [])
        self.assertIn("COST_FRAGILITY_NON_POSITIVE_MEDIAN_TEST_RETURN", summary["warnings"])
        self.assertEqual(summary["recommended_action"], "eligible_for_stage3x_micro_nsga")

    def test_negative_validation_median_warns_but_keeps_micro_nsga_open(self):
        summary = W.summarize_contract(
            FX_FIXTURE_CONTRACT,
            _full_cost_rows(
                validation_by_cost={
                    "base": [-0.03, -0.02, -0.01],
                    "plus_50pct": [-0.02, -0.01, -0.03],
                    "plus_100pct": [-0.01, -0.02, -0.03],
                }
            ),
        )

        self.assertEqual(summary["blockers"], [])
        self.assertIn("NON_POSITIVE_MEDIAN_VALIDATION_RETURN", summary["warnings"])
        self.assertIn("COST_FRAGILITY_NON_POSITIVE_MEDIAN_VALIDATION_RETURN", summary["warnings"])
        self.assertEqual(summary["recommended_action"], "eligible_for_stage3x_micro_nsga")
        self.assertIn("MICRO_NSGA_WILL_OPTIMIZE_NON_POSITIVE_VALIDATION_RETURN", summary["warnings"])

    def test_base_only_positive_contract_gets_micro_nsga_entry(self):
        rows = [
            _row(cost="base", validation_return=0.03, test_return=0.04),
            _row(cost="base", validation_return=0.04, test_return=0.05),
            _row(cost="base", validation_return=0.05, test_return=0.06),
        ]

        summary = W.summarize_contract(FX_FIXTURE_CONTRACT, rows)

        self.assertEqual(summary["blockers"], [])
        self.assertEqual(summary["recommended_action"], "eligible_for_stage3x_micro_nsga")
        self.assertIn("MICRO_NSGA_BASE_COST_ONLY", summary["warnings"])

    def test_cost_to_gross_edge_estimate_is_available_and_warns_when_high(self):
        est = W.cost_edge_estimate(
            net_return=0.02,
            trades=100,
            commission=0.0002,
            slippage=0.0,
        )
        self.assertAlmostEqual(est["cost_drag_estimate"], 0.04)
        self.assertAlmostEqual(est["gross_edge_estimate"], 0.06)
        self.assertAlmostEqual(est["cost_to_gross_edge_ratio"], 0.04 / 0.06)

        rows = [
            _row(
                cost="base",
                validation_cost_to_gross_edge_ratio=0.8,
                test_cost_to_gross_edge_ratio=0.9,
            )
        ]
        summary = W.summarize_contract(FX_FIXTURE_CONTRACT, rows)
        self.assertIn("COST_TO_GROSS_EDGE_HIGH", summary["warnings"])
        self.assertNotIn("COST_TO_GROSS_EDGE_UNAVAILABLE", summary["warnings"])


class TestBrokerProfileInference(unittest.TestCase):

    def test_fx_pair_returns_oanda_us_fx(self):
        out = W.infer_broker_profile("audusd__1h__fx_full__corr_stability_topk__p00__selected")
        self.assertEqual(out["broker_profile"], W.BROKER_OANDA_FX)
        self.assertEqual(out["regulatory_profile"], "cftc_nfa_retail_forex")
        self.assertEqual(out["timeframe"], "1h")
        self.assertEqual(out["broker_profile_blockers"], [])

    def test_perp_returns_crypto_exchange_perp(self):
        out = W.infer_broker_profile("btcusdt_perp__4h__crypto_full__rank_ic_topk__p00__selected")
        self.assertEqual(out["broker_profile"], W.BROKER_CRYPTO_PERP)
        self.assertEqual(out["broker_profile_blockers"], [])

    def test_spot_crypto_without_venue_is_unconfirmed_and_blocks(self):
        out = W.infer_broker_profile("btcusdt__1h__learned_lstm__corr_stability_topk__p00__selected")
        self.assertEqual(out["broker_profile"], W.BROKER_UNCONFIRMED)
        self.assertIn("BROKER_PROFILE_MISSING_OR_UNCONFIRMED", out["broker_profile_blockers"])

    def test_explicit_selected_contract_metadata_overrides_slug_guess(self):
        metadata = {
            "asset": "btcusdt",
            "timeframe": "1h",
            "broker_profile": W.BROKER_CRYPTO_SPOT,
            "regulatory_profile": "none_or_external",
        }
        out = W.infer_broker_profile(
            "btcusdt__1h__learned_lstm__corr_stability_topk__p00__selected",
            metadata,
        )
        self.assertEqual(out["broker_profile"], W.BROKER_CRYPTO_SPOT)
        self.assertEqual(out["broker_profile_blockers"], [])


class TestTradeFrequencyPolicyLookup(unittest.TestCase):

    def test_policy_known_for_each_broker_timeframe_combo(self):
        for broker in (
            W.BROKER_OANDA_FX,
            W.BROKER_OANDA_SPOT_CRYPTO,
            W.BROKER_CRYPTO_SPOT,
            W.BROKER_CRYPTO_PERP,
            W.BROKER_UNCONFIRMED,
        ):
            for tf in ("1h", "4h"):
                band = W.lookup_trade_frequency_policy(broker, tf)
                self.assertTrue(band["policy_known"], msg=f"{broker}/{tf}")
                self.assertGreater(band["hard_max"], band["warning_above"])

    def test_policy_unknown_returns_empty_band(self):
        band = W.lookup_trade_frequency_policy(W.BROKER_OANDA_FX, "30m")
        self.assertFalse(band["policy_known"])
        self.assertIsNone(band["hard_max"])


class TestTradeFrequencyGates(unittest.TestCase):

    def test_hard_max_blocks_contract(self):
        # btcusdt 1h spot — hard max is 36/week (non-OANDA unconfirmed band).
        # Build a contract whose max validation/test trades-per-week exceeds it.
        rows = [
            _row(cost="base", validation_trades_per_week=42.0, test_trades_per_week=40.0),
            _row(cost="base", validation_trades_per_week=10.0, test_trades_per_week=10.0),
        ]
        summary = W.summarize_contract("btcusdt__1h__learned_lstm__rank_ic_topk__p00__selected", rows)
        self.assertIn("TRADE_FREQUENCY_HARD_MAX_EXCEEDED", summary["blockers"])
        self.assertIn("BROKER_PROFILE_MISSING_OR_UNCONFIRMED", summary["blockers"])
        self.assertEqual(summary["recommended_action"], "defer_blocked_by_smoke_evidence")

    def test_warning_band_emits_warning_but_no_hard_block(self):
        # OANDA FX 4h: warning above 6/week, hard max 12/week. Median 7 → warning only.
        rows = [
            _row(cost="base", validation_trades_per_week=7.0, test_trades_per_week=7.0,
                 friday_force_flat_violations=0, daily_break_trade_attempts=0),
            _row(cost="base", validation_trades_per_week=8.0, test_trades_per_week=8.0,
                 friday_force_flat_violations=0, daily_break_trade_attempts=0),
            _row(cost="base", validation_trades_per_week=9.0, test_trades_per_week=9.0,
                 friday_force_flat_violations=0, daily_break_trade_attempts=0),
        ]
        summary = W.summarize_contract("audusd__4h__fx_full__corr_stability_topk__p00__selected", rows)
        self.assertNotIn("TRADE_FREQUENCY_HARD_MAX_EXCEEDED", summary["blockers"])
        self.assertIn("TRADE_FREQUENCY_WARNING_BAND_EXCEEDED", summary["warnings"])

    def test_unconfirmed_broker_blocks_eligibility_even_when_metrics_clean(self):
        # All three required pragmatic costs, positive medians, modest trade rate.
        rows: list[dict] = []
        for cost in ("base", "plus_50pct", "plus_100pct"):
            for vr, tr in ((0.04, 0.05), (0.05, 0.06), (0.06, 0.07)):
                rows.append(_row(
                    cost=cost,
                    validation_return=vr,
                    test_return=tr,
                    validation_trades=200, test_trades=210,
                    validation_weeks=52.0, test_weeks=52.0,
                ))
        summary = W.summarize_contract(
            "btcusdt__1h__learned_lstm__corr_stability_topk__p00__selected", rows
        )
        # Spot crypto without venue → broker blocker prevents micro-NSGA.
        self.assertIn("BROKER_PROFILE_MISSING_OR_UNCONFIRMED", summary["blockers"])
        self.assertNotEqual(summary["recommended_action"], "eligible_for_stage3x_micro_nsga")

    def test_fx_oanda_clean_run_can_still_reach_eligibility(self):
        rows: list[dict] = []
        for cost in ("base", "plus_50pct", "plus_100pct"):
            for vr, tr in ((0.04, 0.05), (0.05, 0.06), (0.06, 0.07)):
                rows.append(_row(
                    cost=cost,
                    validation_return=vr,
                    test_return=tr,
                    validation_trades=120, test_trades=130,
                    validation_weeks=52.0, test_weeks=52.0,
                    friday_force_flat_violations=0,
                    daily_break_trade_attempts=0,
                ))
        summary = W.summarize_contract(
            "eurusd__1h__fx_full__corr_stability_topk__p00__selected", rows
        )
        self.assertEqual(summary["broker_profile"], W.BROKER_OANDA_FX)
        # 130/52 ≈ 2.5/week, well under the 24/week FX 1h hard max.
        self.assertNotIn("TRADE_FREQUENCY_HARD_MAX_EXCEEDED", summary["blockers"])
        self.assertNotIn("BROKER_PROFILE_MISSING_OR_UNCONFIRMED", summary["blockers"])
        self.assertEqual(summary["recommended_action"], "eligible_for_stage3x_micro_nsga")

    def test_negative_return_can_enter_micro_nsga_when_mechanics_are_clean(self):
        rows = [
            _row(validation_return=-0.05, test_return=0.04, validation_trades=103, test_trades=103),
            _row(validation_return=-0.04, test_return=0.03, validation_trades=103, test_trades=103),
            _row(validation_return=-0.06, test_return=0.05, validation_trades=103, test_trades=103),
        ]

        summary = W.summarize_contract(
            "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p00__selected",
            rows,
            {
                "broker_profile": W.BROKER_CRYPTO_PERP,
                "regulatory_profile": "none_or_external",
                "selected_features": ["rsi_14", "atr_14", "volume_z"],
            },
        )

        self.assertEqual(summary["blockers"], [])
        self.assertIn("NON_POSITIVE_MEDIAN_VALIDATION_RETURN", summary["warnings"])
        self.assertEqual(summary["recommended_action"], "eligible_for_stage3x_micro_nsga")
        self.assertIn("MICRO_NSGA_WILL_OPTIMIZE_NON_POSITIVE_VALIDATION_RETURN", summary["warnings"])

    def test_seed_failure_does_not_block_micro_nsga_when_two_clean_seeds_exist(self):
        rows = [
            _row(validation_return=-0.05, test_return=0.04, validation_trades=103, test_trades=103),
            _row(validation_return=-0.04, test_return=0.03, validation_trades=103, test_trades=103),
            _row(status="failed", validation_return="", test_return="", test_trades=0),
        ]

        summary = W.summarize_contract(
            "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p00__selected",
            rows,
            {
                "broker_profile": W.BROKER_CRYPTO_PERP,
                "regulatory_profile": "none_or_external",
                "selected_features": ["rsi_14", "atr_14", "volume_z"],
            },
        )

        self.assertEqual(summary["blockers"], [])
        self.assertIn("FAILED_OR_ABORTED_SEEDS", summary["warnings"])
        self.assertEqual(summary["recommended_action"], "eligible_for_stage3x_micro_nsga")
        self.assertIn("MICRO_NSGA_SEED_FAILURES_REMAIN_IN_LEDGER", summary["warnings"])

    def test_missing_feature_hash_blocks_micro_nsga_entry(self):
        rows = [
            _row(validation_return=0.01, test_return=0.02, feature_list_hash=""),
            _row(validation_return=0.02, test_return=0.03),
        ]

        summary = W.summarize_contract(
            "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p00__selected",
            rows,
            {
                "broker_profile": W.BROKER_CRYPTO_PERP,
                "regulatory_profile": "none_or_external",
                "selected_features": ["rsi_14", "atr_14", "volume_z"],
            },
        )

        self.assertIn("MISSING_FEATURE_LIST_HASH", summary["blockers"])
        self.assertEqual(summary["recommended_action"], "defer_blocked_by_smoke_evidence")

    def test_missing_market_state_profile_evidence_blocks_micro_nsga_entry(self):
        rows = [
            _row(
                validation_return=0.01,
                test_return=0.02,
                expected_market_state_profile_id="btcusdt_perp__4h__anchor__engineered_pca",
                market_state_profile_id="",
                market_state_profile_hash="",
                market_state_selected_columns="",
            ),
            _row(
                validation_return=0.02,
                test_return=0.03,
                expected_market_state_profile_id="btcusdt_perp__4h__anchor__engineered_pca",
                market_state_profile_id="btcusdt_perp__4h__anchor__engineered_pca",
                market_state_profile_hash="m" * 64,
                market_state_selected_columns=["state_pca_00", "state_pca_01"],
            ),
        ]

        summary = W.summarize_contract(
            "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p00__selected",
            rows,
            {
                "broker_profile": W.BROKER_CRYPTO_PERP,
                "regulatory_profile": "none_or_external",
                "selected_features": ["rsi_14", "atr_14", "volume_z"],
            },
        )

        self.assertIn("MISSING_MARKET_STATE_PROFILE_EVIDENCE", summary["blockers"])
        self.assertEqual(summary["recommended_action"], "defer_blocked_by_smoke_evidence")

    def test_target_leak_feature_blocks_micro_nsga_entry(self):
        rows = [
            _row(validation_return=0.01, test_return=0.02),
            _row(validation_return=0.02, test_return=0.03),
        ]

        summary = W.summarize_contract(
            "btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p00__selected",
            rows,
            {
                "broker_profile": W.BROKER_CRYPTO_PERP,
                "regulatory_profile": "none_or_external",
                "selected_features": ["rsi_14", "future_return"],
            },
        )

        self.assertIn("SELECTED_FEATURES_CONTAIN_TARGET_LEAK", summary["blockers"])
        self.assertEqual(summary["recommended_action"], "defer_blocked_by_smoke_evidence")
