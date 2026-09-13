"""Operator GUI + lake HTTP API consumed by data-gov http_lake."""

from __future__ import annotations

import io
import json
import os
import threading
from datetime import date
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for

from app.config_handler import save_config
from app.lake_auth import check_bearer, load_token
from inventory_plugins.fs_inventory import (
    DAY_RE,
    HoldoutError,
    LakeError,
    UnparseableError,
    UnsupportedError,
)

MAX_READ_ROWS = 8000
MAX_SPAN_DAYS = 366
RETRY_AFTER = "30"


def _fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def _day(value):
    """The calendar day of a YYYY-MM-DD string, else None."""
    if not isinstance(value, str) or not DAY_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _day_range(start, end):
    """(from, to) as dates when both are calendar days and from <= to, else None."""
    lo, hi = _day(start), _day(end)
    if lo is None or hi is None or lo > hi:
        return None
    return lo, hi


def _lake_error(exc):
    if isinstance(exc, HoldoutError):
        return jsonify({"error": str(exc)}), 403
    if isinstance(exc, (UnsupportedError, UnparseableError)):
        return jsonify({"error": str(exc)}), 422
    if isinstance(exc, FileNotFoundError):
        return jsonify({"error": "unknown resource"}), 404
    return jsonify({"error": "invalid from/to"}), 400


class _SlotFile(io.FileIO):
    """The open download handle; closing it returns the download slot."""

    def __init__(self, path, release):
        self._release = None
        super().__init__(path, "rb")
        self._release = release

    def close(self):
        release, self._release = self._release, None
        try:
            super().close()
        finally:
            if release is not None:
                release()


