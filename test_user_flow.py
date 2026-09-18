"""Live end-to-end acceptance flow supplied for evaluation.

These fixtures are never imported by application code and never enter prompts/indexes
except as the user questions being tested.
"""
import re
import json
from pathlib import Path
from time import perf_counter


def contains(answer, *values):
    for value in values:
        assert value.casefold() in answer.casefold(), f"'{value}' yok: {answer}"


def excludes(answer, *values):
    for value in values:
        assert value.casefold() not in answer.casefold(), f"Beklenmeyen '{value}': {answer}"


def run():
    from src.chains import RAGPipeline
    pipeline = RAGPipeline()
    history = []
    records = []
    report = Path('review_artifacts/end_to_end_2026-09-16.json')
    def record(question, result, elapsed, checks):
        errors = []
        for check in checks:
            try:
                check()
            except AssertionError as exc:
                errors.append(str(exc))
        records.append(dict(question=question, result=result, seconds=round(elapsed, 3), errors=errors, passed=not errors))
        report.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    def equal(actual, expected):
        assert actual == expected, f'Expected {expected}, got {actual}'
    cases = [
        ("Trafo merkezleri için amortisman süresi kaç yıldır?", "MEVZUAT", ("20",), ()),
        ("orta gerilim şebeke hatları", "MEVZUAT", ("25",), ("20 yıl",)),
        ("bilgi işlem", "MEVZUAT", ("5",), ("20 yıl", "25 yıl", "10 yıl")),
        ("sayaçlar", "MEVZUAT", ("10",), ("20 yıl", "25 yıl", "5 yıl")),
        ("A grubu bölgelerde kayıp-kaçak hedef üst sınırı nedir?", "MEVZUAT", ("%8",), ()),
        ("b ve c", "MEVZUAT", ("%12", "%18"), ()),
        ("Kasa ve bankalardaki toplam nakit varlığımız nedir?", "FINANCE", ("24.700.000,00 TL",), ()),
        ("2024 yılı toplam genel yönetim gideri ne kadar?", "FINANCE", ("21.200.000,00 TL",), ()),
        ("500 ve 570 topla", "FINANCE", ("68.200.000,00 TL",), ()),
        ("Ticari alacaklarımız ne kadardır?", "FINANCE", ("22.500.000,00 TL", "20.400.000,00 TL"), ()),
        ("253 nolu hesaptaki yatırımlarımızın DVT'ye giriş koşulları nelerdir?", "HYBRID",
         ("205.500.000,00 TL", "işletme", "program", "253/255"), ()),
        ("Kayıp-kaçak geliri hedefin üzerinde mi ve bu bizim gelir tablomuzu nasıl etkiler?", "HYBRID",
         ("%2", "hesaplanamaz"), ("kesin olarak aşı",)),
    ]
    started = perf_counter()
    for index, (question, expected_type, required, forbidden) in enumerate(cases, 1):
        case_started = perf_counter()
        result = pipeline.ask(question, chat_history=history)
        print(f"[{index}] {question}\n{result['type']}: {result['answer']}\n", flush=True)
        record(question, result, perf_counter()-case_started, [
            lambda: equal(result['type'], expected_type),
            lambda: contains(result['answer'], *required),
            lambda: excludes(result['answer'], *forbidden),
            lambda: equal(bool(result.get('sources')), True)])
        history.extend([{"role": "user", "content": question},
                        {"role": "assistant", "content": result["answer"], "badge": result['type']}])

    meta = [
        ("neler konuştuk özetle", ("Soru 1: Trafo", "Soru 12: Kayıp-kaçak")),
        ("1. soruda ne sordum", ("Trafo merkezleri",)),
        ("ondan 2 sonrakinde ne sordum", ("Soru 3:", "bilgi işlem")),
        ("1. sorudaki 3. kelime nedir", ("için",)),
        ("hangi soruda kasa dedim", ("Soru 7:", "Kasa ve bankalardaki")),
    ]
    for offset, (question, required) in enumerate(meta, len(cases) + 1):
        case_started = perf_counter()
        result = pipeline.ask(question, chat_history=history)
        print(f"[{offset}] {question}\n{result['type']}: {result['answer']}\n", flush=True)
        record(question, result, perf_counter()-case_started, [
            lambda: equal(result['type'], 'CHAT_META'), lambda: contains(result['answer'], *required)])
        history.extend([{"role": "user", "content": question},
                        {"role": "assistant", "content": result["answer"], "badge": result["type"],
                         **({"history_result": result["history_result"]} if "history_result" in result else {})}])
    passed = sum(r['passed'] for r in records)
    print(f"{passed}/{len(records)} başarılı; {perf_counter()-started:.2f} sn", flush=True)
    raise SystemExit(passed != len(records))


if __name__ == "__main__":
    run()
