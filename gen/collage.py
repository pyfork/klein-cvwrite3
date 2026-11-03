# design-lead-Opus5.5-agent, 2026-10-27; moved from the design spike by senior-lead-Opus5.5-agent, 2026-11-03
# (redesign slice 5): only the 20 images the home uses, the torn edge as WebP, written into app/static/art.
"""Cut-paper collage generator for the Better Jobs home (brief Addendum 14). Dev-only: never installed in CI or on the server.

Every piece is a binary mask first. OpenCV turns masks into paper:
  torn  = signed distance field + fractal noise, thresholded (ragged edge),
          plus a patchy white fibre rim where the tear exposes the paper core;
  cut   = cv2.findContours on a mask, cv2.approxPolyDP to straight scissor snips;
  paper = flat colour x fine grain x fibre streaks x slow mottling;
  shadow= the piece's own mask, offset and Gaussian-blurred, in ink at low alpha.
Pieces are composited "over" onto an RGBA canvas and written as WebP with alpha.

Run from the repo root, in a venv of its own:
    python -m venv ~/.cvwrite3-gen-venv
    ~/.cvwrite3-gen-venv/bin/pip install --require-hashes --only-binary :all: -r gen/requirements.txt
    ~/.cvwrite3-gen-venv/bin/python gen/collage.py
It overwrites the files in app/static/art. Seeded, so a rerun with the pinned packages on the same machine writes the
same bytes. Every image is drawn in one run, in NAMES order, because cut() draws from the shared RNG.
"""
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

RNG = np.random.default_rng(11)
OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "art"
NAMES = ("ad-lilac", "ad-teal", "ad-marigold", "copy", "cv-lilac", "cv-teal", "cv-marigold", "scissors", "scissors-ink",
         "pages", "clipping", "redacted", "ground", "arrow", "folder", "spotlight", "scrap-star", "scrap-tri", "scrap-dot",
         "edge")

INK = (19, 35, 58)
PAL = {
    "ink": INK,
    "coral": (255, 90, 71),
    "lilac": (196, 178, 236),
    "teal": (38, 150, 132),
    "marigold": (243, 180, 60),
    "sky": (160, 205, 236),
    "blush": (247, 201, 186),
    "copy": (214, 212, 206),
    "toner": (88, 86, 92),
    "white": (252, 250, 245),
    "core": (250, 247, 238),
    "steel": (205, 212, 220),
    "steel2": (150, 160, 174),
    "kraft": (205, 170, 120),
}


