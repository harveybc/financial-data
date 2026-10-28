#!/usr/bin/env python3
"""C74-C80 (order 2026-09-12): FEATURE_DAG.v3, additive to v1 and v2.

v2 walked an expression with `ast.walk`, ignoring statement order,
scope and control flow; it kept the FIRST assignment of a local, folded
nested function bodies into the outer scope, treated callables passed to
`apply`/`map`/`transform` as element-wise, let constant positional
indices through, took the widest of two chained windows instead of
their composition, and picked a producer by `(live or symbols)[0]` —
by name and by order, with no link to the physical dataset.

v3 is a small abstract interpreter over one producer symbol:

* scope: a nested def/lambda/class body is never executed as the outer
  body; it is a callable value, analysed only when it is called.
* reaching definitions: statements execute in order; `if`/`try` branches
  join the set of definitions that may reach a use. When the reaching
  definitions disagree in class or lookback the use is UNRESOLVED.
  Loops over a literal sequence (or over the exactly-known columns of a
  local frame) are unrolled; any other loop havocs what its body writes.
* callables passed to apply/map/transform/pipe/agg/rolling().apply are
  followed; one that cannot be followed is UNRESOLVED. A bare call that
  resolves to a user function is always followed, whatever its name.
* every positional index (iloc/loc/iat/at/values[...]/[int]/[slice]) is
  UNRESOLVED; no positional index is treated as proven historical.
* offsets compose: a value's dependency is a range [lo, hi] of bars back
  (0 = current bar, negative = future). shift(k) adds k, rolling(w) adds
  w-1 to hi, ewm/expanding/cumsum/ffill make hi UNBOUNDED, bfill and
  centred windows push lo below 0. lookback_bars = hi + 1 (current bar
  included): rolling(10).rolling(20) -> 29; rolling(10).shift(3) -> 13
  (the oldest bar read is 12 bars back).
* getattr/eval/exec, **kwargs calls, calls through subscripts, unknown
  calls, cycles and depth/budget exhaustion are UNRESOLVED.

C78: a dataset column is bound to a producer only through provenance
evidence that names the physical dataset (manifest digest), the
intermediate artifact, a run receipt and a code identity (commit or code
digest recorded at run time). A producer found only by static search is
STATIC_CAUSAL_CANDIDATE_UNBOUND at best, never CAUSAL_ACTIVE.

C79: bound and executable producers get a prefix-invariance probe on
synthetic OHLCV frames (see prefix_invariance_probe.py). Unbound
candidates may be probed for information; that never changes a class.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import itertools
import json
import math
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CAUSAL = "CAUSAL_ACTIVE"
CANDIDATE = "STATIC_CAUSAL_CANDIDATE_UNBOUND"
NON_CAUSAL = "NON_CAUSAL"
RETIRED = "HISTORICAL_OR_RETIRED_PRODUCER"
EXTERNAL = "EXTERNAL_LATENCY_REQUIRED"
UNRESOLVED = "UNRESOLVED"
UNBOUND = "UNRESOLVED_PRODUCER_BINDING"
#: the static layer speaks of a proven-causal expression; it is not a
#: dataset class and never appears as a node class
STATIC_CAUSAL = "STATIC_CAUSAL"

MAX_DEPTH = 12
MAX_UNROLL = 64
STEP_BUDGET = 400_000

#: C80 mutants: each switch disables one guard so a test can prove the
#: guard is load-bearing. Production always runs with every guard on.
GUARDS = {
    "scope_isolation": True,
    "reaching_definitions": True,
    "callable_following": True,
    "positional_index": True,
    "window_composition": True,
    "binding_requirement": True,
    "producer_conflict": True,
}

FRAME_PARAMS = frozenset({
    "df", "data", "frame", "series", "s", "x", "prices", "ohlc", "ohlcv",
    "bars", "d", "input_data", "dataframe", "raw",
})
RAW_LEAVES = {"OPEN", "HIGH", "LOW", "CLOSE", "VOLUME", "DATE_TIME"}
RETIRED_TOKENS = ("invalidated", "deprecated", "archive", "_old",
                  "legacy", "attic")
SKIP_PARTS = ("__pycache__", ".git", "build", "tests", "test", ".tox",
              ".venv", "site-packages", "node_modules")

# ------------------------------------------------------------ semantics
ELEMENTWISE_METHODS = frozenset({
    "astype", "abs", "clip", "round", "replace", "isna", "notna",
    "isnull", "notnull", "add", "sub", "mul", "div", "truediv",
    "floordiv", "pow", "mod", "radd", "rsub", "rmul", "rdiv",
    "rtruediv", "rpow", "eq", "ne", "lt", "le", "gt", "ge", "where",
    "mask", "to_numpy", "copy", "rename", "squeeze", "to_frame",
    "between", "isin", "lower", "upper", "strip", "floor", "ceil",
    "tz_convert", "tz_localize", "infer_objects", "convert_dtypes",
    "clip_lower", "clip_upper", "log", "exp", "sqrt",
})
REDUCTIONS = frozenset({
    "mean", "std", "sum", "min", "max", "median", "var", "skew", "kurt",
    "kurtosis", "count", "quantile", "prod", "sem", "nunique", "all",
    "any", "corr", "cov", "mad",
})
WINDOW_REDUCTIONS = REDUCTIONS | {"apply", "agg", "aggregate"}
POSITIONAL_METHODS = frozenset({
    "head", "tail", "first", "last", "idxmax", "idxmin", "nlargest",
    "nsmallest", "item", "take", "sample", "mode", "value_counts",
    "unique", "describe", "argmax", "argmin", "tolist", "to_list",
})
ROW_TRANSFORMS = frozenset({
    "dropna", "drop_duplicates", "sort_values", "sort_index",
    "reset_index", "set_index", "reindex", "groupby", "resample",
    "asfreq", "merge", "join", "iterrows", "itertuples", "align",
    "explode", "melt", "pivot", "pivot_table", "stack", "unstack",
    "query", "filter", "truncate", "interpolate",
})
CALLABLE_METHODS = frozenset({"apply", "map", "transform", "pipe", "agg",
                              "aggregate", "applymap", "combine"})
SINK_METHODS = frozenset({"to_parquet", "to_csv", "to_pickle",
                          "to_feather", "to_json", "to_hdf", "to_excel"})
NP_ELEMENTWISE = frozenset({
    "log", "log1p", "log2", "log10", "exp", "expm1", "sqrt", "abs",
    "absolute", "sign", "square", "isnan", "isfinite", "isinf", "tanh",
    "arctan", "sin", "cos", "clip", "where", "maximum", "minimum",
    "fmax", "fmin", "nan_to_num", "floor", "ceil", "power", "divide",
    "multiply", "subtract", "add", "true_divide", "asarray", "array",
    "float64", "float32", "round", "rint", "logical_and", "logical_or",
    "logical_not", "exp2", "reciprocal", "negative", "greater", "less",
})
PD_ELEMENTWISE = frozenset({"to_numeric", "isna", "notna", "isnull",
                            "notnull", "to_datetime"})
MATH_CONST_FUNCS = {"sqrt": math.sqrt, "log": math.log, "exp": math.exp,
                    "floor": math.floor, "ceil": math.ceil,
                    "log10": math.log10, "log2": math.log2}
BUILTIN_CONST = {"int": int, "float": float, "abs": abs, "round": round,
                 "min": min, "max": max, "str": str, "bool": bool,
                 "len": len}
DYNAMIC_NAMES = frozenset({"getattr", "eval", "exec", "globals", "locals",
                           "vars", "__import__", "setattr", "compile"})
MODULE_ALIASES = {"np": "numpy", "numpy": "numpy", "pd": "pandas",
                  "pandas": "pandas", "math": "math"}


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha_obj(o) -> str:
    return hashlib.sha256(
        json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def git(repo: Path, *args) -> str:
    return subprocess.run(("git", "-C", str(repo), *args),
                          capture_output=True, text=True).stdout.strip()


class Budget(Exception):
    pass


# ------------------------------------------------------ abstract values
def _lo_add(a, b):
    return None if a is None or b is None else a + b


def _hi_add(a, b):
    return None if a is None or b is None else a + b


def _lo_min(a, b):
    return None if a is None or b is None else min(a, b)


def _hi_max(a, b):
    return None if a is None or b is None else max(a, b)


class Flow:
    """A time-aligned series value and everything known about its past.

    lo/hi: offsets in bars back that the value reads (None = unbounded;
    lo < 0 or lo None means it reads the future)."""

    __slots__ = ("leaves", "lo", "hi", "forward", "unresolved", "params",
                 "helpers", "notes")

    def __init__(self, leaves=(), lo=0, hi=0, forward=(), unresolved=(),
                 params=(), helpers=(), notes=()):
        self.leaves = frozenset(leaves)
        self.lo, self.hi = lo, hi
        self.forward = frozenset(forward)
        self.unresolved = frozenset(unresolved)
        self.params = frozenset(params)
        self.helpers = frozenset(helpers)
        self.notes = frozenset(notes)

    def key(self):
        return ("F", self.leaves, self.lo, self.hi, self.forward,
                self.unresolved, self.params, self.helpers, self.notes)

    def __eq__(self, o):
        return isinstance(o, Flow) and self.key() == o.key()

    def __hash__(self):
        return hash(self.key())

    def is_forward(self):
        return self.lo is None or self.lo < 0 or bool(self.forward)

    def signature(self):
        """What a reaching-definition join must agree on."""
        if self.unresolved:
            return ("UNRESOLVED",)
        if self.is_forward():
            return ("NON_CAUSAL",)
        return ("CAUSAL", self.hi)

    def shifted(self, lo_add, hi_add, **extra):
        return Flow(self.leaves, _lo_add(self.lo, lo_add),
                    _hi_add(self.hi, hi_add),
                    self.forward | frozenset(extra.get("forward", ())),
                    self.unresolved | frozenset(extra.get("unresolved", ())),
                    self.params, self.helpers,
                    self.notes | frozenset(extra.get("notes", ())))


def unknown(code: str, *more: Flow) -> Flow:
    return combine(Flow(unresolved=(code,)), *more)


def combine(*flows) -> Flow:
    flows = [f for f in flows if isinstance(f, Flow)]
    if not flows:
        return Flow()
    out = flows[0]
    for f in flows[1:]:
        out = Flow(out.leaves | f.leaves, _lo_min(out.lo, f.lo),
                   _hi_max(out.hi, f.hi), out.forward | f.forward,
                   out.unresolved | f.unresolved, out.params | f.params,
                   out.helpers | f.helpers, out.notes | f.notes)
    return out


class Val:
    """Non-series abstract values. `kind` + payload, hashable."""

    __slots__ = ("kind", "payload")

    def __init__(self, kind, payload=None):
        self.kind, self.payload = kind, payload

    def __eq__(self, o):
        return isinstance(o, Val) and (self.kind, _hk(self.payload)) == (
            o.kind, _hk(o.payload))

    def __hash__(self):
        return hash((self.kind, _hk(self.payload)))

    def __repr__(self):
        return f"Val({self.kind},{self.payload!r})"


def _hk(p):
    try:
        hash(p)
        return p
    except TypeError:
        return id(p)


def const(v):
    return Val("const", v)


SCALAR = Val("scalar")


def is_const(v):
    return isinstance(v, Val) and v.kind == "const"


def as_flow(v, code="NON_SERIES_VALUE") -> Flow | None:
    """Coerce a value used in arithmetic with a series."""
    if isinstance(v, Flow):
        return v
    if isinstance(v, Val):
        if v.kind in ("const", "scalar", "columns"):
            return None
        if v.kind == "param":
            return Flow(params=(v.payload,))
        if v.kind == "unknown":
            return v.payload
    return unknown(f"{code}:{getattr(v, 'kind', type(v).__name__)}")


class Frame:
    __slots__ = ("cols", "base", "havoc", "exact", "pending")

    def __init__(self, cols=None, base=None, havoc=(), exact=True,
                 pending=()):
        self.cols: dict[str, tuple] = dict(cols or {})
        self.base = base          # parameter name, or None for local
        self.havoc = frozenset(havoc)
        self.exact = exact and base is None
        self.pending = tuple(pending)   # column-wise ops on base columns

    def clone(self):
        return Frame(self.cols, self.base, self.havoc, self.exact,
                     self.pending)


class State:
    __slots__ = ("env", "heap")

    def __init__(self, env=None, heap=None):
        self.env: dict[str, tuple] = dict(env or {})
        self.heap: dict[int, Frame] = heap if heap is not None else {}

    def clone(self):
        return State(dict(self.env),
                     {k: f.clone() for k, f in self.heap.items()})


def _uniq(vals):
    out, seen = [], set()
    for v in vals:
        k = v.key() if isinstance(v, Flow) else ("V", v.kind, _hk(v.payload))
        if k not in seen:
            seen.add(k)
            out.append(v)
    return tuple(out)


def join_states(states):
    states = [s for s in states if s is not None]
    if not states:
        return None
    if len(states) == 1:
        return states[0]
    out = State()
    names = set().union(*(s.env for s in states))
    for n in names:
        vals = [v for s in states for v in s.env.get(n, ())]
        if not GUARDS["reaching_definitions"]:
            vals = vals[:1]
        # a name bound on only some paths joins to the bindings that
        # exist: a path that reaches the use unbound raises NameError
        # and produces no value at all
        out.env[n] = _uniq(vals)
    fids = set().union(*(s.heap for s in states))
    for fid in fids:
        frames = [s.heap[fid] for s in states if fid in s.heap]
        f = frames[0].clone()
        if f.base is not None:
            # on a caller's frame a column absent on one path still holds
            # the caller's value on that path, not "nothing"
            allc = set().union(*(g.cols for g in frames))
            for c in allc:
                if any(c not in g.cols for g in frames):
                    f.cols[c] = _uniq(f.cols.get(c, ())
                                      + (Flow(leaves=(c,)),))
        for g in frames[1:]:
            for c, vals in g.cols.items():
                merged = f.cols.get(c, ()) + vals
                if not GUARDS["reaching_definitions"]:
                    merged = merged[:1]
                f.cols[c] = _uniq(merged)
            f.havoc |= g.havoc
            # the column SET is the union: a column present on one path
            # only is "maybe present", and absent-or-v joins to v
            f.exact = f.exact and g.exact
            if g.pending != f.pending:
                f.havoc |= {"DIVERGENT_COLUMNWISE_OPS"}
        out.heap[fid] = f
    return out


def resolve(vals) -> Flow | Val:
    """One value from the set of reaching definitions, or UNRESOLVED."""
    vals = _uniq(vals)
    if not vals:
        return unknown("UNBOUND_NAME")
    if len(vals) == 1:
        return vals[0]
    if all(isinstance(v, Flow) for v in vals):
        if len({v.signature() for v in vals}) == 1:
            return combine(*vals)
        return unknown("AMBIGUOUS_REACHING_DEFINITIONS", *vals)
    if all(isinstance(v, Val) and v.kind == "frame" for v in vals):
        return Val("frameset", tuple(sorted({v.payload for v in vals})))
    flows = [v for v in vals if isinstance(v, Flow)]
    return unknown("AMBIGUOUS_REACHING_DEFINITIONS", *flows)


# ------------------------------------------------------------- modules
class ModuleInfo:
    """One source file: its module-scope definitions, constants, imports."""

    def __init__(self, repo, file, source, commit="0" * 40,
                 digest="d" * 64):
        self.repo, self.file = repo, file
        self.commit, self.digest = commit, digest
        self.tree = ast.parse(source)
        self.retired = any(t in file.lower() for t in RETIRED_TOKENS)
        self.defs: dict[str, list] = {}
        self.classes: dict[str, dict[str, list]] = {}
        self.consts: dict[str, object] = {}
        self.imports: dict[str, tuple] = {}
        assigned: dict[str, int] = {}
        for stmt in self.tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.defs.setdefault(stmt.name, []).append(stmt)
            elif isinstance(stmt, ast.ClassDef):
                meths = self.classes.setdefault(stmt.name, {})
                for s in stmt.body:
                    if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        meths.setdefault(s.name, []).append(s)
            elif isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name):
                        assigned[t.id] = assigned.get(t.id, 0) + 1
                        try:
                            self.consts[t.id] = ast.literal_eval(stmt.value)
                        except (ValueError, SyntaxError, TypeError):
                            self.consts.pop(t.id, None)
            elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
                _bind_imports(stmt, self.imports)
        # a module constant assigned twice is not a constant
        for n, k in assigned.items():
            if k > 1:
                self.consts.pop(n, None)

    def symbols(self):
        """Every function, method and nested function, in source order."""
        out = []

        def visit(node, cls, prefix):
            for s in ast.iter_child_nodes(node):
                if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    q = f"{prefix}{s.name}"
                    out.append((s, cls, q))
                    visit(s, None, q + ".")
                elif isinstance(s, ast.ClassDef):
                    visit(s, s.name, f"{prefix}{s.name}.")
                else:
                    visit(s, cls, prefix) if not isinstance(
                        s, ast.Lambda) else None
        visit(self.tree, None, "")
        return out


def _bind_imports(stmt, table):
    if isinstance(stmt, ast.Import):
        for a in stmt.names:
            root = a.name.split(".")[0]
            table[a.asname or root] = ("module", a.name if a.asname
                                       else root)
    else:
        mod = stmt.module or ""
        for a in stmt.names:
            table[a.asname or a.name] = ("from", mod, a.name)


class Result:
    __slots__ = ("fall", "conts", "breaks", "rets")

    def __init__(self, fall=None):
        self.fall = fall
        self.conts, self.breaks, self.rets = [], [], []


def _either(vals):
    vals = _uniq(vals)
    return vals[0] if len(vals) == 1 else Val("either", vals)


def vals_of(v):
    return v.payload if isinstance(v, Val) and v.kind == "either" else (v,)


def norm(v):
    return resolve(v.payload) if isinstance(v, Val) and \
        v.kind == "either" else v


def _assigned_names(stmts):
    names = set()
    for s in stmts:
        for n in _walk_scope(s):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                names.add(n.id)
    return names


def _walk_scope(node):
    """ast.walk that never enters a nested function, lambda or class."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.Lambda, ast.ClassDef)):
                if GUARDS["scope_isolation"]:
                    continue
            stack.append(c)


