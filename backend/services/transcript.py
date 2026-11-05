import re
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from backend.models import TranscriptDocument, TranscriptSegment
from backend.services.errors import InvalidInputError, TranscriptUnavailableError

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
TIMESTAMPED_LINE = re.compile(
    r"^\s*\[?(?P<timestamp>(?:\d{1,2}:)?\d{1,2}:\d{2}(?:\.\d+)?)\]?\s*(?P<text>.*)$"
)


def extract_video_id(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as error:
        raise InvalidInputError("Enter a valid YouTube URL.") from error

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or parsed.username
        or parsed.password
        or port not in {None, 80, 443}
    ):
        raise InvalidInputError("Enter a valid YouTube URL.")

    if hostname == "youtu.be" or hostname.endswith(".youtu.be"):
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif hostname == "youtube.com" or hostname.endswith(".youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        else:
            path_parts = parsed.path.strip("/").split("/")
            video_id = path_parts[1] if len(path_parts) == 2 and path_parts[0] in {
                "embed",
                "shorts",
                "live",
            } else ""
    else:
        video_id = ""

    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise InvalidInputError("Enter a valid YouTube video URL.")
    return video_id


def _parse_timestamp(value: str) -> float:
    parts = value.split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2])
    hours = int(parts[-3]) if len(parts) == 3 else 0
    if seconds >= 60 or minutes >= 60:
        raise ValueError("Invalid transcript timestamp.")
    return hours * 3600 + minutes * 60 + seconds


def parse_pasted_transcript(text: str) -> TranscriptDocument:
    segments: list[TranscriptSegment] = []
    for line in text.splitlines():
        match = TIMESTAMPED_LINE.match(line)
        if not match:
            continuation = line.strip()
            if continuation and segments:
                previous = segments[-1]
                segments[-1] = TranscriptSegment(
                    start=previous.start,
                    duration=previous.duration,
                    text=f"{previous.text} {continuation}",
                )
            continue
        snippet = match.group("text").strip()
        if not snippet:
            continue
        try:
            start = _parse_timestamp(match.group("timestamp"))
        except ValueError:
            continue
        segments.append(TranscriptSegment(start=start, duration=0.0, text=snippet))
    return TranscriptDocument(segments=segments)


def fetch_transcript(video_id: str) -> TranscriptDocument:
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en"])
    except (NoTranscriptFound, TranscriptsDisabled) as error:
        raise TranscriptUnavailableError(
            "No English captions were found. Paste a timestamped transcript instead."
        ) from error
    except RequestBlocked as error:
        raise TranscriptUnavailableError(
            "YouTube blocked caption access. Paste a timestamped transcript instead."
        ) from error
    except CouldNotRetrieveTranscript as error:
        raise TranscriptUnavailableError(
            "We couldn't retrieve captions. Paste a timestamped transcript instead."
        ) from error

    segments = [
        TranscriptSegment(
            start=float(snippet.start),
            duration=float(snippet.duration),
            text=str(snippet.text),
        )
        for snippet in fetched
    ]
    return TranscriptDocument(segments=segments)
