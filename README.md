# YtLyrics

**Lyrics video factory for YouTube.** It watches your channel's comments for
`!lyrics` requests, fetches the track, times the lyrics, renders a scrolling
lyrics video over an animated background, and uploads it back to your channel —
all from one desktop app.

> Powered by Vi3ecode.com

## Features

- **Comment monitor** — picks up `!lyrics Artist - Title` requests from the
  newest upload on your channel (or a target video ID), with `pitch` and
  background extras
- **Manual queue** — add tracks by hand from the dashboard
- **Lyrics timing** — synced lyrics from LRCLIB first, otherwise
  faster-whisper word-level alignment
- **Audio** — downloads via yt-dlp, pitch shift with rubberband (or
  `asetrate`+`atempo` fallback)
- **Render** — ASS scrolling lyrics (`\move`) over animated gradient/smoke
  backgrounds with particle/bokeh overlays, 1080p/30fps by default
- **Upload** — straight to YouTube via OAuth, with comment reply to the
  requester (privacy configurable, defaults to `private`)
- **Glass UI** — black-and-white monochrome, animated background, page
  transitions, live log console, full cancel/retry on every job
- **Crash recovery** — interrupted jobs requeue automatically on next start

## Requirements

- Python 3.12
- ffmpeg (the app auto-resolves `static-ffmpeg`, no system install needed)
- A Google Cloud project with **YouTube Data API v3** enabled (for upload)

## Install

```bash
git clone https://github.com/kagan-u/YTLyrics.git
cd YTLyrics
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Setup

1. Open **Settings** in the app.
2. Paste your Google Cloud **OAuth Client ID** and **Client Secret**
   (type: Desktop app, scopes: `youtube.upload` + `youtube`).
3. Click **Connect with Google** and approve access.
4. Enable *Automatically pick up lyrics requests from comments* (target video
   ID can stay empty → newest upload on the channel).
5. Optionally set upload privacy, title/description templates, resolution,
   fps, font, scroll speed, and background preset
   (`aurora`, `sunset`, `ocean`, `mono`, `violet`, `emerald`).

Then comment on your own latest video:

```
!lyrics Adele - Easy On Me
!lyrics Daft Punk - Around the World pitch -2 bg sunset
```

Output lands in `~/.ytlyrics/output/`; config in `~/.ytlyrics/config.json`.

> **Quota note:** each upload costs 1600 units against the default
> 10,000/day YouTube API quota — about **6 videos per day** without a quota
> increase request.

### Troubleshooting

- **`Error 401: invalid_client` / "The OAuth client was not found"** —
  the credentials are wrong. In Google Cloud → *Credentials*, create the
  OAuth client with application type **Desktop app** (not *Web
  application*), then copy the exact **Client ID**
  (ends with `.apps.googleusercontent.com`) and its **Client Secret** into
  Settings. A deleted/re-created client makes old credentials invalid too.
- **Browser didn't open** — the authorization link is printed in the app's
  log console (`Authorize: https://accounts.google.com/...`); open it
  manually.
- **`redirect_uri_mismatch`** — you used a *Web application* client. Use
  *Desktop app* instead.
- **`access_denied`** — you cancelled the Google consent screen; retry.

## Prebuilt downloads

Every push to `main` builds installers via GitHub Actions
(**Actions → build → Artifacts**):

| Platform | Artifacts |
|---|---|
| Windows | `YtLyrics.exe` (portable) + `YtLyrics.msi` (installer) |
| macOS | `YtLyrics.app` + `YtLyrics.dmg` |
| Linux | `YtLyrics.AppImage` (double-click to run) + `YtLyrics-linux-x86_64.tar.gz` |

First run on a machine without network will download the static ffmpeg
binaries and the whisper model (~150 MB for `base`).

## Development

```bash
ruff check ytlyrics/ scripts/ tests/   # lint
QT_QPA_PLATFORM=offscreen python -m pytest -q
python scripts/smoke_render.py         # end-to-end render (network)
python scripts/screenshot_ui.py        # offscreen UI screenshots -> .shots/
python scripts/gen_icon.py             # regenerate packaging/icons
pyinstaller --noconfirm YtLyrics.spec  # local build
```

### Layout

```
ytlyrics/core/     monitor, fetch, lyrics timing, ASS, render, upload, worker
ytlyrics/ui/       PySide6 glass interface (queue, settings, logs)
packaging/         icons, WiX MSI template, Linux AppImage files
.github/workflows  lint + tests + 3-platform build matrix
```

## Pipeline

```
comment → queued → downloading → aligning → rendering → uploading → done
                 (cancel/retry available at every stage)
```
