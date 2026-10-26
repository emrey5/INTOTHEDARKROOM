"""Yayın paketi: YouTube kapak resmi, başlık/açıklama/etiket/bölüm metni ve dikey (Shorts) sürüm."""
import os
import re
import subprocess

import cairo

from . import characters as C
from . import draw as D
from . import theme as th
from .render import FFMPEG, AUD, _NOWIN, enc
from .theme import fmt_num


def _ts(s):
    s = int(s)
    return f"{s // 60:02}:{s % 60:02}" if s < 3600 else f"{s // 3600}:{s % 3600 // 60:02}:{s % 60:02}"


def _scene_label(sc):
    t = sc.get("type")
    name = sc.get("title") or sc.get("caption") or sc.get("kicker") or ""
    if t == "title":
        return "Giriş"
    if t == "outro":
        return "Kapanış ve kaynaklar"
    return name.strip() or {"character": "Sohbet", "map": "Harita", "versus": "Karşılaştırma"}.get(t, "Bölüm")


def chapters(sc_list, min_len=10):
    """YouTube bölümleri: ilki 00:00, her biri en az 10 sn."""
    out, t = [], 0.0
    for sc in sc_list:
        lab = _scene_label(sc)
        if not out or (t - out[-1][0] >= min_len and lab != out[-1][1]):
            out.append([t, lab])
        t += sc["duration"]
    if len(out) > 1 and t - out[-1][0] < min_len:
        out.pop()
    return out if len(out) >= 3 else []


def _key_stat(sc_list):
    for sc in sc_list:
        if sc.get("type") == "stat" and isinstance(sc.get("value"), (int, float)):
            return sc.get("prefix", "") + fmt_num(sc["value"]) + sc.get("suffix", ""), sc.get("label", "")
    for sc in sc_list:
        if sc.get("type") == "versus":
            return "VS", f"{sc['left'].get('label', '')} · {sc['right'].get('label', '')}"
    return None, None


def youtube_text(plan, sc_list, path, shorts=False):
    if shorts:
        return shorts_text(plan, sc_list, path)
    title = plan.get("title", "")
    narr = [sc.get("narration", "") for sc in sc_list if sc.get("narration")]
    desc = " ".join(narr[:3])
    srcs = []
    for sc in sc_list:
        for s in ([sc.get("source")] if sc.get("source") else []) + list(sc.get("sources") or []):
            if s and s not in srcs:
                srcs.append(s)
    words = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]{4,}", " ".join([title] + [sc.get("kicker", "") for sc in sc_list]))
    tags = list(dict.fromkeys(w.lower() for w in words))[:15] + ["bilgi", "belgesel", "veri", "infografik"]
    lines = [f"BAŞLIK\n{title}\n", "AÇIKLAMA", desc, ""]
    ch = chapters(sc_list)
    if ch:
        lines += ["Bölümler:"] + [f"{_ts(t)} {lab}" for t, lab in ch] + [""]
    if srcs:
        lines += ["Kaynaklar:"] + [f"• {s}" for s in srcs] + [""]
    if plan.get("music_credit"):
        lines += ["Müzik: " + plan["music_credit"], ""]
    lines += ["DARKROOM ile hazırlandı.", "", "ETİKETLER", ", ".join(tags)]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _hashtag(w):
    return "#" + re.sub(r"[^\wçğıöşüÇĞİÖŞÜ]", "", w.title())


