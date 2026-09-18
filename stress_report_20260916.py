"""Reviewed findings; keep raw answers and frozen expectations intact."""
from collections import Counter
import json
import statistics
from stress_test_20260916 import OUT, verify, write

# Human assessment of answers AND source rows. No keyword-only success grading.
NOTES = {
1:('hatalı','Mevzuat sorusu FINANCE; kaynakta olmayan 6 yıl üretildi. Beklenen 10 yıl.'),
2:('hatalı','Sayaç/ölçüm kapsamı yerine ilgisiz bilanço başlıkları ve tutarlar verildi.'),
3:('hatalı','Önceki yanlış finans bağlamı sürdü; ölçüm sistemleri diğer dönen varlıklara eşitlendi.'),
4:('hatalı','Kısaltma genişledi ancak yanlış FINANCE kanalı ve ilgisiz varlık kayıtları korundu.'),
5:('hatalı','Periyodik kontrol sıklığı yerine varlık tutarları döndü; kaynakta bulunmama açıklanmadı.'),
6:('hatalı','Açık bakım/amortisman düzeltmesine rağmen ilgisiz finans tutarları tekrarlandı.'),
7:('geçti','Kasa/Bankalar doğru yönde hesaplandı: %1,11; iki ham değer ve kaynak doğru.'),
8:('güvenli eksik','Takipteki iki kalem çözülemedi; plan hatası olarak güvenli netleştirme verildi. Servis arızası değil.'),
9:('hatalı','Brüt ve net yerine karşılık ile brüt karşılaştırıldı; -20.400.000 TL üretildi.'),
10:('hatalı','Alacak görünümleri yerine Kasa ile TOPLAM AKTİF karşılaştırıldı.'),
11:('geçti','887 kodu yok; 100 hesabını kısmi birleşik toplam diye sunmadan no_match verildi.'),
12:('geçti','Yinelenen 102 kodu ikiye katlanmadı: 24.430.000 TL.'),
13:('hatalı','Kaynakta Ekim ayı sonu yazarken Ocak cevabı verildi; kaynak gösterilmesi hatayı engellemedi.'),
14:('hatalı','Takipte Mart ayı sonu yerine Kasa ve sosyal güvenlik borcu anlatıldı.'),
15:('hatalı','Borç/alacak toplam eşitliği kuralı yerine alıcılar ve satıcılar hesapları toplandı.'),
16:('hatalı','50.000.000 TL sermaye tutarı doğru ancak eski soru taşınarak borç/alacak denetimi diye yanlış açıklandı.'),
17:('hatalı','Fiziksel kayıp oranının hesaplanamayacağını belirtmek yerine alacak kalemleri toplandı.'),
18:('güvenli eksik','Takvim konusuna dönüş geçmiş yönetimi sanıldı; Nisan yerine netleştirme istendi.'),
19:('geçti','Tek hesap kaydının yeterli olmadığı, işletmeye alma ve yatırım programı koşulları kaynaklı belirtildi.'),
20:('hatalı','Eksik işletmeye alınma bilgisinin uygunluğu etkilemeyeceği iddia edildi.'),
21:('geçti','602 birleşik tutarı 24.300.000 TL gösterildi; alt gelirlerin ayrıştırılamadığı açıklandı.'),
22:('geçti','Kesin parasal etki hesaplanamadığı belirtildi; kaynakta olmayan kesinti üretilmedi.'),
23:('geçti','Geç raporlamaya özel parasal tutar uydurulmadı; net hüküm bulunmadığı belirtildi.'),
24:('hatalı','Eksik bilgi özetini istemek ilk kullanıcı sorusunu getirme işlemine dönüştü.'),
25:('geçti','24 önceki kullanıcı mesajı, geçmiş yönetimi sorusu dahil, sıra ve metinleriyle listelendi.'),
26:('hatalı','Sayım politikasını sormak geçmişi sorgulayan ifadesini arama işlemine dönüştü.'),
27:('geçti','26 geçmiş mesaj üzerinden sondan dördüncü=23; baştan üçüncü sözcük verildiğinde.'),
28:('güvenli eksik','Geçerli seçim referansı23 varken önceki mesaj22 getirilemedi; açıklama istendi.'),
29:('geçti','Kullanıcı geçmişinde elektrik ifadesi yok; asistan metinlerinden yanlış eşleşme eklenmedi.'),
30:('geçti','Boş oturumda başka oturumun ilk sorusu ifşa edilmedi veya uydurulmadı.'),
}