class Interp:
    def __init__(self, index):
        self.index = index
        self.steps = 0

    def tick(self):
        self.steps += 1
        if self.steps > STEP_BUDGET:
            raise Budget()

    def new_frame(self, st, ctx, **kw):
        fid = next(ctx["fids"])
        st.heap[fid] = Frame(**kw)
        return Val("frame", fid)

    # ---------------------------------------------------- statements
    def exec_block(self, stmts, st, ctx) -> Result:
        res = Result(st)
        for s in stmts:
            if res.fall is None:
                break
            r = self.exec_stmt(s, res.fall, ctx)
            res.conts += r.conts
            res.breaks += r.breaks
            res.rets += r.rets
            res.fall = r.fall
        return res

    def exec_stmt(self, s, st, ctx) -> Result:
        self.tick()
        r = Result(st)
        if isinstance(s, ast.Assign):
            v = self.eval(s.value, st, ctx)
            for t in s.targets:
                self.assign(t, v, st, ctx)
        elif isinstance(s, ast.AugAssign):
            cur = self.eval(_as_load(s.target), st, ctx)
            v = self.binop(cur, self.eval(s.value, st, ctx), s.op)
            self.assign(s.target, v, st, ctx)
        elif isinstance(s, ast.AnnAssign):
            if s.value is not None:
                self.assign(s.target, self.eval(s.value, st, ctx), st, ctx)
        elif isinstance(s, ast.Expr):
            self.eval(s.value, st, ctx)
        elif isinstance(s, ast.If):
            return self.exec_if(s, st, ctx)
        elif isinstance(s, (ast.For, ast.AsyncFor)):
            return self.exec_for(s, st, ctx)
        elif isinstance(s, ast.While):
            self.eval(s.test, st, ctx)
            return self.havoc_loop(s.body, s.orelse, st, ctx, None)
        elif isinstance(s, ast.Try) or type(s).__name__ == "TryStar":
            return self.exec_try(s, st, ctx)
        elif isinstance(s, (ast.With, ast.AsyncWith)):
            for item in s.items:
                self.eval(item.context_expr, st, ctx)
                if item.optional_vars is not None:
                    self.assign(item.optional_vars,
                                unknown("CONTEXT_MANAGER_VALUE"), st, ctx)
            return self.exec_block(s.body, st, ctx)
        elif isinstance(s, ast.Return):
            v = (self.eval(s.value, st, ctx) if s.value is not None
                 else const(None))
            r.rets.append((v, st))
            r.fall = None
        elif isinstance(s, ast.Continue):
            r.conts.append(st)
            r.fall = None
        elif isinstance(s, ast.Break):
            r.breaks.append(st)
            r.fall = None
        elif isinstance(s, ast.Raise):
            r.fall = None
        elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not GUARDS["scope_isolation"]:
                # MUTANT: the v2 defect — a nested body read as the outer
                inner = self.exec_block(s.body, st, ctx)
                if inner.fall is not None:
                    st.env.update(inner.fall.env)
            st.env[s.name] = (Val("callable", (
                "def", ctx["module"], s, None, dict(st.env))),)
        elif isinstance(s, ast.ClassDef):
            st.env[s.name] = (unknown("NESTED_CLASS"),)
        elif isinstance(s, (ast.Import, ast.ImportFrom)):
            table = {}
            _bind_imports(s, table)
            for k, v in table.items():
                st.env[k] = (Val("import", v),)
        elif isinstance(s, (ast.Global, ast.Nonlocal)):
            for n in s.names:
                st.env[n] = (unknown("DYNAMIC_SCOPE"),)
        elif isinstance(s, ast.Delete):
            for t in s.targets:
                if isinstance(t, ast.Name):
                    st.env.pop(t.id, None)
                else:
                    ctx["taint"].add("DELETE_OF_NON_NAME")
        elif isinstance(s, (ast.Pass, ast.Assert)):
            pass
        else:
            ctx["taint"].add(f"UNSUPPORTED_STATEMENT:{type(s).__name__}")
        return r

    def exec_if(self, s, st, ctx) -> Result:
        test = self.eval(s.test, st, ctx)
        t = norm(test)
        if is_const(t):
            return self.exec_block(s.body if t.payload else s.orelse,
                                   st, ctx)
        a, b = st.clone(), st.clone()
        _narrow(s.test, a, b)
        ra = self.exec_block(s.body, a, ctx)
        rb = self.exec_block(s.orelse, b, ctx)
        return self._merge_branches(st, [ra, rb], test)

    def _merge_branches(self, pre, results, test):
        out = Result(join_states([r.fall for r in results]))
        for r in results:
            out.conts += r.conts
            out.breaks += r.breaks
            out.rets += r.rets
        if isinstance(test, Flow):
            # the path taken depends on data: every definition that the
            # branches changed inherits that dependency as a refusal
            taint = unknown("CONTROL_DEPENDS_ON_DATA", test)
            for s in [out.fall, *out.conts, *out.breaks,
                      *(x for _, x in out.rets)]:
                if s is not None:
                    _taint_changes(pre, s, taint)
        return out

    def exec_for(self, s, st, ctx) -> Result:
        it = norm(self.eval(s.iter, st, ctx))
        items = _unrollable(it, st)
        if items is None:
            return self.havoc_loop(s.body, s.orelse, st, ctx, s.target)
        cur, breaks, out = st, [], Result(None)
        for item in items:
            self.assign(s.target, item, cur, ctx)
            r = self.exec_block(s.body, cur, ctx)
            breaks += r.breaks
            out.rets += r.rets
            cur = join_states([r.fall, *r.conts])
            if cur is None:
                break
            cur = cur.clone()
        if cur is not None and s.orelse:
            r = self.exec_block(s.orelse, cur, ctx)
            out.rets += r.rets
            out.conts += r.conts
            cur = r.fall
        out.fall = join_states([cur, *breaks])
        return out

    def havoc_loop(self, body, orelse, st, ctx, target):
        """A loop whose iteration count is unknown: whatever its body
        writes may or may not have happened, any number of times."""
        pre = st.clone()
        once = st.clone()
        if target is not None:
            self.assign(target, unknown("LOOP_VARIABLE"), once, ctx)
        r = self.exec_block(body, once, ctx)
        after = join_states([pre, r.fall, *r.conts, *r.breaks]) or pre
        taint = unknown("LOOP_BODY_DEFINITION")
        _taint_changes(pre, after, taint, force=True)
        out = Result(after)
        out.rets += r.rets
        if orelse:
            r2 = self.exec_block(orelse, after, ctx)
            out.rets += r2.rets
            out.fall = r2.fall
        return out

    def exec_try(self, s, st, ctx) -> Result:
        pre = st.clone()
        rb = self.exec_block(s.body, st.clone(), ctx)
        # an exception may leave the body anywhere: handlers start from
        # the join of before and after
        mid = join_states([pre, rb.fall]) or pre
        _taint_changes(pre, mid, unknown("EXCEPTION_PATH_DEFINITION"),
                       force=True)
        results = []
        if rb.fall is not None and s.orelse:
            results.append(self.exec_block(s.orelse, rb.fall, ctx))
        else:
            results.append(Result(rb.fall))
        for h in s.handlers:
            hs = mid.clone()
            if h.name:
                hs.env[h.name] = (unknown("EXCEPTION_VALUE"),)
            results.append(self.exec_block(h.body, hs, ctx))
        out = Result(join_states([r.fall for r in results]))
        out.rets += rb.rets
        for r in results:
            out.rets += r.rets
            out.conts += r.conts
            out.breaks += r.breaks
        if s.finalbody and out.fall is not None:
            rf = self.exec_block(s.finalbody, out.fall, ctx)
            out.rets += rf.rets
            out.fall = rf.fall
        return out

    # ---------------------------------------------------- assignment
    def assign(self, t, v, st, ctx):
        if isinstance(t, ast.Name):
            if not GUARDS["reaching_definitions"] and t.id in st.env:
                return  # MUTANT: v2 kept the first definition
            st.env[t.id] = vals_of(v)
        elif isinstance(t, (ast.Tuple, ast.List)):
            v = norm(v)
            items = None
            if isinstance(v, Val) and v.kind in ("seq", "const") and \
                    isinstance(v.payload, (tuple, list)) and \
                    len(v.payload) == len(t.elts):
                items = [x if v.kind == "seq" else const(x)
                         for x in v.payload]
            for i, e in enumerate(t.elts):
                self.assign(e, items[i] if items else
                            unknown("UNPACKING_OF_UNKNOWN_VALUE"), st, ctx)
        elif isinstance(t, ast.Subscript):
            obj = norm(self.eval(t.value, st, ctx))
            key = norm(self.eval(t.slice, st, ctx))
            if isinstance(obj, Val) and obj.kind in ("frame", "frameset"):
                fids = ([obj.payload] if obj.kind == "frame"
                        else list(obj.payload))
                for fid in fids:
                    fr = st.heap[fid]
                    if is_const(key) and isinstance(key.payload, str):
                        new = vals_of(v)
                        fr.cols[key.payload] = (
                            new if len(fids) == 1
                            else _uniq(fr.cols.get(key.payload, ()) + new))
                    else:
                        fr.havoc |= {"DYNAMIC_COLUMN_WRITE"}
            elif isinstance(obj, Val) and obj.kind == "indexer":
                inner = obj.payload
                if isinstance(inner, Val) and inner.kind == "frame":
                    st.heap[inner.payload].havoc |= {"POSITIONAL_WRITE"}
                self._rebind_root(t.value, st, "POSITIONAL_WRITE")
            else:
                self._rebind_root(t.value, st, "SUBSCRIPT_WRITE")
        elif isinstance(t, ast.Attribute):
            ctx["taint"].add("ATTRIBUTE_WRITE") if isinstance(
                t.value, ast.Name) and t.value.id != "self" else None
        elif isinstance(t, ast.Starred):
            self.assign(t.value, unknown("STARRED_ASSIGNMENT"), st, ctx)

    def _rebind_root(self, node, st, code):
        while isinstance(node, (ast.Attribute, ast.Subscript)):
            node = node.value
        if isinstance(node, ast.Name) and node.id in st.env:
            cur = [v for v in st.env[node.id]]
            if any(isinstance(v, Val) and v.kind == "frame" for v in cur):
                for v in cur:
                    if isinstance(v, Val) and v.kind == "frame":
                        st.heap[v.payload].havoc |= {code}
            else:
                st.env[node.id] = (unknown(code),)

