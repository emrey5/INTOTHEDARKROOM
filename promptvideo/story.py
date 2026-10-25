"""Hikâye animasyonu: yapay zekâ kısa ve sürükleyici bir hikâye yazar, her sahnenin resmini kullanıcının
ekran kartı çizer (imagegen), program resimlere kamera hareketi, seslendirme, kelime kelime büyük altyazı,
müzik ve efekt ekler. Dikey (Shorts) seçilirse video baştan 1080x1920 çizilir, resimler de dikey üretilir.
"""
import hashlib
import os
import re
import subprocess
import time

import cairo

from . import audio as A
from . import draw as D
from . import imagegen, tts
from . import theme as th
from .render import FFMPEG, AUD, _NOWIN, enc, concat
from .theme import clamp, ease_out_cubic, ease_out_back, ease_in_out

LENGTHS = {"kisa": ("6-8", 7), "orta": ("10-14", 12), "uzun": ("16-22", 18)}
CAMERAS = ("zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down")
XF = 0.35  # sahneler arası çapraz geçiş (sn)
LEAD = 0.15  # sahne başladıktan sonra konuşmanın başladığı an
CAPTION = "#FFE14D"  # o an söylenen kelimenin rengi (Shorts sarısı)

SYSTEM = """Sen YouTube ve Shorts'ta milyonlarca izlenen kısa animasyon hikâyeleri yazan bir senaristsin.
Kullanıcının isteğinden {n} sahnelik bir hikâye yaz.

Viral kurgu:
- 1. sahne KANCA: ilk cümle izleyiciyi hemen yakalasın (şaşırtıcı bir an, bir soru ya da bir tehlike).
  Selamlama, giriş, "bu videoda" gibi cümleler YOK.
- Hemen bir sorun ya da merak başlasın; her sahnede gerilim artsın, izleyici "sonra ne oldu" desin.
- Sonlara doğru beklenmedik bir dönüş olsun, ardından duygusal bir sonuç gelsin.
- Son sahne izleyiciye bir soru sorsun ya da onu düşündürsün (yorum yazdırmak için).
- Her sahnenin "narration"ı 1-2 kısa, akıcı, konuşma dilinde cümledir (en fazla 25 kelime).
  Anlatım kullanıcının dilindedir (varsayılan Türkçe).

Görseller (çok önemli, İngilizce yazılır):
- "character": ana karakterin görünüşü, İngilizce tek cümle: yaş, tür, saç, kıyafet ve renkler
  (ör. "a small orange tabby kitten with big green eyes and a red scarf"). Her resimde aynı karakterin
  çıkması bu tarife bağlıdır; ayrıntılı ve ayırt edici yaz.
- "art_style": cartoon (3D çizgi film), anime, comic, realistic, storybook birinden biri.
  Kullanıcı bir tarz söylemediyse cartoon.
- Her sahnenin "image_prompt"u İngilizce, tek bir donmuş an: karakter ne yapıyor, yüz ifadesi, mekân,
  ışık ve kamera açısı (close-up, wide shot, low angle...). Ana karakterden "the main character" diye söz et,
  ismini yazma. Resimde yazı, harf ya da tabela OLMASIN.
- Sahnede ana karakter yoksa "show_character": false.
- "camera": zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down; gerilimli anlarda zoom_in.

Yalnızca şu JSON'u döndür:
{{"title": "merak uyandıran kısa başlık", "language": "tr", "character": "...", "art_style": "cartoon",
 "scenes": [{{"image_prompt": "...", "narration": "...", "camera": "zoom_in", "show_character": true}}]}}
"""

ART_WORDS = {"anime": ("anime", "manga", "ghibli"), "comic": ("çizgi roman", "comic", "karikatür"),
             "realistic": ("gerçekçi", "realistic", "sinematik", "fotoğraf gibi"),
             "storybook": ("masal", "çocuk kitabı", "suluboya", "storybook", "çocuklar için")}


