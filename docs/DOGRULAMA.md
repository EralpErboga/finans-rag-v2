# Doğrulama sonuçları ve kapsamı

## 18 Eylül 2026 hesap özelliği

`python -m unittest test_accounts test_access_audit -q` komutu 13 kontrolde
başarıyla tamamlandı (52,366 saniye). Gerçek hesaplara dokunulmadı; geçici
veritabanları kullanıldı. Canlı model yanıtı üretilmedi.

Kontroller: kayıt anahtarı yetkilendirmesi, kullanıcı adı normalizasyonu ve
benzersizliği, şifre/kodun düz metin saklanmaması, yanlış mevcut şifre,
şifre değişimi, kurtarma kodu rotasyonu ve yeniden kullanımın reddi,
sıfırlama/giriş deneme sınırı, sunucu yeniden başladığında sayacın korunması,
süre dolumu, hesaplar arası izolasyon, oturum süreleri ve iptali.

Streamlit AppTest ile kayıt → kod ekranı → giriş → şifre değiştirme → kodla
sıfırlama → yeniden giriş → çıkış akışı geçti. Yerel IP'nin boş dönmesi yalnızca
loopback bağlamada kabul edildi; ağa açık bağlamada reddedildi. Ek kontroller
eksik yapılandırma, yasak ağ, günlük maskeleme ve boyut döndürmesini kapsadı.
AppTest gerçek tarayıcı/ağ/TLS veya yük testi değildir.

## Önceki doğruluk çalışmaları

17 Eylül'de hesap özelliği öncesindeki 101 otomatik kontrol geçti. Bu sayı yeni
özellik sonrasında tekrar çalıştırılmış toplam olarak sunulmaz. Son canlı
değerlendirmede 30 sorunun çıktısı kaydedildi. Önceki oran, brüt/net, tarih ve
geçmiş seçim sorunlarında iyileşme görüldü; bazı hibrit yanıtlar eksik kaldı.
Özellikle 20. soruda mali hesap bağlamı kayboldu, bazı yanıtlarda genel sonuç
ve ilgisiz ek madde vardı. Bu nedenle 30/30 hatasız iddiası yoktur.

16 Eylül başlangıç stres sonucu 11 başarılı, 3 güvenli eksik, 16 hatalıydı.
Bu rapor geçmiş sonuçları silmez veya yeni sürümün sonucu gibi göstermez.
