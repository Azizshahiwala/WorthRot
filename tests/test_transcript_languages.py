from types import SimpleNamespace

import pytest

from backend.services.transcript import _transcript_candidates


def track(code, *, generated=False, translatable=False, translations=()):
    return SimpleNamespace(
        language_code=code,
        is_generated=generated,
        is_translatable=translatable,
        translation_languages=[
            SimpleNamespace(language_code=item) for item in translations
        ],
        translate=lambda target: track(target),
        fetch=lambda: [],
    )


def transcript_list(manual=(), generated=()):
    return SimpleNamespace(
        manually_created_transcripts={item.language_code: item for item in manual},
        generated_transcripts={item.language_code: item for item in generated},
    )


def test_caption_selection_prefers_manual_question_language_then_original():
    manual_spanish = track("es")
    manual_english = track("en")
    auto_hindi = track("hi", generated=True)
    candidates = _transcript_candidates(
        transcript_list(
            [manual_spanish, manual_english],
            [auto_hindi],
        ),
        "en",
    )

    assert candidates[0] == (manual_english, "manual", "en")
    assert candidates[1] == (manual_spanish, "manual", "es")
    assert candidates[2] == (auto_hindi, "auto", "hi")


def test_caption_selection_uses_generated_original_when_no_manual_exists():
    generated = track("ja", generated=True)

    assert _transcript_candidates(
        transcript_list(generated=[generated]), "en"
    ) == [(generated, "auto", "ja")]


def test_translatable_caption_is_last_choice():
    original = track(
        "es", generated=True, translatable=True, translations=("en",)
    )
    candidates = _transcript_candidates(
        transcript_list(generated=[original]), "en"
    )

    assert candidates[0] == (original, "auto", "es")
    assert candidates[1][1:] == ("translated", "es")
    assert candidates[1][0].language_code == "en"
