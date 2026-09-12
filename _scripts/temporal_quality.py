"""C98 temporal quality semantics (order 2026-09-12). Successor layer over v1.

v1 (``temporal_availability``) answers ONE question per bar: when could its
information be complete (the causal information bound). It says nothing
about whether consecutive rows form a regular nominal horizon. This module
keeps that answer untouched and adds three further, SEPARATE layers:

1. availability  -- v1's causal bound, per bar, reused verbatim
                    (``temporal_availability.causal_information_bound``).
2. completeness  -- of the bar's interval: a bar is TRUNCATED when
                    ``close_time - open_time`` is shorter than the nominal
                    span (nominal seconds minus the 1 ms inclusive-close
                    convention). Independent of availability.
3. regularity    -- of the step to the next observed bar: regular iff
                    ``next_open == open + nominal``; a longer step is a GAP
                    that leaves nominal intervals absent. The last row's step
                    is UNKNOWN (no next row observed).
4. eligibility   -- of a SAMPLE (forecast origin row t) for a fixed horizon:
                    every nominal interval of its lookback, its operator
                    window and its target must be PRESENT as a row, AVAILABLE
                    and COMPLETE. Nothing is interpolated or filled.
                    ``next bar`` is the next NOMINAL interval
                    (open_t + nominal); when that interval has no row the
                    target is absent -- the next observed row after a hole is
                    never used in its place.

Window definitions for origin position q (integer nominal grid index):

* lookback           positions [q - L + 1, q]   (L = model_lookback_bars)
* operator window    positions [q - W + 1, q]   (W = max_operator_warmup_bars)
* target             positions [q + 1, q + h]   (h = target_horizon_nominal_bars)

Prefix invariance: a sample's eligibility, reasons and cumulative support
depend only on rows whose open time lies in [open_t - (max(L, W) - 1) *
nominal, open_t + h * nominal]. Absence of the target is reported with ONE
code whether the missing interval sits in a hole or after the last row, so
that appending rows can never relabel a sample whose target lies before
them. A dataset that is STRUCTURALLY invalid (non-increasing or off-grid
open times, contradictory close times) is refused as a whole; that
refusal is the single documented exception to prefix invariance.

Rolling-origin assignment (NOT prefix-invariant by construction; it is
anchored at the last eligible sample) is defined in ``rolling_origins``.

Pure functions over arrays/mappings. No I/O.
"""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

_HERE = str(Path(__file__).resolve().parent)
if "temporal_availability" not in sys.modules and _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import temporal_availability as ta  # noqa: E402

SCHEMA_ID = "financial_data.temporal_quality_schema.v1"

# ------------------------------------------------------------------ codes
STRUCTURAL_REFUSAL_CODES = (
    "EMPTY_DATASET",
    "LENGTH_MISMATCH",
    "AVAILABILITY_CONTRACT_INVALID",
    "AVAILABILITY_CONTRACT_NOT_BAR_OPEN",
    "OPEN_TIME_ABSENT",
    "OPEN_TIME_NOT_STRICTLY_INCREASING",
    "OPEN_TIME_OFF_NOMINAL_GRID",
    "CLOSE_TIME_BEFORE_OPEN_TIME",
    "CLOSE_TIME_EXCEEDS_NOMINAL_BAR",
    "CLOSE_TIME_OVERLAPS_NEXT_BAR",
    "AVAILABILITY_REFUSED",
)

# Order is the bit order of ``reason_bits`` and the order reasons are listed.
SAMPLE_REASON_CODES = (
    "LOOKBACK_BEFORE_FIRST_BAR",
    "LOOKBACK_CROSSES_GAP",
    "LOOKBACK_CONTAINS_TRUNCATED_BAR",
    "LOOKBACK_CONTAINS_UNAVAILABLE_BAR",
    "OPERATOR_WINDOW_BEFORE_FIRST_BAR",
    "OPERATOR_WINDOW_CROSSES_GAP",
    "OPERATOR_WINDOW_CONTAINS_TRUNCATED_BAR",
    "OPERATOR_WINDOW_CONTAINS_UNAVAILABLE_BAR",
    "TARGET_NOMINAL_BAR_ABSENT",
    "TARGET_CONTAINS_TRUNCATED_BAR",
    "TARGET_CONTAINS_UNAVAILABLE_BAR",
)
_BIT = {c: 1 << i for i, c in enumerate(SAMPLE_REASON_CODES)}
TRUNCATION_REASONS = tuple(c for c in SAMPLE_REASON_CODES if c.endswith("TRUNCATED_BAR"))
GAP_REASONS = ("LOOKBACK_CROSSES_GAP", "OPERATOR_WINDOW_CROSSES_GAP", "TARGET_NOMINAL_BAR_ABSENT")
HISTORY_REASONS = ("LOOKBACK_BEFORE_FIRST_BAR", "OPERATOR_WINDOW_BEFORE_FIRST_BAR")

