# Aptilume 0.3.0 — güvenlik iyileştirme sonuç raporu

**Tarih:** 4 Kasım 2026
**Başlangıç:** 0.2.0, `2aa16121c07a80de5f327280274eaf428c7b28ac`
**İlk bulgu kaydı:** [SECURITY_REVIEW.md](SECURITY_REVIEW.md); uygulama öncesinde oluşturuldu ve tarihsel kayıt olarak korundu.
**Sonuç:** Bulgular için düzeltmeler uygulandı ve yerel doğrulamalar geçti. Kurumsal üretim kabulü aşağıdaki dış ortam kontrolleri tamamlanana kadar koşulludur.

## Yönetici değerlendirmesi

İlk incelemede 1 kritik, 5 yüksek, 5 orta ve 1 düşük bulgu kaydedildi. En ciddi sorunlar entegrasyon admininin AD rol politikasını değiştirerek kendi yetkisini büyütebilmesi ve iş verisini başka DB/LLM hedefine yönlendirebilmesiydi. Bu işlemler veri sahibi İK onayına veya çevrimdışı işletim sürecine alındı. Çalışan yalnızca kendisini, yönetici AD `manager` ağacındaki kişileri, entegrasyon admini yalnızca yapılandırmaları görür; İK kurum genelini görür. Sunucudaki kapsam kontrolü esas alınır.

Container incelemesinde ayrıca önceki Debian tabanında 13 farklı CVE'ye karşılık gelen 38 paket-CVE eşleşmesi bulundu: 36 yüksek, 2 kritik. Bu, uygulama mantığı bulgularından ayrı, ek SEC-13 bulgusudur. Runtime güncel ve digest ile sabitlenmiş Alpine tabanına taşındı. Sonraki tüm seviye taramasında görülen pip/ensurepip paketleme araçları da runtime'dan kaldırıldı. Son amd64 ve arm64 taramalarında bilinen açık bildirilmedi; ignore/VEX istisnası eklenmedi.

Bu sonuç sıfır açık garantisi veya kurum ortamında sızma testi sertifikası değildir. Kaynak kodu, izole testler ve tarama anındaki bilinen CVE verileri incelendi. Gerçek AD, LLM, kurum PostgreSQL TLS'i ve OpenShift ortamı henüz sağlanmadığı için bunlar adına kabul verilmedi.

## Bulguların kapanış kaydı

