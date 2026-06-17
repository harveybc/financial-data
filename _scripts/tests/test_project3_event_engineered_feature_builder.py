from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import project3_event_engineered_feature_builder as W


class TestProject3EventEngineeredFeatureBuilder(unittest.TestCase):

    def test_builds_scheduled_only_features_and_blocks_surprise_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_file = root / "inputs" / "ethusdt" / "4h" / "sota_low_cost" / "train.csv"
            event_file = root / "economic_calendar" / "scheduled_events" / "fred_proxy" / "events.csv"
            output_file = root / "inputs" / "ethusdt" / "4h" / "sota_low_cost_plus_event_engineered_v1" / "train.csv"
            input_file.parent.mkdir(parents=True)
            event_file.parent.mkdir(parents=True)
            input_file.write_text(
                "\n".join(
                    [
                        "DATE_TIME,CLOSE,feature_a",
                        "2024-01-01 00:00:00,100.0,0.1",
                        "2024-01-01 04:00:00,101.0,0.2",
                        "2025-01-01 00:00:00,102.0,0.3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            event_file.write_text(
                "\n".join(
                    [
                        "event_slug,scheduled_date_proxy,actual,surprise,provider_importance",
                        "cpi_yoy,2024-01-01 08:00:00+00:00,3.2,0.1,high",
                        "nonfarm_payrolls_mom,2024-01-05 13:30:00+00:00,250,0.3,high",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            metadata = W.build_event_features(
                input_file=input_file,
                event_source_file=event_file,
                output_file=output_file,
                target_asset="ethusdt",
                no_trade_hours=6.0,
            )
            out_text = output_file.read_text(encoding="utf-8")
            meta = json.loads(output_file.with_name("train_metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(metadata["schema_version"], W.SCHEMA_VERSION)
        self.assertEqual(metadata["stage_c_access"], "DENIED")
        self.assertFalse(metadata["training_launched"])
        self.assertEqual(metadata["dropped_heldout_or_later_input_rows"], 1)
        self.assertIn("event_upcoming_high_count_24h", out_text)
        self.assertIn("event_no_trade_window_active", out_text)
        self.assertFalse(meta["event_audit"]["actual_fields_used"])
        self.assertFalse(meta["event_audit"]["surprise_fields_used"])
        self.assertIn("first_available_ts", meta["event_audit"]["disabled_point_in_time_fields_reason"])

    def test_derive_output_file_adds_event_preset(self):
        input_file = Path("/tmp/repo/experiments/stage_a_screening/inputs/ethusdt/4h/sota_low_cost/train.csv")
        derived = W._derive_output_file(input_file, None)
        self.assertEqual(
            str(derived),
            "/tmp/repo/experiments/stage_a_screening/inputs/ethusdt/4h/sota_low_cost_plus_event_engineered_v1/train.csv",
        )


if __name__ == "__main__":
    unittest.main()
