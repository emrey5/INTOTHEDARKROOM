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
from .theme import W, H, FPS, clamp, ease_out_cubic



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
ENC = ["-c:v", "libx264", "-preset", os.environ.get("PV_PRESET", "medium"),
       "-crf", os.environ.get("PV_CRF", "19"), "-pix_fmt", "yuv420p", "-r", str(FPS)]
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
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=bgra"
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
    D.BOIL = int(gt * FPS) // BOIL_EVERY if th.SKETCH else 0
    D.background(ctx, gt)
    D.SUBS = bool(sc.get("_subs") and sc.get("narration") and sc["type"] != "character")  # karakterde balon yeter
    # ilk sahne yumuşak açılır, son sahne yumuşak kapanır; aradaki kesmeleri geçiş perdeleri örter
    a = 1.0
    if sidx == 0:
        a *= ease_out_cubic(clamp(t / 0.6))
    if sidx == nscenes - 1:
        a *= clamp((dur - t) / 0.8)
    ctx.push_group()
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
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", *_audio_inputs(audio),
           "-map", "0:v", "-map", "1:a", "-af", "apad", "-t", f"{dur:.3f}", *ENC, *AUD, out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, **_NOWIN)
    reader = VideoReader(sc["video_path"], dur) if sc["type"] == "video" and sc.get("video_path") else None
    surf, ctx = D.new_surface()
    try:
        for f in range(int(round(dur * FPS))):
            t = f / FPS
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


def concat(parts, out_path, music=None, sfx=None):
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
            fc += [f"[{len(ins) // 2 - 1}:a]volume=0.35,aloop=loop=-1:size=2e9[m]",
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
