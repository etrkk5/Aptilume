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
