from pathlib import Path

from backend.services.media.errors import MediaError
from backend.services.media.ffmpeg_runner import run_ffmpeg


def _parse_srt(content: str) -> str | None:
    lines: list[str] = []
    for block in content.replace("\r\n", "\n").split("\n\n"):
        rows = [line.strip() for line in block.splitlines() if line.strip()]
        if len(rows) < 2:
            continue
        timing = rows[1] if rows[0].isdigit() else rows[0]
        start = timing.split("-->", 1)[0].strip()
        pieces = start.replace(",", ".").split(":")
        try:
            if len(pieces) != 3:
                continue
            seconds = int(float(pieces[2]))
            total = int(pieces[0]) * 3600 + int(pieces[1]) * 60 + seconds
        except ValueError:
            continue
        text_rows = rows[2:] if rows[0].isdigit() else rows[1:]
        text = " ".join(text_rows).strip()
        if text:
            lines.append(f"[{total // 60:02d}:{total % 60:02d}] {text}")
    return "\n".join(lines) or None


def extract_subtitles(
    media_path: Path, stream_index: int, timeout: float
) -> str | None:
    output = run_ffmpeg(
        [
            "-protocol_whitelist",
            "file",
            "-i",
            str(media_path),
            "-map",
            f"0:{stream_index}",
            "-f",
            "srt",
            "-",
        ],
        timeout=timeout,
    )
    if output.returncode:
        raise MediaError(
            "The embedded subtitles could not be read.",
            code="subtitle_extraction_failed",
        )
    return _parse_srt(output.stdout.decode("utf-8", errors="replace"))
