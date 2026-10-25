"""Görsel tema: çözünürlük, iki stil (modern / çizgi), yazı tipleri, easing fonksiyonları.

Stil `apply_style("modern")` ya da `apply_style("cizgi")` ile seçilir; diğer modüller değerleri
`theme.TEXT` gibi modül üzerinden okur.
"""
import os

W, H = 1920, 1080
FPS = 30
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


STYLES = {
    # Koyu, parlak, sinematik bilgi grafiği
    "modern": dict(
        SKETCH=False,
        BG="#0A0E1F", BG2="#141A36", TEXT="#F4F6FF", MUTED="#9AA4C7", GRID="#2A3360",
        INK="#F4F6FF", ACCENT="#7C5CFF", ACCENT2="#00D4FF", HILITE="#7C5CFF",
        PALETTE=["#7C5CFF", "#00D4FF", "#FF5C8A", "#FFC857", "#3DDC97", "#FF8A3D", "#B07CFF", "#4DA3FF"],
        FONTS=dict(body="Inter-Regular.ttf", bold="Inter-SemiBold.ttf", display="Inter-ExtraBold.ttf",
                   hand="Caveat-Bold.ttf"),
    ),
    # Siyah-turuncu, mekanik/terminal görünümü (uygulama temasıyla aynı)
    "mekanik": dict(
        SKETCH=False,
        BG="#050505", BG2="#120A04", TEXT="#F2EBE1", MUTED="#8C8277", GRID="#2A2018",
        INK="#F2EBE1", ACCENT="#FF7A1A", ACCENT2="#FFB066", HILITE="#FF7A1A",
        PALETTE=["#FF7A1A", "#FFB066", "#C2560E", "#FFD2A1", "#8C3B06", "#E8E2D9", "#FF9A3D", "#6E5B4A"],
        FONTS=dict(body="Inter-Regular.ttf", bold="JetBrainsMono-Bold.ttf", display="Inter-ExtraBold.ttf",
                   hand="JetBrainsMono-Regular.ttf"),
    ),
    # Kâğıt üstüne elle çizilmiş çizgi film / doodle görünümü
    "cizgi": dict(
        SKETCH=True,
        BG="#FBF5E9", BG2="#F3EAD7", TEXT="#1F1B2E", MUTED="#5B5470", GRID="#CFC3AA",
        INK="#1F1B2E", ACCENT="#FF6B6B", ACCENT2="#4E7CFF", HILITE="#FFD93D",
        PALETTE=["#FF6B6B", "#4E7CFF", "#FFD93D", "#2EC4B6", "#A66CFF", "#FF9F43", "#7BD389", "#FF8FC7"],
        FONTS=dict(body="Baloo2-SemiBold.ttf", bold="Baloo2-SemiBold.ttf", display="Baloo2-ExtraBold.ttf",
                   hand="Caveat-Bold.ttf"),
    ),
}

STYLE = "modern"
SKETCH = False
BG = BG2 = TEXT = MUTED = GRID = INK = ACCENT = ACCENT2 = HILITE = (0, 0, 0)
PALETTE = []
FONTS = {}


def apply_style(name):
    global STYLE, SKETCH, BG, BG2, TEXT, MUTED, GRID, INK, ACCENT, ACCENT2, HILITE, PALETTE, FONTS
    s = STYLES[name]
    STYLE = name
    SKETCH = s["SKETCH"]
    BG, BG2, TEXT, MUTED, GRID, INK, ACCENT, ACCENT2, HILITE = (
        hex2rgb(s[k]) for k in ("BG", "BG2", "TEXT", "MUTED", "GRID", "INK", "ACCENT", "ACCENT2", "HILITE"))
    PALETTE = [hex2rgb(c) for c in s["PALETTE"]]
    FONTS = {k: os.path.join(FONT_DIR, v) for k, v in s["FONTS"].items()}


apply_style(os.environ.get("PV_STYLE", "cizgi"))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_cubic(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_cubic(x):
    x = clamp(x)
    return x ** 3


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.7):
    x = clamp(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def ease_out_expo(x):
    x = clamp(x)
    return 1 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_out_elastic(x):
    import math
    x = clamp(x)
    if x in (0, 1):
        return x
    return 2 ** (-10 * x) * math.sin((x * 10 - 0.75) * (2 * math.pi) / 3) + 1


def prog(t, start, dur):
    """t anında [start, start+dur] aralığındaki ilerleme (0..1)."""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return clamp((t - start) / dur)


def lerp(a, b, x):
    return a + (b - a) * x


def mix(c1, c2, x):
    return tuple(lerp(a, b, x) for a, b in zip(c1, c2))


def fmt_num(v, lang="tr", decimals=None):
    """Sayıyı okunur biçimde yazar: 85300000 -> '85,3 milyon'."""
    if v is None:
        return ""
    av = abs(v)
    units = {"tr": [(1e12, " trilyon"), (1e9, " milyar"), (1e6, " milyon")],
             "en": [(1e12, "T"), (1e9, "B"), (1e6, "M")]}.get(lang, [])
    suffix = ""
    for div, name in units:
        if av >= div:
            v, suffix = v / div, name
            break
    if decimals is None:
        decimals = 0 if abs(v) >= 100 or float(v).is_integer() else (1 if abs(v) >= 10 else 2)
    s = f"{v:,.{decimals}f}"
    if lang == "tr":
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s + suffix
