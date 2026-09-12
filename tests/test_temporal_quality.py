"""C99 battery (order 2026-09-12): temporal quality and sample eligibility.

Truncation/gap shapes are taken from the ETH H4 source parquet. Real data
files are only READ; digest-mismatch fixtures use temporary copies.
"""
from __future__ import annotations

import builtins
import hashlib
import importlib.util
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ta = _load("temporal_availability", "_scripts/temporal_availability.py")
tq = _load("temporal_quality", "_scripts/temporal_quality.py")
mat = _load("materialize_eth_h4_temporal_quality", "_scripts/materialize_eth_h4_temporal_quality.py")

SHA = "a" * 64
H = 14_400_000
FULL = H - 1
T0 = 1546300800000  # 2019-01-01 00:00 UTC, on the H4 grid

LB_BEFORE, LB_GAP, LB_TRUNC, LB_UNAV = ("LOOKBACK_BEFORE_FIRST_BAR", "LOOKBACK_CROSSES_GAP",
                                        "LOOKBACK_CONTAINS_TRUNCATED_BAR", "LOOKBACK_CONTAINS_UNAVAILABLE_BAR")
OP_BEFORE, OP_GAP, OP_TRUNC, OP_UNAV = ("OPERATOR_WINDOW_BEFORE_FIRST_BAR", "OPERATOR_WINDOW_CROSSES_GAP",
                                        "OPERATOR_WINDOW_CONTAINS_TRUNCATED_BAR", "OPERATOR_WINDOW_CONTAINS_UNAVAILABLE_BAR")
TG_ABSENT, TG_TRUNC, TG_UNAV = ("TARGET_NOMINAL_BAR_ABSENT", "TARGET_CONTAINS_TRUNCATED_BAR",
                                "TARGET_CONTAINS_UNAVAILABLE_BAR")


def ms(s: str) -> int:
    fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in s else "%Y-%m-%d %H:%M:%S"
    return int(round(datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp() * 1000))


def contract(**over):
    c = {"contract_id": "fixture.bar_open", "dataset_id": "fixture.eth_h4",
         "dataset_sha256": SHA, "timestamp_semantics": "BAR_OPEN",
         "information_complete_not_before": "PER_BAR_CLOSE_TIME",
         "nominal_bar_seconds": 14400, "bar_close_time_convention": "INCLUSIVE_LAST_MILLISECOND",
         "provider_delivery_latency": {"status": "UNOBSERVED", "seconds": None, "evidence": "none"},
         "provenance": {"status": "EVIDENCED_BY_EXACT_MATCH_NOT_BY_DECLARATION", "basis": "fixture"}}
    c.update(over)
    return c


def dataset(positions, spans=None, t0=T0):
    """positions: nominal grid indices present; spans: {position: span_ms or None}."""
    spans = spans or {}
    opens = [t0 + p * H for p in positions]
    closes = [None if spans.get(p, FULL) is None else o + spans.get(p, FULL)
              for p, o in zip(positions, opens)]
    return opens, closes


def P(**kw):
    base = dict(model_lookback_bars=3, max_operator_warmup_bars=4, target_horizon_nominal_bars=1,
                n_rolling_origins=1, test_block_bars=5, embargo_bars=0,
                inner_validation_fraction=0.5, inner_validation_embargo_bars=0)
    base.update(kw)
    return tq.EligibilityParams(**base)


def run(positions, spans=None, params=None):
    o, c = dataset(positions, spans)
    bars = tq.evaluate_bars(contract(), o, c, observed_sha256=SHA)
    return bars, tq.sample_eligibility(bars, params or P())


def reasons_by_pos(positions, bars, mask):
    return {p: set(mask.reasons(i)) for i, p in enumerate(positions)}