def _as_load(t):
    t2 = copy.deepcopy(t)
    for n in ast.walk(t2):
        if hasattr(n, "ctx"):
            n.ctx = ast.Load()
    return t2


def _narrow(test, yes: State, no: State):
    """`x is not None` / `x is None`: keep only the matching bindings."""
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and \
            isinstance(test.left, ast.Name) and \
            isinstance(test.comparators[0], ast.Constant) and \
            test.comparators[0].value is None and \
            isinstance(test.ops[0], (ast.Is, ast.IsNot)):
        name = test.left.id
        if name not in yes.env:
            return
        is_none = [v for v in yes.env[name] if is_const(v) and v.payload is None]
        other = [v for v in yes.env[name] if not (is_const(v) and v.payload is None)]
        pos, neg = (other, is_none) if isinstance(test.ops[0], ast.IsNot) \
            else (is_none, other)
        if pos:
            yes.env[name] = tuple(pos)
        if neg:
            no.env[name] = tuple(neg)


def _taint_changes(pre: State, post: State, taint: Flow, force=False):
    for n, vals in post.env.items():
        if pre.env.get(n) != vals or (force and n not in pre.env):
            if pre.env.get(n) != vals:
                post.env[n] = _uniq(vals + (taint,))
    for fid, fr in post.heap.items():
        old = pre.heap.get(fid)
        for c, vals in fr.cols.items():
            if old is None or old.cols.get(c) != vals:
                fr.cols[c] = _uniq(vals + (taint,))


def _unrollable(it, st):
    if is_const(it) and isinstance(it.payload, (tuple, list)):
        items = [const(x) for x in it.payload]
    elif isinstance(it, Val) and it.kind == "seq":
        items = list(it.payload)
    elif isinstance(it, Val) and it.kind == "columns":
        fr = st.heap.get(it.payload)
        if fr is None or not fr.exact or fr.havoc:
            return None
        items = [const(c) for c in fr.cols]
    else:
        return None
    return items if len(items) <= MAX_UNROLL else None


def _const_binop(a, b, op):
    ops = {ast.Add: lambda x, y: x + y, ast.Sub: lambda x, y: x - y,
           ast.Mult: lambda x, y: x * y, ast.Div: lambda x, y: x / y,
           ast.FloorDiv: lambda x, y: x // y, ast.Mod: lambda x, y: x % y,
           ast.Pow: lambda x, y: x ** y}
    fn = ops.get(type(op))
    if fn is None:
        return SCALAR
    try:
        return const(fn(a, b))
    except Exception:
        return SCALAR


def _int_amount(v):
    return v.payload if is_const(v) and isinstance(v.payload, int) and \
        not isinstance(v.payload, bool) else None


def _amount_refusal(v, what):
    if isinstance(v, Val) and v.kind == "param":
        return unknown(f"WINDOW_FROM_PARAMETER:{v.payload}")
    if isinstance(v, Flow) and v.params:
        return unknown("WINDOW_FROM_PARAMETER:" + ",".join(sorted(v.params)))
    return unknown(f"NON_LITERAL_{what}")


class _Eval:
    # ---------------------------------------------------- expressions
    def eval(self, n, st, ctx):
        self.tick()
        if isinstance(n, ast.Constant):
            return const(n.value)
        if isinstance(n, ast.Name):
            return self.lookup(n.id, st, ctx)
        if isinstance(n, ast.JoinedStr):
            parts = []
            for p in n.values:
                if isinstance(p, ast.Constant):
                    parts.append(str(p.value))
                    continue
                v = norm(self.eval(p.value, st, ctx))
                if not is_const(v) or p.format_spec is not None:
                    return unknown("DYNAMIC_STRING")
                parts.append(str(v.payload))
            return const("".join(parts))
        if isinstance(n, (ast.List, ast.Tuple, ast.Set)):
            items = [norm(self.eval(e, st, ctx)) for e in n.elts]
            if all(is_const(i) for i in items):
                return const(tuple(i.payload for i in items))
            return Val("seq", tuple(items))
        if isinstance(n, ast.Dict):
            if any(k is None for k in n.keys):
                return unknown("DICT_UNPACKING")
            return Val("dict", tuple(
                (norm(self.eval(k, st, ctx)), norm(self.eval(v, st, ctx)))
                for k, v in zip(n.keys, n.values)))
        if isinstance(n, ast.Attribute):
            return self.attribute(norm(self.eval(n.value, st, ctx)),
                                  n.attr, st, ctx)
        if isinstance(n, ast.Subscript):
            return self.subscript(norm(self.eval(n.value, st, ctx)),
                                  norm(self.eval(n.slice, st, ctx)),
                                  st, ctx)
        if isinstance(n, ast.Slice):
            for part in (n.lower, n.upper, n.step):
                if part is not None:
                    self.eval(part, st, ctx)
            return Val("slice")
        if isinstance(n, ast.BinOp):
            return self.binop(self.eval(n.left, st, ctx),
                              self.eval(n.right, st, ctx), n.op)
        if isinstance(n, ast.UnaryOp):
            v = norm(self.eval(n.operand, st, ctx))
            if is_const(v):
                try:
                    return const({ast.USub: lambda x: -x,
                                  ast.UAdd: lambda x: +x,
                                  ast.Not: lambda x: not x,
                                  ast.Invert: lambda x: ~x}[type(n.op)](
                                      v.payload))
                except Exception:
                    return SCALAR
            return self.binop(v, const(0), ast.Add())
        if isinstance(n, ast.BoolOp):
            vals = [norm(self.eval(v, st, ctx)) for v in n.values]
            if all(is_const(v) for v in vals):
                out = vals[0].payload
                for v in vals[1:]:
                    out = (out and v.payload) if isinstance(
                        n.op, ast.And) else (out or v.payload)
                return const(out)
            flows = [as_flow(v) for v in vals]
            flows = [f for f in flows if f is not None]
            return combine(*flows) if flows else SCALAR
        if isinstance(n, ast.Compare):
            return self.compare(n, st, ctx)
        if isinstance(n, ast.IfExp):
            test = norm(self.eval(n.test, st, ctx))
            if is_const(test):
                return self.eval(n.body if test.payload else n.orelse,
                                 st, ctx)
            a = self.eval(n.body, st, ctx)
            b = self.eval(n.orelse, st, ctx)
            vals = vals_of(a) + vals_of(b)
            if isinstance(test, Flow):
                return unknown("CONTROL_DEPENDS_ON_DATA", test,
                               *[v for v in vals if isinstance(v, Flow)])
            return _either(vals)
        if isinstance(n, ast.Call):
            return self.call(n, st, ctx)
        if isinstance(n, ast.Lambda):
            return Val("callable", ("lambda", ctx["module"], n, ctx["cls"],
                                    dict(st.env)))
        if isinstance(n, (ast.ListComp, ast.GeneratorExp)):
            return self.comprehension(n, st, ctx)
        return unknown(f"UNSUPPORTED_EXPRESSION:{type(n).__name__}")

    def comprehension(self, n, st, ctx):
        if len(n.generators) != 1 or n.generators[0].ifs or \
                n.generators[0].is_async:
            return unknown("COMPREHENSION")
        g = n.generators[0]
        items = _unrollable(norm(self.eval(g.iter, st, ctx)), st)
        if items is None:
            return unknown("COMPREHENSION")
        out = []
        for item in items:
            inner = State(dict(st.env), st.heap)
            self.assign(g.target, item, inner, ctx)
            out.append(norm(self.eval(n.elt, inner, ctx)))
        if all(is_const(i) for i in out):
            return const(tuple(i.payload for i in out))
        return Val("seq", tuple(out))

    def lookup(self, name, st, ctx):
        if name in st.env:
            vals = st.env[name]
            if len(vals) == 1:
                return vals[0]
            if all(isinstance(v, Flow) for v in vals):
                return resolve(vals)
            if all(isinstance(v, Val) and v.kind == "frame" for v in vals):
                return resolve(vals)
            return _either(vals)
        mod = ctx["module"]
        if name in mod.consts:
            return const(mod.consts[name])
        if name in mod.defs:
            defs = mod.defs[name]
            if len(defs) > 1:
                return unknown(f"AMBIGUOUS_HELPER:{name}:defined "
                               f"{len(defs)} times")
            return Val("callable", ("def", mod, defs[0], None, None))
        if name in mod.imports:
            return Val("import", mod.imports[name])
        if name in MODULE_ALIASES:
            return Val("module", MODULE_ALIASES[name])
        if name in BUILTIN_CONST or name in (
                "isinstance", "hasattr", "range", "list", "tuple", "zip",
                "enumerate", "sorted", "print", "dict", "set", "callable",
                "type", "sum", "any", "all", "map", "filter", "iter",
                "next", "repr", "format"):
            return Val("builtin", name)
        if name in DYNAMIC_NAMES:
            return Val("dynamic", name)
        if name in ("True", "False", "None"):
            return const({"True": True, "False": False}.get(name))
        if name in self.index.by_name:
            return unknown(f"HELPER_OUTSIDE_MODULE_SCOPE:{name}")
        return unknown(f"UNBOUND_NAME:{name}")

    def attribute(self, obj, attr, st, ctx):
        if isinstance(obj, Val) and obj.kind == "import" and \
                obj.payload[0] == "module":
            obj = Val("module", MODULE_ALIASES.get(
                obj.payload[1], obj.payload[1]))
        if isinstance(obj, Val) and obj.kind == "module":
            if attr in ("nan", "inf", "pi", "e", "NaN", "NA", "NaT",
                        "newaxis"):
                return SCALAR
            return Val("modattr", (obj.payload, attr))
        if isinstance(obj, Val) and obj.kind == "param":
            obj = Flow(leaves=(f"<param:{obj.payload}>",),
                       params=(obj.payload,))
        if isinstance(obj, Flow):
            if attr in ("values", "array", "str", "dt", "T"):
                return obj
            if attr in ("iloc", "loc", "iat", "at"):
                return Val("indexer", obj)
            if attr in ("hour", "minute", "second", "day", "month", "year",
                        "dayofweek", "weekday", "date", "dayofyear",
                        "quarter", "is_month_end", "is_month_start"):
                return obj
            if attr in ("shape", "size", "dtype", "name", "index", "ndim",
                        "empty", "dtypes", "columns"):
                return SCALAR
            return unknown(f"UNFOLLOWED_ATTRIBUTE:{attr}", obj)
        if isinstance(obj, Val) and obj.kind == "frame":
            if attr == "columns":
                return Val("columns", obj.payload)
            if attr in ("iloc", "loc", "iat", "at"):
                return Val("indexer", obj)
            if attr in ("index", "shape", "size", "dtypes", "ndim",
                        "empty"):
                return SCALAR
            if attr in ("values", "T"):
                return unknown("FRAME_ARRAY")
            return self.read_col(st, obj.payload, attr, ctx)
        if isinstance(obj, Val) and obj.kind == "self":
            return unknown(f"SELF_ATTRIBUTE:{attr}")
        if isinstance(obj, Flow):
            return obj
        return unknown(f"UNFOLLOWED_ATTRIBUTE:{attr}")

    def read_col(self, st, fid, col, ctx):
        fr = st.heap[fid]
        hav = [unknown(h) for h in sorted(fr.havoc)]
        if col in fr.cols:
            return resolve(fr.cols[col] + tuple(hav))
        if hav:
            return combine(*hav)
        if fr.base is not None:
            v = Flow(leaves=(col,))
            for m, a, k in fr.pending:
                v = self.flow_method(v, m, a, k, st, ctx)
            return v
        return unknown(f"COLUMN_NOT_DEFINED_ON_LOCAL_FRAME:{col}")

    def subscript(self, obj, key, st, ctx):
        if isinstance(obj, Val) and obj.kind == "frame":
            if is_const(key) and isinstance(key.payload, str):
                return self.read_col(st, obj.payload, key.payload, ctx)
            if is_const(key) and isinstance(key.payload, tuple) and \
                    all(isinstance(k, str) for k in key.payload):
                src = st.heap[obj.payload]
                new = self.new_frame(st, ctx)
                nf = st.heap[new.payload]
                for k in key.payload:
                    nf.cols[k] = (self.read_col(st, obj.payload, k, ctx),)
                return new
            if not GUARDS["positional_index"]:
                return obj
            return unknown("POSITIONAL_INDEX:frame")
        if isinstance(obj, Val) and obj.kind == "frameset":
            if is_const(key) and isinstance(key.payload, str):
                return resolve([self.read_col(st, f, key.payload, ctx)
                                for f in obj.payload])
            return unknown("POSITIONAL_INDEX:frame")
        if isinstance(obj, Val) and obj.kind == "indexer":
            inner = obj.payload
            if not GUARDS["positional_index"]:
                return inner if isinstance(inner, Flow) else unknown(
                    "POSITIONAL_INDEX:indexer")
            return unknown("POSITIONAL_INDEX:" + (
                "iloc/loc" if True else ""),
                inner if isinstance(inner, Flow) else Flow())
        if isinstance(obj, Flow):
            if not GUARDS["positional_index"]:
                return obj
            return unknown("POSITIONAL_INDEX:series", obj)
        if isinstance(obj, Val) and obj.kind == "dict" and is_const(key):
            for k, v in obj.payload:
                if is_const(k) and k.payload == key.payload:
                    return v
            return unknown("DICT_KEY_NOT_FOUND")
        if isinstance(obj, Val) and obj.kind == "seq" and \
                _int_amount(key) is not None:
            try:
                return obj.payload[key.payload]
            except IndexError:
                return unknown("SEQUENCE_INDEX")
        if is_const(obj) and is_const(key):
            try:
                return const(obj.payload[key.payload])
            except Exception:
                return SCALAR
        if isinstance(obj, Val) and obj.kind in ("columns", "scalar"):
            return SCALAR
        return unknown("DYNAMIC_SUBSCRIPT")

    def binop(self, a, b, op):
        a, b = norm(a), norm(b)
        if is_const(a) and is_const(b):
            return _const_binop(a.payload, b.payload, op)
        for v in (a, b):
            if isinstance(v, Val) and v.kind in ("frame", "frameset",
                                                  "window", "callable"):
                return unknown(f"UNSUPPORTED_ARITHMETIC:{v.kind}")
        fa, fb = as_flow(a), as_flow(b)
        flows = [f for f in (fa, fb) if f is not None]
        return combine(*flows) if flows else SCALAR

    def compare(self, n, st, ctx):
        if len(n.ops) == 1 and isinstance(n.ops[0], (ast.Is, ast.IsNot)):
            # identity against None is a question about which binding
            # reached, never a read of the data
            lv = self.eval(n.left, st, ctx)
            rv = self.eval(n.comparators[0], st, ctx)
            if is_const(lv) and is_const(rv):
                same = lv.payload is rv.payload
                return const(same if isinstance(n.ops[0], ast.Is)
                             else not same)
            return SCALAR
        left = norm(self.eval(n.left, st, ctx))
        rights = [norm(self.eval(c, st, ctx)) for c in n.comparators]
        if len(n.ops) == 1:
            op, r = n.ops[0], rights[0]
            if isinstance(op, (ast.In, ast.NotIn)) and \
                    isinstance(r, Val) and r.kind == "columns":
                fr = st.heap.get(r.payload)
                if is_const(left) and fr is not None and fr.exact and \
                        not fr.havoc:
                    res = left.payload in fr.cols
                    return const(res if isinstance(op, ast.In) else not res)
                return SCALAR
            if is_const(left) and is_const(r):
                try:
                    fn = {ast.Eq: lambda x, y: x == y,
                          ast.NotEq: lambda x, y: x != y,
                          ast.Is: lambda x, y: x is y,
                          ast.IsNot: lambda x, y: x is not y,
                          ast.Lt: lambda x, y: x < y,
                          ast.LtE: lambda x, y: x <= y,
                          ast.Gt: lambda x, y: x > y,
                          ast.GtE: lambda x, y: x >= y,
                          ast.In: lambda x, y: x in y,
                          ast.NotIn: lambda x, y: x not in y}[type(op)]
                    return const(fn(left.payload, r.payload))
                except Exception:
                    return SCALAR
        flows = [as_flow(v) for v in [left, *rights]]
        flows = [f for f in flows if f is not None]
        return combine(*flows) if flows else SCALAR

