"""C74-C80 fixtures (order 2026-09-12) for FEATURE_DAG.v3.

The seven PRE families (C74.1-C74.7) each assert the CORRECT outcome;
the mutant tests switch one guard off and show the old wrong answer
comes back, so every guard is load-bearing.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GH = ROOT.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


d3 = _load("dagv3", "_scripts/derive_feature_dag_v3.py")
pip = _load("prefix_invariance_probe", "_scripts/prefix_invariance_probe.py")


def static(src, column, *, file="producer.py", repo="fixture", order=None):
    idx = d3.index_source(src, file=file, repo=repo)
    return d3.classify(column, idx, order=order)


SRC1 = """
def compute(df):
    x = df['close'].shift(1)
    x = df['close'].shift(-1)
    df['o'] = x
"""
SRC2 = """
def compute(df):
    df['o'] = df['close'].rolling(10).mean().rolling(20).mean()
"""
SRC3 = """
def lead(s):
    return s.shift(-1)

def compute(df):
    df['o'] = df['close'].{meth}(lead)
"""
SRC5 = """
def compute(df):
    def inner():
        x = df['close']
        return x
    df['o'] = x
"""
SRC6 = """
def causal_one(df):
    df['o'] = df['close'].rolling(3).mean()

def forward_one(df):
    df['o'] = df['close'].shift(-1)
"""
SRC7 = """
def unrelated_worker(df):
    df['close_ma_3'] = df['close'].rolling(3).mean()
"""


# ------------------------------------------------- C74 PRE families
def test_c74_1_the_last_reaching_definition_governs():
    out = static(SRC1, "o")
    assert out["klass"] == d3.NON_CAUSAL
    assert "shift(-1)" in out["forward"]


def test_c74_2_chained_windows_compose_inclusively():
    out = static(SRC2, "o")
    assert out["klass"] == d3.STATIC_CAUSAL
    assert out["lookback"] == 29


def test_c74_2_a_shift_after_a_window_adds_its_reach():
    out = static("def compute(df):\n    df['o'] = "
                 "df['close'].rolling(10).mean().shift(3)\n", "o")
    assert out["lookback"] == 13, "oldest bar read is 12 back, inclusive 13"


@pytest.mark.parametrize("meth", ["apply", "map", "transform", "pipe", "agg"])
def test_c74_3_a_forward_callable_is_followed(meth):
    out = static(SRC3.format(meth=meth), "o")
    assert out["klass"] == d3.NON_CAUSAL, meth


def test_c74_3_a_lambda_and_a_rolling_apply_are_followed():
    assert static("def compute(df):\n    df['o'] = df['close'].transform("
                  "lambda s: s.shift(-2))\n", "o")["klass"] == d3.NON_CAUSAL
    assert static("def lead(w):\n    return w.shift(-1)\n\ndef compute(df):\n"
                  "    df['o'] = df['close'].rolling(5).apply(lead)\n",
                  "o")["klass"] == d3.NON_CAUSAL


def test_c74_3_an_unfollowable_callable_is_unresolved():
    out = static("def compute(df, fn):\n    df['o'] = df['close'].apply(fn)\n",
                 "o")
    assert out["klass"] == d3.UNRESOLVED
    assert any("UNFOLLOWABLE_CALLABLE" in u for u in out["unresolved"])


@pytest.mark.parametrize("expr", ["df['close'].iloc[-1]", "df['close'].iloc[5]",
                                  "df['close'].values[-1]",
                                  "df['close'].loc[3]", "df['close'][1:]",
                                  "df['close'].head(3)"])
def test_c74_4_every_positional_index_is_unresolved(expr):
    out = static(f"def compute(df):\n    df['o'] = {expr}\n", "o")
    assert out["klass"] == d3.UNRESOLVED, expr
    assert any("POSITIONAL" in u for u in out["unresolved"])


def test_c74_5_a_nested_body_never_binds_the_outer_scope():
    out = static(SRC5, "o")
    assert out["klass"] == d3.UNRESOLVED
    assert "UNBOUND_NAME:x" in out["unresolved"]


def test_c74_6_two_disagreeing_producers_are_unresolved_in_any_order():
    a = static(SRC6, "o", order=["causal_one", "forward_one"])
    b = static(SRC6, "o", order=["forward_one", "causal_one"])
    assert a["klass"] == d3.UNRESOLVED
    assert "CONFLICTING_PRODUCER_CANDIDATES" in a["unresolved"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_c74_7_a_name_coincident_producer_is_never_causal_active():
    out = static(SRC7, "close_ma_3", repo="some_other_project",
                 file="elsewhere/worker.py")
    assert out["klass"] == d3.STATIC_CAUSAL
    final = d3.finalize(out, bound=False)
    assert final["class"] == d3.CANDIDATE
    assert final["class"] != d3.CAUSAL


def test_c74_7_only_a_binding_makes_it_causal_active():
    out = static(SRC7, "close_ma_3")
    assert d3.finalize(out, bound=True)["class"] == d3.CAUSAL
    assert d3.finalize(out, bound=True, probe={"verdict": "FAIL"})[
        "class"] == d3.NON_CAUSAL


def test_unbound_non_causal_or_unresolved_is_a_binding_refusal():
    assert d3.finalize(static(SRC1, "o"), bound=False)["class"] == d3.UNBOUND
    assert d3.finalize(static(SRC5, "o"), bound=False)["class"] == d3.UNBOUND


# --------------------------------------------------- branches, loops
def test_a_definition_in_one_branch_that_disagrees_is_unresolved():
    out = static("""