def main():
    verify()
    rows=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    assessed=[]
    for row in rows:
        status,note=NOTES.get(row['id'],('inceleme bekliyor','Henüz değerlendirilmedi'))
        assessed.append({'id':row['id'],'status':status,'note':note})
    write('assessments.json',assessed)
    counts=Counter(a['status'] for a in assessed)
    lines=['# Yeni ifadelerle stres testi sonuçları','',
           'Bu çalışma seçilmiş zorlayıcı senaryoları değerlendirir; genel doğruluk yüzdesi veya yük kapasitesi ölçümü değildir.',
           'Uygulama kodu ve kaynak veriler test boyunca değiştirilmedi; başlangıç/son SHA-256 kontrolleri eşleşti.', '',
           '## Ana akış', '', f"Tamamlanan soru: {len(rows)}. Sonuçlar: {dict(counts)}.",
           'Yanıtların sayıları, anlamları, ham kayıtları ve kaynakları birlikte incelendi. Modelin ERROR etiketi her zaman servis arızası değildir; geçersiz planlar güvenli eksik olarak ayrıldı.', '',
           '| No | Sonuç | Bulgu |','| --- | --- | --- |']
    lines += [f"| {a['id']} | {a['status']} | {a['note']} |" for a in assessed]
    times=[r['seconds'] for r in rows]
    lines += ['', '## Süre ve kapsam', '',
              f"Ana akış toplam sorgu süresi {sum(times):.2f} saniye; ortanca {statistics.median(times):.2f}; en uzun {max(times):.2f} saniye.",
              f"Ana akıştaki yerel chat çağrısı sayısı: {sum(len(r['chat_calls']) for r in rows)}. Embedding çağrıları bu sayıya dahil değildir.",
              'İlk 29 soru gerçek üretilmiş yanıtlarla sürdürülen tek oturumdur. 30. soru boş oturumda soruldu. İlk 12 sonrasında sonuçlar incelendi; farklı alan kapsamına devam edildi, başarısız sorular tekrarlanmadı.', '',
              '## Kanıt dosyaları', '',
              '- manifest.json: çalışmadan önce sabitlenmiş beklentiler ve kaynak/kod özetleri.',
              '- source_snapshot.json: salt okunur SQLite kaynak satırları; Excel eşitliği ayrıca doğrulandı.',
              '- results.json: her soru, tam yanıt, kaynaklar, ham mali kayıtlar, gerçek geçmiş ve model çıktıları.',
              '- technical.txt: altı modelsiz teknik kontrol; 6/6 geçti. Gerçek servisler kapatılmadı.',
              '- context_probes.json: dört kontrollü modelsiz bağlam deneyi; canlı model cevabı değildir.',
              '- paraphrases.json: iki ayrı canlı ifade karşılaştırması.', '',
              '## Öncelikli düzeltme alanları', '',
              '1. Tam emir/düzeltme cümlelerini eski soruyla birleştirmeme; takip referansını son ilgili sonuçtan çözme.',
              '2. Mevzuat/finans ayrımında amorti etme, raporlama ve eksik bilgi ifadeleri; yanlış kanalın geçmişe yayılmasını sınırlama.',
              '3. Mali anlatımda ek sayı ve yanlış anlam üretimini engelleme; brüt/net karşılığı için doğru kalem çifti.',
              '4. Tarih ve uygunluk iddialarını kaynakla doğrulama; yalnız sayısal metin korumasının yetersizliği.',
              'Bu rapor bir düzeltme çalışması değildir. Başarısız cevaplara göre üretim promptları veya veri indeksi değiştirilmedi.']
    comparisons=json.loads((OUT/'paraphrases.json').read_text(encoding='utf-8'))
    lines += ['', '## Altı ek bağlam ve tutarlılık kontrolü', '',
              '| Kontrol | Sonuç ve kapsam |','| --- | --- |',
              '| C1 Tekrarlanan kısaltma | Modelsiz incelemede tekil genişleme kayboldu, yönlendiriciye iki çağrı yapıldı. Canlı cevabın yanlışlığı bu deneyle kanıtlanmadı. |',
              '| C2 İki olası açılım | Otomatik genişletme birini seçmedi. Sonraki model kararının doğruluğu bu modelsiz deneyin kapsamı dışında. |',
              '| C3 Aynı kanalda konu değişimi | Kısaltılmış varlık son raporlama tarihi sorusuyla birleştirildi. Kullanıcı niyeti belirsizse yanlış özellik taşıma riski var; bu deney tek başına yanlış cevabı kanıtlamaz. |',
              '| C4 Kanal değişimi | Eski mevzuat konusu otomatik seçilmedi; yeni finans bağlamı model yoluna aktarıldı. Son yanıt test edilmedi. |',
              '| C5 Mali ifade değişimi | Canlı cevap doğru ve Q7 ile tutarlı: %1,11, aynı kaynak tutarları. |',
              '| C6 Mevzuat ifade değişimi | Yeni ifade canlıda 10 yıl verdi. Q1 ise 6 yıl vermişti; tek cevap doğru, iki ifade arasında tutarlılık testi başarısız. |', '',
              'İlk dört kontrol kontrollü, kanal etiketli yapay geçmişlerle modelsiz yürütüldü; gerçek cevap üretimi diye raporlanmıyor. Son ikisi canlı çalıştı. Böylece 30 ana + 6 bağlam/tutarlılık + 6 teknik = 42 planlı senaryo ele alındı; bunların 32 tanesi canlı kullanıcı sorgusudur.',
              f"İki ek canlı sorgu toplam {sum(c['seconds'] for c in comparisons):.2f} saniye. Tüm 32 sorgunun süre toplamı {sum(times)+sum(c['seconds'] for c in comparisons):.2f} saniye; hazırlık ve insan inceleme süresi hariçtir.",
              'Sıcak/soğuk model koşulları eşitlenmedi. Bu çalışma hız optimizasyonu karşılaştırması veya eşzamanlı yük testi değildir. Sorgu sayısı model çağrısı sayısı değildir; bir sorgu birkaç model çağrısı yapabilir.', '',
              '## Değerlendirme sınırı', '',
              'Sorular özellikle zorlayıcı seçildi; sonuç yüzdesi genel kullanım doğruluğu değildir. Aynı oturumda ilk yanlış yanıt sonraki sonuçları etkilediği için 16 hatalı cevap 16 bağımsız kök neden demek değildir. Doğru sayıyla yanlış açıklama yapan Q16 da hatalı sayıldı. ERROR etiketiyle güvenli netleştirme yapan Q8 servis arızası diye sayılmadı.',
              'Tam kaynaklı görünen cevap da yanlış olabilir: Q13 kaynaklar arasında doğru genelgeyi gösterirken Ocak dedi; belgede Ekim yazıyor. Bu nedenle kaynak varlığı tek başına başarı ölçütü yapılmadı.']
    (OUT/'RAPOR.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(dict(counts))


if __name__=='__main__':main()
