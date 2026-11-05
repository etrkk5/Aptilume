# İlk kurulum: yerel HR + admin ve PostgreSQL

LDAP hazır olmadan gerçek, boş bir kurumsal kurulum açılabilir. Kullanıcı adları `admin` ve `hr`; parolaları kurulumda Secret'tan verilir. Sentetik kişi/yanıt/puan oluşturulmaz. Admin yalnız entegrasyonları, HR tüm iş alanlarını görür. İki hesap da hesap menüsünden kendi parolasını değiştirebilir.

## Tek Secret

Ad: **`aptilume-secrets`**, tür: **Opaque**. [Doldurulmamış şablon](../deploy/openshift/secret.example.yaml).

| Key | Value |
| --- | --- |
| `BOOTSTRAP_ADMIN_PASSWORD` | `admin` hesabının ilk parolası. |
| `BOOTSTRAP_HR_PASSWORD` | `hr` hesabının ilk parolası. |
| `SECRET_ENCRYPTION_KEY` | Kuruluma özel, kalıcı Fernet anahtarı. |
| `DATABASE_URL` | PostgreSQL kullanıcı, parola, host ve DB içeren bağlantı adresi. |

Parolalar 15–128 karakter olmalı; yaygın/tekrarlı olmamalı, `admin` içermemeli. Aynı parolayı iki hesapta kullanmayın. `BOOTSTRAP_HR_PASSWORD` verilmezse geriye uyumlu olarak yalnız admin oluşturulur. Boş/geçersiz HR parolası verilirse yeni hesapların oluşturulması durur. Parolalar image'a girmez; DB'de Argon2 hash olarak saklanır. Rastgele parola üretip pod'dan geri okumak gerekmez.

Fernet anahtarı projenin Python ortamında bir kez üretilebilir:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`DATABASE_URL` ilk kurulumda hem kontrol tablolarını (hesap/oturum/bağlantı) hem uygulama tablolarını (anket/sonuç) aynı PostgreSQL veritabanına yerleştirir. Veritabanı önceden açılmış olmalı; ilk kurulum kullanıcısı tablo oluşturabilmeli. Bu ayar varken ilk uygulama bağlantısı SQLite oluşturmaz. Ayrı kontrol DB'si istenirse `CONTROL_STORE_URL` önce gelir. PostgreSQL parolasındaki `@`, `:`, `/`, `?`, `#`, `%` gibi karakterler URL-encode edilmelidir.

## Deployment ekibine verilecek kısa akış

1. `aptilume:0.7.0` image'ını build edip kurum registry'sine yükleyin. Secret build sırasında verilmez.
2. `aptilume-secrets` içindeki key'leri **bootstrap, API ve worker** container'larına environment olarak bağlayın. Secret ve pod'lar aynı OpenShift projesinde olmalı.
3. Aşağıdaki normal ortam ayarlarını verin. PostgreSQL CA dosyasını URL'deki yola mount edin. Veri/Excel alanı `/app/data` yazılabilir ve API/worker arasında paylaşılabilir olmalı.
4. İlk açılışta aynı image ile `bootstrap` komutunu bir kez çalıştırıp başarıyla bitmesini bekleyin. Bu işlem tabloları, 42 kaynak yetkinliğini ve iki hesabı hazırlar. Ardından ana container `api`, ayrı worker container `worker` argümanıyla çalışır. Image entrypoint'i zaten `python -m app.cli`; yalnız argümanı değiştirin. Worker'a HTTP probe eklemeyin.
5. Service hedef portu `8080`, dış erişim HTTPS Route olsun. Login ekranında `admin` veya `hr` ve Secret'a yazdığınız parola ile giriş yapın. LDAP zorunlu değildir. Gerçek LLM bağlantısını admin ekler; görevlerde kullanımı HR etkinleştirir. Gerçek endpoint eklenmeden üretimde mock değerlendirme çalışmaz.

Secret'ın container bağlantısı:

```yaml
envFrom:
  - secretRef:
      name: aptilume-secrets
```

Normal ortam ayarları (Secret değildir):

| Ayar | Örnek |
| --- | --- |
| `APP_MODE` | `production` |
| `PUBLIC_BASE_URL` | `https://aptilume.kurum.example` — gerçek Route kök adresi |

İlk kurulumda Secret'taki `DATABASE_URL`, yalnız kendi PostgreSQL host ve portuna erişim izni verir; bu hedef için ayrıca DB host/CIDR listesi girilmez. TLS `verify-full`, DNS/IP sabitleme ve loopback/metadata/özel hedef engelleri korunur. Panelden başka DB hedefi eklemek bu izni genişletmez. İşletim ekibi `DB_ALLOWED_HOSTS` veya `OUTBOUND_ALLOWED_CIDRS` verirse açık ağ politikası önceliklidir ve tam DB hedefi/kurum içi ağı tanımlanmalıdır. Kurum CA'sı standart güven zincirindeyse URL'de `sslrootcert` belirtilmeyebilir. Route/proxy ve sonraki LLM/AD ağ ayarlarının ayrıntıları [README](../README.md#openshift--üretim-ayarları) içindedir.

## Yeniden başlatma ve LDAP

Kalıcı DB, Secret ve `/app/data` korunur. Yeniden başlatma mevcut parolaları, yetkileri, pasifleştirilmiş hesabı veya anketleri sıfırlamaz. `BOOTSTRAP_*` değerleri sadece eksik hesabı ilk kez oluşturur; sonraki Secret değişikliği parola sıfırlamaz. `DATABASE_URL` ilk uygulama bağlantısını hazırlar; sonraki değişiklik mevcut uygulama deposunu kendiliğinden taşımaz veya panelde etkinleştirilmiş bağlantıyı ezmez. Uygulama DB parolası değişirse mevcut profildeki parola da panelden güncellenir; depo taşıması mevcut offline migration sürecini kullanır.

LDAP hazır olduğunda admin panelinden AD bağlantısını ve HR grup eşleştirmesini girin. Kurumsal HR hesabıyla girişi doğrulayın; mevcut yerel hesaplar otomatik silinmez veya kurumsal hesaba dönüştürülmez. Yerel HR hesabının emekliye ayrılması ve admin kurtarma hesabının yönetimi ayrıca planlanır.

Mevcut kurulumların sürüm yükseltmesinde önce yazmaları durdurup `migrate` çalıştırın; `bootstrap` bir sürüm yükseltme/migration aracı değildir. Kurum deployment'ını bu repo otomatik oluşturmaz veya yayınlamaz.
