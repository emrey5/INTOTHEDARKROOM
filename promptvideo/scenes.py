"""Sahne türleri. Her çizici `draw(ctx, sc, t, dur)` imzasına sahiptir; t sahne içi saniyedir.
Her sahne iki stilde de (modern / çizgi) çalışır."""
import math

import cairo

from . import draw as D
from . import characters as C
from . import backdrops as B
from . import theme as th
from .theme import (W, H, clamp, prog, lerp, ease_out_cubic, ease_out_back, ease_out_expo,
                    ease_in_out, ease_out_elastic, fmt_num, mix)

LANG = "tr"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _col(i):
    return th.PALETTE[i % len(th.PALETTE)]


# --- Başlık ----------------------------------------------------------------

def draw_title(ctx, sc, t, dur):
    title = sc.get("title", "")
    sub = sc.get("subtitle", "")
    cx, cy = W / 2, H / 2 - 30

    if th.SKETCH:
        # elle çizilmiş patlama/güneş ışınları ve daireler
        for i in range(14):
            p = ease_out_back(prog(t, 0.1 + i * 0.02, 0.5))
            a = i * math.tau / 14 + 0.05 * math.sin(t * 2)
            r1, r2 = 430, 430 + 90 * p
            D.rough_stroke_poly(ctx, [(cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 0.62),
                                      (cx + math.cos(a) * r2, cy + math.sin(a) * r2 * 0.62)],
                                _col(i), 8, passes=1, key=i, alpha=clamp(p))
        q = prog(t, 0.0, 0.8)
        if q >= 1:
            D.rough_ellipse(ctx, cx, cy, 400, 250, th.INK, 5, fill=th.HILITE, key=1)
        else:
            D.rough_ellipse(ctx, cx, cy, 400, 250, th.INK, 5, key=1, frac=ease_out_cubic(q))
    else:
        for i, (r, sp, col) in enumerate(((330, 0.25, th.ACCENT), (400, -0.18, th.ACCENT2), (470, 0.12, th.ACCENT))):
            p = ease_out_cubic(prog(t, 0.1 * i, 1.2))
            ctx.set_line_width(2)
            ctx.set_source_rgba(*col, 0.35 * p)
            a0 = t * sp + i
            ctx.arc(cx, cy, r * (0.8 + 0.2 * p), a0, a0 + math.pi * 1.2 * p)
            ctx.stroke()
        D.glow_circle(ctx, cx, cy, 520, th.ACCENT, 0.12 * ease_out_cubic(prog(t, 0, 1)))

    size = 112 if th.SKETCH else 104
    maxw = 700 if th.SKETCH else W - 360
    lines = D.wrap(title, size, maxw, "display")
    while (len(lines) > 2 or any(D.text_width(l, size, "display") > W - 300 for l in lines)) and size > 56:
        size -= 6
        lines = D.wrap(title, size, maxw if size > 80 else W - 360, "display")
    lh = size * 1.08
    y0 = cy - (len(lines) - 1) * lh / 2 + size * 0.33
    grad = None if th.SKETCH else D.accent_gradient(cx - 600, 0, cx + 600, 0, th.TEXT, mix(th.TEXT, th.ACCENT2, 0.55))
    start = 0.25
    for li, line in enumerate(lines):
        D.anim_text(ctx, line, cx, y0 + li * lh, size, t, start, "display", align="center",
                    stagger=0.035, dur=0.55, source=grad, color=th.INK if th.SKETCH else None,
                    outline=(1, 1, 1) if th.SKETCH else None, shadow=(6, 6) if th.SKETCH else None)
        start += len(line) * 0.035
    ybot = y0 + (len(lines) - 1) * lh
    if not th.SKETCH:
        lw = 240 * ease_out_expo(prog(t, start, 0.9))
        ctx.set_source(D.accent_gradient(cx - 120, 0, cx + 120, 0))
        D.round_rect(ctx, cx - lw / 2, ybot + 50, lw, 8, 4)
        ctx.fill()
    if sub:
        p = ease_out_cubic(prog(t, start + 0.2, 0.7))
        ss = 46 if th.SKETCH else 38
        kind = "hand" if th.SKETCH else "body"
        for i, s in enumerate(D.wrap(sub, ss, W - 500, kind)[:2]):
            yy = (cy + 365 if th.SKETCH else ybot + 130) + i * ss * 1.25 + (1 - p) * 20
            if th.SKETCH:
                D.draw_text(ctx, s, cx, yy, ss, th.INK, alpha=p, kind=kind, align="center")
            else:
                D.draw_text(ctx, s, cx, yy, ss, th.MUTED, alpha=p, kind=kind, align="center")


# --- Madde listesi ---------------------------------------------------------

def draw_bullets(ctx, sc, t, dur):
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    items = sc.get("items", [])[:6]
    y = 320
    gap = min(1.0, (dur - 2.0) / max(1, len(items)))
    fs = 44 if th.SKETCH else 40
    for i, it in enumerate(items):
        st = 0.7 + i * gap
        p = ease_out_cubic(prog(t, st, 0.6))
        if p <= 0:
            break
        lines = D.wrap(it, fs, W - 440, "body")[:2]
        x = 160
        if th.SKETCH:
            # elle çizilmiş daire içinde numara + çizilen tik
            e = ease_out_back(prog(t, st, 0.5), 2.5)
            ctx.save()
            ctx.translate(x + 30, y + 22)
            ctx.scale(max(0.01, e), max(0.01, e))
            D.rough_ellipse(ctx, 0, 0, 32, 30, th.INK, 4, fill=_col(i), key=i)
            D.draw_text(ctx, str(i + 1), 0, 14, 38, th.INK, kind="display", align="center")
            ctx.restore()
        else:
            ctx.set_source(D.accent_gradient(x, y, x + 56, y + 56, alpha=p))
            D.round_rect(ctx, x + (1 - p) * 60, y - 6, 56, 56, 16)
            ctx.fill()
            D.draw_text(ctx, str(i + 1), x + 28 + (1 - p) * 60, y + 34, 28, alpha=p, kind="bold", align="center")
        for j, ln in enumerate(lines):
            D.anim_text(ctx, ln, x + 100, y + 36 + j * fs * 1.3, fs, t, st + 0.1 + j * 0.3, "body",
                        color=th.INK if th.SKETCH else th.TEXT, stagger=0.012, dur=0.35,
                        mode="rise")
        y += 74 + fs * 1.3 * len(lines)
    D.footer_source(ctx, sc.get("source"), t)


# --- Büyük sayı ------------------------------------------------------------