def shorts_text(plan, sc_list, path):
    """Shorts için başlık (≤100 karakter, #shorts), kısa açıklama, seri bilgisi, kaynaklar, etiketler ve
    YouTube'daki "değiştirilmiş ya da yapay içerik" sorusunun cevabı."""
    series = plan.get("series") or {}
    title = (plan.get("hook") or plan.get("title") or "").strip()
    if series.get("label"):
        title = f"{title} | {series['label']}"
    words = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]{4,}", " ".join([plan.get("title", "")] + [sc.get("kicker", "") for sc in sc_list]))
    tags = list(dict.fromkeys(w.lower() for w in words))[:12]
    hashtags = [_hashtag(w) for w in tags[:3]]
    full = f"{title} #shorts"
    if len(full) > 100:
        full = title[:100 - 8].rstrip() + "… #shorts"
    narr = [sc.get("narration", "") for sc in sc_list if sc.get("narration")]
    srcs = []
    for sc in sc_list:
        for s in ([sc.get("source")] if sc.get("source") else []) + list(sc.get("sources") or []) + \
                 ([sc.get("credit")] if sc.get("credit") else []):
            if s and s not in srcs:
                srcs.append(s)
    lines = [f"BAŞLIK (Shorts, {len(full)}/100 karakter)", full, "", "AÇIKLAMA", " ".join(narr[:2]), ""]
    if series.get("name"):
        lines += [f"📚 Seri: {series['name']} · {series.get('label', '')}", ""]
    if plan.get("review", {}).get("opinion"):
        lines += [f"Benim yorumum: {plan['review']['opinion']}", ""]
    if srcs:
        lines += ["Kaynaklar:"] + [f"• {s}" for s in srcs] + [""]
    if plan.get("music_credit"):
        lines += ["Müzik: " + plan["music_credit"], ""]
    lines += [" ".join(hashtags + ["#shorts", "#bilgi"]), "", "ETİKETLER", ", ".join(tags + ["shorts", "bilgi"]), "",
              "YÜKLERKEN", "• \"Değiştirilmiş ya da yapay içerik\" sorusu: HAYIR. Videoda gerçek gibi görünen yapay "
              "insan ya da olay yok; grafikler, stok görüntüler ve yapay zekâ seslendirmesi bu etiketi gerektirmez.",
              "• Yükleme sıklığı: aynı seriden günde en fazla 1-2 video; her bölümün konusu gerçekten farklı olsun."]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def thumbnail(plan, sc_list, path):
    """1280x720 YouTube kapak resmi: iri başlık, şaşkın karakter ve öne çıkan sayı."""
    w, h = 1280, 720
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(*th.BG)
    ctx.paint()
    g = cairo.RadialGradient(860, 360, 40, 860, 360, 700)
    g.add_color_stop_rgba(0, *th.ACCENT, 0.55)
    g.add_color_stop_rgba(1, *th.ACCENT, 0)
    ctx.set_source(g)
    ctx.paint()
    # çapraz turuncu şerit
    ctx.set_source_rgba(*th.ACCENT, 0.9)
    ctx.move_to(0, h - 120)
    ctx.line_to(w, h - 220)
    ctx.line_to(w, h - 190)
    ctx.line_to(0, h - 90)
    ctx.close_path()
    ctx.fill()
    look = next((c.get("look", 0) for sc in sc_list if sc.get("type") == "character"
                 for c in (sc.get("characters") or [{}])[:1]), 0)
    C.draw_character(ctx, 1010, h + 40, 1.0, 1.05, look=look, pose="shrug", emotion="surprised", facing=-1, seed=2)
    title = plan.get("title", "")
    size = 96
    lines = D.wrap(title, size, 760, "display")
    while len(lines) > 3 and size > 54:
        size -= 6
        lines = D.wrap(title, size, 760, "display")
    y = 120 + size
    for i, ln in enumerate(lines[:3]):
        col = th.ACCENT if i == len(lines[:3]) - 1 else th.TEXT
        D.draw_text(ctx, ln, 64 + 6, y + 6, size, (0, 0, 0), alpha=0.7, kind="display")
        D.draw_text(ctx, ln, 64, y, size, col, kind="display")
        y += size * 1.05
    num, label = _key_stat(sc_list)
    if num:
        ns = D.fit_size(num, 88, 560, "display")
        bw = D.text_width(num, ns, "display") + 60
        by = min(h - 170, y + 30)
        ctx.set_source_rgb(*th.ACCENT)
        D.round_rect(ctx, 64, by - ns - 10, bw, ns + 40, 14)
        ctx.fill()
        D.draw_text(ctx, num, 94, by + 8, ns, (0.05, 0.05, 0.05), kind="display")
    D.draw_text(ctx, "DARKROOM", w - 40, 50, 24, th.ACCENT, kind="bold", align="right")
    surf.write_to_png(path)
    return path


