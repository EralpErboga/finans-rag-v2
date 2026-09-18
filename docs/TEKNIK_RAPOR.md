# Finans RAG v2 teknik raporu

Bu çalışmadaki amacım, mali hesaplamaları kaynaklı mevzuat yanıtlarıyla aynı arayüzde birleştirmek. Sayısal işlemler için Python hesaplamalarını, metin yorumlama ve kaynak seçimi için yerel dil modelini kullanıyorum.

Sürüm tarihi: 18 Eylül 2026. Proje, yerel dil modeliyle soru yorumlamasını,
veritabanı sorgularını ve kaynaklı mevzuat yanıtlarını birleştirir. Veriler
kurgusaldır; çalışma üretime hazır bir kurumsal uyum sistemi değildir.

## Amaç ve mimari

Amaç mali aritmetiği dil modelinden ayırmak, mevzuat yanıtlarını getirilen
kaynaklarla ilişkilendirmektir. Streamlit önce ağ ve hesap kontrolünü uygular.
Girişten sonra `RAGPipeline` soruyu ve oturum geçmişini işler.

```text
Tarayıcı → Ağ denetimi → Kişisel hesap → Streamlit → RAGPipeline
  FINANCE   → Katalog ve işlem planı → SQLite/Python → Mali bulgu
  MEVZUAT   → BGE-M3/Qdrant → Yeniden sıralama → Kaynak pasajları
  HYBRID    → Mali bulgu + kaynak koşulları + veri yeterliliği sınırı
  CHAT_META → Geçmiş işlem planı → Python sıra/kelime/arama işlemleri
  Sonuç    → Kaynak gösterimi ve yerel sorgu günlüğü
```

Konu dışı sorular `OUT_OF_SCOPE`, belirsiz takipler `CLARIFY`, hizmet/işlem
hataları `ERROR` olarak ayrılır. Özel Python orkestrasyonu kullanılır;
LangChain/LlamaIndex kullanılmaz.

| Bileşen | Uygulama |
| --- | --- |
| Arayüz | Streamlit, app.py |
| Dil modeli | Ollama, qwen2.5:7b-instruct-q4_K_M |
| Embedding | BGE-M3, 1024 boyut |
| Vektör veritabanı | Qdrant, kosinüs benzerliği |
| Mali veri | Pandas/OpenPyXL içe aktarımı, SQLite |
| Model sınırları | 2048 bağlam, 768 üretim, 120 saniye zaman aşımı |
| Hesaplar | SQLite, PBKDF2-HMAC-SHA256, kurtarma kodu |
| Kayıt | Kullanıcı adına bağlı yerel JSONL |

## Mali hesaplama

Excel'in mizan, bilanço ve gelir tablosu bölümleri normalize edilerek içe
aktarılır. Dolu veritabanı başlangıçta yeniden yüklenmez. Model katalog
kimlikleriyle `lookup`, `sum`, `compare`, `ratio` veya `balance_check` işlemi
seçer. Plan doğrulanır; aritmetik Python ile yapılır. Model yürütülebilir SQL
üretmez. Sorgulama katmanında salt okunur erişim ve parametreli sorgular kullanılır.

Açık hesap kodları doğrulanır; bulunmayan kod sessizce atlanarak toplam verilmez.
Brüt/net etiketleri ayrılır; desteklenen takipler seçilmiş kayıt kimliklerini
korur. Doğru hesabın her doğal dil ifadesinde seçilmesi garanti değildir.
Kodla aritmetik, doğal dil yorumlamasını kusursuz kılmaz.

## Mevzuat ve hibrit akış

Metinler MADDE başlıklarından bölünür; fıkralar madde bloğunda kalır. MADDE
başlığı içermeyen genelgeler daha geniş bloklarda kalabilir. Qdrant'taki ilk
20 aday, BM25 benzeri leksikal puan ve yoğun benzerliğin 0,65/0,35 ağırlıklı
birleşimiyle sıralanır. Sözcüklerin ilk beş karakterinin eşleştirilmesi tam bir
Türkçe kök çözümleyici değildir ve CPU belleği kullanır.