def draw_stat(ctx, sc, t, dur):
    val = _num(sc.get("value"))
    p = ease_out_expo(prog(t, 0.3, min(2.2, dur * 0.5)))
    cur = val * p
    dec = sc.get("decimals")
    s = sc.get("prefix", "") + fmt_num(cur, LANG, dec if dec is not None else
                                         (0 if float(val).is_integer() and abs(val) < 1e6 else None)) + sc.get("suffix", "")
    cx, cy = W / 2, H / 2 + 50
    if sc.get("kicker"):
        k = sc["kicker"] if th.SKETCH else sc["kicker"].upper()
        ks, kind = (48, "hand") if th.SKETCH else (28, "bold")
        kw = D.text_width(k, ks, kind)
        D.marker_highlight(ctx, cx - kw / 2 - 8, 300 - ks * 0.8, kw + 16, ks, prog(t, 0.1, 0.5),
                           None if th.SKETCH else th.ACCENT)
        D.draw_text(ctx, k, cx, 300, ks, th.INK if th.SKETCH else th.TEXT, alpha=clamp(t * 2), kind=kind, align="center")
    size = D.fit_size(s, 230, W - 260, "display")
    e = ease_out_elastic(prog(t, 0.1, 1.2)) if th.SKETCH else ease_out_back(prog(t, 0.1, 0.8))
    ctx.save()
    ctx.translate(cx, cy)
    sc_ = 0.6 + 0.4 * e if th.SKETCH else 0.85 + 0.15 * e
    ctx.scale(sc_, sc_)
    if th.SKETCH:
        ctx.rotate(-0.03 + 0.01 * math.sin(t * 3))
        D.draw_text(ctx, s, 0, 0, size, _col(0), alpha=clamp(t * 4), kind="display", align="center",
                    outline=th.INK, shadow=(10, 10))
    else:
        D.glow_circle(ctx, 0, -60, 600, th.ACCENT2, 0.10 * p)
        D.draw_text(ctx, s, 0, 0, size, kind="display", align="center", alpha=clamp(t * 3),
                    source=D.accent_gradient(-500, 0, 500, 0, th.TEXT, th.ACCENT2))
    ctx.restore()
    for i, ln in enumerate(D.wrap(sc.get("label", ""), 48, W - 400, "body")[:2]):
        D.anim_text(ctx, ln, cx, cy + 120 + i * 62, 48, t, 0.9 + i * 0.3, "body", align="center",
                    color=th.INK if th.SKETCH else th.MUTED, stagger=0.015, dur=0.4, mode="rise")
    if th.SKETCH:  # sayının altına çizilen dalga
        q = prog(t, 1.0, 0.7)
        ctx.save()
        ln = 520
        ctx.move_to(cx - ln / 2, cy + 40)
        for i in range(6):
            x0 = cx - ln / 2 + i * ln / 6
            ctx.curve_to(x0 + ln / 18, cy + 28, x0 + ln / 9, cy + 52, x0 + ln / 6, cy + 40)
        D.draw_on(ctx, ln * 1.3, ease_out_cubic(q))
        ctx.set_source_rgb(*_col(1))
        ctx.set_line_width(8)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()
        ctx.restore()
    D.footer_source(ctx, sc.get("source"), t)


# --- Yatay çubuk grafik -----------------------------------------------------

def draw_bar(ctx, sc, t, dur):
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    data = [d for d in sc.get("data", []) if d.get("value") is not None][:10]
    if sc.get("sort", True):
        data.sort(key=lambda d: -_num(d["value"]))
    if not data:
        return
    unit = sc.get("unit", "")
    vmax = max(_num(d["value"]) for d in data) or 1
    top, bottom = 290, H - 140
    n = len(data)
    slot = (bottom - top) / n
    bh = min(66, slot * 0.66)
    fs = 34 if th.SKETCH else 30
    label_w = min(440, max(D.text_width(str(d["label"]), fs, "bold") for d in data) + 30)
    x0 = 140 + label_w
    max_w = W - x0 - 340
    hi = sc.get("highlight")
    for i, d in enumerate(data):
        v = _num(d["value"])
        st = 0.5 + i * 0.12
        p = ease_out_back(prog(t, st, 1.1), 1.2) if th.SKETCH else ease_out_cubic(prog(t, st, 1.3))
        y = top + i * slot + (slot - bh) / 2
        a = clamp(prog(t, st - 0.1, 0.4))
        is_hi = (hi is not None and str(d["label"]) == str(hi)) or (hi is None and i == 0)
        D.draw_text(ctx, str(d["label"]), x0 - 30, y + bh / 2 + fs * 0.36, fs,
                    th.INK if th.SKETCH else th.TEXT, alpha=a, kind="bold", align="right")
        w = max(bh * 0.5, max_w * (v / vmax) * p)
        if th.SKETCH:
            col = _col(0) if is_hi else _col(i + 1 if i + 1 < len(th.PALETTE) else i)
            D.rough_rect(ctx, x0, y, w, bh, fill=col, width=4, key=i, shadow=6, alpha=a, hatch=not is_hi)
        else:
            ctx.set_source_rgba(*th.GRID, 0.35 * a)
            D.round_rect(ctx, x0, y, max_w, bh, bh / 2)
            ctx.fill()
            col = _col(i) if sc.get("multicolor") else th.ACCENT
            c2 = th.ACCENT2 if is_hi else mix(col, th.ACCENT2, 0.4)
            ctx.set_source(D.accent_gradient(x0, 0, x0 + w, 0, col, c2, alpha=a))
            D.round_rect(ctx, x0, y, w, bh, bh / 2)
            ctx.fill()
            if is_hi:
                D.glow_circle(ctx, x0 + w - bh / 2, y + bh / 2, bh * 1.6, th.ACCENT2, 0.35 * p)
        lab = fmt_num(v * clamp(p), LANG) + (" " + unit if unit else "")
        D.draw_text(ctx, lab, x0 + w + 26, y + bh / 2 + fs * 0.36, fs,
                    th.INK if th.SKETCH else th.TEXT, alpha=a, kind="display" if is_hi else "bold")
    if th.SKETCH:  # öne çıkan çubuğa el yazısıyla ok ve not
        q = prog(t, 0.5 + n * 0.12 + 0.6, 0.6)
        if q > 0:
            v0 = _num(data[0]["value"])
            bx = x0 + max_w * v0 / vmax
            by = top + (slot - bh) / 2
            ax, ay = min(bx + 160, W - 120), by + bh + 90
            ctx.save()
            ctx.move_to(ax, ay)
            ctx.curve_to(ax + 10, ay - 40, ax - 20, ay - 70, ax - 60, ay - 80)
            D.draw_on(ctx, 160, ease_out_cubic(q))
            ctx.set_source_rgb(*th.INK)
            ctx.set_line_width(5)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.stroke()
            ctx.restore()
            if q >= 1:
                D.rough_stroke_poly(ctx, [(ax - 40, ay - 96), (ax - 62, ay - 80), (ax - 36, ay - 66)], th.INK, 5, passes=1, key=3)
            D.draw_text(ctx, sc.get("note") or "en yüksek!", ax - 40, ay + 50, 44, th.ACCENT, alpha=clamp(q * 2),
                        kind="hand")
    D.footer_source(ctx, sc.get("source"), t)


# --- Çizgi grafik ----------------------------------------------------------

def _nice_ticks(lo, hi, n=5):
    span = hi - lo or abs(hi) or 1
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=mag * 10)
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v <= hi + step * 0.01:
        ticks.append(v)
        v += step
    return ticks