| ID / ilk önem | Uygulanan düzeltme | Doğrulama |
|---|---|---|
| SEC-01 / Kritik | İlk AD kurulumu sonrasında admin değişiklikleri şifreli bekleyen öneridir. İK onaylamadan aktif politika değişmez. Eski/tekrarlanan kararlar reddedilir; uygulanan değişiklik kurumsal oturumları iptal eder. İlk kurulum yetkisi yeniden açılmaz. | Admin öneri, İK onay/red, superseded/replay ve oturum iptali testleri; tarayıcıda iki ayrı rol ile doğrulama. |
| SEC-02 / Yüksek | LLM görev bağlama ve veri taşıma izni İK rolünde. Üretimde web DB taşıması kapalı; yalnızca yetkili operatörün çevrimdışı komutu var. | Admin 403 testleri; üretim API engeli; SQLite → PostgreSQL aktarım ve kapsamlı Excel kabulü. |
| SEC-03 / Yüksek | Bağlantılar izin listeli şemalarla doğrulanır. Serbest secret/header kabul edilmez. Hedef/hesap değişiminde eski sır yeni hedefe taşınmaz; sır yeniden girilir. Eski kayıtların API gösterimi de maskelenir. | Düz metin sır reddi, eski kayıt redaksiyonu, endpoint/hesap değişimi ve secret rotasyonu testleri. |
| SEC-04 / Yüksek | Varsayılan production; bilinmeyen mod başlangıcı durdurur. HTTPS sabit public origin, güçlü parola ve kalıcı şifreleme anahtarı zorunlu. PostgreSQL üretimde verify-full. | Yanlış mod, admin/admin, eksik secret, TLS disable ve geçersiz origin retleri; gerçek production container girişi. |
| SEC-05 / Yüksek | Ortak SQL deposunda atomik hesap/IP/genel kotalar; parola doğrulamada en fazla 4 eşzamanlı işlem; güçlü parola politikası; 5 oturum üst sınırı. AD taramaları TTL ve kilitle sınırlı, grup sorguları toplu. | IP değiştirme, eşzamanlı deneme ve oturum testleri hem SQLite hem PostgreSQL'de; AD önbellek/toplu sorgu testleri. |
| SEC-06 / Yüksek | Operatörün host/port/CIDR izin listeleri; metadata/loopback/link-local engeli. DNS'de doğrulanan IP ile bağlantı; özgün TLS SNI/hostname korunur. Örtük proxy ve yönlendirme kapalı. | SSRF, mapped IPv6, DNS sabitleme ve port testleri; gerçek TLS soketinde güvenilir CA/SNI başarı, yanlış hostname ve güvenilmeyen CA reddi. |
| SEC-07 / Orta | Auth gövdesi 8 KiB, diğer API gövdeleri 64 KiB; akış ve süre kontrolü. LLM girdi 256 KiB/çıktı 1 MiB; model token üst sınırı. Export 50 MiB, alan bütçesi 1 GiB; işlem ve oturum kotaları. | Parçalı büyük gövde, model boyutu/sıkıştırma/süre, export bütçesi ve kota testleri. |
| SEC-08 / Orta | Tipli, uzunluk sınırlı girişler; bilinmeyen alanlar, yinelenen JSON anahtarları, aşırı derinlik, NaN/Infinity reddi. Doğrulama hataları girilen sırrı yansıtmaz. | 4xx/secret redaksiyonu, biçim ve sonlu sayı testleri. |
| SEC-09 / Orta | Sabit production Host/Origin, CSRF, çift cookie reddi; __Host- Secure/HttpOnly cookie; CSP/HSTS ve hata yanıtlarında koruma başlıkları. API/HTML no-store. | Sahte Host/Origin, CSRF/cookie ve header testleri; Pod IP sağlık probe'ları çalışırken API Host sınırı korunur. |
| SEC-10 / Orta | Yalnızca bekleyen inceleme atomik kararla sonuçlanır; kişi kendi yanıtını inceleyemez. LLM puan/rubrik/kanıt çıktısı şema ile doğrulanır; uyumsuz kanıt incelemeye gider. | Kendi puanını onaylama, çift karar, model şeması/kanıt/sonlu sayı testleri. |
| SEC-11 / Orta | Aktör/korelasyon içeren güvenlik olayı DB + JSON stdout'a yazılır. Ham parola, anahtar, cookie, cevap veya hata gövdesi loglanmaz. İK olay ekranı; anonim ret örneklemesi ve saklama işi. | Yetkili olay görünümü, audit redaksiyonu/ret ve temizlik testleri. |
| SEC-12 / Düşük | Export yolu, symlink, SHA-256 ve boyut indirmede doğrulanır. Süre dolan dosyalar worker ile silinir. Test/kurulum araçları runtime dışında, image/action digestleri sabit. | Değiştirilmiş dosya/hash/yol/saklama testleri; minimal runtime kontrolü. |
| SEC-13 / ek Kritik | Eski Debian runtime yerine güncel Alpine; pip ve ensurepip kodları kaldırıldı. CI tüm CVE seviyelerinde image tarar. | Son linux/amd64 ve linux/arm64 Trivy taramalarında LOW/MEDIUM/HIGH/CRITICAL toplam 0 bildirim. |

## Ek dayanıklılık düzeltmeleri

