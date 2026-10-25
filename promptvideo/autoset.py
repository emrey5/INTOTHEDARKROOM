"""Prompttan video ayarlarını seçer: stil, müzik, tempo, süre, format, dil, ses, renk, kalite.

Kullanıcı ayrıca bir şey seçmek zorunda kalmaz: "Shorts için kısa, mavi renkli bir video: ..." gibi
açık istekler doğrudan uygulanır; açık istek yoksa konu türüne göre (tarih, ekonomi, bilim, gizem…)
uygun görünüm ve müzik seçilir. İnternetsiz ve anında çalışır.
"""
import re

DEFAULTS = dict(kind="infografik", style="mekanik", accent="", bg="", quality="1080", fps="30", tempo="normal", vertical="0",
                square="0", subs="1", sub_size="orta", sub_pos="alt", sub_box="kutu", voice="tr-TR-AhmetNeural",
                music_mode="auto:sakin", music_vol=35, sfx="1", length="orta", lang="tr")

# konu türü -> (ad, ayarlar); sırası önemli: ilk eşleşen kazanır
TOPICS = [
    ("gizem", ("korku", "gizem", "gizemli", "esrarengiz", "cinayet", "suç", "seri katil", "komplo", "karanlık",
               "paranormal", "hayalet", "kayıp", "çözülemeyen", "mystery", "crime", "horror"),
     dict(style="mekanik", music_mode="auto:gerilim", tempo="normal", sub_box="kutu")),
    ("haber", ("haber", "gündem", "son dakika", "seçim", "enflasyon", "faiz", "dolar", "euro", "borsa", "ekonomi",
               "bütçe", "işsizlik", "asgari ücret", "maaş", "zam", "vergi", "deprem", "news", "election",
               "inflation", "economy"),
     dict(style="haber", music_mode="auto:enerjik", tempo="normal", sub_box="vurgu")),
    ("tarih", ("tarih", "tarihi", "belgesel", "savaş", "imparatorluk", "osmanlı", "roma", "antik", "uygarlık",
               "medeniyet", "hikâyesi", "hikayesi", "biyografi", "hayatı", "kuruluş", "devrim", "fetih", "kral",
               "padişah", "history", "war", "empire", "ancient"),
     dict(style="belgesel", music_mode="auto:epik", tempo="yavas", sub_box="kutu")),
    ("bilim", ("uzay", "gezegen", "evren", "yıldız", "galaksi", "kara delik", "bilim", "teknoloji", "yapay zeka",
               "yapay zekâ", "robot", "gelecek", "fizik", "kuantum", "nasa", "roket", "space", "science",
               "technology", " ai "),
     dict(style="modern", music_mode="auto:gizemli", tempo="normal", sub_box="kutu")),
    ("spor", ("futbol", "basketbol", "voleybol", "spor", "maç", "şampiyon", "lig", "olimpiyat", "transfer",
              "football", "soccer", "sport"),
     dict(style="modern", music_mode="auto:enerjik", tempo="hizli", sub_box="vurgu")),
    ("eglence", ("çocuk", "eğlenceli", "komik", "ilginç bilgi", "hayvan", "kedi", "köpek", "yemek", "tarif",
                 "oyun", "çizgi", "masal", "fun", "kids", "animal"),
     dict(style="cizgi", music_mode="auto:enerjik", tempo="normal", sub_box="kutu")),
    ("yasam", ("sağlık", "psikoloji", "uyku", "beslenme", "diyet", "spor yapmak", "meditasyon", "mutluluk",
               "kişisel gelişim", "verimlilik", "alışkanlık", "health", "psychology"),
     dict(style="minimal", music_mode="auto:sakin", tempo="normal", sub_box="golge", sfx="0")),
]
TOPIC_NAMES = {"gizem": "gizem / suç", "haber": "haber / ekonomi", "tarih": "tarih / belgesel",
               "bilim": "bilim / teknoloji", "spor": "spor", "eglence": "eğlence", "yasam": "sağlık / yaşam"}

COLORS = {"turuncu": "#FF7A1A", "mavi": "#3D8BFF", "lacivert": "#2F5BFF", "yeşil": "#2ED47A", "yesil": "#2ED47A",
          "mor": "#9B6BFF", "kırmızı": "#FF3B4E", "kirmizi": "#FF3B4E", "altın": "#E0B04A", "sarı": "#FFC83D",
          "pembe": "#FF5CA8", "turkuaz": "#00C2C7", "beyaz": "#FFFFFF", "gri": "#A0A4AE"}

