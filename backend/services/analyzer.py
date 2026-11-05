from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from backend.cache import AnalysisCache, question_hash
from backend.models import AnalysisResponse, TranscriptDocument
from backend.services.chunker import make_windows
from backend.services.config import Settings
from backend.services.errors import (
    AnalysisError,
    InvalidInputError,
    TranscriptUnavailableError,
    VideoTooLongError,
)
from backend.services.retriever import estimate_tokens, format_context, retrieve_windows
from backend.services.transcript import (
    extract_video_id,
    fetch_transcript,
    parse_pasted_transcript,
)
from backend.services.verdict import extract_facts, map_verdict
from backend.services.verifier import verify_facts


def _response(
    verdict: str,
    video_id: str,
    facts: list[dict[str, str]] | None = None,
    missing: list[str] | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cached: bool = False,
) -> AnalysisResponse:
    return {
        "verdict": verdict,
        "facts": [
            {**fact, "url": ""}
            for fact in facts or []
        ],
        "missing": missing or [],
        "meta": {
            "video_id": video_id,
            "cached": cached,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        },
    }


def _attach_timestamp_urls(
    result: AnalysisResponse, video_url: str
) -> AnalysisResponse:
    for fact in result["facts"]:
        if not video_url:
            continue
        minutes, seconds = map(int, fact["timestamp"].split(":")[-2:])
        timestamp = minutes * 60 + seconds
        parsed = urlparse(video_url)
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key != "t"
        ]
        query.append(("t", str(timestamp)))
        fact["url"] = urlunparse(parsed._replace(query=urlencode(query)))
    return result


def _check_video_length(transcript: TranscriptDocument, settings: Settings) -> None:
    if transcript.duration_seconds > settings.max_video_minutes * 60:
        raise VideoTooLongError(settings.max_video_minutes)


def _cannot_verify(video_id: str, reason: str) -> AnalysisResponse:
    return _response("Can't verify", video_id, missing=[reason])


def _get_transcript(
    video_id: str,
    transcript_text: str,
    cache: AnalysisCache | None,
) -> TranscriptDocument:
    if transcript_text:
        transcript = parse_pasted_transcript(transcript_text)
        return transcript

    if cache:
        cached_transcript = cache.get_transcript(video_id)
        if cached_transcript is not None:
            return cached_transcript

    transcript = fetch_transcript(video_id)
    if cache:
        cache.set_transcript(video_id, transcript)
    return transcript


def analyze_video(question: str, url: str, transcript_text: str) -> AnalysisResponse:
    question = question.strip()
    if not question:
        raise InvalidInputError("Add a question to continue.")
    if not url and not transcript_text.strip():
        raise InvalidInputError("Add a YouTube URL or paste a timestamped transcript.")

    video_id = extract_video_id(url) if url else ""
    settings = Settings.from_env()
    cache = AnalysisCache(settings.data_dir) if video_id else None
    try:
        transcript = _get_transcript(video_id, transcript_text.strip(), cache)
    except TranscriptUnavailableError as error:
        error.result = _cannot_verify(video_id, "transcript unavailable")
        raise

    if not transcript.segments:
        if transcript_text.strip():
            return _cannot_verify(video_id, "paste a timestamped transcript")
        raise TranscriptUnavailableError(
            "No captions were found. Paste a timestamped transcript instead."
        )

    _check_video_length(transcript, settings)

    normalized_hash = question_hash(question)
    if cache and not transcript_text.strip():
        cached_result = cache.get_result(video_id, normalized_hash)
        if cached_result is not None:
            cached_result["meta"]["cached"] = True
            return _attach_timestamp_urls(cached_result, url)
    windows = make_windows(transcript)
    if not windows:
        if transcript_text.strip():
            return _cannot_verify(video_id, "paste a timestamped transcript")
        raise TranscriptUnavailableError(
            "No usable captions were found. Paste a timestamped transcript instead."
        )

    selected_windows, _ = retrieve_windows(
        question,
        windows,
        top_k=settings.top_k_windows,
        short_transcript_tokens=settings.short_transcript_tokens,
        max_context_tokens=settings.max_context_tokens,
    )
    if not selected_windows:
        result = _response(
            "Rot",
            video_id,
            missing=["no matching content found"],
        )
        if cache and not transcript_text.strip():
            cache.set_result(video_id, normalized_hash, result)
        return _attach_timestamp_urls(result, url)

    context = format_context(question, selected_windows)
    if estimate_tokens(context) > settings.max_context_tokens:
        raise AnalysisError("The analysis context exceeds its configured token limit.")

    try:
        extraction = extract_facts(settings, context)
    except AnalysisError as error:
        error.result = _attach_timestamp_urls(
            _cannot_verify(video_id, "analysis could not be verified"),
            url,
        )
        raise
    facts = verify_facts(extraction["facts"], selected_windows)
    verdict = map_verdict(extraction["coverage"], len(facts))
    missing = extraction["missing"]
    if not facts and not missing:
        missing = ["no verified facts found"]
    result = _response(
        verdict,
        video_id,
        facts=facts,
        missing=missing,
        tokens_in=extraction["tokens_in"],
        tokens_out=extraction["tokens_out"],
    )
    if cache and not transcript_text.strip():
        cache.set_result(video_id, normalized_hash, result)
    return _attach_timestamp_urls(result, url)