class _Calls:
    def call(self, n, st, ctx):
        if any(isinstance(a, ast.Starred) for a in n.args) or \
                any(k.arg is None for k in n.keywords):
            flows = []
            for a in n.args:
                v = norm(self.eval(getattr(a, "value", a), st, ctx))
                self._havoc_frames(v, st, "MUTATION_BY_DYNAMIC_CALL")
                flows.append(as_flow(v) or Flow())
            return unknown("DYNAMIC_ARGUMENTS", *flows)
        f = n.func
        if isinstance(f, ast.Attribute):
            recv = norm(self.eval(f.value, st, ctx))
            args = [norm(self.eval(a, st, ctx)) for a in n.args]
            kw = {k.arg: norm(self.eval(k.value, st, ctx))
                  for k in n.keywords}
            return self.method(recv, f.attr, args, kw, st, ctx)
        args = [norm(self.eval(a, st, ctx)) for a in n.args]
        kw = {k.arg: norm(self.eval(k.value, st, ctx)) for k in n.keywords}
        if isinstance(f, ast.Lambda):
            fn = self.eval(f, st, ctx)
            return self.call_value(fn, args, kw, st, ctx)
        if not isinstance(f, ast.Name):
            return self._unknown_call("DYNAMIC_DISPATCH:call_of_expression",
                                      args, kw, st)
        fn = self.eval(f, st, ctx)
        return self.call_value(fn, args, kw, st, ctx, name=f.id)

    def _havoc_frames(self, v, st, code):
        if isinstance(v, Val) and v.kind == "frame":
            st.heap[v.payload].havoc |= {code}
        elif isinstance(v, Val) and v.kind == "seq":
            for x in v.payload:
                self._havoc_frames(x, st, code)

    def _unknown_call(self, code, args, kw, st):
        flows = []
        for v in [*args, *kw.values()]:
            self._havoc_frames(v, st, "MUTATION_BY_UNKNOWN_CALL")
            if isinstance(v, Flow):
                flows.append(v)
        return unknown(code, *flows)

    def call_value(self, fn, args, kw, st, ctx, name=None):
        if isinstance(fn, Val) and fn.kind == "either":
            return self._unknown_call(
                f"AMBIGUOUS_HELPER:{name}:several reaching definitions",
                args, kw, st)
        if isinstance(fn, Val) and fn.kind == "callable":
            return self.call_user(fn, args, kw, st, ctx)
        if isinstance(fn, Val) and fn.kind == "dynamic":
            return self._unknown_call(f"DYNAMIC_DISPATCH:{fn.payload}",
                                      args, kw, st)
        if isinstance(fn, Val) and fn.kind == "modattr":
            return self.library_call(fn.payload[0], fn.payload[1], args,
                                     kw, st, ctx)
        if isinstance(fn, Val) and fn.kind == "import":
            spec = fn.payload
            if spec[0] == "from" and spec[1].split(".")[0] in (
                    "numpy", "pandas", "math"):
                return self.library_call(spec[1].split(".")[0], spec[2],
                                         args, kw, st, ctx)
            return self._unknown_call(f"UNFOLLOWED_IMPORT:{name}", args,
                                      kw, st)
        if isinstance(fn, Val) and fn.kind == "builtin":
            return self.builtin(fn.payload, args, kw, st)
        if isinstance(fn, Flow) and fn.unresolved:
            return self._unknown_call(sorted(fn.unresolved)[0], args, kw,
                                      st)
        if name and name in ctx["module"].classes:
            return self._unknown_call(f"CLASS_INSTANTIATION:{name}", args,
                                      kw, st)
        return self._unknown_call(f"UNFOLLOWED_CALL:{name}", args, kw, st)

    def builtin(self, name, args, kw, st):
        if name in BUILTIN_CONST and args and all(is_const(a) for a in args):
            try:
                return const(BUILTIN_CONST[name](*[a.payload for a in args]))
            except Exception:
                return SCALAR
        if name == "range" and all(_int_amount(a) is not None for a in args):
            r = range(*[a.payload for a in args])
            return const(tuple(r)) if len(r) <= MAX_UNROLL else SCALAR
        if name in ("list", "tuple", "sorted") and len(args) == 1:
            a = args[0]
            if is_const(a) and isinstance(a.payload, (tuple, list)):
                vals = tuple(sorted(a.payload)) if name == "sorted" \
                    else tuple(a.payload)
                return const(vals)
            if isinstance(a, Val) and a.kind in ("seq", "columns") and \
                    name != "sorted":
                return a
        if name in ("zip", "enumerate") and args and \
                all(is_const(a) for a in args):
            fn = zip if name == "zip" else enumerate
            return const(tuple(fn(*[a.payload for a in args])))
        if name == "abs" and len(args) == 1 and isinstance(args[0], Flow):
            return args[0]
        if name in ("len", "isinstance", "hasattr", "callable", "type",
                    "repr", "print", "format"):
            return SCALAR
        return self._unknown_call(f"BUILTIN_ON_NON_CONSTANT:{name}", args,
                                  kw, st)

    # ------------------------------------------------------- libraries
    def library_call(self, module, name, args, kw, st, ctx):
        allv = [*args, *kw.values()]
        if module == "numpy":
            if name == "roll":
                a = args[0] if args else None
                k = args[1] if len(args) > 1 else kw.get("shift")
                if not isinstance(a, Flow):
                    return unknown("NP_ROLL_OF_NON_SERIES")
                amt = _int_amount(k) if k is not None else None
                if amt is None:
                    return _amount_refusal(k, "ROLL")
                if amt == 0:
                    return a
                # both directions wrap around: the first |k| rows of a
                # positive roll are read from the END of the array
                return Flow(a.leaves, None, a.hi,
                            a.forward | {f"roll({amt})"}, a.unresolved,
                            a.params, a.helpers, a.notes)
            if name in ("cumsum", "cumprod", "nancumsum"):
                a = args[0] if args else None
                if isinstance(a, Flow):
                    return a.shifted(0, None)
            if name in NP_ELEMENTWISE:
                flows = [v for v in allv if isinstance(v, Flow)]
                bad = [v for v in allv if isinstance(v, Val) and v.kind in (
                    "frame", "frameset", "seq", "callable", "window",
                    "indexer", "dict")]
                if bad:
                    return self._unknown_call(
                        f"UNSUPPORTED_LIBRARY_ARGUMENT:numpy.{name}",
                        args, kw, st)
                if flows:
                    params = [v.payload for v in allv
                              if isinstance(v, Val) and v.kind == "param"]
                    return combine(*flows, Flow(params=params))
                if name in MATH_CONST_FUNCS and len(args) == 1 and \
                        is_const(args[0]):
                    try:
                        return const(MATH_CONST_FUNCS[name](args[0].payload))
                    except Exception:
                        return SCALAR
                return SCALAR
        if module == "pandas":
            if name == "concat":
                axis = kw.get("axis")
                seq = args[0] if args else kw.get("objs")
                if not (is_const(axis) and axis.payload in (1, "columns")) \
                        or not (isinstance(seq, Val) and seq.kind == "seq"):
                    return self._unknown_call("CONCAT_ALONG_ROWS", args, kw,
                                              st)
                new = self.new_frame(st, ctx)
                nf = st.heap[new.payload]
                for i, item in enumerate(seq.payload):
                    if isinstance(item, Flow):
                        nf.cols[f"<{i}>"] = (item,)
                    elif isinstance(item, Val) and item.kind == "frame":
                        src = st.heap[item.payload]
                        if not src.exact or src.havoc:
                            nf.havoc |= {"CONCAT_OF_UNKNOWN_COLUMNS"}
                        for c, v in src.cols.items():
                            nf.cols[c] = v
                    else:
                        nf.havoc |= {"CONCAT_OF_NON_SERIES"}
                return new
            if name == "DataFrame":
                data = args[0] if args else kw.get("data")
                if data is None:
                    return self.new_frame(st, ctx)
                if isinstance(data, Val) and data.kind == "dict" and all(
                        is_const(k) and isinstance(k.payload, str)
                        for k, _ in data.payload):
                    new = self.new_frame(st, ctx)
                    for k, v in data.payload:
                        st.heap[new.payload].cols[k.payload] = (
                            v if isinstance(v, Flow)
                            else unknown("NON_SERIES_COLUMN"),)
                    return new
                return self.new_frame(st, ctx, havoc=(
                    "DATAFRAME_FROM_UNKNOWN_DATA",), exact=False)
            if name == "Series":
                data = args[0] if args else kw.get("data")
                if isinstance(data, Flow):
                    return data
                return unknown("SERIES_FROM_NON_SERIES")
            if name in PD_ELEMENTWISE:
                flows = [v for v in allv if isinstance(v, Flow)]
                return combine(*flows) if flows else SCALAR
        if module == "math" and name in MATH_CONST_FUNCS and \
                len(args) == 1 and is_const(args[0]):
            try:
                return const(MATH_CONST_FUNCS[name](args[0].payload))
            except Exception:
                return SCALAR
        return self._unknown_call(f"UNFOLLOWED_LIBRARY_CALL:{module}.{name}",
                                  args, kw, st)

    # --------------------------------------------------------- methods
    def method(self, recv, m, args, kw, st, ctx):
        if isinstance(recv, Val) and recv.kind == "import" and \
                recv.payload[0] == "module":
            recv = Val("module", MODULE_ALIASES.get(recv.payload[1],
                                                    recv.payload[1]))
        if isinstance(recv, Val) and recv.kind == "module":
            return self.library_call(recv.payload, m, args, kw, st, ctx)
        if isinstance(recv, Val) and recv.kind == "self":
            meths = ctx["module"].classes.get(recv.payload, {}).get(m, [])
            if len(meths) == 1:
                fn = Val("callable", ("def", ctx["module"], meths[0],
                                      recv.payload, None))
                return self.call_user(fn, args, kw, st, ctx, bound=recv)
            return self._unknown_call(
                f"UNFOLLOWED_SELF_METHOD:{m}:{len(meths)} definitions",
                args, kw, st)
        if isinstance(recv, Val) and recv.kind == "param":
            recv = Flow(leaves=(f"<param:{recv.payload}>",),
                        params=(recv.payload,))
        if isinstance(recv, Flow):
            return self.flow_method(recv, m, args, kw, st, ctx)
        if isinstance(recv, Val) and recv.kind == "frame":
            return self.frame_method(recv, m, args, kw, st, ctx)
        if isinstance(recv, Val) and recv.kind == "window":
            return self.window_method(recv, m, args, kw, st, ctx)
        if isinstance(recv, Val) and recv.kind == "columns":
            return recv if m in ("tolist", "to_list", "copy") else SCALAR
        if is_const(recv) and all(is_const(a) for a in args):
            try:
                return const(getattr(recv.payload, m)(
                    *[a.payload for a in args]))
            except Exception:
                return SCALAR
        return self._unknown_call(
            f"UNFOLLOWED_METHOD:{m}:on_{getattr(recv, 'kind', 'value')}",
            args, kw, st)

    def flow_method(self, f, m, args, kw, st, ctx):
        if is_const(kw.get("inplace")) and kw["inplace"].payload:
            return unknown(f"INPLACE_MUTATION:{m}", f)
        extra = [v for v in [*args, *kw.values()] if isinstance(v, Flow)]
        if m == "shift":
            if "freq" in kw:
                return unknown("TIME_SHIFT", f)
            k = args[0] if args else kw.get("periods", const(1))
            amt = _int_amount(k)
            if amt is None:
                return _amount_refusal(k, "SHIFT")
            return f.shifted(amt, amt, forward=[f"shift({amt})"]
                             if amt < 0 else [])
        if m in ("diff", "pct_change"):
            k = args[0] if args else kw.get("periods", const(1))
            amt = _int_amount(k)
            if amt is None:
                return _amount_refusal(k, m.upper())
            out = f.shifted(min(0, amt), max(0, amt),
                            forward=[f"{m}({amt})"] if amt < 0 else [])
            fm = kw.get("fill_method")
            if m == "pct_change" and not (is_const(fm) and fm.payload is None):
                # pandas pads NaNs before a pct_change unless told not
                # to: the value can reach an arbitrarily old bar
                out = out.shifted(0, None,
                                  notes=["pct_change pads by default"])
            return out
        if m in ("ffill", "pad", "cumsum", "cumprod", "cummax", "cummin"):
            return f.shifted(0, None)
        if m in ("bfill", "backfill", "interpolate"):
            return Flow(f.leaves, None, f.hi, f.forward | {f"{m}()"},
                        f.unresolved, f.params, f.helpers, f.notes)
        if m == "fillna":
            meth = kw.get("method")
            if is_const(meth) and meth.payload in ("bfill", "backfill"):
                return Flow(f.leaves, None, f.hi,
                            f.forward | {"fillna(bfill)"}, f.unresolved,
                            f.params, f.helpers, f.notes)
            if is_const(meth) and meth.payload in ("ffill", "pad"):
                return f.shifted(0, None)
            return combine(f, *extra)
        if m in ("rolling", "expanding", "ewm"):
            return self.make_window(f, m, args, kw)
        if m in CALLABLE_METHODS:
            return self.follow_callable(f, m, args, kw, st, ctx)
        if m in POSITIONAL_METHODS:
            if not GUARDS["positional_index"]:
                return f
            return unknown(f"POSITIONAL_SELECTION:{m}", f)
        if m in ROW_TRANSFORMS:
            return unknown(f"ROW_TRANSFORM:{m}", f)
        if m in REDUCTIONS:
            # a reduction over the whole series reads every row,
            # including the ones after the current bar
            base = combine(f, *extra)
            return Flow(base.leaves, None, None,
                        base.forward | {f"full_sample_{m}()"},
                        base.unresolved, base.params, base.helpers,
                        base.notes)
        if m in ELEMENTWISE_METHODS or m in (
                "contains", "startswith", "endswith", "len", "zfill"):
            if any(isinstance(v, Val) and v.kind == "callable"
                   for v in [*args, *kw.values()]):
                return unknown(f"CALLABLE_ARGUMENT_TO:{m}", f)
            return combine(f, *extra)
        return unknown(f"UNFOLLOWED_METHOD:{m}", f, *extra)

    def make_window(self, f, m, args, kw):
        if m == "expanding":
            return Val("window", (f, "expanding", None, False))
        if m == "ewm":
            if "times" in kw:
                return unknown("EWM_WITH_TIMES", f)
            size = [v for k, v in kw.items()
                    if k in ("span", "com", "halflife", "alpha")]
            size += args[:1]
            if not size:
                return unknown("EWM_WITHOUT_DECAY", f)
            for v in size:
                if not (is_const(v) and isinstance(v.payload, (int, float))):
                    return _amount_refusal(v, "WINDOW")
            return Val("window", (f, "ewm", None, False))
        w = args[0] if args else kw.get("window")
        center = kw.get("center")
        centred = is_const(center) and bool(center.payload)
        if is_const(w) and isinstance(w.payload, str):
            return unknown("TIME_BASED_WINDOW", f)
        size = _int_amount(w) if w is not None else None
        if size is None or size < 1:
            return _amount_refusal(w, "WINDOW")
        return Val("window", (f, "rolling", size, centred))

    def _reach(self, win, base):
        _, kind, size, centred = win.payload
        if kind != "rolling":
            return base.shifted(0, None)
        if centred:
            half = size // 2
            return Flow(base.leaves, _lo_add(base.lo, -half),
                        _hi_add(base.hi, size - 1 - half),
                        base.forward | {f"centred window({size})"},
                        base.unresolved, base.params, base.helpers,
                        base.notes)
        if not GUARDS["window_composition"]:
            # MUTANT: v2 took the widest window instead of composing
            hi = None if base.hi is None else max(base.hi, size - 1)
            return Flow(base.leaves, base.lo, hi, base.forward,
                        base.unresolved, base.params, base.helpers,
                        base.notes)
        return base.shifted(0, size - 1)

    def window_method(self, win, m, args, kw, st, ctx):
        f = win.payload[0]
        if m in ("corr", "cov"):
            other = args[0] if args else kw.get("other")
            if not isinstance(other, Flow):
                return unknown(f"WINDOW_{m.upper()}_WITHOUT_SERIES", f)
            return self._reach(win, combine(f, other))
        if m in ("apply", "agg", "aggregate"):
            fn = args[0] if args else kw.get("func")
            if is_const(fn) and fn.payload in REDUCTIONS:
                return self._reach(win, f)
            r = self._callable_result(f, fn, st, ctx)
            if r is None:
                return unknown(f"UNFOLLOWABLE_CALLABLE:rolling.{m}", f)
            return self._reach(win, combine(f, r))
        if m in REDUCTIONS:
            return self._reach(win, f)
        return unknown(f"UNFOLLOWED_WINDOW_METHOD:{m}", f)

    def _callable_result(self, f, fn, st, ctx):
        """The flow a callable produces from `f`, or None if unfollowable."""
        if not GUARDS["callable_following"]:
            return f  # MUTANT: v2 treated every callable as element-wise
        if isinstance(fn, Val) and fn.kind == "callable":
            r = self.call_user(fn, [f], {}, st, ctx)
            r = norm(r)
            return r if isinstance(r, Flow) else f
        if isinstance(fn, Val) and fn.kind == "modattr" and (
                (fn.payload[0] == "numpy" and fn.payload[1] in NP_ELEMENTWISE)
                or (fn.payload[0] == "pandas"
                    and fn.payload[1] in PD_ELEMENTWISE)):
            return f
        if isinstance(fn, Val) and fn.kind == "builtin" and fn.payload in (
                "float", "int", "abs", "str", "round", "bool"):
            return f
        if isinstance(fn, Val) and fn.kind == "dict":
            return f
        return None

    def follow_callable(self, f, m, args, kw, st, ctx):
        fn = args[0] if args else (kw.get("func") or kw.get("arg"))
        if is_const(fn) and isinstance(fn.payload, str):
            if fn.payload in REDUCTIONS:
                return self.flow_method(f, fn.payload, [], {}, st, ctx)
            return self.flow_method(f, fn.payload, [], {}, st, ctx)
        r = self._callable_result(f, fn, st, ctx)
        if r is None:
            return unknown(f"UNFOLLOWABLE_CALLABLE:{m}", f)
        return combine(f, r)

    def frame_method(self, fr, m, args, kw, st, ctx):
        fid = fr.payload
        src = st.heap[fid]
        if is_const(kw.get("inplace")) and kw["inplace"].payload:
            src.havoc |= {f"INPLACE_MUTATION:{m}"}
            return const(None)
        if m in SINK_METHODS:
            ctx["escapes"].append(_snapshot(src))
            return const(None)
        if m == "copy":
            new = self.new_frame(st, ctx)
            st.heap[new.payload] = src.clone()
            return new
        if m == "get" and args and is_const(args[0]):
            return self.read_col(st, fid, args[0].payload, ctx)
        if m == "assign":
            new = self.new_frame(st, ctx)
            st.heap[new.payload] = nf = src.clone()
            for k, v in kw.items():
                nf.cols[k] = (v if isinstance(v, Flow)
                              else unknown("NON_SERIES_COLUMN"),)
            return new
        if m == "pipe":
            fn = args[0] if args else kw.get("func")
            if isinstance(fn, Val) and fn.kind == "callable":
                return self.call_user(fn, [fr, *args[1:]], {}, st, ctx)
            return unknown("UNFOLLOWABLE_CALLABLE:pipe")
        if m in REDUCTIONS:
            axis = kw.get("axis")
            if is_const(axis) and axis.payload in (1, "columns"):
                if not src.exact or src.havoc:
                    return unknown("ROWWISE_OVER_UNKNOWN_COLUMNS")
                return combine(*[resolve(v) for v in src.cols.values()]) \
                    if src.cols else unknown("ROWWISE_OVER_NO_COLUMNS")
            return unknown(f"FRAME_REDUCTION:{m}")
        if m in ELEMENTWISE_METHODS or m in (
                "shift", "diff", "pct_change", "ffill", "bfill", "fillna",
                "cumsum", "pad", "backfill"):
            if m == "rename":
                cols = kw.get("columns")
                if not (isinstance(cols, Val) and cols.kind == "dict"):
                    return self.new_frame(st, ctx, havoc=(
                        "RENAME_WITHOUT_LITERAL_MAPPING",), exact=False)
                mapping = {k.payload: v.payload for k, v in cols.payload
                           if is_const(k) and is_const(v)}
                new = self.new_frame(st, ctx)
                nf = st.heap[new.payload]
                for c, v in src.cols.items():
                    nf.cols[mapping.get(c, c)] = v
                nf.havoc = set(src.havoc)
                if src.base is not None:
                    nf.exact, nf.havoc = False, nf.havoc | {
                        "RENAMED_CALLER_FRAME"}
                return new
            new = self.new_frame(st, ctx)
            nf = src.clone()
            st.heap[new.payload] = nf
            for c, vals in src.cols.items():
                nf.cols[c] = (self.flow_method(resolve(vals), m, args, kw,
                                               st, ctx),)
            if src.base is not None:
                nf.pending = src.pending + ((m, args, kw),)
            return new
        if m == "drop":
            cols = kw.get("columns")
            if is_const(cols):
                names = cols.payload if isinstance(cols.payload, tuple) \
                    else (cols.payload,)
                new = self.new_frame(st, ctx)
                nf = src.clone()
                for c in names:
                    nf.cols.pop(c, None)
                st.heap[new.payload] = nf
                return new
            return self.new_frame(st, ctx, havoc=("DROP_ROWS_OR_UNKNOWN",),
                                  exact=False)
        if m in ROW_TRANSFORMS:
            return self.new_frame(st, ctx, havoc=(f"ROW_TRANSFORM:{m}",),
                                  exact=False)
        if m in POSITIONAL_METHODS:
            return unknown(f"POSITIONAL_SELECTION:{m}")
        if m in ("to_numpy",):
            return unknown("FRAME_ARRAY")
        return unknown(f"UNFOLLOWED_FRAME_METHOD:{m}")

    # ------------------------------------------------------ user code
    def call_user(self, fn, args, kw, st, ctx, bound=None):
        kind, module, node, cls, closure = fn.payload
        if id(node) in ctx["stack"]:
            return unknown("CYCLE")
        if len(ctx["stack"]) > MAX_DEPTH:
            return unknown(f"DEPTH>{MAX_DEPTH}")
        env = dict(closure) if closure else {}
        a = node.args
        params = [p.arg for p in (a.posonlyargs + a.args)]
        values = list(args)
        if bound is not None:
            values = [bound] + values
        defaults = a.defaults
        first_default = len(params) - len(defaults)
        for i, p in enumerate(params):
            if i < len(values):
                env[p] = vals_of(values[i])
            elif p in kw:
                env[p] = vals_of(kw[p])
            elif i >= first_default:
                try:
                    env[p] = (const(ast.literal_eval(
                        defaults[i - first_default])),)
                except (ValueError, SyntaxError, TypeError):
                    env[p] = (unknown("NON_LITERAL_DEFAULT"),)
            else:
                env[p] = (unknown("MISSING_ARGUMENT"),)
        for p, d in zip(a.kwonlyargs, a.kw_defaults):
            if p.arg in kw:
                env[p.arg] = vals_of(kw[p.arg])
            elif d is not None:
                try:
                    env[p.arg] = (const(ast.literal_eval(d)),)
                except (ValueError, SyntaxError, TypeError):
                    env[p.arg] = (unknown("NON_LITERAL_DEFAULT"),)
        if len(values) > len(params) and a.vararg is None:
            return unknown("TOO_MANY_ARGUMENTS")
        for extra in (a.vararg, a.kwarg):
            if extra is not None:
                env[extra.arg] = (unknown("DYNAMIC_ARGUMENTS"),)
        sub = State(env, st.heap)
        ctx2 = dict(ctx, stack=ctx["stack"] + (id(node),), module=module,
                    cls=cls)
        name = getattr(node, "name", "<lambda>")
        if kind == "lambda":
            val = self.eval(node.body, sub, ctx2)
            st.heap = sub.heap
        else:
            r = self.exec_block(node.body, sub, ctx2)
            vals = [v for v, _ in r.rets]
            states = [s for _, s in r.rets]
            if r.fall is not None:
                vals.append(const(None))
                states.append(r.fall)
            joined = join_states(states)
            if joined is not None:
                st.heap = joined.heap
            flat = [x for v in vals for x in vals_of(v)]
            val = resolve(flat) if flat else unknown(
                f"HELPER_NEVER_RETURNS:{name}")
        val = norm(val)
        if isinstance(val, Flow):
            val = Flow(val.leaves, val.lo, val.hi, val.forward,
                       val.unresolved, val.params,
                       val.helpers | {(module.repo, module.file, name)},
                       val.notes)
        return val


