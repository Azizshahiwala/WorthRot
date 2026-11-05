import base64
import json
import math
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.services.media.errors import MediaProviderError

MAX_TRANSCRIPT_CHARACTERS = 100_000
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
ELEVENLABS_MODEL = "scribe_v2"
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/speech-to-text"


@dataclass(frozen=True)
class Transcription:
    text: str
    timed: bool


def has_gemini_api_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def _format_timestamped_segments(
    segments: list[tuple[float, str]], duration_seconds: float
) -> Transcription | None:
    lines: list[str] = []
    length = 0
    for start, segment_text in segments:
        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not math.isfinite(start)
            or start < 0
            or start >= duration_seconds
            or not segment_text.strip()
        ):
            continue
        seconds = int(start)
        line = f"[{seconds // 60:02d}:{seconds % 60:02d}] {segment_text.strip()}"
        if length + len(line) > MAX_TRANSCRIPT_CHARACTERS:
            remaining = MAX_TRANSCRIPT_CHARACTERS - length
            if remaining > 0:
                lines.append(line[:remaining])
            break
        lines.append(line)
        length += len(line) + 1
    if lines:
        return Transcription("\n".join(lines), timed=True)
    return None


def _transcribe_elevenlabs(
    audio_path: Path, duration_seconds: float, timeout: float, api_key: str
) -> Transcription | None:
    boundary = f"worthrot-{uuid.uuid4().hex}"
    audio = audio_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="model_id"\r\n\r\n'
        f"{ELEVENLABS_MODEL}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="timestamps_granularity"\r\n\r\n'
        "word\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="audio.mp3"\r\n'
        "Content-Type: audio/mpeg\r\n\r\n"
    ).encode("utf-8") + audio + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = Request(
        ELEVENLABS_API_URL,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "xi-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in {400, 404, 405, 410, 415, 422}:
            return None
        raise MediaProviderError(
            "ElevenLabs speech transcription is unavailable. Please try again."
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise MediaProviderError(
            "ElevenLabs speech transcription is unavailable. Please try again."
        ) from error

    if not isinstance(payload, dict):
        raise MediaProviderError("ElevenLabs returned invalid transcription data.")
    words = payload.get("words")
    if not isinstance(words, list):
        raise MediaProviderError("ElevenLabs returned invalid transcription data.")

    segments: list[tuple[float, str]] = []
    current_start: float | None = None
    current_end = 0.0
    current_words: list[str] = []
    for word in words:
        if not isinstance(word, dict) or word.get("type") == "audio_event":
            continue
        start, end, text = word.get("start"), word.get("end"), word.get("text")
        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not math.isfinite(start)
            or start < 0
            or start >= duration_seconds
            or not isinstance(end, (int, float))
            or isinstance(end, bool)
            or not math.isfinite(end)
            or end < start
            or not isinstance(text, str)
            or not text.strip()
            or word.get("type") == "spacing"
        ):
            continue

        if current_words and (
            start - current_end > 1.5
            or (
                current_start is not None
                and start - current_start >= 8
            )
            or current_words[-1].endswith((".", "!", "?"))
        ):
            segments.append((current_start or 0.0, " ".join(current_words)))
            current_words = []
            current_start = None
        if current_start is None:
            current_start = float(start)
        current_words.append(text.strip())
        current_end = float(end)
    if current_words and current_start is not None:
        segments.append((current_start, " ".join(current_words)))
    return _format_timestamped_segments(segments, duration_seconds)


def transcribe_audio(
    audio_path: Path, duration_seconds: float, timeout: float
) -> Transcription | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    audio = audio_path.read_bytes()
    request_payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Transcribe the spoken words verbatim. Return concise "
                            "consecutive speech segments with each segment's start "
                            "time in seconds from the beginning of the audio. Do not "
                            "summarize or invent speech. If there is no intelligible "
                            "speech, return an empty segments array."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": "audio/mp3",
                            "data": base64.b64encode(audio).decode("ascii"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "segments": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "start_seconds": {"type": "NUMBER"},
                                "text": {"type": "STRING"},
                            },
                            "required": ["start_seconds", "text"],
                        },
                    }
                },
                "required": ["segments"],
            },
        },
    }
    request = Request(
        GEMINI_API_URL,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 429:
            elevenlabs_key = os.environ.get("ELEVEN_LABS_API", "").strip()
            if elevenlabs_key:
                return _transcribe_elevenlabs(
                    audio_path, duration_seconds, timeout, elevenlabs_key
                )
            return None
        if error.code in {400, 404, 405, 410, 415, 422}:
            return None
        raise MediaProviderError(
            "Gemini speech transcription is unavailable. Please try again."
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise MediaProviderError(
            "Gemini speech transcription is unavailable. Please try again."
        ) from error

    if not isinstance(payload, dict):
        raise MediaProviderError("Gemini returned invalid transcription data.")
    try:
        candidates = payload["candidates"]
        parts = candidates[0]["content"]["parts"]
        transcript_payload = json.loads(parts[0]["text"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise MediaProviderError("Gemini returned invalid transcription data.") from error
    if not isinstance(transcript_payload, dict):
        raise MediaProviderError("Gemini returned invalid transcription data.")

    segments = transcript_payload.get("segments")
    timestamped_segments: list[tuple[float, str]] = []
    if isinstance(segments, list):
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            start = segment.get("start_seconds")
            segment_text = segment.get("text")
            if (
                not isinstance(start, (int, float))
                or isinstance(start, bool)
                or not math.isfinite(start)
                or not isinstance(segment_text, str)
                or not segment_text.strip()
            ):
                continue
            timestamped_segments.append((float(start), segment_text))
    return _format_timestamped_segments(timestamped_segments, duration_seconds)
