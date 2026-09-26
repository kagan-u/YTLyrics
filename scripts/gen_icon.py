"""Generate YtLyrics app icons (PNG / ICO / ICNS) into packaging/icons/."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "packaging" / "icons"
S = 1024
RADIUS = 200


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make(size: int = S) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size // 14
    # dark rounded card
    d.rounded_rectangle(
        (m, m, size - m, size - m),
        radius=RADIUS * size // S,
        fill=(8, 8, 8, 255),
        outline=(255, 255, 255, 235),
        width=max(4, size // 42),
    )
    # subtle inner sheen
    sheen = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheen)
    for i in range(size):
        a = int(26 * (1 - i / (size * 0.75)))
        if a > 0:
            sd.line([(0, i), (size, i)], fill=(255, 255, 255, a))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (m, m, size - m, size - m),
        radius=RADIUS * size // S,
        fill=255,
    )
    img = Image.composite(Image.alpha_composite(img, sheen), img, mask)
    d = ImageDraw.Draw(img)
    # bold Y
    f = _font(int(size * 0.52))
    tw = d.textlength("Y", font=f)
    d.text(
        ((size - tw) / 2, size * 0.19),
        "Y",
        font=f,
        fill=(255, 255, 255, 255),
    )
    # caption
    f2 = _font(int(size * 0.075))
    cap = "LYRICS"
    tw2 = d.textlength(cap, font=f2)
    d.text(
        ((size - tw2) / 2, size * 0.74),
        cap,
        font=f2,
        fill=(170, 170, 170, 255),
    )
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    img = make()
    img.resize((256, 256), Image.LANCZOS).save(OUT / "ytlyrics.png")  # linux
    img.save(
        OUT / "YtLyrics.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
               (128, 128), (256, 256)],
    )
    img.save(OUT / "YtLyrics.icns", format="ICNS")
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
