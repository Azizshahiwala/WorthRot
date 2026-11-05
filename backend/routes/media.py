import logging
import threading

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from backend.services.config import Settings
from backend.services.media.analyzer import analyze_media_upload
from backend.services.media.errors import MediaBusyError, MediaError
from backend.services.media.workdir import sweep_stale_workdirs

logger = logging.getLogger(__name__)
media_bp = Blueprint("media", __name__)
_media_semaphore = threading.BoundedSemaphore(1)


@media_bp.errorhandler(RequestEntityTooLarge)
def handle_upload_too_large(
    _error: RequestEntityTooLarge,
) -> tuple[Response, int]:
    return jsonify(message="The uploaded file is too large."), 413


@media_bp.post("/analyze-media")
def analyze_media() -> Response | tuple[Response, int]:
    settings = Settings.from_env()
    sweep_stale_workdirs(settings)
    if not _media_semaphore.acquire(blocking=False):
        error = MediaBusyError()
        return jsonify(message=error.message, code=error.code), error.status_code
    try:
        question = request.form.get("question", "")
        uploads = request.files.getlist("file")
        if not uploads:
            return jsonify(message="Choose an MP4 or MP3 file."), 400
        if len(uploads) != 1:
            return jsonify(message="Upload one MP4 or MP3 file at a time."), 400
        upload = uploads[0]
        result = analyze_media_upload(question, upload.stream, settings)
        return jsonify(result)
    except MediaError as error:
        return jsonify(message=error.message, code=error.code), error.status_code
    except OSError:
        logger.exception("Media file processing failed")
        return (
            jsonify(message="Media analysis could not be completed. Please try again."),
            500,
        )
    finally:
        _media_semaphore.release()
