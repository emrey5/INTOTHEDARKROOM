"""Seslendirme: edge-tts (ücretsiz, doğal Türkçe sesler) -> gTTS -> sessiz."""
import asyncio
import os
import subprocess

VOICES = {"tr": "tr-TR-AhmetNeural", "en": "en-US-AndrewNeural"}


def duration(path):
    """Ses süresi (sn). Ayrıca ffprobe gerektirmemek için ffmpeg çıktısından okunur."""
    import re
    from .render import FFMPEG, _NOWIN
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True, **_NOWIN)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def synthesize(text, path, lang="tr", voice=None, rate="+0%"):
    """Metni mp3'e çevirir. Başarılıysa dosya yolunu, değilse None döner."""
    if not text or not text.strip():
        return None
    voice = voice or os.environ.get("PV_VOICE") or VOICES.get(lang, VOICES["en"])
    try:
        import edge_tts

        async def run():
            await edge_tts.Communicate(text, voice, rate=rate).save(path)
        asyncio.run(run())
        if os.path.getsize(path) > 0:
            return path
    except Exception as e:
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