ROLE_CODES = (
    "TRAIN",
    "VALIDATION",
    "TEST",
    "NOT_ELIGIBLE",
    "INNER_TRAIN_PURGED_BEFORE_VALIDATION",
    "DEV_TARGET_CROSSES_EMBARGO_START",
    "EMBARGO",
    "TEST_TARGET_CROSSES_BLOCK_END",
    "AFTER_TEST_BLOCK",
)
REGION_CODES = ("DEVELOPMENT", "EMBARGO", "TEST_BLOCK", "AFTER_TEST_BLOCK")
ORIGIN_STATUSES = ("SUPPORTED", "INSUFFICIENT_SUPPORT", "NOT_CONSTRUCTED")
ORIGIN_STATUS_REASONS = (
    "NO_ELIGIBLE_SAMPLES",
    "DEVELOPMENT_REGION_BEFORE_FIRST_BAR",
    "NO_TRAIN_SAMPLES",
    "NO_VALIDATION_SAMPLES",
    "NO_TEST_SAMPLES",
)
STEP_STATES = ("REGULAR", "GAP", "UNKNOWN_LAST_ROW")
DEVELOPMENT_WINDOWS = ("EXPANDING",)


class StructuralRefusal(ValueError):
    def __init__(self, codes: Sequence[str], detail: str = ""):
        self.codes = tuple(codes)
        super().__init__(f"{list(self.codes)} {detail}".strip())


class ParameterRefusal(ValueError):
    def __init__(self, defects: Sequence[str]):
        self.defects = tuple(defects)
        super().__init__(str(list(self.defects)))


# ------------------------------------------------------------- parameters
@dataclass(frozen=True)
class EligibilityParams:
    """Explicit inputs. Defaults are the current design draft's values,
    except ``inner_validation_embargo_bars`` which the draft does not state
    (0 = purge only: an inner-train target may not enter validation)."""
    model_lookback_bars: int = 24
    max_operator_warmup_bars: int = 512
    target_horizon_nominal_bars: int = 1
    n_rolling_origins: int = 5
    test_block_bars: int = 1000
    embargo_bars: int = 24
    development_window: str = "EXPANDING"
    inner_validation_fraction: float = 0.10
    inner_validation_embargo_bars: int = 0

    def defects(self) -> tuple[str, ...]:
        d = []
        for k in ("model_lookback_bars", "max_operator_warmup_bars",
                  "target_horizon_nominal_bars", "n_rolling_origins", "test_block_bars"):
            v = getattr(self, k)
            if not ta._is_int(v) or v < 1:
                d.append(f"INVALID:{k}")
        for k in ("embargo_bars", "inner_validation_embargo_bars"):
            v = getattr(self, k)
            if not ta._is_int(v) or v < 0:
                d.append(f"INVALID:{k}")
        if self.development_window not in DEVELOPMENT_WINDOWS:
            d.append("INVALID:development_window")
        f = self.inner_validation_fraction
        if isinstance(f, bool) or not isinstance(f, (int, float)) or not (0 < f < 1):
            d.append("INVALID:inner_validation_fraction")
        return tuple(d)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _iso(ms: int) -> str:
    t = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(ms))
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ------------------------------------------------------------- bar layers
@dataclass(frozen=True)
class BarLayers:
    open_ms: np.ndarray            # int64
    close_ms: np.ndarray           # int64, meaningless where ~close_present
    close_present: np.ndarray      # bool
    position: np.ndarray           # int64 nominal grid index
    available: np.ndarray          # bool  (v1 causal bound RESOLVED)
    interval_complete: np.ndarray  # bool
    truncated: np.ndarray          # bool
    next_step_state: np.ndarray    # int8: 0 REGULAR, 1 GAP, 2 UNKNOWN_LAST_ROW
    missing_nominal_bars_after: np.ndarray  # int64, -1 for the last row
    nominal_ms: int
    full_span_ms: int
    grid_anchor_ms: int
    availability_status_counts: dict[str, int]

    @property
    def n(self) -> int:
        return int(len(self.open_ms))


