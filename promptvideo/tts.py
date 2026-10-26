"""Seslendirme: edge-tts (ücretsiz, doğal Türkçe sesler) -> gTTS -> sessiz."""
import asyncio
import os
import subprocess

VOICES = {"tr": "tr-TR-AhmetNeural", "en": "en-US-AndrewNeural"}
# Karakter sesleri: erkek / kadın (dil başına)
PAIRS = {"tr": ("tr-TR-AhmetNeural", "tr-TR-EmelNeural"), "en": ("en-US-AndrewNeural", "en-US-AvaNeural")}
LOOK_VOICE = {0: 0, 1: 1, 2: 0, 3: 1, 4: 0, 5: 0}  # karakter görünümüne göre varsayılan ses


def character_voices(chars, lang, main_voice):
    """Her karaktere bir ses verir; iki karakter varsa sesleri farklı olur."""
    pair = PAIRS.get(lang, PAIRS["tr"])
    out = []
    for i, c in enumerate(chars):
        v = c.get("voice")
        if v in ("erkek", "male"):
            v = pair[0]
        elif v in ("kadın", "kadin", "female"):
            v = pair[1]
        if not v:
            v = pair[LOOK_VOICE.get(c.get("look", i * 2) % 6, 0)]
            if i == 0 and main_voice in pair and len(chars) == 1:
                v = main_voice
        out.append(v)
    if len(out) > 1 and out[0] == out[1] and not chars[1].get("voice"):
        out[1] = pair[1] if out[0] == pair[0] else pair[0]
    return out


def join(paths, out, lead=0.4, gap=0.35):
    """Ses parçalarını aralarında kısa sessizlikle birleştirir (WAV). Her parçanın başlangıç zamanını döner."""
    from .render import FFMPEG, _NOWIN
    ins, fc, labels, starts, t = [], [], [], [], lead
    for i, p in enumerate(paths):
        ins += ["-i", p]
        d = duration(p)
        starts.append((t, t + d))
        fc.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,apad=pad_dur={gap}[a{i}]")
        labels.append(f"[a{i}]")
        t += d + gap
    fc.append(f"{''.join(labels)}concat=n={len(paths)}:v=0:a=1,adelay={int(lead * 1000)}|{int(lead * 1000)}[a]")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[a]", out],
                   check=True, **_NOWIN)
    return out, starts


def duration(path):
    """Ses süresi (sn). Ayrıca ffprobe gerektirmemek için ffmpeg çıktısından okunur."""
    import re
    from .render import FFMPEG, _NOWIN
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True, **_NOWIN)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def synthesize(text, path, lang="tr", voice=None, rate="+0%", edge=True):
    """Metni mp3'e çevirir. Başarılıysa dosya yolunu, değilse None döner. edge=False: doğrudan gTTS."""
    if not text or not text.strip():
        return None
    voice = voice or os.environ.get("PV_VOICE") or VOICES.get(lang, VOICES["en"])
    try:
        if not edge:
            raise RuntimeError("edge-tts atlandı")
        import edge_tts

        async def run():
            await edge_tts.Communicate(text, voice, rate=rate).save(path)
        asyncio.run(run())
        if os.path.getsize(path) > 0:
            return path
    except Exception as e:
        if edge:
            print(f"  [tts] edge-tts kullanılamadı ({type(e).__name__}), gTTS deneniyor")
    try:
        from gtts import gTTS
        gTTS(text, lang=lang).save(path)
        return path
    except Exception as e:
        print(f"  [tts] gTTS de kullanılamadı ({type(e).__name__}); sahne sessiz kalacak")
    if os.path.exists(path) and os.path.getsize(path) == 0:
        os.remove(path)
    return None


def synthesize_words(text, path, lang="tr", voice=None, rate="+0%"):
    """synthesize gibi; ayrıca her kelimenin söylendiği zamanı döner: (yol, [(başlangıç, bitiş, kelime)]).
    Kelime zamanları yalnızca edge-tts ile gelir; gTTS'e düşülürse liste boş olur."""
    if not text or not text.strip():
        return None, []
    voice = voice or os.environ.get("PV_VOICE") or VOICES.get(lang, VOICES["en"])
    words = []
    try:
        import edge_tts

        async def run():
            with open(path, "wb") as f:
                async for ch in edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary").stream():
                    if ch["type"] == "audio":
                        f.write(ch["data"])
                    elif ch["type"] == "WordBoundary":
                        s = ch["offset"] / 1e7
                        words.append((s, s + ch["duration"] / 1e7, ch["text"]))
        asyncio.run(run())
        if os.path.getsize(path) > 0:
            return path, words
    except Exception as e:
        print(f"  [tts] edge-tts kullanılamadı ({type(e).__name__}), gTTS deneniyor")
    return synthesize(text, path, lang, voice, rate, edge=False), []
