"""Laat de datum in het creme labeltje ("ZATERDAG 10 JULI 2027") van een productafbeelding wegvallen.

Alleen de binnenkant van het labeltje wordt aangepast: de letters worden zacht uitgevloeid
over de eigen crème achtergrond. Rand, ribbons en de rest van de afbeelding blijven pixel-gelijk.

Gebruik: python3 soften_date.py IN.jpg OUT.png [--sigma 8] [--strength 0.45]
"""
import argparse

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

# Zoekgebied van het labeltje in de 600x450 productafbeeldingen (x0, y0, x1, y1).
ROI = (130, 95, 470, 165)


def gblur(a, sigma):
    if a.ndim == 3:
        return np.stack([ndi.gaussian_filter(a[..., c], sigma) for c in range(a.shape[2])], -1)
    return ndi.gaussian_filter(a, sigma)


def masked_blur(img, mask, sigma):
    """Gaussian blur die alleen pixels binnen `mask` meeneemt (geen donkere rand die naar binnen lekt)."""
    m = mask.astype(float)
    num = gblur(img * m[..., None], sigma)
    den = gblur(m, sigma)[..., None]
    return num / np.maximum(den, 1e-6)


def soften(path_in, path_out, sigma=8.0, strength=0.45, debug=None):
    im = Image.open(path_in).convert("RGB")
    a = np.asarray(im).astype(float)
    x0, y0, x1, y1 = ROI
    roi = a[y0:y1, x0:x1]
    R, G, B = roi[..., 0], roi[..., 1], roi[..., 2]

    # Creme vulling: licht en geel-wit (roze achtergrond heeft G ~165, creme G > 195).
    cream = (R > 200) & (G > 195) & (B > 150)
    lab, n = ndi.label(cream)
    sizes = ndi.sum(cream, lab, range(1, n + 1))
    pill_fill = lab == (int(np.argmax(sizes)) + 1)
    # Binnenkant van het labeltje, per kolom: van de eerste tot de laatste creme pixel.
    # Waar letters de bovenrand raken (de "27" tegen het rode lint) ontbreekt creme bovenaan;
    # die kolommen krijgen de rand van hun buren (alleen als er aan beide kanten schone kolommen zijn,
    # zodat de ronde uiteinden van het label onaangetast blijven).
    H, W = pill_fill.shape
    has = pill_fill.any(axis=0)
    top = np.where(has, pill_fill.argmax(axis=0), np.inf).astype(float)
    bot = np.where(has, H - 1 - pill_fill[::-1].argmax(axis=0), -np.inf).astype(float)

    def fix_bumps(v, sign, reach=15, slope=0.25, grow=3):
        v = v * sign  # werk altijd met "kleiner = verder naar buiten"
        fin = np.isfinite(v)
        bump = np.zeros(W, bool)
        inner = np.zeros(W, bool)  # kolommen met schone buren aan beide kanten (dus niet in de ronde kap)
        for x in range(W):
            if not fin[x]:
                continue
            left = [v[x - d] + d * slope for d in range(1, reach + 1) if x - d >= 0 and fin[x - d]]
            right = [v[x + d] + d * slope for d in range(1, reach + 1) if x + d < W and fin[x + d]]
            if left and right:
                inner[x] = True
                bump[x] = v[x] > max(min(left), min(right)) + 0.5
        # Randkolommen van een bult zijn vaak maar half aangetast: neem er een paar extra mee.
        bump = ndi.binary_dilation(bump, iterations=grow) & inner
        out = v.copy()
        good = np.nonzero(fin & ~bump)[0]
        for x in np.nonzero(bump)[0]:
            lo, hi = good[good < x], good[good > x]
            if len(lo) and len(hi):
                a_, b_ = lo[-1], hi[0]
                out[x] = min(v[x], v[a_] + (v[b_] - v[a_]) * (x - a_) / (b_ - a_))
        return out * sign

    top = fix_bumps(top, 1)
    bot = fix_bumps(bot, -1)
    yy = np.arange(H)[:, None]
    interior = has[None, :] & (yy >= np.ceil(top)[None, :]) & (yy <= np.floor(bot)[None, :])

    # Achtergrond zonder letters: alleen creme pixels, sterk uitgesmeerd (houdt de lichte verloop).
    bg_mask = interior & ndi.binary_erosion(pill_fill, iterations=1)
    bg = masked_blur(roi, bg_mask, 9.0)
    # Letters zacht uitgevloeid binnen het labeltje.
    soft = masked_blur(roi, interior, sigma)
    out_roi = bg + strength * (soft - bg)

    # Harde maskerrand is hier naadloos: aan beide kanten van de grens zit (bijna) dezelfde creme.
    alpha = interior.astype(float)[..., None]
    new_roi = roi * (1 - alpha) + out_roi * alpha

    res = a.copy()
    res[y0:y1, x0:x1] = new_roi
    Image.fromarray(np.clip(res + 0.5, 0, 255).astype(np.uint8)).save(path_out)
    if debug:
        Image.fromarray((interior * 255).astype(np.uint8)).save(debug)
    return int(interior.sum())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("inp")
    p.add_argument("out")
    p.add_argument("--sigma", type=float, default=8.0)
    p.add_argument("--strength", type=float, default=0.45)
    p.add_argument("--debug")
    a = p.parse_args()
    print(a.out, "interior px:", soften(a.inp, a.out, a.sigma, a.strength, a.debug))
