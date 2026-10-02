"""Naadloze 10s loop: statische groene achtergrond + bewegende visual met 3D-parallax.

De foto wordt gesplitst in (1) een stilstaande achtergrondplaat en (2) de visual met
een zacht alpha-masker. Alleen de visual beweegt (camera-orbit met parallax op een
pseudo-dieptekaart, rotatie, ademende zoom, golvende vervorming, bewegende belichting).
Alle beweging = sinussen met een geheel aantal periodes over de loop => frame 0 == frame N.

  python make_loop.py [--width 2160] [--out loop_4k.mp4] [--debug]
"""
import argparse, subprocess, os, numpy as np, cv2
from multiprocessing import Pool

ap = argparse.ArgumentParser()
ap.add_argument("--src", default=os.path.join(os.path.dirname(__file__), "source.jpg"))
ap.add_argument("--width", type=int, default=2160)          # 2160x3840 = 4K staand
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--dur", type=int, default=10)
ap.add_argument("--crf", type=int, default=12)
ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "loop_4k.mp4"))
ap.add_argument("--debug", action="store_true")
a = ap.parse_args()

src = cv2.cvtColor(cv2.imread(a.src), cv2.COLOR_BGR2RGB).astype(np.float32)
H0, W0, _ = src.shape
W = a.width; H = round(W * H0 / W0); N = a.fps * a.dur

# ---------- 1. scheiden: achtergrondplaat + masker (op bronresolutie) ----------
sm = cv2.GaussianBlur(src, (0, 0), 8)
yy, xx = np.mgrid[0:H0, 0:W0].astype(np.float32); u, v = xx / W0, yy / H0
clean = ((v < .05) | ((u < .04) & (v < .45)) | ((u > .96) & (v < .2)) |
         ((u < .55) & (v > .975)) | ((u < .12) & (v > .9)))          # zones zonder visual
cm = clean.astype(np.float32)
bg = np.clip(cv2.GaussianBlur(sm * cm[..., None], (0, 0), 300) /
             np.maximum(cv2.GaussianBlur(cm, (0, 0), 300)[..., None], 1e-4), 0, 255)
lab = lambda x: cv2.cvtColor(x.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
d = np.linalg.norm(lab(sm) - lab(bg), axis=2)
core = (np.clip((d - 14) / 26, 0, 1) > .5).astype(np.uint8)
core = cv2.morphologyEx(core, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (121, 121)))
n, lbl, st, _ = cv2.connectedComponentsWithStats(core)
keep = np.isin(lbl, [i for i in range(1, n) if st[i, 4] > .02 * H0 * W0]).astype(np.uint8)
cont, _ = cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
filled = np.zeros_like(keep); cv2.drawContours(filled, cont, -1, 1, -1)
alpha = cv2.GaussianBlur(filled.astype(np.float32), (0, 0), 25)

# ---------- 2. pseudo-diepte (dichtbij = hoog): masker + helderheid ----------
lum = cv2.GaussianBlur(src.mean(2), (0, 0), 10)
lum = np.clip((lum - np.percentile(lum, 5)) / (np.percentile(lum, 95) - np.percentile(lum, 5)), 0, 1)
depth = cv2.GaussianBlur(.55 * alpha + .45 * lum * alpha, (0, 0), 0.012 * W0)
depth = (depth - depth.min()) / (depth.max() - depth.min())

# ---------- 3. naar uitvoerresolutie ----------
up = lambda x, k=cv2.INTER_LANCZOS4: cv2.resize(x, (W, H), interpolation=k)
fg = up(src)
fg = np.clip(fg + 0.6 * (fg - cv2.GaussianBlur(fg, (0, 0), 2.0)), 0, 255)       # lichte unsharp
alpha_u = np.clip(up(alpha, cv2.INTER_CUBIC), 0, 1)
depth_u = up(depth, cv2.INTER_CUBIC)
rng = np.random.default_rng(11)
bg_u = up(bg, cv2.INTER_CUBIC)
bg_u = np.clip(bg_u + rng.normal(0, 4.5, bg_u.shape[:2])[..., None] + rng.normal(0, 1.5, bg_u.shape), 0, 255).astype(np.float32)  # vaste korrel

