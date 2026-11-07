import io
import json
import subprocess
from pathlib import Path
from urllib.error import HTTPError

import pytest
from PIL import Image, ImageDraw

from backend.services.config import Settings
from backend.services.media.errors import (
    FfmpegUnavailableError,
    MediaError,
    UnsupportedMediaError,
)
from backend.services.media import ffmpeg_runner, frames, validate
from backend.services.media import stt
from backend.services.media import vision
from backend.services.media.frames import VideoFrame
from backend.services.media.subtitles import _parse_srt
from backend.services.media.vision import _parse_response
from backend.services.media.workdir import media_workdir


def make_settings(data_dir: Path, **overrides) -> Settings:
    values = {
        "data_dir": data_dir,
        "model_name": "test-model",
        "max_output_tokens": 300,
        "max_context_tokens": 2500,
        "top_k_windows": 6,
        "short_transcript_tokens": 1500,
        "max_video_minutes": 45,
    }
    values.update(overrides)
    return Settings(**values)


def test_settings_use_shared_model_and_provider_url(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("BAZAARLINK_BASE_URL", "https://ignored.test/v1")
    monkeypatch.setenv("VISION_MODEL", "ignored-model")
    settings = Settings.from_env()
    assert settings.model_name == "qwen/qwen3.7-flash:free"
    assert settings.llm_base_url == "https://api.bazaarlink.ai/v1"

    monkeypatch.setenv("MODEL_NAME", "shared-vision-capable-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.test/v1/")
    settings = Settings.from_env()
    assert settings.model_name == "shared-vision-capable-model"
    assert settings.llm_base_url == "https://provider.test/v1"


def write_mp4(path: Path) -> None:
    path.write_bytes(b"\x00\x00\x00\x18ftypisom")


def test_detect_media_type_uses_magic_bytes_and_ignores_extension(tmp_path):
    mp4 = tmp_path / "misleading.mp3"
    write_mp4(mp4)
    assert validate.detect_media_type(mp4) == "mp4"

    mp3 = tmp_path / "misleading.mp4"
    mp3.write_bytes(b"ID3\x04\x00\x00")
    assert validate.detect_media_type(mp3) == "mp3"


def test_detect_media_type_rejects_disguised_other_file(tmp_path):
    disguised = tmp_path / "movie.mp4"
    disguised.write_bytes(b"not a media file")
    with pytest.raises(UnsupportedMediaError):
        validate.detect_media_type(disguised)


def test_validate_media_file_enforces_size_before_probe(tmp_path, monkeypatch):
    path = tmp_path / "oversized.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"x" * 1024 * 1024)
    monkeypatch.setattr(
        validate,
        "probe_media",
        lambda *_args: pytest.fail("oversize file should not be probed"),
    )
    with pytest.raises(MediaError, match="1 MB or smaller"):
        validate.validate_media_file(
            path, make_settings(tmp_path, max_upload_mb=1), 1
        )


def test_validate_media_file_enforces_duration(tmp_path, monkeypatch):
    path = tmp_path / "movie.mp4"
    write_mp4(path)
    monkeypatch.setattr(
        validate,
        "probe_media",
        lambda *_args: {
            "duration": 301,
            "streams": [{"codec_type": "video"}],
        },
    )
    with pytest.raises(MediaError, match="5 minutes or shorter"):
        validate.validate_media_file(path, make_settings(tmp_path), 1)


def test_ffmpeg_runner_uses_bounded_safe_arguments(tmp_path, monkeypatch):
    calls = {}
    monkeypatch.setattr(ffmpeg_runner, "resolve_ffmpeg", lambda: "C:\\tools\\ffmpeg.exe")

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(ffmpeg_runner.subprocess, "run", fake_run)
    ffmpeg_runner.run_ffmpeg(
        ["-protocol_whitelist", "file", "-i", str(tmp_path / "input.mp4")],
        timeout=13,
    )
    assert isinstance(calls["command"], list)
    assert calls["command"][0] == "C:\\tools\\ffmpeg.exe"
    assert "-nostdin" in calls["command"]
    assert "-protocol_whitelist" in calls["command"]
    assert calls["kwargs"] == {
        "shell": False,
        "timeout": 13,
        "check": False,
        "capture_output": True,
    }
    assert "untrusted-name.mp4" not in calls["command"]


def test_probe_media_reports_ffmpeg_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg_runner, "resolve_ffmpeg", lambda: None)
    with pytest.raises(FfmpegUnavailableError):
        ffmpeg_runner.probe_media(tmp_path / "input.mp4", 1)


