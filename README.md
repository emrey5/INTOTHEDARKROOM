# DARKROOM

Prompt'tan veri destekli animasyonlu video üreten masaüstü uygulaması (tamamen ücretsiz).

Bir konu yazarsınız; program webden veriyi toplar, senaryoyu yazar, animasyonlu grafik,
tablo, sayaç, görsel ve video sahneleri çizer, Türkçe seslendirir ve tek bir MP4 verir.
Hiçbir ücretli servis kullanmaz.

## Masaüstü uygulaması: DARKROOM

**Windows'ta en kolay yol:**
1. Python 3.10+ kurun (kurarken "Add Python to PATH" kutusunu işaretleyin): `winget install Python.Python.3.12`
2. Bu klasörde `kurulum_windows.bat` dosyasına çift tıklayın (bir kerelik).
3. Uygulamayı açmak için `calistir.bat` dosyasına çift tıklayın.

ffmpeg ayrıca kurulmaz, uygulamanın içinde gelir.

**Tek tıkla açılan .exe ve kurulum dosyası** yapmak isterseniz `exe_olustur_windows.bat`
çalıştırın: `dist\DARKROOM\DARKROOM.exe` oluşur. Ücretsiz Inno Setup ile `kurulum.iss`
dosyasını derlerseniz başkalarına verebileceğiniz `DARKROOM-Kurulum.exe` çıkar.
Kurulumu denemek için: `DARKROOM.exe --selftest deneme` (2 sahnelik deneme videosu çizer).

Uygulamada:
- **Konu** kutusuna videonun konusunu yazın ya da örneklerden birine tıklayın.
- **Video süresi**: Kısa (~30 sn), Orta (~1 dk) ya da Uzun (~2 dk). Yapay zekâ sahne sayısını buna göre ayarlar.
- **Altyazı**: "Videoya yaz" seçiliyse anlatım, konuşmayla eşzamanlı olarak alt şeritte görünür. Ayrı `altyazi.srt` dosyası her zaman oluşur.
- **1 · Araştır**: Wikipedia, Wikidata, Dünya Bankası, Our World in Data, IMF ve web aramasından bilgi toplar.
  **Araştırma** sekmesinde her bilgiyi kaynağıyla görürsünüz; istemediklerinizin işaretini kaldırın.
- **Kendi kaynağın**: Araştırma sekmesindeki **＋ Dosya ekle** ile PDF, Excel (xlsx), CSV ya da metin
  dosyası; **＋ Web adresi ekle** ile bir sayfa (içindeki tablolar dahil) eklenir. Yıl sütunu olan tablolar
  çizgi grafiğe ve önce/sonra sahnesine, ad + sayı tabloları çubuk grafiğe, il ya da ülke listeleri haritaya
  dönüşür. Araştırma yapmadan sadece kendi kaynaklarınla da video yapabilirsin.
- **2 · Senaryoyu yaz**: yalnızca işaretli bilgilerden sahneleri yazar. Ardından **doğruluk kontrolü**
  senaryodaki her sayıyı kaynaklarda arar: bulunanlar ✓, bulunamayanlar ⚠ ile işaretlenir.
- **Senaryo** sekmesi: sahneleri ekleyin, silin, sıralayın; başlık, anlatım ve verileri düzeltin,
  "Önizle" ile anında görün.
- **Arka plan müziği**: Yok, programın ürettiği telifsiz müzik (sakin / enerjik / gizemli) ya da kendi dosyan.
  Müzik konuşma sırasında otomatik kısılır. **Ses efektleri** (whoosh, pop, tık, ding) animasyonlara denk gelir.
- **Dikey sürüm**: "Oluştur" seçiliyse ayrıca 1080x1920 `video_dikey.mp4` (Shorts / Reels / TikTok) çıkar.
- **3 · Videoyu oluştur**: çizim sırasında kareler canlı önizlenir; bitince "Videoyu aç". Video klasöründe
  ayrıca `kapak.png` (YouTube kapak resmi) ve `youtube.txt` (başlık, açıklama, bölümler, kaynaklar, etiketler) olur.
- **Videolarım**: önceki videolar; eski bir senaryoyu açıp yeniden çizebilirsiniz.

## Komut satırı

```
python -m promptvideo "Türkiye'nin nüfusu 1960'tan bugüne nasıl değişti?"
```

