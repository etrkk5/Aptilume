# Aptilume 0.4.0 — raporlama, İK talimatları ve yanıt kalitesi

## Yeni form ve soru üretimi

**Ölçüm dönemleri → Yeni ölçüm dönemi** ekranında hedef ekipler seçilir. “Tüm ekipler” yalnız kullanıcının yetkili olduğu ekipleri seçer/kaldırır; kısmi seçimde seçilen ekip sayısı görünür. Seçilen ekip bağlamı, unvan, kademe, rol profili ve yetkinlik hedefleri döneme sabitlenir.

**Soruları hazırla** ayrı bir iş başlatır. Gerçek LLM endpointi bağlıysa her rol profili için bu bağlamla sorular/rubrikler üretilir. Ortak sorular rolden bağımsızdır ve aynı dönem içinde tüm rollere aynı set atanır; role özel sorular ilgili rolün hedeflerinden gelir. İK/yönetici içerik onayından sonra dönem açılır ve kişilere atanmış rol formu sunulur. Her kişiye rastgele farklı bir ortak sınav verilmez.

Şu anki soru dağılımı sabittir: 22 soru; 12 açık uçlu, 4 bilgi kontrolü, 6 öz değerlendirme. Soru içeriği ve rol setleri dinamiktir. Demo motoru deterministik örnekler üretir; gerçek LLM kalitesi veya talimat değişikliğinin dilsel etkisi mock sonuçlardan çıkarılamaz. Yeni bir dönem oluşturmak mevcut formları ve yayımlanmış sonuçları değiştirmez.

## İK'nın düzenlediği ölçüm politikası

Yalnız İK'nın gördüğü **Ölçüm politikası** ekranında soru üretimi, yanıt değerlendirme/kalite kontrolü ve sonuç özeti talimatları aynı sayfada düzenlenir. Mevcut talimatlar `data/default-instructions.json` dosyasından ilk kurulumda kontrol deposuna v1 olarak yüklenir. Bu, demo ve production için aynı varsayılandır. Politika metni çalışanların veya entegrasyon admininin eriştiği API'lerden okunamaz.

- Her kaydetme yeni ve değişmez bir sürüm oluşturur; eski sürüm güncellenmez/silinmez.
- Eşzamanlı İK düzenlemelerinde `expected_version` kontrolü eski taslağın yeni kararı ezmesini engeller.
- “Varsayılanları taslağa al” henüz aktif politikayı değiştirmez; ayrıca kaydetmek gerekir.
- Geçmiş bir sürüm taslağa yüklenip yeni sürüm olarak kaydedilebilir.
- Talimat sınırı bölüm başına 30–5.000 karakterdir. API gövde sınırı ve politika kayıt kotaları da geçerlidir.
- Ekip metinleri ve çalışan cevapları veri olarak ele alınır. Kimlik/yetki, JSON şeması, puan aralığı, soru dağılımı, kanıt doğrulaması ve İK inceleme zorunluluğu talimatla değiştirilemez.

Soru üretimi kuyruğa alınırken politika sürümü iş kaydına bağlanır. Değerlendirme başlatılırken sürüm `RunPolicy` kaydına ve puanlama işlerine sabitlenir; dönem özeti aynı sürümle üretilir. Politika sonradan değişse bile başlamış işler bu sürümü kullanır. Yayımlanan snapshot soru üretimi/değerlendirme sürümlerini taşır; **Rapor bilgileri** bunları gösterir. Eski sürümlerde kaydedilmemiş talimat geçmişi için yeni bir sürüm uydurulmaz.

## Zorunlu sorular ve kalite incelemesi

Tüm sorular zorunludur. Düzenlenebilir formda eksik sayfadan ilerlenemez; gönderimde ilk eksik soruya dönülür. Sunucu, tüm atanmış sorularda görünür metin veya geçerli seçim bulunmasını ayrıca denetler. Taslak kaydı boş olabilir; formun teslimi boş olamaz. “Deneyimim yok” şeklinde dürüst beyan ve öz değerlendirmedeki deneyimim-yok seçeneği geçerlidir.

Kalite analizi anket doldurulurken veya gönderildiğinde çalışmaz. **Dönem kapandıktan sonraki worker değerlendirmesinde** her açık yanıt için modelden şu sınıflar istenir:

| Sınıf | İşlem |
|---|---|
| Soruya ilişkin / deneyim-bilgi eksikliğini açıkça beyan | Rubrik değerlendirmesi; dürüst deneyimsizlik anlamsız yanıt sayılmaz. |
| Anlamlı içerik bulunamadı | İK ön inceleme etiketi |
| Soruyla ilgisiz | İK ön inceleme etiketi |
| Değerlendirme için yetersiz içerik | İK ön inceleme etiketi |
| Model talimatını yönlendirme içeren yanıt | İK ön inceleme etiketi |

Model sınıfı, Türkçe gerekçe ve yanıttan kısa alıntılar tipli şemayla doğrulanır. Yanıtta olmayan alıntılar kanıt olarak gösterilmez. Boş/tekrarlı harf/klavye örüntüsü gibi belirgin durumlarda ek temel içerik kontrolü vardır. Kısa ama anlamlı yanıt yalnız uzunluğu nedeniyle reddedilmez. Anlamsal alaka kontrolünün kalitesi kurumun gerçek LLM'siyle kalibre edilmelidir; mock yalnız belirgin örüntüleri simüle eder.

