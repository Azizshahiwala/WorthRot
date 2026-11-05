import math
import re

from backend.models import TranscriptWindow
from backend.services.errors import ConfigurationError, InvalidInputError

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
    "from", "how", "i", "in", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "what", "when", "where", "which", "who", "why", "with",
}


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in TOKEN_PATTERN.findall(text.casefold())
        if token not in STOPWORDS
    ]


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


def format_context(question: str, windows: list[TranscriptWindow]) -> str:
    content = "\n".join(f"[{window.timestamp}] {window.text}" for window in windows)
    return f"Question: {question.strip()}\n\n{content}".rstrip()


def _score_windows(
    question: str, windows: list[TranscriptWindow]
) -> list[TranscriptWindow]:
    query_tokens = set(_tokens(question))
    if not query_tokens:
        return [TranscriptWindow(w.start, w.end, w.text, 0.0) for w in windows]

    tokenized = [_tokens(window.text) for window in windows]
    document_frequency = {
        term: sum(term in set(document) for document in tokenized)
        for term in query_tokens
    }
    average_length = sum(map(len, tokenized)) / max(1, len(tokenized))
    scored: list[TranscriptWindow] = []
    for window, document in zip(windows, tokenized):
        frequencies = {term: document.count(term) for term in query_tokens}
        document_length = len(document)
        score = 0.0
        for term, frequency in frequencies.items():
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (len(windows) - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            denominator = frequency + 1.5 * (
                1 - 0.75 + 0.75 * document_length / max(1, average_length)
            )
            score += inverse_frequency * (frequency * 2.5 / denominator)
        scored.append(TranscriptWindow(window.start, window.end, window.text, score))
    return scored


def _trim_context(
    question: str, windows: list[TranscriptWindow], max_context_tokens: int
) -> list[TranscriptWindow]:
    if estimate_tokens(f"Question: {question.strip()}") > max_context_tokens:
        raise InvalidInputError("The question is too long to analyze.")

    ranked = sorted(windows, key=lambda window: window.score, reverse=True)
    selected: list[TranscriptWindow] = []
    for window in ranked:
        candidate = sorted([*selected, window], key=lambda item: item.start)
        if estimate_tokens(format_context(question, candidate)) <= max_context_tokens:
            selected.append(window)

    if not selected and ranked:
        highest = ranked[0]
        prefix = f"Question: {question.strip()}\n\n[{highest.timestamp}] "
        available_chars = max_context_tokens * 4 - len(prefix)
        if available_chars > 0:
            clipped = TranscriptWindow(
                highest.start,
                highest.end,
                highest.text[:available_chars].rsplit(" ", 1)[0],
                highest.score,
            )
            while (
                clipped.text
                and estimate_tokens(format_context(question, [clipped]))
                > max_context_tokens
            ):
                clipped = TranscriptWindow(
                    clipped.start,
                    clipped.end,
                    clipped.text.rsplit(" ", 1)[0],
                    clipped.score,
                )
            if clipped.text:
                selected.append(clipped)
    return sorted(selected, key=lambda window: window.start)


def retrieve_windows(
    question: str,
    windows: list[TranscriptWindow],
    top_k: int,
    short_transcript_tokens: int,
    max_context_tokens: int,
) -> tuple[list[TranscriptWindow], bool]:
    if estimate_tokens(f"Question: {question.strip()}") > max_context_tokens:
        raise InvalidInputError("The question is too long to analyze.")

    short_transcript = estimate_tokens(
        " ".join(window.text for window in windows)
    ) < short_transcript_tokens
    if short_transcript:
        if estimate_tokens(format_context(question, windows)) <= max_context_tokens:
            return windows, True
        candidates = _score_windows(question, windows)
    else:
        scored = _score_windows(question, windows)
        candidates = sorted(scored, key=lambda window: window.score, reverse=True)[
            :top_k
        ]
        if not any(window.score > 0 for window in candidates):
            return [], False

    selected = _trim_context(question, candidates, max_context_tokens)
    if candidates and not selected:
        raise ConfigurationError(
            "MAX_CONTEXT_TOKENS is too small to include transcript text."
        )
    return selected, short_transcript
