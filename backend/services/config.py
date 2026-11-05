import os
from dataclasses import dataclass
from pathlib import Path

from backend.services.errors import ConfigurationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DATA_DIR = REPOSITORY_ROOT / "src" / "backend" / "data"
DEFAULT_MODEL_NAME = "qwen/qwen3.7-flash:free"
DEFAULT_LLM_BASE_URL = "https://api.bazaarlink.ai/v1"


def _read_int(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a whole number.") from error
    if value < minimum or (maximum is not None and value > maximum):
        bound = f"between {minimum} and {maximum}" if maximum else f"at least {minimum}"
        raise ConfigurationError(f"{name} must be {bound}.")
    return value


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    model_name: str
    max_output_tokens: int
    max_context_tokens: int
    top_k_windows: int
    short_transcript_tokens: int
    max_video_minutes: int
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    max_compare_videos: int = 3
    compare_timeout_seconds: int = 45
    max_upload_mb: int = 100
    max_media_seconds: int = 300
    media_timeout_seconds: int = 90
    ffmpeg_timeout_seconds: int = 60
    frame_interval_seconds: int = 5
    frame_max_side: int = 768
    max_frames: int = 16
    dedupe_hamming_threshold: int = 6
    ffmpeg_path: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir_value = os.environ.get("DATA_DIR", "").strip()
        data_dir = Path(data_dir_value) if data_dir_value else LOCAL_DATA_DIR
        if not data_dir.is_absolute():
            data_dir = REPOSITORY_ROOT / data_dir

        return cls(
            data_dir=data_dir.resolve(),
            model_name=(
                os.environ.get("MODEL_NAME", DEFAULT_MODEL_NAME).strip()
                or DEFAULT_MODEL_NAME
            ),
            llm_base_url=(
                os.environ.get("LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
                .strip()
                .rstrip("/")
                or DEFAULT_LLM_BASE_URL
            ),
            max_output_tokens=_read_int("MAX_OUTPUT_TOKENS", 300, 1, 300),
            max_context_tokens=_read_int("MAX_CONTEXT_TOKENS", 2500, 1),
            top_k_windows=_read_int("TOP_K_WINDOWS", 6, 1),
            short_transcript_tokens=_read_int("SHORT_TRANSCRIPT_TOKENS", 1500, 1),
            max_video_minutes=_read_int("MAX_VIDEO_MINUTES", 45, 1),
            max_compare_videos=_read_int("MAX_COMPARE_VIDEOS", 3, 2, 3),
            compare_timeout_seconds=_read_int("COMPARE_TIMEOUT_SECONDS", 45, 1),
            max_upload_mb=_read_int("MAX_UPLOAD_MB", 100, 1, 2048),
            max_media_seconds=_read_int("MAX_MEDIA_SECONDS", 300, 1, 3599),
            media_timeout_seconds=_read_int("MEDIA_TIMEOUT_SECONDS", 90, 1),
            ffmpeg_timeout_seconds=_read_int("FFMPEG_TIMEOUT_SECONDS", 60, 1),
            frame_interval_seconds=_read_int("FRAME_INTERVAL_SECONDS", 5, 1),
            frame_max_side=_read_int("FRAME_MAX_SIDE", 768, 64, 2048),
            max_frames=_read_int("MAX_FRAMES", 16, 1, 60),
            dedupe_hamming_threshold=_read_int(
                "DEDUPE_HAMMING_THRESHOLD", 6, 0, 64
            ),
            ffmpeg_path=os.environ.get("FFMPEG_PATH", "").strip(),
        )
