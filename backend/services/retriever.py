import math
from dataclasses import replace

from backend.models import TranscriptWindow
from backend.services.errors import ConfigurationError, InvalidInputError
from backend.services.language import estimate_tokens
from backend.services.language import tokens as tokenize


def format_context(
    question: str, windows: list[TranscriptWindow], language: str = "en"
) -> str:
    content = "\n".join(f"[{window.timestamp}] {window.text}" for window in windows)
    return f"Question: {question.strip()}\n\n{content}".rstrip()


def _tokens(text: str, language: str) -> list[str]:
    return tokenize(text, language)


def _score_windows(
    question: str, windows: list[TranscriptWindow], language: str
) -> list[TranscriptWindow]:
    query_tokens = set(_tokens(question, language))
    if not query_tokens:
        return [replace(window, score=0.0) for window in windows]

    tokenized = [_tokens(window.text, language) for window in windows]
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
        scored.append(replace(window, score=score))
    return scored


def _trim_context(
    question: str,
    windows: list[TranscriptWindow],
    max_context_tokens: int,
    language: str,
) -> list[TranscriptWindow]:
    if estimate_tokens(f"Question: {question.strip()}") > max_context_tokens:
        raise InvalidInputError("The question is too long to analyze.")

    ranked = sorted(windows, key=lambda window: window.score, reverse=True)
    selected: list[TranscriptWindow] = []
    for window in ranked:
        candidate = sorted([*selected, window], key=lambda item: item.start)
        if estimate_tokens(format_context(question, candidate, language)) <= max_context_tokens:
            selected.append(window)

    if not selected and ranked:
        highest = ranked[0]
        prefix = f"Question: {question.strip()}\n\n[{highest.timestamp}] "
        available_chars = max_context_tokens * 2 - len(prefix)
        if available_chars > 0:
            clipped = replace(
                highest,
                text=highest.text[:available_chars].rstrip(),
            )
            while (
                clipped.text
                and estimate_tokens(format_context(question, [clipped], language))
                > max_context_tokens
            ):
                clipped = replace(
                    clipped,
                    text=clipped.text[
                        : max(0, len(clipped.text) - max(1, len(clipped.text) // 10))
                    ].rstrip(),
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
    language: str = "en",
    best_effort: bool = False,
) -> tuple[list[TranscriptWindow], bool]:
    if estimate_tokens(f"Question: {question.strip()}") > max_context_tokens:
        raise InvalidInputError("The question is too long to analyze.")

    short_transcript = estimate_tokens(
        " ".join(window.text for window in windows)
    ) < short_transcript_tokens
    if short_transcript:
        if estimate_tokens(format_context(question, windows, language)) <= max_context_tokens:
            return windows, True
        short_transcript = False
        candidates = _score_windows(question, windows, language)
    else:
        scored = _score_windows(question, windows, language)
        candidates = sorted(scored, key=lambda window: window.score, reverse=True)[
            :top_k
        ]
        if not any(window.score > 0 for window in candidates) and not best_effort:
            return [], False

    if best_effort and not any(window.score > 0 for window in candidates):
        candidates = sorted(candidates, key=lambda window: window.start)[:top_k]
    selected = _trim_context(
        question, candidates, max_context_tokens, language
    )
    if candidates and not selected:
        raise ConfigurationError(
            "MAX_CONTEXT_TOKENS is too small to include transcript text."
        )
    return selected, short_transcript
