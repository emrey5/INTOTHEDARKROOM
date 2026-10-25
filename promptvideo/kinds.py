"""Video türleri: gerçekçi, çizgi animasyon, infografik, haber, kinetik yazı, karakter anlatıyor, hikâye.

Tür üç şeyi belirler: görünüm (stil), yapay zekâya verilen senaryo talimatı ve senaryo yazıldıktan sonra
sahnelerin türe uydurulması (ör. kinetik yazıda anlatım sahneleri büyük hareketli yazıya dönüşür).
Bu son adım Ollama olmadan yazılan senaryoda da türün gerçekten görünmesini sağlar.
"""
import re

KINDS = {
    "gercekci": dict(name="Gerçekçi", label="GERÇEKÇİ", desc="Gerçek video ve fotoğraflar, belgesel havası", style="belgesel",
                     hint="Bu video GERÇEKÇİ türde: sahnelerin çoğu (en az yarısı) gerçek görüntü olsun: "
                          "'video' (stock_query) ve 'image' (image_query) sahneleri; aramalar somut, görsel ve "
                          "İngilizce olsun (ör. 'coffee beans roasting', 'ottoman palace'). 'character' sahnesi "
                          "KULLANMA. Veriyi 1-2 grafik ya da 'stat' ile göster."),
    "cizgi": dict(name="Çizgi animasyon", label="ÇİZGİ ANİMASYON", desc="Elle çizilmiş görünüm, konuşan karakterler", style="cizgi",
                  hint="Bu video ÇİZGİ ANİMASYON türünde: 3-4 'character' sahnesi kullan; iki karakter soru-cevap "
                       "yapsın, duygular ve pozlar değişsin. Dil samimi ve eğlenceli olsun."),
    "infografik": dict(name="İnfografik", label="İNFOGRAFİK", desc="Grafikler, haritalar ve sayaçlarla veri", style=None,
                       hint="Bu video İNFOGRAFİK türünde: sahnelerin çoğu veri sahnesi olsun (bar, line, pie, map, "
                            "stat, people, timeline, compare). En fazla 1 'character' sahnesi."),
    "haber": dict(name="Haber bülteni", label="HABER BÜLTENİ", desc="Haber kanalı görünümü, net ve hızlı", style="haber",
                  hint="Bu video HABER BÜLTENİ türünde: kısa, net, tarafsız cümleler; ilk sahnenin kicker'ı "
                       "'GÜNDEM' olsun. Önce en önemli bilgi, sonra veriler (stat, bar, line), arada 'video' "
                       "sahneleri. 'character' sahnesi KULLANMA."),
    "kinetik": dict(name="Kinetik yazı", label="KİNETİK YAZI", desc="Büyük hareketli yazılar, az grafik", style=None,
                    hint="Bu video KİNETİK YAZI türünde: sahnelerin çoğu 'kinetic' olsun: "
                         '{"type": "kinetic", "kicker": "kısa etiket", "narration": "1-2 vurucu cümle"}. '
                         "Ekranda anlatım kelime kelime büyük yazıyla görünür; sayıları rakamla yaz. "
                         "Arada 1-2 'stat' olabilir. 'character' sahnesi KULLANMA."),
    "karakter": dict(name="Karakter anlatıyor", label="KARAKTER ANLATIYOR", desc="Bir karakter konuyu sunucu gibi anlatır", style="modern",
                     hint="Bu video KARAKTER ANLATIYOR türünde: aynı sunucu karakter (look 0) videonun çoğunda "
                          "konuşsun; anlatım sahneleri 'character' olsun ('say' = anlatımın kısa hali), veri "
                          "sahneleri arada kalsın. Haritada 'presenter': true kullan."),
    "hikaye": dict(name="Hikâye animasyonu", label="HİKÂYE ANİMASYONU",
                   desc="Ekran kartın her sahneyi çizer; sürükleyici kısa hikâye, büyük altyazı", style="modern",
                   music="auto:epik", research=False,
                   hint="Bu video HİKÂYE ANİMASYONU türünde (ayrı planlayıcı yazar)."),
    "piksel": dict(name="Retro piksel", label="RETRO PİKSEL", desc="8-bit oyun görünümü ve oyun müziği", style="piksel", music="auto:retro",
                   hint="Bu video RETRO PİKSEL (8-bit oyun) türünde: dil eğlenceli ve oyun havasında olsun "
                        "(ör. 'Seviye 1', 'Yeni bilgi açıldı!'); kicker'lar oyun terimleri olabilir. 1-2 'character' "
                        "sahnesi ve sade grafikler kullan; fotoğraf ve video sahnesi KULLANMA."),
}
DEFAULT = "infografik"

