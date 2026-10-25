"""Webden bilgi toplama. Her bilgi parçası ("bulgu") ayrı tutulur; kullanıcı araştırma panelinde
istemediklerini çıkarabilir, senaryo yalnızca seçili bulgulardan yazılır ve sayılar bunlarla doğrulanır.

Bulgu: {"id", "kind", "label", "title", "source", "url", "text", "selected",
        isteğe bağlı "image", "series", "latest", "facts"}
"""
import datetime
import re

from . import webdata as W

KINDS = {"wiki": "WIKIPEDIA", "table": "WIKI TABLO", "wikidata": "WIKIDATA", "worldbank": "DÜNYA BANKASI",
         "owid": "OUR WORLD IN DATA", "imf": "IMF", "search": "ARAMA", "web": "WEB SAYFASI"}


def topic_of(prompt):
    return re.sub(r"(?i)\b(hakkında|ile ilgili|bir video|video|yap|oluştur|anlat)\b", "", prompt).strip(" .,") or prompt


def _num(v):
    return f"{v:.4g}" if abs(v) < 1e4 else f"{v:,.0f}"


def _series_text(name, label, unit, pts):
    step = max(1, len(pts) // 30)
    sample = pts[::step] + ([pts[-1]] if pts[::step][-1] != pts[-1] else [])
    return f"{label} ({unit or 'değer'}), {name}: " + ", ".join(f"{y}={_num(v)}" for y, v in sample)


def _latest_text(label, unit, rows):
    return f"{label} ({unit or 'değer'}) son değerler: " + ", ".join(f"{n} ({y})={_num(v)}" for n, y, v in rows)


def _page_text(url, limit=4000):
    try:
        html = W._get(url, timeout=15).text
        html = re.sub(r"(?is)<(script|style|nav|footer|header).*?</\1>", " ", html)
        txt = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", txt)[:limit]
    except Exception:
        return ""


class _Collector:
    def __init__(self):
        self.items = []

    def add(self, kind, title, source, text, url="", **extra):
        if not text:
            return
        self.items.append({"id": f"f{len(self.items) + 1}", "kind": kind, "label": KINDS[kind], "title": title,
                           "source": source, "url": url or "", "text": text, "selected": True, **extra})


def gather(prompt, lang="tr", log=print):
    """Tüm ücretsiz kaynaklardan bulgu listesi döner. Bir kaynak çalışmazsa diğerleri devam eder."""
    c = _Collector()
    topic = topic_of(prompt)
    countries = W.detect_countries(prompt) or (["TUR"] if lang == "tr" else ["WLD"])
    peers = countries if len(countries) > 1 else list(dict.fromkeys(countries + PEERS_FOR(countries[0])))[:8]

    wiki = W.wiki_summary(topic, lang)
    if wiki:
        log(f"  [wikipedia] {wiki['title']}")
        c.add("wiki", wiki["title"], "Wikipedia", wiki["extract"], wiki.get("url"), image=wiki.get("image"))
        for i, df in enumerate(W.wiki_tables(wiki["title"], wiki["lang"], 3)):
            c.add("table", f"{wiki['title']} · tablo {i + 1}", "Wikipedia",
                  df.head(15).to_csv(index=False)[:2500], wiki.get("url"))

    try:
        wd = W.wikidata_facts((wiki or {}).get("title") or topic, lang)
        if wd:
            label, desc, url, facts = wd
            log(f"  [wikidata] {label}: {len(facts)} bilgi")
            lines = [f"{n}: {_num(v) if isinstance(v, float) else v}{' ' + u if u else ''}"
                     f"{f' ({str(t)[:4]})' if t else ''}" for n, v, u, t in facts]
            c.add("wikidata", f"{label} — {desc}" if desc else label, "Wikidata", "\n".join(lines), url, facts=facts)
    except Exception as e:
        log(f"  [wikidata] {e}")

    ind = W.detect_indicator(prompt)
    if ind:
        code, label, unit = ind
        src = "Dünya Bankası"
        try:
            pts, cname = W.worldbank_series(countries[0], code)
            if pts:
                log(f"  [dünya bankası] {label}: {len(pts)} yıl")
                c.add("worldbank", f"{label} · {cname}", src, _series_text(cname, label, unit, pts),
                      f"https://data.worldbank.org/indicator/{code}?locations={countries[0]}",
                      series={"name": cname, "label": label, "unit": unit, "points": pts})
            latest = W.worldbank_latest(peers, code)
            if len(latest) > 2:
                c.add("worldbank", f"{label} · ülke karşılaştırması", src, _latest_text(label, unit, latest),
                      f"https://data.worldbank.org/indicator/{code}",
                      latest={"label": label, "unit": unit, "rows": latest, "highlight": cname if pts else None})
        except Exception as e:
            log(f"  [dünya bankası] {e}")

    for slug, label, unit in W.detect_owid(prompt)[:3]:
        try:
            tab = W.owid_table(slug)
            key = W.OWID_CODES.get(countries[0], countries[0])
            url = f"https://ourworldindata.org/grapher/{slug}"
            if key in tab:
                name, pts = tab[key]
                log(f"  [our world in data] {label}: {len(pts)} yıl")
                c.add("owid", f"{label} · {name}", "Our World in Data", _series_text(name, label, unit, pts), url,
                      series={"name": name, "label": label, "unit": unit, "points": pts})
            rows = [(tab[k][0], *tab[k][1][-1]) for k in (W.OWID_CODES.get(p, p) for p in peers) if k in tab]
            if len(rows) > 2:
                c.add("owid", f"{label} · ülke karşılaştırması", "Our World in Data", _latest_text(label, unit, rows),
                      url, latest={"label": label, "unit": unit, "rows": rows,
                                   "highlight": tab[key][0] if key in tab else None})
        except Exception as e:
            log(f"  [our world in data] {slug}: {e}")

    this_year = datetime.date.today().year
    for code, label, unit in W.detect_imf(prompt)[:2]:
        try:
            data = W.imf_series(code, peers)
            url = f"https://www.imf.org/external/datamapper/{code}"
            if countries[0] in data and data[countries[0]]:
                pts = [(y, v) for y, v in data[countries[0]] if y >= 1990]
                log(f"  [imf] {label}: {len(pts)} yıl")
                name = W.ISO_NAMES.get(countries[0], countries[0])
                c.add("imf", f"{label} · {name}", "IMF",
                      _series_text(name, label, unit, pts) + f". {this_year} sonrası değerler IMF tahminidir.",
                      url, series={"name": name, "label": label, "unit": unit, "points": pts})
            rows = [(W.ISO_NAMES.get(k, k), *max((p for p in v if p[0] <= this_year), default=(0, 0))) for k, v in data.items() if v]
            rows = [r for r in rows if r[1]]
            if len(rows) > 2:
                c.add("imf", f"{label} · ülke karşılaştırması", "IMF", _latest_text(label, unit, rows), url,
                      latest={"label": label, "unit": unit, "rows": rows, "highlight": W.ISO_NAMES.get(countries[0], countries[0])})
        except Exception as e:
            log(f"  [imf] {code}: {e}")

    try:
        from ddgs import DDGS
        hits = DDGS().text(prompt, max_results=8)
        log(f"  [arama] {len(hits)} sonuç")
        for h in hits:
            c.add("search", h.get("title") or h.get("href"), _domain(h.get("href")), h.get("body"), h.get("href"))
        for h in hits[:3]:
            c.add("web", h.get("title") or h["href"], _domain(h["href"]), _page_text(h["href"]), h["href"])
    except Exception as e:
        log(f"  [arama] {e}")
    log(f"Toplam {len(c.items)} bilgi bulundu.")
    return c.items


def _domain(url):
    m = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else (url or "")


def PEERS_FOR(code):
    return W.PEERS if code in W.PEERS else ["WLD", "TUR", "DEU", "USA", "CHN", "IND"]


def selected(findings):
    return [f for f in findings if f.get("selected", True)]


def notes(findings, limit=24000):
    """Yapay zekâya verilecek araştırma notları (yalnızca seçili bulgular)."""
    out = [f"[{f['label']} · {f['title']}]\n{f['text']}" for f in selected(findings)]
    return "\n\n".join(out)[:limit]


def sources(findings):
    seen = []
    for f in selected(findings):
        if f["kind"] == "search":
            continue
        s = f["source"] if f["kind"] not in ("web",) else f"{f['source']}"
        if s not in seen:
            seen.append(s)
    return seen
