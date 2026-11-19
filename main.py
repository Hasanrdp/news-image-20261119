"""The Daily Globe -- front page for Thursday 19 November 2026 (v2).

Draws a 1024x1024 PNG of the day's world news, pure standard library,
no network, deterministic (two runs write identical bytes).

Design notes (v2 fixes the v1 craft problems):
- Everything is rendered at 2x supersampling and box-downsampled, so text
  and illustration edges are smooth instead of chunky 8-bit bitmaps.
- Text is a hand-built single-stroke geometric font (clean, even strokes),
  and the masthead is a filled serif nameplate drawn as polygons.
- Every story image is a real illustration: gradients, layered shapes,
  silhouettes and detail, each depicting its story.
- Layout is a tight newspaper grid: nameplate, lead story with hero image,
  three mid stories, two lower stories, an "also today" strip.

The facts are the real 19 November 2026 headlines: GTA VI launches
worldwide; Hakeem Jeffries nominated for US Speaker; Cyclone Akvan nears
India's east coast; Voyager 1 one light-day out; EU 45bn-euro loan for
Ukraine; US-Iran strikes widen in the Gulf; ICJ Myanmar ruling; Pew on
Islam by 2035; Fed minutes; Trump, Xi and Putin to meet in Shenzhen.
"""

import math
import os
import random
import struct
import sys
import zlib
from pathlib import Path

SS = 2                      # supersampling factor
W = 1024 * SS               # canvas width in render pixels
H = 1024 * SS               # canvas height in render pixels
FW, FH = 1024, 1024         # final size

PAPER = (246, 241, 229)
INK = (26, 26, 24)
RED = (178, 35, 27)
GREY = (110, 105, 95)
RULE = (40, 38, 34)


# ---------------------------------------------------------------- PNG output

def _chunk(kind, data):
    c = struct.pack(">I", len(data)) + kind + data
    return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path, w, h, rgb):
    """rgb: bytes of w*h*3. Writes a plain 8-bit RGB PNG."""
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", comp) + _chunk(b"IEND", b"")
    Path(path).write_bytes(png)
    return len(png)


# ---------------------------------------------------------------- canvas

