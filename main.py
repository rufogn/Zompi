"""
ZOMBİ AVI 3D  -  Pygame ile gerçek 3D (perspektif poligon motoru) nişancı oyunu
Ekran: 1920x1200

Harita: San Francisco tarzı 56x56 şehir ızgarası – geniş sokaklar, girilebilir
        binalar (kapılı, bazıları iç bölmeli), parklar ve merkezi meydan.
        Binaların içine girip savaşabilirsiniz.

Kontroller:
  W A S D / Fare / Sol tık (asa, 5 mana) / Sağ tık ADS
  Shift koşu · Space zıpla · 1-7 element · Q/E/T büyü · P duraklat
  LAN: menüden Sunucu Kur veya Sunucuya Katıl (F5 = otomatik bul)
  ESC menü/çıkış · Enter yeniden başla

Vuruş bölgeleri:  KAFA x3.5 | GÖVDE x1 | KOL x0.5 | BACAK x0.6 (+ zombiyi yavaşlatır)
Kurulum:  pip install pygame
"""
import math
import os
import random
import sys
import socket
import threading
import json
import time as _time
from array import array
from collections import deque
from contextlib import contextmanager

import pygame

# Android (python-for-android / buildozer) üzerinde mi çalışıyoruz?
IS_ANDROID = hasattr(sys, "getandroidapilevel") or "ANDROID_ARGUMENT" in os.environ

NET_PORT = 27345
NET_DISCOVER = 27346
NET_TICK = 0.05

# ============================================================== AYARLAR
SCREEN_W, SCREEN_H = 1920, 1080
RENDER_SCALE = 4 if IS_ANDROID else 3   # 3D çözünürlük = ekran / RENDER_SCALE (büyük = hızlı, pikselli)
RW, RH = SCREEN_W // RENDER_SCALE, SCREEN_H // RENDER_SCALE
HW, HH = RW / 2.0, RH / 2.0
DRAW_DIST = 36.0                 # bundan uzak dünya öğeleri hiç işlenmez
DRAW_D2 = DRAW_DIST * DRAW_DIST
BASE_FOV = 82                    # yatay görüş açısı (derece)
NEAR = 0.08
WALL_H = 3.0
EYE_H = 1.65
GRAVITY = 16.0

MOVE_SPEED = 3.4
SPRINT_MULT = 1.55
MOUSE_SENS = 0.0021

STAFF_MANA = 5
STAFF_DELAY = 0.16
STAFF_DAMAGE = 30
MANA_MAX = 100
MANA_REGEN = 8.0

# Elemental büyüler (1-7). Her birinin rengi, mana maliyeti ve bekleme süresi var.
ELEMENTS = [
    {"id": "fire", "name": "ATEŞ", "col": (255, 95, 25), "mana": 26, "cd": 0.90,
     "hint": "Q ateş topu  |  E ateş halkası  |  T ateş duvarı"},
    {"id": "water", "name": "SU", "col": (70, 170, 255), "mana": 22, "cd": 0.75,
     "hint": "Q buz oku  |  E tsunami  |  T girdap"},
    {"id": "earth", "name": "TOPRAK", "col": (168, 118, 52), "mana": 28, "cd": 1.10,
     "hint": "Q diken hattı  |  E taş pençe  |  T deprem"},
    {"id": "air", "name": "RÜZGAR", "col": (190, 230, 245), "mana": 20, "cd": 0.70,
     "hint": "Q rüzgar konisi  |  E kasırga  |  T fırtına dalgası"},
    {"id": "lightning", "name": "YILDIRIM", "col": (170, 200, 255), "mana": 30, "cd": 1.00,
     "hint": "Q zincir şimşek  |  E yıldırım oku  |  T fırtına çağrısı"},
    {"id": "dark", "name": "GÖLGE", "col": (128, 48, 190), "mana": 24, "cd": 0.85,
     "hint": "Q gölge oku  |  E Hadar kolları  |  T Hadar açlığı"},
    {"id": "light", "name": "IŞIK", "col": (255, 245, 170), "mana": 32, "cd": 1.15,
     "hint": "Q kutsal ışın  |  E ruh koruyucuları  |  T güneş patlaması"},
]

# Her element: Q / E / T  (D&D esintili)
ELEMENT_SKILLS = {
    "fire": [
        {"id": "ball", "key": "Q", "name": "ATEŞ TOPU", "mana": 26, "cd": 0.90},
        {"id": "ring", "key": "E", "name": "ATEŞ HALKASI", "mana": 32, "cd": 1.40},
        {"id": "wall", "key": "T", "name": "ATEŞ DUVARI", "mana": 36, "cd": 1.60},
    ],
    "water": [
        {"id": "bolt", "key": "Q", "name": "BUZ OKU", "mana": 22, "cd": 0.75},
        {"id": "tsunami", "key": "E", "name": "TSUNAMİ", "mana": 34, "cd": 1.50},
        {"id": "vortex", "key": "T", "name": "GİRDAP", "mana": 36, "cd": 1.70},
    ],
    "earth": [
        {"id": "spikes", "key": "Q", "name": "DİKEN HATTI", "mana": 28, "cd": 1.10},
        {"id": "grasp", "key": "E", "name": "TAŞ PENÇE", "mana": 34, "cd": 1.55},
        {"id": "quake", "key": "T", "name": "DEPREM", "mana": 40, "cd": 1.85},
    ],
    "air": [
        {"id": "gust", "key": "Q", "name": "RÜZGAR KONİSİ", "mana": 20, "cd": 0.70},
        {"id": "whirl", "key": "E", "name": "KASIRGA", "mana": 32, "cd": 1.45},
        {"id": "wave", "key": "T", "name": "FIRTINA DALGASI", "mana": 34, "cd": 1.60},
    ],
    "lightning": [
        {"id": "chain", "key": "Q", "name": "ZİNCİR ŞİMŞEK", "mana": 30, "cd": 1.00},
        {"id": "bolt", "key": "E", "name": "YILDIRIM OKU", "mana": 34, "cd": 1.35},
        {"id": "storm", "key": "T", "name": "FIRTINA ÇAĞRISI", "mana": 40, "cd": 1.90},
    ],
    "dark": [
        {"id": "bolt", "key": "Q", "name": "GÖLGE OKU", "mana": 24, "cd": 0.85},
        {"id": "arms", "key": "E", "name": "HADAR KOLLARI", "mana": 32, "cd": 1.40},
        {"id": "hunger", "key": "T", "name": "HADAR AÇLIĞI", "mana": 38, "cd": 1.80},
    ],
    "light": [
        {"id": "ray", "key": "Q", "name": "KUTSAL IŞIN", "mana": 32, "cd": 1.15},
        {"id": "guardians", "key": "E", "name": "RUH KORUYUCULARI", "mana": 36, "cd": 1.70},
        {"id": "sunburst", "key": "T", "name": "GÜNEŞ PATLAMASI", "mana": 42, "cd": 2.00},
    ],
}
FIRE_SKILLS = ELEMENT_SKILLS["fire"]
WATER_SKILLS = ELEMENT_SKILLS["water"]

_DATA_DIR = os.environ.get("ANDROID_PRIVATE") or os.path.dirname(os.path.abspath(__file__))
HIGHSCORE_FILE = os.path.join(_DATA_DIR, "zombi_highscore.txt")

FOG = (10, 12, 22)
SKY_TOP = (4, 6, 18)
SKY_HOR = (26, 32, 58)
GROUND = (22, 22, 24)
LX, LY, LZ = 0.45, 0.35, 0.82     # ay ışığı yönü

# ============================================================== HARİTA
MAP_W, MAP_H = 56, 56
WORLD = [[0] * MAP_W for _ in range(MAP_H)]
BUILDINGS = []  # (x, y, w, h, wall_t, door_side, roof_col, wall_base)

for i in range(MAP_W):
    WORLD[0][i] = WORLD[MAP_H - 1][i] = 1
for j in range(MAP_H):
    WORLD[j][0] = WORLD[j][MAP_W - 1] = 1

WALL_COLORS = {
    1: (158, 82, 62),      # tuğla
    2: (118, 120, 128),    # gri taş
    3: (72, 112, 74),      # yeşil / çit
    4: (210, 185, 140),    # krem / sarı
    5: (155, 58, 52),      # koyu kırmızı
    6: (95, 130, 155),     # mavi-gri (SF bay)
    7: (175, 145, 165),    # morumsu Victorian
    8: (200, 175, 120),    # açık hardal
}

ROOF_PALETTE = [
    (168, 72, 48),   # terracotta
    (92, 96, 102),   # slate
    (70, 88, 68),    # yosun yeşili
    (130, 70, 55),   # koyu kiremit
    (110, 105, 95),  # gri kiremit
    (150, 85, 50),   # turuncu kiremit
]

def _hollow_house(x, y, w, h, wall_t, door_side="s"):
    """Müstakil ev: içi boş, kapılı, BUILDINGS listesine kaydedilir."""
    if w < 4 or h < 4:
        return
    if x < 1 or y < 1 or x + w >= MAP_W - 1 or y + h >= MAP_H - 1:
        return
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if WORLD[yy][xx] != 0:
                return
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if yy == y or yy == y + h - 1 or xx == x or xx == x + w - 1:
                WORLD[yy][xx] = wall_t
            else:
                WORLD[yy][xx] = 0
    mid_x = x + w // 2
    mid_y = y + h // 2
    if door_side == "s":
        WORLD[y + h - 1][mid_x] = 0
        if w >= 5:
            WORLD[y + h - 1][max(x + 1, mid_x - 1)] = 0
    elif door_side == "n":
        WORLD[y][mid_x] = 0
        if w >= 5:
            WORLD[y][max(x + 1, mid_x - 1)] = 0
    elif door_side == "e":
        WORLD[mid_y][x + w - 1] = 0
        if h >= 5:
            WORLD[max(y + 1, mid_y - 1)][x + w - 1] = 0
    else:
        WORLD[mid_y][x] = 0
        if h >= 5:
            WORLD[max(y + 1, mid_y - 1)][x] = 0
    if w >= 7 and h >= 6 and random.random() < 0.5:
        split = x + w // 2
        for yy in range(y + 1, y + h - 1):
            WORLD[yy][split] = wall_t
        WORLD[y + h // 2][split] = 0
    roof_col = random.choice(ROOF_PALETTE)
    base = WALL_COLORS.get(wall_t, (140, 100, 80))
    BUILDINGS.append((x, y, w, h, wall_t, door_side, roof_col, base))

STREET_YS = [4, 12, 20, 28, 36, 44, 51]
STREET_XS = [4, 12, 20, 28, 36, 44, 51]
for sy in STREET_YS:
    for x in range(1, MAP_W - 1):
        WORLD[sy][x] = 0
        if sy + 1 < MAP_H - 1:
            WORLD[sy + 1][x] = 0
for sx in STREET_XS:
    for y in range(1, MAP_H - 1):
        WORLD[y][sx] = 0
        if sx + 1 < MAP_W - 1:
            WORLD[y][sx + 1] = 0

random.seed(42)
house_types = [1, 4, 5, 6, 7, 8, 1, 4, 2, 6, 5, 7]
door_cycle = ["s", "n", "e", "w", "s", "n"]
bi = 0

for by in range(2, MAP_H - 5, 7):
    for bx in range(2, MAP_W - 5, 7):
        if any(abs(bx - sx) < 3 for sx in STREET_XS) or any(abs(by - sy) < 3 for sy in STREET_YS):
            continue
        if random.random() < 0.12:
            continue
        bw = random.choice([4, 5, 5, 6, 6, 7])
        bh = random.choice([4, 5, 5, 6])
        ox = random.randint(0, 1)
        oy = random.randint(0, 1)
        wt = house_types[bi % len(house_types)]
        _hollow_house(bx + ox, by + oy, bw, bh, wt, door_cycle[bi % 6])
        bi += 1

for row_y in (8, 16, 24, 32, 40):
    for start_x in (6, 22, 38):
        for i in range(3):
            x = start_x + i * 5
            if x + 4 >= MAP_W - 2:
                break
            wt = 4 if i % 2 == 0 else 5
            _hollow_house(x, row_y, 4, 5, wt, "s")

for (tx, ty) in [(31, 31), (32, 33), (15, 39), (43, 15), (30, 30), (33, 31)]:
    if 1 <= tx < MAP_W - 1 and 1 <= ty < MAP_H - 1 and WORLD[ty][tx] == 0:
        WORLD[ty][tx] = 3

for yy in range(26, 32):
    for xx in range(26, 32):
        WORLD[yy][xx] = 0

for yy in range(2, 8):
    for xx in range(2, 8):
        WORLD[yy][xx] = 0

for i in range(MAP_W):
    WORLD[0][i] = WORLD[MAP_H - 1][i] = 1
for j in range(MAP_H):
    WORLD[j][0] = WORLD[j][MAP_W - 1] = 1


def is_wall(x, y):
    mx, my = int(math.floor(x)), int(math.floor(y))
    if mx < 0 or my < 0 or mx >= MAP_W or my >= MAP_H:
        return True
    return WORLD[my][mx] != 0


def free_circle(x, y, r):
    return not (is_wall(x - r, y - r) or is_wall(x + r, y - r) or
                is_wall(x - r, y + r) or is_wall(x + r, y + r))


def los_clear(x0, y0, x1, y1, r=0.18):
    dx, dy = x1 - x0, y1 - y0
    dist = math.hypot(dx, dy)
    n = max(1, int(dist / 0.35))
    for i in range(1, n):
        t = i / n
        if not free_circle(x0 + dx * t, y0 + dy * t, r):
            return False
    return True


# ---- sabit geometri
random.seed(7)
WALL_H = 2.9
ROOF_RISE = 1.15
WALL_FACES = []
ROOF_FACES = []
DETAIL_FACES = []


def _wq(gx, gy, nx, ny, z0, z1, u0=0.0, u1=1.0):
    """Duvar hücresi yüzü; u0-u1 kenar boyunca kısmi (0..1)."""
    if nx == 1:
        y_a, y_b = gy + u0, gy + u1
        return [(gx + 1, y_a, z0), (gx + 1, y_b, z0), (gx + 1, y_b, z1), (gx + 1, y_a, z1)]
    if nx == -1:
        y_a, y_b = gy + u1, gy + u0
        return [(gx, y_a, z0), (gx, y_b, z0), (gx, y_b, z1), (gx, y_a, z1)]
    if ny == 1:
        x_a, x_b = gx + u1, gx + u0
        return [(x_a, gy + 1, z0), (x_b, gy + 1, z0), (x_b, gy + 1, z1), (x_a, gy + 1, z1)]
    x_a, x_b = gx + u0, gx + u1
    return [(x_a, gy, z0), (x_b, gy, z0), (x_b, gy, z1), (x_a, gy, z1)]


_BUILDING_COL = {}
for (bx, by, bw, bh, wt, door, roof_col, wall_base) in BUILDINGS:
    for yy in range(by, by + bh):
        for xx in range(bx, bx + bw):
            if WORLD[yy][xx] == wt:
                _BUILDING_COL[(xx, yy)] = wall_base

for gy in range(MAP_H):
    for gx in range(MAP_W):
        t = WORLD[gy][gx]
        if not t:
            continue
        base = _BUILDING_COL.get((gx, gy), WALL_COLORS.get(t, (130, 100, 80)))
        if t == 3:
            base = WALL_COLORS[3]
        for nx, ny in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ax, ay = gx + nx, gy + ny
            if not (0 <= ax < MAP_W and 0 <= ay < MAP_H and WORLD[ay][ax] == 0):
                continue
            cx = gx + 0.5 + nx * 0.5
            cy = gy + 0.5 + ny * 0.5
            WALL_FACES.append((_wq(gx, gy, nx, ny, 0.0, WALL_H), nx, ny, base, cx, cy))

WIN_GLASS = (40, 70, 95)
WIN_FRAME = (55, 45, 35)
DOOR_COL = (70, 45, 30)
DOOR_FRAME = (45, 35, 28)

for (bx, by, bw, bh, wt, door_side, roof_col, wall_base) in BUILDINGS:
    mid_x = bx + bw // 2
    mid_y = by + bh // 2
    if door_side == "s":
        gx, gy, nx, ny = mid_x, by + bh - 1, 0, 1
        DETAIL_FACES.append((_wq(gx, gy, nx, ny, 0.0, 2.05, 0.15, 0.85), DOOR_COL, gx + 0.5, gy + 1.0))
        DETAIL_FACES.append((_wq(gx, gy, nx, ny, 2.05, 2.25, 0.12, 0.88), DOOR_FRAME, gx + 0.5, gy + 1.0))
    elif door_side == "n":
        gx, gy, nx, ny = mid_x, by, 0, -1
        DETAIL_FACES.append((_wq(gx, gy, nx, ny, 0.0, 2.05, 0.15, 0.85), DOOR_COL, gx + 0.5, gy))
        DETAIL_FACES.append((_wq(gx, gy, nx, ny, 2.05, 2.25, 0.12, 0.88), DOOR_FRAME, gx + 0.5, gy))
    elif door_side == "e":
        gx, gy, nx, ny = bx + bw - 1, mid_y, 1, 0
        DETAIL_FACES.append((_wq(gx, gy, nx, ny, 0.0, 2.05, 0.15, 0.85), DOOR_COL, gx + 1.0, gy + 0.5))
        DETAIL_FACES.append((_wq(gx, gy, nx, ny, 2.05, 2.25, 0.12, 0.88), DOOR_FRAME, gx + 1.0, gy + 0.5))
    else:
        gx, gy, nx, ny = bx, mid_y, -1, 0
        DETAIL_FACES.append((_wq(gx, gy, nx, ny, 0.0, 2.05, 0.15, 0.85), DOOR_COL, gx, gy + 0.5))
        DETAIL_FACES.append((_wq(gx, gy, nx, ny, 2.05, 2.25, 0.12, 0.88), DOOR_FRAME, gx, gy + 0.5))

    for yy in range(by, by + bh):
        for xx in range(bx, bx + bw):
            if WORLD[yy][xx] != wt:
                continue
            is_door_cell = False
            if door_side == "s" and yy == by + bh - 1 and abs(xx - mid_x) <= 1:
                is_door_cell = True
            if door_side == "n" and yy == by and abs(xx - mid_x) <= 1:
                is_door_cell = True
            if door_side == "e" and xx == bx + bw - 1 and abs(yy - mid_y) <= 1:
                is_door_cell = True
            if door_side == "w" and xx == bx and abs(yy - mid_y) <= 1:
                is_door_cell = True
            for nx, ny in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ax, ay = xx + nx, yy + ny
                if not (0 <= ax < MAP_W and 0 <= ay < MAP_H and WORLD[ay][ax] == 0):
                    continue
                if is_door_cell and ((door_side == "s" and ny == 1) or (door_side == "n" and ny == -1) or
                                     (door_side == "e" and nx == 1) or (door_side == "w" and nx == -1)):
                    continue
                cx = xx + 0.5 + nx * 0.5
                cy = yy + 0.5 + ny * 0.5
                DETAIL_FACES.append((_wq(xx, yy, nx, ny, 1.15, 2.05, 0.22, 0.78), WIN_GLASS, cx, cy))
                DETAIL_FACES.append((_wq(xx, yy, nx, ny, 1.08, 1.15, 0.20, 0.80), WIN_FRAME, cx, cy))
                DETAIL_FACES.append((_wq(xx, yy, nx, ny, 2.05, 2.12, 0.20, 0.80), WIN_FRAME, cx, cy))

# ============================================================== ÇATILAR
ROOF_BOUNDS = []
ROOF_EAVE_OUT = 0.18


def _face_normal(v):
    ax, ay, az = v[1][0] - v[0][0], v[1][1] - v[0][1], v[1][2] - v[0][2]
    bx, by, bz = v[2][0] - v[0][0], v[2][1] - v[0][1], v[2][2] - v[0][2]
    nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / ln, ny / ln, nz / ln)


DETAIL_FACES = [(v, c, cx, cy, _face_normal(v)) for (v, c, cx, cy) in DETAIL_FACES]


def _add_roof_face(verts, col, bid, kind, ref=None, normal=None):
    k = len(verts)
    c = (sum(v[0] for v in verts) / k,
         sum(v[1] for v in verts) / k,
         sum(v[2] for v in verts) / k)
    if normal is not None:
        n = normal
    else:
        n = _face_normal(verts)
        if ref is not None:
            side = n[0] * (c[0] - ref[0]) + n[1] * (c[1] - ref[1]) + n[2] * (c[2] - ref[2])
            if side < 0:
                n = (-n[0], -n[1], -n[2])
    ROOF_FACES.append((verts, col, n, c, kind, bid))


DOWN = (0.0, 0.0, -1.0)

for bid, (bx, by, bw, bh, wt, door, roof_col, wall_base) in enumerate(BUILDINGS):
    x0, y0 = float(bx), float(by)
    x1, y1 = float(bx + bw), float(by + bh)
    ROOF_BOUNDS.append((x0, y0, x1, y1))
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    z_e = WALL_H
    z_r = WALL_H + ROOF_RISE
    z_s = z_e - 0.04
    o = ROOF_EAVE_OUT
    c_main = roof_col
    c_shade = tuple(max(0, int(v * 0.78)) for v in roof_col)
    c_under = tuple(max(0, int(v * 0.55)) for v in roof_col)
    gable = wall_base
    ref = (cx, cy, z_e)

    _add_roof_face([(x0, y0, z_e), (x1, y0, z_e), (x1, y1, z_e), (x0, y1, z_e)],
                   c_under, bid, "ceiling", normal=DOWN)

    if bw >= bh:
        mx = cx
        _add_roof_face([(x0, y0, z_e), (x0, y1, z_e), (mx, y1, z_r), (mx, y0, z_r)],
                       c_main, bid, "shell", ref)
        _add_roof_face([(mx, y0, z_r), (mx, y1, z_r), (x1, y1, z_e), (x1, y0, z_e)],
                       c_shade, bid, "shell", ref)
        _add_roof_face([(x0, y0, z_e), (x1, y0, z_e), (mx, y0, z_r)],
                       gable, bid, "shell", ref)
        _add_roof_face([(x0, y1, z_e), (mx, y1, z_r), (x1, y1, z_e)],
                       gable, bid, "shell", ref)
        _add_roof_face([(x0 - o, y0, z_s), (x0, y0, z_s), (x0, y1, z_s), (x0 - o, y1, z_s)],
                       c_shade, bid, "eave", normal=DOWN)
        _add_roof_face([(x1, y0, z_s), (x1 + o, y0, z_s), (x1 + o, y1, z_s), (x1, y1, z_s)],
                       c_shade, bid, "eave", normal=DOWN)
    else:
        my = cy
        _add_roof_face([(x0, y0, z_e), (x1, y0, z_e), (x1, my, z_r), (x0, my, z_r)],
                       c_main, bid, "shell", ref)
        _add_roof_face([(x0, my, z_r), (x1, my, z_r), (x1, y1, z_e), (x0, y1, z_e)],
                       c_shade, bid, "shell", ref)
        _add_roof_face([(x0, y0, z_e), (x0, y1, z_e), (x0, my, z_r)],
                       gable, bid, "shell", ref)
        _add_roof_face([(x1, y0, z_e), (x1, my, z_r), (x1, y1, z_e)],
                       gable, bid, "shell", ref)
        _add_roof_face([(x0, y0 - o, z_s), (x1, y0 - o, z_s), (x1, y0, z_s), (x0, y0, z_s)],
                       c_shade, bid, "eave", normal=DOWN)
        _add_roof_face([(x0, y1, z_s), (x1, y1, z_s), (x1, y1 + o, z_s), (x0, y1 + o, z_s)],
                       c_shade, bid, "eave", normal=DOWN)

    if (bx + by) % 3 == 0:
        chx, chy = cx - 0.15, cy - 0.1
        cw = cd = 0.34
        z0b, z1b = z_r - 0.15, z_r + 0.55
        brick = (105, 58, 48)
        cref = (chx + cw * 0.5, chy + cd * 0.5, (z0b + z1b) * 0.5)
        for verts in (
            [(chx, chy, z0b), (chx + cw, chy, z0b), (chx + cw, chy, z1b), (chx, chy, z1b)],
            [(chx, chy + cd, z0b), (chx, chy, z0b), (chx, chy, z1b), (chx, chy + cd, z1b)],
            [(chx + cw, chy, z0b), (chx + cw, chy + cd, z0b), (chx + cw, chy + cd, z1b), (chx + cw, chy, z1b)],
            [(chx + cw, chy + cd, z0b), (chx, chy + cd, z0b), (chx, chy + cd, z1b), (chx + cw, chy + cd, z1b)],
            [(chx, chy, z1b), (chx + cw, chy, z1b), (chx + cw, chy + cd, z1b), (chx, chy + cd, z1b)],
        ):
            _add_roof_face(verts, brick, bid, "chimney", cref)

