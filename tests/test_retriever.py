from backend.models import TranscriptSegment, TranscriptWindow
from backend.services.retriever import (
    estimate_tokens,
    format_context,
    retrieve_windows,
)


def test_relevant_windows_rank_before_unrelated_windows():
    windows = [
        TranscriptWindow(0, 30, "A story about old castles and stone walls."),
        TranscriptWindow(40, 70, "Sharpen a kitchen knife with a whetstone."),
    ]

    selected, short_transcript = retrieve_windows(
        "How do I sharpen a knife with a stone?",
        windows,
        top_k=1,
        short_transcript_tokens=1,
        max_context_tokens=200,
    )

    assert short_transcript is False
    assert selected[0].timestamp == "00:40"


def test_zero_score_returns_no_windows_for_long_transcript():
    windows = [TranscriptWindow(0, 40, "A quiet story about sailing boats.")]

    selected, _ = retrieve_windows(
        "How do I sharpen a kitchen knife?",
        windows,
        top_k=6,
        short_transcript_tokens=1,
        max_context_tokens=200,
    )

    assert selected == []


def test_context_budget_trims_lower_ranked_windows():
    windows = [
        TranscriptWindow(
            start=index * 40,
            end=index * 40 + 35,
            text=(
                "Sharpening a knife uses a whetstone. "
                + ("Angle the blade carefully. " * 18)
            ),
        )
        for index in range(8)
    ]

    selected, _ = retrieve_windows(
        "How do I sharpen a knife with a whetstone?",
        windows,
        top_k=8,
        short_transcript_tokens=1,
        max_context_tokens=90,
    )
    context = format_context("How do I sharpen a knife with a whetstone?", selected)

    assert selected
    assert estimate_tokens(context) <= 90
    assert len(selected) < len(windows)


def test_short_transcript_skips_keyword_retrieval():
    windows = [
        TranscriptWindow(0, 10, "A quiet story about boats."),
        TranscriptWindow(10, 20, "More details about the harbor."),
    ]

    selected, short_transcript = retrieve_windows(
        "How do I sharpen a kitchen knife?",
        windows,
        top_k=1,
        short_transcript_tokens=100,
        max_context_tokens=200,
    )

    assert short_transcript is True
    assert [window.timestamp for window in selected] == ["00:00", "00:10"]


def test_scored_windows_preserve_caption_segments():
    segment = TranscriptSegment(12, 3, "Use a whetstone to sharpen a knife.")
    windows = [
        TranscriptWindow(
            0,
            40,
            segment.text,
            segments=[segment],
        )
    ]

    selected, _ = retrieve_windows(
        "How do I sharpen a knife?",
        windows,
        top_k=1,
        short_transcript_tokens=1,
        max_context_tokens=200,
    )

    assert selected[0].segments == [segment]
