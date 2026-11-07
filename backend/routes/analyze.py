from flask import Blueprint, Response, jsonify, request

from backend.rate_limit import limited
from backend.services.pipeline import analyze_video

analyze_bp = Blueprint("analyze", __name__)


def _public_result(result: dict) -> dict:
    return {
        "verdict": result["verdict"],
        "facts": result["facts"],
        "missing": result["missing"],
        "gap": result.get("gap"),
        "meta": result["meta"],
    }


@analyze_bp.post("/analyze")
@limited("analyze")
def analyze() -> Response | tuple[Response, int]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return (
            jsonify(message="Send a JSON request with a question and video source."),
            400,
        )

    question = payload.get("question")
    urls = payload.get("urls", [])
    transcript = payload.get("transcript", "")
    if not isinstance(question, str):
        return jsonify(message="Add a question to continue."), 400
    if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
        return jsonify(message="Provide a valid YouTube URL list."), 400
    if len(urls) > 1:
        return jsonify(message="Analyze one YouTube video at a time."), 400
    if not isinstance(transcript, str):
        return jsonify(message="The pasted transcript must be text."), 400

    url = urls[0].strip() if urls else ""
    result = analyze_video(question, url, transcript)
    if result.get("error"):
        response = {"message": result["error"]}
        if result.get("failure_result") is not None:
            response["result"] = _public_result(result["failure_result"])
        return jsonify(response), result.get("error_status", 422)
    return jsonify(_public_result(result))
