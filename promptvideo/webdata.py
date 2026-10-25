"""Anahtar gerektirmeyen web veri kaynakları + isteğe bağlı Pexels stok video/görsel."""
import os
import re
import urllib.parse

import requests

UA = {"User-Agent": "DARKROOM/0.3 (https://github.com/emrey5/INTOTHEDARKROOM)"}
S = requests.Session()
S.headers.update(UA)


def _get(url, **kw):
    r = S.get(url, timeout=kw.pop("timeout", 20), **kw)
    r.raise_for_status()
    return r


# --- Wikipedia ---------------------------------------------------------------

def wiki_search(query, lang="tr"):
    r = _get(f"https://{lang}.wikipedia.org/w/api.php",
             params={"action": "query", "list": "search", "srsearch": query, "format": "json",
                     "srlimit": 1})
    hits = r.json().get("query", {}).get("search", [])
    return hits[0]["title"] if hits else None


def wiki_summary(query, lang="tr"):
    """{'title','extract','image','url'} veya None."""
    for lg in (lang, "en") if lang != "en" else ("en",):
        try:
            title = wiki_search(query, lg)
            if not title:
                continue
            r = _get(f"https://{lg}.wikipedia.org/api/rest_v1/page/summary/" +
                     urllib.parse.quote(title.replace(" ", "_")))
            j = r.json()
            img = (j.get("originalimage") or j.get("thumbnail") or {}).get("source")
            return {"title": j.get("title"), "extract": j.get("extract", ""), "image": img,
                    "url": j.get("content_urls", {}).get("desktop", {}).get("page"), "lang": lg}
        except Exception as e:
            print(f"  [wiki] {lg}: {e}")
    return None


def wiki_tables(title, lang="tr", limit=3):
    """Makaledeki 'wikitable' tablolarını pandas DataFrame listesi olarak döner."""
    try:
        import pandas as pd
        from io import StringIO
        html = _get(f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))).text
        return pd.read_html(StringIO(html), attrs={"class": "wikitable"})[:limit]
    except Exception as e:
        print(f"  [wiki] tablo alınamadı: {e}")
        return []


# --- Dünya Bankası (ülke istatistikleri, anahtarsız) ------------------------

INDICATORS = {
    "nüfus": ("SP.POP.TOTL", "Nüfus", ""),
    "population": ("SP.POP.TOTL", "Population", ""),
    "gsyh": ("NY.GDP.MKTP.CD", "GSYH", "$"),
    "gdp": ("NY.GDP.MKTP.CD", "GDP", "$"),
    "milli gelir": ("NY.GDP.PCAP.CD", "Kişi başı GSYH", "$"),
    "kişi başı": ("NY.GDP.PCAP.CD", "Kişi başı GSYH", "$"),
    "enflasyon": ("FP.CPI.TOTL.ZG", "Enflasyon", "%"),
    "inflation": ("FP.CPI.TOTL.ZG", "Inflation", "%"),
    "işsizlik": ("SL.UEM.TOTL.ZS", "İşsizlik oranı", "%"),
    "unemployment": ("SL.UEM.TOTL.ZS", "Unemployment", "%"),
    "yaşam süresi": ("SP.DYN.LE00.IN", "Ortalama yaşam süresi", "yıl"),
    "co2": ("EN.GHG.CO2.MT.CE.AR5", "CO2 emisyonu", "Mt"),
    "karbon": ("EN.GHG.CO2.MT.CE.AR5", "CO2 emisyonu", "Mt"),
    "internet": ("IT.NET.USER.ZS", "İnternet kullanıcıları", "%"),
    "ihracat": ("NE.EXP.GNFS.CD", "İhracat", "$"),
    "export": ("NE.EXP.GNFS.CD", "Exports", "$"),
}

COUNTRIES = {
    "türkiye": "TUR", "turkey": "TUR", "almanya": "DEU", "germany": "DEU", "fransa": "FRA",
    "france": "FRA", "abd": "USA", "amerika": "USA", "usa": "USA", "çin": "CHN", "china": "CHN",
    "japonya": "JPN", "japan": "JPN", "hindistan": "IND", "india": "IND", "rusya": "RUS",
    "russia": "RUS", "ingiltere": "GBR", "birleşik krallık": "GBR", "uk": "GBR", "italya": "ITA",
    "italy": "ITA", "ispanya": "ESP", "spain": "ESP", "brezilya": "BRA", "brazil": "BRA",
    "yunanistan": "GRC", "greece": "GRC", "iran": "IRN", "mısır": "EGY", "egypt": "EGY",
    "güney kore": "KOR", "kore": "KOR", "korea": "KOR", "kanada": "CAN", "canada": "CAN",
    "azerbaycan": "AZE", "suudi arabistan": "SAU", "polonya": "POL", "hollanda": "NLD",
    "dünya": "WLD", "world": "WLD", "avrupa birliği": "EUU", "ab": "EUU",
}

