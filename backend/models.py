from dataclasses import dataclass
from typing import Literal, TypedDict


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    duration: float
    text: str


@dataclass(frozen=True)
class TranscriptDocument:
    segments: list[TranscriptSegment]

    @property
    def duration_seconds(self) -> float:
        return max(
            (segment.start + segment.duration for segment in self.segments),
            default=0.0,
        )


@dataclass(frozen=True)
class TranscriptWindow:
    start: float
    end: float
    text: str
    score: float = 0.0

    @property
    def timestamp(self) -> str:
        total_seconds = int(self.start)
        return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


class AnalysisFact(TypedDict):
    text: str
    timestamp: str
    url: str


class AnalysisMeta(TypedDict):
    video_id: str
    cached: bool
    tokens_in: int
    tokens_out: int


class AnalysisResponse(TypedDict):
    verdict: Literal["Worth it", "Skim", "Rot", "Can't verify"]
    facts: list[AnalysisFact]
    missing: list[str]
    meta: AnalysisMeta
