import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, Response, current_app, jsonify, make_response, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from backend.services.errors import ConfigurationError

logger = logging.getLogger(__name__)
WINDOW_SECONDS = 5 * 60 * 60
FEATURES = ("analyze", "compare", "media")
rate_limit_bp = Blueprint("rate_limit", __name__)


def _read_positive_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a whole number.") from error
    if value < 1:
        raise ConfigurationError(f"{name} must be at least 1.")
    return value


@dataclass(frozen=True)
class RateLimitSettings:
    enabled: bool
    feature_limits: dict[str, int]
    global_daily_cap: int
    timezone: ZoneInfo
    trusted_proxy_hops: int
    salt: str
    bypass_key: str
    data_dir: Path

    @classmethod
    def from_env(cls, data_dir: Path) -> "RateLimitSettings":
        enabled_value = (
            os.environ.get("RATE_LIMIT_ENABLED", "").strip().lower() or "true"
        )
        if enabled_value not in {"true", "false"}:
            raise ConfigurationError("RATE_LIMIT_ENABLED must be true or false.")

        base_limit = _read_positive_int("RATE_LIMIT_PER_FEATURE", 5)
        feature_limits = {
            feature: _read_positive_int(
                f"RATE_LIMIT_{feature.upper()}", base_limit
            )
            for feature in FEATURES
        }
        try:
            timezone_name = os.environ.get("RATE_LIMIT_TZ", "").strip() or "UTC"
            rate_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ConfigurationError(
                "RATE_LIMIT_TZ must be a valid time zone."
            ) from error

        raw_hops = os.environ.get("TRUSTED_PROXY_HOPS", "").strip() or "1"
        try:
            trusted_proxy_hops = int(raw_hops)
        except ValueError as error:
            raise ConfigurationError(
                "TRUSTED_PROXY_HOPS must be a whole number."
            ) from error
        if trusted_proxy_hops < 1:
            raise ConfigurationError("TRUSTED_PROXY_HOPS must be at least 1.")

        return cls(
            enabled=enabled_value == "true",
            feature_limits=feature_limits,
            global_daily_cap=_read_positive_int(
                "GLOBAL_DAILY_CAP_PER_FEATURE", 200
            ),
            timezone=rate_timezone,
            trusted_proxy_hops=trusted_proxy_hops,
            salt=os.environ.get("RATE_LIMIT_SALT", "").strip(),
            bypass_key=os.environ.get("RATE_LIMIT_BYPASS_KEY", "").strip(),
            data_dir=data_dir,
        )

    def limit_for(self, feature: str) -> int:
        return self.feature_limits[feature]


@dataclass(frozen=True)
class Reservation:
    key_hash: str
    feature: str
    day: str
    bypassed_ip: bool


