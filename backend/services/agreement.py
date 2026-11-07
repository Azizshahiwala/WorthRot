import json
import logging

from backend.models import VideoResult
from backend.services.config import Settings
from backend.services.verdict import _parse_json_response, _request_facts

logger = logging.getLogger(__name__)
MAX_ITEMS = 3


def _short_text(value: object, max_words: int) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = " ".join(value.split())
    return text if len(text.split()) <= max_words else None


def _build_agree(value: object, labels: set[str]) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        point = _short_text(item.get("point"), 15)
        videos = item.get("videos")
        if not isinstance(videos, list):
            continue
        videos = list(
            dict.fromkeys(
                label
                for label in videos
                if isinstance(label, str) and label in labels
            )
        )
        if point and len(videos) >= 2:
            items.append({"point": point, "videos": videos})
    return items


def _build_disagree(value: object, labels: set[str]) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value[:MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        point = _short_text(item.get("point"), 12)
        positions = item.get("positions")
        if not isinstance(positions, list):
            continue
        valid_positions = []
        seen_labels = set()
        for position in positions:
            if not isinstance(position, dict):
                continue
            label = position.get("video")
            claim = _short_text(position.get("claim"), 10)
            if (
                isinstance(label, str)
                and label in labels
                and label not in seen_labels
                and claim
            ):
                valid_positions.append({"video": label, "claim": claim})
                seen_labels.add(label)
        if point and len(valid_positions) >= 2:
            items.append({"point": point, "positions": valid_positions})
    return items


def _build_unanswered(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        text
        for item in value[:MAX_ITEMS]
        if (text := _short_text(item, 8)) is not None
    ]


def build_agreement(
    settings: Settings,
    question: str,
    ranked_results: list[VideoResult],
    timeout_seconds: float | None = None,
) -> dict | None:
    labeled_results = [
        (chr(ord("A") + index), result)
        for index, result in enumerate(ranked_results)
        if result.get("facts")
    ]
    if len(labeled_results) < 2:
        return None

    context = json.dumps(
        {
            "question": question,
            "videos": [
                {
                    "label": label,
                    "facts": [
                        {
                            "number": fact_number,
                            "timestamp": fact["timestamp"],
                            "text": fact["text"],
                        }
                        for fact_number, fact in enumerate(result["facts"], start=1)
                    ],
                }
                for label, result in labeled_results
            ],
        },
        ensure_ascii=False,
    )
    labels = {label for label, _ in labeled_results}
    try:
        response_text, tokens_in, tokens_out = _request_facts(
            settings,
            context,
            timeout_seconds=timeout_seconds,
            prompt_filename="agreement_prompt.txt",
        )
        response = _parse_json_response(response_text)
        if not isinstance(response, dict):
            return None
        return {
            "agree": _build_agree(response.get("agree"), labels),
            "disagree": _build_disagree(response.get("disagree"), labels),
            "unanswered": _build_unanswered(response.get("unanswered")),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
    except Exception:
        logger.exception("Could not build cross-video agreement.")
        return None
