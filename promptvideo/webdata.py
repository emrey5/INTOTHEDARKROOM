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
ISO_NAMES = {"TUR": "Türkiye", "DEU": "Almanya", "FRA": "Fransa", "USA": "ABD", "CHN": "Çin", "JPN": "Japonya",
             "IND": "Hindistan", "RUS": "Rusya", "GBR": "Birleşik Krallık", "ITA": "İtalya", "ESP": "İspanya",
             "BRA": "Brezilya", "GRC": "Yunanistan", "IRN": "İran", "EGY": "Mısır", "KOR": "Güney Kore",
             "CAN": "Kanada", "AZE": "Azerbaycan", "SAU": "Suudi Arabistan", "POL": "Polonya", "NLD": "Hollanda",
             "WLD": "Dünya", "EUU": "Avrupa Birliği"}


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


# --- Our World in Data (hazır grafik verileri, anahtarsız) ------------------

# anahtar kelimeler -> (grafik adı, Türkçe etiket, birim)
OWID = [
    (("yaşam süresi", "ömür", "life expectancy"), "life-expectancy", "Ortalama yaşam süresi", "yıl"),
    (("co2", "karbon", "emisyon", "sera gazı", "iklim"), "co-emissions-per-capita", "Kişi başı CO₂ emisyonu", "ton"),
    (("enerji tüketimi", "enerji kullanımı", "energy use"), "per-capita-energy-use", "Kişi başı enerji tüketimi", "kWh"),
    (("yenilenebilir", "renewable", "güneş enerjisi", "rüzgar enerjisi"), "share-electricity-renewables",
     "Elektrikte yenilenebilir payı", "%"),
    (("elektrik üretimi", "electricity generation"), "electricity-generation", "Elektrik üretimi", "TWh"),
    (("insani gelişme", "hdi", "human development"), "human-development-index", "İnsani Gelişme Endeksi", ""),
    (("çocuk ölüm", "bebek ölüm", "child mortality"), "child-mortality", "Çocuk ölüm oranı", "%"),
    (("doğurganlık", "doğum oranı", "fertility", "çocuk sayısı"), "children-per-woman-un", "Kadın başına çocuk", ""),
    (("internet",), "share-of-individuals-using-the-internet", "İnternet kullanan nüfus", "%"),
    (("obezite", "şişmanlık", "obesity"), "share-of-adults-defined-as-obese", "Obez yetişkin oranı", "%"),
    (("cinayet", "homicide", "suç"), "homicide-rate-unodc", "Cinayet oranı (100 bin kişide)", ""),
    (("mutluluk", "happiness", "mutlu"), "happiness-cantril-ladder", "Mutluluk puanı (0-10)", ""),
    (("medyan yaş", "yaşlanma", "nüfus yaşı", "median age"), "median-age", "Medyan yaş", "yıl"),
    (("kentleşme", "şehirleşme", "kentsel nüfus", "urban"), "share-of-population-urban", "Kentsel nüfus payı", "%"),
    (("askeri harcama", "savunma harcama", "military"), "military-expenditure-share-gdp",
     "Askeri harcama (GSYH'ye oranı)", "%"),
    (("okuryazar", "literacy"), "literacy-rate-adults", "Yetişkin okuryazarlık oranı", "%"),
    (("et tüketimi", "meat"), "meat-supply-per-person", "Kişi başı et tüketimi", "kg"),
    (("alkol", "alcohol"), "total-alcohol-consumption-per-capita-litres-of-pure-alcohol",
     "Kişi başı alkol tüketimi", "litre"),
    (("aşırı yoksul", "yoksulluk", "poverty"), "share-of-population-in-extreme-poverty", "Aşırı yoksulluk oranı", "%"),
    (("orman", "forest"), "forest-area-as-share-of-land-area", "Orman alanı (karaya oranı)", "%"),
    (("sigara", "tütün", "smok"), "share-of-adults-who-smoke", "Sigara içen yetişkin oranı", "%"),
    (("çalışma saati", "working hours"), "annual-working-hours-per-worker", "Yıllık çalışma saati", "saat"),
    (("trafik kaza", "road deaths"), "death-rates-road-incidents", "Trafik kazası ölüm oranı (100 bin kişide)", ""),
    (("intihar", "suicide"), "suicide-death-rates", "İntihar oranı (100 bin kişide)", ""),
]
OWID_CODES = {"WLD": "OWID_WRL"}


def detect_owid(text):
    low = text.lower()
    return [(slug, label, unit) for keys, slug, label, unit in OWID if any(k in low for k in keys)]


def owid_table(slug):
    """Grafiğin tüm verisi: {iso3: (ülke adı, [(yıl, değer)])}."""
    import csv
    import io
    r = _get(f"https://ourworldindata.org/grapher/{slug}.csv",
             params={"v": 1, "csvType": "full", "useColumnShortNames": "false"}, timeout=40)
    rows = csv.reader(io.StringIO(r.text))
    next(rows, None)  # Entity, Code, Year, <değer>
    out = {}
    for row in rows:
        if len(row) < 4 or not row[1] or not row[3]:
            continue
        try:
            v = float(row[3])
        except ValueError:
            continue
        out.setdefault(row[1], (row[0], []))[1].append((int(row[2]), v))
    for _, pts in out.values():
        pts.sort()
    return out


# --- IMF DataMapper (makroekonomi + tahminler, anahtarsız) ------------------