# ---------------------------------------------------------------- noise
def fractal(h, w, base=64, octaves=5, persist=0.55, seed=None):
    """Value noise in [-1, 1], summed over octaves (OpenCV resize does the interpolation)."""
    rng = np.random.default_rng(seed) if seed is not None else RNG
    out = np.zeros((h, w), np.float32)
    amp, total, cell = 1.0, 0.0, base
    for _ in range(octaves):
        gh, gw = max(2, h // cell + 2), max(2, w // cell + 2)
        grid = rng.uniform(-1, 1, (gh, gw)).astype(np.float32)
        up = cv2.resize(grid, (gw * cell, gh * cell), interpolation=cv2.INTER_CUBIC)[:h, :w]
        out += amp * up
        total += amp
        amp *= persist
        cell = max(1, cell // 2)
    return out / total


def sdf(mask):
    """Signed distance: positive inside, negative outside (pixels)."""
    m = (mask > 127).astype(np.uint8)
    inside = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    outside = cv2.distanceTransform(1 - m, cv2.DIST_L2, 5)
    return inside - outside


# ---------------------------------------------------------------- edges
def torn(mask, amp=9.0, base=40, rim=7.0, rim_cover=0.55, seed=None):
    """Return (piece_mask, rim_mask) floats in [0,1]. The rim is the white core a tear shows."""
    h, w = mask.shape
    d = sdf(mask)
    n = fractal(h, w, base=base, octaves=6, persist=0.6, seed=seed)
    fine = fractal(h, w, base=6, octaves=2, seed=None if seed is None else seed + 1)
    field = d + amp * n + 2.2 * fine
    piece = (field > 0).astype(np.uint8) * 255
    # patchy rim: thresholded slow noise decides where the tear shows white core
    patch = fractal(h, w, base=120, octaves=3, seed=None if seed is None else seed + 2)
    _, patch_m = cv2.threshold(patch, 1 - 2 * rim_cover, 1, cv2.THRESH_BINARY)
    rimfield = d + amp * n + 2.2 * fine + rim * (0.6 + 0.8 * np.abs(fine)) * patch_m
    outer = (rimfield > 0).astype(np.uint8) * 255
    piece_f = cv2.GaussianBlur(piece, (0, 0), 0.7).astype(np.float32) / 255
    outer_f = cv2.GaussianBlur(outer, (0, 0), 0.9).astype(np.float32) / 255
    rim_f = np.clip(outer_f - piece_f, 0, 1)
    return piece_f, rim_f


def cut(mask, eps=0.012, jitter=1.2):
    """Scissor-cut version of a mask: contour -> approxPolyDP -> slightly jittered straight snips."""
    m = (mask > 127).astype(np.uint8)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = np.zeros_like(m)
    for c in cnts:
        peri = cv2.arcLength(c, True)
        poly = cv2.approxPolyDP(c, eps * peri, True).astype(np.float32)
        poly += RNG.normal(0, jitter, poly.shape).astype(np.float32)
        cv2.fillPoly(out, [poly.astype(np.int32)], 1, lineType=cv2.LINE_AA)
    f = cv2.GaussianBlur(out.astype(np.float32), (0, 0), 0.6)
    return np.clip(f, 0, 1)


def soft(mask, s=0.7):
    return np.clip(cv2.GaussianBlur((mask > 127).astype(np.float32), (0, 0), s), 0, 1)


# ---------------------------------------------------------------- paper
def paper(h, w, rgb, grain=0.035, fibres=True, mottle=0.03, seed=None):
    rng = np.random.default_rng(seed) if seed is not None else RNG
    base = np.ones((h, w, 3), np.float32) * (np.array(rgb, np.float32) / 255)
    g = rng.normal(0, 1, (h, w)).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 0.8)
    mot = fractal(h, w, base=160, octaves=3, seed=None if seed is None else seed + 5)
    shade = 1 + grain * g + mottle * mot
    if fibres:
        f = np.zeros((h, w), np.float32)
        for _ in range(int(h * w / 2600)):
            x, y = rng.uniform(0, w), rng.uniform(0, h)
            a = rng.uniform(0, math.pi)
            L = rng.uniform(4, 16)
            cv2.line(f, (int(x), int(y)), (int(x + L * math.cos(a)), int(y + L * math.sin(a))),
                     float(rng.choice([-1, 1])), 1, cv2.LINE_AA)
        f = cv2.GaussianBlur(f, (0, 0), 0.6)
        shade += 0.05 * f
    return np.clip(base * shade[..., None], 0, 1)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rgb = np.zeros((h, w, 3), np.float32)
        self.a = np.zeros((h, w), np.float32)

    def over(self, rgb, alpha):
        a = alpha[..., None]
        out_a = alpha + self.a * (1 - alpha)
        num = rgb * a + self.rgb * self.a[..., None] * (1 - a)
        self.rgb = np.where(out_a[..., None] > 1e-5, num / np.maximum(out_a[..., None], 1e-5), 0)
        self.a = out_a

    def shadow(self, alpha, dx=6, dy=10, blur=10, op=0.26, color=INK):
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        sh = cv2.warpAffine(alpha, M, (self.w, self.h))
        sh = cv2.GaussianBlur(sh, (0, 0), blur) * op
        # contact shadow: tight and darker
        M2 = np.float32([[1, 0, dx * 0.25], [0, 1, dy * 0.25]])
        c = cv2.GaussianBlur(cv2.warpAffine(alpha, M2, (self.w, self.h)), (0, 0), max(1.5, blur * 0.2)) * op * 0.6
        tot = np.clip(sh + c, 0, 0.6)
        self.over(np.ones((self.h, self.w, 3), np.float32) * (np.array(color, np.float32) / 255), tot)

    def piece(self, alpha, rgb, rim=None, rimrgb=PAL["core"], shadow=True, sh=None, seed=None):
        """Lay one sheet: shadow, then white torn core (rim), then the coloured face."""
        sh = sh or {}
        full = alpha if rim is None else np.clip(alpha + rim, 0, 1)
        if shadow:
            self.shadow(full, **sh)
        if rim is not None:
            self.over(paper(self.h, self.w, rimrgb, grain=0.02, fibres=True, seed=seed), rim)
        tex = rgb if rgb.ndim == 3 else paper(self.h, self.w, rgb)
        self.over(tex, alpha)

    def ink(self, alpha, rgb, op=1.0):
        self.over(np.ones((self.h, self.w, 3), np.float32) * (np.array(rgb, np.float32) / 255), alpha * op)

    def save(self, path, q=86):
        rgba = np.dstack([self.rgb, self.a])
        img = Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA")
        img.save(path, "WEBP", quality=q, method=6)
        return path


def blank(w, h):
    return np.zeros((h, w), np.uint8)


def rot(mask, deg, cx=None, cy=None):
    h, w = mask.shape[:2]
    cx = w / 2 if cx is None else cx
    cy = h / 2 if cy is None else cy
    M = cv2.getRotationMatrix2D((cx, cy), deg, 1)
    return cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_LINEAR)