def draw_line(ctx, sc, t, dur):
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    series = sc.get("series") or []
    if not series and sc.get("data"):
        series = [{"name": sc.get("unit", ""), "data": sc["data"]}]
    series = [s for s in series if s.get("data")][:4]
    if not series:
        return
    xs = [str(p["x"]) for p in series[0]["data"]]
    allv = [_num(p["y"]) for s in series for p in s["data"]]
    lo, hi = min(allv), max(allv)
    if 0 < lo < hi * 0.6:
        lo = 0
    ticks = _nice_ticks(lo, hi)
    lo, hi = ticks[0], ticks[-1]
    L, R, T, B = 270, W - 220, 300, H - 170
    unit = sc.get("unit", "")
    sk = th.SKETCH
    axis_col = th.INK if sk else th.MUTED
    fs = 30 if sk else 24
    kind = "hand" if sk else "body"

    def px(i, n):
        return L + (R - L) * (i / max(1, n - 1))

    def py(v):
        return B - (B - T) * ((v - lo) / ((hi - lo) or 1))

    ga = clamp(prog(t, 0.3, 0.6))
    for k, tv in enumerate(ticks):
        y = py(tv)
        if sk:
            if k == 0:
                continue
            ctx.set_dash([10, 12])
            D.rough_line_path(ctx, L, y, R, y, 1.5, key=k)
            ctx.set_source_rgba(*th.GRID, ga)
            ctx.set_line_width(2)
            ctx.stroke()
            ctx.set_dash([])
        else:
            ctx.set_source_rgba(*th.GRID, 0.6 * ga)
            ctx.set_line_width(1)
            ctx.move_to(L, y)
            ctx.line_to(R, y)
            ctx.stroke()
        D.draw_text(ctx, fmt_num(tv, LANG), L - 24, y + fs * 0.35, fs, axis_col, alpha=ga, kind=kind, align="right")
    if sk:  # elle çizilmiş eksenler (oklu)
        q = ease_out_cubic(prog(t, 0.2, 0.6))
        D.rough_stroke_poly(ctx, [(L, T - 30), (L, T - 30 + (B - T + 30) * q)], th.INK, 5, passes=2, key=91)
        D.rough_stroke_poly(ctx, [(L, B), (L + (R - L + 40) * q, B)], th.INK, 5, passes=2, key=92)
    n = len(xs)
    every = max(1, math.ceil(n / 9))
    for i, x in enumerate(xs):
        if i % every == 0 or i == n - 1:
            D.draw_text(ctx, x, px(i, n), B + 48, fs, axis_col, alpha=ga, kind=kind, align="center")

    draw_p = ease_in_out(prog(t, 0.7, max(1.5, dur - 2.4)))
    for si, s in enumerate(series):
        pts = [(px(i, len(s["data"])), py(_num(p["y"]))) for i, p in enumerate(s["data"])]
        col = _col(si) if len(series) > 1 or sk else th.ACCENT2
        f = draw_p * (len(pts) - 1)
        k = int(f)
        frac = f - k
        vis = pts[:k + 1]
        if k + 1 < len(pts):
            (x1, y1), (x2, y2) = pts[k], pts[k + 1]
            vis.append((lerp(x1, x2, frac), lerp(y1, y2, frac)))
        if len(vis) < 2:
            continue
        hx, hy = vis[-1]
        if len(series) == 1:  # alan dolgusu
            ctx.move_to(vis[0][0], B)
            for x, y in vis:
                ctx.line_to(x, y)
            ctx.line_to(hx, B)
            ctx.close_path()
            if sk:
                ctx.save()
                ctx.clip()
                ctx.set_source_rgba(*col, 0.35)
                ctx.set_line_width(4)
                for hxx in range(int(L - (B - T)), int(R), 22):  # tarama dolgu
                    ctx.move_to(hxx, B)
                    ctx.line_to(hxx + (B - T), T)
                ctx.stroke()
                ctx.restore()
            else:
                g = cairo.LinearGradient(0, T, 0, B)
                g.add_color_stop_rgba(0, *col, 0.35)
                g.add_color_stop_rgba(1, *col, 0.0)
                ctx.set_source(g)
                ctx.fill()
        if sk:
            D.rough_stroke_poly(ctx, vis, col, 9, passes=2, key=si * 100)
            for x, y in pts[:k + 1]:
                D.rough_ellipse(ctx, x, y, 9, 9, th.INK, 3.5, fill=(1, 1, 1), key=int(x))
        else:
            ctx.move_to(*vis[0])
            for x, y in vis[1:]:
                ctx.line_to(x, y)
            ctx.set_line_width(6)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.set_source(D.accent_gradient(L, 0, R, 0, th.ACCENT, col) if len(series) == 1 else cairo.SolidPattern(*col))
            ctx.stroke()
            D.glow_circle(ctx, hx, hy, 46, col, 0.5)
            ctx.set_source_rgb(*th.TEXT)
            ctx.arc(hx, hy, 9, 0, math.tau)
            ctx.fill()
        vals = [_num(p["y"]) for p in s["data"]]
        cv = lerp(vals[min(k, len(vals) - 1)], vals[min(k + 1, len(vals) - 1)], frac)
        lab = fmt_num(cv, LANG) + (" " + unit if unit and len(series) == 1 else "")
        lfs = 32 if sk else 28
        lw = D.text_width(lab, lfs, "display" if sk else "bold") + 34
        bx = min(hx + 20, R - lw + 80)
        by = hy - 78
        if sk:
            D.rough_rect(ctx, bx, by, lw, 54, fill=th.HILITE, width=3.5, key=si + 50, shadow=5)
            D.draw_text(ctx, lab, bx + 17, by + 39, lfs, th.INK, kind="display")
        else:
            ctx.set_source_rgba(*mix(th.BG, col, 0.25), 0.92)
            D.round_rect(ctx, bx, by, lw, 50, 14)
            ctx.fill()
            D.draw_text(ctx, lab, bx + 17, by + 35, lfs, kind="bold")
    if len(series) > 1:  # lejant
        x = L
        for si, s in enumerate(series):
            ctx.set_source_rgba(*_col(si), ga)
            D.round_rect(ctx, x, T - 56, 28, 14, 7)
            ctx.fill()
            x += 40 + D.draw_text(ctx, s.get("name", ""), x + 40, T - 40, 28, th.INK if sk else th.TEXT,
                                  alpha=ga, kind="bold") + 40
    D.footer_source(ctx, sc.get("source"), t)


# --- Halka (pasta) grafik --------------------------------------------------

