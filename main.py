#!/usr/bin/env python3
"""THE DAILY GLOBE -- front page summing up Thursday 19 November 2026.

A pure-stdlib Python 3 program: it draws a 1024x1024 newspaper front page
with a tiny built-in 5x7 bitmap font and writes it as a PNG to
$MAKEFUN_OUTPUT_DIR/entry.png (or /output/entry.png). No network, no
external files, no clock: the same input always produces the same bytes.

Stories (all reported on 19 November 2026):
  * Grand Theft Auto VI begins its global rollout; gamers enter Vice City.
  * Democrats nominate Hakeem Jeffries for US House Speaker.
  * Cyclone Akvan nears India's east coast, landfall expected between
    Machilipatnam and Puri.
  * NASA's Voyager 1 reaches one light-day from Earth.
  * The EU proposes a 45-billion-euro loan for Ukraine.
  * US-Iran strikes widen across the Gulf.
  * Also today: the ICJ rules on Myanmar, a Pew report on faith by 2035,
    Fed minutes point to more rate rises, and Trump, Xi and Putin meet
    in Shenzhen.
"""

import math
import os
import struct
import zlib

W = H = 1024

# --- palette ---------------------------------------------------------------
PAPER = (247, 243, 232)
INK = (20, 20, 20)
RED = (176, 30, 36)
BLUE = (29, 78, 137)
GREY = (110, 108, 100)
SUNSET_TOP = (255, 154, 60)
SUNSET_MID = (255, 94, 120)
SUNSET_BOT = (123, 45, 139)
DUSK = (42, 26, 74)
SUN = (255, 210, 62)
SKY = (214, 228, 238)
DOME = (245, 245, 240)
DOME_SHADE = (198, 203, 208)
GROUND = (206, 204, 190)
SEA_PALE = (200, 216, 228)
SPIRAL = (40, 90, 140)
SPIRAL_LT = (110, 160, 200)
LAND = (222, 205, 170)
SPACE = (8, 10, 18)
GOLD = (212, 175, 55)
EU_BLUE = (30, 58, 138)
GULF_SEA = (16, 60, 74)
GULF_SKY = (150, 178, 186)
SHIP = (36, 38, 44)
FIRE = (255, 140, 40)
FIRE_Y = (255, 214, 80)
SMOKE = (130, 130, 128)

# --- canvas ----------------------------------------------------------------
buf = bytearray(W * H * 3)


def fill_rect(x, y, w, h, color):
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(W, x + w)
    y1 = min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(color) * (x1 - x0)
    for yy in range(y0, y1):
        base = (yy * W + x0) * 3
        buf[base:base + len(row)] = row


def px(x, y, color):
    if 0 <= x < W and 0 <= y < H:
        base = (y * W + x) * 3
        buf[base:base + 3] = bytes(color)


def hline(x, y, w, color, thick=1):
    fill_rect(x, y, w, thick, color)


def vline(x, y, h, color, thick=1):
    fill_rect(x, y, thick, h, color)


def line(x0, y0, x1, y1, color, thick=1):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        fill_rect(x0 - thick // 2, y0 - thick // 2, thick, thick, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def disc(cx, cy, r, color):
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(r * r - dy * dy))
        fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, color)


def ring(cx, cy, r, color, thick=2):
    for a in range(360):
        rad = math.radians(a)
        for t in range(thick):
            px(int(cx + (r + t) * math.cos(rad)),
               int(cy + (r + t) * math.sin(rad)), color)


def triangle(x0, y0, x1, y1, x2, y2, color):
    min_y = min(y0, y1, y2)
    max_y = max(y0, y1, y2)
    for yy in range(min_y, max_y + 1):
        xs = []
        for (ax, ay, bx, by) in ((x0, y0, x1, y1), (x1, y1, x2, y2),
                                 (x2, y2, x0, y0)):
            if ay == by:
                continue
            if min(ay, by) <= yy < max(ay, by):
                xs.append(ax + (yy - ay) * (bx - ax) / (by - ay))
        if len(xs) >= 2:
            fill_rect(int(min(xs)), yy, int(max(xs)) - int(min(xs)) + 1, 1,
                      color)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# --- 5x7 bitmap font (glyph = 7 rows of 5 bits) ----------------------------
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    '3': ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    '4': ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ':': ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ';': ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '/': ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    '(': ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ')': ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    '%': ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '?': ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    '&': ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    '+': ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    '=': ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '\u2022': ("00000", "00000", "01100", "01100", "01100", "00000", "00000"),
    '\u2014': ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
}


