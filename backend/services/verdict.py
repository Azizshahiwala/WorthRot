import json
import os
import re
from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.services.config import Settings
from backend.services.errors import ConfigurationError, LLMError

DEFAULT_LLM_BASE_URL = "https://api.bazaarlink.ai/v1"
MAX_FACTS = 5
MAX_MISSING_ITEMS = 3
MAX_FACT_WORDS = 15
MAX_QUOTE_WORDS = 12
MAX_MISSING_WORDS = 8
WORTH_IT_MINIMUM_FACTS = 2
SKIM_MINIMUM_FACTS = 1
FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class ModelFact(TypedDict):
    f: str
    t: str
    q: str


class Extraction(TypedDict):
    coverage: str
    facts: list[ModelFact]
    missing: list[str]
    tokens_in: int
    tokens_out: int


def _word_count(value: str) -> int:
    return len(value.split())


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


def parse_model_json(response_text: str) -> dict:
    content = FENCE_PATTERN.sub("", response_text.strip()).strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise LLMError(
            "The analysis response couldn't be verified. Please try again."
        ) from error

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
            _word_count(text) > MAX_FACT_WORDS
            or _word_count(quote) > MAX_QUOTE_WORDS
        ):
            continue
        parsed_facts.append({"f": text, "t": timestamp, "q": quote})

    parsed_missing = [
        " ".join(item.split())
        for item in missing
        if (
            isinstance(item, str)
            and item.strip()
            and _word_count(item) <= MAX_MISSING_WORDS
        )
    ][:MAX_MISSING_ITEMS]
    return {
        "coverage": coverage,
        "facts": parsed_facts if coverage != "none" else [],
        "missing": parsed_missing,
    }


def _request_facts(settings: Settings, context: str) -> tuple[str, int, int]:
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

    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "verdict_prompt.txt"
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
        with urlopen(request, timeout=30) as response:
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


def extract_facts(settings: Settings, context: str) -> Extraction:
    response_text, tokens_in, tokens_out = _request_facts(settings, context)
    parsed = parse_model_json(response_text)
    return {
        "coverage": parsed["coverage"],
        "facts": parsed["facts"],
        "missing": parsed["missing"],
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
