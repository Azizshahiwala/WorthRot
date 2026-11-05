import re

from backend.models import TranscriptDocument, TranscriptSegment, TranscriptWindow

BRACKETED_TAG = re.compile(r"\[[^\]]+\]")
WHITESPACE = re.compile(r"\s+")
DEFAULT_WINDOW_SECONDS = 40


def _clean_text(value: str) -> str:
    return WHITESPACE.sub(" ", BRACKETED_TAG.sub(" ", value)).strip()


def clean_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    cleaned: list[TranscriptSegment] = []
    previous_text = ""
    for segment in segments:
        text = _clean_text(segment.text)
        normalized = text.casefold()
        if not text or normalized == previous_text:
            continue
        cleaned.append(
            TranscriptSegment(
                start=max(0.0, segment.start),
                duration=max(0.0, segment.duration),
                text=text,
            )
        )
        previous_text = normalized
    return cleaned


def make_windows(
    transcript: TranscriptDocument, window_seconds: int = DEFAULT_WINDOW_SECONDS
) -> list[TranscriptWindow]:
    if window_seconds < 30 or window_seconds > 45:
        raise ValueError("Analysis windows must be between 30 and 45 seconds.")

    segments = sorted(
        clean_segments(transcript.segments), key=lambda segment: segment.start
    )
    if not segments:
        return []

    windows: list[TranscriptWindow] = []
    current: list[TranscriptSegment] = []
    window_start = segments[0].start

    def flush() -> None:
        if not current:
            return
        windows.append(
            TranscriptWindow(
                start=window_start,
                end=max(segment.start + segment.duration for segment in current),
                text=" ".join(segment.text for segment in current),
            )
        )

    for segment in segments:
        if current and segment.start - window_start >= window_seconds:
            flush()
            current.clear()
            window_start = segment.start
        current.append(segment)
    flush()
    return windows


def clean_transcript(transcript: TranscriptDocument) -> TranscriptDocument:
    return TranscriptDocument(segments=clean_segments(transcript.segments))