def text_width(s, scale):
    return len(s) * 6 * scale - scale if s else 0


def draw_text(x, y, s, scale, color, align="l"):
    if align == "c":
        x -= text_width(s, scale) // 2
    elif align == "r":
        x -= text_width(s, scale)
    for ci, ch in enumerate(s):
        glyph = FONT.get(ch, FONT[" "])
        gx = x + ci * 6 * scale
        for r in range(7):
            row = glyph[r]
            for c in range(5):
                if row[c] == "1":
                    fill_rect(gx + c * scale, y + r * scale, scale, scale,
                              color)


def wrap(text, max_w, scale):
    lines = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for wd in words:
            trial = wd if not cur else cur + " " + wd
            if text_width(trial, scale) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
    return lines


def kicker(x, y, s, scale=2):
    draw_text(x, y, s, scale, RED)


def headline(x, y, lines, scale):
    for i, ln in enumerate(lines):
        draw_text(x, y + i * (7 * scale + 8), ln, scale, INK)


def deck(x, y, text, max_w, scale=2, gap=6):
    lines = wrap(text, max_w, scale)
    for i, ln in enumerate(lines):
        draw_text(x, y + i * (7 * scale + gap), ln, scale, INK)
    return y + len(lines) * (7 * scale + gap)


# --- illustrations ---------------------------------------------------------
def art_vice_city(x, y, w, h):
    for row in range(h):
        t = row / max(1, h - 1)
        if t < 0.5:
            col = lerp(SUNSET_TOP, SUNSET_MID, t * 2)
        else:
            col = lerp(SUNSET_MID, SUNSET_BOT, (t - 0.5) * 2)
        fill_rect(x, y + row, w, 1, col)
    disc(x + int(w * 0.62), y + int(h * 0.42), int(h * 0.20), SUN)
    ring(x + int(w * 0.62), y + int(h * 0.42), int(h * 0.24), SUN, 2)
    base = y + h
    heights = [0.30, 0.46, 0.24, 0.56, 0.38, 0.62, 0.30, 0.48]
    bw = w // 8
    for i, f in enumerate(heights):
        bh = int(h * f)
        fill_rect(x + i * bw, base - bh, bw - 3, bh, DUSK)
        for wy in range(3):
            px(x + i * bw + 4, base - bh + 8 + wy * 10, SUN)
            px(x + i * bw + bw - 8, base - bh + 14 + wy * 10, SUN)
    fill_rect(x, base - int(h * 0.12), w, int(h * 0.12), (26, 16, 52))
    hline(x, base - int(h * 0.12) + 4, w, (120, 70, 150), 2)
    hline(x, base - int(h * 0.12) + 10, w, (90, 50, 120), 2)
    # two palm silhouettes
    for px0, ph in ((x + 26, 52), (x + w - 34, 44)):
        line(px0, base - int(h * 0.12), px0 + 6, base - int(h * 0.12) - ph,
             DUSK, 4)
        tx, ty = px0 + 6, base - int(h * 0.12) - ph
        for dx, dy in ((-26, 6), (-14, -8), (0, -12), (14, -8), (26, 4)):
            line(tx, ty, tx + dx, ty + dy, DUSK, 3)