Etiketli sayısal hükümler kaynak metinden alınır. Diğer hükümlerde modelin
seçtiği pasaj kimlikleri doğrulanıp pasajlar doğrudan gösterilir. İstenen
koşulla hükmün eşleşmesi kontrol edilir. Buna rağmen ilgili maddenin bulunamaması
veya ilgisiz ek pasajların seçilmesi mümkündür.

HYBRID çıktısı mali kayıt, mevzuat koşulları ve veri yeterliliği açıklamasını
birleştirir. Veritabanında teknik ölçüm, işletmeye alınma veya idari onay
bulunmadığından kesin uygunluk/ceza hesabı üretilmez. Eksik veri, koşulun
sağlanmadığının da kanıtı değildir.

## Hesap güvenliği

Kayıt anahtarını bilen kişi kişisel hesap açabilir. Parola ve kurtarma kodu
ayrı 16 bayt tuzlarla, 600.000 iterasyon PBKDF2-HMAC-SHA256 kullanılarak
özetlenir. Kurtarma kodu 192 bit rastgelelik taşır. Şifre değişimi/sıfırlama
eski kodu iptal eder; hesap sürümü değişerek diğer oturumları sonraki işlemde
geçersizleştirir. 8 saat toplam, 30 dakika hareketsizlik sınırı uygulanır.
Başarısız deneme sayaçları SQLite'ta kalıcıdır.

Tüm hesaplar aynı veri yetkisine sahiptir; roller, MFA ve SSO yoktur. Sunucu
varsayılan olarak yalnızca 127.0.0.1'de dinler. Kurum ağı için TLS, güvenlik
duvarı ve istemci IP güven zinciri gerekir. Hesap dosyası/günlükler disk
şifrelemesi sağlamaz. Yerel yönetici yetkisi güven sınırıdır.

Sorgu günlüğü kullanıcı adı, oturum, soru, cevap, kaynak ve süreyi tutar.
Parola formları bu günlüğe yazılmaz. Belirli gizli bilgi kalıpları maskelenir;
kayıtlar imzalı değildir ve ayrı giriş olay günlüğü bulunmaz.

## Değerlendirme ve sınırlar

16 Eylül'deki 30 soruluk stres testinde 11 başarı, 3 güvenli eksik ve 16 hata
vardı. 17 Eylül'de 101 otomatik kontrol geçti; bu kişisel hesap özelliğinden
önceki sürümdür. Son 30 soruluk canlı akışta oran, brüt/net, tarih ve geçmiş
seçiminde düzeltmeler görüldü. Ancak 20. soruda mali bağlam kaybı ve bazı
hibrit cevaplarda genel açıklama/ilgisiz ek madde kaldı. “30/30 kusursuz”
sonucu çıkarılmadı. Tarihli ayrıntılar `DOGRULAMA.md` içindedir.

12 soruluk embedding değerlendirmesinde yeniden sıralama sonrası ilk kaynak
BGE-M3 için 12/12, Nomic için 11/12 idi. Bu küçük örneklem tüm Türkçe mevzuat
sorularındaki üstünlüğü kanıtlamaz; model yükleme koşulları eşitlenmediğinden
süreler kesin hız karşılaştırması olarak kullanılamaz.

Teslimde açık kalanlar:

- Serbest Türkçe hesap seçimi, kısa takipler ve kaynak ilgililiği her zaman doğru değildir.
- Teknik/idari sonuçlar için gerçek ek veri gerekir.
- CSV içe aktarma ve arayüzden veri yenileme yoktur.
- E-posta sıfırlama, MFA, SSO ve rol bazlı yetkilendirme yoktur.
- Gerçek kurum ağı/TLS, çok süreçli dağıtım ve tamamen internetsiz son sürüm demosu yapılmadı.
- Qdrant Compose etiketi `latest` olduğu için konteyner sürümü sabitlenmiş değildir.
- Föyde LangChain/LlamaIndex zorunluysa özel orkestrasyonun kabulü danışmanla netleştirilmelidir.
