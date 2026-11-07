import json
import time
from pathlib import Path

import pytest

from app import create_app
from backend.models import TranscriptDocument, TranscriptSegment, VideoResult

VIDEO_IDS = ["abcdefghijk", "lmnopqrstuv", "wxyzABCDEFG", "123456789ab"]
VIDEO_URLS = [f"https://www.youtube.com/watch?v={video_id}" for video_id in VIDEO_IDS]
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "youtube-transcript.json"


def prepare_client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MAX_COMPARE_VIDEOS", "3")
    return create_app().test_client()


def result(video_id: str, verdict: str = "Worth it") -> VideoResult:
    return {
        "verdict": verdict,
        "facts": [
            {
                "text": "A verified fact.",
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
            "tokens_out": 5,
        },
        "coverage": "full",
        "verified_fact_count": 1,
        "error": None,
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"urls": VIDEO_URLS[:2]}, "question"),
        ({"question": "Q", "urls": [VIDEO_URLS[0]]}, "2 to 3"),
        ({"question": "Q", "urls": VIDEO_URLS}, "2 to 3"),
        ({"question": "Q", "urls": ["https://example.com/watch?v=abcdefghijk", VIDEO_URLS[1]]}, "YouTube"),
        ({"question": "Q", "urls": [VIDEO_URLS[0], f"https://youtu.be/{VIDEO_IDS[0]}"]}, "different"),
    ],
)
def test_compare_validation(monkeypatch, tmp_path, payload, message):
    response = prepare_client(monkeypatch, tmp_path).post("/compare", json=payload)

    assert response.status_code == 400
    assert message.lower() in response.get_json()["message"].lower()


def test_compare_ranks_results_and_returns_only_public_fields(
    monkeypatch, tmp_path
):
    client = prepare_client(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "backend.routes.compare._run_video",
        lambda question, url: result(url.split("=")[-1]),
    )
    monkeypatch.setattr(
        "backend.routes.compare.build_agreement",
        lambda *args, **kwargs: {
            "agree": [{"point": "A verified fact", "videos": ["A", "B"]}],
            "disagree": [],
            "unanswered": [],
            "tokens_in": 3,
            "tokens_out": 2,
        },
    )

    response = client.post(
        "/compare",
        json={"question": "How does this work?", "urls": VIDEO_URLS[:2]},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["best"] == VIDEO_IDS[0]
    assert [item["rank"] for item in payload["ranking"]] == [1, 2]
    assert payload["ranking"][0]["videoId"] == VIDEO_IDS[0]
    assert payload["ranking"][0]["error"] is None
    assert payload["ranking"][0]["gap"] is None
    assert payload["ranking"][0]["meta"] == {
        "cached": False,
        "tokens_in": 10,
        "tokens_out": 5,
    }
    assert "coverage" not in payload["ranking"][0]
    assert payload["agreement"] == {
        "agree": [{"point": "A verified fact", "videos": ["A", "B"]}],
        "disagree": [],
        "unanswered": [],
    }
    assert payload["meta"] == {"tokens_in_total": 23, "tokens_out_total": 12}


def test_compare_partial_failure_does_not_fail_other_videos(monkeypatch, tmp_path):
    client = prepare_client(monkeypatch, tmp_path)

    def run(question, url):
        if VIDEO_IDS[0] in url:
            raise RuntimeError("unavailable")
        return result(VIDEO_IDS[1])

    monkeypatch.setattr("backend.routes.compare._run_video", run)
    response = client.post(
        "/compare",
        json={"question": "Question?", "urls": VIDEO_URLS[:2]},
    )

    assert response.status_code == 200
    by_id = {video["videoId"]: video for video in response.get_json()["ranking"]}
    assert by_id[VIDEO_IDS[0]]["verdict"] == "Can't verify"
    assert by_id[VIDEO_IDS[0]]["error"]["message"]
    assert by_id[VIDEO_IDS[1]]["verdict"] == "Worth it"
    assert response.get_json()["agreement"] is None


def test_compare_timeout_does_not_block_completed_videos(monkeypatch, tmp_path):
    client = prepare_client(monkeypatch, tmp_path)
    monkeypatch.setenv("COMPARE_TIMEOUT_SECONDS", "1")

    def run(question, url):
        if VIDEO_IDS[0] in url:
            time.sleep(1.2)
            return result(VIDEO_IDS[0])
        return result(VIDEO_IDS[1])

    monkeypatch.setattr("backend.routes.compare._run_video", run)
    response = client.post(
        "/compare",
        json={"question": "Question?", "urls": VIDEO_URLS[:2]},
    )

    by_id = {video["videoId"]: video for video in response.get_json()["ranking"]}
    assert by_id[VIDEO_IDS[0]]["verdict"] == "Can't verify"
    assert by_id[VIDEO_IDS[1]]["verdict"] == "Worth it"


def test_agreement_failure_does_not_fail_compare(monkeypatch, tmp_path):
    client = prepare_client(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "backend.routes.compare._run_video",
        lambda question, url: result(url.split("=")[-1]),
    )
    monkeypatch.setattr(
        "backend.routes.compare.build_agreement",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("model error")),
    )

    response = client.post(
        "/compare",
        json={"question": "Question?", "urls": VIDEO_URLS[:2]},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["agreement"] is None
    assert len(payload["ranking"]) == 2


def test_repeated_compare_uses_cached_result_without_another_llm_call(
    monkeypatch, tmp_path
):
    client = prepare_client(monkeypatch, tmp_path)
    segments = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    transcript = TranscriptDocument(
        segments=[TranscriptSegment(**segment) for segment in segments]
    )
    model_calls = []
    monkeypatch.setattr(
        "backend.services.analyzer.fetch_transcript",
        lambda video_id, question_language: transcript,
    )

    def extract(settings, context):
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
            ],
            "missing": [],
            "tokens_in": 20,
            "tokens_out": 5,
        }

    monkeypatch.setattr("backend.services.analyzer.extract_facts", extract)
    monkeypatch.setattr("backend.routes.compare.build_agreement", lambda *args, **kwargs: None)
    payload = {"question": "How to sharpen a knife?", "urls": VIDEO_URLS[:2]}

    first = client.post("/compare", json=payload)
    second = client.post("/compare", json=payload)

    assert first.status_code == second.status_code == 200
    assert len(model_calls) == 2
    assert all(video["meta"]["cached"] for video in second.get_json()["ranking"])