def art_capitol(x, y, w, h):
    fill_rect(x, y, w, h, SKY)
    cx = x + w // 2
    ground_y = y + int(h * 0.82)
    fill_rect(x, ground_y, w, y + h - ground_y, GROUND)
    # dome: shaded half-disc with a dark outline so it reads on pale sky
    dome_r = int(w * 0.17)
    dome_cy = ground_y - int(h * 0.34)
    for dy in range(-dome_r, 1):
        dx = int(math.sqrt(dome_r * dome_r - dy * dy))
        fill_rect(cx - dx, dome_cy + dy, 2 * dx + 1, 1, DOME)
    for a in range(180, 361, 1):
        rad = math.radians(a)
        px(int(cx + dome_r * math.cos(rad)),
           int(dome_cy + dome_r * math.sin(rad)), GREY)
        px(int(cx + (dome_r - 1) * math.cos(rad)),
           int(dome_cy + (dome_r - 1) * math.sin(rad)), GREY)
    # shade the dome's right half
    for dy in range(-dome_r + 6, -4):
        dx = int(math.sqrt(dome_r * dome_r - dy * dy))
        fill_rect(cx + dx // 3, dome_cy + dy, dx - dx // 3, 1, DOME_SHADE)
    fill_rect(cx - dome_r, dome_cy, 2 * dome_r, 4, DOME_SHADE)
    fill_rect(cx - 6, dome_cy - dome_r - 12, 12, 12, DOME)
    fill_rect(cx - 1, dome_cy - dome_r - 22, 2, 10, INK)
    fill_rect(cx + 1, dome_cy - dome_r - 22, 10, 6, RED)
    # drum + columns + base: shaded block, pale columns standing out
    fill_rect(cx - int(w * 0.20), dome_cy, int(w * 0.40), 10, DOME)
    col_y = dome_cy + 10
    fill_rect(cx - int(w * 0.20), col_y, int(w * 0.40),
              ground_y - col_y - 12, DOME_SHADE)
    for i in range(6):
        col_x = cx - int(w * 0.20) + 6 + i * int(w * 0.065)
        fill_rect(col_x, col_y, 8, ground_y - col_y - 12, DOME)
    fill_rect(cx - int(w * 0.24), ground_y - 12, int(w * 0.48), 6, DOME)
    fill_rect(cx - int(w * 0.28), ground_y - 6, int(w * 0.56), 6, DOME_SHADE)


def art_cyclone(x, y, w, h):
    fill_rect(x, y, w, h, SEA_PALE)
    cx, cy = x + int(w * 0.42), y + int(h * 0.52)
    disc(cx, cy, 7, PAPER)
    ring(cx, cy, 7, SPIRAL, 2)
    for k, r in enumerate((14, 22, 30, 38, 46, 54)):
        col = SPIRAL if k % 2 == 0 else SPIRAL_LT
        start = 40 + k * 55
        for a in range(start, start + 300, 2):
            rad = math.radians(a)
            px(int(cx + r * math.cos(rad)), int(cy + r * math.sin(rad)), col)
            px(int(cx + r * math.cos(rad)) + 1,
               int(cy + r * math.sin(rad)), col)
    # rain, bottom left
    for i in range(9):
        rx = x + 12 + i * 14
        ry = y + h - 26 + (i % 3) * 6
        line(rx, ry, rx - 5, ry + 12, SPIRAL_LT, 2)
    # landmass, bottom right
    triangle(x + w - 8, y + h, x + w - int(w * 0.42), y + h,
             x + w - int(w * 0.18), y + int(h * 0.62), LAND)
    line(x + w - int(w * 0.42), y + h, x + w - int(w * 0.18),
         y + int(h * 0.62), INK, 2)


def art_voyager(x, y, w, h):
    fill_rect(x, y, w, h, SPACE)
    stars = [(0.08, 0.12), (0.22, 0.06), (0.34, 0.20), (0.48, 0.08),
             (0.62, 0.16), (0.78, 0.06), (0.90, 0.18), (0.12, 0.38),
             (0.30, 0.44), (0.55, 0.36), (0.86, 0.40), (0.18, 0.62),
             (0.40, 0.70), (0.66, 0.62), (0.92, 0.66), (0.06, 0.84),
             (0.28, 0.88), (0.74, 0.86)]
    for fx, fy in stars:
        fill_rect(x + int(w * fx), y + int(h * fy), 2, 2, PAPER)
    disc(x + int(w * 0.88), y + int(h * 0.86), 16, (46, 90, 160))
    disc(x + int(w * 0.88) - 5, y + int(h * 0.86) - 4, 5, (90, 160, 110))
    # dashed trajectory
    sx, sy = x + int(w * 0.10), y + int(h * 0.90)
    ex, ey = x + int(w * 0.52), y + int(h * 0.46)
    for i in range(0, 12):
        t0 = i / 12.0
        t1 = (i + 0.55) / 12.0
        line(int(sx + (ex - sx) * t0), int(sy + (ey - sy) * t0),
             int(sx + (ex - sx) * t1), int(sy + (ey - sy) * t1), GOLD, 2)
    # spacecraft: bus, dish, boom
    bx, by = ex, ey
    fill_rect(bx - 8, by - 6, 20, 12, GOLD)
    fill_rect(bx + 12, by - 2, 22, 4, GOLD)
    ring(bx - 16, by - 12, 9, GOLD, 2)
    line(bx - 12, by - 8, bx - 8, by - 4, GOLD, 2)
    line(bx + 2, by + 6, bx + 2, by + 16, GOLD, 2)
    disc(bx + 2, by + 18, 2, GOLD)


def art_eu(x, y, w, h):
    fill_rect(x, y, w, h, EU_BLUE)
    cx, cy = x + w // 2, y + h // 2
    for k in range(12):
        a = math.radians(k * 30 - 90)
        sx = int(cx + 30 * math.cos(a))
        sy = int(cy + 30 * math.sin(a))
        disc(sx, sy, 3, GOLD)
        line(sx - 5, sy, sx + 5, sy, GOLD, 1)
        line(sx, sy - 5, sx, sy + 5, GOLD, 1)
    disc(cx, cy, 3, GOLD)


def art_gulf(x, y, w, h):
    fill_rect(x, y, w, h, GULF_SKY)
    horizon = y + int(h * 0.55)
    fill_rect(x, horizon, w, y + h - horizon, GULF_SEA)
    disc(x + int(w * 0.82), y + int(h * 0.20), 10, (250, 240, 210))
    # ship 1 (left, on fire)
    sx, sy = x + int(w * 0.14), horizon + int(h * 0.16)
    fill_rect(sx, sy, 74, 10, SHIP)
    triangle(sx + 74, sy, sx + 88, sy, sx + 74, sy + 10, SHIP)
    fill_rect(sx + 18, sy - 12, 8, 12, SHIP)
    fill_rect(sx + 34, sy - 18, 6, 18, SHIP)
    # fire burst above ship 1
    fx, fy = sx + 38, sy - 26
    for k in range(8):
        a = math.radians(k * 45)
        line(fx, fy, int(fx + 16 * math.cos(a)), int(fy + 16 * math.sin(a)),
             FIRE, 3)
    disc(fx, fy, 7, FIRE_Y)
    for dx, dy in ((-12, -22), (-4, -30), (6, -26)):
        disc(fx + dx, fy + dy, 5, SMOKE)
    # ship 2 (right)
    sx2 = x + int(w * 0.60)
    sy2 = horizon + int(h * 0.24)
    fill_rect(sx2, sy2, 60, 9, SHIP)
    triangle(sx2 + 60, sy2, sx2 + 72, sy2, sx2 + 60, sy2 + 9, SHIP)
    fill_rect(sx2 + 14, sy2 - 10, 7, 10, SHIP)
    # wave lines
    for wy in (horizon + 8, horizon + 22, horizon + 34):
        for wx in range(0, w - 20, 34):
            hline(x + wx, y + wy, 18, (120, 170, 180), 2)


# --- page ------------------------------------------------------------------
def rule(x, y, w, thick=2, color=INK):
    fill_rect(x, y, w, thick, color)


def draw_page():
    fill_rect(0, 0, W, H, PAPER)
    M = 28
    CW = W - 2 * M

    # masthead
    rule(M, 28, CW, 2)
    draw_text(W // 2, 40, "THE DAILY GLOBE", 9, INK, align="c")
    draw_text(W // 2, 112, "THURSDAY, 19 NOVEMBER 2026", 3, RED, align="c")
    draw_text(W // 2, 140, "THE WORLD'S NEWS IN ONE PAGE", 2, GREY,
              align="c")
    rule(M, 162, CW, 3)

    # lead story: GTA VI
    kicker(M, 180, "CULTURE \u2022 LEAD STORY")
    headline(M, 204, ["GRAND THEFT AUTO VI", "LAUNCHES WORLDWIDE"], 5)
    deck(M, 308,
         "AFTER A 13-YEAR WAIT, GAMERS ENTER VICE CITY AS THE ROLLOUT "
         "BEGINS.", 620, scale=3, gap=8)
    art_vice_city(668, 180, 328, 198)
    rule(M, 396, CW, 2)

    # row 2: America / Asia
    y2 = 412
    art_capitol(M, y2, 468, 96)
    art_cyclone(528, y2, 468, 96)
    kicker(M, y2 + 106, "AMERICA")
    kicker(528, y2 + 106, "ASIA")
    headline(M, y2 + 130, ["JEFFRIES NOMINATED", "FOR US SPEAKER"], 4)
    headline(528, y2 + 130, ["CYCLONE AKVAN NEARS", "INDIA'S EAST COAST"],
             4)
    deck(M, y2 + 196,
         "DEMOCRATS PICK HAKEEM JEFFRIES. HE WOULD BE THE FIRST BLACK "
         "SPEAKER.", 468, scale=2, gap=6)
    deck(528, y2 + 196,
         "LANDFALL EXPECTED BETWEEN MACHILIPATNAM AND PURI. STATES ON "
         "ALERT.", 468, scale=2, gap=6)
    rule(M, 656, CW, 2)

    # row 3: Science / Europe / Middle East
    y3 = 672
    cols = [(M, 312), (356, 312), (684, 312)]
    for i, (cx, cw) in enumerate(cols):
        if i:
            vline(cx - 8, y3, 196, GREY, 1)
    art_voyager(M, y3, 312, 72)
    art_eu(356, y3, 312, 72)
    art_gulf(684, y3, 312, 72)
    kicker(M, y3 + 82, "SCIENCE")
    kicker(356, y3 + 82, "EUROPE")
    kicker(684, y3 + 82, "MIDDLE EAST")
    headline(M, y3 + 106, ["VOYAGER 1", "ONE LIGHT-DAY"], 3)
    headline(356, y3 + 106, ["EU 45BN-EURO LOAN", "FOR UKRAINE"], 3)
    headline(684, y3 + 106, ["US-IRAN STRIKES", "WIDEN IN GULF"], 3)
    deck(M, y3 + 164, "NASA TO CONFIRM THE MILESTONE TODAY.", 312, scale=2)
    deck(356, y3 + 164, "BRUSSELS LENDS KYIV 45BN EUROS.", 312, scale=2)
    deck(684, y3 + 164, "IRAN HIT GULF BASES. THE US STRUCK BACK.", 312,
         scale=2)
    rule(M, 884, CW, 2)

    # also-today strip
    kicker(M, 896, "ALSO TODAY")
    draw_text(M, 922, "ICJ TO RULE ON MYANMAR GENOCIDE CASE", 2, INK)
    draw_text(M, 942, "PEW: ISLAM SET TO BE LARGEST FAITH BY 2035", 2, INK)
    draw_text(M, 962,
              "FED MINUTES POINT TO MORE RATE RISES \u2022 TRUMP, XI, "
              "PUTIN TO MEET IN SHENZHEN", 2, INK)
    rule(M, 984, CW, 1, GREY)
    draw_text(W // 2, 992, "THE DAILY GLOBE \u2022 THURSDAY 19 NOVEMBER 2026",
              2, GREY, align="c")


def png_bytes(w, h, rgb):
    raw = bytearray()
    for yy in range(h):
        raw.append(0)
        raw += rgb[yy * w * 3:(yy + 1) * w * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main():
    draw_page()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png_bytes(W, H, buf))
    print("wrote", path, os.path.getsize(path), "bytes")


if __name__ == "__main__":
    main()
