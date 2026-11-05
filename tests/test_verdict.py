import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from backend.services.config import Settings
from backend.services.errors import ConfigurationError, LLMError
from backend.services.verdict import (
    _request_facts,
    map_verdict,
    parse_model_json,
)


def test_json_parser_accepts_valid_and_fenced_json():
    text = """```json
    {
      "coverage":"full",
      "facts":[{"f":"Use a whetstone.","t":"00:00","q":"Use a whetstone"}],
      "missing":[]
    }
    ```"""

    result = parse_model_json(text)

    assert result["coverage"] == "full"
    assert result["facts"][0]["q"] == "Use a whetstone"


def test_json_parser_rejects_invalid_json():
    with pytest.raises(LLMError, match="couldn't be verified"):
        parse_model_json("not json")

    with pytest.raises(LLMError, match="couldn't be verified"):
        parse_model_json('{"coverage":[],"facts":[],"missing":[]}')


@pytest.mark.parametrize(
    ("coverage", "facts", "expected"),
    [
        ("full", 2, "Worth it"),
        ("full", 1, "Skim"),
        ("partial", 1, "Skim"),
        ("partial", 0, "Rot"),
        ("none", 0, "Rot"),
    ],
)
def test_verdict_mapping(coverage, facts, expected):
    assert map_verdict(coverage, facts) == expected


def test_zero_verified_facts_always_means_rot():
    assert map_verdict("full", 0) == "Rot"


def test_model_request_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("BAZAARLINK_API_KEY", raising=False)
    settings = Settings(
        data_dir=tmp_path,
        model_name="configured-model",
        max_output_tokens=211,
        max_context_tokens=2500,
        top_k_windows=6,
        short_transcript_tokens=1500,
        max_video_minutes=45,
    )

    with pytest.raises(ConfigurationError, match="BAZAARLINK_API_KEY"):
        _request_facts(settings, "Question: how?")


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (400, "Check MODEL_NAME"),
        (401, "Check BAZAARLINK_API_KEY"),
        (403, "API key's permissions"),
        (404, "could not find the configured model"),
        (429, "account's limits"),
        (503, "temporarily unavailable"),
    ],
)
def test_provider_http_errors_include_actionable_message(
    monkeypatch, tmp_path, status_code, message
):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            status_code,
            "upstream error",
            hdrs=None,
            fp=BytesIO(b'{"error":{"message":"private upstream details"}}'),
        )

    monkeypatch.setenv("BAZAARLINK_API_KEY", "test-key")
    monkeypatch.setattr("backend.services.verdict.urlopen", fake_urlopen)
    settings = Settings(
        data_dir=tmp_path,
        model_name="configured-model",
        max_output_tokens=211,
        max_context_tokens=2500,
        top_k_windows=6,
        short_transcript_tokens=1500,
        max_video_minutes=45,
    )

    with pytest.raises(LLMError, match=message) as error:
        _request_facts(settings, "Question: how?")

    assert "private upstream details" not in error.value.message
    assert error.value.status_code == 502


def test_bazaarlink_request_uses_configured_model_and_records_usage(
    monkeypatch, tmp_path
):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exception_type, exception, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {"message": {"content": '{"coverage":"none"}'}}
                    ],
                    "usage": {"prompt_tokens": 13, "completion_tokens": 7},
                }
            ).encode()

    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("BAZAARLINK_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://proxy.example/v1/")
    monkeypatch.setattr("backend.services.verdict.urlopen", fake_urlopen)
    settings = Settings(
        data_dir=tmp_path,
        model_name="configured-model",
        max_output_tokens=211,
        max_context_tokens=2500,
        top_k_windows=6,
        short_transcript_tokens=1500,
        max_video_minutes=45,
    )

    response_text, tokens_in, tokens_out = _request_facts(
        settings, "Question: how?\n\n[00:00] transcript text"
    )

    request_payload = json.loads(captured["request"].data)
    assert request_payload["model"] == "configured-model"
    assert request_payload["max_tokens"] == 211
    assert request_payload["temperature"] == 0
    assert request_payload["messages"][0]["role"] == "system"
    assert request_payload["messages"][1]["content"].endswith("transcript text")
    assert captured["request"].full_url == (
        "https://proxy.example/v1/chat/completions"
    )
    assert captured["request"].get_header("Authorization") == "Bearer test-key"
    assert captured["timeout"] == 30
    assert (tokens_in, tokens_out) == (13, 7)
    assert response_text == '{"coverage":"none"}'
