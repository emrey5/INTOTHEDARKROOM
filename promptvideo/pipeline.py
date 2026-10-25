"""Üretim hattı: plan -> medya -> ses -> çizim -> montaj. Komut satırı ve masaüstü uygulaması
aynı fonksiyonları kullanır."""
import copy
import hashlib
import json
import os
import sys
import time

from . import webdata as W
from . import scenes, tts
from . import audio as A
from .scenes import _say_lines
from .render import render_scene, concat

MIN_DUR = {"title": 5, "bullets": 7, "stat": 5, "bar": 7, "line": 8, "pie": 7, "table": 7,
           "image": 5, "video": 5, "outro": 5, "character": 5, "versus": 7, "people": 7, "map": 8,
           "timeline": 9, "compare": 7}


# tempo: seslendirme hızı, sahne sonundaki nefes payı (sn), en kısa süre çarpanı
TEMPO = {"yavas": ("-8%", 1.8, 1.15), "normal": ("+0%", 1.2, 1.0), "hizli": ("+12%", 0.7, 0.85)}


class Callbacks:
    """Arayüzün (ya da komut satırının) ilerlemeyi izlemesi için kancalar."""

    def log(self, msg):
        print(msg, flush=True)

    def stage(self, i, n, label):
        self.log(f"{i}/{n} {label}")

    def progress(self, frac):
        pass

    def preview(self, image):
        pass

    def cancelled(self):
        return False


class Cancelled(Exception):
    pass


_cb = Callbacks()


def log(*a):
    _cb.log(" ".join(str(x) for x in a))


def _cache_name(url, ext):
    return hashlib.md5(url.encode()).hexdigest()[:12] + ext


def fetch_media(sc, assets):
    """Görsel/video sahneleri için dosyaları indirir; bulunamazsa sahneyi karta çevirir."""
    os.makedirs(assets, exist_ok=True)
    t = sc["type"]
    try:
        if t == "video" and not sc.get("video_path"):
            url, credit = None, None
            q = sc.get("stock_query") or sc.get("caption")
            if q:
                url, credit = W.pexels_video(q)  # PEXELS_API_KEY (ücretsiz) varsa
                if not url:
                    url, credit = W.commons_video(q)
            if url:
                ext = os.path.splitext(url.split("?")[0])[1] or ".mp4"
                sc["video_path"] = W.download(url, os.path.join(assets, _cache_name(url, ext)))
                sc.setdefault("credit", credit)
            else:  # video yoksa görsele düş
                sc["type"], sc["image_query"] = "image", sc.get("image_query") or sc.get("stock_query")
                t = "image"
        if t == "image" and not sc.get("image_path"):
            url, credit = sc.get("image_url"), sc.get("credit")
            if not url and sc.get("image_query"):
                url = W.commons_image(sc["image_query"])
                credit = "Görsel: Wikimedia Commons" if url else None
                if not url:
                    url, credit = W.pexels_photo(sc["image_query"])
            if url:
                ext = os.path.splitext(url.split("?")[0])[1].lower()
                ext = ext if ext in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"
                sc["image_path"] = W.download(url, os.path.join(assets, _cache_name(url, ext)))
                sc["credit"] = credit
    except Exception as e:
        log(f"  [medya] {e}")
    if sc["type"] == "image" and not sc.get("image_path"):
        sc["type"] = "title"
        sc["title"] = sc.get("caption") or sc.get("title", "")
        sc["subtitle"] = sc.get("kicker", "")
    if sc["type"] == "video" and not sc.get("video_path"):
        sc["type"] = "title"
        sc["title"] = sc.get("caption") or sc.get("title", "")


def srt_time(s):
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h):02}:{int(m):02}:{int(sec):02},{int((sec % 1) * 1000):03}"




def research_topic(prompt, out_dir, lang="tr", cb=None):
    """Webde araştırır; bulguları out_dir/research.json olarak kaydeder ve döner."""
    global _cb
    _cb = cb or Callbacks()
    from .research import gather
    os.makedirs(out_dir, exist_ok=True)
    _cb.stage(1, 5, "Araştırma")
    findings = gather(prompt, lang, log)
    save_findings(findings, out_dir)
    return findings


