from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    ALIGNING = "aligning"
    RENDERING = "rendering"
    UPLOADING = "uploading"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


TERMINAL = {Status.DONE, Status.CANCELLED, Status.FAILED}

STATUS_LABELS: dict[str, str] = {
    "queued": "Queued",
    "downloading": "Downloading",
    "aligning": "Timing",
    "rendering": "Rendering",
    "uploading": "Uploading",
    "done": "Done",
    "cancelled": "Cancelled",
    "failed": "Failed",
}

TRANSITIONS: dict[Status, set[Status]] = {
    Status.QUEUED: {Status.DOWNLOADING, Status.CANCELLED, Status.FAILED},
    Status.DOWNLOADING: {Status.ALIGNING, Status.CANCELLED, Status.FAILED},
    Status.ALIGNING: {Status.RENDERING, Status.CANCELLED, Status.FAILED},
    Status.RENDERING: {Status.UPLOADING, Status.DONE, Status.CANCELLED, Status.FAILED},
    Status.UPLOADING: {Status.DONE, Status.CANCELLED, Status.FAILED},
    Status.DONE: set(),
    Status.CANCELLED: {Status.QUEUED},
    Status.FAILED: {Status.QUEUED},
}


@dataclass
class Request:
    id: int
    video_id: str
    comment_id: str
    commenter: str
    artist: str
    title: str
    pitch: float = 0.0
    status: Status = Status.QUEUED
    progress: float = 0.0
    error: str = ""
    output_path: str = ""
    yt_video_id: str = ""
    query: str = ""
    bg_preset: str = ""
    created_at: int = 0
    updated_at: int = 0

    @property
    def display_name(self) -> str:
        if self.artist:
            return f"{self.artist} - {self.title}"
        return self.title


@dataclass
class ParsedRequest:
    artist: str
    title: str
    pitch: float = 0.0
    bg_preset: str = ""
    raw: str = ""
    extras: dict = field(default_factory=dict)