def evaluate_bars(contract: Mapping[str, Any], open_ms: Sequence[Any],
                  close_ms: Sequence[Any], *, observed_sha256: str | None,
                  grid_anchor_ms: int = 0) -> BarLayers:
    """Layers 1-3 for every row. Raises StructuralRefusal on a dataset that
    cannot carry a nominal horizon at all."""
    defects = ta.validate_contract(contract)
    if defects:
        raise StructuralRefusal(["AVAILABILITY_CONTRACT_INVALID"], str(defects))
    if contract["timestamp_semantics"] != "BAR_OPEN":
        raise StructuralRefusal(["AVAILABILITY_CONTRACT_NOT_BAR_OPEN"])
    if len(open_ms) != len(close_ms):
        raise StructuralRefusal(["LENGTH_MISMATCH"])
    if len(open_ms) == 0:
        raise StructuralRefusal(["EMPTY_DATASET"])
    nominal = int(contract["nominal_bar_seconds"]) * 1000
    full_span = nominal - (1 if contract["bar_close_time_convention"]
                           == "INCLUSIVE_LAST_MILLISECOND" else 0)
    opens = [ta._ms(v) for v in open_ms]
    if any(v is None for v in opens):
        raise StructuralRefusal(["OPEN_TIME_ABSENT"])
    closes = [ta._ms(v) for v in close_ms]
    o = np.asarray(opens, dtype=np.int64)
    present = np.array([v is not None for v in closes], dtype=bool)
    c = np.array([v if v is not None else 0 for v in closes], dtype=np.int64)

    codes = []
    step = np.diff(o)
    if (step <= 0).any():
        codes.append("OPEN_TIME_NOT_STRICTLY_INCREASING")
    if ((o - int(grid_anchor_ms)) % nominal != 0).any():
        codes.append("OPEN_TIME_OFF_NOMINAL_GRID")
    span = c - o
    if (present & (span < 0)).any():
        codes.append("CLOSE_TIME_BEFORE_OPEN_TIME")
    if (present & (span > full_span)).any():
        codes.append("CLOSE_TIME_EXCEEDS_NOMINAL_BAR")
    if (present[:-1] & (c[:-1] >= o[1:])).any():
        codes.append("CLOSE_TIME_OVERLAPS_NEXT_BAR")
    if codes:
        raise StructuralRefusal(codes)

    # layer 1: v1 availability, verbatim, row by row
    n = len(o)
    available = np.zeros(n, dtype=bool)
    status_counts: dict[str, int] = {}
    refused: dict[str, int] = {}
    for i in range(n):
        row = {"timestamp_ms": int(o[i]),
               "close_time_ms": int(c[i]) if present[i] else None,
               "next_timestamp_ms": int(o[i + 1]) if i + 1 < n else None}
        b = ta.causal_information_bound(contract, row, observed_sha256=observed_sha256)
        status_counts[b.status] = status_counts.get(b.status, 0) + 1
        if b.status == "REFUSED":
            for r in b.reasons:
                refused[r] = refused.get(r, 0) + 1
        available[i] = b.status == "RESOLVED"
    if refused:
        raise StructuralRefusal(["AVAILABILITY_REFUSED"], str(dict(sorted(refused.items()))))

    # layer 2: completeness (independent of availability)
    complete = present & (span == full_span)
    truncated = present & (span < full_span)
    # layer 3: regularity of the step to the next observed row
    state = np.full(n, 2, dtype=np.int8)
    state[:-1] = np.where(step == nominal, 0, 1)
    missing = np.full(n, -1, dtype=np.int64)
    missing[:-1] = step // nominal - 1
    return BarLayers(o, c, present, (o - int(grid_anchor_ms)) // nominal, available,
                     complete, truncated, state, missing, nominal, full_span,
                     int(grid_anchor_ms), dict(sorted(status_counts.items())))


