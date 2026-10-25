"""Düz renkli, büyük kafalı anlatıcı karakterler (bilgi grafiği videoları tarzında, kendi tasarımımız).

Karakter tamamen Cairo ile çizilir: göz kırpar, konuşurken ağzı oynar, nefes alır gibi hafifçe
sallanır ve pozlar arasında yumuşakça geçer. Koordinatlar ayakların ortasına göredir; ölçek 1'de
karakter yaklaşık 610 px boyundadır.
"""
import math

from . import theme as th
from .theme import clamp, prog, lerp, ease_out_back, ease_in_out

SKINS = ["#F1C27D", "#E0AC69", "#FFDBAC", "#C68642", "#8D5524"]
HAIRS = ["#2B1B12", "#5A3A22", "#151515", "#B5651D", "#D9C3A0"]
LOOKS = [  # hazır karakterler: ten, saç rengi, saç modeli, gömlek, pantolon, aksesuar
    dict(skin=0, hair=0, style="short", shirt="#FF7A1A", pants="#3A3330", extra="tie"),
    dict(skin=2, hair=3, style="long", shirt="#F2EBE1", pants="#3A3330", extra=None),
    dict(skin=3, hair=2, style="curly", shirt="#FFB066", pants="#2E2A28", extra="glasses"),
    dict(skin=1, hair=1, style="bun", shirt="#C2560E", pants="#3A3330", extra=None),
    dict(skin=4, hair=2, style="bald", shirt="#8C8277", pants="#2E2A28", extra="beard"),
    dict(skin=0, hair=4, style="cap", shirt="#FFD2A1", pants="#3A3330", extra=None),
]

# Kol açıları: 0 aşağı, +π/2 ileri (bakılan yön), ±π yukarı. (üst kol, ön kol) — ön kol / arka kol
POSES = {
    "idle": ((0.18, 0.08), (-0.18, -0.08)),
    "talk": ((0.45, 1.1), (-0.2, -0.1)),
    "point": ((1.45, 1.55), (-0.2, -0.1)),
    "present": ((1.0, 1.35), (-0.45, -0.7)),
    "wave": ((2.4, 2.9), (-0.2, -0.1)),
    "cheer": ((2.2, 2.7), (-2.2, -2.7)),
    "shrug": ((0.9, 2.3), (-0.9, -2.3)),
    "think": ((-1.25, 2.45), (-0.15, -0.1)),
    "sad": ((0.05, 0.0), (-0.05, 0.0)),
}
EMOTIONS = ("happy", "neutral", "surprised", "sad", "angry", "worried")


def _rgb(h):
    return th.hex2rgb(h)


def _shade(c, k):
    return tuple(clamp(x * k) for x in c)


def _ellipse(ctx, x, y, rx, ry):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(max(rx, 0.01), max(ry, 0.01))
    ctx.arc(0, 0, 1, 0, math.tau)
    ctx.restore()


def _rrect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def look_of(i):
    return LOOKS[i % len(LOOKS)] if isinstance(i, int) else LOOKS[0]


def _blink(t, seed):
    period = 3.1 + (seed % 3) * 0.7
    ph = (t + seed * 1.37) % period
    return 0.12 if ph < 0.12 else 1.0


def _mouth_open(t, talking, seed):
    if not talking:
        return 0.0
    v = 0.5 + 0.5 * math.sin(t * 17 + seed) * math.sin(t * 6.3 + seed * 2)
    return clamp(abs(v) * 1.2)


