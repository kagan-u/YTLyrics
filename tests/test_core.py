from ytlyrics.core.ass import _ts, build_ass
from ytlyrics.core.config import Config
from ytlyrics.core.fetch import (
    align_lines,
    clean_lyric_lines,
    parse_lrc,
    pitch_filter,
)


def test_ts_format():
    assert _ts(0) == "0:00:00.00"
    assert _ts(61.5) == "0:01:01.50"
    assert _ts(3661.25) == "1:01:01.25"


def test_build_ass_scroll(tmp_path):
    cfg = Config()
    lines = [(0.0, 2.0, "first line"), (2.0, 4.5, "second {line}")]
    out = build_ass(lines, tmp_path / "a.ass", cfg)
    text = out.read_text(encoding="utf-8")
    assert "[Events]" in text
    assert text.count("Dialogue:") == 2
    assert "\\fad(" in text
    assert "\\move(960," in text
    # braces sanitized so libass does not treat them as overrides
    assert "{line}" not in text.split("[Events]")[1]
    assert "(line)" in text


def test_lrc_parse():
    lrc = "[00:12.00]hello world\n[00:15.50]second line\n[offset:500]\n[00:18.00]third"
    parsed = parse_lrc(lrc)
    assert len(parsed) == 3
    assert abs(parsed[0][0] - 12.5) < 1e-6  # offset applied
    assert parsed[1][1] == "second line"


def test_clean_lyric_lines():
    raw = "[Verse 1]\nHello\nWorld\nx2\n[Chorus]\nLa la\n\n"
    lines = clean_lyric_lines(raw)
    assert lines == ["Hello", "World", "La la"]


def test_align_lines_even_fallback():
    lines = ["one", "two", "three", "four"]
    out = align_lines(lines, [], duration=8.0)
    assert len(out) == 4
    assert out[0][0] == 0.0
    assert abs(out[1][0] - 2.0) < 1e-6


def test_align_lines_with_words():
    lines = ["hello world", "second line"]
    words = [
        (0.5, 0.9, "hello"),
        (0.9, 1.3, "world"),
        (3.0, 3.4, "second"),
        (3.4, 3.9, "line"),
    ]
    out = align_lines(lines, words, duration=6.0)
    assert abs(out[0][0] - 0.5) < 1e-6
    assert abs(out[0][1] - 1.3) < 1e-6
    assert abs(out[1][0] - 3.0) < 1e-6


def test_pitch_filter_zero():
    assert pitch_filter(0) is None


def test_pitch_filter_semitone():
    f = pitch_filter(12)
    assert f is not None
    assert "asetrate" in f or "rubberband" in f
