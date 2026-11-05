# Hazır Python paketi

[Aptilume-0.6.1-Python.zip](Aptilume-0.6.1-Python.zip), Node.js veya Docker kurulmadan yerel demo çalıştırmak için hazır web arayüzünü ve Python uygulamasını içerir. Python 3.12 ve `requirements.lock.txt` bağımlılıkları gerekir; paket Python runtime veya çevrimdışı wheel deposu içermez.

`git pull` sonrası ZIP'i tamamen çıkarın. Terminali içindeki `Aptilume-0.6.1-Python` klasöründe açın; [kurulum rehberindeki](../docs/LOCAL_PYTHON.md) adımları uygulayın. ZIP içinde de README bulunur. API ve worker ayrı terminallerde çalışır.

- Kaynak commit: ZIP içindeki `PACKAGE.json` dosyasında kayıtlıdır.
- Bütünlük: [ZIP SHA-256 dosyası](Aptilume-0.6.1-Python.zip.sha256). ZIP içindeki `PACKAGE.json` her dosyanın SHA-256 değerini içerir.
- Yerel çalışma alanındaki çalışan/yanıt kayıtları, kayıtlı şifreler, `.env`, sanal ortam ve Node.js runtime'ı dahil değildir. Demo hesapları ilk yerel kurulumda üretilir.
- Paket bu kaynak commit'in sabit çıktısıdır; yeni kaynak değişikliklerini otomatik içermez. Yeni arayüz sürümü izinli build ortamında derlenip paketlenir; ZIP ve SHA-256 birlikte güncellenmelidir.

Bu ZIP yerel demo içindir. OpenShift production build/deployment akışı ana README ve Dockerfile üzerinden devam eder.

Önceki sabit paket: [0.5.0](Aptilume-0.5.0-Python.zip). 0.6.0, İK soru seti editörünü ve yayın akışını içerir. Mevcut kurulum güncellemesi için [rehberin son bölümünü](../docs/LOCAL_PYTHON.md) izleyin.

[0.6.0 sabit paketi](Aptilume-0.6.0-Python.zip) de korunur. Güncel 0.6.1 paketi yerleşim ve taşma düzeltmelerini içerir.
