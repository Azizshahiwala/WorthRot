import base64
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.services.config import Settings
from backend.services.media.errors import MediaProviderError
from backend.services.media.frames import VideoFrame

MAX_FACTS = 5
MAX_FACT_WORDS = 15
MAX_MISSING_ITEMS = 3
MAX_MISSING_WORDS = 8
TIMESTAMP_PATTERN = re.compile(r"^(?:(\d+):)?([0-5]?\d):([0-5]\d)$")
SYSTEM_PROMPT = """Describe only what is visible in the supplied video frames.
Return JSON only with coverage, facts, and missing. Each fact must answer the
question, describe something visible, use at most 15 words, and cite the exact
timestamp of a supplied frame. Return at most 5 facts and 3 missing topics.
Each missing topic has at most 8 words. If the frames do not answer the
question, use coverage "none" and an empty facts list.
Shape: {"coverage":"full|partial|none","facts":[{"f":"...","t":"mm:ss"}],
"missing":["..."]}"""


def _seconds(timestamp: str) -> int | None:
    match = TIMESTAMP_PATTERN.fullmatch(timestamp)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return (int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)


def _parse_response(content: str, sent_timestamps: set[str]) -> dict:
    try:
        payload = json.loads(content.strip())
    except json.JSONDecodeError as error:
        raise MediaProviderError(
            "The vision model returned an invalid response."
        ) from error
    if not isinstance(payload, dict):
        raise MediaProviderError("The vision model returned an invalid response.")
    coverage = payload.get("coverage")
    if coverage not in {"full", "partial", "none"}:
        raise MediaProviderError("The vision model returned an invalid response.")
    raw_facts = payload.get("facts")
    raw_missing = payload.get("missing")
    if not isinstance(raw_facts, list) or not isinstance(raw_missing, list):
        raise MediaProviderError("The vision model returned an invalid response.")

    facts: list[dict] = []
    for item in raw_facts[:MAX_FACTS]:
        if not isinstance(item, dict):
            continue
        text, timestamp = item.get("f"), item.get("t")
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text.split()) > MAX_FACT_WORDS
            or not isinstance(timestamp, str)
            or timestamp not in sent_timestamps
            or _seconds(timestamp) is None
        ):
            continue
        facts.append({"text": " ".join(text.split()), "timestamp": timestamp})
    missing = [
        " ".join(value.split())
        for value in raw_missing
        if (
            isinstance(value, str)
            and value.strip()
            and len(value.split()) <= MAX_MISSING_WORDS
        )
    ][:MAX_MISSING_ITEMS]
    if coverage == "none":
        facts = []
    return {"coverage": coverage, "facts": facts, "missing": missing}


def analyze_frames(
    question: str, frames: list[VideoFrame], settings: Settings, timeout: float
) -> dict:
    api_key = os.environ.get("BAZAARLINK_API_KEY", "").strip()
    if not api_key:
        raise MediaProviderError(
            "Frame analysis is not configured. Set BAZAARLINK_API_KEY "
            "in the backend environment."
        )

    content = [{"type": "text", "text": f"Question: {question}"}]
    for frame in frames:
        encoded = base64.b64encode(frame.path.read_bytes()).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
            }
        )
        content.append(
            {"type": "text", "text": f"Frame timestamp: {frame.timestamp}"}
        )
    body = json.dumps(
        {
            "model": settings.model_name,
            "temperature": 0,
            "max_tokens": 300,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        }
    ).encode("utf-8")
    request = Request(
        f"{settings.llm_base_url}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    request.add_header("Authorization", "Bearer " + api_key)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 410:
            raise MediaProviderError(
                "The configured vision model is no longer available."
            ) from error
        raise MediaProviderError(
            "Frame analysis is unavailable. Try again later."
        ) from error
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise MediaProviderError(
            "Frame analysis is unavailable. Please try again."
        ) from error

    choices = payload.get("choices") if isinstance(payload, dict) else None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices else None
    message = choice.get("message") if isinstance(choice, dict) else None
    response_content = message.get("content") if isinstance(message, dict) else None
    if isinstance(response_content, list):
        response_content = "".join(
            part.get("text", "")
            for part in response_content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    if not isinstance(response_content, str):
        raise MediaProviderError("The vision model returned an invalid response.")
    parsed = _parse_response(response_content, {frame.timestamp for frame in frames})
    tokens_in = usage.get("prompt_tokens", 0) if isinstance(usage, dict) else 0
    tokens_out = usage.get("completion_tokens", 0) if isinstance(usage, dict) else 0
    if not isinstance(tokens_in, int) or tokens_in < 0:
        tokens_in = 0
    if not isinstance(tokens_out, int) or tokens_out < 0:
        tokens_out = 0
    return {
        **parsed,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