def rect(w, h, x0, y0, x1, y1, deg=0):
    m = blank(w, h)
    cv2.rectangle(m, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
    return rot(m, deg, (x0 + x1) / 2, (y0 + y1) / 2) if deg else m


def poly(w, h, pts):
    m = blank(w, h)
    cv2.fillPoly(m, [np.array(pts, np.int32)], 255, lineType=cv2.LINE_AA)
    return m


def ellipse(w, h, cx, cy, rx, ry, deg=0):
    m = blank(w, h)
    cv2.ellipse(m, (int(cx), int(cy)), (int(rx), int(ry)), deg, 0, 360, 255, -1, cv2.LINE_AA)
    return m


def blob(w, h, cx, cy, r, wob=0.35, seed=None):
    """Organic shape: a disc pushed around by thresholded noise, kept as the largest contour."""
    base = np.zeros((h, w), np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    n = fractal(h, w, base=max(8, int(r / 1.4)), octaves=3, seed=seed)
    base = 1 - d + wob * n
    _, th = cv2.threshold(base, 0, 255, cv2.THRESH_BINARY)
    th = th.astype(np.uint8)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    m = blank(w, h)
    if cnts:
        c = max(cnts, key=cv2.contourArea)
        cv2.drawContours(m, [c], -1, 255, -1)
    return m


def lines_mask(w, h, x0, y0, x1, rows, gap, thick, ragged=0.35, seed=0):
    """Grey bars standing in for set text on a sheet."""
    rng = np.random.default_rng(seed)
    m = np.zeros((h, w), np.float32)
    for i in range(rows):
        y = y0 + i * gap
        end = x1 - rng.uniform(0, ragged) * (x1 - x0) if rng.random() > 0.25 else x1
        cv2.rectangle(m, (int(x0), int(y)), (int(end), int(y + thick)), 1, -1)
    return m


# ---------------------------------------------------------------- pieces
def ad_sheet(name, col, seed):
    """A torn newspaper-style job ad clipping, with a tape strip. Text is HTML, not baked."""
    W, H = 560, 700
    c = Canvas(W, H)
    m = rect(W, H, 44, 52, W - 40, H - 46)
    pm, rim = torn(m, amp=10, base=36, rim=8, seed=seed)
    c.piece(pm, paper(H, W, col, seed=seed), rim=rim, sh=dict(dx=8, dy=14, blur=12, op=0.24), seed=seed + 9)
    # printed rule under the masthead
    band = rect(W, H, 84, 150, W - 84, 154)
    c.ink(soft(band) * pm, INK, 0.55)
    # tape strip, translucent, slightly torn ends
    t = rect(W, H, W / 2 - 80, 24, W / 2 + 80, 84, deg=-4)
    tm, _ = torn(t, amp=4, base=10, rim=0, seed=seed + 3)
    c.over(paper(H, W, (240, 236, 222), grain=0.02, fibres=False), tm * 0.72)
    return c


def copy_sheet(seed=3):
    """A photocopy: grey, toner specks, a dark scanner edge, everything a little crooked."""
    W, H = 520, 700
    c = Canvas(W, H)
    m = rect(W, H, 36, 30, W - 36, H - 40)
    pm = soft(m)
    face = paper(H, W, PAL["copy"], grain=0.05, mottle=0.05, seed=seed)
    c.piece(pm, face, sh=dict(dx=6, dy=10, blur=9, op=0.22))
    rng = np.random.default_rng(seed)
    tone = np.zeros((H, W), np.float32)
    # scanner edge streak and toner noise
    cv2.rectangle(tone, (W - 64, 30), (W - 50, H - 40), 0.35, -1)
    tone = cv2.GaussianBlur(tone, (0, 0), 3)
    specks = (rng.random((H, W)) > 0.9965).astype(np.float32)
    specks = cv2.dilate(specks, np.ones((2, 2), np.uint8))
    tone += specks * 0.8
    # crooked text bars
    bars = lines_mask(W, H, 80, 190, W - 90, 16, 26, 9, seed=seed)
    cv2.rectangle(bars, (80, 80), (300, 108), 1, -1)
    cv2.rectangle(bars, (80, 124), (240, 136), 1, -1)
    bars = rot(bars, 0.9)
    bars = cv2.GaussianBlur(bars, (0, 0), 1.1)
    c.ink(np.clip(tone + bars * 0.85, 0, 1) * pm, PAL["toner"], 0.9)
    return c


def cut_sheet(col, seed):
    """A CV cut to fit: white sheet, scissor-cut edges, a coloured cut band across the top."""
    W, H = 520, 700
    c = Canvas(W, H)
    m = rect(W, H, 34, 28, W - 34, H - 40)
    pm = cut(m, eps=0.004, jitter=1.4)
    c.piece(pm, paper(H, W, PAL["white"], grain=0.025, seed=seed), sh=dict(dx=6, dy=12, blur=11, op=0.22))
    # coloured band with a scissor-snipped lower edge: random walk, then approxPolyDP snips
    rng = np.random.default_rng(seed)
    xs = np.linspace(20, W - 20, 14)
    ys = 120 + np.cumsum(rng.normal(0, 9, len(xs)))
    ys = np.clip(ys - (ys.mean() - 128), 96, 160)
    pts = [(20, 10), (W - 20, 10)] + list(zip(xs[::-1], ys[::-1]))
    b = poly(W, H, pts)
    band = cut(b, eps=0.006, jitter=1.0) * pm
    c.over(paper(H, W, col, seed=seed + 1), band)
    return c


def scissors(seed=5, handle="coral"):
    W, H = 760, 420
    c = Canvas(W, H)
    piv = (430, 214)
    # blades: tapered quads from behind the pivot to each tip
    def blade(tip, side):
        d = np.array(tip, np.float32) - np.array(piv, np.float32)
        L = float(np.linalg.norm(d)); d /= L
        n = np.array([-d[1], d[0]], np.float32) * side
        p = np.array(piv, np.float32)
        return [tuple(p - 40 * d + 30 * n), tuple(p + 0.4 * L * d + 38 * n), tuple(tip),
                tuple(p + 0.5 * L * d - 6 * n), tuple(p - 40 * d - 14 * n)]
    b1 = poly(W, H, blade((W - 20, 150), -1))
    b2 = poly(W, H, blade((W - 22, 286), 1))
    for i, b in enumerate((b2, b1)):
        bm = cut(b, eps=0.006, jitter=0.6)
        c.piece(bm, paper(H, W, PAL["steel"] if i else PAL["steel2"], grain=0.02, fibres=False, seed=seed + i),
                sh=dict(dx=6, dy=10, blur=8, op=0.22))
        if i:
            spine = cv2.subtract(b, cv2.erode(b, np.ones((9, 9), np.uint8)))
            c.ink(soft(cv2.bitwise_and(spine, poly(W, H, [(0, 0), (W, 0), (W, 214), (0, 214)]))) * bm, (255, 255, 255), 0.6)
    # handles: torn rings
    for (cx, cy, deg) in ((250, 128, -20), (250, 300, 20)):
        outer = ellipse(W, H, cx, cy, 128, 82, deg)
        inner = ellipse(W, H, cx + 8, cy, 82, 44, deg)
        ring = cv2.subtract(outer, inner)
        neck = poly(W, H, [(cx + 100, cy - 26), (piv[0] - 10, piv[1] - 18), (piv[0] - 10, piv[1] + 18), (cx + 100, cy + 26)]) if cy < piv[1] else \
            poly(W, H, [(cx + 100, cy + 26), (piv[0] - 10, piv[1] + 18), (piv[0] - 10, piv[1] - 18), (cx + 100, cy - 26)])
        hm, rim = torn(cv2.bitwise_or(ring, neck), amp=5, base=18, rim=5, seed=seed + cy)
        c.piece(hm, paper(H, W, PAL[handle], seed=seed + cy), rim=rim, sh=dict(dx=6, dy=10, blur=9, op=0.24))
    # pivot rivet
    c.piece(soft(ellipse(W, H, piv[0], piv[1], 15, 15)), paper(H, W, INK if handle != "ink" else PAL["marigold"], fibres=False), sh=dict(dx=2, dy=3, blur=3, op=0.3))
    return c


def two_pages(seed=31):
    W, H = 560, 520
    c = Canvas(W, H)
    for i, (x, y, deg, col) in enumerate(((70, 70, -6, PAL["white"]), (190, 40, 5, PAL["white"]))):
        m = rot(rect(W, H, x, y, x + 280, y + 380), deg, x + 140, y + 190)
        pm = cut(m, eps=0.004, jitter=1.0)
        c.piece(pm, paper(H, W, col, grain=0.02, seed=seed + i), sh=dict(dx=6, dy=12, blur=10, op=0.22))
        bars = rot(lines_mask(W, H, x + 36, y + 110, x + 244, 9, 24, 7, seed=seed + i), deg, x + 140, y + 190)
        c.ink(cv2.GaussianBlur(bars, (0, 0), 0.8) * pm, INK, 0.28)
        head = rot(rect(W, H, x + 36, y + 40, x + 190, y + 70), deg, x + 140, y + 190)
        c.ink(soft(head) * pm, INK, 0.85)
    # coral tag: "2"
    tag = cut(blob(W, H, 440, 410, 62, wob=0.25, seed=seed), eps=0.02, jitter=1)
    c.piece(tag, paper(H, W, PAL["coral"], seed=seed + 4), sh=dict(dx=4, dy=8, blur=7))
    return c


def clipping(seed=41):
    W, H = 560, 520
    c = Canvas(W, H)
    m = rot(rect(W, H, 90, 70, 470, 450), -5)
    pm, rim = torn(m, amp=9, base=30, rim=8, seed=seed)
    c.piece(pm, paper(H, W, PAL["teal"], seed=seed), rim=rim, sh=dict(dx=8, dy=12, blur=11))
    bars = rot(lines_mask(W, H, 140, 200, 420, 8, 26, 8, seed=seed), -5)
    c.ink(cv2.GaussianBlur(bars, (0, 0), 0.9) * pm, PAL["white"], 0.55)
    head = rot(rect(W, H, 140, 120, 360, 160), -5)
    c.ink(soft(head) * pm, PAL["white"], 0.95)
    # paper clip: two nested rounded loops of navy paper strip
    clip = blank(W, H)
    cv2.ellipse(clip, (190, 110), (34, 84), -5, 0, 360, 255, 12, cv2.LINE_AA)
    cv2.ellipse(clip, (192, 128), (20, 58), -5, 0, 360, 255, 10, cv2.LINE_AA)
    c.piece(soft(clip, 0.8), paper(H, W, INK, fibres=False), sh=dict(dx=3, dy=5, blur=4, op=0.3))
    return c


def redacted_card(seed=51):
    W, H = 600, 420
    c = Canvas(W, H)
    m = rot(rect(W, H, 60, 60, 540, 360), 3)
    pm = cut(m, eps=0.004, jitter=1)
    c.piece(pm, paper(H, W, PAL["white"], seed=seed), sh=dict(dx=8, dy=12, blur=11))
    for i, (y, x1) in enumerate(((128, 380), (190, 470), (236, 440), (282, 330))):
        bar = rot(rect(W, H, 104, y - 14, x1, y + 14), 3 + RNG.uniform(-1.5, 1.5), W / 2, H / 2)
        bm, _ = torn(bar, amp=3, base=8, rim=0, seed=seed + i)
        c.piece(bm * pm, paper(H, W, INK if i else PAL["coral"], fibres=False, seed=seed + i),
                shadow=True, sh=dict(dx=2, dy=3, blur=3, op=0.25))
    return c


def scraps(seed=81):
    """Confetti offcuts for the hero: scissor-cut blobs and torn bits, each its own file."""
    out = {}
    specs = [("scrap-star", "marigold", "star"), ("scrap-tri", "teal", "tri"), ("scrap-dot", "coral", "dot")]
    for i, (name, col, kind) in enumerate(specs):
        W = H = 220
        c = Canvas(W, H)
        if kind == "star":
            pts = []
            for k in range(10):
                r = 86 if k % 2 == 0 else 38
                a = -math.pi / 2 + k * math.pi / 5
                pts.append((110 + r * math.cos(a), 110 + r * math.sin(a)))
            m = cut(poly(W, H, pts), eps=0.003, jitter=1.2)
        elif kind == "tri":
            m = cut(poly(W, H, [(30, 180), (110, 30), (190, 170)]), eps=0.003, jitter=1.5)
        else:
            m, _ = torn(ellipse(W, H, 110, 110, 70, 70), amp=6, base=14, rim=0, seed=seed + i)
        c.piece(m, paper(H, W, PAL[col], seed=seed + i), sh=dict(dx=5, dy=8, blur=7, op=0.22))
        out[name] = c
    return out


def hero_ground(seed=91):
    """A big torn marigold field behind the hero collage, with a sky offcut."""
    W, H = 1240, 1080
    c = Canvas(W, H)
    g = blob(W, H, 640, 540, 470, wob=0.22, seed=seed)
    gm, rim = torn(g, amp=14, base=60, rim=10, seed=seed)
    c.piece(gm, paper(H, W, PAL["marigold"], seed=seed), rim=rim, sh=dict(dx=10, dy=16, blur=18, op=0.18))
    s = cut(blob(W, H, 980, 220, 170, wob=0.4, seed=seed + 1), eps=0.012, jitter=1.5)
    c.piece(s, paper(H, W, PAL["sky"], seed=seed + 1), sh=dict(dx=6, dy=10, blur=10, op=0.18))
    return c


def torn_edge(seed=101):
    """A wide torn edge used as a CSS mask between sections (alpha only matters)."""
    W, H = 2400, 90
    m = rect(W, H, -40, 34, W + 40, H + 40)
    pm, _ = torn(m, amp=12, base=46, rim=0, seed=seed)
    img = Image.fromarray((np.dstack([np.zeros((H, W, 3)), pm]) * 255).astype(np.uint8), "RGBA")
    return img


def hand_cut_arrow(seed=111):
    W, H = 360, 200
    c = Canvas(W, H)
    m = poly(W, H, [(20, 82), (230, 70), (226, 30), (340, 100), (228, 170), (232, 126), (22, 120)])
    pm = cut(m, eps=0.004, jitter=1.4)
    c.piece(pm, paper(H, W, PAL["coral"], seed=seed), sh=dict(dx=5, dy=8, blur=7))
    return c


def folder(seed=121):
    """The applications folder: kraft back, three coloured sheets with tabs, kraft front."""
    W, H = 640, 520
    c = Canvas(W, H)
    back = poly(W, H, [(60, 120), (250, 120), (280, 90), (580, 90), (580, 470), (60, 470)])
    c.piece(cut(back, eps=0.004, jitter=1), paper(H, W, PAL["kraft"], seed=seed), sh=dict(dx=8, dy=14, blur=14, op=0.22))
    for i, (col, x, deg) in enumerate(((PAL["lilac"], 110, -5), (PAL["teal"], 170, 2), (PAL["marigold"], 230, -2))):
        sheet = rot(rect(W, H, x, 60 + i * 26, x + 300, 440), deg, x + 150, 250)
        tab = rot(rect(W, H, x + 40 + i * 60, 40 + i * 26, x + 120 + i * 60, 80 + i * 26), deg, x + 150, 250)
        m = cv2.bitwise_or(sheet, tab)
        sm, rim = torn(m, amp=5, base=18, rim=5, seed=seed + i)
        c.piece(sm, paper(H, W, col, seed=seed + i), rim=rim, sh=dict(dx=5, dy=8, blur=8, op=0.2))
        bars = rot(lines_mask(W, H, x + 30, 160 + i * 26, x + 250, 5, 22, 7, seed=seed + i), deg, x + 150, 250)
        c.ink(cv2.GaussianBlur(bars, (0, 0), 0.8) * sm, INK, 0.22)
    front = poly(W, H, [(40, 250), (600, 230), (612, 480), (52, 490)])
    fm = cut(front, eps=0.004, jitter=1.2)
    c.piece(fm, paper(H, W, (214, 180, 130), seed=seed + 9), sh=dict(dx=6, dy=12, blur=12, op=0.26))
    label = rot(rect(W, H, 240, 330, 420, 380), -2)
    c.piece(cut(label, eps=0.004, jitter=0.8) * fm, paper(H, W, PAL["white"], seed=seed + 10), sh=dict(dx=2, dy=3, blur=3, op=0.2))
    return c


def spotlight(seed=131):
    """Best foot forward: a CV sheet in a marigold spotlight, with a coral star on its best line."""
    W, H = 600, 600
    c = Canvas(W, H)
    glow = blob(W, H, 300, 300, 250, wob=0.18, seed=seed)
    gm, grim = torn(glow, amp=10, base=40, rim=8, seed=seed)
    c.piece(gm, paper(H, W, PAL["marigold"], seed=seed), rim=grim, sh=dict(dx=6, dy=10, blur=14, op=0.14))
    sheet = rot(rect(W, H, 170, 110, 430, 500), -4, 300, 300)
    sm = cut(sheet, eps=0.004, jitter=1)
    c.piece(sm, paper(H, W, PAL["white"], seed=seed + 1), sh=dict(dx=8, dy=14, blur=12, op=0.24))
    hi = rot(rect(W, H, 196, 186, 404, 232), -4, 300, 300)
    c.ink(soft(hi) * sm, PAL["coral"], 0.32)
    bars = rot(lines_mask(W, H, 200, 140, 400, 1, 26, 12, seed=seed), -4, 300, 300)
    c.ink(cv2.GaussianBlur(bars, (0, 0), 0.8) * sm, INK, 0.85)
    bars = rot(lines_mask(W, H, 206, 202, 396, 1, 26, 9, seed=seed + 1), -4, 300, 300)
    c.ink(cv2.GaussianBlur(bars, (0, 0), 0.8) * sm, INK, 0.7)
    bars = rot(lines_mask(W, H, 200, 270, 400, 8, 26, 7, seed=seed + 2), -4, 300, 300)
    c.ink(cv2.GaussianBlur(bars, (0, 0), 0.8) * sm, INK, 0.25)
    pts = []
    for k in range(10):
        r = 64 if k % 2 == 0 else 28
        a = -math.pi / 2 + k * math.pi / 5
        pts.append((430 + r * math.cos(a), 190 + r * math.sin(a)))
    c.piece(cut(rot(poly(W, H, pts), 12, 430, 190), eps=0.003, jitter=1.2), paper(H, W, PAL["coral"], seed=seed + 3), sh=dict(dx=5, dy=9, blur=8, op=0.26))
    return c


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = {
        "ad-lilac": lambda: ad_sheet("lilac", PAL["lilac"], 201),
        "ad-teal": lambda: ad_sheet("teal", PAL["teal"], 202),
        "ad-marigold": lambda: ad_sheet("marigold", PAL["marigold"], 203),
        "copy": lambda: copy_sheet(3),
        "cv-lilac": lambda: cut_sheet(PAL["lilac"], 301),
        "cv-teal": lambda: cut_sheet(PAL["teal"], 302),
        "cv-marigold": lambda: cut_sheet(PAL["marigold"], 303),
        "scissors": scissors,
        "scissors-ink": lambda: scissors(handle="ink"),
        "pages": two_pages,
        "clipping": clipping,
        "redacted": redacted_card,
        "ground": hero_ground,
        "arrow": hand_cut_arrow,
        "folder": folder,
        "spotlight": spotlight,
    }
    for name, fn in jobs.items():
        fn().save(OUT / f"{name}.webp")
    for name, c in scraps().items():
        c.save(OUT / f"{name}.webp")
    # The edge is a CSS mask: only its alpha matters, so lossless keeps the tear exact.
    torn_edge().save(OUT / "edge.webp", "WEBP", lossless=True, method=6)
    written = sorted(p.stem for p in OUT.glob("*.webp"))
    assert written == sorted(NAMES), f"wrote {written}, NAMES says {sorted(NAMES)}"
    print("wrote", len(written), "files to", OUT)


if __name__ == "__main__":
    main()
