from backend.models import TranscriptWindow
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
