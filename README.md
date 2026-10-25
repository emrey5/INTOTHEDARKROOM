# INTOTHEDARKROOM · PromptVideo Stüdyo

Prompt'tan veri destekli animasyonlu video üreten masaüstü uygulaması (tamamen ücretsiz).

Bir konu yazarsınız; program webden veriyi toplar, senaryoyu yazar, animasyonlu grafik,
tablo, sayaç, görsel ve video sahneleri çizer, Türkçe seslendirir ve tek bir MP4 verir.
Hiçbir ücretli servis kullanmaz.

## Masaüstü uygulaması: PromptVideo Stüdyo

**Windows'ta en kolay yol:**
1. Python 3.10+ kurun (kurarken "Add Python to PATH" kutusunu işaretleyin): `winget install Python.Python.3.12`
2. Bu klasörde `kurulum_windows.bat` dosyasına çift tıklayın (bir kerelik).
3. Uygulamayı açmak için `calistir.bat` dosyasına çift tıklayın.

ffmpeg ayrıca kurulmaz, uygulamanın içinde gelir.

**Tek tıkla açılan .exe ve kurulum dosyası** yapmak isterseniz `exe_olustur_windows.bat`
çalıştırın: `dist\PromptVideo\PromptVideo.exe` oluşur. Ücretsiz Inno Setup ile `kurulum.iss`
dosyasını derlerseniz başkalarına verebileceğiniz `PromptVideo-Kurulum.exe` çıkar.
Kurulumu denemek için: `PromptVideo.exe --selftest deneme` (2 sahnelik deneme videosu çizer).

Uygulamada:
- **Konu** kutusuna videonun konusunu yazın ya da örneklerden birine tıklayın.
- **Görünüm**: Çizgi film ya da Modern. Kartlardaki küçük resimler gerçek önizlemedir.
- **1 · Senaryoyu hazırla**: webde araştırır ve sahneleri yazar, sonra Senaryo sekmesi açılır.
- **Senaryo** sekmesi: sahneleri ekleyin, silin, sıralayın; başlık, anlatım ve verileri düzeltin,
  "Önizle" ile anında görün.
- **2 · Videoyu oluştur**: çizim sırasında kareler canlı önizlenir; bitince "Videoyu aç".
- **Videolarım**: önceki videolar; eski bir senaryoyu açıp yeniden çizebilirsiniz.

## Komut satırı

```
python -m promptvideo "Türkiye'nin nüfusu 1960'tan bugüne nasıl değişti?"
```

