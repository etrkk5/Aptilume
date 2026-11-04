# Aptilume 0.2.0 doğrulama kaydı

4 Kasım 2026. Son kaynak kodu ve Docker imajında çalıştırılan kontroller:

| Kontrol | Sonuç |
|---|---|
| Python testleri | **53 geçti**. Starlette TestClient ve ldap3/pyasn1 için toplam üç bağımlılık kullanım dışı bırakma uyarısı; başarısız test yok. |
| TypeScript + Vite production build | Başarılı; modüler ECharts; büyük bundle uyarısı yok. |
| Oturum | Anonim erişim reddi, Argon2 parola, cookie HttpOnly/SameSite/Secure, CSRF/Origin, oturum rotasyonu, çıkış, parola değişimiyle tüm oturumların iptali, giriş sınırı ve boşta kalma süresi doğrulandı. Arka plan yenilemesi idle süresini uzatmıyor. |
| Çalışan kapsamı | Başkasının atama/form/yanıt/submit adresleriyle erişim engellendi. Kendi profil, sonuç, anket ve gelişim planları doğrulandı. Yönetici/İK başkası adına yanıt gönderemiyor. |
| Yönetici kapsamı | Aynı departmandaki iki yöneticinin kişi kapsamları ayrıldı. Alt yönetici ağacı ve yalnızca doğrudan rapor seçeneği test edildi. Yetkisiz ekip filtresi/dönem oluşturma/ortak dönem kapatma/puanlama/yayın engellendi. |
| Admin ve İK | Entegrasyon admini iş verisi uçlarından 403 alıyor; bootstrap çalışan/ekip/dönem listeleri boş. İK tüm veri ve entegrasyonlara erişebiliyor. |
| Canlı yetki değişimi | Devre dışı hesap, rol değişimi, yönetici değişimi ve AD ayar değişiminden sonra oturum/kapsam yeniden uygulanıyor. İstemci kapsam sürümü değişince eski ekran verisini temizliyor. |
| LDAP | Gerçek ldap3 MOCK_SYNC bind, yanlış parola, filtre kaçışları, GUID/durum alanları, manager döngüsü, grup önceliği ve otomatik yönetici rolü test edildi. LDAPS sertifika doğrulaması zorunlu; referral takip edilmiyor. Dizin kesintisinde süresi dolmuş yetki önbelleği fail-closed çalışıyor. Gerçek kurum AD’si kullanılmadı. |
| Sırlar | AD servis parolası şifreleniyor ve API yanıtlarında yok. Çalışan LDAP parolası saklanmıyor. Bağlantı/servis hesabı değişiminde eski sır başka sunucuya taşınmıyor. Repo kontrolünde runtime DB, anahtar veya token kalıbı bulunmadı. |
| Anket / değerlendirme | 22 soruluk karma form, rol/title snapshot’ı, taslak sürüm çatışması, kapanış sonrası ayrı worker, rubrik matematiği, alıntı kontrolü, teknik hata/sıfır ayrımı, lease ve çift worker kurtarması doğrulandı. |
| Rapor / Excel | Metrikler hesaplanmadan önce kişi kapsamı uygulanıyor. Dosya oluşturma ve indirme kapsamı denetleniyor; yönetici ilişkisi değişince eski dosya indirilemiyor. Excel formül benzeri metinler literal string. |
| Gelişim planları | Oluşturma/düzenleme, kişi/ekip kapsamı, durumu ve optimistic revision çatışması; tarayıcı yenilemesinden sonra kalıcılık doğrulandı. |
| PostgreSQL 16 | Son imajla izole container’da SQLite → PostgreSQL taşıma, katalog, 30 fixture kişi, 3 rol, form, worker, yayın, metrik, oturumlu plan oluşturma/güncelleme ve kapsamlı Excel indirme başarılı. |
| Docker | `aptilume:0.2.0` **linux/amd64 + linux/arm64** olarak üretildi. Manifest index: `sha256:fa490bd8dd0898e37b4d604d0e93456e84bd908e9c341bd322ae1c8bf0f928ad`. |
| Üretim modu container testi | UID **100123:0**, read-only root, tüm capability’ler kapalı, no-new-privileges, yalnızca data/tmp yazılabilir. Temiz kurulum: 42 skill, **0 kişi / 0 ekip**. Üretim admin girişi, Secure cookie, adminin iş verisinden reddi ve dokümantasyon uçlarının kapalı olması doğrulandı. Runtime image’da UI fixture/test login bypass bulunmuyor. |
| Üretim başlangıç sınırları | Varsayılan admin/admin ve eksik şifreleme anahtarı reddediliyor. Güçlü bootstrap parola kabul ediliyor. Üretimde mock LLM ile iş başlatılması engelleniyor. |
| Tarayıcı | Yapı Kredi logosu + Aptilume giriş sayfası; admin/İK/yönetici/çalışan menüleri; alt kullanıcı menüsü ve çıkış; AD formu; gelişim butonları ve karşılaştırma; çalışan form autosave ve yeniden açınca korunması doğrulandı. |
| Temalar | Açık/koyu tema hem giriş sayfası hem uygulama/formlarda incelendi. Seçim sayfa yenilemesinden sonra korunuyor; dar ve geniş yerleşim kontrol edildi. |

## Yerel çalışma durumu

API ve worker `compose.dev.yml` ile `http://127.0.0.1:8080` adresinde çalışır. İlk kurulum hesabı yerelde **admin / admin**; yalnızca entegrasyon ekranına erişir. Mevcut `aptilume_aptilume-data` volume’u korunmuştur; eski örnek veriler otomatik silinmemiştir. Yeni kurulum sentetik kişi/dönem üretmez.

İK/yönetici/çalışan tarayıcı kontrolleri 8090 portunda geçici, izole fixture verisiyle yapıldı. Bu sunucu, PostgreSQL fixture container/network ve kabul testi volume’u doğrulama sonrasında temizlenir. Gerçek uygulama kimlik doğrulamasına test kullanıcısı eklenmez.

## Yeniden çalıştırma

```bash
.venv/bin/python -m pytest
cd web
pnpm build
cd ..
docker buildx build --platform linux/amd64,linux/arm64 --load -t aptilume:0.2.0 .
docker compose -f compose.dev.yml up -d --no-build
```

PostgreSQL harness `tests/check_postgres.py`, yalnızca adı doğrulanan izole fixture host’una bağlanır; kurum veritabanında çalıştırılacak genel bir veri silme/yeniden oluşturma aracı değildir. UI fixture `tests/serve_ui_fixture.py` runtime imajına kopyalanmaz.

## Kurum ortamında kalan kabul

Gerçek AD sunucu/CA/servis hesabı ve rol grup DN’leri admin panelinde girilmeli; kurum hesabı ile giriş, disabled kullanıcı, grup ve `manager` senaryoları kurumda doğrulanmalıdır. Gerçek LLM kalite/kalibrasyonu, OpenShift Route/SCC/Secret/PVC koşulları, yedek/geri dönüş ve hedef eşzamanlı yük henüz kurum ortamında test edilmemiştir. Bu kayıt gerçek endpoint veya cluster kabulünün yapıldığını iddia etmez. Deployment kullanıcı ekibine aittir.
