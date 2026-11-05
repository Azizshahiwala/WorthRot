import os
from dataclasses import dataclass
from pathlib import Path

from backend.services.errors import ConfigurationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DATA_DIR = REPOSITORY_ROOT / "src" / "backend" / "data"
DEFAULT_MODEL_NAME = "qwen/qwen3.7-flash:free"


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
    max_compare_videos: int = 3
    compare_timeout_seconds: int = 45

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
            max_output_tokens=_read_int("MAX_OUTPUT_TOKENS", 300, 1, 300),
            max_context_tokens=_read_int("MAX_CONTEXT_TOKENS", 2500, 1),
            top_k_windows=_read_int("TOP_K_WINDOWS", 6, 1),
            short_transcript_tokens=_read_int("SHORT_TRANSCRIPT_TOKENS", 1500, 1),
            max_video_minutes=_read_int("MAX_VIDEO_MINUTES", 45, 1),
            max_compare_videos=_read_int("MAX_COMPARE_VIDEOS", 3, 2, 3),
            compare_timeout_seconds=_read_int("COMPARE_TIMEOUT_SECONDS", 45, 1),
        )
