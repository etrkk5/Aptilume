# Aptilume 0.5.0 — Python ile yerel çalıştırma paketi

5 Kasım 2026. Node.js ve Docker kullanılamayan bilgisayarlar için hazır browser arayüzü + Python API/worker paketi. [Kurulum rehberi](LOCAL_PYTHON.md).

- ZIP ayrı, boşluk içeren bir klasöre çıkarılarak Python 3.12 ile kontrol edildi. Runtime PATH'inde Node.js yokken bootstrap, tekrar bootstrap, hesapların korunması, dört normal rol girişi ve 30/10/1/0 kişi kapsamı geçti. Kaynak katalog 42 yetkinlik, varsayılan İK politikası v1, opsiyonel kalite örneği ve tüm statik dosyalar doğrulandı.
- Gerçek loopback HTTP sunucusu ve worker, `local_demo.py` üzerinden ayrı Python süreçleriyle başlatıldı; hazır HTML ve readiness başarılı, süreçler kontrollü durduruldu. Windows için komutlar rehberde verilir; bu yerel kontrol macOS üzerinde yapıldı.
- Dört yeni regresyon: paket içeriği/hash değerleri ve sır/yerel veri hariç tutma; hazır arayüz zorunluluğu; production DB/anahtar/LAN bind ayarlarını devralmama; eksik UI ve geçersiz port reddi. Black ve yeni başlatıcı/paketleyici için Bandit orta/yüksek eşik başarılı. CI tüm regresyonları ve gerçek arayüzden Python paket üretimini tekrar çalıştırır.
- ZIP bir Python runtime veya wheel deposu içermez. İlk pip kurulumu kurumun izinli paket deposuna ya da hedef Python/OS/mimariye uygun onaylı wheel dosyalarına ihtiyaç duyar. Node.js yalnız izinli build ortamında kullanılır; şirket bilgisayarında kurulmaz/çalıştırılmaz. Paket kişisel veri, parola, `.env`, Node runtime ve sanal ortam içermez; dosya hash'leri `PACKAGE.json` içindedir.
- Başlatıcı yalnız izole yerel demo kullanır; OpenShift production başlatma yolu ve güvenlik koşulları aynı kalır. Çalışan yerel Docker sunumu veya onun kayıtları bu paket testiyle değiştirilmedi.

---

# Aptilume 0.5.0 — yetkinlik kataloğu doğrulaması

4 Kasım 2026. [Katalog yönetimi ve yükseltme rehberi](FEATURES_0_5.md). Önceki doğrulamalar aşağıda tarihsel kayıt olarak korunur.

- **186 Python testi geçti**; son PostgreSQL sorgu düzeltmesinden sonra ilgili **47 test** tekrar geçti. Mevcut 3 bağımlılık deprecation uyarısı sürer.
- İK ekleme/düzenleme/silme/geri yükleme; benzersiz ve değişmeyen kod, L1–L5 doğrulaması, arama/sayfalama, dinamik sayaç, audit ve eşzamanlı 200/409 kontrolü geçti. Çalışan, yönetici ve entegrasyon admininin yazma denemeleri 403 ile reddedildi.
- Yeni yetkinlik rol hedefinde 22 soruluk üretime dahil edildi. Yeni dönem snapshot'ı, eski dönemlerin değişiklik öncesi bir defalık sabitlenmesi, arşivden sonra bekleyen dönem üretimi, mevcut form adlarının ve yayınlanmış sonuçların korunması doğrulandı. Arşivli hedefle yeni dönem açıklamalı 409 verir; ortak üç yetkinliğin silinmesi engellenir.
- PostgreSQL 16: aktarım/işçi/yayın/Excel, kontrol deposu ve önceki İK akışlarına ek olarak, CRUD-only runtime rolünde katalog ekleme/düzenleme/silme/geri yükleme, JSON sürüm çakışması ve eski dönem snapshot'ı geçti. JSON sütunlarında DISTINCT yerine ID alt sorgusu kullanılır. İzole fixture TLS kapalıdır; kurum CA kabulü değildir.
- Gerçek LLM HTTP adaptöründe İK talimatı aktarımı düzeltildi; iki endpoint biçiminde özel/varsayılan system talimatı ve zorunlu güvenlik sözleşmesinin birlikte gönderildiği 4 test geçti. Gerçek model kalitesi değerlendirmesi yapılmadı.
- TypeScript/Vite üretim derlemesi ve Black başarılı; Bandit orta/yüksek önem ve güven eşiğinde 0 sonuç. Runtime bağımlılıkları değişmedi.
- Tarayıcıda ayrı test alanında ekleme, ad/L3 düzenleme, arşiv filtresi, silme ve geri yükleme doğrulandı. Sunum alanındaki 42 aktif yetkinlik, hesaplar, talimatlar ve dönemler korunur; test yetkinliği sunum alanına eklenmedi.
- Son linux/amd64 ve linux/arm64 paketlerinde Trivy tüm önem seviyelerinde 0 bildirim; ignore/VEX istisnası yok. Tarama 4 Kasım 2026 yerel verisiyle, image yüklenmeden yapılır. CI yeni veriyle tekrar tarar.

