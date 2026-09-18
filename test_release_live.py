"""Opt-in live paraphrase and absent-information release checks."""
import json
import time
from pathlib import Path
from src.chains import RAGPipeline


def main():
    pipeline = RAGPipeline()
    rows = []
    cases = [
        ('Şirketin yönetim faaliyetlerine ait gider toplamı kaç TL?', 'FINANCE', ['21.200.000,00']),
        ('D grubu bölgelerde kayıp-kaçak hedef üst sınırı nedir?', 'MEVZUAT', []),
        ('Trafo merkezleri için bakım aralığı kaç gündür?', 'MEVZUAT', []),
        ('Ticari alacakların brüt mizan tutarı ile net bilanço tutarını karşılaştır.', 'FINANCE', ['22.500.000,00', '20.400.000,00']),
        ('999 numaralı hesabın bakiyesi nedir?', 'FINANCE', []),
    ]
    for question, kind, expected in cases:
        start = time.perf_counter()
        result = pipeline.ask(question, [])
        passed = result['type'] == kind and all(s in result['answer'] for s in expected)
        if not expected:
            passed = (passed and not result.get('raw_data', {}).get('data')
                      and not any(c.isdigit() for c in result['answer'])
                      and any(s in result['answer'].lower() for s in ['bulunma', 'belirtilme', 'bilgi yok']))
        rows.append(dict(question=question, result=result,
                         seconds=round(time.perf_counter()-start, 3), passed=passed))
        Path('review_artifacts/targeted_final_2026-09-16.json').write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(question, passed, flush=True)
    raise SystemExit(not all(row['passed'] for row in rows))


if __name__ == '__main__':
    main()