STYLE_WORDS = {"belgesel": ("belgesel tarzı", "belgesel gibi", "sinematik"), "haber": ("haber tarzı", "haber gibi", "haber bülteni"),
               "minimal": ("minimal", "sade", "beyaz arka plan", "açık renkli"), "cizgi": ("çizgi film", "karikatür", "elle çizilmiş", "doodle"),
               "modern": ("modern", "neon", "parlak"), "mekanik": ("darkroom", "karanlık tema", "siyah turuncu", "terminal", "matrix")}
MUSIC_WORDS = {"": ("müziksiz", "müzik olmasın", "müzik yok"), "auto:epik": ("epik", "destansı", "heyecanlı müzik"),
               "auto:gerilim": ("gerilim", "gergin", "korkutucu müzik"), "auto:sakin": ("sakin müzik", "huzurlu", "rahatlatıcı", "lofi"),
               "auto:enerjik": ("enerjik", "hareketli", "coşkulu"), "auto:gizemli": ("gizemli müzik", "atmosferik")}

_EN_WORDS = re.compile(r"\b(the|of|and|how|why|what|in|is|are|history|world|video|about)\b", re.I)
_TR_CHARS = re.compile(r"[çğıöşüÇĞİÖŞÜ]")


def _has(text, words):
    return next((w for w in words if w in text), None)


