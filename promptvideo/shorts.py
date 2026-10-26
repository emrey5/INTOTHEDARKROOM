"""Gerçek dikey Shorts: video baştan 1080x1920 tasarım alanında çizilir (yatay videonun kırpılmışı değil).

- Görüntü, video, büyük sayı, kinetik yazı, kanca ve kapanış sahneleri dikeye göre ayrıca çizilir;
  grafik, harita, tablo gibi veri sahneleri ortada büyük bir kart olarak yer alır, üstünde iri başlık.
- Anlatım kelime kelime büyük altyazıyla görünür; o an söylenen kelime vurgu renginde (edge-tts kelime
  zamanlarıyla). Sahneler hızlı "yumruk" geçişlerle değişir; açılışta kararma yoktur (ilk kare dolu),
  sonda da yoktur (video döngüye girince kesinti hissedilmez).
"""
import os
import re
import subprocess

import cairo

from . import draw as D
from . import theme as th
from .render import FFMPEG, AUD, _NOWIN, enc, _audio_inputs
from .scenes import DRAWERS, load_image, _paint_cover
from .theme import clamp, lerp, prog, fmt_num, ease_out_cubic, ease_out_back, ease_out_expo, ease_in_out

SW, SH = 1080, 1920  # dikey tasarım alanı
FULL = {"video", "image", "kinetic", "title", "stat", "outro"}  # dikeye özel çizilen sahneler
CARD_Y, CARD_H = 640, 608  # veri kartının yeri (1920x1080 sahne 1080 genişliğe sığar)
CAP_Y = 1480  # altyazının taban çizgisi (Shorts arayüzünün üstünde kalır)
PUNCH = 0.18  # sahne başındaki yumruk geçişinin süresi
LEAD = 0.0  # sesin sahne içindeki başlangıcı (pipeline sesi sahne başında başlatır)


def out_size():
    k = th.SCALE
    return int(round(SW * k / 2)) * 2, int(round(SH * k / 2)) * 2


def setup_fonts():
    th.FONTS = dict(th.FONTS, caption=os.path.join(th.FONT_DIR, "Baloo2-ExtraBold.ttf"))


# --- Altyazı -----------------------------------------------------------------

def _upper(s, lang="tr"):
    if lang == "tr":
        s = s.replace("i", "İ").replace("ı", "I")
    return s.upper()


def word_times(text, words, speech):
    """Her kelimenin (başlangıç, bitiş) zamanı: edge-tts verdiyse onu, yoksa uzunluğa göre tahmini kullanır."""
    toks = text.split()
    if words and len(words) >= len(toks) * 0.6:
        out, j = [], 0
        for tok in toks:  # metindeki kelimeleri ses zamanlarıyla eşleştir (noktalama, "3" / "üç" farkı olabilir)
            bare = re.sub(r"\W", "", tok.lower())
            for jj in range(j, min(j + 3, len(words))):
                if re.sub(r"\W", "", words[jj][2].lower()) == bare:
                    j = jj
                    break
            s, e, _ = words[min(j, len(words) - 1)]
            out.append((s, e))
            j += 1
        return out
    total = sum(len(t) + 2 for t in toks) or 1
    acc, out = 0.0, []
    for t in toks:
        d = speech * (len(t) + 2) / total
        out.append((acc, acc + d))
        acc += d
    return out


def groups(text, times, max_chars=16, max_words=3):
    """Ekranda birlikte duracak 1-3 kelimelik gruplar: [(başlangıç, bitiş, [(kelime, s, e)])]."""
    toks, out, cur = text.split(), [], []
    for tok, (s, e) in zip(toks, times):
        if cur and (len(" ".join(w for w, _, _ in cur) + " " + tok) > max_chars or len(cur) >= max_words):
            out.append(cur)
            cur = []
        cur.append((tok, s, e))
        if tok[-1:] in ".!?:;,":
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [(g[0][1], out[k + 1][0][1] if k + 1 < len(out) else 1e9, g) for k, g in enumerate(out)]


