import hashlib
import hmac
import ipaddress
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo

import pytest
from flask import Flask, jsonify, request
from werkzeug.wrappers import Request

from app import create_app
from backend.rate_limit import (
    FEATURES,
    RateLimitSettings,
    RateLimiter,
    limited,
    rate_limit_bp,
)


class FakeClock:
    def __init__(self, value: datetime):
        self.value = value
        self.lock = Lock()

    def __call__(self) -> datetime:
        with self.lock:
            return self.value

    def set(self, value: datetime) -> None:
        with self.lock:
            self.value = value


def make_limiter(
    tmp_path: Path,
    *,
    limit: int = 10,
    global_cap: int = 200,
    clock: FakeClock | None = None,
    salt: str = "test-rate-salt",
    bypass_key: str = "",
    enabled: bool = True,
    trusted_proxy_hops: int = 1,
) -> RateLimiter:
    return RateLimiter(
        RateLimitSettings(
            enabled=enabled,
            feature_limits={feature: limit for feature in FEATURES},
            global_daily_cap=global_cap,
            timezone=ZoneInfo("UTC"),
            trusted_proxy_hops=trusted_proxy_hops,
            salt=salt,
            bypass_key=bypass_key,
            data_dir=tmp_path,
        ),
        clock=clock,
    )


def make_app(limiter: RateLimiter) -> Flask:
    app = Flask(__name__)
    app.extensions["rate_limiter"] = limiter
    app.register_blueprint(rate_limit_bp)

    @app.post("/analyze")
    @limited("analyze")
    def analyze():
        if request.args.get("raise") == "true":
            raise RuntimeError("forced route failure")
        status = int(request.args.get("status", "200"))
        return jsonify(status=status), status

    @app.post("/compare")
    @limited("compare")
    def compare():
        return jsonify(ok=True)

    @app.post("/limited-media")
    @limited("media")
    def media():
        request.form.get("question")
        return jsonify(ok=True)

    return app


def post(client, route="/analyze", **kwargs):
    return client.post(route, environ_base={"REMOTE_ADDR": "198.51.100.10"}, **kwargs)


def test_concurrent_reservations_never_exceed_limit(tmp_path):
    app = make_app(make_limiter(tmp_path, limit=10))

    def send_request(_):
        with app.test_client() as client:
            return post(client).status_code

    with ThreadPoolExecutor(max_workers=20) as executor:
        statuses = list(executor.map(send_request, range(20)))

    assert statuses.count(200) == 10
    assert statuses.count(429) == 10


def test_non_2xx_and_exceptions_release_but_success_keeps_slot(tmp_path):
    app = make_app(make_limiter(tmp_path, limit=1))
    client = app.test_client()

    failed = post(client, query_string={"status": "400"})
    assert failed.status_code == 400
    assert failed.headers["X-RateLimit-Remaining"] == "1"

    raised = post(client, query_string={"raise": "true"})
    assert raised.status_code == 500
    assert raised.headers["X-RateLimit-Remaining"] == "1"

    succeeded = post(client)
    assert succeeded.status_code == 200
    assert succeeded.headers["X-RateLimit-Remaining"] == "0"
    assert post(client).status_code == 429


def test_feature_counters_are_independent(tmp_path):
    client = make_app(make_limiter(tmp_path, limit=1)).test_client()

    assert post(client, "/analyze").status_code == 200
    assert post(client, "/compare").status_code == 200
    assert post(client, "/analyze").status_code == 429
    assert post(client, "/compare").status_code == 429


def test_day_rollover_resets_quota_in_configured_timezone(tmp_path):
    clock = FakeClock(datetime(2026, 11, 5, 23, 59, tzinfo=timezone.utc))
    app = make_app(make_limiter(tmp_path, limit=1, clock=clock))
    client = app.test_client()

    assert post(client).status_code == 200
    assert post(client).status_code == 429
    clock.set(datetime(2026, 11, 6, 0, 0, tzinfo=timezone.utc))
    assert post(client).status_code == 200