# ------------------------------------------------------ sample eligibility
@dataclass(frozen=True)
class SampleMask:
    eligible: np.ndarray        # bool
    reason_bits: np.ndarray     # int32
    support_through: np.ndarray  # int64 cumulative eligible count up to and including row

    def reasons(self, i: int) -> tuple[str, ...]:
        b = int(self.reason_bits[i])
        return tuple(c for c in SAMPLE_REASON_CODES if b & _BIT[c])


def _grid(bars: BarLayers):
    g = bars.position - bars.position[0]
    size = int(g[-1]) + 1
    def cs(flags):
        a = np.zeros(size, dtype=np.int64)
        a[g] = flags.astype(np.int64)
        return np.concatenate([[0], np.cumsum(a)])
    return g, size, cs(np.ones(bars.n, dtype=bool)), cs(bars.truncated), cs(~bars.available)


def sample_eligibility(bars: BarLayers, params: EligibilityParams) -> SampleMask:
    d = params.defects()
    if d:
        raise ParameterRefusal(d)
    g, size, cs_p, cs_t, cs_u = _grid(bars)
    bits = np.zeros(bars.n, dtype=np.int64)

    def window(lo, hi, prefix):
        """Backward window [lo, hi] on the grid, hi always a present row."""
        before = lo < 0
        lo_c = np.maximum(lo, 0)
        length = hi - lo_c + 1
        gap = (cs_p[hi + 1] - cs_p[lo_c]) < length
        trunc = (cs_t[hi + 1] - cs_t[lo_c]) > 0
        unav = (cs_u[hi + 1] - cs_u[lo_c]) > 0
        out = np.zeros(bars.n, dtype=np.int64)
        out |= np.where(before, _BIT[f"{prefix}_BEFORE_FIRST_BAR"], 0)
        out |= np.where(gap, _BIT[f"{prefix}_CROSSES_GAP"], 0)
        out |= np.where(trunc, _BIT[f"{prefix}_CONTAINS_TRUNCATED_BAR"], 0)
        out |= np.where(unav, _BIT[f"{prefix}_CONTAINS_UNAVAILABLE_BAR"], 0)
        return out

    bits |= window(g - params.model_lookback_bars + 1, g, "LOOKBACK")
    bits |= window(g - params.max_operator_warmup_bars + 1, g, "OPERATOR_WINDOW")
    h = params.target_horizon_nominal_bars
    lo, hi = g + 1, g + h
    beyond = hi > size - 1
    hi_c = np.minimum(hi, size - 1)
    length = np.maximum(hi_c - lo + 1, 0)
    lo_c = np.minimum(lo, size)
    hi_idx = np.maximum(hi_c + 1, lo_c)
    absent = beyond | ((cs_p[hi_idx] - cs_p[lo_c]) < length)
    bits |= np.where(absent, _BIT["TARGET_NOMINAL_BAR_ABSENT"], 0)
    bits |= np.where((cs_t[hi_idx] - cs_t[lo_c]) > 0, _BIT["TARGET_CONTAINS_TRUNCATED_BAR"], 0)
    bits |= np.where((cs_u[hi_idx] - cs_u[lo_c]) > 0, _BIT["TARGET_CONTAINS_UNAVAILABLE_BAR"], 0)
    eligible = bits == 0
    return SampleMask(eligible, bits.astype(np.int32), np.cumsum(eligible).astype(np.int64))


def _only_history_or_end(bars: BarLayers, mask: SampleMask, h: int = 1) -> np.ndarray:
    """Ineligible samples whose ONLY reasons are the dataset's edges: history
    before the first bar, and/or a target absent because it lies after the
    last row (h taken as the smallest horizon that reaches past the end)."""
    rb = mask.reason_bits.astype(np.int64)
    hist = _BIT["LOOKBACK_BEFORE_FIRST_BAR"] | _BIT["OPERATOR_WINDOW_BEFORE_FIRST_BAR"]
    tgt = _BIT["TARGET_NOMINAL_BAR_ABSENT"]
    beyond_end = bars.position + h > bars.position[-1]
    return (~mask.eligible) & ((rb & ~(hist | tgt)) == 0) & (((rb & tgt) == 0) | beyond_end)