def draw_pie(ctx, sc, t, dur):
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    data = [d for d in sc.get("data", []) if _num(d.get("value")) > 0][:8]
    if not data:
        return
    sk = th.SKETCH
    total = sum(_num(d["value"]) for d in data)
    cx, cy, r = 620, 650, 300
    p = ease_in_out(prog(t, 0.5, 1.8))
    a = -math.pi / 2
    for i, d in enumerate(data):
        frac = _num(d["value"]) / total
        sweep = math.tau * frac * p
        col = _col(i)
        if sk:  # pasta dilimleri: düz dolgu + mürekkep kontur + ayrılma
            mid = a + sweep / 2
            off = 14 * ease_out_back(prog(t, 2.2 + i * 0.1, 0.5))
            ox, oy = math.cos(mid) * off, math.sin(mid) * off
            ctx.move_to(cx + ox + 8, cy + oy + 8)
            ctx.arc(cx + ox + 8, cy + oy + 8, r, a, a + sweep)
            ctx.close_path()
            ctx.set_source_rgb(*th.INK)
            ctx.fill()
            ctx.move_to(cx + ox, cy + oy)
            ctx.arc(cx + ox, cy + oy, r, a, a + sweep)
            ctx.close_path()
            ctx.set_source_rgb(*col)
            ctx.fill_preserve()
            ctx.set_source_rgb(*th.INK)
            ctx.set_line_width(5)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.stroke()
        else:
            ctx.set_line_width(110)
            ctx.set_source_rgb(*col)
            ctx.arc(cx, cy, r - 55, a + 0.012, a + max(0.0, sweep - 0.012))
            ctx.stroke()
        a += sweep
    top = max(data, key=lambda d: _num(d["value"]))
    pct_top = _num(top["value"]) / total * 100 * p
    if sk:
        D.rough_ellipse(ctx, cx, cy, 120, 120, th.INK, 5, fill=(1, 1, 1), key=77)
        D.draw_text(ctx, f"%{pct_top:.0f}", cx, cy + 22, 70, th.INK, kind="display", align="center")
    else:
        D.draw_text(ctx, f"%{pct_top:.0f}", cx, cy + 10, 76, kind="display", align="center",
                    source=D.accent_gradient(cx - 100, 0, cx + 100, 0, th.TEXT, th.ACCENT2))
        D.draw_text(ctx, str(top["label"]), cx, cy + 62, 28, th.MUTED, align="center")
    lx, ly = 1080, 360
    for i, d in enumerate(data):
        q = ease_out_cubic(prog(t, 0.9 + i * 0.15, 0.6))
        col = _col(i)
        y = ly + i * 84
        if sk:
            D.rough_rect(ctx, lx + (1 - q) * 40, y - 30, 38, 38, fill=col, width=3, key=i + 20, shadow=4, alpha=q)
        else:
            ctx.set_source_rgba(*col, q)
            D.round_rect(ctx, lx + (1 - q) * 40, y - 26, 34, 34, 10)
            ctx.fill()
        D.draw_text(ctx, str(d["label"]), lx + 60 + (1 - q) * 40, y, 36, th.INK if sk else th.TEXT, alpha=q)
        pct = f"%{_num(d['value']) / total * 100:.1f}".replace(".", ",")
        D.draw_text(ctx, pct, W - 160, y, 36, th.ACCENT if sk else th.ACCENT2, alpha=q, kind="display", align="right")
    D.footer_source(ctx, sc.get("source"), t)


# --- Tablo -----------------------------------------------------------------

def draw_table(ctx, sc, t, dur):
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    cols = [str(c) for c in sc.get("columns", [])]
    rows = [[("" if c is None else str(c)) for c in r] for r in sc.get("rows", [])][:9]
    if not cols:
        return
    sk = th.SKETCH
    fs = 36 if len(cols) <= 4 else 30
    widths = []
    for j, c in enumerate(cols):
        w = D.text_width(c, fs, "bold")
        for r in rows:
            if j < len(r):
                w = max(w, D.text_width(r[j], fs, "bold"))
        widths.append(w + 64)
    total = sum(widths)
    target = min(W - 280, max(total, 1200))
    widths = [w * target / total for w in widths]
    total = target
    x0 = (W - total) / 2
    y = 280
    rh = min(84, (H - 150 - y) / (len(rows) + 1))
    ha = ease_out_cubic(prog(t, 0.3, 0.6))
    if sk:
        D.rough_rect(ctx, x0, y, total, rh, fill=th.HILITE, width=4, key=1, shadow=6, alpha=ha)
    else:
        ctx.set_source(D.accent_gradient(x0, 0, x0 + total, 0, alpha=0.9 * ha))
        D.round_rect(ctx, x0, y, total, rh, 18)
        ctx.fill()

    def is_num(s):
        return s.replace(".", "").replace(",", "").replace("%", "").replace("-", "").replace("+", "").replace(" ", "").isdigit()

    x = x0
    for j, c in enumerate(cols):
        D.draw_text(ctx, c, x + 32, y + rh / 2 + fs * 0.36, fs, th.INK if sk else th.TEXT, alpha=ha, kind="display" if sk else "bold")
        x += widths[j]
    for i, r in enumerate(rows):
        st = 0.7 + i * 0.14
        p = ease_out_back(prog(t, st, 0.6), 1.3) if sk else ease_out_cubic(prog(t, st, 0.6))
        yy = y + (i + 1) * rh
        off = (1 - p) * 80
        a = clamp(prog(t, st, 0.3))
        if sk:
            D.rough_stroke_poly(ctx, [(x0, yy + rh), (x0 + (total) * clamp(p), yy + rh)], th.GRID, 3, passes=1, key=i + 30)
        elif i % 2 == 0:
            ctx.set_source_rgba(*th.GLASS, 0.05 * a)
            D.round_rect(ctx, x0 + off, yy + 4, total, rh - 8, 14)
            ctx.fill()
        x = x0 + off
        for j in range(len(cols)):
            s = r[j] if j < len(r) else ""
            last = j == len(cols) - 1
            col = (th.ACCENT if sk else th.ACCENT2) if last else (th.INK if sk else th.TEXT)
            if is_num(s) and j > 0:
                D.draw_text(ctx, s, x + widths[j] - 32, yy + rh / 2 + fs * 0.36, fs, col, alpha=a, align="right",
                            kind="display" if last else "body")
            else:
                D.draw_text(ctx, s, x + 32, yy + rh / 2 + fs * 0.36, fs, col, alpha=a, kind="bold" if j == 0 else "body")
            x += widths[j]
    D.footer_source(ctx, sc.get("source"), t)


# --- Görsel ve video -------------------------------------------------------

_img_cache = {}


def load_image(path):
    if path in _img_cache:
        return _img_cache[path]
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((2600, 2600))
    im = im.convert("RGBA")
    data = bytearray(im.tobytes("raw", "BGRA"))
    surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, im.width, im.height, im.width * 4)
    _img_cache[path] = (surf, data)
    return surf, data