def prepare(sc, words=None):
    """Sahnenin altyazı gruplarını hazırlar (seslendirmeden sonra çağrılır)."""
    text = (sc.get("narration") or "").strip()
    speech = sc.get("_speech") or max(1.5, len(text.split()) * 0.36)
    sc["_groups"] = groups(text, word_times(text, words or [], speech)) if text else []


def caption(ctx, sc, t, y=CAP_Y, size=88, lang="tr"):
    """Büyük, çerçeveli, kelime kelime altyazı; söylenen kelime vurgu renginde ve hafif büyük."""
    gs = sc.get("_groups")
    if not gs:
        return
    ts = t - LEAD
    cur = next((g for g in gs if g[0] <= ts < g[1]), None)
    if not cur:
        return
    start, _, words = cur
    toks = [_upper(D.clean(w), lang) for w, _, _ in words]
    space = D.text_width(" ", size, "caption")
    widths = [D.text_width(w, size, "caption") for w in toks]
    total = sum(widths) + space * (len(toks) - 1)
    if total > SW * 0.9:
        f = SW * 0.9 / total
        size, space, total = size * f, space * f, SW * 0.9
        widths = [x * f for x in widths]
    pop = 0.8 + 0.2 * ease_out_back(clamp((ts - start) / 0.14))
    hi = th.HILITE if th.LIGHT else (1.0, 0.882, 0.302)  # Shorts sarısı; açık temada stilin vurgusu
    ctx.save()
    ctx.translate(SW / 2, y)
    ctx.scale(pop, pop)
    x = -total / 2
    for w, (_, s, e), wd in zip(toks, words, widths):
        on = s <= ts < max(e, s + 0.12)
        D.draw_text(ctx, w, x, 0, size, hi if on else (1, 1, 1), kind="caption", outline=(0, 0, 0),
                    shadow=(0, size * 0.08))
        x += wd + space
    ctx.restore()


# --- Zemin ve ortak parçalar -------------------------------------------------

def background(ctx, gt):
    g = cairo.LinearGradient(0, 0, 0, SH)
    g.add_color_stop_rgb(0, *th.BG2)
    g.add_color_stop_rgb(1, *th.BG)
    ctx.set_source(g)
    ctx.paint()
    for i, (bx, by, r) in enumerate(((0.2, 0.25, 700), (0.85, 0.7, 800))):  # yavaşça gezinen iki ışık
        x = SW * bx + 120 * (1 if i else -1) * (0.5 - 0.5 * __import__("math").cos(gt * 0.25 + i))
        y = SH * by + 160 * __import__("math").sin(gt * 0.2 + i * 2)
        rg = cairo.RadialGradient(x, y, 10, x, y, r)
        rg.add_color_stop_rgba(0, *(th.ACCENT if i == 0 else th.ACCENT2), 0.22 if not th.LIGHT else 0.14)
        rg.add_color_stop_rgba(1, *(th.ACCENT if i == 0 else th.ACCENT2), 0)
        ctx.set_source(rg)
        ctx.paint()


def kicker(ctx, text, y, t, lang="tr"):
    """Üstte vurgu renginde küçük etiket kutusu."""
    if not text:
        return
    s = _upper(D.clean(text), lang)
    size = D.fit_size(s, 40, SW - 200, "bold")
    w = D.text_width(s, size, "bold") + 56
    p = max(0.02, ease_out_back(prog(t, 0.0, 0.3)))
    ctx.save()
    ctx.translate(SW / 2, y)
    ctx.scale(p, p)
    ctx.set_source_rgb(*th.ACCENT)
    D.round_rect(ctx, -w / 2, -size - 18, w, size + 36, 14)
    ctx.fill()
    D.draw_text(ctx, s, 0, 0, size, th.BG if not th.LIGHT else (1, 1, 1), kind="bold", align="center")
    ctx.restore()


