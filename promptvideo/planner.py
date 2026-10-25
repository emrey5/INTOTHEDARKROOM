"""Prompt'u sahne sahne video planına (storyboard JSON) çevirir. Tamamen ücretsizdir.

1) Ücretsiz kaynaklardan araştırma (research.py): Wikipedia, Wikidata, Dünya Bankası,
   Our World in Data, IMF ve web araması.
2) Bilgisayarınızda çalışan ücretsiz yerel yapay zekâ (Ollama) bu araştırmadan senaryoyu yazar.
   Ollama kurulu değilse kural tabanlı planlayıcı devreye girer.
"""
import json
import os
import re

import requests

from . import research as R

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
    {"type": "character", "kicker": "...", "backdrop": "studio", "characters": [{"look": 0, "pose": "talk", "emotion": "happy", "voice": "erkek ya da kadın"}], "say": [{"who": 0, "text": "karakterin söylediği kısa cümle"}], "narration": "..."},
    {"type": "versus", "kicker": "...", "backdrop": "studio", "title": "...", "left": {"label": "...", "value": 1.0}, "right": {"label": "...", "value": 2.0}, "unit": "", "higher_is_better": true, "source": "...", "narration": "..."},
    {"type": "people", "kicker": "...", "title": "...", "value": 30, "total": 100, "label": "Her 100 kişiden 30'u ...", "source": "...", "narration": "..."},
    {"type": "timeline", "kicker": "...", "title": "...", "events": [{"year": "1923", "text": "kısa olay"}], "source": "...", "narration": "..."},
    {"type": "compare", "kicker": "...", "title": "...", "unit": "", "higher_is_better": true, "before": {"label": "2000", "value": 1.0, "text": "kısa not"}, "after": {"label": "2024", "value": 2.0, "text": "kısa not"}, "source": "...", "narration": "..."},
    {"type": "map", "map": "world ya da turkey", "kicker": "...", "title": "...", "unit": "", "data": [{"label": "ülke ya da il adı", "value": 1.0}], "presenter": true, "source": "...", "narration": "..."},
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
- Notlardaki her bilgi "[KAYNAK · başlık]" ile başlar; "source" alanına o kaynağın adını yaz
  (ör. "Dünya Bankası", "Our World in Data", "IMF", "Wikidata"). Sayılar sonradan notlarla karşılaştırılır.
- Sayılar JSON number olsun (ör. 85.3), metin değil.
- Zaman serisi için "line", karşılaştırma için "bar", pay/oran için "pie", çok sütunlu veri için
  "table", tek çarpıcı sayı için "stat". En az bir "image" ve bir "video" sahnesi ekle.
- Videoyu canlı tut: 1-2 "character" sahnesi ekle (çizgi karakterler konuşur; "say" balonda görünür,
  1-2 kısa cümle; iki karakter soru-cevap yapabilir). look 0-5 farklı karakterlerdir; pose: talk, point,
  present, wave, cheer, shrug, think; emotion: happy, neutral, surprised, sad, angry, worried.
  Her karakter kendi sesiyle konuşur (look 1 ve 3 varsayılan olarak kadın, diğerleri erkek sesi).
  "backdrop" konuya uygun mekân: studio, city, office, space, lab, nature.
  İki şeyi kıyaslarken "versus", bir oranı (yüzde) anlatırken "people" kullan.
- Ülkelere ya da Türkiye'nin illerine göre veri varsa "map" sahnesi kullan (map: "world" ya da "turkey";
  label olarak Türkçe ülke/il adı yaz). "presenter": true ise köşede haritayı gösteren bir karakter durur.
- Tarihsel gelişmeleri "timeline" ile anlat (3-6 olay, yıl sırasıyla, her olay en fazla 50 karakter).
  Bir şeyin eskiden ve şimdi nasıl olduğunu "compare" (önce/sonra) ile göster.
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


