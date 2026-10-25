"""PromptVideo Stüdyo: masaüstü uygulaması (PySide6).

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
from PySide6.QtGui import QImage, QPixmap, QDesktopServices, QIcon, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel,
    QPlainTextEdit, QPushButton, QComboBox, QLineEdit, QFileDialog, QProgressBar, QTabWidget,
    QListWidget, QListWidgetItem, QFrame, QMessageBox, QSplitter, QSizePolicy, QCheckBox,
    QFormLayout, QDoubleSpinBox, QToolButton, QScrollArea)

from . import theme, pipeline, planner, scenes, updater, __version__
from . import draw as D
from .render import render_frame

APP_NAME = "PromptVideo Stüdyo"
HERE = os.path.dirname(os.path.abspath(__file__))

SCENE_TYPES = {
    "title": "Başlık", "bullets": "Madde listesi", "stat": "Büyük sayı", "bar": "Çubuk grafik",
    "line": "Çizgi grafik", "pie": "Pasta grafik", "table": "Tablo", "image": "Görsel",
    "video": "Video klip", "outro": "Kapanış",
}
SCENE_ICONS = {"title": "✦", "bullets": "☰", "stat": "#", "bar": "▤", "line": "📈", "pie": "◔",
               "table": "▦", "image": "🖼", "video": "🎬", "outro": "★"}
VOICES = [("Ahmet (erkek)", "tr-TR-AhmetNeural"), ("Emel (kadın)", "tr-TR-EmelNeural"),
          ("Sessiz", "")]
EXAMPLES = [
    "Türkiye'nin nüfusu 1960'tan bugüne nasıl değişti?",
    "Avrupa'da enflasyon: Türkiye, Almanya, Fransa karşılaştırması",
    "Kahvenin dünyaya yayılış hikâyesi",
]
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
    "outro": {"type": "outro", "title": "İzlediğiniz için teşekkürler", "sources": []},
}
COMMON_KEYS = ("type", "kicker", "title", "narration", "duration")

# Arayüz teması: mekanik, derin siyah tonlar + turuncu vurgu
C = dict(
    bg="#050505", panel="#0B0B0B", panel2="#111111", field="#070707", line="#1F1F1F", line2="#2B2B2B",
    text="#E6DED3", muted="#7D746A", dim="#4A443E", orange="#FF7A1A", orange2="#FF9A3D", orange3="#B84E00",
    warn="#FF4D1A",
)
QSS = """
* { font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 14px; color: %(text)s; }
QMainWindow { background: %(bg)s; }
QWidget#root { background-color: %(bg)s; background-image: url(%(tile)s); }
QFrame#side { background: %(panel)s; border-right: 1px solid %(line)s; }
QLabel#brand { font-family: 'JetBrains Mono'; font-size: 21px; font-weight: 800; color: %(orange)s; letter-spacing: 2px; }
QLabel#brandsub { font-family: 'JetBrains Mono'; color: %(muted)s; font-size: 11px; }
QLabel[class="section"] { font-family: 'JetBrains Mono'; color: %(orange)s; font-size: 11px; font-weight: 700;
    letter-spacing: 2px; margin-top: 12px; padding-bottom: 2px; border-bottom: 1px solid %(line)s; }
