import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError

from flask import Blueprint, Response, jsonify, request

from backend.models import VideoResult
from backend.services.config import Settings
from backend.services.errors import ConfigurationError, InvalidInputError
from backend.services.pipeline import analyze_video
from backend.services.ranker import best_video_id, rank_results
from backend.services.transcript import extract_video_id

logger = logging.getLogger(__name__)
compare_bp = Blueprint("compare", __name__)


def _failure(video_id: str, message: str) -> VideoResult:
    return {
        "verdict": "Can't verify",
        "facts": [],
        "missing": [],
        "meta": {
            "video_id": video_id,
            "cached": False,
            "tokens_in": 0,
            "tokens_out": 0,
        },
        "coverage": "none",
        "verified_fact_count": 0,
        "error": message,
    }


def _run_video(question: str, url: str) -> VideoResult:
    return analyze_video(question, url)


def _public_video_result(result: VideoResult) -> dict:
    error = result.get("error")
    return {
        "verdict": result["verdict"],
        "facts": result["facts"],
        "missing": result["missing"],
        "error": {"message": error} if error else None,
        "meta": {
            "cached": result["meta"]["cached"],
            "tokens_in": result["meta"]["tokens_in"],
            "tokens_out": result["meta"]["tokens_out"],
        },
    }


@compare_bp.post("/compare")
def compare() -> Response | tuple[Response, int]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return (
            jsonify(message="Send a JSON request with a question and video URLs."),
            400,
        )

    question = payload.get("question")
    urls = payload.get("urls")
    if not isinstance(question, str) or not question.strip():
        return jsonify(message="Add a question to continue."), 400
    if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
        return jsonify(message="Provide a list of YouTube URLs."), 400

    try:
        settings = Settings.from_env()
    except ConfigurationError as error:
        return jsonify(message=error.message), error.status_code

    if not 2 <= len(urls) <= settings.max_compare_videos:
        return (
            jsonify(
                message=(
                    f"Compare 2 to {settings.max_compare_videos} YouTube videos."
                )
            ),
            400,
        )

    normalized_urls = [url.strip() for url in urls]
    video_ids: list[str] = []
    try:
        video_ids = [extract_video_id(url) for url in normalized_urls]
    except InvalidInputError:
        return jsonify(message="Enter valid YouTube video URLs."), 400
    if len(set(video_ids)) != len(video_ids):
        return jsonify(message="Choose different videos to compare."), 400

    executor = ThreadPoolExecutor(max_workers=len(normalized_urls))
    futures: list[Future[VideoResult]] = []
    submitted_at: list[float] = []
    try:
        for url in normalized_urls:
            futures.append(executor.submit(_run_video, question.strip(), url))
            submitted_at.append(time.monotonic())

        results: list[VideoResult] = []
        for video_id, future, start_time in zip(video_ids, futures, submitted_at):
            timeout = max(
                0, settings.compare_timeout_seconds - (time.monotonic() - start_time)
            )
            try:
                results.append(future.result(timeout=timeout))
            except TimeoutError:
                future.cancel()
                results.append(
                    _failure(video_id, "This video took too long to check.")
                )
            except Exception:
                logger.exception("Unexpected error while analyzing video %s", video_id)
                results.append(
                    _failure(
                        video_id,
                        "This video could not be checked. Please try again.",
                    )
                )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    ranked_results = rank_results(results)
    video_by_result = {
        id(result): (video_id, url)
        for result, video_id, url in zip(results, video_ids, normalized_urls)
    }
    ranking = []
    for rank, result in enumerate(ranked_results, start=1):
        video_id, url = video_by_result[id(result)]
        ranking.append(
            {
                "rank": rank,
                "videoId": video_id,
                "url": url,
                **_public_video_result(result),
            }
        )

    return jsonify(
        {
            "question": question.strip(),
            "best": best_video_id(ranked_results),
            "ranking": ranking,
            "meta": {
                "tokens_in_total": sum(
                    result["meta"]["tokens_in"] for result in results
                ),
                "tokens_out_total": sum(
                    result["meta"]["tokens_out"] for result in results
                ),
            },
        }
    )
