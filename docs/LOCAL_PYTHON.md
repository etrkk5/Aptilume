# Aptilume — yalnız Python ile yerel demo

Bu paket derlenmiş web arayüzünü içerir. Çalıştırılan süreçler Python API ve worker'dır. Node.js, npm, pnpm, Docker ve ayrı bir veritabanı kurulumu gerekmez. Tarayıcı hazır JavaScript/CSS dosyalarını Python sunucusundan alır. Python 3.12 önerilir. Demo sentetik veriler ve mock LLM kullanır.

## Windows / PowerShell

ZIP dosyasını tamamen normal bir klasöre çıkarın. Terminali `local_demo.py`, `backend`, `data`, `web` ve `requirements.lock.txt` bulunan klasörde açın. ZIP içinden doğrudan çalıştırmayın.

İlk kurulum:

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe local_demo.py setup
.\.venv\Scripts\python.exe local_demo.py accounts
```

`py` komutu bulunmuyorsa `python --version` ile Python 3.12'yi doğrulayın; ilk iki komutta `py -3.12` yerine `python` kullanın. Aktivasyon betiği veya PowerShell execution policy değişikliği gerekmez. Bağımlılıklar ilk kurulumda kurumun izin verdiği Python paket deposundan indirilmelidir. Paket tam çevrimdışı kurulum için platforma özel Python wheel dosyaları içermez; ağ kapalıysa kurum içi depo veya Python 3.12 / işletim sistemi / mimariye uygun onaylı wheel paketi gerekir. TLS doğrulamasını kapatmayın.

Birinci terminalde web uygulaması:

```powershell
.\.venv\Scripts\python.exe local_demo.py api
```

Aynı proje klasöründe ikinci terminalde arka plan işleri:

```powershell
.\.venv\Scripts\python.exe local_demo.py worker
```

Tarayıcı: **http://127.0.0.1:8080/**. `accounts` komutunun gösterdiği `hr` hesabıyla başlayın. Dört hesap `hr`, `manager`, `employee`, `admin`; parolalar yeni bilgisayarda ilk kurulumda rastgele oluşturulur. Demo modunda admin/admin geçerli değildir. Şifreleri paylaşmayın veya Git'e eklemeyin.

İsteğe bağlı İK yanıt kalitesi örneği (web sunucusunu başlatmadan önce):

```powershell
.\.venv\Scripts\python.exe local_demo.py quality-sample
```

8080 başka uygulamada kullanılıyorsa iki süreçte de aynı portu seçin:

```powershell
.\.venv\Scripts\python.exe local_demo.py api --port 8091
.\.venv\Scripts\python.exe local_demo.py worker --port 8091
```

İki komutu ayrı terminallerde çalıştırın; tarayıcıda http://127.0.0.1:8091/ açın.

## macOS / Linux

Proje klasöründe:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python local_demo.py setup
.venv/bin/python local_demo.py accounts
.venv/bin/python local_demo.py api
```

İkinci terminalde aynı klasörde:

```bash
.venv/bin/python local_demo.py worker
```

## Tekrar çalıştırma ve veriler

İki terminalde Ctrl+C süreçleri durdurur. Sonraki açılışta yalnız `api` ve `worker` komutlarını çalıştırın. Başlatıcı ortam değişkenlerini kendi ayarlar; `.env` okunmasına veya elle değişken tanımlamaya ihtiyaç duymaz. Her zaman izole `demo` modu, klasör içindeki `runtime/presentation-demo` ve yalnız `127.0.0.1` bağlantısı kullanılır. Klasörü taşımadan önce süreçleri durdurun; kurulu ortam ve veritabanı yollarını korumak için ilk kurulumu kalıcı konumda yapın. `runtime` klasörünü silmek yerel veri/şifreleri siler; Git'e eklemeyin.

## Paket üretimi ve kurum deployment'ı

Paketin Git kaynakları tek başına hazır arayüzü içermez; `web/dist` Git'te tutulmaz. Python paket ZIP'i kullanın. Yeni sürümün arayüzü Node.js'e izin verilen build ortamında derlenir, ardından şu komutla paketlenir:

```bash
python scripts/package_python.py --output work/Aptilume-0.5.0-Python.zip
```

ZIP yalnız uygulama kaynakları, kaynak katalog/talimatlar ve hazır arayüzü içerir; kişisel demo verileri, parolalar, `.env`, sanal ortam ve Node.js runtime'ı dahil edilmez. `PACKAGE.json` kaynak commit ve dosya SHA-256 değerlerini içerir.

Bu başlatıcı yerel demo içindir. OpenShift'teki gerçek production çalıştırması mevcut Dockerfile ve `python -m app.cli api` / `worker` komutlarını, kurumsal Secret/AD/LLM/DB ayarlarını kullanır. `local_demo.py` production başlatıcısı değildir.
