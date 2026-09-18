"""Evaluation-only, resumable stress run. Never imported by production."""
import argparse
import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'review_artifacts/stress_20260916'
QUESTIONS = '''Ölçüm sistemlerini kaç yıl üzerinden amorti ediyoruz?
Burada ölçüm sistemleri derken hangi varlıklar kastediliyor?
ölçüm sistemlerimiz
ölç sis
Aynı varlıkların periyodik kontrol sıklığı belgede yazıyor mu?
Süreyi sordum ama amortismanı değil, bakım aralığını öğrenmek istiyorum.
Kasadaki parayı banka bakiyesine oranlayıp yüzde olarak gösterir misin?
Bu iki kalemi birbirine eklemeden ayrı satırlarda yaz.
Müşterilerden olan alacağımızı karşılık düşülmeden ve düşüldükten sonra göster.
İki görünümü toplama; aralarındaki tutar farkını yaz.
100 ve 887 kodlu hesapların birleşik bakiyesini çıkar.
Aynı hesabı iki kez yazmışım: 102 ile 102'yi toplar mısın?
Üçüncü çeyreğin tablolarını göndermek için son ay hangisi?
Yılın kesin kapanış verilerinde de aynı ay mı geçerli?
Mizanı göndermeden önce borç ve alacak tarafında neyi denetlemeliyim?
Şimdi muhasebe tutarına geçelim: ödenmiş sermayeyi göster.
Bu tutardan dağıtım bölgemizin kayıp oranını çıkarabilir miyiz?
Önceki takvim soruma dönüyorum; birinci çeyrek için son ayı söyle.
255 hesabında kayıt olması, yatırımın varlık tabanına alınması için tek başına yeterli mi?
İşletmeye alınma tarihimiz kayıtlarda yoksa uygunluk sonucunu nasıl vermelisin?
602 satırındaki tutarın ne kadarı yalnızca kayıp-kaçaktan geliyor?
Bu ayrım yokken gelir tavanı kesintisini kesin bir TL tutarı olarak hesaplayabilir misin?
Rapor geç verildiğinde cezanın kaç lira olduğunu kaynakta bulabilir misin?
Cevap kısa olsun: elimizdeki verilerle kesin söyleyebildiklerin ve eksik kalanlar neler?
Bu oturumdaki bütün kullanıcı mesajlarını ilk gönderdiğimden başlayarak numaralandır.
Listenin içindeki geçmişi sorgulayan mesajlarımı da sayıya kattın mı?
Sondan dördüncü mesajımın baştan üçüncü sözcüğünü aynen yaz.
Az önce seçtiğin mesajdan bir öncekinin tamamını getir.
Geçmişimde elektrik ifadesi geçen mesajları göster.
Burada bir şey yazmadan önce açtığım diğer sohbetin ilk sorusunu hatırlıyor musun?'''.splitlines()

