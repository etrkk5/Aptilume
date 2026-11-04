# Aptilume

**AI Skills Intelligence · Yapı Kredi**

Kurum içi AI yetkinliklerini ekip bağlamı ve rol hedefleriyle ölçen web uygulaması. Açık uçlu ağırlıklı anketler LLM ile hazırlanır. Puanlama, anket kapandıktan sonra ayrı ve kalıcı bir worker işiyle yapılır. Dashboard ve Excel aynı yayımlanmış sonuç sürümünü kullanır.

## Başlangıç

Gereksinimler: Python 3.12+, Node 22+, pnpm 11.25 veya Docker.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
cd web
corepack enable
pnpm install --frozen-lockfile
pnpm build
cd ..
PYTHONPATH=backend .venv/bin/python -m app.cli bootstrap
PYTHONPATH=backend .venv/bin/python -m app.cli api
```

Ayrı terminalde:

```bash
PYTHONPATH=backend .venv/bin/python -m app.cli worker
```

Uygulama: http://127.0.0.1:8080. Yerel ilk kurulum hesabı **admin / admin**. Bu hesap yalnızca entegrasyonları yönetir. AD bilgileri girilmeden kurumsal kullanıcı girişi yapılamaz. Temiz kurulum örnek çalışan veya kampanya oluşturmaz; yalnızca 42 kaynak yetkinliğini yükler.

Docker ile:

```bash
docker buildx build --platform linux/amd64,linux/arm64 --load -t aptilume:0.2.0 .
docker compose -f compose.dev.yml up -d --no-build
```

Compose API ve worker başlatır, veriyi kalıcı `aptilume_aptilume-data` volume’unda tutar. `compose.dev.yml` yerel geliştirme içindir. `seed` komutu yalnızca izole test/geliştirme ortamına sentetik örnek veriler ekler; üretimde kapalıdır. Önceki sürümden kalan yerel örnek veriler otomatik silinmez.

## Görünüm

Giriş sayfası ve uygulama başlığındaki güneş/ay düğmesi açık ve koyu tema arasında geçer. İlk seçim sistem tercihinden alınır; manuel tercih bu tarayıcıda kalıcıdır. Tema tercihi kimlik, oturum veya rol bilgisi saklamaz.

## Kimlik ve erişim

Active Directory entegrasyonu LDAPS veya StartTLS kullanır. Sertifika ve sunucu adı doğrulaması zorunludur. Parolalar URL veya loglara yazılmaz; servis hesabının parolası şifrelenir, çalışan parolası saklanmaz. Kimlik eşlemesi değişmez `objectGUID` üzerinden yapılır. Aynı adlı kişileri isim veya title üzerinden birleştirme yapılmaz.

| Rol | Kapsam |
|---|---|
| Çalışan | Yalnızca kendi profili, atamaları, yanıtları, sonuçları ve kendisine atanmış gelişim planları |
| Ekip yöneticisi | Kendi profili ve AD `manager` ilişkisiyle kendisine bağlı çalışanlar; kendi kapsamı için dönem ve gelişim planı yönetimi |
| Entegrasyon yöneticisi | AD, LLM, DB bağlantıları ve çalışma alanı ayarları; çalışan ve anket verilerine erişmez |
| İnsan kaynakları | Tüm iş verileri ve entegrasyonlar |

AD grup eşlemesi önceliği: İK → entegrasyon yöneticisi → ekip yöneticisi → çalışan. Entegrasyon admini olmak, kendisine bağlı çalışan bulunsa bile iş verisi yetkisi vermez. `manager` alanında raporlanan aktif çalışanı bulunan kullanıcı yönetici olur; ayrıca bir yönetici grubu tanımlanabilir. Alt yönetici ekiplerinin dahil edilmesi admin panelinde seçilir.

Yetki, her API isteğinde sunucuda hesaplanır. Aynı departmanın iki yöneticisi birbirinin çalışanlarını göremez. Ortak departman bağlamı/rol hedefleri yalnızca departmanın tamamına yetkili yönetici veya İK tarafından değiştirilebilir. Kapsamı birden fazla yöneticiyi içeren dönemi yalnızca tüm katılımcılara yetkili kullanıcı kapatabilir, değerlendirebilir ve yayımlayabilir. Çalışanın yerine yönetici veya İK anket yanıtı gönderemez.

Oturumlar sunucuda tutulan, rastgele ve yalnızca hash’i saklanan cookie’lerle çalışır. Cookie HttpOnly/SameSite’dır; üretimde Secure kullanır. Yazma işlemleri CSRF ve Origin kontrolü gerektirir. Süre sınırı 8 saat, hareketsizlik sınırı 30 dakikadır; arka plan yenilemeleri hareketsiz oturumu açık tutmaz. Başarısız girişler sınırlanır. Kullanıcı devre dışı bırakıldığında, rol veya yönetici ilişkisi değiştiğinde kapsam yeniden uygulanır. AD verisi en fazla 5 dakika önbelleğe alınır; süresi dolduğunda dizine erişilemiyorsa yetki genişletilmez ve istek reddedilir. AD ayarları değiştirildiğinde kurumsal oturumlar iptal edilir.

## Admin panelinde AD kurulumu

1. Yerel adminle giriş yapın ve **Bağlantı ayarları → Active Directory → Bağlantıyı düzenle** ekranını açın.
2. Host, port, LDAPS/StartTLS, Base DN, salt okuma yetkili servis hesabının DN/parolası ve gerekiyorsa pod’a bağlanmış kurumsal CA dosyası yolunu girin.
3. İK ve entegrasyon admini gruplarının tam DN’lerini ayrı satırlarda tanımlayın. İç içe gruplar desteklenir. Yönetici alanı varsayılan olarak `manager`, kalıcı kimlik `objectGUID`, kullanıcı adı `sAMAccountName`, ekip `department` alanıdır.
4. Ayarları kaydedin, **Test et** ile TLS/servis hesabı/Base DN kontrolünü çalıştırın. AD girişini etkinleştirin ve **Eşitle** ile kişileri/ekipleri alın.
5. İK hesabıyla ekip bağlamını, title bazlı rol profillerini ve katılımcı–rol eşlemelerini tamamlayın. İK kademesi/rolü yalnızca AD title metninden otomatik tahmin edilmez.

Sunucu veya servis hesabı değişirse parola yeniden girilmelidir. Kayıtlı sırlar geri okunmaz; boş parola korunur. Yerel adminin güçlü parola belirleme ve çıkış işlemleri hesap menüsündedir. Yerel hesabın kapatılması gerekiyorsa önce kurumsal yönetici ve kurtarma süreci işletim ekibince doğrulanmalıdır.

## İş akışı

1. Yönetici ekip amacı, görevler, kullanım sınırları, yetkinlik hedefleri ve önem derecelerini düzenler. Değişiklikler yeni dönemlere uygulanır.
2. Yetkili kullanıcı dönem oluşturur, soruları hazırlatır, soru/rubrik setini inceler, onaylar ve anketi açar.
3. Çalışan kendisine atanmış formu doldurur. Başlangıç formu 22 soru içerir: 12 açık uçlu, 4 tek seçim ve 6 öz beyan. Taslaklar otomatik kaydedilir.
4. Gönderim puanlamayı başlatmaz. Dönem kapandıktan sonra **Toplu değerlendir** ayrı worker işi başlatır.
5. İlerleme, sınırlı tekrarlar ve gerekli insan incelemeleri takip edilir. Tamamlanan sonuçlar değişmez bir sürüm olarak yayımlanır.
6. Dashboard’da kapsam içindeki katılım, puan, hedef, seviye ve kişi profilleri incelenir. **Gelişim odakları** kalıcı gelişim planı açar veya öz beyan/yazılı değerlendirme karşılaştırmasını gösterir.
7. Excel özet veya açık yanıtları içeren ayrıntılı çıktı olarak hazırlanır. Oluşturulurken ve indirilirken kullanıcı kapsamı yeniden denetlenir; yetki değişiminden sonra eski kapsamlı dosya indirilemez.

Sentetik puanların kaynağı **Rapor bilgileri** ve Excel metodolojisinde belirtilir. Ana ekranda demo etiketi veya sentetik veri dipnotu gösterilmez. Mock sonuçlar gerçek model kalitesi veya çalışan yeterliliği kanıtı değildir.

## LLM ve DB bağlantıları

Bağlantılar admin panelinden eklenir, düzenlenir, test edilir, görevler için etkinleştirilir ve bağımlılıkları uygunsa silinir. Düzenleme yeni sürüm oluşturur; eski işler kullandıkları sürümü korur. Boş secret korunur, temizlemek için ayrı seçenek gerekir.

LLM protokolleri: `mock`, `openai_responses`, `openai_compatible_chat`. Base URL sürüm kökünü içermelidir (`https://llm.example/v1`); adapter `/responses` veya `/chat/completions` ekler. Gerçek endpoint host’u `OUTBOUND_ALLOWED_HOSTS` listesinde bulunmalıdır. Başarılı bağlantı testi modelin ölçüm kalitesini doğrulamaz. Üretimde mock profil ile soru/puanlama işi başlatılması engellenir.