class Canvas:
    def __init__(self, w, h, color):
        self.w, self.h = w, h
        self.px = bytearray(bytes(color) * (w * h))

    def _idx(self, x, y):
        return (int(y) * self.w + int(x)) * 3

    def set(self, x, y, color, alpha=1.0):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            if alpha >= 1.0:
                self.px[i:i + 3] = bytes(color)
            else:
                a = alpha
                self.px[i] = int(self.px[i] * (1 - a) + color[0] * a)
                self.px[i + 1] = int(self.px[i + 1] * (1 - a) + color[1] * a)
                self.px[i + 2] = int(self.px[i + 2] * (1 - a) + color[2] * a)

    def hline(self, x0, x1, y, color, alpha=1.0):
        """Fill one horizontal run, clipped. Fast path for opaque."""
        if y < 0 or y >= self.h:
            return
        x0 = max(0, int(math.floor(x0)))
        x1 = min(self.w, int(math.ceil(x1)))
        if x1 <= x0:
            return
        i0 = self._idx(x0, y)
        n = x1 - x0
        if alpha >= 1.0:
            self.px[i0:i0 + n * 3] = bytes(color) * n
        else:
            a = alpha
            r, g, b = color
            for k in range(n):
                i = i0 + k * 3
                self.px[i] = int(self.px[i] * (1 - a) + r * a)
                self.px[i + 1] = int(self.px[i + 1] * (1 - a) + g * a)
                self.px[i + 2] = int(self.px[i + 2] * (1 - a) + b * a)

    def rect(self, x0, y0, x1, y1, color, alpha=1.0):
        y0i = max(0, int(math.floor(y0)))
        y1i = min(self.h, int(math.ceil(y1)))
        for y in range(y0i, y1i):
            self.hline(x0, x1, y, color, alpha)

    def vgrad(self, x0, y0, x1, y1, top, bottom):
        """Vertical linear gradient fill."""
        y0i = max(0, int(math.floor(y0)))
        y1i = min(self.h, int(math.ceil(y1)))
        span = max(1, y1 - y0)
        for y in range(y0i, y1i):
            t = (y - y0) / span
            c = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3))
            self.hline(x0, x1, y, c)

    def disk(self, cx, cy, r, color, alpha=1.0):
        r = float(r)
        if r <= 0:
            return
        y0 = max(0, int(math.floor(cy - r)))
        y1 = min(self.h, int(math.ceil(cy + r)))
        for y in range(y0, y1 + 1):
            dy = y + 0.5 - cy
            dx = math.sqrt(max(0.0, r * r - dy * dy))
            self.hline(cx - dx, cx + dx, y, color, alpha)

    def thick_line(self, x0, y0, x1, y1, w, color, alpha=1.0):
        """Thick line with round caps, stamped as disks."""
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        r = w / 2.0
        if length < 0.5:
            self.disk(x0, y0, r, color, alpha)
            return
        step = max(1.0, r * 0.8)
        n = int(length / step) + 1
        for k in range(n + 1):
            t = k / n
            self.disk(x0 + dx * t, y0 + dy * t, r, color, alpha)

    def poly(self, pts, color, alpha=1.0):
        """Scanline fill of a polygon (even-odd)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(math.floor(min(ys))))
        y1 = min(self.h, int(math.ceil(max(ys))))
        n = len(pts)
        for y in range(y0, y1):
            yc = y + 0.5
            xs = []
            for k in range(n):
                x0, y0p = pts[k]
                x1, y1p = pts[(k + 1) % n]
                if (y0p <= yc < y1p) or (y1p <= yc < y0p):
                    t = (yc - y0p) / (y1p - y0p)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.hline(xs[k], xs[k + 1], y, color, alpha)

    def ellipse(self, cx, cy, rx, ry, color, alpha=1.0):
        y0 = max(0, int(math.floor(cy - ry)))
        y1 = min(self.h, int(math.ceil(cy + ry)))
        for y in range(y0, y1 + 1):
            dy = (y + 0.5 - cy) / ry
            if abs(dy) >= 1:
                continue
            dx = rx * math.sqrt(1 - dy * dy)
            self.hline(cx - dx, cx + dx, y, color, alpha)

    def downsample(self):
        """2x2 box average to FW x FH. Returns bytes."""
        out = bytearray(FW * FH * 3)
        src = self.px
        w3 = self.w * 3
        for y in range(FH):
            sy = y * SS
            for x in range(FW):
                sx = x * SS
                o = (y * FW + x) * 3
                for c in range(3):
                    s = 0
                    for dy in range(SS):
                        base = (sy + dy) * w3 + sx * 3 + c
                        for dx in range(SS):
                            s += src[base + dx * 3]
                    out[o + c] = (s + 2) // 4
        return bytes(out)


def arc_pts(cx, cy, rx, ry, a0, a1, n=24):
    """Points along an ellipse arc, angles in degrees, y down (clockwise)."""
    if a1 < a0:
        a1 += 360.0
    pts = []
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def star_pts(cx, cy, r_out, r_in, points=5, rot=-90.0):
    pts = []
    for k in range(points * 2):
        r = r_out if k % 2 == 0 else r_in
        a = math.radians(rot + k * 180.0 / points)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts

# ---------------------------------------------------------------- stroke font
# Single-stroke geometric font. Grid: x 0..16 (advance), cap top y=0,
# baseline y=16, x-height top y=5, descender y=20. Each glyph is
# (advance, [paths]); a path is a list of (x, y) points, drawn as one
# thick polyline. A one-point path draws a dot.

def _A(cx, cy, rx, ry, a0, a1, n=20):
    return arc_pts(cx, cy, rx, ry, a0, a1, n)


_G = {}


def _g(ch, adv, paths):
    _G[ch] = (adv, paths)


# ---- uppercase
_g("A", 16, [[(0, 16), (8, 0), (16, 16)], [(4.5, 10), (11.5, 10)]])
_g("B", 16, [[(0, 16), (0, 0), (10, 0)] + _A(10, 4, 4.5, 4, -90, 90, 10) +
             [(10, 8), (0, 8)] + _A(10, 12, 4.5, 4, -90, 90, 10) +
             [(10, 16), (0, 16)]])
_g("C", 16, [_A(9, 8, 8, 8, 55, 305)])
_g("D", 16, [[(0, 16), (0, 0), (9, 0)] + _A(9, 8, 8, 8, -90, 90, 14) +
             [(9, 16), (0, 16)]])
_g("E", 16, [[(15, 0), (0, 0), (0, 16), (15, 16)], [(0, 8), (11, 8)]])
_g("F", 16, [[(15, 0), (0, 0), (0, 16)], [(0, 8), (11, 8)]])
_g("G", 16, [_A(9, 8, 8, 8, 50, 310), [(16.5, 8), (11, 8), (11, 13)]])
_g("H", 16, [[(0, 0), (0, 16)], [(16, 0), (16, 16)], [(0, 8), (16, 8)]])
_g("I", 10, [[(5, 0), (5, 16)], [(1.5, 0), (8.5, 0)], [(1.5, 16), (8.5, 16)]])
_g("J", 15, [[(12, 0), (12, 11)] + _A(7, 11, 5, 5, 0, 180, 12),
             [(8, 0), (13, 0)]])
_g("K", 16, [[(0, 0), (0, 16)], [(15, 0), (1, 8)], [(7, 10), (15, 16)]])
_g("L", 15, [[(0, 0), (0, 16), (14, 16)]])
_g("M", 18, [[(0, 16), (0, 0), (9, 7), (18, 0), (18, 16)]])
_g("N", 17, [[(0, 16), (0, 0), (17, 16), (17, 0)]])
_g("O", 17, [_A(8.5, 8, 8, 8, 0, 360)])
_g("P", 16, [[(0, 16), (0, 0), (10, 0)] + _A(10, 4, 4.5, 4, -90, 90, 10) +
             [(10, 8), (0, 8)]])
_g("Q", 17, [_A(8.5, 8, 8, 8, 0, 360), [(10.5, 11), (16.5, 17)]])
_g("R", 16, [[(0, 16), (0, 0), (10, 0)] + _A(10, 4, 4.5, 4, -90, 90, 10) +
             [(10, 8), (0, 8)], [(8, 8), (16, 16)]])
_g("S", 16, [[(14, 2.5), (10, 0), (5, 1), (2.5, 4), (4.5, 7), (9, 8),
              (13, 9), (14.5, 12), (12.5, 15), (8, 16), (4, 15), (2, 13)]])
_g("T", 16, [[(0, 0), (16, 0)], [(8, 0), (8, 16)]])
_g("U", 17, [[(0, 0), (0, 12)] + _A(8.5, 12, 8.5, 4, 0, 180, 12)[::-1] +
             [(17, 12), (17, 0)]])
_g("V", 17, [[(0, 0), (8.5, 16), (17, 0)]])
_g("W", 22, [[(0, 0), (4.5, 16), (11, 5), (17.5, 16), (22, 0)]])
_g("X", 16, [[(0, 0), (16, 16)], [(16, 0), (0, 16)]])
_g("Y", 16, [[(0, 0), (8, 8), (16, 0)], [(8, 8), (8, 16)]])
_g("Z", 16, [[(0, 0), (16, 0), (0, 16), (16, 16)]])

# ---- lowercase
_g("a", 15, [_A(7.5, 10.5, 6.5, 5.5, 0, 360),
             [(14, 5.5), (14, 16)]])
_g("b", 15, [[(0, 0), (0, 16)], _A(8, 11, 6.5, 5, 0, 360)])
_g("c", 14, [_A(7.5, 10.5, 7, 5.5, 60, 300)])
_g("d", 15, [_A(7, 10.5, 6.5, 5.5, 0, 360), [(13.5, 0), (13.5, 16)]])
_g("e", 15, [_A(7.5, 10.5, 6.5, 5.5, 55, 305), [(1.5, 11), (13.5, 11)]])
_g("f", 11, [[(8, 0), (8, 16)] + _A(8, 4, 4, 4, 180, 270, 8),
             [(3, 7), (12, 7)]])
_g("g", 15, [_A(7.5, 10.5, 6.5, 5.5, 0, 360),
             [(14, 11), (14, 20), (9, 20)]])
_g("h", 15, [[(0, 0), (0, 16)],
             [(0, 11)] + _A(7.5, 11, 7.5, 6, 180, 360, 12) +
             [(15, 11), (15, 16)]])
_g("i", 7, [[(3.5, 5), (3.5, 16)], [(3.5, 1.5)]])
_g("j", 8, [[(4.5, 5), (4.5, 19), (1.5, 19)], [(4.5, 1.5)]])
_g("k", 15, [[(0, 0), (0, 16)], [(13, 5), (1, 11)], [(6, 12), (13, 16)]])
_g("l", 7, [[(3.5, 0), (3.5, 16)]])
_g("m", 22, [[(0, 5), (0, 16)],
             [(0, 9)] + _A(4.5, 9, 4.5, 4, 180, 360, 10) +
             [(9, 9), (9, 16)],
             [(9, 9)] + _A(13.5, 9, 4.5, 4, 180, 360, 10) +
             [(18, 9), (18, 16)]])
_g("n", 15, [[(0, 5), (0, 16)],
             [(0, 9)] + _A(7.5, 9, 7.5, 4, 180, 360, 12) +
             [(15, 9), (15, 16)]])
_g("o", 15, [_A(7.5, 10.5, 6.5, 5.5, 0, 360)])
_g("p", 15, [[(0, 5), (0, 20)], _A(8, 10.5, 6.5, 5.5, 0, 360)])
_g("q", 15, [_A(7, 10.5, 6.5, 5.5, 0, 360), [(13.5, 5), (13.5, 20)]])
_g("r", 12, [[(0, 5), (0, 16)],
             [(0, 8)] + _A(6, 8, 5, 3.5, 180, 360, 10)])
_g("s", 14, [[(12, 6.5), (8, 5), (4.5, 6), (3, 8.5), (5, 10.5),
              (9.5, 11.5), (12, 13.5), (10, 15.5), (5.5, 16), (3, 14.5)]])
_g("t", 11, [[(6, 2), (6, 16), (9, 16)] + _A(9, 13, 3, 3, 0, 90, 6),
             [(2, 7), (10, 7)]])
_g("u", 15, [[(0, 5), (0, 13)] + _A(7.5, 13, 7.5, 3, 0, 180, 12)[::-1] +
             [(15, 13), (15, 5)]])
_g("v", 15, [[(0, 5), (7.5, 16), (15, 5)]])
_g("w", 21, [[(0, 5), (4, 16), (10.5, 8), (17, 16), (21, 5)]])
_g("x", 14, [[(0, 5), (14, 16)], [(14, 5), (0, 16)]])
_g("y", 15, [[(0, 5), (7.5, 14), (15, 5)], [(7.5, 14), (7.5, 20)]])
_g("z", 14, [[(0, 5), (14, 5), (0, 16), (14, 16)]])

# ---- digits
_g("0", 16, [_A(8, 8, 7, 8, 0, 360)])
_g("1", 13, [[(4, 3), (8, 0), (8, 16)], [(4, 16), (12, 16)]])
_g("2", 15, [[(1, 6), (3, 2), (7, 0), (11, 1), (13.5, 4), (12.5, 7),
              (4, 16), (14.5, 16)]])
_g("3", 15, [[(2, 1), (8, 0), (12, 1), (14, 4), (12, 7), (8, 8),
              (12, 9), (14, 12), (12, 15), (8, 16), (3, 15)]])
_g("4", 15, [[(11, 0), (11, 16)], [(0, 11), (13, 11)], [(11, 0), (0, 11)]])
_g("5", 15, [[(14, 0), (2, 0), (2, 7), (10, 7), (14, 9), (14, 13),
              (11, 16), (5, 16), (2, 14)]])
_g("6", 15, [[(13, 0), (7, 1), (3, 5), (2, 9), (4, 14), (8, 16),
              (12, 15), (14, 11), (13, 7), (9, 6), (5, 7)]])
_g("7", 15, [[(0, 0), (15, 0), (7, 16)]])
_g("8", 15, [_A(7.5, 4.5, 6, 4.5, 0, 360), _A(7.5, 11.5, 6.5, 4.5, 0, 360)])
_g("9", 15, [_A(7.5, 5, 6.5, 5, 0, 360),
             [(14, 5), (14, 13), (11, 16), (6, 16), (3, 14)]])

# ---- punctuation
_g(" ", 8, [])
_g(".", 7, [[(3.5, 14.8)]])
_g(",", 7, [[(4, 14), (3.5, 17.5), (1, 20)]])
_g(":", 7, [[(3.5, 6)], [(3.5, 13.5)]])
_g(";", 7, [[(3.5, 6)], [(4, 13.5), (3.5, 17), (1, 20)]])
_g("!", 7, [[(3.5, 0), (3.5, 11)], [(3.5, 14.8)]])
_g("?", 14, [[(2, 6), (3, 2), (7, 0), (11, 1), (12.5, 4), (10.5, 7),
              (7.5, 8), (7.5, 11)], [(7.5, 14.8)]])
_g("'", 6, [[(3.5, 0), (2, 5)]])
_g('"', 10, [[(3, 0), (2, 4)], [(8, 0), (7, 4)]])
_g("-", 12, [[(1, 8), (11, 8)]])
_g("–", 14, [[(1, 8), (13, 8)]])
_g("—", 16, [[(0, 8), (16, 8)]])
_g("(", 9, [_A(11, 8, 6, 8, 100, 260)])
_g(")", 9, [_A(5, 8, 6, 8, -80, 80)])
_g("/", 13, [[(2, 16), (11, 0)]])
_g("&", 16, [[(12, 5), (9, 4), (5, 6), (4, 9), (7, 11), (12, 16),
              (14, 11), (11, 8), (7, 9), (5, 12), (6, 15), (10, 16)]])
_g("%", 17, [[(3, 0), (14, 16)], _A(5, 4, 2.6, 2.6, 0, 360),
             _A(12, 12, 2.6, 2.6, 0, 360)])
_g("+", 14, [[(7, 3), (7, 13)], [(2, 8), (12, 8)]])
_g("=", 14, [[(2, 6), (12, 6)], [(2, 11), (12, 11)]])
_g("$", 15, [[(13, 2.5), (9, 0), (5, 1), (3, 4), (5, 7), (9, 8),
              (12, 9), (13, 12), (11, 15), (7, 16), (4, 15), (2.5, 13)],
             [(7.5, -1), (7.5, 17)]])
_g("#", 16, [[(6, 0), (5, 16)], [(11, 0), (10, 16)],
             [(0, 6), (16, 6)], [(0, 11), (16, 11)]])
_g("•", 8, [[(4, 8)]])
_g("*", 14, [[(7, 1), (7, 15)], [(1, 5), (13, 11)], [(13, 5), (1, 11)]])
_g("£", 14, [[(12, 1), (7, 0), (3, 2), (2, 5), (3, 8), (2, 11),
              (4, 14), (3, 16), (12, 16)], [(1, 8), (9, 8)]])


def glyph(ch):
    return _G.get(ch, _G.get("?", (14, [[(2, 6), (3, 2), (7, 0), (11, 1),
                                        (12.5, 4), (10.5, 7), (7.5, 8),
                                        (7.5, 11)], [(7.5, 14.8)]])))


def text_width(s, size, track=0.0):
    """Width of s in final px at cap-height `size`."""
    sc = size / 16.0
    w = 0.0
    for ch in s:
        adv, _ = glyph(ch)
        w += adv * sc + track
    return w - track if s else 0.0


def draw_text(cv, x, y, s, size, color, weight=1.0, track=0.0, align="l"):
    """Draw text at final coords (x, y = top of cap height)."""
    sc = size / 16.0 * SS
    wpx = size * 0.145 * weight * SS
    if align == "c":
        x -= text_width(s, size, track) / 2.0
    elif align == "r":
        x -= text_width(s, size, track)
    cx = x * SS
    cy = y * SS
    for ch in s:
        adv, paths = glyph(ch)
        # side bearings: shrink ink to 84% of the advance, centred
        ox = cx + adv * sc * 0.08
        sx = sc * 0.84
        for path in paths:
            if len(path) == 1:
                px, py = path[0]
                cv.disk(ox + px * sx, cy + py * sc, wpx * 0.62, color)
                continue
            for k in range(len(path) - 1):
                x0, y0 = path[k]
                x1, y1 = path[k + 1]
                cv.thick_line(ox + x0 * sx, cy + y0 * sc,
                              ox + x1 * sx, cy + y1 * sc, wpx, color)
        cx += (adv * sc) + track * SS
    return x + text_width(s, size, track)


def wrap_text(s, size, max_w, track=0.0):
    """Greedy word wrap. Returns list of lines."""
    words = s.split(" ")
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_width(trial, size, track) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines

# ---------------------------------------------------------------- masthead
# Filled serif nameplate letters on a 96-unit cap-height grid.
# Each glyph: (advance, [(op, poly), ...]) where op "F" fills with ink and
# "C" cuts with paper colour. Drawn scaled to fit a target width.

_M = {}


def _m(ch, adv, ops):
    _M[ch] = (adv, ops)


_m("T", 96, [("F", [(0, 0), (96, 0), (96, 18), (0, 18)]),
             ("F", [(39, 18), (57, 18), (57, 96), (39, 96)]),
             ("F", [(33, 88), (63, 88), (63, 96), (33, 96)]),
             ("F", [(0, 18), (8, 18), (8, 26), (0, 26)]),
             ("F", [(88, 18), (96, 18), (96, 26), (88, 26)])])
_m("H", 100, [("F", [(0, 0), (20, 0), (20, 96), (0, 96)]),
              ("F", [(80, 0), (100, 0), (100, 96), (80, 96)]),
              ("F", [(20, 40), (80, 40), (80, 58), (20, 58)]),
              ("F", [(0, 0), (26, 0), (26, 8), (0, 8)]),
              ("F", [(74, 0), (100, 0), (100, 8), (74, 8)]),
              ("F", [(0, 88), (26, 88), (26, 96), (0, 96)]),
              ("F", [(74, 88), (100, 88), (100, 96), (74, 96)])])
_m("E", 88, [("F", [(0, 0), (20, 0), (20, 96), (0, 96)]),
             ("F", [(0, 0), (88, 0), (88, 18), (0, 18)]),
             ("F", [(0, 40), (70, 40), (70, 58), (0, 58)]),
             ("F", [(0, 78), (88, 78), (88, 96), (0, 96)])])
_m("D", 96, [("F", [(0, 0), (20, 0), (20, 96), (0, 96)]),
             ("F", [(20, 0), (66, 0), (86, 18), (92, 40), (92, 56),
                    (86, 78), (66, 96), (20, 96)]),
             ("C", [(38, 18), (62, 18), (72, 30), (74, 48), (72, 66),
                    (62, 78), (38, 78)])])
_m("A", 92, [("F", [(0, 96), (36, 0), (56, 0), (28, 96)]),
             ("F", [(56, 0), (74, 0), (92, 96), (64, 96)]),
             ("F", [(11, 58), (86, 58), (86, 74), (11, 74)])])
_m("I", 72, [("F", [(26, 0), (46, 0), (46, 96), (26, 96)]),
             ("F", [(14, 0), (58, 0), (58, 16), (14, 16)]),
             ("F", [(14, 80), (58, 80), (58, 96), (14, 96)])])
_m("L", 86, [("F", [(0, 0), (20, 0), (20, 96), (0, 96)]),
             ("F", [(0, 78), (86, 78), (86, 96), (0, 96)])])
_m("Y", 92, [("F", [(0, 0), (22, 0), (50, 44), (36, 50)]),
             ("F", [(92, 0), (70, 0), (50, 44), (56, 50)]),
             ("F", [(38, 44), (56, 44), (56, 96), (38, 96)]),
             ("F", [(32, 88), (62, 88), (62, 96), (32, 96)])])
_m("G", 96, [("F", [(20, 0), (72, 0), (90, 18), (96, 44), (96, 52),
                    (90, 78), (72, 96), (20, 96), (6, 78), (0, 52),
                    (0, 44), (6, 18)]),
             ("C", [(28, 22), (64, 22), (76, 34), (78, 48), (76, 62),
                    (64, 74), (28, 74), (16, 62), (14, 48), (16, 34)]),
             ("F", [(56, 44), (96, 44), (96, 62), (56, 62)]),
             ("F", [(76, 44), (96, 44), (96, 96), (76, 96)])])
_m("O", 96, [("F", [(20, 0), (72, 0), (90, 18), (96, 44), (96, 52),
                    (90, 78), (72, 96), (20, 96), (6, 78), (0, 52),
                    (0, 44), (6, 18)]),
             ("C", [(28, 22), (64, 22), (76, 34), (78, 48), (76, 62),
                    (64, 74), (28, 74), (16, 62), (14, 48), (16, 34)])])
_m("B", 90, [("F", [(0, 0), (20, 0), (20, 96), (0, 96)]),
             ("F", [(20, 0), (62, 0), (80, 12), (82, 28), (76, 40),
                    (62, 44), (20, 44)]),
             ("C", [(38, 14), (56, 14), (62, 20), (62, 30), (56, 36),
                    (38, 36)]),
             ("F", [(20, 44), (68, 44), (86, 56), (88, 74), (80, 88),
                    (62, 96), (20, 96)]),
             ("C", [(38, 58), (60, 58), (68, 66), (68, 78), (60, 86),
                    (38, 86)])])
_m(" ", 36, [])


def draw_masthead(cv, x, y, text, target_w, color=INK):
    """Draw the nameplate at final coords, top-left (x, y). Returns height."""
    gap = 10.0
    total = sum(_M[ch][0] for ch in text) + gap * (len(text) - 1)
    s = target_w / total
    cx = x * SS
    cy = y * SS
    for ch in text:
        adv, ops = _M[ch]
        for op, poly in ops:
            pts = [(cx + px * s * SS, cy + py * s * SS) for px, py in poly]
            cv.poly(pts, color if op == "F" else PAPER)
        cx += (adv + gap) * s * SS
    return 96.0 * s

# ---------------------------------------------------------------- illustrations
# All take render-pixel coords (x, y, w, h) already scaled by SS.

def ill_skyline(cv, x, y, w, h):
    """Vice City sunset skyline for the GTA VI lead."""
    # sky: orange -> pink -> purple
    cv.vgrad(x, y, x + w, y + h * 0.45, (255, 138, 58), (238, 82, 108))
    cv.vgrad(x, y + h * 0.45, x + w, y + h * 0.72, (238, 82, 108), (96, 44, 112))
    cv.vgrad(x, y + h * 0.72, x + w, y + h, (96, 44, 112), (52, 30, 84))
    # sun + glow
    sx, sy, sr = x + w * 0.62, y + h * 0.44, h * 0.17
    cv.disk(sx, sy, sr * 2.1, (255, 170, 90), 0.16)
    cv.disk(sx, sy, sr * 1.5, (255, 190, 110), 0.25)
    cv.disk(sx, sy, sr, (255, 214, 120))
    # skyline silhouette
    rnd = random.Random(11)
    base = y + h * 0.86
    bx = x
    dark = (32, 20, 52)
    while bx < x + w:
        bw = w * rnd.uniform(0.05, 0.10)
        bh = h * rnd.uniform(0.18, 0.48)
        cv.rect(bx, base - bh, bx + bw, base, dark)
        # lit windows
        for wy in range(int(base - bh + 6), int(base - 4), 14):
            for wx in range(int(bx + 4), int(bx + bw - 4), 12):
                if rnd.random() < 0.28:
                    cv.rect(wx, wy, wx + 4, wy + 5, (255, 196, 90))
        bx += bw + w * 0.008
    # palm silhouettes
    for px, ph in ((x + w * 0.10, h * 0.34), (x + w * 0.88, h * 0.28)):
        cv.thick_line(px, base, px + w * 0.015, base - ph, 7, dark)
        for ang in (-150, -120, -95, -70, -45, -20):
            a = math.radians(ang)
            ex = px + w * 0.015 + math.cos(a) * w * 0.055
            ey = base - ph + math.sin(a) * h * 0.10
            cv.thick_line(px + w * 0.015, base - ph, ex, ey, 5, dark)
    # water + reflections
    cv.rect(x, base, x + w, y + h, (22, 18, 44))
    for k in range(26):
        rx = x + rnd.uniform(0, w * 0.9)
        ry = base + rnd.uniform(4, h * 0.11)
        rl = rnd.uniform(w * 0.03, w * 0.12)
        cv.hline(rx, rx + rl, ry, (255, 160, 90), 0.45)
    # birds
    for bx, by, bs in ((x + w * 0.30, y + h * 0.16, 12),
                       (x + w * 0.38, y + h * 0.11, 9),
                       (x + w * 0.45, y + h * 0.19, 8)):
        cv.thick_line(bx - bs, by, bx, by - bs * 0.5, 3, dark)
        cv.thick_line(bx, by - bs * 0.5, bx + bs, by, 3, dark)


def ill_capitol(cv, x, y, w, h):
    """US Capitol dome for the Speaker story."""
    cv.vgrad(x, y, x + w, y + h, (198, 220, 236), (243, 236, 220))
    # distant skyline hint
    cv.rect(x, y + h * 0.78, x + w, y + h, (214, 210, 196))
    stone = (238, 234, 222)
    shadow = (203, 198, 184)
    dark = (120, 116, 104)
    cx = x + w / 2
    # base terrace + steps
    cv.rect(x + w * 0.10, y + h * 0.80, x + w * 0.90, y + h * 0.86, stone)
    cv.rect(x + w * 0.06, y + h * 0.86, x + w * 0.94, y + h * 0.92, shadow)
    cv.rect(x + w * 0.02, y + h * 0.92, x + w * 0.98, y + h, (188, 182, 168))
    # wings
    cv.rect(x + w * 0.10, y + h * 0.62, x + w * 0.34, y + h * 0.80, stone)
    cv.rect(x + w * 0.66, y + h * 0.62, x + w * 0.90, y + h * 0.80, stone)
    for wx in (0.13, 0.19, 0.25, 0.31, 0.69, 0.75, 0.81, 0.87):
        cv.rect(x + w * wx, y + h * 0.66, x + w * wx + 5, y + h * 0.78, dark)
    # central block + columns
    cv.rect(cx - w * 0.16, y + h * 0.52, cx + w * 0.16, y + h * 0.80, stone)
    for k in range(6):
        colx = cx - w * 0.135 + k * w * 0.054
        cv.rect(colx, y + h * 0.56, colx + 7, y + h * 0.78, (250, 247, 238))
        cv.rect(colx, y + h * 0.56, colx + 2, y + h * 0.78, shadow)
    # pediment
    cv.poly([(cx - w * 0.17, y + h * 0.52), (cx + w * 0.17, y + h * 0.52),
             (cx, y + h * 0.42)], stone)
    cv.poly([(cx - w * 0.13, y + h * 0.51), (cx + w * 0.13, y + h * 0.51),
             (cx, y + h * 0.45)], shadow)
    # drum + dome
    cv.rect(cx - w * 0.11, y + h * 0.30, cx + w * 0.11, y + h * 0.42, stone)
    for k in range(7):
        colx = cx - w * 0.10 + k * w * 0.033
        cv.rect(colx, y + h * 0.31, colx + 3, y + h * 0.41, shadow)
    dome = arc_pts(cx, y + h * 0.30, w * 0.115, h * 0.20, 180, 360, 28)
    cv.poly(dome + [(cx + w * 0.115, y + h * 0.30),
                    (cx - w * 0.115, y + h * 0.30)], (246, 244, 236))
    # dome ribs
    for a in (-60, -30, 0, 30, 60):
        ar = math.radians(a)
        ex = cx + math.sin(ar) * w * 0.115
        ey = y + h * 0.30 - math.cos(ar) * h * 0.20
        cv.thick_line(cx, y + h * 0.10, ex, ey, 2, shadow)
    # lantern + statue + flag
    cv.rect(cx - 4, y + h * 0.06, cx + 4, y + h * 0.11, stone)
    cv.disk(cx, y + h * 0.055, 5, dark)
    cv.thick_line(cx + w * 0.16, y + h * 0.10, cx + w * 0.16, y + h * 0.30, 3, dark)
    cv.poly([(cx + w * 0.16, y + h * 0.10), (cx + w * 0.16 + 26, y + h * 0.125),
             (cx + w * 0.16, y + h * 0.15)], (178, 35, 27))
    # clouds
    for ccx, ccy, cr in ((x + w * 0.16, y + h * 0.16, 26),
                         (x + w * 0.82, y + h * 0.10, 22),
                         (x + w * 0.86, y + h * 0.22, 16)):
        cv.disk(ccx, ccy, cr, (255, 255, 255), 0.85)
        cv.disk(ccx + cr, ccy + 4, cr * 0.7, (255, 255, 255), 0.85)


def ill_cyclone(cv, x, y, w, h):
    """Satellite view of a cyclone over the Bay of Bengal."""
    cv.vgrad(x, y, x + w, y + h, (18, 52, 88), (10, 32, 62))
    cx, cy = x + w * 0.52, y + h * 0.52
    # spiral arms: Archimedean spiral bands
    rnd = random.Random(23)
    for arm in range(3):
        a0 = arm * 120.0
        pts = []
        for k in range(120):
            a = math.radians(a0 + k * 6.0)
            r = h * 0.06 + k * h * 0.0032
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a) * 0.92))
        for k in range(len(pts) - 1):
            wd = 16 - k * 0.07
            if wd < 4:
                wd = 4
            cv.thick_line(pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1],
                          wd, (238, 244, 250), 0.75)
    # cloud texture blobs
    for _ in range(46):
        a = rnd.uniform(0, 360)
        r = rnd.uniform(h * 0.08, h * 0.42)
        bx = cx + r * math.cos(math.radians(a))
        by = cy + r * math.sin(math.radians(a)) * 0.92
        cv.disk(bx, by, rnd.uniform(5, 16), (240, 246, 252),
                rnd.uniform(0.18, 0.5))
    # eye
    cv.disk(cx, cy, h * 0.075, (12, 36, 66))
    for k in range(10):
        a = math.radians(k * 36)
        cv.disk(cx + math.cos(a) * h * 0.085, cy + math.sin(a) * h * 0.085,
                7, (250, 250, 250), 0.9)
    # landmass (India's east coast) bottom-right
    land = [(x + w * 0.66, y + h), (x + w, y + h), (x + w, y + h * 0.72),
            (x + w * 0.88, y + h * 0.80), (x + w * 0.78, y + h * 0.88),
            (x + w * 0.70, y + h * 0.94)]
    cv.poly(land, (196, 178, 138))
    cv.poly([(x + w * 0.66, y + h), (x + w, y + h), (x + w, y + h * 0.72),
             (x + w * 0.88, y + h * 0.80)], (214, 196, 156))
    # rain-band streaks
    for k in range(18):
        rx = x + rnd.uniform(0, w * 0.4)
        ry = y + rnd.uniform(0, h * 0.9)
        cv.thick_line(rx, ry, rx - 10, ry + 22, 3, (200, 220, 240), 0.5)


def ill_voyager(cv, x, y, w, h):
    """Voyager 1 in deep space, one light-day from home."""
    cv.rect(x, y, x + w, y + h, (7, 9, 18))
    rnd = random.Random(31)
    for _ in range(130):
        sx = x + rnd.uniform(0, w)
        sy = y + rnd.uniform(0, h)
        r = rnd.uniform(1, 3.2)
        b = rnd.uniform(0.35, 1.0)
        cv.disk(sx, sy, r, (255, 255, 255), b)
    # sun glow top-right
    gx, gy = x + w * 0.92, y + h * 0.06
    cv.disk(gx, gy, h * 0.30, (255, 220, 140), 0.12)
    cv.disk(gx, gy, h * 0.16, (255, 230, 160), 0.25)
    cv.disk(gx, gy, h * 0.06, (255, 244, 200))
    # Earth bottom-left
    ex, ey, er = x + w * 0.16, y + h * 0.82, h * 0.17
    cv.disk(ex, ey, er * 1.18, (120, 170, 230), 0.35)
    cv.disk(ex, ey, er, (38, 98, 188))
    cv.ellipse(ex - er * 0.3, ey - er * 0.25, er * 0.42, er * 0.30, (74, 148, 92))
    cv.ellipse(ex + er * 0.35, ey + er * 0.30, er * 0.30, er * 0.22, (120, 110, 80))
    cv.ellipse(ex + er * 0.1, ey - er * 0.55, er * 0.34, er * 0.16, (230, 240, 245), 0.9)
    cv.ellipse(ex - er * 0.55, ey + er * 0.45, er * 0.30, er * 0.14, (230, 240, 245), 0.8)
    # trajectory (dashed)
    px, py = x + w * 0.68, y + h * 0.34
    steps = 26
    for k in range(steps + 1):
        t = k / steps
        tx = ex + (px - ex) * t + math.sin(t * 3.0) * w * 0.02
        ty = ey + (py - ey) * t - t * t * h * 0.08
        if k % 2 == 0:
            cv.disk(tx, ty, 3, (255, 220, 120), 0.9)
    # Voyager probe: gold body, white dish, boom + RTG
    cv.poly([(px - 24, py - 14), (px + 24, py - 14), (px + 32, py),
             (px + 24, py + 14), (px - 24, py + 14), (px - 32, py)],
            (212, 168, 60))
    # dish (ellipse, tilted)
    cv.ellipse(px - 48, py - 30, 28, 16, (238, 240, 244))
    cv.thick_line(px - 30, py - 18, px - 42, py - 26, 5, (200, 200, 205))
    cv.thick_line(px - 48, py - 30, px - 62, py - 42, 3, (220, 222, 226))
    cv.thick_line(px - 48, py - 30, px - 34, py - 42, 3, (220, 222, 226))
    cv.thick_line(px - 48, py - 30, px - 48, py - 46, 3, (220, 222, 226))
    # boom + RTG
    cv.thick_line(px + 30, py + 6, px + 72, py + 24, 5, (180, 180, 185))
    cv.rect(px + 70, py + 16, px + 88, py + 32, (150, 150, 155))
    cv.rect(px + 70, py + 16, px + 88, py + 21, (210, 210, 215))


def ill_eu(cv, x, y, w, h):
    """EU flag with gold coins for the Ukraine loan story."""
    cv.vgrad(x, y, x + w, y + h, (0, 58, 168), (0, 44, 132))
    cx, cy = x + w * 0.5, y + h * 0.44
    rr = h * 0.30
    for k in range(12):
        a = math.radians(-90 + k * 30)
        sx = cx + rr * math.cos(a)
        sy = cy + rr * math.sin(a)
        cv.poly(star_pts(sx, sy, h * 0.055, h * 0.022), (255, 204, 0))
    # coins at the bottom
    rnd = random.Random(41)
    base = y + h * 0.86
    for k in range(9):
        cox = x + w * (0.10 + k * 0.10)
        cor = h * 0.05
        cv.ellipse(cox, base - cor * 0.4, cor, cor * 0.55, (226, 172, 44))
        cv.ellipse(cox, base - cor * 0.4, cor * 0.8, cor * 0.42, (255, 214, 90))
        cv.disk(cox, base - cor * 0.4, cor * 0.16, (200, 150, 30))


def ill_gulf(cv, x, y, w, h):
    """Gulf at dusk: ships, smoke plume, explosion glow."""
    cv.vgrad(x, y, x + w, y + h * 0.55, (52, 48, 84), (214, 122, 62))
    cv.vgrad(x, y + h * 0.55, x + w, y + h, (214, 122, 62), (120, 62, 52))
    # moon
    cv.disk(x + w * 0.84, y + h * 0.14, h * 0.055, (244, 238, 220))
    # sea
    cv.rect(x, y + h * 0.62, x + w, y + h, (14, 44, 56))
    rnd = random.Random(53)
    for _ in range(30):
        wx = x + rnd.uniform(0, w * 0.9)
        wy = y + h * 0.62 + rnd.uniform(4, h * 0.34)
        cv.hline(wx, wx + rnd.uniform(w * 0.03, w * 0.10), wy,
                 (120, 170, 190), 0.35)
    # explosion glow on the horizon
    gx, gy = x + w * 0.30, y + h * 0.60
    cv.disk(gx, gy, h * 0.22, (255, 150, 60), 0.35)
    cv.disk(gx, gy, h * 0.12, (255, 200, 90), 0.6)
    cv.disk(gx, gy, h * 0.05, (255, 230, 160))
    # smoke plume
    for k in range(9):
        sx = gx + (k - 4) * w * 0.012 + rnd.uniform(-4, 4)
        sy = gy - k * h * 0.055
        cv.disk(sx, sy, h * (0.05 + k * 0.012), (70, 66, 64),
                0.75 - k * 0.05)
    # ships (dark silhouettes)
    def ship(sx, sy, sw, sh):
        hull = [(sx, sy), (sx + sw, sy), (sx + sw * 0.92, sy + sh * 0.55),
                (sx + sw * 0.08, sy + sh * 0.55)]
        cv.poly(hull, (16, 20, 28))
        cv.rect(sx + sw * 0.30, sy - sh * 0.55, sx + sw * 0.62, sy, (16, 20, 28))
        cv.rect(sx + sw * 0.66, sy - sh * 0.35, sx + sw * 0.74, sy, (16, 20, 28))
        cv.thick_line(sx + sw * 0.42, sy - sh * 0.55, sx + sw * 0.42,
                      sy - sh * 0.95, 3, (16, 20, 28))
    ship(x + w * 0.52, y + h * 0.68, w * 0.40, h * 0.16)
    ship(x + w * 0.06, y + h * 0.76, w * 0.26, h * 0.12)

# ---------------------------------------------------------------- layout helpers

def draw_para(cv, x, y, text, size, max_w, lh, color=INK, weight=1.0,
              track=0.0):
    lines = wrap_text(text, size, max_w, track)
    for ln in lines:
        draw_text(cv, x, y, ln, size, color, weight, track)
        y += lh
    return y


def hrule(cv, x0, x1, y, w=2, color=RULE):
    cv.rect(x0 * SS, y * SS, x1 * SS, (y + w) * SS, color)


def double_rule(cv, x0, x1, y):
    hrule(cv, x0, x1, y, 3)
    hrule(cv, x0, x1, y + 6, 1)


def kicker(cv, x, y, s, size=15):
    draw_text(cv, x, y, s, size, RED, 1.25, 1.5)
    return y + size + 10


# ---------------------------------------------------------------- build the page

def build():
    cv = Canvas(W, H, PAPER)
    rnd = random.Random(20261119)
    # paper texture: faint speckles
    for _ in range(2600):
        sx = rnd.uniform(0, W)
        sy = rnd.uniform(0, H)
        cv.disk(sx, sy, rnd.uniform(0.8, 2.2), (120, 110, 90),
                rnd.uniform(0.02, 0.05))
    for _ in range(900):
        sx = rnd.uniform(0, W)
        sy = rnd.uniform(0, H)
        cv.disk(sx, sy, rnd.uniform(0.8, 1.8), (255, 255, 250),
                rnd.uniform(0.03, 0.06))

    MX = 36                      # side margin
    RX = 1024 - MX               # right edge

    # frame
    cv.rect(10 * SS, 10 * SS, 1014 * SS, 12 * SS, INK)
    cv.rect(10 * SS, 1012 * SS, 1014 * SS, 1014 * SS, INK)
    cv.rect(10 * SS, 10 * SS, 12 * SS, 1014 * SS, INK)
    cv.rect(1012 * SS, 10 * SS, 1014 * SS, 1014 * SS, INK)

    # ---- nameplate
    y = 18
    mh = draw_masthead(cv, MX, y, "THE DAILY GLOBE", RX - MX)
    y += mh + 6
    draw_text(cv, 512, y, "THURSDAY,  19  NOVEMBER  2026", 19, RED, 1.3, 2.0,
              align="c")
    y += 24
    draw_text(cv, 512, y, "THE WORLD'S NEWS IN ONE PAGE", 13, GREY, 1.0, 2.5,
              align="c")
    y += 18
    double_rule(cv, MX, RX, y)
    y += 10

    # ---- lead headline + deck
    draw_text(cv, 512, y, "GRAND THEFT AUTO VI", 36, INK, 1.25, 1.0, align="c")
    y += 42
    draw_text(cv, 512, y, "LAUNCHES WORLDWIDE", 36, INK, 1.25, 1.0, align="c")
    y += 44
    draw_text(cv, 512, y, "After a 13-year wait, gamers enter Vice City.",
              18, INK, 1.0, 0.4, align="c")
    y += 26

    # ---- lead row: text left, hero image right
    lead_top = y
    lead_w = 452
    tx = MX
    ty = draw_para(cv, tx, lead_top,
                   "Rockstar Games releases its most anticipated title after "
                   "13 years. Vice City returns, bigger and louder, as "
                   "players flood in from launch night.", 16.5, lead_w, 21.5)
    ty += 8
    ty = draw_para(cv, tx, ty,
                   "The rollout began at midnight in New Zealand and sweeps "
                   "the globe. Queues formed in London, New York and Tokyo.",
                   16.5, lead_w, 21.5)
    img_x, img_w = 512, RX - 512
    img_h = 172
    ill_skyline(cv, img_x * SS, lead_top * SS, img_w * SS, img_h * SS)
    # caption under the hero image
    draw_text(cv, img_x, lead_top + img_h + 5,
              "Vice City at dusk — 13 years in the making.",
              12.5, GREY, 1.0, 0.3)
    y = lead_top + img_h + 20
    hrule(cv, MX, RX, y, 1)
    y += 10

    # ---- mid row: three stories
    col_w = (RX - MX - 2 * 20) / 3.0
    mid = [
        ("AMERICA", "JEFFRIES NOMINATED FOR US SPEAKER",
         "Democrats pick Hakeem Jeffries. He would be the first Black "
         "Speaker.", ill_capitol),
        ("ASIA", "CYCLONE AKVAN NEARS INDIA",
         "Landfall expected between Machilipatnam and Puri. States on "
         "alert.", ill_cyclone),
        ("SCIENCE", "VOYAGER 1 ONE LIGHT-DAY OUT",
         "NASA to confirm the milestone today as the probe sails on into "
         "interstellar space.", ill_voyager),
    ]
    row_top = y
    row_bottom = row_top
    for i, (kick, head, body, ill) in enumerate(mid):
        cx0 = MX + i * (col_w + 20)
        cy = row_top
        cy = kicker(cv, cx0, cy, kick, 14)
        cy = draw_para(cv, cx0, cy, head, 21, col_w, 25, INK, 1.25)
        cy += 6
        ih = 106
        ill(cv, cx0 * SS, cy * SS, col_w * SS, ih * SS)
        cy += ih + 8
        cy = draw_para(cv, cx0, cy, body, 14, col_w, 17.5)
        row_bottom = max(row_bottom, cy)
    for i in (0, 1):
        dx = MX + (i + 1) * col_w + i * 20 + 10
        cv.rect(dx * SS, row_top * SS, (dx + 1) * SS, row_bottom * SS,
                (200, 194, 180))
    y = row_bottom + 10
    hrule(cv, MX, RX, y, 1)
    y += 10

    # ---- bottom row: two stories, image left / text right
    col2_w = (RX - MX - 20) / 2.0
    bot = [
        ("EUROPE", "EU 45BN-EURO LOAN FOR UKRAINE",
         "Brussels lends Kyiv 45bn euros to keep the state running through "
         "the war's fifth winter.", ill_eu),
        ("MIDDLE EAST", "US-IRAN STRIKES WIDEN IN GULF",
         "Iran hit Gulf bases. The US struck back. Shipping and oil markets "
         "braced for a wider war.", ill_gulf),
    ]
    row_top = y
    row_bottom = row_top
    for i, (kick, head, body, ill) in enumerate(bot):
        cx0 = MX + i * (col2_w + 20)
        iw, ih = 190, 92
        ill(cv, cx0 * SS, row_top * SS, iw * SS, ih * SS)
        tx0 = cx0 + iw + 12
        tw = col2_w - iw - 12
        cy = row_top
        cy = kicker(cv, tx0, cy, kick, 13)
        cy = draw_para(cv, tx0, cy, head, 20, tw, 24, INK, 1.25)
        cy += 4
        cy = draw_para(cv, tx0, cy, body, 13.5, tw, 17)
        row_bottom = max(row_bottom, cy, row_top + ih)
    y = row_bottom + 8
    hrule(cv, MX, RX, y, 1)
    y += 8

    # ---- also today
    y = kicker(cv, MX, y, "ALSO TODAY", 13)
    y = draw_para(cv, MX, y,
                  "ICJ to rule on Myanmar genocide case  •  Pew: Islam set to be "
                  "largest faith by 2035", 13.5, RX - MX, 17)
    y = draw_para(cv, MX, y,
                  "Fed minutes point to more rate rises  •  Trump, Xi, Putin to "
                  "meet in Shenzhen", 13.5, RX - MX, 17)
    y += 8
    hrule(cv, MX, RX, y, 1)
    y += 8
    draw_text(cv, 512, y, "THE DAILY GLOBE  •  THURSDAY 19 NOVEMBER 2026",
              12.5, GREY, 1.0, 1.5, align="c")
    return cv


def main():
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "out"))
    out_dir.mkdir(parents=True, exist_ok=True)
    cv = build()
    rgb = cv.downsample()
    path = out_dir / "entry.png"
    n = write_png(path, FW, FH, rgb)
    print(f"wrote {path} ({n} bytes)")


if __name__ == "__main__":
    main()