Kalite sorunu olan değerlendirmede `score=None` tutulur, sonuç otomatik sıfıra çevrilmez. Dayanıklı **Yanıt kalitesi** kaydı oluşturulur ve İK menüsünde bekleyen kayıt sayısı gösterilir. Liste dönem/ekip/durumla filtrelenir, sayfalanır ve otomatik yenilenir. İK soru, yanıt, etiket, gerekçe ve kanıtı inceleyip açık bir 0–100 puan kararı ve gerekçe kaydeder. Kendi yanıtına karar veremez. Entegrasyon admini/çalışan/yönetici bu İK kuyruğunu açamaz; yönetici kendi kapsamındaki değerlendirmede İK kararı gerektiğini görebilir, kalite puanını onaylayamaz.

Bekleyen kalite/diğer zorunlu incelemeler bitmeden değerlendirme yayımlanamaz. Karar atomiktir; tekrar/paralel karar kabul edilmez. Etiket ve özgün kanıt korunur; geçmiş İK kararı detayda gösterilir. Etiket bir kişilik, niyet, performans veya disiplin hükmü değildir. Bildirim uygulama içindeki İK kuyruğudur; dışarıya e-posta/mesaj gönderilmez.

## Rapor filtreleri ve metrikler

Dönem ve ekip seçimine ek olarak unvan/rol, yetkinlik, ortak/role özel bölüm, kademe ve yanıt durumu filtrelenir. Önce oturumun kişi kapsamı uygulanır; filtre seçenekleri dahi bu kapsamdan çıkarılır. Çalışan kendisini, yönetici güncel AD manager ağacını, İK kurum genelini görür. Filtreleme yeni LLM çağrısı yapmaz.

- Ortak puan ortalaması/medyanı, kişi başına üç ortak yetkinliğin ortalamasıdır. Farklı rol rubrikleri tek bir genel başarı puanında birleştirilmez.
- Yetkinlik seçildiğinde paydada o soruların gerçekten atandığı çalışanlar kalır; yalnız cevap verenler sayılarak katılım şişirilmez. Unvan/kademe dönem açılışındaki sabit profilden okunur.
- Ortak puan ve dağılım seçili çalışan kapsamının referans ölçütüdür. Yetkinlik/bölüm filtresi seviye, hedef ve yetkinlik tablosunu daraltır. Yetkinlik filtresi uygulanabilir çalışan kapsamını da daraltabilir.
- Katılım: gönderildi/taslak/başlamadı sayıları. Puan veya yeterlilik değildir.
- Puan dağılımı: her kişi bir kez sayılır; puan bandı yeterlilik seviyesi değildir.
- Seviye dağılımı kişi-yetkinlik gözlemidir. Anket L1–L3 önerir; L4/L5 ölçülmüş sayılmaz. Seviye üretilemeyenler ayrıca gösterilir.
- Hedefe ulaşma oranı yalnız seviye üretilebilen L1–L3 hedef gözlemleri içindir. Ölçüm kapsamı ayrıca `ölçülebilen / yanıtı olan uygun hedef gözlemi` olarak gösterilir; yanıtlamayanlar katılım metriğinde ayrıca izlenir. Kısmi ölçümdeki %100 tüm çalışanların hedefe ulaştığı anlamına gelmez.
- Toplu puan, seviye, dağılım ve hedef metrikleri için en az 5 **farklı kişi** gerekir; satır sayısı bu kuralı aşamaz. Eksik/bastırılmış metrik sıfır değildir.

Ekip ortak puanı, yığılmış katılım grafiği, puan histogramı, seviye dağılımı, hedef farkı ve yetkinlik puan çubukları birlikte sunulur. Grafiklerde erişilebilir veri tabloları bulunur. Profiller aranabilir, sıralanabilir ve sayfalanabilir. Yetkinlik satırından gelişim planı açılabilir. Açık/koyu tema ve dar ekran desteklenir. Sağ üstte tekrarlanan logo kaldırılmıştır.

Excel aynı filtreleri ve hesaplamayı kullanır; ekip katılımı, puan/seviye dağılımı, karşılaştırma grubu ve metodoloji sayfalarını içerir. Filtreli dışa aktarımda kurum geneli LLM önerileri yanlışlıkla taşınmaz.

## Dağıtım / yükseltme

Image `aptilume:0.4.0`; API ve worker birlikte güncellenmelidir. Yedek ve durdurulmuş yazmalarla operatör migration/kurulum sırasını izleyin. `0003`, uygulama DB'sine kalite kayıtları ve değerlendirme-politika bağlantısını ekler; kontrol deposunda `prompt_policies` ve aktif sürüm ayarı kurulum yetkisiyle oluşturulur. Runtime rolü yeni tablolar için de gereken CRUD yetkilerine sahip olmalıdır; DDL yetkisi runtime'a verilmez. Mevcut formlar/sonuçlar yeniden yazılmaz.

Demo için isteğe bağlı, ek ve tekrarlanabilir örnek:

```bash
docker compose -f compose.dev.yml exec -T api python -m app.cli demo-quality-sample
```

Bu komut yalnız `APP_MODE=demo` ile çalışır. “Yanıt Kalitesi · Örnek” adlı kapalı bir dönem ve İK kararını bekleyen sentetik yanıt oluşturur; yayımlamaz. Demo hesap parolalarını değiştirmez. Production bu komutu reddeder. Gerçek AD/LLM/CA, MFA, OpenShift/ağ/SIEM ve kurum sızma/yük kabulü şartları devam eder.
