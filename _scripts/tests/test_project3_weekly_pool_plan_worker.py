from __future__ import annotations

import argparse
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import project3_weekly_pool_plan_worker as W


def _write_4h_input(path: Path) -> None:
    header = ["DATE_TIME", "CLOSE", *W.DEFAULT_FEATURES]
    start = dt.datetime(2022, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2024, 12, 31, 20, 0, 0, tzinfo=dt.timezone.utc)
    rows = [",".join(header)]
    current = start
    while current <= end:
        values = [current.replace(tzinfo=None).isoformat(sep=" "), "100.0"]
        values.extend("0.1" for _ in W.DEFAULT_FEATURES)
        rows.append(",".join(values))
        current += dt.timedelta(hours=4)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_4h_input_with_event_features(path: Path) -> None:
    header = ["DATE_TIME", "CLOSE", *W.DEFAULT_FEATURES, "event_upcoming_high_count_24h", "event_no_trade_window_active"]
    start = dt.datetime(2022, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2024, 12, 31, 20, 0, 0, tzinfo=dt.timezone.utc)
    rows = [",".join(header)]
    current = start
    while current <= end:
        values = [current.replace(tzinfo=None).isoformat(sep=" "), "100.0"]
        values.extend("0.1" for _ in W.DEFAULT_FEATURES)
        values.extend(["1.0", "0.0"])
        rows.append(",".join(values))
        current += dt.timedelta(hours=4)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_4h_input_with_available_features(path: Path) -> None:
    header = [
        "DATE_TIME",
        "OPEN",
        "HIGH",
        "LOW",
        "CLOSE",
        "VOLUME",
        "return_1",
        "rsi_14",
        "volume_ratio_20",
        "future_return_1",
        "target_label",
    ]
    start = dt.datetime(2022, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2024, 12, 31, 20, 0, 0, tzinfo=dt.timezone.utc)
    rows = [",".join(header)]
    current = start
    while current <= end:
        values = [current.replace(tzinfo=None).isoformat(sep=" ")]
        values.extend("1.0" for _ in header[1:])
        rows.append(",".join(values))
        current += dt.timedelta(hours=4)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


