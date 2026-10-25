"""Sahneleri kare kare çizip ffmpeg ile videoya dönüştürür ve birleştirir.

Tüm sahneler (video klipler dahil) aynı Cairo hattından geçer; böylece geçişler, metin
animasyonları ve stil her sahnede tutarlıdır."""
import os
import shutil
import subprocess

import cairo

from . import draw as D
from . import theme as th
from .scenes import DRAWERS, media_scene
from .theme import W, H, clamp, ease_out_cubic



def _find_ffmpeg():
    """Önce sistemdeki ffmpeg, yoksa uygulamayla gelen (imageio-ffmpeg) kopya."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


FFMPEG = _find_ffmpeg()
_NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}  # Windows'ta konsol penceresi açma
def enc():
    """x264 ayarları; kare hızı o anki seçime (30/60) göre."""
    return ["-c:v", "libx264", "-preset", os.environ.get("PV_PRESET", "medium"),
            "-crf", os.environ.get("PV_CRF", "19"), "-pix_fmt", "yuv420p", "-r", str(th.FPS)]


ENC = enc()  # eski kullanım için (30 fps)
AUD = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
TR = 0.55  # geçiş süresi (sn), sahnenin sonunda kapanır, sonrakinin başında açılır
BOIL_EVERY = 4  # çizgi stilinde çizgiler kaç karede bir "titresin"


def _audio_inputs(audio):
    if audio and os.path.exists(audio):
        return ["-i", audio]
    return ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]


class VideoReader:
    """Klipten 1920x1080 BGRA kareler okur (gerekirse başa sarar)."""

    def __init__(self, path, dur):
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={th.FPS},format=bgra"
        self.proc = subprocess.Popen(
            [FFMPEG, "-loglevel", "error", "-stream_loop", "-1", "-i", path, "-t", f"{dur + 1:.2f}",
             "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgra", "-"], stdout=subprocess.PIPE, **_NOWIN)
        self.size = W * H * 4
        self.buf = None
        self.surf = None

    def next(self):
        data = self.proc.stdout.read(self.size)
        if len(data) == self.size:
            self.buf = bytearray(data)
            self.surf = cairo.ImageSurface.create_for_data(self.buf, cairo.FORMAT_ARGB32, W, H, W * 4)
        return self.surf

    def close(self):
        try:
            self.proc.stdout.close()
            self.proc.kill()
        except Exception:
            pass


def render_frame(ctx, sc, t, dur, gt, total_t, sidx, nscenes, video_surf=None):
    D.BOIL = int(gt * 30) // BOIL_EVERY if th.SKETCH else 0  # 60 fps'te de aynı hızda titrer
    D.background(ctx, gt)
    D.SUBS = bool(sc.get("_subs") and sc.get("narration") and sc["type"] != "character")  # karakterde balon yeter
    # ilk sahne yumuşak açılır, son sahne yumuşak kapanır; aradaki kesmeleri geçiş perdeleri örter
    a = 1.0
    if sidx == 0:
        a *= ease_out_cubic(clamp(t / 0.6))
    if sidx == nscenes - 1:
        a *= clamp((dur - t) / 0.8)
    ctx.push_group()
    with th.scene_accent(sc.get("accent")):  # sahneye özel vurgu rengi
        if sc["type"] == "video":
            media_scene(ctx, sc, t, dur, video_surf)
        else:
            DRAWERS.get(sc["type"], DRAWERS["bullets"])(ctx, sc, t, dur)
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(a)
    if D.SUBS:
        D.subtitle(ctx, sc["narration"], t, 0.3, sc.get("_speech") or max(1.0, dur - 1.2))
    if sidx > 0 and t < TR:
        D.transition(ctx, D.TRANSITIONS[(sidx - 1) % len(D.TRANSITIONS)], 1 - t / TR, True, sidx - 1)
    if sidx < nscenes - 1 and t > dur - TR:
        D.transition(ctx, D.TRANSITIONS[sidx % len(D.TRANSITIONS)], (t - (dur - TR)) / TR, False, sidx)
    progress_bar(ctx, gt / max(total_t, 0.01))
    if th.PIXEL:
        pixelate(ctx.get_target())


# 8-bit palet (PICO-8): her piksel en yakın renge indirgenir
_PAL = None
_BAYER = None


def pixelate(surf, px=None):
    """Kareyi iri piksellere ve sınırlı palete indirger (retro oyun görünümü)."""
    import numpy as np
    global _PAL, _BAYER
    if _PAL is None:
        cols = ["000000", "1D2B53", "7E2553", "008751", "AB5236", "5F574F", "C2C3C7", "FFF1E8", "FF004D",
                "FFA300", "FFEC27", "00E436", "29ADFF", "83769C", "FF77A8", "FFCCAA", "1D1430", "2B1B4A"]
        _PAL = np.array([[int(c[i:i + 2], 16) for i in (4, 2, 0)] for c in cols], np.int32)  # BGR sırası
        _BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 - 0.5) * 24
    surf.flush()
    w, h = surf.get_width(), surf.get_height()
    stride = surf.get_stride()
    k = px or max(2, int(round(4 * w / W)))  # 1080p'de 4 piksel = 480x270 "ekran"
    buf = np.ndarray((h, stride // 4, 4), np.uint8, surf.get_data())
    a = buf[:h - h % k, :w - w % k, :3].astype(np.int32)
    sh, sw = a.shape[0] // k, a.shape[1] // k
    small = a.reshape(sh, k, sw, k, 3).mean(axis=(1, 3))
    small += _BAYER[np.arange(sh)[:, None] % 4, np.arange(sw)[None, :] % 4][..., None]  # düzenli titreşim (dither)
    d = ((small[:, :, None, :] - _PAL[None, None, :, :]) ** 2).sum(-1)
    q = _PAL[d.argmin(-1)].astype(np.uint8)
    big = np.repeat(np.repeat(q, k, axis=0), k, axis=1)
    buf[:big.shape[0], :big.shape[1], :3] = big
    surf.mark_dirty()


def progress_bar(ctx, p):
    if th.SKETCH:
        ctx.set_source_rgba(*th.INK, 0.15)
        ctx.rectangle(0, H - 8, W, 8)
        ctx.fill()
        ctx.set_source_rgb(*th.ACCENT)
        ctx.rectangle(0, H - 8, W * clamp(p), 8)
        ctx.fill()
        return
    ctx.set_source_rgba(1, 1, 1, 0.08)
    ctx.rectangle(0, H - 6, W, 6)
    ctx.fill()
    ctx.set_source(D.accent_gradient(0, 0, W, 0))
    ctx.rectangle(0, H - 6, W * clamp(p), 6)
    ctx.fill()


def render_scene(sc, out_path, t_offset, total_t, sidx, nscenes, audio=None, on_frame=None):
    dur = sc["duration"]
    ow, oh = th.out_size()
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{ow}x{oh}", "-r", str(th.FPS), "-i", "-", *_audio_inputs(audio),
           "-map", "0:v", "-map", "1:a", "-af", "apad", "-t", f"{dur:.3f}", *enc(), *AUD, out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, **_NOWIN)
    reader = VideoReader(sc["video_path"], dur) if sc["type"] == "video" and sc.get("video_path") else None
    surf, ctx = D.new_surface()
    try:
        for f in range(int(round(dur * th.FPS))):
            t = f / th.FPS
            vs = reader.next() if reader else None
            ctx.save()
            render_frame(ctx, sc, t, dur, t_offset + t, total_t, sidx, nscenes, vs)
            ctx.restore()
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
        raise RuntimeError(f"ffmpeg sahne {sidx} için başarısız oldu")


def concat(parts, out_path, music=None, sfx=None, music_vol=0.35):
    lst = out_path + ".txt"
    with open(lst, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    music = music if music and os.path.exists(music) else None
    sfx = sfx if sfx and os.path.exists(sfx) else None
    if music or sfx:
        tmp = out_path + ".nomusic.mp4"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c", "copy", tmp], check=True, **_NOWIN)
        ins, fc, mix = ["-i", tmp], ["[0:a]asplit=2[v][vk]"], ["[v]"]
        if music:
            # müzik düşük seviyede çalar, konuşma varken otomatik kısılır (sidechain ducking)
            ins += ["-i", music]
            fc += [f"[{len(ins) // 2 - 1}:a]volume={music_vol:.2f},aloop=loop=-1:size=2e9[m]",
                   "[m][vk]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md]"]
            mix.append("[md]")
        else:
            fc[0] = "[0:a]anull[v]"
        if sfx:
            ins += ["-i", sfx]
            fc.append(f"[{len(ins) // 2 - 1}:a]volume=0.55[sx]")
            mix.append("[sx]")
        fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0[a]")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc),
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", *AUD, "-movflags", "+faststart", out_path],
                       check=True, **_NOWIN)
        os.remove(tmp)
    else:
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c", "copy", "-movflags", "+faststart", out_path], check=True, **_NOWIN)
    os.remove(lst)