def compute(df, flag):
    x = df['close'].rolling(3).mean()
    if flag:
        x = df['close'].shift(-1)
    df['o'] = x
""", "o")
    assert out["klass"] == d3.UNRESOLVED
    assert "AMBIGUOUS_REACHING_DEFINITIONS" in out["unresolved"]


def test_a_window_that_differs_between_branches_is_unresolved():
    out = static("""
def compute(df, flag):
    if flag:
        x = df['close'].rolling(3).mean()
    else:
        x = df['close'].rolling(5).mean()
    df['o'] = x
""", "o")
    assert out["klass"] == d3.UNRESOLVED


def test_identical_definitions_in_both_branches_resolve():
    out = static("""
def compute(df, flag):
    if flag:
        x = df['close'].rolling(3).mean()
    else:
        x = df['close'].rolling(3).mean()
    df['o'] = x
""", "o")
    assert out["klass"] == d3.STATIC_CAUSAL and out["lookback"] == 3


def test_a_literal_loop_is_unrolled_and_fstring_outputs_resolve():
    src = """
def compute(df):
    out = pd.DataFrame({'t': df['t']})
    for p in [10, 20]:
        out[f'sma_{p}'] = df['close'].rolling(p).mean()
    return out
"""
    assert static(src, "sma_10")["lookback"] == 10
    assert static(src, "sma_20")["lookback"] == 20


def test_a_while_loop_definition_is_unresolved():
    out = static("""
def compute(df, n):
    x = df['close']
    while n > 0:
        x = x.shift(1)
        n -= 1
    df['o'] = x
""", "o")
    assert out["klass"] == d3.UNRESOLVED
    assert "LOOP_BODY_DEFINITION" in out["unresolved"]


# ------------------------------------------------ ported v2 fixtures
def test_local_variable_chain_reaches_the_real_input():
    out = static("def compute(df):\n    returns = df['close'].pct_change("
                 "fill_method=None)\n    df['log_return_1'] = returns\n",
                 "log_return_1")
    assert out["klass"] == d3.STATIC_CAUSAL
    assert out["leaves"] == ["close"] and out["lookback"] == 2


def test_default_pct_change_pads_and_is_unbounded():
    out = static("def compute(df):\n    df['r'] = df['close'].pct_change()\n",
                 "r")
    assert out["klass"] == d3.STATIC_CAUSAL and out["lookback"] == "UNBOUNDED"


def test_two_local_hops_still_reach_the_input():
    out = static("def compute(df):\n    a = df['close'].diff()\n"
                 "    b = a / df['close']\n    df['ratio'] = b\n", "ratio")
    assert out["klass"] == d3.STATIC_CAUSAL and out["leaves"] == ["close"]


def test_macd_reaches_both_emas_and_an_ewm_has_unbounded_memory():
    out = static("""
def compute(df):
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
""", "macd")
    assert out["klass"] == d3.STATIC_CAUSAL and out["leaves"] == ["close"]
    assert out["lookback"] == "UNBOUNDED"


def test_stochastic_names_high_low_and_close():
    out = static("""
