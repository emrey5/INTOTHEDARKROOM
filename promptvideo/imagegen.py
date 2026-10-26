"""Görsel motoru: hikâye sahnelerinin resimlerini kullanıcının ekran kartında çizer.

Ücretsiz ComfyUI (https://github.com/Comfy-Org/ComfyUI) arka planda çalışır; program ona HTTP ile
iş gönderir. Model: Stable Diffusion XL + SDXL-Lightning (4 adımda çizer, 8 GB kartta sahne başına birkaç
saniye). Windows'ta kurulum tek tıkla yapılır: taşınabilir ComfyUI ve modeller indirilir, kurulum
gerektirmez, %LOCALAPPDATA%\\DARKROOM altına açılır.
"""
import json
import os
import subprocess
import sys
import time
import uuid

import requests

HOST = os.environ.get("PV_COMFY", "http://127.0.0.1:8188")
COMFY_URL = "https://github.com/Comfy-Org/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z"
SEVENZIP_URL = "https://www.7-zip.org/a/7zr.exe"
MODELS = {  # (klasör, dosya, adres, yaklaşık boyut GB)
    "base": ("checkpoints", "sd_xl_base_1.0.safetensors",
             "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors", 6.9),
    "lightning": ("loras", "sdxl_lightning_4step_lora.safetensors",
                  "https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_4step_lora.safetensors", 0.4),
}
TOTAL_GB = 1.9 + sum(m[3] for m in MODELS.values())  # ComfyUI + modeller
_NOWIN = {"creationflags": 0x08000000 | 0x00000008} if sys.platform == "win32" else {}

# çizim tarzları: her sahnenin istemine eklenir, tüm resimler aynı görünür
STYLES = {
    "cartoon": "3d animated movie still, pixar style, cute cartoon, vibrant colors, soft cinematic lighting, "
               "highly detailed, depth of field",
    "anime": "anime style illustration, studio ghibli inspired, vibrant colors, detailed background, soft light",
    "comic": "comic book illustration, bold ink outlines, flat vibrant colors, dynamic composition",
    "realistic": "cinematic photo, realistic, dramatic lighting, 35mm film, highly detailed",
    "storybook": "children's storybook illustration, watercolor and gouache, warm colors, whimsical",
}
NEGATIVE = ("text, letters, watermark, logo, signature, blurry, low quality, deformed, ugly, extra limbs, "
            "extra fingers, bad anatomy, cropped, frame, border")


def home():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "DARKROOM", "ComfyUI_windows_portable")


def comfy_dir():
    return os.path.join(home(), "ComfyUI")


def server_up(timeout=2):
    try:
        return requests.get(f"{HOST}/system_stats", timeout=timeout).ok
    except Exception:
        return False


def installed():
    """ComfyUI ve modeller yerinde mi?"""
    if not os.path.isfile(os.path.join(comfy_dir(), "main.py")):
        return False
    return all(os.path.isfile(os.path.join(comfy_dir(), "models", d, f)) for d, f, _, _ in MODELS.values())


def ready():
    return server_up() or installed()