**Image:** `aptilume:0.5.0`, linux/amd64 + linux/arm64. API ve worker birlikte güncellenir. Ek şema migration'ı yok; 0.4 kurulum gereksinimleri geçerli. Gerçek AD/LLM/CA, MFA, model kalibrasyonu, OpenShift ve kurum sızma/yük kabulü koşulları devam eder.

---

# Aptilume 0.4.0 — raporlama ve İK yönetişimi doğrulaması

4 Kasım 2026. Önceki sürüm kayıtları aşağıda korunur. Ayrıntılı iş akışı ve migration notları [0.4.0 rehberindedir](FEATURES_0_4.md).

| Kontrol | Sonuç |
|---|---|
| Python | **169 test geçti**, 3 mevcut bağımlılık deprecation uyarısı. Önceki güvenlik/erişim/transport regresyonları korunur. |
| Yeni metrikler | Filtreler, yanıtlamayanların paydada tutulması, gerçekten atanmış soru setiyle uygunluk, eski snapshot uyumu, kişi bazında dağılım ve 5 farklı kişi bastırması doğrulandı. Excel ile dashboard aynı kapsam ve metrikleri verir. |
| Rol formları | Aynı ekipte iki unvana farklı rol formu ve ortak bölümde aynı soru seti; yeni dönemde hedef ekip seçimi / Tümü UI kontrolü. |
| Zorunlu sorular | Eksik, boş ve görünmez metinle teslim reddi; taslak kaydı korunur. Düzenlenebilir sayfalarda eksik soruyla ilerleme engellenir. |
| Yanıt kalitesi | Kalite kaydı yalnız kapanış sonrası worker ile; tipli semantik model çıktısı ve temel anlamsız içerik kontrolü; kanıt alıntısı doğrulaması; otomatik skor yerine `None`; bekleyen incelemede yayın engeli. |
| İK kararı | HR-only liste/detay ve puan kararı; yönetici/çalışan/admin reddi; açık puan zorunlu; kendi yanıtına karar reddi; tekrar karar 409; dürüst deneyimsizlik yanlış etiketlenmez. |
| Talimatlar | Aynı varsayılanlar development/production; HR-only okuma/yazma; değişmez sürümler, eşzamanlı kayıt 201/409; kuyruktaki üretim/puanlama/özet işlerinin eski politika sürümünü koruması ve snapshot izi. |
| PostgreSQL 16 | SQLite aktarımı, rol formları, worker/yayın/metrik/Excel ve kontrol deposu kotalarına ek olarak **CRUD-only runtime rolüyle İK politika sürüm kaydı, JSON ekip/dönem kalite filtreleri ve kalite puan kararı geçti**; DDL reddi korunur. İzole fixture TLS kapalıdır; kurum CA kabulü değildir. |
| Web | TypeScript/Vite production build ve Black başarılı. ECharts modüler; bundle boyutu uyarı eşiğinin altında. Yeni grafikler açık/koyu temayı izler. |
| Statik güvenlik | Bandit orta/yüksek önem ve güven eşiğinde 0 sonuç; önceki gerekçeli Pod bind istisnası korunur. |
| Container CVE | Son amd64 ve arm64 arşivlerinde tüm seviyelerde 0 bildirim; ignore/VEX istisnası yok. Yerel tarama, 4 Kasım 2026 verisi. |
| Tarayıcı | Rol/yetkinlik/bölüm/yanıt durumu, filtre temizleme ve boş kapsam; düzenlenebilir İK talimatları ve sentetik kalite kaydı; yeni form ekip seçimi ve üst logo kaldırılması kontrol edildi. |

**Image:** `aptilume:0.4.0`, linux/amd64 + linux/arm64. Yerel manifest index:

`sha256:14a97dde7195b3ea8af85ebe1b1faf6b0532937a18678153bd70e17f483235fe`

Yerel demo eski hesabı/veriyi korur. “Yanıt Kalitesi · Örnek” adlı ek, kapalı ve yayımlanmamış sentetik dönem İK kuyruğunu göstermek için oluşturulmuştur. Policy varsayılan v1 korunur. Talimatlar `data/default-instructions.json` → kontrol deposu sürüm kaydı üzerinden kullanılır; geçmişte kaydedilmeyen politika sürümü için yeni sürüm uydurulmaz.

