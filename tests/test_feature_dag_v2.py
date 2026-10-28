"""C55 fixtures (order 2026-09-12).

Every fixture the order names, each written so that the v1 reader —
which looked at one assignment line — would get it WRONG. A test that
only the new code can pass is the only evidence that the new code does
something.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "dagv2", ROOT / "_scripts/derive_feature_dag_v2.py")
dagv2 = importlib.util.module_from_spec(_spec)
sys.modules["dagv2"] = dagv2
_spec.loader.exec_module(dagv2)


def index(source: str, *, file: str = "producer.py") -> dict:
    """Index one source string the way the tool indexes a repository."""
    tree = ast.parse(source)
    by_output, by_name = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sym = dagv2.Symbol(node, file, "fixture", "0" * 40, "d" * 64)
            by_name.setdefault(sym.name, []).append(sym)
            for col in sym.outputs:
                by_output.setdefault(col, []).append(sym)
    return {"by_output": by_output, "by_name": by_name}


def classify(source: str, column: str, *, file: str = "producer.py"):
    idx = index(source, file=file)
    return dagv2.classify(column, idx["by_output"].get(column, []),
                          idx["by_name"])


# ---------------------------------------------- the resolved fixtures
def test_local_variable_chain_reaches_the_real_input():
    """`returns` is a LOCAL. v1 saw `df['log_return_1'] = returns` and
    reported no inputs at all."""
    out = classify("""
def compute(df):
    returns = df['close'].pct_change()
    df['log_return_1'] = returns
""", "log_return_1")
    assert out["klass"] == dagv2.CAUSAL
    assert out["leaves"] == ["close"]


def test_two_local_hops_still_reach_the_input():
    out = classify("""
def compute(df):
    a = df['close'].diff()
    b = a / df['close']
    df['ratio'] = b
""", "ratio")
    assert out["klass"] == dagv2.CAUSAL
    assert out["leaves"] == ["close"]


def test_macd_reaches_both_emas_and_their_windows():
    out = classify("""
def compute(df):
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
""", "macd")
    assert out["klass"] == dagv2.CAUSAL
    assert out["leaves"] == ["close"]
    assert out["lookback"] == 26, "the WIDEST window governs"


def test_stochastic_names_high_low_and_close():
    out = classify("""
def compute(df):
    lo = df['low'].rolling(14).min()
    hi = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * (df['close'] - lo) / (hi - lo)
""", "stoch_k")
    assert out["klass"] == dagv2.CAUSAL
    assert out["leaves"] == ["close", "high", "low"]
    assert out["lookback"] == 14


# ------------------------------------------- the forward-looking ones
def test_helper_hiding_a_negative_shift_is_not_causal():
    """The defining line is `df['x'] = lead(df['close'])` — spotless.
    v1 called it CAUSAL."""
    out = classify("""
def lead(series):
    return series.shift(-1)

def compute(df):
    df['next_close'] = lead(df['close'])
""", "next_close")
    assert out["klass"] == dagv2.NON_CAUSAL
    assert any("shift(-1)" in f for f in out["forward"])
    assert out["helpers"][0]["symbol"] == "lead"


def test_helper_with_bfill_is_not_causal():
    out = classify("""
def fill(series):
    return series.bfill()

def compute(df):
    df['filled'] = fill(df['close'])
""", "filled")
    assert out["klass"] == dagv2.NON_CAUSAL
    assert any("bfill" in f for f in out["forward"])


def test_fillna_with_the_bfill_method_is_not_causal():
    out = classify("""
def compute(df):
    df['filled'] = df['close'].fillna(method='bfill')
""", "filled")
    assert out["klass"] == dagv2.NON_CAUSAL


def test_numpy_roll_backwards_is_not_causal():
    out = classify("""
def compute(df):
    df['shifted'] = np.roll(df['close'].values, -1)
""", "shifted")
    assert out["klass"] == dagv2.NON_CAUSAL
    assert any("roll(-1)" in f for f in out["forward"])


def test_centred_rolling_window_is_not_causal():
    out = classify("""
