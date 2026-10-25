"""Ses efektleri ve arka plan müziği: hepsi programın içinde sentezlenir, telif sorunu yoktur.

- Efektler (whoosh, pop, tık, bloop, ding) her sahnenin animasyon zamanlarına göre yerleştirilir.
- Müzik, seçilen havaya göre (enerjik / sakin / gizemli) video süresi kadar üretilir.
"""
import math
import wave

import numpy as np

SR = 44100
MOODS = {"enerjik": "Enerjik", "sakin": "Sakin", "gizemli": "Gizemli", "epik": "Epik", "gerilim": "Gerilim"}


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _env(n, attack=0.005, decay=None, sr=SR):
    a = max(1, int(attack * sr))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    if decay:
        e[a:] = np.exp(-np.arange(n - a) / (decay * sr))
    return e


def _smooth(x, k):
    """Basit alçak geçiren süzgeç (hareketli ortalama)."""
    if k <= 1:
        return x
    return np.convolve(x, np.ones(k) / k, mode="same")


# --- Efektler ----------------------------------------------------------------

def _whoosh(rng):
    d = 0.55
    n = int(d * SR)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    # süpürülen bant: düşükten yükseğe, ortada en yüksek ses
    for i, k in enumerate((48, 24, 12, 6)):
        seg = _smooth(noise, k) * (0.6 + i * 0.25)
        w = np.exp(-((np.linspace(0, 1, n) - (0.25 + i * 0.15)) ** 2) / 0.02)
        out += seg * w
    return out * np.hanning(n) * 0.9


def _pop(rng, f0=880):
    d = 0.12
    t = _t(d)
    f = f0 * np.exp(-t * 18) + f0 * 0.5
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * _env(len(t), 0.002, 0.03) * 0.8


def _tick(rng):
    t = _t(0.03)
    return np.sin(2 * np.pi * 2400 * t) * _env(len(t), 0.0005, 0.006) * 0.35


def _bloop(rng):
    t = _t(0.22)
    f = 300 + 500 * (t / t[-1]) ** 0.6
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * _env(len(t), 0.005, 0.08) * 0.7


def _ding(rng):
    t = _t(1.2)
    out = sum(a * np.sin(2 * np.pi * 1318.5 * m * t) * np.exp(-t * dcy)
              for m, a, dcy in ((1, 0.6, 3), (2.01, 0.25, 5), (3.0, 0.12, 8), (0.5, 0.2, 2.5)))
    return out * _env(len(t), 0.002) * 0.55


def _thud(rng):
    t = _t(0.35)
    f = 110 * np.exp(-t * 8) + 40
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * _env(len(t), 0.002, 0.12) * 0.9


SFX = {"whoosh": _whoosh, "pop": _pop, "tick": _tick, "bloop": _bloop, "ding": _ding, "thud": _thud}


