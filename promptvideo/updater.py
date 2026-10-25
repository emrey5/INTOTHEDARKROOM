"""GitHub Releases üzerinden güncelleme kontrolü ve kurulumu.

Yeni sürüm yayınlamak: GitHub'da Releases -> "Draft a new release" -> yeni etiket (ör. v0.3.1)
-> "Publish release". GitHub Actions kurulum dosyasını derleyip sürüme ekler; uygulamalar
açılışta bunu görür ve tek tıkla günceller.

Depo gizliyse GitHub API sürümleri ancak bir token ile gösterir: PV_GITHUB_TOKEN ortam değişkeni
ya da uygulama ayarlarındaki "GitHub token" alanı (salt-okunur, yalnızca bu depo için).
"""
import os
import re
import subprocess
import sys
import tempfile

import requests

from . import __version__, UPDATE_REPO

API = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
INSTALLER_SUFFIX = "Kurulum.exe"


def parse_version(v):
    """'v0.3.1' -> (0, 3, 1). Sayı olmayan kısımlar yok sayılır."""
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def is_newer(remote, local=__version__):
    return parse_version(remote) > parse_version(local)


def _headers(token=None, binary=False):
    h = {"Accept": "application/octet-stream" if binary else "application/vnd.github+json",
         "User-Agent": f"PromptVideo/{__version__}"}
    token = token or os.environ.get("PV_GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def check(token=None, timeout=10):
    """En son sürümü sorgular. Daha yeni ve kurulum dosyası hazırsa bilgi sözlüğü, değilse None.

    Hata durumunda istisna fırlatır (ör. depo gizli ve token yok: 404)."""
    r = requests.get(API, headers=_headers(token), timeout=timeout)
    if r.status_code == 404:
        raise PermissionError("Sürüm bulunamadı (depo gizliyse token gerekir ya da henüz sürüm yok)")
    r.raise_for_status()
    rel = r.json()
    tag = rel.get("tag_name", "")
    if not is_newer(tag):
        return None
    asset = next((a for a in rel.get("assets", []) if a["name"].endswith(INSTALLER_SUFFIX)), None)
    return {
        "version": tag.lstrip("v"),
        "notes": rel.get("body") or "",
        "page": rel.get("html_url"),
        "asset_name": asset["name"] if asset else None,
        "asset_api": asset["url"] if asset else None,
        "asset_size": asset["size"] if asset else 0,
    }


def download(info, token=None, progress=None):
    """Kurulum dosyasını geçici klasöre indirir ve yolunu döner."""
    path = os.path.join(tempfile.gettempdir(), info["asset_name"])
    with requests.get(info["asset_api"], headers=_headers(token, binary=True), stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or info.get("asset_size") or 0)
        done = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total)
    return path


def launch_installer(path):
    """Kurulumu başlatır; uygulama hemen ardından kapanmalı (kurulum dosyaları değiştirebilsin)."""
    if sys.platform == "win32":
        subprocess.Popen([path, "/SILENT", "/SP-", "/NOCANCEL", "/RESTARTAPPLICATIONS"], close_fds=True)
    else:
        raise RuntimeError("Otomatik kurulum yalnızca Windows'ta; sürüm sayfasından indirin.")


def can_self_update():
    """Yalnızca kurulum dosyasıyla kurulmuş .exe sürümü kendini güncelleyebilir."""
    return sys.platform == "win32" and getattr(sys, "frozen", False)
