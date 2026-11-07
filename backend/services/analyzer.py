import logging
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from backend.cache import AnalysisCache, question_hash
from backend.models import GapCheck, VideoResult, TranscriptDocument
from backend.services.chunker import make_windows
from backend.services.config import Settings
from backend.services.errors import (
    AnalysisError,
    InvalidInputError,
    TranscriptUnavailableError,
    VideoTooLongError,
)
from backend.services.retriever import estimate_tokens, format_context, retrieve_windows
from backend.services.language import detect_language, language_name
from backend.services.transcript import (
    extract_video_id,
    fetch_transcript,
    parse_pasted_transcript,
)
from backend.services.verdict import (
    PROMPT_VERSION,
    _request_facts,
    extract_facts,
    map_gap,
    map_verdict,
)
from backend.services.verifier import verify_facts

LINK_LEAD_IN_SECONDS = 2
logger = logging.getLogger(__name__)


def _response(
    verdict: str,
    video_id: str,
    facts: list[dict[str, str]] | None = None,
    missing: list[str] | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cached: bool = False,
    coverage: str = "none",
    gap: GapCheck | None = None,
    question_language: str = "und",
    transcript_language: str = "und",
    transcript_original_language: str = "und",
    transcript_source: str = "manual",
    retrieval_translation_failed: bool = False,
) -> VideoResult:
    return {
        "verdict": verdict,
        "facts": [
            {**fact, "url": ""}
            for fact in facts or []
        ],
        "missing": missing or [],
        "gap": gap,
        "meta": {
            "video_id": video_id,
            "cached": cached,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "questionLanguage": question_language,
            "transcriptLanguage": transcript_language,
            "transcriptOriginalLanguage": transcript_original_language,
            "transcriptSource": transcript_source,
            "retrievalTranslationFailed": retrieval_translation_failed,
        },
        "coverage": coverage,
        "verified_fact_count": len(facts or []),
    }


def _attach_timestamp_urls(
    result: VideoResult, video_url: str
) -> VideoResult:
    for fact in result["facts"]:
        if not video_url:
            continue
        minutes, seconds = map(int, fact["timestamp"].split(":")[-2:])
        timestamp = max(
            0, minutes * 60 + seconds - LINK_LEAD_IN_SECONDS
        )
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


def _cannot_verify(video_id: str, reason: str) -> VideoResult:
    return _response("Can't verify", video_id, missing=[reason])


def _get_transcript(
    video_id: str,
    transcript_text: str,
    cache: AnalysisCache | None,
    question_language: str,
) -> TranscriptDocument:
    if transcript_text:
        transcript = parse_pasted_transcript(transcript_text)
        return transcript

    if cache:
        cached_transcript = cache.get_transcript(video_id, question_language)
        if cached_transcript is not None:
            return cached_transcript

    transcript = fetch_transcript(video_id, question_language)
    if cache:
        cache.set_transcript(video_id, transcript, question_language)
    return transcript