IMF = {
    "büyüme": ("NGDP_RPCH", "Reel GSYH büyümesi", "%"),
    "growth": ("NGDP_RPCH", "Real GDP growth", "%"),
    "enflasyon": ("PCPIPCH", "Enflasyon (TÜFE)", "%"),
    "inflation": ("PCPIPCH", "Inflation", "%"),
    "işsizlik": ("LUR", "İşsizlik oranı", "%"),
    "borç": ("GGXWDG_NGDP", "Kamu borcu (GSYH'ye oranı)", "%"),
    "debt": ("GGXWDG_NGDP", "Government debt (% of GDP)", "%"),
    "cari": ("BCA_NGDPD", "Cari denge (GSYH'ye oranı)", "%"),
    "ekonomi": ("NGDP_RPCH", "Reel GSYH büyümesi", "%"),
}


def detect_imf(text):
    low = text.lower()
    seen, out = set(), []
    for k, v in IMF.items():
        if k in low and v[0] not in seen:
            seen.add(v[0])
            out.append(v)
    return out


def imf_series(code, countries):
    """{iso3: [(yıl, değer)]}; IMF gelecek yıllar için tahmin de verir."""
    r = _get(f"https://www.imf.org/external/datamapper/api/v1/{code}/{'/'.join(countries)}", timeout=30)
    vals = r.json().get("values", {}).get(code, {})
    return {c: sorted((int(y), float(v)) for y, v in d.items() if v is not None) for c, d in vals.items()}


# --- Wikidata (kesin bilgiler: tarih, nüfus, alan, kişi bilgileri) ----------

WD_PROPS = {
    "P1082": ("Nüfus", ""), "P2046": ("Yüzölçümü", "km²"), "P36": ("Başkent", ""), "P571": ("Kuruluş", ""),
    "P35": ("Devlet başkanı", ""), "P6": ("Hükümet başkanı", ""), "P2131": ("GSYH (nominal)", "$"),
    "P2132": ("Kişi başı GSYH", "$"), "P38": ("Para birimi", ""), "P37": ("Resmî dil", ""),
    "P2044": ("Rakım", "m"), "P2048": ("Yükseklik", "m"), "P2043": ("Uzunluk", "km"),
    "P569": ("Doğum tarihi", ""), "P570": ("Ölüm tarihi", ""), "P19": ("Doğum yeri", ""),
    "P27": ("Vatandaşlık", ""), "P106": ("Meslek", ""), "P112": ("Kurucu", ""), "P159": ("Merkez", ""),
    "P1128": ("Çalışan sayısı", ""), "P2139": ("Gelir", "$"), "P17": ("Ülke", ""), "P131": ("Bulunduğu yer", ""),
    "P580": ("Başlangıç", ""), "P582": ("Bitiş", ""), "P585": ("Tarih", ""), "P1120": ("Ölü sayısı", ""),
    "P2250": ("Yaşam beklentisi", "yıl"), "P1198": ("İşsizlik oranı", "%"), "P1279": ("Enflasyon", "%"),
}
WD_API = "https://www.wikidata.org/w/api.php"


def _wd_value(snak):
    dv = (snak or {}).get("datavalue") or {}
    v, t = dv.get("value"), dv.get("type")
    if t == "quantity":
        return float(v["amount"]), None
    if t == "time":
        return v["time"].lstrip("+")[:10].replace("-00", ""), None
    if t == "wikibase-entityid":
        return None, v.get("id")
    if t == "monolingualtext":
        return v.get("text"), None
    if t == "string":
        return v, None
    return None, None


def wikidata_facts(query, lang="tr"):
    """(etiket, açıklama, url, [(özellik adı, değer, birim, tarih)]) ya da None."""
    r = _get(WD_API, params={"action": "wbsearchentities", "search": query, "language": lang,
                             "uselang": lang, "format": "json", "limit": 1})
    hits = r.json().get("search", [])
    if not hits:
        return None
    qid = hits[0]["id"]
    ent = _get(WD_API, params={"action": "wbgetentities", "ids": qid, "props": "claims|labels|descriptions",
                               "languages": f"{lang}|en", "format": "json"}).json()["entities"][qid]
    facts, refs = [], []
    for pid, (name, unit) in WD_PROPS.items():
        claims = ent.get("claims", {}).get(pid, [])
        if not claims:
            continue
        best = [c for c in claims if c.get("rank") == "preferred"] or claims
        c = best[-1]
        val, ref = _wd_value(c.get("mainsnak"))
        when = None
        for q in (c.get("qualifiers") or {}).get("P585", []):
            when, _ = _wd_value(q)
        if val is None and ref is None:
            continue
        facts.append([name, val, unit, when, ref])
        if ref:
            refs.append(ref)
    if refs:  # varlık değerlerinin (başkent, para birimi…) adlarını al
        lab = _get(WD_API, params={"action": "wbgetentities", "ids": "|".join(dict.fromkeys(refs))[:2000],
                                   "props": "labels", "languages": f"{lang}|en", "format": "json"}).json()
        names = {k: (e.get("labels", {}).get(lang) or e.get("labels", {}).get("en") or {}).get("value")
                 for k, e in lab.get("entities", {}).items()}
        for f in facts:
            if f[4]:
                f[1] = names.get(f[4])
    labels, descs = ent.get("labels", {}), ent.get("descriptions", {})
    label = (labels.get(lang) or labels.get("en") or {}).get("value", query)
    desc = (descs.get(lang) or descs.get("en") or {}).get("value", "")
    return label, desc, f"https://www.wikidata.org/wiki/{qid}", [f[:4] for f in facts if f[1] is not None]


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