Yükseltmede uygulama migration `0003` ve kontrol deposu yeni politika tablosu kurulum yetkisiyle hazırlanmalıdır. Runtime yalnız gerekli CRUD yetkileriyle çalışır. Gerçek AD/LLM/CA, model alaka/puan kalibrasyonu, MFA, OpenShift/ağ/Secret/SIEM ve kurum sızma/yük kabulü koşulları devam eder.

---

# Aptilume 0.3.1 — sunum modu ek doğrulaması

4 Kasım 2026. Önceki güvenlik incelemesi aşağıda tarihsel kayıt olarak korunur. Bu sürüm açık `APP_MODE=demo` seçimini ve üretimden ayrı demo depolarını ekler.

- **131 test geçti**, 3 mevcut bağımlılık deprecation uyarısı. Yeni 12 regresyon: mod/depo seçimi, üretim URL/anahtarını devralmama, dört rolün gerçek giriş ve kapsamı, Argon2 hash, yanlış parola, tekrarlı bootstrap, web'den parola dosyasına erişememe ve kopyalanmış demo deposu/oturumunun production API/worker tarafından reddi.
- Dört rol hesabı ile sunucu kapsamı: İK 30, yönetici 10, çalışan 1, admin 0 kişi; admin yalnız entegrasyonlar. Kurulum 30 kişi + 2 dönem; tekrar başlatma hesap/parola ve düzenlemeleri korur.
- `aptilume:0.3.1` linux/amd64 + linux/arm64 üretildi. Manifest index: `sha256:64653a0060496a79dcd0f3a22211ebd8110652939dbf166ef77ae47e073c351f`.
- Yerel API ve worker 0.3.1 ile demo modunda sağlıklı çalışır. Gerçek eski veri alanı korunur; sunum verisi DATA_DIR/presentation-demo içindedir.
- Tarayıcıda çalışan profili/açık 22 soruluk form ve İK genel görünümü doğrulandı. Örnek anket sunum için gönderilmeden bırakıldı.
- Parolalar rastgele üretilir, Git'e girmez. Kontrollü demo kurtarma dosyası yalnız yerel demo alanındadır; production bu kaynağı kabul etmez. `demo-accounts` yalnız demo modunda işletim komutudur.
- Black ve Bandit orta/yüksek eşik kontrolü başarılı. Mevcut otomatik CI, bu sürümü de test, bağımlılık/image taraması, build ve PostgreSQL kabulünden geçirir; durum Actions'tan izlenir.

Sunum akışı ve tek parametreyle mod seçimi [DEMO.md](DEMO.md) içindedir. Gerçek AD/LLM/CA, MFA ve OpenShift kurum kabul koşulları devam eder.

---

# Aptilume 0.3.0 doğrulama kaydı

**4 Kasım 2026.** Güvenlik incelemesi [ilk bulgular](SECURITY_REVIEW.md) ve [uygulama sonuçları](SECURITY_REMEDIATION.md) olarak ayrı tutulur.

