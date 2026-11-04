from flask import Blueprint, Response, jsonify

analyze_bp = Blueprint("analyze", __name__)


@analyze_bp.post("/analyze")
def analyze() -> tuple[Response, int]:
    return jsonify(message="Video analysis has not been implemented yet."), 501