- Kimlik/kapsam değiştiğinde istemci eski hesabın verisini çizmez. Tarayıcı geri/ileri önbelleği oturumu tekrar doğrular.
- Uygulama DB'si bozulduğunda entegrasyon admininin kurtarma ekranı kontrol deposu üzerinden açılır. Worker DB kesintisinde sır içermeyen hata ile sınırlı yeniden dener.
- AD production eşitleme önbelleği en fazla 5 dakika; geçerli yetki bilgisi alınamazsa süresi dolmuş kapsamla erişim verilmez. İlk kurumsal eşitlemede İK grubu ve aktif İK kimliği zorunludur.
- Runtime kaynak dosyaları grup tarafından yazılamaz. Dinamik OpenShift UID'si ile yalnızca data/tmp yazılabilir; production kabulünde read-only root, tüm capability'ler kapalı ve no-new-privileges kullanıldı.

## Doğrulama özeti

| Kontrol | Sonuç / sınır |
|---|---|
| Python testleri | **119 geçti**, 3 bağımlılık deprecation uyarısı. Kayıt kapsamı, anket/worker/yayın, auth ve kötüye kullanım regresyonları dahil. |
| TypeScript / Vite / biçim | Production build ve Black kontrolü başarılı. |
| Python bağımlılıkları | pip-audit: kilitli runtime paketlerinde bilinen açık yok. Python sürümleri tam sabitlenmiş; tam hash zorunluluğu uygulanmış bir pip lock iddiası yok. |
| Web bağımlılıkları | pnpm audit: production + development dahil 125 bağımlılıkta tüm önem seviyeleri 0. |
| Statik analiz | Bandit orta/yüksek önem ve güven eşiğinde 0 sonuç. Pod'da tüm arayüzlere bind için tek yerel B104 istisnası gerekçeli; global skip yok. Düşük seviye fixture parola/puan dizesi uyarıları gözden geçirildi. |
| Container CVE | Her iki mimaride tüm seviyelerde 0 bildirim; yerel arşiv tarandı, özel image harici servise yüklenmedi. Bu sonuç 4 Kasım 2026 tarama verisine bağlıdır. |
| Native TLS | Güvenilir test CA'sı ve özgün SNI ile başarı; yanlış hostname ve güvenilmeyen CA reddi. Kurum CA/endpoint kabulü değildir. |
| PostgreSQL 16 | 42 skill, 30 sentetik kişi, 3 rol profili, 22 soruluk form, worker/yayın/metrik, oturumlu gelişim planı ve kapsamlı Excel geçti. Kontrol deposu atomik kotaları/oturum sınırı ve CRUD-only runtime hesabı doğrulandı; DDL reddedildi. İzole fixture TLS kapalıdır; gerçek kurum DB TLS el sıkışması ayrıca doğrulanacak. |
| Production container | UID 100123:0, read-only root, capabilities kapalı, güçlü bootstrap + HTTPS giriş; 42 skill / 0 kişi; adminin iş verisinden reddi; docs kapalı; fixture bypass, pytest, pip ve ensurepip yok. |
| Tarayıcı | Admin önerisinin aktif AD ayarını değiştirmediği, yalnız İK'nın onay verebildiği ve onayda LDAP oturumlarının kapandığı izole fixture ile doğrulandı. |
| Otomatik kontrol | GitHub Actions; test, bağımlılık/statik tarama, web/image build, production fail-closed, tüm seviyelerde image CVE ve PostgreSQL kabul adımları. Yerel sonuçlar uzaktaki CI başarısı yerine geçmez; her çalıştırma Actions'tan izlenir. |

**Dağıtım image etiketi:** `aptilume:0.3.0`
**Mimariler:** linux/amd64, linux/arm64
**Yerel manifest index:** `sha256:e33921a9332216e07db2f37d1729709672c31c8de87ceed34c0d6b7bfad7909d`
Registry'ye aktarım ve OpenShift deployment kullanıcı ekibine aittir. Registry dönüşümünde digest değişirse o artefact yeniden doğrulanmalıdır.

## Üretim kabulü — kurumda tamamlanacak

