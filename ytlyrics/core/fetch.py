from __future__ import annotations

import logging
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import requests
import yt_dlp

from .errors import Cancelled, FetchError
from .ffmpeg_util import ffmpeg_path, ffprobe_path, run

log = logging.getLogger(__name__)

LRCLIB = "https://lrclib.net/api"
ProgressFn = Callable[[float], None]
CancelFn = Callable[[], bool]


def _check(cancel: CancelFn | None) -> None:
    if cancel and cancel():
        raise Cancelled()


def ffprobe_duration(path: Path) -> float:
    try:
        probe = ffprobe_path()
    except RuntimeError:
        probe = ""
    if probe:
        try:
            out = run(
                [probe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(path)],
                timeout=30,
            )
            if out.returncode == 0 and out.stdout.strip():
                return float(out.stdout.strip())
        except (ValueError, subprocess.TimeoutExpired):
            pass
    # fallback: parse ffmpeg banner
    try:
        ffmpeg = ffmpeg_path()
    except RuntimeError:
        ffmpeg = ""
    if ffmpeg:
        out = run([ffmpeg, "-i", str(path)], timeout=30)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out.stderr)
        if m:
            h, mi, s = m.groups()
            return int(h) * 3600 + int(mi) * 60 + float(s)
    raise FetchError(f"Could not read duration: {path}")


def download_audio(
    query: str,
    workdir: Path,
    *,
    on_progress: ProgressFn | None = None,
    cancel: CancelFn | None = None,
) -> tuple[Path, dict]:
    workdir.mkdir(parents=True, exist_ok=True)
    for old in workdir.glob("audio.*"):
        old.unlink(missing_ok=True)

    def hook(d: dict) -> None:
        _check(cancel)
        if d.get("status") == "downloading" and on_progress:
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                on_progress(min(0.99, done / total))

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "audio.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [hook],
        "socket_timeout": 30,
        "retries": 3,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
    except Cancelled:
        raise
    except Exception as exc:
        if cancel and cancel():
            raise Cancelled() from exc
        raise FetchError(f"Download failed: {exc}") from exc

    entries = (info or {}).get("entries") or []
    if not entries:
        raise FetchError(f"Song not found: {query}")
    entry = entries[0]
    filepath = None
    req = entry.get("requested_downloads") or []
    if req:
        filepath = req[0].get("filepath")
    if not filepath:
        filepath = ydl.prepare_filename(entry)
    path = Path(filepath)
    if not path.exists():
        raise FetchError(f"Downloaded file missing: {path}")
    meta = {
        "title": entry.get("title") or "",
        "uploader": entry.get("uploader") or entry.get("channel") or "",
        "duration": entry.get("duration") or 0,
        "webpage_url": entry.get("webpage_url") or "",
        "channel": entry.get("channel") or "",
    }
    if on_progress:
        on_progress(1.0)
    return path, meta


_RUBBERBAND_OK: bool | None = None


def has_rubberband() -> bool:
    global _RUBBERBAND_OK
    if _RUBBERBAND_OK is None:
        ok = False
        try:
            ffmpeg = ffmpeg_path()
            out = run([ffmpeg, "-hide_banner", "-filters"], timeout=30)
            ok = " rubberband " in out.stdout
        except (RuntimeError, subprocess.TimeoutExpired):
            ok = False
        _RUBBERBAND_OK = ok
    return _RUBBERBAND_OK


def pitch_filter(semitones: float) -> str | None:
    if abs(semitones) < 1e-6:
        return None
    factor = 2.0 ** (semitones / 12.0)
    if has_rubberband():
        return f"rubberband=pitch={factor:.6f}:tempo=1"
    return f"asetrate=44100*{factor:.6f},aresample=44100,atempo={1 / factor:.6f}"


def apply_pitch(
    src: Path,
    dst: Path,
    semitones: float,
    *,
    cancel: CancelFn | None = None,
) -> Path:
    if abs(semitones) < 1e-6:
        if src != dst:
            shutil.copyfile(src, dst)
        return dst
    af = pitch_filter(semitones)
    if af is None:
        shutil.copyfile(src, dst)
        return dst
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-af", af, "-vn",
        "-c:a", "aac", "-b:a", "192k", str(dst),
    ]
    _check(cancel)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        while True:
            try:
                _, err = proc.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if cancel and cancel():
                    proc.kill()
                    proc.wait(timeout=10)
                    raise Cancelled()
                continue
    except Cancelled:
        raise
    except Exception as exc:
        proc.kill()
        raise FetchError(f"Pitch conversion failed: {exc}") from exc
    if proc.returncode != 0:
        raise FetchError(f"Pitch conversion failed: {err.decode(errors='ignore')[-400:]}")
    return dst


