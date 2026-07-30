import importlib.util
import sys
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "select_oanda_practice_assets.py"
)
SPEC = importlib.util.spec_from_file_location("select_oanda_practice_assets", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_build_selection_prefers_e4_quality_but_preserves_control():
    e4 = {
        ("usdcad", "4h"): {
            "seed_count": 3,
            "mean_evaluation_weeks": 49,
            "mean_annual_return": 0.01,
            "mean_annual_rap": 0.02,
            "worst_seed_annual_rap": 0.01,
            "annual_rap_seed_stddev": 0.002,
            "mean_max_drawdown": 0.01,
            "best_artifact_job_id": "usdcad-best",
        },
        ("nzdusd", "1h"): {
            "seed_count": 3,
            "mean_evaluation_weeks": 49,
            "mean_annual_return": -0.01,
            "mean_annual_rap": -0.03,
            "worst_seed_annual_rap": -0.04,
            "annual_rap_seed_stddev": 0.01,
            "mean_max_drawdown": 0.02,
            "best_artifact_job_id": "nzdusd-best",
        },
    }
    historical = {
        ("usdcad", "4h"): {
            "mean_weekly_trades": 2.0,
            "unique_validation_weeks": 51,
        },
        ("nzdusd", "1h"): {
            "mean_weekly_trades": 5.0,
            "unique_validation_weeks": 51,
        },
        ("eurusd", "1h"): {
            "mean_weekly_trades": 0.0,
            "unique_validation_weeks": 51,
        },
    }

    rows = MODULE.build_selection(e4, historical)

    assert rows[0]["oanda_instrument"] == "EUR_USD"
    by_instrument = {row["oanda_instrument"]: row for row in rows}
    assert (
        by_instrument["USD_CAD"]["observation_priority_score"]
        > by_instrument["NZD_USD"]["observation_priority_score"]
    )
    assert by_instrument["USD_CAD"]["e4_validation"]["best_artifact_job_id"] == "usdcad-best"
    assert all(row["execution_permission"] == "read_only" for row in rows)


def test_write_outputs_marks_score_as_observation_only(tmp_path):
    rows = MODULE.build_selection({}, {})
    MODULE.write_outputs(tmp_path, rows)

    payload = (tmp_path / "oanda_practice_asset_selection_v1.json").read_text()
    report = (
        tmp_path / "PROJECT3_OANDA_PRACTICE_ASSET_SELECTION_2026_07_29.md"
    ).read_text()

    assert "not a financial promotion metric" in payload
    assert "One live day calibrates plumbing and costs" in report
