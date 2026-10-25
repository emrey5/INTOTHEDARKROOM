"""Açılış efekti: "karanlık odaya giriş".

Ağır çelik kapının sürgüleri çekilir, kapı açılır; kamera karanlık odanın içine ilerler, dipteki turuncu
karanlık oda lambası (safelight) titreyerek yanar ve DARKROOM harfleri karanlıktan tek tek öne gelip
yerine kilitlenir. Tıklayınca geçilir. Ses Windows'ta winsound, macOS'ta afplay ile çalınır; yoksa sessiz geçer.
"""
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

BG = QColor(6, 5, 5)
ORANGE = QColor(255, 122, 26)
DEEP = QColor(255, 77, 26)
TEXT = QColor(242, 236, 228)
MUTED = QColor(140, 130, 119)
GRID = QColor(40, 34, 30)

DURATION = 2.6
WORD = "DARKROOM"
LINES = ["› kapı kilidi açıldı", "› karanlık oda lambası yandı", "› animasyon motoru hazır"]

# zaman çizelgesi (saniye): ses de bu anlara göre üretilir
T_BOLTS = (0.10, 0.16, 0.22)   # sürgüler çekilir
T_DOOR = (0.28, 0.5)           # kapı açılmaya başlar, süre
T_LAMP = 0.55                  # karanlık oda lambası yanar
T_LETTER = 0.7                 # ilk harf yola çıkar
LETTER_GAP = 0.06
LETTER_FLY = 0.42
T_LOCK = T_LETTER + (len(WORD) - 1) * LETTER_GAP + LETTER_FLY + 0.04  # son kilitlenme
FADE = 0.45                    # sonda ana pencereye yumuşak geçiş


def _p(t, start, dur):
    return max(0.0, min(1.0, (t - start) / dur))


def _ease(x):
    return 1 - (1 - x) ** 3


def _ease_in_out(x):
    return x * x * (3 - 2 * x)


def _lamp(t):
    """Lambanın parlaklığı: yanarken birkaç kez titrer, sonra hafifçe dalgalanır."""
    if t < T_LAMP:
        return 0.0
    d = t - T_LAMP
    rise = _ease_in_out(min(1.0, d / 0.35))
    dip = 0.35 * math.exp(-((d - 0.12) / 0.04) ** 2)  # tek, yumuşak bir titreme
    return max(0.0, rise - dip) * (0.95 + 0.05 * math.sin(t * 9))