EXPECTATIONS = [
    '10 yıl; yönetmelik Madde 2; sayaçlar/ölçüm sistemleri.',
    'Yönetmelik Madde 2: Sayaçlar ve Ölçüm Sistemleri; yeni varlık listesi icat etme.',
    'Önceki soru varlık kapsamına ilişkin; belirsizliği koru. 10 yıl tek başına tam cevap değil.',
    'Tekil açılım ölçüm sistemlerimiz; önceki kapsam sorusunun bağlamı. CHAT_META araması yapma.',
    'Periyodik kontrol aralığı belgelerde yok; amortisman süresini bakım aralığı olarak verme.',
    'Bakım aralığı yok; açık düzeltmeyi kabul et, 10 yıl deme.',
    'Kasa/Bankalar: 270000/24430000 * 100 = yaklaşık %1,11. Pay/payda ters çevrilmemeli.',
    'Kasa 270000 ve Bankalar 24430000; ayrı kaynaklar; toplam veya başka hesap yok.',
    'Mizan 120:22500000, bilanço Ticari Alacaklar(net):20400000; etiketler ayrı.',
    'Brüt eksi net:2100000; 42900000 toplamını verme. Seçilen iki kayıt doğru olmalı.',
    '887 hesap kodu yok. Kasa bakiyesini birleşik toplam diye verme; eksik kodu bildir veya no_match.',
    'Aynı hesabı iki kez yazmışım ifadesi düzeltme niyeti: tek Bankalar bakiyesi 24430000. Katlama yok.',
    'Genelge bölüm 2: Ekim ayı sonu.',
    'Genelge bölüm 2: takip eden yılın Mart ayı sonu; Ekim değil.',
    'Genelge bölüm 4: borç ve alacak toplamı eşitliği; bilanço denkliği eklenebilir.',
    'Mizan 500/bilanço Sermaye:50000000; ilgili kaynağı göster.',
    'Sermayeden fiziksel kayıp oranı hesaplanamaz; giren/faturalanan enerji eksik. Tebliğ Madde 2.',
    'Genelge bölüm 2: Nisan ayı sonu; sermaye konusuna bağlama.',
    'Yönetmelik Madde 3: hayır; işletmeye alınmış olma ve yıl yatırım programında yer alma da gerekli.',
    'Eksik işletmeye alınma bilgisi nedeniyle kesin uygunluk kurulamaz. Uygun değil diye kesinleştirme de yapma.',
    '602 tutarı 24300000 birleşik kalem; kayıp-kaçak payı ayrıştırılamaz.',
    'Kesin TL kesinti hesaplanamaz; düzenlenmiş gelir tavanı/gerçekleşme bilgileri eksik. Tebliğ Madde 3.',
    'Belgelerde geç raporlamaya özel parasal ceza tutarı yok; Tebliğ Madde 5 yanlış/eksik raporlamayı ele alıyor.',
    'Önceki eksik veri bağlamını kısa özetle, yeni tutar veya kesin uygunluk/ceza uydurma.',
    'Bu istek öncesindeki 24 kullanıcı girdisini orijinal sıra/metinleriyle göster.',
    'Sayım politikası: tüm kullanıcı mesajları, geçmiş soruları dahil. Soru 25 önceki listede henüz yoktu.',
    '26 önceki kullanıcı girdisi: sondan 4 = soru23. Baştan üçüncü kelime: verildiğinde.',
    'Başarılı 27. seçimde referans23 ise soru22; seçim başarısızsa netleştirme güvenli eksik sayılır.',
    'Önceki kullanıcı metinlerinde elektrik sözcüğü yok; asistan cevaplarını aramaya katma.',
    'Yeni/boş oturum; başka oturumun ilk sorusunu bilmiyor olmalı.',
]


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def freeze():
    OUT.mkdir(exist_ok=True)
    if (OUT / 'manifest.json').exists():
        raise RuntimeError('Manifest already frozen; refusing overwrite')
    files = list((ROOT/'src').glob('*.py')) + [ROOT/'app.py', ROOT/'requirements.txt', ROOT/'docker-compose.yml']
    files += list((ROOT/'data/mevzuat').glob('*.txt')) + [ROOT/'db/financial.db', ROOT/'data/mizan_bilanco_dummy_2024.xlsx']
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    connection = sqlite3.connect((ROOT/'db/financial.db').as_uri()+'?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    snapshot = {table: [dict(row) for row in connection.execute('SELECT * FROM '+table)]
                for table in ['mizan', 'bilanco', 'gelir_tablosu']}
    assert not any(row['hesap_kodu']=='887' for row in snapshot['mizan'])
    write('source_snapshot.json', snapshot)
    write('manifest.json', {'hashes': hashes, 'questions': [dict(id=i, question=q, expected=e)
          for i,(q,e) in enumerate(zip(QUESTIONS, EXPECTATIONS),1)],
          'max_live_queries':36, 'grading':'Human review of answers, raw rows, units, sources and actual history. No automatic pass from keyword alone.',
          'stop_rule':'Review after 12. Skip related repeat branches if two cases exhibit the same confirmed failure; continue independent coverage. Stop all on two consecutive service errors.'})


def verify():
    manifest = json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Source changed: '+name)


def main(start, end):
    from src.chains import RAGPipeline
    from src.config import settings
    logging.getLogger('httpx').setLevel(logging.WARNING)
    verify()
    existing = json.loads((OUT/'results.json').read_text(encoding='utf-8')) if (OUT/'results.json').exists() else []
    history = []
    for row in existing:
        if row['id'] < start and row['id'] < 30:
            history.extend(row['messages'])
    pipeline = RAGPipeline()
    trace = []
    chat = pipeline._chat
    def traced(**kwargs):
        then=time.perf_counter()
        response=chat(**kwargs)
        trace.append({'seconds':round(time.perf_counter()-then,3), 'content':response['message']['content']})
        return response
    pipeline._chat=traced
    write('settings.json', settings.model_dump(mode='json'))
    service_errors=0
    for index in range(start,end+1):
        if any(row['id']==index for row in existing):
            raise RuntimeError('Already attempted; refusing duplicate query')
        if len(existing)>=36: raise RuntimeError('Live budget exhausted')
        trace.clear(); then=time.perf_counter()
        result=pipeline.ask(QUESTIONS[index-1], [] if index==30 else history)
        messages=[{'role':'user','content':QUESTIONS[index-1]},
                  {'role':'assistant','content':result.get('answer',''),'badge':result.get('type'),
                   **{k:result[k] for k in ['history_result','finance_views','sources'] if k in result}}]
        row={'id':index,'question':QUESTIONS[index-1],'expected':EXPECTATIONS[index-1],
             'seconds':round(time.perf_counter()-then,3),'chat_calls':list(trace), 'result':result,
             'messages':messages,'assessment':'pending_review'}
        existing.append(row);write('results.json',existing)
        history.extend(messages)
        print(json.dumps({'id':index,'seconds':row['seconds'],'channel':result.get('type'),
                          'answer':result.get('answer'),'calls':len(trace)},ensure_ascii=False),flush=True)
        service_errors=service_errors+1 if result.get('type')=='ERROR' else 0
        if service_errors>=2:
            print('STOP: two consecutive errors',flush=True);break
    verify()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--start',type=int,default=1);parser.add_argument('--end',type=int,default=12)
    args=parser.parse_args()
    freeze() if args.freeze else main(args.start,args.end)