| Sorumlu | Gereken kanıt |
|---|---|
| Kimlik / İK | Gerçek AD CA, salt okuma servis hesabı, Base DN, HR/admin grup DN'leri, disabled kullanıcı, iç içe grup ve `manager` ağacı. Adminin öneri/İK onay akışı. İlk kurulum kontrollü işletim ağında yapılmalı; ilk İK eşitlemesinden sonra kilit kalıcıdır. |
| Güvenli erişim | Ayrıcalıklı erişimde kurumsal MFA/koşullu erişim katmanı ve bunun atlanamaması. Uygulamanın doğrudan LDAP parola girişi MFA sağlamaz. |
| OpenShift / ağ | HTTPS Route, doğru PUBLIC_BASE_URL, yalnız gerçek proxy ağlarına FORWARDED_ALLOW_IPS; SCC/dinamik UID/read-only root; ingress/WAF kotaları, egress NetworkPolicy ve host/port/CIDR izin listeleri. Pod probe'ları `/health/*` ile sınanmalı. |
| PKI / DB | AD, LLM ve PostgreSQL gerçek CA/hostname kontrolleri; DB'de verify-full. Bootstrap/migration için ayrı işletim rolü, runtime için gereken tablolarla sınırlı CRUD rolü. |
| Secret / veri | Kalıcı Fernet anahtarı ve güçlü bootstrap parola cluster Secret'tan; Secret/PVC şifreleme, sınırlı erişim, yedek/geri yükleme ve anahtar kaybı/rotasyon prosedürü. Sırları Git'e koymayın. |
| LLM / veri sahibi | Gerçek model kalitesi ve kalibrasyonu, alıntı/kanıt ve prompt-injection denemeleri; çalışan cevaplarının onaylı gateway'e gitmesi, DLP, model sağlayıcısı saklama politikası ve maliyet kotası. Yapılandırma testi model kalitesini kanıtlamaz. |
| SOC / işletim | JSON stdout güvenlik olaylarının SIEM'e alınması, başarısız giriş/yetki/entegrasyon değişimi için alarm ve alarm testi. Varsayılan audit 90 gün, export 7 gün; kurum saklama politikasıyla eşleştirilmeli. |
| QA / güvenlik | Hedef eşzamanlı kullanıcı/worker yükü, gerçek reverse proxy arkasında DAST, yetkili sızma testi, yedekten dönüş ve arıza tatbikatı. Bağımlılık ve image taramaları periyodik tekrarlanmalı. |

Bu dış ortam maddeleri tamamlanmadan kurumun üretim kabulü kapanmış sayılmaz. Kaynak düzeltmeleri bu maddelerin yerine geçmez.

## İşletim notları

- Yerel Compose bilinçli olarak development modundadır ve geçici `admin/admin` hesabını korur. Production bu hesabı reddeder. Mevcut hesap parolası üretimden önce hesap formundan yeni politikaya uygun değiştirilmeli; parolalar sohbetten/Git'ten iletilmemelidir.
- Production DB taşımada yedek alın; API/worker yazmalarını gerçekten durdurun. `storage-migrate --profile-id ID --services-stopped` operatörün durdurma beyanını ister; bayrak servisleri kendisi durdurmaz. Kontrol deposu/anahtar ile hedef DB yetkilerini ayrı değerlendirin. Ayrıntılı sıra README'dedir.
- Paylaşılan üretim kontrol deposu PostgreSQL olmalı; birden fazla pod'un ayrı SQLite dosyası kullanması ortak oturum ve kotayı sağlamaz. SQLite yerel/tek örnek çalışma içindir.
- Export saklama sınırı uygulama yaşam döngüsüdür; yedek ve harici kopyalar için kurumun ayrıca saklama/silme politikası gerekir. Örneklenen anonim ret logları tüm paketlerin eksiksiz ağ kaydı değildir.
- CI'da sabit action/image referansları kullanılır; bu referansların ve CVE verisinin güncellenmesi işletim sorumluluğudur. Gelecekte yeni açık açıklanabilir.

## Referanslar

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [HTTPX — TLS SNI extension](https://www.python-httpx.org/advanced/extensions/)
- [PostgreSQL — host/hostaddr ve TLS bağlantı parametreleri](https://www.postgresql.org/docs/current/libpq-connect.html)
