from pathlib import Path

from backend.services.language import (
    detect_language,
    estimate_tokens,
    tokens,
    word_count,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / f"language-{name}.txt").read_text(encoding="utf-8")


def test_language_detection_handles_requested_scripts():
    assert detect_language(fixture("hi")) == "hi"
    assert detect_language(fixture("gu")) == "gu"
    assert detect_language(fixture("es")) == "es"
    assert detect_language(fixture("ja")) == "ja"
    assert detect_language(fixture("ar")) == "ar"


def test_retrieval_tokens_use_accent_insensitive_latin_and_cjk_bigrams():
    assert tokens("¿Cómo afilar el cuchillo?", "es") == [
        "afilar",
        "cuchillo",
    ]
    assert "砥石" in tokens("動画では砥石を使う", "ja")
    assert tokens("knife", "en") == tokens("knife", "en")


def test_word_and_token_estimates_account_for_scripts():
    assert word_count("包丁を砥石で研ぐ", "ja") == 4
    assert estimate_tokens("研" * 24) > estimate_tokens("a" * 24)