def plan_with_ollama(prompt, findings, lang="tr", log=print, length="orta"):
    log(f"  [ollama] {MODEL} senaryoyu yazıyor (birkaç dakika sürebilir)…")
    r = requests.post(f"{OLLAMA}/api/chat", timeout=1800, json={
        "model": MODEL, "stream": False, "format": "json", "think": False,
        "options": {"temperature": 0.4, "num_ctx": 16384},
        "messages": [{"role": "system", "content": system_prompt(length)},
                     {"role": "user", "content": f"İSTEK: {prompt}\n\nARAŞTIRMA NOTLARI:\n{R.notes(findings)}"}]})
    r.raise_for_status()
    plan = extract_json(r.json()["message"]["content"])
    plan.setdefault("language", lang)
    for sc in plan.get("scenes", []):
        if sc.get("type") == "outro" and not sc.get("sources"):
            sc["sources"] = R.sources(findings)
    return plan


# --- Ücretsiz yedek planlayıcı ----------------------------------------------

def _sentences(text, n):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if len(p) > 20][:n]


def _short(s, n=80):
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


BACKDROP_WORDS = {"space": ("uzay", "gezegen", "astronomi", "yıldız", "ay ", "mars", "nasa", "roket"),
                  "lab": ("bilim", "sağlık", "ilaç", "hastalık", "virüs", "kimya", "deney", "obezite", "kanser"),
                  "office": ("ekonomi", "şirket", "iş ", "enflasyon", "gsyh", "borsa", "maaş", "işsizlik", "borç"),
                  "city": ("şehir", "nüfus", "kent", "trafik", "konut", "ülke"),
                  "nature": ("doğa", "iklim", "orman", "hayvan", "co2", "karbon", "enerji", "su ", "kahve", "tarım")}


