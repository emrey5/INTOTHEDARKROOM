"""Kullanım:
    python -m promptvideo "Türkiye'nin nüfusu 1960'tan bugüne nasıl değişti?"
    python -m promptvideo --plan cikti/plan.json      # düzenlenmiş planı yeniden çiz
    python -m promptvideo --gui                       # masaüstü uygulaması
"""
import argparse
import json
import sys

from .pipeline import create_plan, render_plan


def main(argv=None):
    ap = argparse.ArgumentParser(prog="promptvideo", description="Prompt'tan veri destekli video üretir")
    ap.add_argument("prompt", nargs="?", help="Videonun konusu / isteğiniz")
    ap.add_argument("--plan", help="Hazır plan.json dosyasından üret")
    ap.add_argument("--out", default="cikti", help="Çıktı klasörü (varsayılan: cikti)")
    ap.add_argument("--lang", default="tr")
    ap.add_argument("--voice", help="edge-tts ses adı, ör. tr-TR-EmelNeural")
    ap.add_argument("--music", help="Arka plan müziği: dosya yolu ya da auto:sakin / enerjik / gizemli / epik / gerilim / retro")
    ap.add_argument("--no-sfx", action="store_true", help="Ses efektlerini kapat")
    ap.add_argument("--vertical", action="store_true", help="Ayrıca 9:16 dikey (Shorts) sürüm üret")
    ap.add_argument("--plan-only", action="store_true", help="Sadece planı oluştur, videoyu çizme")
    ap.add_argument("--square", action="store_true", help="Ayrıca 1:1 kare sürüm üret")
    ap.add_argument("--kind", choices=["gercekci", "cizgi", "infografik", "haber", "kinetik", "karakter", "piksel"],
                    help="Video türü (senaryo ve görünüm buna göre)")
    ap.add_argument("--style", choices=["mekanik", "modern", "belgesel", "haber", "minimal", "cizgi", "piksel"],
                    help="Görünüm (varsayılan: mekanik)")
    ap.add_argument("--accent", help="Vurgu rengi, ör. #FF7A1A")
    ap.add_argument("--bg", help="Arka plan rengi, ör. #050505")
    ap.add_argument("--quality", choices=["720", "1080", "1440", "2160"], default="1080", help="Çözünürlük")
    ap.add_argument("--fps", type=int, choices=[30, 60], default=30)
    ap.add_argument("--tempo", choices=["yavas", "normal", "hizli"], default="normal")
    ap.add_argument("--music-volume", type=float, default=35, help="Müzik seviyesi (0-100, varsayılan 35)")
    ap.add_argument("--length", choices=["kisa", "orta", "uzun"], default="orta", help="Video süresi")
    ap.add_argument("--subtitles", action="store_true", help="Altyazıyı videonun üstüne yaz")
    ap.add_argument("--no-voice", action="store_true", help="Seslendirmeyi kapat")
    ap.add_argument("--gui", action="store_true", help="Masaüstü uygulamasını aç")
    a = ap.parse_args(argv)
    if a.gui or (not a.prompt and not a.plan):
        from .app import run_app
        return run_app()
    if a.plan:
        with open(a.plan, encoding="utf-8") as f:
            plan = json.load(f)
    else:
        plan = create_plan(a.prompt, a.out, a.lang, length=a.length, kind=a.kind)
        if a.plan_only:
            return
    render_plan(plan, a.out, a.style, a.voice, a.music, a.no_voice, a.lang, subtitles=a.subtitles, sfx=not a.no_sfx,
                vertical=a.vertical, square=a.square, quality=a.quality, fps=a.fps, tempo=a.tempo,
                accent=a.accent, bg=a.bg, music_vol=a.music_volume / 100)


if __name__ == "__main__":
    sys.exit(main())