Üç görünüm var: `--style mekanik` (siyah-turuncu, uygulamayla aynı tema), `--style cizgi` (varsayılan; kâğıt üstüne elle çizilmiş çizgi film tarzı,
titreyen çizgiler, doodle'lar, el yazısı notlar) ve `--style modern` (koyu, parlak, sinematik).

Çıktı `cikti/` klasörüne yazılır: `video.mp4` (1920x1080, 30 fps), `plan.json` (senaryo), `altyazi.srt`.

## Nasıl çalışır

| Adım | Ne yapar | Ücretsiz araç |
|---|---|---|
| 1. Araştırma | Konuyu Wikipedia'da bulur (özet + tablolar), DuckDuckGo'da arar, ilk sayfaları okur, ülke istatistiği istenirse Dünya Bankası'ndan çeker | Wikipedia API, `ddgs`, World Bank Open Data |
| 2. Senaryo | Araştırma notlarından 6-10 sahnelik plan yazar; sayıları sadece notlardan alır | **Ollama** ile bilgisayarınızda çalışan açık kaynak model (varsayılan `qwen3:8b`). Ollama yoksa kural tabanlı planlayıcı |
| 3. Medya | Görseller ve özgür lisanslı videolar | Wikimedia Commons (anahtarsız), isterseniz Pexels (ücretsiz anahtar) |
| 4. Ses | Doğal Türkçe seslendirme | `edge-tts` (tr-TR-AhmetNeural / EmelNeural), yedek gTTS |
| 5. Animasyon | Her kare Cairo ile vektörel çizilir: harf harf zıplayan/yükselen metinler, fosforlu kalem vurguları, sayan sayaçlar, yaylanarak büyüyen çubuklar, kendini çizen çizgi grafik, açılan pasta dilimleri, kayan tablo satırları, bantla yapıştırılmış fotoğraf kartları; sahneler arasında 5 çeşit geçiş (eğik silme, daire, şerit, panjur, kayan panel) | `pycairo`, programa gömülü ücretsiz fontlar (Inter, Baloo 2, Caveat; OFL lisanslı) |
| 6. Montaj | Sahneleri sesle birleştirir, isterseniz müziği konuşma sırasında otomatik kısar | `ffmpeg` |

## Kurulum (bir kerelik)

1. **Python 3.10+** ve **ffmpeg** kurun.
   - Windows: `winget install Python.Python.3.12` ve `winget install Gyan.FFmpeg`
   - macOS: `brew install python ffmpeg`
2. Bu klasörde: `pip install -r requirements.txt` (ffmpeg kurulu değilse uygulamayla gelen kopya kullanılır)
3. **Senaryo beyni (önerilir):** https://ollama.com adresinden Ollama'yı kurun, sonra
   `ollama pull qwen3:8b`  (8 GB RAM yeterli; güçlü bilgisayarda `qwen3:14b` daha iyi yazar:
   `PV_MODEL=qwen3:14b`)
4. İsteğe bağlı: daha çok stok video için https://www.pexels.com/api adresinden ücretsiz
   anahtar alıp `PEXELS_API_KEY` ortam değişkenine yazın.

## Kullanım

```
python -m promptvideo "İstanbul'un en kalabalık ilçeleri"
python -m promptvideo "Avrupa'da enflasyon: Türkiye, Almanya, Fransa" --voice tr-TR-EmelNeural
python -m promptvideo "..." --music muzik.mp3        # arka plan müziği (telifsiz bir parça)
python -m promptvideo "..." --plan-only               # sadece plan.json üret
python -m promptvideo --plan cikti/plan.json          # planı elle düzeltip yeniden çiz
python -m promptvideo --plan ornekler/demo_plan.json  # internetsiz demo
python -m promptvideo "..." --style modern          # koyu sinematik görünüm
```

En iyi sonuç için önce `--plan-only` çalıştırıp `plan.json`'daki rakamları ve metinleri
kontrol edin, sonra `--plan` ile çizin. Planı elle yazmak da mümkün.

## Sahne türleri (plan.json)

`title`, `bullets`, `stat`, `bar`, `line` (birden çok seri olabilir), `pie`, `table`,
`image` (`image_query` / `image_url` / `image_path`), `video` (`stock_query` / `video_path`),
`outro`. Alanların tam örneği `promptvideo/planner.py` içindeki `SCHEMA`'da ve
`ornekler/demo_plan.json`'da.

## Ayarlar (ortam değişkenleri)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `PV_MODEL` | `qwen3:8b` | Ollama modeli |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama adresi |
| `PV_VOICE` | `tr-TR-AhmetNeural` | Ses |
| `PV_PRESET` / `PV_CRF` | `medium` / `19` | Kodlama hızı / kalitesi (düşük CRF = daha kaliteli, büyük dosya) |
| `PV_STYLE` | `cizgi` | Varsayılan görünüm (`cizgi` / `modern`); `--style` ile de seçilir |

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
   çizdirerek test eder ve `PromptVideo-0.3.1-Kurulum.exe` dosyasını o sürüme ekler (~10-15 dk).
4. Kurulu uygulamalar açılışta yeni sürümü görür: üstte turuncu **YENİ SÜRÜM** şeridi çıkar,
   **GÜNCELLE** kurulumu indirir, uygulamayı kapatıp yeni sürümü kurar ve yeniden açar.

İlk kurulum için son sürümün `...-Kurulum.exe` dosyasını Releases sayfasından indirin. Kurulum
yönetici izni istemez, programı kullanıcı klasörüne kurar.

Derlemeyi sürüm yayınlamadan denemek için: **Actions → Windows sürümü derle → Run workflow**.
Çıkan kurulum dosyası iş sayfasında "Artifacts" altında olur.