def headline(ctx, text, y, t, size=84, max_lines=3, lang="tr"):
    """İri başlık (satır satır belirir); son satırın tabanını döner."""
    if not text:
        return y
    lines = D.wrap(text, size, SW - 140, "display")
    while len(lines) > max_lines and size > 48:
        size -= 6
        lines = D.wrap(text, size, SW - 140, "display")
    for i, ln in enumerate(lines[:max_lines]):
        p = ease_out_cubic(prog(t, 0.04 * i, 0.3))
        col = th.ACCENT if i == len(lines[:max_lines]) - 1 and len(lines) > 1 else th.TEXT
        D.draw_text(ctx, ln, SW / 2, y + i * size * 1.12 + (1 - p) * 30, size, col, alpha=p, kind="display",
                    align="center", shadow=(0, 5) if not th.LIGHT else None)
    return y + (len(lines[:max_lines]) - 1) * size * 1.12


def _shade(ctx, top=True, bottom=True):
    if top:
        g = cairo.LinearGradient(0, 0, 0, 560)
        g.add_color_stop_rgba(0, 0, 0, 0, 0.6)
        g.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(g)
        ctx.rectangle(0, 0, SW, 560)
        ctx.fill()
    if bottom:
        g = cairo.LinearGradient(0, SH * 0.55, 0, SH)
        g.add_color_stop_rgba(0, 0, 0, 0, 0)
        g.add_color_stop_rgba(1, 0, 0, 0, 0.7)
        ctx.set_source(g)
        ctx.rectangle(0, SH * 0.55, SW, SH * 0.45)
        ctx.fill()


# --- Dikey sahneler ----------------------------------------------------------

def draw_media(ctx, sc, t, dur, surf, lang):
    if surf:
        p = t / max(dur, 0.01)
        zoom = lerp(1.0, 1.12, ease_in_out(p))
        pan = lerp(-40, 40, p) * (1 if sc.get("pan", 1) > 0 else -1)
        _paint_cover(ctx, surf, 0, 0, SW, SH, zoom, pan)
    _shade(ctx)
    kicker(ctx, sc.get("kicker") or sc.get("caption"), 300, t, lang)
    if sc.get("credit"):
        D.draw_text(ctx, sc["credit"], SW - 40, SH - 260, 22, (1, 1, 1), alpha=0.6, align="right")


def draw_text_scene(ctx, sc, t, dur, lang):
    """Kanca (title) ve kinetik yazı: altyazı ekranın ortasında, çok büyük."""
    if sc["type"] == "title" and sc.get("title") and _norm(sc.get("title")) != _norm(sc.get("narration")):
        kicker(ctx, sc["title"], 420, t, lang)
    else:
        kicker(ctx, sc.get("kicker"), 420, t, lang)


def _norm(s):
    return re.sub(r"\W", "", str(s or "").lower())


def draw_stat(ctx, sc, t, dur, lang):
    try:
        val = float(sc.get("value") or 0)
    except (TypeError, ValueError):
        val = 0.0
    kicker(ctx, sc.get("kicker"), 420, t, lang)
    p = ease_out_expo(prog(t, 0.1, min(1.4, dur * 0.45)))
    dec = sc.get("decimals")
    s = sc.get("prefix", "") + fmt_num(val * p, lang, dec if dec is not None else
                                        (0 if float(val).is_integer() and abs(val) < 1e6 else None)) + sc.get("suffix", "")
    size = D.fit_size(s, 230, SW - 120, "display")
    pop = max(0.02, ease_out_back(prog(t, 0.0, 0.35)))
    ctx.save()
    ctx.translate(SW / 2, 900)
    ctx.scale(pop, pop)
    D.draw_text(ctx, s, 0, 0, size, None, kind="display", align="center",
                source=D.accent_gradient(-SW / 2, 0, SW / 2, 0))
    ctx.restore()
    lab = sc.get("label", "")
    if lab:
        y = 1010
        for i, ln in enumerate(D.wrap(lab, 52, SW - 160, "bold")[:3]):
            D.draw_text(ctx, ln, SW / 2, y + i * 62, 52, th.TEXT, alpha=ease_out_cubic(prog(t, 0.3, 0.4)),
                        kind="bold", align="center")
    if sc.get("source"):
        D.draw_text(ctx, "Kaynak: " + sc["source"], SW / 2, 1240, 26, th.MUTED, align="center")