FLOOR_TILES = []
STREET_SET = set()
for sy in [4, 5, 12, 13, 20, 21, 28, 29, 36, 37, 44, 45, 51, 52]:
    for x in range(MAP_W):
        STREET_SET.add((x, sy))
for sx in [4, 5, 12, 13, 20, 21, 28, 29, 36, 37, 44, 45, 51, 52]:
    for y in range(MAP_H):
        STREET_SET.add((sx, y))
for gy in range(MAP_H):
    for gx in range(MAP_W):
        if WORLD[gy][gx] == 0:
            if (gx, gy) in STREET_SET or (26 <= gx < 32 and 26 <= gy < 32):
                c = 46 if (gx + gy) % 2 == 0 else 40
                col = (c, c, c + 3)
            elif 30 <= gx < 34 and 30 <= gy < 34:
                c = 55 + ((gx * 3 + gy) % 5)
                col = (c - 10, c + 14, c - 14)
            else:
                c = 74 if (gx + gy) % 2 == 0 else 66
                col = (c + 6, c - 4, c - 16)
            FLOOR_TILES.append(([(gx, gy, 0), (gx + 1, gy, 0), (gx + 1, gy + 1, 0), (gx, gy + 1, 0)],
                                gx + 0.5, gy + 0.5, col))

OPEN_CELLS = [(x + 0.5, y + 0.5) for y in range(MAP_H) for x in range(MAP_W) if WORLD[y][x] == 0]

STARS = []
for _ in range(160):
    a = random.uniform(0, math.tau)
    z = random.uniform(0.03, 1.0)
    r = math.sqrt(1 - z * z)
    STARS.append((math.cos(a) * r, math.sin(a) * r, z, random.randint(110, 255)))
_m = (0.6, 0.5, 0.55)
_ml = math.sqrt(sum(c * c for c in _m))
MOON = (_m[0] / _ml, _m[1] / _ml, _m[2] / _ml)


# ============================================================== KAMERA
class Cam:
    def __init__(self):
        self.set(0, 0, EYE_H, 0, 0, 1.0)

    def set(self, x, y, z, yaw, pitch, zoom):
        self.x, self.y, self.z = x, y, z
        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        self.fx, self.fy, self.fz = cy * cp, sy * cp, sp
        self.rx, self.ry = sy, -cy
        self.ux, self.uy, self.uz = -cy * sp, -sy * sp, cp
        self.focal = HW / math.tan(math.radians(BASE_FOV) / 2.0) * zoom
        self.pitch = pitch

    def to_screen(self, x, y, z):
        vx, vy, vz = x - self.x, y - self.y, z - self.z
        d = vx * self.fx + vy * self.fy + vz * self.fz
        if d < NEAR:
            return None
        xs = vx * self.rx + vy * self.ry
        ys = vx * self.ux + vy * self.uy + vz * self.uz
        return HW + xs / d * self.focal, HH - ys / d * self.focal, d

    def poly(self, verts):
        px, py, pz = self.x, self.y, self.z
        rx, ry = self.rx, self.ry
        ux, uy, uz = self.ux, self.uy, self.uz
        fx, fy, fz = self.fx, self.fy, self.fz
        cv = []
        for (x, y, z) in verts:
            vx, vy, vz = x - px, y - py, z - pz
            cv.append((vx * rx + vy * ry, vx * ux + vy * uy + vz * uz, vx * fx + vy * fy + vz * fz))
        out = []
        n = len(cv)
        for i in range(n):
            a = cv[i]
            b = cv[(i + 1) % n]
            ain = a[2] >= NEAR
            bin_ = b[2] >= NEAR
            if ain:
                out.append(a)
            if ain != bin_:
                t = (NEAR - a[2]) / (b[2] - a[2])
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, NEAR))
        if len(out) < 3:
            return None
        foc = self.focal
        pts = []
        minx = miny = 1e9
        maxx = maxy = -1e9
        for (x, y, d) in out:
            sx = HW + x / d * foc
            sy = HH - y / d * foc
            if sx > 6000: sx = 6000
            elif sx < -6000: sx = -6000
            if sy > 6000: sy = 6000
            elif sy < -6000: sy = -6000
            pts.append((sx, sy))
            if sx < minx: minx = sx
            if sx > maxx: maxx = sx
            if sy < miny: miny = sy
            if sy > maxy: maxy = sy
        if maxx < 0 or minx > RW or maxy < 0 or miny > RH:
            return None
        return pts


# ============================================================== ZOMBİ MODELİ
CORNERS = [(i & 1, (i >> 1) & 1, (i >> 2) & 1) for i in range(8)]
FACES = [((1, 3, 7, 5), (1, 0, 0)), ((0, 4, 6, 2), (-1, 0, 0)),
         ((2, 3, 7, 6), (0, 1, 0)), ((0, 1, 5, 4), (0, -1, 0)),
         ((4, 5, 7, 6), (0, 0, 1))]

SKIN = (92, 138, 76)
SKIN_HEAD = (125, 165, 104)
SHIRT = (74, 84, 118)
PANTS = (58, 52, 46)
ZONE_NAMES = {"head": "KAFA", "torso": "GÖVDE", "armL": "KOL", "armR": "KOL",
              "legL": "BACAK", "legR": "BACAK"}


def zombie_boxes(z):
    """(ad, (x0,x1,y0,y1,z0,z1), renk, hasar_çarpanı, vurulabilir, ışıklı)"""
    sw = math.sin(z.phase)
    lo = sw * 0.2 * z.speed_mult
    hs = 0.03 * math.sin(z.phase * 0.5)
    arm_up = 0.12 * math.sin(max(0.0, z.swing) / 0.4 * math.pi) if z.swing > 0 else 0.0
    b = [
        ("legL", (-0.12 + lo, 0.14 + lo, 0.0, 0.27, 0.0, 0.8), PANTS, 0.6, True, False),
        ("legR", (-0.12 - lo, 0.14 - lo, -0.27, 0.0, 0.0, 0.8), PANTS, 0.6, True, False),
        ("torso", (-0.15, 0.15, -0.30, 0.30, 0.8, 1.42), SHIRT, 1.0, True, False),
        ("armL", (0.0, 0.72, 0.30, 0.46, 1.15 + 0.03 * sw + arm_up, 1.35 + 0.03 * sw + arm_up), SKIN, 0.5, True, False),
        ("armR", (0.0, 0.72, -0.46, -0.30, 1.15 - 0.03 * sw + arm_up, 1.35 - 0.03 * sw + arm_up), SKIN, 0.5, True, False),
        ("head", (-0.15, 0.15, -0.15 + hs, 0.15 + hs, 1.44, 1.76), SKIN_HEAD, 3.5, True, False),
        ("eyeL", (0.15, 0.17, 0.04 + hs, 0.10 + hs, 1.62, 1.67), (255, 40, 30), 0, False, True),
        ("eyeR", (0.15, 0.17, -0.10 + hs, -0.04 + hs, 1.62, 1.67), (255, 40, 30), 0, False, True),
        ("mouth", (0.15, 0.16, -0.07 + hs, 0.07 + hs, 1.50, 1.54), (40, 8, 8), 0, False, False),
    ]
    if not z.alive:
        sc = max(0.08, 1.0 - z.dying * 1.3)
        b = [(n, (bb[0], bb[1], bb[2], bb[3], bb[4] * sc, bb[5] * sc), c, m, h, e) for (n, bb, c, m, h, e) in b]
    return b


def ray_box(o, d, b):
    tmin, tmax = 0.0, 1e9
    for i in range(3):
        lo, hi = b[2 * i], b[2 * i + 1]
        if abs(d[i]) < 1e-9:
            if o[i] < lo or o[i] > hi:
                return None
        else:
            t1 = (lo - o[i]) / d[i]
            t2 = (hi - o[i]) / d[i]
            if t1 > t2:
                t1, t2 = t2, t1
            if t1 > tmin: tmin = t1
            if t2 < tmax: tmax = t2
            if tmin > tmax:
                return None
    return tmin


class Zombie:
    def __init__(self, x, y, wave):
        self.x, self.y = x, y
        self.face = random.uniform(0, math.tau)
        self.maxhp = 100 + 8 * (wave - 1)
        self.hp = self.maxhp
        self.base_speed = min(3.2, 1.0 + wave * 0.12 + random.uniform(0, 0.4))
        self.speed_mult = 1.0
        self.attack_cd = 0.0
        self.hit_timer = 0.0
        self.stun = 0.0
        self.phase = random.uniform(0, 6)
        self.alive = True
        self.dying = 0.0
        self.dmg = 8 + wave
        self.groan_t = random.uniform(2, 8)
        self.swing = 0.0
        self.los = False
        self.los_t = random.uniform(0, 0.2)
        self.burn = 0.0
        self.burn_dps = 0.0
        self.wet = 0.0
        self.slow_t = 0.0
        self.slow_amt = 1.0
        self.frozen = 0.0
        self.weaken = 0.0
        self.knock_x = 0.0
        self.knock_y = 0.0
        self.elem_glow = None
        self.elem_glow_t = 0.0


class Player:
    def __init__(self, x=2.5, y=2.5, yaw=0.78):
        self.x, self.y = x, y
        self.yaw, self.pitch = yaw, 0.0
        self.vx = self.vy = 0.0
        self.jump = 0.0
        self.vj = 0.0
        self.hp = 100
        self.fire_cd = 0.0
        self.bob = 0.0
        self.score = 0
        self.kills = 0
        self.shots = 0
        self.hits = 0
        self.headshots = 0
        self.mana = MANA_MAX
        self.elem = 0
        self.spell_cd = 0.0
        self.skill_cd = {e["id"]: [0.0, 0.0, 0.0] for e in ELEMENTS}
        self.alive = True

    def snapshot(self):
        return {
            "x": round(self.x, 3), "y": round(self.y, 3),
            "yaw": round(self.yaw, 4), "pitch": round(self.pitch, 4),
            "hp": int(self.hp), "mana": int(self.mana), "elem": self.elem,
            "score": self.score, "kills": self.kills,
            "alive": self.alive and self.hp > 0, "jump": round(self.jump, 3),
        }

    def apply_snapshot(self, s):
        self.x = s.get("x", self.x); self.y = s.get("y", self.y)
        self.yaw = s.get("yaw", self.yaw); self.pitch = s.get("pitch", self.pitch)
        self.hp = s.get("hp", self.hp); self.mana = s.get("mana", self.mana)
        self.elem = s.get("elem", self.elem); self.score = s.get("score", self.score)
        self.kills = s.get("kills", self.kills); self.alive = s.get("alive", True)
        self.jump = s.get("jump", 0.0)


# ============================================================== LAN AĞ
class NetLink:
    def __init__(self):
        self.mode = "solo"
        self.sock = None
        self.conn = None
        self.addr = None
        self.alive = False
        self.lock = threading.Lock()
        self.inbox = deque(maxlen=64)
        self.outbox = deque(maxlen=64)
        self.thread = None
        self.status = ""
        self.local_ip = self._guess_ip()
        self.found_hosts = []
        self._beacon_sock = None

    def _guess_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]; s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def parse_address(text, default_port=NET_PORT):
        text = (text or "").strip().replace(" ", "").replace(",", ".")
        port = default_port
        ip = text
        if ":" in text:
            a, b = text.rsplit(":", 1)
            ip = a
            try: port = int(b)
            except Exception: port = default_port
        return ip or "127.0.0.1", port

    def host(self, port=NET_PORT):
        self.close()
        self.mode = "host"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("0.0.0.0", port))
        except OSError as e:
            self.status = "Port açılamadı: %s" % e
            self.mode = "solo"
            return False
        self.sock.listen(1)
        self.sock.settimeout(0.5)
        self.alive = True
        self.status = "Sunucu açık — IP: %s (bekleniyor)" % self.local_ip
        self.thread = threading.Thread(target=self._host_loop, daemon=True)
        self.thread.start()
        threading.Thread(target=self._beacon_loop, daemon=True).start()
        return True

    def _beacon_loop(self):
        try:
            bs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            bs.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            bs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._beacon_sock = bs
            msg = json.dumps({"zombi": 1, "ip": self.local_ip, "port": NET_PORT}).encode()
            while self.alive and self.mode == "host":
                parts = self.local_ip.split(".")
                targets = ["255.255.255.255"]
                if len(parts) == 4:
                    targets.append("%s.%s.%s.255" % (parts[0], parts[1], parts[2]))
                for t in targets:
                    try: bs.sendto(msg, (t, NET_DISCOVER))
                    except Exception: pass
                _time.sleep(1.0)
            try: bs.close()
            except Exception: pass
        except Exception:
            pass

    def discover(self, timeout=1.6):
        found = {}
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            try: s.bind(("", NET_DISCOVER))
            except OSError: s.bind(("", 0))
            s.settimeout(0.3)
            deadline = _time.time() + timeout
            ping = b'{"zombi_ping":1}'
            parts = self.local_ip.split(".")
            for _ in range(3):
                try: s.sendto(ping, ("255.255.255.255", NET_DISCOVER))
                except Exception: pass
                if len(parts) == 4:
                    try: s.sendto(ping, ("%s.%s.%s.255" % (parts[0], parts[1], parts[2]), NET_DISCOVER))
                    except Exception: pass
            while _time.time() < deadline:
                try:
                    data, addr = s.recvfrom(1024)
                    obj = json.loads(data.decode("utf-8", errors="ignore"))
                    if obj.get("zombi") == 1:
                        ip = obj.get("ip") or addr[0]
                        if ip != self.local_ip:
                            found[ip] = int(obj.get("port", NET_PORT))
                except socket.timeout:
                    continue
                except Exception:
                    break
            s.close()
        except Exception as e:
            self.status = "Tarama hatası: %s" % e
            self.found_hosts = []
            return []
        self.found_hosts = sorted(found.items())
        self.status = ("Bulunan: " + ", ".join(ip for ip, _ in self.found_hosts)) if self.found_hosts else "Sunucu yok — aynı Wi-Fi mi?"
        return self.found_hosts

    def join(self, ip_text, port=NET_PORT):
        ip, port = self.parse_address(ip_text, port)
        self.close()
        self.mode = "client"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        try:
            self.sock.connect((ip, port))
            self.sock.settimeout(0.05)
            self.conn = self.sock
            self.alive = True
            self.status = "Bağlandı: %s" % ip
            self.thread = threading.Thread(target=self._io_loop, args=(self.conn,), daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            self.status = "Bağlanamadı (%s): %s" % (ip, e)
            self.mode = "solo"; self.alive = False
            try: self.sock.close()
            except Exception: pass
            self.sock = None
            return False

    def _host_loop(self):
        while self.alive and self.mode == "host":
            try:
                c, addr = self.sock.accept()
                c.settimeout(0.05)
                self.conn = c; self.addr = addr
                self.status = "İstemci bağlandı: %s" % addr[0]
                self._io_loop(c)
                self.status = "İstemci ayrıldı"
                self.conn = None
            except socket.timeout:
                continue
            except Exception:
                if not self.alive: break
                _time.sleep(0.2)

    def _io_loop(self, conn):
        buf = ""
        while self.alive and conn:
            try:
                while True:
                    with self.lock:
                        if not self.outbox: break
                        msg = self.outbox.popleft()
                    conn.sendall((json.dumps(msg, separators=(",", ":")) + "\n").encode())
            except Exception:
                break
            try:
                chunk = conn.recv(65536)
                if not chunk: break
                buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line: continue
                    try:
                        obj = json.loads(line)
                        with self.lock:
                            self.inbox.append(obj)
                    except Exception:
                        pass
            except socket.timeout:
                pass
            except Exception:
                break
            _time.sleep(0.001)

    def send(self, obj):
        if not self.alive or self.mode == "solo": return
        with self.lock:
            self.outbox.append(obj)

    def recv_all(self):
        with self.lock:
            items = list(self.inbox); self.inbox.clear()
        return items

    def connected(self):
        return self.alive and self.conn is not None and self.mode in ("host", "client")

    def close(self):
        self.alive = False
        for s in (self.conn, self.sock, self._beacon_sock):
            try:
                if s: s.close()
            except Exception: pass
        self.conn = self.sock = self._beacon_sock = None
        self.mode = "solo"


# ============================================================== SES
RATE = 22050


def make_sound(gen, dur, vol=1.0):
    n = int(RATE * dur)
    data = array("h", (max(-32767, min(32767, int(gen(i / RATE, i / n) * 32767 * vol))) for i in range(n)))
    return pygame.mixer.Sound(buffer=data.tobytes())


def build_sounds():
    r = random.uniform
    tau = math.tau
    s = {}
    s["shot"] = make_sound(lambda t, u: r(-1, 1) * 0.8 * math.exp(-t * 20) + math.sin(tau * 62 * t) * 0.7 * math.exp(-t * 28), 0.3, 0.8)
    s["empty"] = make_sound(lambda t, u: r(-1, 1) * math.exp(-t * 200), 0.05, 0.5)
    s["reload"] = make_sound(lambda t, u: r(-1, 1) * (math.exp(-(t % 0.5) * 120)) * 0.7 if t < 1.0 else 0, 1.2, 0.6)
    s["hit"] = make_sound(lambda t, u: (r(-1, 1) * 0.6 + math.sin(tau * 110 * t)) * math.exp(-t * 35), 0.15, 0.7)
    s["head"] = make_sound(lambda t, u: (math.sin(tau * 1400 * t) * 0.5 + r(-1, 1) * 0.4) * math.exp(-t * 22), 0.25, 0.7)
    s["hurt"] = make_sound(lambda t, u: (math.sin(tau * 70 * t) + r(-1, 1) * 0.3) * math.exp(-t * 7), 0.45, 0.9)
    s["die"] = make_sound(lambda t, u: math.sin(tau * (170 - 120 * u) * t) * 0.6 * (1 - u) + r(-1, 1) * 0.1 * (1 - u), 0.5, 0.6)
    for k in (1, 2):
        f0 = 62 + 16 * k
        s["groan%d" % k] = make_sound(
            lambda t, u, f0=f0: (((t * (f0 + 12 * math.sin(tau * 4 * t))) % 1.0) * 2 - 1) * 0.35 * math.sin(math.pi * u) ** 1.5
            + r(-0.1, 0.1) * math.sin(math.pi * u), 0.9, 0.55)
    s["wave"] = make_sound(lambda t, u: (math.sin(tau * 440 * t) + math.sin(tau * 660 * t)) * 0.3 * math.exp(-t * 4), 0.6, 0.5)
    s["cast"] = make_sound(lambda t, u: math.sin(tau * (220 + 880 * u) * t) * 0.45 * (1 - u) + r(-0.2, 0.2) * math.exp(-t * 12), 0.35, 0.7)
    s["fire"] = make_sound(lambda t, u: (r(-1, 1) * 0.7 + math.sin(tau * 90 * t) * 0.4) * math.exp(-t * 8), 0.4, 0.75)
    s["water"] = make_sound(lambda t, u: math.sin(tau * (520 - 220 * u) * t) * 0.5 * (1 - u) + r(-0.15, 0.15) * (1 - u), 0.35, 0.65)
    s["earth"] = make_sound(lambda t, u: r(-1, 1) * 0.8 * math.exp(-t * 9) + math.sin(tau * 40 * t) * 0.5 * math.exp(-t * 6), 0.45, 0.8)
    s["air"] = make_sound(lambda t, u: r(-1, 1) * 0.55 * math.exp(-t * 6) * (1.0 - 0.4 * u), 0.4, 0.6)
    s["lightning"] = make_sound(lambda t, u: r(-1, 1) * math.exp(-t * 18) + math.sin(tau * 1800 * t) * 0.35 * math.exp(-t * 14), 0.28, 0.8)
    s["dark"] = make_sound(lambda t, u: math.sin(tau * (90 + 40 * math.sin(tau * 3 * t)) * t) * 0.55 * (1 - u), 0.5, 0.7)
    s["light"] = make_sound(lambda t, u: (math.sin(tau * 880 * t) + math.sin(tau * 1320 * t)) * 0.35 * math.exp(-t * 5), 0.5, 0.65)
    return s


# ============================================================== ANDROID DOKUNMATİK KONTROL
_TOUCH_EVENTS = (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP)
JOY_R = 150.0        # sanal joystick yarıçapı (px)
JOY_DEAD = 0.3       # joystick ölü bölgesi
LOOK_GAIN = 1.4      # dokunmatik bakış hassasiyeti
JOY_ZONE_X = 950     # bu x'in solundaki alt bölge joystick için ayrılır
JOY_ZONE_Y = 420


def _post_key(key, ch=""):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=ch, scancode=0))


class _KeyOverlay:
    """pygame.key.get_pressed() sonucunu sanal (dokunmatik) tuşlarla birleştirir."""
    def __init__(self, base, extra):
        self.base = base
        self.extra = extra

    def __getitem__(self, k):
        return bool(self.base[k]) or self.extra.get(k, False)


