"""End-to-end render smoke test (no network, no GUI).

Usage: .venv/bin/python scripts/smoke_render.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ytlyrics.core.ass import build_ass
from ytlyrics.core.config import Config
from ytlyrics.core.ffmpeg_util import ffmpeg_path, ffprobe_path
from ytlyrics.core.render import render_video


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ytlyrics_smoke_") as td:
        work = Path(td)
        audio = work / "audio.wav"
        # 6.5s sine + a beat-ish modulation
        cmd = [
            ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i",
            "sine=frequency=440:duration=6.5,volume='0.6+0.4*sin(2*PI*2*t)':eval=frame",
            "-c:a", "pcm_s16le", str(audio),
        ]
        subprocess.run(cmd, check=True)

        lines = [
            (0.0, 1.6, "Burada birinci satır kayar"),
            (1.6, 3.2, "Sonra ikinci satır gelir"),
            (3.2, 4.8, "Ve üçüncü satır yukarı çıkar"),
            (4.8, 6.4, "Son satır ekranda kalır"),
        ]
        ass = build_ass(lines, work / "lyrics.ass", Config())
        out = work / "smoke.mp4"
        render_video(
            ass_path=ass,
            audio_path=audio,
            out_path=out,
            workdir=work,
            preset="violet",
            duration=6.5,
            width=1280,
            height=720,
            fps=24,
            sprite_count=5,
        )
        assert out.exists() and out.stat().st_size > 50_000, "output missing/too small"

        probe = subprocess.run(
            [ffprobe_path(), "-v", "error", "-show_entries",
             "format=duration", "-of", "default=nw=1:nk=1", str(out)],
            capture_output=True, text=True, check=True,
        )
        dur = float(probe.stdout.strip())
        assert 5.8 <= dur <= 7.5, f"unexpected duration {dur}"
        print(f"SMOKE OK -> {out} ({out.stat().st_size // 1024} KB, {dur:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
