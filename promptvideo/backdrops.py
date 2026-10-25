"""Karakter sahneleri için düz çizim mekânlar (şehir, ofis, uzay, laboratuvar, doğa, stüdyo).

Hepsi koyu tonlarda ve turuncu ışıklarla çizilir ki önlerindeki karakter ve yazılar öne çıksın.
Zemin çizgisi y=960 civarındadır; karakterlerin ayakları ~1015'te durur.
"""
import math
import random

import cairo

from . import theme as th
from .theme import W, H, mix

FLOOR = 960
NAMES = {"studio": "Stüdyo", "city": "Şehir", "office": "Ofis", "space": "Uzay", "lab": "Laboratuvar",
         "nature": "Doğa", "none": "Yok"}


def _rgb(h):
    return th.hex2rgb(h)


def _floor(ctx, col_top, col_bot):
    g = cairo.LinearGradient(0, FLOOR, 0, H)
    g.add_color_stop_rgb(0, *col_top)
    g.add_color_stop_rgb(1, *col_bot)
    ctx.set_source(g)
    ctx.rectangle(0, FLOOR, W, H - FLOOR)
    ctx.fill()


def _rect(ctx, x, y, w, h, col, a=1.0):
    ctx.set_source_rgba(*col, a)
    ctx.rectangle(x, y, w, h)
    ctx.fill()


def studio(ctx, t):
    _rect(ctx, 0, 0, W, H, _rgb("#0B0806"))
    # arka perde ve dikey şeritler
    for i in range(24):
        x = i * W / 24
        _rect(ctx, x, 0, W / 48, FLOOR, _rgb("#120C08"))
    for k, x in enumerate((420, 1500)):  # spot ışıkları
        sway = math.sin(t * 0.6 + k * 2) * 40
        g = cairo.LinearGradient(x, 0, x + sway, FLOOR)
        g.add_color_stop_rgba(0, *th.ACCENT, 0.22)
        g.add_color_stop_rgba(1, *th.ACCENT, 0.0)
        ctx.set_source(g)
        ctx.move_to(x - 30, -10)
        ctx.line_to(x + 30, -10)
        ctx.line_to(x + sway + 260, FLOOR + 40)
        ctx.line_to(x + sway - 260, FLOOR + 40)
        ctx.close_path()
        ctx.fill()
    _floor(ctx, _rgb("#1A120C"), _rgb("#070504"))
    for k, x in enumerate((420, 1500)):
        sway = math.sin(t * 0.6 + k * 2) * 40
        ctx.save()
        ctx.translate(x + sway, FLOOR + 50)
        ctx.scale(1, 0.18)
        g = cairo.RadialGradient(0, 0, 10, 0, 0, 300)
        g.add_color_stop_rgba(0, *th.ACCENT, 0.25)
        g.add_color_stop_rgba(1, *th.ACCENT, 0)
        ctx.set_source(g)
        ctx.arc(0, 0, 300, 0, math.tau)
        ctx.fill()
        ctx.restore()


def city(ctx, t):
    g = cairo.LinearGradient(0, 0, 0, FLOOR)
    g.add_color_stop_rgb(0, *_rgb("#07050A"))
    g.add_color_stop_rgb(1, *_rgb("#2A1306"))
    ctx.set_source(g)
    ctx.rectangle(0, 0, W, FLOOR)
    ctx.fill()
    ctx.set_source_rgba(*_rgb("#F2EBE1"), 0.9)  # ay
    ctx.arc(1580, 180, 60, 0, math.tau)
    ctx.fill()
    ctx.set_source_rgb(*_rgb("#07050A"))
    ctx.arc(1555, 165, 56, 0, math.tau)
    ctx.fill()
    for layer, (col, base, hmin, hmax, speed) in enumerate((
            ("#140C08", 760, 140, 380, 4), ("#1E120A", 860, 120, 300, 9), ("#27170C", FLOOR, 80, 240, 16))):
        rnd = random.Random(layer * 11 + 3)
        x = -((t * speed) % 300) - 100
        while x < W + 200:
            bw = rnd.randint(90, 190)
            bh = rnd.randint(hmin, hmax)
            _rect(ctx, x, base - bh, bw, bh + (FLOOR - base), _rgb(col))
            if layer > 0:  # pencereler
                for wy in range(int(base - bh + 20), int(base - 20), 34):
                    for wx in range(int(x + 14), int(x + bw - 20), 30):
                        r = rnd.random()
                        if r < 0.28:
                            flick = 0.5 + 0.5 * math.sin(t * 2 + wx * 0.13 + wy) if r < 0.04 else 1
                            _rect(ctx, wx, wy, 12, 16, th.ACCENT, (0.35 + 0.3 * layer / 2) * flick)
            x += bw + rnd.randint(4, 30)
    _floor(ctx, _rgb("#1A100A"), _rgb("#070504"))


