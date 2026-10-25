"""Açılış efekti: diyafram açılır, DARKROOM harfleri şifre çözer gibi yerine oturur, sistem satırları akar.
Tıklayınca geçilir. Ses Windows'ta winsound, macOS'ta afplay ile çalınır; yoksa sessiz geçer."""
import math
import os
import random
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient, QLinearGradient
from PySide6.QtWidgets import QWidget, QApplication

BG = QColor(10, 9, 8)
ORANGE = QColor(255, 122, 26)
DEEP = QColor(255, 77, 26)
TEXT = QColor(242, 236, 228)
MUTED = QColor(140, 130, 119)
GRID = QColor(40, 34, 30)

DURATION = 3.2
WORD = "DARKROOM"
GLYPHS = "ABCDEFGHJKLMNPRSTUVXYZ0123456789#%&$*+<>/"
LINES = ["› yazı tipleri yüklendi", "› harita verisi hazır", "› ses motoru çalışıyor", "› animasyon motoru hazır"]


def _p(t, start, dur):
    return max(0.0, min(1.0, (t - start) / dur))


def _ease(x):
    return 1 - (1 - x) ** 3


def _back(x, s=1.8):
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def _sound_path():
    """Metal dövme sesi: örs üstünde çekiç vuruşları (her vuruştan sonra küçük sekme tıkı),
    en sonda en ağır vuruş ve suya batırılan kızgın demirin tıslaması."""
    path = os.path.join(tempfile.gettempdir(), "darkroom_acilis_v3.wav")
    if os.path.exists(path):
        return path
    import numpy as np
    from . import audio as A
    sr = A.SR
    rng = np.random.default_rng(11)
    out = np.zeros(int(3.6 * sr))

    def tt(d):
        return np.arange(int(d * sr)) / sr

    def put(sec, clip, gain=1.0):
        i = int(sec * sr)
        j = min(len(out), i + len(clip))
        out[i:j] += clip[: j - i] * gain

    def hp(x, k=2):
        return x - np.convolve(x, np.ones(k) / k, mode="same")

    def strike(f0=1050, ring=1.0, weight=1.0):
        """Örs vuruşu: çelik çubuğun uyumsuz titreşim kipleri + çekiç darbesi + gövde gümbürtüsü."""
        t = tt(0.4 + 1.6 * ring)
        modes = ((1.0, 1.0, 0.9), (2.76, 0.55, 0.45), (5.40, 0.35, 0.22), (8.93, 0.22, 0.12), (1.5, 0.25, 0.6))
        x = sum(a * np.sin(2 * np.pi * f0 * m * (1 + rng.uniform(-0.003, 0.003)) * t + rng.random() * 6)
                * np.exp(-t / (dcy * ring)) for m, a, dcy in modes)
        # hafif vuruntu (iki yakın frekans) metale canlılık verir
        x *= 1 + 0.12 * np.sin(2 * np.pi * 5.5 * t)
        hit = hp(rng.standard_normal(len(t))) * np.exp(-t / 0.0025) * 1.6
        body = np.sin(2 * np.pi * np.cumsum(160 * np.exp(-t * 20) + 70) / sr) * np.exp(-t / 0.05) * weight
        return (x * 0.55 + hit + body * 0.8) * np.minimum(1, t / 0.0008)

    def tap(f0):
        """Çekicin örsten sekmesi: kısa, ince bir tın."""
        return strike(f0 * 1.04, ring=0.18, weight=0.1) * 0.35

    # ritim: VURUŞ ... tık, görüntüdeki anlarla eşleşir (diyafram, harfler, kilitlenme)
    for sec, f0, g in ((0.08, 980, 0.75), (0.52, 1010, 0.8), (0.98, 1040, 0.85)):
        put(sec, strike(f0, ring=0.8), g)
        put(sec + 0.13, tap(f0), 1.0)
        put(sec + 0.21, tap(f0) * 0.5, 1.0)
    # son ve en ağır vuruş: uzun çınlama
    put(1.60, strike(900, ring=1.5, weight=1.6), 1.0)
    put(1.60, strike(1350, ring=1.0, weight=0.0), 0.35)  # ikinci tını: daha zengin metal
    # kızgın demir suya: tıslama
    ht = tt(1.3)
    hiss = hp(rng.standard_normal(len(ht)), 3)
    hiss *= np.minimum(1, ht / 0.04) * np.exp(-ht / 0.45) * (1 + 0.3 * rng.standard_normal(len(ht)) * 0.2)
    put(2.0, hiss, 0.12)
    peak = np.max(np.abs(out)) or 1
    A._write(path, np.tanh(out / peak * 1.3) * 0.88)
    return path


