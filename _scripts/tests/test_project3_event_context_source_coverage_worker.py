from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import project3_event_context_source_coverage_worker as W


class TestProject3EventContextSourceCoverageWorker(unittest.TestCase):

    def test_audits_point_in_time_event_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "economic_calendar" / "release_actuals" / "provider" / "announcements.csv"
            source.parent.mkdir(parents=True)
            source.write_text(
                "\n".join(
                    [
                        "currency,indicator,scheduled_release_ts,first_available_ts,actual_value,forecast_median,previous_value,revised_value,provider_importance",
                        "USD,nfp,2024-02-02 13:30:00+00:00,2024-02-02 13:30:05+00:00,350,200,210,205,high",
                        "USD,cpi,2025-02-12 13:30:00+00:00,2025-02-12 13:30:03+00:00,3.1,3.0,3.2,3.1,high",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            report = W.build_report(root)

        self.assertEqual(report["schema_version"], W.SCHEMA_VERSION)
        self.assertEqual(report["stage_c_access"], "DENIED")
        self.assertFalse(report["training_launched"])
        self.assertEqual(report["source_count"], 1)
        audited = report["sources"][0]
        self.assertTrue(audited["has_scheduled_release_ts"])
        self.assertTrue(audited["has_first_available_ts"])
        self.assertTrue(audited["has_actual"])
        self.assertTrue(audited["has_forecast"])
        self.assertTrue(audited["has_previous"])
        self.assertTrue(audited["has_revision"])
        self.assertTrue(audited["has_provider_importance"])
        self.assertEqual(audited["pre_heldout_rows"], 1)
        self.assertEqual(audited["heldout_or_later_rows"], 1)
        self.assertTrue(audited["uses_heldout"])
        self.assertEqual(len(audited["source_hash"]), 64)
        self.assertNotIn("POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS", audited["blocking_issues"])

    def test_actual_values_without_first_available_timestamp_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "economic_calendar" / "scheduled_events" / "provider" / "scheduled_events.csv"
            source.parent.mkdir(parents=True)
            source.write_text(
                "\n".join(
                    [
                        "currency,event_family,scheduled_release_ts,actual_value,surprise,provider_importance",
                        "EUR,policy_rate,2024-03-07 12:45:00+00:00,4.50,0.25,high",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            report = W.build_report(root)

        audited = report["sources"][0]
        self.assertTrue(audited["has_actual"])
        self.assertTrue(audited["has_surprise"])
        self.assertFalse(audited["has_first_available_ts"])
        self.assertIn("POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS", audited["blocking_issues"])
        self.assertIn("ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS", audited["blocking_issues"])
        self.assertIn("SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS", audited["blocking_issues"])
        self.assertGreater(report["blocking_issues"]["ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS"], 0)

    def test_writes_json_and_markdown_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            out = Path(tmp) / "out"
            source = root / "economic_calendar" / "scheduled_events" / "provider" / "release_calendar.csv"
            source.parent.mkdir(parents=True)
            source.write_text(
                "currency,release,announcement_datetime_utc,provider_importance\n"
                "AUD,policy_rate,2024-05-05 04:30:00+00:00,high\n",
                encoding="utf-8",
            )
            report = W.build_report(root)
            W.write_json(report, out / "coverage.json")
            W.write_markdown(report, out / "coverage.md")

            written = (out / "coverage.json").read_text(encoding="utf-8")
            rendered = (out / "coverage.md").read_text(encoding="utf-8")

        self.assertIn(W.SCHEMA_VERSION, written)
        self.assertIn("Project 3 Event-Context Source Coverage Report", rendered)
        self.assertIn("release_calendar.csv", rendered)


if __name__ == "__main__":
    unittest.main()