def compute(df):
    df['smooth'] = df['close'].rolling(5, center=True).mean()
""", "smooth")
    assert out["klass"] == dagv2.NON_CAUSAL


def test_positional_indexing_is_unresolved_not_assumed_causal():
    """A static reader cannot tell `df[i+1]` from `df[i-1]`. It refuses
    rather than guessing in the permissive direction."""
    out = classify("""
def compute(df):
    df['peek'] = df['close'].values[1:]
""", "peek")
    assert out["klass"] == dagv2.UNRESOLVED
    assert any("positional indexing" in u for u in out["unknown"])


# ------------------------------------------------ the refusal fixtures
def test_a_cycle_is_unresolved_and_does_not_hang():
    out = classify("""
def f(x):
    return g(x)

def g(x):
    return f(x)

def compute(df):
    df['looped'] = f(df['close'])
""", "looped")
    assert out["klass"] == dagv2.UNRESOLVED
    assert "cycle" in out["unknown"]


def test_a_self_referential_local_is_a_cycle():
    out = classify("""
def compute(df):
    a = a + df['close']
    df['self'] = a
""", "self")
    assert out["klass"] == dagv2.UNRESOLVED


def test_an_unfollowed_call_leaves_the_whole_output_unresolved():
    out = classify("""
def compute(df):
    df['mystery'] = some_c_extension(df['close'])
""", "mystery")
    assert out["klass"] == dagv2.UNRESOLVED
    assert any("some_c_extension" in u for u in out["unknown"])


def test_an_ambiguous_helper_is_unresolved_not_guessed():
    out = classify("""
def helper(s):
    return s.shift(1)

def helper(s):
    return s.shift(-1)

def compute(df):
    df['ambiguous'] = helper(df['close'])
""", "ambiguous")
    assert out["klass"] == dagv2.UNRESOLVED
    assert any("defined 2 times" in u for u in out["unknown"])


def test_a_window_size_that_arrives_as_a_parameter_is_unresolved():
    out = classify("""
def compute(df, span):
    df['param_window'] = df['close'].ewm(span=span).mean()
""", "param_window")
    assert out["klass"] == dagv2.UNRESOLVED
    assert "span" in out["params"]


def test_no_producer_at_all_is_unresolved_never_causal():
    out = classify("def compute(df):\n    pass\n", "orphan")
    assert out["klass"] == dagv2.UNRESOLVED
    assert out["producer"] is None


# ------------------------------------------------------- the retired
def test_a_producer_found_only_under_a_retired_path_is_labelled():
    out = classify("""
def compute(df):
    df['legacy_feature'] = df['close'].rolling(3).mean()
""", "legacy_feature", file="_invalidated/old_worker.py")
    assert out["klass"] == dagv2.RETIRED
    assert out["leaves"] == ["close"]


def test_a_live_producer_is_not_labelled_retired():
    out = classify("""
def compute(df):
    df['live_feature'] = df['close'].rolling(3).mean()
""", "live_feature", file="_scripts/workers/worker.py")
    assert out["klass"] == dagv2.CAUSAL


# --------------------------------------------- a method is not a helper
def test_a_method_call_is_not_confused_with_a_module_function():
    """My own defect: `series.mean()` was looked up as a function named
    `mean`, and finding three of them made every moving average
    UNRESOLVED."""
    out = classify("""
def mean(a, b):
    return (a + b) / 2

def compute(df):
    df['avg'] = df['close'].rolling(5).mean()
