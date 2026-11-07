from backend.models import TranscriptWindow
from backend.models import TranscriptSegment
from backend.services.verifier import verify_facts


def test_fake_quote_is_dropped_and_real_quote_passes_case_and_whitespace():
    windows = [
        TranscriptWindow(
            0,
            20,
            "Use a whetstone   to sharpen a knife. Keep the blade steady.",
        )
    ]
    facts = [
        {
            "f": "A whetstone sharpens a knife.",
            "t": "00:00",
            "q": "USE a whetstone to sharpen a knife.",
        },
        {
            "f": "The video recommends oil.",
            "t": "00:00",
            "q": "Apply oil after sharpening.",
        },
        {
            "f": "It also says to use a whetstone.",
            "t": "00:00",
            "q": "use a whetstone to sharpen a knife.",
        },
    ]

    verified = verify_facts(facts, windows)

    assert verified == [
        {"text": "A whetstone sharpens a knife.", "timestamp": "00:00"}
    ]


def test_fact_with_unrelated_timestamp_is_dropped():
    windows = [TranscriptWindow(0, 20, "Use a whetstone to sharpen a knife.")]

    verified = verify_facts(
        [
            {
                "f": "A whetstone sharpens a knife.",
                "t": "01:00",
                "q": "Use a whetstone to sharpen a knife.",
            }
        ],
        windows,
    )

    assert verified == []


def test_fact_timestamp_uses_caption_line_containing_its_quote():
    windows = [
        TranscriptWindow(
            0,
            40,
            "An introduction. Use a whetstone to sharpen a knife.",
            segments=[
                TranscriptSegment(0, 4, "An introduction."),
                TranscriptSegment(17.5, 5, "Use a whetstone to sharpen a knife."),
            ],
        )
    ]

    verified = verify_facts(
        [
            {
                "f": "A whetstone sharpens a knife.",
                "t": "00:00",
                "q": "Use a whetstone to sharpen a knife.",
            }
        ],
        windows,
    )

    assert verified == [
        {"text": "A whetstone sharpens a knife.", "timestamp": "00:17"}
    ]


def test_fact_timestamp_falls_back_to_window_start_without_segments():
    windows = [
        TranscriptWindow(10, 40, "Use a whetstone to sharpen a knife.")
    ]

    verified = verify_facts(
        [
            {
                "f": "A whetstone sharpens a knife.",
                "t": "00:10",
                "q": "Use a whetstone to sharpen a knife.",
            }
        ],
        windows,
    )

    assert verified == [
        {"text": "A whetstone sharpens a knife.", "timestamp": "00:10"}
    ]
