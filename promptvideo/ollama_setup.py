"""Ollama'yı uygulamanın içinden hazırlar: bulur, kapalıysa başlatır, yoksa indirip kurar, modeli indirir.

Ollama ücretsiz ve açık kaynaktır (https://ollama.com). Windows'ta resmî OllamaSetup.exe sessiz kurulur;
macOS ve Linux'ta indirme sayfası açılır (orada kurulum tek adımdır).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import requests

from . import planner

SETUP_URL = "https://ollama.com/download/OllamaSetup.exe"
DOWNLOAD_PAGE = "https://ollama.com/download"
_NOWIN = {"creationflags": 0x08000000 | 0x00000008} if sys.platform == "win32" else {}  # pencere yok, ayrık


def server_up(timeout=2):
    try:
        return requests.get(f"{planner.OLLAMA}/api/tags", timeout=timeout).ok
    except Exception:
        return False


def find_exe():
    """Kurulu ollama programının yolu (yoksa None)."""
    found = shutil.which("ollama")
    if found:
        return found
    cands = []
    if sys.platform == "win32":
        la = os.environ.get("LOCALAPPDATA", "")
        cands += [os.path.join(la, "Programs", "Ollama", "ollama.exe"),
                  os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Ollama", "ollama.exe")]
    elif sys.platform == "darwin":
        cands += ["/Applications/Ollama.app/Contents/Resources/ollama", "/usr/local/bin/ollama",
                  "/opt/homebrew/bin/ollama"]
    else:
        cands += ["/usr/local/bin/ollama", "/usr/bin/ollama"]
    return next((c for c in cands if os.path.isfile(c)), None)


def start_server(exe=None, wait=20):
    """Ollama kapalıysa arka planda başlatır; açılınca True döner."""
    if server_up():
        return True
    exe = exe or find_exe()
    if not exe:
        return False
    try:
        subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, **_NOWIN)
    except OSError:
        return False
    end = time.time() + wait
    while time.time() < end:
        if server_up(1):
            return True
        time.sleep(0.5)
    return False


def ram_gb():
    try:
        if sys.platform == "win32":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
            m = MS()
            m.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.total / 2 ** 30
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30
    except Exception:
        return 16.0


def recommended_model():
    """Bilgisayarın belleğine uygun model: 12 GB altı için daha küçük ve hızlı olanı."""
    return "qwen3:8b" if ram_gb() >= 12 else "qwen3:4b"


def has_model(model):
    try:
        names = [m["name"] for m in requests.get(f"{planner.OLLAMA}/api/tags", timeout=3).json().get("models", [])]
    except Exception:
        return False
    return model in names or (":" not in model and f"{model}:latest" in names)


def _download(url, path, progress, cancelled):
    with requests.get(url, stream=True, timeout=60, headers={"User-Agent": "DARKROOM"}) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                if cancelled():
                    raise RuntimeError("İptal edildi.")
                f.write(chunk)
                done += len(chunk)
                if total:
                    progress(done / total, f"Ollama indiriliyor… {done / 2 ** 20:.0f} / {total / 2 ** 20:.0f} MB")


def install(progress, log, cancelled=lambda: False):
    """Windows'ta Ollama'yı indirip sessizce kurar. Diğer sistemlerde False döner (sayfa açılmalı)."""
    if sys.platform != "win32":
        return False
    path = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
    _download(SETUP_URL, path, progress, cancelled)
    progress(1.0, "Ollama kuruluyor… (bir iki dakika sürebilir)")
    log("Ollama kuruluyor…")
    subprocess.run([path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"], check=False)
    for _ in range(60):  # kurulum bitince program yerinde olur
        if find_exe():
            break
        time.sleep(1)
    try:
        os.remove(path)
    except OSError:
        pass
    return bool(find_exe())


def pull(model, progress, cancelled=lambda: False):
    """Modeli indirir; ilerlemeyi katman katman bildirir."""
    with requests.post(f"{planner.OLLAMA}/api/pull", json={"model": model, "stream": True},
                       stream=True, timeout=(10, 600)) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if cancelled():
                raise RuntimeError("İptal edildi.")
            if not line:
                continue
            d = json.loads(line)
            if d.get("error"):
                raise RuntimeError(d["error"])
            tot, comp = d.get("total"), d.get("completed")
            if tot and comp:
                progress(comp / tot, f"{model} indiriliyor… {comp / 2 ** 30:.1f} / {tot / 2 ** 30:.1f} GB")
            elif d.get("status"):
                progress(None, f"{model}: {d['status']}")
            if d.get("status") == "success":
                return True
    return has_model(model)


def ensure(model, progress, log, cancelled=lambda: False):
    """Her şeyi hazırlar. Dönüş: (hazır mı, açıklama)."""
    if not server_up():
        exe = find_exe()
        if not exe:
            if sys.platform != "win32":
                return False, "page"
            log("Ollama bulunamadı, indiriliyor…")
            if not install(progress, log, cancelled):
                return False, "Ollama kurulamadı. ollama.com/download adresinden elle kurmayı deneyin."
        progress(None, "Ollama başlatılıyor…")
        if not start_server():
            return False, "Ollama kuruldu ama başlatılamadı. Bilgisayarı yeniden başlatıp tekrar deneyin."
    if not has_model(model):
        log(f"{model} modeli indiriliyor…")
        pull(model, progress, cancelled)
    return has_model(model), "ok"
