"""Çizim yardımcıları: metin (gömülü fontlarla), animasyonlu metin, elle çizilmiş (rough)
şekiller, arka planlar ve sahne geçişleri. İki stili de (modern / çizgi) destekler."""
import math
import random

import cairo
from PIL import Image, ImageDraw, ImageFont

from . import theme as th
from .theme import W, H, clamp, mix, lerp, prog, ease_out_cubic, ease_out_back, ease_in_out

BOIL = 0  # çizgi stilinde "titreyen çizgi" tohumu; her birkaç karede bir değişir


def new_surface():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    return surf, cairo.Context(surf)


# --- Metin -------------------------------------------------------------------

_fonts, _masks = {}, {}


def font(kind, size):
    key = (th.FONTS[kind], int(size))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(key[0], int(size))
    return _fonts[key]


def text_width(s, size, kind="body"):
    return font(kind, size).getlength(s)


def _mask(s, size, kind, stroke=0):
    """Metnin alfa maskesi (cairo A8) ve taban çizgisine göre ofseti."""
    key = (s, int(size), kind, th.STYLE, stroke)
    m = _masks.get(key)
    if m:
        return m
    if len(_masks) > 6000:
        _masks.clear()
    f = font(kind, size)
    l, t, r, b = f.getbbox(s, anchor="ls", stroke_width=stroke)
    pad = 4
    w, h = max(1, r - l + 2 * pad), max(1, b - t + 2 * pad)
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((-l + pad, -t + pad), s, fill=255, font=f, anchor="ls",
                            stroke_width=stroke, stroke_fill=255)
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_A8, w)
    raw = im.tobytes()
    data = bytearray(stride * h)
    for row in range(h):
        data[row * stride:row * stride + w] = raw[row * w:(row + 1) * w]
    surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_A8, w, h, stride)
    m = (surf, l - pad, t - pad, data)
    _masks[key] = m
    return m


def _paint_mask(ctx, s, x, y, size, kind, source, alpha, stroke=0):
    surf, ox, oy, _ = _mask(s, size, kind, stroke)
    ctx.save()
    if isinstance(source, cairo.Pattern):
        ctx.set_source(source)
    else:
        ctx.set_source_rgba(*source, alpha)
    if alpha < 1 and isinstance(source, cairo.Pattern):
        ctx.push_group()
        ctx.set_source(source)
        ctx.mask_surface(surf, x + ox, y + oy)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)
    else:
        ctx.mask_surface(surf, x + ox, y + oy)
    ctx.restore()


def draw_text(ctx, s, x, y, size, color=None, alpha=1.0, kind="body", align="left", source=None,
              outline=None, shadow=None):
    """y taban çizgisidir. Çizgi stilinde outline/shadow ile çıkartma görünümü verilebilir."""
    s = str(s)
    if not s or alpha <= 0.002:
        return text_width(s, size, kind) if s else 0
    color = th.TEXT if color is None else color
    w = text_width(s, size, kind)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    sw = max(2, int(size * 0.07))
    if shadow:
        _paint_mask(ctx, s, x + shadow[0], y + shadow[1], size, kind, th.INK, alpha * 0.9,
                    sw if outline else 0)
    if outline:
        _paint_mask(ctx, s, x, y, size, kind, outline, alpha, sw)
    _paint_mask(ctx, s, x, y, size, kind, source if source is not None else color, alpha)
    return w


def anim_text(ctx, s, x, y, size, t, start=0.0, kind="display", color=None, align="left",
              stagger=0.03, dur=0.6, source=None, mode=None, outline=None, shadow=None):
    """Harf harf animasyonlu metin. mode: 'rise' (modern), 'pop' (çizgi), 'type' (daktilo)."""
    s = str(s)
    mode = mode or ("pop" if th.SKETCH else "rise")
    w = text_width(s, size, kind)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    f = font(kind, size)
    n = len(s)
    for i, ch in enumerate(s):
        if ch == " ":
            continue
        p = prog(t, start + i * stagger, dur)
        if p <= 0:
            if mode == "type":
                break
            continue
        cx = x + f.getlength(s[:i])
        cw = f.getlength(ch)
        ctx.save()
        if mode == "rise":
            e = ease_out_cubic(p)
            ctx.translate(0, (1 - e) * size * 0.5)
            a = e
        elif mode == "pop":
            e = ease_out_back(p, 2.4)
            rot = math.sin(i * 1.7 + BOIL * 0.9) * 0.04 if th.SKETCH else 0
            ctx.translate(cx + cw / 2, y - size * 0.3)
            ctx.rotate(rot * (1.5 - p))
            ctx.scale(max(0.01, e), max(0.01, e))
            ctx.translate(-(cx + cw / 2), -(y - size * 0.3))
            a = clamp(p * 3)
        else:  # type
            a = 1.0
        draw_text(ctx, ch, cx, y, size, color, a, kind, source=source, outline=outline, shadow=shadow)
        ctx.restore()
    if mode == "type":
        k = sum(1 for i in range(n) if prog(t, start + i * stagger, dur) > 0)
        if k < n and int(t * 3) % 2 == 0:
            cx = x + f.getlength(s[:k])
            ctx.set_source_rgba(*(color or th.TEXT), 0.9)
            ctx.rectangle(cx + 2, y - size * 0.75, max(3, size * 0.06), size * 0.85)
            ctx.fill()
    return w