class TouchControls:
    # (ad, tür, klavye tuşu, x, y, yarıçap, etiket)
    # tür: hold = basılı tutulur | key = tek tuş olayı | elem = element değiştir
    PLAY_BUTTONS = [
        ("fire", "hold", None, 1760, 880, 105, "ATEŞ"),
        ("ads", "hold", None, 1560, 900, 70, "NİŞAN"),
        ("jump", "hold", None, 1760, 700, 72, "ZIPLA"),
        ("sprint", "hold", None, 1560, 720, 66, "KOŞ"),
        ("q", "key", pygame.K_q, 1420, 470, 58, "Q"),
        ("e", "key", pygame.K_e, 1580, 470, 58, "E"),
        ("t", "key", pygame.K_t, 1740, 470, 58, "T"),
        ("elem", "elem", None, 1870, 330, 52, "ELEM"),
        ("pause", "key", pygame.K_p, 1740, 80, 48, "II"),
        ("menu", "key", pygame.K_ESCAPE, 1860, 80, 48, "MENU"),
    ]
    MENU_ROW_Y = 330     # menü satırları: 330 + 75*i ... 405 + 75*i
    MENU_ROW_H = 75

    def __init__(self):
        self.active = IS_ANDROID
        self.held = {}
        self.axis = (0.0, 0.0)
        self.look_dx = 0.0
        self.look_dy = 0.0
        self.fingers = {}
        self.joy_id = None
        self.joy_o = (300, 800)

    # ------------------------------------------------ olaylar
    def handle(self, e, state, menu_sel, elem):
        if not self.active:
            return
        px, py = e.x * SCREEN_W, e.y * SCREEN_H
        if e.type == pygame.FINGERDOWN:
            self._down(e.finger_id, px, py, state, menu_sel, elem)
        elif e.type == pygame.FINGERMOTION:
            self._motion(e.finger_id, px, py)
        elif e.type == pygame.FINGERUP:
            self._up(e.finger_id)

    def _down(self, fid, px, py, state, menu_sel, elem):
        if state == "menu":
            self._menu_tap(px, py, menu_sel)
            return
        if state == "dead":
            _post_key(pygame.K_RETURN, "\r")
            return
        if state != "play":
            return
        for name, kind, key, bx, by, r, _ in self.PLAY_BUTTONS:
            if (px - bx) ** 2 + (py - by) ** 2 <= (r * 1.15) ** 2:
                if kind == "hold":
                    self.held[name] = True
                    self.fingers[fid] = {"role": "hold", "name": name}
                elif kind == "key":
                    _post_key(key)
                elif kind == "elem":
                    _post_key(pygame.K_1 + (elem + 1) % 7)
                return
        if px < JOY_ZONE_X and py > JOY_ZONE_Y and self.joy_id is None:
            self.joy_id = fid
            self.joy_o = (px, py)
            self.axis = (0.0, 0.0)
            self.fingers[fid] = {"role": "joy"}
        else:
            self.fingers[fid] = {"role": "look", "x": px, "y": py}

    def _motion(self, fid, px, py):
        f = self.fingers.get(fid)
        if not f:
            return
        if f["role"] == "look":
            self.look_dx += (px - f["x"]) * LOOK_GAIN
            self.look_dy += (py - f["y"]) * LOOK_GAIN
            f["x"], f["y"] = px, py
        elif f["role"] == "joy":
            ox, oy = self.joy_o
            ax = max(-1.0, min(1.0, (px - ox) / JOY_R))
            ay = max(-1.0, min(1.0, -(py - oy) / JOY_R))
            self.axis = (ax, ay)

    def _up(self, fid):
        f = self.fingers.pop(fid, None)
        if not f:
            return
        if f["role"] == "hold":
            self.held[f["name"]] = False
        elif f["role"] == "joy":
            self.joy_id = None
            self.axis = (0.0, 0.0)

    def _menu_tap(self, px, py, sel):
        # ARA (F5) düğmesi: yalnızca "Sunucuya Katıl" satırındayken görünür
        if sel == 2 and abs(px - 960) <= 110 and abs(py - 880) <= 50:
            _post_key(pygame.K_F5)
            return
        for i in range(3):
            top = self.MENU_ROW_Y + self.MENU_ROW_H * i
            if top <= py < top + self.MENU_ROW_H and 380 <= px <= 1540:
                d = i - sel
                if d == 0:
                    _post_key(pygame.K_RETURN, "\r")
                else:
                    key = pygame.K_DOWN if d > 0 else pygame.K_UP
                    for _ in range(abs(d)):
                        _post_key(key)
                return

    def reset_holds(self):
        self.held.clear()
        self.axis = (0.0, 0.0)

    # ------------------------------------------------ oyun girdisi
    def merge(self, keys, mx, my):
        """Android'de klavye/fare yerine yalnız dokunmatik durumu kullanılır.
        Dönüş: (tuş durumu, fare tuşları, bakış dx, bakış dy)"""
        dx, dy = self.look_dx, self.look_dy
        self.look_dx = self.look_dy = 0.0
        vk = {}
        ax, ay = self.axis
        if ay > JOY_DEAD:
            vk[pygame.K_w] = True
        elif ay < -JOY_DEAD:
            vk[pygame.K_s] = True
        if ax > JOY_DEAD:
            vk[pygame.K_d] = True
        elif ax < -JOY_DEAD:
            vk[pygame.K_a] = True
        if self.held.get("jump"):
            vk[pygame.K_SPACE] = True
        if self.held.get("sprint"):
            vk[pygame.K_LSHIFT] = True
        mb = (bool(self.held.get("fire")), False, bool(self.held.get("ads")))
        return _KeyOverlay(keys, vk), mb, dx, dy

    # ------------------------------------------------ çizim
    @staticmethod
    def _btn(surf, font, x, y, r, label, on=False):
        pygame.draw.circle(surf, (60, 70, 100) if on else (20, 24, 36), (x, y), r)
        pygame.draw.circle(surf, (210, 215, 235), (x, y), r, 3)
        t = font.render(label, True, (255, 255, 255))
        surf.blit(t, t.get_rect(center=(x, y)))

    def draw(self, surf, font, state, menu_sel, elem):
        if not self.active:
            return
        if state == "menu":
            if menu_sel == 2:
                self._btn(surf, font, 960, 880, 85, "ARA (F5)")
            return
        if state != "play":
            return
        if self.joy_id is not None:
            ox, oy = self.joy_o
            pygame.draw.circle(surf, (90, 100, 120), (ox, oy), int(JOY_R), 2)
            kx = ox + self.axis[0] * JOY_R
            ky = oy - self.axis[1] * JOY_R
            pygame.draw.circle(surf, (200, 210, 230), (int(kx), int(ky)), 40)
        else:
            pygame.draw.circle(surf, (90, 100, 120), (300, 800), int(JOY_R), 2)
        for name, kind, key, bx, by, r, label in self.PLAY_BUTTONS:
            if kind == "hold":
                on = self.held.get(name, False)
            else:
                on = False
            self._btn(surf, font, bx, by, r, label, on)