# promptta türü söyleyen kelimeler
WORDS = {
    # "kahvenin hikâyesi" gibi belgesel konuları tetiklemesin diye yalnızca açık ifadeler
    "hikaye": ("hikaye animasyon", "hikâye animasyon", "animasyon hikaye", "animasyon hikâye", "kısa hikaye",
               "kısa hikâye", "bir hikaye anlat", "bir hikâye anlat", "masal", "öykü", "kısa film",
               "story animation", "short story", "animated story"),
    "piksel": ("piksel", "pixel", "8-bit", "8 bit", "retro", "oyun tarzı", "atari"),
    "gercekci": ("gerçekçi", "gercekci", "gerçek görüntü", "belgesel tarzı", "realistic", "sinematik"),
    "cizgi": ("çizgi film", "cizgi film", "çizgi animasyon", "animasyon", "karikatür", "cartoon"),
    "infografik": ("infografik", "grafikli", "veri odaklı", "infographic"),
    "haber": ("haber bülteni", "haber tarzı", "haber gibi", "bülten", "news"),
    "kinetik": ("kinetik", "yazılı video", "yazı animasyonu", "motivasyon", "alıntı", "söz ", "typography"),
    "karakter": ("karakter anlat", "sunucu", "anlatıcı karakter", "karakterli", "presenter"),
}


def needs_research(kind):
    """Hikâye gibi türler webde araştırma yapmaz, doğrudan senaryoya geçer."""
    return KINDS.get(kind, {}).get("research", True)


def detect(text):
    """Prompttan tür (bulunamazsa None)."""
    t = " " + (text or "").lower() + " "
    for k, words in WORDS.items():
        if any(w in t for w in words):
            return k
    return None


def _sentences(text, n=2, maxlen=110):
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", str(text or "")) if p.strip()]
    out = []
    for p in parts[:n]:
        out.append(p if len(p) <= maxlen else p[:maxlen - 1].rsplit(" ", 1)[0] + "…")
    return out


def _text_of(sc):
    if sc.get("narration"):
        return sc["narration"]
    if sc.get("items"):
        return ". ".join(str(x) for x in sc["items"][:3])
    return sc.get("title") or sc.get("caption") or ""


def _to_character(sc, i, title):
    lines = _sentences(_text_of(sc)) or [title]
    poses, moods = ("talk", "point", "explain", "talk"), ("happy", "excited", "thinking", "happy")
    return {"type": "character", "kicker": sc.get("kicker", ""), "backdrop": sc.get("backdrop", "studio"),
            "characters": [{"look": 0, "pose": poses[i % 4], "emotion": moods[i % 4]}],
            "say": [{"who": 0, "text": ln} for ln in lines], "narration": sc.get("narration") or " ".join(lines)}


def _to_kinetic(sc):
    return {"type": "kinetic", "kicker": sc.get("kicker") or sc.get("title", "")[:40],
            "narration": _text_of(sc), **({"duration": sc["duration"]} if sc.get("duration") else {})}


def _to_broll(sc, query):
    return {"type": "video", "kicker": sc.get("kicker", ""), "caption": sc.get("title") or sc.get("caption") or query,
            "stock_query": sc.get("stock_query") or sc.get("image_query") or query,
            "narration": _text_of(sc)}


DATA = ("bar", "line", "pie", "table", "map", "stat", "people", "timeline", "compare", "versus")


def apply(plan, kind, topic=""):
    """Yazılmış senaryoyu türe uydurur (yerinde değiştirir ve döner)."""
    if kind not in KINDS or kind == "hikaye" or not plan.get("scenes"):
        return plan
    plan["kind"] = kind
    sc = plan["scenes"]
    title = plan.get("title") or topic
    query = topic or title
    out = []
    for i, s in enumerate(sc):
        t = s.get("type")
        first, last = i == 0, i == len(sc) - 1
        if first or last or t in ("title", "outro"):
            out.append(s)
            continue
        if kind == "gercekci":
            if t in ("character", "bullets", "kinetic"):
                s = _to_broll(s, query)
        elif kind == "haber":
            if t in ("character", "kinetic"):
                s = _to_broll(s, query)
        elif kind == "infografik":
            if t == "character" and any(x.get("type") == "character" for x in out):
                s = _to_kinetic(s)  # en fazla bir karakter sahnesi
        elif kind == "kinetik":
            if t not in ("stat", "compare"):
                s = _to_kinetic(s)
        elif kind == "karakter":
            if t in ("bullets", "image", "video", "kinetic"):
                s = _to_character(s, i, title)
            elif t == "map":
                s["presenter"] = True
        elif kind == "piksel":
            if t in ("image", "video"):
                s = _to_character(s, i, title) if i % 2 else _to_kinetic(s)  # fotoğraf piksel havasını bozar
        elif kind == "cizgi":
            if t in ("bullets", "kinetic") and sum(x.get("type") == "character" for x in out) < 3:
                s = _to_character(s, i, title)
        out.append(s)
    if kind == "gercekci" and not any(x.get("type") in ("video", "image") for x in out[1:-1]):
        out.insert(1, {"type": "video", "stock_query": query, "caption": title, "kicker": "",
                       "narration": ""})
    if kind == "cizgi" and not any(x.get("type") == "character" for x in out):
        out.insert(1, _to_character({"narration": f"Merhaba! Bugün {title} konusuna birlikte bakıyoruz."}, 0, title))
    plan["scenes"] = out
    return plan
