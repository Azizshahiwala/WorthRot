from pathlib import Path

from backend.services.media.errors import MediaError
from backend.services.media.ffmpeg_runner import run_ffmpeg


def extract_audio(
    media_path: Path, output_path: Path, timeout: float
) -> Path:
    output = run_ffmpeg(
        [
            "-protocol_whitelist",
            "file",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "48k",
            "-f",
            "mp3",
            str(output_path),
        ],
        timeout=timeout,
    )
    if output.returncode or not output_path.is_file():
        raise MediaError(
            "The audio track could not be prepared for transcription.",
            code="audio_extraction_failed",
        )
    return output_path
