# Finans RAG v2 kurulum ve kullanım kılavuzu

Bu uygulama kurgusal 2024 mali tabloları ve örnek EPDK metinleri üzerinde çalışan
yerel bir prototiptir. Gerçek mali veya hukuki kararlar için doğrulanmış bir servis değildir.

## Mevcut bilgisayarda kullanım

1. Docker Desktop ve Ollama'yı açın. Qdrant kapalıysa `docker compose up -d qdrant` çalıştırın.
2. Proje terminalinde sanal ortam açıkken `streamlit run app.py` çalıştırın.
3. `http://127.0.0.1:8501` adresini açın.
4. İlk kullanımda **Yeni kullanıcı oluştur** sekmesini seçin. Kayıt anahtarı,
   daha önce belirlediğiniz uygulama parolasıdır. Bir kullanıcı adı seçip yeni
   kişisel şifrenizi iki kez girin.
5. Kurtarma kodunu güvenli yerde saklayın. **Kodu kaydettim, giriş yap** düğmesine
   basın ve kişisel kullanıcı adı/şifrenizle giriş yapın.

Sonraki açılışlarda yeniden kayıt gerekmez. Kullanıcı adı 3–32 karakterdir;
a-z, 0-9 ve alt çizgi kullanılabilir. Şifre 12–256 karakterdir.

## Yeni bilgisayarda ilk kurulum

Python 3.11, Docker Desktop ve Ollama gerekir. İlk bağımlılık/model indirmeleri
internet gerektirir. Model ağırlıkları ZIP'e dahil değildir. Proje 6 GB VRAM'li
bir bilgisayarda geliştirilmiştir; hız ve bellek ihtiyacı CPU/GPU yerleşimine
ve boş RAM'e bağlıdır.

ZIP'i yazma izniniz olan bir klasöre çıkarıp PowerShell'i o klasörde açın:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-lock.txt
docker compose up -d qdrant
```

Ollama zaten çalışıyorsa ikinci kez başlatmayın. Çalışmıyorsa ayrı terminalde:

```powershell
.\start_ollama.ps1
```

Kurulum terminalinde:

```powershell
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull bge-m3
.\venv\Scripts\python.exe -m src.ingest_qdrant
.\venv\Scripts\python.exe setup_access.py
.\venv\Scripts\python.exe -m streamlit run app.py
```

**İndeksleme komutu mevcut BGE-M3 koleksiyonunu silip yeniden oluşturur.** Yalnız
ilk kurulumda veya bilinçli veri yenilemede çalıştırın. Günlük açılış adımı değildir.
Mali SQLite veritabanı ilk uygulama açılışında örnek Excel'den oluşturulur.
Teslim paketi mevcut hesapları ve Qdrant depolamasını içermez.

Kurulumda ağ sorusuna boş Enter yalnızca bu bilgisayara izin verir. Parola
yazarken terminalde karakter görünmemesi normaldir. `setup_access.py` kişisel
şifreyi değil, hesap oluşturmaya izin veren kayıt anahtarını ayarlar.

## Arayüzü kullanma

Sohbet kutusuna sorunuzu yazın. Yanıt altında işlem kanalı ve **Kaynaklar**
alanı bulunur. Mali kaynaklarda hesap/kalem, mevzuatta belge/bölüm gösterilir.
Yan panelde mizan inceleme ve bilanço denkliği kontrolü vardır. SQL veya
uygulama kodu kullanıcıya kaynak olarak gösterilmez.

Örnek sorular:

- Kasa hesabının bakiyesi ne kadar?
- Kasadaki parayı banka bakiyesine oranlayıp yüzde olarak göster.
- Müşterilerden olan alacağımızı karşılık düşülmeden ve düşüldükten sonra göster.
- Üçüncü çeyreğin tablolarını göndermek için son ay hangisi?
- 255 hesabında kayıt olması, yatırımın varlık tabanına alınması için tek başına yeterli mi?

Takip soruları önceki konuşmayla çözümlenir, fakat her ifade doğru anlaşılamayabilir.
Konu yanlış taşınırsa hesap ve işlem adını açıkça yazın. **Sohbet Geçmişini Sıfırla**
yeni konuşma başlatır. `ERROR`, hizmet/işlem hatasıdır; kaynakta bilginin
bulunmaması ile aynı anlama gelmez.

## Hesap işlemleri

| İşlem | Gereken bilgi |
| --- | --- |
| Yeni kullanıcı oluştur | Kayıt anahtarı, kullanıcı adı ve yeni şifre |
| Yan panelde Şifre değiştir | Mevcut şifre ve yeni şifre |
| Girişte Şifremi unuttum | Kullanıcı adı, kurtarma kodu ve yeni şifre |
| Şifre ve kod birlikte kayıp | Yerel yönetici `python reset_user_password.py` çalıştırır |
| Kayıt anahtarı değişikliği | `python setup_access.py`; kişisel şifreler değişmez |

Şifre değiştirme/sıfırlama yeni kurtarma kodu üretir; eski kodu iptal eder.
Diğer açık oturumlar sonraki etkileşimde yeniden giriş ister. 30 dakika
hareketsizlik veya toplam 8 saat sonrasında ilk işlemde oturum kapanır.
**Çıkış yap** oturum belleğini temizler; disk günlüklerini silmez.

## Kapatma ve sorun giderme

Streamlit terminalinde Ctrl+C ile kapatın. Qdrant için `docker compose stop qdrant`
kullanın; veri klasörünü silmeyin. Ollama'yı kendi terminalinden veya masaüstü
uygulamasından kapatın.

| Belirti | Çözüm |
| --- | --- |
| Port 8501 is not available | Önceden açık Streamlit'i kullanın veya Ctrl+C ile kapatın. |
| Ağ adresinden erişime izin verilmiyor | 127.0.0.1:8501 ve proje içindeki `.streamlit/config.toml` dosyasını kullanın; ağa erişimde izinli CIDR gerekir. |
| Giriş başarısız | Kişisel kullanıcı adı/şifre kullanın. Eski ortak parola kayıt anahtarıdır. Beş yanlış denemede beş dakikalık pencereyi bekleyin. |
| Erişim yapılandırılmamış | Proje terminalinde `setup_access.py` çalıştırın. |
| Ollama/model hatası | Ollama'yı açın; `ollama list` içinde iki modelin bulunduğunu kontrol edin. |
| Qdrant/koleksiyon hatası | Docker Desktop ve Qdrant'ı açın. Yeni kurulumda indeksleme adımını tamamlayın. |
| Kaynakta bilgi bulunamadı | Örnek kaynaklarda cevap olmayabilir; bunu bağlantı hatası saymayın. |
| Excel değişti, değerler değişmedi | Dolu veritabanı otomatik yenilenmez; bu sürümde arayüzden veri yenileme yoktur. |

Kurum ağı/HTTPS ve kayıtların ayrıntıları `ACCESS_AND_LOGS.md` içindedir.

Ekran görüntüleriyle adım adım kullanım için [PDF kılavuzunu](teslim/Finans_RAG_v2_Ekran_Goruntulu_Kilavuz.pdf) açın.
