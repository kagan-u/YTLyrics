from __future__ import annotations

import logging
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from .background import (
    build_video_filter,
    ensure_sprites,
    gradient_input_args,
    smoke_input_args,
    sprite_input_args,
)
from .errors import Cancelled, RenderError
from .ffmpeg_util import ffmpeg_path

log = logging.getLogger(__name__)

ProgressFn = Callable[[float], None]
CancelFn = Callable[[], bool]


def render_video(
    *,
    ass_path: Path,
    audio_path: Path,
    out_path: Path,
    workdir: Path,
    preset: str,
    duration: float,
    width: int,
    height: int,
    fps: int,
    cancel: CancelFn | None = None,
    on_progress: ProgressFn | None = None,
    sprite_count: int = 7,
) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    sprites = ensure_sprites()

    inputs: list[str] = []
    inputs += gradient_input_args(
        preset, width=width, height=height, fps=fps, duration=duration
    )
    inputs += smoke_input_args(
        width=width, height=height, fps=fps, duration=duration,
        seed=abs(hash(preset)) % 99991,
    )
    inputs += sprite_input_args(sprites, sprite_count, duration)

    # relative filename: cwd=workdir avoids colon-escaping issues on Windows
    ass_name = Path(ass_path).name
    filter_complex = build_video_filter(
        preset, ass_file=ass_name, sprites=sprites, sprite_count=sprite_count
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    audio_idx = 2 + sprite_count
    cmd = [
        ffmpeg_path(),
        "-y", "-hide_banner", "-loglevel", "error",
        "-stats_period", "0.5",
        *inputs,
        "-i", str(audio_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", f"{audio_idx}:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-shortest", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        str(out_path),
    ]

    log.debug("render cmd: %s", " ".join(cmd))
    if cancel and cancel():
        raise Cancelled()

    err_path = workdir / "ffmpeg_render.log"
    with err_path.open("wb") as err_f:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=err_f,
            text=True,
            bufsize=1,
        )
        try:
            _read_progress(proc, duration, cancel, on_progress)
        except Cancelled:
            proc.kill()
            proc.wait(timeout=15)
            raise
        except Exception:
            proc.kill()
            proc.wait(timeout=15)
            raise

    if proc.returncode != 0:
        tail = ""
        try:
            tail = err_path.read_text(errors="ignore")[-600:]
        except OSError:
            pass
        raise RenderError(f"ffmpeg render error (rc={proc.returncode}): {tail}")
    if cancel and cancel():
        raise Cancelled()
    if on_progress:
        on_progress(1.0)
    return out_path


def _read_progress(
    proc: subprocess.Popen,
    duration: float,
    cancel: CancelFn | None,
    on_progress: ProgressFn | None,
) -> None:
    assert proc.stdout is not None
    watchdog = threading.Event()

    def _tick() -> None:
        while not watchdog.is_set():
            if proc.poll() is not None:
                return
            if cancel and cancel():
                proc.kill()
                return
            watchdog.wait(0.5)

    killer = threading.Thread(target=_tick, daemon=True)
    killer.start()
    try:
        for raw in proc.stdout:
            line = raw.strip()
            if cancel and cancel():
                proc.kill()
                raise Cancelled()
            if not line or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key == "out_time_us" or key == "out_time_ms":
                try:
                    secs = int(val) / 1_000_000.0
                except ValueError:
                    continue
                if duration > 0 and on_progress:
                    on_progress(min(0.99, secs / duration))
            elif key == "progress" and val == "end":
                if on_progress:
                    on_progress(1.0)
        proc.wait(timeout=30)
    finally:
        watchdog.set()
        killer.join(timeout=2)
