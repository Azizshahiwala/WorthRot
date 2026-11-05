import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, send_from_directory

load_dotenv()

from backend.routes.analyze import analyze_bp
from backend.routes.compare import compare_bp
from backend.routes.health import health_bp
from backend.routes.media import media_bp
from backend.services.config import Settings
from backend.services.media.ffmpeg_runner import log_ffmpeg_binary
from backend.services.media.workdir import sweep_stale_workdirs

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


def create_app(frontend_dist: Path = FRONTEND_DIST) -> Flask:
    app = Flask(__name__)
    settings = Settings.from_env()
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_mb * 1024 * 1024 + 1024 * 1024
    log_ffmpeg_binary(settings.ffmpeg_path)
    sweep_stale_workdirs(settings)
    app.register_blueprint(health_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(compare_bp)
    app.register_blueprint(media_bp)

    @app.errorhandler(413)
    def request_too_large(_error) -> tuple[Response, int]:
        return jsonify(message="The uploaded file is too large."), 413

    @app.get("/")
    def index() -> Response | tuple[Response, int]:
        if not (frontend_dist / "index.html").is_file():
            return jsonify(
                message="Frontend build not found. Run `npm run build` in frontend."
            ), 503
        return send_from_directory(frontend_dist, "index.html")

    @app.get("/<path:asset_path>")
    def frontend_asset(asset_path: str) -> Response | tuple[Response, int]:
        if not frontend_dist.is_dir():
            return jsonify(message="Frontend build not found."), 404

        asset = frontend_dist / asset_path
        if asset.is_file():
            return send_from_directory(frontend_dist, asset_path)
        if (frontend_dist / "index.html").is_file():
            return send_from_directory(frontend_dist, "index.html")
        return jsonify(message="Not found."), 404

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