def draw_outro(ctx, sc, t, dur, lang, series=None):
    y = headline(ctx, sc.get("title") or "", 720, t, 80, 3, lang)
    tag = "DEVAMI GELİYOR · TAKİP ET" if lang == "tr" else "MORE COMING · FOLLOW"
    if series:
        tag = f"{series} · " + tag
    kicker(ctx, tag, y + 170, t - 0.3, lang)


def draw_card(ctx, sc, t, dur, gt, lang, k):
    """Veri sahnesi (grafik, harita, tablo...): yatay tasarımda çizilir, ortada kart olarak durur."""
    kicker(ctx, sc.get("kicker"), 330, t, lang)
    if sc.get("title") and sc["type"] not in ("character",):
        headline(ctx, sc["title"], 470, t, 66, 2, lang)
    iw, ih = int(round(SW * k)), int(round(CARD_H * k))
    inner = cairo.ImageSurface(cairo.FORMAT_ARGB32, iw, ih)
    ictx = cairo.Context(inner)
    ictx.scale(iw / th.W, ih / th.H)
    old_k, old_subs = D._K, D.SUBS
    D._K, D.SUBS = iw / th.W, False
    try:
        D.background(ictx, gt)
        with th.scene_accent(sc.get("accent")):
            DRAWERS.get(sc["type"], DRAWERS["bullets"])(ictx, sc, t, dur)
    finally:
        D._K, D.SUBS = old_k, old_subs
    inner.flush()
    p = ease_out_cubic(prog(t, 0.0, 0.35))
    ctx.save()
    ctx.translate(0, CARD_Y + (1 - p) * 80)
    ctx.set_source_rgba(0, 0, 0, 0.35 * p)  # gölge
    D.round_rect(ctx, 24, 18, SW - 48, CARD_H, 28)
    ctx.fill()
    D.round_rect(ctx, 24, 0, SW - 48, CARD_H, 28)
    ctx.clip()
    ctx.scale(1 / k, 1 / k)
    ctx.set_source_surface(inner, 0, 0)
    ctx.paint_with_alpha(p)
    ctx.restore()


# --- Kare ve sahne çizimi ----------------------------------------------------

def render_frame(ctx, sc, t, dur, gt, total, sidx, n, video_surf, k, lang="tr", series=None):
    background(ctx, gt)
    typ = sc["type"]
    z = 1.0
    if sidx > 0 and t < PUNCH:  # yumruk geçiş: yeni sahne hafif büyükten yerine oturur
        z = lerp(1.07, 1.0, ease_out_cubic(t / PUNCH))
    ctx.save()
    if z != 1.0:
        ctx.translate(SW / 2, SH / 2)
        ctx.scale(z, z)
        ctx.translate(-SW / 2, -SH / 2)
    with th.scene_accent(sc.get("accent")):
        if typ in ("video", "image"):
            surf = video_surf if typ == "video" else (load_image(sc["image_path"])[0] if sc.get("image_path") else None)
            draw_media(ctx, sc, t, dur, surf, lang)
        elif typ in ("title", "kinetic"):
            draw_text_scene(ctx, sc, t, dur, lang)
        elif typ == "stat":
            draw_stat(ctx, sc, t, dur, lang)
        elif typ == "outro":
            draw_outro(ctx, sc, t, dur, lang, series)
        else:
            draw_card(ctx, sc, t, dur, gt, lang, k)
    ctx.restore()
    if typ in ("title", "kinetic"):
        caption(ctx, sc, t, 1000, 124, lang)
    elif typ != "character":  # karakterde konuşma balonu yeter
        caption(ctx, sc, t, CAP_Y, 88, lang)
    if sidx > 0 and t < PUNCH:  # kısa beyaz parlama
        ctx.set_source_rgba(1, 1, 1, 0.28 * (1 - t / PUNCH))
        ctx.paint()
    ctx.set_source_rgba(1, 1, 1, 0.15)  # üstte ince ilerleme çizgisi
    ctx.rectangle(0, 0, SW, 8)
    ctx.fill()
    ctx.set_source(D.accent_gradient(0, 0, SW, 0))
    ctx.rectangle(0, 0, SW * clamp(gt / max(total, 0.01)), 8)
    ctx.fill()
    if th.PIXEL:
        from .render import pixelate
        pixelate(ctx.get_target())


