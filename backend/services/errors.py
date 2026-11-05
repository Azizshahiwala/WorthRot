class AnalysisError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.result: dict | None = None


class InvalidInputError(AnalysisError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class VideoTooLongError(AnalysisError):
    def __init__(self, max_minutes: int) -> None:
        super().__init__(
            f"This video's transcript exceeds the {max_minutes}-minute limit.",
            status_code=413,
        )


class TranscriptUnavailableError(AnalysisError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class LLMError(AnalysisError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message, status_code=status_code)


class ConfigurationError(AnalysisError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class CacheError(AnalysisError):
    def __init__(self) -> None:
        super().__init__(
            "The analysis cache is unavailable. Please try again later.",
            status_code=503,
        )
