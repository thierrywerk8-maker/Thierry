#!/usr/bin/env python3
"""Maak een geanimeerde GIF van het Salt Wave-logo waarin alleen het zonnetje draait.

Bron:   logo/source/saltwave-logo.png   (900 x 300 = Figma-frame 225 x 75 op 4x)
Output: logo/saltwave-logo-900x300.gif  (900 x 300, transparante achtergrond)

Net als bij de PNG-export op 4x levert dit een bestand van 900 x 300 op; Paylogic
schaalt het zelf in dezelfde verhouding naar de logoplek. Het logo staat op exact
dezelfde plek als in de bron (1:1, geen herschaling).

Kwaliteit:
- Het zonnetje wordt per frame vanuit het origineel geroteerd (BICUBIC), met
  premultiplied alpha, zodat de randen niet grauw worden. Mengen gebeurt in sRGB,
  precies zoals een browser de PNG over de achtergrond legt.
- GIF kent geen half-transparante pixels: zachte randen worden gemengd met de
  shop-achtergrond (BG). Alleen vrijwel onzichtbare pixels worden transparant.
- Eén gedeeld palet, geen dithering (geen ruis of flikkering).

Bestandsgrootte (Paylogic: max. 300 KB):
- Frame 0 is het volledige logo. Elk volgend frame bevat alleen het vak rond het
  zonnetje en wist dat vak na tonen (disposal 2), dus zonder spookbeelden.
- De zon-frames gebruiken een eigen deel van het palet (63 kleuren), zodat ze met
  6-bits LZW-codes kunnen (eigen LZW-encoder), wat ~25% per frame scheelt.

Gebruik:  python3 logo/make_gif.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE / "source" / "saltwave-logo.png"
OUT = HERE / "saltwave-logo-900x300.gif"

BG = np.array([0x24, 0x80, 0xA5], dtype=np.float64)  # shop-achtergrond #2480A5
DOWNSCALE = 1                     # 1 = 900 x 300 (zoals de 4x-export), 4 = 225 x 75
SECONDS_PER_TURN = 8.0
FRAMES = 128                      # ~16 fps; vertragingen van 6/7 cs, samen precies 8,0 s
ALPHA_CUTOFF = 0.04               # dekking (0-1) waaronder een pixel transparant wordt
# Lineair licht alleen bij verkleinen (gamma-correct). Op 1:1 mengen we in sRGB, net
# zoals de browser de PNG over de achtergrond legt, zodat de GIF er precies zo uitziet.
LINEAR_LIGHT = DOWNSCALE > 1
MAX_BYTES = 300_000               # 300 KB (decimaal gerekend, dus veilig onder de limiet)

SUN_BITS = 6                      # zon-frames: 2^6 = 64 indices (63 kleuren + transparant)
SUN_TRANSPARENT = (1 << SUN_BITS) - 1
TRANSPARENT = 255                 # transparante index in frame 0

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


def frame_delays() -> list[int]:
    """Vertragingen in honderdsten van seconden, samen exact SECONDS_PER_TURN."""
    total = round(SECONDS_PER_TURN * 100)
    return [(k + 1) * total // FRAMES - k * total // FRAMES for k in range(FRAMES)]


def render(static: Image.Image, sun: Image.Image, center, out_size):
    """Rendert alle frames. Geeft (frame 0 volledig, venster, uitsneden per frame).

    Elk frame is een float-array (h, w, 4): premultiplied RGB + alpha (0-1).
    Buiten het venster rond de zon is elk frame identiek aan frame 0 (gecontroleerd).
    """
    def finish(channels):
        small = [np.array(Image.fromarray(c, "F").resize(out_size, Image.Resampling.LANCZOS),
                          dtype=np.float64) if out_size != static.size else c.astype(np.float64)
                 for c in channels]
        f = np.stack(small, axis=2)
        a = np.clip(f[:, :, 3:4], 0.0, 1.0)
        return np.concatenate([np.clip(f[:, :, :3], 0.0, a), a], axis=2)  # wit: kleur <= dekking

    static_ch = premultiplied(static)
    sun_ch = [Image.fromarray(c, "F") for c in premultiplied(sun)]
    only_static = finish(static_ch)

    delays = frame_delays()
    t = np.concatenate([[0], np.cumsum(delays)[:-1]])
    frames = []
    for tk in t:
        angle = -360.0 * tk / sum(delays)    # negatief = met de klok mee; hoek volgt de tijd
        rot = [np.array(c.rotate(angle, resample=Image.Resampling.BICUBIC, center=center))
               for c in sun_ch]
        # Zon en rest overlappen nooit, dus optellen = samenstellen.
        frames.append(finish([s + r for s, r in zip(static_ch, rot)]))

    changed = np.zeros(frames[0].shape[:2], bool)
    for f in frames:
        changed |= (f != only_static).any(2)
    ys, xs = np.nonzero(changed)
    win = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    x0, y0, x1, y1 = win
    return frames[0], win, [f[y0:y1, x0:x1] for f in frames], delays


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


def quantize(px: np.ndarray, n: int) -> np.ndarray:
    """Max. n kleuren voor de gegeven pixels (exact als er niet meer zijn)."""
    uniq = np.unique(px, axis=0)
    if len(uniq) <= n:
        return uniq
    strip = Image.fromarray(np.ascontiguousarray(px.reshape(1, -1, 3)), "RGB")
    q = strip.quantize(colors=n, method=Image.Quantize.MEDIANCUT, kmeans=3,
                       dither=Image.Dither.NONE)
    return np.unique(np.array(q.getpalette()[: n * 3], np.uint8).reshape(-1, 3), axis=0)


def nearest(rgb: np.ndarray, palette: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """Index van de dichtstbijzijnde paletkleur (alleen uit `allowed`)."""
    flat = rgb.reshape(-1, 3).astype(np.int32)
    uniq, inv = np.unique(flat, axis=0, return_inverse=True)
    cand = palette[allowed].astype(np.int32)
    best = np.empty(len(uniq), np.int64)
    for s in range(0, len(uniq), 4096):
        d = ((uniq[s:s + 4096, None, :] - cand[None]) ** 2).sum(-1)
        best[s:s + 4096] = d.argmin(1)
    return allowed[best][inv.ravel()].reshape(rgb.shape[:2]).astype(np.uint8)


def lzw_encode(pixels: bytes, min_code_size: int) -> bytes:
    """GIF-LZW zoals giflib: code-grootte omhoog zodra de volgende vrije code niet
    meer past, clear-code bij een volle tabel (4095)."""
    clear, eoi = 1 << min_code_size, (1 << min_code_size) + 1
    bits, nxt = min_code_size + 1, eoi + 1
    table: dict[tuple[int, int], int] = {}
    acc = nacc = 0
    out = bytearray()

    def emit(code: int) -> None:
        nonlocal acc, nacc, bits
        acc |= code << nacc
        nacc += bits
        while nacc >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nacc -= 8
        if nxt >= (1 << bits) and code <= 4095 and bits < 12:
            bits += 1

    emit(clear)
    it = iter(pixels)
    cur = next(it)
    for px in it:
        code = table.get((cur, px))
        if code is not None:
            cur = code
            continue
        emit(cur)
        if nxt >= 4095:
            emit(clear)
            table.clear()
            nxt, bits = eoi + 1, min_code_size + 1
        else:
            table[(cur, px)] = nxt
            nxt += 1
        cur = px
    emit(cur)
    emit(eoi)
    if nacc:
        out.append(acc & 0xFF)
    return bytes(out)


def image_block(idx: np.ndarray, offset, delay_cs: int, disposal: int,
                transparent: int, min_code_size: int) -> bytes:
    h, w = idx.shape
    assert int(idx.max()) < (1 << min_code_size)
    gce = b"!\xf9\x04" + struct.pack("<BHBB", (disposal << 2) | 1, delay_cs, transparent, 0)
    desc = b"," + struct.pack("<HHHHB", offset[0], offset[1], w, h, 0)
    data = lzw_encode(np.ascontiguousarray(idx).tobytes(), min_code_size)
    blocks = bytearray()
    for i in range(0, len(data), 255):
        blocks += bytes([len(data[i:i + 255])]) + data[i:i + 255]
    return gce + desc + bytes([min_code_size]) + bytes(blocks) + b"\x00"


def build(static, sun, info):
    out_size = (static.size[0] // DOWNSCALE, static.size[1] // DOWNSCALE)
    full0, win, crops, delays = render(static, sun, info["center"], out_size)
    wx0, wy0, wx1, wy1 = win
    rgb0, op0 = matte(full0)
    crop_m = [matte(c) for c in crops]

    # Palet: index 0..62 voor alles in het zonvenster (zon-frames, 6 bits),
    # 63 = transparant in zon-frames, 64..254 voor de rest van het logo, 255 = transparant.
    in_win = np.zeros(rgb0.shape[:2], bool)
    in_win[wy0:wy1, wx0:wx1] = True
    sun_pal = quantize(np.concatenate([rgb[op] for rgb, op in crop_m]), SUN_TRANSPARENT)
    rest_pal = quantize(rgb0[op0 & ~in_win], 255 - (SUN_TRANSPARENT + 1))
    palette = np.zeros((256, 3), np.uint8)
    palette[:] = BG.astype(np.uint8)
    palette[: len(sun_pal)] = sun_pal
    palette[SUN_TRANSPARENT + 1: SUN_TRANSPARENT + 1 + len(rest_pal)] = rest_pal
    sun_idx = np.arange(len(sun_pal))
    all_idx = np.concatenate([sun_idx, SUN_TRANSPARENT + 1 + np.arange(len(rest_pal))])

    # Frame 0: volledig logo; het zonvenster gebruikt dezelfde kleuren als de zon-frames.
    f0 = nearest(rgb0, palette, all_idx)
    f0[wy0:wy1, wx0:wx1] = nearest(rgb0[wy0:wy1, wx0:wx1], palette, sun_idx)
    f0[~op0] = TRANSPARENT
    wins = []
    for rgb, op in crop_m:
        full = nearest(rgb, palette, sun_idx)
        wins.append((full, op))
    w_idx = [np.where(op, full, SUN_TRANSPARENT).astype(np.uint8) for full, op in wins]
    assert (np.where(w_idx[0] == SUN_TRANSPARENT, TRANSPARENT, w_idx[0])
            == f0[wy0:wy1, wx0:wx1]).all()

    # Frame 1 komt bovenop frame 0: pixels die daar transparant zouden worden maar in
    # frame 0 dekkend zijn, blijven dekkend met hun juist gemengde kleur (~ #2480A5).
    keep = (w_idx[0] != SUN_TRANSPARENT) & (w_idx[1] == SUN_TRANSPARENT)
    w_idx[1][keep] = wins[1][0][keep]

    # Vak dat per frame wordt opgeslagen: alles wat ooit verschilt van frame 0.
    stack = np.stack(w_idx)
    ys, xs = np.nonzero((stack != stack[0]).any(0))
    rx0, ry0, rx1, ry1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1

    w, h = out_size
    gif = bytearray(b"GIF89a" + struct.pack("<HHBBB", w, h, 0xF7, TRANSPARENT, 0))
    gif += palette.tobytes()
    gif += b"!\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", 0) + b"\x00"  # oneindig
    gif += image_block(f0, (0, 0), delays[0], 1, TRANSPARENT, 8)
    for k in range(1, FRAMES):
        gif += image_block(w_idx[k][ry0:ry1, rx0:rx1], (int(wx0 + rx0), int(wy0 + ry0)),
                           delays[k], 2, SUN_TRANSPARENT, SUN_BITS)
    gif += b";"

    # Verwachte beelden zoals een browser ze toont (RGBA).
    def to_rgba(idx, transparent):
        out = np.zeros((*idx.shape, 4), np.uint8)
        vis = idx != transparent
        out[vis, :3] = palette[idx[vis]]
        out[vis, 3] = 255
        return out
    exp0 = to_rgba(f0, TRANSPARENT)
    expected = []
    for k in range(FRAMES):
        e = exp0.copy()
        if k:
            e[wy0:wy1, wx0:wx1] = to_rgba(w_idx[k], SUN_TRANSPARENT)
        expected.append(e)

    err_rest = np.abs(palette[f0].astype(int) - rgb0)[op0 & ~in_win].max(1)
    err_sun = np.concatenate([np.abs(palette[f].astype(int) - rgb)[op].max(1)
                              for (f, _), (rgb, op) in zip(wins, crop_m)])
    stats = dict(window=win, rect=(rx1 - rx0, ry1 - ry0), keep=int(keep.sum()),
                 colours=(len(sun_pal), len(rest_pal)),
                 err_rest=(err_rest.mean(), err_rest.max()), err_sun=(err_sun.mean(), err_sun.max()))
    return bytes(gif), np.stack(expected), delays, stats


def verify(path: Path, expected: np.ndarray, delays: list[int]) -> None:
    """Leest de GIF terug (Pillow past disposal toe) en vergelijkt elk frame exact."""
    gif = Image.open(path)
    size = path.stat().st_size
    assert gif.size == expected.shape[2:0:-1], gif.size
    assert gif.n_frames == FRAMES, gif.n_frames
    assert gif.info.get("loop") == 0, gif.info.get("loop")
    total = 0
    for i in range(FRAMES):
        gif.seek(i)
        assert gif.info["duration"] == delays[i] * 10
        total += gif.info["duration"]
        got = np.array(gif.convert("RGBA"))
        vis = expected[i][:, :, 3] > 0
        assert ((got[:, :, 3] > 0) == vis).all(), f"transparantie wijkt af in frame {i}"
        assert (got[vis, :3] == expected[i][vis, :3]).all(), f"kleur wijkt af in frame {i}"
    assert total == round(SECONDS_PER_TURN * 1000), total
    assert size <= MAX_BYTES, size
    print(f"OK: {path.name}  {gif.size[0]}x{gif.size[1]}  {FRAMES} frames  "
          f"{total / 1000:.1f}s per draai  {size / 1000:.1f} KB ({size} bytes)")


def main() -> None:
    src = Image.open(SRC)
    assert src.size == (900, 300), src.size
    static, sun, info = split_layers(src)
    print(f"zon-middelpunt {info['center'][0]:.2f}, {info['center'][1]:.2f}  "
          f"straal {info['r_sun']:.1f}px  vrije ruimte tot rest {info['d_other']:.1f}px")
    data, expected, delays, st = build(static, sun, info)
    OUT.write_bytes(data)
    print(f"zonvenster {st['window']}, opgeslagen vak per frame {st['rect'][0]}x{st['rect'][1]}px; "
          f"frame 1: {st['keep']} randpixels dekkend gehouden")
    print(f"palet: {st['colours'][0]} zonkleuren + {st['colours'][1]} overige; kleurfout "
          f"logo gem {st['err_rest'][0]:.2f} max {st['err_rest'][1]}, "
          f"zon gem {st['err_sun'][0]:.2f} max {st['err_sun'][1]}")
    verify(OUT, expected, delays)


if __name__ == "__main__":
    main()
