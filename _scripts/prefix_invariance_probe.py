#!/usr/bin/env python3
"""C79: a dynamic complement to the static FEATURE_DAG.v3 analysis.

A producer is called on a small synthetic OHLCV frame, then again on a
copy whose rows AFTER a cut are perturbed. If any output value at or
before the cut changes, the producer read the future. Passing proves
nothing about inputs the synthetic frame does not exercise; it
complements, never replaces, the static proof.

Execution is in-process on CPU, inside a guard that refuses file writes
outside a temporary directory, subprocesses and sockets. The guard
patches Python-level entry points only; a C extension could bypass it,
which is why only producers whose module imports nothing beyond the
standard library, numpy and pandas are eligible.
"""
from __future__ import annotations

import ast
import builtins
import contextlib
import importlib.util
import io
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ALLOWED_IMPORT_ROOTS = frozenset({
    "__future__", "argparse", "json", "os", "datetime", "pathlib", "typing",
    "math", "re", "hashlib", "collections", "itertools", "functools",
    "dataclasses", "numpy", "pandas", "time", "socket", "logging",
    "warnings", "subprocess", "sys",
})


class SandboxViolation(RuntimeError):
    pass


def module_imports(source: str) -> set[str]:
    roots = set()
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Import):
            roots |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            roots.add(n.module.split(".")[0])
        elif isinstance(n, ast.ImportFrom) and n.level:
            roots.add("<relative>")
    return roots


def eligibility(path: Path) -> dict:
    src = Path(path).read_text(encoding="utf-8", errors="replace")
    roots = module_imports(src)
    extra = sorted(roots - ALLOWED_IMPORT_ROOTS)
    if extra:
        return {"eligible": False,
                "reason": "MODULE_IMPORTS_OUTSIDE_STDLIB_NUMPY_PANDAS",
                "imports": extra}
    return {"eligible": True, "reason": "IMPORTS_STDLIB_NUMPY_PANDAS_ONLY",
            "imports": sorted(roots)}


@contextlib.contextmanager
def sandbox(tmpdir: Path):
    tmp = str(Path(tmpdir).resolve())
    real_open = builtins.open

    def inside(p) -> bool:
        try:
            return str(Path(os.fspath(p)).resolve()).startswith(tmp)
        except TypeError:
            return False

    def guarded_open(file, mode="r", *a, **k):
        if any(c in mode for c in "wax+") and not inside(file):
            raise SandboxViolation(f"write outside sandbox refused")
        return real_open(file, mode, *a, **k)

    def refuse(*a, **k):
        raise SandboxViolation("process/network access refused")

    patches = [(builtins, "open", guarded_open), (io, "open", guarded_open),
               (subprocess, "run", refuse), (subprocess, "Popen", refuse),
               (os, "system", refuse), (socket, "socket", refuse),
               (os, "replace", refuse), (os, "rename", refuse),
               (os, "remove", refuse), (os, "unlink", refuse)]
    try:
        import pandas as pd
        for meth in ("to_csv", "to_parquet", "to_pickle", "to_json"):
            patches.append((pd.DataFrame, meth, refuse))
    except ImportError:
        pass
    saved = [(o, n, getattr(o, n)) for o, n, _ in patches]
    cwd = os.getcwd()
    try:
        for o, n, v in patches:
            setattr(o, n, v)
        os.chdir(tmp)
        yield
    finally:
        os.chdir(cwd)
        for o, n, v in saved:
            setattr(o, n, v)


def load_symbol(path: Path, symbol: str):
    name = f"_probe_{abs(hash((str(path), symbol)))}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = mod
    for part in symbol.split("."):
        fn = getattr(fn, part)
    return fn


def synthetic_ohlcv(n: int = 1200, seed: int = 7, timestamp_col="timestamp"):
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    open_ = close * np.exp(rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * np.exp(np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(open_, close) * np.exp(-np.abs(rng.normal(0, 0.003, n)))
    vol = rng.lognormal(10, 0.5, n)
    return pd.DataFrame({
        timestamp_col: pd.date_range("2020-01-01", periods=n, freq="4h",
                                     tz="UTC"),
        "open": open_, "high": high, "low": low, "close": close,
        "volume": vol})


def perturb_after(df, cut: int, seed: int = 11):
    import numpy as np
    out = df.copy()
    rng = np.random.default_rng(seed)
    rows = slice(cut + 1, None)
    from pandas.api.types import is_numeric_dtype
    for c in out.columns:
        if is_numeric_dtype(out[c].dtype) and \
                not str(out[c].dtype).startswith(("datetime", "bool")):
            vals = out[c].to_numpy(dtype="float64").copy()
            k = len(vals) - (cut + 1)
            if k > 0:
                vals[cut + 1:] = vals[cut + 1:] * rng.uniform(0.5, 1.5, k) \
                    + rng.normal(0, 1, k)
            out[c] = vals
    return out


def probe(fn, frame=None, cut: int | None = None) -> dict:
    """Run `fn(frame)` twice; compare every output row <= cut."""
    import numpy as np
    import pandas as pd
    base = synthetic_ohlcv() if frame is None else frame
    cut = (len(base) * 3) // 4 if cut is None else cut
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with sandbox(Path(tmp)):
                a = fn(base.copy())
                b = fn(perturb_after(base, cut))
        except SandboxViolation as exc:
            return {"verdict": "NOT_EXECUTABLE_SIDE_EFFECT",
                    "error": str(exc)}
        except Exception as exc:
            return {"verdict": "NOT_EXECUTABLE_ERROR",
                    "error": f"{type(exc).__name__}: {exc}"[:300]}
    if isinstance(a, pd.Series):
        a, b = a.to_frame(), b.to_frame()
    if not isinstance(a, pd.DataFrame) or len(a) != len(base) or \
            len(b) != len(base) or list(a.columns) != list(b.columns):
        return {"verdict": "NOT_COMPARABLE",
                "error": "output is not a row-aligned frame"}
    columns, failed = {}, []
    from pandas.api.types import is_numeric_dtype
    for c in a.columns:
        if not is_numeric_dtype(a[c].dtype) or \
                str(a[c].dtype).startswith("datetime"):
            continue
        x = a[c].to_numpy(dtype="float64")[:cut + 1]
        y = b[c].to_numpy(dtype="float64")[:cut + 1]
        same = (x == y) | (np.isnan(x) & np.isnan(y))
        compared = int((~np.isnan(x)).sum())
        first_bad = None if same.all() else int(np.argmin(same))
        state = ("PASS" if same.all() and compared else
                 "VACUOUS_ALL_NAN" if same.all() else "FAIL")
        columns[str(c)] = {"state": state, "compared_values": compared,
                           "first_changed_row": first_bad}
        if state == "FAIL":
            failed.append(str(c))
    verdict = "FAIL" if failed else (
        "PASS" if any(v["state"] == "PASS" for v in columns.values())
        else "VACUOUS")
    return {"verdict": verdict, "cut_row": cut, "rows": len(base),
            "failed_columns": sorted(failed), "columns": columns}
