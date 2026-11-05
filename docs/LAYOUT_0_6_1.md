# Aptilume 0.6.1 — yerleşim ve taşma kontrolü

5 Kasım 2026. JavaScript/React ve ECharts mimarisi korunur. Python paketi ve Docker image aynı kaynak arayüzünü içerir; Node.js yalnız izinli build ortamında kullanılır.

## Bulunan ve düzeltilen durumlar

- 375 px ekranda soru editörü grup seçimi, modalın 351 px iç alanını 447 px'e genişletiyordu. Grid sütunu ve seçim alanının minimum/iç genişliği düzeltildi; içerik kesilmeden satıra bölünür.
- Kesintisiz uzun başlık/soru/rol/yetkinlik adları, grid ve flex öğelerinin içerik genişliğini zorluyordu. Metin kırılması, sıfırlanabilir minimum genişlikler ve sabit ikon alanlarıyla kartlar/pencereler sınırlarında tutulur. İkonlar metin tarafından sıkıştırılmaz.
- 320 px ekranda genel görünüm ve anket listesindeki dönem/ekip filtreleri sayfayı 359 px'e genişletiyordu. Filtre kutusu ve içindeki seçim alanı kalan genişliğe uyar.
- Çalışan formunda uzun dönem adı, tek satırlık etiket ve grid minimumu nedeniyle 320 px ekranda sayfayı 1311 px'e genişletebiliyordu. Etiket artık satıra bölünür; form sütunu ve yan panel ekran genişliğine uyar.
- Soru kartının koyu temadaki alt kenarlık rengi düzeltildi.

## Tarayıcı doğrulaması

Codex in-app browser üzerinde normal demo verileri ve ayrı geçici test deposuyla 118 geometri ölçümü yapıldı; hata bulunan durumlar düzeltmelerden sonra tekrarlandı. Son 0.6.1 sunumunda beş viewport daha kontrol edildi: 320/375/768/1280/1440 px genişliklerin tamamında sayfa ve modal iç genişliği sınırlar içinde, ekran dışındaki kontrol sayısı sıfırdı. Gerçek sunum kayıtları test verileriyle değiştirilmedi.

Ölçüler: 320×568, 375×812, 640×360, 768×900/1024, 1280×600 ve 1440×900. Bu ölçüler tarayıcı viewport'udur; belirli bir fiziksel telefon veya tüm tarayıcılar için test iddiası değildir.

Kontrol edilen alanlar:

- Giriş; genel görünüm/rapor filtreleri; dönem kartları; ekip/rol hedefleri; yetkinlik kataloğu; anket listesi ve formu; gelişim planları; profil; değerlendirmeler; kalite kuyruğu; talimatlar; bağlantı ayarları.
- Soru seti; açık uçlu/tek seçim/öz beyan düzenleme; uzun değerlendirme referansının açılması; yayın onayı; katalog ve ekip düzenleme pencereleri.
- Açık ve koyu tema. Veri sınırlarını zorlamak için 200 karakter kesintisiz başlık/rol/yetkinlik adları, 150 karakter ekip adı, 4.400 karakter soru ve uzun referans/seçenek metinleri kullanıldı.

Son kontrollerde sayfanın yatay genişliği viewport'u aşmadı; soru editörünün iç alanında yatay kayma, ekran dışına çıkan alan/düğme veya yatay kesilen başlık/metin bulunmadı. Pencere, kapatma ve alt işlem düğmeleri ekran içinde kaldı; kısa ekranda içerik dikey kaydırılarak okunur. Geniş tablolar kendi kutularında yatay kaydırılır; bu sayfa taşması sayılmaz ve korunmuştur.

Bu sürüm CSS yerleşimi ve sürüm/paket belgelerini değiştirir. İş akışı, JavaScript bağımlılıkları, yetkiler, puanlama, veri şeması ve LLM davranışı değiştirilmez. TypeScript/Vite production build başarılıdır; mevcut CI regresyonları ayrıca çalıştırır.

## Local / OpenShift arayüz eşitliği

0.6.1 Python ZIP paketindeki yedi `web/dist` dosyasının SHA-256 değerleri hem linux/amd64 hem linux/arm64 Docker image içindeki dosyalarla birebir karşılaştırıldı ve eşleşti. JavaScript/React kodu aynı kalır; Node.js yalnız build ortamında kullanılır. Demo/production kimlik, bağlantı ve veri ayarları mevcut parametrelerden seçilir.