# ------------------------------------------------------ reference model
def reference(opens, closes, L, W, h, nominal=H):
    """Independent brute force over nominal open times (dict lookups, loops)."""
    idx = {o: i for i, o in enumerate(opens)}
    first = opens[0]
    trunc = [c is not None and c - o < nominal - 1 for o, c in zip(opens, closes)]
    unav = [c is None for c in closes]
    out = []
    for o in opens:
        rs = []
        for name, k in (("LOOKBACK", L), ("OPERATOR_WINDOW", W)):
            ts = [o - j * nominal for j in range(k)]
            inside = [t for t in ts if t >= first]
            if len(inside) < len(ts):
                rs.append(f"{name}_BEFORE_FIRST_BAR")
            if any(t not in idx for t in inside):
                rs.append(f"{name}_CROSSES_GAP")
            if any(t in idx and trunc[idx[t]] for t in inside):
                rs.append(f"{name}_CONTAINS_TRUNCATED_BAR")
            if any(t in idx and unav[idx[t]] for t in inside):
                rs.append(f"{name}_CONTAINS_UNAVAILABLE_BAR")
        ts = [o + j * nominal for j in range(1, h + 1)]
        if any(t not in idx for t in ts):
            rs.append(TG_ABSENT)
        if any(t in idx and trunc[idx[t]] for t in ts):
            rs.append(TG_TRUNC)
        if any(t in idx and unav[idx[t]] for t in ts):
            rs.append(TG_UNAV)
        out.append(tuple(rs))
    return out


def random_dataset(rng, n_pos=160, p_drop=0.06, p_trunc=0.04, p_absent=0.01):
    pos = [p for p in range(n_pos) if p == 0 or rng.random() > p_drop]
    spans = {}
    for p in pos:
        r = rng.random()
        if r < p_trunc:
            spans[p] = int(rng.integers(0, FULL))
        elif r < p_trunc + p_absent:
            spans[p] = None
    return pos, spans


# ------------------------------------------------------------ layers
def test_complete_regular_bars_all_eligible_except_edges():
    pos = list(range(40))
    bars, mask = run(pos, params=P(model_lookback_bars=5, max_operator_warmup_bars=7, target_horizon_nominal_bars=2))
    assert bars.interval_complete.all() and not bars.truncated.any() and bars.available.all()
    assert [tq.STEP_STATES[s] for s in bars.next_step_state] == ["REGULAR"] * 39 + ["UNKNOWN_LAST_ROW"]
    r = reasons_by_pos(pos, bars, mask)
    assert all(r[p] == set() for p in range(6, 38))
    assert r[0] == {LB_BEFORE, OP_BEFORE} and r[3] == {LB_BEFORE, OP_BEFORE}
    assert r[4] == r[5] == {OP_BEFORE} and r[38] == r[39] == {TG_ABSENT}
    assert int(mask.eligible.sum()) == 40 - 6 - 2
    assert mask.support_through[-1] == 32 and (np.diff(mask.support_through) >= 0).all()


def test_truncation_without_gap_real_shape():
    # 2018-01-04 00:00 closes 03:00:14.849 (span 10814.849 s), next bar regular
    pos = list(range(20))
    span = ms("2018-01-04 03:00:14.849") - ms("2018-01-04 00:00:00")
    bars, mask = run(pos, {10: span})
    i = 10
    # availability is untouched: the truncated bar is still RESOLVED/available
    assert bars.available[i] and bars.truncated[i] and not bars.interval_complete[i]
    assert tq.STEP_STATES[bars.next_step_state[i]] == "REGULAR"
    r = reasons_by_pos(pos, bars, mask)
    assert r[9] == {TG_TRUNC}
    assert r[10] == r[11] == r[12] == {LB_TRUNC, OP_TRUNC}
    assert r[13] == {OP_TRUNC} and r[14] == set()


def test_truncation_followed_by_gap_real_shape_and_no_next_observed_substitution():
    # 2018-02-08 00:00 closes 00:28:14.799; next bar 2018-02-09 08:00 (7 intervals absent)
    span = ms("2018-02-08 00:28:14.799") - ms("2018-02-08 00:00:00")
    pos = list(range(11)) + list(range(18, 30))
    bars, mask = run(pos, {10: span})
    i10 = pos.index(10)
    assert tq.STEP_STATES[bars.next_step_state[i10]] == "GAP"
    assert bars.missing_nominal_bars_after[i10] == 7 and bars.available[i10]
    r = reasons_by_pos(pos, bars, mask)
    assert r[9] == {TG_TRUNC}
    # the next OBSERVED row (position 18) is NOT the target of position 10
    assert r[10] == {LB_TRUNC, OP_TRUNC, TG_ABSENT}
    assert r[18] == r[19] == {LB_GAP, OP_GAP}
    assert r[20] == {OP_GAP} and r[21] == set()