# lage-resolutie raster voor de (gladde) velden
sc = 8; h, w = H // sc, W // sc
gy, gx = np.mgrid[0:h, 0:w].astype(np.float32); gx *= sc; gy *= sc
dl = cv2.resize(depth_u, (w, h), interpolation=cv2.INTER_AREA)
dgy, dgx = np.gradient(cv2.GaussianBlur(dl, (0, 0), 2))
gm = np.percentile(np.hypot(dgx, dgy), 98); dgx /= gm; dgy /= gm
al = cv2.resize(alpha_u, (w, h), interpolation=cv2.INTER_AREA)
ys, xs = np.nonzero(al > .5); cx, cy = xs.mean() * sc, ys.mean() * sc          # zwaartepunt visual
rng2 = np.random.default_rng(7)
waves = [(fx, fy, amp, rng2.uniform(0, 6.28), rng2.uniform(0, 6.28), k)
         for fx, fy, amp, k in [(1.3, .9, .0095, 1), (.8, 1.7, .008, 2), (2.1, 1.2, .0045, 3), (1.1, 2.6, .0035, 1)]]

def render(i):
    t = 2 * np.pi * i / N
    ox = np.zeros((h, w), np.float32); oy = np.zeros_like(ox)
    # 3D camera-orbit: parallax evenredig met diepte
    dc = dl - dl.mean()
    ox += dc * .075 * W * np.cos(t); oy += dc * .075 * W * np.sin(t)
    # lichte rotatie + ademende zoom om het zwaartepunt
    th = np.radians(1.0) * np.sin(t); z = .012 * np.sin(t + 1.3)
    ox += -th * (gy - cy) + z * (gx - cx); oy += th * (gx - cx) + z * (gy - cy)
    # rustige golven (alleen zichtbaar waar de visual is)
    uu, vv = gx / W, gy / H
    for fx, fy, amp, p1, p2, k in waves:
        ox += amp * W * np.sin(2 * np.pi * (fx * uu + fy * vv) + p1 + k * t)
        oy += amp * W * np.cos(2 * np.pi * (fy * uu - fx * vv) + p2 + k * t)
    # bewegende belichting op het "oppervlak" (3D-cue)
    shade = 1 + .10 * (dgx * np.cos(t) + dgy * np.sin(t))
    mx = (np.arange(W, dtype=np.float32)[None] + cv2.resize(ox, (W, H), interpolation=cv2.INTER_CUBIC))
    my = (np.arange(H, dtype=np.float32)[:, None] + cv2.resize(oy, (W, H), interpolation=cv2.INTER_CUBIC))
    f = cv2.remap(fg, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    al_t = cv2.remap(alpha_u, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)[..., None]
    f *= cv2.resize(shade, (W, H), interpolation=cv2.INTER_CUBIC)[..., None]
    out = bg_u * (1 - al_t) + f * al_t
    return i, np.clip(out, 0, 255).astype(np.uint8)

if __name__ == "__main__":
    if a.debug:
        o = os.path.dirname(a.out)
        cv2.imwrite(o + "/dbg_alpha.png", (alpha * 255).astype(np.uint8))
        cv2.imwrite(o + "/dbg_bg.png", cv2.cvtColor(bg.astype(np.uint8), cv2.COLOR_RGB2BGR))
        cv2.imwrite(o + "/dbg_depth.png", (depth * 255).astype(np.uint8))
        for k in (0, N // 4, N // 2):
            cv2.imwrite(f"{o}/dbg_f{k}.png", cv2.cvtColor(render(k)[1], cv2.COLOR_RGB2BGR))
        raise SystemExit
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-crf", str(a.crf), "-preset", "slow", "-movflags", "+faststart", a.out],
        stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for i, fr in pool.imap(render, range(N), chunksize=1):
            p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait(); print("klaar", a.out)