def scene_events(sc, dur):
    """Sahne içi efekt zamanları: [(saniye, efekt, kazanç)]. Zamanlar scenes.py'deki animasyonlarla eşleşir."""
    t = sc.get("type")
    ev = []
    if t == "title":
        ev += [(0.25, "thud", 0.8), (1.0, "ding", 0.5)]
    elif t == "bullets":
        items = sc.get("items", [])[:6]
        gap = min(1.0, (dur - 2.0) / max(1, len(items)))
        ev += [(0.7 + i * gap, "pop", 0.6) for i in range(len(items))]
    elif t == "stat":
        end = 0.3 + min(2.2, dur * 0.5)
        ev += [(0.3 + k * 0.09, "tick", 0.5) for k in range(int((end - 0.3) / 0.09 * 0.6))]
        ev += [(end * 0.75, "pop", 0.7), (end * 0.8, "ding", 0.4)]
    elif t in ("bar", "pie"):
        n = len(sc.get("data", []))
        ev += [(0.6 + i * 0.18, "pop", 0.45) for i in range(min(n, 10))]
    elif t == "line":
        ev += [(0.5, "whoosh", 0.35)]
    elif t == "table":
        ev += [(0.6 + i * 0.12, "tick", 0.6) for i in range(min(len(sc.get("rows", [])), 8))]
    elif t == "character":
        ev += [(0.05, "bloop", 0.7)]
        if len(sc.get("characters") or []) > 1:
            ev += [(0.2, "bloop", 0.6)]
    elif t == "versus":
        ev += [(0.2, "bloop", 0.6), (0.35, "bloop", 0.6), (0.5, "thud", 0.7), (1.8, "ding", 0.6)]
    elif t == "people":
        ev += [(0.9 + k * 0.25, "pop", 0.35) for k in range(6)]
    elif t in ("map",):
        ev += [(0.4, "whoosh", 0.4), (1.2, "pop", 0.5)]
    elif t == "timeline":
        n = len(sc.get("events", []))
        ev += [(0.6 + i * max(0.4, (dur - 2) / max(1, n)), "pop", 0.55) for i in range(n)]
    elif t == "compare":
        ev += [(0.4, "whoosh", 0.4), (1.4, "pop", 0.6)]
    elif t == "outro":
        ev += [(0.2, "ding", 0.45)]
    return [(s, n, g) for s, n, g in ev if s < dur]


def build_sfx(timeline, total, path, transition_times=(), volume=1.0):
    """timeline: [(mutlak saniye, efekt, kazanç)]. Geçişlere whoosh eklenir. WAV dosyası yazar."""
    rng = np.random.default_rng(7)
    cache = {k: f(rng) for k, f in SFX.items()}
    out = np.zeros(int((total + 1.5) * SR))
    for tt in transition_times:
        timeline = list(timeline) + [(max(0, tt - 0.3), "whoosh", 0.55)]
    for s, name, gain in timeline:
        clip = cache[name] * gain
        i = int(s * SR)
        j = min(len(out), i + len(clip))
        if i < len(out):
            out[i:j] += clip[: j - i]
    _write(path, out * volume)
    return path


# --- Müzik -------------------------------------------------------------------

def _midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


PROGS = {  # akor dizileri (MIDI notaları), tempo, davul yoğunluğu
    "enerjik": ([[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]], 108, 2),
    "sakin": ([[57, 60, 64], [53, 57, 60], [60, 64, 67], [55, 59, 62]], 84, 1),
    "gizemli": ([[50, 53, 57], [46, 50, 53], [43, 46, 50], [45, 49, 52]], 76, 0),
    "epik": ([[57, 60, 64], [53, 57, 60], [60, 64, 67], [55, 59, 62]], 96, 2),
    "gerilim": ([[45, 48, 52], [46, 49, 53], [45, 48, 52], [44, 47, 51]], 100, 1),
}


