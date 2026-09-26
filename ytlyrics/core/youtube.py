from __future__ import annotations

import logging
import time
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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


def run_auth_flow(
    client_id: str,
    client_secret: str,
    token_path: Path,
    on_url: Callable[[str], None] | None = None,
    timeout: float = 300.0,
) -> Credentials:
    client_id = client_id.strip()
    client_secret = client_secret.strip()
    if not client_id or not client_secret:
        raise RuntimeError("Client ID and Client Secret required")
    if not client_id.endswith(".apps.googleusercontent.com"):
        raise RuntimeError(
            "Invalid Client ID — it must end with "
            "'.apps.googleusercontent.com'. Copy it from Google Cloud "
            "Console → APIs & Services → Credentials → OAuth client ID "
            "(application type: Desktop app)."
        )
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

    got: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/":
                self.send_error(404)
                return
            q = parse_qs(parsed.query)
            if "error" in q:
                got["error"] = q["error"][0]
            elif "code" in q:
                got["code"] = q["code"][0]
                got["state"] = q.get("state", [""])[0]
            body = (
                b'<html><body style="font-family:sans-serif;background:#111;'
                b'color:#eee;text-align:center;padding:60px">'
                b"<h2>Authorization complete</h2>"
                b"<p>You can close this tab and return to YtLyrics.</p>"
                b"</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:  # silence request log
            del args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    flow.redirect_uri = f"http://localhost:{port}"
    auth_url, state = flow.authorization_url(prompt="consent")
    if on_url:
        on_url(auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception as exc:  # noqa: BLE001 - URL is shown in the log anyway
        log.warning("could not open browser: %s", exc)

    deadline = time.monotonic() + timeout
    server.timeout = 5.0
    while not got and time.monotonic() < deadline:
        server.handle_request()
    server.server_close()

    if got.get("error"):
        raise RuntimeError(f"Authorization denied: {got['error']}")
    if not got.get("code"):
        raise RuntimeError(
            "Timed out waiting for authorization — use the link from the log"
        )
    if got.get("state") != state:
        raise RuntimeError("OAuth state mismatch, try again")

    creds = flow.fetch_token(code=got["code"])
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