def summarize(bars: BarLayers, mask: SampleMask) -> dict[str, Any]:
    reason_counts = {c: int(((mask.reason_bits & _BIT[c]) != 0).sum()) for c in SAMPLE_REASON_CODES}
    sets: dict[str, int] = {}
    for b, k in zip(*np.unique(mask.reason_bits[~mask.eligible], return_counts=True)):
        key = "|".join(c for c in SAMPLE_REASON_CODES if int(b) & _BIT[c])
        sets[key] = int(k)
    rb = mask.reason_bits
    has = lambda codes: (rb & sum(_BIT[c] for c in codes)) != 0  # noqa: E731
    inel = ~mask.eligible
    return {
        "bars": {
            "rows": bars.n,
            "availability_status_counts": bars.availability_status_counts,
            "available": int(bars.available.sum()),
            "interval_complete": int(bars.interval_complete.sum()),
            "truncated": int(bars.truncated.sum()),
            "close_time_absent": int((~bars.close_present).sum()),
            "next_step_state_counts": {s: int((bars.next_step_state == i).sum())
                                       for i, s in enumerate(STEP_STATES)},
            "missing_nominal_intervals_inside_span": int(bars.missing_nominal_bars_after[:-1].sum()),
            "nominal_positions_spanned": int(bars.position[-1] - bars.position[0] + 1),
        },
        "samples": {
            "total": bars.n,
            "eligible": int(mask.eligible.sum()),
            "ineligible": int(inel.sum()),
            "reason_counts_multilabel": reason_counts,
            "reason_set_counts": dict(sorted(sets.items())),
            "ineligible_with_any_truncation_reason": int((inel & has(TRUNCATION_REASONS)).sum()),
            # TARGET_NOMINAL_BAR_ABSENT also covers a target after the last row,
            # so these two include dataset-end samples; event_propagation does not.
            "ineligible_with_any_gap_or_absent_target_reason": int((inel & has(GAP_REASONS)).sum()),
            "ineligible_with_truncation_gap_or_absent_target_reason": int((inel & has(TRUNCATION_REASONS + GAP_REASONS)).sum()),
            "ineligible_only_by_history_or_dataset_end": int(_only_history_or_end(bars, mask).sum()),
        },
    }


def event_propagation(bars: BarLayers, mask: SampleMask,
                      params: EligibilityParams) -> dict[str, Any]:
    """Which samples each truncated bar and each gap renders ineligible."""
    L, W, h = (params.model_lookback_bars, params.max_operator_warmup_bars,
               params.target_horizon_nominal_bars)
    pos = bars.position

    def rows_in(lo, hi):
        return np.flatnonzero((pos >= lo) & (pos <= hi))

    def describe(sel_by_window):
        union = np.unique(np.concatenate(list(sel_by_window.values()))) if sel_by_window else np.array([], int)
        out = {f"samples_via_{k}": int(len(v)) for k, v in sel_by_window.items()}
        out["samples_affected_union"] = int(len(union))
        if len(union):
            out["first_affected_open_time_utc"] = _iso(bars.open_ms[union[0]])
            out["last_affected_open_time_utc"] = _iso(bars.open_ms[union[-1]])
        return out, union

    trunc_events, gap_events = [], []
    all_t, all_g = [], []
    for r in np.flatnonzero(bars.truncated):
        q = int(pos[r])
        info, u = describe({"lookback": rows_in(q, q + L - 1),
                            "operator_window": rows_in(q, q + W - 1),
                            "target": rows_in(q - h, q - 1)})
        all_t.append(u)
        trunc_events.append({"row_index": int(r), "open_time_utc": _iso(bars.open_ms[r]),
                             "span_ms": int(bars.close_ms[r] - bars.open_ms[r]),
                             "followed_by_gap": bool(bars.next_step_state[r] == 1), **info})
    for r in np.flatnonzero(bars.next_step_state == 1):
        a, b = int(pos[r]) + 1, int(pos[r + 1]) - 1
        info, u = describe({"lookback": rows_in(a, b + L - 1),
                            "operator_window": rows_in(a, b + W - 1),
                            "target": rows_in(a - h, b - 1)})
        all_g.append(u)
        gap_events.append({"previous_row_index": int(r),
                           "previous_open_time_utc": _iso(bars.open_ms[r]),
                           "next_open_time_utc": _iso(bars.open_ms[r + 1]),
                           "missing_nominal_intervals": int(b - a + 1),
                           "previous_bar_truncated": bool(bars.truncated[r]), **info})
    ut = np.unique(np.concatenate(all_t)) if all_t else np.array([], int)
    ug = np.unique(np.concatenate(all_g)) if all_g else np.array([], int)
    both = np.union1d(ut, ug)
    assert not mask.eligible[both].any(), "an affected sample was marked eligible"
    return {
        "truncated_bar_events": trunc_events,
        "gap_events": gap_events,
        "samples_affected_by_any_truncated_bar": int(len(ut)),
        "samples_affected_by_any_gap": int(len(ug)),
        "samples_affected_by_truncation_and_gap": int(len(np.intersect1d(ut, ug))),
        "samples_affected_by_truncation_or_gap": int(len(both)),
    }