def test_gap_inside_lookback_only():
    pos = [p for p in range(26) if p != 10]
    bars, mask = run(pos, params=P(model_lookback_bars=5, max_operator_warmup_bars=2))
    r = reasons_by_pos(pos, bars, mask)
    assert r[9] == {TG_ABSENT}
    assert r[11] == {LB_GAP, OP_GAP}
    assert r[12] == r[13] == r[14] == {LB_GAP}
    assert r[15] == set()


def test_gap_in_target_multi_bar_horizon():
    pos = [p for p in range(20) if p != 10]
    bars, mask = run(pos, params=P(target_horizon_nominal_bars=2))
    r = reasons_by_pos(pos, bars, mask)
    assert r[7] == set()
    assert r[8] == {TG_ABSENT} and r[9] == {TG_ABSENT}
    assert TG_ABSENT not in r[11]


def test_unavailable_bar_is_its_own_layer():
    pos = list(range(12))
    bars, mask = run(pos, {5: None})
    i = 5
    assert not bars.available[i] and not bars.truncated[i] and not bars.interval_complete[i]
    r = reasons_by_pos(pos, bars, mask)
    assert r[4] == {TG_UNAV} and r[5] == {LB_UNAV, OP_UNAV} and r[8] == {OP_UNAV} and r[9] == set()
    assert bars.availability_status_counts == {"RESOLVED": 11, "UNRESOLVED": 1}


def test_operator_with_warmup_512():
    n = 1400
    pos = list(range(n))
    bars, mask = run(pos, {700: 7_199_999}, tq.EligibilityParams())
    r = reasons_by_pos(pos, bars, mask)
    assert r[0] == r[22] == {LB_BEFORE, OP_BEFORE}
    assert r[23] == r[510] == {OP_BEFORE}
    assert r[511] == set() and r[698] == set()
    assert r[699] == {TG_TRUNC}
    assert r[700] == r[723] == {LB_TRUNC, OP_TRUNC}
    assert r[724] == r[1211] == {OP_TRUNC}
    assert r[1212] == set() and r[1399] == {TG_ABSENT}
    assert int(mask.eligible.sum()) == (698 - 511 + 1) + (1398 - 1212 + 1)


# ----------------------------------------------------------- irregular
@pytest.mark.parametrize("seed", range(25))
def test_irregular_dataset_matches_brute_force_reference(seed):
    rng = np.random.default_rng(seed)
    pos, spans = random_dataset(rng)
    L, W, h = int(rng.integers(1, 12)), int(rng.integers(1, 40)), int(rng.integers(1, 4))
    o, c = dataset(pos, spans)
    bars = tq.evaluate_bars(contract(), o, c, observed_sha256=SHA)
    mask = tq.sample_eligibility(bars, P(model_lookback_bars=L, max_operator_warmup_bars=W,
                                         target_horizon_nominal_bars=h))
    ref = reference(o, c, L, W, h)
    assert [mask.reasons(i) for i in range(len(o))] == ref
    assert list(mask.eligible) == [not x for x in ref]
    assert list(mask.support_through) == list(np.cumsum([not x for x in ref]))