def office(ctx, t):
    _rect(ctx, 0, 0, W, FLOOR, _rgb("#16100C"))
    for i in range(0, W, 120):  # duvar paneli
        _rect(ctx, i, 0, 2, FLOOR, _rgb("#1E1610"))
    # pencere ve dışarıdaki şehir
    wx, wy, ww, wh = 1180, 140, 560, 420
    _rect(ctx, wx - 16, wy - 16, ww + 32, wh + 32, _rgb("#2A1E15"))
    g = cairo.LinearGradient(0, wy, 0, wy + wh)
    g.add_color_stop_rgb(0, *_rgb("#1B0F08"))
    g.add_color_stop_rgb(1, *_rgb("#5A2A0C"))
    ctx.set_source(g)
    ctx.rectangle(wx, wy, ww, wh)
    ctx.fill()
    rnd = random.Random(5)
    x = wx
    while x < wx + ww:
        bw, bh = rnd.randint(40, 90), rnd.randint(90, 260)
        _rect(ctx, x, wy + wh - bh, bw, bh, _rgb("#120A06"))
        x += bw + 6
    _rect(ctx, wx + ww / 2 - 6, wy, 12, wh, _rgb("#2A1E15"))
    _rect(ctx, wx, wy + wh / 2 - 6, ww, 12, _rgb("#2A1E15"))
    # duvar panosu: küçük grafik
    _rect(ctx, 200, 170, 420, 280, _rgb("#221812"))
    for i, hh in enumerate((90, 140, 120, 200, 170)):
        grow = min(1, max(0, (t - 0.3 - i * 0.1) * 2))
        _rect(ctx, 240 + i * 74, 420 - hh * grow, 46, hh * grow, th.ACCENT, 0.55)
    # saksı bitkisi
    _rect(ctx, 1810, 820, 70, 140, _rgb("#3A2A1E"))
    for k in range(6):
        a = -1.9 + k * 0.35 + 0.05 * math.sin(t * 1.5 + k)
        ctx.save()
        ctx.translate(1845, 820)
        ctx.rotate(a)
        ctx.scale(1, 0.32)
        ctx.set_source_rgb(*_rgb("#4C6B2E"))
        ctx.arc(110, 0, 110, 0, math.tau)
        ctx.fill()
        ctx.restore()
    _floor(ctx, _rgb("#2A1D14"), _rgb("#0D0907"))
    _rect(ctx, 0, FLOOR, W, 6, _rgb("#3A2A1E"))


def space(ctx, t):
    _rect(ctx, 0, 0, W, H, _rgb("#04030A"))
    rnd = random.Random(9)
    for i in range(220):
        x, y = rnd.random() * W, rnd.random() * H * 0.9
        r = rnd.random() * 2.2 + 0.4
        tw = 0.5 + 0.5 * math.sin(t * (1 + rnd.random() * 3) + i)
        ctx.set_source_rgba(1, 0.95, 0.9, 0.3 + 0.6 * tw * rnd.random())
        ctx.arc(x, y, r, 0, math.tau)
        ctx.fill()
    # halkalı gezegen
    px, py = 1500, 260
    g = cairo.RadialGradient(px - 40, py - 40, 10, px, py, 150)
    g.add_color_stop_rgb(0, *th.ACCENT2)
    g.add_color_stop_rgb(1, *_rgb("#7A3208"))
    ctx.set_source(g)
    ctx.arc(px, py, 130, 0, math.tau)
    ctx.fill()
    ctx.save()
    ctx.translate(px, py)
    ctx.rotate(-0.35)
    ctx.scale(1, 0.25)
    ctx.set_source_rgba(*_rgb("#F2EBE1"), 0.55)
    ctx.set_line_width(14)
    ctx.arc(0, 0, 220, 0, math.tau)
    ctx.stroke()
    ctx.restore()
    # kayan yıldız
    st = (t * 0.5) % 4
    if st < 0.6:
        sx, sy = 200 + st * 1200, 120 + st * 300
        g = cairo.LinearGradient(sx - 160, sy - 40, sx, sy)
        g.add_color_stop_rgba(0, 1, 1, 1, 0)
        g.add_color_stop_rgba(1, 1, 1, 1, 0.9)
        ctx.set_source(g)
        ctx.set_line_width(3)
        ctx.move_to(sx - 160, sy - 40)
        ctx.line_to(sx, sy)
        ctx.stroke()
    # yüzey (ay toprağı)
    ctx.set_source_rgb(*_rgb("#1E1A18"))
    ctx.move_to(0, FLOOR - 10)
    ctx.curve_to(W * 0.3, FLOOR - 50, W * 0.7, FLOOR - 50, W, FLOOR - 10)
    ctx.line_to(W, H)
    ctx.line_to(0, H)
    ctx.close_path()
    ctx.fill()
    for cx, cy, r in ((300, 1010, 50), (1300, 990, 36), (1750, 1040, 60), (800, 1050, 28)):
        ctx.save()
        ctx.translate(cx, cy)
        ctx.scale(1, 0.3)
        ctx.set_source_rgb(*_rgb("#141110"))
        ctx.arc(0, 0, r, 0, math.tau)
        ctx.fill()
        ctx.restore()


