import json
from pathlib import Path

from backend.models import TranscriptDocument, TranscriptSegment
from backend.services.chunker import clean_segments, make_windows

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "youtube-transcript.json"


def load_transcript():
    values = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return TranscriptDocument(
        segments=[TranscriptSegment(**segment) for segment in values]
    )


def test_cleaning_removes_music_tags_and_repeated_caption_lines():
    segments = [
        TranscriptSegment(0, 1, "[Music] Use the whetstone."),
        TranscriptSegment(1, 1, "Use the whetstone."),
        TranscriptSegment(2, 1, "Keep the blade steady."),
    ]

    cleaned = clean_segments(segments)

    assert [segment.text for segment in cleaned] == [
        "Use the whetstone.",
        "Keep the blade steady.",
    ]


def test_windowing_merges_caption_lines_and_preserves_start_timestamps():
    windows = make_windows(load_transcript())

    assert [window.timestamp for window in windows] == ["00:00", "00:45"]
    assert "whetstone" in windows[0].text
    assert "thirty degree angle" in windows[0].text
    assert "pasta water" in windows[1].text