def start_server(wait=180):
    """ComfyUI'yi arka planda başlatır; açılınca True döner (ilk açılış bir iki dakika sürebilir)."""
    if server_up():
        return True
    py = os.path.join(home(), "python_embeded", "python.exe")
    if not os.path.isfile(py):
        return False
    global _proc
    try:
        _proc = subprocess.Popen([py, "-s", os.path.join(comfy_dir(), "main.py"), "--windows-standalone-build",
                          "--listen", "127.0.0.1", "--port", HOST.rsplit(":", 1)[-1], "--disable-auto-launch"],
                         cwd=home(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, **_NOWIN)
    except OSError:
        return False
    end = time.time() + wait
    while time.time() < end:
        if server_up(1):
            return True
        time.sleep(1)
    return False


_proc = None  # programın kendi başlattığı ComfyUI


def release():
    """Çizim bitince ekran kartının belleğini boşaltır (oyunlar ve diğer programlar için).
    ComfyUI'yi program başlattıysa kapatır; kullanıcı kendisi açtıysa yalnızca modelleri bellekten çıkarır."""
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        _proc = None
        return
    try:
        requests.post(f"{HOST}/free", json={"unload_models": True, "free_memory": True}, timeout=5)
    except Exception:
        pass


def _download(url, path, progress, label, cancelled, limit=None):
    """limit: saniyede en fazla kaç MB (None = sınırsız). Oyun oynarken internetin yavaşlamaması için."""
    if os.path.isfile(path):
        return
    tmp = path + ".part"
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0  # yarıda kalan indirme kaldığı yerden sürer
    headers = {"User-Agent": "DARKROOM", **({"Range": f"bytes={have}-"} if have else {})}
    with requests.get(url, stream=True, timeout=60, headers=headers, allow_redirects=True) as r:
        r.raise_for_status()
        if have and r.status_code != 206:
            have = 0
        total = int(r.headers.get("content-length") or 0) + have
        done = have
        t0, got = time.time(), 0
        with open(tmp, "ab" if have else "wb") as f:
            for chunk in r.iter_content(1 << 20):
                if cancelled():
                    raise RuntimeError("İptal edildi.")
                f.write(chunk)
                done += len(chunk)
                got += len(chunk)
                if limit:  # hız sınırı: beklenen süreden hızlı gidiyorsak biraz bekle
                    ahead = got / (limit * 2 ** 20) - (time.time() - t0)
                    if ahead > 0:
                        time.sleep(ahead)
                if total:
                    sp = got / max(0.1, time.time() - t0) / 2 ** 20
                    progress(done / total, f"{label} indiriliyor… {done / 2 ** 30:.1f} / {total / 2 ** 30:.1f} GB"
                                           f" · {sp:.1f} MB/sn{' (yavaş mod)' if limit else ''}")
    os.replace(tmp, path)


SLOW_MB = 3  # yavaş modda saniyede en fazla 3 MB (~24 Mbit): oyun ve video izlerken fark edilmez


def install(progress, log, cancelled=lambda: False, slow=False):
    """Windows'ta ComfyUI'yi ve modelleri indirip hazırlar. Dönüş: (hazır mı, açıklama).
    slow=True: indirme hızı sınırlanır, yarıda kesilirse sonra kaldığı yerden sürer."""
    limit = SLOW_MB if slow else None
    if sys.platform != "win32":
        return False, "Görsel motorunun otomatik kurulumu şimdilik yalnızca Windows'ta. ComfyUI'yi elle kurup " \
                      "8188 portunda çalıştırırsanız program onu kullanır."
    root = os.path.dirname(home())
    os.makedirs(root, exist_ok=True)
    if not os.path.isfile(os.path.join(comfy_dir(), "main.py")):
        arc = os.path.join(root, "ComfyUI_windows_portable_nvidia.7z")
        _download(COMFY_URL, arc, progress, "ComfyUI", cancelled, limit)
        # arşiv BCJ2 süzgeciyle sıkıştırılmış; bunu yalnızca 7-Zip'in kendi aracı açabiliyor (7zr.exe, ~600 KB)
        seven = os.path.join(root, "7zr.exe")
        _download(SEVENZIP_URL, seven, progress, "7-Zip", cancelled)
        progress(None, "ComfyUI açılıyor… (birkaç dakika sürebilir)")
        log("ComfyUI arşivi açılıyor…")
        r = subprocess.run([seven, "x", arc, f"-o{root}", "-y", "-bso0", "-bsp0"], capture_output=True, text=True,
                           creationflags=0x08000000 | 0x00004000)  # pencere yok, düşük öncelik (oyun etkilenmesin)
        if r.returncode != 0 or not os.path.isfile(os.path.join(comfy_dir(), "main.py")):
            return False, f"ComfyUI arşivi açılamadı: {(r.stderr or r.stdout).strip()[:300]}"
        os.remove(arc)
    for key, (folder, name, url, _) in MODELS.items():
        d = os.path.join(comfy_dir(), "models", folder)
        os.makedirs(d, exist_ok=True)
        _download(url, os.path.join(d, name), progress, "Çizim modeli" if key == "base" else "Hızlandırıcı", cancelled,
                  limit)
    progress(None, "Görsel motoru başlatılıyor…")
    if not start_server():
        return False, "Görsel motoru kuruldu ama başlatılamadı. Ekran kartı sürücüsünü güncelleyip tekrar deneyin."
    release()  # çalıştığı görüldü; video yapılırken yeniden açılır
    return True, "ok"


def _workflow(prompt, width, height, seed):
    base, lora = MODELS["base"][1], MODELS["lightning"][1]
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": base}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": NEGATIVE}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "positive": ["3", 0], "negative": ["4", 0],
                                                    "latent_image": ["5", 0], "seed": seed, "steps": 4, "cfg": 1.0,
                                                    "sampler_name": "euler", "scheduler": "sgm_uniform", "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "darkroom"}},
    }


