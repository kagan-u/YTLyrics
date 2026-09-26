from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .config import SPRITE_DIR

# preset -> gradient colors, smoke tint multiplier, smoke opacity, seed
PRESETS: dict[str, dict] = {
    "violet": {
        "colors": ["0x120b26", "0x2a1458", "0x7b3fa0", "0x1a0f30"],
        "smoke_tint": (1.4, 1.0, 2.2),
        "smoke_opacity": 0.30,
        "seed": 11,
    },
    "aurora": {
        "colors": ["0x04121f", "0x0b3b3b", "0x1e6f5c", "0x0a1f2e"],
        "smoke_tint": (0.7, 1.9, 1.6),
        "smoke_opacity": 0.28,
        "seed": 7,
    },
    "sunset": {
        "colors": ["0x2b0f1e", "0x8c2f39", "0xe06c3a", "0x1c0a14"],
        "smoke_tint": (2.2, 1.0, 0.7),
        "smoke_opacity": 0.26,
        "seed": 23,
    },
    "ocean": {
        "colors": ["0x03142b", "0x0a3d62", "0x1178a8", "0x062033"],
        "smoke_tint": (0.7, 1.2, 2.2),
        "smoke_opacity": 0.30,
        "seed": 5,
    },
    "mono": {
        "colors": ["0x0a0a0a", "0x262626", "0x4d4d4d", "0x111111"],
        "smoke_tint": (1.4, 1.4, 1.5),
        "smoke_opacity": 0.22,
        "seed": 3,
    },
    "emerald": {
        "colors": ["0x031a12", "0x0d4a2f", "0x1f8a54", "0x06251a"],
        "smoke_tint": (0.7, 2.0, 1.2),
        "smoke_opacity": 0.28,
        "seed": 17,
    },
}

SPRITE_ORDER = ("bokeh_a", "bokeh_b", "bokeh_c", "dust")


def ensure_sprites(directory: Path | None = None) -> dict[str, Path]:
    directory = Path(directory or SPRITE_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    def _radial_falloff(size: int, gamma: float, inner: float = 0.0) -> Image.Image:
        base = ImageOps.invert(Image.radial_gradient("L")).resize((size, size))
        lut = []
        for p in range(256):
            v = (p / 255.0) ** gamma
            if inner:
                v = max(0.0, (v - inner) / (1.0 - inner))
            lut.append(int(v * 255))
        return base.point(lut)

    def _save(name: str, size: int, make_alpha) -> None:
        path = directory / name
        if not path.exists():
            img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
            img.putalpha(make_alpha())
            img.save(path)
        out[name.rsplit(".", 1)[0]] = path

    def alpha_a() -> Image.Image:
        return _radial_falloff(256, gamma=3.2)

    def alpha_b() -> Image.Image:
        return _radial_falloff(256, gamma=1.6, inner=0.55).filter(
            ImageFilter.GaussianBlur(6)
        )

    def alpha_c() -> Image.Image:
        a = _radial_falloff(256, gamma=1.2, inner=0.62)
        d = ImageDraw.Draw(a)
        d.ellipse((6, 6, 250, 250), outline=0, width=14)
        return a.filter(ImageFilter.GaussianBlur(4))

    def alpha_dust() -> Image.Image:
        return _radial_falloff(64, gamma=6.0)

    _save("bokeh_a.png", 256, alpha_a)
    _save("bokeh_b.png", 256, alpha_b)
    _save("bokeh_c.png", 256, alpha_c)
    _save("dust.png", 64, alpha_dust)
    return out


def _overlay_expr(rnd: random.Random) -> tuple[str, str]:
    amp_x = rnd.uniform(0.03, 0.09)
    amp_y = rnd.uniform(0.05, 0.14)
    speed = rnd.uniform(0.18, 0.45)
    phase = rnd.uniform(0, 6.28)
    base_x = rnd.uniform(0.06, 0.84)
    base_y = rnd.uniform(0.08, 0.78)
    x = f"(main_w)*({base_x:.3f}+{amp_x:.3f}*sin(t*{speed:.3f}+{phase:.3f}))"
    y = (
        f"(main_h)*({base_y:.3f}+{amp_y:.3f}"
        f"*sin(t*{speed * 0.8:.3f}+{phase + 1.7:.3f}))"
    )
    return x, y


def gradient_input_args(
    preset: str, *, width: int, height: int, fps: int, duration: float
) -> list[str]:
    p = PRESETS.get(preset) or PRESETS["violet"]
    c = p["colors"]
    graph = (
        f"gradients=s={width}x{height}:r={fps}:d={duration:.3f}:"
        f"nb_colors=4:c0={c[0]}:c1={c[1]}:c2={c[2]}:c3={c[3]}:"
        f"speed=0.0012:seed={p['seed']}"
    )
    return ["-f", "lavfi", "-i", graph]


def smoke_input_args(
    *, width: int, height: int, fps: int, duration: float, seed: int
) -> list[str]:
    graph = (
        f"color=c=gray:s={width}x{height}:r={fps}:d={duration:.3f},"
        f"noise=alls=85:allf=t+u:all_seed={seed}"
    )
    return ["-f", "lavfi", "-i", graph]


def sprite_input_args(
    sprites: dict[str, Path], count: int, duration: float
) -> list[str]:
    args: list[str] = []
    for i in range(count):
        path = sprites[SPRITE_ORDER[i % 4]]
        args += ["-loop", "1", "-t", f"{duration + 1:.3f}", "-i", str(path)]
    return args


def build_video_filter(
    preset: str,
    *,
    ass_file: str,
    sprites: dict[str, Path],
    sprite_count: int = 7,
    seed: int | None = None,
) -> str:
    """filter_complex for inputs: [0] gradients, [1] smoke, [2..] sprites."""
    p = PRESETS.get(preset) or PRESETS["violet"]
    rnd = random.Random(seed if seed is not None else p["seed"])
    tr, tg, tb = p["smoke_tint"]
    smoke_op = p["smoke_opacity"]

    parts: list[str] = [
        (
            f"[1:v]gblur=sigma=110,format=rgb24,"
            f"lutrgb=r='min(val*{tr:.2f},255)':g='min(val*{tg:.2f},255)':"
            f"b='min(val*{tb:.2f},255)'[smoke]"
        ),
        f"[0:v][smoke]blend=all_mode=lighten:all_opacity={smoke_op:.2f}[base]",
    ]

    cur = "base"
    for i in range(sprite_count):
        input_idx = 2 + i
        name = SPRITE_ORDER[i % 4]
        scale = {
            "bokeh_a": rnd.randint(150, 340),
            "bokeh_b": rnd.randint(220, 420),
            "bokeh_c": rnd.randint(120, 260),
            "dust": rnd.randint(18, 46),
        }[name]
        alpha = rnd.uniform(0.10, 0.30) if name != "dust" else rnd.uniform(0.25, 0.55)
        blur = rnd.randint(0, 4)
        x_expr, y_expr = _overlay_expr(rnd)
        tag = f"sp{i}"
        chain = f"[{input_idx}:v]scale={scale}:{scale},format=rgba,colorchannelmixer=aa={alpha:.3f}"
        if blur:
            chain += f",boxblur={blur}:{blur}"
        parts.append(chain + f"[{tag}]")
        parts.append(
            f"[{cur}][{tag}]overlay=x='{x_expr}':y='{y_expr}':eval=frame[v{i}]"
        )
        cur = f"v{i}"

    parts.append(
        f"[{cur}]vignette=angle=PI/5,noise=alls=5:allf=t+u,"
        f"ass={ass_file},format=yuv420p[vout]"
    )
    return ";".join(parts)
