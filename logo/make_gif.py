#!/usr/bin/env python3
"""Maak een geanimeerde GIF van het Salt Wave-logo waarin alleen het zonnetje draait.

Bron:   logo/source/saltwave-logo.png  (900 x 300, wit logo op transparant)
Output: logo/saltwave-logo-sun.gif     (225 x 75, transparante achtergrond)

Het zonnetje wordt op volle resolutie geroteerd en daarna 4x verkleind, zodat de
randen netjes anti-aliased zijn. GIF kent geen half-transparante pixels, dus de
zachte randen worden gemengd met de achtergrondkleur van de shop (BG). Pixels die
bijna volledig transparant zijn worden helemaal transparant.

Gebruik:  python3 logo/make_gif.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from PIL import GifImagePlugin, Image

HERE = Path(__file__).resolve().parent
SRC = HERE / "source" / "saltwave-logo.png"
OUT = HERE / "saltwave-logo-sun.gif"

BG = np.array([0x24, 0x80, 0xA5], dtype=np.float64)  # shop-achtergrond #2480A5
OUT_SIZE = (225, 75)
SECONDS_PER_TURN = 8.0
FRAMES = 160                      # 160 x 50 ms = 8,0 s
DELAY_CS = round(SECONDS_PER_TURN * 100 / FRAMES)
ALPHA_CUTOFF = 0.10               # dekking (0-1) waaronder een pixel transparant wordt
MAX_BYTES = 300 * 1024

# Gebied in de bron waarin alleen het zonnetje staat (gecontroleerd hieronder).
SUN_RECT = (311, 216, 393, 291)   # x0, y0, x1, y1 (exclusief)


def pick_center(X, Y, alpha, in_rect) -> tuple[float, float]:
    """Draaipunt: het hart van de zon (zwaartepunt van de dekkende kern), binnen
    ~1 px daarvan verschoven naar het punt met de meeste ruimte tot de rest van
    het logo. Zo draait de zon om zijn eigen as zonder te wiebelen."""
    core = in_rect & (alpha > 128)
    wgt = alpha[core].astype(float)
    kx, ky = (X[core] * wgt).sum() / wgt.sum(), (Y[core] * wgt).sum() / wgt.sum()
    sun = in_rect & (alpha > 3)
    near = (~in_rect) & (alpha > 3) & (np.hypot(X - kx, Y - ky) < 60)
    sx, sy, ox, oy = X[sun], Y[sun], X[near], Y[near]
    best = (-np.inf, kx, ky)
    grid = np.arange(-1.25, 1.25 + 1e-9, 0.125)
    for dx in grid:
        for dy in grid:
            if dx * dx + dy * dy > 1.25 ** 2:
                continue
            cx, cy = kx + dx, ky + dy
            clear = np.hypot(ox - cx, oy - cy).min() - np.hypot(sx - cx, sy - cy).max()
            if clear > best[0]:
                best = (clear, cx, cy)
    return best[1], best[2]


def split_layers(src: Image.Image):
    rgba = np.array(src.convert("RGBA"))
    alpha = rgba[:, :, 3]
    h, w = alpha.shape
    yy, xx = np.mgrid[0:h, 0:w]
    X, Y = xx + 0.5, yy + 0.5                  # pixelmiddens, zoals Pillow rekent
    x0, y0, x1, y1 = SUN_RECT
    in_rect = (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)

    cx, cy = pick_center(X, Y, alpha, in_rect)
    dist = np.hypot(X - cx, Y - cy)
    # Pixels met dekking <= 3/255 zijn onzichtbare stofjes; die tellen niet mee.
    r_sun = dist[in_rect & (alpha > 3)].max()
    r_vis = dist[in_rect & (alpha > 30)].max()
    d_other = dist[(~in_rect) & (alpha > 3)].min()
    # Het draaiende zonnetje mag nooit de rest van het logo raken.
    assert d_other > r_sun + 1.0 and d_other > r_vis + 3.0, (r_sun, r_vis, d_other)

    sun_mask = in_rect & (dist <= r_sun + 0.75)
    sun = rgba.copy()
    sun[~sun_mask] = 0
    static = rgba.copy()
    static[in_rect] = 0
    info = dict(center=(cx, cy), r_sun=r_sun, d_other=d_other)
    return Image.fromarray(static, "RGBA"), Image.fromarray(sun, "RGBA"), info


def render_frames(static: Image.Image, sun: Image.Image, center) -> list[np.ndarray]:
    """Geeft per frame een float-array (h, w, 4): premultiplied RGB + alpha, 0-1."""
    static_pm = static.convert("RGBa")
    frames = []
    for i in range(FRAMES):
        angle = -360.0 * i / FRAMES          # negatief = met de klok mee
        rot = sun.convert("RGBa").rotate(angle, resample=Image.Resampling.BICUBIC,
                                         center=center)
        # Zon en rest overlappen nooit, dus optellen = samenstellen.
        full = np.array(static_pm, dtype=np.uint16) + np.array(rot, dtype=np.uint16)
        full = Image.fromarray(np.clip(full, 0, 255).astype(np.uint8), "RGBa")
        small = full.resize(OUT_SIZE, Image.Resampling.LANCZOS)
        frames.append(np.array(small, dtype=np.float64) / 255.0)
    return frames


def matte(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mengt premultiplied kleur met BG; geeft (rgb uint8, opaque bool)."""
    pm, a = frame[:, :, :3] * 255.0, frame[:, :, 3:4]
    rgb = pm + (1.0 - a) * BG
    opaque = a[:, :, 0] >= ALPHA_CUTOFF
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8), opaque