def save_findings(findings, out_dir):
    with open(os.path.join(out_dir, "research.json"), "w", encoding="utf-8") as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)


def load_findings(out_dir):
    p = os.path.join(out_dir, "research.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def write_plan(prompt, findings, out_dir, lang="tr", cb=None, length="orta"):
    """Seçili bulgulardan senaryoyu yazar, sayıları doğrular, out_dir/plan.json olarak kaydeder."""
    global _cb
    _cb = cb or Callbacks()
    from .planner import make_plan
    from .factcheck import check_plan
    os.makedirs(out_dir, exist_ok=True)
    _cb.stage(1, 5, "Senaryo yazılıyor")
    plan = make_plan(prompt, lang, log, length, findings)
    plan.setdefault("prompt", prompt)
    chk = check_plan(plan, findings)
    if chk:
        log(f"Doğruluk kontrolü: {chk['verified']} sayı kaynaklarda bulundu, {chk['missing']} sayı bulunamadı.")
        for i, sc in enumerate(plan["scenes"]):
            if sc.get("check", {}).get("missing"):
                log(f"  ⚠ Sahne {i + 1}: kaynakta yok → {', '.join(sc['check']['missing'])}")
    with open(os.path.join(out_dir, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    log(f"Plan kaydedildi: {os.path.join(out_dir, 'plan.json')} ({len(plan.get('scenes', []))} sahne)")
    return plan


def create_plan(prompt, out_dir, lang="tr", cb=None, length="orta"):
    """Araştırma + senaryo tek adımda (komut satırı için)."""
    findings = research_topic(prompt, out_dir, lang, cb)
    return write_plan(prompt, findings, out_dir, lang, cb, length)


def render_plan(plan, out_dir, style=None, voice=None, music=None, no_voice=False, lang="tr", cb=None,
                preview_every=10, subtitles=False, sfx=True, vertical=False, square=False, quality="1080",
                fps=30, tempo="normal", accent=None, bg=None, sub_opts=None, music_vol=0.35):
    """Planı videoya çevirir; video yolunu döner.
    music: ses dosyası yolu ya da "auto:enerjik" / "auto:sakin" / "auto:gizemli" (program üretir).
    quality: "720" / "1080" / "1440" / "2160"; tempo: "yavas" / "normal" / "hizli";
    accent / bg: "#RRGGBB" ile stil renklerini değiştirir; sub_opts: altyazı boyut/konum/kutu."""
    global _cb
    _cb = cb or Callbacks()
    from . import theme
    from . import draw as D
    t0 = time.time()
    theme.apply_style(style or plan.get("style") or theme.STYLE, accent=accent or "", bg=bg or "")
    theme.set_output(quality, fps)
    D._paper = None  # stil değişince kâğıt dokusunu yeniden üret
    D.SUB_OPTS = dict(D.SUB_OPTS, **(sub_opts or {}))
    rate, pad, min_k = TEMPO.get(tempo, TEMPO["normal"])
    ow, oh = theme.out_size()
    log(f"Çıktı: {ow}x{oh}, {theme.FPS} fps, stil {theme.STYLE_NAMES.get(theme.STYLE, theme.STYLE)}")
    lang = plan.get("language", lang)
    scenes.LANG = lang
    sc_list = copy.deepcopy(plan["scenes"])
    assets = os.path.join(out_dir, "assets")
    os.makedirs(assets, exist_ok=True)

    _cb.stage(2, 5, "Görseller ve videolar")
    for sc in sc_list:
        if _cb.cancelled():
            raise Cancelled()
        if sc["type"] in ("image", "video"):
            fetch_media(sc, assets)

    _cb.stage(3, 5, "Seslendirme")
    for i, sc in enumerate(sc_list):
        if _cb.cancelled():
            raise Cancelled()
        audio = None
        if sc["type"] == "character" and not sc.get("narration"):  # anlatım yoksa balondaki replikler okunur
            sc["narration"] = " ".join(x.get("text", "") for x in _say_lines(sc))
        lines = _say_lines(sc) if sc["type"] == "character" else []
        if not no_voice and lines:  # her karakter kendi sesiyle konuşur
            chars = sc.get("characters") or [{}]
            voices = tts.character_voices(chars, lang, voice)
            parts = []
            for k, ln in enumerate(lines):
                who = min(int(ln.get("who", 0)), len(voices) - 1)
                parts.append(tts.synthesize(ln["text"], os.path.join(assets, f"voice_{i:02}_{k}.mp3"), lang,
                                            voices[who], rate))
            if all(parts):
                try:
                    audio, sc["_line_times"] = tts.join(parts, os.path.join(assets, f"voice_{i:02}.wav"))
                except Exception as e:
                    log(f"  [ses] replikler birleştirilemedi: {e}")
        elif not no_voice and sc.get("narration"):
            audio = tts.synthesize(sc["narration"], os.path.join(assets, f"voice_{i:02}.mp3"), lang, voice, rate)
        sc["_audio"] = audio
        alen = tts.duration(audio) if audio else 0
        sc["_speech"], sc["_subs"] = alen, subtitles
        sc["duration"] = max(float(sc.get("duration") or 0), MIN_DUR.get(sc["type"], 6) * min_k, alen + pad)
        _cb.progress((i + 1) / len(sc_list))

    _cb.stage(4, 5, "Animasyonlar çiziliyor")
    total = sum(sc["duration"] for sc in sc_list)
    parts, off, srt, events, cuts = [], 0.0, [], [], []

    def on_frame(gt, surf):
        if _cb.cancelled():
            raise Cancelled()
        _cb.progress(gt / total)
        if int(gt * 30) % preview_every == 0:
            from PIL import Image
            im = Image.frombuffer("RGBA", (surf.get_width(), surf.get_height()), bytes(surf.get_data()),
                                  "raw", "BGRA", 0, 1).convert("RGB")
            _cb.preview(im)

    for i, sc in enumerate(sc_list):
        p = os.path.join(assets, f"scene_{i:02}.mp4")
        log(f"[{i + 1}/{len(sc_list)}] {sc['type']} · {sc['duration']:.1f} sn · {sc.get('title') or sc.get('caption') or ''}")
        render_scene(sc, p, off, total, i, len(sc_list), sc.get("_audio"), on_frame)
        if sc.get("narration"):
            srt.append(f"{len(srt) + 1}\n{srt_time(off + 0.3)} --> {srt_time(off + sc['duration'] - 0.5)}\n{sc['narration']}\n")
        parts.append(p)
        events += [(off + s, n, g) for s, n, g in A.scene_events(sc, sc["duration"])]
        off += sc["duration"]
        cuts.append(off)

    _cb.stage(5, 5, "Montaj")
    out = os.path.join(out_dir, "video.mp4")
    sfx_path = None
    if sfx:
        sfx_path = A.build_sfx(events, total, os.path.join(assets, "efektler.wav"), cuts[:-1])
    if music and music.startswith("auto:"):
        mood = music.split(":", 1)[1]
        log(f"Müzik üretiliyor ({A.MOODS.get(mood, mood)})…")
        music = A.build_music(mood, total, os.path.join(assets, "muzik.wav"))
    concat(parts, out, music, sfx_path, music_vol)
    with open(os.path.join(out_dir, "altyazi.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    from . import publish
    try:
        publish.thumbnail(plan, sc_list, os.path.join(out_dir, "kapak.png"))
        publish.youtube_text(plan, sc_list, os.path.join(out_dir, "youtube.txt"))
        log("Kapak resmi (kapak.png) ve YouTube metinleri (youtube.txt) hazır.")
    except Exception as e:
        log(f"  [yayın paketi] {e}")
    if vertical:
        log("Dikey (Shorts) sürüm hazırlanıyor…")
        publish.vertical(out, os.path.join(out_dir, "video_dikey.mp4"), plan.get("title", ""))
    if square:
        log("Kare (1:1) sürüm hazırlanıyor…")
        publish.square(out, os.path.join(out_dir, "video_kare.mp4"), plan.get("title", ""))
    for p in parts:
        try:
            os.remove(p)
        except OSError:
            pass
    log(f"Bitti: {out} ({total:.0f} sn video, {time.time() - t0:.0f} sn sürdü)")
    return out