def test_probe_media_fallback_preserves_stream_indexes(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg_runner, "resolve_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(ffmpeg_runner, "_ffprobe_path", lambda _binary: None)
    monkeypatch.setattr(
        ffmpeg_runner,
        "run_ffmpeg",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [],
            1,
            stdout=b"",
            stderr=(
                b"Duration: 00:00:12.50, start: 0.000000\n"
                b"Stream #0:0: Video: h264\n"
                b"Stream #0:2(eng): Subtitle: mov_text\n"
            ),
        ),
    )
    probe = ffmpeg_runner.probe_media(tmp_path / "input.mp4", 5)
    assert probe["duration"] == 12.5
    assert probe["streams"] == [
        {"index": 0, "codec_type": "video"},
        {"index": 2, "codec_type": "subtitle"},
    ]


def test_frames_deduplicate_and_preserve_sample_timestamps(tmp_path, monkeypatch):
    settings = make_settings(tmp_path, frame_interval_seconds=5, max_frames=16)

    def make_frame(path: Path, inverse: bool = False):
        image = Image.new("RGB", (32, 32), "black")
        draw = ImageDraw.Draw(image)
        if inverse:
            draw.rectangle((0, 0, 15, 31), fill="white")
        else:
            draw.rectangle((16, 0, 31, 31), fill="white")
        image.save(path)

    def fake_run_ffmpeg(_arguments, **_kwargs):
        frame_dir = tmp_path / "frames"
        make_frame(frame_dir / "frame_0001.jpg")
        make_frame(frame_dir / "frame_0002.jpg")
        make_frame(frame_dir / "frame_0003.jpg", inverse=True)
        return subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(frames, "run_ffmpeg", fake_run_ffmpeg)
    sampled = frames.sample_frames(
        tmp_path / "input.mp4",
        tmp_path,
        duration=15,
        settings=settings,
        timeout=10,
    )
    assert [frame.timestamp for frame in sampled] == ["00:00", "00:10"]
    assert len(list((tmp_path / "frames").glob("*.jpg"))) == 2


def test_evenly_spaced_frame_cap():
    frames_in = [
        VideoFrame(Path(str(index)), f"00:{index:02d}") for index in range(5)
    ]
    assert frames._evenly_spaced(frames_in, 3) == [
        frames_in[0],
        frames_in[2],
        frames_in[4],
    ]


def test_frame_verifier_drops_unknown_timestamps():
    parsed = _parse_response(
        '{"coverage":"full","facts":['
        '{"f":"Visible label","t":"00:05"},'
        '{"f":"Unsupported claim","t":"00:07"}],"missing":[]}',
        {"00:05"},
    )
    assert parsed["facts"] == [{"text": "Visible label", "timestamp": "00:05"}]
    assert parsed["parts"] == []