class Plugin:
    plugin_params = {"web_host": "127.0.0.1", "web_port": 5056, "secret_key": "x"}

    def __init__(self):
        self.params = dict(self.plugin_params)
        self._context = None

    def set_params(self, **kwargs):
        self.params.update(kwargs)

    def create_app(self, context):
        self._context = context
        here = Path(__file__).resolve().parent
        app = Flask(
            __name__,
            template_folder=str(here / "templates"),
            static_folder=str(here / "static"),
            static_url_path="/static",
        )
        app.secret_key = self.params.get("secret_key") or "x"
        inv = lambda: context["plugins"]["inventory"]
        cfg = lambda: context["config"]
        max_downloads = cfg().get("max_downloads")
        slots = threading.BoundedSemaphore(2 if max_downloads is None else int(max_downloads))
        inv().sweep()

        @app.context_processor
        def inject():
            return {"fmt_bytes": _fmt_bytes}

        @app.get("/healthz")
        def healthz():
            return "ok\n", 200, {"Content-Type": "text/plain"}

        @app.get("/")
        def home():
            inventory = inv()
            return render_template(
                "home.html",
                meta=inventory.describe(),
                storage=inventory.storage(),
                resources=inventory.discover(),
                globs="\n".join(cfg().get("include_globs") or []),
                holdout=cfg().get("holdout_start") or "",
            )

        @app.post("/config")
        def save():
            globs = [
                line.strip()
                for line in (request.form.get("globs") or "").splitlines()
                if line.strip()
            ]
            holdout = (request.form.get("holdout_start") or "").strip() or None
            cfg()["include_globs"] = globs
            cfg()["holdout_start"] = holdout
            inv().set_params(**cfg())
            inv().discover(refresh=True)
            dest = Path(__file__).resolve().parents[1] / "examples" / "config" / "local.json"
            save_config({k: cfg()[k] for k in cfg() if k != "plugins"}, dest)
            flash(f"Saved {dest.name} and refreshed inventory.", "success")
            return redirect(url_for("home"))

        @app.post("/ops/coverage")
        def ops_coverage():
            resource = request.form.get("resource") or ""
            try:
                payload = inv().coverage(resource)
            except FileNotFoundError:
                flash("Unknown resource.", "danger")
                return redirect(url_for("home"))
            except LakeError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("home"))
            flash(json.dumps(payload, default=str)[:800], "info")
            return redirect(url_for("home"))

        def _api_ok():
            expected = cfg().get("lake_service_token") or load_token()
            if check_bearer(request.headers.get("Authorization"), expected):
                return None
            return jsonify({"error": "unauthenticated"}), 401

        @app.get("/api/v1/describe")
        def api_describe():
            denied = _api_ok()
            if denied:
                return denied
            return jsonify(inv().describe())

        @app.get("/api/v1/storage")
        def api_storage():
            denied = _api_ok()
            if denied:
                return denied
            return jsonify(inv().storage())

        @app.get("/api/v1/discover")
        def api_discover():
            denied = _api_ok()
            if denied:
                return denied
            return jsonify({"resources": inv().discover()})

        @app.get("/api/v1/coverage")
        def api_coverage():
            denied = _api_ok()
            if denied:
                return denied
            resource = request.args.get("resource")
            try:
                return jsonify(inv().coverage(resource))
            except (FileNotFoundError, LakeError) as exc:
                return _lake_error(exc)

        @app.get("/api/v1/read")
        def api_read():
            denied = _api_ok()
            if denied:
                return denied
            resource = request.args.get("resource")
            start = request.args.get("from")
            end = request.args.get("to")
            if not start or not end:
                return jsonify({"error": "from and to are required"}), 400
            days = _day_range(start, end)
            if days is None:
                return jsonify({"error": "invalid from/to"}), 400
            if (days[1] - days[0]).days > MAX_SPAN_DAYS:
                return jsonify({"error": "date span exceeds limit"}), 400
            holdout = inv().params.get("holdout_start")
            if holdout and end >= str(holdout)[:10]:
                return jsonify({"error": "holdout"}), 403
            try:
                payload = inv().read(resource, start=start, end=end)
            except (FileNotFoundError, LakeError, ValueError) as exc:
                return _lake_error(exc)
            if len(payload.get("rows") or []) > MAX_READ_ROWS:
                return jsonify({"error": "result too large; narrow the range"}), 400
            return jsonify(payload)

        @app.get("/api/v1/download")
        def api_download():
            denied = _api_ok()
            if denied:
                return denied
            resource = request.args.get("resource") or ""
            start = request.args.get("from")
            end = request.args.get("to")
            ranged = start is not None or end is not None
            if ranged and _day_range(start, end) is None:
                return jsonify({"error": "invalid from/to"}), 400
            if not slots.acquire(blocking=False):
                return (
                    jsonify({"error": "download slots busy"}),
                    503,
                    {"Retry-After": RETRY_AFTER},
                )
            try:
                info = inv().download(resource, start=start, end=end)
                handle = _SlotFile(info["path"], slots.release)
            except (FileNotFoundError, LakeError, ValueError) as exc:
                slots.release()
                return _lake_error(exc)
            except BaseException:
                slots.release()
                raise
            # from here the slot is returned when the handle closes
            try:
                if inv().is_spool(info["path"]):
                    os.unlink(info["path"])
                response = send_file(
                    handle,
                    mimetype="application/octet-stream",
                    as_attachment=True,
                    download_name=info["filename"],
                    conditional=False,
                    etag=False,
                )
            except BaseException:
                handle.close()
                raise
            quoted = info["filename"].replace("\\", "\\\\").replace('"', '\\"')
            response.headers["Content-Disposition"] = f'attachment; filename="{quoted}"'
            response.headers["Content-Length"] = str(info["bytes"])
            response.headers["X-Content-SHA256"] = info["sha256"]
            response.headers["X-Source-SHA256"] = info["source_sha256"]
            response.headers["X-Delivery"] = info["delivery"]
            response.headers["X-Time-Column"] = info["time_column"] or ""
            return response

        return app

    def serve(self, context):
        app = self.create_app(context)
        host = self.params.get("web_host") or "127.0.0.1"
        port = int(self.params.get("web_port") or 5056)
        print(f"financial-data lake UI → http://{host}:{port}")
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
        return 0