def infer(prompt, kind=None):
    """Prompttan ayarlar. kind verilirse (kullanıcı seçtiyse) video türü odur, yoksa prompttan bulunur.
    Dönüş: (ayarlar, neden seçildiklerinin kısa listesi, araştırılacak konu)."""
    from . import kinds as K
    raw = prompt or ""
    t = " " + raw.lower().replace("i̇", "i") + " "
    o = dict(DEFAULTS)
    why = []
    cut = []  # konudan atılacak talimat parçaları (araştırmayı kirletmesin)

    # dil
    if _has(t, ("ingilizce", "english", "in english")):
        o["lang"] = "en"
        cut += [r"ingilizce", r"in english", r"english"]
    elif not _TR_CHARS.search(raw) and len(_EN_WORDS.findall(raw)) >= 2:
        o["lang"] = "en"
    if o["lang"] == "en":
        o["voice"] = "en-US-AndrewNeural"
        why.append("İngilizce")

    # konu türü
    topic = None
    story = (kind or K.detect(t)) == "hikaye"  # hikâyede görünümü konu değil tür belirler
    for name, words, preset in TOPICS:
        if not story and _has(t, words):
            topic = name
            o.update(preset)
            why.append(f"konu: {TOPIC_NAMES[name]}")
            break

    # video türü: görünümü ve senaryonun yapısını belirler
    kind = kind or K.detect(t) or K.DEFAULT
    o["kind"] = kind
    kd = K.KINDS[kind]
    if kd.get("style"):
        o["style"] = kd["style"]
    if kd.get("music"):
        o["music_mode"] = kd["music"]
    for w in K.WORDS.get(kind, ()):
        if w in t:
            cut.append(re.escape(w.strip()) + r"\w*")

    # açık stil isteği görünümü ezer
    for st, words in STYLE_WORDS.items():
        w = _has(t, words)
        if w:
            o["style"] = st
            cut.append(re.escape(w) + r"\w*")
            break

    # sosyal medya / format
    if _has(t, ("shorts", "short video", "reels", "reel", "tiktok", "tik tok", "dikey")):
        o.update(vertical="1", length="kisa", tempo="hizli", sub_size="buyuk", sub_box="vurgu",
                 music_mode=o["music_mode"] if topic or story else "auto:enerjik")
        why.append("dikey (Shorts/Reels)")
        cut += [r"(youtube\s+)?shorts?\w*", r"reels?\w*", r"tik\s?tok\w*", r"dikey\w*"]
    if _has(t, ("instagram", "kare format", "kare video", "1:1")):
        o["square"] = "1"
        why.append("kare (Instagram)")
        cut += [r"instagram\w*", r"kare (format|video)\w*", r"1:1"]

    # süre
    if re.search(r"\b(kısa|kisa|30 saniye|yarım dakika|hızlıca özet)", t):
        o["length"] = "kisa"
    elif re.search(r"\b(uzun|detaylı|ayrıntılı|kapsamlı|derinlemesine|2 dakika|iki dakika|3 dakika)", t):
        o["length"] = "uzun"
    cut += [r"\b(çok\s+)?(kısa|uzun|detaylı|ayrıntılı|kapsamlı)\s+(bir\s+)?(video|anlatım)\w*",
            r"\b\d+\s*(saniye|dakika)\w*(lık|lik)?", r"\b(detaylı|ayrıntılı|kapsamlı|derinlemesine)\b",
            r"\b(çok\s+)?(kısa|uzun)\b(?=\s*(,|bir\b|ve\b|olsun|$))"]
    why.append({"kisa": "kısa (~30 sn)", "orta": "orta (~1 dk)", "uzun": "uzun (~2 dk)"}[o["length"]])

    # kalite
    if re.search(r"\b4\s?k\b|2160", t):
        o["quality"] = "2160"
        why.append("4K")
        cut += [r"\b4\s?k\b\w*", r"2160p?"]
    elif re.search(r"\b2k\b|1440", t):
        o["quality"] = "1440"
        cut += [r"\b2k\b", r"1440p?"]
    elif re.search(r"\b720", t):
        o["quality"] = "720"
        cut += [r"720p?"]
    if re.search(r"60\s?fps|akıcı", t):
        o["fps"] = "60"
        why.append("60 fps")
        cut += [r"60\s?fps\w*"]

    # tempo
    if _has(t, ("hızlı tempo", "hızlı anlat", "dinamik", "tempolu")):
        o["tempo"] = "hizli"
    elif _has(t, ("yavaş", "ağır tempo", "sakin anlat")):
        o["tempo"] = "yavas"

    # müzik
    for mode, words in MUSIC_WORDS.items():
        w = _has(t, words)
        if w:
            o["music_mode"] = mode
            cut.append(re.escape(w) + r"\w*( müzik\w*)?")
            break

    # ses ve altyazı
    if _has(t, ("kadın sesi", "kadın sesiyle", "kadın seslendir", "female voice")):
        o["voice"] = "en-US-AvaNeural" if o["lang"] == "en" else "tr-TR-EmelNeural"
        cut.append(r"kadın ses\w*")
    elif _has(t, ("erkek sesi", "erkek sesiyle", "male voice")):
        cut.append(r"erkek ses\w*")
    if _has(t, ("seslendirmesiz", "sessiz video", "anlatıcısız")):
        o["voice"] = ""
        cut += [r"seslendirmesiz", r"sessiz video", r"anlatıcısız"]
    if _has(t, ("altyazısız", "altyazı olmasın")):
        o["subs"] = "0"
        cut += [r"altyazısız", r"altyazı olmasın"]
    if _has(t, ("efektsiz", "ses efekti olmasın")):
        o["sfx"] = "0"

    # renk: "mavi renkli", "kırmızı tonlarında", "renk: yeşil"
    m = re.search(r"(" + "|".join(COLORS) + r")\s+(renk\w*|ton\w*|tema\w*|vurgu\w*)", t) or \
        re.search(r"renk\w*\s*:?\s*(" + "|".join(COLORS) + r")", t)
    if m:
        c = m.group(1)
        if c in ("beyaz",):
            o["style"] = "minimal"
        else:
            o["accent"] = COLORS[c]
        why.append(f"{c} renk")
        cut.append(re.escape(m.group(0)))

    from .theme import STYLE_NAMES
    if o["style"] != kd.get("style"):
        why.insert(0, STYLE_NAMES.get(o["style"], o["style"]).split(" (")[0] + " görünüm")
    why.insert(0, K.KINDS[kind]["name"])
    mus = {"": "müziksiz", "auto:sakin": "sakin müzik", "auto:enerjik": "enerjik müzik", "auto:gizemli": "gizemli müzik",
           "auto:epik": "epik müzik", "auto:gerilim": "gerilim müziği", "auto:retro": "8-bit müzik"}.get(o["music_mode"], "")
    if mus:
        why.append(mus)
    if o["tempo"] != "normal":
        why.append({"hizli": "hızlı tempo", "yavas": "ağır tempo"}[o["tempo"]])
    return o, why, clean_topic(raw, cut)


def clean_topic(prompt, cut):
    """Format/stil talimatlarını konudan çıkarır: "Shorts için kısa bir video: Kahvenin tarihi" -> "Kahvenin tarihi"."""
    s = prompt
    if ":" in s:  # "…bir video: KONU" kalıbında konu iki noktadan sonradır
        head, tail = s.split(":", 1)
        if len(tail.strip()) > 8 and re.search(r"video|için|tarz|renk|müzik|stil", head, re.I):
            return tail.strip()
    for pat in cut:
        s = re.sub(pat, " ", s, flags=re.I)
    s = re.sub(r"\b(için|olsun|olacak|bir video( hazırla| yap)?|video( hazırla| yap)|hazırla|yap)\b", " ", s, flags=re.I)
    s = re.sub(r"\s*,\s*(,\s*)+", ", ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,.-")
    s = re.sub(r"[\s,]+(ve|ile|and)$", "", s, flags=re.I).strip(" ,.-")
    return s or prompt.strip()