def compute(df):
    lo = df['low'].rolling(14).min()
    hi = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * (df['close'] - lo) / (hi - lo)
""", "stoch_k")
    assert out["leaves"] == ["close", "high", "low"] and out["lookback"] == 14


def test_helper_hiding_a_negative_shift_is_not_causal():
    out = static("def lead(series):\n    return series.shift(-1)\n\n"
                 "def compute(df):\n    df['n'] = lead(df['close'])\n", "n")
    assert out["klass"] == d3.NON_CAUSAL
    assert any("lead" in h for h in out["helpers"])


@pytest.mark.parametrize("body,col", [
    ("def fill(s):\n    return s.bfill()\n\ndef compute(df):\n"
     "    df['f'] = fill(df['close'])\n", "f"),
    ("def compute(df):\n    df['f'] = df['close'].fillna(method='bfill')\n",
     "f"),
    ("def compute(df):\n    df['f'] = np.roll(df['close'].values, -1)\n", "f"),
    ("def compute(df):\n    df['f'] = np.roll(df['close'].values, 1)\n", "f"),
    ("def compute(df):\n    df['f'] = df['close'].rolling(5, center=True)"
     ".mean()\n", "f"),
    ("def compute(df):\n    df['f'] = df['close'] - df['close'].mean()\n",
     "f"),
])
def test_forward_operations_are_non_causal(body, col):
    assert static(body, col)["klass"] == d3.NON_CAUSAL


def test_a_cycle_is_unresolved_and_does_not_hang():
    out = static("def f(x):\n    return g(x)\n\ndef g(x):\n    return f(x)\n"
                 "\ndef compute(df):\n    df['l'] = f(df['close'])\n", "l")
    assert out["klass"] == d3.UNRESOLVED and "CYCLE" in out["unresolved"]


def test_a_self_referential_local_is_unresolved():
    out = static("def compute(df):\n    a = a + df['close']\n"
                 "    df['s'] = a\n", "s")
    assert out["klass"] == d3.UNRESOLVED


@pytest.mark.parametrize("body", [
    "df['m'] = some_c_extension(df['close'])",
    "df['m'] = getattr(df['close'], 'shift')(1)",
    "df['m'] = eval('df')['close']",
    "df['m'] = FUNCS['lead'](df['close'])",
    "df['m'] = helper(df['close'], **opts)",
])
def test_unknown_and_dynamic_calls_are_unresolved(body):
    src = ("FUNCS = {}\n\ndef helper(s, **k):\n    return s\n\n"
           "def compute(df, opts):\n    " + body + "\n")
    assert static(src, "m")["klass"] == d3.UNRESOLVED, body


def test_an_ambiguous_helper_is_unresolved_not_guessed():
    out = static("def helper(s):\n    return s.shift(1)\n\n"
                 "def helper(s):\n    return s.shift(-1)\n\n"
                 "def compute(df):\n    df['a'] = helper(df['close'])\n", "a")
    assert out["klass"] == d3.UNRESOLVED
    assert any("AMBIGUOUS_HELPER" in u for u in out["unresolved"])


def test_a_window_size_that_arrives_as_a_parameter_is_unresolved():
    out = static("def compute(df, span):\n    df['p'] = "
                 "df['close'].ewm(span=span).mean()\n", "p")
    assert out["klass"] == d3.UNRESOLVED
    assert "WINDOW_FROM_PARAMETER:span" in out["unresolved"]


def test_a_window_bound_by_a_helper_argument_is_resolved():
    out = static("def sma(s, n):\n    return s.rolling(n).mean()\n\n"
                 "def compute(df):\n    df['p'] = sma(df['close'], 7)\n", "p")
    assert out["klass"] == d3.STATIC_CAUSAL and out["lookback"] == 7


def test_no_producer_at_all_is_unresolved():
    out = static("def compute(df):\n    pass\n", "orphan")
    assert out["klass"] == d3.UNRESOLVED
    assert out["unresolved"] == ["NO_STATIC_CANDIDATE"]


def test_a_producer_found_only_under_a_retired_path_is_labelled():
    out = static("def compute(df):\n    df['lf'] = df['close'].rolling(3)"
                 ".mean()\n", "lf", file="_invalidated/old_worker.py")
    assert out["klass"] == d3.RETIRED
    assert d3.finalize(out, bound=False)["class"] == d3.RETIRED


def test_a_method_call_is_not_confused_with_a_module_function():
    out = static("def mean(a, b):\n    return (a + b) / 2\n\n"
                 "def compute(df):\n    df['avg'] = df['close'].rolling(5)"
                 ".mean()\n", "avg")
    assert out["klass"] == d3.STATIC_CAUSAL and out["helpers"] == []


def test_a_module_function_is_not_resolved_against_a_local_helper():
    out = static("def log(a, b):\n    return a.shift(-1)\n\n"
                 "def compute(df):\n    df['l'] = np.log(df['close']).diff()\n",
                 "l")
    assert out["klass"] == d3.STATIC_CAUSAL and out["helpers"] == []


def test_a_safe_method_name_never_hides_a_user_function():
    """A bare call to a user function named like a safe method is
    followed: `mean` here is a leak, not a moving average."""
    out = static("def mean(s):\n    return s.shift(-1)\n\n"
                 "def compute(df):\n    df['x'] = mean(df['close'])\n", "x")
    assert out["klass"] == d3.NON_CAUSAL


def test_a_test_file_is_never_indexed_as_a_producer(tmp_path):
    (tmp_path / "worker.py").write_text(
        "def compute(df):\n    df['c'] = df['close'].rolling(3).mean()\n")
    (tmp_path / "test_worker.py").write_text(
        "def compute(df):\n    df['c'] = df['close'].shift(-1)\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "helpers.py").write_text(
        "def compute(df):\n    df['c'] = df['close'].shift(-1)\n")
    idx = d3.index_producers({"fixture": tmp_path})
    assert idx.files_scanned == 1
    assert [s.file for s in idx.by_output["c"]] == ["worker.py"]


# ------------------------------------------------------------ mutants
MUTANTS = [
    ("scope_isolation", SRC5, "o",
     lambda o: o["klass"] == d3.STATIC_CAUSAL),
    ("reaching_definitions", SRC1, "o",
     lambda o: o["klass"] == d3.STATIC_CAUSAL),
    ("callable_following", SRC3.format(meth="apply"), "o",
     lambda o: o["klass"] == d3.STATIC_CAUSAL),
    ("positional_index", "def compute(df):\n    df['o'] = "
     "df['close'].iloc[-1]\n", "o",
     lambda o: o["klass"] == d3.STATIC_CAUSAL),
    ("window_composition", SRC2, "o", lambda o: o["lookback"] == 20),
]


@pytest.mark.parametrize("guard,src,col,old_wrong", MUTANTS,
                         ids=[m[0] for m in MUTANTS])
def test_each_static_guard_is_load_bearing(monkeypatch, guard, src, col,
                                           old_wrong):
    assert not old_wrong(static(src, col)), "guard on: correct answer"
    monkeypatch.setitem(d3.GUARDS, guard, False)
    assert old_wrong(static(src, col)), f"{guard} off: v2's wrong answer"


def test_the_binding_requirement_is_load_bearing(monkeypatch):
    out = static(SRC7, "close_ma_3")
    assert d3.finalize(out, bound=False)["class"] == d3.CANDIDATE
    monkeypatch.setitem(d3.GUARDS, "binding_requirement", False)
    assert d3.finalize(out, bound=False)["class"] == d3.CAUSAL


def test_the_producer_conflict_guard_is_load_bearing(monkeypatch):
    monkeypatch.setitem(d3.GUARDS, "producer_conflict", False)
    a = static(SRC6, "o", order=["causal_one", "forward_one"])
    b = static(SRC6, "o", order=["forward_one", "causal_one"])
    assert a["klass"] != b["klass"], "order decides again, as in v2"


# ---------------------------------------------- order independence
def _fixture_world(tmp_path):
    pred = tmp_path / "predictor"
    (pred / "examples/research").mkdir(parents=True)
    (pred / "examples/data").mkdir(parents=True)
    csv = pred / "examples/data/ds.csv"
    csv.write_text("DATE_TIME,CLOSE,o,sma_3,lead\n2020-01-01,1,1,1,1\n")
    inv = {"datasets": [{
        "dataset_id": "fixture.eth_4h_x.v1",
        "relative_path": "examples/data/ds.csv",
        "physical_sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
        "time_profile": {"timestamp_column": "DATE_TIME"}}]}
    (pred / "examples/research/crispdm_dataset_inventory.v1.json"
     ).write_text(json.dumps(inv))
    repo = tmp_path / "prod"
    (repo / "a").mkdir(parents=True)
    (repo / "b").mkdir(parents=True)
    (repo / "a/one.py").write_text(SRC6)
    (repo / "b/two.py").write_text(
        "def other(df):\n    df['sma_3'] = df['close'].rolling(3).mean()\n"
        "def lead(df):\n    df['lead'] = df['close'].shift(-1)\n")
    (repo / "b/three.py").write_text(
        "def again(df):\n    df['sma_3'] = df['close'].rolling(3).mean()\n")
    return pred, {"prod": repo}


def test_shuffling_index_and_scan_order_yields_identical_nodes(tmp_path):
    pred, repos = _fixture_world(tmp_path)
    runs = []
    for seed in (None, 1, 2, 3, 4):
        doc, manifest = d3.derive(pred, repos, "T", shuffle_seed=seed,
                                  run_probe=False)
        runs.append(json.dumps(doc["nodes"], sort_keys=True))
    assert len(set(runs)) == 1
    nodes = {n["column"]: n for n in json.loads(runs[0])}
    assert nodes["o"]["class"] == d3.UNBOUND
    assert nodes["sma_3"]["class"] == d3.CANDIDATE
    assert nodes["CLOSE"]["class"] == d3.UNBOUND


def test_v1_and_v2_are_byte_identical_after_a_v3_derivation(tmp_path):
    census = ROOT / "features/census"
    before = {f: hashlib.sha256((census / f).read_bytes()).hexdigest()
              for f in ("FEATURE_DAG.v1.json", "FEATURE_DAG.v2.json")}
    repos = [f"{n}={GH / n}" for n in ("feature-eng", "feature-extractor",
                                       "financial-data")]
    if not (GH / "predictor").is_dir():
        pytest.skip("predictor checkout absent")
    argv = ["--predictor-root", str(GH / "predictor"),
            "--output", str(tmp_path / "FEATURE_DAG.v3.json"),
            "--derived-at", "2026-09-12T00:00:00Z", "--skip-probe"]
    for r in repos:
        argv += ["--producer-root", r]
    assert d3.main(argv) == 0
    after = {f: hashlib.sha256((census / f).read_bytes()).hexdigest()
             for f in before}
    assert before == after
    assert (tmp_path / "PRODUCER_BINDING_MANIFEST.v1.json").is_file()
    assert "/home/" not in (tmp_path / "FEATURE_DAG.v3.json").read_text()


# ------------------------------------------------ C79 prefix invariance
def test_a_causal_rolling_mean_passes_the_prefix_probe():
    def producer(df):
        out = df[["timestamp"]].copy()
        out["m"] = df["close"].rolling(5).mean()
        return out
    r = pip.probe(producer)
    assert r["verdict"] == "PASS"


def test_a_negative_shift_fails_the_prefix_probe():
    def producer(df):
        out = df[["timestamp"]].copy()
        out["lead"] = df["close"].shift(-1)
        return out
    r = pip.probe(producer)
    assert r["verdict"] == "FAIL" and r["failed_columns"] == ["lead"]
    assert r["columns"]["lead"]["first_changed_row"] == r["cut_row"]


def test_a_producer_that_writes_outside_the_sandbox_is_not_executable(
        tmp_path):
    target = tmp_path.parent / "escape_attempt.txt"

    def producer(df):
        with open(target, "w") as fh:
            fh.write("x")
        return df
    r = pip.probe(producer)
    assert r["verdict"] == "NOT_EXECUTABLE_SIDE_EFFECT"
    assert not target.exists()


def test_eligibility_refuses_modules_with_heavy_imports(tmp_path):
    p = tmp_path / "m.py"
    p.write_text("import tensorflow as tf\n\ndef f(df):\n    return df\n")
    assert pip.eligibility(p)["eligible"] is False


def test_the_real_stage22_producers_pass_the_prefix_probe():
    path = ROOT / "_scripts/workers/stage22_trading_features_worker.py"
    for sym in ("compute_technical", "compute_statistical"):
        r = pip.probe(pip.load_symbol(path, sym))
        assert r["verdict"] == "PASS", (sym, r.get("failed_columns"),
                                        r.get("error"))
