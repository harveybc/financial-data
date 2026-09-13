"""Operator GUI + lake HTTP API consumed by data-gov http_lake."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from app.config_handler import save_config


def _fmt_bytes(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


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
            flash(json.dumps(payload, default=str)[:800], "info")
            return redirect(url_for("home"))

        @app.get("/api/v1/describe")
        def api_describe():
            return jsonify(inv().describe())

        @app.get("/api/v1/storage")
        def api_storage():
            return jsonify(inv().storage())

        @app.get("/api/v1/discover")
        def api_discover():
            return jsonify({"resources": inv().discover()})

        @app.get("/api/v1/coverage")
        def api_coverage():
            resource = request.args.get("resource")
            try:
                return jsonify(inv().coverage(resource))
            except FileNotFoundError:
                return jsonify({"error": "unknown resource"}), 404

        @app.get("/api/v1/read")
        def api_read():
            resource = request.args.get("resource")
            start = request.args.get("from")
            end = request.args.get("to")
            holdout = inv().params.get("holdout_start")
            if holdout and end and str(end)[:10] >= str(holdout)[:10]:
                return jsonify({"error": "holdout"}), 403
            if holdout and start and str(start)[:10] >= str(holdout)[:10]:
                return jsonify({"error": "holdout"}), 403
            try:
                return jsonify(inv().read(resource, start=start, end=end))
            except FileNotFoundError:
                return jsonify({"error": "unknown resource"}), 404

        return app

    def serve(self, context):
        app = self.create_app(context)
        host = self.params.get("web_host") or "127.0.0.1"
        port = int(self.params.get("web_port") or 5056)
        print(f"financial-data lake UI → http://{host}:{port}")
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
        return 0