def _paint_cover(ctx, surf, x, y, w, h, zoom=1.0, pan=0.0):
    iw, ih = surf.get_width(), surf.get_height()
    s = max(w / iw, h / ih) * zoom
    ctx.save()
    ctx.rectangle(x, y, w, h)
    ctx.clip()
    ctx.translate(x + (w - iw * s) / 2 + pan, y + (h - ih * s) / 2)
    ctx.scale(s, s)
    ctx.set_source_surface(surf, 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint()
    ctx.restore()


def media_scene(ctx, sc, t, dur, surf):
    """Görsel ve video sahneleri için ortak düzen. surf: o anki kare (ya da None)."""
    p = t / max(dur, 0.01)
    zoom = lerp(1.0, 1.1, ease_in_out(p))
    pan = lerp(-30, 30, p) * (1 if sc.get("pan", 1) > 0 else -1)
    if th.SKETCH:
        # bantla yapıştırılmış, hafif eğik fotoğraf kartı
        e = ease_out_back(prog(t, 0.0, 0.8), 1.4)
        fw, fh = 1280, 720
        ctx.save()
        ctx.translate(W / 2, H / 2 - 40 + (1 - e) * 200)
        ctx.rotate(lerp(-0.12, -0.025, e) + 0.004 * math.sin(t * 1.3))
        D.rough_rect(ctx, -fw / 2 - 22, -fh / 2 - 22, fw + 44, fh + 44, fill=(1, 1, 1), width=4, key=5, shadow=12)
        if surf:
            _paint_cover(ctx, surf, -fw / 2, -fh / 2, fw, fh, zoom, pan * 0.5)
        D.rough_stroke_poly(ctx, [(-fw / 2, -fh / 2), (fw / 2, -fh / 2), (fw / 2, fh / 2), (-fw / 2, fh / 2)],
                            th.INK, 3, closed=True, passes=1, key=6)
        for tx, ty, rot in ((-fw / 2 + 40, -fh / 2 - 10, -0.5), (fw / 2 - 40, -fh / 2 - 10, 0.5)):
            ctx.save()
            ctx.translate(tx, ty)
            ctx.rotate(rot)
            ctx.set_source_rgba(*th.HILITE, 0.8)
            ctx.rectangle(-70, -20, 140, 40)
            ctx.fill()
            ctx.restore()
        ctx.restore()
        cap = sc.get("caption") or sc.get("title", "")
        if cap:
            cs = D.fit_size(cap, 60, W - 300, "display")
            D.anim_text(ctx, cap, W / 2, H - 70, cs, t, 0.5, "display", align="center", stagger=0.02,
                        color=th.INK, outline=(1, 1, 1), shadow=(4, 4))
        if sc.get("credit"):
            D.draw_text(ctx, sc["credit"], W - 60, 60, 28, th.MUTED, align="right", kind="hand", alpha=0.9)
        return
    if surf:
        ctx.save()
        ctx.set_source_rgba(0, 0, 0, 1)
        _paint_cover(ctx, surf, 0, 0, W, H, zoom, pan)
        ctx.restore()
    g = cairo.LinearGradient(0, H * 0.45, 0, H)
    g.add_color_stop_rgba(0, *th.BG, 0)
    g.add_color_stop_rgba(1, *th.BG, 0.92)
    ctx.set_source(g)
    ctx.paint()
    lower_third(ctx, sc.get("caption") or sc.get("title", ""), sc.get("kicker"), t)
    if sc.get("credit"):
        D.draw_text(ctx, sc["credit"], W - 60, H - 40, 18, mix(th.TEXT, th.BG, 0.4), align="right", alpha=0.8)


def draw_image(ctx, sc, t, dur):
    surf = load_image(sc["image_path"])[0] if sc.get("image_path") else None
    media_scene(ctx, sc, t, dur, surf)


def lower_third(ctx, text, kicker, t):
    if not text:
        return
    p = ease_out_cubic(prog(t, 0.3, 0.7))
    lines = D.wrap(text, 54, W - 400, "display")[:2]
    y = H - 140 - (len(lines) - 1) * 64
    ctx.set_source(D.accent_gradient(140, 0, 150, 0))
    D.round_rect(ctx, 140, y - 60, 8, (60 + 64 * len(lines)) * p, 4)
    ctx.fill()
    if kicker:
        D.draw_text(ctx, kicker.upper(), 176, y - 30, 24, th.ACCENT2, alpha=p, kind="bold")
    for i, ln in enumerate(lines):
        D.anim_text(ctx, ln, 176, y + 30 + i * 64, 54, t, 0.4 + i * 0.2, "display", stagger=0.015, dur=0.45)


# --- Kapanış ---------------------------------------------------------------

def draw_outro(ctx, sc, t, dur):
    cx = W / 2
    sk = th.SKETCH
    title = sc.get("title", "Teşekkürler")
    size = D.fit_size(title, 92, W - 300, "display")
    D.anim_text(ctx, title, cx, 390, size, t, 0.1, "display", align="center", stagger=0.03,
                color=th.INK if sk else None, outline=(1, 1, 1) if sk else None, shadow=(6, 6) if sk else None,
                source=None if sk else D.accent_gradient(cx - 500, 0, cx + 500, 0, th.TEXT, th.ACCENT2))
    srcs = [s for s in sc.get("sources", []) if s][:6]
    if srcs:
        q = ease_out_cubic(prog(t, 0.6, 0.6))
        if sk:
            kw = D.text_width("Kaynaklar", 46, "hand")
            D.marker_highlight(ctx, cx - kw / 2 - 10, 470, kw + 20, 46, prog(t, 0.6, 0.5))
            D.draw_text(ctx, "Kaynaklar", cx, 507, 46, th.INK, alpha=q, kind="hand", align="center")
        else:
            D.draw_text(ctx, "KAYNAKLAR", cx, 500, 26, th.ACCENT2, alpha=q, kind="bold", align="center")
        for i, s in enumerate(srcs):
            qi = ease_out_cubic(prog(t, 0.8 + i * 0.12, 0.5))
            s = s if len(s) < 90 else s[:87] + "…"
            D.draw_text(ctx, s, cx, 575 + i * 52 + (1 - qi) * 16, 30, th.MUTED, alpha=qi, align="center")


# --- Karakterli sahneler ----------------------------------------------------

def _say_lines(sc):
    say = sc.get("say") or []
    if isinstance(say, str):
        say = [{"who": 0, "text": say}]
    return [x if isinstance(x, dict) else {"who": 0, "text": str(x)} for x in say if x]


def _chars(sc, n=2):
    cs = sc.get("characters") or [{}]
    return [c if isinstance(c, dict) else {} for c in cs[:n]]


def draw_character_scene(ctx, sc, t, dur):
    """Bir ya da iki karakter konuşur; repliği konuşma balonunda görünür."""
    B.draw_backdrop(ctx, sc.get("backdrop", "studio"), t)
    chars = _chars(sc)
    lines = _say_lines(sc)
    n = len(lines)
    times = sc.get("_line_times")
    if times and len(times) == n:  # seslendirme varsa balon konuşmayla eşzamanlı değişir
        cur = max([k for k, (a, _) in enumerate(times) if t >= a - 0.05] or [0])
        line_start, line_end = times[cur]
    else:
        span = max(0.5, dur - 1.0)
        cur = min(n - 1, int(clamp((t - 0.4) / span) * n)) if n else -1
        line_start = 0.4 + cur * span / max(1, n)
        line_end = line_start + span / max(1, n) - 0.2
    two = len(chars) > 1
    xs = (430, 1490) if two else (470,)
    sc_ = 1.0 if two else 1.12
    for i, c in enumerate(chars):
        speaking = (n and lines[cur].get("who", 0) == i) or (not n and i == 0)
        pose = c.get("pose") or ("talk" if speaking else "idle")
        C.draw_character(ctx, xs[i], 1015, t, sc_, look=c.get("look", i * 2), pose=pose, prev_pose="idle",
                         pose_t=prog(t, 0.35, 0.5), emotion=c.get("emotion", "happy"),
                         talking=bool(speaking and line_start <= t <= line_end + 0.1 if n else t < dur - 0.5),
                         facing=-1 if i == 1 else 1, seed=i * 3 + 1,
                         enter=prog(t, 0.05 + 0.15 * i, 0.5))
    if sc.get("kicker") or sc.get("title"):
        x0 = 640 if two else 860
        k = (sc.get("kicker") or "").upper()
        if k:
            D.draw_text(ctx, k, x0, 130, 26, th.ACCENT, alpha=clamp(t * 3), kind="bold")
        if sc.get("title"):
            D.anim_text(ctx, sc["title"], x0, 195, 56, t, 0.1, "display", stagger=0.02, dur=0.45)
    if n:
        who = lines[cur].get("who", 0) if two else 0
        head_x, mouth_y = xs[min(who, len(xs) - 1)], 1015 - 430 * sc_
        if two:
            bx, by, bw = 560, 250, 800
        else:
            bx, by, bw = 860, 260, 900
        C.bubble(ctx, lines[cur]["text"], bx, by, bw, t, line_start,
                 tail_x=head_x + (165 if who == 0 else -165) * sc_, tail_y=mouth_y, size=44)
    D.footer_source(ctx, sc.get("source"), t)


def draw_versus(ctx, sc, t, dur):
    """İki taraf karşı karşıya: sayılar sayarak büyür, kazanan sevinir."""
    B.draw_backdrop(ctx, sc.get("backdrop", "studio"), t)
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    left, right = sc.get("left") or {}, sc.get("right") or {}
    lv, rv = _num(left.get("value")), _num(right.get("value"))
    hib = sc.get("higher_is_better", True)
    reveal = 1.8
    win = None if lv == rv else (0 if (lv > rv) == bool(hib) else 1)
    unit = sc.get("unit", "")
    for i, (side, v, x) in enumerate(((left, lv, 520), (right, rv, 1400))):
        done = t > reveal
        if done and win is not None:
            pose, emo = ("cheer", "happy") if i == win else ("shrug", "sad")
        else:
            pose, emo = "idle", "neutral"
        C.draw_character(ctx, x, 1020, t, 0.9, look=side.get("look", i * 3), pose=pose, prev_pose="idle",
                         pose_t=prog(t, reveal, 0.4), emotion=emo, facing=1 if i == 0 else -1, seed=i * 5 + 2,
                         enter=prog(t, 0.2 + i * 0.15, 0.5))
        p = ease_out_expo(prog(t, 0.6, 1.2))
        num = (sc.get("prefix", "") + fmt_num(v * p, LANG) + (f" {unit}" if unit and unit not in ("$",) else "")
               if unit != "$" else "$" + fmt_num(v * p, LANG))
        size = D.fit_size(num, 92, 700, "display")
        col = th.ACCENT if (done and i == win) else th.TEXT
        D.draw_text(ctx, num, x, 380, size, col, alpha=clamp((t - 0.5) * 3), kind="display", align="center")
        D.draw_text(ctx, str(side.get("label", "")), x, 432, 38, th.MUTED, alpha=clamp((t - 0.6) * 3),
                    kind="bold", align="center")
    q = ease_out_back(prog(t, 0.5, 0.5), 2.2)
    if q > 0:
        ctx.save()
        ctx.translate(W / 2, 700)
        ctx.scale(q, q)
        ctx.set_source_rgb(*th.ACCENT)
        ctx.arc(0, 0, 70, 0, math.tau)
        ctx.fill()
        D.draw_text(ctx, "VS", 0, 20, 58, (0.05, 0.05, 0.05), kind="display", align="center")
        ctx.restore()
    D.footer_source(ctx, sc.get("source"), t)


def draw_people(ctx, sc, t, dur):
    """Piktogram: 100 (ya da 10) kişiden kaçının bu gruba girdiğini gösterir."""
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    total = _num(sc.get("total")) or 100
    share = clamp(_num(sc.get("value")) / total)
    n = 10 if sc.get("icons") == 10 else 100
    k = round(share * n)
    cols = 10
    rows = n // cols
    ih = 64 if n == 100 else 190
    gx, gy = (88, 70) if n == 100 else (88, 0)
    x0, y0 = 960, 340 + ih if n == 100 else 760
    if n == 10:
        gx, x0 = 84, 960
    for j in range(n):
        r, c = divmod(j, cols)
        x = x0 + c * gx + 40
        y = y0 + (rows - 1 - r) * gy if n == 100 else y0
        on = j < k
        appear = ease_out_cubic(prog(t, 0.2 + j * 0.004, 0.4))
        lit = ease_out_back(prog(t, 0.9 + j * (1.6 / max(1, k)), 0.3), 2.5) if on else 0
        C.person_icon(ctx, x, y, ih, mix(th.GRID, th.MUTED, 0.3), 0.8 * appear)
        if lit > 0:
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(lit, lit)
            C.person_icon(ctx, 0, 0, ih, th.ACCENT)
            ctx.restore()
    p = ease_out_expo(prog(t, 0.8, 1.8))
    pct = "%" + fmt_num(share * 100 * p, LANG, 0 if (share * 100).is_integer() else 1)
    if sc.get("format") == "count":
        pct = f"{round(k * p)} / {n}"
    D.draw_text(ctx, pct, 140, 560, 200, th.ACCENT, alpha=clamp((t - 0.6) * 3), kind="display")
    for i, ln in enumerate(D.wrap(sc.get("label", ""), 44, 720, "body")[:4]):
        D.anim_text(ctx, ln, 140, 660 + i * 58, 44, t, 1.2 + i * 0.2, "body", color=th.TEXT, stagger=0.012,
                    dur=0.35, mode="rise")
    D.footer_source(ctx, sc.get("source"), t)


# --- Harita ------------------------------------------------------------------

_MAPS = {}
_TR_MAP = str.maketrans("İIıÇçĞğÖöŞşÜüÂâÎî", "iiiccggoossuuaaii")


def _key(s):
    return str(s).translate(_TR_MAP).lower().strip()


def _load_map(kind):
    if kind not in _MAPS:
        import json
        import os
        fn = "turkiye_iller.json" if kind == "turkey" else "dunya.json"
        with open(os.path.join(os.path.dirname(__file__), "assets", "maps", fn), encoding="utf-8") as f:
            m = json.load(f)
        for ft in m["features"]:
            big = max(ft["polys"], key=len)
            ft["c"] = (sum(p[0] for p in big) / len(big), sum(p[1] for p in big) / len(big))
            ft["keys"] = {_key(k) for k in (ft.get("iso"), ft.get("name"), ft.get("en"), ft.get("id")) if k}
        _MAPS[kind] = m
    return _MAPS[kind]


def _match(m, label):
    k = _key(label)
    alias = {"abd": "usa", "amerika": "usa", "ingiltere": "gbr", "birlesik krallik": "gbr", "rusya": "rus",
             "guney kore": "kor", "kuzey kore": "prk", "cek cumhuriyeti": "cze", "iran": "irn"}
    k = alias.get(k, k)
    for ft in m["features"]:
        if k in ft["keys"]:
            return ft
    return None


def _unit_fmt(v, unit):
    n = fmt_num(v, LANG, None if abs(v) >= 1e6 else (0 if float(v).is_integer() or abs(v) >= 100 else 1))
    if unit == "%":
        return "%" + n
    if unit == "$":
        return "$" + n
    return f"{n} {unit}".strip()


def draw_map(ctx, sc, t, dur):
    """Dünya ya da Türkiye (il) haritası; bölgeler değere göre turuncunun tonlarıyla boyanır."""
    kind = "turkey" if _key(sc.get("map", "world")) in ("turkey", "turkiye", "tr", "iller") else "world"
    m = _load_map(kind)
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    vals = {}
    for d in sc.get("data", []):
        ft = _match(m, d.get("label", ""))
        if ft is not None:
            vals[id(ft)] = (_num(d.get("value")), d.get("label"))
    x0, y0, x1, y1 = m["bbox"]
    ax, ay, aw, ah = 140, 250, W - 280, H - 330
    s0 = min(aw / (x1 - x0), ah / (y1 - y0))
    # kamera: veriler küçük bir bölgedeyse oraya yakınlaş
    cam = (x0, y0, x1, y1)
    if vals and kind == "world":
        pts = [ft["c"] for ft in m["features"] if id(ft) in vals]
        bx0, by0 = min(p[0] for p in pts), min(p[1] for p in pts)
        bx1, by1 = max(p[0] for p in pts), max(p[1] for p in pts)
        pad = max(bx1 - bx0, (by1 - by0) * aw / ah, 0.6) * 0.35
        tgt = (bx0 - pad, by0 - pad, bx1 + pad, by1 + pad)
        if (tgt[2] - tgt[0]) < (x1 - x0) * 0.7:
            z = ease_in_out(prog(t, 0.6, 1.4))
            cam = tuple(lerp(a, b, z) for a, b in zip(cam, tgt))
    cs = min(aw / (cam[2] - cam[0]), ah / (cam[3] - cam[1]))
    ox = ax + (aw - (cam[2] - cam[0]) * cs) / 2 - cam[0] * cs
    oy = ay + (ah - (cam[3] - cam[1]) * cs) / 2 - cam[1] * cs
    lo = min((v for v, _ in vals.values()), default=0)
    hi = max((v for v, _ in vals.values()), default=1)
    base = mix(th.BG2, th.GRID, 0.7)
    dark, bright = mix(th.BG2, th.ACCENT, 0.35), th.ACCENT
    ctx.push_group()  # harita kenarlarda yumuşakça kaybolur
    for ft in m["features"]:
        cx_ = (ft["c"][0] - x0) / (x1 - x0)
        a = ease_out_cubic(prog(t, 0.1 + cx_ * 0.5, 0.5))
        if a <= 0:
            continue
        col = base
        if id(ft) in vals:
            v = vals[id(ft)][0]
            f = (v - lo) / (hi - lo) if hi > lo else 1.0
            q = ease_out_cubic(prog(t, 1.0 + cx_ * 0.6, 0.6))
            col = mix(base, mix(dark, bright, f), q)
        ctx.new_path()
        for poly in ft["polys"]:
            ctx.move_to(ox + poly[0][0] * cs, oy + poly[0][1] * cs)
            for px, py in poly[1:]:
                ctx.line_to(ox + px * cs, oy + py * cs)
            ctx.close_path()
        ctx.set_source_rgba(*col, a)
        ctx.fill_preserve()
        ctx.set_source_rgba(*th.BG, 0.9 * a)
        ctx.set_line_width(1.2 if kind == "world" else 1.6)
        ctx.stroke()
    ctx.pop_group_to_source()
    fade = cairo.LinearGradient(0, ay - 30, 0, ay + ah + 50)
    for st, a_ in ((0, 0), (0.08, 1), (0.9, 1), (1, 0)):
        fade.add_color_stop_rgba(st, 0, 0, 0, a_)
    ctx.mask(fade)
    # en yüksek değerli bölgelere etiket iğneleri (üst üste binmesinler)
    top = sorted(((v, lab, ft) for ft in m["features"] if id(ft) in vals for v, lab in [vals[id(ft)]]),
                 key=lambda r: -r[0])[: int(sc.get("labels", 6))]
    unit = sc.get("unit", "")
    placed = []
    for i, (v, lab, ft) in enumerate(top):
        px, py = ox + ft["c"][0] * cs, oy + ft["c"][1] * cs
        txt = f"{lab}  {_unit_fmt(v, unit)}"
        tw = D.text_width(txt, 26, "bold") + 28
        stem = 40
        for k in range(8):
            box = (px - tw / 2 - 6, py - stem - 50, px + tw / 2 + 6, py - stem + 2)
            if not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in placed):
                break
            stem = 40 + 56 * (k + 1) * (1 if k % 2 == 0 else -1) if py - 40 - 56 * (k + 1) > ay else stem + 56
        placed.append(box)
        q = ease_out_back(prog(t, 1.8 + i * 0.25, 0.4), 2.2)
        if q <= 0:
            continue
        ctx.save()
        ctx.translate(px, py)
        ctx.scale(q, q)
        ctx.set_source_rgb(*th.TEXT)
        ctx.arc(0, 0, 7, 0, math.tau)
        ctx.fill()
        ctx.move_to(0, 0)
        ctx.line_to(0, -stem)
        ctx.set_line_width(3)
        ctx.stroke()
        ctx.set_source_rgba(0.03, 0.03, 0.03, 0.92)
        D.round_rect(ctx, -tw / 2, -stem - 44, tw, 46, 8)
        ctx.fill()
        ctx.set_source_rgb(*th.ACCENT)
        ctx.rectangle(-tw / 2, -stem - 44, 5, 46)
        ctx.fill()
        D.draw_text(ctx, txt, 0, -stem - 12, 26, th.TEXT, kind="bold", align="center")
        ctx.restore()
    # gösterge
    if vals:
        q = clamp((t - 1.2) * 2)
        lx, ly = W - 140 - 360, H - 70
        g = cairo.LinearGradient(lx, 0, lx + 360, 0)
        g.add_color_stop_rgba(0, *dark, q)
        g.add_color_stop_rgba(1, *bright, q)
        ctx.set_source(g)
        D.round_rect(ctx, lx, ly - 14, 360, 14, 7)
        ctx.fill()
        D.draw_text(ctx, _unit_fmt(lo, unit), lx, ly + 22, 22, th.MUTED, alpha=q)
        D.draw_text(ctx, _unit_fmt(hi, unit), lx + 360, ly + 22, 22, th.MUTED, alpha=q, align="right")
    if sc.get("presenter"):
        C.draw_character(ctx, 150, H - 20, t, 0.5, look=sc.get("look", 0), pose="point", prev_pose="idle",
                         pose_t=prog(t, 0.6, 0.5), emotion="happy", talking=t < dur - 0.6, seed=4,
                         enter=prog(t, 0.2, 0.5))
    D.footer_source(ctx, sc.get("source"), t)