# ---------------------------------------------------------------- lyrics

def _http_get(url: str, **kwargs) -> requests.Response:
    resp = requests.get(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp


def fetch_lrclib_synced(artist: str, title: str) -> str | None:
    try:
        r = _http_get(
            f"{LRCLIB}/search",
            params={"track_name": title, "artist_name": artist} if artist
            else {"q": title},
        )
        items = r.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("LRCLIB search failed: %s", exc)
        return None
    if not isinstance(items, list) or not items:
        return None
    for item in items:
        synced = item.get("syncedLyrics")
        if synced and item.get("instrumental") is not True:
            return synced
    for item in items:
        plain = item.get("plainLyrics")
        if plain:
            return plain
    return None


def fetch_lyrics_ovh(artist: str, title: str) -> str | None:
    if not artist:
        return None
    try:
        r = requests.get(
            f"https://api.lyrics.ovh/v1/{requests.utils.quote(artist)}"
            f"/{requests.utils.quote(title)}",
            timeout=30,
        )
    except requests.RequestException as exc:
        log.warning("lyrics.ovh failed: %s", exc)
        return None
    if r.status_code != 200:
        return None
    try:
        return r.json().get("lyrics") or None
    except ValueError:
        return None


_LRC_LINE = re.compile(r"^\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]\s*(.*)$")


def parse_lrc(text: str) -> list[tuple[float, str]]:
    entries: list[tuple[float, str]] = []
    m_off = re.search(r"\[offset:([+-]?\d+)\]", text, re.IGNORECASE)
    offset_ms = float(m_off.group(1)) if m_off else 0.0
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = _LRC_LINE.match(raw)
        if not m:
            continue
        mm, ss, frac, lyric = m.groups()
        frac_val = 0.0
        if frac:
            frac_val = int(frac) / (10 ** len(frac))
        t = int(mm) * 60 + int(ss) + frac_val
        lyric = lyric.strip()
        if lyric and lyric not in {"[Instrumental]", "♪"}:
            entries.append((t + offset_ms / 1000.0, lyric))
    entries.sort(key=lambda x: x[0])
    return entries


def _norm_tokens(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\sçğıöşüâîûÇĞİÖŞÜ]", " ", text, flags=re.UNICODE)
    return [t for t in text.split() if t]


def _token_match(a: str, b: str) -> bool:
    if a == b:
        return True
    return len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a))


def align_lines(
    lines: list[str], words: list[tuple[float, float, str]], duration: float
) -> list[tuple[float, float, str]]:
    """Align plain lyric lines to timed words; interpolate the misses."""
    n = len(lines)
    if n == 0:
        return []
    result: list[tuple[float | None, float | None, str]] = [
        (None, None, line) for line in lines
    ]
    if not words:
        return _spread_evenly(lines, duration)

    wi = 0
    matched = 0
    for idx, line in enumerate(lines):
        toks = _norm_tokens(line)
        if not toks:
            continue
        best = None
        limit = min(len(words), wi + 40)
        for start in range(wi, limit):
            hit = 0
            for k, tok in enumerate(toks):
                if start + k < len(words) and _token_match(tok, words[start + k][2]):
                    hit += 1
            score = hit / len(toks)
            if best is None or score > best[0]:
                best = (score, start)
            if best and best[0] >= 0.999:
                break
        if best and best[0] >= 0.5:
            s = best[1]
            e = min(len(words) - 1, s + len(toks) - 1)
            result[idx] = (words[s][0], words[e][1], line)
            matched += 1
            wi = e + 1

    if matched < max(1, n * 0.3):
        return _spread_evenly(lines, duration)

    # fill gaps by interpolation
    last_end = 0.0
    for i in range(n):
        start, end, text = result[i]
        if start is None or end is None:
            nxt = next(
                (result[j] for j in range(i + 1, n)
                 if result[j][0] is not None),
                None,
            )
            nxt_start = nxt[0] if nxt else duration
            fill_start = last_end
            fill_end = max(fill_start + 0.4, nxt_start - 0.05)
            fill_end = min(fill_end, duration)
            result[i] = (fill_start, fill_end, text)
        last_end = result[i][1] or last_end
    if result[-1][1] is not None and result[-1][1] < duration - 1.0:
        # keep final line visible a bit
        pass
    return [(float(s), float(e), t) for s, e, t in result]  # type: ignore[arg-type]