Uygulama her zaman siyah-turuncu `mekanik` görünümü kullanır. Komut satırında ayrıca `--style cizgi` (kâğıt üstüne elle çizilmiş çizgi film tarzı,
titreyen çizgiler, doodle'lar, el yazısı notlar) ve `--style modern` (koyu, parlak, sinematik).

Çıktı `cikti/` klasörüne yazılır: `video.mp4` (1920x1080, 30 fps), `plan.json` (senaryo), `altyazi.srt`.

## Nasıl çalışır

| Adım | Ne yapar | Ücretsiz araç |
|---|---|---|
| 1. Araştırma | Konuyu Wikipedia'da bulur (özet + tablolar), Wikidata'dan kesin bilgileri (nüfus, alan, tarihler, kişiler) alır, DuckDuckGo'da arar ve ilk sayfaları okur; konuya göre Dünya Bankası, Our World in Data (yaşam süresi, CO₂, enerji, mutluluk… 24 gösterge) ve IMF (büyüme, enflasyon, borç; tahminler dahil) verisini çeker | Wikipedia/Wikidata API, `ddgs`, World Bank, OWID, IMF DataMapper (hepsi anahtarsız) |
| 1b. Doğrulama | Senaryo yazıldıktan sonra her sayı (grafik değerleri, tablo hücreleri, anlatımdaki rakamlar) seçili kaynaklarda aranır | `factcheck.py` |
| 2. Senaryo | Araştırma notlarından 6-10 sahnelik plan yazar; sayıları sadece notlardan alır | **Ollama** ile bilgisayarınızda çalışan açık kaynak model (varsayılan `qwen3:8b`). Ollama yoksa kural tabanlı planlayıcı |
| 3. Medya | Görseller ve özgür lisanslı videolar | Wikimedia Commons (anahtarsız), isterseniz Pexels (ücretsiz anahtar) |
| 4. Ses | Doğal Türkçe seslendirme | `edge-tts` (tr-TR-AhmetNeural / EmelNeural), yedek gTTS |
| 5. Animasyon | Her kare Cairo ile vektörel çizilir: harf harf zıplayan/yükselen metinler, fosforlu kalem vurguları, sayan sayaçlar, yaylanarak büyüyen çubuklar, kendini çizen çizgi grafik, açılan pasta dilimleri, kayan tablo satırları, bantla yapıştırılmış fotoğraf kartları; göz kırpan, konuşurken ağzı oynayan, el kol hareketi yapan düz renkli çizgi karakterler (6 karakter, 9 poz, 6 duygu, konuşma balonu), iki tarafın yarıştığı VS sahnesi ve 100 kişilik insan piktogramı; sahneler arasında 5 çeşit geçiş (eğik silme, daire, şerit, panjur, kayan panel) | `pycairo`, programa gömülü ücretsiz fontlar (Inter, Baloo 2, Caveat; OFL lisanslı) |
| 6. Montaj | Sahneleri sesle birleştirir, isterseniz müziği konuşma sırasında otomatik kısar | `ffmpeg` |

## Kurulum (bir kerelik)

1. **Python 3.10+** ve **ffmpeg** kurun.
   - Windows: `winget install Python.Python.3.12` ve `winget install Gyan.FFmpeg`
   - macOS: `brew install python ffmpeg`
2. Bu klasörde: `pip install -r requirements.txt` (ffmpeg kurulu değilse uygulamayla gelen kopya kullanılır)
3. **Senaryo beyni (önerilir):** uygulamada üstteki **⚡ KUR VE HAZIRLA** düğmesine basın. Ücretsiz Ollama
   indirilip kurulur (Windows), başlatılır ve senaryo modeli indirilir: 12 GB ve üstü bellekte `qwen3:8b`
   (≈5 GB), daha azında `qwen3:4b` (≈2,5 GB). Ollama kurulu ama kapalıysa uygulama onu kendisi başlatır.
   Elle kurmak isterseniz: https://ollama.com, sonra `ollama pull qwen3:8b`.
4. İsteğe bağlı: daha çok stok video için https://www.pexels.com/api adresinden ücretsiz
   anahtar alıp `PEXELS_API_KEY` ortam değişkenine yazın.

## Kullanım

```
python -m promptvideo "İstanbul'un en kalabalık ilçeleri"
python -m promptvideo "Avrupa'da enflasyon: Türkiye, Almanya, Fransa" --voice tr-TR-EmelNeural
python -m promptvideo "..." --music muzik.mp3        # kendi müziğin
python -m promptvideo "..." --music auto:enerjik     # programın ürettiği telifsiz müzik (sakin/enerjik/gizemli)
python -m promptvideo "..." --vertical --no-sfx     # dikey sürüm de üret, ses efektsiz
python -m promptvideo "..." --plan-only               # sadece plan.json üret
python -m promptvideo --plan cikti/plan.json          # planı elle düzeltip yeniden çiz
python -m promptvideo --plan ornekler/demo_plan.json  # internetsiz demo
python -m promptvideo "..." --length kisa --subtitles  # ~30 sn, altyazılı
python -m promptvideo "..." --style modern          # koyu sinematik görünüm
```

En iyi sonuç için önce `--plan-only` çalıştırıp `plan.json`'daki rakamları ve metinleri
kontrol edin, sonra `--plan` ile çizin. Planı elle yazmak da mümkün.

## Sahne türleri (plan.json)

`title`, `bullets`, `stat`, `bar`, `line` (birden çok seri olabilir), `pie`, `table`,
`image` (`image_query` / `image_url` / `image_path`), `video` (`stock_query` / `video_path`),
`character` (çizgi karakterler konuşur; her karakterin kendi sesi, `backdrop`: studio, city, office, space,
lab, nature), `versus`, `people` (piktogram), `map` (`world` ya da `turkey`), `timeline` (yıllara göre olaylar),
`compare` (önce / sonra), `outro`. Alanların tam örneği `promptvideo/planner.py` içindeki `SCHEMA`'da ve
`ornekler/demo_plan.json`'da.

## Ayarlar (ortam değişkenleri)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `PV_MODEL` | `qwen3:8b` | Ollama modeli |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama adresi |
| `PV_VOICE` | `tr-TR-AhmetNeural` | Ses |
| `PV_PRESET` / `PV_CRF` | `medium` / `19` | Kodlama hızı / kalitesi (düşük CRF = daha kaliteli, büyük dosya) |
| `PV_NO_SPLASH` / `PV_SPLASH_MUTE` | boş | `1` yapılırsa açılış efekti hiç gösterilmez / sessiz oynar |
| `PV_STYLE` | `mekanik` | Komut satırındaki varsayılan görünüm (`mekanik` / `cizgi` / `modern`); `--style` ile de seçilir |

## Sınırlar

- "Higgsfield kalitesi"ndeki yapay zekâ ile üretilmiş sinematik klipler ücretsiz bir API ile
  yapılamıyor. Bu sürüm onların yerine Wikimedia/Pexels'teki gerçek videoları kullanıyor.
  Güçlü bir NVIDIA ekran kartınız varsa (12 GB+ VRAM) açık kaynak Wan 2.x modeli yerel olarak
  eklenebilir.
- Kural tabanlı planlayıcı (Ollama yokken) basit kalır; asıl kalite Ollama ile gelir.
- Model bazen yanlış sayı yazabilir; yayınlamadan önce `plan.json`'u kontrol edin.

## Güncellemeler nasıl yayınlanır

1. Değişiklikler `main` dalına girer (PR birleştirilir).
2. GitHub'da **Releases → Draft a new release** açın, **Choose a tag** kutusuna yeni bir sürüm
   yazın (ör. `v0.3.1`; her seferinde bir öncekinden büyük olmalı), kısa bir not yazıp
   **Publish release** deyin.
3. GitHub Actions (`.github/workflows/release.yml`) Windows'ta uygulamayı paketler, deneme videosu
   çizdirerek test eder ve `DARKROOM-0.3.1-Kurulum.exe` dosyasını o sürüme ekler (~10-15 dk).
4. Kurulu uygulamalar açılışta yeni sürümü görür: üstte turuncu **YENİ SÜRÜM** şeridi çıkar,
   **GÜNCELLE** kurulumu indirir, uygulamayı kapatıp yeni sürümü kurar ve yeniden açar.

İlk kurulum için son sürümün `...-Kurulum.exe` dosyasını Releases sayfasından indirin. Kurulum
yönetici izni istemez, programı kullanıcı klasörüne kurar.

Derlemeyi sürüm yayınlamadan denemek için: **Actions → Windows sürümü derle → Run workflow**.
Çıkan kurulum dosyası iş sayfasında "Artifacts" altında olur.