def wrap(s, size, max_w, kind="body"):
    lines, cur = [], ""
    for word in str(s).split():
        trial = (cur + " " + word).strip()
        if text_width(trial, size, kind) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_size(s, size, max_w, kind="display", min_size=24):
    while size > min_size and text_width(s, size, kind) > max_w:
        size -= 2
    return size


# --- Temel şekiller ----------------------------------------------------------

def round_rect(ctx, x, y, w, h, r):
    r = max(0, min(r, w / 2, h / 2))
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def accent_gradient(x0, y0, x1, y1, c1=None, c2=None, alpha=1.0):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    g.add_color_stop_rgba(0, *(c1 or th.ACCENT), alpha)
    g.add_color_stop_rgba(1, *(c2 or th.ACCENT2), alpha)
    return g


def glow_circle(ctx, x, y, r, color, alpha=1.0):
    if r <= 0:
        return
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, *color, alpha)
    g.add_color_stop_rgba(1, *color, 0)
    ctx.set_source(g)
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.fill()


# --- Elle çizilmiş (rough) şekiller ----------------------------------------

def _rng(*key):
    return random.Random(hash((BOIL,) + key) & 0xFFFFFFFF)


def rough_line_path(ctx, x1, y1, x2, y2, amp=2.5, key=0):
    r = _rng("l", key, int(x1), int(y1))
    ln = math.hypot(x2 - x1, y2 - y1)
    a = min(amp, ln * 0.05 + 0.6)
    ctx.move_to(x1 + r.uniform(-a, a), y1 + r.uniform(-a, a))
    m1, m2 = r.uniform(0.3, 0.5), r.uniform(0.55, 0.8)
    ctx.curve_to(lerp(x1, x2, m1) + r.uniform(-a, a) * 1.5, lerp(y1, y2, m1) + r.uniform(-a, a) * 1.5,
                 lerp(x1, x2, m2) + r.uniform(-a, a) * 1.5, lerp(y1, y2, m2) + r.uniform(-a, a) * 1.5,
                 x2 + r.uniform(-a, a), y2 + r.uniform(-a, a))


def rough_stroke_poly(ctx, pts, color=None, width=4, closed=False, passes=2, key=0, alpha=1.0):
    color = color or th.INK
    seg = list(zip(pts, pts[1:] + (pts[:1] if closed else [])))
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    for p in range(passes):
        for i, ((x1, y1), (x2, y2)) in enumerate(seg):
            rough_line_path(ctx, x1, y1, x2, y2, key=(key, p, i))
        ctx.set_source_rgba(*color, alpha * (1 if p == 0 else 0.7))
        ctx.set_line_width(width if p == 0 else width * 0.6)
        ctx.stroke()


