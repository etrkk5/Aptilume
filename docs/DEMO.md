# Aptilume — 5 Kasım 2026 sunum rehberi

## Başlatma ve mod seçimi

Sunum modu, üretim kimlik doğrulamasını gevşetmeden ayrı bir veri alanı kullanır. Tek seçim parametresi `APP_MODE` değeridir:

| Değer | Davranış |
|---|---|
| `demo` | DATA_DIR/presentation-demo altında ayrı SQLite depoları, yerel anahtar, rastgele parolalı dört rol, 30 sentetik çalışan, 42 yetkinlik, yayımlanmış sonuçlar ve açık anket. LLM mock çalışır; sunum için gerçek endpoint gerekmez. |
| `production` | Normal/kurumsal depolar, gerçek AD/LLM, HTTPS/CA, kalıcı Secret ve güçlü ilk parola kuralları. Demo kimlikleri, demo deposu ve mock değerlendirme reddedilir. Varsayılan mod budur. |
| `development` / `test` | Geliştirme/test davranışı; sunum hesapları otomatik açılmaz. |

Yerel `.env` içinde `APP_MODE=demo` seçin. Güncel `aptilume:0.4.0` image ile:

```bash
docker compose -f compose.dev.yml up -d --no-build
docker compose -f compose.dev.yml exec -T api python -m app.cli demo-accounts
```

Uygulama: http://127.0.0.1:8080/ . Parolalar ilk kurulumda oluşturulur; üstteki komut yalnızca demo modunda aynı parolaları gösterir. Yeniden başlatma sunum düzenlemelerini veya anket taslaklarını sıfırlamaz. Parolalar web ekranında/API'de/loglarda yoktur; işletim erişimi olan kişi demo-access.json dosyasına erişebilir. Sadece demo deposunda düz metin kurtarma kopyası, DB'de Argon2 hash bulunur. Bu dosya ve runtime Git/Docker build bağlamı dışında tutulur.

## Hesapların kapsamı

| Kullanıcı | Rol | Gösterilecek ekranlar |
|---|---|---|
| `hr` | İnsan kaynakları | 3 ekip / 30 çalışan, kurum özeti, dönemler, değerlendirmeler, Excel, gelişim planları, bağlantı ve güvenlik olayları. |
| `manager` | Yönetici | Data & Analytics ekibi; kendisi dahil 10 profil, ekip hedefleri, sonuç ve gelişim planları. Diğer 20 çalışan ve entegrasyon ayarları kapalı. |
| `employee` | Çalışan | Data & Analytics içindeki Ekin; yalnız kendi profili, anketi, sonuçları ve gelişim planı. |
| `admin` | Entegrasyon admini | Yalnız bağlantı ayarları; çalışan/ekip/sonuç verisi kapalı. Bu modda admin/admin geçersizdir; üretilen demo parolasını kullanın. |

Girişler gerçek oturum, CSRF, hesap kotası ve sunucu tarafı kapsam kontrollerinden geçer. Menü değiştirme veya görünmeyen bir test giriş adresi kullanılmaz. Aynı tarayıcıdaki sekmeler aynı oturumu paylaşır; roller arasında sağ alttaki/sol bardaki hesap menüsünden çıkış yapın. İki rolü aynı anda göstermek için ayrı tarayıcı profili veya gizli pencere kullanın.

## Önerilen sunum sırası

1. `hr` ile başlayın. Yayımlanmış **AI Skills Baseline · Kasım 2026** sonuçlarını, katılımı ve yetkinlik haritasını gösterin. Rapor bilgileri ve Excel metodolojisi sentetik/mock kaynağı belirtir.
2. `manager` ile Data & Analytics kapsamını, ekip bağlamı/hedeflerini ve gelişim planı oluşturmayı gösterin.
3. `employee` ile kendi profilini ve **AI Readiness Pulse · Pilot** anketini açın. Bir açık yanıt yazıp sayfayı yenileyerek taslağın korunduğunu gösterin. Sunum sonunda formun durumunu değiştirmek istemiyorsanız göndermeyin.
4. `admin` ile LLM ve DB profillerini gösterin. Gerçek kurum endpointi/sırrı girmeyin; sunumda mevcut mock bağlantı yeterlidir. Adminin iş verisini göremediğini anlatın.
5. İstenirse `hr` ile yeni dönem → soru üretimi → onay/açılış → yanıt → kapanış → ayrı toplu değerlendirme → yayın akışını uygulayın. Soru/puanlar deterministik mock sonuçlarıdır; gerçek model kalitesini kanıtlamaz.

Ana ekranda demo etiketi veya ek logo eklenmez; Yapı Kredi markası ve Aptilume görünümü korunur. Güvenlik incelemesi raporları önceki sürüme aittir; bu sürüm demo ayrımı için ek regresyonlarla doğrulanmıştır.

## Üretime geçiş

Kurum ayarları hazır olduğunda `APP_MODE=production` yapıp bootstrap, API ve worker süreçlerini yeniden başlatın. Mod değişikliği canlı süreçte otomatik uygulanmaz. OpenShift'te aynı değer yeni pod'ların ortamına verilir; dağıtımı kurum ekibi yürütür.

Demo modunda üretim `CONTROL_STORE_URL` ve `SECRET_ENCRYPTION_KEY` kullanılmaz; üretime dönünce normal ayarlar devreye girer. Demo verisi/hesabı üretime kopyalanmaz. Üretim deposuna yanlışlıkla demo kimliği kopyalanırsa API ve worker başlangıcı engellenir. Ayrı ortamlar için ayrı PVC/Secret kullanılması önerilir.

Tek parametre modu seçer; gerçek AD, LLM, DB/CA, PUBLIC_BASE_URL, kalıcı anahtar, güçlü bootstrap parola, ağ/MFA ve kurum kabulünün yerini almaz. Önceki geliştirme deposunda admin/admin varsa üretim başlangıcı onu reddeder. Yerel Compose kurumsal deployment şablonu değildir. Güvenlik kabul listesi [SECURITY_REMEDIATION.md](SECURITY_REMEDIATION.md) içindedir.

## 0.4.0 sunumuna eklenenler

- İK: Ölçüm politikası sayfasında varsayılan soru/değerlendirme talimatlarını gösterin. Düzenleme taslaktır; yeni sürüm olarak kaydedilince yeni işlere uygulanır.
- İK: Yanıt kalitesi menüsünde “Yanıt Kalitesi · Örnek” sentetik kaydını inceleyin. Karar kaydetmeden modalı kapatırsanız sunumda bekleyen örnek korunur. Gerekirse `demo-quality-sample` komutu örneği yalnız bir kez ekler.
- Yeni ölçüm: “Tüm ekipler” ile toplu seçim/kaldırma; ayrıca tek tek seçim.
- Çalışan: Tüm sorular zorunlu; boş sayfadan ilerleme engellenir. “Deneyimim yok” dürüst ve geçerli bir yanıttır.
- Dashboard: Ekip/rol/yetkinlik/bölüm filtrelerini ve “Diğer filtreler” alanını gösterin; Excel seçili kapsamı taşır. Oranları yorumlarken geçerli kişi sayısını ve hedef ölçüm kapsamını birlikte okuyun.

Detaylı akış ve yükseltme: [0.4.0 özellikleri](FEATURES_0_4.md).