QPlainTextEdit, QLineEdit, QComboBox, QDoubleSpinBox, QListWidget {
    background: %(field)s; border: 1px solid %(line2)s; border-top: 1px solid #000000; border-radius: 3px;
    padding: 8px; selection-background-color: %(orange)s; selection-color: #000000; }
QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border: 1px solid %(orange)s; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url(%(arrow_down)s); width: 12px; height: 12px; margin-right: 8px; }
QDoubleSpinBox::up-arrow { image: url(%(arrow_up)s); width: 10px; height: 10px; }
QDoubleSpinBox::down-arrow { image: url(%(arrow_down)s); width: 10px; height: 10px; }
QComboBox QAbstractItemView { background: %(panel2)s; border: 1px solid %(orange3)s; outline: none;
    selection-background-color: %(orange)s; selection-color: #000000; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { background: %(panel2)s; border-left: 1px solid %(line2)s; width: 18px; }

/* mekanik düğmeler: siyah metal gövde, üstte ince ışık, basınca içe göçer */
QPushButton {
    font-family: 'JetBrains Mono'; font-weight: 700; font-size: 13px; letter-spacing: 1px; color: %(text)s;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #232323, stop:0.08 #1A1A1A, stop:0.5 #121212, stop:1 #0A0A0A);
    border: 1px solid #2E2E2E; border-bottom: 2px solid #000000; border-top: 1px solid #3A3A3A;
    border-radius: 3px; padding: 9px 14px; }
QPushButton:hover { color: %(orange2)s; border: 1px solid %(orange3)s; border-bottom: 2px solid #000000; }
QPushButton:pressed { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #050505, stop:1 #141414);
    border-top: 2px solid #000000; border-bottom: 1px solid #2E2E2E; padding-top: 10px; padding-bottom: 8px; }
QPushButton:disabled { color: %(dim)s; background: #0C0C0C; border: 1px solid #191919; }
QPushButton#primary {
    color: %(orange)s; font-size: 14px; padding: 13px; letter-spacing: 2px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #262626, stop:0.07 #1B1B1B, stop:0.55 #111111, stop:1 #080808);
    border: 1px solid %(orange3)s; border-left: 4px solid %(orange)s; border-bottom: 2px solid #000000; }
QPushButton#primary:hover { color: #000000; background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 %(orange2)s, stop:1 %(orange)s);
    border: 1px solid %(orange2)s; border-left: 4px solid #FFFFFF; }
QPushButton#primary:pressed { color: #000000; background: %(orange3)s; }
QPushButton#primary:disabled { color: %(dim)s; border: 1px solid #1C1C1C; border-left: 4px solid #2A2A2A; background: #0C0C0C; }
QPushButton#danger { color: %(warn)s; border: 1px solid #4A1A08; border-left: 4px solid %(warn)s; }
QPushButton#chip { font-family: 'Inter'; font-weight: 500; font-size: 12px; letter-spacing: 0; text-align: left;
    padding: 6px 10px; color: %(muted)s; background: %(field)s; border: 1px solid %(line)s; border-radius: 2px; }
QPushButton#chip:hover { color: %(orange2)s; border-color: %(orange3)s; }
QToolButton#stylecard { font-family: 'JetBrains Mono'; font-weight: 700; letter-spacing: 1px; color: %(muted)s;
    background: %(field)s; border: 1px solid %(line2)s; border-radius: 3px; padding: 6px; }
QToolButton#stylecard:hover { border-color: %(orange3)s; }
QToolButton#stylecard:checked { color: %(orange)s; border: 2px solid %(orange)s; background: #120A03; }

QTabWidget::pane { border: none; }
QTabBar::tab { font-family: 'JetBrains Mono'; background: transparent; color: %(muted)s; padding: 12px 20px;
    font-weight: 700; letter-spacing: 2px; border-bottom: 2px solid %(line)s; }
QTabBar::tab:hover { color: %(text)s; }
QTabBar::tab:selected { color: %(orange)s; border-bottom: 2px solid %(orange)s; background: #0E0905; }

/* segmentli ilerleme göstergesi */
QProgressBar { background: #000000; border: 1px solid %(line2)s; border-radius: 2px; height: 16px; padding: 2px; }
QProgressBar::chunk { background: %(orange)s; width: 9px; margin: 0 1px; }

QLabel#preview { background: #000000; border: 1px solid %(line)s; border-radius: 2px; }
QLabel#status { font-family: 'JetBrains Mono'; color: %(muted)s; font-size: 12px; }
QLabel[class="step"] { font-family: 'JetBrains Mono'; color: %(dim)s; font-weight: 700; font-size: 12px; }
QLabel[class="stepon"] { font-family: 'JetBrains Mono'; color: %(orange)s; font-weight: 800; font-size: 12px; }
QLabel[class="stepdone"] { font-family: 'JetBrains Mono'; color: %(text)s; font-weight: 700; font-size: 12px; }
QPlainTextEdit#log { font-family: 'JetBrains Mono'; font-size: 12px; color: %(orange2)s; background: #000000; }
QListWidget { outline: none; }
QListWidget::item { padding: 10px; border-left: 2px solid transparent; margin: 1px 0; }
QListWidget::item:hover { background: #100B06; }
QListWidget::item:selected { background: #1A0F05; color: %(orange)s; border-left: 2px solid %(orange)s; }
QScrollBar:vertical { background: %(bg)s; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #262626; min-height: 30px; border-radius: 1px; }
QScrollBar::handle:vertical:hover { background: %(orange3)s; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QLabel#formlabel { font-family: 'JetBrains Mono'; color: %(muted)s; font-size: 12px; letter-spacing: 1px; }
QFrame#banner { background: #140A02; border: 1px solid %(orange3)s; border-left: 4px solid %(orange)s; border-radius: 2px; }
QLabel#bannertext { font-family: 'JetBrains Mono'; color: %(orange)s; font-weight: 700; letter-spacing: 1px; }
QToolTip { background: #000000; color: %(orange2)s; border: 1px solid %(orange3)s; font-family: 'JetBrains Mono'; }
"""


def app_stylesheet():
    def asset(name):
        return os.path.join(HERE, "assets", name).replace("\\", "/")
    return QSS % dict(C, tile=asset("bg_tile.png"), arrow_down=asset("arrow_down.png"),
                      arrow_up=asset("arrow_up.png"))


def pil_to_pixmap(im):
    im = im.convert("RGB")
    qi = QImage(im.tobytes("raw", "RGB"), im.width, im.height, 3 * im.width, QImage.Format_RGB888)
    return QPixmap.fromImage(qi.copy())


def render_still(scene, style, t=None, size=(960, 540)):
    """Tek bir sahnenin bir karesini (varsayılan: animasyonlar bitmişken) çizer."""
    from PIL import Image
    theme.apply_style(style)
    D._paper = None if getattr(render_still, "_style", None) != style else D._paper
    render_still._style = style
    sc = dict(scene)
    sc.setdefault("duration", 8)
    dur = float(sc["duration"])
    t = dur * 0.6 if t is None else t
    surf, ctx = D.new_surface()
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


# --- Arka plan işçisi --------------------------------------------------------

class Worker(QThread):
    log = Signal(str)
    stage = Signal(int, int, str)
    progress = Signal(float)
    preview = Signal(object)
    planned = Signal(object)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, mode, prompt=None, plan=None, out_dir="", opts=None):
        super().__init__()
        self.mode, self.prompt, self.plan, self.out_dir, self.opts = mode, prompt, plan, out_dir, opts or {}
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
            if self.mode == "plan":
                plan = pipeline.create_plan(self.prompt, self.out_dir, cb=cb)
                self.planned.emit(plan)
            else:
                o = self.opts
                out = pipeline.render_plan(self.plan, self.out_dir, o.get("style"), o.get("voice") or None,
                                           o.get("music") or None, not o.get("voice"), cb=cb)
                self.finished_ok.emit(out)
        except pipeline.Cancelled:
            self.failed.emit("İptal edildi.")
        except Exception as e:
            import traceback
            self.log.emit(traceback.format_exc())
            self.failed.emit(str(e))
        finally:
            sys.stdout = old


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
        self.result.emit(ok, names)


# --- Ana pencere -------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{__version__}")
        self.resize(1440, 900)
        self.settings = QSettings("PromptVideo", "Studio")
        self.plan = None
        self.plan_dir = None
        self.worker = None
        self.last_video = None
        self.style = self.settings.value("style", "cizgi")

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_sidebar())
        lay.addWidget(self._build_main(), 1)

        self.check_ollama()
        QTimer.singleShot(50, self.render_style_cards)
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

        v.addWidget(QLabel("▌PROMPTVIDEO", objectName="brand"))
        v.addWidget(QLabel("// STÜDYO · veri destekli animasyon motoru", objectName="brandsub"))

        v.addWidget(self._section("Konu"))
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Videonun konusunu yazın…\nör. Türkiye'de en çok ihracat yapılan ürünler")
        self.prompt.setFixedHeight(96)
        self.prompt.setPlainText(self.settings.value("prompt", ""))
        v.addWidget(self.prompt)
        for ex in EXAMPLES:
            b = QPushButton("↳ " + ex, objectName="chip")
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.setToolTip(ex)
            b.clicked.connect(lambda _=False, e=ex: self.prompt.setPlainText(e))
            v.addWidget(b)

        v.addWidget(self._section("Görünüm"))
        g = QHBoxLayout()
        self.style_btns = {}
        for key, label in (("cizgi", "ÇİZGİ"), ("modern", "MODERN"), ("mekanik", "MEKANİK")):
            b = QToolButton(objectName="stylecard")
            b.setText(label)
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIconSize(QSize(92, 52))
            b.setChecked(key == self.style)
            b.clicked.connect(lambda _=False, k=key: self.set_style(k))
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            self.style_btns[key] = b
            g.addWidget(b)
        v.addLayout(g)

        v.addWidget(self._section("Seslendirme"))
        self.voice = QComboBox()
        for name, val in VOICES:  # noqa
            self.voice.addItem(name, val)
        self.voice.setCurrentIndex(int(self.settings.value("voice_idx", 0)))
        v.addWidget(self.voice)

        v.addWidget(self._section("Arka plan müziği (isteğe bağlı)"))
        h = QHBoxLayout()
        self.music = QLineEdit(self.settings.value("music", ""))
        self.music.setPlaceholderText("Telifsiz bir mp3 seçin")
        mb = QPushButton("Seç")
        mb.clicked.connect(self.pick_music)
        h.addWidget(self.music, 1)
        h.addWidget(mb)
        v.addLayout(h)

        v.addWidget(self._section("Kayıt klasörü"))
        h = QHBoxLayout()
        default_out = os.path.join(os.path.expanduser("~"), "Videos", "PromptVideo")
        self.outdir = QLineEdit(self.settings.value("outdir", default_out))
        ob = QPushButton("Seç")
        ob.clicked.connect(self.pick_outdir)
        h.addWidget(self.outdir, 1)
        h.addWidget(ob)
        v.addLayout(h)

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

        v.addStretch(1)
        # eylem düğmeleri kaydırma alanının dışında, hep görünür
        v = QVBoxLayout()
        v.setContentsMargins(22, 10, 22, 22)
        v.setSpacing(8)
        outer.addLayout(v)
        self.btn_plan = QPushButton("01 ▸ SENARYOYU HAZIRLA", objectName="primary")
        self.btn_plan.clicked.connect(self.start_plan)
        v.addWidget(self.btn_plan)
        self.btn_render = QPushButton("02 ▸ VİDEOYU OLUŞTUR", objectName="primary")
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
        chk = QPushButton("GÜNCELLEMELERİ DENETLE", objectName="chip")
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
        self.tabs.addTab(self._build_preview_tab(), "Önizleme")
        self.tabs.addTab(self._build_editor_tab(), "Senaryo")
        self.tabs.addTab(self._build_library_tab(), "Videolarım")
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(24, 12, 24, 20)
        l.addWidget(self._build_update_banner())
        l.addWidget(self.tabs)
        return w

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
        self.preview.setText("> Bir konu yazıp  [ SENARYOYU HAZIRLA ]  düğmesine basın_")
        v.addWidget(self.preview, 1)

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

    def _build_editor_tab(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 16, 0, 0)
        left = QVBoxLayout()
        self.scene_list = QListWidget()
        self.scene_list.setFixedWidth(330)
        self.scene_list.currentRowChanged.connect(self.load_scene)
        left.addWidget(self.scene_list, 1)
        tools = QGridLayout()
        self.add_type = QComboBox()
        for k, v in SCENE_TYPES.items():
            self.add_type.addItem(f"{SCENE_ICONS[k]}  {v}", k)
        add = QPushButton("+ Ekle")
        add.clicked.connect(self.add_scene)
        up, down, rm = QPushButton("↑"), QPushButton("↓"), QPushButton("Sil")
        up.clicked.connect(lambda: self.move_scene(-1))
        down.clicked.connect(lambda: self.move_scene(1))
        rm.clicked.connect(self.remove_scene)
        tools.addWidget(self.add_type, 0, 0, 1, 2)
        tools.addWidget(add, 0, 2)
        tools.addWidget(up, 1, 0)
        tools.addWidget(down, 1, 1)
        tools.addWidget(rm, 1, 2)
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
        self.f_data = QPlainTextEdit()
        self.f_data.setPlaceholderText("Sahneye özel alanlar (JSON): veriler, maddeler, tablo satırları…")
        form.addRow(QLabel("TÜR", objectName="formlabel"), self.f_type)
        form.addRow(QLabel("ÜST ETİKET", objectName="formlabel"), self.f_kicker)
        form.addRow(QLabel("BAŞLIK", objectName="formlabel"), self.f_title)
        form.addRow(QLabel("ANLATIM", objectName="formlabel"), self.f_narr)
        form.addRow(QLabel("SÜRE", objectName="formlabel"), self.f_dur)
        form.addRow(QLabel("VERİLER", objectName="formlabel"), self.f_data)
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
    def set_style(self, key):
        self.style = key
        for k, b in self.style_btns.items():
            b.setChecked(k == key)
        self.settings.setValue("style", key)
        self.load_scene(self.scene_list.currentRow())

    def render_style_cards(self):
        sample = {"type": "bar", "kicker": "Örnek", "title": "Şehir nüfusları",
                  "data": [{"label": "İstanbul", "value": 15.7}, {"label": "Ankara", "value": 5.8},
                           {"label": "İzmir", "value": 4.5}]}
        for key, b in self.style_btns.items():
            b.setIcon(QIcon(pil_to_pixmap(render_still(sample, key, 5, (300, 168)))))
        theme.apply_style(self.style)

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
        if names:
            self.ai_status.setText("<span style='color:#FF7A1A'>■ Ollama çalışıyor.</span> Model seçin "
                                   "(önerilen: qwen3:8b ya da daha büyüğü).")
        else:
            self.ai_status.setText(
                "<span style='color:#FF4D1A'>■ Ollama bulunamadı.</span> Program yine çalışır ama senaryo "
                "basit kalır. Ücretsiz kurulum: <a style='color:#FF9A3D' href='https://ollama.com/download'>"
                "ollama.com</a>, sonra komut satırında <b>ollama pull qwen3:8b</b>")

    def set_busy(self, busy):
        self.btn_plan.setEnabled(not busy)
        self.btn_render.setEnabled(not busy and self.plan is not None)
        self.btn_cancel.setVisible(busy)

    def mark_stage(self, i, n, label):
        for k, l in enumerate(self.step_labels):
            l.setProperty("class", "stepdone" if k < i - 1 else ("stepon" if k == i - 1 else "step"))
            l.style().unpolish(l)
            l.style().polish(l)
        self.status.setText(label + "…")
        self.bar.setValue(0)

    def append_log(self, s):
        self.log.appendPlainText(s)

    def show_preview(self, im):
        pm = pil_to_pixmap(im)
        self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def save_settings(self):
        s = self.settings
        s.setValue("prompt", self.prompt.toPlainText())
        s.setValue("voice_idx", self.voice.currentIndex())
        s.setValue("music", self.music.text())
        s.setValue("outdir", self.outdir.text())
        s.setValue("model", self.model.currentText())

    # ---- iş akışı ----
    def start_plan(self):
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, APP_NAME, "Önce videonun konusunu yazın.")
            return
        self.save_settings()
        planner.MODEL = self.model.currentText().strip() or planner.MODEL
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        self.plan_dir = os.path.join(self.outdir.text(), f"{stamp}-{slugify(prompt)}")
        self.log.clear()
        self.tabs.setCurrentIndex(0)
        self.worker = Worker("plan", prompt=prompt, out_dir=self.plan_dir)
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
        opts = {"style": self.style, "voice": self.voice.currentData(), "music": self.music.text().strip()}
        self.tabs.setCurrentIndex(0)
        self.worker = Worker("render", plan=self.plan, out_dir=self.plan_dir, opts=opts)
        self._wire(self.worker)
        self.worker.finished_ok.connect(self.on_rendered)
        self.set_busy(True)
        self.worker.start()

    def _wire(self, w):
        w.log.connect(self.append_log)
        w.stage.connect(self.mark_stage)
        w.progress.connect(lambda f: self.bar.setValue(int(f * 1000)))
        w.preview.connect(self.show_preview)
        w.failed.connect(self.on_failed)

    def cancel(self):
        if self.worker:
            self.worker.cancel()
            self.status.setText("İptal ediliyor…")

    def on_planned(self, plan):
        self.plan = plan
        self.set_busy(False)
        self.populate_scenes()
        self.status.setText(f"Senaryo hazır: {len(plan.get('scenes', []))} sahne. Gözden geçirip “Videoyu oluştur”a basın.")
        self.bar.setValue(1000)
        self.tabs.setCurrentIndex(1)

    def on_rendered(self, path):
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
            it = QListWidgetItem(f"{SCENE_ICONS.get(t, '•')}  {i + 1}. {SCENE_TYPES.get(t, t)}\n     {name[:34]}")
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
        rest = {k: v for k, v in sc.items() if k not in COMMON_KEYS and k != "caption" and not k.startswith("_")}
        self.f_data.setPlainText(json.dumps(rest, ensure_ascii=False, indent=2))
        self.edit_msg.setText("")
        self.scene_preview.setPixmap(pil_to_pixmap(render_still(sc, self.style, size=(533, 300))))

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
            self.scene_preview.setPixmap(pil_to_pixmap(render_still(sc, self.style, size=(533, 300))))
        if preview_only:
            self.edit_msg.setText("Önizleme güncellendi (henüz kaydedilmedi).")
            return
        self.plan["scenes"][row] = sc
        self.write_plan()
        self.populate_scenes(row)
        self.edit_msg.setText("<span style='color:#FF7A1A'>Kaydedildi.</span>")

    def commit_scene_silently(self):
        row = self.scene_list.currentRow()
        if self.plan and row >= 0:
            try:
                self.plan["scenes"][row] = self._scene_from_form()
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
        self.populate_scenes()
        self.btn_render.setEnabled(True)
        self.tabs.setCurrentIndex(1)

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
    app.setStyleSheet(app_stylesheet())
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_app())
