from __future__ import annotations

import functools
import logging
import shutil
import subprocess

log = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _static_paths() -> tuple[str, ...]:
    try:
        from static_ffmpeg import run as _srun

        paths = _srun.get_or_fetch_platform_executables_else_raise()
        return tuple(str(p) for p in paths if p)
    except Exception as exc:  # noqa: BLE001 - fall back to system binaries
        log.debug("static-ffmpeg unavailable: %s", exc)
        return ()


@functools.lru_cache(maxsize=1)
def ffmpeg_path() -> str:
    paths = _static_paths()
    if paths:
        return paths[0]
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    raise RuntimeError("ffmpeg not found (static-ffmpeg or PATH required)")


@functools.lru_cache(maxsize=1)
def ffprobe_path() -> str:
    paths = _static_paths()
    if len(paths) > 1:
        return paths[1]
    sys_ffprobe = shutil.which("ffprobe")
    if sys_ffprobe:
        return sys_ffprobe
    raise RuntimeError("ffprobe not found")


def run(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )
