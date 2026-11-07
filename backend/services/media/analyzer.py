import time
from typing import BinaryIO
from pathlib import Path

from backend.models import GapCheck, MediaAnalysisResponse
from backend.services.config import Settings
from backend.services.language import detect_language, language_code
from backend.services.media.audio import extract_audio
from backend.services.media.errors import MediaError, MediaProviderError, MediaTimeoutError
from backend.services.media.frames import sample_frames
from backend.services.media.stt import has_gemini_api_key, transcribe_audio
from backend.services.media.subtitles import extract_subtitles
from backend.services.media.validate import (
    copy_upload,
    detect_media_type,
    subtitle_stream_index,
    subtitle_stream_language,
    validate_media_file,
    validate_question,
)
from backend.services.media.vision import analyze_frames
from backend.services.media.workdir import media_workdir
from backend.services.pipeline import analyze_video
from backend.services.verdict import map_gap


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise MediaTimeoutError()
    return remaining


def _ffmpeg_timeout(settings: Settings, deadline: float) -> float:
    return min(settings.ffmpeg_timeout_seconds, _remaining(deadline))


def _media_result(
    verdict: str,
    source: str,
    facts: list[dict],
    missing: list[str],
    tokens_in: int = 0,
    tokens_out: int = 0,
    frames_sent: int = 0,
    gap: GapCheck | None = None,
    question_language: str = "und",
    transcript_language: str = "und",
    transcript_source: str = "speech",
    transcript_original_language: str = "und",
) -> MediaAnalysisResponse:
    return {
        "verdict": verdict,
        "source": source,
        "facts": [
            {"text": fact["text"], "timestamp": fact.get("timestamp"), "url": None}
            for fact in facts
        ],
        "missing": missing,
        "gap": gap,
        "meta": {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "frames_sent": frames_sent,
            "questionLanguage": question_language,
            "transcriptLanguage": transcript_language,
            "transcriptOriginalLanguage": (
                transcript_original_language
                if transcript_original_language != "und"
                else transcript_language
            ),
            "transcriptSource": transcript_source,
        },
    }


def _transcript_result(
    question: str,
    transcript: str,
    source: str,
    timeout: float,
    transcript_language: str = "und",
) -> MediaAnalysisResponse:
    analyzed = analyze_video(question, "", transcript, timeout_seconds=timeout)
    question_language = analyzed["meta"]["questionLanguage"]
    if analyzed.get("error"):
        return _media_result(
            "Can't verify",
            source,
            [],
            [analyzed["error"]],
            analyzed["meta"]["tokens_in"],
            analyzed["meta"]["tokens_out"],
            gap=None,
            question_language=question_language,
            transcript_language=transcript_language,
            transcript_source=source,
        )
    return _media_result(
        analyzed["verdict"],
        source,
        analyzed["facts"],
        analyzed["missing"],
        analyzed["meta"]["tokens_in"],
        analyzed["meta"]["tokens_out"],
        gap=analyzed.get("gap"),
        question_language=question_language,
        transcript_language=(
            transcript_language
            if transcript_language != "und"
            else analyzed["meta"]["transcriptLanguage"]
        ),
        transcript_source=source,
    )


def analyze_media_upload(
    question: str, upload_stream: BinaryIO, settings: Settings
) -> MediaAnalysisResponse:
    validate_question(question)
    question_language = detect_language(question)
    deadline = time.monotonic() + settings.media_timeout_seconds
    with media_workdir(settings) as workdir:
        input_path = workdir / "input.mp4"
        max_bytes = settings.max_upload_mb * 1024 * 1024
        copy_upload(upload_stream, input_path, max_bytes)
        media_type = detect_media_type(input_path)
        if media_type == "mp3":
            mp3_path = workdir / "input.mp3"
            input_path.rename(mp3_path)
            input_path = mp3_path
        validated = validate_media_file(
            input_path,
            settings,
            _ffmpeg_timeout(settings, deadline),
        )
        streams = validated["streams"]
        subtitle_index = (
            subtitle_stream_index(streams, question_language)
            if media_type == "mp4"
            else None
        )

        if subtitle_index is not None:
            try:
                subtitle_text = extract_subtitles(
                    input_path,
                    subtitle_index,
                    _ffmpeg_timeout(settings, deadline),
                )
            except MediaError as error:
                if error.code in {"media_timeout", "ffmpeg_unavailable"}:
                    raise
                subtitle_text = None
            if subtitle_text:
                subtitle_language = subtitle_stream_language(
                    streams, subtitle_index
                )
                result = _transcript_result(
                    question,
                    subtitle_text,
                    "subtitles",
                    _remaining(deadline),
                    subtitle_language,
                )
                _remaining(deadline)
                return result

        transcript = None
        stream_types = {stream.get("codec_type") for stream in streams}
        if "audio" in stream_types and has_gemini_api_key():
            try:
                audio_path = extract_audio(
                    input_path,
                    workdir / "audio.mp3",
                    _ffmpeg_timeout(settings, deadline),
                )
                try:
                    transcript = transcribe_audio(
                        audio_path,
                        validated["duration"],
                        _remaining(deadline),
                    )
                finally:
                    audio_path.unlink(missing_ok=True)
            except MediaProviderError:
                transcript = None
            except MediaError as error:
                if error.code in {"media_timeout", "ffmpeg_unavailable"}:
                    raise
                transcript = None
            if transcript:
                if transcript.timed:
                    result = _transcript_result(
                        question,
                        transcript.text,
                        "speech",
                        _remaining(deadline),
                        transcript.language_code,
                    )
                    _remaining(deadline)
                    return result
                return _media_result(
                    "Can't verify",
                    "speech",
                    [],
                    [
                        "Speech transcript has no timestamps; evidence cannot be verified."
                    ],
                    question_language=question_language,
                    transcript_language=transcript.language_code,
                    transcript_source="speech",
                )

        if media_type == "mp3":
            return _media_result(
                "Can't verify",
                "speech",
                [],
                ["No transcript available for audio-only files."],
                question_language=question_language,
                transcript_source="speech",
            )

        try:
            frames = sample_frames(
                input_path,
                workdir,
                validated["duration"],
                settings,
                _ffmpeg_timeout(settings, deadline),
            )
        except MediaError as error:
            if error.code in {"media_timeout", "ffmpeg_unavailable"}:
                raise
            return _media_result(
                "Can't verify",
                "frames",
                [],
                [error.message],
                question_language=question_language,
                transcript_source="frames",
            )
        if not frames:
            return _media_result(
                "Rot",
                "frames",
                [],
                ["No usable video frames were found."],
                question_language=question_language,
                transcript_source="frames",
            )
        try:
            frame_result = analyze_frames(
                question,
                frames,
                settings,
                _remaining(deadline),
                question_language,
            )
        except MediaProviderError as error:
            return _media_result(
                "Can't verify",
                "frames",
                [],
                [error.message],
                frames_sent=len(frames),
                question_language=question_language,
                transcript_source="frames",
            )
        finally:
            for frame in frames:
                frame.path.unlink(missing_ok=True)
        _remaining(deadline)
        verdict = (
            "Skim"
            if frame_result["facts"] and frame_result["coverage"] in {"full", "partial"}
            else "Rot"
        )
        return _media_result(
            verdict,
            "frames",
            frame_result["facts"],
            frame_result["missing"],
            frame_result["tokens_in"],
            frame_result["tokens_out"],
            len(frames),
            map_gap(frame_result.get("parts", []), len(frame_result["facts"])),
            question_language=question_language,
            transcript_source="frames",
        )