class RateLimiter:
    def __init__(
        self,
        settings: RateLimitSettings,
        clock: Callable[[], datetime] | None = None,
    ):
        self.settings = settings
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._connections = threading.local()
        self._salt_lock = threading.Lock()
        self._salt: bytes | None = None
        self._request_lock = threading.Lock()
        self._request_count = 0
        self._forwarded_log_lock = threading.Lock()
        self._forwarded_logged = False

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self.settings.timezone)

    def _reset(self, now: datetime | None = None) -> tuple[str, int, int]:
        current = now or self._now()
        timestamp = current.timestamp()
        end = (int(timestamp // WINDOW_SECONDS) + 1) * WINDOW_SECONDS
        reset_at = datetime.fromtimestamp(end, tz=self.settings.timezone)
        return (
            reset_at.isoformat(),
            int(end),
            max(1, int(end - timestamp)),
        )

    def _day(self, now: datetime | None = None) -> str:
        # "day" now names the current 5-hour window.
        return str(int((now or self._now()).timestamp() // WINDOW_SECONDS))

    def _connection(self) -> sqlite3.Connection:
        connection = getattr(self._connections, "connection", None)
        if connection is None:
            self.settings.data_dir.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                self.settings.data_dir / "ratelimit.sqlite",
                timeout=5,
                isolation_level=None,
            )
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS rate_counts (
                    key_hash TEXT NOT NULL,
                    feature TEXT NOT NULL,
                    day TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY (key_hash, feature, day)
                );
                CREATE TABLE IF NOT EXISTS global_counts (
                    feature TEXT NOT NULL,
                    day TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY (feature, day)
                );
                """
            )
            self._connections.connection = connection
        return connection

    def _get_salt(self) -> bytes:
        if self.settings.salt:
            return self.settings.salt.encode("utf-8")
        if self._salt is not None:
            return self._salt
        with self._salt_lock:
            if self._salt is not None:
                return self._salt
            self.settings.data_dir.mkdir(parents=True, exist_ok=True)
            salt_path = self.settings.data_dir / "rate_salt"
            try:
                descriptor = os.open(
                    salt_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                )
            except FileExistsError:
                salt = salt_path.read_bytes()
            else:
                salt = secrets.token_bytes(32)
                with os.fdopen(descriptor, "wb") as salt_file:
                    salt_file.write(salt)
                os.chmod(salt_path, 0o600)
            if len(salt) != 32:
                raise OSError("Rate-limit salt file is invalid.")
            self._salt = salt
            return salt

    def _forwarded_entries(self) -> list[str]:
        values = request.headers.get("X-Forwarded-For", "")
        entries = [value.strip() for value in values.split(",") if value.strip()]
        with self._forwarded_log_lock:
            if not self._forwarded_logged:
                logger.debug("Rate-limit received %d forwarded hops", len(entries))
                self._forwarded_logged = True
        return entries

    def _normalized_ip(self) -> str:
        entries = self._forwarded_entries()
        selected = (
            entries[-self.settings.trusted_proxy_hops]
            if len(entries) >= self.settings.trusted_proxy_hops
            else request.remote_addr
        )
        try:
            parsed = ipaddress.ip_address(selected or "")
        except ValueError:
            try:
                parsed = ipaddress.ip_address(request.remote_addr or "")
            except ValueError as error:
                raise OSError("No valid client address is available.") from error
        if isinstance(parsed, ipaddress.IPv6Address):
            return ipaddress.ip_network(f"{parsed}/64", strict=False).with_prefixlen
        return str(parsed)

    def _key_hash(self) -> str:
        return hmac.new(
            self._get_salt(), self._normalized_ip().encode("ascii"), hashlib.sha256
        ).hexdigest()

    def _request_tick(self) -> None:
        with self._request_lock:
            self._request_count += 1
            purge = self._request_count == 1 or self._request_count % 100 == 0
        if purge:
            self._purge_old_rows()

    def _purge_old_rows(self) -> None:
        previous = int(self._day()) - 1
        connection = self._connection()
        connection.execute(
            "DELETE FROM rate_counts WHERE CAST(day AS INTEGER) < ?", (previous,)
        )
        connection.execute(
            "DELETE FROM global_counts WHERE CAST(day AS INTEGER) < ?", (previous,)
        )

    def purge_stale_on_startup(self) -> None:
        if not self.settings.enabled:
            return
        try:
            self._purge_old_rows()
        except Exception:
            logger.exception("Could not purge old rate-limit records at startup.")

    @staticmethod
    def _count(
        connection: sqlite3.Connection, query: str, parameters: tuple[str, ...]
    ) -> int:
        row = connection.execute(query, parameters).fetchone()
        return int(row[0]) if row else 0

    def _remaining(
        self,
        connection: sqlite3.Connection,
        key_hash: str,
        feature: str,
        day: str,
        bypassed_ip: bool = False,
    ) -> int:
        personal_count = self._count(
            connection,
            "SELECT count FROM rate_counts WHERE key_hash=? AND feature=? AND day=?",
            (key_hash, feature, day),
        )
        global_count = self._count(
            connection,
            "SELECT count FROM global_counts WHERE feature=? AND day=?",
            (feature, day),
        )
        return max(
            0,
            min(
                self.settings.limit_for(feature)
                - (0 if bypassed_ip else personal_count),
                self.settings.global_daily_cap - global_count,
            ),
        )

    def remaining(
        self,
        feature: str,
        key_hash: str | None = None,
        bypassed_ip: bool = False,
    ) -> int:
        if not self.settings.enabled:
            return self.settings.limit_for(feature)
        key_hash = key_hash or self._key_hash()
        day = self._day()
        return self._remaining(
            self._connection(), key_hash, feature, day, bypassed_ip
        )

    def _is_bypassed(self) -> bool:
        expected_key = self.settings.bypass_key
        supplied_key = request.headers.get("X-Demo-Key", "")
        return bool(
            expected_key and hmac.compare_digest(supplied_key, expected_key)
        )

    def reserve(self, feature: str) -> tuple[Reservation | None, str, int]:
        self._request_tick()
        connection = self._connection()
        key_hash = self._key_hash()
        now = self._now()
        day = self._day(now)
        bypassed_ip = self._is_bypassed()
        try:
            connection.execute("BEGIN IMMEDIATE")
            global_count = self._count(
                connection,
                "SELECT count FROM global_counts WHERE feature=? AND day=?",
                (feature, day),
            )
            if global_count >= self.settings.global_daily_cap:
                remaining = self._remaining(
                    connection, key_hash, feature, day, bypassed_ip
                )
                connection.execute("COMMIT")
                return None, "capacity_reached", remaining

            if not bypassed_ip:
                connection.execute(
                    "INSERT OR IGNORE INTO rate_counts VALUES (?, ?, ?, 0)",
                    (key_hash, feature, day),
                )
                changed = connection.execute(
                    """
                    UPDATE rate_counts SET count=count+1
                    WHERE key_hash=? AND feature=? AND day=? AND count < ?
                    """,
                    (key_hash, feature, day, self.settings.limit_for(feature)),
                ).rowcount
                if changed != 1:
                    remaining = self._remaining(connection, key_hash, feature, day)
                    connection.execute("COMMIT")
                    return None, "rate_limited", remaining

            connection.execute(
                "INSERT OR IGNORE INTO global_counts VALUES (?, ?, 0)",
                (feature, day),
            )
            changed = connection.execute(
                """
                UPDATE global_counts SET count=count+1
                WHERE feature=? AND day=? AND count < ?
                """,
                (feature, day, self.settings.global_daily_cap),
            ).rowcount
            if changed != 1:
                connection.execute("ROLLBACK")
                remaining = self._remaining(
                    connection, key_hash, feature, day, bypassed_ip
                )
                return None, "capacity_reached", remaining

            remaining = self._remaining(
                connection, key_hash, feature, day, bypassed_ip
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

        return Reservation(key_hash, feature, day, bypassed_ip), "", remaining

    def release(self, reservation: Reservation) -> None:
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            if not reservation.bypassed_ip:
                connection.execute(
                    """
                    UPDATE rate_counts SET count=MAX(count-1, 0)
                    WHERE key_hash=? AND feature=? AND day=?
                    """,
                    (reservation.key_hash, reservation.feature, reservation.day),
                )
            connection.execute(
                """
                UPDATE global_counts SET count=MAX(count-1, 0)
                WHERE feature=? AND day=?
                """,
                (reservation.feature, reservation.day),
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    def snapshot(self) -> dict[str, dict[str, int | str]]:
        if not self.settings.enabled:
            return {
                feature: {
                    "limit": self.settings.limit_for(feature),
                    "remaining": self.settings.limit_for(feature),
                    "resetsAt": self._reset()[0],
                }
                for feature in FEATURES
            }
        key_hash = self._key_hash()
        day = self._day()
        connection = self._connection()
        reset_at = self._reset()[0]
        bypassed_ip = self._is_bypassed()
        return {
            feature: {
                "limit": self.settings.limit_for(feature),
                "remaining": self._remaining(
                    connection, key_hash, feature, day, bypassed_ip
                ),
                "resetsAt": reset_at,
            }
            for feature in FEATURES
        }


def _get_limiter() -> RateLimiter:
    limiter = current_app.extensions.get("rate_limiter")
    if not isinstance(limiter, RateLimiter):
        raise RuntimeError("The rate limiter is not configured.")
    return limiter


def _headers(
    response: Response, limiter: RateLimiter, feature: str, remaining: int
) -> Response:
    _reset_at, reset_epoch, _retry_after = limiter._reset()
    response.headers["X-RateLimit-Limit"] = str(limiter.settings.limit_for(feature))
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(reset_epoch)
    return response


def _error_response(
    message: str, status: int, code: str | None = None
) -> tuple[Response, int]:
    payload = {"message": message}
    if code:
        payload["code"] = code
    return jsonify(payload), status


def limited(feature: str) -> Callable:
    if feature not in FEATURES:
        raise ValueError(f"Unknown rate-limit feature: {feature}")

    def decorate(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args, **kwargs) -> Response:
            limiter = _get_limiter()
            if not limiter.settings.enabled:
                try:
                    response = make_response(view(*args, **kwargs))
                except HTTPException as error:
                    if isinstance(error, RequestEntityTooLarge):
                        response = make_response(
                            jsonify(message="The uploaded file is too large."), 413
                        )
                    else:
                        response = make_response(
                            jsonify(message=error.description), error.code or 500
                        )
                except Exception:
                    logger.exception("Unexpected error in limited %s request.", feature)
                    response = make_response(
                        jsonify(message="The request could not be completed."), 500
                    )
                return _headers(
                    response, limiter, feature, limiter.settings.limit_for(feature)
                )

            try:
                reservation, reason, remaining = limiter.reserve(feature)
            except Exception:
                logger.exception("Rate-limit storage is unavailable.")
                _reset_at, reset_epoch, _retry_after = limiter._reset()
                response = make_response(
                    jsonify(
                        message="Daily request limits are temporarily unavailable.",
                        code="rate_limit_unavailable",
                    ),
                    503,
                )
                response.headers["X-RateLimit-Limit"] = str(
                    limiter.settings.limit_for(feature)
                )
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(reset_epoch)
                return response

            if reservation is None:
                reset_at, reset_epoch, retry_after = limiter._reset()
                if reason == "capacity_reached":
                    message = "The service is at capacity for today."
                else:
                    message = (
                        "Daily limit reached for this feature. It resets at the "
                        "time shown."
                    )
                response = make_response(
                    jsonify(
                        message=message,
                        code=reason,
                        retry_after_seconds=retry_after,
                        resets_at=reset_at,
                    ),
                    429,
                )
                response.headers["Retry-After"] = str(retry_after)
                response.headers["X-RateLimit-Limit"] = str(
                    limiter.settings.limit_for(feature)
                )
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(reset_epoch)
                return response

            released = False
            try:
                response = make_response(view(*args, **kwargs))
            except HTTPException as error:
                try:
                    limiter.release(reservation)
                    released = True
                except Exception:
                    logger.exception("Rate-limit reservation release failed.")
                    return _storage_error_response(limiter, feature)
                if isinstance(error, RequestEntityTooLarge):
                    response = make_response(
                        jsonify(message="The uploaded file is too large."), 413
                    )
                else:
                    response = make_response(
                        jsonify(message=error.description), error.code or 500
                    )
            except Exception:
                logger.exception("Unexpected error in limited %s request.", feature)
                try:
                    limiter.release(reservation)
                    released = True
                except Exception:
                    logger.exception("Rate-limit reservation release failed.")
                    return _storage_error_response(limiter, feature)
                response = make_response(
                    jsonify(message="The request could not be completed."), 500
                )

            if not 200 <= response.status_code < 300:
                if not released:
                    try:
                        limiter.release(reservation)
                    except Exception:
                        logger.exception("Rate-limit reservation release failed.")
                        return _storage_error_response(limiter, feature)
                try:
                    remaining = limiter.remaining(
                        feature, reservation.key_hash, reservation.bypassed_ip
                    )
                except Exception:
                    logger.exception("Rate-limit storage is unavailable.")
                    return _storage_error_response(limiter, feature)
            else:
                try:
                    remaining = limiter.remaining(
                        feature, reservation.key_hash, reservation.bypassed_ip
                    )
                except Exception:
                    logger.exception("Rate-limit storage is unavailable.")
                    try:
                        limiter.release(reservation)
                    except Exception:
                        logger.exception("Rate-limit reservation release failed.")
                    return _storage_error_response(limiter, feature)
            return _headers(response, limiter, feature, remaining)

        return wrapped

    return decorate


def _storage_error_response(limiter: RateLimiter, feature: str) -> Response:
    _reset_at, reset_epoch, _retry_after = limiter._reset()
    response = make_response(
        jsonify(
            message="Daily request limits are temporarily unavailable.",
            code="rate_limit_unavailable",
        ),
        503,
    )
    response.headers["X-RateLimit-Limit"] = str(limiter.settings.limit_for(feature))
    response.headers["X-RateLimit-Remaining"] = "0"
    response.headers["X-RateLimit-Reset"] = str(reset_epoch)
    return response


@rate_limit_bp.get("/limits")
def limits() -> Response | tuple[Response, int]:
    try:
        return jsonify(limits=_get_limiter().snapshot())
    except Exception:
        logger.exception("Could not read daily request limits.")
        return _error_response(
            "Daily request limits are temporarily unavailable.",
            503,
            "rate_limit_unavailable",
        )