# Aptilume güvenlik incelemesi ve iyileştirme raporu

**İlk inceleme:** 4 Kasım 2026
**İncelenen başlangıç:** `2aa16121c07a80de5f327280274eaf428c7b28ac` (0.2.0)
**Durum:** İlk bulgular kaydedildi; aşağıdaki düzeltmeler henüz uygulanmadı.

## Karar

0.2.0, gerçek çalışan verisiyle üretime açılmamalıdır. Entegrasyon yöneticisinin kimlik politikası ve veri aktarımı üzerindeki yetkileri, ekrandaki “iş verisine erişemez” sınırını dolaylı yoldan aşmaktadır. İzole testlerde bu durum ve diğer koruma eksikleri yeniden üretildi. Bu rapor önce bulguları kaydeder; düzeltme ve doğrulama sonuçları ayrı bir sonuç kaydında tutulacaktır.

İnceleme kaynak kod, oturum/RBAC, AD güven sınırı, sır yönetimi, LLM/DB dış bağlantıları, girdi/çıktı boyutları, dosya çıktıları, bağımlılıklar ve container varsayılanlarını kapsar. Kurumun gerçek AD/LLM/OpenShift ortamında sızma testi veya denetim sertifikası değildir. “Hiç açık yok” garantisi sunmaz.

## Kanıtlanan bulgular

| ID | Öncelik | Bulgu ve kanıt | Yapılacak düzeltme |
|---|---|---|---|
| SEC-01 | Kritik | Entegrasyon admini `PUT /admin/directory` ile İK grubunu değiştirebiliyor (HTTP 200). AD grup/kimlik/yönetici politikası bu rolün kendi yetkisini büyütmesine imkân veriyor. | İlk güvenli kurulum sonrasında AD değişikliklerini İK onayına bağla; onaysız öneri aktif politikayı değiştirmesin. İlk İK kurulumu tamamlandıktan sonra bootstrap yetkisini geri açma. |
| SEC-02 | Yüksek | İş verisine erişemeyen admin `POST /admin/db-connections/{id}/activate` ile 30 fixture çalışanı başka DB’ye kopyalayabildi (HTTP 200). LLM görevini de kendi eklediği profile bağlayabiliyor. | Veri taşıyan LLM etkinleştirmesini veri sahibi İK rolüyle sınırla. Üretimde web üzerinden canlı DB taşımasını kapat; kontrollü çevrimdışı işletim komutu sağla. |
| SEC-03 | Yüksek | LLM endpointi değiştirildiğinde eski şifreli anahtar yeni hedefe taşınıyor. Serbest `config.secret` alanı düz metin olarak saklanıp geri dönüyor. | Bağlantı alanlarını izin listeli şemalarla doğrula; sırları yalnızca şifreli secret kanalında kabul et. Hedef/hesap değiştiğinde sırrın tekrar girilmesini zorunlu kıl. |
| SEC-04 | Yüksek | Yanlış `APP_MODE=prodution` sessizce geliştirme moduna dönüyor. Docker varsayılanı geliştirme. Üretim PostgreSQL profili `sslmode=disable` kabul ediyor. | Geçersiz modda başlangıcı reddet; image varsayılanını üretim yap. HTTPS/public origin ve PostgreSQL sertifika/host doğrulamasını üretim için zorunlu kıl. |
| SEC-05 | Yüksek | Aynı hesaba altı farklı IP’den yanlış parola denemesi altı kez 401 döndürüyor; hesap bazlı engel yok. Sayım ve deneme rezervasyonu atomik değil. Her başarılı AD girişi tam dizin eşitlemesi başlatıyor. | Hesap/IP bazlı atomik, kalıcı kotalar; parola doğrulama eşzamanlılık sınırı; güçlü parola; başarılı girişte TTL içinde toplu AD taramasını tekrarlamama. |
| SEC-06 | Yüksek | LLM için DNS doğrulaması ve bağlantı ayrı çözümleme yapıyor; DNS değişimi aralığı var. IPv4-mapped IPv6 ve ortam proxy’si güven sınırı açıkça ele alınmamış. DB/LDAP hedefleri işletim izin listesiyle kısıtlı değil. | Hedef host/port/IP ağlarını işletim izin listesiyle sınırla; bağlantıyı doğrulanmış IP’ye sabitle, TLS SNI/host doğrulamasını koru; metadata/loopback eşdeğerlerini reddet; örtük proxy’yi kapat. |
| SEC-07 | Orta | 2 MiB ek JSON içeren login isteği kabul edildi (HTTP 200). LLM yanıtı tamamen belleğe alınıyor; export oluşturma/kullanıcı oturum sayısı ve çağrı boyutları sınırsız. | Akış boyunca istek ve LLM yanıt boyutu sınırı, mutasyon/export kotaları, oturum üst sınırı ve sınırlı model çıktısı. |
| SEC-08 | Orta | İstek gövdesi ve bağlantı parametrelerinde çok sayıda serbest dict var. Hatalı şekiller 500’e gidebiliyor; varsayılan doğrulama yanıtları girilen değerleri yansıtıyor. | Tipli ve boyut sınırlı girişler; tutarlı 4xx; parola/anahtarları hata yanıtından çıkar; geçersiz sayısal değerleri ve bilinmeyen alanları reddet. |
| SEC-09 | Orta | Host doğrulanmıyor. `Host: untrusted.example` ve aynı Origin ile login kabul edildi (HTTP 200); izin verilen origin istek Host’undan türetiliyor. | Üretimde sabit PUBLIC_BASE_URL/izinli Host doğrulaması; güvenilmeyen Host/Origin ve cookie gölgelemesini engelle; hata yanıtlarında da koruma başlıkları. |
| SEC-10 | Orta | İnceleme kararı yalnızca yayımlanmış koşuyu engelliyor; pending olmayan karar yeniden yazılabiliyor, eşzamanlı karar ve kişinin kendi puanını onaylaması açıkça engellenmiyor. | Kararı yalnızca bekleyen inceleme için atomik uygula; kendi yanıtını incelemeyi reddet; model çıktısını tip/boyut/sonlu sayı ve beklenen kanıt türüyle doğrula. |
| SEC-11 | Orta | Güvenlik reddi, başarısız giriş, hassas yapılandırma ve dosya indirmeleri için merkezi, aktör/korelasyon içeren güvenlik izi eksik. | Parola/anahtar/yanıt metni içermeyen yapılandırılmış güvenlik olayları ve yetkili izleme görünümü; temel saklama/temizleme işi. |
| SEC-12 | Düşük | Excel dosyası indirilirken hash’i yeniden doğrulanmıyor; dosya saklama süresi tanımlı değil. Runtime bağımlılıklarında pytest var; image taban etiketleri değişebilir. | Export dizini/hash/dosyatürü kontrolü; saklama süresi; geliştirme paketlerini runtime’dan ayır; sabit image digestleri ve otomatik güvenlik kontrolleri. |

