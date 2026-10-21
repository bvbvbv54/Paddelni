"""Padeli Hyeti Flask application factory."""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException


def _api_error(status: int, code: str, message: str):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("PADELI_SECRET_KEY", "local-development-key-change-before-sharing"),
        DATABASE=os.environ.get("PADELI_DATABASE", str(Path(app.instance_path) / "padeli.sqlite3")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("PADELI_SECURE_COOKIES", "0") == "1",
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    from . import db

    db.init_app(app)

    with app.app_context():
        db.init_db()

    @app.before_request
    def load_user_and_check_csrf():
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            g.user = db.get_db().execute(
                "SELECT id, name, phone, skill_level, location, bio, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if g.user is None:
                session.clear()

        protected_public_endpoint = request.endpoint in {"api.register", "api.login"}
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and (g.user is not None or protected_public_endpoint):
            expected = session.get("csrf_token")
            supplied = request.headers.get("X-CSRF-Token") or request.form.get("_csrf_token")
            if not expected or not supplied or not hmac.compare_digest(expected, supplied):
                if request.path.startswith("/api/"):
                    return _api_error(400, "invalid_csrf", "Your form session expired. Refresh the page and try again.")
                return render_template(
                    "error.html",
                    status=400,
                    title="Invalid request",
                    message="Your form session expired. Refresh the page and try again.",
                ), 400
        return None

    def csrf_token() -> str:
        token = session.get("csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    app.jinja_env.globals["csrf_token"] = csrf_token

    from .api import bp as api_bp
    from .views import bp as views_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return _api_error(404, "not_found", "The requested API resource does not exist.")
        return render_template(
            "error.html", status=404, title="Page not found", message="We could not find that page."
        ), 404

    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith("/api/"):
            return _api_error(500, "server_error", "An unexpected server error occurred.")
        return render_template(
            "error.html",
            status=500,
            title="Something went wrong",
            message="The server could not complete the request. Please try again.",
        ), 500

    @app.errorhandler(Exception)
    def unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        app.logger.exception("Unhandled application error")
        return internal_error(error)

    return app
