from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .ass import build_ass
from .config import OUTPUT_DIR, TOKEN_PATH, WORK_DIR, Config
from .db import Database
from .errors import Cancelled, FetchError, RenderError
from .fetch import apply_pitch, download_audio, ffprobe_duration, get_lyrics
from .models import Status
from .monitor import CommentMonitor
from .render import render_video
from .youtube import load_credentials, upload_video

log = logging.getLogger(__name__)


def _sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:120] or "lyrics_video"


def _fill_template(tpl: str, **kw: str) -> str:
    try:
        return tpl.format(**kw)
    except (KeyError, IndexError, ValueError):
        return tpl


class Worker(QObject):
    log_message = Signal(str, str)      # message, level
    queue_changed = Signal()
    auth_needed = Signal()
    auth_ok = Signal(str)               # channel title
    monitor_ticked = Signal(str)        # status text

    def __init__(self, cfg_provider: Callable[[], Config], db: Database) -> None:
        super().__init__()
        self._cfg_provider = cfg_provider
        self.db = db
        self._stop = threading.Event()
        self._cancel: threading.Event | None = None
        self._current_job: int | None = None
        self._creds = None
        self._creds_checked_at = 0.0
        self._shutdown = False

    # ------------------------------------------------------------ control
    def stop(self) -> None:
        self._shutdown = True
        self._stop.set()
        if self._cancel:
            self._cancel.set()

    def request_cancel(self, job_id: int) -> bool:
        if self._current_job == job_id and self._cancel is not None:
            self._cancel.set()
            self.emit_log(f"Cancelling request #{job_id}...", "info")
            return True
        ok = self.db.cancel(job_id)
        if ok:
            self.emit_log(f"Request #{job_id} cancelled", "info")
            self._emit_safe(self.queue_changed)
        return ok

    def emit_log(self, msg: str, level: str = "info") -> None:
        try:
            self.log_message.emit(msg, level)
        except RuntimeError:
            pass  # shutting down

    def _emit_safe(self, signal: Signal, *args) -> None:
        try:
            signal.emit(*args)
        except RuntimeError:
            pass

    # ------------------------------------------------------------ main loop
    def run(self) -> None:
        recovered = self.db.recover_stale()
        if recovered:
            self.emit_log(
                f"Recovered {recovered} interrupted request(s)", "warn"
            )
        self.emit_log("Worker started", "ok")
        next_poll = 0.0
        while not self._stop.is_set():
            cfg = self._cfg_provider()
            try:
                if cfg.monitor_enabled:
                    now = time.time()
                    if now >= next_poll:
                        next_poll = now + max(10, int(cfg.poll_interval))
                        self._poll_comments(cfg)
                job = self.db.claim_next()
                if job:
                    self._emit_safe(self.queue_changed)
                    self._process(job["id"])
                    next_poll = 0.0
                    continue
            except Exception as exc:
                self.emit_log(f"Worker error: {exc}", "error")
                log.exception("worker loop error")
            self._stop.wait(0.8)
        self.emit_log("Worker stopped", "warn")

    # ------------------------------------------------------------ monitor
    def _ensure_creds(self, cfg: Config):
        now = time.time()
        if self._creds is not None and self._creds.valid:
            return self._creds
        if now - self._creds_checked_at < 15 and self._creds is not None:
            return self._creds if self._creds.valid else None
        self._creds_checked_at = now
        self._creds = load_credentials(TOKEN_PATH)
        return self._creds

    def _poll_comments(self, cfg: Config) -> None:
        creds = self._ensure_creds(cfg)
        if creds is None:
            if cfg.client_id:
                self._emit_safe(self.auth_needed)
            return
        try:
            monitor = CommentMonitor(
                creds,
                video_id=cfg.api_video_id,
                command=cfg.request_command,
                max_results=cfg.monitor_poll_count,
                is_seen=self.db.has_comment_seen,
                mark_seen=self.db.mark_comment_seen,
            )
            found = monitor.fetch_new_requests()
        except Exception as exc:  # noqa: BLE001
            self.emit_log(f"Comment scan error: {exc}", "warn")
            return
        added = 0
        for comment_id, author, parsed in found:
            req_id = self.db.add_request(
                parsed.artist,
                parsed.title,
                video_id=cfg.api_video_id,
                comment_id=comment_id,
                commenter=author,
                pitch=parsed.pitch or cfg.default_pitch,
                bg_preset=parsed.bg_preset,
                query=f"{parsed.artist} {parsed.title}".strip(),
            )
            if req_id:
                added += 1
                self.emit_log(
                    f"New request #{req_id}: {parsed.artist or '?'} - {parsed.title}"
                    f" (@{author})", "ok"
                )
        if added:
            self._emit_safe(self.queue_changed)
        self._emit_safe(self.monitor_ticked, time.strftime("%H:%M:%S"))

    # ------------------------------------------------------------ pipeline
    def _process(self, job_id: int) -> None:
        cfg = self._cfg_provider()
        job = self.db.get_request(job_id)
        if not job or job["status"] == Status.CANCELLED.value:
            return
        cancel = threading.Event()
        self._cancel = cancel
        self._current_job = job_id
        artist = job["artist"]
        title = job["title"]
        pitch = float(job["pitch"] or cfg.default_pitch)
        preset = job["bg_preset"] or cfg.bg_preset
        workdir = WORK_DIR / f"job_{job_id}"
        workdir.mkdir(parents=True, exist_ok=True)
        self.emit_log(f"Processing #{job_id}: {artist + ' - ' if artist else ''}{title}",
                      "info")
        self._emit_safe(self.queue_changed)

        output_path = ""
        yt_id = ""
        try:
            # stage 1: download + pitch --------------------------------
            query = (
                f"{artist} - {title} official audio" if artist
                else f"{title} official audio"
            )
            audio_raw, meta = download_audio(
                query, workdir,
                on_progress=lambda p: self.db.set_progress(job_id, p * 0.30),
                cancel=cancel.is_set,
            )
            if cancel.is_set():
                raise Cancelled()
            audio = workdir / "prepared.m4a"
            self.emit_log(f"Audio ready: {meta.get('title', '')}", "info")
            apply_pitch(audio_raw, audio, pitch, cancel=cancel.is_set)
            if cancel.is_set():
                raise Cancelled()
            self.db.set_progress(job_id, 0.32)

            # stage 2: lyrics + timing --------------------------------
            if not self.db.set_status(job_id, Status.ALIGNING):
                raise Cancelled()
            lines = get_lyrics(
                artist, title, audio,
                language=cfg.align_language,
                model_size=cfg.whisper_model,
                cancel=cancel.is_set,
                on_progress=lambda p: self.db.set_progress(job_id, 0.32 + p * 0.18),
            )
            if cancel.is_set():
                raise Cancelled()
            duration = ffprobe_duration(audio)
            self.emit_log(f"Lyrics timed: {len(lines)} lines", "ok")

            # stage 3: render -----------------------------------------
            if not self.db.set_status(job_id, Status.RENDERING):
                raise Cancelled()
            ass_path = build_ass(lines, workdir / "lyrics.ass", cfg)
            w, h = (int(x) for x in cfg.resolution.lower().split("x"))
            name = _sanitize(f"{artist} - {title} (Lyrics)" if artist
                             else f"{title} (Lyrics)")
            output_path = str(OUTPUT_DIR / f"{name}_{job_id}.mp4")
            render_video(
                ass_path=ass_path,
                audio_path=audio,
                out_path=Path(output_path),
                workdir=workdir,
                preset=preset,
                duration=duration,
                width=w, height=h, fps=cfg.fps,
                cancel=cancel.is_set,
                on_progress=lambda p: self.db.set_progress(job_id, 0.50 + p * 0.40),
            )
            self.emit_log(f"Render complete: {Path(output_path).name}", "ok")

            # stage 4: upload -----------------------------------------
            do_upload = cfg.upload_enabled and not cfg.dry_run
            if do_upload:
                creds = self._ensure_creds(cfg)
                if creds is None:
                    self._emit_safe(self.auth_needed)
                    raise FetchError("YouTube account not connected — video file saved, "
                                     "upload will be pending")
                if not self.db.set_status(job_id, Status.UPLOADING):
                    raise Cancelled()
                track = f"{artist} - {title}" if artist else title
                title_txt = _fill_template(cfg.title_template, track=track,
                                           artist=artist or "", title=title)
                desc = _fill_template(
                    cfg.description_template, track=track, artist=artist or "",
                    title=title,
                    artist_tag=(artist or "lyrics").replace(" ", ""),
                )
                tags = [t for t in [
                    f"{artist} {title} lyrics".strip(), "lyrics", "lyrics video",
                    artist or None, title,
                ] if t][:30]
                yt_id = upload_video(
                    creds, Path(output_path),
                    title=title_txt, description=desc, tags=tags,
                    privacy=cfg.privacy,
                    on_progress=lambda p: self.db.set_progress(
                        job_id, 0.90 + p * 0.10),
                    cancel=cancel.is_set,
                )
                self.emit_log(f"Upload complete: https://youtu.be/{yt_id}", "ok")

            if cancel.is_set():
                raise Cancelled()
            self.db.set_result(job_id, output_path=output_path,
                               yt_video_id=yt_id, status=Status.DONE)
            self.emit_log(f"Completed #{job_id}", "ok")

        except Cancelled:
            if self._shutdown:
                self.db.recover_stale()
                self.emit_log(f"Requeued #{job_id} (worker stopped)", "warn")
            else:
                self.db.set_result(job_id, status=Status.CANCELLED,
                                   output_path=output_path)
                self.emit_log(f"Cancelled #{job_id}", "warn")
        except (FetchError, RenderError) as exc:
            self.db.set_result(job_id, status=Status.FAILED, error=str(exc),
                               output_path=output_path)
            self.emit_log(f"Error #{job_id}: {exc}", "error")
        except Exception as exc:
            log.exception("job %s failed", job_id)
            self.db.set_result(job_id, status=Status.FAILED, error=str(exc)[:400],
                               output_path=output_path)
            self.emit_log(f"Error #{job_id}: {exc}", "error")
        finally:
            self._cancel = None
            self._current_job = None
            for leftover in workdir.glob("audio.*"):
                try:
                    leftover.unlink(missing_ok=True)
                except OSError:
                    pass
            self._emit_safe(self.queue_changed)
