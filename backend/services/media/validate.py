import math
from pathlib import Path
from typing import BinaryIO

from backend.services.config import Settings
from backend.services.language import language_code
from backend.services.media.errors import MediaError, UnsupportedMediaError
from backend.services.media.ffmpeg_runner import probe_media

MP4_BRAND_OFFSET = 4
MP4_BRAND = b"ftyp"


def detect_media_type(path: Path) -> str:
    with path.open("rb") as media_file:
        header = media_file.read(12)
    if (
        len(header) >= MP4_BRAND_OFFSET + len(MP4_BRAND)
        and header[MP4_BRAND_OFFSET : MP4_BRAND_OFFSET + 4] == MP4_BRAND
    ):
        return "mp4"
    if header.startswith(b"ID3") or (
        len(header) >= 2
        and header[0] == 0xFF
        and header[1] & 0xE0 == 0xE0
    ):
        return "mp3"
    raise UnsupportedMediaError()


def validate_media_file(
    path: Path, settings: Settings, timeout: float
) -> dict[str, object]:
    size = path.stat().st_size
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size > max_bytes:
        raise MediaError(
            f"Files must be {settings.max_upload_mb} MB or smaller.",
            status_code=413,
            code="upload_too_large",
        )

    media_type = detect_media_type(path)
    probe = probe_media(path, timeout)
    streams = probe.get("streams", [])
    usable_types = {stream.get("codec_type") for stream in streams}
    if media_type == "mp4" and "video" not in usable_types:
        raise MediaError(
            "The MP4 file does not contain a video stream.",
            status_code=415,
            code="invalid_media",
        )
    if media_type == "mp3" and "audio" not in usable_types:
        raise MediaError(
            "The MP3 file does not contain an audio stream.",
            status_code=415,
            code="invalid_media",
        )

    duration = probe.get("duration", 0)
    if (
        not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration <= 0
    ):
        raise MediaError(
            "The file duration could not be determined.",
            status_code=415,
            code="invalid_media",
        )
    if duration > settings.max_media_seconds:
        limit = (
            f"{settings.max_media_seconds // 60} minutes"
            if settings.max_media_seconds % 60 == 0
            else f"{settings.max_media_seconds} seconds"
        )
        raise MediaError(
            f"Media files must be {limit} or shorter.",
            status_code=413,
            code="media_too_long",
        )
    return {
        "media_type": media_type,
        "duration": float(duration),
        "streams": streams,
    }


def copy_upload(stream: BinaryIO, path: Path, max_bytes: int) -> int:
    total = 0
    with path.open("wb") as target:
        while chunk := stream.read(64 * 1024):
            total += len(chunk)
            if total > max_bytes:
                raise MediaError(
                    "The uploaded file is too large.",
                    status_code=413,
                    code="upload_too_large",
                )
            target.write(chunk)
    return total


def _subtitle_language(stream: dict[str, object]) -> str:
    tags = stream.get("tags")
    if isinstance(tags, dict) and isinstance(tags.get("language"), str):
        return language_code(tags["language"])
    return "und"


def subtitle_stream_index(
    streams: list[dict[str, object]], question_language: str = "und"
) -> int | None:
    subtitles = [
        stream
        for stream in streams
        if stream.get("codec_type") == "subtitle"
        and isinstance(stream.get("index"), int)
    ]
    for stream in subtitles:
        if _subtitle_language(stream) == language_code(question_language):
            return stream["index"]
    return subtitles[0]["index"] if subtitles else None


def subtitle_stream_language(
    streams: list[dict[str, object]], stream_index: int
) -> str:
    for stream in streams:
        if stream.get("index") == stream_index:
            return _subtitle_language(stream)
    return "und"


def validate_question(question: str) -> None:
    if not question.strip():
        raise MediaError(
            "Add a question to continue.", status_code=400, code="invalid_question"
        )
