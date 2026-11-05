import re

from backend.models import TranscriptWindow
from backend.services.verdict import ModelFact

WHITESPACE = re.compile(r"\s+")
TIMESTAMP_PATTERN = re.compile(r"^(?:(\d+):)?([0-5]?\d):([0-5]\d)$")


def _normalize(value: str) -> str:
    return WHITESPACE.sub(" ", value.casefold()).strip()


def _timestamp_seconds(value: str) -> int | None:
    match = TIMESTAMP_PATTERN.fullmatch(value)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return (int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)


def verify_facts(
    facts: list[ModelFact], windows: list[TranscriptWindow]
) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    seen_quotes: set[tuple[int, str]] = set()
    windows_by_start = {int(window.start): window for window in windows}
    for fact in facts:
        seconds = _timestamp_seconds(fact["t"])
        if seconds is None:
            continue
        window = windows_by_start.get(seconds)
        if window is None:
            continue
        if _normalize(fact["q"]) not in _normalize(window.text):
            continue
        quote_key = (seconds, _normalize(fact["q"]))
        if quote_key in seen_quotes:
            continue
        seen_quotes.add(quote_key)
        verified.append({"text": fact["f"], "timestamp": window.timestamp})
    return verified