# --------------------------------------------------------- rolling origins
def rolling_origins(bars: BarLayers, mask: SampleMask,
                    params: EligibilityParams) -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    """Deterministic rolling-origin assignment on the eligible timeline.

    Rule (positions are nominal grid indices, all blocks in NOMINAL bars):
    * Anchor: q_last = position of the LAST eligible sample; the last test
      block ends at B_n = q_last + h (the last eligible sample's target).
    * Test block j (j = 1..n, oldest first): B_j = B_n - (n - j) * test_block,
      T_j = B_j - test_block + 1; positions [T_j, B_j]; blocks are
      contiguous and non-overlapping.
    * Embargo: positions [T_j - embargo, T_j - 1].
    * Development region (EXPANDING): positions [first bar, dev_end],
      dev_end = T_j - embargo - 1.
    * TEST: eligible, T_j <= q and q + h <= B_j. An eligible q in the block
      whose target passes B_j is TEST_TARGET_CROSSES_BLOCK_END.
    * EMBARGO: eligible q inside the embargo.
    * DEV_TARGET_CROSSES_EMBARGO_START: eligible q <= dev_end, q + h > dev_end.
    * D = remaining eligible development samples, ordered. n_val =
      floor(Fraction(str(inner_validation_fraction)) * |D|); VALIDATION is
      the last n_val of D, starting at position V. TRAIN: q + h <= V - 1 -
      inner_validation_embargo_bars; other D samples before V are
      INNER_TRAIN_PURGED_BEFORE_VALIDATION.
    * Test samples' lookback/operator windows MAY reach before T_j (causal
      past); they are counted, not excluded.
    * Every ineligible sample is NOT_ELIGIBLE in every origin; q > B_j is
      AFTER_TEST_BLOCK.
    """
    d = params.defects()
    if d:
        raise ParameterRefusal(d)
    n_o, tb, emb = params.n_rolling_origins, params.test_block_bars, params.embargo_bars
    h, L, W = (params.target_horizon_nominal_bars, params.model_lookback_bars,
               params.max_operator_warmup_bars)
    pos, elig = bars.position, mask.eligible
    to_ms = lambda q: int(bars.grid_anchor_ms + int(q) * bars.nominal_ms)  # noqa: E731
    roles_out, reports = [], []
    if not elig.any():
        for j in range(1, n_o + 1):
            roles_out.append(np.where(elig, "", "NOT_ELIGIBLE").astype(object))
            reports.append({"origin": j, "status": "NOT_CONSTRUCTED",
                            "status_reasons": ["NO_ELIGIBLE_SAMPLES"]})
        return roles_out, reports
    q_last = int(pos[elig].max())
    B_n = q_last + h
    first = int(pos[0])
    for j in range(1, n_o + 1):
        B = B_n - (n_o - j) * tb
        T = B - tb + 1
        dev_end = T - emb - 1
        role = np.full(bars.n, "AFTER_TEST_BLOCK", dtype=object)
        region = np.full(bars.n, "AFTER_TEST_BLOCK", dtype=object)
        in_test = (pos >= T) & (pos <= B)
        in_emb = (pos > dev_end) & (pos < T)
        in_dev = pos <= dev_end
        region[in_test], region[in_emb], region[in_dev] = "TEST_BLOCK", "EMBARGO", "DEVELOPMENT"
        role[in_test & elig & (pos + h <= B)] = "TEST"
        role[in_test & elig & (pos + h > B)] = "TEST_TARGET_CROSSES_BLOCK_END"
        role[in_emb & elig] = "EMBARGO"
        role[in_dev & elig & (pos + h > dev_end)] = "DEV_TARGET_CROSSES_EMBARGO_START"
        D = np.flatnonzero(in_dev & elig & (pos + h <= dev_end))
        n_val = int((Fraction(str(params.inner_validation_fraction)) * len(D)).__floor__())
        V = None
        if n_val > 0:
            val = D[-n_val:]
            V = int(pos[val[0]])
            role[val] = "VALIDATION"
            pre = D[:-n_val]
            ok = pos[pre] + h <= V - 1 - params.inner_validation_embargo_bars
            role[pre[ok]] = "TRAIN"
            role[pre[~ok]] = "INNER_TRAIN_PURGED_BEFORE_VALIDATION"
        else:
            role[D] = "TRAIN"
        role[~elig] = "NOT_ELIGIBLE"
        counts = {r: int((role == r).sum()) for r in ROLE_CODES}
        reasons = []
        if dev_end < first:
            reasons.append("DEVELOPMENT_REGION_BEFORE_FIRST_BAR")
        if counts["TRAIN"] == 0:
            reasons.append("NO_TRAIN_SAMPLES")
        if counts["VALIDATION"] == 0:
            reasons.append("NO_VALIDATION_SAMPLES")
        if counts["TEST"] == 0:
            reasons.append("NO_TEST_SAMPLES")
        by_region = {}
        for rg in REGION_CODES:
            sel = (region == rg) & ~elig
            by_region[rg] = {c: int((sel & ((mask.reason_bits & _BIT[c]) != 0)).sum())
                             for c in SAMPLE_REASON_CODES}
            by_region[rg] = {"ineligible_samples": int(sel.sum()),
                             "reason_counts_multilabel": {k: v for k, v in by_region[rg].items() if v}}
        test = role == "TEST"
        reports.append({
            "origin": j,
            "status": "INSUFFICIENT_SUPPORT" if reasons else "SUPPORTED",
            "status_reasons": reasons,
            "development_region": {
                "first_open_time_utc": _iso(bars.open_ms[0]),
                "last_nominal_open_time_utc": _iso(to_ms(dev_end)),
                "nominal_positions": max(dev_end - first + 1, 0),
                "rows_present": int(in_dev.sum()),
                "validation_first_open_time_utc": _iso(to_ms(V)) if V is not None else None},
            "embargo": {"first_nominal_open_time_utc": _iso(to_ms(dev_end + 1)),
                        "last_nominal_open_time_utc": _iso(to_ms(T - 1)),
                        "nominal_positions": emb, "rows_present": int(in_emb.sum())},
            "test_block": {"first_nominal_open_time_utc": _iso(to_ms(T)),
                           "last_nominal_open_time_utc": _iso(to_ms(B)),
                           "nominal_positions": tb, "rows_present": int(in_test.sum()),
                           "nominal_positions_absent": int(tb - in_test.sum())},
            "eligible_sample_counts": {
                "development_train": counts["TRAIN"],
                "validation": counts["VALIDATION"],
                "test": counts["TEST"],
                "development_region_eligible_before_purge": int((in_dev & elig).sum())},
            "role_counts": counts,
            "ineligible_by_region": by_region,
            "test_samples_with_history_before_test_start": {
                "lookback": int((test & (pos - L + 1 < T)).sum()),
                "operator_window": int((test & (pos - W + 1 < T)).sum())},
        })
        roles_out.append(role)
    return roles_out, reports


