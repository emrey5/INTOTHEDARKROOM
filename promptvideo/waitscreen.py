"""Bekleme ekranı: piksel sanat tarzında, kayayı dağın tepesine iten adam.

İşin ilerlemesi adamın yamaçtaki yerini belirler: yüzde 0'da dağın eteğinde, yüzde 100'de zirvede.
Sahne düşük çözünürlüklü bir görüntüye kenar yumuşatma olmadan çizilir ve tam sayı katıyla büyütülür;
böylece gerçek piksel görünümü oluşur.
"""
import math
import random
import time

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

PW, PH = 192, 108  # piksel tuvali

SKY = [(8, 7, 7), (14, 11, 10), (22, 15, 12), (34, 20, 14), (52, 26, 14)]
MOUNT = (26, 22, 20)
MOUNT_DARK = (17, 15, 14)
RIM = (255, 122, 26)
FAR = (20, 16, 15)
ROCK = (92, 84, 78)
ROCK_DARK = (58, 52, 48)
ROCK_LIGHT = (140, 128, 118)
SHIRT = (226, 218, 206)
SHIRT_DARK = (150, 142, 132)
BAND = (255, 122, 26)
PANTS = (62, 54, 48)
SKIN = (232, 186, 148)
HAIR = (30, 22, 18)
TEXT = QColor(242, 236, 228)
MUTED = QColor(140, 130, 119)
ORANGE = QColor(255, 122, 26)

BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))

X0, Y0 = 6, 100          # yamacın başladığı yer
SX, SY = 150, 30         # zirve
R = 8                    # kayanın yarıçapı

TIPS = ["Kaya ağır ama veri sağlam…", "Zirveye az kaldı, sabır…", "Her kare tek tek boyanıyor…",
        "Kaynaklar okunuyor, sayılar tartılıyor…", "Sisifos bile mola vermez…", "Grafikler yerine oturuyor…"]


def _slope_y(x):
    """Yamaç yüksekliği: eteğinden zirveye basamaklı bir çizgi, zirveden sonra hafif iniş."""
    if x <= SX:
        k = (Y0 - SY) / (SX - X0)
        y = Y0 - (x - X0) * k
        y += 1.5 * math.sin(x * 0.35) + 0.8 * math.sin(x * 1.3)  # kayalık pürüzler
        return y
    return SY + (x - SX) * 0.55


class WaitScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.img = QImage(PW, PH, QImage.Format_RGB32)
        self.target = 0.0      # gerçek ilerleme (0-1)
        self.shown = 0.0       # ekranda yumuşatılmış ilerleme
        self.stage = ""
        self.t0 = time.perf_counter()
        self.clock = None      # test için sabit zaman verilebilir
        self.timer = QTimer(self, interval=33)
        self.timer.timeout.connect(self._tick)
        rnd = random.Random(7)
        self.stars = [(rnd.randrange(PW), rnd.randrange(60), rnd.random() * 6) for _ in range(46)]
        self.far = [52 + 10 * math.sin(x * 0.07) + 6 * math.sin(x * 0.19 + 1) for x in range(PW)]
        self.texture = [(rnd.randrange(PW), rnd.randrange(30, PH)) for _ in range(160)]
        self.dust = []

    # ---- dışarıdan çağrılanlar ----
    def start(self, label=""):
        self.target = self.shown = 0.0
        self.stage = label
        self.dust = []
        self.t0 = time.perf_counter()
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def set_progress(self, frac):
        self.target = max(self.target, max(0.0, min(1.0, frac)))  # adam geri kaymaz

    def set_stage(self, label):
        self.stage = label

    # ---- iç işler ----
    def elapsed(self):
        return self.clock if self.clock is not None else time.perf_counter() - self.t0

    def _tick(self):
        self.shown += (self.target - self.shown) * 0.06
        self.update()

    def _px(self, p, x, y, c):
        if 0 <= x < PW and 0 <= y < PH:
            p.fillRect(int(x), int(y), 1, 1, QColor(*c))

    def _background(self):
        """Değişmeyen katman bir kez çizilir: gökyüzü, ay, uzak dağlar, ana dağ."""
        img = QImage(PW, PH, QImage.Format_RGB32)
        p = QPainter(img)
        for y in range(PH):  # gökyüzü: bantlı ve noktalı (dithering) geçiş
            f = y / PH * (len(SKY) - 1)
            i = int(f)
            frac = f - i
            for x in range(PW):
                th = (BAYER[y % 4][x % 4] + 0.5) / 16
                c = SKY[min(i + 1, len(SKY) - 1)] if frac > th else SKY[i]
                img.setPixel(x, y, QColor(*c).rgb())
        mx, my, mr = 168, 17, 9  # dolunay (turuncu), kraterli
        for yy in range(-mr, mr + 1):
            for xx in range(-mr, mr + 1):
                d = xx * xx + yy * yy
                if d <= mr * mr:
                    c = (255, 150, 60) if d < (mr - 2) ** 2 else (230, 110, 30)
                    if (xx + 3) ** 2 + (yy + 2) ** 2 < 5 or (xx - 3) ** 2 + (yy - 3) ** 2 < 3:
                        c = (210, 100, 30)
                    self._px(p, mx + xx, my + yy, c)
        for x in range(PW):  # uzaktaki dağlar
            p.fillRect(x, int(self.far[x]), 1, PH, QColor(*FAR))
        p.end()
        self.stars_bg = img.copy()  # yıldızlar dağların arkasında kalsın diye ayrı katman
        p = QPainter(img)
        for x in range(PW):  # ana dağ
            top = int(_slope_y(x))
            p.fillRect(x, top, 1, PH, QColor(*MOUNT))
            for y in range(top + 14, PH):
                if (x + y) % 3 == 0:
                    self._px(p, x, y, MOUNT_DARK)
            self._px(p, x, top, RIM)  # ay ışığında parlayan sırt
            if x % 3 == 0:
                self._px(p, x, top + 1, (150, 70, 20))
        for x, y in self.texture:
            if y > _slope_y(x) + 2:
                self._px(p, x, y, MOUNT_DARK)
        p.end()
        return img

    def _render(self, t):
        if not hasattr(self, "bg"):
            self.bg = self._background()
            self.sky_mask = [[self.stars_bg.pixel(x, y) == self.bg.pixel(x, y) for x in range(PW)]
                             for y in range(60)]
        self.img = self.bg.copy()
        p = QPainter(self.img)
        # yıldızlar (yalnızca açık gökyüzünde) göz kırpar
        for x, y, ph in self.stars:
            b = 0.5 + 0.5 * math.sin(t * 2 + ph)
            if b > 0.35 and y < self.far[x] and self.sky_mask[y][x]:
                v = int(120 + 120 * b)
                self._px(p, x, y, (v, v - 20, v - 40))
        # süzülen sis şeritleri
        for k in range(3):
            y = 62 + k * 9
            off = int(t * (3 + k)) % (PW + 60) - 60
            for x in range(off, off + 40 + k * 10):
                if (x + y) % 2 == 0 and y < _slope_y(x):
                    self._px(p, x, y, (40, 30, 26))
        # zirvede dalgalanan bayrak
        fx, fy = SX + 2, int(_slope_y(SX + 2))
        for k in range(9):
            self._px(p, fx, fy - k, (160, 150, 140))
        wave = int(t * 6) % 2
        for yy in range(3):
            for xx in range(5):
                self._px(p, fx + 1 + xx, fy - 9 + yy + (1 if xx > 2 and wave else 0), RIM)
        # ilerlemeye göre kaya ve adam
        done = self.shown > 0.985
        bx = 22 + (SX - 12 - 22) * self.shown
        by = _slope_y(bx) - R + 1
        ang = -(bx / R)  # yuvarlandıkça döner
        self._rock(p, bx, by, ang)
        self._man(p, t, bx - R - 10, done, bx)
        # ayak tozları
        if not done and int(t * 10) % 3 == 0:
            self.dust.append([bx - R - 6, _slope_y(bx - R - 6) - 1, 0.0])
        for d in self.dust:
            d[2] += 0.033
            d[0] -= 0.6
            d[1] -= 0.25
            if d[2] < 0.8:
                self._px(p, d[0], d[1], (110, 96, 86) if d[2] < 0.4 else (70, 60, 54))
        self.dust = [d for d in self.dust if d[2] < 0.8]
        p.end()

    def _rock(self, p, cx, cy, ang):
        for yy in range(-R, R + 1):
            for xx in range(-R, R + 1):
                d = xx * xx + yy * yy
                if d <= R * R + 2:
                    c = ROCK
                    if xx + yy > 4:
                        c = ROCK_DARK  # sağ alt gölge
                    elif xx + yy < -6 and d < (R - 1) ** 2:
                        c = ROCK_LIGHT
                    self._px(p, cx + xx, cy + yy, c)
        # dönen çatlaklar: kaya yuvarlanıyor hissi
        for k in range(3):
            a = ang + k * 2.1
            for rr in range(1, R - 1):
                self._px(p, cx + math.cos(a) * rr * 0.8, cy + math.sin(a) * rr * 0.8 + (rr % 2), ROCK_DARK)

    def _line(self, p, x1, y1, x2, y2, c, w=1):
        n = int(max(abs(x2 - x1), abs(y2 - y1))) + 1
        for i in range(n + 1):
            x = x1 + (x2 - x1) * i / n
            y = y1 + (y2 - y1) * i / n
            for dx in range(w):
                self._px(p, round(x) + dx, round(y), c)

    def _man(self, p, t, x, done, rock_x):
        """Öne eğilmiş, kayayı iten (ya da zirvede sevinen) piksel adam. Boyu yaklaşık 18 piksel."""
        ph = t * 6
        fy = _slope_y(x)
        hip = (x, fy - 9)
        if done:
            sh, head = (x, fy - 17), (x - 2, fy - 23)
        else:
            sh, head = (x + 5, fy - 15), (x + 6, fy - 21)  # gövde öne eğik, kafa önde
        # bacaklar: arkadaki iten bacak gergin, öndeki adım atar
        for k in (0, 1):
            s_ = math.sin(ph + k * math.pi) * (0 if done else 1)
            foot_x = x - 2 + s_ * 4 - (2 if k else 0)
            foot_y = _slope_y(foot_x) - 1
            knee = ((hip[0] + foot_x) / 2 + 2, (hip[1] + foot_y) / 2 - (1.5 if s_ > 0 else 0))
            col = PANTS if k == 0 else (48, 42, 38)
            self._line(p, hip[0], hip[1], knee[0], knee[1], col, 2)
            self._line(p, knee[0], knee[1], foot_x, foot_y, col, 2)
            for dx in range(3):  # bot
                self._px(p, foot_x + dx, foot_y, HAIR)
        # gövde (tişört) ve gölgesi
        self._line(p, hip[0], hip[1], sh[0], sh[1], SHIRT, 4)
        self._line(p, hip[0], hip[1] + 1, sh[0], sh[1] + 1, SHIRT_DARK, 1)
        self._line(p, hip[0] - 1, hip[1], hip[0] + 3, hip[1], PANTS, 1)  # kemer
        # kollar
        if done:
            wave = int(t * 4) % 2
            for sgn in (-1, 1):
                self._line(p, sh[0] + 1, sh[1], sh[0] + 1 + sgn * 4, sh[1] - 7 - wave * (sgn > 0), SKIN, 2)
        else:
            push = math.sin(ph * 2) * 0.7
            hx = rock_x - R + 1 + push
            for dy, col in ((0, SKIN), (3, (205, 160, 124))):  # iki kol, arkadaki daha koyu
                self._line(p, sh[0] + 1, sh[1] + dy, hx, _slope_y(rock_x) - R - 1 + dy, col, 2)
        # kafa, saç ve kırmızı-turuncu bandana
        for yy in range(5):
            for xx in range(5):
                if not (yy == 4 and xx in (0, 4)):
                    self._px(p, head[0] + xx, head[1] + yy, SKIN)
        for xx in range(5):
            self._px(p, head[0] + xx, head[1] - 1, HAIR)
            self._px(p, head[0] + xx, head[1], BAND)
        self._px(p, head[0] - 1, head[1], HAIR)
        self._px(p, head[0] - 1, head[1] + 1, HAIR)
        flap = int(t * 8) % 2
        self._px(p, head[0] - 2, head[1] + flap, BAND)  # bandananın uçuşan ucu
        self._px(p, head[0] - 3, head[1] + 1 - flap, BAND)
        self._px(p, head[0] + 3, head[1] + 2, HAIR)  # göz
        self._px(p, head[0] + 4, head[1] + 3, (190, 140, 110))  # burun gölgesi

    def paintEvent(self, _):
        t = self.elapsed()
        self._render(t)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(8, 7, 7))
        k = max(1, min(self.width() // PW, (self.height() - 70) // PH))
        sw, sh = PW * k, PH * k
        ox, oy = (self.width() - sw) // 2, max(0, (self.height() - sh - 64) // 2)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(QRectF(ox, oy, sw, sh), self.img)
        # alttaki yazılar
        y = oy + sh + 30
        f = QFont("JetBrains Mono", 12)
        f.setWeight(QFont.Bold)
        p.setFont(f)
        p.setPen(TEXT)
        p.drawText(QRectF(ox, y - 18, sw * 0.7, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   (self.stage or "Çalışıyor") + "…" * (not (self.stage or "").endswith("…")))
        p.setPen(ORANGE)
        p.drawText(QRectF(ox, y - 18, sw, 22), Qt.AlignRight | Qt.AlignVCenter, f"%{int(self.shown * 100)}")
        p.setFont(QFont("JetBrains Mono", 10))
        p.setPen(MUTED)
        p.drawText(QRectF(ox, y + 6, sw, 20), Qt.AlignLeft | Qt.AlignVCenter, TIPS[int(t / 4) % len(TIPS)])
        # piksel ilerleme çubuğu
        bw = sw
        p.fillRect(QRectF(ox, oy + sh + 4, bw, 4), QColor(40, 34, 30))
        seg = max(4, k * 2)
        n = int(bw * self.shown) // seg
        for i in range(n):
            p.fillRect(QRectF(ox + i * seg, oy + sh + 4, seg - 2, 4), ORANGE)
        p.end()