def _sound_path():
    """Matrix tarzı dijital ses: yağan kod gibi hızlı dijital bip yağmuru, kapıda veri takılmaları (glitch),
    harflerde şifre çözme cıvıltıları, altta derin dijital nabız ve sonda temiz, derin bir "veri kilidi"."""
    path = os.path.join(tempfile.gettempdir(), "darkroom_acilis_v8.wav")
    if os.path.exists(path):
        return path
    import numpy as np
    from . import audio as A
    sr = A.SR
    rng = np.random.default_rng(1999)
    total = DURATION + 0.4
    out = np.zeros(int(total * sr))

    def tt(d):
        return np.arange(int(d * sr)) / sr

    def put(sec, clip, gain=1.0):
        i = int(sec * sr)
        j = min(len(out), i + len(clip))
        if i < len(out):
            out[i:j] += clip[: j - i] * gain

    def crush(x, bits=6, hold=3):
        """Hafif dijital doku: örnekleri tutarak ve basamaklayarak 'bilgisayar' tınısı verir."""
        x = np.repeat(x[::hold], hold)[: len(x)]
        q = 2 ** (bits - 1)
        return np.round(x * q) / q

    def blip(f, d=0.018):
        t = tt(d)
        return np.sin(2 * np.pi * f * t) * np.exp(-t / (d / 3)) * np.minimum(1, t / 0.0008)

    def chirp(f0, f1, d=0.05):
        """Şifre çözme cıvıltısı: hızla perdesi değişen kısa dijital sinyal."""
        t = tt(d)
        f = f0 * (f1 / f0) ** (t / d)
        x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / (d / 2.5)) * np.minimum(1, t / 0.001)
        return crush(x, 7, 2)

    # 1) dijital yağmur: rastgele bip'ler, kapı açılınca yoğunlaşır, kilitte durulur
    scale = [1046.5, 1174.7, 1396.9, 1568.0, 1760.0, 2093.0, 2349.3, 2793.8, 3136.0]
    k = 0.05
    while k < T_LOCK + 0.5:
        dens = 18 + 70 * _p(k, T_DOOR[0], 0.6) * (1 - 0.7 * _p(k, T_LOCK - 0.2, 0.5))
        g = 0.10 + 0.08 * rng.random()
        put(k, crush(blip(scale[rng.integers(len(scale))] * rng.choice([0.5, 1, 1, 2]), 0.012 + 0.015 * rng.random()), 6, 2), g)
        k += rng.exponential(1 / dens)
    # 2) derin dijital nabız: temiz alçak sinüs, yavaşça kabarır (bozulma yok)
    t = tt(total)
    pulse = np.sin(2 * np.pi * 55 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 2.0 * t) ** 2)
    pulse += 0.35 * np.sin(2 * np.pi * 82.4 * t)
    pulse *= np.clip(t / T_LOCK, 0, 1) ** 1.5 * np.clip((total - t) / 0.8, 0, 1)
    put(0, pulse, 0.18)
    # 3) kapı sürgüleri: kısa dijital tıklar
    for sec in T_BOLTS:
        put(sec, chirp(4000, 1500, 0.025), 0.35)
    # 4) kapı açılırken veri takılması (glitch): aynı küçük dilimin hızla tekrarı
    sl = chirp(2600, 600, 0.03)
    for r in range(7):
        put(T_DOOR[0] + r * 0.028, sl * (1 - r / 9), 0.3)
    n = int((T_DOOR[1] + 0.1) * sr)  # süzülmüş dijital rüzgâr
    wind = np.convolve(rng.standard_normal(n), np.ones(24) / 24, mode="same")
    put(T_DOOR[0], crush(wind * np.sin(np.linspace(0, np.pi, n)) ** 2 * 3, 5, 4), 0.08)
    # 5) lamba: yükselen tarama sinyali
    put(T_LAMP, chirp(300, 2400, 0.18), 0.22)
    # 6) harfler: her biri şifre çözme cıvıltısı (yüksekten alçağa), perde harften harfe iner
    for i in range(len(WORD)):
        put(T_LETTER + i * LETTER_GAP + LETTER_FLY - 0.02, chirp(3600 - i * 160, 900 - i * 40, 0.045), 0.3)
    # 7) veri kilidi: kısa ters süpürme + derin temiz darbe + aşağı inen dijital ışıltı
    n = int(0.35 * sr)
    rev = np.convolve(rng.standard_normal(n), np.ones(10) / 10, mode="same") * np.linspace(0, 1, n) ** 3
    put(T_LOCK - 0.35, rev, 0.25)
    t = tt(1.4)
    boom = np.sin(2 * np.pi * np.cumsum(110 * np.exp(-t * 7) + 41) / sr) * np.exp(-t / 0.45) * np.minimum(1, t / 0.003)
    put(T_LOCK, boom, 0.75)
    for j, f in enumerate((3136.0, 2349.3, 1760.0, 1396.9, 1046.5, 783.99)):
        put(T_LOCK + 0.04 + j * 0.045, blip(f, 0.08), 0.18)
    # pencere geçişiyle sönme
    fo, end = int(0.6 * sr), int((DURATION + 0.3) * sr)
    out[end - fo:end] *= np.linspace(1, 0, fo)
    out[end:] = 0
    peak = np.max(np.abs(out)) or 1
    A._write(path, out / peak * 0.7)
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
        self.t0 = None
        self.timer = QTimer(self, interval=16)
        self.timer.timeout.connect(self._tick)
        self._done = False
        self._handed = False
        rnd = random.Random(3)
        self.dust = [(rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.2, 1)) for _ in range(70)]
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
        t = self.elapsed()
        if t >= DURATION - FADE and not self._handed:
            self._handed = True
            self.finished.emit()  # ana pencere, açılış solarken belirmeye başlar
        if t >= DURATION:
            self._finish()
        else:
            self.update()

    def _finish(self):
        if self._done:
            return
        self._done = True
        self.timer.stop()
        self.close()
        if not self._handed:
            self._handed = True
            self.finished.emit()

    # ---- çizim ----
    def paintEvent(self, _):
        t = self.elapsed()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setOpacity(_ease(_p(t, 0, 0.2)) * (1 - _ease_in_out(_p(t, DURATION - FADE, FADE))))
        p.setPen(QPen(QColor(60, 48, 40), 1))
        p.setBrush(BG)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 14, 14)
        p.setClipPath(clip)
        # kamera hafifçe sarsılır: kapı dayandığında ve son kilitlenmede
        shake = 0.0
        for at, amp in ((T_LOCK, 1.5),):  # yalnızca kilitlenmede çok hafif
            d = t - at
            if 0 <= d < 0.35:
                shake += amp * math.exp(-d * 12) * math.sin(d * 90)
        p.translate(0, shake)
        self._room(p, t, w, h)
        self._letters(p, t, w, h)
        self._door(p, t, w, h)
        p.translate(0, -shake)
        self._hud(p, t, w, h)
        p.restore()
        p.setPen(QPen(ORANGE, 3))
        k = 22 * _ease(_p(t, 0.1, 0.4))
        for x, y, dx, dy in ((14, 14, 1, 1), (w - 14, 14, -1, 1), (14, h - 14, 1, -1), (w - 14, h - 14, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * k, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + dy * k))
        p.end()

    def _vp(self, w, h):
        return w / 2, h / 2 - 30

    def _room(self, p, t, w, h):
        """Perspektif oda: kamera içeri ilerledikçe tavan/zemin/duvar çerçeveleri yaklaşır."""
        vx, vy = self._vp(w, h)
        lamp = _lamp(t)
        # kapı açılınca ilerleme başlar, sonra yavaşlayarak durur
        travel = _ease(_p(t, T_DOOR[0] + 0.2, T_LOCK - T_DOOR[0])) * 3.2
        # dipteki karanlık oda lambası
        if lamp > 0:
            g = QRadialGradient(QPointF(vx, vy), 420)
            for stop, a in ((0, 0.55), (0.25, 0.22), (1, 0)):
                c = QColor(DEEP)
                c.setAlphaF(a * lamp)
                g.setColorAt(stop, c)
            p.fillRect(QRectF(0, 0, w, h), g)
        rw, rh = 1.25, 0.95  # oda kesiti (görüntüye göre oran)
        light = 0.25 + 0.75 * lamp
        frames = []
        for k in range(12):
            z = (k * 0.55 - travel) % 6.6 + 0.35
            frames.append(z)
        frames.sort(reverse=True)
        for z in frames:
            s = 1 / z
            hw, hh = rw * s * w / 2, rh * s * h / 2
            fog = max(0.0, min(1.0, 1.6 / z)) * max(0.0, min(1.0, (6.9 - z) / 1.2))
            c = QColor(ORANGE) if lamp > 0 else QColor(90, 80, 72)
            c.setAlphaF(0.32 * fog * light)
            p.setPen(QPen(c, 1.2 + 1.5 * s))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(vx - hw, vy - hh, hw * 2, hh * 2))
        # köşelerden kaçış noktasına uzanan kenarlar ve zemin çizgileri
        c = QColor(ORANGE) if lamp > 0 else QColor(90, 80, 72)
        c.setAlphaF(0.22 * light)
        p.setPen(QPen(c, 1.2))
        for fx in (-1, -0.5, 0, 0.5, 1):
            p.drawLine(QPointF(vx, vy), QPointF(vx + fx * rw * w * 1.4, vy + rh * h * 1.4))
        for sx, sy in ((-1, -1), (1, -1)):
            p.drawLine(QPointF(vx, vy), QPointF(vx + sx * rw * w * 1.4, vy + sy * rh * h * 1.4))
        # havada süzülen toz, lambanın ışığında görünür
        if lamp > 0:
            for i, (dx, dy, z0) in enumerate(self.dust):
                z = (z0 * 3 - travel * 0.8 - t * 0.05) % 3 + 0.2
                x, y = vx + dx * w * 0.5 / z, vy + dy * h * 0.4 / z
                c = QColor(255, 170, 110)
                c.setAlphaF(min(0.5, 0.25 / z) * lamp)
                p.setPen(Qt.NoPen)
                p.setBrush(c)
                p.drawEllipse(QPointF(x, y), 1.2 / z, 1.2 / z)
        # kenarlar karanlıkta kalır
        vg = QRadialGradient(QPointF(vx, vy), w * 0.62)
        vg.setColorAt(0.45, QColor(0, 0, 0, 0))
        vg.setColorAt(1, QColor(0, 0, 0, 235))
        p.fillRect(QRectF(0, 0, w, h), vg)

    def _letters(self, p, t, w, h):
        """Harfler dipteki karanlıktan kamera ilerledikçe öne gelir ve yerine çakılır."""
        vx, vy = self._vp(w, h)
        f = QFont("JetBrains Mono", 46)
        f.setWeight(QFont.ExtraBold)
        p.setFont(f)
        fm = p.fontMetrics()
        cw = fm.horizontalAdvance("M") + 10
        total = cw * len(WORD) - 10
        x0, y0 = w / 2 - total / 2, h / 2 + 4
        lamp = _lamp(t)
        for i, ch in enumerate(WORD):
            st = T_LETTER + i * LETTER_GAP
            q = _p(t, st, LETTER_FLY)
            if q <= 0:
                continue
            e = _ease_in_out(q) ** 1.4  # derinlik hissi, ama yumuşak duruş
            fx, fy = x0 + i * cw + cw / 2, y0
            x, y = vx + (fx - vx) * e, vy + (fy - vy) * e
            sc = 0.06 + 0.94 * e
            base = TEXT if i < 4 else ORANGE
            dark = 0.15 + 0.85 * e
            col = QColor(int(base.red() * dark), int(base.green() * dark), int(base.blue() * dark))
            col.setAlphaF(min(1.0, q * 2.5))  # karanlıktan yavaşça belirir
            p.save()
            p.translate(x, y)
            p.scale(sc, sc)
            # çakıldığı an kısa bir parlama
            flash = 1 - _ease(_p(t, st + LETTER_FLY, 0.3))
            if q >= 1 and flash > 0:
                g = QRadialGradient(QPointF(0, -18), 60)
                c = QColor(ORANGE)
                c.setAlphaF(0.3 * flash)
                g.setColorAt(0, c)
                c2 = QColor(ORANGE)
                c2.setAlphaF(0)
                g.setColorAt(1, c2)
                p.fillRect(QRectF(-60, -80, 120, 120), g)
            # lambanın sıcak yansıması: harfin altına turuncu bir hale
            if lamp > 0 and q >= 1:
                p.setPen(QColor(255, 90, 20, int(70 * lamp)))
                p.drawText(QPointF(-fm.horizontalAdvance(ch) / 2, 3), ch)
            p.setPen(col)
            p.drawText(QPointF(-fm.horizontalAdvance(ch) / 2, 0), ch)
            p.restore()
        # son kilitlenmede alt çizgi ve slogan
        lk = _ease(_p(t, T_LOCK, 0.3))
        if lk > 0:
            p.fillRect(QRectF(w / 2 - total / 2 * lk, y0 + 18, total * lk, 4), ORANGE)
        sub = "credit by EC"
        sa = _ease(_p(t, T_LOCK + 0.05, 0.35))
        if sa > 0:
            p.setFont(QFont("JetBrains Mono", 11))
            c = QColor(MUTED)
            c.setAlphaF(sa)
            p.setPen(c)
            fm2 = p.fontMetrics()
            p.drawText(QPointF(w / 2 - fm2.horizontalAdvance(sub) / 2, y0 + 50 + (1 - sa) * 8), sub)

    def _door(self, p, t, w, h):
        """Perçinli, uyarı şeritli iki kanatlı çelik kapı; sürgüler çekilir, kanatlar yana kayar."""
        op = _ease_in_out(_p(t, T_DOOR[0], T_DOOR[1]))
        if op >= 1:
            return
        half = w / 2
        for side in (-1, 1):
            off = op * half * 1.05 * side
            x = (0 if side < 0 else half) + off
            rect = QRectF(x, 0, half, h)
            g = QLinearGradient(rect.left(), 0, rect.right(), 0)
            g.setColorAt(0, QColor(30, 27, 25) if side < 0 else QColor(44, 40, 37))
            g.setColorAt(1, QColor(44, 40, 37) if side < 0 else QColor(30, 27, 25))
            p.fillRect(rect, g)
            # yatay panel çizgileri ve perçinler
            p.setPen(QPen(QColor(18, 16, 15), 2))
            for yy in (h * 0.25, h * 0.5, h * 0.75):
                p.drawLine(QPointF(rect.left() + 20, yy), QPointF(rect.right() - 20, yy))
            p.setPen(Qt.NoPen)
            for yy in range(30, h, 40):
                for xx in (rect.left() + 22, rect.right() - 22):
                    p.setBrush(QColor(70, 63, 58))
                    p.drawEllipse(QPointF(xx, yy), 3.2, 3.2)
                    p.setBrush(QColor(20, 18, 16))
                    p.drawEllipse(QPointF(xx + 1, yy + 1), 1.6, 1.6)
            # birleşim kenarında uyarı şeridi
            ex = rect.right() - 26 if side < 0 else rect.left()
            p.save()
            p.setClipRect(QRectF(ex, 0, 26, h))
            p.fillRect(QRectF(ex, 0, 26, h), QColor(20, 18, 16))
            p.setBrush(ORANGE)
            for yy in range(-40, h + 40, 28):
                path = QPainterPath()
                path.moveTo(ex, yy)
                path.lineTo(ex + 26, yy - 14)
                path.lineTo(ex + 26, yy - 2)
                path.lineTo(ex, yy + 12)
                path.closeSubpath()
                p.drawPath(path)
            p.restore()
            # kapı üstündeki yazı
            p.setFont(QFont("JetBrains Mono", 13, QFont.Bold))
            p.setPen(QColor(120, 108, 98))
            label = "DARK" if side < 0 else "ROOM"
            fm = p.fontMetrics()
            lx = rect.right() - 60 - fm.horizontalAdvance(label) if side < 0 else rect.left() + 60
            p.drawText(QPointF(lx, h * 0.5 + 40), label)
        # sürgüler: kapının ortasından yana çekilir
        if op <= 0:
            for yy, at in zip((h * 0.25, h * 0.5, h * 0.75), T_BOLTS):
                pull = _ease(_p(t, at, 0.1))
                bx = half - 46
                p.fillRect(QRectF(bx - pull * 60, yy - 9, 92, 18), QColor(88, 80, 74))
                p.fillRect(QRectF(bx - pull * 60, yy - 9, 92, 3), QColor(130, 120, 110))
                p.setBrush(ORANGE if pull >= 1 else QColor(160, 40, 20))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(half - 80, yy - 22), 4, 4)  # durum ışığı: kırmızı → turuncu

    def _hud(self, p, t, w, h):
        p.setFont(QFont("JetBrains Mono", 10))
        y0 = h - 92
        for i, (ln, at) in enumerate(zip(LINES, (T_BOLTS[-1] + 0.1, T_LAMP + 0.1, T_LOCK))):
            if t < at:
                continue
            p.setPen(MUTED)
            p.drawText(QPointF(40, y0 + i * 18), ln)
            if t > at + 0.2:
                p.setPen(ORANGE)
                p.drawText(QPointF(290, y0 + i * 18), "[ OK ]")
        pr = _ease(_p(t, 0.1, T_LOCK))
        bx, by, bw = 40, h - 26, w - 80
        p.fillRect(QRectF(bx, by, bw, 3), GRID)
        p.fillRect(QRectF(bx, by, bw * pr, 3), ORANGE)
        if self.version:
            p.setPen(MUTED)
            p.drawText(QRectF(bx, by - 22, bw, 18), Qt.AlignRight | Qt.AlignVCenter, f"v{self.version}")