_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})(?:['’]?(?:te|ta|de|da|den|dan|e|a)\b)?"
                   r"(?:\s+(?:yılında|yılı|yılından|itibarıyla|itibariyle|yılına kadar)\b)?", re.I)


def year_events(text, n=6):
    """Metindeki yıllı cümlelerden zaman çizelgesi olayları çıkarır (yıl sırasıyla)."""
    out, seen = [], set()
    for sent in re.split(r"(?<=[.!?])\s+", text or ""):
        m = _YEAR.search(sent)
        if not m or m.group(1) in seen or len(sent) < 25:
            continue
        rest = (sent[:m.start()] + sent[m.end():]).strip(" ,.;:-'’")
        rest = re.sub(r"\s+", " ", rest)
        if len(rest) < 12:
            continue
        seen.add(m.group(1))
        out.append({"year": m.group(1), "text": _short(("İ" if rest[0] == "i" else rest[0].upper()) + rest[1:], 50)})
    out.sort(key=lambda e: int(e["year"]))
    if len(out) > n:  # baştan sona yayılan n olay seç
        idx = sorted({round(i * (len(out) - 1) / (n - 1)) for i in range(n)})
        out = [out[i] for i in idx]
    return out


def pick_backdrop(text):
    low = f" {text.lower()} "
    for name, words in BACKDROP_WORDS.items():
        if any(w in low for w in words):
            return name
    return "studio"


def plan_fallback(prompt, findings, lang="tr", log=print):
    """Yapay zekâ yokken seçili bulgulardan basit ama veriye dayalı bir senaryo kurar."""
    sel = R.selected(findings)
    scenes = []
    wiki = next((f for f in sel if f["kind"] == "wiki"), None)
    title = wiki["title"] if wiki else R.topic_of(prompt)[:60]
    if not wiki:  # Vikipedi yoksa kullanıcının kendi metni anlatının temeli olur
        wiki = next((f for f in sel if f["kind"] == "user" and len(f["text"]) > 200
                     and not (f.get("series") or f.get("latest"))), None)
    sents = _sentences(wiki["text"], 5) if wiki else []
    scenes.append({"type": "title", "title": title, "subtitle": _short(sents[0], 110) if sents else "",
                   "narration": sents[0] if sents else title})
    scenes.append({"type": "character", "kicker": "Anlatıcı", "backdrop": pick_backdrop(prompt),
                   "characters": [{"look": 0, "pose": "wave"}],
                   "say": [{"who": 0, "text": f"Merhaba! Bugün {title} konusuna birlikte bakıyoruz."}],
                   "narration": f"Merhaba! Bugün {title} konusuna birlikte bakıyoruz."})
    scenes.append({"type": "video", "stock_query": title, "caption": title, "kicker": "",
                   "narration": sents[1] if len(sents) > 1 else ""})
    if wiki and wiki.get("image"):
        scenes.append({"type": "image", "image_url": wiki["image"], "kicker": "Genel bakış", "caption": title,
                       "credit": "Görsel: Wikimedia", "narration": " ".join(sents[2:4]) or title})
    if len(sents) > 3:
        scenes.append({"type": "bullets", "kicker": "Öne çıkanlar", "title": title,
                       "items": [_short(x) for x in sents[1:5]], "narration": " ".join(sents[3:5])})
    evs = year_events(wiki["text"]) if wiki else []
    if len(evs) >= 3:
        scenes.append({"type": "timeline", "kicker": "Zaman çizelgesi", "title": title, "events": evs,
                       "source": wiki.get("source", "Vikipedi"),
                       "narration": " ".join(f"{e['year']}: {e['text'].rstrip('…')}." for e in evs[:3])})
    wd = next((f for f in sel if f["kind"] == "wikidata" and f.get("facts")), None)
    if wd:
        items = [f"{n}: {_fmt(v, u) if isinstance(v, float) else f'{v} {u}'.strip()}" for n, v, u, _ in wd["facts"][:5]]
        scenes.append({"type": "bullets", "kicker": "Kısa bilgiler", "title": title, "items": items,
                       "source": "Wikidata", "narration": ". ".join(items[:3]) + "."})

    for f in sel:
        se = f.get("series")
        if se and len(se["points"]) > 1:
            pts, unit, label, name = se["points"], se["unit"], se["label"], se["name"]
            step = max(1, len(pts) // 25)
            pts_s = pts[::step] + ([pts[-1]] if pts[::step][-1] != pts[-1] else [])
            (y0, v0), (y1, v1) = pts[0], pts[-1]
            scenes.append({"type": "line", "kicker": name, "title": f"{label} ({y0}-{y1})", "unit": unit,
                           "series": [{"name": name, "data": [{"x": str(y), "y": v} for y, v in pts_s]}],
                           "source": f["source"],
                           "narration": f"{name} için {label.lower()} {y0} yılında {_fmt(v0, unit)} iken "
                                        f"{y1} yılında {_fmt(v1, unit)} oldu."})
            scenes.append({"type": "stat", "kicker": f"{name} · {y1}", "value": v1,
                           "suffix": f" {unit}" if unit and unit != "$" else "", "prefix": "$" if unit == "$" else "",
                           "label": label, "source": f["source"],
                           "narration": f"En güncel veriye göre {label.lower()} {_fmt(v1, unit)}."})
            if v0 and abs(v1 - v0) / abs(v0) > 0.05:
                scenes.append({"type": "compare", "kicker": f"{name} · önce / sonra", "title": label, "unit": unit,
                               "before": {"label": str(y0), "value": v0}, "after": {"label": str(y1), "value": v1},
                               "source": f["source"],
                               "narration": f"{y0} ile {y1} arasında {label.lower()} {_fmt(v0, unit)} "
                                            f"düzeyinden {_fmt(v1, unit)} düzeyine geldi."})
            if unit == "%" and 0 < v1 <= 100 and f["kind"] != "user":  # kendi verinde oran kişi sayısı olmayabilir
                scenes.append({"type": "people", "kicker": name, "title": label, "value": round(v1, 1), "total": 100,
                               "label": f"Her 100 kişiden yaklaşık {round(v1)} tanesi.", "source": f["source"],
                               "narration": f"Yani her 100 kişiden yaklaşık {round(v1)} tanesi."})
        wm = f.get("world")
        if wm:
            top = max(wm["rows"], key=lambda r: r[2])
            mk = wm.get("map", "world")
            scenes.append({"type": "map", "map": mk, "kicker": "Türkiye" if mk == "turkey" else "Dünya",
                           "title": wm["label"], "unit": wm["unit"],
                           "data": [{"label": n, "value": v} for n, _, v in wm["rows"]], "presenter": True,
                           "source": f["source"],
                           "narration": f"Haritada {wm['label'].lower()} en yüksek {top[0]}: "
                                        f"{_fmt(top[2], wm['unit'])}."})
        la = f.get("latest")
        if la and len(la["rows"]) > 2:
            rows, unit, label = la["rows"], la["unit"], la["label"]
            hi = next((r for r in rows if r[0] == la.get("highlight")), None)
            other = max((r for r in rows if r is not hi), key=lambda r: r[2], default=None)
            if hi and other:
                scenes.append({"type": "versus", "kicker": "Karşılaştırma", "title": label, "unit": unit,
                               "left": {"label": hi[0], "value": hi[2]}, "right": {"label": other[0], "value": other[2]},
                               "source": f["source"],
                               "narration": f"{hi[0]}: {_fmt(hi[2], unit)}. {other[0]}: {_fmt(other[2], unit)}."})
            scenes.append({"type": "bar", "kicker": "Karşılaştırma", "title": label if la.get("name_col") else f"{label}: ülkeler", "unit": unit,
                           "highlight": la.get("highlight"), "source": f["source"],
                           "data": [{"label": n, "value": v} for n, _, v in rows],
                           "narration": "Diğer ülkelerle karşılaştırıldığında tablo böyle görünüyor."})
            scenes.append({"type": "table", "kicker": "Veri tablosu", "title": label, "source": f["source"],
                           "columns": [la.get("name_col", "Ülke")] + (["Yıl"] if rows[0][1] else []) + [label],
                           "rows": [[n] + ([str(y)] if y else []) + [_fmt(v, unit)]
                                    for n, y, v in sorted(rows, key=lambda r: -r[2])][:8],
                           "narration": "Ayrıntılı rakamlar tabloda."})
    scenes.append({"type": "outro", "title": "İzlediğiniz için teşekkürler", "sources": R.sources(findings),
                   "narration": "Kaynaklar ekranda. İzlediğiniz için teşekkürler."})
    return {"title": title, "language": lang, "scenes": scenes}


def _fmt(v, unit):
    from .theme import fmt_num
    s = fmt_num(v)
    if unit == "$":
        return "$" + s
    if unit == "%":
        return "%" + s
    return f"{s} {unit}".strip()


def make_plan(prompt, lang="tr", log=print, length="orta", findings=None):
    """Senaryoyu yazar. findings verilmezse önce araştırma yapılır."""
    if findings is None:
        findings = R.gather(prompt, lang, log)
    ok, names = ollama_available()
    if ok:
        log(f"Yerel yapay zekâ ({MODEL}) senaryoyu yazıyor…")
        try:
            plan = plan_with_ollama(prompt, findings, lang, log, length)
            if plan.get("scenes"):
                return plan
        except Exception as e:
            log(f"  Ollama planlaması başarısız ({e}); kural tabanlı planlayıcıya geçiliyor")
    else:
        log(f"Ollama'da {MODEL} bulunamadı (kurulu modeller: {names or 'yok'}). "
            f"Kural tabanlı planlayıcı kullanılıyor. Daha iyi senaryo için: ollama pull {MODEL}")
    return trim_plan(plan_fallback(prompt, findings, lang, log), length)


def trim_plan(plan, length="orta"):
    """Yedek planı seçilen süreye sığdırır: başlık ve kapanış kalır, aradakiler kısalır."""
    sc, mx = plan["scenes"], LENGTHS.get(length, LENGTHS["orta"])[1]
    if len(sc) > mx:
        prio = {"title": 0, "outro": 0, "character": 1, "line": 1, "map": 2, "stat": 2, "versus": 2, "timeline": 2,
                "compare": 3, "bar": 3, "people": 3,
                "bullets": 4, "image": 5, "video": 6}
        keep = sorted(sorted(range(len(sc)), key=lambda i: (prio.get(sc[i]["type"], 7), i))[:mx])
        plan["scenes"] = [sc[i] for i in keep]
    return plan