# ============================================================== OYUN
class Game:
    def __init__(self):
        self.audio = False
        try:
            pygame.mixer.init(RATE, -16, 1, 512, allowedchanges=0)
            if tuple(pygame.mixer.get_init()) == (RATE, -16, 1):
                self.audio = True
                pygame.mixer.set_num_channels(24)
        except Exception:
            self.audio = False
        pygame.init()
        try:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN | pygame.SCALED)
        except pygame.error:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("ZOMBİ AVI 3D")
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
        try:
            pygame.scrap.init()
        except Exception:
            pass
        self.clock = pygame.time.Clock()
        self.low = pygame.Surface((RW, RH)).convert()
        self.font = pygame.font.SysFont("arial", 36, bold=True)
        self.big = pygame.font.SysFont("arial", 130, bold=True)
        self.mid = pygame.font.SysFont("arial", 54, bold=True)
        self.small = pygame.font.SysFont("arial", 28)
        self.tiny = pygame.font.SysFont("arial", 18, bold=True)
        self.pop_font = pygame.font.SysFont("arial", 34, bold=True)
        self.vignette = pygame.Surface((SCREEN_W, SCREEN_H))
        self.cam = Cam()
        self.snd = build_sounds() if self.audio else {}
        self.highscore = self.load_high()
        self.net = NetLink()
        self.p2 = None
        self.net_timer = 0.0
        self.join_ip = ""
        self.menu_sel = 0
        self.state = "menu"
        self.visual_only = False
        self.remote_ctx = False
        self.own = None
        self._txt_cache = {}
        self._mm_base = None
        self.touch = TouchControls()
        self._ti_on = False
        self.reset()

    # ----------------------------------------------------- yardımcılar
    def load_high(self):
        try:
            with open(HIGHSCORE_FILE) as f:
                return int(f.read().strip())
        except Exception:
            return 0

    def save_high(self):
        try:
            with open(HIGHSCORE_FILE, "w") as f:
                f.write(str(self.highscore))
        except Exception:
            pass

    def play(self, name, vol=1.0):
        if self.audio and name in self.snd:
            s = self.snd[name]
            s.set_volume(max(0.0, min(1.0, vol)))
            s.play()

    def reset(self, keep_net=False):
        if getattr(self, "net", None) and self.net.mode == "client":
            self.p = Player(5.5, 2.5, 0.78)
            self.p2 = Player(2.5, 2.5, 0.78)
        else:
            self.p = Player(2.5, 2.5, 0.78)
            self.p2 = Player(5.5, 2.5, 0.78)
        self.own = self.p
        self.zombies = []
        self.particles = []
        self.popups = []
        self.bolts = []
        self.beams = []
        self.rings = []
        self.props = []
        self.fire_zones = []
        self.water_zones = []
        self.spell_zones = []
        self.wave = 1
        self.to_spawn = self.wave_size()
        self.spawn_t = 1.5
        self.intermission = 0.0
        self.flash = 0.0
        self.hurt = 0.0
        self.hitmark = 0.0
        self.hit_head = False
        self.killmark = 0.0
        self.ads = 0.0
        self.kick_p = self.kick_y = 0.0
        self.bloom = 0.0
        self.sway_x = self.sway_y = 0.0
        self.recoil_vis = 0.0
        self.move_amt = 0.0
        self.combo = 0
        self.combo_t = 0.0
        self.banner = ("DALGA 1", 3.0)
        self.bonus_lines = []
        self.state = "play" if keep_net else "menu"
        self.time = 0.0
        self.net_timer = 0.0
        self.flow = None
        self.flow_cell = None
        self.boost = 0.0
        self.spell_flash = 0.0
        self.spell_col = (255, 255, 255)
        pygame.mouse.get_rel()
        self.update_camera()

    def wave_size(self):
        return 5 + self.wave * 3

    def combo_mult(self):
        return min(5.0, 1.0 + 0.5 * max(0, self.combo - 1))

    def spread(self):
        sp = 0.006 + (1 - self.ads) * 0.020 + self.bloom + self.move_amt * 0.018
        if self.p.jump > 0:
            sp += 0.03
        return sp

    def update_camera(self):
        p = self.p
        eye = EYE_H + p.jump + math.sin(p.bob) * 0.035 * self.move_amt
        pitch = max(-1.5, min(1.5, p.pitch + self.kick_p))
        self.cam.set(p.x, p.y, eye, p.yaw + self.kick_y, pitch, 1.0 + 0.65 * self.ads)

    def tick_player(self, pl, dt):
        pl.fire_cd = max(0.0, pl.fire_cd - dt)
        pl.spell_cd = max(0.0, pl.spell_cd - dt)
        for eid in pl.skill_cd:
            pl.skill_cd[eid] = [max(0.0, t - dt) for t in pl.skill_cd[eid]]
        pl.mana = min(MANA_MAX, pl.mana + MANA_REGEN * dt)

    def heal_self(self, amount):
        """Yalnızca yetkili tarafta (solo/host) can ekler. Görsel modda etkisizdir."""
        if self.visual_only or amount <= 0:
            return
        self.p.hp = min(100, self.p.hp + amount)

    # ----------------------------------------------------- GÜNCELLEME
    def update(self, dt):
        p = self.p
        self.time += dt
        keys = pygame.key.get_pressed()
        mb = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_rel()
        if IS_ANDROID:
            keys, mb, mx, my = self.touch.merge(keys, mx, my)

        sens = MOUSE_SENS * (1.0 - 0.5 * self.ads)
        p.yaw -= mx * sens
        p.pitch = max(-1.45, min(1.45, p.pitch - my * sens))
        k = min(1.0, dt * 9)
        self.sway_x += (max(-80, min(80, -mx * 1.2)) - self.sway_x) * k
        self.sway_y += (max(-60, min(60, -my * 1.2)) - self.sway_y) * k

        sprint = keys[pygame.K_LSHIFT] and not mb[2]
        dx, dy = math.cos(p.yaw), math.sin(p.yaw)
        rx, ry = math.sin(p.yaw), -math.cos(p.yaw)
        ix = iy = 0.0
        if keys[pygame.K_w]: ix += dx; iy += dy
        if keys[pygame.K_s]: ix -= dx; iy -= dy
        if keys[pygame.K_d]: ix += rx; iy += ry
        if keys[pygame.K_a]: ix -= rx; iy -= ry
        ln = math.hypot(ix, iy)
        sp = MOVE_SPEED * (SPRINT_MULT if sprint else 1.0) * (1.0 - 0.45 * self.ads)
        tvx = ix / ln * sp if ln else 0.0
        tvy = iy / ln * sp if ln else 0.0
        acc = min(1.0, dt * (13 if p.jump <= 0 else 3))
        p.vx += (tvx - p.vx) * acc
        p.vy += (tvy - p.vy) * acc
        if free_circle(p.x + p.vx * dt, p.y, 0.24):
            p.x += p.vx * dt
        else:
            p.vx = 0
        if free_circle(p.x, p.y + p.vy * dt, 0.24):
            p.y += p.vy * dt
        else:
            p.vy = 0
        speed = math.hypot(p.vx, p.vy)
        self.move_amt = min(1.0, speed / MOVE_SPEED) if p.jump <= 0 else self.move_amt * 0.9
        if self.move_amt > 0.05:
            p.bob += dt * (6 + 5 * min(1.0, speed / MOVE_SPEED))
        if keys[pygame.K_SPACE] and p.jump <= 0 and p.vj <= 0:
            p.vj = 5.0
        if p.jump > 0 or p.vj > 0:
            p.vj -= GRAVITY * dt
            p.jump += p.vj * dt
            if p.jump <= 0:
                p.jump = 0.0
                p.vj = 0.0

        want_ads = 1.0 if (mb[2] and not sprint) else 0.0
        self.ads += (want_ads - self.ads) * min(1.0, dt * 10)

        self.kick_p -= self.kick_p * min(1.0, dt * 5)
        self.kick_y -= self.kick_y * min(1.0, dt * 5)
        self.bloom = max(0.0, self.bloom - dt * 0.07)
        self.recoil_vis = max(0.0, self.recoil_vis - dt * 9)
        self.tick_player(p, dt)
        if self.net.mode == "host" and self.p2:
            self.tick_player(self.p2, dt)
        self.flash = max(0.0, self.flash - dt)
        self.spell_flash = max(0.0, self.spell_flash - dt)
        self.hurt = max(0.0, self.hurt - dt)
        self.hitmark = max(0.0, self.hitmark - dt)
        self.killmark = max(0.0, self.killmark - dt)
        if self.combo_t > 0:
            self.combo_t -= dt
            if self.combo_t <= 0:
                self.combo = 0
        if self.banner[1] > 0:
            self.banner = (self.banner[0], self.banner[1] - dt)

        self.update_camera()

        if mb[0] and p.fire_cd <= 0:
            if p.mana >= STAFF_MANA:
                self.staff_attack()
            else:
                p.fire_cd = 0.35
                self.play("empty", 0.45)

        self.update_flow()
        self.update_zombies(dt)
        self.update_bolts(dt)
        self.update_beams(dt)
        self.update_fire_zones(dt)
        self.update_water_zones(dt)
        self.update_spell_zones(dt)
        self.update_fx(dt)
        self.update_particles(dt)
        self.update_popups(dt)
        self.update_waves(dt)
        self.boost = 0.55 if self.flash > 0 or self.spell_flash > 0 else 0.0

        self.net_timer += dt
        if self.net_timer >= NET_TICK:
            self.net_timer = 0.0
            self.net_sync()

        if self.net.mode == "solo":
            if p.hp <= 0:
                self.state = "dead"
                if p.score > self.highscore:
                    self.highscore = p.score
                    self.save_high()
        elif self.net.mode == "host":
            if p.hp <= 0 and (not self.p2 or self.p2.hp <= 0):
                self.state = "dead"
                total = p.score + (self.p2.score if self.p2 else 0)
                if total > self.highscore:
                    self.highscore = total
                    self.save_high()

    def net_sync(self):
        net = self.net
        if net.mode == "solo" or not net.connected():
            return
        if net.mode == "host":
            zlist = []
            for z in self.zombies:
                if not z.alive and getattr(z, "dying", 0) > 0.5:
                    continue
                zlist.append({"x": round(z.x, 3), "y": round(z.y, 3), "face": round(z.face, 3),
                              "hp": int(z.hp), "alive": z.alive, "phase": round(z.phase, 2),
                              "maxhp": int(z.maxhp)})
            net.send({"t": "state", "p1": self.p.snapshot(),
                      "p2": self.p2.snapshot() if self.p2 else None,
                      "z": zlist, "wave": self.wave, "to_spawn": self.to_spawn,
                      "intermission": round(self.intermission, 2), "state": self.state})
        elif net.mode == "client":
            net.send({"t": "player", "p": self.p.snapshot()})
        for msg in net.recv_all():
            typ = msg.get("t")
            if net.mode == "host":
                if typ == "player" and self.p2 and "p" in msg:
                    s = msg["p"]
                    self.p2.x = s.get("x", self.p2.x); self.p2.y = s.get("y", self.p2.y)
                    self.p2.yaw = s.get("yaw", self.p2.yaw); self.p2.pitch = s.get("pitch", self.p2.pitch)
                    self.p2.elem = s.get("elem", self.p2.elem); self.p2.jump = s.get("jump", 0)
                elif typ == "atk" and msg.get("kind") == "staff":
                    o = msg.get("o", [0, 0, 1.6])
                    d = msg.get("d", [1, 0, 0])
                    o = (float(o[0]), float(o[1]), float(o[2]))
                    d = (float(d[0]), float(d[1]), float(d[2]))
                    self.remote_staff_attack(o, d, int(msg.get("elem", 0)))
                elif typ == "skill":
                    self._host_run_client_skill(int(msg.get("idx", 0)), int(msg.get("elem", 0)))
            elif net.mode == "client":
                if typ == "state":
                    if msg.get("p1") and self.p2:
                        self.p2.apply_snapshot(msg["p1"])
                    if msg.get("p2"):
                        s = msg["p2"]
                        self.p.hp = s.get("hp", self.p.hp)
                        if "score" in s:
                            self.p.score = s["score"]
                        if "kills" in s:
                            self.p.kills = s["kills"]
                        if "mana" in s:
                            self.p.mana = s["mana"]
                    zlist = msg.get("z", [])
                    while len(self.zombies) < len(zlist):
                        self.zombies.append(Zombie(2, 2, self.wave))
                    self.zombies = self.zombies[:len(zlist)]
                    for i, zd in enumerate(zlist):
                        z = self.zombies[i]
                        z.x, z.y = zd["x"], zd["y"]
                        z.face = zd.get("face", 0); z.hp = zd.get("hp", 100)
                        z.maxhp = zd.get("maxhp", 100); z.alive = zd.get("alive", True)
                        z.phase = zd.get("phase", 0)
                        if not z.alive and z.dying <= 0:
                            z.dying = 0.01
                    self.wave = msg.get("wave", self.wave)
                    self.to_spawn = msg.get("to_spawn", self.to_spawn)
                    self.intermission = msg.get("intermission", 0)
                    if msg.get("state") == "dead":
                        self.state = "dead"
                elif typ == "fx" and msg.get("kind") == "staff":
                    o = msg.get("o", [0, 0, 1.6])
                    d = msg.get("d", [1, 0, 0])
                    o = (float(o[0]), float(o[1]), float(o[2]))
                    d = (float(d[0]), float(d[1]), float(d[2]))
                    if msg.get("from_peer"):
                        if msg.get("hit"):
                            hx, hy, hz = float(msg["hx"]), float(msg["hy"]), float(msg["hz"])
                            head = bool(msg.get("head"))
                            self.hitmark = 0.15
                            self.hit_head = head
                            self.spawn_particles((hx, hy, hz), 12 if head else 7, (170, 15, 15), 0.05, 3.2)
                            self.play("head" if head else "hit", 0.75)
                    else:
                        self._play_remote_staff_fx(o, d, msg)
                elif typ == "fx" and msg.get("kind") == "burst":
                    pos = msg.get("pos", [0, 0, 1])
                    col = tuple(msg.get("col", [200, 200, 255]))
                    self.spawn_particles((float(pos[0]), float(pos[1]), float(pos[2])),
                                         int(msg.get("n", 12)), col, 0.05, 3.0)
                elif typ == "cast":
                    if self.p2:
                        self.p2.elem = int(msg.get("elem", 0)) % len(ELEMENTS)
                        with self._as_player(self.p2, visual=True):
                            self.try_elem_skill(int(msg.get("idx", 0)))

    def _play_remote_staff_fx(self, o, d, msg):
        try:
            col = ELEMENTS[self.p2.elem % len(ELEMENTS)]["col"]
        except Exception:
            col = (180, 200, 255)
        hit = bool(msg.get("hit"))
        hp = (float(msg["hx"]), float(msg["hy"]), float(msg["hz"])) if hit else None
        self._tracer(o, d, math.dist(hp, o) if hit else 40.0, col)
        if hit:
            self.spawn_particles(hp, 12 if msg.get("head") else 7, (170, 15, 15), 0.05, 3.2)

    def _host_run_client_skill(self, idx, elem):
        p2 = self.p2
        if not p2 or p2.hp <= 0:
            return
        p2.elem = elem % len(ELEMENTS)
        with self._as_player(p2):
            self.try_elem_skill(idx)

    @contextmanager
    def _as_player(self, pl, visual=False):
        saved = (self.p, dict(self.cam.__dict__), self.visual_only, self.remote_ctx)
        self.p = pl
        self.cam.set(pl.x, pl.y, EYE_H + pl.jump, pl.yaw, pl.pitch, 1.0)
        self.visual_only = visual
        self.remote_ctx = pl is not self.own
        try:
            yield
        finally:
            self.p, cam_state, self.visual_only, self.remote_ctx = saved
            self.cam.__dict__.update(cam_state)

    def _cast_feedback(self, col):
        if not self.remote_ctx:
            self.spell_flash = 0.12
            self.spell_col = col
            self.kick_p += 0.012
        self.play("cast", 0.5)

    def request_skill(self, idx):
        if self.net.mode == "client" and self.net.connected():
            eid = self.current_elem()["id"]
            sk = ELEMENT_SKILLS[eid][idx]
            if self.p.skill_cd[eid][idx] > 0:
                return
            if self.p.mana < sk["mana"]:
                self.play("empty", 0.45)
                return
            self.p.mana -= sk["mana"]
            self.p.skill_cd[eid][idx] = sk["cd"]
            self.net.send({"t": "skill", "idx": idx, "elem": self.p.elem})
            with self._as_player(self.p, visual=True):
                self.try_elem_skill(idx)
        elif self.try_elem_skill(idx):
            if self.net.mode == "host" and self.net.connected():
                self.net.send({"t": "cast", "idx": idx, "elem": self.p.elem})

    def cast_spell(self):
        self.request_skill(0)

    def try_hotkey_skill(self, idx):
        self.request_skill(idx)

    # ----------------------------------------------------- ATEŞ ETME
    def ray_world(self, o, d):
        t = 0.0
        while t < 70.0:
            t += 0.08
            x, y, z = o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t
            if z <= 0:
                return t
            if z > WALL_H and d[2] > 0:
                return 999.0
            if z <= WALL_H and is_wall(x, y):
                return t
        return 999.0

    def ray_zombie(self, o, d, z, tmax):
        wx, wy, wz = z.x - o[0], z.y - o[1], 0.9 - o[2]
        t0 = wx * d[0] + wy * d[1] + wz * d[2]
        if t0 < -1.3 or t0 > tmax + 1.3:
            return None
        if wx * wx + wy * wy + wz * wz - t0 * t0 > 1.5:
            return None
        ca, sa = math.cos(z.face), math.sin(z.face)
        ox, oy = o[0] - z.x, o[1] - z.y
        lo = (ox * ca + oy * sa, -ox * sa + oy * ca, o[2])
        ld = (d[0] * ca + d[1] * sa, -d[0] * sa + d[1] * ca, d[2])
        best = None
        for name, b, col, mult, hit, emi in zombie_boxes(z):
            if not hit:
                continue
            t = ray_box(lo, ld, b)
            if t is not None and t < tmax and (best is None or t < best[0]):
                best = (t, name, mult)
        return best

    def _tracer(self, o, d, dist, col):
        dist = min(dist, 40.0)
        end = (o[0] + d[0] * dist, o[1] + d[1] * dist, o[2] + d[2] * dist)
        self.add_beam(o, end, col, 0.12, 3)
        self.add_beam(o, end, (255, 255, 255), 0.08, 1)

    def _clip_seg(self, a, b):
        cam = self.cam
        da = (a[0] - cam.x) * cam.fx + (a[1] - cam.y) * cam.fy + (a[2] - cam.z) * cam.fz
        db = (b[0] - cam.x) * cam.fx + (b[1] - cam.y) * cam.fy + (b[2] - cam.z) * cam.fz
        if da < NEAR and db < NEAR:
            return None
        if da < NEAR or db < NEAR:
            t = (NEAR - da) / (db - da)
            q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
            if da < NEAR:
                a = q
            else:
                b = q
        return a, b

    def _proj(self, p):
        cam = self.cam
        vx, vy, vz = p[0] - cam.x, p[1] - cam.y, p[2] - cam.z
        d = max(NEAR, vx * cam.fx + vy * cam.fy + vz * cam.fz)
        xs = vx * cam.rx + vy * cam.ry
        ys = vx * cam.ux + vy * cam.uy + vz * cam.uz
        return int(HW + xs / d * cam.focal), int(HH - ys / d * cam.focal)

    def staff_attack(self):
        p, cam = self.p, self.cam
        if p.mana < STAFF_MANA:
            return
        p.mana -= STAFF_MANA
        p.shots += 1
        p.fire_cd = STAFF_DELAY
        self.flash = 0.06
        self.recoil_vis = 1.0
        self.play("cast", 0.55)
        sp = self.spread()
        a = random.uniform(0, math.tau)
        rr = sp * math.sqrt(random.random())
        ox_, oy_ = math.cos(a) * rr, math.sin(a) * rr
        d = (cam.fx + cam.rx * ox_ + cam.ux * oy_,
             cam.fy + cam.ry * ox_ + cam.uy * oy_,
             cam.fz + cam.uz * oy_)
        dl = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
        d = (d[0] / dl, d[1] / dl, d[2] / dl)
        o = (cam.x, cam.y, cam.z)
        self.kick_p += (0.016 - 0.007 * self.ads) * random.uniform(0.8, 1.2)
        self.kick_y += random.uniform(-0.006, 0.006) * (1 - 0.5 * self.ads)
        self.bloom = min(0.045, self.bloom + 0.006)

        if self.net.mode == "client" and self.net.connected():
            self.net.send({
                "t": "atk", "kind": "staff",
                "o": [round(o[0], 3), round(o[1], 3), round(o[2], 3)],
                "d": [round(d[0], 4), round(d[1], 4), round(d[2], 4)],
                "elem": p.elem,
            })
            self._staff_vfx_only(o, d)
            return

        hit_info = self._staff_resolve(o, d, shooter=p)
        if self.net.mode == "host" and self.net.connected():
            self.net.send({
                "t": "fx", "kind": "staff",
                "o": [round(o[0], 3), round(o[1], 3), round(o[2], 3)],
                "d": [round(d[0], 4), round(d[1], 4), round(d[2], 4)],
                "hit": 1 if hit_info else 0,
                "hx": round(hit_info[0], 3) if hit_info else 0,
                "hy": round(hit_info[1], 3) if hit_info else 0,
                "hz": round(hit_info[2], 3) if hit_info else 0,
                "head": 1 if hit_info and hit_info[3] else 0,
            })

    def _staff_vfx_only(self, o, d):
        wall_t = self.ray_world(o, d)
        best, best_t = None, wall_t
        for z in self.zombies:
            if not z.alive:
                continue
            res = self.ray_zombie(o, d, z, best_t)
            if res and res[0] < best_t:
                best_t = res[0]
                best = (z, res[1], res[2])
        self._tracer(o, d, best_t, ELEMENTS[self.p.elem % len(ELEMENTS)]["col"])
        hx, hy, hz = o[0] + d[0] * best_t, o[1] + d[1] * best_t, o[2] + d[2] * best_t
        if best is None:
            if best_t < 900:
                self.spawn_particles((hx, hy, max(0.03, hz)), 5, (190, 190, 170), 0.04, 2.2)
            return
        z, name, _ = best
        z.hit_timer = 0.12
        head = name == "head"
        self.hitmark = 0.12
        self.hit_head = head
        self.spawn_particles((hx, hy, hz), 10 if head else 6, (170, 15, 15), 0.05, 3.0)
        self.play("head" if head else "hit", 0.7)

    def _friendly_fire_target(self, shooter=None):
        """LAN eşli oyununda atıcının vurabileceği diğer oyuncuyu döndürür."""
        if self.net.mode != "host" or not self.net.connected():
            return None
        shooter = shooter or self.p
        local_player = self.own if self.own is not None else self.p
        target = self.p2 if shooter is local_player else local_player
        if target is None or target.hp <= 0:
            return None
        return target

    def _damage_teammate(self, shooter, damage, x=None, y=None, radius=0.65, z=None):
        """Yetkili sunucuda takım arkadaşına hasar uygular; solo/istemci görselinde çalışmaz."""
        if self.visual_only or self.net.mode != "host":
            return False
        target = self._friendly_fire_target(shooter)
        if target is None:
            return False
        if x is not None and y is not None and math.hypot(target.x - x, target.y - y) > radius:
            return False
        if z is not None and abs((EYE_H + target.jump) - z) > 1.8:
            return False
        target.hp = max(0, target.hp - max(1, int(damage)))
        if target is self.p:
            self.hurt = max(self.hurt, 0.35)
        self.add_popup((target.x, target.y, 1.7), "TAKIM HASARI -%d" % max(1, int(damage)),
                       (255, 90, 90), 0.8)
        self.spawn_particles((target.x, target.y, 1.0), 8, (255, 70, 70), 0.06, 2.8)
        return True

    def _staff_resolve(self, o, d, shooter=None):
        if shooter is None:
            shooter = self.p
        wall_t = self.ray_world(o, d)
        best, best_t = None, wall_t
        for z in self.zombies:
            if not z.alive:
                continue
            res = self.ray_zombie(o, d, z, best_t)
            if res and res[0] < best_t:
                best_t = res[0]
                best = (z, res[1], res[2])
        # Takım arkadaşı zombiden önce ışının üzerindeyse mermiyi o karşılar.
        teammate = self._friendly_fire_target(shooter)
        teammate_hit_t = None
        if teammate is not None:
            # Oyuncuyu gövde çevresinde yaklaşık daire/silindir olarak ele al.
            vx, vy = teammate.x - o[0], teammate.y - o[1]
            proj = vx * d[0] + vy * d[1]
            if 0.0 < proj < best_t:
                closest_x = o[0] + d[0] * proj
                closest_y = o[1] + d[1] * proj
                if math.hypot(teammate.x - closest_x, teammate.y - closest_y) < 0.38:
                    hit_z = o[2] + d[2] * proj
                    if 0.35 < hit_z < 2.15 + teammate.jump:
                        teammate_hit_t = proj
                        best_t = proj
        hx = o[0] + d[0] * best_t
        hy = o[1] + d[1] * best_t
        hz = o[2] + d[2] * best_t
        shot_col = ELEMENTS[getattr(shooter, "elem", 0) % len(ELEMENTS)]["col"]
        self._tracer(o, d, best_t, shot_col)
        col = shot_col
        for i in range(5):
            t = min(best_t, 12) * (i + 1) / 6
            self.spawn_particles((o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t), 1, col, 0.03, 1.0)
        if teammate_hit_t is not None:
            damage = int(STAFF_DAMAGE * random.uniform(0.93, 1.07))
            self._damage_teammate(shooter, damage, z=hz)
            return (hx, hy, hz, False)
        if best is None:
            if best_t < 900:
                self.spawn_particles((hx, hy, max(0.03, hz)), 6, (190, 190, 170), 0.04, 2.5)
            return None
        z, name, mult = best
        dmg = int(STAFF_DAMAGE * mult * random.uniform(0.93, 1.07))
        if z.weaken > 0:
            dmg = int(dmg * 1.35)
        dealt = min(dmg, z.hp)
        z.hp -= dmg
        z.hit_timer = 0.1
        z.stun = 0.35 if name == "head" else 0.15
        if name.startswith("leg"):
            z.speed_mult = max(0.45, z.speed_mult - 0.18)
        head = name == "head"
        shooter.hits = getattr(shooter, "hits", 0) + 1
        if head:
            shooter.headshots = getattr(shooter, "headshots", 0) + 1
        if shooter is self.p:
            self.hitmark = 0.15
            self.hit_head = head
        self.spawn_particles((hx, hy, hz), 14 if head else 8, (170, 15, 15), 0.05, 3.5)
        self.play("head" if head else "hit", 0.8)
        pts = max(1, int(dealt * 0.3))
        shooter.score = getattr(shooter, "score", 0) + pts
        zone = ZONE_NAMES.get(name, "")
        pcol = (255, 210, 60) if head else ((255, 255, 255) if name == "torso" else (140, 200, 255))
        self.add_popup((hx, hy, hz + 0.1), "%s +%d" % (zone, pts), pcol, 0.9)
        if z.hp <= 0:
            self.kill_zombie(z, head, shooter=shooter)
        return (hx, hy, hz, head)

    def remote_staff_attack(self, o, d, elem=0):
        p2 = self.p2
        if not p2 or p2.hp <= 0 or p2.mana < STAFF_MANA:
            return
        p2.elem = elem % len(ELEMENTS)
        p2.mana -= STAFF_MANA
        p2.shots += 1
        hit_info = self._staff_resolve(o, d, shooter=p2)
        if self.net.connected():
            self.net.send({
                "t": "fx", "kind": "staff",
                "o": [round(o[0], 3), round(o[1], 3), round(o[2], 3)],
                "d": [round(d[0], 4), round(d[1], 4), round(d[2], 4)],
                "hit": 1 if hit_info else 0,
                "hx": round(hit_info[0], 3) if hit_info else 0,
                "hy": round(hit_info[1], 3) if hit_info else 0,
                "hz": round(hit_info[2], 3) if hit_info else 0,
                "head": 1 if hit_info and hit_info[3] else 0,
                "from_peer": 1,
            })

    def kill_zombie(self, z, head, shooter=None):
        if shooter is None:
            shooter = self.p
        z.alive = False
        z.dying = 0.0
        shooter.kills = getattr(shooter, "kills", 0) + 1
        if shooter is self.p:
            self.combo += 1
            self.combo_t = 4.0
            self.killmark = 0.3
        m = self.combo_mult() if shooter is self.p else 1.0
        gain = int((100 + (150 if head else 0)) * m)
        shooter.score = getattr(shooter, "score", 0) + gain
        txt = ("KAFA ÖLDÜRME +%d" if head else "ÖLDÜRME +%d") % gain
        if m > 1:
            txt += "  x%.1f" % m
        self.add_popup((z.x, z.y, 1.9), txt, (255, 90, 60) if head else (255, 160, 90), 1.4)
        self.spawn_particles((z.x, z.y, 1.2), 22, (150, 10, 10), 0.06, 4.0)
        self.play("die", 0.7)

    # ----------------------------------------------------- GÖRSEL YARDIMCILAR
    def _jag_points(self, a, b, amp):
        """İki nokta arasında zikzaklı (şimşek benzeri) yol üretir."""
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        L = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        n = max(2, min(14, int(L / 0.7)))
        ux, uy, uz = dx / L, dy / L, dz / L
        hx, hy, hz = (0.0, 0.0, 1.0) if abs(uz) < 0.9 else (1.0, 0.0, 0.0)
        px, py, pz = uy * hz - uz * hy, uz * hx - ux * hz, ux * hy - uy * hx
        pl = math.sqrt(px * px + py * py + pz * pz) or 1.0
        px, py, pz = px / pl, py / pl, pz / pl
        qx, qy, qz = uy * pz - uz * py, uz * px - ux * pz, ux * py - uy * px
        pts = [a]
        for i in range(1, n):
            t = i / n
            j = amp * random.uniform(-1, 1)
            k = amp * random.uniform(-1, 1)
            pts.append((a[0] + dx * t + px * j + qx * k,
                        a[1] + dy * t + py * j + qy * k,
                        a[2] + dz * t + pz * j + qz * k))
        pts.append(b)
        return pts

    def add_beam(self, a, b, col, life, width=3, jag=0.0):
        pts = self._jag_points(a, b, jag) if jag > 0 else None
        self.beams.append({"a": a, "b": b, "pts": pts, "col": col,
                           "life": life, "max": life, "w": width})

    def add_ring(self, pos, r0, r1, col, life, w=0.12, z=0.05):
        self.rings.append({"x": pos[0], "y": pos[1], "z": z, "r0": r0, "r1": r1,
                           "r": r0, "w": w, "life": life, "max": life, "col": col})

    def add_prop(self, x, y, r, h, col, life, lean=(0.0, 0.0)):
        self.props.append({"x": x, "y": y, "r": r, "h": h, "col": col,
                           "life": life, "max": life, "lean": lean})

    def add_particle(self, pos, vel, life, col, size):
        self.particles.append([pos[0], pos[1], pos[2], vel[0], vel[1], vel[2], life, col, size])

    def update_fx(self, dt):
        for r in self.rings:
            r["life"] -= dt
            t = 1.0 - max(0.0, r["life"]) / r["max"]
            r["r"] = r["r0"] + (r["r1"] - r["r0"]) * t
        self.rings = [r for r in self.rings if r["life"] > 0]
        for pr in self.props:
            pr["life"] -= dt
        self.props = [pr for pr in self.props if pr["life"] > 0]

    def add_fx_items(self, items):
        """Halka (şok dalgası) ve yerden yükselen taş/diken prizmalarını çizim listesine ekler."""
        cam = self.cam
        px, py = cam.x, cam.y
        for r in self.rings:
            cx, cy = r["x"], r["y"]
            d2 = (cx - px) ** 2 + (cy - py) ** 2
            if d2 > DRAW_D2:
                continue
            fade = max(0.0, r["life"] / r["max"])
            col = tuple(min(255, int(c * (0.35 + 0.65 * fade))) for c in r["col"])
            ro = max(0.05, r["r"])
            ri = max(0.02, ro - r["w"])
            zz = r["z"]
            n = 20
            for i in range(n):
                a0 = i / n * math.tau
                a1 = (i + 1) / n * math.tau
                verts = [(cx + math.cos(a0) * ri, cy + math.sin(a0) * ri, zz),
                         (cx + math.cos(a1) * ri, cy + math.sin(a1) * ri, zz),
                         (cx + math.cos(a1) * ro, cy + math.sin(a1) * ro, zz),
                         (cx + math.cos(a0) * ro, cy + math.sin(a0) * ro, zz)]
                pts = cam.poly(verts)
                if pts:
                    items.append((d2, 0, col, pts, None))
        for pr in self.props:
            self._prop_items(pr, items)

    def _prop_items(self, pr, items):
        """Yükselen dört yüzlü taş/diken. Yükselme süresi boyunca büyür."""
        cam = self.cam
        px, py = cam.x, cam.y
        cx, cy = pr["x"], pr["y"]
        d2 = (cx - px) ** 2 + (cy - py) ** 2
        if d2 > DRAW_D2:
            return
        t = 1.0 - pr["life"] / pr["max"]
        rise = min(1.0, t * 6.0)
        h = pr["h"] * rise
        rr = pr["r"]
        lx, ly = pr["lean"]
        apex = (cx + lx * rise, cy + ly * rise, h)
        fade = max(0.35, min(1.0, pr["life"] / 0.45))
        col = tuple(int(c * fade) for c in pr["col"])
        corners = [(cx - rr, cy - rr), (cx + rr, cy - rr), (cx + rr, cy + rr), (cx - rr, cy + rr)]
        for i in range(4):
            c0 = corners[i]
            c1 = corners[(i + 1) % 4]
            mx, my = (c0[0] + c1[0]) * 0.5 - cx, (c0[1] + c1[1]) * 0.5 - cy
            ml = math.hypot(mx, my) or 1.0
            nx, ny = mx / ml, my / ml
            nz = 0.55
            nl = math.sqrt(nx * nx + ny * ny + nz * nz)
            nx, ny, nz = nx / nl, ny / nl, nz / nl
            lit = max(0.0, nx * LX + ny * LY + nz * LZ)
            verts = [(c0[0], c0[1], 0.0), (c1[0], c1[1], 0.0), apex]
            pts = cam.poly(verts)
            if pts:
                vcx = (c0[0] + c1[0]) * 0.5
                vcy = (c0[1] + c1[1]) * 0.5
                dd = (vcx - px) ** 2 + (vcy - py) ** 2
                items.append((dd, 0, self.sh(col, dd, lit), pts, None))

    # ----------------------------------------------------- ELEMENTAL BÜYÜ
    def current_elem(self):
        return ELEMENTS[self.p.elem]

    def aim_dir(self, spread=0.0):
        cam = self.cam
        if spread <= 0:
            d = (cam.fx, cam.fy, cam.fz)
        else:
            a = random.uniform(0, math.tau)
            rr = spread * math.sqrt(random.random())
            ox_, oy_ = math.cos(a) * rr, math.sin(a) * rr
            d = (cam.fx + cam.rx * ox_ + cam.ux * oy_,
                 cam.fy + cam.ry * ox_ + cam.uy * oy_,
                 cam.fz + cam.uz * oy_)
        dl = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
        return (d[0] / dl, d[1] / dl, d[2] / dl)

    def begin_cast(self, mana, cd_attr, cd_val, col):
        p = self.p
        if p.mana < mana:
            self.play("empty", 0.45)
            self.add_popup((p.x, p.y, EYE_H + 0.4), "MANA YETERSİZ", (140, 180, 255), 0.7)
            return False
        p.mana -= mana
        if cd_attr == "spell":
            p.spell_cd = cd_val
        elif isinstance(cd_attr, tuple):
            p.skill_cd[cd_attr[0]][cd_attr[1]] = cd_val
        else:
            p.skill_cd["fire"][cd_attr] = cd_val
        self._cast_feedback(col)
        return True

    def try_elem_skill(self, idx):
        el = self.current_elem()
        eid = el["id"]
        sk = ELEMENT_SKILLS[eid][idx]
        if self.visual_only:
            self._cast_feedback(el["col"])
        else:
            cds = self.p.skill_cd[eid]
            if cds[idx] > 0:
                return False
            if not self.begin_cast(sk["mana"], (eid, idx), sk["cd"], el["col"]):
                cds[idx] = 0.25
                return False
        {
            ("fire", "ball"): self.cast_fireball,
            ("fire", "ring"): self.cast_fire_ring,
            ("fire", "wall"): self.cast_fire_wall,
            ("water", "bolt"): self.cast_water,
            ("water", "tsunami"): self.cast_tsunami,
            ("water", "vortex"): self.cast_vortex,
            ("earth", "spikes"): self.cast_earth,
            ("earth", "grasp"): self.cast_earth_grasp,
            ("earth", "quake"): self.cast_earthquake,
            ("air", "gust"): self.cast_air,
            ("air", "whirl"): self.cast_whirlwind,
            ("air", "wave"): self.cast_storm_wave,
            ("lightning", "chain"): self.cast_lightning,
            ("lightning", "bolt"): self.cast_lightning_bolt,
            ("lightning", "storm"): self.cast_call_lightning,
            ("dark", "bolt"): self.cast_dark,
            ("dark", "arms"): self.cast_arms_of_hadar,
            ("dark", "hunger"): self.cast_hunger_of_hadar,
            ("light", "ray"): self.cast_light,
            ("light", "guardians"): self.cast_spirit_guardians,
            ("light", "sunburst"): self.cast_sunburst,
        }[(eid, sk["id"])]()
        return True

    def spawn_bolt(self, d, elem, speed, life, size):
        cam = self.cam
        col = next(e["col"] for e in ELEMENTS if e["id"] == elem)
        self.bolts.append({
            "x": cam.x + d[0] * 0.6, "y": cam.y + d[1] * 0.6, "z": cam.z + d[2] * 0.4,
            "dx": d[0] * speed, "dy": d[1] * speed, "dz": d[2] * speed,
            "elem": elem, "life": life, "r": size, "col": col,
        })

    def tint_zombie(self, z, col, t):
        z.elem_glow = col
        z.elem_glow_t = max(z.elem_glow_t, t)

    def deal_magic(self, z, dmg, hx, hy, hz, label, col, head=False, popup=True):
        """Hasarı hesaplar ve döndürür. Hasar/skor yalnızca yetkili tarafta (solo/host) uygulanır.
        İstemcide ve görsel modda dönüş değeri gerçek hesaplanır, böylece can çalma doğru tahmin edilir."""
        if z.weaken > 0:
            dmg = int(dmg * 1.35)
        dealt = min(dmg, z.hp)
        if self.visual_only or self.net.mode == "client":
            return dealt
        # Alan büyülerinin patlama/vuruş noktasına çok yakın takım arkadaşı da etkilenir.
        if self.net.mode == "host":
            self._damage_teammate(self.p, max(1, int(dmg * 0.45)), hx, hy, radius=0.7, z=hz)
        z.hp -= dmg
        z.hit_timer = 0.12
        z.stun = max(z.stun, 0.12)
        p = self.p
        self.hitmark = 0.15
        self.hit_head = False
        pts = max(1, int(dealt * 0.35))
        p.score += pts
        if popup:
            self.add_popup((hx, hy, hz + 0.15), "%s +%d" % (label, pts), col, 0.85)
        if z.hp <= 0:
            self.kill_zombie(z, head, shooter=p)
        return dealt

    def ignite(self, z, dps=16.0, dur=3.2):
        z.burn = max(z.burn, dur)
        z.burn_dps = max(z.burn_dps, dps)
        self.tint_zombie(z, (255, 95, 25), dur)

    def hit_scan_first(self, o, d, reach=28.0):
        wall_t = min(reach, self.ray_world(o, d))
        best, best_t = None, wall_t
        for z in self.zombies:
            if not z.alive:
                continue
            res = self.ray_zombie(o, d, z, best_t)
            if res and res[0] < best_t:
                best_t = res[0]
                best = (z, res[1], res[2])
        hx = o[0] + d[0] * best_t
        hy = o[1] + d[1] * best_t
        hz = o[2] + d[2] * best_t
        return best, best_t, (hx, hy, hz)

    def ground_aim(self, fallback=4.5):
        cam = self.cam
        d = self.aim_dir()
        if abs(d[2]) > 0.04:
            t = -cam.z / d[2]
            if 0.8 < t < 16.0:
                x, y = cam.x + d[0] * t, cam.y + d[1] * t
                if not is_wall(x, y):
                    return x, y
        fx, fy = cam.fx, cam.fy
        fl = math.hypot(fx, fy) or 1.0
        x, y = cam.x + fx / fl * fallback, cam.y + fy / fl * fallback
        if is_wall(x, y):
            return cam.x, cam.y
        return x, y

    def look_xy(self):
        fx, fy = self.cam.fx, self.cam.fy
        fl = math.hypot(fx, fy) or 1.0
        return fx / fl, fy / fl

    # ---- ATEŞ
    def cast_fireball(self):
        self.play("fire")
        self.spawn_bolt(self.aim_dir(0.004), "fire", 22.0, 1.4, 0.15)

    def fire_explode(self, x, y, zpos):
        col = (255, 95, 25)
        self.spawn_particles((x, y, zpos), 34, col, 0.09, 5.5)
        self.spawn_particles((x, y, zpos + 0.3), 14, (255, 200, 60), 0.06, 3.6)
        self.add_ring((x, y), 0.3, 2.6, (255, 140, 50), 0.45, w=0.16, z=max(0.05, zpos * 0.2))
        self.add_ring((x, y), 0.1, 1.4, (255, 230, 150), 0.25, w=0.1, z=0.06)
        # Ateş topu patlaması, menzildeki takım arkadaşına da hasar verir.
        teammate = self._friendly_fire_target(self.p)
        if teammate is not None:
            dist_p = math.hypot(teammate.x - x, teammate.y - y)
            if dist_p <= 2.4:
                fall_p = 1.0 - dist_p / 2.4
                self._damage_teammate(self.p, int(58 * (0.45 + 0.55 * fall_p)),
                                      x, y, radius=2.4)
        for z in self.zombies:
            if not z.alive:
                continue
            dist = math.hypot(z.x - x, z.y - y)
            if dist > 2.4:
                continue
            fall = 1.0 - dist / 2.4
            dmg = int(58 * (0.45 + 0.55 * fall))
            self.deal_magic(z, dmg, z.x, z.y, 1.2, "ATEŞ TOPU", col)
            if z.alive:
                self.ignite(z)
                z.stun = max(z.stun, 0.2)

    def cast_fire_ring(self):
        self.play("fire")
        x, y = self.ground_aim(3.2)
        col = (255, 95, 25)
        r = 2.35
        self.add_ring((x, y), 0.4, r + 0.4, (255, 150, 60), 0.5, w=0.2)
        for i in range(18):
            a = i / 18 * math.tau
            self.spawn_particles((x + math.cos(a) * r, y + math.sin(a) * r, 0.2), 4, col, 0.07, 2.4)
        self.fire_zones.append({
            "kind": "ring", "x": x, "y": y, "r": r, "r_in": r * 0.55,
            "life": 5.5, "max": 5.5, "tick": 0.0, "hit": set(),
        })
        self.add_popup((x, y, 1.1), "ATEŞ HALKASI", col, 0.9)

    def cast_fire_wall(self):
        self.play("fire")
        fx, fy = self.look_xy()
        wx, wy = -fy, fx
        cx, cy = self.p.x + fx * 2.4, self.p.y + fy * 2.4
        if is_wall(cx, cy):
            cx, cy = self.p.x + fx * 1.4, self.p.y + fy * 1.4
        col = (255, 120, 30)
        length, height = 5.2, 2.15
        for i in range(10):
            t = (i / 9.0 - 0.5) * length
            px, py = cx + wx * t, cy + wy * t
            if not is_wall(px, py):
                self.spawn_particles((px, py, 0.6), 6, col, 0.08, 2.8)
                self.add_prop(px, py, 0.16, 0.9 + 0.5 * random.random(), (255, 110, 30), 0.6,
                              lean=(fx * 0.2, fy * 0.2))
        self.fire_zones.append({
            "kind": "wall", "x": cx, "y": cy, "wx": wx, "wy": wy, "fx": fx, "fy": fy,
            "length": length, "thick": 0.55, "h": height,
            "life": 6.0, "max": 6.0, "tick": 0.0, "hit": set(),
        })
        self.add_popup((cx, cy, 1.4), "ATEŞ DUVARI", col, 0.9)

    def update_fire_zones(self, dt):
        keep = []
        col = (255, 95, 25)
        for zn in self.fire_zones:
            zn["life"] -= dt
            if zn["life"] <= 0:
                continue
            zn["tick"] -= dt
            if random.random() < min(1.0, dt * 18):
                if zn["kind"] == "ring":
                    a = random.uniform(0, math.tau)
                    rr = zn["r_in"] + random.random() * (zn["r"] - zn["r_in"])
                    self.add_particle((zn["x"] + math.cos(a) * rr, zn["y"] + math.sin(a) * rr, 0.25),
                                      (0, 0, random.uniform(1.0, 2.2)), 0.5, col, 0.05)
                else:
                    t = (random.random() - 0.5) * zn["length"]
                    self.add_particle((zn["x"] + zn["wx"] * t, zn["y"] + zn["wy"] * t, 0.2),
                                      (random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3),
                                       random.uniform(1.2, 2.4)), 0.55, col, 0.06)
            if zn["tick"] <= 0:
                zn["tick"] = 0.28
                for z in self.zombies:
                    if not z.alive:
                        continue
                    if zn["kind"] == "ring":
                        d = math.hypot(z.x - zn["x"], z.y - zn["y"])
                        if d > zn["r"] or d < zn["r_in"] * 0.35:
                            continue
                    else:
                        dx, dy = z.x - zn["x"], z.y - zn["y"]
                        along = dx * zn["wx"] + dy * zn["wy"]
                        across = dx * zn["fx"] + dy * zn["fy"]
                        if abs(along) > zn["length"] * 0.5 or abs(across) > zn["thick"]:
                            continue
                    dmg = 14 if zn["kind"] == "ring" else 18
                    self.deal_magic(z, dmg, z.x, z.y, 1.1,
                                    "HALKA" if zn["kind"] == "ring" else "DUVAR",
                                    col, popup=False)
                    if z.alive:
                        self.ignite(z, 18.0, 2.4)
            keep.append(zn)
        self.fire_zones = keep

    # ---- SU
    def cast_water(self):
        self.play("water")
        self.spawn_bolt(self.aim_dir(0.003), "water", 20.0, 1.5, 0.11)

    def water_hit(self, z, hx, hy, hz):
        col = (70, 170, 255)
        self.spawn_particles((hx, hy, hz), 18, col, 0.05, 3.4)
        for i in range(6):
            a = i / 6 * math.tau
            self.add_particle((hx, hy, hz), (math.cos(a) * 1.6, math.sin(a) * 1.6, 0.8),
                              0.4, (200, 240, 255), 0.04)
        self.add_ring((hx, hy), 0.1, 0.9, (150, 220, 255), 0.3, w=0.07, z=0.06)
        dmg = 42
        if z.wet > 0 or z.slow_t > 0:
            dmg = 55
            z.frozen = max(z.frozen, 1.6)
            z.stun = max(z.stun, 1.6)
            self.add_popup((hx, hy, hz + 0.3), "DONDU!", col, 0.9)
        self.deal_magic(z, dmg, hx, hy, hz, "SU", col)
        if z.alive:
            self.drench(z, 4.0, 3.5, 0.42)

    def drench(self, z, wet=3.5, slow_dur=2.4, slow_amt=0.5):
        z.wet = max(z.wet, wet)
        z.slow_t = max(z.slow_t, slow_dur)
        z.slow_amt = min(z.slow_amt if z.slow_t > 0 else 1.0, slow_amt)
        z.speed_mult = min(z.speed_mult, 0.7)
        self.tint_zombie(z, (70, 170, 255), max(wet, slow_dur))

    def cast_tsunami(self):
        self.play("water")
        fx, fy = self.look_xy()
        wx, wy = -fy, fx
        p = self.p
        x, y = p.x + fx * 1.4, p.y + fy * 1.4
        if is_wall(x, y):
            x, y = p.x + fx * 0.8, p.y + fy * 0.8
        col = (70, 170, 255)
        for i in range(10):
            t = (i / 9.0 - 0.5) * 3.6
            px, py = x + wx * t, y + wy * t
            if not is_wall(px, py):
                self.spawn_particles((px, py, 0.5), 5, col, 0.08, 3.2)
        self.water_zones.append({
            "kind": "tsunami", "x": x, "y": y, "fx": fx, "fy": fy, "wx": wx, "wy": wy,
            "length": 2.4, "width": 3.8, "speed": 9.0,
            "life": 1.05, "max": 1.05, "hit": set(),
        })
        self.add_popup((x + fx * 1.5, y + fy * 1.5, 1.3), "TSUNAMİ", col, 0.9)

    def cast_vortex(self):
        self.play("water")
        x, y = self.ground_aim(5.2)
        col = (40, 130, 230)
        r = 4.0
        self.add_ring((x, y), r * 0.9, r, (90, 180, 255), 0.6, w=0.15)
        self.water_zones.append({
            "kind": "vortex", "x": x, "y": y, "r": r,
            "life": 4.2, "max": 4.2, "tick": 0.0,
        })
        self.add_popup((x, y, 1.2), "GİRDAP", col, 0.9)

    def update_water_zones(self, dt):
        keep = []
        col = (70, 170, 255)
        for zn in self.water_zones:
            zn["life"] -= dt
            if zn["life"] <= 0:
                continue
            if zn["kind"] == "tsunami":
                nx = zn["x"] + zn["fx"] * zn["speed"] * dt
                ny = zn["y"] + zn["fy"] * zn["speed"] * dt
                if is_wall(nx, ny):
                    self.spawn_particles((zn["x"], zn["y"], 0.6), 14, col, 0.06, 3.0)
                    continue
                zn["x"], zn["y"] = nx, ny
                # dalga tepesinde köpük ve sıçrama
                for _ in range(3):
                    if random.random() < min(1.0, dt * 40):
                        t = (random.random() - 0.5) * zn["width"]
                        fxp = zn["x"] + zn["fx"] * zn["length"] * 0.45 + zn["wx"] * t
                        fyp = zn["y"] + zn["fy"] * zn["length"] * 0.45 + zn["wy"] * t
                        self.add_particle((fxp, fyp, 0.8),
                                          (zn["fx"] * 2.0, zn["fy"] * 2.0, random.uniform(1.5, 3.0)),
                                          0.45, (200, 235, 255), 0.05)
                if random.random() < min(1.0, dt * 18):
                    t = (random.random() - 0.5) * zn["width"]
                    self.spawn_particles((zn["x"] + zn["wx"] * t, zn["y"] + zn["wy"] * t, 0.45),
                                         1, col, 0.05, 2.2)
                for z in self.zombies:
                    if not z.alive or id(z) in zn["hit"]:
                        continue
                    dx, dy = z.x - zn["x"], z.y - zn["y"]
                    along = dx * zn["fx"] + dy * zn["fy"]
                    across = dx * zn["wx"] + dy * zn["wy"]
                    if abs(along) > zn["length"] * 0.5 or abs(across) > zn["width"] * 0.5:
                        continue
                    zn["hit"].add(id(z))
                    self.deal_magic(z, 48, z.x, z.y, 1.15, "TSUNAMİ", col)
                    if z.alive:
                        push = 11.0
                        z.knock_x += zn["fx"] * push
                        z.knock_y += zn["fy"] * push
                        z.stun = max(z.stun, 0.45)
                        self.drench(z, 3.2, 2.2, 0.5)
            else:
                # girdap: dışarıdan içeri dönen köpük spirali
                if random.random() < min(1.0, dt * 30):
                    a = random.uniform(0, math.tau)
                    rr = zn["r"] * random.uniform(0.6, 1.0)
                    cx, cy = zn["x"] + math.cos(a) * rr, zn["y"] + math.sin(a) * rr
                    vx = -math.sin(a) * 2.6 - math.cos(a) * 2.0
                    vy = math.cos(a) * 2.6 - math.sin(a) * 2.0
                    self.add_particle((cx, cy, 0.15), (vx, vy, 0.9), 0.6, (120, 200, 255), 0.04)
                zn["tick"] -= dt
                for z in self.zombies:
                    if not z.alive:
                        continue
                    dx, dy = zn["x"] - z.x, zn["y"] - z.y
                    dist = math.hypot(dx, dy)
                    if dist > zn["r"] or dist < 0.08:
                        continue
                    pull = 26.0 * (1.05 - dist / zn["r"] * 0.35)
                    z.knock_x += dx / dist * pull * dt
                    z.knock_y += dy / dist * pull * dt
                    z.stun = max(z.stun, 0.08)
                    if zn["tick"] <= 0:
                        self.deal_magic(z, 16, z.x, z.y, 1.05, "GİRDAP", col, popup=False)
                        if z.alive:
                            self.drench(z, 2.4, 1.6, 0.55)
                if zn["tick"] <= 0:
                    zn["tick"] = 0.32
            keep.append(zn)
        self.water_zones = keep

    # ---- TOPRAK
    def cast_earth(self):
        self.play("earth")
        p, cam = self.p, self.cam
        fx, fy = cam.fx, cam.fy
        fl = math.hypot(fx, fy) or 1.0
        fx, fy = fx / fl, fy / fl
        hit_any = False
        struck = set()
        for i in range(1, 9):
            x = p.x + fx * i * 1.05
            y = p.y + fy * i * 1.05
            if is_wall(x, y):
                break
            # her adımda yerden fırlayan taş diken
            self.add_prop(x, y, 0.2, 0.7 + 0.35 * random.random(), (150, 105, 55), 1.3,
                          lean=(fx * 0.15, fy * 0.15))
            self.spawn_particles((x, y, 0.2), 6, (168, 118, 52), 0.07, 2.8)
            for z in self.zombies:
                if not z.alive or id(z) in struck:
                    continue
                if math.hypot(z.x - x, z.y - y) > 0.95:
                    continue
                hit_any = True
                struck.add(id(z))
                self.deal_magic(z, 72, z.x, z.y, 1.1, "TOPRAK", (200, 150, 70))
                if z.alive:
                    z.stun = max(z.stun, 0.95)
                    z.speed_mult = max(0.4, z.speed_mult - 0.12)
                    self.tint_zombie(z, (168, 118, 52), 1.2)
        if not hit_any:
            self.add_popup((p.x + fx * 2, p.y + fy * 2, 1.2), "ISKA", (180, 150, 110), 0.6)

    def cast_earth_grasp(self):
        self.play("earth")
        x, y = self.ground_aim(4.2)
        col = (168, 118, 52)
        r = 2.2
        self.add_ring((x, y), 0.3, r, (180, 130, 70), 0.5, w=0.14)
        # dört taş pençe, merkeze doğru eğik
        for i in range(4):
            a = i / 4 * math.tau + 0.4
            px, py = x + math.cos(a) * r * 0.85, y + math.sin(a) * r * 0.85
            self.add_prop(px, py, 0.2, 1.5, (150, 100, 50), 1.6,
                          lean=(-math.cos(a) * 0.5, -math.sin(a) * 0.5))
        hit_any = False
        for z in self.zombies:
            if not z.alive:
                continue
            if math.hypot(z.x - x, z.y - y) > r:
                continue
            hit_any = True
            self.deal_magic(z, 64, z.x, z.y, 1.1, "TAŞ PENÇE", col)
            if z.alive:
                z.stun = max(z.stun, 1.85)
                z.slow_t = max(z.slow_t, 2.4)
                z.slow_amt = min(z.slow_amt if z.slow_t > 0 else 1.0, 0.35)
                self.tint_zombie(z, col, 2.0)
        self.spell_zones.append({
            "kind": "grasp", "x": x, "y": y, "r": r,
            "life": 2.5, "max": 2.5, "col": col, "spin": 0.4,
        })
        self.add_popup((x, y, 1.2), "TAŞ PENÇE" if hit_any else "ISKA", col, 0.9)

    def cast_earthquake(self):
        self.play("earth")
        p = self.p
        col = (200, 150, 70)
        self.spawn_particles((p.x, p.y, 0.2), 26, col, 0.09, 3.4)
        self.add_ring((p.x, p.y), 0.5, 6.4, (210, 160, 80), 0.9, w=0.22)
        # zemin çatlakları
        for i in range(7):
            a = i / 7 * math.tau + random.uniform(-0.2, 0.2)
            L = random.uniform(2.5, 4.5)
            self.add_beam((p.x, p.y, 0.04),
                          (p.x + math.cos(a) * L, p.y + math.sin(a) * L, 0.04),
                          (120, 80, 40), 0.9, 3, jag=0.12)
        self.spell_zones.append({
            "kind": "quake", "x": p.x, "y": p.y, "r": 0.7, "r_max": 6.4,
            "life": 0.95, "max": 0.95, "hit": set(), "col": col, "spin": 0.0,
        })
        self.add_popup((p.x, p.y, 1.2), "DEPREM", col, 0.9)

    # ---- RÜZGAR
    def cast_air(self):
        self.play("air")
        p, cam = self.p, self.cam
        fx, fy = cam.fx, cam.fy
        fl = math.hypot(fx, fy) or 1.0
        fx, fy = fx / fl, fy / fl
        o = (cam.x, cam.y, cam.z)
        col = (210, 235, 245)
        # rüzgar çizgileri (konide ileri akan şeritler)
        for k in range(12):
            off = random.uniform(-1.4, 1.4)
            lat = (-fy * off, fx * off)
            dist0 = 0.6 + random.uniform(0, 4.0)
            s = (o[0] + fx * dist0 + lat[0], o[1] + fy * dist0 + lat[1], o[2] - 0.2 + random.uniform(-0.4, 0.4))
            e = (s[0] + fx * 1.4, s[1] + fy * 1.4, s[2])
            self.add_beam(s, e, col, 0.22, 2)
        for k in range(8):
            t = 0.6 + k * 0.55
            self.add_particle((o[0] + fx * t, o[1] + fy * t, 1.1),
                              (fx * 2.5, fy * 2.5, random.uniform(-0.2, 0.3)), 0.4, col, 0.04)
        for z in self.zombies:
            if not z.alive:
                continue
            dx, dy = z.x - p.x, z.y - p.y
            dist = math.hypot(dx, dy)
            if dist > 7.5 or dist < 0.15:
                continue
            ang = (dx * fx + dy * fy) / dist
            if ang < 0.55:
                continue
            self.deal_magic(z, 34, z.x, z.y, 1.3, "RÜZGAR", col)
            if not z.alive:
                continue
            push = 7.5 * ang
            z.knock_x += fx * push
            z.knock_y += fy * push
            z.stun = max(z.stun, 0.35)
            self.tint_zombie(z, (200, 230, 240), 0.6)

    def cast_whirlwind(self):
        self.play("air")
        x, y = self.ground_aim(5.0)
        col = (210, 235, 245)
        r = 3.6
        self.add_ring((x, y), r * 0.8, r, (220, 240, 250), 0.5, w=0.1)
        self.spell_zones.append({
            "kind": "whirl", "x": x, "y": y, "r": r,
            "life": 4.0, "max": 4.0, "tick": 0.0, "col": col, "spin": 3.2,
        })
        self.add_popup((x, y, 1.3), "KASIRGA", col, 0.9)

    def cast_storm_wave(self):
        self.play("air")
        p = self.p
        fx, fy = self.look_xy()
        col = (200, 230, 255)
        o = (self.cam.x, self.cam.y, self.cam.z)
        self.add_ring((p.x, p.y), 0.5, 6.2, col, 0.5, w=0.16, z=0.6)
        for k in range(10):
            t = 0.4 + k * 0.5
            self.add_particle((o[0] + fx * t, o[1] + fy * t, 1.0),
                              (fx * 3.0, fy * 3.0, 0.2), 0.45, col, 0.05)
        for z in self.zombies:
            if not z.alive:
                continue
            dx, dy = z.x - p.x, z.y - p.y
            dist = math.hypot(dx, dy)
            if dist > 6.2 or dist < 0.12:
                continue
            ang = (dx * fx + dy * fy) / dist
            if ang < 0.12:
                continue
            self.deal_magic(z, 46, z.x, z.y, 1.3, "FIRTINA DALGASI", col)
            if z.alive:
                push = 13.5 * (0.45 + 0.55 * ang)
                z.knock_x += fx * push
                z.knock_y += fy * push
                z.stun = max(z.stun, 0.55)
                self.tint_zombie(z, col, 0.7)
        self.add_popup((p.x + fx * 2.2, p.y + fy * 2.2, 1.4), "FIRTINA DALGASI", col, 0.9)

    # ---- YILDIRIM
    def cast_lightning(self):
        self.play("lightning")
        cam = self.cam
        o = (cam.x, cam.y, cam.z)
        d = self.aim_dir(0.002)
        col = (180, 210, 255)
        best, _, hit = self.hit_scan_first(o, d, 32.0)
        self.add_beam(o, hit, col, 0.18, 4, jag=0.22)
        self.add_beam(o, hit, (255, 255, 255), 0.12, 1, jag=0.22)
        self.spawn_particles(hit, 14, col, 0.04, 4.0)
        chained = []
        if best:
            z = best[0]
            extra = 1.45 if z.wet > 0 or z.frozen > 0 else 1.0
            self.deal_magic(z, int(48 * extra), hit[0], hit[1], hit[2], "YILDIRIM", col)
            chained.append(z)
            src = z
            for _ in range(3):
                nxt, nd = None, 4.2
                for oth in self.zombies:
                    if not oth.alive or oth in chained:
                        continue
                    dd = math.hypot(oth.x - src.x, oth.y - src.y)
                    if dd < nd:
                        nd, nxt = dd, oth
                if nxt is None:
                    break
                a = (src.x, src.y, 1.35)
                b = (nxt.x, nxt.y, 1.35)
                self.add_beam(a, b, col, 0.18, 3, jag=0.3)
                self.add_ring((nxt.x, nxt.y), 0.1, 0.8, col, 0.25, w=0.06)
                wet_m = 1.45 if nxt.wet > 0 or nxt.frozen > 0 else 1.0
                self.deal_magic(nxt, int(36 * wet_m), nxt.x, nxt.y, 1.35, "ZİNCİR", col)
                chained.append(nxt)
                src = nxt
            for z in chained:
                if z.alive:
                    z.stun = max(z.stun, 0.45)
                    self.tint_zombie(z, col, 0.7)

    def cast_lightning_bolt(self):
        self.play("lightning")
        p, cam = self.p, self.cam
        fx, fy = self.look_xy()
        col = (180, 210, 255)
        reach = 16.0
        end = (cam.x + cam.fx * reach, cam.y + cam.fy * reach, cam.z + cam.fz * reach)
        self.add_beam((cam.x, cam.y, cam.z), end, col, 0.22, 5, jag=0.25)
        self.add_beam((cam.x, cam.y, cam.z), end, (255, 255, 255), 0.14, 1, jag=0.25)
        # yerde kıvılcımlar
        for k in range(10):
            t = 2.0 + k * 1.4
            self.add_particle((p.x + fx * t, p.y + fy * t, 0.1),
                              (random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(0.5, 1.5)),
                              0.35, col, 0.04)
        struck = set()
        for z in self.zombies:
            if not z.alive:
                continue
            dx, dy = z.x - p.x, z.y - p.y
            along = dx * fx + dy * fy
            across = dx * (-fy) + dy * fx
            if along < 0.35 or along > reach or abs(across) > 0.78:
                continue
            extra = 1.45 if z.wet > 0 or z.frozen > 0 else 1.0
            self.deal_magic(z, int(62 * extra), z.x, z.y, 1.35, "YILDIRIM OKU", col)
            struck.add(z)
            if z.alive:
                z.stun = max(z.stun, 0.55)
                self.tint_zombie(z, col, 0.8)
            self.spawn_particles((z.x, z.y, 1.3), 8, col, 0.04, 3.5)
        if not struck:
            self.add_popup((p.x + fx * 3, p.y + fy * 3, 1.3), "ISKA", col, 0.6)

    def cast_call_lightning(self):
        self.play("lightning")
        x, y = self.ground_aim(6.0)
        col = (170, 200, 255)
        r = 3.8
        self.add_ring((x, y), 0.5, r, col, 0.6, w=0.12)
        self.spell_zones.append({
            "kind": "storm", "x": x, "y": y, "r": r,
            "life": 5.2, "max": 5.2, "tick": 0.05, "col": col, "spin": 1.2,
        })
        self.add_popup((x, y, 1.4), "FIRTINA ÇAĞRISI", col, 0.9)

    # ---- KARANLIK
    def cast_dark(self):
        self.play("dark")
        self.spawn_bolt(self.aim_dir(0.004), "dark", 18.0, 1.6, 0.13)

    def dark_hit(self, z, hx, hy, hz):
        col = (128, 48, 190)
        self.spawn_particles((hx, hy, hz), 22, col, 0.05, 3.2)
        self.add_ring((hx, hy), 0.1, 1.0, (110, 40, 170), 0.35, w=0.08)
        dealt = self.deal_magic(z, 52, hx, hy, hz, "GÖLGE", col)
        heal = int(dealt * 0.28)
        if heal > 0:
            self.heal_self(heal)
            if not self.visual_only:
                self.add_popup((self.p.x, self.p.y, EYE_H), "+%d CAN" % heal, (180, 80, 220), 0.8)
        if z.alive:
            z.weaken = max(z.weaken, 4.5)
            self.tint_zombie(z, col, 4.5)

    def cast_arms_of_hadar(self):
        self.play("dark")
        p = self.p
        col = (128, 48, 190)
        r = 3.15
        # altı gölge kolu (zikzak dokunaçlar) çevreye uzanır
        for i in range(6):
            a = i / 6 * math.tau + random.uniform(-0.2, 0.2)
            end = (p.x + math.cos(a) * r * 0.9, p.y + math.sin(a) * r * 0.9, random.uniform(0.2, 1.0))
            self.add_beam((p.x, p.y, 1.0), end, col, 0.5, 4, jag=0.35)
            self.add_beam((p.x, p.y, 1.0), end, (200, 120, 255), 0.4, 1, jag=0.35)
        self.add_ring((p.x, p.y), 0.3, r, col, 0.4, w=0.1, z=0.1)
        for z in self.zombies:
            if not z.alive:
                continue
            dx, dy = p.x - z.x, p.y - z.y
            dist = math.hypot(dx, dy)
            if dist > r or dist < 0.08:
                continue
            dealt = self.deal_magic(z, 44, z.x, z.y, 1.2, "HADAR KOLLARI", col)
            if z.alive:
                z.knock_x += dx / dist * 9.0
                z.knock_y += dy / dist * 9.0
                z.weaken = max(z.weaken, 3.2)
                z.stun = max(z.stun, 0.4)
                self.tint_zombie(z, col, 3.2)
            heal = int(dealt * 0.18)
            if heal > 0:
                self.heal_self(heal)
        self.add_popup((p.x, p.y, 1.3), "HADAR KOLLARI", col, 0.9)

    def cast_hunger_of_hadar(self):
        self.play("dark")
        x, y = self.ground_aim(5.4)
        col = (90, 30, 140)
        r = 3.7
        self.add_ring((x, y), r, r * 0.4, col, 0.5, w=0.1)
        self.spell_zones.append({
            "kind": "hunger", "x": x, "y": y, "r": r,
            "life": 5.0, "max": 5.0, "tick": 0.0, "col": col, "spin": 1.6,
        })
        self.add_popup((x, y, 1.2), "HADAR AÇLIĞI", col, 0.9)

    # ---- IŞIK
    def cast_light(self):
        self.play("light")
        cam = self.cam
        o = (cam.x, cam.y, cam.z)
        d = self.aim_dir(0.0)
        col = (255, 245, 170)
        best, _, hit = self.hit_scan_first(o, d, 34.0)
        self.add_beam(o, hit, col, 0.22, 6)
        self.add_beam(o, hit, (255, 255, 240), 0.2, 2)
        self.add_ring(hit, 0.1, 0.9, col, 0.3, w=0.07, z=hit[2])
        self.spawn_particles(hit, 22, col, 0.05, 3.6)
        if best:
            z = best[0]
            dealt = self.deal_magic(z, 86, hit[0], hit[1], hit[2], "IŞIK", col)
            if z.alive:
                z.stun = max(z.stun, 0.7)
                z.burn = 0.0
                z.weaken = max(z.weaken, 1.2)
                self.tint_zombie(z, col, 1.0)
            self.heal_self(8)
            if not self.visual_only:
                self.add_popup((self.p.x, self.p.y, EYE_H), "+8 CAN", col, 0.7)
            if dealt > 0 and not self.visual_only:
                self.p.mana = min(MANA_MAX, self.p.mana + 8)
        else:
            self.heal_self(4)

    def cast_spirit_guardians(self):
        self.play("light")
        p = self.p
        col = (255, 245, 170)
        r = 2.55
        self.add_ring((p.x, p.y), 0.2, r, col, 0.6, w=0.06, z=1.1)
        self.spell_zones.append({
            "kind": "guardians", "x": p.x, "y": p.y, "r": r,
            "life": 6.0, "max": 6.0, "tick": 0.0, "col": col, "spin": 2.4, "follow": p,
        })
        self.add_popup((p.x, p.y, 1.4), "RUH KORUYUCULARI", col, 0.9)

    def cast_sunburst(self):
        self.play("light")
        x, y = self.ground_aim(4.6)
        col = (255, 245, 170)
        r = 5.1
        self.spell_flash = 0.22
        self.spell_col = col
        self.add_ring((x, y), 0.3, r, (255, 240, 200), 0.55, w=0.22, z=0.2)
        for i in range(14):
            a = i / 14 * math.tau
            self.add_beam((x, y, 0.8), (x + math.cos(a) * r, y + math.sin(a) * r, 0.8),
                          col, 0.45, 3)
        self.spawn_particles((x, y, 0.8), 40, col, 0.1, 4.6)
        hit_any = False
        for z in self.zombies:
            if not z.alive:
                continue
            if math.hypot(z.x - x, z.y - y) > r:
                continue
            hit_any = True
            self.deal_magic(z, 78, z.x, z.y, 1.3, "GÜNEŞ PATLAMASI", col)
            if z.alive:
                z.stun = max(z.stun, 0.85)
                z.burn = 0.0
                self.tint_zombie(z, col, 1.2)
        self.heal_self(14 if hit_any else 6)
        self.add_popup((x, y, 1.5), "GÜNEŞ PATLAMASI", col, 1.0)

    # ---- ZONE GÜNCELLEME
    def update_spell_zones(self, dt):
        keep = []
        p = self.p
        for zn in self.spell_zones:
            zn["life"] -= dt
            if zn["life"] <= 0:
                continue
            if zn.get("follow"):
                zn["x"], zn["y"] = zn["follow"].x, zn["follow"].y
            kind, col = zn["kind"], zn["col"]
            if kind == "whirl":
                # hortum: yukarı döner, tepe daha dar
                for _ in range(2):
                    if random.random() < min(1.0, dt * 30):
                        h = random.uniform(0.0, 2.6)
                        ang = self.time * 7.0 + random.uniform(0, math.tau)
                        rr = zn["r"] * (0.35 + 0.65 * h / 2.6)
                        self.add_particle((zn["x"] + math.cos(ang) * rr, zn["y"] + math.sin(ang) * rr, h),
                                          (0, 0, 0.6), 0.5, col, 0.05)
            elif kind == "hunger":
                # void: parçacıklar içeri doğru çekilir
                for _ in range(2):
                    if random.random() < min(1.0, dt * 28):
                        a = random.uniform(0, math.tau)
                        rr = zn["r"] * random.uniform(0.9, 1.0)
                        cx, cy = zn["x"] + math.cos(a) * rr, zn["y"] + math.sin(a) * rr
                        self.add_particle((cx, cy, 0.3),
                                          (-math.cos(a) * 2.8, -math.sin(a) * 2.8, 0.3),
                                          0.55, (150, 70, 210), 0.05)
            elif random.random() < min(1.0, dt * 12):
                a = random.uniform(0, math.tau)
                rr = random.random() * zn.get("r", 2.0)
                h = 0.9 if kind in ("whirl", "guardians", "storm") else 0.25
                self.spawn_particles((zn["x"] + math.cos(a) * rr, zn["y"] + math.sin(a) * rr, h),
                                     1, col, 0.04, 1.8)
            if kind == "quake":
                zn["r"] = min(zn["r_max"], zn["r"] + 7.2 * dt)
                for z in self.zombies:
                    if not z.alive or id(z) in zn["hit"]:
                        continue
                    dx, dy = z.x - zn["x"], z.y - zn["y"]
                    dist = math.hypot(dx, dy)
                    if dist > zn["r"] or dist < zn["r"] - 1.15:
                        continue
                    zn["hit"].add(id(z))
                    self.deal_magic(z, 52, z.x, z.y, 1.05, "DEPREM", col)
                    if z.alive:
                        if dist > 0.1:
                            z.knock_x += dx / dist * 8.5
                            z.knock_y += dy / dist * 8.5
                        z.stun = max(z.stun, 0.85)
                        self.tint_zombie(z, col, 1.0)
            elif kind == "grasp":
                for z in self.zombies:
                    if not z.alive:
                        continue
                    if math.hypot(z.x - zn["x"], z.y - zn["y"]) > zn["r"]:
                        continue
                    z.stun = max(z.stun, 0.12)
                    z.slow_t = max(z.slow_t, 0.2)
                    z.slow_amt = min(z.slow_amt if z.slow_t > 0 else 1.0, 0.3)
            elif kind == "whirl":
                zn["tick"] -= dt
                for z in self.zombies:
                    if not z.alive:
                        continue
                    dx, dy = z.x - zn["x"], z.y - zn["y"]
                    dist = math.hypot(dx, dy)
                    if dist > zn["r"] or dist < 0.08:
                        continue
                    tx, ty = -dy / dist, dx / dist
                    z.knock_x += tx * 22.0 * dt + dx / dist * 6.0 * dt
                    z.knock_y += ty * 22.0 * dt + dy / dist * 6.0 * dt
                    z.stun = max(z.stun, 0.06)
                    if zn["tick"] <= 0:
                        self.deal_magic(z, 14, z.x, z.y, 1.2, "KASIRGA", col, popup=False)
                if zn["tick"] <= 0:
                    zn["tick"] = 0.30
            elif kind == "storm":
                zn["tick"] -= dt
                if zn["tick"] <= 0:
                    zn["tick"] = 0.62
                    targets = [z for z in self.zombies
                               if z.alive and math.hypot(z.x - zn["x"], z.y - zn["y"]) <= zn["r"]]
                    random.shuffle(targets)
                    for z in targets[:3]:
                        extra = 1.45 if z.wet > 0 or z.frozen > 0 else 1.0
                        sky = (z.x + random.uniform(-0.2, 0.2), z.y + random.uniform(-0.2, 0.2), 4.2)
                        self.add_beam(sky, (z.x, z.y, 0.2), col, 0.2, 3, jag=0.4)
                        self.add_beam(sky, (z.x, z.y, 0.2), (255, 255, 255), 0.14, 1, jag=0.4)
                        self.add_ring((z.x, z.y), 0.1, 0.9, col, 0.3, w=0.08)
                        self.deal_magic(z, int(28 * extra), z.x, z.y, 1.4, "ÇAĞRI", col)
                        if z.alive:
                            z.stun = max(z.stun, 0.35)
                            self.tint_zombie(z, col, 0.5)
            elif kind == "hunger":
                zn["tick"] -= dt
                drained = 0
                for z in self.zombies:
                    if not z.alive:
                        continue
                    if math.hypot(z.x - zn["x"], z.y - zn["y"]) > zn["r"]:
                        continue
                    z.slow_t = max(z.slow_t, 0.4)
                    z.slow_amt = min(z.slow_amt if z.slow_t > 0 else 1.0, 0.55)
                    z.weaken = max(z.weaken, 0.4)
                    if zn["tick"] <= 0:
                        dealt = self.deal_magic(z, 15, z.x, z.y, 1.1, "AÇLIK", col, popup=False)
                        drained += dealt
                        if z.alive:
                            self.tint_zombie(z, col, 0.6)
                if zn["tick"] <= 0:
                    zn["tick"] = 0.34
                    if drained > 0:
                        self.heal_self(max(2, int(drained * 0.22)))
            elif kind == "guardians":
                zn["tick"] -= dt
                for z in self.zombies:
                    if not z.alive:
                        continue
                    if math.hypot(z.x - zn["x"], z.y - zn["y"]) > zn["r"]:
                        continue
                    if zn["tick"] <= 0:
                        self.deal_magic(z, 16, z.x, z.y, 1.15, "RUH", col, popup=False)
                        if z.alive:
                            z.stun = max(z.stun, 0.18)
                            self.tint_zombie(z, col, 0.4)
                if zn["tick"] <= 0:
                    zn["tick"] = 0.36
                    self.heal_self(1)
            keep.append(zn)
        self.spell_zones = keep

    # ---- MERMİLER
    def update_bolts(self, dt):
        keep = []
        for b in self.bolts:
            b["life"] -= dt
            if b["life"] <= 0:
                if b["elem"] == "fire":
                    self.fire_explode(b["x"], b["y"], b["z"])
                continue
            nx = b["x"] + b["dx"] * dt
            ny = b["y"] + b["dy"] * dt
            nz = b["z"] + b["dz"] * dt
            if nz <= 0.04 or (nz <= WALL_H and is_wall(nx, ny)):
                if b["elem"] == "fire":
                    self.fire_explode(b["x"], b["y"], max(0.1, b["z"]))
                else:
                    self.spawn_particles((b["x"], b["y"], max(0.1, b["z"])), 8, b["col"], 0.04, 2.4)
                continue
            hit = None
            best = 0.42
            for z in self.zombies:
                if not z.alive:
                    continue
                dxy = math.hypot(z.x - nx, z.y - ny)
                dz = abs(1.1 - nz)
                if dxy < best and dz < 1.3:
                    best = dxy
                    hit = z
            if hit:
                if b["elem"] == "fire":
                    self.fire_explode(nx, ny, nz)
                elif b["elem"] == "water":
                    self.water_hit(hit, nx, ny, nz)
                elif b["elem"] == "dark":
                    self.dark_hit(hit, nx, ny, nz)
                continue
            b["x"], b["y"], b["z"] = nx, ny, nz
            # her mermi kendi izini bırakır
            if random.random() < 0.85:
                tr = {"fire": (255, 150, 60), "water": (200, 235, 255), "dark": (170, 90, 230)}.get(b["elem"], b["col"])
                self.add_particle((nx, ny, nz),
                                  (random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4), random.uniform(-0.2, 0.4)),
                                  0.3, tr, 0.035)
            keep.append(b)
        self.bolts = keep

    def update_beams(self, dt):
        for bm in self.beams:
            bm["life"] -= dt
        self.beams = [bm for bm in self.beams if bm["life"] > 0]

    # ----------------------------------------------------- PARÇACIK / POPUP
    def spawn_particles(self, pos, n, col, size, speed):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            e = random.uniform(-0.2, 1.0)
            s = random.uniform(0.3, 1.0) * speed
            self.particles.append([pos[0], pos[1], pos[2],
                                   math.cos(a) * s * (1 - e * 0.4), math.sin(a) * s * (1 - e * 0.4), e * s + 1.0,
                                   random.uniform(0.5, 1.4), col, size * random.uniform(0.6, 1.3)])
        if len(self.particles) > 500:
            del self.particles[:150]

    def update_particles(self, dt):
        out = []
        for q in self.particles:
            q[6] -= dt
            if q[6] <= 0:
                continue
            q[5] -= 9.0 * dt
            q[0] += q[3] * dt
            q[1] += q[4] * dt
            q[2] += q[5] * dt
            if q[2] < 0.03:
                q[2] = 0.03
                q[3] = q[4] = q[5] = 0.0
            out.append(q)
        self.particles = out

    def add_popup(self, pos, text, col, life):
        self.popups.append({"pos": pos, "text": text, "col": col, "life": life, "max": life})

    def update_popups(self, dt):
        for pu in self.popups:
            pu["life"] -= dt
        self.popups = [pu for pu in self.popups if pu["life"] > 0]

    # ----------------------------------------------------- ZOMBİLER
    def update_flow(self):
        p = self.p
        cell = (int(p.x), int(p.y))
        if cell == self.flow_cell:
            return
        self.flow_cell = cell
        dist = [[-1] * MAP_W for _ in range(MAP_H)]
        dq = deque([cell])
        dist[cell[1]][cell[0]] = 0
        while dq:
            x, y = dq.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < MAP_W and 0 <= ny < MAP_H and WORLD[ny][nx] == 0 and dist[ny][nx] < 0:
                    dist[ny][nx] = dist[y][x] + 1
                    dq.append((nx, ny))
        self.flow = dist

    def flow_target(self, z):
        cx, cy = int(z.x), int(z.y)
        if not (0 <= cx < MAP_W and 0 <= cy < MAP_H):
            return None
        best, bd = None, self.flow[cy][cx]
        if bd < 0:
            return None
        for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = cx + ox, cy + oy
            if not (0 <= nx < MAP_W and 0 <= ny < MAP_H) or WORLD[ny][nx] != 0:
                continue
            if ox and oy and (WORLD[cy][cx + ox] != 0 or WORLD[cy + oy][cx] != 0):
                continue
            dv = self.flow[ny][nx]
            if dv >= 0 and dv < bd:
                bd, best = dv, (nx + 0.5, ny + 0.5)
        return best

    def _nearest_player(self, zx, zy):
        cands = []
        if self.p.hp > 0:
            cands.append(self.p)
        if self.p2 and self.p2.hp > 0 and getattr(self, "net", None) and self.net.mode != "solo":
            cands.append(self.p2)
        if not cands:
            return self.p, math.hypot(self.p.x - zx, self.p.y - zy)
        best, bd = cands[0], math.hypot(cands[0].x - zx, cands[0].y - zy)
        for c in cands[1:]:
            d = math.hypot(c.x - zx, c.y - zy)
            if d < bd:
                best, bd = c, d
        return best, bd

    def update_zombies(self, dt):
        if getattr(self, "net", None) and self.net.mode == "client" and self.net.connected():
            for z in self.zombies:
                if not z.alive:
                    z.dying += dt
                z.hit_timer = max(0.0, z.hit_timer - dt)
                z.elem_glow_t = max(0.0, z.elem_glow_t - dt)
                if z.elem_glow_t <= 0:
                    z.elem_glow = None
            self.zombies = [z for z in self.zombies if z.alive or z.dying < 0.8]
            return
        p = self.p
        for z in self.zombies:
            if not z.alive:
                z.dying += dt
                continue
            z.hit_timer = max(0.0, z.hit_timer - dt)
            z.stun = max(0.0, z.stun - dt)
            z.attack_cd = max(0.0, z.attack_cd - dt)
            z.swing = max(0.0, z.swing - dt)
            z.elem_glow_t = max(0.0, z.elem_glow_t - dt)
            if z.elem_glow_t <= 0:
                z.elem_glow = None
            z.wet = max(0.0, z.wet - dt)
            z.slow_t = max(0.0, z.slow_t - dt)
            z.frozen = max(0.0, z.frozen - dt)
            z.weaken = max(0.0, z.weaken - dt)
            if z.knock_x or z.knock_y:
                kx, ky = z.knock_x * dt, z.knock_y * dt
                if free_circle(z.x + kx, z.y, 0.28):
                    z.x += kx
                if free_circle(z.x, z.y + ky, 0.28):
                    z.y += ky
                fade = max(0.0, 1.0 - dt * 5.5)
                z.knock_x *= fade
                z.knock_y *= fade
            if z.frozen > 0:
                z.stun = max(z.stun, 0.05)
            if z.burn > 0:
                z.burn -= dt
                z.hp -= z.burn_dps * dt
                if random.random() < min(1.0, dt * 10):
                    self.spawn_particles((z.x, z.y, 1.15), 2, (255, 90, 20), 0.035, 1.4)
                if z.hp <= 0:
                    self.kill_zombie(z, False)
                    continue
            target, dist = self._nearest_player(z.x, z.y)
            dx, dy = target.x - z.x, target.y - z.y
            z.groan_t -= dt
            if z.groan_t <= 0:
                z.groan_t = random.uniform(4, 10)
                if dist < 16:
                    self.play(random.choice(("groan1", "groan2")), (1 - dist / 16) * 0.8)
            z.los_t -= dt
            if z.los_t <= 0:
                z.los_t = 0.2
                z.los = los_clear(z.x, z.y, target.x, target.y)
            if z.stun <= 0 and dist > 0.9:
                if z.los or self.flow is None:
                    tx, ty = target.x, target.y
                else:
                    tgt = self.flow_target(z)
                    tx, ty = tgt if tgt else (target.x, target.y)
                mx, my = tx - z.x, ty - z.y
                ml = math.hypot(mx, my) or 1.0
                spd = z.base_speed * z.speed_mult * (1.25 if dist < 2.5 else 1.0)
                if z.slow_t > 0:
                    spd *= z.slow_amt
                vx, vy = mx / ml * spd * dt, my / ml * spd * dt
                for o in self.zombies:
                    if o is not z and o.alive:
                        ox, oy = z.x - o.x, z.y - o.y
                        od = math.hypot(ox, oy)
                        if 0 < od < 0.7:
                            vx += ox / od * 1.2 * dt
                            vy += oy / od * 1.2 * dt
                if free_circle(z.x + vx, z.y, 0.28):
                    z.x += vx
                if free_circle(z.x, z.y + vy, 0.28):
                    z.y += vy
                z.phase += dt * spd * 3.2
                target_face = math.atan2(my, mx)
                diff = (target_face - z.face + math.pi) % math.tau - math.pi
                z.face += diff * min(1.0, dt * 8)
            elif dist <= 0.9:
                diff = (math.atan2(dy, dx) - z.face + math.pi) % math.tau - math.pi
                z.face += diff * min(1.0, dt * 10)
            if dist < 1.25 and z.attack_cd <= 0 and z.stun <= 0:
                z.attack_cd = 1.0
                z.swing = 0.4
                target.hp -= z.dmg
                if target is self.p:
                    self.hurt = 0.45
                    self.kick_p += random.uniform(-0.02, 0.03)
                    self.kick_y += random.uniform(-0.03, 0.03)
                    self.play("hurt")
        self.zombies = [z for z in self.zombies if z.alive or z.dying < 0.8]

    def alive_count(self):
        return sum(1 for z in self.zombies if z.alive)

    def update_waves(self, dt):
        if getattr(self, "net", None) and self.net.mode == "client" and self.net.connected():
            return
        p = self.p
        if self.intermission > 0:
            self.intermission -= dt
            if self.intermission <= 0:
                self.wave += 1
                self.to_spawn = self.wave_size()
                self.spawn_t = 1.0
                self.banner = ("DALGA %d" % self.wave, 3.0)
                self.bonus_lines = []
                self.play("wave")
            return
        if self.to_spawn > 0:
            self.spawn_t -= dt
            if self.spawn_t <= 0 and self.alive_count() < 8 + int(self.wave * 1.8):
                self.spawn_t = max(0.5, 1.6 - self.wave * 0.1)
                far = [c for c in OPEN_CELLS if math.hypot(c[0] - p.x, c[1] - p.y) > 14
                       and (self.flow is None or self.flow[int(c[1])][int(c[0])] >= 0)]
                x, y = random.choice(far or OPEN_CELLS)
                self.zombies.append(Zombie(x, y, self.wave))
                self.to_spawn -= 1
        elif self.alive_count() == 0:
            self.intermission = 5.0
            acc = p.hits / p.shots if p.shots else 0.0
            wb = 250 * self.wave
            ab = int(acc * 300)
            p.score += wb + ab
            p.hp = min(100, p.hp + 30)
            p.mana = MANA_MAX
            self.bonus_lines = ["Dalga bonusu +%d" % wb, "Doğruluk bonusu (%%%d) +%d" % (int(acc * 100), ab),
                                "+30 can   mana doldu"]
            self.play("wave")

    # ----------------------------------------------------- 3D RENDER
    def sh(self, col, d2, lit, specular=0.0, ao=1.0):
        d = math.sqrt(d2)
        ambient = 0.11
        diffuse = 0.38 * max(0.0, lit)
        atten = max(0.0, 1.0 - d / 36.0) ** 1.35
        bounce = 0.22 * atten
        b = (ambient + diffuse + bounce) * ao + self.boost / (1.0 + d * 0.22)
        if specular > 0.0:
            b += specular * 0.55 * atten
        if b > 1.55:
            b = 1.55
        f = min(1.0, d / 50.0) ** 1.55 * 0.58
        g = 1.0 - f
        r = min(255, int(col[0] * b * g + FOG[0] * f + specular * 40 * atten))
        gre = min(255, int(col[1] * b * g + FOG[1] * f + specular * 38 * atten))
        bl = min(255, int(col[2] * b * g + FOG[2] * f + specular * 30 * atten))
        return (r, gre, bl)

    def render_sky(self):
        low, cam = self.low, self.cam
        low.fill(GROUND)
        hy = HH + math.tan(cam.pitch) * cam.focal
        if hy > 0:
            n = 14
            for i in range(n):
                y0 = int(hy * i / n)
                y1 = int(hy * (i + 1) / n)
                if y0 >= RH:
                    break
                t = i / (n - 1)
                col = (int(SKY_TOP[0] + (SKY_HOR[0] - SKY_TOP[0]) * t),
                       int(SKY_TOP[1] + (SKY_HOR[1] - SKY_TOP[1]) * t),
                       int(SKY_TOP[2] + (SKY_HOR[2] - SKY_TOP[2]) * t))
                pygame.draw.rect(low, col, (0, y0, RW, y1 - y0 + 1))
        foc = cam.focal
        for sx_, sy_, sz_, br in STARS:
            d = sx_ * cam.fx + sy_ * cam.fy + sz_ * cam.fz
            if d > 0.05:
                xs = sx_ * cam.rx + sy_ * cam.ry
                ys = sx_ * cam.ux + sy_ * cam.uy + sz_ * cam.uz
                X, Y = HW + xs / d * foc, HH - ys / d * foc
                if 0 <= X < RW and 0 <= Y < RH:
                    low.set_at((int(X), int(Y)), (br, br, br))
        d = MOON[0] * cam.fx + MOON[1] * cam.fy + MOON[2] * cam.fz
        if d > 0.05:
            xs = MOON[0] * cam.rx + MOON[1] * cam.ry
            ys = MOON[0] * cam.ux + MOON[1] * cam.uy + MOON[2] * cam.uz
            X, Y = int(HW + xs / d * foc), int(HH - ys / d * foc)
            r = max(3, int(foc * 0.035))
            pygame.draw.circle(low, (40, 48, 70), (X, Y), int(r * 1.8))
            pygame.draw.circle(low, (228, 228, 208), (X, Y), r)

    def render_world(self):
        low, cam = self.low, self.cam
        self.render_sky()
        px, py, pz = cam.x, cam.y, cam.z
        fx, fy, fz = cam.fx, cam.fy, cam.fz
        rx, ry = cam.rx, cam.ry
        ux, uy, uz = cam.ux, cam.uy, cam.uz
        th = HW / cam.focal
        tv = HH / cam.focal
        M = 1.6

        def inview(wx, wy, wz):
            d = wx * fx + wy * fy + wz * fz
            if d < -M:
                return False
            if abs(wx * rx + wy * ry) > th * d + M:
                return False
            return abs(wx * ux + wy * uy + wz * uz) <= tv * d + M

        for verts, cx, cy, col in FLOOR_TILES:
            vx, vy = cx - px, cy - py
            d2 = vx * vx + vy * vy
            if d2 > DRAW_D2 or not inview(vx, vy, -pz):
                continue
            pts = cam.poly(verts)
            if pts:
                pygame.draw.polygon(low, self.sh(col, d2 + pz * pz, 0.9), pts)

        for z in self.zombies:
            if (z.x - px) ** 2 + (z.y - py) ** 2 > DRAW_D2:
                continue
            r = 0.5 * (1.0 if z.alive else max(0.2, 1 - z.dying))
            ring = [(z.x + math.cos(a * 0.7854) * r, z.y + math.sin(a * 0.7854) * r, 0.01) for a in range(8)]
            pts = cam.poly(ring)
            if pts:
                pygame.draw.polygon(low, (24, 24, 26), pts)

        items = []

        for verts, nx, ny, col, cx, cy in WALL_FACES:
            vx, vy = px - cx, py - cy
            if nx * vx + ny * vy <= 0:
                continue
            d2 = vx * vx + vy * vy
            if d2 > DRAW_D2 or not inview(cx - px, cy - py, WALL_H * 0.5 - pz):
                continue
            pts = cam.poly(verts)
            if not pts:
                continue
            lit = max(0.0, nx * LX + ny * LY * 0.85 + 0.12)
            c = self.sh(col, d2, lit, specular=0.0, ao=0.94)
            items.append((d2 + 1.0, 0, c, pts, None))

        for verts, col, cx, cy, nrm in DETAIL_FACES:
            vx, vy = px - cx, py - cy
            d2 = vx * vx + vy * vy
            if d2 > DRAW_D2 or nrm[0] * vx + nrm[1] * vy <= 0:
                continue
            if not inview(cx - px, cy - py, 1.2 - pz):
                continue
            pts = cam.poly(verts)
            if not pts:
                continue
            is_glass = col[2] > col[0] + 20
            c = self.sh(col, d2, 0.6, specular=0.7 if is_glass else 0.15, ao=1.0)
            items.append((d2 + 0.15, 0, c, pts, None))

        for verts, col, nrm, ctr, kind, bid in ROOF_FACES:
            mxr, myr, mzr = ctr
            vx, vy = px - mxr, py - myr
            d2 = vx * vx + vy * vy
            if d2 > DRAW_D2:
                continue
            if nrm[0] * vx + nrm[1] * vy + nrm[2] * (pz - mzr) <= 0:
                continue
            if kind in ("eave", "chimney"):
                bx0, by0, bx1, by1 = ROOF_BOUNDS[bid]
                if bx0 <= px <= bx1 and by0 <= py <= by1 and pz < WALL_H:
                    continue
            if not inview(mxr - px, myr - py, mzr - pz):
                continue
            pts = cam.poly(verts)
            if not pts:
                continue
            if kind == "ceiling":
                lit, spec = 0.3, 0.0
            elif kind == "eave":
                lit, spec = 0.35, 0.0
            else:
                lit = 0.55 + 0.45 * max(0.0, nrm[2])
                spec = (0.35 + 0.4 * max(0.0, lit - 0.5)) if kind == "shell" else 0.0
            c = self.sh(col, d2, lit, specular=spec, ao=1.0)
            items.append((d2 + 0.5, 0, c, pts, None))

        self.add_fire_zone_items(items)
        self.add_water_zone_items(items)
        self.add_spell_zone_items(items)
        self.add_fx_items(items)

        for z in self.zombies:
            self.add_zombie_items(z, items)

        if getattr(self, "net", None) and self.net.mode != "solo" and self.p2 and self.p2.hp > 0:
            self.add_ally_items(self.p2, items)

        for q in self.particles:
            s = cam.to_screen(q[0], q[1], q[2])
            if s:
                X, Y, d = s
                if -10 < X < RW + 10 and -10 < Y < RH + 10:
                    r = max(1, int(q[8] * cam.focal / d))
                    vx, vy = px - q[0], py - q[1]
                    items.append((vx * vx + vy * vy, 1, q[7], (int(X), int(Y), r), None))

        # büyü mermileri: halo + kuyruk izi + parlak çekirdek
        for b in self.bolts:
            s = cam.to_screen(b["x"], b["y"], b["z"])
            if not s:
                continue
            X, Y, d = s
            if not (-40 < X < RW + 40 and -40 < Y < RH + 40):
                continue
            r = max(2, int(b["r"] * cam.focal / max(0.2, d)))
            vx, vy = px - b["x"], py - b["y"]
            d2 = vx * vx + vy * vy
            col = b["col"]
            tail = cam.to_screen(b["x"] - b["dx"] * 0.08, b["y"] - b["dy"] * 0.08, b["z"] - b["dz"] * 0.08)
            if tail:
                items.append((d2 + 0.01, 2, col, ((int(X), int(Y)), (int(tail[0]), int(tail[1])), max(1, r)), None))
            halo = tuple(c // 3 for c in col)
            items.append((d2 + 0.02, 1, halo, (int(X), int(Y), r * 2), None))
            core = tuple(min(255, c + 70) for c in col)
            items.append((d2 - 0.01, 1, core, (int(X), int(Y), max(1, r // 2)), None))

        items.sort(key=lambda it: it[0], reverse=True)
        draw_poly = pygame.draw.polygon
        for key, kind, col, data, outl in items:
            if kind == 0:
                draw_poly(low, col, data)
                if outl:
                    draw_poly(low, outl, data, 1)
            elif kind == 1:
                pygame.draw.circle(low, col, (data[0], data[1]), data[2])
            else:
                pygame.draw.line(low, col, data[0], data[1], data[2])

        # ışınlar: zikzak yollu, kırpılmış ve görünür
        for bm in self.beams:
            k = max(0.15, bm["life"] / bm["max"])
            w = max(1, int(bm["w"] * k))
            pts = bm.get("pts") or [bm["a"], bm["b"]]
            for i in range(len(pts) - 1):
                seg = self._clip_seg(pts[i], pts[i + 1])
                if not seg:
                    continue
                a, b = self._proj(seg[0]), self._proj(seg[1])
                pygame.draw.line(low, bm["col"], a, b, w + 2)
                pygame.draw.line(low, (255, 255, 255), a, b, max(1, w - 1))

    def add_fire_zone_items(self, items):
        cam = self.cam
        px, py = cam.x, cam.y
        pulse = 0.5 + 0.5 * math.sin(self.time * 12)
        for zn in self.fire_zones:
            fade = max(0.3, zn["life"] / zn["max"])
            hot = (min(255, int(255 * fade)), min(255, int((70 + 110 * pulse) * fade)), min(255, int(18 * fade)))
            core = (255, min(255, int(160 + 80 * pulse)), 40)
            if zn["kind"] == "ring":
                cx, cy, r, ri = zn["x"], zn["y"], zn["r"], zn["r_in"]
                n = 16
                d2 = (cx - px) ** 2 + (cy - py) ** 2
                if d2 > DRAW_D2:
                    continue
                for i in range(n):
                    a0 = i / n * math.tau
                    a1 = (i + 1) / n * math.tau
                    verts = [
                        (cx + math.cos(a0) * ri, cy + math.sin(a0) * ri, 0.05),
                        (cx + math.cos(a1) * ri, cy + math.sin(a1) * ri, 0.05),
                        (cx + math.cos(a1) * r, cy + math.sin(a1) * r, 0.05),
                        (cx + math.cos(a0) * r, cy + math.sin(a0) * r, 0.05),
                    ]
                    pts = cam.poly(verts)
                    if pts:
                        items.append((d2, 0, hot, pts, None))
                # dönen alev dilleri (uçları sivri)
                for i in range(12):
                    a = i / 12 * math.tau + self.time * 1.7
                    x = cx + math.cos(a) * ((ri + r) * 0.5)
                    y = cy + math.sin(a) * ((ri + r) * 0.5)
                    h = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self.time * 10 + i))
                    tx, ty = -math.sin(a), math.cos(a)
                    flame = [(x - tx * 0.12, y - ty * 0.12, 0.02), (x + tx * 0.12, y + ty * 0.12, 0.02),
                             (x, y, h)]
                    pts = cam.poly(flame)
                    if pts:
                        items.append(((x - px) ** 2 + (y - py) ** 2, 0, core, pts, None))
            else:
                cx, cy = zn["x"], zn["y"]
                wx, wy = zn["wx"], zn["wy"]
                L, th, h = zn["length"], zn["thick"], zn["h"]
                d2 = (cx - px) ** 2 + (cy - py) ** 2
                if d2 > DRAW_D2:
                    continue
                segs = 8
                for i in range(segs):
                    t0 = (i / segs - 0.5) * L
                    t1 = ((i + 1) / segs - 0.5) * L
                    flicker = h * (0.72 + 0.28 * math.sin(self.time * 14 + i * 1.7))
                    x0, y0 = cx + wx * t0, cy + wy * t0
                    x1, y1 = cx + wx * t1, cy + wy * t1
                    if is_wall(x0, y0) and is_wall(x1, y1):
                        continue
                    ox, oy = zn["fx"] * th * 0.4, zn["fy"] * th * 0.4
                    for side in (1, -1):
                        verts = [
                            (x0 + ox * side, y0 + oy * side, 0.02),
                            (x1 + ox * side, y1 + oy * side, 0.02),
                            (x1 + ox * side, y1 + oy * side, flicker),
                            (x0 + ox * side, y0 + oy * side, flicker),
                        ]
                        pts = cam.poly(verts)
                        if pts:
                            mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
                            items.append(((mx - px) ** 2 + (my - py) ** 2, 0,
                                          hot if side > 0 else core, pts, None))
                    # tepede sivri alev dili
                    tip = [(x0, y0, flicker), (x1, y1, flicker),
                           ((x0 + x1) * 0.5, (y0 + y1) * 0.5, flicker + 0.55 * (0.5 + 0.5 * math.sin(self.time * 16 + i)))]
                    pts = cam.poly(tip)
                    if pts:
                        items.append(((cx - px) ** 2 + (cy - py) ** 2 - 0.01, 0, core, pts, None))

    def add_water_zone_items(self, items):
        cam = self.cam
        px, py = cam.x, cam.y
        pulse = 0.5 + 0.5 * math.sin(self.time * 8)
        for zn in self.water_zones:
            fade = max(0.35, zn["life"] / zn["max"])
            foam = (min(255, int((90 + 80 * pulse) * fade)),
                    min(255, int((170 + 50 * pulse) * fade)),
                    min(255, int(255 * fade)))
            deep = (20, min(255, int(90 * fade)), min(255, int(180 * fade)))
            if zn["kind"] == "tsunami":
                cx, cy = zn["x"], zn["y"]
                wx, wy = zn["wx"], zn["wy"]
                fx, fy = zn["fx"], zn["fy"]
                L, W = zn["length"], zn["width"]
                d2 = (cx - px) ** 2 + (cy - py) ** 2
                if d2 > DRAW_D2:
                    continue
                segs = 6
                h = 1.35 + 0.25 * pulse
                for i in range(segs):
                    t0 = (i / segs - 0.5) * W
                    t1 = ((i + 1) / segs - 0.5) * W
                    x0, y0 = cx + wx * t0, cy + wy * t0
                    x1, y1 = cx + wx * t1, cy + wy * t1
                    # kavis: merkeze yakın kısımlar daha yüksek (dalga tepesi)
                    bulge = 1.0 - abs((i + 0.5) / segs - 0.5) * 1.2
                    ox, oy = fx * L * 0.35, fy * L * 0.35
                    verts = [
                        (x0 - ox, y0 - oy, 0.04), (x1 - ox, y1 - oy, 0.04),
                        (x1 + ox, y1 + oy, h * 0.55 * bulge), (x0 + ox, y0 + oy, h * 0.55 * bulge),
                    ]
                    pts = cam.poly(verts)
                    if pts:
                        mx, my = (x0 + x1) * 0.5, (y0 + y1) * 0.5
                        items.append(((mx - px) ** 2 + (my - py) ** 2, 0, foam if i % 2 else deep, pts, None))
            else:
                cx, cy, r = zn["x"], zn["y"], zn["r"]
                d2 = (cx - px) ** 2 + (cy - py) ** 2
                if d2 > DRAW_D2:
                    continue
                n = 14
                ri = r * (0.18 + 0.08 * pulse)
                for i in range(n):
                    a0 = i / n * math.tau + self.time * 2.4
                    a1 = (i + 1) / n * math.tau + self.time * 2.4
                    verts = [
                        (cx + math.cos(a0) * ri, cy + math.sin(a0) * ri, 0.06),
                        (cx + math.cos(a1) * ri, cy + math.sin(a1) * ri, 0.06),
                        (cx + math.cos(a1) * r, cy + math.sin(a1) * r, 0.06),
                        (cx + math.cos(a0) * r, cy + math.sin(a0) * r, 0.06),
                    ]
                    pts = cam.poly(verts)
                    if pts:
                        items.append((d2, 0, foam if i % 2 else deep, pts, None))
                for i in range(8):
                    a = i / 8 * math.tau + self.time * 3.5
                    rr = r * (0.35 + 0.2 * math.sin(self.time * 5 + i))
                    x = cx + math.cos(a) * rr
                    y = cy + math.sin(a) * rr
                    h = 0.55 + 0.25 * (0.5 + 0.5 * math.sin(self.time * 9 + i))
                    spray = [(x - 0.12, y, 0.02), (x + 0.12, y, 0.02), (x, y, h)]
                    pts = cam.poly(spray)
                    if pts:
                        items.append(((x - px) ** 2 + (y - py) ** 2, 0, foam, pts, None))

    def add_spell_zone_items(self, items):
        cam = self.cam
        px, py = cam.x, cam.y
        pulse = 0.5 + 0.5 * math.sin(self.time * 9)
        for zn in self.spell_zones:
            fade = max(0.35, zn["life"] / zn["max"])
            col = zn["col"]
            a = tuple(min(255, int(c * fade * (0.7 + 0.3 * pulse))) for c in col)
            b = tuple(min(255, int(min(255, c + 40) * fade)) for c in col)
            cx, cy = zn["x"], zn["y"]
            r = zn["r"]
            d2 = (cx - px) ** 2 + (cy - py) ** 2
            if d2 > DRAW_D2:
                continue
            ri = max(0.12, r * (0.22 if zn["kind"] != "quake" else 0.72))
            n = 14
            spin = zn.get("spin", 1.0) * self.time
            for i in range(n):
                a0 = i / n * math.tau + spin
                a1 = (i + 1) / n * math.tau + spin
                verts = [
                    (cx + math.cos(a0) * ri, cy + math.sin(a0) * ri, 0.05),
                    (cx + math.cos(a1) * ri, cy + math.sin(a1) * ri, 0.05),
                    (cx + math.cos(a1) * r, cy + math.sin(a1) * r, 0.05),
                    (cx + math.cos(a0) * r, cy + math.sin(a0) * r, 0.05),
                ]
                pts = cam.poly(verts)
                if pts:
                    items.append((d2, 0, a if i % 2 else b, pts, None))

            kind = zn["kind"]
            if kind == "guardians":
                # dört ruh küre olarak dönüyor
                for i in range(4):
                    ang = self.time * 2.4 + i * math.tau / 4
                    gx = cx + math.cos(ang) * r * 0.9
                    gy = cy + math.sin(ang) * r * 0.9
                    gz = 1.2 + 0.15 * math.sin(self.time * 5 + i)
                    s = cam.to_screen(gx, gy, gz)
                    if s:
                        X, Y, dd = s
                        rad = max(3, int(0.18 * cam.focal / max(0.2, dd)))
                        gd2 = (gx - px) ** 2 + (gy - py) ** 2
                        items.append((gd2 - 0.05, 1, (255, 252, 210), (int(X), int(Y), rad), None))
                        items.append((gd2 - 0.04, 1, (255, 230, 120), (int(X), int(Y), max(1, rad // 2)), None))
            else:
                spikes = 8 if kind in ("whirl", "storm") else 6
                hbase = 1.15 if kind == "whirl" else 0.55
                for i in range(spikes):
                    ang = i / spikes * math.tau + spin * 1.3
                    rr = r * (0.4 + 0.25 * math.sin(self.time * 6 + i))
                    x = cx + math.cos(ang) * rr
                    y = cy + math.sin(ang) * rr
                    h = hbase + 0.3 * pulse
                    flame = [(x - 0.12, y, 0.02), (x + 0.12, y, 0.02), (x, y, h)]
                    pts = cam.poly(flame)
                    if pts:
                        items.append(((x - px) ** 2 + (y - py) ** 2, 0, b, pts, None))

    def add_ally_items(self, pl, items):
        cam = self.cam
        px, py, pz = cam.x, cam.y, cam.z
        if (pl.x - px) ** 2 + (pl.y - py) ** 2 > DRAW_D2:
            return
        if (pl.x - px) * cam.fx + (pl.y - py) * cam.fy + (0.9 - pz) * cam.fz < -1.6:
            return
        ca, sa = math.cos(pl.yaw), math.sin(pl.yaw)
        try:
            el_col = ELEMENTS[pl.elem % len(ELEMENTS)]["col"]
        except Exception:
            el_col = (80, 160, 255)
        parts = [
            (-0.14, 0.14, -0.14, 0.14, 0.0, 0.78, (35, 40, 65)),
            (-0.18, 0.18, -0.22, 0.22, 0.78, 1.42, (45, 100, 190)),
            (-0.14, 0.14, -0.14, 0.14, 1.42, 1.74, (220, 175, 135)),
            (0.08, 0.58, -0.06, 0.06, 1.05, 1.22, el_col),
        ]
        zx, zy = pl.x, pl.y
        jz = getattr(pl, "jump", 0.0) or 0.0
        for x0, x1, y0, y1, z0, z1, col in parts:
            z0, z1 = z0 + jz, z1 + jz
            cs = []
            for ix, iy, iz in CORNERS:
                lx = x1 if ix else x0
                ly = y1 if iy else y0
                lz = z1 if iz else z0
                cs.append((zx + lx * ca - ly * sa, zy + lx * sa + ly * ca, lz))
            lcx, lcy, lcz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
            hx, hy, hz = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
            for idx, (nx, ny, nz) in FACES:
                wnx = nx * ca - ny * sa
                wny = nx * sa + ny * ca
                fl_x = lcx + nx * hx
                fl_y = lcy + ny * hy
                fz_ = lcz + nz * hz
                fxw = zx + fl_x * ca - fl_y * sa
                fyw = zy + fl_x * sa + fl_y * ca
                vx, vy, vz = px - fxw, py - fyw, pz - fz_
                if wnx * vx + wny * vy + nz * vz <= 0:
                    continue
                pts = cam.poly([cs[i] for i in idx])
                if not pts:
                    continue
                d2 = vx * vx + vy * vy
                c = self.sh(col, d2 + vz * vz, max(0.0, wnx * LX + wny * LY + nz * LZ))
                items.append((d2 + 0.05, 0, c, pts, None))
        ring = []
        for i in range(10):
            a = i / 10 * math.tau
            ring.append((zx + math.cos(a) * 0.35, zy + math.sin(a) * 0.35, 0.04))
        pts = cam.poly(ring)
        if pts:
            items.append(((zx - px) ** 2 + (zy - py) ** 2, 0, (80, 200, 255), pts, None))

    def add_zombie_items(self, z, items):
        cam = self.cam
        px, py, pz = cam.x, cam.y, cam.z
        if (z.x - px) ** 2 + (z.y - py) ** 2 > DRAW_D2:
            return
        if (z.x - px) * cam.fx + (z.y - py) * cam.fy + (0.9 - pz) * cam.fz < -1.6:
            return
        ca, sa = math.cos(z.face), math.sin(z.face)
        zx, zy = z.x, z.y
        for name, b, col, mult, hit, emi in zombie_boxes(z):
            x0, x1, y0, y1, z0, z1 = b
            if z.elem_glow and z.elem_glow_t > 0:
                g = z.elem_glow
                col = ((col[0] + g[0]) // 2, (col[1] + g[1]) // 2, (col[2] + g[2]) // 2)
            if z.frozen > 0:
                col = (min(255, col[0] // 2 + 40), min(255, col[1] // 2 + 140), min(255, col[2] + 90))
            if z.hit_timer > 0:
                col = (min(255, col[0] + 120), col[1] // 2, col[2] // 2)
            cs = []
            for ix, iy, iz in CORNERS:
                lx = x1 if ix else x0
                ly = y1 if iy else y0
                lz = z1 if iz else z0
                cs.append((zx + lx * ca - ly * sa, zy + lx * sa + ly * ca, lz))
            lcx, lcy, lcz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
            hx, hy, hz = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
            for idx, (nx, ny, nz) in FACES:
                wnx = nx * ca - ny * sa
                wny = nx * sa + ny * ca
                fl_x = lcx + nx * hx
                fl_y = lcy + ny * hy
                fz_ = lcz + nz * hz
                fxw = zx + fl_x * ca - fl_y * sa
                fyw = zy + fl_x * sa + fl_y * ca
                vx, vy, vz = px - fxw, py - fyw, pz - fz_
                if wnx * vx + wny * vy + nz * vz <= 0:
                    continue
                pts = cam.poly([cs[i] for i in idx])
                if not pts:
                    continue
                d2 = vx * vx + vy * vy
                if emi:
                    c = col
                else:
                    lit = max(0.0, wnx * LX + wny * LY + nz * LZ)
                    c = self.sh(col, d2 + vz * vz, lit)
                items.append((d2 + 0.1 * vz * vz, 0, c, pts, None))

    # ----------------------------------------------------- HUD
    def _render(self, font, txt, col):
        key = (id(font), txt, col)
        surf = self._txt_cache.get(key)
        if surf is None:
            if len(self._txt_cache) > 600:
                self._txt_cache.clear()
            surf = font.render(txt, True, col)
            self._txt_cache[key] = surf
        return surf

    def text(self, font, txt, pos, color=(255, 255, 255), center=False):
        img = self._render(font, txt, color)
        sh = self._render(font, txt, (0, 0, 0))
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        self.screen.blit(sh, (r.x + 3, r.y + 3))
        self.screen.blit(img, r)

    def tint_screen(self, col, alpha):
        v = self.vignette
        v.fill(col)
        v.set_alpha(max(0, min(255, int(alpha))))
        self.screen.blit(v, (0, 0))

    def draw_weapon(self):
        s, p, a = self.screen, self.p, self.ads
        cx, cy = SCREEN_W // 2, SCREEN_H // 2
        bobx = math.cos(p.bob * 0.5) * 16 * (1 - a) * self.move_amt
        boby = abs(math.sin(p.bob)) * 12 * (1 - a) * self.move_amt
        recoil = self.recoil_vis * 55
        bx = cx + (1 - a) * 380 + self.sway_x + bobx
        by = SCREEN_H + 60 + a * 170 + boby + recoil + self.sway_y
        tipx = cx + (1 - a) * 150 + self.sway_x * 0.3
        tipy = cy + (1 - a) * 330 + a * 90 + self.sway_y * 0.3 + recoil * 0.3

        def L(t, w0=170, w1=16):
            return (bx + (tipx - bx) * t, by + (tipy - by) * t, w0 + (w1 - w0) * t)

        def seg(t0, t1, col, k=1.0):
            x0, y0, w0 = L(t0)
            x1, y1, w1 = L(t1)
            pygame.draw.polygon(s, col, [(x0 - w0 * k, y0), (x0 + w0 * k, y0), (x1 + w1 * k, y1), (x1 - w1 * k, y1)])

        mx0, my0, mw = L(0.12)
        pygame.draw.polygon(s, (30, 30, 34), [(mx0 - 40, my0), (mx0 + 40, my0), (mx0 + 70, my0 + 190), (mx0 - 10, my0 + 215)])
        ec = self.current_elem()["col"]
        wood = ((105 + ec[0]) // 2, (70 + ec[1]) // 2, (40 + ec[2]) // 2)
        wood2 = ((135 + ec[0]) // 2, (92 + ec[1]) // 2, (55 + ec[2]) // 2)
        seg(0.0, 0.34, (40, 42, 48))
        seg(0.0, 0.34, (62, 64, 72), 0.35)
        seg(0.34, 0.70, wood)
        seg(0.34, 0.70, wood2, 0.3)
        seg(0.70, 1.0, (28, 28, 32), 0.55)
        x1, y1, w1 = L(1.0)
        pygame.draw.rect(s, (15, 15, 15), (x1 - 4, y1 - 34, 8, 34))
        x2, y2, w2 = L(0.30)
        pygame.draw.rect(s, (15, 15, 15), (x2 - 46, y2 - 44, 12, 44))
        pygame.draw.rect(s, (15, 15, 15), (x2 + 34, y2 - 44, 12, 44))
        hx, hy, hw = L(0.52)
        pygame.draw.ellipse(s, (205, 152, 120), (hx - hw * 1.3 - 40, hy - 10, hw * 2.2, hw * 1.0))
        pygame.draw.polygon(s, (45, 60, 45), [(hx - hw * 2.0, hy + 60), (hx - hw * 0.5, hy + 20),
                                              (hx - hw * 0.2, SCREEN_H + 100), (hx - hw * 2.8, SCREEN_H + 100)])
        gx, gy, gw = L(0.05)
        pygame.draw.ellipse(s, (205, 152, 120), (gx + 20, gy - 40, 150, 100))
        if self.flash > 0 or self.spell_flash > 0:
            ex, ey, _ = L(1.0)
            ey -= 10
            pts = []
            for i in range(10):
                ang = i * math.pi / 5
                r = 60 if i % 2 == 0 else 24
                pts.append((ex + math.cos(ang) * r * 1.2, ey + math.sin(ang) * r - 20))
            burst = (255, 205, 80) if self.flash > 0 else self.spell_col
            pygame.draw.polygon(s, burst, pts)
            pygame.draw.circle(s, (255, 250, 210), (int(ex), int(ey - 20)), 22)

    def draw_crosshair(self):
        s = self.screen
        cx, cy = SCREEN_W // 2, SCREEN_H // 2
        gap = int(self.spread() * self.cam.focal * RENDER_SCALE)
        gap = max(6, min(140, gap))
        col = (255, 255, 255)
        for (ax, ay), (bx_, by_) in (((-gap - 16, 0), (-gap, 0)), ((gap, 0), (gap + 16, 0)),
                                     ((0, -gap - 16), (0, -gap)), ((0, gap), (0, gap + 16))):
            pygame.draw.line(s, (0, 0, 0), (cx + ax, cy + ay), (cx + bx_, cy + by_), 6)
            pygame.draw.line(s, col, (cx + ax, cy + ay), (cx + bx_, cy + by_), 3)
        pygame.draw.circle(s, (255, 60, 60), (cx, cy), 3)
        if self.hitmark > 0 or self.killmark > 0:
            if self.killmark > 0:
                c, r = (255, 40, 40), 34
            elif self.hit_head:
                c, r = (255, 210, 60), 28
            else:
                c, r = (255, 255, 255), 22
            for sx_, sy_ in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                pygame.draw.line(s, c, (cx + sx_ * 12, cy + sy_ * 12), (cx + sx_ * r, cy + sy_ * r), 4)

    def draw_popups(self):
        for pu in self.popups:
            k = 1 - pu["life"] / pu["max"]
            pos = pu["pos"]
            sc = self.cam.to_screen(pos[0], pos[1], pos[2] + k * 0.7)
            if not sc:
                continue
            X, Y = sc[0] * RENDER_SCALE, sc[1] * RENDER_SCALE
            if -100 < X < SCREEN_W + 100 and -100 < Y < SCREEN_H + 100:
                a = int(255 * min(1.0, pu["life"] / pu["max"] * 2.2))
                img = self._render(self.pop_font, pu["text"], pu["col"])
                sh = self._render(self.pop_font, pu["text"], (0, 0, 0))
                img.set_alpha(a)
                sh.set_alpha(a)
                r = img.get_rect(center=(X, Y))
                self.screen.blit(sh, (r.x + 2, r.y + 2))
                self.screen.blit(img, r)

    def draw_minimap(self):
        s, p = self.screen, self.p
        cell = 7
        ox, oy = SCREEN_W - MAP_W * cell - 30, 30
        if self._mm_base is None:
            base = pygame.Surface((MAP_W * cell, MAP_H * cell))
            base.fill((0, 0, 0))
            for y in range(MAP_H):
                for x in range(MAP_W):
                    if WORLD[y][x]:
                        pygame.draw.rect(base, WALL_COLORS[WORLD[y][x]], (x * cell, y * cell, cell, cell))
            self._mm_base = base
        pygame.draw.rect(s, (0, 0, 0), (ox - 4, oy - 4, MAP_W * cell + 8, MAP_H * cell + 8))
        s.blit(self._mm_base, (ox, oy))
        for z in self.zombies:
            if z.alive:
                pygame.draw.circle(s, (255, 40, 40), (int(ox + z.x * cell), int(oy + z.y * cell)), 3)
        px, py = ox + p.x * cell, oy + p.y * cell
        pygame.draw.circle(s, (80, 255, 120), (int(px), int(py)), 4)
        pygame.draw.line(s, (80, 255, 120), (px, py),
                         (px + math.cos(p.yaw) * 16, py + math.sin(p.yaw) * 16), 2)
        if getattr(self, "net", None) and self.net.mode != "solo" and self.p2 and self.p2.hp > 0:
            pygame.draw.circle(s, (80, 180, 255), (int(ox + self.p2.x * cell), int(oy + self.p2.y * cell)), 4)

    def draw_hud(self):
        s, p = self.screen, self.p
        self.draw_popups()
        self.draw_crosshair()
        pygame.draw.rect(s, (0, 0, 0), (40, SCREEN_H - 90, 404, 50))
        hp = max(0, p.hp)
        col = (60, 220, 80) if hp > 50 else (230, 180, 40) if hp > 25 else (230, 50, 50)
        pygame.draw.rect(s, col, (42, SCREEN_H - 88, int(400 * hp / 100), 46))
        self.text(self.font, "CAN %d" % hp, (56, SCREEN_H - 86))
        pygame.draw.rect(s, (0, 0, 0), (40, SCREEN_H - 148, 404, 44))
        pygame.draw.rect(s, (50, 110, 230), (42, SCREEN_H - 146, int(400 * p.mana / MANA_MAX), 40))
        self.text(self.font, "MANA %d" % int(p.mana), (56, SCREEN_H - 144), (210, 230, 255))
        self.draw_elements()
        el = self.current_elem()
        self.text(self.mid, "ASA  ·  %s" % el["name"], (SCREEN_W - 520, SCREEN_H - 100), el["col"])
        self.text(self.small, "Sol tık: 5 mana", (SCREEN_W - 520, SCREEN_H - 55), (180, 190, 210))
        if p.mana < STAFF_MANA:
            self.text(self.mid, "MANA YETERSİZ!", (SCREEN_W // 2, SCREEN_H // 2 + 180), (100, 160, 255), True)
        self.text(self.big, "%d" % p.score, (SCREEN_W // 2, 85), (255, 240, 170), True)
        self.text(self.small, "SKOR   |   REKOR %d" % max(self.highscore, p.score), (SCREEN_W // 2, 160), (210, 210, 210), True)
        if self.combo > 1:
            self.text(self.mid, "KOMBO x%.1f" % self.combo_mult(), (SCREEN_W // 2, 215), (255, 150, 60), True)
            w = int(300 * max(0.0, self.combo_t) / 4.0)
            pygame.draw.rect(s, (255, 150, 60), (SCREEN_W // 2 - 150, 250, w, 8))
        acc = int(100 * p.hits / p.shots) if p.shots else 0
        self.text(self.font, "DALGA %d" % self.wave, (40, 30))
        self.text(self.small, "Öldürülen: %d" % p.kills, (40, 80))
        self.text(self.small, "Kafa atışı: %d" % p.headshots, (40, 114))
        self.text(self.small, "İsabet: %%%d" % acc, (40, 148))
        self.text(self.small, "Kalan zombi: %d" % (self.alive_count() + self.to_spawn), (40, 182))
        if self.banner[1] > 0 and self.intermission <= 0:
            self.text(self.big, self.banner[0], (SCREEN_W // 2, 400), (255, 230, 80), True)
        if self.intermission > 0:
            self.text(self.mid, "DALGA %d TEMİZLENDİ" % self.wave, (SCREEN_W // 2, 330), (255, 230, 80), True)
            for i, ln in enumerate(self.bonus_lines):
                self.text(self.font, ln, (SCREEN_W // 2, 400 + i * 48), (230, 230, 230), True)
            self.text(self.font, "Sonraki dalga: %d" % (int(self.intermission) + 1),
                      (SCREEN_W // 2, 400 + len(self.bonus_lines) * 48 + 30), (200, 200, 255), True)
        if self.time < 10:
            self.text(self.small, "WASD hareket | Fare bak | Sol tık ateş | 1-7 element | Q / E / T büyü | "
                      "KAFAYA nişan al: x3.5 hasar!", (SCREEN_W // 2, SCREEN_H - 168), (235, 235, 235), True)
        if self.hurt > 0:
            self.tint_screen((200, 0, 0), 160 * self.hurt / 0.45)
        elif p.hp < 30 and self.state == "play":
            self.tint_screen((160, 0, 0), 40 + 25 * math.sin(self.time * 6))
        self.draw_minimap()
        self.text(self.tiny, "FPS %d" % self.clock.get_fps(), (40, SCREEN_H - 200), (255, 255, 0))

    def draw_elements(self):
        s, p = self.screen, self.p
        n = len(ELEMENTS)
        w, h = 86, 86
        gap = 10
        total = n * w + (n - 1) * gap
        ox = SCREEN_W // 2 - total // 2
        oy = SCREEN_H - 250
        for i, el in enumerate(ELEMENTS):
            x = ox + i * (w + gap)
            sel = i == p.elem
            bg = (18, 18, 24)
            pygame.draw.rect(s, bg, (x, oy, w, h))
            border = el["col"] if sel else (70, 70, 80)
            pygame.draw.rect(s, border, (x, oy, w, h), 4 if sel else 2)
            pygame.draw.circle(s, el["col"], (x + w // 2, oy + 32), 16 if sel else 12)
            self.text(self.tiny, "%d %s" % (i + 1, el["name"]), (x + w // 2, oy + 62), el["col"] if sel else (200, 200, 200), True)
        hint = ELEMENTS[p.elem]
        skills = ELEMENT_SKILLS[hint["id"]]
        cds = p.skill_cd[hint["id"]]
        c = hint["col"]
        bg = tuple(max(8, v // 14) for v in c)
        wait_b = tuple(max(28, v // 3) for v in c)
        wait_t = tuple(min(200, 70 + v // 2) for v in c)
        mana_c = tuple(min(255, 120 + v // 2) for v in c)
        bw, bh, gap2 = 168, 52, 8
        total2 = 3 * bw + 2 * gap2
        sx = SCREEN_W // 2 - total2 // 2
        sy = oy - 78
        for i, sk in enumerate(skills):
            x = sx + i * (bw + gap2)
            ready = cds[i] <= 0 and p.mana >= sk["mana"]
            pygame.draw.rect(s, bg, (x, sy, bw, bh))
            pygame.draw.rect(s, hint["col"] if ready else wait_b, (x, sy, bw, bh), 2)
            label = "%s  %s" % (sk["key"], sk["name"])
            if cds[i] > 0:
                label = "%s  %.1fs" % (sk["key"], cds[i])
            self.text(self.tiny, label, (x + bw // 2, sy + 16), hint["col"] if ready else wait_t, True)
            self.text(self.tiny, "%d mana" % sk["mana"], (x + bw // 2, sy + 34), mana_c, True)
        self.text(self.small, hint["hint"], (SCREEN_W // 2, sy - 26), hint["col"], True)

    # ----------------------------------------------------- ANA DÖNGÜ
    def draw_menu(self):
        s = self.screen
        s.fill((8, 10, 18))
        cx = SCREEN_W // 2
        self.text(self.big, "ZOMBİ AVI 3D", (cx, 150), (255, 230, 100), True)
        self.text(self.font, "LAN  ·  Port %d  ·  Modem ayarı gerekmez" % NET_PORT, (cx, 240), (160, 180, 220), True)
        options = ["TEK OYUNCU", "SUNUCU KUR (aynı Wi-Fi)", "SUNUCUYA KATIL"]
        for i, opt in enumerate(options):
            col = (255, 255, 120) if i == self.menu_sel else (200, 200, 210)
            prefix = "> " if i == self.menu_sel else "  "
            self.text(self.mid, prefix + opt, (cx, 360 + i * 75), col, True)
        if self.menu_sel == 1:
            self.text(self.font, self.net.status or ("Senin IP: %s" % self.net.local_ip), (cx, 620), (120, 220, 140), True)
            self.text(self.small, "Arkadasin ayni Wi-Fi'de 'Sunucuya Katil' + F5 yapsin", (cx, 670), (150, 160, 170), True)
        elif self.menu_sel == 2:
            self.text(self.font, "IP: %s" % (self.join_ip or "..."), (cx, 600), (120, 200, 255), True)
            self.text(self.small, "F5 = otomatik bul  |  rakam ve nokta yaz  |  Ctrl+V yapistir", (cx, 650), (150, 160, 170), True)
            self.text(self.small, "Ornek: 192.168.1.12   (iki nokta yazmana gerek yok)", (cx, 685), (140, 150, 160), True)
            if self.net.status:
                self.text(self.small, self.net.status, (cx, 725), (255, 180, 100), True)
        self.text(self.small, "Ok tuslari sec  |  Enter onayla  |  ESC cikis", (cx, SCREEN_H - 70), (140, 140, 150), True)
        if self.net.mode == "host" and self.net.connected():
            self.text(self.mid, "ISTEMCI BAGLANDI - Enter ile basla", (cx, 780), (80, 255, 120), True)

    def start_solo(self):
        self.net.close()
        self.reset(keep_net=False)
        self.state = "play"
        self.banner = ("DALGA 1", 3.0)
        pygame.event.set_grab(True)
        pygame.mouse.set_visible(False)
        pygame.mouse.get_rel()

    def start_host(self):
        self.net.host()

    def try_join(self):
        ip = self.join_ip.strip() or "127.0.0.1"
        if self.net.join(ip):
            self.reset(keep_net=True)
            self.state = "play"
            self.banner = ("LAN - ISTEMCI", 2.5)
            pygame.event.set_grab(True)
            pygame.mouse.set_visible(False)
            pygame.mouse.get_rel()

    def begin_host_game(self):
        if self.net.mode == "host" and self.net.connected():
            self.reset(keep_net=True)
            self.state = "play"
            self.banner = ("LAN - SUNUCU", 2.5)
            pygame.event.set_grab(True)
            pygame.mouse.set_visible(False)
            pygame.mouse.get_rel()

    def draw(self):
        if self.state == "menu":
            self.draw_menu()
            self.touch.draw(self.screen, self.tiny, self.state, self.menu_sel, self.p.elem)
            pygame.display.flip()
            return
        self.render_world()
        pygame.transform.scale(self.low, (SCREEN_W, SCREEN_H), self.screen)
        self.draw_weapon()
        self.draw_hud()
        if self.net.mode != "solo":
            label = "SUNUCU" if self.net.mode == "host" else "ISTEMCI"
            col = (100, 255, 140) if self.net.connected() else (255, 120, 80)
            self.text(self.tiny, "LAN %s  %s" % (label, self.net.status), (SCREEN_W // 2, 20), col, True)
            if self.p2 and self.p2.hp > 0:
                self.text(self.tiny, "Takim arkadasi CAN %d" % int(self.p2.hp), (SCREEN_W // 2, 48), (180, 220, 255), True)
        if self.state == "dead":
            self.tint_screen((110, 0, 0), 175)
            p = self.p
            cx = SCREEN_W // 2
            self.text(self.big, "OLDUN", (cx, 330), (255, 60, 60), True)
            sc = p.score + (self.p2.score if self.p2 and self.net.mode != "solo" else 0)
            self.text(self.mid, "Skor: %d" % sc, (cx, 460), (255, 240, 170), True)
            self.text(self.font, "Dalga: %d  Oldurulen: %d" % (self.wave, p.kills), (cx, 560), (230, 230, 230), True)
            self.text(self.mid, "ENTER yeniden  |  ESC menu", (cx, 680), (230, 230, 230), True)
        self.touch.draw(self.screen, self.tiny, self.state, self.menu_sel, self.p.elem)
        pygame.display.flip()

    def _sync_android_ui(self):
        # Android'de yazı girişi (soft klavye) yalnızca IP alanındayken açık olsun
        want = self.state == "menu" and self.menu_sel == 2
        if want != self._ti_on:
            (pygame.key.start_text_input if want else pygame.key.stop_text_input)()
            self._ti_on = want
        if self.state != "play":
            self.touch.reset_holds()

    def run(self):
        paused = False
        while True:
            try:
                dt = min(self.clock.tick(60) / 1000.0, 0.05)
                for e in pygame.event.get():
                    if e.type in _TOUCH_EVENTS:
                        self.touch.handle(e, self.state, self.menu_sel, self.p.elem)
                        continue
                    if IS_ANDROID and e.type == pygame.TEXTINPUT and self.state == "menu" and self.menu_sel == 2:
                        for ch in e.text:
                            if ch == ",":
                                ch = "."
                            if ch.isdigit() or ch == ".":
                                if len(self.join_ip) < 21:
                                    self.join_ip += ch
                            elif ch == ":" and ":" not in self.join_ip:
                                self.join_ip += ":"
                        continue
                    if e.type == pygame.QUIT:
                        self.net.close()
                        pygame.quit(); sys.exit()
                    if e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_ESCAPE:
                            if self.state in ("play", "dead"):
                                self.net.close()
                                self.state = "menu"
                                pygame.event.set_grab(False)
                                pygame.mouse.set_visible(True)
                            else:
                                self.net.close()
                                pygame.quit(); sys.exit()
                        if self.state == "menu":
                            if e.key == pygame.K_UP:
                                self.menu_sel = (self.menu_sel - 1) % 3
                            elif e.key == pygame.K_DOWN:
                                self.menu_sel = (self.menu_sel + 1) % 3
                            elif e.key == pygame.K_F5 and self.menu_sel == 2:
                                self.net.status = "Taranıyor..."
                                self.draw()
                                hosts = self.net.discover(1.6)
                                if hosts:
                                    self.join_ip = hosts[0][0]
                                    self.net.status = "Bulundu: %s  (Enter)" % self.join_ip
                            elif e.key == pygame.K_RETURN:
                                if self.menu_sel == 0:
                                    self.start_solo()
                                elif self.menu_sel == 1:
                                    if self.net.mode == "host" and self.net.connected():
                                        self.begin_host_game()
                                    else:
                                        self.start_host()
                                else:
                                    self.try_join()
                            elif self.menu_sel == 2:
                                mods = pygame.key.get_mods()
                                if e.key == pygame.K_BACKSPACE:
                                    self.join_ip = self.join_ip[:-1]
                                elif e.key == pygame.K_v and (mods & pygame.KMOD_CTRL):
                                    try:
                                        clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                                        if clip:
                                            t = clip.decode("utf-8", errors="ignore").strip()
                                            t = "".join(c for c in t if c.isdigit() or c in ".:")
                                            if t:
                                                self.join_ip = t[:21]
                                    except Exception:
                                        pass
                                elif not IS_ANDROID and e.key in (pygame.K_PERIOD, pygame.K_KP_PERIOD, pygame.K_COMMA):
                                    if len(self.join_ip) < 21:
                                        self.join_ip += "."
                                elif not IS_ANDROID and e.key in (pygame.K_SEMICOLON, pygame.K_COLON):
                                    if len(self.join_ip) < 21 and ":" not in self.join_ip:
                                        self.join_ip += ":"
                                elif e.unicode and not IS_ANDROID:
                                    ch = e.unicode
                                    if ch == ",":
                                        ch = "."
                                    if ch.isdigit() or ch == ".":
                                        if len(self.join_ip) < 21:
                                            self.join_ip += ch
                                    elif ch == ":" and ":" not in self.join_ip:
                                        self.join_ip += ":"
                        if e.key == pygame.K_RETURN and self.state == "dead":
                            self.reset(keep_net=(self.net.mode != "solo"))
                            self.state = "play"
                        if e.key == pygame.K_p and self.state == "play":
                            paused = not paused
                            pygame.event.set_grab(not paused)
                            pygame.mouse.set_visible(paused)
                            pygame.mouse.get_rel()
                        if self.state == "play" and pygame.K_1 <= e.key <= pygame.K_7:
                            self.p.elem = e.key - pygame.K_1
                            self.banner = (self.current_elem()["name"], 0.7)
                        if self.state == "play":
                            if e.key == pygame.K_q:
                                self.request_skill(0)
                            elif e.key == pygame.K_e:
                                self.request_skill(1)
                            elif e.key == pygame.K_t:
                                self.request_skill(2)
                if IS_ANDROID:
                    self._sync_android_ui()
                if self.state == "menu":
                    self.draw()
                    continue
                if paused:
                    self.text(self.big, "DURAKLATILDI", (SCREEN_W // 2, SCREEN_H // 2), (255, 255, 255), True)
                    pygame.display.flip()
                    continue
                if self.state == "play":
                    self.update(dt)
                else:
                    self.update_fx(dt)
                    self.update_particles(dt)
                    self.update_popups(dt)
                    self.hurt = max(0.0, self.hurt - dt)
                self.draw()
            except Exception as ex:
                print("Uyari:", type(ex).__name__, ex)
                continue


if __name__ == "__main__":
    Game().run()