Kanıtlar yalnızca geçici SQLite dosyaları ve sentetik verilerle üretildi. Gerçek sunucuya kaba kuvvet, saldırı veya veri aktarımı yapılmadı. Test parolaları gerçek kurum sırrı değildir.

## Başlangıçta başarılı olan kontroller

- 53 mevcut test: kayıt bazlı çalışan/yönetici/İK kapsamı, atama IDOR, CSRF, logout ve export kapsamı gibi kontrolleri kapsıyor. Yeni bulgular bu testlerin kapsamı dışındadır.
- Python kilit dosyasında pip-audit ve web production paketlerinde pnpm audit, sorgulama anında bilinen bir açık bildirmedi. Bu sonuç kod mantığı veya gelecekteki CVE’ler için güvence değildir.
- Bandit: tüm arayüzlere API bind edilmesi (container için gerekli), açık geliştirme parolası ve iki sayısal puan dizesi işaretlendi. Tek başına istismar kanıtı sayılmadı; üretim/geliştirme ayrımı ayrıca sertleştirilecek.
- React metin kaçışları, LDAP filtre kaçışları, doğrulanan LDAPS/StartTLS, şifreli servis sırları ve değişmez yayımlanmış sonuçlar mevcut.

## Uygulama sırası

1. Kimlik politikası ve veri aktarımındaki yetki ayrımını düzelt.
2. Güvenli ortam varsayılanları, sabit origin, bağlantı hedefleri ve sır doğrulamasını uygula.
3. Oturum/parola/kaynak tüketimi kotaları, tipli giriş ve LLM çıktı sınırlarını ekle.
4. İnceleme bütünlüğü, güvenlik izi ve dosya yaşam döngüsünü tamamla.
5. Her bulgu için kötüye kullanım regresyon testi çalıştır; bağımlılık/container taramalarını tekrarla; Docker ve PostgreSQL akışını doğrula.

## Kurum ortamında zorunlu kabul

Gerçek AD grup üyelikleri ve manager ağacı, TLS/CA ve ağ çıkış politikası, ayrıcalıklı hesaplar için kurumsal MFA/koşullu erişim, Secret/PVC şifreleme/yedek, SIEM alarmı, Route/proxy ayarları ve yetkili DAST/sızma testi kurum ortamında doğrulanmalıdır. Doğrudan LDAP parola girişi tek başına MFA sağlamaz. Bu maddeler onaylanmadan “üretim kabulü tamamlandı” denemez.

## Referanslar

- [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html): hesap bazlı giriş denemesi sınırı ve ayrıcalıklı işlem koruması.
- [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html): hedef/ağ izin listeleri ve DNS/redirect sınırları.
- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html): sabit kaynak doğrulaması.
- [OWASP Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html): güvenlik olayları ve gizli verilerin logdan çıkarılması.
