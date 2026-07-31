from pathlib import Path

from flask import Flask, abort, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, NotFound

from app.config import get_settings
from app.db import close_session
from app.routes import measurements


def create_app() -> Flask:
    app = Flask(__name__)

    origins = get_settings().cors_origin_list
    if origins:
        CORS(app, resources={r"/api/*": {"origins": origins}}, methods=["GET"])

    app.teardown_appcontext(close_session)

    app.register_blueprint(measurements.bp)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return jsonify(error=exc.name, message=exc.description), exc.code

    @app.get("/api/ping")
    def ping():
        return {"status": "ok"}

    # Serve the built frontend (production image copies frontend/dist here).
    # Absent in local dev and tests, where Vite serves the frontend instead.
    spa_dir = Path(app.root_path).parent / "static"
    if spa_dir.is_dir():

        @app.get("/", defaults={"path": "index.html"})
        @app.get("/<path:path>")
        def spa(path: str):
            if path.startswith("api/"):
                abort(404)
            try:
                return send_from_directory(spa_dir, path)
            except NotFound:
                # History-mode router: unknown paths fall back to the SPA shell.
                return send_from_directory(spa_dir, "index.html")

    return app