# Resim stüdyosu biçimleri: SDXL'in iyi çizdiği boyutlar (genişlik, yükseklik)
FORMATS = {"yatay": (1344, 768), "dikey": (768, 1344), "kare": (1024, 1024)}
STYLE_NAMES = {"cartoon": "3D çizgi film", "anime": "Anime", "comic": "Çizgi roman", "realistic": "Gerçekçi",
               "storybook": "Masal kitabı"}


def to_english(text, log=print):
    """Türkçe tarifi çizim modeli için İngilizce isteme çevirir (Ollama varsa); yoksa olduğu gibi döner."""
    import re as _re
    if not text.strip() or not _re.search(r"[çğıöşüÇĞİÖŞÜ]|\b(ve|bir|ile|olan|gibi)\b", text):
        return text
    try:
        from . import planner as P
        ok, _ = P.ollama_available()
        if not ok:
            return text
        r = requests.post(f"{P.OLLAMA}/api/chat", timeout=300, json={
            "model": P.MODEL, "stream": False, "think": False, "options": {"temperature": 0.2},
            "messages": [{"role": "system", "content": "Translate the user's picture description into a concise English "
                                                       "image-generation prompt (comma separated visual details). "
                                                       "Reply with the prompt only."},
                         {"role": "user", "content": text}]})
        out = _re.sub(r"<think>.*?</think>", "", r.json()["message"]["content"], flags=_re.S).strip().strip('"')
        return out or text
    except Exception as e:
        log(f"  [çeviri] {e}")
        return text


def full_prompt(scene_prompt, character="", style="cartoon"):
    # önce konu, sonra tarz: istemin başındaki kelimeler resimde daha güçlü etki eder
    parts = [character, scene_prompt, STYLES.get(style, STYLES["cartoon"])]
    return ", ".join(p.strip(" ,") for p in parts if p and p.strip())


def generate(prompt, path, width=1344, height=768, seed=1, timeout=600, cancelled=lambda: False):
    """Bir resim çizer ve path'e kaydeder. SDXL için uygun boyutlar: 1344x768 (yatay), 768x1344 (dikey)."""
    if not server_up() and not start_server():
        raise RuntimeError("Görsel motoru (ComfyUI) çalışmıyor.")
    r = requests.post(f"{HOST}/prompt", json={"prompt": _workflow(prompt, width, height, seed),
                                               "client_id": uuid.uuid4().hex}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Görsel motoru isteği reddetti: {r.text[:300]}")
    pid = r.json()["prompt_id"]
    end = time.time() + timeout
    while time.time() < end:
        if cancelled():
            raise RuntimeError("İptal edildi.")
        h = requests.get(f"{HOST}/history/{pid}", timeout=10).json().get(pid)
        if h:
            st = h.get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError(f"Görsel çizilemedi: {json.dumps(st.get('messages', ''))[:300]}")
            for out in h.get("outputs", {}).values():
                for im in out.get("images", []):
                    data = requests.get(f"{HOST}/view", params={"filename": im["filename"],
                                                                 "subfolder": im.get("subfolder", ""),
                                                                 "type": im.get("type", "output")}, timeout=60)
                    data.raise_for_status()
                    with open(path, "wb") as f:
                        f.write(data.content)
                    return path
        time.sleep(0.5)
    raise RuntimeError("Görsel motoru zamanında yanıt vermedi.")
