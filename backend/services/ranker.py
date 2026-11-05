from backend.models import VideoResult

VERDICT_TIERS = {
    "Worth it": 0,
    "Skim": 1,
    "Rot": 2,
    "Can't verify": 3,
}
COVERAGE_TIERS = {"full": 0, "partial": 1, "none": 2}
SUCCESS_VERDICTS = {"Worth it", "Skim"}


def rank_results(results: list[VideoResult]) -> list[VideoResult]:
    return sorted(
        results,
        key=lambda result: (
            VERDICT_TIERS[result["verdict"]],
            COVERAGE_TIERS[result.get("coverage", "none")],
            -result.get("verified_fact_count", len(result["facts"])),
        ),
    )


def best_video_id(results: list[VideoResult]) -> str | None:
    if not results or results[0]["verdict"] not in SUCCESS_VERDICTS:
        return None
    return results[0]["meta"]["video_id"]
