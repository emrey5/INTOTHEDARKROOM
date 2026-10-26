"""DARKROOM: masaüstü uygulaması (PySide6).

Akış: konu yaz -> senaryoyu hazırla (araştırma + plan) -> sahneleri gözden geçir/düzenle ->
videoyu oluştur (canlı önizleme ile) -> videoyu aç.
"""
import datetime
import json
import os
import re
import sys
import threading

from PySide6.QtCore import Qt, QThread, Signal, QSettings, QUrl, QSize, QTimer
from PySide6.QtGui import QImage, QPixmap, QDesktopServices, QIcon, QFont, QFontDatabase, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel,
    QPlainTextEdit, QPushButton, QComboBox, QLineEdit, QFileDialog, QProgressBar, QTabWidget,
    QListWidget, QListWidgetItem, QFrame, QMessageBox, QSplitter, QSizePolicy, QCheckBox,
    QFormLayout, QDoubleSpinBox, QToolButton, QScrollArea, QButtonGroup, QInputDialog, QStackedWidget,
    QSlider, QDialog, QColorDialog, QDialogButtonBox, QAbstractItemView)

from . import theme, pipeline, planner, scenes, updater, userdata, __version__
from .waitscreen import WaitScreen
from . import ollama_setup, autoset, kinds
from . import draw as D
from .render import render_frame

APP_NAME = "DARKROOM"
HERE = os.path.dirname(os.path.abspath(__file__))

SCENE_TYPES = {
    "title": "Başlık", "bullets": "Madde listesi", "stat": "Büyük sayı", "bar": "Çubuk grafik",
    "line": "Çizgi grafik", "pie": "Pasta grafik", "table": "Tablo", "image": "Görsel",
    "video": "Video klip", "character": "Karakter konuşur", "versus": "Karşılaştırma (VS)",
    "people": "İnsan piktogramı", "map": "Harita", "timeline": "Zaman çizelgesi",
    "compare": "Önce / sonra", "kinetic": "Kinetik yazı", "outro": "Kapanış",
}
SCENE_ICONS = {"title": "✦", "bullets": "☰", "stat": "#", "bar": "▤", "line": "📈", "pie": "◔",
               "table": "▦", "image": "🖼", "video": "🎬", "character": "☺", "versus": "⚔",
               "people": "☷", "map": "🗺", "timeline": "⏱", "compare": "⇄", "kinetic": "Aa", "outro": "★"}
VOICES_BY_LANG = {
    "tr": [("Ahmet (erkek)", "tr-TR-AhmetNeural"), ("Emel (kadın)", "tr-TR-EmelNeural"), ("Sessiz", "")],
    "en": [("Andrew (erkek)", "en-US-AndrewNeural"), ("Ava (kadın)", "en-US-AvaNeural"),
           ("Ryan (erkek, İngiliz)", "en-GB-RyanNeural"), ("Sonia (kadın, İngiliz)", "en-GB-SoniaNeural"), ("Sessiz", "")],
}
VOICES = VOICES_BY_LANG["tr"]
MUSIC_MODES = [("Yok", ""), ("Otomatik · Sakin", "auto:sakin"), ("Otomatik · Enerjik", "auto:enerjik"),
               ("Otomatik · Gizemli", "auto:gizemli"), ("Otomatik · Epik", "auto:epik"),
               ("Otomatik · Gerilim", "auto:gerilim"), ("Otomatik · Retro (8-bit)", "auto:retro"),
               ("Kendi dosyam…", "file")]
# videodaki vurgu ve arka plan renkleri ("" = stilin kendi rengi)
ACCENT_SWATCHES = [("", "Stilin rengi"), ("#FF7A1A", "Turuncu"), ("#3D8BFF", "Mavi"), ("#2ED47A", "Yeşil"),
                   ("#9B6BFF", "Mor"), ("#FF3B4E", "Kırmızı"), ("#E0B04A", "Altın"), ("#FF5CA8", "Pembe"),
                   ("#00C2C7", "Turkuaz")]
BG_SWATCHES = [("", "Stilin arka planı"), ("#050505", "Siyah"), ("#0A1230", "Lacivert"), ("#0B1A12", "Koyu yeşil"),
               ("#1A0E1F", "Mürdüm"), ("#1C1C1E", "Antrasit"), ("#F6F5F1", "Beyaz"), ("#FBF3E4", "Krem")]
# hazır stiller: tek tıkla birden çok ayarı birlikte değiştirir
PRESETS = {
    "belgesel": ("BELGESEL", "Altın vurgu, sakin müzik, ağır tempo, alt yazı",
                 dict(style="belgesel", accent="", bg="", music_mode="auto:sakin", tempo="yavas", subs="1",
                      sub_size="orta", sub_box="kutu", sfx="1", vertical="0", square="0")),
    "haber": ("HABER", "Lacivert-kırmızı, enerjik müzik, net altyazı",
              dict(style="haber", accent="", bg="", music_mode="auto:enerjik", tempo="normal", subs="1",
                   sub_size="orta", sub_box="vurgu", sfx="1", vertical="0", square="0")),
    "sosyal": ("SOSYAL", "Kısa, hızlı, büyük altyazı, dikey ve kare sürüm",
               dict(style="modern", accent="#FF5CA8", bg="", music_mode="auto:enerjik", tempo="hizli", subs="1",
                    sub_size="buyuk", sub_box="vurgu", length="kisa", sfx="1", vertical="1", square="1")),
    "minimal": ("MİNİMAL", "Açık zemin, tek renk, sade, efektsiz",
                dict(style="minimal", accent="", bg="", music_mode="auto:sakin", tempo="normal", subs="1",
                     sub_size="orta", sub_box="golge", sfx="0", vertical="0", square="0")),
    "darkroom": ("DARKROOM", "Siyah-turuncu, mekanik, gizemli müzik",
                 dict(style="mekanik", accent="", bg="", music_mode="auto:gizemli", tempo="normal", subs="1",
                      sub_size="orta", sub_box="kutu", sfx="1", vertical="0", square="0")),
    "cizgi": ("ÇİZGİ FİLM", "Kâğıt üstüne elle çizim, neşeli ve enerjik",
              dict(style="cizgi", accent="", bg="", music_mode="auto:enerjik", tempo="normal", subs="1",
                   sub_size="orta", sub_box="kutu", sfx="1", vertical="0", square="0")),
}
STYLE_SAMPLE = {"type": "bar", "kicker": "Örnek", "title": "Stil önizlemesi", "unit": "",
                "data": [{"label": "Birinci", "value": 9}, {"label": "İkinci", "value": 6}, {"label": "Üçüncü", "value": 4}],
                "narration": "Altyazı böyle görünecek.", "duration": 8}
SAMPLE_SCENES = {
    "title": {"type": "title", "title": "Örnek Başlık", "subtitle": "Alt başlık burada"},
    "bullets": {"type": "bullets", "kicker": "Öne çıkanlar", "title": "Başlık", "items": ["Birinci madde", "İkinci madde"]},
    "stat": {"type": "stat", "kicker": "Etiket", "value": 42, "suffix": "", "label": "açıklama"},
    "bar": {"type": "bar", "kicker": "Karşılaştırma", "title": "Başlık", "unit": "",
            "data": [{"label": "A", "value": 10}, {"label": "B", "value": 7}]},
    "line": {"type": "line", "kicker": "Zaman", "title": "Başlık", "unit": "",
             "series": [{"name": "Seri", "data": [{"x": "2020", "y": 1}, {"x": "2021", "y": 3}]}]},
    "pie": {"type": "pie", "kicker": "Dağılım", "title": "Başlık",
            "data": [{"label": "A", "value": 60}, {"label": "B", "value": 40}]},
    "table": {"type": "table", "kicker": "Tablo", "title": "Başlık", "columns": ["Ad", "Değer"],
              "rows": [["A", "1"], ["B", "2"]]},
    "image": {"type": "image", "kicker": "", "caption": "Açıklama", "image_query": "landscape"},
    "video": {"type": "video", "kicker": "", "caption": "Açıklama", "stock_query": "city"},
    "character": {"type": "character", "kicker": "", "backdrop": "studio", "characters": [{"look": 0, "pose": "talk", "emotion": "happy"}],
                  "say": [{"who": 0, "text": "Merhaba! Bugün ilginç bir konuya bakıyoruz."}]},
    "versus": {"type": "versus", "kicker": "Karşılaştırma", "title": "Başlık", "unit": "", "backdrop": "studio",
               "left": {"label": "A", "value": 10}, "right": {"label": "B", "value": 7}},
    "people": {"type": "people", "kicker": "Oran", "title": "Başlık", "value": 30, "total": 100,
               "label": "Her 100 kişiden 30'u"},
    "map": {"type": "map", "map": "turkey", "kicker": "Türkiye", "title": "Başlık", "unit": "",
            "data": [{"label": "İstanbul", "value": 15.7}, {"label": "Ankara", "value": 5.8}], "presenter": True},
    "timeline": {"type": "timeline", "kicker": "Zaman çizelgesi", "title": "Başlık",
                 "events": [{"year": "1923", "text": "Birinci olay"}, {"year": "1950", "text": "İkinci olay"},
                            {"year": "2000", "text": "Üçüncü olay"}]},
    "compare": {"type": "compare", "kicker": "Önce / sonra", "title": "Başlık", "unit": "",
                "before": {"label": "2000", "value": 10, "text": ""}, "after": {"label": "2024", "value": 25, "text": ""}},
    "kinetic": {"type": "kinetic", "kicker": "Biliyor muydunuz?", "narration": "Kahve 15. yüzyılda Yemen'de içilmeye başlandı."},
    "outro": {"type": "outro", "title": "İzlediğiniz için teşekkürler", "sources": []},
}
COMMON_KEYS = ("type", "kicker", "title", "narration", "duration", "accent")

# Arayüz teması: mekanik, derin siyah tonlar + turuncu vurgu (Ayarlar'dan açık tema ve başka vurgu seçilebilir)
APP_ACCENTS = {"turuncu": "#FF7A1A", "mavi": "#3D8BFF", "yesil": "#2ED47A", "mor": "#9B6BFF", "kirmizi": "#FF3B4E",
               "altin": "#E0B04A"}
PALETTES = {
    "koyu": dict(
        bg="#050505", panel="#0B0B0B", panel2="#111111", field="#070707", line="#1F1F1F", line2="#2B2B2B",
        text="#E6DED3", muted="#7D746A", dim="#4A443E", warn="#FF4D1A", deep="#000000", shadow="#000000",
        btn1="#232323", btn2="#1A1A1A", btn3="#121212", btn4="#0A0A0A", btnb="#2E2E2E", btnt="#3A3A3A",
        press1="#050505", press2="#141414", disbg="#0C0C0C", disb="#191919", disb2="#1C1C1C", disl="#2A2A2A",
        pri1="#262626", pri2="#1B1B1B", pri3="#111111", pri4="#080808", handle="#262626", seltext="#000000",
        dangerb="#4A1A08", hi="#FFFFFF", tile=True),
    "acik": dict(
        bg="#F2F0EB", panel="#FAF9F6", panel2="#FFFFFF", field="#FFFFFF", line="#DDD8CE", line2="#CFC9BD",
        text="#1E1B18", muted="#6F675D", dim="#ABA397", warn="#D8341A", deep="#FFFFFF", shadow="#BDB6AA",
        btn1="#FFFFFF", btn2="#FAF8F4", btn3="#F1EEE8", btn4="#E7E3DB", btnb="#CFC9BD", btnt="#FFFFFF",
        press1="#E2DDD3", press2="#EEEAE3", disbg="#EEEBE5", disb="#DDD8CE", disb2="#DDD8CE", disl="#CFC9BD",
        pri1="#FFFFFF", pri2="#FBF9F5", pri3="#F3F0EA", pri4="#EAE6DE", handle="#CFC9BD", seltext="#FFFFFF",
        dangerb="#F0B8A8", hi="#1E1B18", tile=False),
}
C = {}


def _hex_mix(c1, c2, x):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(p + (q - p) * x):02X}" for p, q in zip(a, b))


def set_app_theme(mode="koyu", accent="turuncu"):
    """Arayüz renklerini hazırlar (koyu / açık, vurgu rengi)."""
    pal = PALETTES.get(mode, PALETTES["koyu"])
    acc = APP_ACCENTS.get(accent, accent if str(accent).startswith("#") else APP_ACCENTS["turuncu"])
    C.clear()
    C.update(pal, mode=mode, orange=acc, orange2=_hex_mix(acc, "#FFFFFF", 0.25), orange3=_hex_mix(acc, pal["bg"], 0.35))
    for k, x in (("tint1", 0.07), ("tint2", 0.05), ("tint3", 0.04), ("tint4", 0.10), ("tint5", 0.08)):
        C[k] = _hex_mix(pal["bg"], acc, x)


