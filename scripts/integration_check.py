"""Real-data integration check: download -> lyrics -> pitch -> render (no upload).

Usage: .venv/bin/python scripts/integration_check.py "Artist - Title" [pitch]
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ytlyrics.core.ass import build_ass
from ytlyrics.core.config import Config
from ytlyrics.core.fetch import (
    apply_pitch,
    download_audio,
    ffprobe_duration,
    get_lyrics,
)
from ytlyrics.core.render import render_video


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "Rick Astley - Never Gonna Give You Up"
    pitch = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    if " - " in query:
        artist, title = query.split(" - ", 1)
    else:
        artist, title = "", query

    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="ytlyrics_int_") as td:
        work = Path(td)
        print(f"[1/4] download: {query}")
        audio_raw, meta = download_audio(
            f"{artist} - {title} official audio" if artist else f"{title} official audio",
            work,
        )
        print(f"      -> {meta['title']} ({meta['duration']}s)")

        print(f"[2/4] pitch {pitch:+.1f} st")
        audio = work / "prepared.m4a"
        apply_pitch(audio_raw, audio, pitch)

        print("[3/4] lyrics")
        lines = get_lyrics(artist, title, audio, language="", model_size="base")
        print(f"      -> {len(lines)} satır, ilk: {lines[0] if lines else '-'}")

        print("[4/4] render (720p)")
        duration = ffprobe_duration(audio)
        ass = build_ass(lines, work / "lyrics.ass", Config())
        out = work / "int.mp4"
        render_video(
            ass_path=ass, audio_path=audio, out_path=out, workdir=work,
            preset="ocean", duration=duration,
            width=1280, height=720, fps=24, sprite_count=5,
        )
        size_mb = out.stat().st_size / 1_000_000
        print(f"OK -> {out} ({size_mb:.1f} MB, {duration:.1f}s, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
