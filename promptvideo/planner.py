"""Prompt'u sahne sahne video planına (storyboard JSON) çevirir. Tamamen ücretsizdir.

1) Ücretsiz kaynaklardan araştırma: Wikipedia (özet + tablolar), DuckDuckGo araması,
   Dünya Bankası açık verisi.
2) Bilgisayarınızda çalışan ücretsiz yerel yapay zekâ (Ollama) bu araştırmadan senaryoyu yazar.
   Ollama kurulu değilse kural tabanlı planlayıcı devreye girer.
"""
import json
import os
import re

import requests

from . import webdata as W

OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("PV_MODEL", "qwen3:8b")

SCHEMA = """
{
  "title": "videonun başlığı",
  "language": "tr",
  "scenes": [
    {"type": "title", "title": "...", "subtitle": "...", "narration": "..."},
    {"type": "bullets", "kicker": "kısa üst etiket", "title": "...", "items": ["...", "..."], "narration": "..."},
    {"type": "stat", "kicker": "...", "value": 85.3, "prefix": "", "suffix": " milyon", "decimals": 1, "label": "ne olduğu", "source": "...", "narration": "..."},
    {"type": "bar", "kicker": "...", "title": "...", "unit": "", "data": [{"label": "...", "value": 1.0}], "highlight": "vurgulanacak etiket", "source": "...", "narration": "..."},
    {"type": "line", "kicker": "...", "title": "...", "unit": "", "series": [{"name": "...", "data": [{"x": "2000", "y": 1.0}]}], "source": "...", "narration": "..."},
    {"type": "pie", "kicker": "...", "title": "...", "data": [{"label": "...", "value": 1.0}], "source": "...", "narration": "..."},
    {"type": "table", "kicker": "...", "title": "...", "columns": ["...", "..."], "rows": [["...", "..."]], "source": "...", "narration": "..."},
    {"type": "image", "kicker": "...", "caption": "...", "image_query": "Wikimedia Commons'ta aranacak İngilizce terim", "narration": "..."},
    {"type": "video", "kicker": "...", "caption": "...", "stock_query": "stok video için 1-3 kelimelik İngilizce arama", "narration": "..."},
    {"type": "outro", "title": "...", "sources": ["kaynak adı"], "narration": "..."}
  ]
}
"""

SYSTEM_T = f"""Sen veri odaklı kısa belgesel videoları planlayan bir yapımcısın.
Sana kullanıcının isteği ve webden toplanmış ARAŞTIRMA NOTLARI verilecek. Videoyu sahne sahne planla.

Kurallar:
- {{n_scenes}} sahne. İlk sahne "title", son sahne "outro" olsun.
- Her sahnenin "narration" alanı o sahnede seslendirilecek 1-3 doğal cümledir.
- Grafik, tablo ve sayı sahnelerinde SADECE araştırma notlarındaki sayıları kullan ve "source" yaz.
  Notlarda olmayan sayı uydurma; veri yoksa "bullets", "image" veya "video" sahnesi kullan.
- Sayılar JSON number olsun (ör. 85.3), metin değil.
- Zaman serisi için "line", karşılaştırma için "bar", pay/oran için "pie", çok sütunlu veri için
  "table", tek çarpıcı sayı için "stat". En az bir "image" ve bir "video" sahnesi ekle.
- Kısa yaz: başlıklar en fazla 60 karakter, maddeler en fazla 80 karakter, tablo en fazla 8 satır.
- Metinler kullanıcının dilinde (varsayılan Türkçe); image_query ve stock_query İngilizce.
Yalnızca şu şemaya uyan JSON döndür:
{SCHEMA}"""

# Video süresi seçenekleri: sahne aralığı (yapay zekâ için) ve en fazla sahne (yedek planlayıcı için)
LENGTHS = {"kisa": ("4-5", 5), "orta": ("6-9", 9), "uzun": ("10-14", 14)}


def system_prompt(length="orta"):
    return SYSTEM_T.replace("{n_scenes}", LENGTHS.get(length, LENGTHS["orta"])[0])


def extract_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = m[-1] if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def ollama_available():
    try:
        tags = requests.get(f"{OLLAMA}/api/tags", timeout=3).json()
        names = [m["name"] for m in tags.get("models", [])]
        return MODEL in names or any(n.split(":")[0] == MODEL.split(":")[0] for n in names), names
    except Exception:
        return False, []


def _page_text(url, limit=4000):
    try:
        html = W._get(url, timeout=15).text
        html = re.sub(r"(?is)<(script|style|nav|footer|header).*?</\1>", " ", html)
        txt = re.sub(r"<[^>]+>", " ", html)
        txt = re.sub(r"\s+", " ", txt)
        return txt[:limit]
    except Exception:
        return ""