set_app_theme()

QSS = """
* { font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 14px; color: %(text)s; }
QMainWindow, QDialog { background: %(bg)s; }
QWidget#root { background-color: %(bg)s; %(tile_rule)s }
QFrame#side { background: %(panel)s; border-right: 1px solid %(line)s; }
QLabel#brand { font-family: 'JetBrains Mono'; font-size: 21px; font-weight: 800; color: %(orange)s; letter-spacing: 2px; }
QLabel#brandsub { font-family: 'JetBrains Mono'; color: %(muted)s; font-size: 11px; }
QLabel[class="section"] { font-family: 'JetBrains Mono'; color: %(orange)s; font-size: 11px; font-weight: 700;
    letter-spacing: 2px; margin-top: 12px; padding-bottom: 2px; border-bottom: 1px solid %(line)s; }
QPlainTextEdit, QLineEdit, QComboBox, QDoubleSpinBox, QListWidget {
    background: %(field)s; border: 1px solid %(line2)s; border-top: 1px solid %(shadow)s; border-radius: 3px;
    padding: 8px; selection-background-color: %(orange)s; selection-color: %(seltext)s; }
QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border: 1px solid %(orange)s; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url(%(arrow_down)s); width: 12px; height: 12px; margin-right: 8px; }
QDoubleSpinBox::up-arrow { image: url(%(arrow_up)s); width: 10px; height: 10px; }
QDoubleSpinBox::down-arrow { image: url(%(arrow_down)s); width: 10px; height: 10px; }
QComboBox QAbstractItemView { background: %(panel2)s; border: 1px solid %(orange3)s; outline: none;
    selection-background-color: %(orange)s; selection-color: %(seltext)s; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { background: %(panel2)s; border-left: 1px solid %(line2)s; width: 18px; }

/* mekanik düğmeler: metal gövde, üstte ince ışık, basınca içe göçer */
QPushButton {
    font-family: 'JetBrains Mono'; font-weight: 700; font-size: 13px; letter-spacing: 1px; color: %(text)s;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 %(btn1)s, stop:0.08 %(btn2)s, stop:0.5 %(btn3)s, stop:1 %(btn4)s);
    border: 1px solid %(btnb)s; border-bottom: 2px solid %(shadow)s; border-top: 1px solid %(btnt)s;
    border-radius: 3px; padding: 9px 14px; }
QPushButton:hover { color: %(orange2)s; border: 1px solid %(orange3)s; border-bottom: 2px solid %(shadow)s; }
QPushButton:pressed { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 %(press1)s, stop:1 %(press2)s);
    border-top: 2px solid %(shadow)s; border-bottom: 1px solid %(btnb)s; padding-top: 10px; padding-bottom: 8px; }
QPushButton:disabled { color: %(dim)s; background: %(disbg)s; border: 1px solid %(disb)s; }
QPushButton#primary {
    color: %(orange)s; font-size: 14px; padding: 13px; letter-spacing: 2px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 %(pri1)s, stop:0.07 %(pri2)s, stop:0.55 %(pri3)s, stop:1 %(pri4)s);
    border: 1px solid %(orange3)s; border-left: 4px solid %(orange)s; border-bottom: 2px solid %(shadow)s; }
QPushButton#primary:hover { color: %(seltext)s; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 %(orange2)s, stop:1 %(orange)s);
    border: 1px solid %(orange2)s; border-left: 4px solid %(hi)s; }
QPushButton#primary:pressed { color: %(seltext)s; background: %(orange3)s; }
QPushButton#primary:disabled { color: %(dim)s; border: 1px solid %(disb2)s; border-left: 4px solid %(disl)s; background: %(disbg)s; }
QPushButton#danger { color: %(warn)s; border: 1px solid %(dangerb)s; border-left: 4px solid %(warn)s; }
QPushButton#chip { font-family: 'Inter'; font-weight: 500; font-size: 12px; letter-spacing: 0; text-align: left;
    padding: 6px 10px; color: %(muted)s; background: %(field)s; border: 1px solid %(line)s; border-radius: 2px; }
QPushButton#chip:hover { color: %(orange2)s; border-color: %(orange3)s; }
QPushButton#preset { font-size: 12px; padding: 10px 6px; text-align: center; }
QPushButton#preset:checked { color: %(orange)s; border: 1px solid %(orange)s; border-bottom: 3px solid %(orange)s; background: %(tint1)s; }
QToolButton#seg { font-family: 'JetBrains Mono'; font-weight: 700; font-size: 11px; letter-spacing: 1px; color: %(muted)s;
    background: %(field)s; border: 1px solid %(line2)s; border-radius: 2px; padding: 8px 4px; }
QToolButton#seg:hover { color: %(orange2)s; border-color: %(orange3)s; }
QToolButton#seg:checked { color: %(orange)s; border: 1px solid %(orange)s; border-bottom: 3px solid %(orange)s; background: %(tint1)s; }
QToolButton#swatch { border: 2px solid %(line2)s; border-radius: 3px; min-width: 30px; min-height: 30px; }
QToolButton#swatch:hover { border-color: %(orange2)s; }
QToolButton#swatch:checked { border: 3px solid %(text)s; }
QCheckBox { spacing: 8px; font-family: 'JetBrains Mono'; font-size: 12px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid %(line2)s; background: %(field)s; border-radius: 2px; }
QCheckBox::indicator:checked { background: %(orange)s; border-color: %(orange)s; }
QSlider::groove:horizontal { height: 6px; background: %(deep)s; border: 1px solid %(line2)s; border-radius: 2px; }
QSlider::sub-page:horizontal { background: %(orange)s; border-radius: 2px; }
QSlider::handle:horizontal { background: %(text)s; width: 12px; margin: -6px 0; border-radius: 2px; }

QTabWidget::pane { border: none; }
QTabBar::tab { font-family: 'JetBrains Mono'; background: transparent; color: %(muted)s; padding: 12px 20px;
    font-weight: 700; letter-spacing: 2px; border-bottom: 2px solid %(line)s; }
QTabBar::tab:hover { color: %(text)s; }
QTabBar::tab:selected { color: %(orange)s; border-bottom: 2px solid %(orange)s; background: %(tint2)s; }

/* segmentli ilerleme göstergesi */
QProgressBar { background: %(deep)s; border: 1px solid %(line2)s; border-radius: 2px; height: 16px; padding: 2px; }
QProgressBar::chunk { background: %(orange)s; width: 9px; margin: 0 1px; }

QLabel#preview { background: #000000; border: 1px solid %(line)s; border-radius: 2px; }
QLabel#status { font-family: 'JetBrains Mono'; color: %(muted)s; font-size: 12px; }
QLabel#hint { color: %(muted)s; font-size: 12px; }
QLabel[class="step"] { font-family: 'JetBrains Mono'; color: %(dim)s; font-weight: 700; font-size: 12px; }
QLabel[class="stepon"] { font-family: 'JetBrains Mono'; color: %(orange)s; font-weight: 800; font-size: 12px; }
QLabel[class="stepdone"] { font-family: 'JetBrains Mono'; color: %(text)s; font-weight: 700; font-size: 12px; }
QPlainTextEdit#log { font-family: 'JetBrains Mono'; font-size: 12px; color: %(orange2)s; background: %(deep)s; }
QListWidget { outline: none; }
QListWidget::item { padding: 10px; border-left: 2px solid transparent; margin: 1px 0; }
QListWidget::item:hover { background: %(tint3)s; }
QListWidget::item:selected { background: %(tint4)s; color: %(orange)s; border-left: 2px solid %(orange)s; }
QScrollBar:vertical { background: %(bg)s; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: %(handle)s; min-height: 30px; border-radius: 1px; }
QScrollBar::handle:vertical:hover { background: %(orange3)s; }
QScrollBar:horizontal { background: %(bg)s; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: %(handle)s; min-width: 30px; border-radius: 1px; }
QScrollBar::handle:horizontal:hover { background: %(orange3)s; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QLabel#formlabel { font-family: 'JetBrains Mono'; color: %(muted)s; font-size: 12px; letter-spacing: 1px; }
QFrame#banner { background: %(tint5)s; border: 1px solid %(orange3)s; border-left: 4px solid %(orange)s; border-radius: 2px; }
QFrame#group { background: %(panel)s; border: 1px solid %(line)s; border-radius: 3px; }
QLabel#bannertext { font-family: 'JetBrains Mono'; color: %(orange)s; font-weight: 700; letter-spacing: 1px; }
QToolTip { background: %(panel2)s; color: %(orange2)s; border: 1px solid %(orange3)s; font-family: 'JetBrains Mono'; }
"""


def app_stylesheet():
    def asset(name):
        return os.path.join(HERE, "assets", name).replace("\\", "/")
    tile = f"background-image: url({asset('bg_tile.png')});" if C.get("tile") else "background-image: none;"
    return QSS % dict(C, tile_rule=tile, arrow_down=asset("arrow_down.png"), arrow_up=asset("arrow_up.png"))


def pil_to_pixmap(im):
    im = im.convert("RGB")
    qi = QImage(im.tobytes("raw", "RGB"), im.width, im.height, 3 * im.width, QImage.Format_RGB888)
    return QPixmap.fromImage(qi.copy())


def render_still(scene, style, t=None, size=(960, 540), accent="", bg="", subs=None):
    """Tek bir sahnenin bir karesini (varsayılan: animasyonlar bitmişken) çizer.
    subs: altyazı ayarları verilirse anlatım altyazı olarak da çizilir."""
    from PIL import Image
    theme.apply_style(style, accent=accent or "", bg=bg or "")
    key = (style, bg)
    D._paper = None if getattr(render_still, "_key", None) != key else D._paper
    render_still._key = key
    sc = dict(scene)
    sc.setdefault("duration", 8)
    dur = float(sc["duration"])
    t = dur * 0.6 if t is None else t
    if subs is not None:
        D.SUB_OPTS = dict(D.SUB_OPTS, **subs)
        sc["_subs"], sc["_speech"] = True, dur * 2  # tüm süre boyunca altyazı görünsün
    surf, ctx = D.new_surface(scale=max(0.3, size[0] / theme.W))  # küçük önizleme küçük çizilir, hızlıdır
    try:
        if sc.get("type") == "image" and sc.get("image_path") and not os.path.exists(sc["image_path"]):
            sc.pop("image_path")
        render_frame(ctx, sc, t, dur, t, dur, 0, 1, None)
    except Exception as e:  # yarım düzenlenmiş sahne çizilemezse uygulama çökmesin
        D.background(ctx, 0)
        D.draw_text(ctx, f"Önizleme çizilemedi: {e}", 120, 540, 36, theme.ACCENT)
    surf.flush()
    im = Image.frombuffer("RGBA", (surf.get_width(), surf.get_height()), bytes(surf.get_data()),
                          "raw", "BGRA", 0, 1)
    return im.resize(size, Image.LANCZOS)


def slugify(s):
    s = s.lower()
    for a, b in zip("çğıöşüâî", "cgiosuai"):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or "video"