def draw_character(ctx, x, y, t, scale=1.0, look=0, pose="idle", prev_pose=None, pose_t=1.0,
                   emotion="happy", talking=False, facing=1, seed=0, alpha=1.0, enter=1.0):
    """Karakteri çizer. pose_t (0..1): prev_pose'dan pose'a geçiş ilerlemesi. enter: giriş animasyonu (0..1)."""
    if alpha <= 0 or enter <= 0:
        return
    L = look_of(look)
    skin, hair = _rgb(SKINS[L["skin"]]), _rgb(HAIRS[L["hair"]])
    shirt, pants = _rgb(L["shirt"]), _rgb(L["pants"])
    ctx.save()
    ctx.translate(x, y)
    e = ease_out_back(enter, 1.8)
    ctx.scale(scale * facing, scale * max(0.01, e))
    ctx.push_group()

    bob = math.sin(t * 2.2 + seed) * 4
    # yer gölgesi
    ctx.set_source_rgba(0, 0, 0, 0.35)
    _ellipse(ctx, 0, 4, 120, 18)
    ctx.fill()
    ctx.set_source_rgba(*th.ACCENT, 0.10)
    _ellipse(ctx, 0, 4, 170, 26)
    ctx.fill()

    # bacaklar ve ayakkabılar
    for sx in (-1, 1):
        ctx.set_source_rgb(*pants)
        _rrect(ctx, sx * 30 - 22, -160, 44, 152, 18)
        ctx.fill()
        ctx.set_source_rgb(*_shade(pants, 0.55))
        _ellipse(ctx, sx * 30 + 10, -10, 40, 17)
        ctx.fill()

    ctx.translate(0, bob)
    # uzun saçın arka kısmı (kafanın arkasında kalır)
    if L["style"] == "long":
        ctx.set_source_rgb(*hair)
        _rrect(ctx, -140, -560, 280, 300, 110)
        ctx.fill()

    # gövde
    ctx.set_source_rgb(*shirt)
    _rrect(ctx, -82, -335, 164, 200, 56)
    ctx.fill()
    ctx.set_source_rgba(0, 0, 0, 0.10)  # yan gölge
    _rrect(ctx, 20, -335, 62, 200, 40)
    ctx.fill()
    ctx.set_source_rgb(*_shade(shirt, 0.8))  # yaka
    ctx.move_to(-30, -335)
    ctx.line_to(0, -295)
    ctx.line_to(30, -335)
    ctx.close_path()
    ctx.fill()
    if L["extra"] == "tie":
        ctx.set_source_rgb(*_rgb("#1E1E1E"))
        ctx.move_to(-10, -318)
        ctx.line_to(10, -318)
        ctx.line_to(16, -220)
        ctx.line_to(0, -200)
        ctx.line_to(-16, -220)
        ctx.close_path()
        ctx.fill()

    # kollar: önce arkadaki, sonra öndeki
    p = ease_in_out(pose_t)
    a_now = POSES.get(pose, POSES["idle"])
    a_old = POSES.get(prev_pose or pose, a_now)
    for arm, sx in ((1, -1), (0, 1)):
        u = lerp(a_old[arm][0], a_now[arm][0], p)
        f = lerp(a_old[arm][1], a_now[arm][1], p)
        if pose == "wave" and arm == 0:
            f += 0.35 * math.sin(t * 9)
        if pose in ("talk", "present") and arm == 0:
            f += 0.12 * math.sin(t * 3 + seed)
        sx0, sy0 = sx * 70, -300
        ex, ey = sx0 + math.sin(u) * 100, sy0 + math.cos(u) * 100
        hx, hy = ex + math.sin(f) * 92, ey + math.cos(f) * 92
        col = _shade(shirt, 0.9 if arm == 1 else 1.0)
        ctx.set_line_cap(1)  # yuvarlak uç
        ctx.set_line_join(1)
        ctx.set_source_rgb(*col)
        ctx.set_line_width(36)
        ctx.move_to(sx0, sy0)
        ctx.line_to(ex, ey)
        ctx.line_to(hx, hy)
        ctx.stroke()
        ctx.set_source_rgb(*(skin if arm == 0 else _shade(skin, 0.9)))
        _ellipse(ctx, hx, hy, 23, 23)
        ctx.fill()

    # kafa
    hy0 = -478
    tilt = 0.04 * math.sin(t * 1.3 + seed)
    ctx.save()
    ctx.translate(0, hy0)
    ctx.rotate(tilt)
    ctx.set_source_rgb(*skin)
    for sx in (-1, 1):  # kulaklar
        _ellipse(ctx, sx * 124, 8, 24, 30)
        ctx.fill()
    _ellipse(ctx, 0, 0, 128, 138)
    ctx.fill()
    ctx.set_source_rgba(0, 0, 0, 0.07)
    _ellipse(ctx, 40, 10, 90, 120)
    ctx.fill()
    _hair(ctx, L["style"], hair)
    _face(ctx, t, emotion, talking, seed, L)
    ctx.restore()

    ctx.pop_group_to_source()
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def _hair(ctx, style, c):
    ctx.set_source_rgb(*c)
    if style == "short":
        ctx.move_to(-132, -10)
        ctx.curve_to(-150, -205, 130, -215, 134, -30)
        ctx.curve_to(90, -80, -20, -95, -60, -70)
        ctx.curve_to(-90, -60, -110, -40, -132, -10)
        ctx.fill()
    elif style == "long":
        ctx.move_to(-136, 30)
        ctx.curve_to(-155, -210, 155, -210, 136, 30)
        ctx.curve_to(110, -60, 40, -90, 0, -95)
        ctx.curve_to(-40, -90, -110, -60, -136, 30)
        ctx.fill()
    elif style == "curly":
        for i in range(9):
            a = math.pi + i * math.pi / 8
            _ellipse(ctx, math.cos(a) * 112, math.sin(a) * 112 - 10, 42, 42)
            ctx.fill()
    elif style == "bun":
        _ellipse(ctx, 0, -150, 52, 48)
        ctx.fill()
        ctx.move_to(-132, 0)
        ctx.curve_to(-150, -205, 150, -205, 132, 0)
        ctx.curve_to(100, -80, -100, -80, -132, 0)
        ctx.fill()
    elif style == "cap":
        ctx.set_source_rgb(*th.ACCENT)
        ctx.move_to(-134, -40)
        ctx.curve_to(-130, -170, 130, -170, 134, -40)
        ctx.close_path()
        ctx.fill()
        _rrect(ctx, 40, -58, 150, 26, 13)
        ctx.fill()
        ctx.set_source_rgb(*c)
        _rrect(ctx, -134, -44, 40, 50, 16)
        ctx.fill()
    elif style == "bald":
        ctx.set_source_rgba(*c, 0.9)
        ctx.move_to(-130, 10)
        ctx.curve_to(-136, -40, -120, -60, -112, -60)
        ctx.line_to(-104, 20)
        ctx.close_path()
        ctx.fill()
        ctx.move_to(130, 10)
        ctx.curve_to(136, -40, 120, -60, 112, -60)
        ctx.line_to(104, 20)
        ctx.close_path()
        ctx.fill()


