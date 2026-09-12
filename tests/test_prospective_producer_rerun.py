"""C94-C95 (order 2026-09-12): the prospective rerun harness, the
identified assembler and the end-to-end prefix-invariance probe.

Every refusal and stop asserts the CORRECT outcome; the leaking-assembler
mutants show the probe is load-bearing."""
from __future__ import annotations

import ast
import json
import os
import stat
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prospective_rerun_fixture as fx  # noqa: E402

ROOT = fx.ROOT
rr = fx.load("prospective_producer_rerun_under_test",
             ROOT / "_scripts/prospective_producer_rerun.py")
worker = fx.load("stage22_worker_under_test", ROOT / fx.WORKER)
asm = fx.load("assembler_under_test", ROOT / fx.ASSEMBLER)


@pytest.fixture(autouse=True)
def _cpu(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")


def _refused(world, code, **kw):
    h = fx.harness_of(world)  # the checkout's own copy defines the class
    with pytest.raises(h.RerunRefused) as ei:
        fx.run_world(world, harness=h, **kw)
    assert ei.value.code == code, ei.value
    return ei.value


def _stopped(world, code, **kw):
    h = fx.harness_of(world)
    with pytest.raises(h.RunStopped) as ei:
        fx.run_world(world, harness=h, **kw)
    assert ei.value.code == code, ei.value
    return ei.value


# ------------------------------------------------------------ refusals
def test_a_dirty_checkout_is_refused_and_nothing_is_written(tmp_path):
    w = fx.build_world(tmp_path)
    (w["repo"] / "untracked.txt").write_text("x")
    _refused(w, "CHECKOUT_DIRTY")
    assert not w["out"].exists()


def test_a_modified_tracked_file_is_refused(tmp_path):
    w = fx.build_world(tmp_path)
    p = w["repo"] / fx.WORKER
    p.write_text(p.read_text() + "\n# edit\n")
    _refused(w, "CHECKOUT_DIRTY")


def test_a_commit_other_than_the_expected_one_is_refused(tmp_path):
    w = fx.build_world(tmp_path)
    _refused(w, "COMMIT_MISMATCH", expect_commit="0" * 40)
    _refused(w, "EXPECT_COMMIT_NOT_A_FULL_SHA", expect_commit="abc")


def test_cpu_must_be_forced(tmp_path, monkeypatch):
    w = fx.build_world(tmp_path)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES")
    _refused(w, "CPU_NOT_FORCED")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    _refused(w, "CPU_NOT_FORCED")


def test_a_non_empty_output_root_is_refused(tmp_path):
    w = fx.build_world(tmp_path)
    w["out"].mkdir(parents=True)
    (w["out"] / "leftover").write_text("x")
    _refused(w, "OUTPUT_ROOT_NOT_EMPTY")
    assert sorted(p.name for p in w["out"].iterdir()) == ["leftover"]


@pytest.mark.parametrize("where", ["checkout", "data"])
def test_an_output_root_inside_the_checkout_or_a_data_root_is_refused(
        tmp_path, where):
    w = fx.build_world(tmp_path)
    inside = (w["repo"] if where == "checkout" else w["data"]) / "succ"
    _refused(w, "OUTPUT_ROOT_OVERLAPS_CHECKOUT_OR_DATA_ROOT",
             out_root=inside)
    assert not inside.exists()


def test_an_input_digest_mismatch_is_refused_before_the_seal(tmp_path):
    w = fx.build_world(tmp_path, config_patch=lambda c: c["inputs"][
        "raw_ohlcv"].update(sha256="f" * 64))
    _refused(w, "INPUT_DIGEST_MISMATCH")
    assert not w["out"].exists()


def test_a_changed_input_byte_is_refused(tmp_path):
    w = fx.build_world(tmp_path)
    with open(w["raw_path"], "ab") as fh:
        fh.write(b"\0")
    _refused(w, "INPUT_DIGEST_MISMATCH")


def test_a_comparison_artifact_digest_mismatch_is_refused(tmp_path):
    w = fx.build_world(tmp_path, config_patch=lambda c: c["comparisons"][
        "technical"].update(sha256="e" * 64))
    _refused(w, "COMPARISON_DIGEST_MISMATCH")


def test_a_raw_schema_mismatch_is_refused(tmp_path):
    w = fx.build_world(tmp_path, config_patch=lambda c: c[
        "expected_raw_schema"].update(open="float"))
    _refused(w, "RAW_SCHEMA_MISMATCH")


# ------------------------------------------------------- write policy
def test_write_once_refuses_a_second_write_and_is_read_only(tmp_path):
    rec = rr.write_once(tmp_path, "a/b.bin", b"hello")
    p = tmp_path / "a/b.bin"
    assert rec["sha256"] == fx.sha(p)
    assert stat.S_IMODE(p.stat().st_mode) == 0o444
    with pytest.raises(FileExistsError):
        rr.write_once(tmp_path, "a/b.bin", b"again")
    assert p.read_bytes() == b"hello"
    for bad in ("../escape.bin", str(tmp_path.parent / "abs.bin")):
        with pytest.raises(rr.SandboxViolation):
            rr.write_once(tmp_path, bad, b"x")
    assert not (tmp_path.parent / "escape.bin").exists()


def test_the_guard_refuses_writes_outside_the_root_even_if_swallowed(
        tmp_path):
    root, outside = tmp_path / "root", tmp_path / "outside.txt"
    root.mkdir()
    g = rr.WriteGuard(root)
    with g.active():
        # a producer's `except Exception` cannot swallow the refusal
        with pytest.raises(rr.SandboxViolation):
            try:
                open(outside, "w").write("x")
            except Exception:
                pass
        with pytest.raises(rr.SandboxViolation):
            pd.DataFrame({"a": [1]}).to_csv(root / "x.csv")
        with pytest.raises(rr.SandboxViolation):
            os.system("true")
        with open(root / "inside.txt", "w") as fh:
            fh.write("ok")
    assert not outside.exists()
    assert g.violations and "open-for-write" in g.violations[0]
    assert (root / "inside.txt").read_text() == "ok"


# --------------------------------------------------------- completed run
def test_a_complete_run_seals_first_writes_only_inside_and_reproduces(
        tmp_path):
    w = fx.build_world(tmp_path)
    before = fx.snapshot(w["repo"], w["data"])
    out = fx.run_world(w)
    assert out["status"] == "COMPLETED"
    assert fx.snapshot(w["repo"], w["data"]) == before, \
        "nothing outside the output root changed"
    pre = json.loads((w["out"] / rr.PRE_NAME).read_text())
    post = json.loads((w["out"] / rr.POST_NAME).read_text())
    assert post["pre_run_manifest_sha256"] == pre["manifest_sha256"]
    assert pre["repository"]["commit"] == w["commit"]
    assert pre["repository"]["clean"] is True
    assert set(pre["executed_files"]) == {"harness", "config", "producer",
                                          "assembler"}
    assert {"compute_technical", "compute_statistical", "read_asset",
            "ema", "rsi", "sanitize"} <= set(
        pre["executed_symbols"]["producer"])
    assert set(pre["dependencies"]["packages"]) == {"numpy", "pandas",
                                                    "pyarrow"}
    assert "outputs" not in pre, "the seal precedes every output"
    for rec in post["outputs"]:
        p = w["out"] / rec["path"]
        assert fx.sha(p) == rec["sha256"]
        assert stat.S_IMODE(p.stat().st_mode) == 0o444
    assert not (w["out"] / rr.STOP_NAME).exists()
    for name in (rr.PRE_NAME, rr.POST_NAME, rr.E2E_NAME, rr.CMP_NAME):
        assert "/home/" not in (w["out"] / name).read_text()
        assert str(tmp_path) not in (w["out"] / name).read_text()
    e2e = json.loads((w["out"] / rr.E2E_NAME).read_text())
    assert e2e["verdict"] == "PASS"
    assert e2e["columns_total"] == 89 == e2e["columns_pass"]
    cmp_doc = json.loads((w["out"] / rr.CMP_NAME).read_text())
    tech = cmp_doc["artifacts"]["technical"]
    assert tech["columns_with_differences"] == ["sma_10"]
    assert tech["columns"]["sma_10"]["max_abs_diff"] == pytest.approx(1.0,
                                                                      abs=1e-3)
    assert cmp_doc["artifacts"]["statistical"]["columns_with_differences"] \
        == []
    csv = cmp_doc["artifacts"]["historical_model_ready_csv"]
    assert csv["bytes_identical"] is True
    with pytest.raises(PermissionError):
        (w["out"] / "late.txt").write_text("x")


def test_a_rerun_into_the_same_root_is_refused(tmp_path):
    w = fx.build_world(tmp_path)
    fx.run_world(w, seal_directories=False)
    _refused(w, "OUTPUT_ROOT_NOT_EMPTY")


# ---------------------------------------------------------------- stops
def _sleep_patch(text):
    return text.replace(
        "def compute_technical(df: pd.DataFrame) -> pd.DataFrame:\n",
        "def compute_technical(df: pd.DataFrame) -> pd.DataFrame:\n"
        "    __import__('time').sleep(30)\n", 1)


def test_the_wall_budget_stops_the_run_with_a_stop_record(tmp_path):
    w = fx.build_world(tmp_path, worker_patch=_sleep_patch,
                       config_patch=lambda c: c["budget"].update(
                           wall_seconds=1))
    _stopped(w, "BUDGET_EXCEEDED")
    stop = json.loads((w["out"] / rr.STOP_NAME).read_text())
    assert stop["code"] == "BUDGET_EXCEEDED" and stop["stage"] == "produce"
    assert (w["out"] / rr.PRE_NAME).is_file()
    assert not (w["out"] / rr.POST_NAME).exists()
    assert not (w["out"] / rr.SUCC_PARQUET).exists()


def test_a_producer_writing_outside_the_root_is_stopped(tmp_path):
    target = tmp_path / "escape_attempt.txt"

    def patch(text):
        return text.replace(
            "def compute_statistical(df: pd.DataFrame) -> pd.DataFrame:\n",
            "def compute_statistical(df: pd.DataFrame) -> pd.DataFrame:\n"
            "    try:\n"
            f"        open({str(target)!r}, 'w').write('x')\n"
            "    except Exception:\n"
            "        pass\n", 1)
    w = fx.build_world(tmp_path, worker_patch=patch)
    before = fx.snapshot(w["repo"], w["data"])
    _stopped(w, "SANDBOX_VIOLATION")
    assert not target.exists()
    assert fx.snapshot(w["repo"], w["data"]) == before
    stop = json.loads((w["out"] / rr.STOP_NAME).read_text())
    assert stop["guard_violations"]
    assert str(tmp_path) not in (w["out"] / rr.STOP_NAME).read_text()


def test_the_pre_manifest_exists_before_a_failing_producer_runs(tmp_path):
    def patch(text):
        return text.replace(
            "def compute_technical(df: pd.DataFrame) -> pd.DataFrame:\n",
            "def compute_technical(df: pd.DataFrame) -> pd.DataFrame:\n"
            "    raise RuntimeError('boom')\n", 1)
    w = fx.build_world(tmp_path, worker_patch=patch)
    _stopped(w, "PRODUCER_ERROR")
    written = sorted(str(p.relative_to(w["out"]))
                     for p in w["out"].rglob("*") if p.is_file())
    assert written == sorted([rr.INPUT_COPY, rr.PRE_NAME, rr.STOP_NAME])


# -------------------------------------------------- C95 assembler + probe
def _pipeline(assemble=None):
    assemble = assemble or asm.assemble

    def pipeline(raw_stored):
        import io
        buf = io.BytesIO()
        raw_stored.to_parquet(buf, index=False)
        buf.seek(0)
        r = worker.read_asset(buf)
        return assemble(r, worker.compute_technical(r),
                        worker.compute_statistical(r))
    return pipeline


PROBE = dict(cut_fractions=[0.5, 0.8], seed=9)


def test_the_identified_assembler_is_prefix_invariant_on_every_column():
    res = rr.e2e_prefix_probe(fx.synthetic_raw(), _pipeline(), **PROBE)
    assert res["verdict"] == "PASS", res["columns_not_pass"]
    assert res["columns_total"] == 89 == res["columns_pass"]
    assert set(res["columns"]) == set(asm.OUTPUT_COLUMNS) - {"DATE_TIME"}
    assert all(r["rowset_at_or_before_cut_equal"] for r in res["runs"])


def test_a_leaking_assembler_mutant_fails_the_probe():
    def leaking(raw, tech, stat):
        out = asm.assemble(raw, tech, stat)
        out["typical_price"] = out["typical_price"].shift(-1)
        out["CLOSE"] = out["CLOSE"] / out["CLOSE"].mean()
        return out
    res = rr.e2e_prefix_probe(fx.synthetic_raw(), _pipeline(leaking),
                              **PROBE)
    assert res["verdict"] == "FAIL"
    assert res["columns_fail"] == ["CLOSE", "typical_price"]
    assert res["columns"]["atr_14"]["verdict"] == "PASS"


def test_a_future_dependent_row_filter_fails_every_column():
    def filtering(raw, tech, stat):
        out = asm.assemble(raw, tech, stat)
        return out.loc[out["VOLUME"] < out["VOLUME"].quantile(0.9)
                       ].reset_index(drop=True)
    res = rr.e2e_prefix_probe(fx.synthetic_raw(), _pipeline(filtering),
                              **PROBE)
    assert res["verdict"] == "FAIL"
    assert len(res["columns_fail"]) == 89


def test_a_constant_column_is_not_reported_as_a_pass():
    def constant(raw, tech, stat):
        out = asm.assemble(raw, tech, stat)
        out["obv"] = 1.0
        return out
    res = rr.e2e_prefix_probe(fx.synthetic_raw(), _pipeline(constant),
                              **PROBE)
    assert res["columns"]["obv"]["verdict"] == \
        "NOT_DEMONSTRATED_INSENSITIVE_TO_PERTURBATION"
    assert res["verdict"] == "INCOMPLETE"


def test_perturbation_touches_only_rows_after_the_cut():
    raw = fx.synthetic_raw(100)
    cut = raw["timestamp"].iloc[60]
    rng = np.random.default_rng(0)
    for mode in rr.ALL_MODES:
        p = rr.perturb_raw(raw, cut, mode, rng)
        head = raw.loc[raw["timestamp"] <= cut]
        pd.testing.assert_frame_equal(
            p.loc[p["timestamp"] <= cut].reset_index(drop=True),
            head.reset_index(drop=True))
        if mode != "truncate":
            assert not p.loc[p["timestamp"] > cut, "close"].equals(
                raw.loc[raw["timestamp"] > cut, "close"])


def test_the_assembler_refuses_misalignment_and_missing_columns():
    r = worker.read_asset_frame if hasattr(worker, "read_asset_frame") \
        else None
    raw = fx.synthetic_raw(300)
    import io
    buf = io.BytesIO()
    raw.to_parquet(buf, index=False)
    buf.seek(0)
    r = worker.read_asset(buf)
    tech, stat_ = worker.compute_technical(r), worker.compute_statistical(r)
    with pytest.raises(asm.AssemblyRefused):
        asm.assemble(r, tech.iloc[1:], stat_)
    with pytest.raises(asm.AssemblyRefused):
        asm.assemble(r, tech.drop(columns=["atr_14"]), stat_)
    with pytest.raises(asm.AssemblyRefused):
        asm.assemble(r, tech, stat_.assign(extra=1.0))


def test_the_assembler_declares_and_uses_no_fill_join_or_sort():
    assert (asm.FORWARD_FILL, asm.BACKFILL, asm.TOLERANCE_JOIN, asm.JOIN,
            asm.INTERPOLATION) == ("NONE",) * 5
    banned = {"ffill", "bfill", "fillna", "pad", "backfill", "interpolate",
              "merge", "merge_asof", "join", "sort_values", "sort_index",
              "reindex", "shift", "rolling", "ewm", "expanding", "cumsum",
              "mean", "median", "quantile", "max", "min"}
    tree = ast.parse((ROOT / fx.ASSEMBLER).read_text())
    used = {n.func.attr for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not (used & banned), used & banned


def test_the_real_config_pins_the_recorded_input_and_historical_schema():
    cfg = json.loads((ROOT / "_scripts/prospective_rerun_configs/"
                      "eth_h4_stage22_rerun.v1.json").read_text())
    assert cfg["expected_output_columns"] == list(asm.OUTPUT_COLUMNS)
    meta = fx.ROOT.parent / "predictor/examples/data/project3/" \
        "ethusdt_4h_tech_stat_export_metadata.json"
    if meta.is_file():
        assert json.loads(meta.read_text())["columns"] == \
            cfg["expected_output_columns"]
    spec = cfg["inputs"]["raw_ohlcv"]
    assert spec["path"] == "features/trading_asset_data/ethusdt/4h.parquet"
    p = ROOT / spec["path"]
    if not p.is_file():
        pytest.skip("recorded input absent in this checkout")
    assert fx.sha(p) == spec["sha256"]
    import pyarrow.parquet as pq
    assert {f.name: str(f.type) for f in pq.read_schema(p)} == \
        cfg["expected_raw_schema"]
