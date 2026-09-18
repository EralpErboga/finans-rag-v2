# Erişim ve yerel kayıt

18 Eylül 2026 sürümü kişisel hesap kullanır. Önceki ortak uygulama parolası
yeni kullanıcı oluşturmak için kayıt anahtarıdır; doğrudan giriş sağlamaz.
Ekranların kullanımı `docs/KURULUM_VE_KULLANIM.md` içinde açıklanır.

## Kurulum ve saklama

Yeni kurulumda `python setup_access.py` ile 12–256 karakterlik kayıt anahtarı
ve izin verilen ağlar belirlenir. Mevcut `.local/access.json` korunur;
yeniden kurulum gerekmez. Arayüzde **Yeni kullanıcı oluştur** bölümünde
kullanıcı adı, kayıt anahtarı ve iki kez kişisel şifre girilir.

Kullanıcı adı 3–32 karakterdir; a-z, 0-9 ve alt çizgi kabul edilir, büyük
harfler küçültülür. Şifre 12–256 karakterdir. E-posta doğrulaması yoktur.
Kayıt anahtarı `.local/access.json`, kullanıcılar `.local/users.db` içinde
saklanır. Parolalar 16 bayt rastgele tuz, PBKDF2-HMAC-SHA256 ve 600.000
iterasyonla özetlenir. Karşılaştırma `hmac.compare_digest` ile yapılır.
192 bit rastgele kurtarma kodunun da yalnızca tuzlanmış özeti saklanır.
Başarılı işlemden sonra kod gösterilir; bu ekran kapatılınca yeniden gösterilemez.

## Şifre değiştirme ve kurtarma

- Yan panelde **Şifre değiştir** mevcut şifreyi ister; yeni kod üretir ve yeniden girişe yönlendirir.
- **Şifremi unuttum** kullanıcı adı ve kurtarma kodunu ister. Eski kod iptal edilir, yeni kod gösterilir.
- Kod ve şifre birlikte kayıpsa yerel yönetici `.\venv\Scripts\python.exe reset_user_password.py`
  çalıştırır. Kullanıcıyı doğrulama ve yeni kodu güvenli iletme sorumluluğu yöneticidedir.
- `setup_access.py` kayıt anahtarını/ağ ayarını değiştirir; kişisel şifreleri değiştirmez.
- Şifreyi sıfırlamak için kullanıcı veritabanını silmeyin. `.local` dosyalarını paylaşmayın.

## Oturum ve deneme sınırı

Şifre değişikliği/sıfırlama diğer oturumları sonraki etkileşimde geçersizleştirir.
Yapılandırma değişikliği de yeniden giriş ister. 30 dakika hareketsizlik veya
girişten itibaren 8 saat sonrasındaki ilk işlemde oturum kapanır. Süre sonunda
ekranı kendiliğinden karartan bir zamanlayıcı yoktur. Çıkış oturum belleğini temizler.

Giriş, sıfırlama ve şifre değiştirmede işlem türü başına IP ve kullanıcı adı
bazında beş başarısız deneme sınırı vardır. Kayıt anahtarı IP bazında sınırlanır.
Beş dakikalık pencere ilk başarısız denemeden başlar. Sayaçlar SQLite'ta
saklanır; sunucunun yeniden başlaması sınırı kaldırmaz. Başarılı doğrulama
ilgili sayaçları temizler. Aynı IP'yi paylaşan kişiler birlikte etkilenebilir.

## Ağ ve yetki sınırları

`.streamlit/config.toml` sunucuyu 127.0.0.1:8501'e bağlar. Kurulumda ağ alanı
boş bırakılırsa yalnızca loopback adreslerine izin verilir. Streamlit yerel
istemci IP'sini boş döndürdüğünde, yalnızca sunucunun bağlama ayarı gerçek bir
loopback IP ise yerel bağlantı kabul edilir. Ağa açık bağlamada bilinmeyen IP reddedilir.

Kurum ağı için gerçek CIDR, güvenlik duvarı ve güvenilen TLS sertifikası gerekir:

```powershell
.\start_app.ps1 -Address 'SUNUCU_IP' -CertFile 'SERTIFIKA_DOSYASI' -KeyFile 'ANAHTAR_DOSYASI'
```

Yer tutucuları gerçek değerlerle değiştirin. Betik ağ bağlantısında sertifikasız
başlamaz. Doğrudan `streamlit run` bu betik kontrolünü atlayabilir; işletim
sistemi erişimi yalnızca yöneticide olmalıdır. Proxy arkasında istemci IP
güven zinciri ayrıca kurulmalıdır; bu teslimde denenmedi. IP kontrolü
güvenlik duvarının yerine geçmez. Qdrant ve Ollama localhost üzerinde kalır.

Kayıt anahtarını bilen kişi yeni hesap açabilir. Tüm kullanıcılar aynı örnek
mali verilere erişir. MFA, SSO, roller ve hesap silme/devre dışı bırakma
paneli yoktur. Dosyalara yazabilen yerel yönetici hesapları değiştirebilir.
Bu bir yerel prototiptir, kurumsal üretim güvenlik sertifikası değildir.

## Sorgu günlükleri

`logs/queries.jsonl` UTC zamanı, kullanıcı adı, istek/oturum kimliği, soru,
cevap, kanal, kaynak ve süreyi tutar. Eski kayıtlarda kullanıcı adı olmayabilir.
Giriş formlarındaki şifreler ve kurtarma kodları sorgu günlüğüne yazılmaz.
Ayrı başarılı/başarısız giriş olay günlüğü yoktur.

Belirli gizli bilgi kalıpları maskelenir; her hassas veri otomatik tanınamaz.
Metinler 8.000 karakter, kaynaklar 12 öğeyle sınırlıdır. Dosya yaklaşık 1 MiB'de
döner; dört yedek ve güncel dosya tutulur. Gün bazlı saklama politikası yoktur.
Disk hatasında yanıt gösterilir ve kayıt uyarısı çıkar. Çıkış/sohbeti sıfırlama
disk kayıtlarını silmez. Hesap dosyası ve günlükler diskte şifrelenmiş değildir;
Windows erişim izinleriyle korunmalıdır. Günlükler değiştirilmeye karşı imzalı değildir.