def _snapshot(fr: Frame) -> dict:
    hav = tuple(unknown(h) for h in sorted(fr.havoc))
    return {c: tuple(v) + hav for c, v in fr.cols.items()}


class Analyzer(_Calls, _Eval, Interp):
    pass

# ------------------------------------------------------------ indexing
class SymbolResult:
    __slots__ = ("repo", "file", "commit", "code_sha256", "symbol",
                 "line", "retired", "outputs", "error", "writes")

    def record(self):
        return {"repository": self.repo, "commit": self.commit,
                "file": self.file, "symbol": self.symbol,
                "line": self.line, "code_sha256": self.code_sha256}

    def sort_key(self):
        return (self.repo, self.file, self.line, self.symbol)


def syntactic_writes(node) -> set[str]:
    """Column names written by a literal key in this scope only."""
    out = set()
    for n in _walk_scope_strict(node):
        if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Store):
            sl = n.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                out.add(sl.value)
            elif isinstance(sl, ast.JoinedStr):
                out.add("<fstring>")
    return out


def _walk_scope_strict(node):
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.Lambda, ast.ClassDef)):
                stack.append(c)


def _root_binding(node, cls, st, ctx, an):
    a = node.args
    params = a.posonlyargs + a.args
    for i, p in enumerate(params):
        ann = ast.unparse(p.annotation) if p.annotation is not None else ""
        if i == 0 and cls is not None and p.arg in ("self", "cls"):
            st.env[p.arg] = (Val("self", cls),)
        elif "DataFrame" in ann or (p.arg in FRAME_PARAMS
                                    and "Series" not in ann):
            fid = next(ctx["fids"])
            st.heap[fid] = Frame(base=p.arg)
            ctx["param_frames"].append(fid)
            st.env[p.arg] = (Val("frame", fid),)
        elif "Series" in ann:
            st.env[p.arg] = (Flow(leaves=(f"<param:{p.arg}>",)),)
        else:
            st.env[p.arg] = (Val("param", p.arg),)
    for p in a.kwonlyargs:
        st.env[p.arg] = (Val("param", p.arg),)
    for extra in (a.vararg, a.kwarg):
        if extra is not None:
            st.env[extra.arg] = (unknown("DYNAMIC_ARGUMENTS"),)