# --- Zaman çizelgesi ve önce/sonra -----------------------------------------------

def draw_timeline(ctx, sc, t, dur):
    """Yatay zaman çizgisi: çizgi soldan sağa çizilir, olaylar sırayla belirir (üst/alt dönüşümlü)."""
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    evs = [e for e in (sc.get("events") or []) if isinstance(e, dict)][:7]
    n = max(1, len(evs))
    gap = max(0.4, (dur - 2) / n)
    x0, x1, y = 230, W - 230, 640
    span = (x1 - x0) / max(1, n - 1) if n > 1 else 0
    end_p = ease_in_out(prog(t, 0.3, 0.6 + (n - 1) * gap))
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(*th.GRID, 1)
    ctx.set_line_width(6)
    ctx.move_to(x0 - 40, y)
    ctx.line_to(x1 + 40, y)
    ctx.stroke()
    ctx.set_source_rgb(*th.ACCENT)
    ctx.set_line_width(8)
    ctx.move_to(x0 - 40, y)
    ctx.line_to(x0 - 40 + (x1 - x0 + 80) * end_p, y)
    ctx.stroke()
    tw = min(380, span * 1.8) if n > 1 else 700
    for i, e in enumerate(evs):
        x = x0 + i * span if n > 1 else W / 2
        st = 0.6 + i * gap
        q = ease_out_back(prog(t, st, 0.35), 2.4)
        if q <= 0:
            continue
        last = i == len(evs) - 1
        up = i % 2 == 0
        a = clamp((t - st) * 4)
        # bağlantı çubuğu
        stem = ease_out_cubic(prog(t, st + 0.05, 0.3)) * 70
        ctx.set_source_rgba(*th.MUTED, 0.7 * a)
        ctx.set_line_width(3)
        ctx.move_to(x, y + (-16 if up else 16))
        ctx.line_to(x, y + (-16 - stem if up else 16 + stem))
        ctx.stroke()
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(q, q)
        if last:
            D.glow_circle(ctx, 0, 0, 46, th.ACCENT, 0.5)
        ctx.set_source_rgb(*th.BG)
        ctx.arc(0, 0, 22, 0, math.tau)
        ctx.fill()
        ctx.set_source_rgb(*th.ACCENT)
        ctx.set_line_width(7)
        ctx.arc(0, 0, 18, 0, math.tau)
        ctx.stroke()
        ctx.arc(0, 0, 8 if not last else 12, 0, math.tau)
        ctx.fill()
        ctx.restore()
        year = str(e.get("year", ""))
        ys = D.fit_size(year, 64, tw, "display")
        x = clamp(x, 60 + tw / 2, W - 60 - tw / 2)  # kenardaki etiketler ekrandan taşmasın
        lines = D.wrap(str(e.get("text", "")), 32, tw, "body")[:3]
        if up:
            ty = y - 100
            base = ty - ys - 10 - (len(lines) - 1) * 40
            D.anim_text(ctx, year, x, base, ys, t, st + 0.1, "display", color=th.ACCENT, align="center",
                        stagger=0.03, dur=0.35, mode="rise")
            for k, ln in enumerate(lines):
                D.draw_text(ctx, ln, x, base + 50 + k * 40, 32, th.TEXT, alpha=clamp((t - st - 0.25) * 3),
                            align="center")
        else:
            base = y + 100 + ys
            D.anim_text(ctx, year, x, base, ys, t, st + 0.1, "display", color=th.ACCENT, align="center",
                        stagger=0.03, dur=0.35, mode="rise")
            for k, ln in enumerate(lines):
                D.draw_text(ctx, ln, x, base + 50 + k * 40, 32, th.TEXT, alpha=clamp((t - st - 0.25) * 3),
                            align="center")
    D.footer_source(ctx, sc.get("source"), t)


