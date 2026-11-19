#!/usr/bin/env python3
"""Maak een geanimeerde GIF van het Salt Wave-logo waarin alleen het zonnetje draait.

Bron:   logo/source/saltwave-logo.png  (900 x 300, wit logo op transparant)
Output: logo/saltwave-logo-225x75.gif  (225 x 75, transparante achtergrond)

Het zonnetje wordt op volle resolutie geroteerd en daarna 4x verkleind, zodat de
randen netjes anti-aliased zijn. Draaien, verkleinen en mengen gebeurt in lineair
licht (gamma-correct), zodat dunne witte lijnen hun dikte en helderheid houden.
GIF kent geen half-transparante pixels, dus de zachte randen worden gemengd met de
achtergrondkleur van de shop (BG). Pixels die bijna volledig transparant zijn
worden helemaal transparant.

Gebruik:  python3 logo/make_gif.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from PIL import GifImagePlugin, Image

HERE = Path(__file__).resolve().parent
SRC = HERE / "source" / "saltwave-logo.png"
OUT = HERE / "saltwave-logo-225x75.gif"

BG = np.array([0x24, 0x80, 0xA5], dtype=np.float64)  # shop-achtergrond #2480A5
OUT_SIZE = (225, 75)
SECONDS_PER_TURN = 8.0
FRAMES = 200                      # 200 x 40 ms = 8,0 s (25 fps)
DELAY_CS = round(SECONDS_PER_TURN * 100 / FRAMES)
assert DELAY_CS * FRAMES == round(SECONDS_PER_TURN * 100)
ALPHA_CUTOFF = 0.04               # dekking (0-1) waaronder een pixel transparant wordt
LINEAR_LIGHT = True               # gamma-correct draaien/verkleinen/mengen
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


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def premultiplied(layer: Image.Image) -> list[np.ndarray]:
    """RGBA -> vier float32-kanalen (R*a, G*a, B*a, a), in lineair licht."""
    arr = np.array(layer.convert("RGBA"), dtype=np.float64) / 255.0
    rgb, a = arr[:, :, :3], arr[:, :, 3:4]
    if LINEAR_LIGHT:
        rgb = srgb_to_linear(rgb)
    pm = np.concatenate([rgb * a, a], axis=2).astype(np.float32)
    return [pm[:, :, k] for k in range(4)]


def render_frames(static: Image.Image, sun: Image.Image, center) -> list[np.ndarray]:
    """Geeft per frame een float-array (h, w, 4): premultiplied RGB + alpha, 0-1
    (RGB in lineair licht als LINEAR_LIGHT aan staat)."""
    static_ch = premultiplied(static)
    sun_ch = [Image.fromarray(c, "F") for c in premultiplied(sun)]
    frames = []
    for i in range(FRAMES):
        angle = -360.0 * i / FRAMES          # negatief = met de klok mee
        small = []
        for k in range(4):
            rot = np.array(sun_ch[k].rotate(angle, resample=Image.Resampling.BICUBIC,
                                            center=center))
            # Zon en rest overlappen nooit, dus optellen = samenstellen.
            full = Image.fromarray(static_ch[k] + rot, "F")
            small.append(np.array(full.resize(OUT_SIZE, Image.Resampling.LANCZOS),
                                  dtype=np.float64))
        f = np.stack(small, axis=2)
        a = np.clip(f[:, :, 3:4], 0.0, 1.0)
        pm = np.clip(f[:, :, :3], 0.0, a)    # wit is max. 1, dus kleur <= dekking
        frames.append(np.concatenate([pm, a], axis=2))
    return frames


def matte(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mengt premultiplied kleur met BG; geeft (rgb uint8, opaque bool)."""
    pm, a = frame[:, :, :3], frame[:, :, 3:4]
    bg = BG / 255.0
    if LINEAR_LIGHT:
        rgb = linear_to_srgb(pm + (1.0 - a) * srgb_to_linear(bg))
    else:
        rgb = pm + (1.0 - a) * bg
    opaque = a[:, :, 0] >= ALPHA_CUTOFF
    return np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8), opaque


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


def to_indices(rgb: np.ndarray, opaque: np.ndarray, palette: np.ndarray):
    """Zet een gematte frame om naar paletindices. Geeft (indices voor elke pixel,
    dekkend-masker); transparante pixels krijgen pas in write_gif index 255."""
    flat = rgb.reshape(-1, 3).astype(np.int32)
    uniq, inv = np.unique(flat, axis=0, return_inverse=True)
    d = ((uniq[:, None, :] - palette[None, :, :].astype(np.int32)) ** 2).sum(-1)
    idx = d.argmin(1)[inv.ravel()].reshape(rgb.shape[:2]).astype(np.uint8)
    return idx, opaque


TRANSPARENT = 255


def write_gif(path: Path, frames: list, palette: np.ndarray):
    """Schrijft de GIF met een frame-opbouw zonder spookbeelden.

    - Frame 0: het volledige logo (blijft staan, disposal 1).
    - Frame 1..N-1: alleen het vak rond het zonnetje; na tonen wordt dat vak
      gewist (disposal 2), zodat pixels die transparant worden nooit het vorige
      frame laten doorschemeren.
    Frame 1 komt bovenop frame 0. Pixels die in frame 0 dekkend zijn en in
    frame 1 transparant zouden worden, schrijft frame 1 daarom dekkend, met hun
    juist gemengde kleur (vrijwel exact #2480A5). Zo is ook dat frame op de
    shop-achtergrond exact.

    Geeft de verwachte beelden (indices) terug zoals een browser ze toont.
    """
    expected = [np.where(op, full, TRANSPARENT).astype(np.uint8) for full, op in frames]
    keep = (expected[0] != TRANSPARENT) & (expected[1] == TRANSPARENT)
    expected[1][keep] = frames[1][0][keep]
    print(f"frame 1: {int(keep.sum())} bijna-transparante randpixels dekkend gehouden")

    stack = np.stack(expected)
    changing = (stack != stack[0]).any(0)
    ys, xs = np.nonzero(changing)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1

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