def _face(ctx, t, emotion, talking, seed, L):
    ink = (0.09, 0.08, 0.08)
    look_x = 14  # yüz bakılan yöne biraz kayık
    bl = _blink(t, seed)
    brow = {"happy": (-8, 0.12), "neutral": (0, 0.0), "surprised": (-22, 0.0), "sad": (-6, -0.35),
            "angry": (6, 0.38), "worried": (-10, -0.25)}.get(emotion, (0, 0))
    for sx in (-1, 1):
        ex, ey = look_x + sx * 44, -10
        ctx.set_source_rgb(*ink)
        _ellipse(ctx, ex, ey, 12, 18 * bl * (1.15 if emotion == "surprised" else 1))
        ctx.fill()
        if bl > 0.5:
            ctx.set_source_rgb(1, 1, 1)
            _ellipse(ctx, ex + 4, ey - 6, 4, 4)
            ctx.fill()
        # kaşlar: iç uç açıya göre yükselir/alçalır
        ctx.save()
        ctx.translate(ex, ey - 44 + brow[0])
        ctx.rotate(-sx * brow[1])
        ctx.set_source_rgb(*_shade(ink, 1.0))
        _rrect(ctx, -22, -5, 44, 10, 5)
        ctx.fill()
        ctx.restore()
    if L.get("extra") == "glasses":
        ctx.set_source_rgb(*ink)
        ctx.set_line_width(6)
        for sx in (-1, 1):
            _rrect(ctx, look_x + sx * 44 - 32, -38, 64, 52, 16)
            ctx.stroke()
        ctx.move_to(look_x - 12, -14)
        ctx.line_to(look_x + 12, -14)
        ctx.stroke()
    if L.get("extra") == "beard":
        ctx.set_source_rgb(*_rgb(HAIRS[L["hair"]]))
        ctx.move_to(-110, 20)
        ctx.curve_to(-100, 150, 100, 150, 110, 20)
        ctx.curve_to(60, 70, -60, 70, -110, 20)
        ctx.fill()
    # yanaklar
    if emotion in ("happy", "surprised"):
        ctx.set_source_rgba(*th.hex2rgb("#FF6B6B"), 0.22)
        for sx in (-1, 1):
            _ellipse(ctx, look_x + sx * 72, 30, 20, 12)
            ctx.fill()
    # ağız
    mo = _mouth_open(t, talking, seed)
    mx, my = look_x + 4, 62
    ctx.set_source_rgb(*_shade(ink, 1.6))
    if emotion == "surprised":
        _ellipse(ctx, mx, my, 16, 20 + mo * 6)
        ctx.fill()
    elif mo > 0.08:
        w = 30 if emotion != "sad" else 24
        ctx.move_to(mx - w, my - 4)
        ctx.curve_to(mx - w * 0.6, my + 30 * mo + 6, mx + w * 0.6, my + 30 * mo + 6, mx + w, my - 4)
        ctx.close_path()
        ctx.fill()
        ctx.set_source_rgb(*th.hex2rgb("#E8606A"))
        _ellipse(ctx, mx, my + 14 * mo, w * 0.45, 7 * mo)
        ctx.fill()
    else:
        curve = {"happy": 18, "neutral": 2, "sad": -16, "angry": -6, "worried": -8}.get(emotion, 6)
        ctx.set_line_width(7)
        ctx.set_line_cap(1)
        ctx.move_to(mx - 26, my)
        ctx.curve_to(mx - 12, my + curve, mx + 12, my + curve, mx + 26, my)
        ctx.stroke()


