from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from google.auth.transport.requests import Request as AuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .errors import Cancelled

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

ProgressFn = Callable[[float], None]
CancelFn = Callable[[], bool]


def load_credentials(token_path: Path) -> Credentials | None:
    if not token_path.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except Exception as exc:  # noqa: BLE001
        log.warning("token unreadable: %s", exc)
        return None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(AuthRequest())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            log.warning("token refresh failed: %s", exc)
            return None
    return creds if creds and creds.valid else None


def run_auth_flow(client_id: str, client_secret: str, token_path: Path) -> Credentials:
    if not client_id or not client_secret:
        raise RuntimeError("Client ID and Client Secret required")
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        authorization_prompt_message=(
            "Open this link in your browser to authorize:\n{url}"
        ),
        success_message="Authorization complete. You can close this tab.",
    )
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def channel_title(creds: Credentials) -> str:
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    resp = yt.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items") or []
    if not items:
        return ""
    return items[0]["snippet"]["title"]


def upload_video(
    creds: Credentials,
    file_path: Path,
    *,
    title: str,
    description: str,
    tags: list[str],
    privacy: str = "private",
    category: str = "10",
    on_progress: ProgressFn | None = None,
    cancel: CancelFn | None = None,
) -> str:
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:30],
            "categoryId": category,
        },
        "status": {
            "privacyStatus": privacy if privacy in
            ("private", "unlisted", "public") else "private",
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(
        str(file_path), chunksize=8 * 1024 * 1024, resumable=True,
        mimetype="video/mp4",
    )
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        if cancel and cancel():
            try:
                request.cancel()
            except Exception as exc:  # noqa: BLE001
                log.debug("upload cancel edilemedi: %s", exc)
            raise Cancelled()
        status, response = request.next_chunk()
        if status and on_progress:
            on_progress(min(0.99, float(status.progress())))
    if on_progress:
        on_progress(1.0)
    video_id = response.get("id", "")
    if not video_id:
        raise RuntimeError("Upload finished but no video id returned")
    return video_id


def reply_to_comment(creds: Credentials, comment_id: str, text: str) -> bool:
    try:
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        yt.comments().insert(
            part="snippet",
            body={"snippet": {"parentId": comment_id, "textOriginal": text[:500]}},
        ).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("comment reply failed: %s", exc)
        return False