def rough_rect(ctx, x, y, w, h, fill=None, stroke=None, width=4, key=0, shadow=6, alpha=1.0, hatch=False):
    """Çizgi film tarzı kutu: kayık sert gölge + düz dolgu + titrek mürekkep kontur."""
    r = _rng("r", key)
    j = lambda: r.uniform(-2.5, 2.5)
    pts = [(x + j(), y + j()), (x + w + j(), y + j()), (x + w + j(), y + h + j()), (x + j(), y + h + j())]
    if shadow and w > 2 and h > 2:
        ctx.set_source_rgba(*th.INK, 0.9 * alpha)
        ctx.move_to(*[c + shadow for c in pts[0]])
        for px, py in pts[1:]:
            ctx.line_to(px + shadow, py + shadow)
        ctx.close_path()
        ctx.fill()
    if fill:
        ctx.set_source_rgba(*fill, alpha)
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.close_path()
        ctx.fill()
        if hatch and w > 20:
            ctx.save()
            ctx.rectangle(x, y, w, h)
            ctx.clip()
            ctx.set_source_rgba(*mix(fill, (1, 1, 1), 0.45), 0.55 * alpha)
            ctx.set_line_width(3)
            for hx in range(int(x - h), int(x + w), 18):
                ctx.move_to(hx, y + h)
                ctx.line_to(hx + h, y)
            ctx.stroke()
            ctx.restore()
    if width:
        rough_stroke_poly(ctx, pts, stroke, width, closed=True, key=key, alpha=alpha)


def rough_ellipse(ctx, cx, cy, rx, ry, color=None, width=4, fill=None, key=0, alpha=1.0, frac=1.0):
    r = _rng("e", key)
    n = 28
    over = r.uniform(0.05, 0.15)
    a0 = r.uniform(0, math.tau)
    pts = []
    for i in range(int(n * (1 + over) * frac) + 1):
        a = a0 + math.tau * i / n
        k = 1 + r.uniform(-0.025, 0.025)
        pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    if fill and frac >= 1:
        ctx.set_source_rgba(*fill, alpha)
        ctx.arc(cx, cy, 1, 0, 0)
        ctx.save()
        ctx.translate(cx, cy)
        ctx.scale(rx, ry)
        ctx.arc(0, 0, 1, 0, math.tau)
        ctx.restore()
        ctx.fill()
    if len(pts) > 2:
        ctx.move_to(*pts[0])
        for i in range(1, len(pts) - 2, 2):
            ctx.curve_to(*pts[i], *pts[i + 1], *pts[min(i + 2, len(pts) - 1)])
        ctx.set_source_rgba(*(color or th.INK), alpha)
        ctx.set_line_width(width)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()


def marker_highlight(ctx, x, y, w, h, p, color=None, key=0):
    """Fosforlu kalem vurgusu: soldan sağa süpürülen yarı saydam şerit."""
    if p <= 0:
        return
    color = color or th.HILITE
    r = _rng("m", key)
    ww = w * ease_out_cubic(p)
    ctx.save()
    ctx.set_source_rgba(*color, 0.85 if th.SKETCH else 0.55)
    ctx.move_to(x - 8, y + r.uniform(-3, 3))
    ctx.curve_to(x + ww * 0.3, y - 4, x + ww * 0.7, y + 3, x + ww + 8, y + r.uniform(-3, 3))
    ctx.line_to(x + ww + 4, y + h + r.uniform(-3, 3))
    ctx.curve_to(x + ww * 0.6, y + h + 4, x + ww * 0.3, y + h - 3, x - 4, y + h + r.uniform(-3, 3))
    ctx.close_path()
    ctx.fill()
    ctx.restore()


def draw_on(ctx, length, p):
    """Mevcut yolu p oranında 'çiziliyor' gibi göster (dash hilesi)."""
    ctx.set_dash([max(0.01, length * clamp(p)), length + 10])


def card(ctx, x, y, w, h, alpha=1.0, key=0, fill=None):
    """Stil-bağımsız içerik kartı."""
    if th.SKETCH:
        rough_rect(ctx, x, y, w, h, fill=fill or (1, 1, 1), width=4, key=key, shadow=8, alpha=alpha)
    else:
        ctx.set_source_rgba(*(fill or (1, 1, 1)), 0.05 * alpha if not fill else alpha)
        round_rect(ctx, x, y, w, h, 24)
        ctx.fill()


# --- Arka plan ---------------------------------------------------------------

_r = random.Random(7)
_BLOBS = [(_r.uniform(0.1, 0.9), _r.uniform(0.1, 0.9), _r.uniform(0.15, 0.35),
           _r.uniform(0.04, 0.12), _r.uniform(0, 6.28), i % 3) for i in range(5)]
_PARTICLES = [(_r.uniform(0, W), _r.uniform(0, H), _r.uniform(1, 2.6),
               _r.uniform(8, 30), _r.uniform(0, 6.28)) for _ in range(70)]
_DOODLES = [(_r.choice(("star", "squiggle", "circle", "plus", "dots", "spiral")),
             _r.uniform(0.03, 0.97), _r.uniform(0.04, 0.96), _r.uniform(22, 46), _r.uniform(0, 6.28), i)
            for i in range(16)]
