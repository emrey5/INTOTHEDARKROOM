"""Kullanıcının kendi kaynakları: PDF, Excel/CSV, metin dosyası ya da web adresi bulguya dönüşür.

Tablolar otomatik okunur: yıl sütunu varsa zaman serisi (çizgi grafik), ad + sayı sütunları varsa
karşılaştırma (çubuk grafik ve tablo); adlar ülke ya da Türkiye ili ise harita da çizilebilir.
"""
import io
import os
import re

import pandas as pd

from . import webdata as W

LABEL = "SENİN KAYNAĞIN"
TEXT_LIMIT = 12000


def _finding(title, source, text, url="", **extra):
    return {"id": "", "kind": "user", "label": LABEL, "title": title, "source": source, "url": url,
            "text": text, "selected": True, **extra}


def _unit_of(name):
    low = str(name).lower()
    if "%" in low or "yüzde" in low or "oran" in low:
        return "%"
    if "$" in low or "usd" in low or "dolar" in low:
        return "$"
    if "₺" in low or re.search(r"\btl\b", low):
        return "TL"
    if "€" in low or "euro" in low:
        return "€"
    return ""


def _to_num(x):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return None if pd.isna(x) else float(x)
    s = re.sub(r"[^\d,.\-]", "", str(x))
    if not s or not re.search(r"\d", s):
        return None
    if "," in s and "." in s:  # 1.234,5 ya da 1,234.5
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) != 3 else s.replace(",", "")
    elif s.count(".") > 1 or (len(s.split(".")[-1]) == 3 and len(s) > 4):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _numeric_cols(df):
    out = []
    for c in df.columns:
        vals = df[c].map(_to_num)
        if vals.notna().mean() >= 0.7:
            out.append((c, vals))
    return out


def _is_year(vals):
    v = vals.dropna()
    return len(v) >= 2 and ((v % 1) == 0).all() and v.between(1500, 2100).all()


def _map_kind(names):
    """Adların çoğu Türkiye ili ya da ülke ise harita türünü döner."""
    from .scenes import _load_map, _match
    names = [n for n in names if n]
    if len(names) < 5:
        return None
    for kind in ("turkey", "world"):
        m = _load_map(kind)
        if sum(1 for n in names if _match(m, n)) >= 0.7 * len(names):
            return kind
    return None


def table_findings(df, title, source, url=""):
    """Bir tablodan grafik yapılabilecek bulgular çıkarır."""
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty or len(df.columns) < 2:
        return []
    preview = df.head(40).to_csv(index=False, sep=";")
    nums = _numeric_cols(df)
    year = next(((c, v) for c, v in nums if _is_year(v) or str(c).lower() in ("yıl", "year", "yil")), None)
    values = [(c, v) for c, v in nums if not year or c != year[0]]
    text_cols = [c for c in df.columns if c not in {c2 for c2, _ in nums}]
    out = []
    if year and values:
        for c, v in values[:3]:
            pts = sorted((int(y), float(x)) for y, x in zip(year[1], v) if pd.notna(y) and pd.notna(x))
            if text_cols:  # uzun biçim (ad, yıl, değer): ilk adın serisini al
                first = df[text_cols[0]].iloc[0]
                mask = df[text_cols[0]] == first
                pts = sorted((int(y), float(x)) for y, x, m in zip(year[1], v, mask) if m and pd.notna(y) and pd.notna(x))
                name = str(first)
            else:
                name = title
            pts = list(dict(pts).items())
            if len(pts) >= 2:
                out.append(_finding(f"{title}: {c}", source, preview, url,
                                    series={"name": name, "label": c, "unit": _unit_of(c), "points": pts}))
    elif text_cols and values:
        names = df[text_cols[0]].astype(str).str.strip()
        for c, v in values[:2]:
            rows = [(n, "", float(x)) for n, x in zip(names, v) if pd.notna(x) and n and n != "nan"]
            if len(rows) < 2:
                continue
            extra = {"latest": {"label": c, "unit": _unit_of(c), "rows": rows[:12], "highlight": None,
                                "name_col": text_cols[0]}}
            kind = _map_kind([r[0] for r in rows])
            if kind:
                extra["world"] = {"label": c, "unit": _unit_of(c), "rows": rows, "map": kind}
            out.append(_finding(f"{title}: {c}", source, preview, url, **extra))
    if not out:
        out.append(_finding(title, source, preview, url))
    return out


