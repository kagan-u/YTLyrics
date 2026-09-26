from __future__ import annotations

from pathlib import Path

from .config import Config


def _ts(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(
    lines: list[tuple[float, float, str]],
    out_path: Path,
    cfg: Config,
    *,
    width: int = 1920,
    height: int = 1080,
) -> Path:
    """Classic scrolling lyrics: constant vertical speed, center anchored."""
    speed = max(5.0, float(cfg.scroll_speed))
    font_size = int(cfg.font_size)
    yc = height / 2.0 - font_size * 1.15 / 2.0  # \an8 => y is box top

    header = f"""[Script Info]
Title: YtLyrics
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyrics,{cfg.font_name},{font_size},&H00FFFFFF,&H00B0FFFFFF,&H00141420,&H78000000,-1,0,0,0,100,100,0,0,1,3,2,8,300,300,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    hold = 0.9
    fade_in, fade_out = 250, 420
    for start, end, text in lines:
        text = (text or "").strip()
        if not text:
            continue
        text = text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
        win_end = end + hold
        t_mid = (start + end) / 2.0
        y0 = yc - speed * (start - t_mid)
        y1 = yc - speed * (win_end - t_mid)
        # enter from below the visible area, never start above center
        y0 = max(yc, min(height - 40.0, y0))
        y1 = min(y1, y0)
        ev = (
            f"Dialogue: 0,{_ts(start)},{_ts(win_end)},Lyrics,,0,0,0,,"
            f"{{\\fad({fade_in},{fade_out})\\an8\\move(960,{y0:.1f},960,{y1:.1f})}}"
            f"{text}"
        )
        events.append(ev)

    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path