""", "avg")
    assert out["klass"] == dagv2.CAUSAL
    assert out["helpers"] == [], "no module-level helper was called"


# -------------------------------------------------- C56 availability
def _node(klass, lookback=14):
    return {"klass": klass, "lookback": lookback}


def test_availability_refuses_when_the_timestamp_meaning_is_undeclared():
    a = dagv2.availability(_node(dagv2.CAUSAL), {
        "timestamp_semantics": "UNDECLARED", "bar_seconds": 3600,
        "provider_latency_seconds": 0})
    assert a["earliest_available_time"] == "UNAVAILABLE"
    assert "MEANS" in a["reason"]


def test_availability_refuses_without_a_declared_provider_latency():
    a = dagv2.availability(_node(dagv2.CAUSAL), {
        "timestamp_semantics": "BAR_OPEN", "bar_seconds": 3600,
        "provider_latency_seconds": None})
    assert a["earliest_available_time"] == "UNAVAILABLE"


def test_bar_open_adds_the_bar_and_the_provider_latency():
    a = dagv2.availability(_node(dagv2.CAUSAL), {
        "timestamp_semantics": "BAR_OPEN", "bar_seconds": 3600,
        "provider_latency_seconds": 120})
    assert "3720s" in a["earliest_available_time"]


def test_bar_close_does_not_add_a_second_bar():
    a = dagv2.availability(_node(dagv2.CAUSAL), {
        "timestamp_semantics": "BAR_CLOSE", "bar_seconds": 3600,
        "provider_latency_seconds": 120})
    assert "120s" in a["earliest_available_time"]


def test_one_unresolved_path_makes_the_whole_output_unavailable():
    a = dagv2.availability(_node(dagv2.UNRESOLVED), {
        "timestamp_semantics": "BAR_CLOSE", "bar_seconds": 3600,
        "provider_latency_seconds": 0})
    assert a["earliest_available_time"] == "UNAVAILABLE"


def test_a_non_causal_output_is_never_given_an_availability_time():
    a = dagv2.availability(_node(dagv2.NON_CAUSAL), {
        "timestamp_semantics": "BAR_CLOSE", "bar_seconds": 3600,
        "provider_latency_seconds": 0})
    assert a["earliest_available_time"] == "UNAVAILABLE"


# ------------------------------------------------------------ mutants
@pytest.mark.parametrize("guard,source,column", [
    ("forward detection", """
def compute(df):
    df['x'] = df['close'].shift(-1)
""", "x"),
    ("local resolution", """
def compute(df):
    lead = df['close'].shift(-3)
    df['x'] = lead
""", "x"),
    ("helper following", """
def h(s):
    return s.shift(-1)

def compute(df):
    df['x'] = h(df['close'])
""", "x"),
])
def test_a_leak_is_caught_at_every_depth(guard, source, column):
    assert classify(source, column)["klass"] == dagv2.NON_CAUSAL, guard


def test_a_module_function_is_not_resolved_against_a_local_helper():
    """My second defect: after teaching the walker that `np.roll` is a
    module function, `np.log` started resolving against the seventeen
    local functions named `log`, and every logarithmic return became
    UNRESOLVED for a reason that was about my code, not theirs."""
    out = classify("""
def log(a, b):
    return a.shift(-1)

def compute(df):
    df['log_return_1'] = np.log(df['close']).diff()
""", "log_return_1")
    assert out["klass"] == dagv2.CAUSAL
    assert out["leaves"] == ["close"]
    assert out["helpers"] == []


def test_a_bare_name_call_IS_still_followed_as_a_helper():
    out = classify("""
def lead(s):
    return s.shift(-1)

def compute(df):
    df['x'] = lead(df['close'])
""", "x")
    assert out["klass"] == dagv2.NON_CAUSAL


def test_a_test_file_is_never_indexed_as_a_producer(tmp_path):
    """My third defect: the fixtures in THIS file were indexed as
    producers, and their deliberately ambiguous helpers turned six real
    columns UNRESOLVED."""
    (tmp_path / "worker.py").write_text(
        "def compute(df):\n    df['c'] = df['close'].rolling(3).mean()\n")
    (tmp_path / "test_worker.py").write_text(
        "def mean(a):\n    return a\n\ndef mean(b):\n    return b\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "helpers.py").write_text(
        "def compute(df):\n    df['c'] = df['close'].shift(-1)\n")
    found = dagv2.index_producers({"fixture": tmp_path})
    assert found["files_scanned"] == 1
    assert [s.file for s in found["by_output"]["c"]] == ["worker.py"]