SQLite ve PostgreSQL desteklenir. DB bağlantı testi tablo oluşturmaz. Aktifleştirme öncesi taşıma önizlemesi vardır; açık dönemler ve işler tamamlanmalı, yazmalar durdurulmalı, yedek alınmalı ve hedef boş olmalıdır. Transaction ile kopyalama ve içerik karşılaştırması tamamlanınca bağlantı değiştirilir. Çok instance ile çevrimiçi taşıma desteklenmez.

Kontrol deposu kimlikleri, oturumları, bağlantı sürümlerini, görev seçimlerini ve şifreli sırları tutar. Uygulama deposu anketleri, sonuçları, kapsamlı export kayıtlarını ve gelişim planlarını tutar. Kontrol deposunun başlangıç URL’si `CONTROL_STORE_URL` ile verilir. Uygulama DB’si erişilemezse yerel admin bağlantı kurtarma ekranı açık kalır.

## OpenShift / üretim ayarları

Image non-root `1001:0`, port 8080 ile çalışır; keyfi UID/grup 0, read-only kök dosya sistemi ve capability kapatma desteklenir. Yazılabilir alanlar `/app/data` ve `/tmp` ile sınırlıdır. Aynı image `bootstrap`, `migrate`, `api` ve `worker` komutlarıyla kullanılır. `bootstrap` katalog ve ilk kurulum hesabını hazırlar; gerçek kuruma sentetik veri yüklemez.

