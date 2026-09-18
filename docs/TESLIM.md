# Finans RAG v2 teslim içeriği

18 Eylül 2026 kaynak paketi; yerel prototip, örnek veriler ve belgeler.

## Paket içeriği

- `app.py`, `src/`: uygulama, hesap yönetimi ve veri motorları.
- `setup_access.py`, `reset_user_password.py`: yerel yönetici araçları.
- `.streamlit/config.toml`, başlatma betikleri ve Docker Compose.
- `requirements.txt`: uyumluluk aralıkları; `requirements-lock.txt`: mevcut Windows/Python 3.11 ortamının sürüm kaydı.
- `data/`: kurgusal Excel ve üç örnek mevzuat metni.
- `docs/`: kurulum/kullanım, teknik rapor, demo senaryosu, doğrulama ve bu teslim notu.
- `test_*.py` ve değerlendirme betikleri: değerlendirmeyi tekrarlamak için.
- `DOSYALAR_SHA256.json`: paket dosyalarının bütünlük özetleri.

ZIP'te `.local`, şifre özeti/kullanıcı veritabanı, gerçek sorgu günlükleri,
kişisel staj defteri, sanal ortam, mali SQLite veritabanı, Qdrant depolaması,
model ağırlıkları ve sertifika/anahtar dosyaları yoktur. Mevcut proje
klasöründeki bu dosyalar silinmez; yalnızca pakete alınmaz.

## Alıcı için sıra

1. ZIP'i ayrı bir klasöre çıkarın; mevcut çalışmanın üzerine açmayın.
2. Kurulum kılavuzunu izleyin, bağımlılıkları ve modelleri indirin.
3. Qdrant'ı başlatıp yalnız yeni kurulum için mevzuatı indeksleyin.
4. Kendi kayıt anahtarınızı belirleyip kendi kişisel hesabınızı oluşturun.
5. Demo senaryosunu ve bilinen sınırlamaları birlikte değerlendirin.

Bu teslim kaynak paketi olarak hazırlandı. Yerel Git deposu oluşturuldu;
uzak depoya veya internete yayın yapılmadı. Gerçek kurum ağında TLS ve güvenlik duvarı kurulumu
bu paketin otomatik gerçekleştirdiği bir işlem değildir.

## Danışmanla netleştirilecek kapsam

Föyde LangChain/LlamaIndex veya CSV desteği zorunluysa mevcut sürümün karşılığı
tam değildir. Özel Python orkestrasyonu ve Excel içe aktarımı kullanılır.
Teknik/idari veri olmadan kesin uyum kararı verilmez. Bu açık noktalar
projenin eksiksiz kurumsal ürün olarak tanıtılmasına engeldir; prototip kapsamı
teknik raporda açıkça belirtilmiştir.

## Hazır sunum ve görsel kılavuz

Teslim paketine 10 slaytlık `docs/teslim/Finans_RAG_v2_Sunum.pptx` ve 8 sayfalık `docs/teslim/Finans_RAG_v2_Ekran_Goruntulu_Kilavuz.pdf` eklendi. Altı gerçek arayüz görüntüsü `docs/ekranlar/` altında bulunur.