def _val_text(sc, v, unit):
    if unit == "%":
        return "%" + fmt_num(v, LANG)
    if unit == "$":
        return "$" + fmt_num(v, LANG)
    return sc.get("prefix", "") + fmt_num(v, LANG) + (f" {unit}" if unit else "")


def _change_text(a, b, unit=""):
    if unit == "%":  # yüzdeler arasında fark puan olarak verilir
        d = b - a
        return f"{'+' if d >= 0 else '−'}{fmt_num(abs(d), LANG, 0 if abs(d) >= 10 else 1)} PUAN"
    if a == 0:
        return None
    ch = (b - a) / abs(a) * 100
    if abs(ch) >= 1000:
        return f"{b / a:.1f}".replace(".", ",") + " KAT" if b / a > 0 else None
    sign = "+" if ch >= 0 else "−"
    return f"{sign}%{fmt_num(abs(ch), LANG, 0 if abs(ch) >= 10 else 1)}"


def draw_compare(ctx, sc, t, dur):
    """Önce / sonra: iki panel, sayılar sayar, ortada değişim rozeti belirir."""
    if sc.get("backdrop"):
        B.draw_backdrop(ctx, sc["backdrop"], t, alpha=0.35)
    D.header(ctx, sc.get("title", ""), sc.get("kicker"), t)
    before, after = sc.get("before") or {}, sc.get("after") or {}
    bv, av = _num(before.get("value")), _num(after.get("value"))
    unit = sc.get("unit", "")
    hib = sc.get("higher_is_better", True)
    good = (av >= bv) == bool(hib)
    pw, ph, py = 700, 500, 320
    for i, (side, v, st) in enumerate(((before, bv, 0.2), (after, av, 1.2))):
        px = 140 if i == 0 else W - 140 - pw
        p = ease_out_cubic(prog(t, st, 0.5))
        if p <= 0:
            continue
        dx = (1 - p) * (-140 if i == 0 else 140)
        ctx.save()
        ctx.translate(dx, 0)
        hl = i == 1
        ctx.set_source_rgba(*(mix(th.BG, th.ACCENT, 0.12) if hl else mix(th.BG, th.GRID, 0.6)), 0.92 * p)
        D.round_rect(ctx, px, py, pw, ph, 22)
        ctx.fill_preserve()
        ctx.set_source_rgba(*(th.ACCENT if hl else th.GRID), p)
        ctx.set_line_width(4 if hl else 2)
        ctx.stroke()
        tag = str(side.get("tag") or ("ÖNCE" if i == 0 else "SONRA"))
        D.draw_text(ctx, tag.upper(), px + 44, py + 70, 30, th.ACCENT if hl else th.MUTED, alpha=p, kind="bold")
        D.draw_text(ctx, str(side.get("label", "")), px + 44, py + 140, D.fit_size(str(side.get("label", "")),
                    64, pw - 88, "display"), th.TEXT, alpha=p, kind="display")
        c = ease_out_expo(prog(t, st + 0.2, 1.0))
        num = _val_text(sc, v * c, unit)
        D.draw_text(ctx, num, px + 44, py + 330, D.fit_size(num, 150, pw - 88, "display"),
                    th.ACCENT if hl else th.TEXT, alpha=p, kind="display")
        for k, ln in enumerate(D.wrap(str(side.get("text", "")), 34, pw - 88, "body")[:3]):
            D.draw_text(ctx, ln, px + 44, py + 410 + k * 44, 34, th.MUTED, alpha=clamp((t - st - 0.4) * 3))
        ctx.restore()
    # ok
    a = ease_out_cubic(prog(t, 0.4, 0.6))
    if a > 0:
        cx, cy = W / 2, py + ph / 2
        ctx.set_source_rgba(*th.ACCENT, a)
        ctx.set_line_width(10)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(cx - 60, cy)
        ctx.line_to(cx - 60 + 110 * a, cy)
        ctx.stroke()
        ctx.move_to(cx - 60 + 110 * a + 14, cy)
        ctx.line_to(cx - 60 + 110 * a - 16, cy - 26)
        ctx.line_to(cx - 60 + 110 * a - 16, cy + 26)
        ctx.close_path()
        ctx.fill()
    ch = _change_text(bv, av, unit)
    q = ease_out_back(prog(t, 2.3, 0.45), 2.4)
    if ch and q > 0:
        ctx.save()
        ctx.translate(W / 2, py + ph + 80)
        ctx.scale(q, q)
        ctx.rotate(-0.04)
        bw = D.text_width(ch, 64, "display") + 70
        ctx.set_source_rgb(*(th.ACCENT if good else (0.85, 0.25, 0.22)))
        D.round_rect(ctx, -bw / 2, -50, bw, 96, 18)
        ctx.fill()
        D.draw_text(ctx, ch, 0, 22, 64, (0.05, 0.05, 0.05), kind="display", align="center")
        ctx.restore()
    D.footer_source(ctx, sc.get("source"), t)


DRAWERS = {
    "title": draw_title, "bullets": draw_bullets, "stat": draw_stat, "bar": draw_bar,
    "line": draw_line, "pie": draw_pie, "table": draw_table, "image": draw_image,
    "outro": draw_outro, "character": draw_character_scene, "versus": draw_versus, "people": draw_people,
    "map": draw_map, "timeline": draw_timeline, "compare": draw_compare,
}
