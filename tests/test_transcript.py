import pytest

from backend.services.errors import InvalidInputError
from backend.services.transcript import extract_video_id, parse_pasted_transcript

VIDEO_ID = "abcdefghijk"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VIDEO_ID}",
        f"https://youtu.be/{VIDEO_ID}",
        f"https://youtube.com/shorts/{VIDEO_ID}",
    ],
)
def test_youtube_url_forms_extract_video_id(url):
    assert extract_video_id(url) == VIDEO_ID


def test_non_youtube_and_malformed_urls_are_rejected():
    for url in (
        "https://example.com/watch?v=abcdefghijk",
        "javascript://youtube.com/watch?v=abcdefghijk",
    ):
        with pytest.raises(InvalidInputError):
            extract_video_id(url)


def test_timestamped_pasted_transcript_keeps_timestamps():
    transcript = parse_pasted_transcript(
        "[00:12] The first useful fact.\n[01:03] The second useful fact."
    )

    assert [(segment.start, segment.text) for segment in transcript.segments] == [
        (12, "The first useful fact."),
        (63, "The second useful fact."),
    ]
    assert transcript.language_code == "en"
    assert transcript.source == "manual"