def build_music(mood, total, path, seed=3):
    """Video süresi kadar telifsiz müzik üretir (WAV)."""
    chords, bpm, drums = PROGS.get(mood, PROGS["sakin"])
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    bar = beat * 4
    n = int((total + 2) * SR)
    pad = np.zeros(n)
    arp = np.zeros(n)
    bass = np.zeros(n)
    kit = np.zeros(n)
    nbars = int(math.ceil((total + 2) / bar))
    tb = _t(bar)
    bar_env = np.minimum(1, tb / 0.4) * np.minimum(1, (bar - tb) / 0.5)
    kick = np.sin(2 * np.pi * np.cumsum(55 * np.exp(-_t(0.3) * 10) + 42) / SR) * _env(int(0.3 * SR), 0.002, 0.09)
    hn = rng.standard_normal(int(0.05 * SR))
    hat = (hn - _smooth(hn, 4)) * _env(len(hn), 0.0005, 0.010) * 0.10  # yüksek geçiren gürültü
    clap = _smooth(rng.standard_normal(int(0.18 * SR)), 4) * _env(int(0.18 * SR), 0.002, 0.05) * 0.35
    step = beat / 2
    pl = int(step * SR)
    tp = _t(step)
    for b in range(nbars):
        ch = chords[b % len(chords)]
        i0 = int(b * bar * SR)
        seg = slice(i0, min(n, i0 + len(tb)))
        m = seg.stop - seg.start
        if m <= 0:
            break
        # yumuşak pad: hafif akortsuz sinüsler
        p = np.zeros(len(tb))
        for note in ch:
            f = _midi(note)
            for det in (-0.12, 0.0, 0.12):
                p += np.sin(2 * np.pi * f * (1 + det / 100) * tb + rng.random() * 6) * 0.06
                p += np.sin(2 * np.pi * 2 * f * tb) * 0.012
        pad[seg] += (p * bar_env)[:m]
        # bas
        fb = _midi(ch[0] - 12)
        bs = np.sin(2 * np.pi * fb * tb) * 0.22 * _env(len(tb), 0.01, beat * 1.5)
        if drums == 2:
            bs = np.concatenate([np.sin(2 * np.pi * fb * _t(beat)) * 0.2 * _env(int(beat * SR), 0.005, beat * 0.5)] * 4)
            bs = np.pad(bs, (0, max(0, len(tb) - len(bs))))[: len(tb)]
        bass[seg] += bs[:m]
        # arpej (sekizlikler)
        if mood != "gizemli" or b % 2 == 1:
            pat = [0, 1, 2, 1, 0, 2, 1, 2]
            for k in range(8):
                f = _midi(ch[pat[k]] + 12)
                j0 = i0 + k * pl
                if j0 >= n:
                    break
                tone = (np.sin(2 * np.pi * f * tp) + 0.25 * np.sin(2 * np.pi * 3 * f * tp)) * 0.07
                tone *= _env(pl, 0.003, step * (0.5 if mood == "enerjik" else 0.9))
                arp[j0:j0 + pl] += tone[: max(0, min(pl, n - j0))]
        # davul
        for k in range(4):
            j0 = i0 + int(k * beat * SR)
            if drums >= 1 and (k in (0, 2) or drums == 2):
                kit[j0:j0 + len(kick)] += kick[: max(0, min(len(kick), n - j0))] * (0.55 if drums == 2 else 0.4)
            if drums == 2 and k in (1, 3):
                kit[j0:j0 + len(clap)] += clap[: max(0, min(len(clap), n - j0))]
            if drums >= 1:
                for h in (0, 1):
                    jh = j0 + int(h * beat / 2 * SR)
                    kit[jh:jh + len(hat)] += hat[: max(0, min(len(hat), n - jh))] * (1 if h else 0.6)
        if mood == "gizemli" and b % 4 == 3:  # ara sıra uzak gong
            j0 = i0
            g = _t(min(bar, 2.5))
            gong = sum(np.sin(2 * np.pi * _midi(ch[0] - 24) * mm * g) * aa
                       for mm, aa in ((1, 0.3), (2.76, 0.1), (5.4, 0.05))) * np.exp(-g * 1.5)
            kit[j0:j0 + len(g)] += gong[: max(0, min(len(g), n - j0))]
    mix = _smooth(pad, 3) + arp + bass + kit
    fade = np.ones(n)
    fi, fo = int(1.5 * SR), int(3.0 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    end = int(total * SR)
    fade[max(0, end - fo):end] = np.linspace(1, 0, min(fo, end))
    fade[end:] = 0
    mix *= fade
    rms = np.sqrt(np.mean(mix[: max(1, end)] ** 2)) or 1
    _write(path, np.tanh(mix * 0.16 / rms) * 0.9)  # tutarlı ses düzeyi, yumuşak tepe kırpma
    return path


def _write(path, mono):
    data = np.clip(mono, -1, 1)
    pcm = (data * 32767).astype("<i2")
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())
