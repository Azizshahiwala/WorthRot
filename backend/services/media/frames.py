from dataclasses import dataclass
import math
from pathlib import Path

from PIL import Image

from backend.services.config import Settings
from backend.services.media.errors import MediaError
from backend.services.media.ffmpeg_runner import run_ffmpeg


@dataclass(frozen=True)
class VideoFrame:
    path: Path
    timestamp: str


def _difference_hash(path: Path) -> int:
    try:
        with Image.open(path) as image:
            grayscale = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            pixels = grayscale.tobytes()
    except OSError as error:
        raise MediaError("The extracted video frames could not be read.") from error
    value = 0
    for row in range(8):
        for column in range(8):
            value = (value << 1) | int(
                pixels[row * 9 + column] > pixels[row * 9 + column + 1]
            )
    return value


def _hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _evenly_spaced(frames: list[VideoFrame], limit: int) -> list[VideoFrame]:
    if len(frames) <= limit:
        return frames
    if limit == 1:
        return [frames[len(frames) // 2]]
    indices = [
        round(index * (len(frames) - 1) / (limit - 1))
        for index in range(limit)
    ]
    return [frames[index] for index in indices]


def sample_frames(
    media_path: Path, workdir: Path, duration: float, settings: Settings, timeout: float
) -> list[VideoFrame]:
    frame_dir = workdir / "frames"
    frame_dir.mkdir()
    max_sample_count = max(
        1, math.ceil(duration / settings.frame_interval_seconds)
    )
    output_pattern = frame_dir / "frame_%04d.jpg"
    result = run_ffmpeg(
        [
            "-protocol_whitelist",
            "file",
            "-i",
            str(media_path),
            "-vf",
            (
                f"fps=1/{settings.frame_interval_seconds},"
                f"scale={settings.frame_max_side}:{settings.frame_max_side}:"
                "force_original_aspect_ratio=decrease:force_divisible_by=2"
            ),
            "-q:v",
            "5",
            "-frames:v",
            str(max_sample_count),
            str(output_pattern),
        ],
        timeout=timeout,
    )
    if result.returncode:
        raise MediaError("Video frames could not be extracted.")

    frames: list[VideoFrame] = []
    previous_hash: int | None = None
    for index, path in enumerate(sorted(frame_dir.glob("frame_*.jpg"))):
        current_hash = _difference_hash(path)
        if (
            previous_hash is not None
            and _hamming_distance(previous_hash, current_hash)
            <= settings.dedupe_hamming_threshold
        ):
            path.unlink()
            continue
        previous_hash = current_hash
        seconds = index * settings.frame_interval_seconds
        frames.append(
            VideoFrame(
                path=path,
                timestamp=f"{seconds // 60:02d}:{seconds % 60:02d}",
            )
        )

    selected = _evenly_spaced(frames, settings.max_frames)
    selected_paths = {frame.path for frame in selected}
    for frame in frames:
        if frame.path not in selected_paths:
            frame.path.unlink(missing_ok=True)
    return selected
