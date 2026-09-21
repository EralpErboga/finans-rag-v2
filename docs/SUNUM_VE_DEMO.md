# Finans RAG v2 sunum ve demo senaryosu

Hedef süre 8–10 dakika. Çalışan akışlar ile sınırlarını birlikte gösterin.
Yanıt beklerken gecikmenin donanım/model yüklemesine bağlı olduğunu açıklayın;
sabit yanıt süresi veya yüzde yüz doğruluk vaat etmeyin.

## 1 Problem ve amaç yaklaşık 1 dakika

“Mali tabloları doğrudan dil modeline verip hesap yaptırmak yanlış tutarlara
yol açabiliyor. Bu projede aritmetiği kodla, mevzuat aramasını kaynak getirerek
yürüttüm. Kullanılan şirket verisi ve mevzuat metinleri eğitim amaçlı kurgusal.”

## 2 Mimari yaklaşık 1 dakika

Streamlit → yönlendirme → mali katalog/SQLite veya BGE-M3/Qdrant → kaynaklı
yanıt akışını anlatın. Qwen2.5 soruyu yorumlar; Python hesaplar. HYBRID iki
kanıt türünü bir araya getirir. Orkestrasyonun özel Python olduğunu belirtin.

## 3 Kullanıcı ve güvenlik yaklaşık 1 dakika

Girişte üç sekmeyi gösterin: giriş, yeni kullanıcı ve şifremi unuttum.
Kayıt anahtarının hesap açmayı sınırladığını, kurtarma kodunun şifre sıfırlamak
için gerektiğini anlatın. Önceden oluşturduğunuz demo hesabıyla giriş yapın.
Gerçek kayıt anahtarını veya kurtarma kodunu canlı ekranda göstermeyin.
Yan panelde Şifre değiştir bölümünü gösterin; şifreyi değiştirmeniz gerekmez.

## 4 Mali veri demosu yaklaşık 2 dakika

Yeni sohbet açıp sırasıyla sorun:

| Soru | Gösterilecek nokta |
| --- | --- |
| Kasa hesabının bakiyesi ne kadar? | Örnek kayıtta 270.000 TL ve hesap kaynağı |
| Kasadaki parayı banka bakiyesine oranlayıp yüzde olarak göster. | 270.000 / 24.430.000 × 100 ≈ yüzde 1,11 |
| Bu iki kalemi birbirine eklemeden ayrı satırlarda yaz. | Takip bağlamı, ayrı mali kayıtlar |
| Müşterilerden olan alacağımızı karşılık düşülmeden ve düşüldükten sonra göster. | 22.500.000 TL brüt, 20.400.000 TL net |
| İki görünümü toplama; aralarındaki tutar farkını yaz. | 2.100.000 TL fark |

Kaynaklar bölümünü açın. Bunların uygulamaya yazılmış hazır cevaplar değil,
örnek kaynak kayıtlarından hesaplanan değerler olduğunu açıklayın.

## 5 Mevzuat ve eksik bilgi yaklaşık 2 dakika

“Üçüncü çeyreğin tablolarını göndermek için son ay hangisi?” sorusunda kurgusal
kaynakta Ekim ayı sonunu gösterin. Ardından:

“255 hesabında kayıt olması, yatırımın varlık tabanına alınması için tek başına yeterli mi?”

Demirbaşlar bakiyesi ile işletmeye alınma/yatırım programı koşullarını ayırın.
“Muhasebe kaydı, teknik ve idari koşulların kanıtlandığı anlamına gelmez” deyin.
“Rapor geç verildiğinde cezanın kaç lira olduğunu kaynakta bulabilir misin?”
sorusuyla belgede olmayan ceza tutarının üretilmemesini gösterin.

## 6 Bulgular ve gelecek çalışmalar yaklaşık 1 dakika

“İlk stres testinde bağlam ve hesap seçimi hataları gördüm. Oran, brüt/net,
tarih ve geçmiş mesaj işlemlerinde düzeltmeler yaptım. Bazı hibrit takipler
ve kaynak seçimi hâlâ eksik. Testlerin geçmesi tüm doğal dil sorularında
kusursuzluk demek değil.”

101 otomatik test sonucunun 17 Eylül sürümüne ait olduğunu; kişisel hesap
özelliğinin ayrıca 13 modelsiz kontrolle değerlendirildiğini belirtin.
Gerçek veri, kurumsal HTTPS, rol bazlı yetki ve daha geniş değerlendirmeyi
gelecek çalışma olarak sunun. Çıkış yaparak bitirin.

## Sunum öncesi hazırlık

Docker/Ollama açık, tek Streamlit süreci çalışıyor ve demo hesabı hazır olsun.
Şifreleri ve kişisel dosyaları ekran paylaşımından uzak tutun. Teknik raporla
kılavuzu hazır bulundurun. Servis hatasında tekrar tekrar model çalıştırmak
yerine durumu açıklayıp kayıtlı çıktılara geçin. Kayıtlı sonucu canlı üretimmiş
gibi sunmayın.

Hazır sunum: [14 slaytlık PowerPoint dosyası](teslim/Finans_RAG_v2_Sunum.pptx).
