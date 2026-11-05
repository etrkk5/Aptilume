# Aptilume 0.6.0 — AI soru setine İK düzenlemesi ve yayın

5 Kasım 2026. AI, dönemin sabitlenmiş ekip/rol/yetkinlik bağlamından başlangıç sorularını üretmeye devam eder. Üretilen set **İçerik incelemesi** durumuna gelir; çalışanlara atanmaz.

## İK akışı

1. **Ölçüm dönemleri → Soruları düzenle ve yayınla** ekranını açın.
2. Ortak soru setini veya bir ekip/rol grubunu seçin. Ortak soru tek kayıt olarak tutulur; o dönemin tüm rol formlarında aynıdır.
3. Soru ekleyin, mevcut soruyu kopyalayın, düzenleyin veya silin. Metin, yetkinlik, grup, soru türü, seçenekler/doğru cevap, değerlendirme referansı, kanıt türü ve açık uçlu sorunun ölçüt adı/ağırlığı/davranış/0–4 puan açıklamaları düzenlenebilir. Yetkinlikler dönemin sabitlenmiş hedefleriyle sınırlıdır. Çalışan doğru cevabı veya rubriği görmez.
4. **Soruyu kaydet** ile değişikliği kalıcı taslağa yazın. Kaydetme LLM çağırmaz. Yayın şartlarını henüz sağlamayan taslak saklanabilir; eksikler editörde listelenir.
5. **Seti onayla** yalnızca yayına hazır hale getirir. **Onayla ve yayınla** son özeti gösterir; onaydan sonra çalışan formlarını oluşturur ve yanıt toplamayı açar. Onaylanmış sette tekrar düzenleme yapılırsa onay kalkar ve set içerik incelemesine döner.
6. Yayımdan sonra soru değiştirme/ekleme/silme API'de engellenir. Yeni içerik için yeni dönem gerekir. Yanıt gönderimi puanlamayı başlatmaz; değerlendirme yine dönem kapanınca worker'da yürür.

İK düzenleme/onay/yayın yetkisine sahiptir. Yönetici kendi tam kapsamındaki dönemleri oluşturabilir, AI üretimini başlatabilir ve soru setini salt okunur inceleyebilir; İK onayı ve yayını bekler. Çalışan/entegrasyon admini soru seti yazarak veya cevap anahtarına erişerek kapsamı aşamaz.

## Kapsam ve ölçüm kuralları

AI başlangıç üretimi 22 sorudur; İK sonrasında sayı değişebilir. Katılımcı başına en fazla 60 soru vardır. Her hedef yetkinlikte en az bir açık uçlu soru ve tam bir öz beyan sorusu korunur. Tek seçim soruları isteğe bağlıdır; 2–6 seçenek ve tam bir doğru cevap gerekir. Öz beyan L1–L5 ve deneyimim yok eşlemesini korur. Açık uçlu rubrikler L1–L3 göstergelerini, pozitif ağırlıkları ve 0–4 puan açıklamalarını içerir. Tüm atanmış sorular zorunludur.

Yazılı puan ve kapsamın paydası gerçekten atanmış açık uçlu sorulardır. Bir veya üç açık uçlu soruda sabit iki soruluk varsayım kullanılmaz. Seviye önerisi yine en az iki ayrı sorudan destek gerektirir; tek yazılı soruda puan olsa da seviye üretilmez. L4/L5 bu anketle doğrulanmaz. Öz beyan ve çoktan seçmeli puanları ayrı göstergelerdir. Soru/rubrik içeriğinin hash'i karşılaştırma grubu izine eklenir; farklı düzenlenmiş setler aynı içerik sayılmaz. Eski yayınlanmış snapshot'lar yeniden yazılmaz.

## Sürüm, audit ve API

Aynı seti iki İK kullanıcısı düzenlediğinde veya düzenleme/yayın çakıştığında dönem satırı üzerinde atomik kilit/sürüm kontrolü uygulanır; eski kayıt 409 alır. Soru değişiklikleri, önce/sonra içerik, aktör ve set sürümüyle audit'e yazılır. Onay izi ve soru içeriği hash'leri yayın snapshot'ına taşınır. Onaylanan son set ile dağıtılan sorular aynı işlem sınırında korunur.

- `GET /api/v1/campaigns/{id}/question-set`: yetkili inceleme görünümü, dönem `version`, içerik `revision`, gruplar, sorular ve yayın eksikleri.
- `POST /api/v1/campaigns/{id}/questions`: ekleme; `PATCH .../questions/{qid}`: düzenleme. Gövde `expected_version` içerir.
- `DELETE .../questions/{qid}?expected_version=N`: atanmamış taslak soruyu siler; audit içeriği korunur. Başka döneme ait soru ID'si kabul edilmez.
- `POST .../approve` ve `POST .../open`: yalnız İK; gövde `{"expected_version": N}` zorunludur. Önceki sürümün gövdesiz HTTP çağrıları güncellenmelidir. Onay/yayın cevabındaki `row_version` sonraki işlemin beklenen sürümüdür.

Yeni şema migration'ı yoktur; mevcut dönem config, row_version, soru version ve audit alanları kullanılır. API ile worker birlikte `aptilume:0.6.0` image'a güncellenir. Önceki 0.4 şema kurulumu gereksinimleri sürer. Kurum AD/LLM/CA, ölçüm kalibrasyonu, OpenShift ve kurum güvenlik kabulü ayrıca yapılmalıdır.