def build_palette(mattes) -> np.ndarray:
    """Eén gedeeld palet (max. 255 kleuren) voor alle frames, zonder dithering."""
    px = np.concatenate([rgb[op] for rgb, op in mattes])
    uniq = np.unique(px, axis=0)
    if len(uniq) <= 255:
        return uniq
    strip = Image.fromarray(px.reshape(1, -1, 3), "RGB")
    q = strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT, kmeans=3,
                       dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[: 255 * 3], dtype=np.uint8).reshape(-1, 3)
    return np.unique(pal, axis=0)


def to_indices(rgb: np.ndarray, opaque: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """Zet een gematte frame om naar paletindices; transparant = index 255."""
    flat = rgb.reshape(-1, 3).astype(np.int32)
    uniq, inv = np.unique(flat, axis=0, return_inverse=True)
    d = ((uniq[:, None, :] - palette[None, :, :].astype(np.int32)) ** 2).sum(-1)
    idx = d.argmin(1)[inv.ravel()].reshape(rgb.shape[:2]).astype(np.uint8)
    idx[~opaque] = TRANSPARENT
    return idx


TRANSPARENT = 255


def write_gif(path: Path, frames: list[np.ndarray], palette: np.ndarray) -> np.ndarray:
    """Schrijft de GIF met een frame-opbouw zonder spookbeelden.

    - Frame 0: het volledige logo (blijft staan, disposal 1).
    - Frame 1..N-1: alleen het vak rond het zonnetje; na tonen wordt dat vak
      gewist (disposal 2), zodat pixels die transparant worden nooit het vorige
      frame laten doorschemeren.
    Omdat frame 1 bovenop frame 0 komt, laat frame 0 in het zonvak alleen de
    pixels zien die in frame 1 ook dekkend zijn (verschil: een paar vrijwel
    doorzichtige randpixels, 50 ms lang).

    Geeft de verwachte beelden (indices) terug zoals een browser ze toont.
    """
    stack = np.stack(frames)
    changing = (stack != stack[0]).any(0)
    ys, xs = np.nonzero(changing)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1

    first = frames[0].copy()
    box = first[y0:y1, x0:x1]
    box[frames[1][y0:y1, x0:x1] == TRANSPARENT] = TRANSPARENT
    expected = [first] + frames[1:]

    pal = np.vstack([palette, np.repeat(BG.astype(np.uint8)[None], 256 - len(palette), 0)])
    w, h = OUT_SIZE
    out = bytearray(b"GIF89a" + struct.pack("<HHBBB", w, h, 0xF7, TRANSPARENT, 0))
    out += pal.astype(np.uint8).tobytes()
    out += b"!\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", 0) + b"\x00"  # oneindig
    for i, idx in enumerate(expected):
        if i == 0:
            img, offset, disposal = idx, (0, 0), 1
        else:
            img, offset, disposal = idx[y0:y1, x0:x1], (int(x0), int(y0)), 2
        im = Image.fromarray(np.ascontiguousarray(img), "P")
        for chunk in GifImagePlugin.getdata(im, offset=offset, duration=DELAY_CS * 10,
                                            disposal=disposal, transparency=TRANSPARENT):
            out += chunk
    out += b";"
    path.write_bytes(bytes(out))
    print(f"zonvak per frame: {x1 - x0}x{y1 - y0}px op ({x0},{y0})")
    return np.stack(expected), pal


def main() -> None:
    src = Image.open(SRC)
    assert src.size == (OUT_SIZE[0] * 4, OUT_SIZE[1] * 4), src.size
    static, sun, info = split_layers(src)
    print(f"zon-middelpunt {info['center'][0]:.2f}, {info['center'][1]:.2f}  "
          f"straal {info['r_sun']:.1f}px  vrije ruimte tot rest {info['d_other']:.1f}px")

    mattes = [matte(f) for f in render_frames(static, sun, info["center"])]
    palette = build_palette(mattes)
    print(f"palet: {len(palette)} kleuren + transparant")
    frames = [to_indices(rgb, op, palette) for rgb, op in mattes]
    expected, pal = write_gif(OUT, frames, palette)
    verify(expected, pal)


def verify(expected: np.ndarray, pal: np.ndarray) -> None:
    """Leest de GIF terug (Pillow past disposal toe) en vergelijkt elk frame."""
    gif = Image.open(OUT)
    size = OUT.stat().st_size
    assert gif.size == OUT_SIZE, gif.size
    assert gif.n_frames == FRAMES, gif.n_frames
    assert gif.info.get("loop") == 0, gif.info.get("loop")
    total = 0
    for i in range(FRAMES):
        gif.seek(i)
        total += gif.info["duration"]
        got = np.array(gif.convert("RGBA"))
        want_vis = expected[i] != TRANSPARENT
        assert ((got[:, :, 3] > 0) == want_vis).all(), f"transparantie wijkt af in frame {i}"
        assert (got[want_vis, :3] == pal[expected[i][want_vis]]).all(), f"kleur wijkt af in frame {i}"
    assert total == round(SECONDS_PER_TURN * 1000), total
    assert size <= MAX_BYTES, size
    print(f"OK: {OUT.name}  {gif.size[0]}x{gif.size[1]}  {FRAMES} frames  "
          f"{total / 1000:.1f}s per draai  {size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