def research(prompt, lang="tr", log=print):
    """Ücretsiz kaynaklardan araştırma notları (metin) ve kaynak listesi toplar."""
    notes, sources = [], []
    topic = _topic(prompt)
    wiki = W.wiki_summary(topic, lang)
    if wiki:
        log(f"  [wikipedia] {wiki['title']}")
        notes.append(f"WIKIPEDIA ({wiki['title']}): {wiki['extract']}")
        sources.append(f"Wikipedia - {wiki['title']}")
        for i, df in enumerate(W.wiki_tables(wiki["title"], wiki["lang"], 3)):
            notes.append(f"WIKIPEDIA TABLO {i + 1}:\n{df.head(15).to_csv(index=False)[:2500]}")
    try:
        from ddgs import DDGS
        hits = DDGS().text(prompt, max_results=8)
        log(f"  [arama] {len(hits)} sonuç")
        for h in hits:
            notes.append(f"ARAMA: {h.get('title')} ({h.get('href')}): {h.get('body')}")
        for h in hits[:3]:
            txt = _page_text(h["href"])
            if txt:
                notes.append(f"SAYFA {h['href']}:\n{txt}")
                sources.append(h.get("title") or h["href"])
    except Exception as e:
        log(f"  [arama] {e}")
    ind = W.detect_indicator(prompt)
    if ind:
        code, label, unit = ind
        countries = W.detect_countries(prompt) or ["TUR"]
        try:
            pts, cname = W.worldbank_series(countries[0], code)
            if pts:
                notes.append(f"DÜNYA BANKASI {label} ({unit}) {cname}: " +
                             ", ".join(f"{y}={v:.4g}" for y, v in pts[:: max(1, len(pts) // 30)] + [pts[-1]]))
                peers = list(dict.fromkeys(countries + PEERS_FOR(countries[0])))[:8]
                latest = W.worldbank_latest(peers, code)
                notes.append(f"DÜNYA BANKASI {label} son değerler: " +
                             ", ".join(f"{n} ({y})={v:.4g}" for n, y, v in latest))
                sources.append(f"Dünya Bankası - {code}")
                log(f"  [dünya bankası] {label}: {len(pts)} yıl")
        except Exception as e:
            log(f"  [dünya bankası] {e}")
    return "\n\n".join(notes)[:24000], sources


def plan_with_ollama(prompt, lang="tr", log=print, length="orta"):
    notes, sources = research(prompt, lang, log)
    log(f"  [ollama] {MODEL} senaryoyu yazıyor (birkaç dakika sürebilir)…")
    r = requests.post(f"{OLLAMA}/api/chat", timeout=1800, json={
        "model": MODEL, "stream": False, "format": "json", "think": False,
        "options": {"temperature": 0.4, "num_ctx": 16384},
        "messages": [{"role": "system", "content": system_prompt(length)},
                     {"role": "user", "content": f"İSTEK: {prompt}\n\nARAŞTIRMA NOTLARI:\n{notes}"}]})
    r.raise_for_status()
    plan = extract_json(r.json()["message"]["content"])
    plan.setdefault("language", lang)
    for sc in plan.get("scenes", []):
        if sc.get("type") == "outro" and not sc.get("sources"):
            sc["sources"] = sources
    return plan


def _topic(prompt):
    return re.sub(r"(?i)\b(hakkında|ile ilgili|bir video|video|yap|oluştur|anlat)\b", "", prompt).strip(" .,") or prompt


# --- Ücretsiz yedek planlayıcı ----------------------------------------------

def _sentences(text, n):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if len(p) > 20][:n]


def _short(s, n=80):
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def plan_fallback(prompt, lang="tr", log=print):
    scenes, sources = [], []
    topic = _topic(prompt)
    wiki = W.wiki_summary(topic, lang)
    title = (wiki or {}).get("title") or topic[:60]
    sents = _sentences((wiki or {}).get("extract", ""), 5)
    scenes.append({"type": "title", "title": title, "subtitle": _short(sents[0], 110) if sents else "",
                   "narration": sents[0] if sents else title})
    if wiki:
        sources.append(f"Wikipedia - {wiki['url']}")
        if wiki.get("image"):
            scenes.append({"type": "image", "image_url": wiki["image"], "kicker": "Genel bakış",
                           "caption": title, "credit": "Görsel: Wikimedia",
                           "narration": " ".join(sents[1:3]) or title})
        if len(sents) > 3:
            scenes.append({"type": "bullets", "kicker": "Öne çıkanlar", "title": title,
                           "items": [_short(s) for s in sents[1:5]], "narration": " ".join(sents[3:5])})

    ind = W.detect_indicator(prompt)
    countries = W.detect_countries(prompt) or (["TUR"] if lang == "tr" else ["WLD"])
    if ind:
        code, label, unit = ind
        try:
            pts, cname = W.worldbank_series(countries[0], code)
            if pts:
                step = max(1, len(pts) // 25)
                pts_s = pts[::step] + ([pts[-1]] if pts[::step][-1] != pts[-1] else [])
                src = "Dünya Bankası (World Bank Open Data)"
                sources.append(f"{src} - {code}")
                y0, v0 = pts[0]
                y1, v1 = pts[-1]
                scenes.append({"type": "line", "kicker": cname, "title": f"{label} ({y0}-{y1})",
                               "unit": unit, "series": [{"name": cname, "data": [{"x": str(y), "y": v} for y, v in pts_s]}],
                               "source": src,
                               "narration": f"{cname} için {label.lower()} {y0} yılında {_fmt(v0, unit)} iken {y1} yılında {_fmt(v1, unit)} oldu."})
                scenes.append({"type": "stat", "kicker": f"{cname} · {y1}", "value": v1, "suffix": f" {unit}" if unit and unit != "$" else "",
                               "prefix": "$" if unit == "$" else "", "label": label, "source": src,
                               "narration": f"En güncel veriye göre {label.lower()} {_fmt(v1, unit)}."})
                peers = countries if len(countries) > 1 else list(dict.fromkeys(countries + PEERS_FOR(countries[0])))
                latest = W.worldbank_latest(peers[:8], code)
                if len(latest) > 2:
                    scenes.append({"type": "bar", "kicker": "Karşılaştırma", "title": f"{label}: ülkeler",
                                   "unit": unit if unit != "$" else "$", "highlight": cname,
                                   "data": [{"label": n, "value": v} for n, _, v in latest], "source": src,
                                   "narration": f"Diğer ülkelerle karşılaştırıldığında tablo böyle görünüyor."})
                    scenes.append({"type": "table", "kicker": "Veri tablosu", "title": label,
                                   "columns": ["Ülke", "Yıl", label],
                                   "rows": [[n, str(y), _fmt(v, unit)] for n, y, v in sorted(latest, key=lambda r: -r[2])],
                                   "source": src, "narration": "Ayrıntılı rakamlar tabloda."})
        except Exception as e:
            log(f"  [worldbank] {e}")

    scenes.insert(1, {"type": "video", "stock_query": title, "caption": title, "kicker": "",
                      "narration": sents[1] if len(sents) > 1 else ""})
    scenes.append({"type": "outro", "title": "İzlediğiniz için teşekkürler", "sources": sources,
                   "narration": "Kaynaklar ekranda. İzlediğiniz için teşekkürler."})
    return {"title": title, "language": lang, "scenes": scenes}


def PEERS_FOR(code):
    return W.PEERS if code in W.PEERS else ["WLD", "TUR", "DEU", "USA", "CHN", "IND"]


def _fmt(v, unit):
    from .theme import fmt_num
    s = fmt_num(v)
    if unit == "$":
        return "$" + s
    if unit == "%":
        return "%" + s
    return f"{s} {unit}".strip()


def make_plan(prompt, lang="tr", log=print, length="orta"):
    ok, names = ollama_available()
    if ok:
        log(f"Yerel yapay zekâ ({MODEL}) ile araştırma + senaryo…")
        try:
            plan = plan_with_ollama(prompt, lang, log, length)
            if plan.get("scenes"):
                return plan
        except Exception as e:
            log(f"  Ollama planlaması başarısız ({e}); kural tabanlı planlayıcıya geçiliyor")
    else:
        log(f"Ollama'da {MODEL} bulunamadı (kurulu modeller: {names or 'yok'}). "
            f"Kural tabanlı planlayıcı kullanılıyor. Daha iyi senaryo için: ollama pull {MODEL}")
    return trim_plan(plan_fallback(prompt, lang, log), length)


def trim_plan(plan, length="orta"):
    """Yedek planı seçilen süreye sığdırır: başlık ve kapanış kalır, aradakiler kısalır."""
    sc, mx = plan["scenes"], LENGTHS.get(length, LENGTHS["orta"])[1]
    if len(sc) > mx:
        plan["scenes"] = sc[:mx - 1] + [sc[-1]]
    return plan