def _pdf_text(data):
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(data))
    parts = []
    for page in r.pages[:40]:
        parts.append(page.extract_text() or "")
        if sum(map(len, parts)) > TEXT_LIMIT:
            break
    txt = re.sub(r"[ \t]+", " ", "\n".join(parts))
    return re.sub(r"\n{2,}", "\n", txt).strip()[:TEXT_LIMIT]


def from_file(path):
    """Yerel dosyadan bulgular. Desteklenen: .pdf, .xlsx/.xls, .csv, .txt/.md"""
    name = os.path.basename(path)
    title = os.path.splitext(name)[0]
    ext = os.path.splitext(name)[1].lower()
    source = f"{name} (kendi dosyan)"
    if ext == ".pdf":
        with open(path, "rb") as f:
            txt = _pdf_text(f.read())
        if not txt:
            raise ValueError("PDF'te okunabilir metin yok (taranmış resim olabilir).")
        return [_finding(title, source, txt)]
    if ext in (".xlsx", ".xlsm", ".xls"):
        out = []
        for sheet, df in pd.read_excel(path, sheet_name=None).items():
            out += table_findings(df, title if len(out) == 0 and sheet.lower().startswith(("sheet", "sayfa"))
                                  else f"{title} · {sheet}", source)
        return out
    if ext in (".csv", ".tsv"):
        df = pd.read_csv(path, sep=None, engine="python", encoding_errors="replace")
        return table_findings(df, title, source)
    with open(path, encoding="utf-8", errors="replace") as f:
        return [_finding(title, source, f.read()[:TEXT_LIMIT])]


def from_url(url):
    """Web adresinden bulgular: sayfa metni ve içindeki sayısal tablolar (PDF/CSV bağlantıları da olur)."""
    if not re.match(r"https?://", url):
        url = "https://" + url
    r = W._get(url, timeout=30)
    ctype = r.headers.get("content-type", "").lower()
    host = re.sub(r"^www\.", "", url.split("/")[2])
    if "pdf" in ctype or url.lower().endswith(".pdf"):
        return [_finding(url.rsplit("/", 1)[-1] or host, host, _pdf_text(r.content), url)]
    if "csv" in ctype or url.lower().endswith(".csv"):
        df = pd.read_csv(io.StringIO(r.text), sep=None, engine="python")
        return table_findings(df, url.rsplit("/", 1)[-1], host, url)
    html = r.text
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    title = re.sub(r"\s+", " ", m.group(1)).strip()[:90] if m else host
    body = re.sub(r"(?is)<(script|style|nav|footer|header|aside).*?</\1>", " ", html)
    body = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</li>", ". ", body)
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    import html as _h
    txt = re.sub(r"(\.\s*){2,}", ". ", _h.unescape(txt)).strip()[:TEXT_LIMIT]
    out = [_finding(title, host, txt, url)] if len(txt) > 100 else []
    try:
        tables = pd.read_html(io.StringIO(html), thousands=None)  # "12,0" gibi yazımları _to_num çözer
    except Exception:
        tables = []
    for i, df in enumerate([t for t in tables if len(t) >= 3][:3]):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" ".join(str(x) for x in c if "Unnamed" not in str(x)).strip() for c in df.columns]
        out += [f for f in table_findings(df, f"{title} · tablo {i + 1}", host, url) if "series" in f or "latest" in f]
    if not out:
        raise ValueError("Sayfada okunabilir içerik bulunamadı.")
    return out