def bubble(ctx, text, x, y, w, t, start=0.0, tail_x=None, tail_y=None, size=40, kind="display"):
    """Konuşma balonu: (x, y) sol üst, metin yazılır gibi belirir. Balon yüksekliğini döner."""
    from . import draw as D
    p = ease_out_back(prog(t, start, 0.4), 2.0)
    if p <= 0:
        return 0
    lines = D.wrap(text, size, w - 70, kind)[:5]
    h = 50 + len(lines) * size * 1.3
    ctx.save()
    cx, cy = (tail_x if tail_x is not None else x + 60), (tail_y if tail_y is not None else y + h + 50)
    ctx.translate(cx, cy)
    ctx.scale(max(0.01, p), max(0.01, p))
    ctx.translate(-cx, -cy)
    ctx.set_source_rgba(0, 0, 0, 0.35)
    _rrect(ctx, x + 10, y + 12, w, h, 34)
    ctx.fill()
    ctx.set_source_rgb(*th.hex2rgb("#F2EBE1"))
    _rrect(ctx, x, y, w, h, 34)
    ctx.fill()
    if tail_x is not None:
        if x <= tail_x <= x + w:  # karakter balonun altında/üstünde
            bx, by = clamp(tail_x, x + 60, x + w - 60), (y + h if tail_y > y + h else y)
            b1, b2 = (bx - 26, by), (bx + 26, by)
        else:  # karakter yanda: kuyruk yan kenardan çıkar
            bx = x if tail_x < x else x + w
            by = clamp(tail_y, y + 40, y + h - 40)
            b1, b2 = (bx, by - 24), (bx, by + 24)
        dx, dy = tail_x - bx, tail_y - by
        d = math.hypot(dx, dy) or 1
        k = min(1.0, 150 / d)  # kuyruk en fazla 150 px
        ctx.move_to(*b1)
        ctx.line_to(bx + dx * k, by + dy * k)
        ctx.line_to(*b2)
        ctx.close_path()
        ctx.fill()
    ctx.set_source_rgb(*th.ACCENT)
    _rrect(ctx, x, y + 22, 8, h - 44, 4)
    ctx.fill()
    # metin harf harf yazılır
    total = sum(len(l) for l in lines)
    shown = int(total * clamp((t - start - 0.25) / max(0.6, total * 0.025)))
    for i, ln in enumerate(lines):
        part = ln[:max(0, shown)]
        shown -= len(ln)
        if part:
            D.draw_text(ctx, part, x + 40, y + 28 + size * 0.95 + i * size * 1.3, size, (0.09, 0.08, 0.08), kind=kind)
    ctx.restore()
    return h


def person_icon(ctx, x, y, h, color, alpha=1.0):
    """Piktogram insan: (x, y) ayak ortası, h boy."""
    ctx.set_source_rgba(*color, alpha)
    r = h * 0.19
    _ellipse(ctx, x, y - h + r, r, r)
    ctx.fill()
    _rrect(ctx, x - h * 0.28, y - h + 2.25 * r, h * 0.56, h - 2.25 * r, h * 0.2)
    ctx.fill()
