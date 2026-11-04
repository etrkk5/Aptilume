# Aptilume 0.5.0 — düzenlenebilir yetkinlik kataloğu

İK, **Yetkinlik kataloğu** sayfasından yeni yetkinlik ekleyebilir; adını, tanımını, alanını, ailesini, sorumlu birimini, Skill Owner listesini ve L1–L5 seviye ad/tanımlarını değiştirebilir. Kod 1–9999 aralığında benzersizdir ve oluşturulduktan sonra değişmez. Beş seviye birer kez, boş olmayan alanlarla girilmelidir. Yeni yetkinlikler ekip/rol hedeflerinde seçilebilir ve sonraki dönemin AI soru üretimine katılır.

Silme, yetkinliği aktif katalogdan çıkarıp arşive taşır. Arşiv filtresinden geri yüklenebilir; kodu tekrar kullanılamaz. Eski soru, yanıt, gelişim planı ve sonuç ilişkileri silinmez. Ortak ölçüm setinin bağlı olduğu SKILL-001, SKILL-002 ve SKILL-004 düzenlenebilir, ancak soru şablonu bağımlılığı nedeniyle silinemez. Aktif ekip/rol hedefi arşivdeki yetkinliğe bağlıysa yeni dönem oluşturma açıklamalı 409 ile durur: hedefi değiştirin veya yetkinliği geri yükleyin. Önceden oluşturulmuş dönemler üretime devam edebilir.

Her yeni dönem, kullanacağı yetkinliklerin adını, tanımını, beş seviyesini ve katalog sürümünü `Campaign.config.skill_snapshots` içinde sabitler. Mevcut eski dönemlerin eksik snapshot'ı ilk katalog değişikliğinden önce bir defa doldurulur. O tarihten önce başka yollardan yapılmış değişikliklerin kayıp geçmişi üretilmez. Üretim ve form ekranı dönem içeriğini kullanır; henüz yayınlanmamış rapor da dönem adlarını kullanır. Yayınlanmış rapor snapshot'ları değiştirilmez.

Katalog sayfasında kod/ad/tanım araması, aktif/arşiv/tümü filtresi, sayfalama ve dinamik sayaçlar bulunur. Düzenleme/silme/geri yükleme yalnız İK'ya açıktır; bu yetki API'de de kontrol edilir. Yönetici kataloğu okuyabilir; entegrasyon admini iş verisine erişemez. Girdiler tip ve uzunluk sınırlarına tabidir. Değişiklikler actor + önce/sonra kaydıyla denetlenir; sürüm çakışması 409 döner. Eşzamanlı iki eski kayıt yeni sürümü ezemez. Genel auth/CSRF/kota denetimleri sürer.

Ek şema migration'ı yoktur: sürüm/arşiv mevcut Skill metadata JSON alanında, dönem snapshot'ı mevcut config JSON alanında tutulur. 0.4 uygulama/kontrol şema kurulum gereksinimleri geçerlidir. API ve worker birlikte `aptilume:0.5.0` image'a yükseltilmelidir. Mevcut demo hesapları, talimatlar ve veriler korunur.

Katalog doğrulaması sırasında, düzenlenmiş İK talimatının gerçek LLM HTTP isteğine aktarımındaki eksik parametre düzeltildi. Her iki endpoint biçimi için özel/varsayılan system talimatı ve zorunlu güvenlik sözleşmesinin giden istekte birlikte bulunması ayrıca test edilir.
