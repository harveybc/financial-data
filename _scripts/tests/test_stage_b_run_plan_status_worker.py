import csv
import pathlib
import tempfile
import unittest

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "workers"))

import stage_b_run_plan_status_worker as W


def write_trace(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "step", "timestamp", "asset", "timeframe", "split", "episode_id",
        "run_id", "seed", "bar_index", "price", "action_raw", "position",
        "reward", "gross_return", "net_return", "equity", "pnl",
        "commission_paid", "slippage_paid", "trade_cost", "trades",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class TestReturnTraceAnalysis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_final_no_trade_is_hard_anomaly(self):
        trace = self.root / "trace.csv"
        write_trace(trace, [
            {
                "step": 1, "timestamp": "2024-01-01 00:00:00",
                "position": 0, "equity": 1000, "trades": 0,
            },
            {
                "step": 2, "timestamp": "2024-01-02 00:00:00",
                "position": 0, "equity": 1001, "trades": 0,
            },
        ])
        metrics = W.analyze_return_trace(trace)
        self.assertIn("FINAL_NO_TRADES", metrics["final_trace_anomalies"])
        self.assertEqual(metrics["final_trades_total"], 0)

    def test_cumulative_trade_column_uses_last_value_not_sum(self):
        trace = self.root / "trace.csv"
        write_trace(trace, [
            {
                "step": 1, "timestamp": "2023-01-01 00:00:00",
                "position": 1, "equity": 1000, "trades": 1,
            },
            {
                "step": 2, "timestamp": "2024-01-01 00:00:00",
                "position": 1, "equity": 1100, "trades": 2,
            },
            {
                "step": 3, "timestamp": "2025-01-01 00:00:00",
                "position": 0, "equity": 1200, "trades": 3,
            },
        ])
        metrics = W.analyze_return_trace(trace)
        self.assertEqual(metrics["final_trades_total"], 3)
        self.assertNotIn("FINAL_NO_TRADES", metrics["final_trace_anomalies"])

    def test_excessive_trade_rate_is_hard_anomaly(self):
        trace = self.root / "trace.csv"
        rows = []
        for i in range(11):
            rows.append({
                "step": i,
                "timestamp": f"2024-01-{i + 1:02d} 00:00:00",
                "position": 1 if i % 2 else 0,
                "equity": 1000 + i,
                "trades": i * 50,
            })
        write_trace(trace, rows)
        metrics = W.analyze_return_trace(trace)
        self.assertIn("FINAL_EXCESSIVE_TRADES_HARD", metrics["final_trace_anomalies"])

    def test_always_in_market_losing_is_hard_anomaly(self):
        trace = self.root / "trace.csv"
        write_trace(trace, [
            {
                "step": 1, "timestamp": "2023-01-01 00:00:00",
                "position": 1, "equity": 1000, "trades": 1,
            },
            {
                "step": 2, "timestamp": "2024-01-01 00:00:00",
                "position": 1, "equity": 900, "trades": 1,
            },
        ])
        metrics = W.analyze_return_trace(trace)
        self.assertIn("FINAL_ALWAYS_IN_MARKET_LOSING", metrics["final_trace_anomalies"])


if __name__ == "__main__":
    unittest.main()
