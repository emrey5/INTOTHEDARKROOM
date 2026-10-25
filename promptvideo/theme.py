"""Görsel tema: çözünürlük, stiller, yazı tipleri, easing fonksiyonları.

Stil `apply_style("modern")` gibi seçilir; vurgu ve arka plan rengi isteğe göre değiştirilebilir.
Diğer modüller değerleri `theme.TEXT` gibi modül üzerinden okur.

Sahneler her zaman 1920x1080 "tasarım alanında" çizilir; SCALE ile çıktı 720p'den 4K'ya kadar
keskin (vektörel) büyütülür. FPS 30 ya da 60 olabilir.
"""
import os

W, H = 1920, 1080  # tasarım alanı
FPS = 30
SCALE = 1.0  # çıktı = tasarım alanı x SCALE (720p: 2/3, 4K: 2)
QUALITIES = {"720": 2 / 3, "1080": 1.0, "1440": 4 / 3, "2160": 2.0}


def set_output(quality="1080", fps=30):
    global SCALE, FPS
    SCALE = QUALITIES.get(str(quality), 1.0)
    FPS = int(fps) if int(fps) in (24, 30, 60) else 30


def out_size():
    """Çıktı videosunun piksel boyutu (çift sayı, x264 için)."""
    return int(round(W * SCALE / 2)) * 2, int(round(H * SCALE / 2)) * 2
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
    # Belgesel: koyu kömür, altın vurgu, sakin ve ağırbaşlı
    "belgesel": dict(
        SKETCH=False,
        BG="#0E0C0A", BG2="#1E1912", TEXT="#F3EDE2", MUTED="#A39A8B", GRID="#2E271E",
        INK="#F3EDE2", ACCENT="#E0B04A", ACCENT2="#F2D59A", HILITE="#E0B04A",
        PALETTE=["#E0B04A", "#C9854A", "#8FA6A0", "#F2D59A", "#A0674B", "#D9CBB0", "#6E8B85", "#B89A6A"],
        FONTS=dict(body="Inter-Regular.ttf", bold="Inter-SemiBold.ttf", display="Inter-ExtraBold.ttf",
                   hand="Caveat-Bold.ttf"),
    ),
    # Haber: lacivert, kırmızı vurgu, güçlü ve net
    "haber": dict(
        SKETCH=False,
        BG="#06102A", BG2="#0E1F4A", TEXT="#FFFFFF", MUTED="#A8B6D8", GRID="#1E3266",
        INK="#FFFFFF", ACCENT="#E63946", ACCENT2="#FFFFFF", HILITE="#E63946",
        PALETTE=["#E63946", "#FFFFFF", "#4DA3FF", "#FFC857", "#8FB3FF", "#FF8A8A", "#3DDC97", "#C0C8E0"],
        FONTS=dict(body="Inter-Regular.ttf", bold="Inter-SemiBold.ttf", display="Inter-ExtraBold.ttf",
                   hand="Inter-SemiBold.ttf"),
    ),
    # Minimal: açık zemin, koyu yazı, tek vurgu rengi
    "minimal": dict(
        SKETCH=False, LIGHT=True,
        BG="#F6F5F1", BG2="#E9E7E0", TEXT="#16161A", MUTED="#6B6B73", GRID="#D3D0C6",
        INK="#16161A", ACCENT="#2F5BFF", ACCENT2="#7C9BFF", HILITE="#2F5BFF",
        PALETTE=["#2F5BFF", "#16161A", "#8A8F9C", "#FF5C39", "#5AA9E6", "#B9BCC6", "#2E2E38", "#7C8CFF"],
        FONTS=dict(body="Inter-Regular.ttf", bold="Inter-SemiBold.ttf", display="Inter-ExtraBold.ttf",
                   hand="Inter-SemiBold.ttf"),
    ),
    # Retro piksel: 8-bit oyun görünümü (kareler sonradan iri piksellere ve sınırlı palete indirgenir)
    "piksel": dict(
        SKETCH=False, PIXEL=True,
        BG="#1D1430", BG2="#2B1B4A", TEXT="#FFF1E8", MUTED="#C2C3C7", GRID="#3B2A5E",
        INK="#FFF1E8", ACCENT="#FF004D", ACCENT2="#FFA300", HILITE="#FF004D",
        PALETTE=["#FF004D", "#FFA300", "#FFEC27", "#00E436", "#29ADFF", "#FF77A8", "#83769C", "#FFCCAA"],
        FONTS=dict(body="JetBrainsMono-Bold.ttf", bold="JetBrainsMono-ExtraBold.ttf",
                   display="JetBrainsMono-ExtraBold.ttf", hand="JetBrainsMono-Bold.ttf"),
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

STYLE_NAMES = {"mekanik": "DARKROOM (siyah-turuncu)", "modern": "Modern (mor-mavi)", "belgesel": "Belgesel",
               "haber": "Haber", "minimal": "Minimal (açık)", "cizgi": "Çizgi film",
               "piksel": "Retro piksel (8-bit)"}

STYLE = "modern"
SKETCH = LIGHT = PIXEL = False
BG = BG2 = TEXT = MUTED = GRID = INK = ACCENT = ACCENT2 = HILITE = GLASS = (0, 0, 0)
PALETTE = []
FONTS = {}
_OPTS = {}


def apply_style(name, accent=None, bg=None):
    """Stili uygular. accent / bg: "#RRGGBB" ile stilin vurgu ve arka plan rengini değiştirir.
    Verilmezse bir önceki apply_style çağrısındaki renk seçimi korunur (accent="" ile sıfırlanır)."""
    global STYLE, SKETCH, LIGHT, PIXEL, BG, BG2, TEXT, MUTED, GRID, INK, ACCENT, ACCENT2, HILITE, GLASS, PALETTE, FONTS
    name = name if name in STYLES else "mekanik"
    if accent is not None:
        _OPTS["accent"] = accent
    if bg is not None:
        _OPTS["bg"] = bg
    s = STYLES[name]
    STYLE = name
    SKETCH = s["SKETCH"]
    PIXEL = s.get("PIXEL", False)
    BG, BG2, TEXT, MUTED, GRID, INK, ACCENT, ACCENT2, HILITE = (
        hex2rgb(s[k]) for k in ("BG", "BG2", "TEXT", "MUTED", "GRID", "INK", "ACCENT", "ACCENT2", "HILITE"))
    PALETTE = [hex2rgb(c) for c in s["PALETTE"]]
    FONTS = {k: os.path.join(FONT_DIR, v) for k, v in s["FONTS"].items()}
    if _OPTS.get("accent"):
        set_accent(_OPTS["accent"])
    if _OPTS.get("bg"):
        b = hex2rgb(_OPTS["bg"])
        BG, BG2 = b, mix(b, ACCENT, 0.10)
    LIGHT = luma(BG) > 0.55  # açık zeminde yazılar koyu olmalı
    if LIGHT != s.get("LIGHT", SKETCH) and not SKETCH:
        TEXT = INK = (0.09, 0.09, 0.1) if LIGHT else (0.96, 0.95, 0.93)
        MUTED = mix(TEXT, BG, 0.45)
    if not SKETCH:
        GRID = mix(BG, TEXT, 0.14)
    GLASS = (0, 0, 0) if LIGHT else (1, 1, 1)  # kartların ince dolgusu


def luma(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def set_accent(hexcol):
    """Vurgu rengini değiştirir; ikinci vurgu ve paletin ilk rengi de buna uyar."""
    global ACCENT, ACCENT2, HILITE, PALETTE
    a = hex2rgb(hexcol)
    old = ACCENT
    ACCENT = HILITE = a
    ACCENT2 = mix(a, (1, 1, 1), 0.4) if luma(a) < 0.7 else mix(a, (0, 0, 0), 0.3)
    PALETTE = [a] + [c for c in PALETTE if c != old][:7]




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


class scene_accent:
    """Tek bir sahne için vurgu rengini geçici olarak değiştirir: `with scene_accent("#FF0000"): ...`"""

    def __init__(self, hexcol):
        self.hex = hexcol

    def __enter__(self):
        self.saved = (ACCENT, ACCENT2, HILITE, list(PALETTE))
        if self.hex:
            try:
                set_accent(self.hex)
            except ValueError:
                pass
        return self

    def __exit__(self, *exc):
        global ACCENT, ACCENT2, HILITE, PALETTE
        ACCENT, ACCENT2, HILITE, PALETTE = self.saved
        return False


apply_style(os.environ.get("PV_STYLE", "mekanik"))