def _spread_evenly(lines: list[str], duration: float) -> list[tuple[float, float, str]]:
    if not lines:
        return []
    step = duration / len(lines)
    out = []
    for i, line in enumerate(lines):
        start = max(0.0, i * step)
        end = duration if i == len(lines) - 1 else (i + 1) * step
        out.append((start, end, line))
    return out


def clean_lyric_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]\s*", "", line).strip()
        if not line:
            continue
        if re.match(r"^\[?(verse|chorus|bridge|outro|intro|hook|pre-chorus)",
                    line, re.IGNORECASE):
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        if line in {"/", "x2", "x3", "*"} or re.fullmatch(r"x\d", line, re.IGNORECASE):
            continue
        if line.startswith(("©", "℗", "Uploaded by", "Last updated")):
            continue
        out.append(line)
    return out


def get_lyrics(
    artist: str,
    title: str,
    audio_path: Path,
    *,
    language: str = "",
    model_size: str = "base",
    cancel: CancelFn | None = None,
    on_progress: ProgressFn | None = None,
) -> list[tuple[float, float, str]]:
    """Returns timed lines: (start, end, text)."""
    _check(cancel)
    synced = fetch_lrclib_synced(artist, title)
    if synced:
        timed = parse_lrc(synced)
        if len(timed) >= 3:
            duration = ffprobe_duration(audio_path)
            filled = _fill_lrc_gaps(timed, duration)
            if on_progress:
                on_progress(1.0)
            return filled

    plain = synced if synced else fetch_lyrics_ovh(artist, title)
    lines = clean_lyric_lines(plain) if plain else []
    if len(lines) >= 3 and on_progress:
        on_progress(0.15)
    words = _transcribe_words(
        audio_path, language=language, model_size=model_size, cancel=cancel,
        on_progress=on_progress,
    )
    duration = ffprobe_duration(audio_path)
    _check(cancel)
    if not lines:
        # build lines straight from whisper segments
        if not words:
            raise FetchError("Lyrics not found and transcription is empty")
        lines = _segments_to_lines(words, duration)
    result = align_lines(lines, words, duration)
    if on_progress:
        on_progress(1.0)
    return result


def _fill_lrc_gaps(
    timed: list[tuple[float, str]], duration: float
) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    for i, (start, text) in enumerate(timed):
        if i + 1 < len(timed):
            nxt = timed[i + 1][0]
            end = max(start + 0.4, nxt - 0.05)
        else:
            end = min(duration, max(start + 2.5, start + 0.5))
            end = min(end, duration)
        out.append((start, end, text))
    return out


def _segments_to_lines(words: list[tuple[float, float, str]],
                       duration: float) -> list[str]:
    """Group timed words into lyric-sized lines (~8 words / pauses)."""
    lines: list[str] = []
    buf: list[str] = []
    for s, e, w in words:
        buf.append(w)
        if len(buf) >= 8:
            lines.append(" ".join(buf))
            buf = []
    if buf:
        lines.append(" ".join(buf))
    return lines or [""]


def _transcribe_words(
    audio_path: Path,
    *,
    language: str,
    model_size: str,
    cancel: CancelFn | None,
    on_progress: ProgressFn | None,
) -> list[tuple[float, float, str]]:
    _check(cancel)
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise FetchError("faster-whisper is not installed") from exc
    try:
        model = WhisperModel(
            model_size, device="cpu", compute_type="int8"
        )
    except Exception as exc:
        raise FetchError(f"Whisper model failed to load: {exc}") from exc

    segments, _info = model.transcribe(
        str(audio_path),
        language=language or None,
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )
    words: list[tuple[float, float, str]] = []
    for seg in segments:
        _check(cancel)
        for w in seg.words or []:
            token = (w.word or "").strip()
            if token:
                words.append((float(w.start), float(w.end), token))
        if on_progress:
            on_progress(min(0.95, (seg.end or 0) / 60.0))
    return words