def analyze_symbol(index, mod: ModuleInfo, node, cls, qual) -> SymbolResult:
    res = SymbolResult()
    res.repo, res.file, res.commit = mod.repo, mod.file, mod.commit
    res.code_sha256, res.symbol, res.line = mod.digest, qual, node.lineno
    res.retired, res.error, res.outputs = mod.retired, None, {}
    res.writes = syntactic_writes(node)
    an = Analyzer(index)
    ctx = {"module": mod, "cls": cls, "stack": (id(node),),
           "fids": itertools.count(), "escapes": [], "taint": set(),
           "param_frames": []}
    st = State()
    _root_binding(node, cls, st, ctx, an)
    try:
        r = an.exec_block(node.body, st, ctx)
    except (Budget, RecursionError):
        res.error = "ANALYSIS_BUDGET_EXCEEDED"
        return res
    exits = [(v, s) for v, s in r.rets]
    if r.fall is not None:
        exits.append((const(None), r.fall))
    collected: dict[str, list] = {}

    def take(snap):
        for c, vals in snap.items():
            collected.setdefault(c, []).extend(vals)

    for v, s in exits:
        for x in vals_of(v):
            x = norm(x)
            frames = []
            if isinstance(x, Val) and x.kind == "frame":
                frames = [x.payload]
            elif isinstance(x, Val) and x.kind == "frameset":
                frames = list(x.payload)
            elif isinstance(x, Val) and x.kind == "seq":
                frames = [i.payload for i in x.payload
                          if isinstance(i, Val) and i.kind == "frame"]
            for fid in frames:
                if fid in s.heap:
                    take(_snapshot(s.heap[fid]))
        for fid in ctx["param_frames"]:
            if fid in s.heap:
                take(_snapshot(s.heap[fid]))
    for snap in ctx["escapes"]:
        take(snap)
    taint = tuple(unknown(t) for t in sorted(ctx["taint"]))
    for c, vals in collected.items():
        res.outputs[c] = _uniq(tuple(vals) + taint)
    return res


class Index:
    def __init__(self):
        self.modules: list[ModuleInfo] = []
        self.by_name: dict[str, int] = {}
        self.by_output: dict[str, list[SymbolResult]] = {}
        self.writers: dict[str, list[str]] = {}
        self.files_scanned = 0
        self.symbols_indexed = 0
        self.symbols_analyzed = 0

    def add_module(self, mod: ModuleInfo):
        self.modules.append(mod)
        self.files_scanned += 1
        for node, _, _ in mod.symbols():
            self.by_name[node.name] = self.by_name.get(node.name, 0) + 1
            self.symbols_indexed += 1

    def analyze(self, wanted: set[str] | None = None, shuffle_seed=None):
        mods = list(self.modules)
        if shuffle_seed is not None:
            random.Random(shuffle_seed).shuffle(mods)
        for mod in mods:
            for node, cls, qual in mod.symbols():
                writes = syntactic_writes(node)
                if not writes and not _returns_frame_literal(node):
                    continue
                if wanted is not None and "<fstring>" not in writes and \
                        not (writes & wanted) and \
                        not _returns_frame_literal(node):
                    continue
                res = analyze_symbol(self, mod, node, cls, qual)
                self.symbols_analyzed += 1
                for c in writes - {"<fstring>"}:
                    self.writers.setdefault(c, []).append(
                        f"{mod.repo}:{mod.file}:{qual}")
                for c in res.outputs:
                    self.by_output.setdefault(c, []).append(res)
                if res.error:
                    for c in writes - {"<fstring>"}:
                        self.by_output.setdefault(c, []).append(res)
        return self


def _returns_frame_literal(node) -> bool:
    for n in _walk_scope_strict(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "DataFrame" and n.args and \
                isinstance(n.args[0], ast.Dict):
            return True
    return False


def index_source(source: str, *, file="producer.py", repo="fixture",
                 index: Index | None = None) -> Index:
    idx = index or Index()
    idx.add_module(ModuleInfo(repo, file, source))
    return idx.analyze() if index is None else idx


def producer_files(repo: Path) -> list[Path]:
    out = []
    for py in sorted(repo.rglob("*.py")):
        if any(part in SKIP_PARTS for part in py.relative_to(repo).parts) \
                or py.name.startswith("test_") \
                or py.name.endswith("_test.py") or py.name == "conftest.py":
            continue
        out.append(py)
    return out


def index_producers(repos: dict[str, Path], wanted=None,
                    shuffle_seed=None) -> Index:
    idx = Index()
    entries = []
    for name, repo in repos.items():
        if not repo.is_dir():
            continue
        commit = git(repo, "rev-parse", "HEAD")
        for py in producer_files(repo):
            entries.append((name, repo, commit, py))
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(entries)
    for name, repo, commit, py in entries:
        try:
            src = py.read_text(encoding="utf-8", errors="replace")
            mod = ModuleInfo(name, str(py.relative_to(repo)), src, commit,
                             sha_file(py))
        except (SyntaxError, ValueError, OSError, RecursionError):
            continue
        idx.add_module(mod)
    return idx.analyze(wanted, shuffle_seed)


# ------------------------------------------------------ classification
def verdict_of(res: SymbolResult, column: str) -> dict:
    if res.error:
        return {"class": UNRESOLVED, "codes": [res.error], "flow": None}
    f = resolve(res.outputs.get(column, ()))
    if not isinstance(f, Flow):
        return {"class": UNRESOLVED, "codes": ["NON_SERIES_OUTPUT"],
                "flow": None}
    if f.unresolved:
        return {"class": UNRESOLVED, "codes": sorted(f.unresolved),
                "flow": f}
    if f.is_forward():
        return {"class": NON_CAUSAL, "codes": sorted(f.forward) or
                ["NEGATIVE_OFFSET"], "flow": f}
    real = [x for x in f.leaves if not x.startswith("<")]
    if not real:
        return {"class": UNRESOLVED, "codes": ["NO_LEAF"], "flow": f}
    return {"class": STATIC_CAUSAL, "codes": [], "flow": f}


def _lookback(f: Flow | None):
    if f is None or f.hi is None:
        return "UNBOUNDED" if f is not None else None
    return f.hi + 1


def classify(column: str, index: Index, order=None,
             selected: tuple | None = None) -> dict:
    """The static verdict for a column name, independent of order.

    `selected` names the one symbol (repo, file, symbol) that provenance
    evidence points at; without it every static candidate must agree."""
    base = {"leaves": [], "lookback": None, "forward": [], "unresolved": [],
            "helpers": [], "candidates": [], "selection": None}
    if column.upper() in RAW_LEAVES and selected is None:
        return dict(base, klass=STATIC_CAUSAL, why="a raw bar field",
                    leaves=[column], lookback=1, selection="RAW_FIELD")
    cands = list(index.by_output.get(column, []))
    if order is not None:
        cands = sorted(cands, key=lambda s: order.index(s.symbol))
    if GUARDS["producer_conflict"]:
        cands = sorted(cands, key=SymbolResult.sort_key)
    if selected is not None:
        cands = [c for c in cands
                 if (c.repo, c.file, c.symbol) == tuple(selected)]
        if not cands:
            return dict(base, klass=UNRESOLVED,
                        why="the evidence-selected symbol does not output "
                            "this column under static analysis",
                        unresolved=["SELECTED_SYMBOL_HAS_NO_SUCH_OUTPUT"],
                        selection="EVIDENCE_SELECTED")
    if not cands:
        codes = ["NO_STATIC_CANDIDATE"]
        if index.writers.get(column):
            codes = ["WRITE_DOES_NOT_REACH_AN_ESCAPE"]
        return dict(base, klass=UNRESOLVED, unresolved=codes,
                    why="no analysed symbol outputs this column")
    live = [c for c in cands if not c.retired]
    pool = live or cands
    verdicts = [(c, verdict_of(c, column)) for c in pool]
    if not GUARDS["producer_conflict"]:
        verdicts = verdicts[:1]  # MUTANT: v2 took the first producer
    records = []
    for c, v in verdicts:
        records.append(dict(c.record(), static_class=v["class"],
                            lookback_bars=_lookback(v["flow"]),
                            codes=v["codes"]))
    sigs = {(v["class"], _lookback(v["flow"]) if v["class"] == STATIC_CAUSAL
             else None) for _, v in verdicts}
    flows = [v["flow"] for _, v in verdicts if v["flow"] is not None]
    merged = combine(*flows) if flows else None
    out = dict(base, candidates=records,
               selection=("EVIDENCE_SELECTED" if selected else
                          "ALL_STATIC_CANDIDATES_MUST_AGREE"),
               leaves=sorted(x for x in (merged.leaves if merged else ())
                             if not x.startswith("<")),
               helpers=sorted({"/".join(h) for h in
                               (merged.helpers if merged else ())}),
               forward=sorted(merged.forward) if merged else [])
    if len(sigs) > 1:
        return dict(out, klass=UNRESOLVED,
                    unresolved=["CONFLICTING_PRODUCER_CANDIDATES"],
                    why=f"{len(verdicts)} candidate producers disagree in "
                        "class or lookback and nothing proves which one "
                        "made the data")
    klass = next(iter(sigs))[0]
    v0 = verdicts[0][1]
    codes = sorted({c for _, v in verdicts for c in v["codes"]})
    if klass == UNRESOLVED:
        return dict(out, klass=UNRESOLVED, unresolved=codes,
                    lookback=_lookback(v0["flow"]),
                    why="a dependency could not be proven: "
                        + "; ".join(codes[:3]))
    if klass == NON_CAUSAL:
        return dict(out, klass=NON_CAUSAL, lookback=_lookback(merged),
                    why="a reaching path reads forward in time: "
                        + "; ".join(codes[:3]))
    retired = not live
    return dict(out, klass=RETIRED if retired else STATIC_CAUSAL,
                lookback=_lookback(merged),
                why=("every reaching path ends at an input column and none "
                     "reads forward"
                     + ("; only retired code produces it" if retired
                        else "")))


def finalize(static: dict, bound: bool, probe: dict | None = None) -> dict:
    """Dataset-level class after the binding and dynamic guards."""
    k = static["klass"]
    if not bound and GUARDS["binding_requirement"]:
        if k == STATIC_CAUSAL:
            if static.get("selection") == "RAW_FIELD":
                return {"class": UNBOUND,
                        "codes": ["RAW_FIELD_WITHOUT_PROVIDER_BINDING"]}
            return {"class": CANDIDATE, "codes": ["PRODUCER_NOT_BOUND"]}
        if k == RETIRED:
            return {"class": RETIRED, "codes": ["PRODUCER_NOT_BOUND"]}
        return {"class": UNBOUND,
                "codes": ["PRODUCER_NOT_BOUND", f"STATIC_{k}",
                          *static.get("unresolved", [])]}
    if k == STATIC_CAUSAL:
        if probe is not None and probe.get("verdict") == "FAIL":
            return {"class": NON_CAUSAL,
                    "codes": ["PREFIX_INVARIANCE_FAILED"]}
        return {"class": CAUSAL, "codes": []}
    return {"class": k, "codes": list(static.get("unresolved", []))
            or list(static.get("forward", []))}

# ----------------------------------------------------- C78 provenance
_HOME = re.compile(r"(/home|/Users|/root)/[^\s'\"]*")


def scrub(text: str) -> str:
    return _HOME.sub("<path>", str(text))


def logical_path(abs_path: str, roots: dict[str, Path]):
    for name, root in sorted(roots.items()):
        prefix = str(root.resolve()) + "/"
        if str(abs_path).startswith(prefix):
            return name, str(abs_path)[len(prefix):]
    return None


def _iso_epoch(s):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")
                                      ).timestamp()
    except ValueError:
        return None


