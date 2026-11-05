from flask import Blueprint, Response, jsonify, request

from backend.services.analyzer import analyze_video
from backend.services.errors import AnalysisError

analyze_bp = Blueprint("analyze", __name__)


@analyze_bp.post("/analyze")
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
    try:
        result = analyze_video(question, url, transcript)
    except AnalysisError as error:
        response = {"message": error.message}
        if error.result is not None:
            response["result"] = error.result
        return jsonify(response), error.status_code
    return jsonify(result)