# ----------------------------------------------------------------- schema
def schema_document() -> dict[str, Any]:
    """TEMPORAL_QUALITY_SCHEMA.v1, built from the constants the code enforces."""
    p = EligibilityParams()
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "Temporal quality contract and sample eligibility mask (C98-C99)",
        "type": "object",
        "required": ["artifact", "supersedes", "availability_contract", "parameters",
                     "layers", "bar_layer_summary", "sample_summary", "rolling_origins",
                     "mask_artifact", "self_digest"],
        "properties": {
            "parameters": {
                "type": "object",
                "required": list(p.to_dict()),
                "properties": {
                    "model_lookback_bars": {"type": "integer", "minimum": 1},
                    "max_operator_warmup_bars": {"type": "integer", "minimum": 1},
                    "target_horizon_nominal_bars": {"type": "integer", "minimum": 1},
                    "n_rolling_origins": {"type": "integer", "minimum": 1},
                    "test_block_bars": {"type": "integer", "minimum": 1},
                    "embargo_bars": {"type": "integer", "minimum": 0},
                    "development_window": {"enum": list(DEVELOPMENT_WINDOWS)},
                    "inner_validation_fraction": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
                    "inner_validation_embargo_bars": {"type": "integer", "minimum": 0}},
                "x-defaults": p.to_dict()},
            "supersedes": {"type": "object", "required": ["relative_path", "sha256"],
                           "description": "The v1 availability contract, preserved byte for byte and bound by digest."},
            "mask_artifact": {"type": "object", "required": ["relative_path", "sha256", "rows", "columns"]},
        },
        "x-layers": {
            "availability": "v1 causal_information_bound RESOLVED for the bar (temporal_availability.py, unchanged).",
            "completeness": "close_time present and close_time - open_time == nominal_ms - (1 if INCLUSIVE_LAST_MILLISECOND else 0); shorter = TRUNCATED.",
            "regularity": "next_open - open == nominal_ms -> REGULAR; greater -> GAP (missing = step/nominal - 1); last row -> UNKNOWN_LAST_ROW.",
            "eligibility": "Sample at nominal position q is ELIGIBLE iff every position of lookback [q-L+1,q], operator window [q-W+1,q] and target [q+1,q+h] is a present, available, complete bar. No interpolation, no filling; next bar = next NOMINAL interval.",
        },
        "x-mask-columns": {
            "row_index": "int32, 0-based row of the dataset",
            "open_time_ms": "int64 UTC ms",
            "close_time_ms": "int64 UTC ms, null if absent",
            "bar_available": "bool, layer 1",
            "bar_interval_complete": "bool, layer 2",
            "bar_truncated": "bool, layer 2",
            "next_step_state": f"string in {list(STEP_STATES)}, layer 3",
            "missing_nominal_intervals_after": "int32, null for the last row",
            "sample_eligible": "bool, layer 4",
            "ineligibility_reasons": f"list<string> subset of sample reason codes in declared order; empty iff eligible",
            "eligible_support_through": "int32, eligible samples with row_index <= this row (prefix-invariant)",
            "origin_<j>_role": f"string in {list(ROLE_CODES)} (NOT prefix-invariant; anchored at the last eligible sample)",
        },
        "x-prefix-invariance": "sample_eligible, ineligibility_reasons and eligible_support_through of a row depend only on rows with open time in [open_t - (max(L,W)-1)*nominal, open_t + h*nominal] and earlier rows (support). Rolling-origin roles are not prefix-invariant. A structurally invalid dataset is refused as a whole.",
        "x-enums": {
            "structural_refusal_codes": list(STRUCTURAL_REFUSAL_CODES),
            "sample_reason_codes": list(SAMPLE_REASON_CODES),
            "role_codes": list(ROLE_CODES),
            "region_codes": list(REGION_CODES),
            "origin_statuses": list(ORIGIN_STATUSES),
            "origin_status_reasons": list(ORIGIN_STATUS_REASONS),
            "step_states": list(STEP_STATES),
        },
        "x-rolling-origin-rule": " ".join(rolling_origins.__doc__.split()),
        "x-implementation": {"root_id": "financial-data",
                             "relative_path": "_scripts/temporal_quality.py",
                             "availability_library": "_scripts/temporal_availability.py"},
    }
