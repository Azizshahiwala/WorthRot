import json

from backend.models import VideoResult
from backend.services.agreement import build_agreement
from backend.services.config import Settings


def make_result(video_id: str) -> VideoResult:
    return {
        "verdict": "Skim",
        "facts": [
            {
                "text": "The setup needs a 12V supply.",
                "timestamp": "00:12",
                "url": f"https://youtu.be/{video_id}?t=12",
            }
        ],
        "missing": [],
        "gap": None,
        "meta": {
            "video_id": video_id,
            "cached": False,
            "tokens_in": 10,
            "tokens_out": 4,
        },
        "coverage": "partial",
        "verified_fact_count": 1,
        "error": None,
    }


def make_settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        model_name="test-model",
        max_output_tokens=300,
        max_context_tokens=2500,
        top_k_windows=6,
        short_transcript_tokens=1500,
        max_video_minutes=45,
    )


def test_agreement_skips_when_fewer_than_two_videos_have_facts(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "backend.services.agreement._request_facts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("called")),
    )

    agreement = build_agreement(
        make_settings(tmp_path),
        "How does setup work?",
        [make_result("abcdefghijk"), {**make_result("lmnopqrstuv"), "facts": []}],
    )

    assert agreement is None


def test_agreement_filters_unknown_labels_and_records_usage(monkeypatch, tmp_path):
    observed = {}
    response = {
        "agree": [
            {"point": "Needs a 12V supply", "videos": ["A", "B", "unknown"]}
        ],
        "disagree": [
            {
                "point": "Setup time",
                "positions": [
                    {"video": "A", "claim": "Ten minutes"},
                    {"video": "B", "claim": "About an hour"},
                    {"video": "unknown", "claim": "Unrelated"},
                ],
            }
        ],
        "unanswered": ["warranty coverage"],
    }

    def request_facts(settings, context, **kwargs):
        observed["context"] = json.loads(context)
        observed["kwargs"] = kwargs
        return json.dumps(response), 31, 8

    monkeypatch.setattr(
        "backend.services.agreement._request_facts", request_facts
    )
    agreement = build_agreement(
        make_settings(tmp_path),
        "What are the setup requirements and time?",
        [make_result("abcdefghijk"), make_result("lmnopqrstuv")],
        timeout_seconds=4,
    )

    assert agreement == {
        "agree": [
            {"point": "Needs a 12V supply", "videos": ["A", "B"]}
        ],
        "disagree": [
            {
                "point": "Setup time",
                "positions": [
                    {"video": "A", "claim": "Ten minutes"},
                    {"video": "B", "claim": "About an hour"},
                ],
            }
        ],
        "unanswered": ["warranty coverage"],
        "tokens_in": 31,
        "tokens_out": 8,
    }
    assert observed["context"]["videos"][0]["label"] == "A"
    assert "transcript" not in observed["context"]
    assert observed["kwargs"] == {
        "timeout_seconds": 4,
        "prompt_filename": "agreement_prompt.txt",
    }