def lab(ctx, t):
    _rect(ctx, 0, 0, W, FLOOR, _rgb("#0F0D0C"))
    for y in range(0, FLOOR, 80):  # fayans
        _rect(ctx, 0, y, W, 2, _rgb("#191512"))
    for x in range(0, W, 80):
        _rect(ctx, x, 0, 2, FLOOR, _rgb("#191512"))
    for sy in (300, 520):  # raflar ve şişeler
        _rect(ctx, 120, sy, 600, 14, _rgb("#3A2A1E"))
        _rect(ctx, 1240, sy, 560, 14, _rgb("#3A2A1E"))
        for k, bx in enumerate(list(range(150, 700, 90)) + list(range(1270, 1780, 95))):
            bh = 60 + (k * 37 % 50)
            col = [th.ACCENT, th.ACCENT2, _rgb("#7BD389"), _rgb("#4E7CFF")][k % 4]
            _rect(ctx, bx, sy - bh, 46, bh, _rgb("#2A2420"), 0.9)
            lvl = 0.5 + 0.15 * math.sin(t + k)
            _rect(ctx, bx + 4, sy - bh * lvl, 38, bh * lvl - 2, col, 0.55)
            for b in range(2):  # kabarcıklar
                ph = (t * 0.8 + k * 0.37 + b * 0.5) % 1
                ctx.set_source_rgba(1, 1, 1, 0.35 * (1 - ph))
                ctx.arc(bx + 14 + b * 16, sy - bh * lvl * ph - 6, 3, 0, math.tau)
                ctx.fill()
    _floor(ctx, _rgb("#1C1916"), _rgb("#080706"))


def nature(ctx, t):
    g = cairo.LinearGradient(0, 0, 0, FLOOR)
    g.add_color_stop_rgb(0, *_rgb("#0E0806"))
    g.add_color_stop_rgb(1, *_rgb("#4A1F08"))
    ctx.set_source(g)
    ctx.rectangle(0, 0, W, FLOOR)
    ctx.fill()
    gs = cairo.RadialGradient(1450, 560, 20, 1450, 560, 300)  # batan güneş
    gs.add_color_stop_rgba(0, *th.ACCENT2, 0.9)
    gs.add_color_stop_rgba(0.3, *th.ACCENT, 0.6)
    gs.add_color_stop_rgba(1, *th.ACCENT, 0)
    ctx.set_source(gs)
    ctx.arc(1450, 560, 300, 0, math.tau)
    ctx.fill()
    for k in range(3):  # bulutlar
        cx = (300 + k * 700 + t * 12) % (W + 400) - 200
        ctx.set_source_rgba(*_rgb("#2A1608"), 0.8)
        for dx, r in ((0, 40), (50, 55), (110, 42)):
            ctx.arc(cx + dx, 220 + k * 60, r, 0, math.tau)
            ctx.fill()
    for layer, (col, base, amp) in enumerate((("#1C0F07", 760, 80), ("#140B05", 860, 60), ("#0E0804", FLOOR, 40))):
        ctx.set_source_rgb(*_rgb(col))
        ctx.move_to(0, H)
        for x in range(0, W + 40, 40):
            ctx.line_to(x, base - amp * (0.5 + 0.5 * math.sin(x / (230 - layer * 50) + layer * 2)))
        ctx.line_to(W, H)
        ctx.close_path()
        ctx.fill()
        if layer == 1:  # çam ağaçları
            rnd = random.Random(4)
            for _ in range(14):
                tx = rnd.randint(0, W)
                th_ = rnd.randint(90, 170)
                ty = base - amp * (0.5 + 0.5 * math.sin(tx / 180 + 2)) + 10
                ctx.set_source_rgb(*_rgb("#0B0703"))
                ctx.move_to(tx, ty - th_)
                ctx.line_to(tx + th_ * 0.28, ty)
                ctx.line_to(tx - th_ * 0.28, ty)
                ctx.close_path()
                ctx.fill()
    _floor(ctx, _rgb("#120A05"), _rgb("#050302"))


BACKDROPS = {"studio": studio, "city": city, "office": office, "space": space, "lab": lab, "nature": nature}


def draw_backdrop(ctx, name, t, alpha=1.0):
    f = BACKDROPS.get(name)
    if not f or alpha <= 0:
        return
    ctx.push_group()
    f(ctx, t)
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(alpha)
    # karakterler ve yazılar öne çıksın diye hafif vinyet
    g = cairo.RadialGradient(W / 2, H / 2, 300, W / 2, H / 2, 1200)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.45 * alpha)
    ctx.set_source(g)
    ctx.paint()
