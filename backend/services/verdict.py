import json
import os
import re
from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.models import GapCheck, GapPart
from backend.services.config import DEFAULT_LLM_BASE_URL, Settings
from backend.services.errors import ConfigurationError, LLMError
from backend.services.language import language_name, word_count

MAX_FACTS = 5
MAX_MISSING_ITEMS = 3
MAX_FACT_WORDS = 15
MAX_QUOTE_WORDS = 12
MAX_MISSING_WORDS = 8
WORTH_IT_MINIMUM_FACTS = 2
SKIM_MINIMUM_FACTS = 1
FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
PROMPT_VERSION = "multilingual-v1"


class ModelFact(TypedDict):
    f: str
    t: str
    q: str


class Extraction(TypedDict):
    coverage: str
    facts: list[ModelFact]
    missing: list[str]
    parts: list[GapPart]
    tokens_in: int
    tokens_out: int


def _word_count(value: str, language: str = "und") -> int:
    return word_count(value, language)


def parse_gap_parts(value: object, language: str = "und") -> list[GapPart]:
    if not isinstance(value, list) or not 2 <= len(value) <= 4:
        return []
    parts: list[GapPart] = []
    for item in value:
        if not isinstance(item, dict):
            return []
        text, status = item.get("p"), item.get("s")
        if (
            not isinstance(text, str)
            or not text.strip()
            or _word_count(text, language) > 8
            or not isinstance(status, str)
            or status not in {"covered", "partial", "missing"}
        ):
            return []
        parts.append({"text": " ".join(text.split()), "status": status})
    return parts


def map_gap(parts: list[GapPart], verified_fact_count: int) -> GapCheck:
    mapped = [dict(part) for part in parts]
    if verified_fact_count <= 0:
        for part in mapped:
            part["status"] = "missing"
    else:
        remaining_covered = verified_fact_count
        for part in mapped:
            if part["status"] == "covered":
                if remaining_covered:
                    remaining_covered -= 1
                else:
                    part["status"] = "missing"
    covered = sum(part["status"] == "covered" for part in mapped)
    total = len(mapped)
    label = (
        "All covered"
        if total and covered == total
        else "Partly covered"
        if covered
        else "Not covered"
    )
    return {
        "covered": covered,
        "total": total,
        "label": label,
        "parts": mapped,
    }


def _http_error_message(status_code: int) -> str:
    messages = {
        400: (
            "The model provider rejected the request. Check MODEL_NAME and the configured "
            "request settings."
        ),
        401: (
            "The model provider rejected the API key. Check BAZAARLINK_API_KEY in the "
            "environment used to run the backend."
        ),
        403: (
            "The model provider denied access. Check the API key's permissions "
            "and access to the configured model."
        ),
        404: "The model provider could not find the configured model. Check MODEL_NAME.",
        429: (
            "The model provider rate or usage limit was reached. Check the "
            "account's limits, then try again."
        ),
    }
    if status_code in messages:
        return messages[status_code]
    if status_code >= 500:
        return "The model provider is temporarily unavailable. Please try again later."
    return (
        f"The model provider returned HTTP {status_code}. Check the API configuration "
        "and try again."
    )


def _parse_json_response(response_text: str) -> object:
    content = FENCE_PATTERN.sub("", response_text.strip()).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as error:
        raise LLMError(
            "The analysis response couldn't be verified. Please try again."
        ) from error


