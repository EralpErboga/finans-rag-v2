"""Additional wording/negative cases, separate from production prompts and data."""
import json
import time
from pathlib import Path
from src.chains import RAGPipeline


CASES = [
    ('SCADA sistemleri kaç yılda amorti edilir?', 'MEVZUAT', ['5 yıl'], ['10 yıl']),
    ('İkinci çeyrek mali tablolarının son bildirim ayını yaz.', 'MEVZUAT', ['Temmuz'], ['Ekim']),
    ('Kesin yıl sonu verileri için son bildirim zamanı nedir?', 'MEVZUAT', ['Mart'], ['Temmuz']),
    ('Sayaçların kalibrasyon aralığı kaynaklarda belirtilmiş mi?', 'MEVZUAT', [], ['10 yıl']),
    ('Bankalar bakiyesini kasa bakiyesine bölüp yüzdeyle açıkla.', 'FINANCE', ['%9048,15'], ['%1,11']),
    ('Bu iki kalemi toplama; ayrı ayrı göster.', 'FINANCE', ['24.430.000,00 TL', '270.000,00 TL'], ['24.700.000,00 TL']),
    ('Ticari alacakları hem brüt hem net olarak göster.', 'FINANCE', ['22.500.000,00 TL', '20.400.000,00 TL'], []),
    ('İki görünümün farkını hesapla.', 'FINANCE', ['2.100.000,00 TL'], ['42.900.000,00 TL']),
    ('255 kaydımız varsa diğer şartlar incelenmeden DVT uygunluğu kesinleşir mi?', 'HYBRID', ['hesaplanamaz'], ['uygundur']),
]


def main():
    pipeline = RAGPipeline()
    history, rows = [], []
    for question, channel, required, forbidden in CASES:
        started = time.perf_counter()
        result = pipeline.ask(question, history)
        answer = result['answer']
        passed = result['type'] == channel and all(t in answer for t in required) and not any(t in answer for t in forbidden)
        rows.append({'question': question, 'result': result, 'seconds': round(time.perf_counter()-started, 2),
                     'checks_passed': passed, 'review': 'Content and source association still require review.'})
        Path('review_artifacts/accuracy_variants_20260917.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        history.extend([{'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer,
                       'badge': result['type'], **{k: result[k] for k in ['domain_context', 'finance_views', 'history_result'] if k in result}}])
    raise SystemExit(not all(r['checks_passed'] for r in rows))


if __name__ == '__main__':
    main()