PEERS = ["TUR", "DEU", "FRA", "GBR", "ITA", "ESP", "POL", "GRC"]


def detect_indicator(text):
    low = text.lower()
    for k, v in INDICATORS.items():
        if k in low:
            return v
    return None


def detect_countries(text):
    low = " " + text.lower() + " "
    found = []
    for k, code in sorted(COUNTRIES.items(), key=lambda kv: -len(kv[0])):
        if re.search(r"(?<![a-zçğıöşü])" + re.escape(k), low) and code not in found:
            found.append(code)
    return found


def worldbank_series(country, indicator, start=1960, end=2025):
    """[(yıl, değer)] artan sırada, boş değerler atlanır."""
    r = _get(f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}",
             params={"format": "json", "date": f"{start}:{end}", "per_page": 200})
    j = r.json()
    if len(j) < 2 or not j[1]:
        return [], None
    name = j[1][0]["country"]["value"]
    pts = sorted((int(d["date"]), d["value"]) for d in j[1] if d["value"] is not None)
    return pts, name


def worldbank_latest(countries, indicator):
    """Ülkelerin en güncel değerleri: [(ülke adı, yıl, değer)]."""
    r = _get(f"https://api.worldbank.org/v2/country/{';'.join(countries)}/indicator/{indicator}",
             params={"format": "json", "mrnev": 1, "per_page": 100})
    j = r.json()
    if len(j) < 2 or not j[1]:
        return []
    return [(d["country"]["value"], int(d["date"]), d["value"]) for d in j[1] if d["value"] is not None]


# --- Medya indirme ----------------------------------------------------------

def download(url, path):
    r = S.get(url, timeout=60, stream=True)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    return path


def commons_image(query):
    """Wikimedia Commons'ta arama yapıp ilk uygun görselin URL'sini döner."""
    try:
        r = _get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
            "gsrnamespace": 6, "gsrlimit": 5, "prop": "imageinfo", "iiprop": "url|size",
            "iiurlwidth": 2400, "format": "json"})
        pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
        for p in pages:
            ii = (p.get("imageinfo") or [{}])[0]
            if ii.get("width", 0) >= 1000:
                return ii.get("thumburl") or ii.get("url")
    except Exception as e:
        print(f"  [commons] {e}")
    return None


def commons_video(query, max_mb=150):
    """Wikimedia Commons'tan anahtarsız, özgür lisanslı video (webm/ogv) URL'si."""
    try:
        r = _get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "generator": "search", "gsrsearch": f"filetype:video {query}",
            "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|size|mime",
            "format": "json"})
        pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
        for p in pages:
            ii = (p.get("imageinfo") or [{}])[0]
            if ii.get("width", 0) >= 1280 and ii.get("size", 0) < max_mb * 1e6 and ii.get("duration", 99) >= 4:
                return ii["url"], "Video: Wikimedia Commons"
    except Exception as e:
        print(f"  [commons] {e}")
    return None, None


def pexels_video(query, min_dur=4):
    """Pexels'ten yatay HD stok video URL'si (PEXELS_API_KEY gerekir, ücretsiz)."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None, None
    r = S.get("https://api.pexels.com/videos/search", headers={"Authorization": key},
              params={"query": query, "orientation": "landscape", "size": "medium", "per_page": 8},
              timeout=20)
    r.raise_for_status()
    for v in r.json().get("videos", []):
        if v.get("duration", 0) < min_dur:
            continue
        files = sorted((f for f in v["video_files"] if f.get("width") and f["width"] >= 1280),
                       key=lambda f: abs(f["width"] - 1920))
        if files:
            return files[0]["link"], f"Video: {v['user']['name']} / Pexels"
    return None, None


def pexels_photo(query):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None, None
    r = S.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
              params={"query": query, "orientation": "landscape", "per_page": 3}, timeout=20)
    r.raise_for_status()
    ph = r.json().get("photos", [])
    if ph:
        return ph[0]["src"]["large2x"], f"Foto: {ph[0]['photographer']} / Pexels"
    return None, None
