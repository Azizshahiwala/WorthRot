from backend.models import AnalysisResponse, VideoResult
from backend.services.analyzer import analyze_video as run_analysis
from backend.services.errors import AnalysisError


def _failure_result(video_id: str, error: AnalysisError) -> VideoResult:
    failure_result: AnalysisResponse | None = error.result
    result = failure_result or {
        "verdict": "Can't verify",
        "facts": [],
        "missing": [],
        "meta": {
            "video_id": video_id,
            "cached": False,
            "tokens_in": 0,
            "tokens_out": 0,
        },
    }
    return {
        **result,
        "coverage": "none",
        "verified_fact_count": len(result["facts"]),
        "error": error.message,
        "error_status": error.status_code,
        "failure_result": failure_result,
    }


def analyze_video(
    question: str,
    url: str,
    transcript_text: str = "",
    timeout_seconds: float | None = None,
) -> VideoResult:
    try:
        if timeout_seconds is None:
            result = run_analysis(question, url, transcript_text)
        else:
            result = run_analysis(
                question,
                url,
                transcript_text,
                timeout_seconds=timeout_seconds,
            )
    except AnalysisError as error:
        video_id = (
            error.result.get("meta", {}).get("video_id", "")
            if error.result
            else ""
        )
        return _failure_result(video_id, error)

    coverage = result.get("coverage")
    if coverage not in {"full", "partial", "none"}:
        coverage = {
            "Worth it": "full",
            "Skim": "partial",
            "Rot": "none",
            "Can't verify": "none",
        }[result["verdict"]]
    return {
        **result,
        "coverage": coverage,
        "verified_fact_count": result.get(
            "verified_fact_count", len(result["facts"])
        ),
        "error": None,
    }