def test_vision_request_uses_shared_provider_settings(tmp_path, monkeypatch):
    settings = make_settings(
        tmp_path,
        llm_base_url="https://provider.test/v1",
        model_name="test-vision",
    )
    monkeypatch.setenv("BAZAARLINK_API_KEY", "test-key")
    frame_path = tmp_path / "frame.jpg"
    frame_path.write_bytes(b"jpeg")
    observed = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "coverage": "full",
                                        "facts": [
                                            {"f": "Visible text", "t": "00:00"}
                                        ],
                                        "missing": [],
                                    }
                                )
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                }
            ).encode()

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["auth"] = request.get_header("Authorization")
        observed["payload"] = json.loads(request.data)
        observed["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(vision, "urlopen", fake_urlopen)
    result = vision.analyze_frames(
        "What is shown?",
        [VideoFrame(frame_path, "00:00")],
        settings,
        timeout=9,
    )
    assert observed["url"] == "https://provider.test/v1/chat/completions"
    assert observed["auth"] == "Bearer test-key"
    assert observed["payload"]["model"] == "test-vision"
    assert observed["timeout"] == 9
    assert result["facts"] == [{"text": "Visible text", "timestamp": "00:00"}]


def test_vision_configuration_only_requires_api_key(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    monkeypatch.delenv("BAZAARLINK_API_KEY", raising=False)
    with pytest.raises(MediaError, match="BAZAARLINK_API_KEY"):
        vision.analyze_frames("What is shown?", [], settings, timeout=1)


def test_subtitles_are_normalized_to_timed_transcript():
    srt = "1\n00:00:02,300 --> 00:00:04,000\nHello there\n\n"
    assert _parse_srt(srt) == "[00:02] Hello there"


def test_stt_uses_gemini_key_and_preserves_valid_segment_timestamps(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("BAZAARLINK_API_KEY", raising=False)
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")
    observed = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return observed["body"].encode("utf-8")

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        observed["api_key"] = request.get_header("X-goog-api-key")
        observed["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(stt, "urlopen", fake_urlopen)
    observed["body"] = json.dumps(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "segments": [
                                            {
                                                "start_seconds": 2.5,
                                                "text": "The answer",
                                            },
                                            {
                                                "start_seconds": 12,
                                                "text": "Outside audio",
                                            },
                                        ]
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        }
    )
    timed = stt.transcribe_audio(audio_path, duration_seconds=10, timeout=12)
    assert timed == stt.Transcription("[00:02] The answer", timed=True)
    assert observed["url"] == stt.GEMINI_API_URL
    assert observed["timeout"] == 12
    assert observed["api_key"] == "test-gemini-key"
    assert observed["payload"]["contents"][0]["parts"][1]["inline_data"][
        "mime_type"
    ] == "audio/mp3"
    assert observed["payload"]["generationConfig"]["responseMimeType"] == (
        "application/json"
    )

    observed["body"] = json.dumps(
        {"candidates": [{"content": {"parts": [{"text": '{"segments": []}'}]}}]}
    )
    assert stt.transcribe_audio(audio_path, duration_seconds=10, timeout=12) is None


def test_stt_skips_provider_when_gemini_key_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("BAZAARLINK_API_KEY", "bazaarlink-key")
    assert (
        stt.transcribe_audio(tmp_path / "missing.mp3", duration_seconds=10, timeout=1)
        is None
    )


def test_stt_falls_back_to_elevenlabs_on_gemini_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("ELEVEN_LABS_API", "test-eleven-key")
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")
    observed = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "text": "Hello world! Next sentence",
                    "words": [
                        {
                            "text": "Hello",
                            "type": "word",
                            "start": 0.1,
                            "end": 0.4,
                        },
                        {
                            "text": "world!",
                            "type": "word",
                            "start": 0.4,
                            "end": 0.9,
                        },
                        {
                            "text": "Next",
                            "type": "word",
                            "start": 2.0,
                            "end": 2.3,
                        },
                        {
                            "text": "sentence",
                            "type": "word",
                            "start": 2.3,
                            "end": 2.8,
                        },
                        {
                            "text": "Out",
                            "type": "word",
                            "start": 15,
                            "end": 15.4,
                        },
                    ],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        observed.setdefault("urls", []).append(request.full_url)
        if request.full_url == stt.GEMINI_API_URL:
            raise HTTPError(request.full_url, 429, "Rate limited", None, None)
        observed["timeout"] = timeout
        observed["api_key"] = request.get_header("Xi-api-key")
        observed["body"] = request.data
        return FakeResponse()

    monkeypatch.setattr(stt, "urlopen", fake_urlopen)
    transcript = stt.transcribe_audio(audio_path, duration_seconds=10, timeout=7)

    assert transcript == stt.Transcription(
        "[00:00] Hello world!\n[00:02] Next sentence", timed=True
    )
    assert observed["urls"] == [stt.GEMINI_API_URL, stt.ELEVENLABS_API_URL]
    assert observed["timeout"] == 7
    assert observed["api_key"] == "test-eleven-key"
    assert b'name="model_id"\r\n\r\nscribe_v2' in observed["body"]
    assert b'name="timestamps_granularity"\r\n\r\nword' in observed["body"]
    assert b'name="file"; filename="audio.mp3"' in observed["body"]


def test_stt_does_not_use_elevenlabs_for_non_rate_limit_gemini_errors(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("ELEVEN_LABS_API", "test-eleven-key")
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"audio")

    def fail_if_called(request, timeout):
        assert timeout == 7
        raise HTTPError(request.full_url, 403, "Forbidden", None, None)

    monkeypatch.setattr(stt, "urlopen", fail_if_called)
    with pytest.raises(MediaError, match="Gemini speech transcription"):
        stt.transcribe_audio(audio_path, duration_seconds=10, timeout=7)


def test_media_workdir_is_removed_after_use(tmp_path):
    settings = make_settings(tmp_path)
    with media_workdir(settings) as workdir:
        (workdir / "input.mp4").write_bytes(b"data")
        assert workdir.exists()
    assert not workdir.exists()


def test_copy_upload_enforces_limit(tmp_path):
    with pytest.raises(MediaError, match="too large"):
        validate.copy_upload(io.BytesIO(b"12345"), tmp_path / "input.mp4", 4)


def test_media_route_rejects_wrong_content_type(tmp_path, monkeypatch):
    from app import create_app

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    client = create_app(tmp_path).test_client()
    response = client.post(
        "/analyze-media",
        data={
            "question": "What is shown?",
            "file": (io.BytesIO(b"not media"), "disguised.mp4"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 415
    assert response.json["message"] == "Upload an MP4 video or MP3 audio file."


def test_media_route_returns_friendly_size_error(tmp_path, monkeypatch):
    from app import create_app

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = create_app(tmp_path)
    app.config["MAX_CONTENT_LENGTH"] = 32
    response = app.test_client().post(
        "/analyze-media",
        data={
            "question": "What is shown?",
            "file": (io.BytesIO(b"x" * 100), "clip.mp4"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 413
    assert "too large" in response.json["message"]


def test_media_route_reports_busy_job(tmp_path, monkeypatch):
    from app import create_app
    from backend.routes import media as media_route

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    client = create_app(tmp_path).test_client()
    assert media_route._media_semaphore.acquire(blocking=False)
    try:
        response = client.post(
            "/analyze-media",
            data={"question": "Question"},
            content_type="multipart/form-data",
        )
    finally:
        media_route._media_semaphore.release()
    assert response.status_code == 429
    assert "busy" in response.json["message"]


def test_media_route_returns_ffmpeg_unavailable_message(tmp_path, monkeypatch):
    from app import create_app
    from backend.routes import media as media_route

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        media_route,
        "analyze_media_upload",
        lambda *_args: (_ for _ in ()).throw(FfmpegUnavailableError()),
    )
    response = create_app(tmp_path).test_client().post(
        "/analyze-media",
        data={
            "question": "Question",
            "file": (io.BytesIO(b"ID3\x04\x00"), "clip.mp3"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 503
    assert "ffmpeg" in response.json["message"]


def test_media_service_cleans_workdir_after_success_and_error(tmp_path, monkeypatch):
    from backend.services.media import analyzer

    settings = make_settings(tmp_path)
    monkeypatch.setattr(
        analyzer,
        "validate_media_file",
        lambda *_args: {
            "media_type": "mp3",
            "duration": 3,
            "streams": [{"codec_type": "audio"}],
        },
    )
    result = analyzer.analyze_media_upload(
        "What is said?", io.BytesIO(b"ID3\x04\x00"), settings
    )
    assert result["verdict"] == "Can't verify"
    assert not (tmp_path / "tmp").exists() or not list((tmp_path / "tmp").iterdir())

    def fail_validation(*_args):
        raise UnsupportedMediaError()

    monkeypatch.setattr(analyzer, "validate_media_file", fail_validation)
    with pytest.raises(UnsupportedMediaError):
        analyzer.analyze_media_upload(
            "What is shown?", io.BytesIO(b"ID3\x04\x00"), settings
        )
    assert not list((tmp_path / "tmp").iterdir())


def test_untimed_speech_cannot_return_a_positive_verdict(tmp_path, monkeypatch):
    from backend.services.media import analyzer
    from backend.services.media.stt import Transcription

    settings = make_settings(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(
        analyzer,
        "validate_media_file",
        lambda *_args: {
            "media_type": "mp3",
            "duration": 3,
            "streams": [{"codec_type": "audio"}],
        },
    )
    monkeypatch.setattr(analyzer, "extract_audio", lambda _src, output, _timeout: output)
    monkeypatch.setattr(
        analyzer,
        "transcribe_audio",
        lambda *_args: Transcription(
            "A useful but untimed statement.", timed=False
        ),
    )
    result = analyzer.analyze_media_upload(
        "What is said?", io.BytesIO(b"ID3\x04\x00"), settings
    )
    assert result["verdict"] == "Can't verify"
    assert result["facts"] == []


def test_frame_analysis_verdict_is_capped_at_skim(tmp_path, monkeypatch):
    from backend.services.media import analyzer

    settings = make_settings(tmp_path, max_frames=2)
    monkeypatch.setattr(
        analyzer,
        "validate_media_file",
        lambda *_args: {
            "media_type": "mp4",
            "duration": 10,
            "streams": [{"codec_type": "video"}],
        },
    )

    def fake_sample_frames(_media_path, workdir, *_args):
        frame_dir = workdir / "frames"
        frame_dir.mkdir()
        paths = [frame_dir / "frame_0001.jpg", frame_dir / "frame_0002.jpg"]
        for path in paths:
            path.write_bytes(b"frame")
        return [
            VideoFrame(paths[0], "00:00"),
            VideoFrame(paths[1], "00:05"),
        ]

    monkeypatch.setattr(analyzer, "sample_frames", fake_sample_frames)
    monkeypatch.setattr(
        analyzer,
        "analyze_frames",
        lambda *_args: {
            "coverage": "full",
            "facts": [
                {"text": "Visible first", "timestamp": "00:00"},
                {"text": "Visible second", "timestamp": "00:05"},
            ],
            "missing": [],
            "tokens_in": 20,
            "tokens_out": 10,
        },
    )
    result = analyzer.analyze_media_upload(
        "What is shown?", io.BytesIO(b"\x00\x00\x00\x18ftypisom"), settings
    )
    assert result["verdict"] == "Skim"
    assert result["source"] == "frames"
    assert result["meta"]["frames_sent"] == 2
    assert not list((tmp_path / "tmp").iterdir())