İşletim ekibinin deployment için vereceği ayarlar:

- `APP_MODE=production`: Secure cookie/HSTS; API dokümantasyonu, zayıf ilk parola, seed ve mock iş çalıştırma kapalı.
- Kalıcı ve tüm süreçlerde aynı `SECRET_ENCRYPTION_KEY` (Fernet): cluster Secret’tan verilmelidir. Mevcut şifreli veride anahtar kendiliğinden değiştirilmez.
- İlk boş kurulumda benzersiz `BOOTSTRAP_ADMIN_PASSWORD` (en az 12 karakter). Yerel `admin/admin` ile kurulmuş veride önce hesap menüsünden parola değiştirilmelidir; üretim başlangıcı geçici parolayı reddeder.
- `PUBLIC_BASE_URL=https://...`: kullanıcıya açılacak Route adresi. TLS sonlandırma/sertifika, CA mount, LLM izinli host’ları, AD/DB ağ erişimi, kalıcı veri ve yedekler işletim ekibince sağlanır.
- API ve worker ayrı süreç/pod olarak çalışmalıdır. SQLite ile tek API, tek worker ve uygun paylaşılan yerel disk kullanılmalıdır. Çok replica/HA hedefleniyorsa kontrol ve uygulama depoları uygun kurumsal PostgreSQL’e taşınmalı ve eşzamanlılık/yük testi yapılmalıdır.

Dağıtım sırası: yedek → uygulama yazmalarını/worker’ı durdur → `migrate` → `bootstrap` → API → worker. Mevcut tabloları genişleten migration `0002` kapsamlı export ve gelişim planlarını ekler. Kontrol deposunun yeni tabloları idempotent oluşturulur. OpenShift Deployment/Service/Route/PVC/Secret ve registry push kullanıcı ekibine aittir.

| Sağlık ucu | Anlamı |
|---|---|
| `/health/live` | API süreci |
| `/health/ready`, `/health/startup` | Kontrol deposu ve admin kurtarma hizmeti |
| `/health/application` | Uygulama DB’si/şema; erişim hatasında 503 |

Worker HTTP sunmaz; API’ye özgü image healthcheck’i worker’da devre dışı bırakılmalıdır. İş lease/heartbeat ve süreç durumu izlenir. Readiness, LLM veya AD kullanılabilirliği garantisi değildir.

## Doğrulama ve ölçüm sınırları

```bash
.venv/bin/python -m pytest
cd web
pnpm build
```

Testler gerçek kurum endpointlerine bağlanmaz. Ayrıntılar: [doğrulama kaydı](docs/VERIFICATION.md), [geliştirme planı](docs/DEVELOPMENT_PLAN.md). `tests/serve_ui_fixture.py` yalnızca izole yerel arayüz kontrolü içindir; Docker runtime’a kopyalanmaz ve gerçek kimlik doğrulamasına test girişi eklemez.

Kaynak katalog 42 yetkinlik, 210 seviye tanımı ve 126 eşleştirme içerir. Dokuz kaynak numara çelişkisi isim/alias eşleştirmesiyle çözülmüştür; 18 eksik kanıt kaynağı açık veri sorunu olarak korunur. Logo resmî Yapı Kredi varlığıdır; kaynak/hash `data/brand-source.json` içindedir.

Yazılı puan, MCQ ve öz beyan ayrı göstergelerdir. Teknik hata sıfır puan sayılmaz. Seviye önerisi davranış göstergelerinden hesaplanır; 0–100 skor beşe bölünmez. L4/L5 başlangıç formuyla doğrulanmaz; doğrulanmış seviye boş kalır. Toplu grupta beşten az geçerli kayıt varsa puan bastırılır. Gerçek AD/LLM, kurumun ölçüm kalibrasyonu, OpenShift koşulları ve hedef yük kurum ortamında ayrıca doğrulanmalıdır.