def vertical(video, path, title):
    """9:16 sürüm (Shorts/Reels/TikTok): bulanık arka plan, ortada video, üstte başlık."""
    ow, oh = 1080, 1920
    over = path + ".ust.png"
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ow, oh)
    ctx = cairo.Context(surf)
    size = 78
    lines = D.wrap(title, size, ow - 140, "display")
    while len(lines) > 3 and size > 48:
        size -= 6
        lines = D.wrap(title, size, ow - 140, "display")
    y0 = 520 - len(lines[:3]) * size * 1.1
    ctx.set_source_rgb(*th.ACCENT)
    D.round_rect(ctx, 70, y0 - size - 60, 160, 12, 6)
    ctx.fill()
    for i, ln in enumerate(lines[:3]):
        D.draw_text(ctx, ln, 70 + 4, y0 + i * size * 1.1 + 4, size, (0, 0, 0), alpha=0.7, kind="display")
        D.draw_text(ctx, ln, 70, y0 + i * size * 1.1, size, th.TEXT, kind="display")
    D.draw_text(ctx, "DARKROOM", ow / 2, oh - 160, 30, th.ACCENT, kind="bold", align="center")
    surf.write_to_png(over)
    vh = ow * 9 // 16
    fc = (f"[0:v]scale={ow}:{oh}:force_original_aspect_ratio=increase,crop={ow}:{oh},boxblur=30:3,"
          f"eq=brightness=-0.25[bg];[0:v]scale={ow}:{vh}[fg];[bg][fg]overlay=0:{(oh - vh) // 2}[v1];"
          f"[v1][1:v]overlay=0:0[v]")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", video, "-i", over, "-filter_complex", fc,
                    "-map", "[v]", "-map", "0:a", *enc(), *AUD, "-movflags", "+faststart", path], check=True, **_NOWIN)
    os.remove(over)
    return path


def square(video, path, title):
    """1:1 sürüm (Instagram gönderisi): bulanık arka plan, ortada video, üstte başlık."""
    ow = oh = 1080
    over = path + ".ust.png"
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ow, oh)
    ctx = cairo.Context(surf)
    size = 56
    lines = D.wrap(title, size, ow - 120, "display")
    while len(lines) > 2 and size > 38:
        size -= 4
        lines = D.wrap(title, size, ow - 120, "display")
    vh = ow * 9 // 16
    top = (oh - vh) // 2
    y = top - 40 - (len(lines[:2]) - 1) * size * 1.1
    for i, ln in enumerate(lines[:2]):
        D.draw_text(ctx, ln, 60 + 3, y + i * size * 1.1 + 3, size, (0, 0, 0), alpha=0.7, kind="display")
        D.draw_text(ctx, ln, 60, y + i * size * 1.1, size, th.TEXT, kind="display")
    ctx.set_source_rgb(*th.ACCENT)
    ctx.rectangle(60, top + vh + 34, 120, 8)
    ctx.fill()
    D.draw_text(ctx, "DARKROOM", ow - 60, top + vh + 70, 26, th.ACCENT, kind="bold", align="right")
    surf.write_to_png(over)
    fc = (f"[0:v]scale={ow}:{oh}:force_original_aspect_ratio=increase,crop={ow}:{oh},boxblur=30:3,"
          f"eq=brightness=-0.3[bg];[0:v]scale={ow}:{vh}[fg];[bg][fg]overlay=0:{top}[v1];"
          f"[v1][1:v]overlay=0:0[v]")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", video, "-i", over, "-filter_complex", fc,
                    "-map", "[v]", "-map", "0:a", *enc(), *AUD, "-movflags", "+faststart", path], check=True, **_NOWIN)
    os.remove(over)
    return path
