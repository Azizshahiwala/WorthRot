import logging
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.services.config import Settings

logger = logging.getLogger(__name__)
STALE_WORKDIR_SECONDS = 60 * 60


def media_temp_root(settings: Settings) -> Path:
    return settings.data_dir / "tmp"


def sweep_stale_workdirs(settings: Settings, now: float | None = None) -> None:
    root = media_temp_root(settings)
    if not root.exists():
        return
    current_time = now if now is not None else time.time()
    for path in root.iterdir():
        try:
            if (
                path.is_dir()
                and current_time - path.stat().st_mtime > STALE_WORKDIR_SECONDS
            ):
                shutil.rmtree(path)
        except OSError:
            logger.warning("Unable to remove stale media work directory %s", path)


@contextmanager
def media_workdir(settings: Settings) -> Iterator[Path]:
    root = media_temp_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    workdir = root / str(uuid.uuid4())
    workdir.mkdir()
    try:
        yield workdir
    finally:
        try:
            shutil.rmtree(workdir)
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("Unable to remove media work directory %s", workdir)