def test_global_cap_denies_with_capacity_code_and_releases_personal_slot(tmp_path):
    limiter = make_limiter(tmp_path, limit=1, global_cap=1)
    app = make_app(limiter)
    client = app.test_client()

    assert post(client).status_code == 200
    response = post(client)
    assert response.status_code == 429
    assert response.get_json()["code"] == "capacity_reached"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert limiter._connection().execute(
        "SELECT count FROM rate_counts WHERE feature='analyze'"
    ).fetchone()[0] == 1


def test_client_ip_uses_rightmost_trusted_hop_and_ipv6_64(tmp_path):
    limiter = make_limiter(tmp_path, trusted_proxy_hops=1)
    app = make_app(limiter)
    with app.test_request_context(
        "/analyze",
        headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"},
        environ_base={"REMOTE_ADDR": "9.8.7.6"},
    ):
        key = limiter._key_hash()
    expected = hmac.new(
        limiter._get_salt(), b"5.6.7.8", hashlib.sha256
    ).hexdigest()
    spoofed = hmac.new(
        limiter._get_salt(), b"1.2.3.4", hashlib.sha256
    ).hexdigest()
    assert key == expected
    assert key != spoofed

    addresses = [
        "2001:db8:abcd:12::1",
        "2001:db8:abcd:12::ffff",
    ]
    hashes = []
    for address in addresses:
        with app.test_request_context(
            "/analyze", environ_base={"REMOTE_ADDR": address}
        ):
            hashes.append(limiter._key_hash())
    assert hashes[0] == hashes[1]
    assert ipaddress.ip_network("2001:db8:abcd:12::/64").prefixlen == 64


def test_invalid_forwarding_value_falls_back_to_remote_addr(tmp_path):
    limiter = make_limiter(tmp_path)
    app = make_app(limiter)
    with app.test_request_context(
        "/analyze",
        headers={"X-Forwarded-For": "invalid"},
        environ_base={"REMOTE_ADDR": "198.51.100.20"},
    ):
        forwarded_key = limiter._key_hash()
    with app.test_request_context(
        "/analyze", environ_base={"REMOTE_ADDR": "198.51.100.20"}
    ):
        remote_key = limiter._key_hash()
    assert forwarded_key == remote_key


def test_salt_persists_across_limiter_restart_and_raw_ip_is_not_stored(
    tmp_path, caplog
):
    limiter = make_limiter(tmp_path, salt="")
    app = make_app(limiter)
    caplog.set_level(logging.DEBUG, logger="backend.rate_limit")

    with app.test_client() as client:
        response = post(client, headers={"X-Forwarded-For": "203.0.113.18"})
        assert response.status_code == 200

    restarted = make_limiter(tmp_path, salt="")
    with app.test_request_context(
        "/analyze",
        headers={"X-Forwarded-For": "203.0.113.18"},
        environ_base={"REMOTE_ADDR": "192.0.2.1"},
    ):
        first_hash = limiter._key_hash()
    with app.test_request_context(
        "/analyze",
        headers={"X-Forwarded-For": "203.0.113.18"},
        environ_base={"REMOTE_ADDR": "192.0.2.1"},
    ):
        second_hash = restarted._key_hash()

    assert (tmp_path / "rate_salt").is_file()
    assert first_hash == second_hash
    database = (tmp_path / "ratelimit.sqlite").read_bytes()
    assert b"203.0.113.18" not in database
    assert "203.0.113.18" not in caplog.text
    assert "forwarded hops" in caplog.text


def test_salt_file_preserves_binary_whitespace(tmp_path):
    salt = b" " * 32
    (tmp_path / "rate_salt").write_bytes(salt)
    limiter = make_limiter(tmp_path, salt="")

    assert limiter._get_salt() == salt


def test_demo_bypass_skips_only_personal_counter(tmp_path):
    app = make_app(
        make_limiter(tmp_path, limit=1, global_cap=2, bypass_key="judge-secret")
    )
    client = app.test_client()

    assert post(client).status_code == 200
    assert post(client, headers={"X-Demo-Key": "wrong-key"}).status_code == 429
    assert post(client).status_code == 429
    assert post(client, headers={"X-Demo-Key": "judge-secret"}).status_code == 200
    capacity = post(client, headers={"X-Demo-Key": "judge-secret"})
    assert capacity.status_code == 429
    assert capacity.get_json()["code"] == "capacity_reached"


