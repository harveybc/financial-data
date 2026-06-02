from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stageb_dsr_pbo_evaluator as W


def _write_trace(path: Path, rows: list[dict[str, object]]) -> str:
    fields = [
        "step", "timestamp", "asset", "timeframe", "split", "episode_id", "run_id",
        "seed", "bar_index", "price", "action_raw", "position", "reward",
        "gross_return", "net_return", "equity", "pnl", "commission_paid",
        "slippage_paid", "trade_cost", "trades",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(n: int = 40, start_hour: int = 0) -> list[dict[str, object]]:
    out = []
    equity = 1000.0
    for idx in range(n):
        ret = 0.001 if idx % 2 == 0 else 0.0005
        equity *= 1 + ret
        out.append({
            "step": idx,
            "timestamp": f"2024-01-{1 + (idx + start_hour) // 6:02d} {((idx + start_hour) % 6) * 4:02d}:00:00",
            "asset": "ETHUSDT",
            "timeframe": "4h",
            "split": "evaluation",
            "episode_id": 0,
            "run_id": "candidate_ethusdt_4h_sac_tech_stat_s0_base",
            "seed": 0,
            "bar_index": idx,
            "price": 100 + idx,
            "action_raw": 1,
            "position": 1,
            "reward": ret,
            "gross_return": ret,
            "net_return": ret,
            "equity": equity,
            "pnl": ret * 1000,
            "commission_paid": 0,
            "slippage_paid": 0,
            "trade_cost": 0,
            "trades": idx + 1,
        })
    return out


def _write_evidence(tmp: Path, *, duplicate_split: bool = False, heldout: bool = False, bad_hash: bool = False, missing_trace: bool = False) -> Path:
    trace = tmp / "evaluation_return_trace.csv"
    rows = _rows()
    if heldout:
        rows[-1]["timestamp"] = "2025-01-01 00:00:00"
    sha = _write_trace(trace, rows)
    meta = tmp / "evaluation_return_trace.csv.meta.json"
    meta.write_text("{}", encoding="utf-8")
    trace_entry = {
        "split": "evaluation",
        "trace_file": str(trace if not missing_trace else tmp / "missing.csv"),
        "trace_file_sha256": ("0" * 64) if bad_hash else sha,
        "metadata_file": str(meta),
        "row_count": len(rows),
        "first_timestamp": rows[0]["timestamp"],
        "last_timestamp": rows[-1]["timestamp"],
        "contains_heldout_rows": heldout,
        "stage_c_authorized": False,
        "episode_id": 0,
    }
    traces = [trace_entry]
    if duplicate_split:
        traces.append(dict(trace_entry))
    evidence = {
        "schema_version": W.EVIDENCE_SCHEMA,
        "trace_schema_version": W.TRACE_SCHEMA,
        "run_id": "candidate_ethusdt_4h_sac_tech_stat_s0_base",
        "pipeline_plugin": "rl_pipeline",
        "asset": "ethusdt",
        "timeframe": "4h",
        "seed": 0,
        "config_hash": "abc",
        "data_file": "train.csv",
        "data_file_hash": "def",
        "feature_list_hash": "ghi",
        "heldout_boundary": W.HELDOUT_START,
        "contains_heldout_rows": heldout,
        "stage_c_authorized": False,
        "traces": traces,
    }
    path = tmp / "evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    return path


class TestEvidenceLoader(unittest.TestCase):

    def test_valid_evidence_loads_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence, entries, rows = W.validate_evidence(_write_evidence(Path(tmpdir)))
            self.assertEqual(evidence["schema_version"], W.EVIDENCE_SCHEMA)
            self.assertEqual(len(entries), 1)
            self.assertGreater(len(rows), 0)

    def test_missing_trace_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(W.EvidenceError):
                W.validate_evidence(_write_evidence(Path(tmpdir), missing_trace=True))

    def test_bad_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(W.EvidenceError):
                W.validate_evidence(_write_evidence(Path(tmpdir), bad_hash=True))

    def test_duplicate_split_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(W.EvidenceError):
                W.validate_evidence(_write_evidence(Path(tmpdir), duplicate_split=True))

    def test_unauthorized_heldout_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(W.EvidenceError):
                W.validate_evidence(_write_evidence(Path(tmpdir), heldout=True))


class TestStatisticsAndGates(unittest.TestCase):

    def test_pragmatic_cost_suffixes_group_under_same_candidate(self):
        base = "candidate_ethusdt_4h_sac_tech_stat_s2_base"
        plus_50 = "candidate_ethusdt_4h_sac_tech_stat_s2_plus_50pct"
        plus_100 = "candidate_ethusdt_4h_sac_tech_stat_s2_plus_100pct"
        expected = "ethusdt_4h_sac_tech_stat"
        # Seed marker must be stripped so seed-uncertainty groups can aggregate
        # five seeds under one slug; cost suffix must be stripped so all three
        # pragmatic cost scenarios share the slug.
        self.assertEqual(W.candidate_slug(base), expected)
        self.assertEqual(W.candidate_slug(plus_50), expected)
        self.assertEqual(W.candidate_slug(plus_100), expected)
        self.assertEqual(W.cost_scenario(plus_50), "plus_50pct")
        self.assertEqual(W.cost_scenario(plus_100), "plus_100pct")

    def test_seed_marker_is_stripped_for_all_pragmatic_seeds(self):
        for seed in range(5):
            slug = W.candidate_slug(f"ethusdt_4h_sac_tech_stat_s{seed}_base")
            self.assertEqual(slug, "ethusdt_4h_sac_tech_stat")

    def test_seed_marker_stripped_for_baseline_run_ids(self):
        # Pragmatic baseline run IDs end with _s<seed>_<cost>; stripping seed and
        # cost gives a slug that aggregates the five seed copies.
        for seed in range(5):
            slug = W.candidate_slug(
                f"ethusdt_4h_sac_tech_stat_reduced_corr_v1_baseline_buy_and_hold_s{seed}_base"
            )
            self.assertEqual(slug, "ethusdt_4h_sac_tech_stat_reduced_corr_v1_baseline_buy_and_hold")

    def test_is_baseline_run_detects_pragmatic_baselines(self):
        self.assertTrue(W.is_baseline_run("rl_baseline_12_anything_s0_base", ""))
        self.assertTrue(W.is_baseline_run("foo", "baseline_12"))
        for name in ("buy_and_hold", "no_trade", "random", "momentum", "reversal"):
            run_id = f"ethusdt_4h_sac_some_variant_baseline_{name}_s0_base"
            self.assertTrue(
                W.is_baseline_run(run_id, ""),
                msg=f"pragmatic baseline {name!r} should be classified as baseline",
            )
        # Plain candidate should not be misclassified.
        self.assertFalse(W.is_baseline_run("ethusdt_4h_sac_tech_stat_s0_base", ""))

    def test_cost_contract_accepts_legacy_or_pragmatic_full_sets(self):
        self.assertEqual(W.missing_required_cost_scenarios({"base", "pessimistic"}), [])
        self.assertEqual(W.missing_required_cost_scenarios({"base", "plus_50pct", "plus_100pct"}), [])
        self.assertIn("plus_100pct", W.missing_required_cost_scenarios({"base", "plus_50pct"}))

    def test_discover_evidence_can_read_pragmatic_plan_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            evidence_dir = root / "plans" / "variant" / "runs" / "run_1" / "return_traces"
            evidence_dir.mkdir(parents=True)
            expected = evidence_dir / "evidence.json"
            expected.write_text("{}", encoding="utf-8")
            self.assertEqual(W.discover_evidence(root), [expected])

    def test_default_discovery_roots_include_session_calendar_plan_layout(self):
        roots = {
            W.STAGE_B_RUNS,
            W.PRAGMATIC_STAGE_B_PLANS,
            W.SESSION_CALENDAR_STAGE_B_PLANS,
        }
        self.assertIn(
            W.ROOT / "experiments" / "stage_b_validation" / "session_calendar_run_plan" / "plans",
            roots,
        )

    def test_dsr_positive_fixture_passes_against_zero_benchmark(self):
        import random as _random
        rng = _random.Random(20240501)
        # Approximately Gaussian positive-drift returns: SR/sqrt(T) clearly
        # detectable, moments well-behaved enough for the PSR denominator.
        returns = [0.0040 + 0.0015 * rng.gauss(0.0, 1.0) for _ in range(200)]
        result = W.dsr(returns, 0.0)
        self.assertEqual(result["status"], "PASS")
        self.assertLess(result["dsr_p_value"], 0.01)
        self.assertIn("n_effective_newey_west", result)

    def test_pbo_fixture_reports_rank_degradation(self):
        good_is_bad_oos = []
        stable = []
        for fold in range(8):
            good_is_bad_oos.extend(
                ([0.012 if i % 2 else 0.008 for i in range(20)])
                if fold not in {0, 1, 2}
                else ([-0.025 if i % 2 else -0.015 for i in range(20)])
            )
            stable.extend([0.003 if i % 2 else 0.001 for i in range(20)])
        result = W.pbo_group([
            {"run_id": "overfit", "net_returns": good_is_bad_oos},
            {"run_id": "stable", "net_returns": stable},
        ])
        self.assertIn(result["status"], {"WATCH", "FAIL"})
        self.assertGreater(result["pbo"], 0.0)

    def test_seed_uncertainty_rejects_unpaired_seed_sets(self):
        result = W.seed_uncertainty([
            {
                "evidence_status": "PASS",
                "is_baseline": False,
                "candidate_slug": "candidate_a",
                "cost_scenario": "base",
                "net_returns": [0.01],
            }
        ])
        self.assertEqual(result["candidate_a|base"]["status"], "BLOCKED_UNPAIRED_SEEDS")

    def test_candidate_gate_requires_both_cost_scenarios(self):
        records = [{
            "run_id": "candidate_a_base",
            "candidate_slug": "candidate_a",
            "evidence_status": "PASS",
            "cost_scenario": "base",
            "trade_gate": {"status": "PASS", "blockers": []},
            "dsr_n_raw": {"status": "PASS"},
            "asset": "ethusdt",
            "timeframe": "4h",
            "algo": "sac",
        }]
        gates = W.candidate_gates(
            records,
            {"ethusdt|4h|sac": {"status": "PASS"}},
            {"ethusdt|4h|sac|base": {"status": "PASS"}},
            {"candidate_a|base": {"status": "PASS"}},
        )
        self.assertFalse(gates["candidate_a"]["promotion_allowed"])
        self.assertIn("MISSING_COST_SCENARIO", gates["candidate_a"]["blocking_reasons"])

    def test_candidate_gate_accepts_pragmatic_cost_contract(self):
        records = []
        for cost in ("base", "plus_50pct", "plus_100pct"):
            records.append({
                "run_id": f"candidate_a_{cost}",
                "candidate_slug": "candidate_a",
                "evidence_status": "PASS",
                "cost_scenario": cost,
                "trade_gate": {"status": "PASS", "blockers": []},
                "dsr_n_raw": {"status": "PASS"},
                "asset": "ethusdt",
                "timeframe": "4h",
                "algo": "sac",
            })
        gates = W.candidate_gates(
            records,
            {"ethusdt|4h|sac": {"status": "PASS"}},
            {
                "ethusdt|4h|sac|base": {"status": "PASS"},
                "ethusdt|4h|sac|plus_50pct": {"status": "PASS"},
                "ethusdt|4h|sac|plus_100pct": {"status": "PASS"},
            },
            {
                "candidate_a|base": {"status": "PASS"},
                "candidate_a|plus_50pct": {"status": "PASS"},
                "candidate_a|plus_100pct": {"status": "PASS"},
            },
        )
        self.assertNotIn("MISSING_COST_SCENARIO", gates["candidate_a"]["blocking_reasons"])


class TestTradeGates(unittest.TestCase):

    def _flat_rows(self, n: int = 96, *, days: float = 16.0, position: float = 0.0, per_bar_return: float = 0.0) -> list[dict[str, object]]:
        out = []
        bar_seconds = int(days * 86400 / max(n, 1))
        from datetime import datetime, timedelta
        start = datetime(2024, 1, 1)
        equity = 1000.0
        for idx in range(n):
            equity *= 1 + per_bar_return
            ts = (start + timedelta(seconds=idx * bar_seconds)).strftime("%Y-%m-%d %H:%M:%S")
            out.append({
                "timestamp": ts,
                "position": position,
                "trades": 0,
                "net_return": per_bar_return,
                "gross_return": per_bar_return,
                "equity": equity,
            })
        return out

    def test_no_trades_blocked(self):
        rows = self._flat_rows(n=96, days=16.0, position=0.0, per_bar_return=0.0)
        result = W.trade_gate(rows, [0.0] * len(rows))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("FINAL_NO_TRADES", result["blockers"])

    def test_excessive_trade_rate_blocked(self):
        rows = _rows(n=60)
        result = W.trade_gate(rows, W.returns_from_rows(rows, "net_return"))
        self.assertIn("FINAL_EXCESSIVE_TRADES_HARD", result["blockers"])
        self.assertGreater(result["trades_per_year"], W.EXCESSIVE_TRADES_HARD_PER_YEAR)

    def test_split_reset_cumulative_trades_not_summed_row_by_row(self):
        rows = []
        for split, final_count in (("train", 3), ("validation", 2), ("test", 4)):
            for idx in range(5):
                rows.append({
                    "timestamp": f"2024-01-{idx + 1:02d} 00:00:00",
                    "split": split,
                    "episode_id": f"run::{split}",
                    "position": 1.0,
                    "trades": min(idx, final_count),
                    "net_return": 0.0,
                    "gross_return": 0.0,
                    "equity": 1000.0,
                })
        # Correct count is terminal counter per split: 3 + 2 + 4.
        # The old bug summed every cumulative row after seeing split resets.
        self.assertEqual(W.infer_trade_count(rows), 9)

    def test_always_in_market_losing_blocked(self):
        rows = self._flat_rows(n=400, days=400.0, position=1.0, per_bar_return=-0.001)
        # inject a couple of trades so FINAL_NO_TRADES does not preempt
        rows[10]["trades"] = 1
        rows[-1]["trades"] = 2
        result = W.trade_gate(rows, [r["net_return"] for r in rows])
        self.assertIn("FINAL_ALWAYS_IN_MARKET_LOSING", result["blockers"])
        self.assertGreaterEqual(result["exposure_fraction"], W.ALWAYS_IN_MARKET_HARD)
        self.assertLessEqual(result["total_return_from_trace"], 0)


class TestStageCFirewall(unittest.TestCase):

    def test_row_with_heldout_timestamp_is_rejected_even_when_flag_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            trace = tmp / "evaluation_return_trace.csv"
            rows = _rows()
            # Silently insert a Stage C-dated row while leaving flags clean.
            rows[-1]["timestamp"] = "2025-02-03 04:00:00"
            sha = _write_trace(trace, rows)
            meta = tmp / "evaluation_return_trace.csv.meta.json"
            meta.write_text("{}", encoding="utf-8")
            evidence = {
                "schema_version": W.EVIDENCE_SCHEMA,
                "trace_schema_version": W.TRACE_SCHEMA,
                "run_id": "candidate_ethusdt_4h_sac_tech_stat_s0_base",
                "pipeline_plugin": "rl_pipeline",
                "asset": "ethusdt",
                "timeframe": "4h",
                "seed": 0,
                "config_hash": "abc",
                "data_file": "train.csv",
                "data_file_hash": "def",
                "feature_list_hash": "ghi",
                "heldout_boundary": W.HELDOUT_START,
                "contains_heldout_rows": False,
                "stage_c_authorized": False,
                "traces": [{
                    "split": "evaluation",
                    "trace_file": str(trace),
                    "trace_file_sha256": sha,
                    "metadata_file": str(meta),
                    "row_count": len(rows),
                    "first_timestamp": rows[0]["timestamp"],
                    "last_timestamp": rows[-2]["timestamp"],
                    "contains_heldout_rows": False,
                    "stage_c_authorized": False,
                    "episode_id": 0,
                }],
            }
            path = tmp / "evidence.json"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaises(W.EvidenceError):
                W.validate_evidence(path)


class TestMomentsAndEffectiveN(unittest.TestCase):

    def test_moments_returns_unbiased_non_excess_kurtosis_on_gaussian(self):
        import random as _random
        rng = _random.Random(1234)
        # Long enough that sample moments stabilize near Gaussian truth.
        xs = [rng.gauss(0.0, 1.0) for _ in range(4000)]
        m = W.moments(xs)
        self.assertAlmostEqual(m["skew"], 0.0, delta=0.2)
        # Non-excess Gaussian kurtosis == 3, NOT 0.
        self.assertAlmostEqual(m["kurtosis"], 3.0, delta=0.4)

    def test_moments_detect_skew_in_asymmetric_series(self):
        # Strongly right-skewed series: many small losses, a few large gains.
        xs = ([-0.001] * 300) + ([0.05] * 20)
        m = W.moments(xs)
        self.assertGreater(m["skew"], 0.5)
        # Heavy right tail → leptokurtic, kurtosis well above Gaussian 3.
        self.assertGreater(m["kurtosis"], 3.5)

    def test_effective_n_shrinks_under_positive_autocorrelation(self):
        import random as _random
        rng = _random.Random(2024)
        # AR(1) with phi=0.7 → strong positive autocorrelation.
        ar1 = []
        prev = 0.0
        for _ in range(1000):
            prev = 0.7 * prev + rng.gauss(0.0, 1.0)
            ar1.append(prev)
        iid = [rng.gauss(0.0, 1.0) for _ in range(1000)]
        t_eff_ar = W.effective_n_newey_west(ar1)
        t_eff_iid = W.effective_n_newey_west(iid)
        self.assertLess(t_eff_ar, len(ar1))
        # IID should keep T_eff close to T; AR(1) should shrink it materially.
        self.assertGreater(t_eff_iid, t_eff_ar)


class TestTrainSplitExclusion(unittest.TestCase):

    def _write_pragmatic_evidence(self, tmp: Path) -> Path:
        """Write a tri-split evidence index resembling agent-multi pragmatic output."""
        run_dir = tmp / "candidate_run" / "return_traces"
        run_dir.mkdir(parents=True)
        traces_meta = []
        all_first_last = []
        # Split sizes chosen to be small but unambiguous.
        plan = [("train", "2018-01-01", 40), ("validation", "2022-01-01", 30), ("test", "2023-01-01", 32)]
        from datetime import datetime, timedelta
        for split, start_date, n in plan:
            start = datetime.fromisoformat(start_date + " 00:00:00")
            rows = []
            equity = 1000.0
            for idx in range(n):
                ret = 0.001
                equity *= 1 + ret
                ts = (start + timedelta(hours=4 * idx)).strftime("%Y-%m-%d %H:%M:%S")
                rows.append({
                    "step": idx,
                    "timestamp": ts,
                    "asset": "ethusdt",
                    "timeframe": "4h",
                    "split": split,
                    "episode_id": f"run::{split}",
                    "run_id": "candidate_ethusdt_4h_sac_tech_stat_s0_base",
                    "seed": 0,
                    "bar_index": idx,
                    "price": 100 + idx,
                    "action_raw": 1,
                    "position": 1,
                    "reward": ret,
                    "gross_return": ret,
                    "net_return": ret,
                    "equity": equity,
                    "pnl": ret * 1000,
                    "commission_paid": 0,
                    "slippage_paid": 0,
                    "trade_cost": 0,
                    "trades": idx,
                })
            trace_path = run_dir / f"{split}_return_trace.csv"
            sha = _write_trace(trace_path, rows)
            (run_dir / f"{split}_return_trace.csv.meta.json").write_text("{}", encoding="utf-8")
            traces_meta.append({
                "split": split,
                "trace_file": str(trace_path),
                "trace_file_sha256": sha,
                "metadata_file": str(run_dir / f"{split}_return_trace.csv.meta.json"),
                "row_count": len(rows),
                "first_timestamp": rows[0]["timestamp"],
                "last_timestamp": rows[-1]["timestamp"],
                "contains_heldout_rows": False,
                "stage_c_authorized": False,
                "episode_id": 0,
            })
            all_first_last.append((rows[0]["timestamp"], rows[-1]["timestamp"]))
        evidence = {
            "schema_version": W.EVIDENCE_SCHEMA,
            "trace_schema_version": W.TRACE_SCHEMA,
            "run_id": "candidate_ethusdt_4h_sac_tech_stat_s0_base",
            "pipeline_plugin": "rl_pipeline",
            "asset": "ethusdt",
            "timeframe": "4h",
            "seed": 0,
            "config_hash": "abc",
            "data_file": "train.csv",
            "data_file_hash": "def",
            "feature_list_hash": "ghi",
            "heldout_boundary": W.HELDOUT_START,
            "contains_heldout_rows": False,
            "stage_c_authorized": False,
            "traces": traces_meta,
        }
        evidence_path = run_dir / "evidence.json"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        return evidence_path

    def test_train_split_excluded_from_record_returns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence = self._write_pragmatic_evidence(Path(tmpdir))
            records = W.build_records([evidence])
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["evidence_status"], "PASS")
            # 30 validation + 32 test rows = 62; train (40) must be excluded.
            self.assertEqual(rec["n_returns"], 62)


class TestPBOEmbargo(unittest.TestCase):

    def test_embargo_drops_adjacent_bars_and_keeps_status(self):
        # Reuse the rank-degradation fixture and confirm embargo emits a
        # finite PBO and records the embargo width in the result.
        good_is_bad_oos = []
        stable = []
        for fold in range(8):
            good_is_bad_oos.extend(
                ([0.012 if i % 2 else 0.008 for i in range(40)])
                if fold not in {0, 1, 2}
                else ([-0.025 if i % 2 else -0.015 for i in range(40)])
            )
            stable.extend([0.003 if i % 2 else 0.001 for i in range(40)])
        result = W.pbo_group(
            [
                {"run_id": "overfit", "net_returns": good_is_bad_oos},
                {"run_id": "stable", "net_returns": stable},
            ],
            embargo_bars=4,
        )
        self.assertEqual(result.get("embargo_bars"), 4)
        self.assertGreaterEqual(result["pbo"], 0.0)
        self.assertLessEqual(result["pbo"], 1.0)


if __name__ == "__main__":
    unittest.main()