def _load_table(path: Path):
    import pandas as pd
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _records_naming(obj, target: str, top=None, out=None):
    """Every dict inside a JSON document holding `target` as a value."""
    out = [] if out is None else out
    top = obj if top is None else top
    if isinstance(obj, dict):
        if any(v == target for v in obj.values()):
            out.append(obj)
        for v in obj.values():
            _records_naming(v, target, top, out)
    elif isinstance(obj, list):
        for v in obj:
            _records_naming(v, target, top, out)
    return out


def _has_code_identity(d: dict) -> bool:
    return any(re.search(r"commit|code_sha|git_|revision", str(k), re.I)
               for k in d)


def find_receipts(repo_name, repo: Path, rel: str) -> list[dict]:
    found = []
    meta = repo / "_metadata"
    if not meta.is_dir():
        return found
    for js in sorted(meta.rglob("*.json")):
        try:
            if js.stat().st_size > 8_000_000:
                continue
            text = js.read_text(encoding="utf-8", errors="replace")
            if rel not in text:
                continue
            doc = json.loads(text)
        except (OSError, ValueError):
            continue
        recs = _records_naming(doc, rel)
        if not recs:
            continue
        top = doc if isinstance(doc, dict) else {}
        found.append({
            "type": "RUN_RECEIPT_NAMES_ARTIFACT",
            "repository": repo_name,
            "path": str(js.relative_to(repo)),
            "sha256": sha_file(js),
            "tracked_in_git": bool(git(repo, "ls-files", str(
                js.relative_to(repo)))),
            "generated_at": top.get("generated_at"),
            "stage": top.get("stage"),
            "records_code_identity": any(_has_code_identity(r)
                                         for r in recs + [top]),
            "record_keys": sorted({k for r in recs for k in r}),
        })
    return found