class TestProject3WeeklyPoolPlanWorker(unittest.TestCase):

    def test_metric_windows_are_configurable_and_pre_stage_c(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_csv = root / "train.csv"
            _write_4h_input(input_csv)
            args = argparse.Namespace(
                input_data_file=str(input_csv),
                train_years="1",
                policies="scratch",
                fine_tune_months="12",
                max_anchors=2,
                min_train_rows=500,
                early_stop_train_tail_days=28,
                validation_days=14,
                test_days=21,
                output_dir=str(root),
                plan_stem="custom_windows",
            )

            plan = W.build_plan(args)

        self.assertEqual(
            plan["metric_windows"],
            {
                "early_stop_train_tail_days": 28,
                "validation_days": 14,
                "test_days": 21,
            },
        )
        self.assertEqual(len(plan["jobs"]), 1)
        job = plan["jobs"][0]
        self.assertEqual(job["validation_days"], 14)
        self.assertEqual(job["test_days"], 21)
        self.assertIn("_etd28_vd14_td21", job["job_id"])
        self.assertEqual(job["hyperparameters"]["early_stop_train_tail_days"], 28)
        self.assertGreaterEqual(len(job["subjobs"]), 1)
        subjob = job["subjobs"][0]
        self.assertIn("_etd28_vd14_td21", subjob["subjob_id"])
        self.assertEqual(subjob["validation_rows"], 14 * 6)
        self.assertEqual(subjob["test_rows"], 21 * 6)
        self.assertLessEqual(W.parse_dt(subjob["test_end"]), W.HELDOUT_START)

    def test_asset_timeframe_and_preset_are_inferred_from_input_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_csv = root / "experiments" / "stage_a_screening" / "inputs" / "ethusdt" / "4h" / "sota_low_cost" / "train.csv"
            input_csv.parent.mkdir(parents=True)
            _write_4h_input(input_csv)
            args = argparse.Namespace(
                input_data_file=str(input_csv),
                asset=None,
                timeframe=None,
                feature_preset=None,
                train_years="1",
                policies="scratch",
                fine_tune_months="12",
                max_anchors=1,
                min_train_rows=500,
                early_stop_train_tail_days=7,
                validation_days=7,
                test_days=7,
                output_dir=str(root),
                plan_stem="asset_infer",
            )

            plan = W.build_plan(args)

        job = plan["jobs"][0]
        self.assertEqual(job["asset"], "ethusdt")
        self.assertEqual(job["timeframe"], "4h")
        self.assertEqual(job["feature_preset"], "sota_low_cost")
        self.assertTrue(job["job_id"].startswith("ethusdt_4h_sota_low_cost_sac_"))
        self.assertTrue(job["subjobs"][0]["subjob_id"].startswith("ethusdt_4h_sota_low_cost_sac_"))

    def test_event_feature_columns_are_preserved_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_csv = root / "experiments" / "stage_a_screening" / "inputs" / "ethusdt" / "4h" / "sota_low_cost_plus_event_engineered_v1" / "train.csv"
            input_csv.parent.mkdir(parents=True)
            _write_4h_input_with_event_features(input_csv)
            args = argparse.Namespace(
                input_data_file=str(input_csv),
                asset=None,
                timeframe=None,
                feature_preset=None,
                train_years="1",
                policies="scratch",
                fine_tune_months="12",
                max_anchors=1,
                min_train_rows=500,
                early_stop_train_tail_days=7,
                validation_days=7,
                test_days=7,
                output_dir=str(root),
                plan_stem="event_features",
            )

            plan = W.build_plan(args)

        features = plan["jobs"][0]["feature_columns"]
        self.assertIn("event_upcoming_high_count_24h", features)
        self.assertIn("event_no_trade_window_active", features)
        self.assertEqual(plan["jobs"][0]["feature_preset"], "sota_low_cost_plus_event_engineered_v1")
        self.assertTrue(
            plan["jobs"][0]["subjobs"][0]["subjob_id"].startswith(
                "ethusdt_4h_sota_low_cost_plus_event_engineered_v1_sac_"
            )
        )

    def test_execution_profile_is_preserved_and_namespaces_job_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_csv = root / "experiments" / "stage_a_screening" / "inputs" / "ethusdt" / "4h" / "sota_low_cost_plus_event_engineered_v1" / "train.csv"
            input_csv.parent.mkdir(parents=True)
            _write_4h_input_with_event_features(input_csv)
            args = argparse.Namespace(
                input_data_file=str(input_csv),
                asset=None,
                timeframe=None,
                feature_preset=None,
                execution_profile="event_no_trade_overlay_v1",
                train_years="1",
                policies="scratch",
                fine_tune_months="12",
                max_anchors=1,
                min_train_rows=500,
                early_stop_train_tail_days=7,
                validation_days=7,
                test_days=7,
                output_dir=str(root),
                plan_stem="event_overlay",
            )

            plan = W.build_plan(args)

        job = plan["jobs"][0]
        self.assertEqual(plan["execution_profile"], "event_no_trade_overlay_v1")
        self.assertEqual(job["execution_profile"], "event_no_trade_overlay_v1")
        self.assertIn("_exec_event_no_trade_overlay_v1_", job["job_id"])
        self.assertIn("_exec_event_no_trade_overlay_v1_", job["subjobs"][0]["subjob_id"])

    def test_all_available_feature_mode_excludes_base_and_leakage_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_csv = root / "experiments" / "stage_a_screening" / "inputs" / "solusdt" / "4h" / "sota_low_cost" / "train.csv"
            input_csv.parent.mkdir(parents=True)
            _write_4h_input_with_available_features(input_csv)
            args = argparse.Namespace(
                input_data_file=str(input_csv),
                asset=None,
                timeframe=None,
                feature_preset="sota_low_cost_all_available",
                execution_profile=None,
                feature_column_mode="all_available",
                train_years="1",
                policies="scratch",
                fine_tune_months="12",
                max_anchors=1,
                min_train_rows=500,
                early_stop_train_tail_days=7,
                validation_days=7,
                test_days=7,
                output_dir=str(root),
                plan_stem="all_available_features",
            )

            plan = W.build_plan(args)

        features = plan["jobs"][0]["feature_columns"]
        self.assertEqual(features, ["return_1", "rsi_14", "volume_ratio_20"])
        self.assertEqual(plan["feature_column_mode"], "all_available")
        self.assertEqual(plan["jobs"][0]["feature_column_mode"], "all_available")
        self.assertIn("sota_low_cost_all_available", plan["jobs"][0]["job_id"])


if __name__ == "__main__":
    unittest.main()