class PortraitReader:
    """Klipten dikey (kırpılmış) BGRA kareler okur."""

    def __init__(self, path, dur, w, h):
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={th.FPS},format=bgra"
        self.proc = subprocess.Popen(
            [FFMPEG, "-loglevel", "error", "-stream_loop", "-1", "-i", path, "-t", f"{dur + 1:.2f}",
             "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgra", "-"], stdout=subprocess.PIPE, **_NOWIN)
        self.w, self.h = w, h
        self.surf = None

    def next(self):
        data = self.proc.stdout.read(self.w * self.h * 4)
        if len(data) == self.w * self.h * 4:
            self.buf = bytearray(data)
            self.surf = cairo.ImageSurface.create_for_data(self.buf, cairo.FORMAT_ARGB32, self.w, self.h, self.w * 4)
        return self.surf

    def close(self):
        try:
            self.proc.stdout.close()
            self.proc.kill()
        except Exception:
            pass


def render_scene(sc, out_path, t_offset, total, sidx, n, audio=None, on_frame=None, lang="tr", series=None):
    dur = sc["duration"]
    ow, oh = out_size()
    k = ow / SW
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{ow}x{oh}", "-r", str(th.FPS), "-i", "-", *_audio_inputs(audio),
           "-map", "0:v", "-map", "1:a", "-af", "apad", "-t", f"{dur:.3f}", *enc(), *AUD, out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, **_NOWIN)
    reader = PortraitReader(sc["video_path"], dur, ow, oh) if sc["type"] == "video" and sc.get("video_path") else None
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ow, oh)
    ctx = cairo.Context(surf)
    ctx.scale(k, k)
    D._K = k
    try:
        for f in range(int(round(dur * th.FPS))):
            t = f / th.FPS
            vs = reader.next() if reader else None
            ctx.save()
            render_frame(ctx, sc, t, dur, t_offset + t, total, sidx, n, vs, k, lang, series)
            ctx.restore()
            D._K = k  # kart çizimi değiştirmiş olabilir
            surf.flush()
            proc.stdin.write(surf.get_data())
            if on_frame:
                on_frame(t_offset + t, surf)
    except BaseException:
        if reader:
            reader.close()
        proc.kill()
        raise
    if reader:
        reader.close()
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg Shorts sahnesi {sidx} için başarısız oldu")


def still(sc, t=None, size=(270, 480), lang="tr"):
    """Önizleme için tek bir dikey kare (PIL resmi)."""
    from PIL import Image
    k = size[0] / SW
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size[0], size[1])
    ctx = cairo.Context(surf)
    ctx.scale(k, k)
    D._K = k
    setup_fonts()
    sc = dict(sc)
    sc.setdefault("duration", 6)
    if "_groups" not in sc:
        prepare(sc)
    t = sc["duration"] * 0.5 if t is None else t
    render_frame(ctx, sc, t, sc["duration"], t, sc["duration"], 0, 1, None, k, lang)
    surf.flush()
    return Image.frombuffer("RGBA", size, bytes(surf.get_data()), "raw", "BGRA", 0, 1).convert("RGB")