@pytest.mark.parametrize("mutate,code", [
    (lambda o, c: (o[:3] + [o[2]] + o[4:], c), "OPEN_TIME_NOT_STRICTLY_INCREASING"),
    (lambda o, c: (o[:5] + [o[5] + 60_000] + o[6:], c[:5] + [o[5] + 60_000 + 10] + c[6:]), "OPEN_TIME_OFF_NOMINAL_GRID"),
    (lambda o, c: (o, c[:4] + [o[4] - 1] + c[5:]), "CLOSE_TIME_BEFORE_OPEN_TIME"),
    (lambda o, c: (o, c[:4] + [o[4] + H] + c[5:]), "CLOSE_TIME_EXCEEDS_NOMINAL_BAR"),
    (lambda o, c: (o[:5] + [o[4] + H // 2] + o[6:], c[:4] + [o[4] + H // 2 + 5] + [o[4] + H // 2 + 10] + c[6:]), "CLOSE_TIME_OVERLAPS_NEXT_BAR"),
])
def test_structurally_invalid_dataset_refused_as_a_whole(mutate, code):
    o, c = dataset(list(range(10)))
    o2, c2 = mutate(list(o), list(c))
    with pytest.raises(tq.StructuralRefusal) as e:
        tq.evaluate_bars(contract(), o2, c2, observed_sha256=SHA)
    assert code in e.value.codes and set(e.value.codes) <= set(tq.STRUCTURAL_REFUSAL_CODES)


def test_contract_level_refusals():
    o, c = dataset(list(range(5)))
    with pytest.raises(tq.StructuralRefusal) as e:
        tq.evaluate_bars(contract(), o, c, observed_sha256="b" * 64)
    assert e.value.codes == ("AVAILABILITY_REFUSED",) and "DATASET_TRANSPLANTED" in str(e.value)
    bc = contract(timestamp_semantics="BAR_CLOSE", information_complete_not_before="TIMESTAMP_ITSELF")
    with pytest.raises(tq.StructuralRefusal) as e:
        tq.evaluate_bars(bc, o, c, observed_sha256=SHA)
    assert e.value.codes == ("AVAILABILITY_CONTRACT_NOT_BAR_OPEN",)
    with pytest.raises(tq.StructuralRefusal):
        tq.evaluate_bars(contract(), [], [], observed_sha256=SHA)


@pytest.mark.parametrize("over,defect", [
    ({"model_lookback_bars": 0}, "INVALID:model_lookback_bars"),
    ({"max_operator_warmup_bars": 2.0}, "INVALID:max_operator_warmup_bars"),
    ({"embargo_bars": -1}, "INVALID:embargo_bars"),
    ({"development_window": "ROLLING"}, "INVALID:development_window"),
    ({"inner_validation_fraction": 1.0}, "INVALID:inner_validation_fraction"),
])
def test_invalid_parameters_refused(over, defect):
    bars, _ = run(list(range(10)))
    p = P(**over)
    assert defect in p.defects()
    with pytest.raises(tq.ParameterRefusal):
        tq.sample_eligibility(bars, p)


# -------------------------------------------------------------- splits
def _roles(positions, spans=None, **kw):
    params = P(model_lookback_bars=3, max_operator_warmup_bars=5, n_rolling_origins=2,
               test_block_bars=10, embargo_bars=2, **kw)
    bars, mask = run(positions, spans, params)
    roles, reports = tq.rolling_origins(bars, mask, params)
    return [dict(zip(positions, r)) for r in roles], reports


def test_split_edges_embargo_purge_and_block_end():
    pos = list(range(60))
    (r1, r2), (o1, o2) = _roles(pos)
    # origin 2: test [50,59], embargo [48,49], dev_end 47
    assert r2[59] == "NOT_ELIGIBLE"  # target after the last row
    assert all(r2[q] == "TEST" for q in range(50, 59))
    assert r2[48] == r2[49] == "EMBARGO"
    assert r2[47] == "DEV_TARGET_CROSSES_EMBARGO_START"
    assert all(r2[q] == "VALIDATION" for q in range(26, 47))
    assert r2[25] == "INNER_TRAIN_PURGED_BEFORE_VALIDATION"
    assert all(r2[q] == "TRAIN" for q in range(4, 25)) and r2[3] == "NOT_ELIGIBLE"
    assert o2["eligible_sample_counts"] == {"development_train": 21, "validation": 21, "test": 9,
                                            "development_region_eligible_before_purge": 44}
    assert o2["test_samples_with_history_before_test_start"] == {"lookback": 2, "operator_window": 4}
    # origin 1: test [40,49]; the sample whose target crosses the block end is excluded
    assert r1[49] == "TEST_TARGET_CROSSES_BLOCK_END"
    assert all(r1[q] == "TEST" for q in range(40, 49))
    assert all(r1[q] == "AFTER_TEST_BLOCK" for q in range(50, 59))
    assert r1[38] == r1[39] == "EMBARGO" and r1[37] == "DEV_TARGET_CROSSES_EMBARGO_START"
    assert r1[20] == "INNER_TRAIN_PURGED_BEFORE_VALIDATION"
    assert o1["eligible_sample_counts"]["development_train"] == 16
    assert o1["eligible_sample_counts"]["validation"] == 16
    for o in (o1, o2):
        assert o["status"] == "SUPPORTED" and sum(o["role_counts"].values()) == len(pos)


def test_inner_validation_embargo_is_an_explicit_input():
    (_, r2), (_, o2) = _roles(list(range(60)), inner_validation_embargo_bars=3)
    # V = 26; embargo [23, 25]; a train target must also stay out of it: q + 1 <= 22
    assert [r2[q] for q in (21, 22, 23, 24, 25)] == ["TRAIN"] + ["INNER_TRAIN_PURGED_BEFORE_VALIDATION"] * 4
    assert o2["eligible_sample_counts"]["development_train"] == 18


def test_truncated_bar_in_embargo_spills_into_test_block():
    pos = list(range(60))
    (r1, r2), (_, o2) = _roles(pos, {49: 7_199_999})
    # anchor moves: position 58 still eligible (operator [54,58]) -> blocks unchanged
    assert r2[48] == r2[49] == "NOT_ELIGIBLE"
    assert all(r2[q] == "NOT_ELIGIBLE" for q in range(50, 54))
    assert all(r2[q] == "TEST" for q in range(54, 59))
    reg = o2["ineligible_by_region"]["TEST_BLOCK"]
    assert reg["ineligible_samples"] == 5
    assert reg["reason_counts_multilabel"] == {LB_TRUNC: 2, OP_TRUNC: 4, TG_ABSENT: 1}
    assert o2["ineligible_by_region"]["EMBARGO"]["reason_counts_multilabel"] == {LB_TRUNC: 1, OP_TRUNC: 1, TG_TRUNC: 1}


def test_no_eligible_samples_origins_not_constructed():
    params = P(max_operator_warmup_bars=50)
    bars, mask = run(list(range(10)), params=params)
    roles, reports = tq.rolling_origins(bars, mask, params)
    assert reports[0]["status"] == "NOT_CONSTRUCTED" and set(roles[0]) == {"NOT_ELIGIBLE"}


@pytest.mark.parametrize("seed", range(10))
def test_origin_roles_respect_boundaries_on_irregular_data(seed):
    rng = np.random.default_rng(100 + seed)
    pos, spans = random_dataset(rng, n_pos=400)
    params = P(model_lookback_bars=4, max_operator_warmup_bars=16, n_rolling_origins=3,
               test_block_bars=40, embargo_bars=4, inner_validation_fraction=0.2)
    bars, mask = run(pos, spans, params)
    roles, reports = tq.rolling_origins(bars, mask, params)
    h = params.target_horizon_nominal_bars
    q_last = int(bars.position[mask.eligible].max())
    for j, (role, rep) in enumerate(zip(roles, reports), start=1):
        B = q_last + h - (3 - j) * 40
        T = B - 39
        p = bars.position
        assert set(role[~mask.eligible]) <= {"NOT_ELIGIBLE"}
        assert ((p[role == "TEST"] >= T) & (p[role == "TEST"] + h <= B)).all()
        assert (p[role == "TRAIN"] + h <= T - 4 - 1).all() and (p[role == "VALIDATION"] + h <= T - 5).all()
        if (role == "VALIDATION").any():
            assert (p[role == "TRAIN"] + h < p[role == "VALIDATION"].min()).all()
        assert sum(rep["role_counts"].values()) == bars.n


# ---------------------------------------------------- prefix invariance
def _tail_mutations(rng, pos, spans, k):
    head, tail = pos[:k], pos[k:]
    last = pos[k - 1]
    yield head, {p: s for p, s in spans.items() if p in head}  # tail removed
    yield head + [p for p in tail if rng.random() > 0.3], spans  # rows deleted -> new gaps
    s2 = dict(spans)
    for p in tail:
        s2[p] = int(rng.integers(0, FULL)) if rng.random() < 0.3 else FULL
    yield pos, s2  # truncations changed
    s3 = dict(spans)
    for p in tail:
        if rng.random() < 0.2:
            s3[p] = None
    yield pos, s3  # availability removed
    ext = sorted(set(pos) | set(range(last + 1, pos[-1] + 60)))
    yield ext, spans  # holes filled + rows appended


@pytest.mark.parametrize("seed", range(20))
def test_prefix_invariance_of_mask_reasons_and_support(seed):
    rng = np.random.default_rng(1000 + seed)
    pos, spans = random_dataset(rng, n_pos=220, p_drop=0.08, p_trunc=0.05)
    L, W, h = int(rng.integers(1, 10)), int(rng.integers(1, 30)), int(rng.integers(1, 4))
    params = P(model_lookback_bars=L, max_operator_warmup_bars=W, target_horizon_nominal_bars=h)
    k = int(rng.integers(len(pos) // 3, len(pos) - 5))
    base_bars, base = run(pos, spans, params)
    protected = [i for i in range(k) if pos[i] + h <= pos[k - 1]]
    assert protected
    changed_somewhere = False
    for mpos, mspans in _tail_mutations(rng, pos, spans, k):
        assert mpos[:k] == pos[:k]
        bars, m = run(mpos, mspans, params)
        for i in protected:
            assert m.eligible[i] == base.eligible[i]
            assert m.reasons(i) == base.reasons(i)
            assert m.support_through[i] == base.support_through[i]
        n = min(len(mpos), len(pos))
        changed_somewhere |= (len(mpos) != len(pos)) or bool((m.reason_bits[:n] != base.reason_bits[:n]).any())
    assert changed_somewhere  # the mutations were not vacuous


def test_prefix_invariance_negative_control_target_across_the_cut():
    # a sample whose target lies AT the cut may change: that is why it is excluded above
    pos = list(range(30))
    _, base = run(pos)
    _, cut = run(pos[:21])  # row at position 20 becomes the last row
    assert base.reasons(19) == () and cut.reasons(19) == ()
    assert base.reasons(20) == () and cut.reasons(20) == (TG_ABSENT,)


# --------------------------------------------------------- materializer
def _real(s):
    return (mat.FD_ROOT if s.root_id == "financial-data" else mat.DEFAULT_PREDICTOR_ROOT) / s.relative_path


DATA_PRESENT = all(_real(s).is_file() for s in mat.SOURCES)
needs_data = pytest.mark.skipif(not DATA_PRESENT, reason="local data lake not present")
V1_PATH = ROOT / "features/census/ETH_H4_TEMPORAL_CONTRACT.v1.json"
V1_SHA = "6e3a0c8d67dd2ec64dcad8bd7bb7ca0154dd514b43e9e2990de83578cc794254"


def _mirror(tmp_path, corrupt):
    roots = {"financial-data": tmp_path / "financial-data", "predictor": tmp_path / "predictor"}
    for s in mat.SOURCES:
        dst = roots[s.root_id] / s.relative_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        if s.name == corrupt:
            data = bytearray(_real(s).read_bytes())
            data[len(data) // 2] ^= 0x01
            dst.write_bytes(bytes(data))
        else:
            os.symlink(_real(s), dst)
    return roots


@needs_data
@pytest.mark.parametrize("corrupt", [s.name for s in mat.SOURCES])
def test_materializer_refuses_digest_mismatch_on_tmp_copy(tmp_path, corrupt):
    roots = _mirror(tmp_path, corrupt)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(mat.DigestMismatch):
        mat.main(["--financial-data-root", str(roots["financial-data"]),
                  "--predictor-root", str(roots["predictor"]), "--out-dir", str(out)])
    assert list(out.iterdir()) == []
    for s in mat.SOURCES:
        assert hashlib.sha256(_real(s).read_bytes()).hexdigest() == s.expected_sha256


@needs_data
def test_v1_json_byte_identical_before_and_after_materializing(tmp_path):
    before = V1_PATH.read_bytes()
    assert hashlib.sha256(before).hexdigest() == V1_SHA
    mat.main(["--out-dir", str(tmp_path)])
    after = V1_PATH.read_bytes()
    assert after == before and hashlib.sha256(after).hexdigest() == V1_SHA
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [mat.SCHEMA_NAME, mat.MASK_NAME, mat.CONTRACT_NAME])


@needs_data
def test_materializer_opens_each_file_once_and_parses_hashed_bytes(monkeypatch):
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    watched = {str(_real(s).resolve()): s.name for s in mat.SOURCES}
    opens: dict[str, int] = {}
    orig_open = builtins.open

    def counting_open(file, *a, **k):
        try:
            key = str(Path(file).resolve())
        except TypeError:
            key = None
        if key in watched:
            opens[watched[key]] = opens.get(watched[key], 0) + 1
        return orig_open(file, *a, **k)

    parsed = {"csv": [], "parquet": []}
    orig_read_csv, orig_read_table = pd.read_csv, pq.read_table

    def spy_read_csv(buf, *a, **k):
        assert isinstance(buf, io.BytesIO)
        parsed["csv"].append(hashlib.sha256(buf.getvalue()).hexdigest())
        return orig_read_csv(buf, *a, **k)

    def spy_read_table(src, *a, **k):
        assert isinstance(src, pa.BufferReader)
        src.seek(0)
        parsed["parquet"].append(hashlib.sha256(src.read()).hexdigest())
        src.seek(0)
        return orig_read_table(src, *a, **k)

    monkeypatch.setattr(builtins, "open", counting_open)
    monkeypatch.setattr(mat.pd, "read_csv", spy_read_csv)
    monkeypatch.setattr(mat.pq, "read_table", spy_read_table)
    doc, _, _ = mat.materialize()
    assert opens == {s.name: 1 for s in mat.SOURCES}
    b = doc["bound_files"]
    assert parsed["csv"] == [b["model_ready_csv"]["sha256"]]
    assert parsed["parquet"] == [b["candidate_source_parquet"]["sha256"]]


# ------------------------------------------------- published artifacts
V2_PATH = ROOT / "features/census/ETH_H4_TEMPORAL_CONTRACT.v2.json"
MASK_PATH = ROOT / "features/census/ETH_H4_SAMPLE_ELIGIBILITY_MASK.v1.parquet"
SCHEMA_PATH = ROOT / "features/census/TEMPORAL_QUALITY_SCHEMA.v1.json"
needs_artifacts = pytest.mark.skipif(not (V2_PATH.is_file() and MASK_PATH.is_file()),
                                     reason="v2 not materialized")


@needs_artifacts
def test_published_v2_self_digest_schema_mask_binding_and_no_home_paths():
    import pyarrow.parquet as pq
    for p in (V2_PATH, SCHEMA_PATH):
        text = p.read_text(encoding="utf-8")
        assert "/home/" not in text
        d = json.loads(text)
        assert d["self_digest"]["value"] == mat.self_digest(d)["value"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert {k: v for k, v in schema.items() if k != "self_digest"} == tq.schema_document()
    doc = json.loads(V2_PATH.read_text(encoding="utf-8"))
    assert doc["schema"]["self_digest"] == schema["self_digest"]["value"]
    assert doc["supersedes"]["sha256"] == V1_SHA == hashlib.sha256(V1_PATH.read_bytes()).hexdigest()
    raw = MASK_PATH.read_bytes()
    ma = doc["mask_artifact"]
    assert hashlib.sha256(raw).hexdigest() == ma["sha256"] and len(raw) == ma["bytes"]
    table = pq.read_table(MASK_PATH)
    assert table.column_names == ma["columns"] and table.num_rows == ma["rows"]
    assert mat.content_digest(table) == ma["content_sha256"]
    t = table.to_pydict()
    for e, rs in zip(t["sample_eligible"], t["ineligibility_reasons"]):
        assert e == (rs == []) and set(rs) <= set(tq.SAMPLE_REASON_CODES)
    for j in range(1, doc["parameters"]["n_rolling_origins"] + 1):
        assert set(t[f"origin_{j}_role"]) <= set(tq.ROLE_CODES)


@needs_artifacts
@needs_data
def test_published_v2_reproduces_and_pins_measured_counts():
    doc = json.loads(V2_PATH.read_text(encoding="utf-8"))
    fresh, _, _ = mat.materialize()
    strip = lambda d: {k: v for k, v in d.items() if k not in ("self_digest", "mask_artifact")}  # noqa: E731
    assert strip(fresh) == strip(doc)
    assert fresh["mask_artifact"]["content_sha256"] == doc["mask_artifact"]["content_sha256"]
    assert doc["parameters"] == tq.EligibilityParams().to_dict()
    b, s = doc["bar_layer_summary"], doc["sample_summary"]
    assert b["rows"] == s["total"] == 18085
    assert b["truncated"] == 20 and b["next_step_state_counts"]["GAP"] == 8
    assert b["available"] == 18085
    assert s["eligible"] + s["ineligible"] == 18085
    assert doc["v1_cross_check"]["truncated_open_times_equal_v1"] and doc["v1_cross_check"]["gap_positions_equal_v1"]
    assert doc["gates"]["E5a"]["status"] == "OPEN" and doc["gates"]["E5b"]["status"] == "CLOSED"
    assert len(doc["rolling_origins"]["origins"]) == 5
