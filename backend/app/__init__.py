from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

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

    return app