def art_style_of(prompt):
    t = (prompt or "").lower()
    for k, words in ART_WORDS.items():
        if any(w in t for w in words):
            return k
    return "cartoon"


# --- Senaryo -----------------------------------------------------------------

def _clean_plan(plan, prompt, lang):
    scenes = []
    for i, sc in enumerate(plan.get("scenes") or []):
        if not isinstance(sc, dict) or not (sc.get("narration") or "").strip():
            continue
        cam = sc.get("camera") if sc.get("camera") in CAMERAS else CAMERAS[i % len(CAMERAS)]
        scenes.append({"type": "story", "narration": sc["narration"].strip(),
                       "image_prompt": (sc.get("image_prompt") or prompt).strip(), "camera": cam,
                       "show_character": sc.get("show_character", True) is not False})
    plan["scenes"] = scenes
    plan["kind"] = "hikaye"
    plan.setdefault("language", lang)
    plan["title"] = (plan.get("title") or prompt).strip()
    plan["character"] = (plan.get("character") or "").strip()
    if plan.get("art_style") not in imagegen.STYLES:
        plan["art_style"] = art_style_of(prompt)
    plan.setdefault("seed", int(hashlib.md5(plan["title"].encode()).hexdigest()[:6], 16))
    return plan


def plan_story(prompt, lang="tr", log=print, length="orta"):
    """Hikâyeyi yazar: Ollama varsa viral kurguyla, yoksa basit bir kalıpla."""
    from . import planner as P
    ok, names = P.ollama_available()
    if not names:
        from . import ollama_setup
        if ollama_setup.find_exe() and ollama_setup.start_server():
            ok, names = P.ollama_available()
    if ok:
        log(f"Yerel yapay zekâ ({P.MODEL}) hikâyeyi yazıyor…")
        try:
            import requests
            r = requests.post(f"{P.OLLAMA}/api/chat", timeout=1800, json={
                "model": P.MODEL, "stream": False, "format": "json", "think": False,
                "options": {"temperature": 0.85, "num_ctx": 8192},
                "messages": [{"role": "system", "content": SYSTEM.format(n=LENGTHS.get(length, LENGTHS["orta"])[0])},
                             {"role": "user", "content": f"İSTEK: {prompt}\nDİL: {lang}"}]})
            r.raise_for_status()
            plan = _clean_plan(P.extract_json(r.json()["message"]["content"]), prompt, lang)
            if len(plan["scenes"]) >= 3:
                return plan
            log("  Yapay zekânın hikâyesi çok kısa geldi; kalıp hikâye kullanılıyor.")
        except Exception as e:
            log(f"  Hikâye yazılamadı ({e}); kalıp hikâye kullanılıyor.")
    else:
        log("Ollama bulunamadı: basit bir kalıp hikâye kullanılıyor. Gerçek bir hikâye için soldaki "
            "“Ollama'yı kur ve hazırla” düğmesine basın.")
    return fallback_story(prompt, lang, length)


_TEMPLATE_TR = [
    ("{T}. Bu hikâyenin sonunu kimse tahmin edemedi.", "the main character looking surprised, dramatic light", "zoom_in"),
    ("Her şey sıradan bir günde başladı.", "the main character on an ordinary sunny morning, wide shot", "pan_right"),
    ("Ama bir anda her şey değişti.", "the main character shocked, storm clouds gathering, close-up", "zoom_in"),
    ("Önünde iki yol vardı: vazgeçmek ya da devam etmek.", "the main character standing at a crossroads at dusk", "pan_left"),
    ("Korkuyordu, ama pes etmedi.", "the main character walking forward bravely through the wind, low angle", "pan_up"),
    ("Ve sonunda kimsenin beklemediği bir şey oldu.", "the main character amazed, magical glowing light, wide shot", "zoom_out"),
    ("Sence sen olsan ne yapardın? Yorumlara yaz.", "the main character smiling at sunset, peaceful", "zoom_out"),
]
_TEMPLATE_EN = [
    ("{T}. Nobody saw the ending of this story coming.", "the main character looking surprised, dramatic light", "zoom_in"),
    ("It all started on an ordinary day.", "the main character on an ordinary sunny morning, wide shot", "pan_right"),
    ("But suddenly, everything changed.", "the main character shocked, storm clouds gathering, close-up", "zoom_in"),
    ("There were two paths: give up, or keep going.", "the main character standing at a crossroads at dusk", "pan_left"),
    ("Scared, but not giving up.", "the main character walking forward bravely through the wind, low angle", "pan_up"),
    ("And then, something nobody expected happened.", "the main character amazed, magical glowing light, wide shot", "zoom_out"),
    ("What would you have done? Tell me in the comments.", "the main character smiling at sunset, peaceful", "zoom_out"),
]


