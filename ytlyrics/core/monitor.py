from __future__ import annotations

import logging
import re
from collections.abc import Callable

from googleapiclient.discovery import build

from .models import ParsedRequest

log = logging.getLogger(__name__)

_SEPARATORS = r"\s*[-–—:|]\s*"
_PITCH_RE = re.compile(
    r"(?:pitch|key)\s*([+-]?\d+(?:\.\d+)?)\s*(?:st|semitones?|semi)?\b", re.IGNORECASE
)
_BG_RE = re.compile(r"(?:bg|background)\s*[:=]?\s*([a-z]+)", re.IGNORECASE)
_ARTIST_RE = re.compile(r"^\s*(.{1,60}?)\s+by\s+(.{1,80})$", re.IGNORECASE)


def _clean_line(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(".,;:!?\"'`")
    return text


def parse_request(text: str, command: str = "!lyrics") -> ParsedRequest | None:
    if not text:
        return None
    body = text.strip()
    cmd = command.strip().lower()
    if cmd:
        idx = body.lower().find(cmd)
        if idx < 0:
            return None
        body = body[idx + len(cmd):].strip()
    if not body:
        return None

    pitch = 0.0
    m = _PITCH_RE.search(body)
    if m:
        try:
            pitch = float(m.group(1))
        except ValueError:
            pitch = 0.0
        body = _PITCH_RE.sub("", body)

    bg = ""
    m = _BG_RE.search(body)
    if m:
        bg = m.group(1).lower()
        body = _BG_RE.sub("", body)

    body = _clean_line(body)
    if not body:
        return None

    artist, title = "", ""
    sep_parts = re.split(_SEPARATORS, body, maxsplit=1)
    if len(sep_parts) == 2 and all(p.strip() for p in sep_parts):
        artist, title = _clean_line(sep_parts[0]), _clean_line(sep_parts[1])
    else:
        m = _ARTIST_RE.match(body)
        if m:
            title, artist = _clean_line(m.group(1)), _clean_line(m.group(2))
        else:
            title = body

    if not title or len(title) > 150 or len(artist) > 80:
        return None
    return ParsedRequest(
        artist=artist,
        title=title,
        pitch=pitch,
        bg_preset=bg,
        raw=text,
    )


class CommentMonitor:
    """Polls comments of the newest uploaded video and reports fresh requests."""

    def __init__(
        self,
        creds,
        *,
        video_id: str = "",
        command: str = "!lyrics",
        max_results: int = 100,
        is_seen: Callable[[str], bool] | None = None,
        mark_seen: Callable[[str], bool] | None = None,
    ) -> None:
        self._creds = creds
        self._fixed_video_id = video_id
        self._command = command
        self._max_results = max_results
        self._is_seen = is_seen or (lambda _cid: False)
        self._mark_seen = mark_seen
        self._yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    def latest_video_id(self) -> str:
        if self._fixed_video_id:
            return self._fixed_video_id
        ch = self._yt.channels().list(
            part="contentDetails", mine=True
        ).execute()
        items = ch.get("items") or []
        if not items:
            raise RuntimeError("Channel not found (mine=true returned empty)")
        uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = self._yt.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=1
        ).execute()
        pl_items = pl.get("items") or []
        if not pl_items:
            raise RuntimeError("Channel has no videos")
        return pl_items[0]["contentDetails"]["videoId"]

    def fetch_new_requests(self) -> list[tuple[str, str, ParsedRequest]]:
        """Returns (comment_id, commenter, parsed) for fresh command comments."""
        video_id = self.latest_video_id()
        resp = (
            self._yt.commentThreads()
            .list(
                part="snippet",
                videoId=video_id,
                order="time",
                textFormat="plainText",
                maxResults=min(100, self._max_results),
            )
            .execute()
        )
        out: list[tuple[str, str, ParsedRequest]] = []
        for item in resp.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            cid = item["id"]
            text = snippet.get("textDisplay", "") or snippet.get("textOriginal", "")
            author = snippet.get("authorDisplayName", "unknown")
            if self._is_seen(cid):
                continue
            parsed = parse_request(text, self._command)
            if self._mark_seen:
                self._mark_seen(cid)
            if parsed:
                out.append((cid, author, parsed))
        out.reverse()
        return out
