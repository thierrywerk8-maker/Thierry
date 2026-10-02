"""Seamless 10s loop: rustig bewegende achtergrond + tekstoverlay.

Alle beweging is een som van sinussen met een geheel aantal periodes over
de loop, dus frame 0 == frame N (naadloos). Gebruik:
  python make_loop.py "JOUW TEKST" "regel twee" [bron.jpg]
"""
import sys, subprocess, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

SRC = sys.argv[3] if len(sys.argv) > 3 else "/tmp/claude-0/-home-user-Thierry/9ec764ab-0650-5fb1-8bda-5dfe310266c9/images/1.jpg"
TITLE = sys.argv[1] if len(sys.argv) > 1 else "YOUR TEXT"
SUB = sys.argv[2] if len(sys.argv) > 2 else "subtitle goes here"
W, H, FPS, DUR = 1080, 1920, 30, 10
N = FPS * DUR
FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_L = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

img = cv2.cvtColor(cv2.imread(SRC), cv2.COLOR_BGR2RGB)
# cover-crop naar W x H, met 8% marge zodat warps geen randen tonen
s = max(W / img.shape[1], H / img.shape[0]) * 1.12
img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
y0, x0 = (img.shape[0] - H) // 2, (img.shape[1] - W) // 2
base = img[y0:y0 + H, x0:x0 + W].astype(np.float32)
base = cv2.copyMakeBorder(base, 0, 0, 0, 0, cv2.BORDER_REFLECT)

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
u, v = xx / W, yy / H
rng = np.random.default_rng(7)
# golven: (freq_x, freq_y, amplitude px, fase, k = periodes per loop)
waves = []
for k, (fx, fy, amp) in enumerate([(1.3, 0.9, 26), (0.8, 1.7, 22), (2.1, 1.2, 12), (1.1, 2.6, 9)], 1):
    waves.append((fx, fy, amp, rng.uniform(0, 6.28), rng.uniform(0, 6.28), k if k < 4 else 1))

def frame(i):
    t = 2 * np.pi * i / N
    dx = np.zeros_like(u); dy = np.zeros_like(u)
    for fx, fy, amp, p1, p2, k in waves:
        dx += amp * np.sin(2 * np.pi * (fx * u + fy * v) + p1 + k * t)
        dy += amp * np.cos(2 * np.pi * (fy * u - fx * v) + p2 + k * t)
    zoom = 1 + 0.015 * np.sin(t)               # zacht ademen
    cx, cy = W / 2, H / 2
    mx = (xx - cx) / zoom + cx + dx + 14 * np.sin(t)
    my = (yy - cy) / zoom + cy + dy + 14 * np.cos(t)
    out = cv2.remap(base, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    out = cv2.GaussianBlur(out, (0, 0), 2.2)   # zachter, droomachtiger
    # subtiele kleur-ademhaling (periodiek)
    g = 1 + 0.05 * np.sin(t)
    out[..., 0] *= 1 + 0.04 * np.sin(t + 1.0)
    out[..., 1] *= g
    out[..., 2] *= 1 + 0.04 * np.sin(t + 2.5)
    out *= 0.82                                 # iets donkerder voor tekst-leesbaarheid
    out += rng.normal(0, 6, out.shape).astype(np.float32)  # filmkorrel
    return np.clip(out, 0, 255).astype(np.uint8)

# tekstlaag (statisch, met zachte schaduw) + zeer langzame drijf-beweging
def text_layer():
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f1 = ImageFont.truetype(FONT, 120); f2 = ImageFont.truetype(FONT_L, 44)
    d = ImageDraw.Draw(L)
    def centered(txt, f, y, fill, track=0):
        w = sum(d.textlength(c, font=f) + track for c in txt) - track
        x = (W - w) / 2
        for c in txt:
            d.text((x, y), c, font=f, fill=fill); x += d.textlength(c, font=f) + track
    centered(TITLE.upper(), f1, H // 2 - 90, (255, 255, 255, 255), 6)
    centered(SUB.upper(), f2, H // 2 + 70, (255, 255, 255, 220), 10)
    a = np.array(L)
    shadow = np.zeros_like(a); shadow[..., 3] = cv2.GaussianBlur(a[..., 3], (0, 0), 18) * 0.55
    return a.astype(np.float32), shadow.astype(np.float32)

txt, sh = text_layer()
def comp(bg, i):
    t = 2 * np.pi * i / N
    M = np.float32([[1, 0, 0], [0, 1, 6 * np.sin(t)]])   # tekst zweeft 6px
    tl = cv2.warpAffine(txt, M, (W, H)); sl = cv2.warpAffine(sh, M, (W, H))
    bg = bg.astype(np.float32)
    a = sl[..., 3:4] / 255; bg = bg * (1 - a)
    a = tl[..., 3:4] / 255; bg = bg * (1 - a) + tl[..., :3] * a
    return np.clip(bg, 0, 255).astype(np.uint8)

p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
    "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-crf", "16", "-preset", "slow", "-movflags", "+faststart", "/home/user/Thierry/loop/loop.mp4"],
    stdin=subprocess.PIPE)
for i in range(N):
    p.stdin.write(comp(frame(i), i).tobytes())
p.stdin.close(); p.wait()
print("klaar")
