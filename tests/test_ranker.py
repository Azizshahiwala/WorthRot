from backend.models import VideoResult
from backend.services.ranker import best_video_id, rank_results


def video(
    video_id: str,
    verdict: str,
    coverage: str,
    fact_count: int,
) -> VideoResult:
    return {
        "verdict": verdict,
        "facts": [
            {"text": "Verified fact", "timestamp": "00:00", "url": ""}
            for _ in range(fact_count)
        ],
        "missing": [],
        "meta": {
            "video_id": video_id,
            "cached": False,
            "tokens_in": 0,
            "tokens_out": 0,
        },
        "coverage": coverage,
        "verified_fact_count": fact_count,
    }


def test_verdict_tier_order_and_unverified_always_last():
    results = [
        video("unknown", "Can't verify", "full", 9),
        video("rot", "Rot", "full", 9),
        video("skim", "Skim", "none", 1),
        video("worth", "Worth it", "none", 0),
    ]

    assert [item["meta"]["video_id"] for item in rank_results(results)] == [
        "worth",
        "skim",
        "rot",
        "unknown",
    ]


def test_coverage_breaks_ties_before_fact_count():
    results = [
        video("partial-many", "Skim", "partial", 5),
        video("full-one", "Skim", "full", 1),
    ]

    assert [item["meta"]["video_id"] for item in rank_results(results)] == [
        "full-one",
        "partial-many",
    ]


def test_fact_count_breaks_ties_after_verdict_and_coverage():
    results = [
        video("one", "Worth it", "full", 2),
        video("three", "Worth it", "full", 3),
    ]

    assert [item["meta"]["video_id"] for item in rank_results(results)] == [
        "three",
        "one",
    ]


def test_final_tie_preserves_input_order():
    results = [
        video("first", "Skim", "partial", 1),
        video("second", "Skim", "partial", 1),
    ]

    assert [item["meta"]["video_id"] for item in rank_results(results)] == [
        "first",
        "second",
    ]


def test_best_is_none_without_worthwhile_verdict():
    assert best_video_id(
        rank_results(
            [
                video("rot", "Rot", "none", 0),
                video("unknown", "Can't verify", "none", 0),
            ]
        )
    ) is None


def test_best_returns_top_covered_video_id():
    ranked = rank_results(
        [video("rot", "Rot", "none", 0), video("skim", "Skim", "partial", 1)]
    )

    assert best_video_id(ranked) == "skim"