def play_sound():
    try:
        path = _sound_path()
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        elif sys.platform == "darwin":
            subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            for player in ("paplay", "aplay"):
                try:
                    subprocess.Popen([player, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    break
                except FileNotFoundError:
                    continue
    except Exception:
        pass  # ses çalınamazsa açılış sessiz devam eder


class Splash(QWidget):
    finished = Signal()

    def __init__(self, version="", sound=True, clock=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(820, 480)
        self.version = version
        self.sound = sound
        self.clock = clock  # test için sabit zaman verilebilir
        self.rng = random.Random(5)
        self.t0 = None
        self.timer = QTimer(self, interval=16)
        self.timer.timeout.connect(self._tick)
        self._done = False
        scr = QApplication.primaryScreen()
        if scr:
            g = scr.availableGeometry()
            self.move(g.center().x() - self.width() // 2, g.center().y() - self.height() // 2)

    def start(self):
        self.t0 = time.perf_counter()
        self.show()
        self.timer.start()
        if self.sound:
            QTimer.singleShot(30, play_sound)

    def elapsed(self):
        if self.clock is not None:
            return self.clock
        return time.perf_counter() - self.t0 if self.t0 else 0.0

    def mousePressEvent(self, e):
        self._finish()

    def _tick(self):
        if self.elapsed() >= DURATION:
            self._finish()
        else:
            self.update()

    def _finish(self):
        if self._done:
            return
        self._done = True
        self.timer.stop()
        self.close()
        self.finished.emit()

    # ---- çizim ----
    def paintEvent(self, _):
        t = self.elapsed()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        a = _ease(_p(t, 0, 0.35)) * (1 - _p(t, DURATION - 0.35, 0.35))
        p.setOpacity(a)
        # gövde
        p.setPen(QPen(QColor(60, 48, 40), 1))
        p.setBrush(BG)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 14, 14)
        p.setClipPath(clip)
        # ızgara
        p.setPen(QPen(GRID, 1))
        for x in range(0, w, 32):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 32):
            p.drawLine(0, y, w, y)
        cx, cy = 210, h / 2 - 10
        # arkadaki turuncu ışık
        glow = _ease(_p(t, 0.4, 0.9))
        g = QRadialGradient(QPointF(cx, cy), 260)
        c0 = QColor(ORANGE)
        c0.setAlphaF(0.32 * glow)
        c1 = QColor(ORANGE)
        c1.setAlphaF(0)
        g.setColorAt(0, c0)
        g.setColorAt(1, c1)
        p.fillRect(0, 0, w, h, g)
        self._aperture(p, t, cx, cy)
        self._wordmark(p, t, 400, cy)
        self._status(p, t, w, h)
        # tarama çizgisi
        sp = _p(t, 0.9, 0.7)
        if 0 < sp < 1:
            y = sp * h
            lg = QLinearGradient(0, y - 40, 0, y)
            c = QColor(ORANGE)
            c.setAlphaF(0)
            lg.setColorAt(0, c)
            c2 = QColor(ORANGE)
            c2.setAlphaF(0.22)
            lg.setColorAt(1, c2)
            p.fillRect(QRectF(0, y - 40, w, 40), lg)
            p.fillRect(QRectF(0, y, w, 2), ORANGE)
        p.restore()
        # köşe işaretleri
        p.setPen(QPen(ORANGE, 3))
        k = 22 * _ease(_p(t, 0.1, 0.4))
        for x, y, dx, dy in ((14, 14, 1, 1), (w - 14, 14, -1, 1), (14, h - 14, 1, -1), (w - 14, h - 14, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * k, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + dy * k))
        p.end()

    def _aperture(self, p, t, cx, cy):
        R = 118
        ring_in = _back(_p(t, 0.05, 0.5))
        if ring_in <= 0:
            return
        p.save()
        p.translate(cx, cy)
        p.scale(ring_in, ring_in)
        # dış halka ve dönen ölçek çizgileri
        p.setPen(QPen(QColor(70, 58, 50), 10))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), R + 16, R + 16)
        rot = t * 40 + _ease(_p(t, 0.3, 0.8)) * 120
        for i in range(60):
            ang = math.radians(i * 6 + rot)
            big = i % 5 == 0
            r1, r2 = R + 28, R + (40 if big else 34)
            col = QColor(ORANGE) if big else QColor(MUTED)
            p.setPen(QPen(col, 2 if big else 1))
            p.drawLine(QPointF(math.cos(ang) * r1, math.sin(ang) * r1), QPointF(math.cos(ang) * r2, math.sin(ang) * r2))
        # diyafram kanatları: kapalıdan açığa
        op = _ease(_p(t, 0.35, 0.75)) * 0.82 - 0.06 * math.sin(_p(t, 0.35, 1.2) * math.pi)
        hole = max(0.0, op) * R
        lens = QRadialGradient(QPointF(0, 0), R)
        lens.setColorAt(0, QColor(255, 170, 90))
        lens.setColorAt(0.45, ORANGE)
        lens.setColorAt(1, DEEP.darker(220))
        p.setPen(Qt.NoPen)
        p.setBrush(lens)
        p.drawEllipse(QPointF(0, 0), R, R)
        clip = QPainterPath()
        clip.addEllipse(QPointF(0, 0), R, R)
        p.setClipPath(clip)
        n = 7
        for i in range(n):
            base = i * 2 * math.pi / n + (1 - max(0.0, op)) * 0.9
            path = QPainterPath()
            # her kanat, deliğin kenarına teğet geniş bir dörtgen
            ax, ay = math.cos(base), math.sin(base)
            tx, ty = -ay, ax
            p0 = QPointF(ax * hole, ay * hole)
            path.moveTo(p0)
            path.lineTo(QPointF(p0.x() + tx * R * 2.2, p0.y() + ty * R * 2.2))
            path.lineTo(QPointF(p0.x() + tx * R * 2.2 + ax * R * 2, p0.y() + ty * R * 2.2 + ay * R * 2))
            path.lineTo(QPointF(p0.x() + ax * R * 2, p0.y() + ay * R * 2))
            path.closeSubpath()
            shade = 34 + (i % 2) * 8
            p.setBrush(QColor(shade, shade - 4, shade - 8))
            p.setPen(QPen(QColor(12, 10, 9), 2))
            p.drawPath(path)
        p.setClipping(False)
        p.setPen(QPen(ORANGE, 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), R, R)
        p.restore()

    def _wordmark(self, p, t, x, cy):
        f = QFont("JetBrains Mono", 40)
        f.setWeight(QFont.ExtraBold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        p.setFont(f)
        fm = p.fontMetrics()
        cw = fm.horizontalAdvance("M") + 4
        bar = _ease(_p(t, 0.7, 0.35))
        if bar > 0:
            p.fillRect(QRectF(x, cy - 52, 10, 66 * bar), ORANGE)
        for i, ch in enumerate(WORD):
            st = 0.85 + i * 0.07
            if t < st:
                continue
            settle = st + 0.28
            if t < settle:
                ch = GLYPHS[int(t * 40 + i * 7) % len(GLYPHS)]
                p.setPen(ORANGE)
            else:
                p.setPen(TEXT if i < 4 else ORANGE)
            jitter = (1 - _p(t, st, 0.28)) * 6
            p.drawText(QPointF(x + 26 + i * cw, cy + jitter), ch)
        sub = "// PROMPT → VIDEO · animasyon motoru"
        n = int(len(sub) * _p(t, 1.55, 0.6))
        if n:
            f2 = QFont("JetBrains Mono", 11)
            p.setFont(f2)
            p.setPen(MUTED)
            cursor = "▌" if n < len(sub) or int(t * 3) % 2 == 0 else ""
            p.drawText(QPointF(x + 28, cy + 40), sub[:n] + cursor)

    def _status(self, p, t, w, h):
        f = QFont("JetBrains Mono", 10)
        p.setFont(f)
        y0 = h - 104
        for i, ln in enumerate(LINES):
            st = 0.6 + i * 0.38
            if t < st:
                continue
            p.setPen(MUTED)
            p.drawText(QPointF(410, y0 + i * 18), ln)
            if t > st + 0.25:
                p.setPen(ORANGE)
                p.drawText(QPointF(640, y0 + i * 18), "[ OK ]")
        # ilerleme çubuğu
        pr = _ease(_p(t, 0.2, DURATION - 0.8))
        bx, by, bw = 40, h - 30, w - 80
        p.fillRect(QRectF(bx, by, bw, 4), GRID)
        p.fillRect(QRectF(bx, by, bw * pr, 4), ORANGE)
        p.setPen(MUTED)
        p.drawText(QPointF(bx, by - 10), f"SİSTEM HAZIRLANIYOR  {int(pr * 100):3d}%")
        if self.version:
            p.drawText(QRectF(bx, by - 24, bw, 18), Qt.AlignRight | Qt.AlignVCenter, f"v{self.version}")
