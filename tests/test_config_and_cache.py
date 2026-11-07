import pytest

from backend.cache import question_hash
from backend.cache import AnalysisCache
from backend.models import TranscriptDocument, TranscriptSegment
from backend.services.config import DEFAULT_MODEL_NAME, Settings
from backend.services.errors import ConfigurationError


def test_normalized_question_hash_ignores_case_and_extra_whitespace():
    assert question_hash("  HOW   do I learn? ") == question_hash("how do i learn?")


def test_output_token_setting_cannot_exceed_api_budget(monkeypatch):
    monkeypatch.setenv("MAX_OUTPUT_TOKENS", "301")

    with pytest.raises(ConfigurationError, match="MAX_OUTPUT_TOKENS"):
        Settings.from_env()


def test_model_defaults_to_bazaarlink_qwen_when_not_configured(monkeypatch):
    monkeypatch.delenv("MODEL_NAME", raising=False)

    assert Settings.from_env().model_name == DEFAULT_MODEL_NAME


def test_transcript_cache_keeps_language_source_and_question_language(tmp_path):
    cache = AnalysisCache(tmp_path)
    transcript = TranscriptDocument(
        [TranscriptSegment(1, 2, "Un ejemplo.")],
        language_code="es",
        source="auto",
        original_language_code="es",
    )

    cache.set_transcript("abcdefghijk", transcript, "es")

    assert cache.get_transcript("abcdefghijk", "es") == transcript
    assert cache.get_transcript("abcdefghijk", "en") is None