def fallback_story(prompt, lang="tr", length="orta"):
    topic = re.sub(r"\s+", " ", prompt or "").strip().rstrip(".!?") or "Bir zamanlar"
    tpl = _TEMPLATE_EN if lang == "en" else _TEMPLATE_TR
    scenes = [{"narration": n.format(T=topic[:1].upper() + topic[1:]), "image_prompt": ip, "camera": c}
              for n, ip, c in tpl]
    return _clean_plan({"title": topic[:1].upper() + topic[1:], "character": f"the hero of the story: {topic}",
                        "scenes": scenes}, prompt, lang)


# --- Resimler ----------------------------------------------------------------

def scene_prompt(plan, sc):
    ch = plan.get("character", "")
    p = sc.get("image_prompt", "")
    if ch and re.search(r"\bthe main character\b", p, re.I):
        p = re.sub(r"\bthe main character\b", ch, p, count=1, flags=re.I)
        ch = ""
    return imagegen.full_prompt(p, ch if sc.get("show_character", True) else "", plan.get("art_style", "cartoon"))


def placeholder(path, w, h, i, text=""):
    """Görsel motoru yoksa: sahneye göre renk değiştiren sade bir zemin (video yine de üretilir)."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    hue = (i * 0.13 + 0.55) % 1.0
    import colorsys
    c1 = colorsys.hsv_to_rgb(hue, 0.55, 0.35)
    c2 = colorsys.hsv_to_rgb((hue + 0.08) % 1, 0.7, 0.12)
    g = cairo.RadialGradient(w * 0.5, h * 0.4, 10, w * 0.5, h * 0.5, max(w, h) * 0.8)
    g.add_color_stop_rgb(0, *c1)
    g.add_color_stop_rgb(1, *c2)
    ctx.set_source(g)
    ctx.paint()
    surf.write_to_png(path)
    return path


def as_story(sc, i, plan):
    """Düzenleyicide eklenmiş başka türden bir sahneyi de hikâye sahnesine çevirir."""
    from .kinds import _text_of
    sc = dict(sc)
    sc["narration"] = (sc.get("narration") or _text_of(sc) or "").strip()
    sc.setdefault("image_prompt", sc.get("image_query") or sc.get("stock_query") or sc.get("title") or plan.get("title", ""))
    if sc.get("camera") not in CAMERAS:
        sc["camera"] = CAMERAS[i % len(CAMERAS)]
    sc["type"] = "story"
    return sc


def make_images(plan, assets, vertical, log, progress, cancelled, preview=None):
    """Her sahnenin resmini çizer (önbellekli). Görsel motoru yoksa sade zeminlere düşer."""
    w, h = (768, 1344) if vertical else (1344, 768)
    seed = int(plan.get("seed") or 1)
    engine = imagegen.server_up() or (imagegen.installed() and imagegen.start_server())
    if not engine:
        log("⚠ Görsel motoru kurulu değil ya da açılamadı: resimler yerine sade zeminler kullanılıyor. "
            "Gerçek çizim için “Görsel motorunu kur” düğmesine basın (bir kez, ~9 GB).")
    paths = []
    for i, sc in enumerate(plan["scenes"]):
        if cancelled():
            raise RuntimeError("İptal edildi.")
        prompt = scene_prompt(plan, sc)
        key = hashlib.md5(f"{prompt}|{seed}|{w}x{h}".encode()).hexdigest()[:12]
        path = os.path.join(assets, f"story_{i:02}_{key}.png")
        if not os.path.isfile(path):
            if engine:
                t0 = time.time()
                try:
                    imagegen.generate(prompt, path, w, h, seed, cancelled=cancelled)
                    log(f"  Resim {i + 1}/{len(plan['scenes'])} çizildi ({time.time() - t0:.0f} sn)")
                except Exception as e:
                    if "İptal" in str(e):
                        raise
                    log(f"  [görsel] sahne {i + 1}: {e}")
                    placeholder(path + ".ph.png", w, h, i)
                    path += ".ph.png"
            else:
                placeholder(path + ".ph.png", w, h, i)
                path += ".ph.png"
        paths.append(path)
        progress((i + 1) / len(plan["scenes"]))
        if preview:
            try:
                from PIL import Image
                preview(Image.open(path).convert("RGB"))
            except Exception:
                pass
    return paths


# --- Altyazı -----------------------------------------------------------------

def _upper(s, lang):
    if lang == "tr":
        s = s.replace("i", "İ").replace("ı", "I")
    return s.upper()


def word_times(text, words, speech):
    """Her kelimenin (başlangıç, bitiş) zamanı. edge-tts verdiyse onu, yoksa uzunluğa göre tahmini kullanır."""
    toks = text.split()
    if words and len(words) >= len(toks) * 0.6:
        out, j = [], 0
        for k, tok in enumerate(toks):  # metindeki her kelimeyi ses zamanlarıyla eşleştir (noktalama farkı olabilir)
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
    """Kelimeleri ekranda birlikte duracak 1-3 kelimelik gruplara ayırır: [(başlangıç, bitiş, [(kelime, s, e)])]."""
    toks, out, cur = text.split(), [], []
    for tok, (s, e) in zip(toks, times):
        if cur and (len(" ".join(w for w, _, _ in cur + [(tok, 0, 0)])) > max_chars or len(cur) >= max_words):
            out.append(cur)
            cur = []
        cur.append((tok, s, e))
        if tok[-1:] in ".!?:;,":
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    res = []
    for k, g in enumerate(out):
        end = out[k + 1][0][1] if k + 1 < len(out) else 1e9  # son grup sahne bitene kadar kalır
        res.append((g[0][1], end, g))
    return res


def draw_caption(ctx, sc, t, dw, dh, lang, hi):
    """Büyük, çerçeveli, kelime kelime altyazı; o an söylenen kelime vurgu renginde ve hafifçe büyük."""
    gs = sc.get("_groups")
    if not gs:
        return
    ts = t - LEAD
    cur = next((g for g in gs if g[0] <= ts < g[1]), None)
    if not cur:
        return
    start, _, words = cur
    portrait = dh > dw
    size = 124 if portrait else 96
    y = dh * (0.70 if portrait else 0.83)
    toks = [_upper(w, lang) for w, _, _ in words]
    space = D.text_width(" ", size, "caption")
    widths = [D.text_width(w, size, "caption") for w in toks]
    total = sum(widths) + space * (len(toks) - 1)
    maxw = dw * 0.9
    if total > maxw:
        f = maxw / total
        size *= f
        widths = [x * f for x in widths]
        space *= f
        total = maxw
    p = clamp((ts - start) / 0.16)
    pop = 0.82 + 0.18 * ease_out_back(p)
    ctx.save()
    ctx.translate(dw / 2, y)
    ctx.scale(pop, pop)
    x = -total / 2
    for w, (tok, s, e), wd in zip(toks, words, widths):
        on = s <= ts < max(e, s + 0.12)
        col = hi if on else (1, 1, 1)
        D.draw_text(ctx, w, x, 0, size, col, kind="caption", outline=(0, 0, 0), shadow=(0, size * 0.08))
        x += wd + space
    ctx.restore()


# --- Kamera ------------------------------------------------------------------

def _load(path):
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    r, g, b, a = im.split()
    data = bytearray(Image.merge("RGBA", (b, g, r, a)).tobytes())
    return cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, im.width, im.height, im.width * 4), data


def draw_image(ctx, img, cam, p, ow, oh):
    """Resmi kareyi dolduracak şekilde yerleştirip kamera hareketini (Ken Burns) uygular. p: 0..1."""
    iw, ih = img.get_width(), img.get_height()
    cover = max(ow / iw, oh / ih)
    q = ease_in_out(clamp(p))
    z, dx, dy = 1.12, 0.0, 0.0
    if cam == "zoom_in":
        z = 1.0 + 0.16 * q
    elif cam == "zoom_out":
        z = 1.16 - 0.16 * q
    sw, sh = iw * cover * z, ih * cover * z
    slack_x, slack_y = (sw - ow) / 2, (sh - oh) / 2
    if cam == "pan_left":
        dx = slack_x * (1 - 2 * q)
    elif cam == "pan_right":
        dx = -slack_x * (1 - 2 * q)
    elif cam == "pan_up":
        dy = slack_y * (1 - 2 * q)
    elif cam == "pan_down":
        dy = -slack_y * (1 - 2 * q)
    ctx.save()
    ctx.translate(ow / 2 + dx, oh / 2 + dy)
    ctx.scale(cover * z, cover * z)
    ctx.translate(-iw / 2, -ih / 2)
    ctx.set_source_surface(img, 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint()
    ctx.restore()


def _shade(ctx, ow, oh):
    """Altyazının okunması için alttan hafif karartma."""
    g = cairo.LinearGradient(0, oh * 0.5, 0, oh)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.55)
    ctx.set_source(g)
    ctx.rectangle(0, oh * 0.5, ow, oh * 0.5)
    ctx.fill()


# --- Video -------------------------------------------------------------------

def _voice_track(sc_list, total, path):
    """Sahnelerin seslerini zamanlarına yerleştirip tek bir ses dosyası yapar."""
    ins, fc, labels = [], [], []
    for sc in sc_list:
        if sc.get("_audio"):
            k = len(ins) // 2
            ins += ["-i", sc["_audio"]]
            ms = int((sc["_start"] + LEAD) * 1000)
            fc.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{k}]")
            labels.append(f"[a{k}]")
    if not labels:
        return None
    fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,apad,atrim=0:{total:.3f}[a]")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[a]", path],
                   check=True, **_NOWIN)
    return path


def render(plan, out_dir, cb, voice=None, music=None, no_voice=False, lang="tr", vertical=False,
           quality="1080", fps=30, tempo="normal", accent=None, music_vol=0.35, sfx=True, preview_every=10):
    """Hikâye planını videoya çevirir; video yolunu döner (pipeline.render_plan buradan geçer)."""
    from .pipeline import TEMPO, Cancelled, srt_time
    from . import publish
    t0 = time.time()
    log = cb.log
    lang = plan.get("language", lang)
    th.apply_style("modern")
    th.set_output(quality, fps)
    th.FONTS = dict(th.FONTS, caption=os.path.join(th.FONT_DIR, "Baloo2-ExtraBold.ttf"))
    hi = _rgb(accent or CAPTION)
    rate, pad, _ = TEMPO.get(tempo, TEMPO["normal"])
    pad = min(pad, 0.8)  # hikâyede sahneler hızlı akar
    dw, dh = (1080, 1920) if vertical else (1920, 1080)
    k = th.SCALE
    ow, oh = int(round(dw * k / 2)) * 2, int(round(dh * k / 2)) * 2
    log(f"Hikâye: {len(plan['scenes'])} sahne · çıktı {ow}x{oh}{' (dikey)' if vertical else ''}, {th.FPS} fps")
    assets = os.path.join(out_dir, "assets")
    os.makedirs(assets, exist_ok=True)
    plan = dict(plan, scenes=[as_story(sc, i, plan) for i, sc in enumerate(plan["scenes"])])
    sc_list = [dict(sc) for sc in plan["scenes"]]

    cb.stage(2, 5, "Resimler çiziliyor")
    try:
        paths = make_images(plan, assets, vertical, log, cb.progress, cb.cancelled, cb.preview)
    finally:
        imagegen.release()  # ekran kartı belleği boşalsın: oyun ya da başka program rahat çalışsın

    cb.stage(3, 5, "Seslendirme")
    for i, sc in enumerate(sc_list):
        if cb.cancelled():
            raise Cancelled()
        audio, words = (None, [])
        if not no_voice:
            audio, words = tts.synthesize_words(sc["narration"], os.path.join(assets, f"story_voice_{i:02}.mp3"),
                                                lang, voice, rate)
        speech = tts.duration(audio) if audio else max(2.0, len(sc["narration"].split()) * 0.38)
        sc["_audio"], sc["_speech"] = audio, speech
        sc["_groups"] = groups(sc["narration"], word_times(sc["narration"], words, speech))
        sc["duration"] = max(2.5, LEAD + speech + pad)
        cb.progress((i + 1) / len(sc_list))
    off = 0.0
    for sc in sc_list:
        sc["_start"] = off
        off += sc["duration"]
    total = off

    cb.stage(4, 5, "Animasyon")
    silent = os.path.join(assets, "story_video.mp4")
    voice_path = _voice_track(sc_list, total, os.path.join(assets, "story_voice.wav"))
    a_in = ["-i", voice_path] if voice_path else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{ow}x{oh}",
           "-r", str(th.FPS), "-i", "-", *a_in, "-map", "0:v", "-map", "1:a", "-af", "apad",
           "-t", f"{total:.3f}", *enc(), *AUD, silent]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, **_NOWIN)
    imgs = [_load(p) for p in paths]
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ow, oh)
    ctx = cairo.Context(surf)
    D._K = k
    nfr = int(round(total * th.FPS))
    i = 0
    try:
        for f in range(nfr):
            if cb.cancelled():
                raise Cancelled()
            gt = f / th.FPS
            while i + 1 < len(sc_list) and gt >= sc_list[i + 1]["_start"]:
                i += 1
            sc = sc_list[i]
            t = gt - sc["_start"]
            span = sc["duration"] + XF
            ctx.set_source_rgb(0, 0, 0)
            ctx.paint()
            draw_image(ctx, imgs[i][0], sc["camera"], t / span, ow, oh)
            if i > 0 and t < XF:  # önceki sahne yumuşakça söner
                prev = sc_list[i - 1]
                ctx.push_group()
                draw_image(ctx, imgs[i - 1][0], prev["camera"], (prev["duration"] + t) / (prev["duration"] + XF), ow, oh)
                ctx.pop_group_to_source()
                ctx.paint_with_alpha(1 - ease_out_cubic(t / XF))
            if i == 0 and t < 0.4:
                ctx.set_source_rgba(0, 0, 0, 1 - t / 0.4)
                ctx.paint()
            if i == len(sc_list) - 1 and sc["duration"] - t < 0.6:
                ctx.set_source_rgba(0, 0, 0, 1 - (sc["duration"] - t) / 0.6)
                ctx.paint()
            _shade(ctx, ow, oh)
            ctx.save()
            ctx.scale(k, k)
            draw_caption(ctx, sc, t, dw, dh, lang, hi)
            ctx.restore()
            surf.flush()
            proc.stdin.write(surf.get_data())
            cb.progress(gt / total)
            if f % (preview_every * th.FPS // 30 or 1) == 0:
                from PIL import Image
                cb.preview(Image.frombuffer("RGBA", (ow, oh), bytes(surf.get_data()), "raw", "BGRA", 0, 1).convert("RGB"))
    except BaseException:
        proc.kill()
        raise
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg hikâye videosunu yazamadı")

    cb.stage(5, 5, "Montaj")
    out = os.path.join(out_dir, "video.mp4")
    cuts = [sc["_start"] for sc in sc_list[1:]]
    sfx_path = A.build_sfx([], total, os.path.join(assets, "efektler.wav"), cuts, volume=0.6) if sfx else None
    if music and music.startswith("auto:"):
        mood = music.split(":", 1)[1]
        log(f"Müzik üretiliyor ({A.MOODS.get(mood, mood)})…")
        music = A.build_music(mood, total, os.path.join(assets, "muzik.wav"))
    concat([silent], out, music, sfx_path, music_vol)
    srt = [f"{n + 1}\n{srt_time(sc['_start'] + LEAD)} --> {srt_time(sc['_start'] + sc['duration'])}\n{sc['narration']}\n"
           for n, sc in enumerate(sc_list)]
    with open(os.path.join(out_dir, "altyazi.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    try:
        thumbnail(plan, paths, os.path.join(out_dir, "kapak.png"), lang)
        publish.youtube_text(plan, sc_list, os.path.join(out_dir, "youtube.txt"))
        log("Kapak resmi (kapak.png) ve YouTube metinleri (youtube.txt) hazır.")
    except Exception as e:
        log(f"  [yayın paketi] {e}")
    for p in (silent,):
        try:
            os.remove(p)
        except OSError:
            pass
    log(f"Bitti: {out} ({total:.0f} sn video, {time.time() - t0:.0f} sn sürdü)")
    return out


def _rgb(hexs):
    h = hexs.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def still(sc, size=(960, 540), accent=None, lang="tr"):
    """Düzenleyici önizlemesi: sade zemin üzerinde sahnenin altyazısı (resim videoda çizilir)."""
    from PIL import Image
    w, h = size
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "darkroom_story_still.png")
    img, _ = _load(placeholder(tmp, w, h, len(sc.get("image_prompt", ""))))
    draw_image(ctx, img, sc.get("camera", "zoom_in"), 0.5, w, h)
    _shade(ctx, w, h)
    th.FONTS = dict(th.FONTS, caption=os.path.join(th.FONT_DIR, "Baloo2-ExtraBold.ttf"))
    k = w / 1920
    D._K = k
    text = sc.get("narration") or ""
    x = dict(sc, _groups=groups(text, word_times(text, [], 3.0)))
    ctx.save()
    ctx.scale(k, k)
    draw_caption(ctx, x, LEAD + 0.5, 1920, 1080, lang, _rgb(accent or CAPTION))
    D.draw_text(ctx, "RESİM: " + (sc.get("image_prompt") or "")[:90], 60, 90, 34, (1, 1, 1), 0.8)
    ctx.restore()
    surf.flush()
    return Image.frombuffer("RGBA", (w, h), bytes(surf.get_data()), "raw", "BGRA", 0, 1).convert("RGB")


def thumbnail(plan, paths, path, lang="tr"):
    """1280x720 kapak: hikâyenin en çarpıcı resmi (kanca sahnesi) ve iri başlık."""
    w, h = 1280, 720
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    img, _ = _load(paths[0])
    draw_image(ctx, img, "zoom_in", 0.6, w, h)
    g = cairo.LinearGradient(0, 0, w, 0)
    g.add_color_stop_rgba(0, 0, 0, 0, 0.75)
    g.add_color_stop_rgba(0.6, 0, 0, 0, 0)
    ctx.set_source(g)
    ctx.paint()
    D._K = 1.0
    title = _upper(plan.get("title", ""), lang)
    size = 92
    lines = D.wrap(title, size, 700, "caption")
    while len(lines) > 3 and size > 50:
        size -= 6
        lines = D.wrap(title, size, 700, "caption")
    y = (h - len(lines[:3]) * size * 1.05) / 2 + size * 0.8
    for n, ln in enumerate(lines[:3]):
        col = _rgb(CAPTION) if n == len(lines[:3]) - 1 else (1, 1, 1)
        D.draw_text(ctx, ln, 60, y, size, col, kind="caption", outline=(0, 0, 0), shadow=(0, 6))
        y += size * 1.05
    surf.write_to_png(path)
    return path