_paper = None


def _paper_surface():
    """Kâğıt dokusu: bir kez üretilir, statik olduğu için video boyutunu büyütmez."""
    global _paper
    if _paper is None:
        _paper = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        c = cairo.Context(_paper)
        g = cairo.RadialGradient(W / 2, H / 2, H * 0.2, W / 2, H / 2, W * 0.75)
        g.add_color_stop_rgb(0, *th.BG)
        g.add_color_stop_rgb(1, *th.BG2)
        c.set_source(g)
        c.paint()
        r = random.Random(11)
        for _ in range(9000):  # lif ve benekler
            x, y = r.uniform(0, W), r.uniform(0, H)
            c.set_source_rgba(0.45, 0.38, 0.25, r.uniform(0.02, 0.07))
            c.arc(x, y, r.uniform(0.5, 1.6), 0, math.tau)
            c.fill()
        c.set_line_width(1)
        for _ in range(500):
            x, y = r.uniform(0, W), r.uniform(0, H)
            a = r.uniform(0, math.tau)
            ln = r.uniform(4, 14)
            c.set_source_rgba(0.45, 0.38, 0.25, 0.05)
            c.move_to(x, y)
            c.line_to(x + math.cos(a) * ln, y + math.sin(a) * ln)
            c.stroke()
    return _paper


def _doodle(ctx, kind, x, y, s, key):
    col = th.PALETTE[key % len(th.PALETTE)]
    ctx.set_line_width(3.5)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(*col, 0.45)
    if kind == "star":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = s if i % 2 == 0 else s * 0.45
            pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        rough_stroke_poly(ctx, pts, col, 3.5, closed=True, passes=1, key=key, alpha=0.45)
    elif kind == "squiggle":
        ctx.move_to(x - s, y)
        for i in range(4):
            ctx.curve_to(x - s + (i + 0.3) * s / 2, y - s / 2, x - s + (i + 0.7) * s / 2, y + s / 2,
                         x - s + (i + 1) * s / 2, y)
        ctx.stroke()
    elif kind == "circle":
        rough_ellipse(ctx, x, y, s * 0.6, s * 0.6, col, 3.5, key=key, alpha=0.45)
    elif kind == "plus":
        rough_stroke_poly(ctx, [(x - s / 2, y), (x + s / 2, y)], col, 4, passes=1, key=key, alpha=0.45)
        rough_stroke_poly(ctx, [(x, y - s / 2), (x, y + s / 2)], col, 4, passes=1, key=key + 1, alpha=0.45)
    elif kind == "dots":
        for i in range(3):
            ctx.arc(x + (i - 1) * s * 0.5, y, 4, 0, math.tau)
            ctx.fill()
    else:
        for i in range(40):
            a = i * 0.35
            rr = s * i / 40
            (ctx.move_to if i == 0 else ctx.line_to)(x + math.cos(a) * rr, y + math.sin(a) * rr)
        ctx.stroke()


def background(ctx, gt):
    """gt: videonun genel zamanı (sahneler arası kesintisiz hareket için)."""
    if th.SKETCH:
        ctx.set_source_surface(_paper_surface(), 0, 0)
        ctx.paint()
        for kind, fx, fy, s, ph, key in _DOODLES:
            # orta alanı içerik için boş bırak
            if 0.12 < fx < 0.88 and 0.2 < fy < 0.85:
                continue
            x = fx * W + 10 * math.sin(gt * 0.6 + ph)
            y = fy * H + 8 * math.cos(gt * 0.8 + ph)
            ctx.save()
            ctx.translate(x, y)
            ctx.rotate(0.15 * math.sin(gt * 0.5 + ph))
            _doodle(ctx, kind, 0, 0, s, key)
            ctx.restore()
        return
    g = cairo.LinearGradient(0, 0, W, H)
    g.add_color_stop_rgb(0, *th.BG)
    g.add_color_stop_rgb(1, *th.BG2)
    ctx.set_source(g)
    ctx.paint()
    cols = (th.ACCENT, th.ACCENT2, mix(th.ACCENT, th.ACCENT2, 0.5))
    for bx, by, br, speed, ph, ci in _BLOBS:
        x = (bx + 0.08 * math.sin(gt * speed + ph)) * W
        y = (by + 0.08 * math.cos(gt * speed * 1.3 + ph)) * H
        glow_circle(ctx, x, y, br * W, cols[ci], 0.16)
    ctx.set_line_width(1)
    ctx.set_source_rgba(*th.GRID, 0.18)
    step = 96
    off = (gt * 12) % step
    for x in range(-step, W + step, step):
        ctx.move_to(x + off, 0)
        ctx.line_to(x + off, H)
    for y in range(0, H + step, step):
        ctx.move_to(0, y)
        ctx.line_to(W, y)
    ctx.stroke()
    if th.STYLE == "mekanik":
        _data_rain(ctx, gt)
    for px, py, pr, sp, ph in _PARTICLES:
        y = (py - gt * sp) % H
        x = px + 20 * math.sin(gt * 0.5 + ph)
        ctx.set_source_rgba(*th.TEXT, 0.25 + 0.25 * math.sin(gt * 1.5 + ph))
        ctx.arc(x, y, pr, 0, math.tau)
        ctx.fill()
    v = cairo.RadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, W * 0.75)
    v.add_color_stop_rgba(0, 0, 0, 0, 0)
    v.add_color_stop_rgba(1, 0, 0, 0, 0.55)
    ctx.set_source(v)
    ctx.paint()