def analyze_video(
    question: str,
    url: str,
    transcript_text: str,
    timeout_seconds: float | None = None,
) -> VideoResult:
    question = question.strip()
    if not question:
        raise InvalidInputError("Add a question to continue.")
    if not url and not transcript_text.strip():
        raise InvalidInputError("Add a YouTube URL or paste a timestamped transcript.")

    video_id = extract_video_id(url) if url else ""
    question_language = detect_language(question)
    settings = Settings.from_env()
    cache = AnalysisCache(settings.data_dir) if video_id else None
    try:
        transcript = _get_transcript(
            video_id, transcript_text.strip(), cache, question_language
        )
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

    transcript_text_content = " ".join(
        segment.text for segment in transcript.segments
    )
    transcript_language = (
        transcript.language_code
        if transcript.language_code != "und"
        else detect_language(transcript_text_content)
    )
    transcript_original_language = (
        transcript.original_language_code
        if transcript.original_language_code != "und"
        else transcript_language
    )
    normalized_hash = question_hash(
        f"{question}\n{question_language}\n{transcript_language}\n"
        f"{transcript_original_language}\n{transcript.source}\n{PROMPT_VERSION}"
    )
    if cache and not transcript_text.strip():
        cached_result = cache.get_result(video_id, normalized_hash)
        if cached_result is not None:
            cached_result["meta"]["cached"] = True
            cached_result["meta"].setdefault("questionLanguage", question_language)
            cached_result["meta"].setdefault(
                "transcriptLanguage", transcript_language
            )
            cached_result["meta"].setdefault(
                "transcriptSource", transcript.source
            )
            cached_result["meta"].setdefault(
                "transcriptOriginalLanguage",
                transcript_original_language,
            )
            cached_result["meta"].setdefault(
                "retrievalTranslationFailed", False
            )
            return _attach_timestamp_urls(cached_result, url)
    windows = make_windows(transcript)
    if not windows:
        if transcript_text.strip():
            return _cannot_verify(video_id, "paste a timestamped transcript")
        raise TranscriptUnavailableError(
            "No usable captions were found. Paste a timestamped transcript instead."
        )

    retrieval_question = question
    deadline = (
        time.monotonic() + timeout_seconds
        if timeout_seconds is not None
        else None
    )
    selected_windows, short_transcript = retrieve_windows(
        question,
        windows,
        top_k=settings.top_k_windows,
        short_transcript_tokens=settings.short_transcript_tokens,
        max_context_tokens=settings.max_context_tokens,
        language=transcript_language,
    )
    translation_tokens_in = 0
    translation_tokens_out = 0
    retrieval_translation_failed = False
    if (
        not short_transcript
        and question_language != transcript_language
        and question_language != "und"
        and transcript_language != "und"
    ):
        try:
            remaining = (
                max(0.1, deadline - time.monotonic()) if deadline else None
            )
            translated, translation_tokens_in, translation_tokens_out = (
                _request_facts(
                    settings,
                    f"Target language: {language_name(transcript_language)} "
                    f"({transcript_language}).\nQuestion: {question}",
                    timeout_seconds=min(8, remaining) if remaining else 8,
                    prompt_filename="translate_prompt.txt",
                )
            )
            retrieval_question = translated.strip().strip('"')
            if not retrieval_question:
                raise AnalysisError("The retrieval question translation was empty.")
        except AnalysisError:
            retrieval_translation_failed = True
            logger.warning(
                "Question translation failed; using best-effort transcript retrieval."
            )
            retrieval_question = question

        selected_windows, _ = retrieve_windows(
            retrieval_question,
            windows,
            top_k=settings.top_k_windows,
            short_transcript_tokens=settings.short_transcript_tokens,
            max_context_tokens=settings.max_context_tokens,
            language=transcript_language,
            best_effort=retrieval_translation_failed,
        )
    if not selected_windows:
        result = _response(
            "Rot",
            video_id,
            missing=["no matching content found"],
            coverage="none",
            question_language=question_language,
            transcript_language=transcript_language,
            transcript_original_language=transcript_original_language,
            transcript_source=transcript.source,
        )
        if cache and not transcript_text.strip():
            cache.set_result(video_id, normalized_hash, result)
        return _attach_timestamp_urls(result, url)

    context = format_context(question, selected_windows)
    if estimate_tokens(context) > settings.max_context_tokens:
        raise AnalysisError("The analysis context exceeds its configured token limit.")

    try:
        remaining = max(0.1, deadline - time.monotonic()) if deadline else None
        analysis_context = (
            f"Answer language: {language_name(question_language)} "
            f"({question_language}).\n\n{context}"
        )
        if remaining is None:
            extraction = extract_facts(settings, analysis_context)
        else:
            extraction = extract_facts(
                settings,
                analysis_context,
                timeout_seconds=remaining,
            )
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
        coverage=extraction["coverage"],
        gap=map_gap(extraction.get("parts", []), len(facts)),
        question_language=question_language,
        transcript_language=transcript_language,
        transcript_original_language=transcript_original_language,
        transcript_source=transcript.source,
        retrieval_translation_failed=retrieval_translation_failed,
    )
    result["meta"]["tokens_in"] += translation_tokens_in
    result["meta"]["tokens_out"] += translation_tokens_out
    if cache and not transcript_text.strip():
        cache.set_result(video_id, normalized_hash, result)
    return _attach_timestamp_urls(result, url)
