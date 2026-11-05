import json
import os

import pytest

from backend.models import TranscriptWindow
from backend.services.config import Settings
from backend.services.verdict import extract_facts
from backend.services.verifier import verify_facts

LIVE_TEST_ENABLED = os.environ.get("RUN_LIVE_LLM_TESTS") == "1"
API_KEY_AVAILABLE = bool(os.environ.get("BAZAARLINK_API_KEY", "").strip())

pytestmark = pytest.mark.skipif(
    not (LIVE_TEST_ENABLED and API_KEY_AVAILABLE),
    reason="Set RUN_LIVE_LLM_TESTS=1 and BAZAARLINK_API_KEY in the process environment.",
)


def test_bazaarlink_extracts_a_verifiable_fact(tmp_path):
    model_name = os.environ.get("MODEL_NAME", "qwen/qwen3.7-flash:free").strip()
    transcript = (
        "For pour-over coffee, heat water to 93 degrees Celsius. "
        "Let it cool slightly before pouring."
    )
    settings = Settings(
        data_dir=tmp_path,
        model_name=model_name,
        max_output_tokens=120,
        max_context_tokens=2500,
        top_k_windows=1,
        short_transcript_tokens=1500,
        max_video_minutes=45,
    )
    context = (
        "Question: What water temperature is recommended for pour-over coffee?\n\n"
        f"[00:00] {transcript}"
    )

    extraction = extract_facts(settings, context)
    verified_facts = verify_facts(
        extraction["facts"],
        [TranscriptWindow(start=0, end=20, text=transcript)],
    )

    assert extraction["coverage"] in {"full", "partial", "none"}
    assert extraction["facts"]
    assert verified_facts
    assert extraction["tokens_in"] > 0
    assert extraction["tokens_out"] > 0
    print(
        json.dumps(
            {
                "model": model_name,
                "coverage": extraction["coverage"],
                "facts": extraction["facts"],
                "verified_facts": verified_facts,
                "tokens_in": extraction["tokens_in"],
                "tokens_out": extraction["tokens_out"],
            },
            indent=2,
        )
    )