def test_disabled_flag_does_not_consume_quota(tmp_path):
    app = make_app(make_limiter(tmp_path, limit=1, enabled=False))
    client = app.test_client()

    assert [post(client).status_code for _ in range(12)] == [200] * 12
    assert not (tmp_path / "ratelimit.sqlite").exists()


def test_storage_failure_fails_closed_with_503(tmp_path, monkeypatch, caplog):
    limiter = make_limiter(tmp_path)
    app = make_app(limiter)
    monkeypatch.setattr(
        limiter, "reserve", lambda _feature: (_ for _ in ()).throw(OSError("disk"))
    )

    response = post(app.test_client())

    assert response.status_code == 503
    assert response.get_json()["code"] == "rate_limit_unavailable"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert "Rate-limit storage is unavailable" in caplog.text


def test_purge_removes_rows_older_than_yesterday(tmp_path):
    clock = FakeClock(datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc))
    limiter = make_limiter(tmp_path, clock=clock)
    connection = limiter._connection()
    connection.execute(
        "INSERT INTO rate_counts VALUES ('old-hash', 'analyze', '2026-11-03', 1)"
    )
    connection.execute(
        "INSERT INTO global_counts VALUES ('analyze', '2026-11-03', 1)"
    )
    app = make_app(limiter)

    assert post(app.test_client()).status_code == 200

    assert connection.execute("SELECT COUNT(*) FROM rate_counts").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM global_counts").fetchone()[0] == 1


def test_429_headers_and_limits_endpoint_do_not_consume_quota(tmp_path):
    app = make_app(make_limiter(tmp_path, limit=1))
    client = app.test_client()

    initial = client.get("/limits", environ_base={"REMOTE_ADDR": "198.51.100.10"})
    assert initial.status_code == 200
    assert initial.get_json()["limits"]["analyze"]["remaining"] == 1

    assert post(client).status_code == 200
    denied = post(client)

    assert denied.status_code == 429
    payload = denied.get_json()
    assert payload["code"] == "rate_limited"
    assert payload["retry_after_seconds"] > 0
    assert payload["resets_at"]
    assert denied.headers["Retry-After"] == str(payload["retry_after_seconds"])
    assert denied.headers["X-RateLimit-Limit"] == "1"
    assert denied.headers["X-RateLimit-Remaining"] == "0"
    assert int(denied.headers["X-RateLimit-Reset"]) > 0
    assert client.get(
        "/limits", environ_base={"REMOTE_ADDR": "198.51.100.10"}
    ).get_json()["limits"]["analyze"]["remaining"] == 0


def test_media_limit_check_happens_before_multipart_body_parsing(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("RATE_LIMIT_MEDIA", "1")
    monkeypatch.setenv("RATE_LIMIT_SALT", "body-order-test")
    app = create_app(frontend_dist=tmp_path / "dist")
    limiter = app.extensions["rate_limiter"]
    with app.test_request_context(
        "/analyze-media", environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ):
        reservation, _, _ = limiter.reserve("media")
    assert reservation is not None
    monkeypatch.setattr(
        Request,
        "_load_form_data",
        lambda _request: pytest.fail("Multipart body was parsed before quota check."),
    )

    response = app.test_client().post(
        "/analyze-media",
        data={"question": "What is shown?", "file": (b"payload", "clip.mp4")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 429
    assert response.get_json()["code"] == "rate_limited"


def test_settings_support_feature_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_PER_FEATURE", "8")
    monkeypatch.setenv("RATE_LIMIT_ANALYZE", "4")
    settings = RateLimitSettings.from_env(tmp_path)

    assert settings.limit_for("analyze") == 4
    assert settings.limit_for("compare") == 8
    assert settings.limit_for("media") == 8
