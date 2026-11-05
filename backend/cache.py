import hashlib
import json
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.models import TranscriptDocument, TranscriptSegment
from backend.services.errors import CacheError


def question_hash(question: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", question).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class AnalysisCache:
    def __init__(self, data_dir: Path) -> None:
        self.database_path = data_dir / "worthrot.sqlite3"
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS transcripts (
                        video_id TEXT PRIMARY KEY,
                        transcript_json TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS results (
                        video_id TEXT NOT NULL,
                        question_hash TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        PRIMARY KEY (video_id, question_hash)
                    );
                    """
                )
                connection.commit()
        except (OSError, sqlite3.Error) as error:
            raise CacheError() from error

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=5)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
        finally:
            connection.close()

    def get_transcript(self, video_id: str) -> TranscriptDocument | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT transcript_json FROM transcripts WHERE video_id = ?",
                    (video_id,),
                ).fetchone()
            if row is None:
                return None
            data = json.loads(row[0])
            segments = [
                TranscriptSegment(
                    start=float(segment["start"]),
                    duration=float(segment["duration"]),
                    text=str(segment["text"]),
                )
                for segment in data
            ]
            return TranscriptDocument(segments=segments)
        except (
            OSError,
            sqlite3.Error,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise CacheError() from error

    def set_transcript(self, video_id: str, transcript: TranscriptDocument) -> None:
        payload = json.dumps(
            [
                {
                    "start": segment.start,
                    "duration": segment.duration,
                    "text": segment.text,
                }
                for segment in transcript.segments
            ],
            ensure_ascii=False,
        )
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO transcripts (video_id, transcript_json)
                    VALUES (?, ?)
                    ON CONFLICT(video_id) DO UPDATE SET
                        transcript_json = excluded.transcript_json
                    """,
                    (video_id, payload),
                )
                connection.commit()
        except (OSError, sqlite3.Error) as error:
            raise CacheError() from error

    def get_result(self, video_id: str, normalized_question_hash: str) -> dict | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT result_json FROM results
                    WHERE video_id = ? AND question_hash = ?
                    """,
                    (video_id, normalized_question_hash),
                ).fetchone()
            if row is None:
                return None
            result = json.loads(row[0])
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("meta"), dict)
                or not isinstance(result.get("facts"), list)
                or not isinstance(result.get("missing"), list)
            ):
                raise ValueError("Invalid cached result.")
            return result
        except (OSError, sqlite3.Error, json.JSONDecodeError, ValueError) as error:
            raise CacheError() from error

    def set_result(
        self, video_id: str, normalized_question_hash: str, result: dict
    ) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO results (video_id, question_hash, result_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(video_id, question_hash) DO UPDATE SET
                        result_json = excluded.result_json
                    """,
                    (
                        video_id,
                        normalized_question_hash,
                        json.dumps(result, ensure_ascii=False),
                    ),
                )
                connection.commit()
        except (OSError, sqlite3.Error) as error:
            raise CacheError() from error
