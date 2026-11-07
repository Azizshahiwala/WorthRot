import json
import logging
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from backend.services.media.errors import (
    FfmpegUnavailableError,
    MediaError,
    MediaTimeoutError,
)

logger = logging.getLogger(__name__)
DURATION_PATTERN = re.compile(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)")
STREAM_PATTERN = re.compile(
    r"Stream #\d+:(\d+)(?:\(([^)]+)\))?.*?\b(Video|Audio|Subtitle):"
)


def resolve_ffmpeg(configured_path: str = "") -> str | None:
    candidates = [configured_path or os.environ.get("FFMPEG_PATH", "").strip()]
    for candidate in candidates:
        if candidate:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
            path = Path(candidate)
            if path.is_file():
                return str(path.resolve())

    system_binary = shutil.which("ffmpeg")
    if system_binary:
        return system_binary

    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError):
        return None
    return bundled if Path(bundled).is_file() else None


def log_ffmpeg_binary(configured_path: str = "") -> None:
    binary = resolve_ffmpeg(configured_path)
    if binary:
        logger.info("Using ffmpeg binary at %s", binary)
    else:
        logger.warning("No ffmpeg binary is available")


def _bounded_timeout(timeout: float) -> float:
    if timeout <= 0:
        raise MediaTimeoutError()
    return timeout


def run_ffmpeg(
    arguments: list[str], timeout: float, loglevel: str = "error"
) -> subprocess.CompletedProcess[bytes]:
    binary = resolve_ffmpeg()
    if not binary:
        raise FfmpegUnavailableError()
    command = [
        binary,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        loglevel,
        "-threads",
        "1",
        *arguments,
    ]
    try:
        result = subprocess.run(
            command,
            shell=False,
            timeout=_bounded_timeout(timeout),
            check=False,
            capture_output=True,
        )
    except subprocess.TimeoutExpired as error:
        raise MediaTimeoutError() from error
    except OSError as error:
        logger.warning("Unable to run ffmpeg: %s", error)
        raise FfmpegUnavailableError() from error
    if result.returncode:
        logger.info(
            "ffmpeg returned %s: %s",
            result.returncode,
            result.stderr.decode("utf-8", errors="replace")[:1000],
        )
    return result


def _ffprobe_path(ffmpeg_binary: str) -> str | None:
    found = shutil.which("ffprobe")
    if found:
        return found
    sibling = Path(ffmpeg_binary).with_name(
        "ffprobe.exe" if os.name == "nt" else "ffprobe"
    )
    return str(sibling) if sibling.is_file() else None


def _run_ffprobe(
    binary: str, path: Path, timeout: float
) -> dict[str, object] | None:
    command = [
        binary,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-threads",
        "1",
        "-protocol_whitelist",
        "file",
        "-show_entries",
        "format=duration:stream=codec_type,index:stream_tags=language",
        "-of",
        "json",
        "-i",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            shell=False,
            timeout=_bounded_timeout(timeout),
            check=False,
            capture_output=True,
        )
    except subprocess.TimeoutExpired as error:
        raise MediaTimeoutError() from error
    except OSError:
        return None
    if result.returncode:
        return None
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if not math.isfinite(remaining) or remaining <= 0:
        raise MediaTimeoutError()
    return remaining


def probe_media(path: Path, timeout: float) -> dict[str, object]:
    deadline = time.monotonic() + _bounded_timeout(timeout)
    ffmpeg_binary = resolve_ffmpeg()
    if not ffmpeg_binary:
        raise FfmpegUnavailableError()

    ffprobe_binary = _ffprobe_path(ffmpeg_binary)
    if ffprobe_binary:
        payload = _run_ffprobe(
            ffprobe_binary,
            path,
            _remaining_timeout(deadline),
        )
        if payload is not None:
            streams = payload.get("streams", [])
            format_data = payload.get("format", {})
            if not isinstance(format_data, dict):
                format_data = {}
            try:
                duration = float(format_data.get("duration"))
            except (TypeError, ValueError):
                duration = 0.0
            if not isinstance(streams, list):
                streams = []
            return {
                "duration": duration,
                "streams": [
                    stream
                    for stream in streams
                    if isinstance(stream, dict)
                    and isinstance(stream.get("codec_type"), str)
                ],
            }

    # ffmpeg's input summary is emitted at info level when ffprobe is absent.
    result = run_ffmpeg(
        ["-protocol_whitelist", "file", "-i", str(path)],
        timeout=_remaining_timeout(deadline),
        loglevel="info",
    )
    stderr = result.stderr.decode("utf-8", errors="replace")
    duration_match = DURATION_PATTERN.search(stderr)
    if not duration_match:
        raise MediaError(
            "The file could not be read. Check that it is a valid MP4 or MP3.",
            status_code=415,
            code="invalid_media",
        )
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    streams = []
    for line in stderr.splitlines():
        match = STREAM_PATTERN.search(line)
        if match:
            index, language, stream_type = match.groups()
            stream = {"index": int(index), "codec_type": stream_type.lower()}
            if language:
                stream["tags"] = {"language": language}
            streams.append(stream)
    return {"duration": duration, "streams": streams}
