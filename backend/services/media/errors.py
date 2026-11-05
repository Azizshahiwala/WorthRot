class MediaError(Exception):
    def __init__(
        self, message: str, status_code: int = 422, code: str = "media_error"
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class MediaTimeoutError(MediaError):
    def __init__(self) -> None:
        super().__init__(
            "Media processing took too long. Try a shorter file.",
            status_code=408,
            code="media_timeout",
        )


class FfmpegUnavailableError(MediaError):
    def __init__(self) -> None:
        super().__init__(
            "Media processing is unavailable because ffmpeg is not installed.",
            status_code=503,
            code="ffmpeg_unavailable",
        )


class UnsupportedMediaError(MediaError):
    def __init__(self) -> None:
        super().__init__(
            "Upload an MP4 video or MP3 audio file.",
            status_code=415,
            code="unsupported_media",
        )


class MediaBusyError(MediaError):
    def __init__(self) -> None:
        super().__init__(
            "The media processor is busy. Please try again shortly.",
            status_code=429,
            code="media_busy",
        )


class MediaProviderError(MediaError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502, code="media_provider_error")