| Kontrol | Sonuç |
|---|---|
| Python testleri | **119 geçti**; Starlette TestClient ve ldap3/pyasn1 kaynaklı 3 deprecation uyarısı, başarısız test yok. |
| Web / biçim | TypeScript + Vite production build ve Black kontrolü başarılı. |
| Kayıt kapsamı | Çalışan kendi profil/atama/yanıt/sonuç/planını, yönetici AD manager ağacını görür. Başkasının ID'si, farklı ekip filtresi, export ve yetki değişimi testleri geçti. İK kurum genelinde; entegrasyon admini iş verisi uçlarında 403 alır. |
| Auth | Argon2, güçlü production parola, Secure/HttpOnly/__Host- cookie, CSRF/sabit Host/Origin, logout/rotasyon, boşta kalma/absolute expiry; hesap/IP/genel atomik kota, 4 parola işlemi ve 5 oturum sınırı doğrulandı. |
| AD | GUID/disabled/grup/manager döngüsü, ldap3 MOCK_SYNC, süreli fail-closed önbellek ve toplu grup sorguları. Admin önerisi aktif ayarı değiştirmez; yalnız İK onaylar, eski/çift karar reddedilir, uygulamada LDAP oturumları iptal olur. Gerçek kurum AD'si kullanılmadı. |
| Bağlantı / TLS | İzinli host/port/CIDR, metadata/IPv4-mapped engeli, DNS IP sabitleme, örtük proxy/redirect engeli ve secret rotasyonu. Native TLS testinde doğru CA+SNI başarı, yanlış hostname ve güvenilmeyen CA reddi. |
| Girdi / kaynak | Akışta gövde/boyut/süre sınırı, yinelenen/derin/nonfinite JSON reddi, secret içermeyen 4xx; model bütçeleri/şema/kanıt, export alanı/kota/saklama, atomik inceleme ve kendi yanıtını onaylayamama doğrulandı. |
| İş akışı | 22 soruluk karma form, rol/title snapshot, taslak sürüm çatışması, kapanış sonrası worker, rubrik/kanıt ve teknik hata ayrımı, lease/çift worker, yayın ve gelişim planları mevcut regresyonlarda geçti. |
| Excel / audit | Kapsam, formül metni, SHA-256/yol/symlink/boyut kontrolü, süreli silme; güvenlik olaylarının redaksiyonu ve İK erişimi test edildi. |
| Python CVE | pip-audit: kilitli runtime bağımlılıklarında 0 bilinen açık. |
| Web CVE | pnpm audit: prod+dev 125 bağımlılıkta tüm seviyeler 0. |
| Bandit | Orta/yüksek önem ve güven eşiğinde 0 sonuç. Pod bind'i için tek gerekçeli B104 satır istisnası; global skip yok. |
| Container CVE | Son amd64 ve arm64 image arşivlerinde Trivy tüm önem seviyelerinde 0 bildirim. Ignore/VEX istisnası yok. |
| PostgreSQL 16 | SQLite aktarımı + 42 skill/30 sentetik kişi/3 rol/22 soruluk form; worker/yayın/metrik, oturumlu plan ve kapsamlı Excel geçti. Pg kontrol deposunda atomik kotalar/oturumlar ve CRUD-only runtime rolü doğrulandı; DDL reddedildi. İzole fixture TLS kapalı; kurum DB TLS kabulü yapılmadı. |
| Production container | UID 100123:0, read-only root, tüm capability'ler kapalı, no-new-privileges; HTTPS giriş/Secure cookie, 42 skill/0 kişi, admin iş verisi reddi, docs 404, fixture bypass/test/kurulum araçları yok. Eksik secret/varsayılan zayıf parola başlangıcı reddedilir. |
| Tarayıcı | İki rol ile AD öneri/onay/oturum iptali doğrulandı. Önceki login/tema/rol menüleri ve anket/gelişim/Excel doğrulamaları korunuyor. DB bozukken admin kurtarma ekranı ayrıca test edildi. |
| CI | GitHub Actions test, statik/bağımlılık/image taraması, build, production fail-closed ve PostgreSQL adımlarını otomatik çalıştırır. Çalıştırma durumu GitHub Actions'tan kontrol edilir. |

## Image ve yerel çalışma

`aptilume:0.3.0`, **linux/amd64 + linux/arm64** olarak üretildi. Yerel manifest index:

`sha256:e33921a9332216e07db2f37d1729709672c31c8de87ceed34c0d6b7bfad7909d`

API ve worker `compose.dev.yml` ile `http://127.0.0.1:8080` adresinde çalışır. Yerel hesap **admin / admin**, yalnızca entegrasyon ekranına erişir. Gerçek `aptilume_aptilume-data` volume'u korunmuştur. Yeni production kurulum sentetik çalışan üretmez; production admin/admin kabul etmez.

UI kontrolleri 8090 portunda izole fixture, DB kontrolleri yalnızca adı doğrulanan geçici PostgreSQL host'u ile yapıldı. Bu test yardımcıları runtime image'a alınmaz. Sahip olunan geçici test kaynakları kontrollerden sonra kaldırılır.

## Tekrar çalıştırma

```bash
.venv/bin/python -m pytest
.venv/bin/python -m black --check backend tests
pip-audit --no-deps --disable-pip -r requirements.lock.txt
bandit -r backend/app -ll -ii
cd web
pnpm audit --audit-level=low
pnpm build
cd ..
docker buildx build --platform linux/amd64,linux/arm64 --load -t aptilume:0.3.0 .
docker compose -f compose.dev.yml up -d --no-build
```

Doğrulama araçları `requirements-dev.txt` ve `requirements-security.txt` içindedir; runtime'a kurulmaz. Çok mimarili `--load`, bu ortamda etkin containerd image store gerektirir. Trivy tüm CVE seviyeleriyle yerel image arşivini tarar; CI örneği workflow'dadır.

## Kurum kabulü

Gerçek AD/LLM/CA, PostgreSQL verify-full el sıkışması, MFA erişim katmanı, OpenShift Route/SCC/NetworkPolicy/Secret/PVC, SIEM alarmı, yük/DAST/sızma testi ve yedekten geri dönüş kurumda doğrulanmalıdır. Bu kayıt dış ortam kabulü veya sıfır açık garantisi değildir. Ayrıntılı sorumlu/kanıt listesi [sonuç raporundadır](SECURITY_REMEDIATION.md).
