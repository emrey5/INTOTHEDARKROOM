"""Doğruluk kontrolü: senaryodaki her sayı, senaryonun yazıldığı araştırma notlarında aranır.

Notlarda bulunamayan sayı "doğrulanamadı" olarak işaretlenir; böylece yapay zekânın uydurduğu
rakamlar video çizilmeden önce görülür. Yıllar ve 12'den küçük tam sayılar (sıra, adet) atlanır.
"""
import bisect
import re

from . import research as R

SCALES = {"bin": 1e3, "thousand": 1e3, "milyon": 1e6, "million": 1e6, "mn": 1e6, "milyar": 1e9,
          "billion": 1e9, "bn": 1e9, "trilyon": 1e12, "trillion": 1e12}
_NUM = re.compile(r"(?<![\w.,])[-+−]?\d[\d.,   ]*\d(?![\d])|(?<![\w.,])[-+−]?\d(?![\d])")
_SCALE = re.compile(r"\s*(" + "|".join(sorted(SCALES, key=len, reverse=True)) + r")", re.I)  # "milyona" da sayılır


def _readings(tok):
    """'85.372.377' / '85,3' / '1,234.5' gibi bir yazımın olası sayı değerleri."""
    t = tok.replace("−", "-").replace(" ", "").replace(" ", "").replace(" ", "")
    sign = -1 if t.startswith("-") else 1
    t = t.lstrip("+-")
    out = set()
    if "." in t and "," in t:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
        th = "," if dec == "." else "."
        t2 = t.replace(th, "").replace(dec, ".")
        out.add(t2)
    elif "," in t or "." in t:
        sep = "," if "," in t else "."
        parts = t.split(sep)
        if len(parts) > 2:  # 85.372.377: binlik ayırıcı
            out.add(t.replace(sep, ""))
        else:
            out.add(t.replace(sep, "."))  # ondalık
            if len(parts[1]) == 3:  # 1,234 ya da 1.234: binlik de olabilir
                out.add(t.replace(sep, ""))
    else:
        out.add(t)
    vals = []
    for o in out:
        try:
            vals.append(sign * float(o))
        except ValueError:
            pass
    return vals


def numbers_in(text):
    """Metindeki sayılar: [(yazım, değer)] — 'milyon' gibi çarpanlar da uygulanmış haliyle eklenir."""
    found = []
    for m in _NUM.finditer(str(text)):
        tok = m.group(0).strip(" .,")
        if not tok or not any(ch.isdigit() for ch in tok):
            continue
        sm = _SCALE.match(text, m.end())
        for v in _readings(tok):
            found.append((tok, v))
            if sm:
                found.append((tok, v * SCALES[sm.group(1).lower()]))
    return found


def _is_trivial(v, tok=None):
    if float(v).is_integer() and (abs(v) <= 12 or 1000 <= v <= 2100) and (tok is None or "." not in tok and "," not in tok):
        return True
    return v == 0


def source_numbers(findings):
    vals = set()
    for f in R.selected(findings):
        for _, v in numbers_in(f["text"]):
            vals.add(v)
        se = f.get("series")
        if se:
            vals.update(v for _, v in se["points"])
        for key in ("latest", "world"):
            if f.get(key):
                vals.update(r[2] for r in f[key]["rows"])
        for fact in f.get("facts") or []:
            if isinstance(fact[1], float):
                vals.add(fact[1])
    return sorted(v for v in vals if v)


def _decimals(v, tok=None):
    if tok:
        t = tok.replace(" ", "")
        m = re.search(r"[.,](\d+)$", t)
        if m and not (len(m.group(1)) == 3 and t.count(m.group(0)[0]) >= 1 and len(t) > 4):
            return len(m.group(1))
        return 0
    s = repr(float(v))
    return 0 if s.endswith(".0") else min(4, len(s.split(".")[1]))


def matches(v, pool, tok=None):
    """v (gösterilen hassasiyetiyle) havuzdaki bir sayıya eşit mi? 85,3 milyon ~ 85372377 gibi ölçekler de denenir."""
    d = _decimals(v, tok)
    for r in (1, 1e3, 1e6, 1e9, 1e12):
        target = v * r
        tol = max(abs(target) * 0.002, 10 ** -d * r)
        i = bisect.bisect_left(pool, target - tol)
        if i < len(pool) and pool[i] <= target + tol:
            return True
        if target < 0:
            continue
    return False


def scene_claims(sc):
    """Sahnede gösterilen/söylenen sayılar: [(görünen yazım, değer)]."""
    out = []
    t = sc.get("type")
    if t == "stat" and isinstance(sc.get("value"), (int, float)):
        out.append((None, float(sc["value"])))
    if t in ("bar", "pie", "map"):
        out += [(None, float(d["value"])) for d in sc.get("data", []) if isinstance(d.get("value"), (int, float))]
    if t == "line":
        for se in sc.get("series", []):
            out += [(None, float(p["y"])) for p in se.get("data", []) if isinstance(p.get("y"), (int, float))]
    if t == "table":
        for row in sc.get("rows", []):
            for cell in row[1:] if len(row) > 1 else row:
                out += numbers_in(str(cell))
    if t == "versus":
        out += [(None, float(sc[k]["value"])) for k in ("left", "right")
                if isinstance(sc.get(k), dict) and isinstance(sc[k].get("value"), (int, float))]
    if t == "compare":
        out += [(None, float(sc[k]["value"])) for k in ("before", "after")
                if isinstance(sc.get(k), dict) and isinstance(sc[k].get("value"), (int, float))]
        out += [x for k in ("before", "after") for x in numbers_in(str((sc.get(k) or {}).get("text", "")))]
    if t == "timeline":
        for e in sc.get("events", []):
            out += numbers_in(str(e.get("text", "")))
    if t == "people" and isinstance(sc.get("value"), (int, float)):
        out.append((None, float(sc["value"])))
    if t == "character":
        from .scenes import _say_lines
        for x in _say_lines(sc):
            out += numbers_in(x.get("text", ""))
    if sc.get("narration"):
        out += numbers_in(sc["narration"])
    for it in sc.get("items", []) if t == "bullets" else []:
        out += numbers_in(str(it))
    return [(tok, v) for tok, v in out if not _is_trivial(v, tok)]


def _show(tok, v):
    if tok:
        return tok
    from .theme import fmt_num
    return fmt_num(v)


def check_scene(sc, pool):
    claims = scene_claims(sc)
    ok, missing = 0, []
    # aynı yazımın farklı okumalarından biri tutması yeter
    by_tok = {}
    for tok, v in claims:
        by_tok.setdefault(tok if tok else f"#{len(by_tok)}", []).append((tok, v))
    for key, group in by_tok.items():
        if any(matches(v, pool, tok) for tok, v in group):
            ok += 1
        else:
            s = _show(*group[0])
            if s not in missing:
                missing.append(s)
    return {"verified": ok, "missing": missing}


def check_plan(plan, findings):
    """Her sahneye 'check' ekler; planın özetini döner. Bulgu yoksa (çevrimdışı) kontrol yapılmaz."""
    pool = source_numbers(findings or [])
    if not pool:
        for sc in plan.get("scenes", []):
            sc.pop("check", None)
        plan.pop("check", None)
        return None
    tv = tm = 0
    for sc in plan.get("scenes", []):
        c = check_scene(sc, pool)
        if c["verified"] or c["missing"]:
            sc["check"] = c
        else:
            sc.pop("check", None)
        tv += c["verified"]
        tm += len(c["missing"])
    plan["check"] = {"verified": tv, "missing": tm}
    return plan["check"]