class ColorRow(QWidget):
    """Renk örnekleri + "özel renk" düğmesi. value(): "#RRGGBB" ya da "" (stilin kendi rengi)."""
    changed = Signal(str)

    def __init__(self, swatches, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(5)
        self.grp = QButtonGroup(self)
        self.grp.setExclusive(True)
        self.custom_hex = ""
        for hexcol, name in swatches:
            b = self._swatch(hexcol, name)
            h.addWidget(b)
        self.btn_custom = self._swatch("custom", "Kendi rengini seç…")
        self.btn_custom.setText("＋")
        self.btn_custom.clicked.connect(self.pick_custom)
        h.addWidget(self.btn_custom)
        h.addStretch(1)
        self.grp.buttons()[0].setChecked(True)
        self.grp.buttonClicked.connect(lambda b: b is not self.btn_custom and self.changed.emit(self.value()))

    def _swatch(self, hexcol, name):
        b = QToolButton(objectName="swatch")
        b.setCheckable(True)
        b.setToolTip(name)
        b.setProperty("hex", hexcol)
        if hexcol in ("", "custom"):
            b.setText("∅" if hexcol == "" else "＋")
        else:
            b.setStyleSheet(f"QToolButton#swatch {{ background: {hexcol}; }}")
        self.grp.addButton(b)
        return b

    def pick_custom(self):
        c = QColorDialog.getColor(QColor(self.custom_hex or "#FF7A1A"), self, "Renk seç")
        if c.isValid():
            self.set_value(c.name().upper())
            self.changed.emit(self.value())
        else:
            self.set_value(self.value())

    def value(self):
        b = self.grp.checkedButton()
        if not b:
            return ""
        return self.custom_hex if b is self.btn_custom else b.property("hex")

    def set_value(self, hexcol):
        hexcol = (hexcol or "").upper()
        for b in self.grp.buttons():
            if b is not self.btn_custom and (b.property("hex") or "").upper() == hexcol:
                b.setChecked(True)
                return
        self.custom_hex = hexcol
        self.btn_custom.setChecked(True)
        self.btn_custom.setStyleSheet(f"QToolButton#swatch {{ background: {hexcol}; color: #000000; }}")


class SettingsDialog(QDialog):
    """Uygulama ayarları: tema, vurgu rengi, açılış efekti, kayıt klasörü."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle(f"{APP_NAME} · Ayarlar")
        self.setMinimumWidth(560)
        st = win.settings
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(8)
        v.addWidget(win._section("Uygulama teması"))
        self.mode = win._segmented([("koyu", "KOYU"), ("acik", "AÇIK")], st.value("app_mode", "koyu"), v, self)
        v.addWidget(win._section("Uygulama vurgu rengi"))
        names = {"turuncu": "TURUNCU", "mavi": "MAVİ", "yesil": "YEŞİL", "mor": "MOR", "kirmizi": "KIRMIZI",
                 "altin": "ALTIN"}
        self.accent = win._segmented([(k, names[k]) for k in APP_ACCENTS], st.value("app_accent", "turuncu"), v, self)
        v.addWidget(win._section("Açılış efekti"))
        self.splash = win._segmented([("1", "AÇIK"), ("0", "KAPALI")], st.value("splash", "1"), v, self)
        v.addWidget(win._section("Açılış sesi"))
        self.sound = win._segmented([("1", "AÇIK"), ("0", "KAPALI")], st.value("splash_sound", "1"), v, self)
        v.addWidget(win._section("Kayıt klasörü"))
        h = QHBoxLayout()
        self.outdir = QLineEdit(win.outdir.text())
        ob = QPushButton("Seç")
        ob.clicked.connect(self.pick_outdir)
        h.addWidget(self.outdir, 1)
        h.addWidget(ob)
        v.addLayout(h)
        v.addWidget(win._section("Senaryo yazan yapay zekâ"))
        hint = QLabel("Model seçimi ve kurulum sol paneldeki “Senaryo yazan yapay zekâ” bölümündedir.", objectName="hint")
        hint.setWordWrap(True)
        v.addWidget(hint)
        v.addSpacing(10)
        bb = QDialogButtonBox()
        ok = bb.addButton("KAYDET", QDialogButtonBox.AcceptRole)
        ok.setObjectName("primary")
        bb.addButton("VAZGEÇ", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        for g in (self.mode, self.accent):  # tema anında denensin
            g.buttonClicked.connect(lambda _: self.preview_theme())
        self._old = (st.value("app_mode", "koyu"), st.value("app_accent", "turuncu"))

    def pick_outdir(self):
        p = QFileDialog.getExistingDirectory(self, "Kayıt klasörü", self.outdir.text())
        if p:
            self.outdir.setText(p)

    def preview_theme(self):
        set_app_theme(self.mode.value(), self.accent.value())
        QApplication.instance().setStyleSheet(app_stylesheet())

    def reject(self):
        set_app_theme(*self._old)
        QApplication.instance().setStyleSheet(app_stylesheet())
        super().reject()

    def accept(self):
        st = self.win.settings
        st.setValue("app_mode", self.mode.value())
        st.setValue("app_accent", self.accent.value())
        st.setValue("splash", self.splash.value())
        st.setValue("splash_sound", self.sound.value())
        if self.outdir.text().strip():
            self.win.outdir.setText(self.outdir.text().strip())
            st.setValue("outdir", self.outdir.text().strip())
            self.win.refresh_library()
        self.preview_theme()
        super().accept()


# --- Arka plan işçisi --------------------------------------------------------

class Worker(QThread):
    log = Signal(str)
    stage = Signal(int, int, str)
    progress = Signal(float)
    preview = Signal(object)
    planned = Signal(object)
    researched = Signal(object)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, mode, prompt=None, plan=None, out_dir="", opts=None, findings=None):
        super().__init__()
        self.mode, self.prompt, self.plan, self.out_dir, self.opts = mode, prompt, plan, out_dir, opts or {}
        self.findings = findings
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        w = self

        class CB(pipeline.Callbacks):
            def log(self, msg):
                w.log.emit(str(msg))

            def stage(self, i, n, label):
                w.stage.emit(i, n, label)

            def progress(self, frac):
                w.progress.emit(float(frac))

            def preview(self, im):
                w.preview.emit(im.resize((960, 540)))

            def cancelled(self):
                return w._cancel.is_set()

        cb = CB()

        class Stream:  # webdata/tts içindeki print'leri de günlüğe aktar
            def write(self, s):
                if s.strip():
                    w.log.emit(s.rstrip())

            def flush(self):
                pass

        old = sys.stdout
        sys.stdout = Stream()
        try:
            if self.mode == "research":
                self.researched.emit(pipeline.research_topic(self.prompt, self.out_dir, self.opts.get("lang", "tr"), cb=cb))
            elif self.mode == "plan":
                plan = pipeline.write_plan(self.prompt, self.findings, self.out_dir, self.opts.get("lang", "tr"), cb=cb,
                                           length=self.opts.get("length", "orta"), kind=self.opts.get("kind"))
                self.planned.emit(plan)
            else:
                o = self.opts
                out = pipeline.render_plan(self.plan, self.out_dir, o.get("style"), o.get("voice") or None,
                                           o.get("music") or None, not o.get("voice"), o.get("lang", "tr"), cb=cb,
                                           subtitles=o.get("subtitles", False), sfx=o.get("sfx", True),
                                           vertical=o.get("vertical", False), square=o.get("square", False),
                                           quality=o.get("quality", "1080"), fps=o.get("fps", 30),
                                           tempo=o.get("tempo", "normal"), accent=o.get("accent"), bg=o.get("bg"),
                                           sub_opts=o.get("sub_opts"), music_vol=o.get("music_vol", 0.35))
                self.finished_ok.emit(out)
        except pipeline.Cancelled:
            self.failed.emit("İptal edildi.")
        except Exception as e:
            import traceback
            self.log.emit(traceback.format_exc())
            self.failed.emit(str(e))
        finally:
            sys.stdout = old


class SourceLoader(QThread):
    """Kullanıcının dosyasını ya da web adresini arka planda okur."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path=None, url=None):
        super().__init__()
        self.path, self.url = path, url

    def run(self):
        try:
            self.done.emit(userdata.from_file(self.path) if self.path else userdata.from_url(self.url))
        except Exception as e:
            self.failed.emit(str(e) or e.__class__.__name__)


class UpdateCheck(QThread):
    result = Signal(object, str)

    def __init__(self, token=None):
        super().__init__()
        self.token = token

    def run(self):
        try:
            self.result.emit(updater.check(self.token), "")
        except Exception as e:
            self.result.emit(None, str(e))


class UpdateDownload(QThread):
    progress = Signal(float)
    done = Signal(str, str)

    def __init__(self, info, token=None):
        super().__init__()
        self.info, self.token = info, token

    def run(self):
        try:
            self.done.emit(updater.download(self.info, self.token, self.progress.emit), "")
        except Exception as e:
            self.done.emit("", str(e))


class OllamaCheck(QThread):
    result = Signal(bool, list)

    def run(self):
        ok, names = planner.ollama_available()
        if not names and ollama_setup.find_exe():  # kurulu ama kapalı: arka planda başlat
            if ollama_setup.start_server():
                ok, names = planner.ollama_available()
        self.result.emit(ok, names)


class OllamaSetup(QThread):
    """Tek tıkla: Ollama'yı indirip kurar (Windows), başlatır ve modeli indirir."""
    progress = Signal(object, str)
    done = Signal(bool, str)

    def __init__(self, model):
        super().__init__()
        self.model = model
        self._cancel = threading.Event()

    def run(self):
        try:
            ok, why = ollama_setup.ensure(self.model, lambda f, msg: self.progress.emit(f, msg),
                                          lambda m: self.progress.emit(None, m), self._cancel.is_set)
            self.done.emit(ok, why)
        except Exception as e:
            self.done.emit(False, str(e))


# --- Ana pencere -------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{__version__}")
        self.resize(1440, 900)
        self.settings = QSettings("DARKROOM", "DARKROOM")
        self.plan = None
        self.findings = None
        self.plan_dir = None
        self.worker = None
        self.last_video = None
        self.style = "mekanik"  # seçili video stili (Stil ve format sekmesi)

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.side = self._build_sidebar()
        lay.addWidget(self.side)
        lay.addWidget(self._build_main(), 1)
        self.auto_chain = False  # basit mod: araştır -> senaryo -> video kendiliğinden

        self.set_options(self._saved_options())
        self.set_simple(self.settings.value("simple", "1") == "1")
        self.refresh_profiles()
        self.check_ollama()
        QTimer.singleShot(1500, self.check_updates)
        self.refresh_library()

    # ---- kenar çubuğu ----
    def _section(self, text):
        l = QLabel(text.upper())
        l.setProperty("class", "section")
        return l

    def _build_sidebar(self):
        side = QFrame(objectName="side")
        side.setFixedWidth(380)
        outer = QVBoxLayout(side)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(22, 22, 22, 22)
        v.setSpacing(8)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        v.addWidget(QLabel("▌DARKROOM", objectName="brand"))
        v.addWidget(QLabel("credit by EC", objectName="brandsub"))

        v.addWidget(self._section("Profil"))
        h = QHBoxLayout()
        self.profile = QComboBox()
        self.profile.setToolTip("Kaydettiğin ayar takımları. Seçince bütün video ayarları yüklenir.")
        self.profile.activated.connect(self.load_profile)
        bs = QPushButton("KAYDET")
        bs.setToolTip("Şu anki bütün video ayarlarını bir isimle kaydet")
        bs.clicked.connect(self.save_profile)
        bd = QPushButton("SİL")
        bd.clicked.connect(self.delete_profile)
        h.addWidget(self.profile, 1)
        h.addWidget(bs)
        h.addWidget(bd)
        v.addLayout(h)

        v.addWidget(self._section("Konu"))
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Videonun konusunu yazın…\nör. Türkiye'de en çok ihracat yapılan ürünler")
        self.prompt.setFixedHeight(96)
        self.prompt.setPlainText(self.settings.value("prompt", ""))
        v.addWidget(self.prompt)

        v.addWidget(self._section("Hazır stiller"))
        g = QGridLayout()
        g.setSpacing(6)
        self.preset_btns = {}
        for i, (key, (label, tip, _)) in enumerate(PRESETS.items()):
            b = QPushButton(label, objectName="preset")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.clicked.connect(lambda _=False, k=key: self.apply_preset(k))
            g.addWidget(b, i // 3, i % 3)
            self.preset_btns[key] = b
        v.addLayout(g)
        more = QPushButton("⚙ TÜM VİDEO AYARLARI", objectName="chip")
        more.clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_style))
        v.addWidget(more)

        v.addWidget(self._section("Video süresi"))
        self.length = self._segmented([("kisa", "KISA\n~30 sn"), ("orta", "ORTA\n~1 dk"), ("uzun", "UZUN\n~2 dk")],
                                      self.settings.value("length", "orta"), v)

        v.addWidget(self._section("Video dili"))
        self.lang = self._segmented([("tr", "TÜRKÇE"), ("en", "ENGLISH")], "tr", v)
        self.lang.buttonClicked.connect(lambda _: self.fill_voices())

        default_out = os.path.join(os.path.expanduser("~"), "Videos", "DARKROOM")
        self.outdir = QLineEdit(self.settings.value("outdir", default_out))  # Ayarlar penceresinden değişir

        v.addWidget(self._section("Senaryo yazan yapay zekâ"))
        self.ai_status = QLabel("Kontrol ediliyor…")
        self.ai_status.setWordWrap(True)
        self.ai_status.setOpenExternalLinks(True)
        v.addWidget(self.ai_status)
        h = QHBoxLayout()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setCurrentText(self.settings.value("model", planner.MODEL))
        rb = QPushButton("↻")
        rb.setFixedWidth(44)
        rb.clicked.connect(self.check_ollama)
        h.addWidget(self.model, 1)
        h.addWidget(rb)
        v.addLayout(h)
        self.btn_ai_setup = QPushButton("⚡ OLLAMA'YI KUR VE HAZIRLA")
        self.btn_ai_setup.setToolTip("Ücretsiz Ollama'yı indirir, kurar, başlatır ve senaryo modelini indirir.")
        self.btn_ai_setup.clicked.connect(self.setup_ollama)
        self.btn_ai_setup.hide()
        v.addWidget(self.btn_ai_setup)
        self.ai_bar = QProgressBar()
        self.ai_bar.setRange(0, 1000)
        self.ai_bar.setTextVisible(False)
        self.ai_bar.setFixedHeight(6)
        self.ai_bar.hide()
        v.addWidget(self.ai_bar)

        v.addStretch(1)
        # eylem düğmeleri kaydırma alanının dışında, hep görünür
        v = QVBoxLayout()
        v.setContentsMargins(22, 10, 22, 22)
        v.setSpacing(8)
        outer.addLayout(v)
        self.btn_research = QPushButton("01 ▸ ARAŞTIR", objectName="primary")
        self.btn_research.clicked.connect(self.start_research)
        v.addWidget(self.btn_research)
        self.btn_plan = QPushButton("02 ▸ SENARYOYU YAZ", objectName="primary")
        self.btn_plan.clicked.connect(self.start_plan)
        self.btn_plan.setEnabled(False)
        v.addWidget(self.btn_plan)
        self.btn_render = QPushButton("03 ▸ VİDEOYU OLUŞTUR", objectName="primary")
        self.btn_render.clicked.connect(self.start_render)
        self.btn_render.setEnabled(False)
        v.addWidget(self.btn_render)
        self.btn_cancel = QPushButton("■ İPTAL", objectName="danger")
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_cancel.hide()
        v.addWidget(self.btn_cancel)
        foot = QHBoxLayout()
        ver = QLabel(f"v{__version__}", objectName="status")
        foot.addWidget(ver, 1)
        cfg = QPushButton("⚙ AYARLAR", objectName="chip")
        cfg.clicked.connect(self.open_settings)
        foot.addWidget(cfg)
        chk = QPushButton("GÜNCELLE", objectName="chip")
        chk.setToolTip("Güncellemeleri denetle")
        chk.clicked.connect(lambda: self.check_updates(manual=True))
        tok = QPushButton("TOKEN", objectName="chip")
        tok.setToolTip("GitHub token (yalnızca depo gizliyse gerekir)")
        tok.clicked.connect(self.ask_token)
        foot.addWidget(chk)
        foot.addWidget(tok)
        v.addLayout(foot)
        return side

    # ---- ana alan ----
    def _build_main(self):
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tab_preview = self._build_preview_tab()
        self.tab_style = self._build_style_tab()
        self.tab_research = self._build_research_tab()
        self.tab_editor = self._build_editor_tab()
        self.tabs.addTab(self.tab_preview, "Önizleme")
        self.tabs.addTab(self.tab_style, "Stil ve format")
        self.tabs.addTab(self.tab_research, "Araştırma")
        self.tabs.addTab(self.tab_editor, "Senaryo")
        self.tabs.addTab(self._build_library_tab(), "Videolarım")
        self.tabs.currentChanged.connect(lambda _: self.tabs.currentWidget() is self.tab_style and self.refresh_style_preview())
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(24, 12, 24, 20)
        l.addWidget(self._build_update_banner())
        l.addWidget(self._build_ai_banner())
        l.addWidget(self._build_simple_panel())
        l.addWidget(self.tabs)
        return w

    # ---- basit mod: tek kutu, tek düğme; ayarları prompt belirler ----
    def _build_simple_panel(self):
        self.simple_panel = QWidget()
        v = QVBoxLayout(self.simple_panel)
        v.setContentsMargins(0, 8, 0, 4)
        v.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(QLabel("▌DARKROOM", objectName="brand"))
        top.addWidget(QLabel("  credit by EC", objectName="brandsub"))
        top.addStretch(1)
        adv = QPushButton("⚙ GELİŞMİŞ MOD", objectName="chip")
        adv.setToolTip("Bütün ayarları elle seçmek, senaryoyu düzenlemek için")
        adv.clicked.connect(lambda: self.set_simple(False))
        top.addWidget(adv)
        v.addLayout(top)
        row = QHBoxLayout()
        self.simple_prompt = QPlainTextEdit()
        self.simple_prompt.setPlaceholderText(
            "Nasıl bir video istediğini yaz, gerisini program seçsin…\n"
            "ör. Shorts için kısa bir video: Kahvenin dünyaya yayılış hikâyesi\n"
            "ör. Osmanlı İmparatorluğu'nun yükselişi, detaylı, epik müzikli, 4K")
        self.simple_prompt.setFixedHeight(92)
        self.simple_prompt.setPlainText(self.settings.value("prompt", ""))
        self.simple_prompt.textChanged.connect(lambda: self._auto_timer.start(250))
        row.addWidget(self.simple_prompt, 1)
        col = QVBoxLayout()
        self.btn_make = QPushButton("▶  VİDEOYU YAP", objectName="primary")
        self.btn_make.setMinimumWidth(230)
        self.btn_make.setMinimumHeight(60)
        self.btn_make.clicked.connect(self.start_auto)
        col.addWidget(self.btn_make)
        self.btn_cancel2 = QPushButton("■ İPTAL", objectName="danger")
        self.btn_cancel2.clicked.connect(self.cancel)
        self.btn_cancel2.hide()
        col.addWidget(self.btn_cancel2)
        col.addStretch(1)
        row.addLayout(col)
        v.addLayout(row)
        kl = QHBoxLayout()
        kl.addWidget(QLabel("VİDEO TÜRÜ", objectName="formlabel"))
        v.addLayout(kl)
        self.kind_sel = self._segmented([(k, d["label"]) for k, d in kinds.KINDS.items()], kinds.DEFAULT, v)
        for b in self.kind_sel.buttons():
            b.setToolTip(kinds.KINDS[b.property("key")]["desc"])
        self._kind_locked = False
        self.kind_sel.buttonClicked.connect(self._on_kind_clicked)
        self.auto_info = QLabel("", objectName="status")
        self.auto_info.setWordWrap(True)
        v.addWidget(self.auto_info)
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self.update_auto_info)
        return self.simple_panel

    def _on_kind_clicked(self, *_):
        self._kind_locked = True  # kullanıcı seçti: prompt artık türü değiştirmez
        self.update_auto_info()

    def set_simple(self, on):
        self.simple = on
        self.settings.setValue("simple", "1" if on else "0")
        self.side.setVisible(not on)
        self.simple_panel.setVisible(on)
        self.tabs.tabBar().setVisible(not on)
        if not self.last_video and not self.busy():
            self.preview.setText("> Ne istediğini yaz,  [ VİDEOYU YAP ]  düğmesine bas_" if on else
                                 "> Bir konu yazıp  [ ARAŞTIR ]  düğmesine basın_")
        if on:
            self.simple_prompt.setPlainText(self.prompt.toPlainText())
            self.tabs.setCurrentWidget(self.tab_preview)
            self.update_auto_info()
        else:
            self.prompt.setPlainText(self.simple_prompt.toPlainText())

    def update_auto_info(self):
        text = self.simple_prompt.toPlainText().strip()
        if not text:
            self.auto_info.setText("Program yazdığına göre stili, müziği, süreyi ve formatı kendisi seçer.")
            return
        if not self._kind_locked:
            self.kind_sel.set_value(kinds.detect(text) or kinds.DEFAULT)
        _, why, topic = autoset.infer(text, self.kind_sel.value())
        self.auto_info.setText(f"KONU ▸ {topic}\nSEÇİLENLER ▸ " + "  ·  ".join(why))

    def start_auto(self):
        text = self.simple_prompt.toPlainText().strip()
        if not text:
            QMessageBox.information(self, APP_NAME, "Önce nasıl bir video istediğini yaz.")
            return
        if self.busy():
            return
        opts, why, topic = autoset.infer(text, self.kind_sel.value())
        self.set_options(opts)
        self.prompt.setPlainText(topic)
        self.findings, self.plan = None, None
        self.auto_chain = True
        self.log.clear()
        self.append_log("Seçilen ayarlar: " + " · ".join(why))
        self.start_research()

    def _build_ai_banner(self):
        """Senaryo yapay zekâsı hazır değilse üstte görünür; tek tıkla kurulum ve ilerleme burada."""
        self.ai_banner = QFrame(objectName="banner")
        h = QHBoxLayout(self.ai_banner)
        h.setContentsMargins(14, 8, 8, 8)
        col = QVBoxLayout()
        self.ai_banner_text = QLabel("", objectName="bannertext")
        self.ai_banner_text.setWordWrap(True)
        col.addWidget(self.ai_banner_text)
        self.ai_banner_bar = QProgressBar()
        self.ai_banner_bar.setRange(0, 1000)
        self.ai_banner_bar.setTextVisible(False)
        self.ai_banner_bar.setFixedHeight(5)
        self.ai_banner_bar.hide()
        col.addWidget(self.ai_banner_bar)
        h.addLayout(col, 1)
        self.btn_ai_banner = QPushButton("⚡ KUR VE HAZIRLA", objectName="primary")
        self.btn_ai_banner.clicked.connect(self.setup_ollama)
        later = QPushButton("SONRA")
        later.clicked.connect(self.ai_banner.hide)
        h.addWidget(self.btn_ai_banner)
        h.addWidget(later)
        self.ai_banner.hide()
        return self.ai_banner

    # ---- güncelleme ----
    def _build_update_banner(self):
        self.banner = QFrame(objectName="banner")
        h = QHBoxLayout(self.banner)
        h.setContentsMargins(14, 8, 8, 8)
        self.banner_text = QLabel("", objectName="bannertext")
        h.addWidget(self.banner_text, 1)
        self.btn_update = QPushButton("▲ GÜNCELLE", objectName="primary")
        self.btn_update.clicked.connect(self.do_update)
        self.btn_notes = QPushButton("NOTLAR")
        self.btn_notes.clicked.connect(lambda: self.update_info and QDesktopServices.openUrl(QUrl(self.update_info["page"])))
        later = QPushButton("SONRA")
        later.clicked.connect(self.banner.hide)
        for b in (self.btn_update, self.btn_notes, later):
            h.addWidget(b)
        self.banner.hide()
        self.update_info = None
        return self.banner

    def check_updates(self, manual=False):
        self._uc = UpdateCheck(self.settings.value("gh_token", "") or None)
        self._uc.result.connect(lambda info, err: self.on_update_check(info, err, manual))
        self._uc.start()

    def on_update_check(self, info, err, manual):
        if err:
            if manual:
                QMessageBox.information(self, APP_NAME, f"Güncelleme denetlenemedi:\n{err}")
            return
        if not info:
            if manual:
                QMessageBox.information(self, APP_NAME, f"En güncel sürümü kullanıyorsunuz (v{__version__}).")
            return
        self.update_info = info
        ready = bool(info["asset_api"])
        self.banner_text.setText(
            f"▲ YENİ SÜRÜM  v{info['version']}  ·  şu an v{__version__}"
            + ("" if ready else "  ·  kurulum dosyası hâlâ hazırlanıyor"))
        self.btn_update.setEnabled(ready or not updater.can_self_update())
        self.banner.show()

    def do_update(self):
        info = self.update_info
        if not info:
            return
        if not (updater.can_self_update() and info["asset_api"]):
            QDesktopServices.openUrl(QUrl(info["page"]))
            return
        if self.busy():
            QMessageBox.information(self, APP_NAME, "Önce süren işin bitmesini bekleyin.")
            return
        self.btn_update.setEnabled(False)
        self._ud = UpdateDownload(info, self.settings.value("gh_token", "") or None)
        self._ud.progress.connect(lambda f: self.banner_text.setText(f"▼ İNDİRİLİYOR  %{int(f * 100)}"))
        self._ud.done.connect(self.on_update_downloaded)
        self._ud.start()

    def on_update_downloaded(self, path, err):
        if err:
            self.banner_text.setText(f"İndirme başarısız: {err}")
            self.btn_update.setEnabled(True)
            return
        self.save_settings()
        updater.launch_installer(path)
        QApplication.quit()

    def ask_token(self):
        from PySide6.QtWidgets import QInputDialog
        tok, ok = QInputDialog.getText(
            self, "GitHub token", "Depo gizliyse, güncellemeleri görmek için salt-okunur bir GitHub token girin\n"
            "(GitHub > Settings > Developer settings > Fine-grained tokens, yalnızca bu depo, Contents: Read):",
            QLineEdit.Password, self.settings.value("gh_token", ""))
        if ok:
            self.settings.setValue("gh_token", tok.strip())
            self.check_updates(manual=True)

    def _build_preview_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 16, 0, 0)
        v.setSpacing(12)
        self.preview = QLabel(objectName="preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(640, 360)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setText("> Bir konu yazıp  [ ARAŞTIR ]  düğmesine basın_")
        self.wait = WaitScreen()  # iş sürerken: kayayı zirveye iten piksel adam
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.preview)
        self.preview_stack.addWidget(self.wait)
        v.addWidget(self.preview_stack, 1)

        steps = QHBoxLayout()
        self.step_labels = []
        for i, s in enumerate(("ARAŞTIRMA", "MEDYA", "SES", "ANİMASYON", "MONTAJ")):
            l = QLabel(f"[{i + 1:02}] {s}")
            l.setProperty("class", "step")
            steps.addWidget(l)
            self.step_labels.append(l)
        steps.addStretch(1)
        v.addLayout(steps)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        v.addWidget(self.bar)
        h = QHBoxLayout()
        self.status = QLabel("SİSTEM HAZIR", objectName="status")
        h.addWidget(self.status, 1)
        self.btn_open = QPushButton("▶  Videoyu aç")
        self.btn_open.clicked.connect(lambda: self.open_path(self.last_video))
        self.btn_folder = QPushButton("Klasörü göster")
        self.btn_folder.clicked.connect(lambda: self.open_path(os.path.dirname(self.last_video)))
        self.btn_log = QPushButton("Ayrıntılar")
        self.btn_log.setCheckable(True)
        for b in (self.btn_open, self.btn_folder):
            b.setEnabled(False)
            h.addWidget(b)
        h.addWidget(self.btn_log)
        v.addLayout(h)
        self.log = QPlainTextEdit(objectName="log")
        self.log.setReadOnly(True)
        self.log.setFixedHeight(170)
        self.log.hide()
        self.btn_log.toggled.connect(self.log.setVisible)
        v.addWidget(self.log)
        return w

    def _group(self, title, parent_layout):
        """Başlıklı ayar kutusu; içine eklenecek dikey düzeni döner."""
        box = QFrame(objectName="group")
        v = QVBoxLayout(box)
        v.setContentsMargins(16, 6, 16, 14)
        v.setSpacing(6)
        v.addWidget(self._section(title))
        parent_layout.addWidget(box)
        return v

    def _label(self, text, v):
        l = QLabel(text, objectName="formlabel")
        v.addWidget(l)
        return l

    def _build_style_tab(self):
        """Videonun görünümü, biçimi, temposu, altyazısı ve sesi: hepsi tek sayfada."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
        page = QWidget()
        scroll.setWidget(page)
        cols = QHBoxLayout(page)
        cols.setContentsMargins(0, 16, 8, 8)
        cols.setSpacing(16)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(12)
        right.setSpacing(12)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        self._style_ctrls = []

        v = self._group("Video türü", left)
        self.kind_combo = QComboBox()
        for k, d in kinds.KINDS.items():
            self.kind_combo.addItem(f"{d['name']}  ·  {d['desc']}", k)
        self.kind_combo.setCurrentIndex(max(0, self.kind_combo.findData(kinds.DEFAULT)))
        self.kind_combo.activated.connect(self.on_kind_combo)
        v.addWidget(self.kind_combo)
        hint = QLabel("Tür senaryonun yapısını belirler (ör. kinetik yazıda anlatım büyük yazıya dönüşür). "
                      "Seçince görünüm ve müzik de türe uygun hale gelir.", objectName="hint")
        hint.setWordWrap(True)
        v.addWidget(hint)

        v = self._group("Görünüm", left)
        self.style_combo = QComboBox()
        for k, name in theme.STYLE_NAMES.items():
            self.style_combo.addItem(name, k)
        self.style_combo.currentIndexChanged.connect(self.on_option_changed)
        v.addWidget(self.style_combo)
        self._label("VURGU RENGİ", v)
        self.accent_row = ColorRow(ACCENT_SWATCHES)
        self.accent_row.changed.connect(self.on_option_changed)
        v.addWidget(self.accent_row)
        self._label("ARKA PLAN", v)
        self.bg_row = ColorRow(BG_SWATCHES)
        self.bg_row.changed.connect(self.on_option_changed)
        v.addWidget(self.bg_row)
        self._label("ÖNİZLEME", v)
        self.style_preview = QLabel(objectName="preview")
        self.style_preview.setAlignment(Qt.AlignCenter)
        self.style_preview.setFixedSize(512, 288)
        v.addWidget(self.style_preview)

        v = self._group("Tempo", left)
        self.tempo = self._segmented([("yavas", "YAVAŞ\nsakin anlatım"), ("normal", "NORMAL"),
                                      ("hizli", "HIZLI\nsosyal medya")], "normal", v)
        hint = QLabel("Tempo seslendirmenin hızını ve sahneler arasındaki nefes payını değiştirir.", objectName="hint")
        hint.setWordWrap(True)
        v.addWidget(hint)
        left.addStretch(1)

        v = self._group("Format ve kalite", right)
        self._label("ANA VİDEO: 16:9 YATAY (YOUTUBE). AYRICA OLUŞTUR:", v)
        self.vert = self._segmented([("0", "DİKEY YOK"), ("1", "DİKEY 9:16\nShorts / Reels")], "0", v)
        self.square = self._segmented([("0", "KARE YOK"), ("1", "KARE 1:1\nInstagram")], "0", v)
        self._label("ÇÖZÜNÜRLÜK", v)
        self.quality = self._segmented([("720", "720p"), ("1080", "1080p"), ("1440", "1440p"), ("2160", "4K")], "1080", v)
        self._label("KARE HIZI", v)
        self.fps = self._segmented([("30", "30 FPS"), ("60", "60 FPS\ndaha akıcı")], "30", v)
        self.quality_hint = QLabel("", objectName="hint")
        self.quality_hint.setWordWrap(True)
        v.addWidget(self.quality_hint)

        v = self._group("Altyazı", right)
        self.subs = self._segmented([("0", "YOK"), ("1", "VİDEOYA YAZ")], "1", v)
        self._label("BOYUT", v)
        self.sub_size = self._segmented([("kucuk", "KÜÇÜK"), ("orta", "ORTA"), ("buyuk", "BÜYÜK")], "orta", v)
        self._label("KONUM", v)
        self.sub_pos = self._segmented([("alt", "ALTTA"), ("ust", "ÜSTTE")], "alt", v)
        self._label("GÖRÜNÜM", v)
        self.sub_box = self._segmented([("kutu", "KOYU KUTU"), ("vurgu", "RENKLİ KUTU"), ("golge", "KUTUSUZ")], "kutu", v)

        v = self._group("Ses", right)
        self._label("SESLENDİRME", v)
        self.voice = QComboBox()
        v.addWidget(self.voice)
        self._label("ARKA PLAN MÜZİĞİ", v)
        h = QHBoxLayout()
        self.music_mode = QComboBox()
        for name, val in MUSIC_MODES:
            self.music_mode.addItem(name, val)
        self.music = QLineEdit("")
        self.music.setPlaceholderText("mp3 / wav dosyası")
        self.music_btn = QPushButton("Seç")
        self.music_btn.clicked.connect(self.pick_music)
        self.music_mode.currentIndexChanged.connect(self.on_music_mode)
        self.music_mode.currentIndexChanged.connect(self.on_option_changed)
        h.addWidget(self.music_mode, 1)
        h.addWidget(self.music_btn)
        v.addLayout(h)
        v.addWidget(self.music)
        h = QHBoxLayout()
        self.music_vol_label = QLabel("MÜZİK SEVİYESİ  %35", objectName="formlabel")
        h.addWidget(self.music_vol_label)
        self.music_vol = QSlider(Qt.Horizontal)
        self.music_vol.setRange(0, 100)
        self.music_vol.setValue(35)
        self.music_vol.valueChanged.connect(lambda x: self.music_vol_label.setText(f"MÜZİK SEVİYESİ  %{x}"))
        self.music_vol.valueChanged.connect(self.on_option_changed)
        h.addWidget(self.music_vol, 1)
        v.addLayout(h)
        self._label("SES EFEKTLERİ", v)
        self.sfx = self._segmented([("1", "AÇIK"), ("0", "KAPALI")], "1", v)
        right.addStretch(1)

        for g in (self.tempo, self.vert, self.square, self.quality, self.fps, self.subs, self.sub_size,
                  self.sub_pos, self.sub_box, self.sfx, self.length):
            g.buttonClicked.connect(self.on_option_changed)
        self.voice.currentIndexChanged.connect(self.on_option_changed)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self.refresh_style_preview)
        self.fill_voices()
        self.on_music_mode()
        return scroll

    def _build_research_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 16, 0, 0)
        v.setSpacing(10)
        self.research_info = QLabel("Araştırma sonuçları burada görünecek. Senaryo yalnızca işaretli bilgilerden "
                                    "yazılır ve senaryodaki sayılar bunlarla doğrulanır. Kendi PDF, Excel ya da web "
                                    "kaynağını da aşağıdaki “＋” düğmeleriyle ekleyebilirsin.", objectName="status")
        self.research_info.setWordWrap(True)
        v.addWidget(self.research_info)
        h = QHBoxLayout()
        self.finding_list = QListWidget()
        self.finding_list.setMinimumWidth(420)
        self.finding_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.finding_list.setWordWrap(True)
        self.finding_list.currentRowChanged.connect(self.show_finding)
        self.finding_list.itemChanged.connect(lambda _: self.update_research_info())
        h.addWidget(self.finding_list, 1)
        self.finding_text = QPlainTextEdit(objectName="log")
        self.finding_text.setReadOnly(True)
        h.addWidget(self.finding_text, 1)
        v.addLayout(h, 1)
        hb = QHBoxLayout()
        for label, state in (("Tümünü seç", True), ("Hiçbirini seçme", False)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, st=state: self.check_all_findings(st))
            hb.addWidget(b)
        self.btn_source = QPushButton("Kaynağı aç")
        self.btn_source.clicked.connect(self.open_finding_source)
        hb.addWidget(self.btn_source)
        hb.addSpacing(18)
        self.btn_add_file = QPushButton("＋ Dosya ekle")
        self.btn_add_file.setToolTip("Kendi kaynağın: PDF, Excel (xlsx), CSV ya da metin dosyası.\n"
                                     "Tablolar otomatik grafiğe, il/ülke listeleri haritaya dönüşür.")
        self.btn_add_file.clicked.connect(self.add_source_file)
        hb.addWidget(self.btn_add_file)
        self.btn_add_url = QPushButton("＋ Web adresi ekle")
        self.btn_add_url.setToolTip("Bir sayfanın metnini ve içindeki tabloları kaynak olarak ekler.")
        self.btn_add_url.clicked.connect(self.add_source_url)
        hb.addWidget(self.btn_add_url)
        hb.addStretch(1)
        self.btn_write = QPushButton("02 ▸ SEÇİLENLERLE SENARYOYU YAZ", objectName="primary")
        self.btn_write.clicked.connect(self.start_plan)
        self.btn_write.setEnabled(False)
        hb.addWidget(self.btn_write)
        v.addLayout(hb)
        return w

    def add_source_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Kaynak dosyası seç", os.path.expanduser("~"),
                                              "Kaynaklar (*.pdf *.xlsx *.xlsm *.xls *.csv *.tsv *.txt *.md);;"
                                              "Tüm dosyalar (*)")
        if path:
            self._load_source(SourceLoader(path=path), os.path.basename(path))

    def add_source_url(self):
        url, ok = QInputDialog.getText(self, "Web adresi ekle", "Sayfa, PDF ya da CSV adresi:")
        if ok and url.strip():
            self._load_source(SourceLoader(url=url.strip()), url.strip())

    def _load_source(self, loader, name):
        self.status.setText(f"Kaynak okunuyor: {name}…")
        self.btn_add_file.setEnabled(False)
        self.btn_add_url.setEnabled(False)
        self.loader = loader
        loader.done.connect(self.on_source_loaded)
        loader.failed.connect(lambda e: (QMessageBox.warning(self, APP_NAME, f"Kaynak okunamadı:\n{e}"),
                                         self._source_idle()))
        loader.start()

    def _source_idle(self):
        self.btn_add_file.setEnabled(True)
        self.btn_add_url.setEnabled(True)
        self.status.setText("")

    def on_source_loaded(self, new):
        self._source_idle()
        if self.findings is None:
            self.findings = []
        if not getattr(self, "plan_dir", None):
            prompt = self.prompt.toPlainText().strip() or "kendi kaynaklarim"
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
            self.plan_dir = os.path.join(self.outdir.text(), f"{stamp}-{slugify(prompt)}")
        self.sync_findings()
        n = len(self.findings)
        for i, f in enumerate(new):
            f["id"] = f"u{n + i + 1}"
        self.findings += new
        os.makedirs(self.plan_dir, exist_ok=True)
        pipeline.save_findings(self.findings, self.plan_dir)
        self.populate_findings()
        self.finding_list.setCurrentRow(len(self.findings) - 1)
        self.set_busy(False)
        kinds = ", ".join("grafik" if f.get("series") else "tablo" if f.get("latest") else "metin" for f in new)
        self.status.setText(f"{len(new)} kaynak eklendi ({kinds}). Senaryo yazılırken kullanılacak.")
        self.tabs.setCurrentWidget(self.tab_research)

    def populate_findings(self):
        self.finding_list.blockSignals(True)
        self.finding_list.clear()
        for f in self.findings or []:
            it = QListWidgetItem(f"[{f['label']}]  {f['title'][:70]}\n{f['source']}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if f.get("selected", True) else Qt.Unchecked)
            self.finding_list.addItem(it)
        self.finding_list.blockSignals(False)
        if self.finding_list.count():
            self.finding_list.setCurrentRow(0)
        else:
            self.finding_text.setPlainText("Hiç bilgi bulunamadı. İnternet bağlantısını kontrol edin ya da konuyu "
                                           "farklı yazın. Yine de senaryo yazılabilir (konu başlığıyla sınırlı kalır).")
        self.update_research_info()

    def sync_findings(self):
        for i, f in enumerate(self.findings or []):
            f["selected"] = self.finding_list.item(i).checkState() == Qt.Checked
        if self.findings is not None and self.plan_dir:
            os.makedirs(self.plan_dir, exist_ok=True)
            pipeline.save_findings(self.findings, self.plan_dir)

    def update_research_info(self):
        n = self.finding_list.count()
        if not n:
            return
        k = sum(1 for i in range(n) if self.finding_list.item(i).checkState() == Qt.Checked)
        kinds = sorted({f["label"] for f in self.findings or []})
        self.research_info.setText(f"{n} bilgiden {k} tanesi seçili  ·  kaynaklar: {', '.join(kinds)}")

    def show_finding(self, row):
        if self.findings and 0 <= row < len(self.findings):
            f = self.findings[row]
            self.finding_text.setPlainText(f"{f['title']}\n{f['source']}  ·  {f.get('url') or ''}\n\n{f['text']}")

    def check_all_findings(self, state):
        for i in range(self.finding_list.count()):
            self.finding_list.item(i).setCheckState(Qt.Checked if state else Qt.Unchecked)

    def open_finding_source(self):
        row = self.finding_list.currentRow()
        if self.findings and 0 <= row < len(self.findings) and self.findings[row].get("url"):
            QDesktopServices.openUrl(QUrl(self.findings[row]["url"]))

    def _build_editor_tab(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 16, 0, 0)
        left = QVBoxLayout()
        self.scene_list = QListWidget()
        self.scene_list.setFixedWidth(330)
        self.scene_list.currentRowChanged.connect(self.load_scene)
        self.scene_list.setDragDropMode(QAbstractItemView.InternalMove)  # sürükleyip sırala
        self.scene_list.setDefaultDropAction(Qt.MoveAction)
        self.scene_list.model().rowsMoved.connect(lambda *_: QTimer.singleShot(0, self.on_scenes_dragged))
        left.addWidget(QLabel("Sahneleri sürükleyerek sıralayabilirsin.", objectName="hint"))
        left.addWidget(self.scene_list, 1)
        tools = QGridLayout()
        self.add_type = QComboBox()
        for k, v in SCENE_TYPES.items():
            self.add_type.addItem(f"{SCENE_ICONS[k]}  {v}", k)
        add = QPushButton("+ Ekle")
        add.clicked.connect(self.add_scene)
        up, down, rm, dup = QPushButton("↑"), QPushButton("↓"), QPushButton("Sil"), QPushButton("Çoğalt")
        up.clicked.connect(lambda: self.move_scene(-1))
        down.clicked.connect(lambda: self.move_scene(1))
        rm.clicked.connect(self.remove_scene)
        dup.clicked.connect(self.duplicate_scene)
        tools.addWidget(self.add_type, 0, 0, 1, 3)
        tools.addWidget(add, 0, 3)
        tools.addWidget(up, 1, 0)
        tools.addWidget(down, 1, 1)
        tools.addWidget(dup, 1, 2)
        tools.addWidget(rm, 1, 3)
        left.addLayout(tools)
        h.addLayout(left)

        right = QVBoxLayout()
        self.scene_preview = QLabel(objectName="preview")
        self.scene_preview.setFixedHeight(300)
        self.scene_preview.setAlignment(Qt.AlignCenter)
        right.addWidget(self.scene_preview)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.f_type = QComboBox()
        for k, v in SCENE_TYPES.items():
            self.f_type.addItem(v, k)
        self.f_kicker = QLineEdit()
        self.f_title = QLineEdit()
        self.f_narr = QPlainTextEdit()
        self.f_narr.setFixedHeight(70)
        self.f_narr.setPlaceholderText("Bu sahnede seslendirilecek metin")
        self.f_dur = QDoubleSpinBox()
        self.f_dur.setRange(0, 60)
        self.f_dur.setSuffix(" sn (0 = otomatik)")
        self.f_accent = ColorRow(ACCENT_SWATCHES)
        self.f_accent.setToolTip("Yalnızca bu sahnenin vurgu rengi (∅ = videonun rengi)")
        self.f_data = QPlainTextEdit()
        self.f_data.setPlaceholderText("Sahneye özel alanlar (JSON): veriler, maddeler, tablo satırları…")
        form.addRow(QLabel("TÜR", objectName="formlabel"), self.f_type)
        form.addRow(QLabel("ÜST ETİKET", objectName="formlabel"), self.f_kicker)
        form.addRow(QLabel("BAŞLIK", objectName="formlabel"), self.f_title)
        form.addRow(QLabel("ANLATIM", objectName="formlabel"), self.f_narr)
        form.addRow(QLabel("SÜRE", objectName="formlabel"), self.f_dur)
        form.addRow(QLabel("RENK", objectName="formlabel"), self.f_accent)
        form.addRow(QLabel("VERİLER", objectName="formlabel"), self.f_data)
        self.f_check = QLabel("")
        self.f_check.setWordWrap(True)
        form.addRow(QLabel("DOĞRULAMA", objectName="formlabel"), self.f_check)
        right.addLayout(form, 1)
        hb = QHBoxLayout()
        self.edit_msg = QLabel("", objectName="status")
        hb.addWidget(self.edit_msg, 1)
        b = QPushButton("Önizle")
        b.clicked.connect(lambda: self.save_scene(preview_only=True))
        hb.addWidget(b)
        b = QPushButton("Kaydet", objectName="primary")
        b.clicked.connect(self.save_scene)
        hb.addWidget(b)
        right.addLayout(hb)
        h.addLayout(right, 1)
        return w

    def _build_library_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 16, 0, 0)
        self.library = QListWidget()
        self.library.setIconSize(QSize(192, 108))
        self.library.itemDoubleClicked.connect(lambda it: self.open_path(it.data(Qt.UserRole)))
        v.addWidget(self.library, 1)
        h = QHBoxLayout()
        b = QPushButton("Yenile")
        b.clicked.connect(self.refresh_library)
        h.addWidget(b)
        b = QPushButton("Senaryoyu düzenlemek için aç")
        b.clicked.connect(self.load_from_library)
        h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)
        return w

    # ---- ayarlar ve küçük yardımcılar ----
    def _segmented(self, options, current, v, owner=None):
        """Yan yana, tek seçimli mekanik düğmeler. Seçili anahtarı .value() ile okunan, .set_value() ile
        değiştirilen bir nesne döner."""
        g = QHBoxLayout()
        g.setSpacing(6)
        grp = QButtonGroup(owner or self)
        grp.setExclusive(True)
        for key, label in options:
            b = QToolButton(objectName="seg")
            b.setText(label)
            b.setCheckable(True)
            b.setChecked(key == current)
            b.setProperty("key", key)
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            grp.addButton(b)
            g.addWidget(b)
        if not grp.checkedButton():
            grp.buttons()[0].setChecked(True)
        grp.value = lambda: grp.checkedButton().property("key")

        def set_value(key):
            for b in grp.buttons():
                if b.property("key") == str(key):
                    b.setChecked(True)
        grp.set_value = set_value
        v.addLayout(g)
        return grp

    # ---- video seçenekleri: hazır stiller, profiller ----
    OPTION_KEYS = ("kind", "style", "accent", "bg", "quality", "fps", "tempo", "vertical", "square", "subs", "sub_size",
                   "sub_pos", "sub_box", "voice", "music_mode", "music", "music_vol", "sfx", "length", "lang")

    def get_options(self):
        return {"kind": self.kind_combo.currentData(), "style": self.style_combo.currentData(), "accent": self.accent_row.value(), "bg": self.bg_row.value(),
                "quality": self.quality.value(), "fps": self.fps.value(), "tempo": self.tempo.value(),
                "vertical": self.vert.value(), "square": self.square.value(), "subs": self.subs.value(),
                "sub_size": self.sub_size.value(), "sub_pos": self.sub_pos.value(), "sub_box": self.sub_box.value(),
                "voice": self.voice.currentData(), "music_mode": self.music_mode.currentData(),
                "music": self.music.text(), "music_vol": self.music_vol.value(), "sfx": self.sfx.value(),
                "length": self.length.value(), "lang": self.lang.value()}

    def set_options(self, o):
        """Verilen seçenekleri arayüze yükler (eksik olanlar olduğu gibi kalır)."""
        self._loading = True
        try:
            if "lang" in o:
                self.lang.set_value(o["lang"])
                self.fill_voices()
            if "kind" in o:
                self.kind_combo.setCurrentIndex(max(0, self.kind_combo.findData(o["kind"])))
                if hasattr(self, "kind_sel"):
                    self.kind_sel.set_value(o["kind"])
            if "style" in o:
                self.style_combo.setCurrentIndex(max(0, self.style_combo.findData(o["style"])))
            if "accent" in o:
                self.accent_row.set_value(o["accent"])
            if "bg" in o:
                self.bg_row.set_value(o["bg"])
            for key, grp in (("quality", self.quality), ("fps", self.fps), ("tempo", self.tempo),
                             ("vertical", self.vert), ("square", self.square), ("subs", self.subs),
                             ("sub_size", self.sub_size), ("sub_pos", self.sub_pos), ("sub_box", self.sub_box),
                             ("sfx", self.sfx), ("length", self.length)):
                if key in o:
                    grp.set_value(o[key])
            if "voice" in o:
                i = self.voice.findData(o["voice"])
                self.voice.setCurrentIndex(i if i >= 0 else 0)
            if "music_mode" in o:
                self.music_mode.setCurrentIndex(max(0, self.music_mode.findData(o["music_mode"])))
            if "music" in o:
                self.music.setText(o["music"])
            if "music_vol" in o:
                self.music_vol.setValue(int(o["music_vol"]))
        finally:
            self._loading = False
        self.on_option_changed()

    def _saved_options(self):
        st = self.settings
        try:
            o = json.loads(st.value("options", "") or "{}")
        except ValueError:
            o = {}
        if not o:  # eski sürümlerin ayarlarından
            o = {"length": st.value("length", "orta"), "subs": st.value("subs", "1"),
                 "music_mode": st.value("music_mode", "auto:sakin"), "music": st.value("music", ""),
                 "vertical": st.value("vertical", "0"), "sfx": st.value("sfx", "1")}
            vi = int(st.value("voice_idx", 0) or 0)
            if 0 <= vi < len(VOICES):
                o["voice"] = VOICES[vi][1]
        return o

    def fill_voices(self):
        cur = self.voice.currentData()
        self.voice.blockSignals(True)
        self.voice.clear()
        for name, val in VOICES_BY_LANG.get(self.lang.value(), VOICES):
            self.voice.addItem(name, val)
        i = self.voice.findData(cur)
        self.voice.setCurrentIndex(i if i >= 0 else 0)
        self.voice.blockSignals(False)

    def on_kind_combo(self, *_):
        kd = kinds.KINDS[self.kind_combo.currentData()]
        o = {"kind": self.kind_combo.currentData()}
        if kd.get("style"):
            o["style"] = kd["style"]
        if kd.get("music"):
            o["music_mode"] = kd["music"]
        self.set_options(o)

    def look(self):
        """Videonun görünümü: (stil, vurgu, arka plan)."""
        return self.style_combo.currentData(), self.accent_row.value(), self.bg_row.value()

    def sub_opts(self):
        return {"size": D.SUB_SIZES.get(self.sub_size.value(), 42), "pos": self.sub_pos.value(),
                "box": self.sub_box.value()}

    def on_option_changed(self, *_):
        if getattr(self, "_loading", False) or not hasattr(self, "music_vol"):
            return
        self.style = self.style_combo.currentData()
        q, f = self.quality.value(), self.fps.value()
        slow = {"720": 0.5, "1080": 1, "1440": 1.8, "2160": 4}[q] * (2 if f == "60" else 1)
        self.quality_hint.setText(
            f"Çizim süresi 1080p/30'a göre yaklaşık {slow:g} kat." if slow != 1 else
            "Önerilen ayar: hız ve kalite dengesi.")
        o = self.get_options()
        for key, b in self.preset_btns.items():  # ayarlar bir hazır stille aynıysa o düğme yanık kalır
            b.setChecked(all(o.get(k) == v for k, v in PRESETS[key][2].items()))
        self._preview_timer.start(120)

    def refresh_style_preview(self):
        if self.busy() or self.tabs.currentWidget() is not self.tab_style:
            return
        style, accent, bg = self.look()
        subs = self.sub_opts() if self.subs.value() == "1" else None
        im = render_still(STYLE_SAMPLE, style, 5.5, (512, 288), accent, bg, subs)
        self.style_preview.setPixmap(pil_to_pixmap(im))

    def apply_preset(self, key):
        self.set_options(PRESETS[key][2])
        self.status.setText(f"Hazır stil: {PRESETS[key][0].title()}. İstersen “Stil ve format” sekmesinden ince ayar yap.")
        self.refresh_style_preview()

    def _profiles(self):
        try:
            return json.loads(self.settings.value("profiles", "") or "{}")
        except ValueError:
            return {}

    def refresh_profiles(self, select=None):
        self.profile.clear()
        self.profile.addItem("— profil seç —", "")
        for name in sorted(self._profiles()):
            self.profile.addItem(name, name)
        if select:
            self.profile.setCurrentIndex(max(0, self.profile.findData(select)))

    def save_profile(self):
        cur = self.profile.currentData() or ""
        name, ok = QInputDialog.getText(self, "Profili kaydet", "Profil adı (ör. Benim stilim):", text=cur)
        name = name.strip()
        if not ok or not name:
            return
        p = self._profiles()
        if name in p and name != cur and QMessageBox.question(
                self, APP_NAME, f"“{name}” zaten var. Üzerine yazılsın mı?") != QMessageBox.Yes:
            return
        p[name] = self.get_options()
        self.settings.setValue("profiles", json.dumps(p, ensure_ascii=False))
        self.refresh_profiles(name)
        self.status.setText(f"Profil kaydedildi: {name}")

    def load_profile(self, *_):
        name = self.profile.currentData()
        if name and name in self._profiles():
            self.set_options(self._profiles()[name])
            self.status.setText(f"Profil yüklendi: {name}")
            self.refresh_style_preview()

    def delete_profile(self):
        name = self.profile.currentData()
        if not name:
            return
        if QMessageBox.question(self, APP_NAME, f"“{name}” profili silinsin mi?") != QMessageBox.Yes:
            return
        p = self._profiles()
        p.pop(name, None)
        self.settings.setValue("profiles", json.dumps(p, ensure_ascii=False))
        self.refresh_profiles()

    def open_settings(self):
        SettingsDialog(self).exec()

    def on_music_mode(self, *_):
        own = self.music_mode.currentData() == "file"
        self.music.setVisible(own)
        self.music_btn.setVisible(own)

    def music_choice(self):
        m = self.music_mode.currentData()
        return self.music.text().strip() if m == "file" else m

    def pick_music(self):
        p, _ = QFileDialog.getOpenFileName(self, "Müzik seç", "", "Ses (*.mp3 *.wav *.m4a *.ogg)")
        if p:
            self.music.setText(p)

    def pick_outdir(self):
        p = QFileDialog.getExistingDirectory(self, "Kayıt klasörü", self.outdir.text())
        if p:
            self.outdir.setText(p)

    def open_path(self, p):
        if p and os.path.exists(p):
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def check_ollama(self):
        planner.MODEL = self.model.currentText().strip() or planner.MODEL
        self._oc = OllamaCheck()
        self._oc.result.connect(self.on_ollama)
        self._oc.start()

    def on_ollama(self, ok, names):
        cur = self.model.currentText()
        self.model.clear()
        self.model.addItems(names or [cur])
        self.model.setCurrentText(cur if (cur in names or not names) else names[0])
        if getattr(self, "_ai_setup", None) and self._ai_setup.isRunning():
            return
        rec = ollama_setup.recommended_model()
        if names and ok:
            self.ai_status.setText("<span style='color:#FF7A1A'>■ Ollama çalışıyor.</span> Senaryoları yapay "
                                   "zekâ yazacak.")
            self.btn_ai_setup.hide()
            self.ai_banner.hide()
        elif names:
            self.ai_status.setText(f"<span style='color:#FF9A3D'>■ Ollama çalışıyor ama {planner.MODEL} modeli "
                                   f"yok.</span> Aşağıdaki düğme modeli indirir.")
            self.btn_ai_setup.setText("⚡ MODELİ İNDİR")
            self.btn_ai_setup.show()
            self.ai_banner_text.setText(f"SENARYO MODELİ ({planner.MODEL}) EKSİK  ·  TEK TIKLA İNDİRİLİR")
            self.btn_ai_banner.setText("⚡ MODELİ İNDİR")
            self.ai_banner.show()
        else:
            self.ai_status.setText(
                "<span style='color:#FF4D1A'>■ Ollama kurulu değil.</span> Program yine çalışır ama senaryo "
                "basit kalır. Aşağıdaki düğme ücretsiz Ollama'yı ve senaryo modelini kendisi kurar.")
            self.btn_ai_setup.setText("⚡ OLLAMA'YI KUR VE HAZIRLA")
            self.btn_ai_setup.show()
            self.ai_banner_text.setText("SENARYO YAPAY ZEKÂSI (OLLAMA) KURULU DEĞİL  ·  ÜCRETSİZ, TEK TIKLA KURULUR")
            self.btn_ai_banner.setText("⚡ KUR VE HAZIRLA")
            self.ai_banner.show()
            if self.model.currentText() in ("", "qwen3:8b") and rec != "qwen3:8b":
                self.model.setCurrentText(rec)  # az bellekli bilgisayarda daha küçük model

    def setup_ollama(self):
        model = self.model.currentText().strip() or ollama_setup.recommended_model()
        size = "≈5 GB" if "8b" in model else ("≈2,5 GB" if "4b" in model else "birkaç GB")
        need_install = not ollama_setup.server_up() and not ollama_setup.find_exe()
        if need_install and sys.platform != "win32":
            QDesktopServices.openUrl(QUrl(ollama_setup.DOWNLOAD_PAGE))
            self.ai_status.setText("Ollama indirme sayfası açıldı. Kurduktan sonra ↻ düğmesine basın.")
            return
        msg = (("Ücretsiz Ollama programı (≈1 GB) indirilip kurulacak, ardından " if need_install else "")
               + f"senaryo modeli {model} ({size}) indirilecek.\n\nİnternet hızına göre birkaç dakika ile yarım "
               "saat arası sürebilir. Bu sırada programı kullanmaya devam edebilirsiniz. Başlatılsın mı?")
        if QMessageBox.question(self, APP_NAME, msg) != QMessageBox.Yes:
            return
        planner.MODEL = model
        self.btn_ai_setup.setEnabled(False)
        self.btn_ai_banner.setEnabled(False)
        self.ai_bar.setValue(0)
        self.ai_bar.show()
        self.ai_banner_bar.setValue(0)
        self.ai_banner_bar.show()
        self.ai_banner.show()
        self._ai_setup = OllamaSetup(model)
        self._ai_setup.progress.connect(self.on_ai_progress)
        self._ai_setup.done.connect(self.on_ai_setup_done)
        self._ai_setup.start()

    def on_ai_progress(self, frac, msg):
        self.ai_status.setText(f"<span style='color:#FF9A3D'>■</span> {msg}")
        self.ai_banner_text.setText(msg.upper())
        for bar in (self.ai_bar, self.ai_banner_bar):
            if frac is None:
                bar.setRange(0, 0)  # süresi belirsiz adım
            else:
                bar.setRange(0, 1000)
                bar.setValue(int(frac * 1000))

    def on_ai_setup_done(self, ok, why):
        self.ai_bar.hide()
        self.ai_banner_bar.hide()
        self.btn_ai_setup.setEnabled(True)
        self.btn_ai_banner.setEnabled(True)
        if ok:
            self.settings.setValue("model", planner.MODEL)
            self.check_ollama()
        elif why == "page":
            QDesktopServices.openUrl(QUrl(ollama_setup.DOWNLOAD_PAGE))
        else:
            self.ai_status.setText(f"<span style='color:#FF4D1A'>■ Hazırlanamadı:</span> {why}")
            self.ai_banner_text.setText(f"HAZIRLANAMADI: {why}")

    # tek düğmeli akışta her işin dağdaki payı: (başlangıç, genişlik)
    AUTO_SPAN = {"research": (0.0, 0.12), "plan": (0.12, 0.13), "render": (0.25, 0.75)}

    def _span(self):
        if self.auto_chain and self.worker:
            return self.AUTO_SPAN.get(self.worker.mode, (0.0, 1.0))
        return 0.0, 1.0

    def set_busy(self, busy):
        if self.auto_chain and self.worker and self.worker.mode != "research" and busy:
            self._stage = (1, 1)  # akış sürüyor: bekleme ekranı baştan başlamasın
        elif busy:
            self._stage = (1, 1)
            self.wait.start(self.status.text().rstrip("…") if self.status.text() != "SİSTEM HAZIR" else "")
            self.preview_stack.setCurrentWidget(self.wait)
        elif self.auto_chain:
            pass  # bir sonraki adım hemen başlayacak
        else:
            self.wait.stop()
            self.preview_stack.setCurrentWidget(self.preview)
        self.btn_research.setEnabled(not busy)
        self.btn_plan.setEnabled(not busy and self.findings is not None)
        self.btn_write.setEnabled(not busy and self.findings is not None)
        self.btn_render.setEnabled(not busy and self.plan is not None)
        self.btn_cancel.setVisible(busy)
        self.btn_make.setEnabled(not busy)
        self.btn_cancel2.setVisible(busy)

    def mark_stage(self, i, n, label):
        for k, l in enumerate(self.step_labels):
            l.setProperty("class", "stepdone" if k < i - 1 else ("stepon" if k == i - 1 else "step"))
            l.style().unpolish(l)
            l.style().polish(l)
        self.status.setText(label + "…")
        self.bar.setValue(0)
        if self.worker and self.worker.mode in ("research", "plan"):
            i, n = 1, 1  # tek aşamalı işler: dağın tamamı bu iş
        self._stage = (i, max(1, n))
        self.wait.set_stage(label)
        b, w = self._span()
        self.wait.set_progress(b + w * (i - 1) / max(1, n))

    def append_log(self, s):
        self.log.appendPlainText(s)

    def show_preview(self, im):
        pm = pil_to_pixmap(im)
        self.preview_stack.setCurrentWidget(self.preview)  # çizim başladı: bekleme ekranı yerine kareler
        self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def save_settings(self):
        s = self.settings
        s.setValue("prompt", (self.simple_prompt if getattr(self, "simple", False) else self.prompt).toPlainText())
        s.setValue("options", json.dumps(self.get_options(), ensure_ascii=False))
        s.setValue("outdir", self.outdir.text())
        s.setValue("model", self.model.currentText())

    # ---- iş akışı ----
    def start_research(self):
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, APP_NAME, "Önce videonun konusunu yazın.")
            return
        self.save_settings()
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        self.plan_dir = os.path.join(self.outdir.text(), f"{stamp}-{slugify(prompt)}")
        self.research_prompt = prompt
        self.log.clear()
        self.tabs.setCurrentWidget(self.tab_preview)
        self.worker = Worker("research", prompt=prompt, out_dir=self.plan_dir, opts={"lang": self.lang.value()})
        self._wire(self.worker)
        self.worker.researched.connect(self.on_researched)
        self.set_busy(True)
        self.worker.start()

    def on_researched(self, findings):
        mine = [f for f in self.findings or [] if f.get("kind") == "user"]  # eklenen kendi kaynakların kalır
        self.findings = findings + mine
        if mine:
            pipeline.save_findings(self.findings, self.plan_dir)
        self.set_busy(False)
        self.populate_findings()
        self.bar.setValue(1000)
        if self.auto_chain:
            self.start_plan()
            return
        self.status.setText(f"Araştırma bitti: {len(findings)} bilgi bulundu. İstemediklerinizin işaretini "
                            f"kaldırıp “Senaryoyu yaz”a basın.")
        self.tabs.setCurrentWidget(self.tab_research)

    def start_plan(self):
        if self.findings is None:
            return
        self.save_settings()
        self.sync_findings()
        planner.MODEL = self.model.currentText().strip() or planner.MODEL
        prompt = getattr(self, "research_prompt", None) or self.prompt.toPlainText().strip()
        self.log.clear()
        self.tabs.setCurrentWidget(self.tab_preview)
        self.worker = Worker("plan", prompt=prompt, out_dir=self.plan_dir, findings=self.findings,
                             opts={"length": self.length.value(), "lang": self.lang.value(),
                                   "kind": self.kind_combo.currentData()})
        self._wire(self.worker)
        self.worker.planned.connect(self.on_planned)
        self.set_busy(True)
        self.worker.start()

    def start_render(self):
        if not self.plan:
            return
        self.commit_scene_silently()
        self.save_settings()
        self.write_plan()
        style, accent, bg = self.look()
        opts = {"style": style, "accent": accent, "bg": bg, "voice": self.voice.currentData(),
                "music": self.music_choice(), "music_vol": self.music_vol.value() / 100,
                "sfx": self.sfx.value() == "1", "vertical": self.vert.value() == "1",
                "square": self.square.value() == "1", "subtitles": self.subs.value() == "1",
                "sub_opts": self.sub_opts(), "quality": self.quality.value(), "fps": int(self.fps.value()),
                "tempo": self.tempo.value(), "lang": self.plan.get("language") or self.lang.value()}
        self.tabs.setCurrentWidget(self.tab_preview)
        self.worker = Worker("render", plan=self.plan, out_dir=self.plan_dir, opts=opts)
        self._wire(self.worker)
        self.worker.finished_ok.connect(self.on_rendered)
        self.set_busy(True)
        self.worker.start()

    def _wire(self, w):
        w.log.connect(self.append_log)
        w.stage.connect(self.mark_stage)
        w.progress.connect(self.on_progress)
        w.preview.connect(self.show_preview)
        w.failed.connect(self.on_failed)

    def on_progress(self, f):
        self.bar.setValue(int(f * 1000))
        i, n = getattr(self, "_stage", (1, 1))
        b, w = self._span()
        self.wait.set_progress(b + w * (i - 1 + f) / n)  # bütün işin ilerlemesi: adamın yamaçtaki yeri

    def cancel(self):
        if self.worker:
            self.worker.cancel()
            self.status.setText("İptal ediliyor…")

    def on_planned(self, plan):
        self.plan = plan
        self.set_busy(False)
        self.populate_scenes()
        chk = plan.get("check")
        extra = (f"  ·  {chk['missing']} sayı kaynakta bulunamadı (⚠ işaretli sahneler)" if chk and chk["missing"]
                 else ("  ·  tüm sayılar kaynaklarda doğrulandı ✓" if chk else ""))
        self.status.setText(f"Senaryo hazır: {len(plan.get('scenes', []))} sahne{extra}")
        self.bar.setValue(1000)
        if self.auto_chain:
            self.start_render()
            return
        self.tabs.setCurrentWidget(self.tab_editor)

    def on_rendered(self, path):
        self.auto_chain = False
        self.set_busy(False)
        self.last_video = path
        self.btn_open.setEnabled(True)
        self.btn_folder.setEnabled(True)
        self.bar.setValue(1000)
        for l in self.step_labels:
            l.setProperty("class", "stepdone")
            l.style().unpolish(l)
            l.style().polish(l)
        self.status.setText(f"Video hazır: {path}")
        self.refresh_library()

    def on_failed(self, msg):
        self.auto_chain = False
        self.set_busy(False)
        self.status.setText(f"Durdu: {msg}")
        if msg != "İptal edildi.":
            self.log.show()
            self.btn_log.setChecked(True)

    # ---- senaryo düzenleyici ----
    def populate_scenes(self, select=0):
        self.scene_list.blockSignals(True)
        self.scene_list.clear()
        for i, sc in enumerate(self.plan.get("scenes", [])):
            t = sc.get("type", "?")
            name = sc.get("title") or sc.get("caption") or sc.get("label") or ""
            chk = sc.get("check") or {}
            mark = "  ⚠" if chk.get("missing") else ("  ✓" if chk.get("verified") else "")
            dot = "  ●" if sc.get("accent") else ""
            it = QListWidgetItem(f"{SCENE_ICONS.get(t, '•')}  {i + 1}. {SCENE_TYPES.get(t, t)}{mark}{dot}\n     {name[:34]}")
            it.setData(Qt.UserRole, i)
            if sc.get("accent"):
                it.setForeground(QColor(sc["accent"]))
            self.scene_list.addItem(it)
        self.scene_list.blockSignals(False)
        if self.scene_list.count():
            self.scene_list.setCurrentRow(min(select, self.scene_list.count() - 1))

    def busy(self):
        return bool(self.worker and self.worker.isRunning())

    def load_scene(self, row):
        if self.busy():
            return
        if not self.plan or row < 0 or row >= len(self.plan.get("scenes", [])):
            return
        sc = self.plan["scenes"][row]
        self.f_type.setCurrentIndex(max(0, self.f_type.findData(sc.get("type"))))
        self.f_kicker.setText(sc.get("kicker", ""))
        self.f_title.setText(sc.get("title") or sc.get("caption") or "")
        self.f_narr.setPlainText(sc.get("narration", ""))
        self.f_dur.setValue(float(sc.get("duration") or 0))
        self.f_accent.set_value(sc.get("accent", ""))
        rest = {k: v for k, v in sc.items() if k not in COMMON_KEYS and k not in ("caption", "check") and not k.startswith("_")}
        self.f_data.setPlainText(json.dumps(rest, ensure_ascii=False, indent=2))
        self.edit_msg.setText("")
        self.show_check(sc)
        self.scene_preview.setPixmap(pil_to_pixmap(render_still(sc, self.style, None, (533, 300), *self.look()[1:])))

    def show_check(self, sc):
        c = sc.get("check")
        if not c:
            self.f_check.setText("<span style='color:#8C8277'>Bu sahnede kontrol edilecek sayı yok.</span>"
                                 if self.findings else "<span style='color:#8C8277'>Araştırma verisi yok.</span>")
        elif c["missing"]:
            self.f_check.setText(f"<span style='color:#FF4D1A'>⚠ Kaynaklarda bulunamadı: {', '.join(c['missing'])}</span>"
                                 f"<br><span style='color:#8C8277'>{c['verified']} sayı doğrulandı. Bulunamayanları "
                                 f"düzeltin ya da silin.</span>")
        else:
            self.f_check.setText(f"<span style='color:#FF7A1A'>✓ {c['verified']} sayının hepsi kaynaklarda var.</span>")

    def _scene_from_form(self):
        rest = json.loads(self.f_data.toPlainText() or "{}")
        sc = {"type": self.f_type.currentData(), **rest}
        if self.f_kicker.text():
            sc["kicker"] = self.f_kicker.text()
        key = "caption" if sc["type"] in ("image", "video") else "title"
        sc[key] = self.f_title.text()
        if self.f_narr.toPlainText().strip():
            sc["narration"] = self.f_narr.toPlainText().strip()
        if self.f_dur.value() > 0:
            sc["duration"] = self.f_dur.value()
        if self.f_accent.value():
            sc["accent"] = self.f_accent.value()
        return sc

    def save_scene(self, preview_only=False):
        row = self.scene_list.currentRow()
        if not self.plan or row < 0:
            return
        try:
            sc = self._scene_from_form()
        except json.JSONDecodeError as e:
            self.edit_msg.setText(f"<span style='color:#FF4D1A'>Veriler alanında JSON hatası: {e}</span>")
            return
        if not self.busy():
            self.scene_preview.setPixmap(pil_to_pixmap(render_still(sc, self.style, None, (533, 300), *self.look()[1:])))
        if preview_only:
            self.edit_msg.setText("Önizleme güncellendi (henüz kaydedilmedi).")
            return
        if self.findings:
            from .factcheck import check_scene, source_numbers
            c = check_scene(sc, source_numbers(self.findings))
            if c["verified"] or c["missing"]:
                sc["check"] = c
        self.plan["scenes"][row] = sc
        self.show_check(sc)
        self.write_plan()
        self.populate_scenes(row)
        self.edit_msg.setText("<span style='color:#FF7A1A'>Kaydedildi.</span>")

    def commit_scene_silently(self):
        row = self.scene_list.currentRow()
        if self.plan and row >= 0:
            try:
                old = self.plan["scenes"][row]
                sc = self._scene_from_form()
                if old.get("check") and sc == {k: v for k, v in old.items() if k != "check"}:
                    sc["check"] = old["check"]
                self.plan["scenes"][row] = sc
            except Exception:
                pass

    def add_scene(self):
        if self.plan is None:
            self.plan = {"title": "Yeni video", "language": "tr", "scenes": []}
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
            self.plan_dir = os.path.join(self.outdir.text(), f"{stamp}-elle")
            self.btn_render.setEnabled(True)
        row = self.scene_list.currentRow() + 1
        self.plan["scenes"].insert(row, json.loads(json.dumps(SAMPLE_SCENES[self.add_type.currentData()])))
        self.populate_scenes(row)

    def move_scene(self, d):
        row = self.scene_list.currentRow()
        sc = self.plan["scenes"] if self.plan else []
        if 0 <= row < len(sc) and 0 <= row + d < len(sc):
            sc[row], sc[row + d] = sc[row + d], sc[row]
            self.populate_scenes(row + d)

    def on_scenes_dragged(self):
        """Sürükle-bırak sonrası planın sahne sırasını listedeki yeni sıraya uydurur."""
        if not self.plan:
            return
        order = [self.scene_list.item(i).data(Qt.UserRole) for i in range(self.scene_list.count())]
        old = self.plan["scenes"]
        if sorted(order) != list(range(len(old))) or order == list(range(len(old))):
            return
        cur = self.scene_list.currentRow()
        self.plan["scenes"] = [old[i] for i in order]
        self.write_plan()
        self.populate_scenes(max(0, cur))

    def duplicate_scene(self):
        row = self.scene_list.currentRow()
        if self.plan and 0 <= row < len(self.plan["scenes"]):
            self.commit_scene_silently()
            self.plan["scenes"].insert(row + 1, json.loads(json.dumps(self.plan["scenes"][row])))
            self.populate_scenes(row + 1)

    def remove_scene(self):
        row = self.scene_list.currentRow()
        if self.plan and 0 <= row < len(self.plan["scenes"]):
            del self.plan["scenes"][row]
            self.populate_scenes(row)

    def write_plan(self):
        if self.plan and self.plan_dir:
            os.makedirs(self.plan_dir, exist_ok=True)
            with open(os.path.join(self.plan_dir, "plan.json"), "w", encoding="utf-8") as f:
                json.dump(self.plan, f, ensure_ascii=False, indent=2)

    # ---- kitaplık ----
    def refresh_library(self):
        self.library.clear()
        base = self.outdir.text()
        if not os.path.isdir(base):
            return
        for d in sorted(os.listdir(base), reverse=True):
            full = os.path.join(base, d)
            plan_p = os.path.join(full, "plan.json")
            vid = os.path.join(full, "video.mp4")
            if not os.path.isfile(plan_p):
                continue
            title = d
            try:
                with open(plan_p, encoding="utf-8") as f:
                    title = json.load(f).get("title") or d
            except Exception:
                pass
            state = "video hazır" if os.path.exists(vid) else "sadece senaryo"
            it = QListWidgetItem(f"{title}\n{d} · {state}")
            it.setData(Qt.UserRole, vid if os.path.exists(vid) else plan_p)
            it.setData(Qt.UserRole + 1, full)
            self.library.addItem(it)

    def load_from_library(self):
        it = self.library.currentItem()
        if not it:
            return
        full = it.data(Qt.UserRole + 1)
        with open(os.path.join(full, "plan.json"), encoding="utf-8") as f:
            self.plan = json.load(f)
        self.plan_dir = full
        self.prompt.setPlainText(self.plan.get("prompt", self.plan.get("title", "")))
        self.findings = pipeline.load_findings(full)
        self.populate_findings()
        self.populate_scenes()
        self.btn_render.setEnabled(True)
        self.btn_plan.setEnabled(bool(self.findings))
        self.tabs.setCurrentWidget(self.tab_editor)

    def closeEvent(self, e):
        self.save_settings()
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        super().closeEvent(e)


def run_app():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    for f in ("Inter-Regular.ttf", "Inter-SemiBold.ttf", "Inter-ExtraBold.ttf", "JetBrainsMono-Regular.ttf",
              "JetBrainsMono-Bold.ttf", "JetBrainsMono-ExtraBold.ttf"):
        QFontDatabase.addApplicationFont(os.path.join(theme.FONT_DIR, f))
    icon = os.path.join(HERE, "assets", "icon.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    st = QSettings("DARKROOM", "DARKROOM")
    set_app_theme(st.value("app_mode", "koyu"), st.value("app_accent", "turuncu"))
    app.setStyleSheet(app_stylesheet())
    if os.environ.get("PV_NO_SPLASH") or st.value("splash", "1") == "0":
        w = MainWindow()
        w.show()
        return app.exec()
    from .splash import Splash
    sp = Splash(__version__, sound=not os.environ.get("PV_SPLASH_MUTE") and st.value("splash_sound", "1") != "0")
    sp.start()
    app.processEvents()
    w = MainWindow()  # açılış efekti oynarken ana pencere arkada hazırlanır
    def reveal():  # ana pencere açılış solarken yumuşakça belirir
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        w.setWindowOpacity(0.0)
        w.show()
        w._fade = QPropertyAnimation(w, b"windowOpacity")
        w._fade.setDuration(450)
        w._fade.setStartValue(0.0)
        w._fade.setEndValue(1.0)
        w._fade.setEasingCurve(QEasingCurve.InOutCubic)
        w._fade.start()

    sp.finished.connect(reveal)
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_app())