def find_writers(index: Index, repo_name: str, rel: str) -> list[dict]:
    """Functions that statically write `rel`, and what they write."""
    base = Path(rel).name
    dirs = set(Path(rel).parent.parts)
    out = []
    for mod in sorted(index.modules, key=lambda m: m.file):
        if mod.repo != repo_name:
            continue
        consts = {n.value for n in ast.walk(mod.tree)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if base not in consts or not (dirs & consts):
            continue
        for node, cls, qual in mod.symbols():
            assigns = {}
            for n in _walk_scope_strict(node):
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and \
                        isinstance(n.targets[0], ast.Name):
                    assigns.setdefault(n.targets[0].id, []).append(n.value)
            for n in _walk_scope_strict(node):
                if not (isinstance(n, ast.Call) and
                        isinstance(n.func, ast.Attribute) and
                        n.func.attr in SINK_METHODS and n.args and
                        isinstance(n.func.value, ast.Name) and
                        isinstance(n.args[0], ast.Name)):
                    continue
                pvals = assigns.get(n.args[0].id, [])
                vvals = assigns.get(n.func.value.id, [])
                if len(pvals) != 1 or len(vvals) != 1:
                    continue
                if base not in {c.value for c in ast.walk(pvals[0])
                                if isinstance(c, ast.Constant)}:
                    continue
                v = vvals[0]
                if not (isinstance(v, ast.Call) and
                        isinstance(v.func, ast.Name)):
                    continue
                defs = mod.defs.get(v.func.id, [])
                out.append({
                    "type": "STATIC_WRITER_OF_ARTIFACT",
                    "repository": mod.repo, "file": mod.file,
                    "sha256": mod.digest, "writer_symbol": qual,
                    "writer_line": n.lineno,
                    "producer_symbol": v.func.id if len(defs) == 1
                    else None,
                    "producer_definitions_in_module": len(defs),
                })
    return out


def first_commit(repo: Path, rel: str):
    log = git(repo, "log", "--follow", "--format=%H %ct", "--", rel)
    lines = [ln.split() for ln in log.splitlines() if ln.strip()]
    if not lines:
        return None
    h, t = lines[-1]
    return {"commit": h, "commit_epoch": int(t),
            "commits_touching_file": len(lines)}


def _match_columns(ds_cols, artifacts):
    """dataset column -> (artifact index, artifact column, rule)."""
    stems = {i: Path(a["path"]).stem for i, a in enumerate(artifacts)}
    out = {}
    for c in ds_cols:
        hits = []
        for i, a in enumerate(artifacts):
            cols = a["columns"]
            if c in cols:
                hits.append((i, c, "EXACT_NAME"))
            elif c.startswith(stems[i] + "__") and \
                    c[len(stems[i]) + 2:] in cols:
                hits.append((i, c[len(stems[i]) + 2:],
                             "FAMILY_PREFIX_ON_COLLISION"))
            elif c.lower() in cols and c != c.lower():
                hits.append((i, c.lower(), "CASE_FOLDED"))
        out[c] = hits
    return out


def _disambiguate(c, eq, ds_cols):
    """Several artifacts hold values equal to column `c`. A later
    family's colliding name is renamed with its stem, so an unprefixed
    twin belongs to the family whose prefixed copy is NOT in the data."""
    keep = [m for m in eq if not (
        m["name_rule"] == "EXACT_NAME"
        and f"{Path(m['path']).stem}__{c}" in ds_cols)]
    return keep


def derive_bindings(predictor_root: Path, repos: dict[str, Path],
                    inventory: dict, index: Index) -> tuple[dict, dict]:
    import numpy as np
    roots = dict(repos, predictor=predictor_root)
    manifest = {"schema": "financial_data.producer_binding_manifest.v1",
                "datasets": [], "bindings": []}
    per_column = {}
    for ds in sorted(inventory["datasets"], key=lambda d: d["dataset_id"]):
        path = predictor_root / ds["relative_path"]
        entry = {"dataset_id": ds["dataset_id"],
                 "relative_path": ds["relative_path"],
                 "inventory_physical_sha256": ds.get("physical_sha256"),
                 "evidence": [], "gaps": [], "columns": {}}
        manifest["datasets"].append(entry)
        if not path.is_file():
            entry["gaps"].append("DATASET_FILE_ABSENT")
            continue
        physical = sha_file(path)
        entry["recomputed_physical_sha256"] = physical
        if physical != ds.get("physical_sha256"):
            entry["gaps"].append("PHYSICAL_DIGEST_MISMATCH")
        folder = path.parent
        metas = []
        for js in sorted(folder.glob("*.json")):
            try:
                doc = json.loads(js.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(doc, dict):
                continue
            item = {"repository": "predictor",
                    "path": str(js.relative_to(predictor_root)),
                    "sha256": sha_file(js)}
            if doc.get("sha256") == physical:
                entry["evidence"].append(dict(
                    item, type="DATASET_MANIFEST_DIGEST_MATCH"))
            named = [k for k, v in doc.items() if isinstance(v, str)
                     and v.endswith("/" + ds["relative_path"])]
            if named and isinstance(doc.get("sources"), dict):
                entry["evidence"].append(dict(
                    item, type="EXPORT_METADATA_NAMES_DATASET",
                    naming_keys=named,
                    records_source_digests=any(
                        "sha" in k.lower() for k in doc)))
                metas.append(doc)
        if not metas:
            entry["gaps"].append("NO_EXPORT_METADATA_NAMES_THIS_DATASET")
            continue
        header = [c for c in _load_table(path).columns]
        ts_col = (ds.get("time_profile") or {}).get("timestamp_column")
        data = _load_table(path)
        if ts_col not in data.columns:
            entry["gaps"].append("DATASET_TIMESTAMP_COLUMN_ABSENT")
            continue
        import pandas as pd
        data[ts_col] = pd.to_datetime(data[ts_col], utc=True)
        artifacts = []
        for doc in metas:
            for key, src in sorted(doc["sources"].items()):
                lp = logical_path(src, roots)
                if lp is None:
                    entry["gaps"].append(f"SOURCE_OUTSIDE_KNOWN_ROOTS:{key}")
                    continue
                rname, rel = lp
                apath = roots[rname] / rel
                if not apath.is_file() or apath.suffix not in (".parquet",
                                                               ".csv"):
                    entry["gaps"].append(f"SOURCE_ABSENT_OR_NOT_TABULAR:"
                                         f"{key}")
                    continue
                try:
                    table = _load_table(apath)
                except Exception as exc:
                    entry["gaps"].append(f"SOURCE_UNREADABLE:{key}")
                    continue
                tcol = next((c for c in ("timestamp", "DATE_TIME")
                             if c in table.columns), None)
                if tcol is None:
                    entry["gaps"].append(f"SOURCE_WITHOUT_TIMESTAMP:{key}")
                    continue
                table[tcol] = pd.to_datetime(table[tcol], utc=True)
                artifacts.append({
                    "source_key": key, "repository": rname, "path": rel,
                    "sha256": sha_file(apath),
                    "tracked_in_git": bool(git(roots[rname], "ls-files",
                                               rel)),
                    "columns": [c for c in table.columns if c != tcol],
                    "_table": table.set_index(tcol)})
        for a in artifacts:
            a["receipts"] = find_receipts(a["repository"],
                                          roots[a["repository"]], a["path"])
            a["writers"] = find_writers(index, a["repository"], a["path"])
        cols = [c for c in header if c != ts_col]
        matches = _match_columns(cols, artifacts)
        keys = data[ts_col]
        for c in cols:
            rec = {"artifact_matches": [], "status": "NOT_BOUND",
                   "codes": [], "evidence_selected_symbol": None}
            for i, acol, rule in matches[c]:
                a = artifacts[i]
                s = a["_table"][acol].reindex(keys).to_numpy()
                x = data[c].to_numpy()
                try:
                    equal = bool(np.array_equal(
                        x.astype("float32"), s.astype("float32"),
                        equal_nan=True))
                except (TypeError, ValueError):
                    equal = False
                rec["artifact_matches"].append({
                    "repository": a["repository"], "path": a["path"],
                    "artifact_sha256": a["sha256"], "artifact_column": acol,
                    "name_rule": rule,
                    "values_equal_float32_at_matching_timestamps": equal})
            eq = [m for m in rec["artifact_matches"]
                  if m["values_equal_float32_at_matching_timestamps"]]
            if len({(m["repository"], m["path"]) for m in eq}) > 1:
                eq = _disambiguate(c, eq, cols)
                if eq:
                    rec["disambiguation"] = "FAMILY_PREFIX_COLLISION_RULE"
            if not matches[c]:
                rec["codes"].append("NO_ARTIFACT_CONTAINS_COLUMN")
            elif not eq:
                rec["codes"].append("NO_ARTIFACT_VALUE_EQUALITY")
            elif len({(m["repository"], m["path"]) for m in eq}) > 1:
                rec["codes"].append("SEVERAL_ARTIFACTS_EQUAL")
            else:
                rec["artifact_column"] = eq[0]["artifact_column"]
                a = next(x for x in artifacts
                         if (x["repository"], x["path"]) ==
                         (eq[0]["repository"], eq[0]["path"]))
                rec.update(_bind_through_artifact(a, eq[0], c, index,
                                                  roots, entry))
            entry["columns"][c] = rec
            per_column[(ds["dataset_id"], c)] = rec
        entry["artifacts"] = [{k: v for k, v in a.items() if k != "_table"}
                              for a in artifacts]
        for a in entry["artifacts"]:
            a["columns"] = len(a["columns"])
    for (dsid, col), rec in sorted(per_column.items()):
        if rec["status"] == "BOUND":
            manifest["bindings"].append(dict(rec["binding"],
                                             dataset_id=dsid, output=col))
    manifest["bindings_established"] = len(manifest["bindings"])
    return manifest, per_column


def _bind_through_artifact(a, match, column, index, roots, entry):
    codes = []
    if a["repository"] == "raw" or not a["writers"]:
        codes.append("NO_STATIC_WRITER_OF_ARTIFACT")
    writers = [w for w in a["writers"] if w["producer_symbol"]]
    if len({(w["file"], w["producer_symbol"]) for w in writers}) > 1:
        codes.append("SEVERAL_STATIC_WRITERS")
    if not a["receipts"]:
        codes.append("NO_RUN_RECEIPT_NAMES_ARTIFACT")
    selected = None
    if len({(w["file"], w["producer_symbol"]) for w in writers}) == 1:
        w = writers[0]
        cands = [r for r in index.by_output.get(match["artifact_column"], [])
                 if (r.repo, r.file, r.symbol) ==
                 (w["repository"], w["file"], w["producer_symbol"])]
        if cands:
            selected = (w["repository"], w["file"], w["producer_symbol"])
        else:
            codes.append("WRITER_PRODUCER_DOES_NOT_OUTPUT_COLUMN")
        fc = first_commit(roots[w["repository"]], w["file"])
        if a["receipts"] and not any(r["records_code_identity"]
                                     for r in a["receipts"]):
            codes.append("RECEIPT_RECORDS_NO_CODE_IDENTITY")
        runs = [_iso_epoch(r["generated_at"]) for r in a["receipts"]
                if r.get("generated_at")]
        if fc is None:
            codes.append("PRODUCER_FILE_NEVER_COMMITTED")
        elif runs and max(runs) < fc["commit_epoch"]:
            codes.append("RUN_PRECEDES_FIRST_COMMIT_OF_PRODUCER_FILE")
        fact = {"first_commit": fc["commit"] if fc else None,
                "commits_touching_file": fc["commits_touching_file"]
                if fc else 0}
    else:
        fact = {}
    if column != match["artifact_column"] and \
            match["name_rule"] != "EXACT_NAME":
        codes.append(f"COLUMN_RENAMED_BY_UNRECORDED_EXPORT:"
                     f"{match['name_rule']}")
    if "EXPORT_STEP_CODE_ABSENT" not in entry["gaps"]:
        entry["gaps"].append("EXPORT_STEP_CODE_ABSENT")
    blocking = [c for c in codes if not c.startswith("COLUMN_RENAMED")]
    rec = {"codes": sorted(set(codes)), "evidence_selected_symbol":
           list(selected) if selected else None, "code_identity": fact}
    if selected and not blocking:
        w = writers[0]
        rec["status"] = "BOUND"
        rec["binding"] = {"repository": w["repository"],
                          "commit": fact.get("first_commit"),
                          "file": w["file"], "symbol": selected[2],
                          "artifact": a["path"]}
    return rec


# ---------------------------------------------------- C56 availability
def availability(klass: str, lookback, facts: dict) -> dict:
    if klass != CAUSAL:
        return {"earliest_available_time": "UNAVAILABLE",
                "reason": f"class {klass}: only a bound, proven-causal "
                          "output can be given an availability time"}
    semantics = facts.get("timestamp_semantics", "UNDECLARED")
    if semantics == "UNDECLARED":
        return {"earliest_available_time": "UNAVAILABLE",
                "reason": "the dataset does not declare what its timestamp "
                          "MEANS. event_time is never copied and no bar "
                          "width is assumed"}
    return {"earliest_available_time": "UNAVAILABLE",
            "reason": "timestamp semantics are owned by the temporal "
                      "availability work; this DAG does not derive times"}


_SYMBOL_TF = re.compile(r"\.([a-z0-9]+)_(\d+[mhdw])_", re.I)


def dataset_facts(ds: dict, contracts: dict) -> dict:
    m = _SYMBOL_TF.search(ds["dataset_id"])
    declared = contracts.get(ds["dataset_id"], {})
    return {"symbol": m.group(1).upper() if m else "UNDERIVABLE",
            "timeframe": m.group(2) if m else "UNDERIVABLE",
            "provider": ds.get("provider", "UNDECLARED"),
            "timestamp_semantics": declared.get("timestamp_semantics",
                                                "UNDECLARED"),
            "contract_source": ("DECLARED_BY_DATASET_CONTRACT" if declared
                                else "NO_CONTRACT_DECLARED")}


# ------------------------------------------------------------- derive
def _flow_codes(static):
    return sorted(set(static.get("unresolved", [])))


def run_probes(selected: set, repos: dict[str, Path], bound: set) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import prefix_invariance_probe as pip
    out = {}
    for repo, file, symbol in sorted(selected):
        path = repos[repo] / file
        el = pip.eligibility(path)
        rec = {"repository": repo, "file": file, "symbol": symbol,
               "eligibility": el,
               "bound": (repo, file, symbol) in bound,
               "eligible_for_class": False}
        if el["eligible"]:
            try:
                fn = pip.load_symbol(path, symbol)
                res = pip.probe(fn)
            except Exception as exc:
                res = {"verdict": "NOT_EXECUTABLE_ERROR",
                       "error": scrub(f"{type(exc).__name__}: {exc}")[:300]}
            res.pop("columns", None) if res.get("verdict") == "PASS" \
                else None
            rec["probe"] = {k: (scrub(v) if isinstance(v, str) else v)
                            for k, v in res.items()}
            rec["eligible_for_class"] = rec["bound"] and \
                res.get("verdict") in ("PASS", "FAIL")
        out[(repo, file, symbol)] = rec
    return out


TIMESTAMP_NAMES = ("date_time", "datetime", "date", "timestamp")


def derive(predictor_root: Path, repos: dict[str, Path], derived_at: str,
           contracts=None, shuffle_seed=None, run_probe=True,
           inventory_path=None):
    contracts = contracts or {}
    inv_path = inventory_path or (
        predictor_root / "examples/research/crispdm_dataset_inventory.v1.json")
    inv = json.loads(Path(inv_path).read_text())
    headers = {}
    for ds in inv["datasets"]:
        p = predictor_root / ds["relative_path"]
        if p.is_file():
            with p.open(encoding="utf-8", errors="replace") as fh:
                headers[ds["dataset_id"]] = [
                    c.strip() for c in fh.readline().split(",") if c.strip()]
    wanted = {c for h in headers.values() for c in h}
    index = index_producers(repos, wanted=wanted, shuffle_seed=shuffle_seed)
    manifest, per_column = derive_bindings(predictor_root, repos, inv, index)
    selected = {tuple(r["evidence_selected_symbol"])
                for r in per_column.values() if r["evidence_selected_symbol"]}
    bound = {tuple(r["evidence_selected_symbol"])
             for r in per_column.values() if r["status"] == "BOUND"}
    probes = run_probes(selected, repos, bound) if run_probe else {}
    nodes, by_class, static_by_class = [], {}, {}
    for ds in sorted(inv["datasets"], key=lambda d: d["dataset_id"]):
        if ds["dataset_id"] not in headers:
            continue
        facts = dataset_facts(ds, contracts)
        for column in headers[ds["dataset_id"]]:
            if column.lower() in TIMESTAMP_NAMES:
                continue
            b = per_column.get((ds["dataset_id"], column), {
                "status": "NOT_BOUND", "codes": ["NO_PROVENANCE_EVIDENCE"],
                "evidence_selected_symbol": None})
            sel = b.get("evidence_selected_symbol")
            # the evidence-selected producer is asked about the column
            # name IT writes, which an export may have renamed
            static = classify(b.get("artifact_column", column) if sel
                              else column, index,
                              selected=tuple(sel) if sel else None)
            is_bound = b["status"] == "BOUND"
            pr = probes.get(tuple(sel)) if sel else None
            final = finalize(static, is_bound,
                             pr.get("probe") if pr and is_bound else None)
            by_class[final["class"]] = by_class.get(final["class"], 0) + 1
            static_by_class[static["klass"]] = static_by_class.get(
                static["klass"], 0) + 1
            nodes.append({
                "dataset_id": ds["dataset_id"], "column": column,
                "class": final["class"],
                "reason_codes": sorted(set(final["codes"]
                                           + b.get("codes", []))),
                "why": static["why"],
                "entity": facts,
                "static": {"class": static["klass"],
                           "selection": static["selection"],
                           "candidates": static["candidates"],
                           "unresolved_because": _flow_codes(static),
                           "forward_reads": static["forward"]},
                "binding": {"status": b["status"],
                            "codes": b.get("codes", []),
                            "evidence_selected_symbol": sel},
                "prefix_invariance": (
                    {"eligible_for_class": pr["eligible_for_class"],
                     "verdict": (pr.get("probe") or {}).get("verdict",
                                                           "NOT_RUN"),
                     "eligibility": pr["eligibility"]["reason"]}
                    if pr else {"eligible_for_class": False,
                                "verdict": "NOT_RUN",
                                "eligibility": "NO_EVIDENCE_SELECTED_"
                                               "PRODUCER"}),
                "leaves": static["leaves"],
                "helpers_followed": static["helpers"],
                "lookback_bars": static["lookback"],
                "availability": availability(final["class"],
                                             static["lookback"], facts),
            })
    manifest["probes"] = [dict(v) for _, v in sorted(probes.items())]
    manifest["rules"] = {
        "bound": "BOUND requires: the recomputed physical digest equals "
                 "the inventory; an export record names the dataset and "
                 "its source artifact; the artifact column equals the "
                 "dataset column value-for-value at matching timestamps; "
                 "a run receipt names the artifact; exactly one static "
                 "writer of the artifact calls a producer that outputs "
                 "the column; and a code identity (commit or code digest) "
                 "recorded AT RUN TIME",
        "not_by_name": "no producer is chosen by column name or by order",
        "zero_is_reportable": "no binding is manufactured",
    }
    manifest["derived_at"] = derived_at
    manifest["manifest_sha256"] = sha_obj(
        {k: v for k, v in manifest.items() if k != "derived_at"})
    doc = {
        "schema": "financial_data.feature_dag.v3",
        "derived_at": derived_at,
        "additive": "v1 and v2 are left byte-identical; v3 replaces "
                    "neither file",
        "producer_repositories": {
            k: {"commit": git(v, "rev-parse", "HEAD"),
                "present": v.is_dir()} for k, v in sorted(repos.items())},
        "producer_files_scanned": index.files_scanned,
        "symbols_indexed": index.symbols_indexed,
        "symbols_analyzed": index.symbols_analyzed,
        "columns_examined": len(nodes),
        "by_class": dict(sorted(by_class.items())),
        "static_by_class": dict(sorted(static_by_class.items())),
        "classes": [CAUSAL, CANDIDATE, NON_CAUSAL, RETIRED, EXTERNAL,
                    UNRESOLVED, UNBOUND],
        "bindings_established": manifest["bindings_established"],
        "binding_manifest_sha256": manifest["manifest_sha256"],
        "guards": dict(GUARDS),
        "nodes": nodes,
        "rules": {
            "lookback": "lookback_bars = bars of history a value depends "
                        "on, current bar included (max offset + 1); "
                        "UNBOUNDED for ewm, expanding, cumulative ops, "
                        "ffill and pandas' default-padding pct_change",
            "scope": "nested function, lambda and class bodies are never "
                     "executed as the outer body",
            "reaching": "statements run in order; branches join the "
                        "definitions that may reach a use; disagreement "
                        "in class or lookback is UNRESOLVED",
            "callables": "user callables passed to apply/map/transform/"
                         "pipe/agg/rolling().apply are followed; an "
                         "unfollowable one is UNRESOLVED",
            "positional": "every positional index is UNRESOLVED",
            "forward": "negative shift/diff, any np.roll, bfill, "
                       "interpolate, centred windows and full-sample "
                       "reductions make a path NON_CAUSAL",
            "unknown": "unknown calls, dynamic dispatch, cycles, depth and "
                       "budget exhaustion are UNRESOLVED",
            "binding": "CAUSAL_ACTIVE requires a BOUND producer (see "
                       "PRODUCER_BINDING_MANIFEST.v1.json); a static "
                       "causal candidate without one is "
                       "STATIC_CAUSAL_CANDIDATE_UNBOUND",
            "dynamic": "a bound, executable producer must also pass the "
                       "prefix-invariance probe; the probe never replaces "
                       "the static proof",
            "availability": "anything but CAUSAL_ACTIVE is UNAVAILABLE; "
                            "no timestamp semantics are invented here",
        },
        "grants_nothing": "a lineage describes how a value comes to "
                          "exist. It confers no eligibility",
    }
    doc["dag_sha256"] = sha_obj(doc)
    return doc, manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictor-root", required=True, type=Path)
    ap.add_argument("--producer-root", action="append", default=[])
    ap.add_argument("--contracts", type=Path, default=None)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--binding-output", type=Path, default=None)
    ap.add_argument("--derived-at", required=True)
    ap.add_argument("--skip-probe", action="store_true")
    a = ap.parse_args(argv)
    repos = {}
    for spec in a.producer_root:
        name, _, path = spec.partition("=")
        repos[name] = Path(path).expanduser()
    contracts = (json.loads(a.contracts.read_text())
                 if a.contracts and a.contracts.is_file() else {})
    doc, manifest = derive(a.predictor_root, repos, a.derived_at, contracts,
                           run_probe=not a.skip_probe)
    bout = a.binding_output or (a.output.parent /
                                "PRODUCER_BINDING_MANIFEST.v1.json")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    bout.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    a.output.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in (
        "columns_examined", "by_class", "static_by_class",
        "bindings_established", "producer_files_scanned",
        "symbols_indexed", "symbols_analyzed", "dag_sha256")},
        indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