def parse_model_json(response_text: str, language: str = "und") -> dict:
    data = _parse_json_response(response_text)
    if not isinstance(data, dict):
        raise LLMError("The analysis response couldn't be verified. Please try again.")
    coverage = data.get("coverage")
    facts = data.get("facts")
    missing = data.get("missing")
    if not isinstance(coverage, str) or coverage not in {"full", "partial", "none"}:
        raise LLMError("The analysis response couldn't be verified. Please try again.")
    if not isinstance(facts, list) or not isinstance(missing, list):
        raise LLMError("The analysis response couldn't be verified. Please try again.")

    parsed_facts: list[ModelFact] = []
    for fact in facts[:MAX_FACTS]:
        if not isinstance(fact, dict):
            continue
        text, timestamp, quote = fact.get("f"), fact.get("t"), fact.get("q")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (text, timestamp, quote)
        ):
            continue
        text, timestamp, quote = (
            " ".join(text.split()),
            timestamp.strip(),
            " ".join(quote.split()),
        )
        if (
            _word_count(text, language) > MAX_FACT_WORDS
            or _word_count(quote, language) > MAX_QUOTE_WORDS
        ):
            continue
        parsed_facts.append({"f": text, "t": timestamp, "q": quote})

    parsed_missing = [
        " ".join(item.split())
        for item in missing
        if (
            isinstance(item, str)
            and item.strip()
            and _word_count(item, language) <= MAX_MISSING_WORDS
        )
    ][:MAX_MISSING_ITEMS]
    return {
        "coverage": coverage,
        "facts": parsed_facts if coverage != "none" else [],
        "missing": parsed_missing,
        "parts": parse_gap_parts(data.get("parts"), language),
    }


def _request_facts(
    settings: Settings,
    context: str,
    timeout_seconds: float | None = None,
    prompt_filename: str = "verdict_prompt.txt",
) -> tuple[str, int, int]:
    api_key = os.environ.get("BAZAARLINK_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError(
            "Analysis isn't configured yet. Set BAZAARLINK_API_KEY."
        )
    if not settings.model_name:
        raise ConfigurationError("Analysis isn't configured yet. Set MODEL_NAME.")
    base_url = os.environ.get("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).strip().rstrip("/")
    if not base_url:
        raise ConfigurationError("Analysis isn't configured yet. Set LLM_BASE_URL.")

    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / prompt_filename
    try:
        system_prompt = prompt_path.read_text(encoding="utf-8")
    except OSError as error:
        raise LLMError(
            "The analysis prompt is unavailable. Please try again later.", 503
        ) from error

    body = json.dumps(
        {
            "model": settings.model_name,
            "max_tokens": settings.max_output_tokens,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context},
            ],
        }
    ).encode("utf-8")
    request = Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(
            request, timeout=timeout_seconds if timeout_seconds is not None else 30
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise LLMError(_http_error_message(error.code)) from error
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise LLMError(
            "The analysis service is unavailable. Please try again."
        ) from error

    if not isinstance(payload, dict):
        raise LLMError(
            "The analysis service returned an invalid response. Please try again."
        )
    choices = payload.get("choices")
    usage = payload.get("usage")
    if not isinstance(choices, list) or not choices or not isinstance(usage, dict):
        raise LLMError(
            "The analysis service returned an invalid response. Please try again."
        )
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content:
        raise LLMError(
            "The analysis service returned an invalid response. Please try again."
        )
    try:
        tokens_in = int(usage["prompt_tokens"])
        tokens_out = int(usage["completion_tokens"])
    except (KeyError, TypeError, ValueError) as error:
        raise LLMError(
            "The analysis service returned invalid token usage. Please try again."
        ) from error
    if tokens_in < 0 or tokens_out < 0:
        raise LLMError(
            "The analysis service returned invalid token usage. Please try again."
        )
    return content, tokens_in, tokens_out


def extract_facts(
    settings: Settings,
    context: str,
    timeout_seconds: float | None = None,
) -> Extraction:
    response_text, tokens_in, tokens_out = _request_facts(
        settings, context, timeout_seconds=timeout_seconds
    )
    parsed = parse_model_json(response_text)
    return {
        "coverage": parsed["coverage"],
        "facts": parsed["facts"],
        "missing": parsed["missing"],
        "parts": parsed["parts"],
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }


def map_verdict(coverage: str, verified_fact_count: int) -> str:
    if verified_fact_count == 0:
        return "Rot"
    if coverage == "full" and verified_fact_count >= WORTH_IT_MINIMUM_FACTS:
        return "Worth it"
    if coverage == "partial" or (
        coverage == "full" and verified_fact_count == SKIM_MINIMUM_FACTS
    ):
        return "Skim"
    return "Rot"