_RAIN = [(i * 80 + _r.uniform(-20, 20), _r.uniform(60, 160), _r.uniform(0, H), _r.randint(6, 14))
         for i in range(W // 80 + 1)]


def _data_rain(ctx, gt):
    """Matrix tarzı, çok soluk akan rakam sütunları (turuncu)."""
    for ci, (x, speed, off, n) in enumerate(_RAIN):
        head = (off + gt * speed) % (H + n * 30)
        for k in range(n):
            y = head - k * 30
            if not -30 < y < H + 30:
                continue
            ch = "0123456789ABCDEF"[(ci * 7 + k * 13 + int(gt * 6 + k)) % 16]
            a = (0.16 if k == 0 else 0.07 * (1 - k / n))
            draw_text(ctx, ch, x, y, 22, th.ACCENT if k else th.ACCENT2, alpha=a, kind="hand")


# --- Sahne geçişleri -------------------------------------------------------

TRANSITIONS = ("wipe", "iris", "stripes", "slide", "blinds")


def transition(ctx, kind, p, entering, idx):
    """p: 0..1. entering=False iken perde ekranı kapatır, True iken açılır (ters yöne çekilir)."""
    if p <= 0:
        return
    col1 = th.PALETTE[idx % len(th.PALETTE)]
    col2 = th.PALETTE[(idx + 1) % len(th.PALETTE)]
    e = ease_in_out(p)
    ctx.save()
    if th.SKETCH:
        src = cairo.SolidPattern(*col1)
    else:
        src = accent_gradient(0, 0, W, H, col1, col2)

    def fill_poly(pts, pat=src, outline=True):
        ctx.move_to(*pts[0])
        for q in pts[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        ctx.set_source(pat)
        ctx.fill()
        if th.SKETCH and outline:
            rough_stroke_poly(ctx, pts, th.INK, 6, closed=True, passes=1, key=idx)

    if kind == "wipe":  # eğik panel soldan girer, sağdan çıkar
        sk = 300
        if not entering:
            x1 = lerp(-sk, W + sk, e)
            fill_poly([(-sk - 40, 0), (x1, 0), (x1 - sk, H), (-sk - 40, H)])
        else:
            x0 = lerp(-sk, W + sk, 1 - e)
            fill_poly([(x0, 0), (W + sk + 40, 0), (W + sk + 40, H), (x0 - sk, H)])
    elif kind == "iris":
        R = math.hypot(W, H) / 2 + 40
        if not entering:
            r = R * e
            ctx.arc(W / 2, H / 2, max(0.1, r), 0, math.tau)
            ctx.set_source(src)
            ctx.fill()
            if th.SKETCH and r > 5:
                rough_ellipse(ctx, W / 2, H / 2, r, r, th.INK, 6, key=idx)
        else:
            r = R * (1 - e)
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            ctx.rectangle(0, 0, W, H)
            ctx.arc(W / 2, H / 2, max(0.1, r), 0, math.tau)
            ctx.set_source(src)
            ctx.fill()
            if th.SKETCH and r > 5:
                rough_ellipse(ctx, W / 2, H / 2, r, r, th.INK, 6, key=idx)
    elif kind in ("stripes", "blinds"):
        n = 6
        for i in range(n):
            q = ease_in_out(clamp(p * 1.6 - i * 0.6 / n))
            if kind == "stripes":
                h = H / n
                y = i * h
                if not entering:
                    fill_poly([(-10, y), (W * q, y), (W * q, y + h + 1), (-10, y + h + 1)],
                              cairo.SolidPattern(*th.PALETTE[(idx + i) % len(th.PALETTE)]) if th.SKETCH else src)
                else:
                    fill_poly([(W * (1 - q), y), (W + 10, y), (W + 10, y + h + 1), (W * (1 - q), y + h + 1)],
                              cairo.SolidPattern(*th.PALETTE[(idx + i) % len(th.PALETTE)]) if th.SKETCH else src)
            else:
                wv = W / n
                x = i * wv
                hh = H * q
                if not entering:
                    fill_poly([(x, -10), (x + wv + 1, -10), (x + wv + 1, hh), (x, hh)])
                else:
                    fill_poly([(x, H - hh), (x + wv + 1, H - hh), (x + wv + 1, H + 10), (x, H + 10)])
    else:  # slide: iki katmanlı panel sağdan
        for layer, (c, lag) in enumerate(((col2, 0.0), (col1, 0.18))):
            q = ease_in_out(clamp((p - lag) / (1 - lag))) if not entering else ease_in_out(clamp(p / (1 - lag)))
            pat = cairo.SolidPattern(*c) if th.SKETCH else accent_gradient(0, 0, W, H, c, mix(c, (1, 1, 1), 0.15))
            if not entering:
                x0 = W * (1 - q)
                fill_poly([(x0, -10), (W + 10, -10), (W + 10, H + 10), (x0, H + 10)], pat)
            else:
                x1 = W * q
                fill_poly([(-10, -10), (x1, -10), (x1, H + 10), (-10, H + 10)], pat)
    ctx.restore()


# --- Ortak sahne parçaları ---------------------------------------------------

def header(ctx, title, kicker, t, x=140, y=190, size=68):
    """Üst etiket (fosforlu vurgu) + harf harf gelen başlık + çizilen alt çizgi."""
    p = ease_out_cubic(prog(t, 0.05, 0.6))
    if kicker:
        k = kicker if th.SKETCH else kicker.upper()
        ks = 40 if th.SKETCH else 24
        kind = "hand" if th.SKETCH else "bold"
        kw = text_width(k, ks, kind)
        marker_highlight(ctx, x - 6, y - size - 20 - ks * 0.8, kw + 12, ks * 0.95, prog(t, 0.05, 0.5),
                         None if th.SKETCH else th.ACCENT, key=7)
        draw_text(ctx, k, x, y - size - 22, ks, th.INK if th.SKETCH else th.TEXT, alpha=p, kind=kind)
    size = fit_size(title, size, W - 2 * x)
    if th.SKETCH:  # renkli kayık gölge
        anim_text(ctx, title, x + 4, y + 4, size, t, 0.15, "display", stagger=0.018, dur=0.5,
                  color=th.HILITE)
    anim_text(ctx, title, x, y, size, t, 0.15, "display", stagger=0.018, dur=0.5,
              color=th.INK if th.SKETCH else None)
    tw = min(text_width(title, size, "display"), W - 2 * x)
    q = prog(t, 0.5, 0.7)
    if th.SKETCH:
        ctx.save()
        ln = tw * 0.4 + 20
        ctx.move_to(x, y + 26)
        ctx.curve_to(x + ln * 0.3, y + 18, x + ln * 0.7, y + 34, x + ln, y + 24)
        draw_on(ctx, ln * 1.1, ease_out_cubic(q))
        ctx.set_source_rgb(*th.ACCENT)
        ctx.set_line_width(9)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.stroke()
        ctx.restore()
    else:
        lw = 160 * ease_out_cubic(q)
        ctx.set_source(accent_gradient(x, 0, x + 160, 0))
        round_rect(ctx, x, y + 26, lw, 6, 3)
        ctx.fill()


def footer_source(ctx, source, t):
    if not source:
        return
    a = clamp((t - 0.8) / 0.6) * 0.85
    if th.SKETCH:
        draw_text(ctx, f"Kaynak: {source}", 140, H - 60, 30, th.MUTED, alpha=a, kind="hand")
    else:
        draw_text(ctx, f"Kaynak: {source}", 140, H - 70, 22, mix(th.TEXT, th.BG, 0.4), alpha=a)
