import json
from pathlib import Path

from app import create_app
from backend.models import TranscriptDocument, TranscriptSegment
from backend.services.errors import LLMError, TranscriptUnavailableError

VIDEO_ID = "abcdefghijk"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "youtube-transcript.json"


def load_transcript():
    values = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return TranscriptDocument(
        segments=[TranscriptSegment(**segment) for segment in values]
    )


def prepare_app(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MAX_CONTEXT_TOKENS", "2500")
    return create_app().test_client()


def test_analyze_returns_verified_facts_and_deep_links(monkeypatch, tmp_path):
    client = prepare_app(monkeypatch, tmp_path)
    transcript_calls = []
    model_calls = []

    def fetch(video_id, question_language):
        transcript_calls.append(video_id)
        return load_transcript()

    def extract_facts(settings, context):
        model_calls.append(context)
        return {
            "coverage": "full",
            "facts": [
                {
                    "f": "A whetstone sharpens a knife.",
                    "t": "00:00",
                    "q": "Use a whetstone to sharpen a knife.",
                },
                {
                    "f": "Keep the blade at a thirty degree angle.",
                    "t": "00:00",
                    "q": "Keep the blade at a thirty degree angle.",
                },
                {
                    "f": "Apply oil after sharpening.",
                    "t": "00:00",
                    "q": "Apply oil after sharpening.",
                },
            ],
            "missing": [],
            "parts": [
                {"text": "sharpening method", "status": "covered"},
                {"text": "blade angle", "status": "covered"},
                {"text": "maintenance", "status": "missing"},
            ],
            "tokens_in": 80,
            "tokens_out": 24,
        }

    monkeypatch.setattr("backend.services.analyzer.fetch_transcript", fetch)
    monkeypatch.setattr("backend.services.analyzer.extract_facts", extract_facts)

    response = client.post(
        "/analyze",
        json={"question": "How do I sharpen a knife?", "urls": [VIDEO_URL]},
    )

    assert response.status_code == 200
    result = response.get_json()
    assert set(result) == {"verdict", "facts", "missing", "gap", "meta"}
    assert result["verdict"] == "Worth it"
    assert len(result["facts"]) == 2
    assert set(result["facts"][0]) == {"text", "timestamp", "url"}
    assert result["facts"][0]["timestamp"] == "00:00"
    assert result["facts"][0]["url"].endswith("&t=0")
    assert result["facts"][0]["url"].startswith(VIDEO_URL)
    assert result["meta"] == {
        "video_id": VIDEO_ID,
        "cached": False,
        "tokens_in": 80,
        "tokens_out": 24,
        "questionLanguage": "en",
        "transcriptLanguage": "en",
        "transcriptOriginalLanguage": "en",
        "transcriptSource": "manual",
        "retrievalTranslationFailed": False,
    }
    assert result["gap"]["covered"] == 2
    assert result["gap"]["total"] == 3
    assert result["gap"]["parts"][2]["status"] == "missing"

    second_response = client.post(
        "/analyze",
        json={"question": "  HOW DO I SHARPEN A KNIFE?  ", "urls": [VIDEO_URL]},
    )

    assert second_response.status_code == 200
    assert second_response.get_json()["meta"]["cached"] is True
    assert len(transcript_calls) == 1
    assert len(model_calls) == 1


def test_video_link_leads_fact_timestamp_by_two_seconds(monkeypatch, tmp_path):
    client = prepare_app(monkeypatch, tmp_path)

    monkeypatch.setattr(
        "backend.services.analyzer.fetch_transcript",
        lambda video_id, question_language: TranscriptDocument(
            segments=[
                TranscriptSegment(10, 2, "Use a whetstone to sharpen a knife.")
            ]
        ),
    )
    monkeypatch.setattr(
        "backend.services.analyzer.extract_facts",
        lambda settings, context: {
            "coverage": "full",
            "facts": [
                {
                    "f": "A whetstone sharpens a knife.",
                    "t": "00:10",
                    "q": "Use a whetstone to sharpen a knife.",
                }
            ],
            "missing": [],
            "parts": [],
            "tokens_in": 10,
            "tokens_out": 5,
        },
    )

    response = client.post(
        "/analyze",
        json={"question": "How do I sharpen a knife?", "urls": [VIDEO_URL]},
    )

    assert response.status_code == 200
    fact = response.get_json()["facts"][0]
    assert fact["timestamp"] == "00:10"
    assert fact["url"].endswith("&t=8")


def test_cross_language_question_is_translated_only_for_retrieval(
    monkeypatch, tmp_path
):
    client = prepare_app(monkeypatch, tmp_path)
    monkeypatch.setenv("SHORT_TRANSCRIPT_TOKENS", "1")
    transcript = TranscriptDocument(
        [
            TranscriptSegment(
                12,
                5,
                "Use a whetstone to sharpen a knife. Keep the blade steady.",
            )
        ],
        language_code="en",
        source="auto",
        original_language_code="en",
    )
    translation_calls = []
    analysis_contexts = []

    def translate(settings, context, timeout_seconds, prompt_filename):
        translation_calls.append((context, prompt_filename))
        return "How do I sharpen a knife?", 9, 4

    def extract(settings, context):
        analysis_contexts.append(context)
        return {
            "coverage": "full",
            "facts": [
                {
                    "f": "Una piedra de afilar afila un cuchillo.",
                    "t": "00:12",
                    "q": "Use a whetstone to sharpen a knife.",
                }
            ],
            "missing": [],
            "parts": [],
            "tokens_in": 10,
            "tokens_out": 5,
        }

    monkeypatch.setattr(
        "backend.services.analyzer.fetch_transcript",
        lambda video_id, question_language: transcript,
    )
    monkeypatch.setattr("backend.services.analyzer._request_facts", translate)
    monkeypatch.setattr("backend.services.analyzer.extract_facts", extract)

    response = client.post(
        "/analyze",
        json={"question": "¿Cómo se afila un cuchillo?", "urls": [VIDEO_URL]},
    )

    assert response.status_code == 200
    result = response.get_json()
    assert translation_calls[0][1] == "translate_prompt.txt"
    assert "Target language: English (en)" in translation_calls[0][0]
    assert "Answer language: Spanish (es)" in analysis_contexts[0]
    assert result["meta"]["questionLanguage"] == "es"
    assert result["meta"]["transcriptLanguage"] == "en"
    assert result["meta"]["tokens_in"] == 19
    assert result["meta"]["tokens_out"] == 9


def test_failed_cross_language_translation_uses_best_effort_windows(
    monkeypatch, tmp_path
):
    client = prepare_app(monkeypatch, tmp_path)
    monkeypatch.setenv("SHORT_TRANSCRIPT_TOKENS", "1")
    transcript = TranscriptDocument(
        [
            TranscriptSegment(
                12,
                5,
                "Use a whetstone to sharpen a knife. Keep the blade steady.",
            )
        ],
        language_code="en",
        source="auto",
        original_language_code="en",
    )
    analysis_contexts = []

    def fail_translation(*_args, **_kwargs):
        raise LLMError("translation unavailable")

    def extract(settings, context):
        analysis_contexts.append(context)
        return {
            "coverage": "none",
            "facts": [],
            "missing": [],
            "parts": [],
            "tokens_in": 10,
            "tokens_out": 2,
        }

    monkeypatch.setattr(
        "backend.services.analyzer.fetch_transcript",
        lambda video_id, question_language: transcript,
    )
    monkeypatch.setattr(
        "backend.services.analyzer._request_facts", fail_translation
    )
    monkeypatch.setattr("backend.services.analyzer.extract_facts", extract)

    response = client.post(
        "/analyze",
        json={"question": "¿Cómo se afila un cuchillo?", "urls": [VIDEO_URL]},
    )

    assert response.status_code == 200
    result = response.get_json()
    assert result["meta"]["retrievalTranslationFailed"] is True
    assert "whetstone" in analysis_contexts[0]


def test_timestamped_paste_transcript_uses_same_fact_pipeline(monkeypatch, tmp_path):
    client = prepare_app(monkeypatch, tmp_path)
    model_calls = []

    def extract_facts(settings, context):
        model_calls.append(context)
        return {
            "coverage": "partial",
            "facts": [
                {
                    "f": "A whetstone sharpens a knife.",
                    "t": "00:00",
                    "q": "Use a whetstone to sharpen a knife.",
                }
            ],
            "missing": ["blade angle"],
            "parts": [
                {"text": "sharpening method", "status": "covered"},
                {"text": "blade angle", "status": "missing"},
            ],
            "tokens_in": 20,
            "tokens_out": 10,
        }

    monkeypatch.setattr("backend.services.analyzer.extract_facts", extract_facts)

    response = client.post(
        "/analyze",
        json={
            "question": "How do I sharpen a knife?",
            "urls": [],
            "transcript": "[00:00] Use a whetstone to sharpen a knife.",
        },
    )

    assert response.status_code == 200
    result = response.get_json()
    assert result["verdict"] == "Skim"
    assert result["facts"] == [
        {
            "text": "A whetstone sharpens a knife.",
            "timestamp": "00:00",
            "url": "",
        }
    ]
    assert result["missing"] == ["blade angle"]
    assert len(model_calls) == 1


def test_untimestamped_paste_never_invents_a_timestamp(monkeypatch, tmp_path):
    client = prepare_app(monkeypatch, tmp_path)
    model_calls = []
    monkeypatch.setattr(
        "backend.services.analyzer.extract_facts",
        lambda settings, context: model_calls.append(context),
    )

    response = client.post(
        "/analyze",
        json={
            "question": "How do I sharpen a knife?",
            "urls": [],
            "transcript": "Use a whetstone to sharpen a knife.",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["verdict"] == "Can't verify"
    assert response.get_json()["facts"] == []
    assert model_calls == []


def test_invalid_url_and_multiple_videos_are_rejected(monkeypatch, tmp_path):
    client = prepare_app(monkeypatch, tmp_path)

    invalid_url = client.post(
        "/analyze",
        json={"question": "Question?", "urls": ["https://example.com/video"]},
    )
    multiple_urls = client.post(
        "/analyze",
        json={
            "question": "Question?",
            "urls": [VIDEO_URL, "https://youtu.be/12345678901"],
        },
    )

    assert invalid_url.status_code == 400
    assert "YouTube" in invalid_url.get_json()["message"]
    assert multiple_urls.status_code == 400
    assert "one YouTube video" in multiple_urls.get_json()["message"]


def test_missing_captions_returns_paste_transcript_guidance(monkeypatch, tmp_path):
    client = prepare_app(monkeypatch, tmp_path)

    def fetch(video_id, question_language):
        raise TranscriptUnavailableError("No captions. Paste a transcript.")

    monkeypatch.setattr("backend.services.analyzer.fetch_transcript", fetch)

    response = client.post(
        "/analyze",
        json={"question": "Question?", "urls": [VIDEO_URL]},
    )

    assert response.status_code == 422
    assert "Paste a transcript" in response.get_json()["message"]
    assert response.get_json()["result"]["verdict"] == "Can't verify"
    assert set(response.get_json()["result"]) == {
        "verdict",
        "facts",
        "missing",
        "gap",
        "meta",
    }


def test_video_over_limit_is_rejected(monkeypatch, tmp_path):
    client = prepare_app(monkeypatch, tmp_path)
    monkeypatch.setenv("MAX_VIDEO_MINUTES", "1")
    monkeypatch.setattr(
        "backend.services.analyzer.fetch_transcript",
        lambda video_id, question_language: TranscriptDocument(
            segments=[TranscriptSegment(61, 1, "A long video caption.")]
        ),
    )

    response = client.post(
        "/analyze",
        json={"question": "Question?", "urls": [VIDEO_URL]},
    )

    assert response.status_code == 413
    assert "1-minute limit" in response.get_json()["message"]


def test_llm_failure_is_returned_as_friendly_error(monkeypatch, tmp_path):
    client = prepare_app(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "backend.services.analyzer.fetch_transcript",
        lambda video_id, question_language: load_transcript(),
    )

    def fail(settings, context):
        raise LLMError("The analysis service is unavailable. Please try again.")

    monkeypatch.setattr("backend.services.analyzer.extract_facts", fail)

    response = client.post(
        "/analyze",
        json={"question": "How do I sharpen a knife?", "urls": [VIDEO_URL]},
    )

    assert response.status_code == 502
    assert "Please try again" in response.get_json()["message"]
    assert response.get_json()["result"]["verdict"] == "Can't verify"


def test_zero_score_skips_llm_and_returns_rot(monkeypatch, tmp_path):
    client = prepare_app(monkeypatch, tmp_path)
    monkeypatch.setenv("SHORT_TRANSCRIPT_TOKENS", "1")
    monkeypatch.setattr(
        "backend.services.analyzer.fetch_transcript",
        lambda video_id, question_language: load_transcript(),
    )
    model_calls = []
    monkeypatch.setattr(
        "backend.services.analyzer.extract_facts",
        lambda settings, context: model_calls.append(context),
    )

    response = client.post(
        "/analyze",
        json={"question": "How do astronomers study planets?", "urls": [VIDEO_URL]},
    )

    assert response.status_code == 200
    assert response.get_json()["verdict"] == "Rot"
    assert response.get_json()["facts"] == []
    assert response.get_json()["missing"] == ["no matching content found"]
    assert model_calls == []
